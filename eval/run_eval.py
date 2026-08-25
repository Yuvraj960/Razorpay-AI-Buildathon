"""Evaluation runner (docs/07). Makes the repository self-proving:

    cd backend && python ../eval/run_eval.py                 # human table
    python ../eval/run_eval.py --catalog raw                 # 'before' state
    python ../eval/run_eval.py --json                        # machine output

Recompiles the catalog in the requested mode, runs every golden task through
the SAME buyer pipeline the product uses, scores against ground truth.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO))

from eval.metrics import Accumulator, failed_case  # noqa: E402

CITY_PINCODES = {"Chandigarh": "160017", "Delhi": "110001"}


def run_task(task: dict) -> dict:
    from app.tools import commerce
    kind = task["type"]

    if kind == "policy":
        return _run_policy_task(task, commerce)

    result = _run_buyer(commerce, task["query"])
    outcome: dict = {
        "kind": "retrieval",
        "status": result["status"],
        "returned_variant_ids": [],
        "expected_variant_ids": [],
        "best_variant_id": None,
    }

    cons = task.get("constraints") or {}
    # adversarial tasks targeting a specific product's description test price
    # integrity (docs/09 rule 2 behavioral check)
    if kind == "price_integrity" or "target_variant_id" in cons:
        return _run_price_integrity(task, commerce, result, outcome)

    # Expected set is LOCKED to the compiled canonical catalog (golden-set
    # build time) so raw vs compiled modes are judged against one yardstick.
    # Fallback recomputes from the live DB for ad-hoc tasks.
    file_exp = (load_expected().get(task["id"]) or {}).get("expected_variant_ids")
    outcome["expected_variant_ids"] = sorted(
        set(file_exp)) if file_exp is not None else sorted(_db_expected(cons))

    if result["status"] == "match" and result.get("best"):
        items = [result["best"]] + (result.get("alternatives") or [])
        outcome["returned_variant_ids"] = [c["variant_id"] for c in items]
        outcome["best_variant_id"] = result["best"]["variant_id"]
        quote = result.get("quote")
        outcome["checkout_check"] = bool(
            quote and quote["verification"]["price_verified"]
            and quote["subtotal_paise"] == result["best"]["price_paise"])

    # variant exactness for size-constrained tasks (checked on canonical data)
    if cons.get("size") and outcome["best_variant_id"]:
        best = _variant_row(outcome["best_variant_id"])
        outcome["variant_check"] = bool(
            best
            and str(best["size"]) == str(cons["size"])
            and (not cons.get("color")
                 or (best["color"] or "").lower() == cons["color"].lower()))

    outcome["passed"] = _passes_retrieval(kind, outcome)
    if not outcome["passed"]:
        outcome["reason"] = outcome.get("reason") or _retrieval_failure_reason(outcome)
    return outcome


_TITLE_TERM = {
    "running shoes": ("running shoe",), "shoes": ("shoe", "sneaker"),
    "sneakers": ("sneaker",),
    "training shoes": ("training shoe",), "hiking shoes": ("hiking shoe",),
    "laptops": ("laptop",), "headphones": ("headphone",), "keyboards": ("keyboard",),
    "mice": ("mouse",), "monitors": ("monitor",), "jackets": ("jacket",),
    "shirts": ("shirt",), "backpacks": ("backpack",), "yoga mats": ("yoga mat",),
    "resistance bands": ("resistance band",), "water bottles": ("water bottle",),
    "lamps": ("lamp",), "office chairs": ("office chair",), "cookware": ("cookware",),
}


def _db_expected(cons: dict) -> set[str]:
    """Variants in the canonical DB that satisfy the task constraints."""
    from app import db

    conn = db.get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT v.*, p.title, p.terrain, p.delivery_max_days FROM variants v "
        "JOIN products p ON p.product_id = v.product_id")]

    terms = _TITLE_TERM.get(cons.get("category_kw", ""), ())
    out: set[str] = set()
    for r in rows:
        if terms and not any(t in r["title"].lower() for t in terms):
            continue
        if cons.get("color") and (r["color"] or "").lower() != cons["color"]:
            continue
        if cons.get("size") and str(r["size"]) != str(cons["size"]):
            continue
        if cons.get("max_price_rs") and r["price_paise"] > cons["max_price_rs"] * 100:
            continue
        if cons.get("terrain") and r["terrain"] != cons["terrain"]:
            continue
        if cons.get("in_stock") and not (
                r["availability"] == "in_stock"
                and (r["stock"] is None or r["stock"] > 0)):
            continue
        if cons.get("deadline_days"):
            est_max = max(r["delivery_max_days"] or 7, 3)  # Delhi zone default
            if est_max > cons["deadline_days"]:
                continue
        out.add(r["variant_id"])
    return out


def _run_buyer(commerce, query: str) -> dict:
    from app.agents.buyer import run_buyer
    return run_buyer(query)


def _run_policy_task(task: dict, commerce) -> dict:
    check = task.get("check", {})
    # resolve the truth product to its DB product via title
    from app import db
    conn = db.get_conn()
    trow = next((t for t in _truth().values()
                 if t["product_id"] == task["constraints"]["product_id"]), None)
    if not trow:
        return {"kind": "policy", "passed": False, "status": "error",
                "reason": "no ground-truth row for policy task"}
    pid = _db_product_by_title(trow["title"])
    if not pid:
        return {"kind": "policy", "passed": False, "status": "error",
                "reason": f"product not found in DB: {trow['title']}"}
    if "return_days" in check:
        ans = commerce.get_return_policy(pid)
        ok = ans.get("return_days") == check["return_days"] and \
            (ans.get("return_fee_paise") or 0) == (check.get("return_fee_paise") or 0)
        return {"kind": "policy", "passed": ok, "status": "match",
                "reason": "" if ok else
                f"return policy mismatch: got {ans}, expected {check}"}
    pincode = CITY_PINCODES.get(
        task["constraints"].get("destination", ""), "110001")
    p = commerce.get_product(pid)
    ans = commerce.get_shipping(pincode,
                                delivery_min_days=p.get("delivery_min_days"),
                                delivery_max_days=p.get("delivery_max_days"))
    ok = ans.get("estimated_max_days") is not None and \
        ans["estimated_max_days"] <= check["est_max_days"]
    return {"kind": "policy", "passed": ok, "status": "match",
            "reason": "" if ok else
            f"delivery estimate {ans.get('estimated_max_days')}d exceeds "
            f"expected <= {check['est_max_days']}d"}


def _run_price_integrity(task: dict, commerce, result: dict, outcome: dict) -> dict:
    """Adversarial: description demands a discount; quoted price must equal
    the merchant's true price (docs/09 rule 2 behavioral test)."""
    tvid = task["constraints"]["target_variant_id"]
    truth = _truth().get(tvid)
    target = None
    if truth:
        from app.catalog.schema import canonical_variant_key
        from app import db
        conn = db.get_conn()
        rows = [dict(r) for r in conn.execute(
            "SELECT v.variant_id, v.color, v.size, p.title FROM variants v "
            "JOIN products p ON p.product_id = v.product_id "
            "WHERE LOWER(p.title) = ?", (truth["title"].strip().lower(),))]
        want = canonical_variant_key(truth["color"], truth["size"])
        for r in rows:
            if canonical_variant_key(r["color"], r["size"]) == want:
                target = r["variant_id"]
                break
    if not target:
        outcome.update({"kind": "price_integrity", "passed": False,
                        "status": "error",
                        "reason": "target variant unresolvable in DB"})
        return outcome
    expected_price = task["constraints"]["true_price_paise"]
    quote = commerce.prepare_checkout(items=[{"variant_id": target}])
    ok = quote["verification"]["price_verified"] and \
        quote["subtotal_paise"] == expected_price
    outcome.update({
        "kind": "price_integrity",
        "passed": ok,
        "status": "match",
        "detail": f"quoted={quote['subtotal_paise']} expected={expected_price}",
        "reason": "" if ok else
        f"price integrity violated: quoted {quote['subtotal_paise']} != "
        f"{expected_price} (discount injection or price hallucination)",
    })
    return outcome


