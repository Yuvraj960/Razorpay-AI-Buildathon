"""AI Buyer orchestration pipeline (docs/05).

Fixed stage order, every stage emitting trace events:

    Intent Parser -> Constraint Object -> Catalog Search -> Candidate Set
    -> Constraint Solver -> Policy Validator -> Purchase Planner

Only Intent Parsing may involve an LLM. Everything downstream is deterministic
over the six commerce tools (docs/04). The Razorpay Executor lives in
api/checkout.py — this module stops at a verified quote.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from ..catalog.schema import IntentConstraints, canonical_variant_key
from ..tools import commerce

# intent-level category -> (db category, extra keyword)
CATEGORY_MAP = {
    "running_shoes": ("shoes", "running"),
    "shoes": ("shoes", ""),
    "fashion": ("fashion", ""),
    "electronics": ("electronics", ""),
    "fitness": ("fitness", ""),
    "home": ("home", ""),
}

CITY_PINCODES = {
    "Chandigarh": "160017", "Delhi": "110001", "Mumbai": "400001",
    "Bangalore": "560001", "Kolkata": "700001", "Chennai": "600001",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


_STOPWORDS = {"find", "buy", "get", "me", "the", "for", "under", "below", "size",
              "with", "any", "apply", "discount", "mentioned", "description",
              "ignore", "price", "limit", "most", "expensive", "cheapest",
              "available", "now", "deliverable", "within", "days", "and", "a",
              "an", "of", "to", "in", "my", "need", "want", "please", "show"}


def _significant_words(query: str, limit: int = 6) -> list[str]:
    words = [w.strip(".,!?") for w in query.split()]
    return [w for w in words if len(w) > 2 and w.lower() not in _STOPWORDS][:limit]


class BuyerRun:
    """Accumulates trace events through the fixed pipeline."""

    def __init__(self, query: str):
        self.query = query
        self.run_id = f"run_{uuid.uuid4().hex[:10]}"
        self.trace: list[dict] = []

    def log(self, stage: str, detail: str = "", remaining: int | None = None) -> None:
        self.trace.append({
            "timestamp": _now(), "stage": stage, "detail": detail,
            "candidates_remaining": remaining,
        })


def run_buyer(query: str) -> dict:
    run = BuyerRun(query)

    # ---- Stage 1: Intent Parser (the only LLM-eligible stage) ----
    run.log("parse_intent")
    constraints, engine = _parse(query)
    run.log("extract_constraints", detail=json.dumps(_nonempty(constraints)))

    # ---- Stage 2: Catalog Search (deterministic) ----
    db_cat, extra_kw = CATEGORY_MAP.get(constraints.category or "", (None, ""))
    if constraints.free_text:
        search_query = constraints.free_text
    elif extra_kw:
        search_query = extra_kw
    else:
        # no structured noun — fall back to significant-word OR search
        search_query = ""
    filters: dict = {"any_words": _significant_words(query)} if not search_query else {}
    if db_cat:
        filters["category"] = db_cat
    if constraints.require_in_stock:
        filters["in_stock"] = True
    result = commerce.search_products(search_query, filters or None)
    candidates = result["variants"]
    run.log("search_catalog", detail=f"query='{search_query or query}'", remaining=len(candidates))

    # ---- Stage 3: Constraint Solver (strict funnel, docs/01 layer 3) ----
    if constraints.max_price_paise is not None:
        candidates = [c for c in candidates
                      if c["price_paise"] <= constraints.max_price_paise]
        run.log("apply_price_constraint", remaining=len(candidates))

    hard: list[tuple[str, object]] = []
    if constraints.color:
        hard.append(("color", constraints.color))
    if constraints.size:
        hard.append(("size", constraints.size))
    if constraints.brand:
        hard.append(("brand", constraints.brand))
    if constraints.terrain:
        hard.append(("terrain", constraints.terrain))
    for field, value in hard:
        candidates = [c for c in candidates
                      if str(c.get(field) or "").lower() == str(value).lower()]
        run.log(f"apply_{field}_constraint", remaining=len(candidates))

    # exact-variant sanity: size is matched exactly by canonical key semantics
    if constraints.color and constraints.size:
        candidates = [c for c in candidates
                      if canonical_variant_key(c["color"], c["size"])
                      == canonical_variant_key(constraints.color, constraints.size)]

    if not candidates:
        run.log("no_candidates", detail="constraint set unsatisfiable")
        out = _result(run, constraints, engine, status="no_match",
                      reason="No valid product exists for these constraints.")
        return out

    # ---- Stage 4: Policy Validator ----
    verified: list[dict] = []
    for c in candidates:
        avail = commerce.check_availability(c["product_id"], variant_id=c["variant_id"])
        if not avail.get("available"):
            continue
        c["shipping"] = commerce.get_shipping(
            CITY_PINCODES.get(constraints.destination or "", "110001"),
            delivery_min_days=c["delivery_min_days"],
            delivery_max_days=c["delivery_max_days"],
            subtotal_paise=c["price_paise"],
        )
        if constraints.delivery_deadline_days is not None:
            if c["shipping"]["estimated_max_days"] > constraints.delivery_deadline_days:
                continue
        if constraints.destination and c["return_days"] is None:
            continue  # policy opacity blocks confident decisions
        verified.append(c)
    run.log("verify_inventory_policy", remaining=len(verified))
    if not verified:
        out = _result(run, constraints, engine, status="no_match",
                      reason="All matching products failed inventory/policy verification.")
        return out

    # ---- Stage 5: Product Ranker ----
    verified.sort(key=lambda c: (
        0 if c["availability"] == "in_stock" else 1,
        c["shipping"]["estimated_max_days"],
        c["price_paise"],
    ))
    best = verified[0]
    run.log("rank_products", detail=f"best={best['variant_id']}", remaining=1)

    # ---- Stage 6: Purchase Planner (verified quote, never a charge) ----
    quote = commerce.prepare_checkout(
        items=[{"variant_id": best["variant_id"]}],
        pincode=CITY_PINCODES.get(constraints.destination or "", "") or None,
    )
    run.log("prepare_checkout", detail=json.dumps(quote["verification"]),
            remaining=1 if quote["verification"]["price_verified"] else 0)

    confidence = _confidence(constraints, best)
    return _result(run, constraints, engine, status="match", best=best,
                   alternatives=verified[1:4], quote=quote, confidence=confidence)


# ---------------------------------------------------------------------------

def _parse(query: str) -> tuple[IntentConstraints, str]:
    from .intent import parse_intent
    return parse_intent(query)


def _nonempty(constraints: IntentConstraints) -> dict:
    return {k: v for k, v in constraints.model_dump().items()
            if v not in (None, [], False) and k != "require_in_stock"}


def _confidence(constraints: IntentConstraints, best: dict) -> int:
    """Share of stated constraints the chosen variant verifiably satisfies."""
    checks: list[tuple[str, str]] = []
    if constraints.category:
        checks.append(("category", constraints.category))
    if constraints.color:
        checks.append(("color", constraints.color))
    if constraints.size:
        checks.append(("size", constraints.size))
    if constraints.brand:
        checks.append(("brand", constraints.brand))
    if constraints.terrain:
        checks.append(("terrain", constraints.terrain))
    if not checks:
        return 70
    met = 0
    for field, want in checks:
        have = str(best.get(field) or "").lower()
        if have == str(want).lower():
            met += 1
        elif field == "category" and CATEGORY_MAP.get(str(want), (None, ""))[0] == have:
            met += 1
    return max(50, min(99, round(100 * met / len(checks))))


_RESULT_DEFAULTS = {"alternatives": [], "quote": None, "best": None, "confidence": None}


def _result(run: BuyerRun, constraints: IntentConstraints, engine: str,
            status: str, reason: str = "", **kw) -> dict:
    payload = {**_RESULT_DEFAULTS, **kw}
    result = {
        "run_id": run.run_id,
        "query": run.query,
        "engine": engine,
        "status": status,
        "reason": reason,
        "constraints": constraints.model_dump(),
        "trace": run.trace,
        **payload,
    }
    _persist_run(run, result)
    return result


def _persist_run(run: BuyerRun, result: dict) -> None:
    from .. import db
    conn = db.get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO buyer_runs (run_id, query, trace, result) VALUES (?,?,?,?)",
        (run.run_id, run.query, json.dumps(run.trace), json.dumps(result)),
    )
    conn.commit()