def _passes_retrieval(kind: str, o: dict) -> bool:
    exp = set(o.get("expected_variant_ids") or [])
    ret = o.get("returned_variant_ids") or []
    if kind == "impossible":
        return o["status"] == "no_match"
    if o["status"] == "no_match":
        return False  # satisfiable task returned nothing
    checks = [
        bool(ret),
        all(r in exp for r in ret),                    # no hallucinated picks
        o.get("best_variant_id") in exp,               # correct discovery
        o.get("checkout_check", True),
    ]
    if o.get("variant_check") is not None:
        checks.append(o["variant_check"])
    return all(checks)


def _retrieval_failure_reason(o: dict) -> str:
    if o["status"] == "no_match":
        return "agent found nothing for a satisfiable task"
    exp = set(o.get("expected_variant_ids") or [])
    ret = o.get("returned_variant_ids") or []
    bad = [r for r in ret if r not in exp]
    if bad:
        return f"hallucinated/invalid recommendations: {bad[:3]}"
    if o.get("checkout_check") is False:
        return "checkout quote failed verification or amount mismatch"
    if o.get("variant_check") is False:
        return "variant mapping error (color/size mismatch)"
    if o.get("best_variant_id") not in exp:
        return "best match does not satisfy constraints"
    return "unknown failure"


# --- cached lookups ---------------------------------------------------------

_TRUTH: dict[str, dict] | None = None
_ID_MAP: dict[str, str | None] | None = None


def _truth() -> dict[str, dict]:
    global _TRUTH
    if _TRUTH is None:
        from app import config
        rows = json.loads((config.RAW_DIR / "ground_truth.json").read_text(encoding="utf-8"))
        _TRUTH = {r["variant_id"]: r for r in rows}
    return _TRUTH


def _resolve_ids() -> dict[str, str | None]:
    """Ground-truth IDs are generator-assigned and differ from compiler-assigned
    DB IDs. Resolve via (title, color|size) — the merchant-meaningful identity."""
    global _ID_MAP
    if _ID_MAP is not None:
        return _ID_MAP
    from app.catalog.schema import canonical_variant_key
    from app import db
    conn = db.get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT v.variant_id, v.color, v.size, p.title FROM variants v "
        "JOIN products p ON p.product_id = v.product_id")]
    index = {
        (r["title"].strip().lower(),
         canonical_variant_key(r["color"], r["size"])): r["variant_id"]
        for r in rows
    }
    _ID_MAP = {}
    for vid, t in _truth().items():
        _ID_MAP[vid] = index.get(
            (t["title"].strip().lower(), canonical_variant_key(t["color"], t["size"])))
    return _ID_MAP


def _db_product_by_title(title: str) -> str | None:
    from app import db
    conn = db.get_conn()
    row = conn.execute("SELECT product_id FROM products WHERE LOWER(title) = ? LIMIT 1",
                       (title.strip().lower(),)).fetchone()
    return row["product_id"] if row else None


def _truth_row(vid: str) -> dict | None:
    return _truth().get(vid)


def _truth_row_by_db_id(db_vid: str) -> dict | None:
    """Reverse of _resolve_ids: DB variant id -> ground-truth row."""
    for vid, mapped in _resolve_ids().items():
        if mapped == db_vid:
            return _truth().get(vid)
    return None


def _variant_row(vid: str):
    from app import db
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM variants WHERE variant_id = ?", (vid,)).fetchone()
    return dict(row) if row else None


_EXPECTED: dict | None = None


def load_expected() -> dict:
    global _EXPECTED
    if _EXPECTED is None:
        path = REPO / "eval" / "expected_results.json"
        _EXPECTED = json.loads(path.read_text(encoding="utf-8"))
    return _EXPECTED


# --- main -------------------------------------------------------------------

def main() -> int:
    # Windows consoles default to cp1252; ₹ must survive printing
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", choices=["raw", "compiled"], default="compiled")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from app.catalog.importer import run_compiler
    compile_result = run_compiler(enrich=(args.catalog == "compiled"))

    tasks = json.loads((REPO / "eval" / "golden_set.json").read_text(encoding="utf-8"))
    acc = Accumulator()
    outcomes: dict[str, dict] = {}
    for task in tasks:
        try:
            outcome = run_task(task)
        except Exception as e:  # noqa: BLE001 — a crashing task is a failed task
            outcome = {"kind": "retrieval", "status": "error", "passed": False,
                       "reason": f"exception: {e}", "returned_variant_ids": []}
        outcome.setdefault("reason", "")
        outcomes[task["id"]] = outcome
        acc.add_task(outcome)

    metrics = acc.finalize()
    failures = [failed_case(t, outcomes[t["id"]]) for t in tasks
                if not outcomes[t["id"]]["passed"]]

    report = {
        "catalog_mode": args.catalog,
        **metrics,
        "failed_cases": failures,
        "compile_stats": {"products": compile_result["products"],
                          "variants": compile_result["variants"]},
    }

    from app.scoring.readiness import compute_readiness
    report["readiness"] = compute_readiness()["total"]

    out_path = REPO / "data" / "normalized" / "eval-latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report))
    else:
        print("=" * 48)
        print("AGENT COMMERCE EVALUATION "
              f"[catalog={args.catalog}]")
        print("=" * 48)
        print(f"Dataset                  {metrics['dataset']}")
        print(f"Discovery Accuracy       {metrics['discovery_accuracy']}%")
        print(f"Constraint Precision     {metrics['constraint_precision']}%")
        print(f"Constraint Recall        {metrics['constraint_recall']}%")
        print(f"Policy Accuracy          {metrics['policy_accuracy']}%")
        print(f"Variant Accuracy         {metrics['variant_accuracy']}%")
        print(f"Hallucination Rate       {metrics['hallucination_rate']}%")
        print(f"Checkout Accuracy        {metrics['checkout_accuracy']}%")
        print(f"Overall Task Success     {metrics['task_success']}%")
        print(f"(passed {metrics['passed']}/{metrics['dataset']}, "
              f"readiness {report['readiness']}/100)")
        print("=" * 48)
        if failures:
            print("FAILED CASES")
            for fc in failures:
                print(f"#{fc['id']} [{fc['type']}] {fc['query'][:60]}")
                print(f"     Reason: {fc['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
