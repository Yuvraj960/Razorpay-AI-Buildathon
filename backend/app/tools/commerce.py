"""The six deterministic merchant tools (docs/04).

One service layer, three transports: REST (api/), MCP (mcp-server/), and the
AI Buyer pipeline. NO LLM anywhere in this module — grep-able guarantee:
the only imports are stdlib + our db/schema.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

from ..catalog.schema import CheckoutQuote, IntentConstraints, canonical_variant_key

MAX_LIMIT = 50


def _rows(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


# ---------------------------------------------------------------------------
# Tool 1 — search_products(query, filters)
# ---------------------------------------------------------------------------

def search_products(query: str = "", filters: Optional[dict] = None) -> dict:
    filters = filters or {}
    conn = _conn()

    where = ["1=1"]
    args: list[Any] = []

    if query.strip():
        like = f"%{query.strip().lower()}%"
        where.append("(LOWER(p.title) LIKE ? OR LOWER(p.description) LIKE ? "
                     "OR LOWER(p.category) LIKE ? OR LOWER(p.brand) LIKE ?)")
        args += [like, like, like, like]
    elif filters.get("any_words"):
        # token OR-match against the title; ranking happens downstream
        words = [str(w).lower() for w in filters["any_words"]][:6]
        conds = [f"LOWER(p.title) LIKE ?" for _ in words]
        where.append("(" + " OR ".join(conds) + ")")
        args += [f"%{w}%" for w in words]

    if filters.get("category"):
        where.append("p.category = ?")
        args.append(filters["category"])
    if filters.get("color"):
        where.append("v.color = ?")
        args.append(filters["color"])
    if filters.get("size"):
        where.append("v.size = ?")
        args.append(str(filters["size"]))
    if filters.get("brand"):
        where.append("LOWER(p.brand) = ?")
        args.append(str(filters["brand"]).lower())
    if filters.get("terrain"):
        where.append("p.terrain = ?")
        args.append(filters["terrain"])
    if filters.get("max_price_paise") is not None:
        where.append("COALESCE(v.price_paise, p.price_paise) <= ?")
        args.append(int(filters["max_price_paise"]))
    if filters.get("min_price_paise") is not None:
        where.append("COALESCE(v.price_paise, p.price_paise) >= ?")
        args.append(int(filters["min_price_paise"]))
    if filters.get("in_stock"):
        where.append("v.availability = 'in_stock' AND COALESCE(v.stock, 1) > 0")

    rows = _rows(conn, f"""
        SELECT v.variant_id, v.product_id, v.sku AS variant_sku, v.color, v.size,
               v.stock, v.availability,
               COALESCE(v.price_paise, p.price_paise) AS price_paise,
               p.title, p.description, p.category, p.brand, p.gender, p.terrain,
               p.cushioning, p.material, p.audience, p.use_cases,
               p.delivery_min_days, p.delivery_max_days,
               p.return_days, p.return_fee_paise
        FROM variants v JOIN products p ON p.product_id = v.product_id
        WHERE {' AND '.join(where)}
        ORDER BY CASE WHEN v.availability = 'in_stock' THEN 0 ELSE 1 END,
                 COALESCE(v.price_paise, p.price_paise) ASC
        LIMIT ?
    """, tuple(args) + (min(int(filters.get("limit", MAX_LIMIT)), MAX_LIMIT),))

    return {"count": len(rows), "variants": [_flatten(r) for r in rows]}


def _conn() -> sqlite3.Connection:
    from .. import db
    return db.get_conn()


def _flatten(r: dict) -> dict:
    out = dict(r)
    out["audience"] = (r.get("audience") or "").split(",") if r.get("audience") else []
    out["use_cases"] = (r.get("use_cases") or "").split(",") if r.get("use_cases") else []
    return out


# ---------------------------------------------------------------------------
# Tool 2 — get_product(product_id)
# ---------------------------------------------------------------------------

def get_product(product_id: str) -> dict:
    conn = _conn()
    prow = conn.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone()
    if not prow:
        return {"error": f"product not found: {product_id}"}
    p = dict(prow)
    p["variants"] = _rows(conn, "SELECT * FROM variants WHERE product_id = ?", (product_id,))
    p["provenance"] = json.loads(p.pop("provenance", "{}"))
    p["problems"] = json.loads(p.pop("problems", "[]"))
    p.pop("raw", None)
    return p


# ---------------------------------------------------------------------------
# Tool 3 — check_availability(product_id, variant_id?)  [DB, never LLM]
# ---------------------------------------------------------------------------

def check_availability(product_id: str, variant_id: str | None = None,
                       color: str | None = None, size: str | None = None) -> dict:
    conn = _conn()
    if variant_id:
        row = conn.execute(
            "SELECT * FROM variants WHERE product_id = ? AND variant_id = ?",
            (product_id, variant_id)).fetchone()
    elif color and size:
        want = canonical_variant_key(color, size)
        candidates = _rows(conn, "SELECT * FROM variants WHERE product_id = ?", (product_id,))
        row = next(
            (c for c in candidates
             if canonical_variant_key(c["color"], c["size"]) == want), None)
        row = dict(row) if row else None  # type: ignore[assignment]
    else:
        rows = _rows(conn, "SELECT * FROM variants WHERE product_id = ?", (product_id,))
        in_stock = [r for r in rows if r["availability"] == "in_stock" and (r["stock"] or 0) > 0]
        return {"product_id": product_id, "available": bool(in_stock),
                "in_stock_variants": len(in_stock), "total_variants": len(rows)}
    if not row:
        return {"product_id": product_id, "available": False, "reason": "variant_not_found"}
    row = dict(row)
    # stock count may be unknown (None) — trust the availability signal then
    available = row["availability"] == "in_stock" and (
        row["stock"] is None or row["stock"] > 0)
    return {**row, "available": available}


# ---------------------------------------------------------------------------
# Tools 4 & 5 — get_shipping / get_return_policy
# ---------------------------------------------------------------------------

def get_shipping(pincode: str, delivery_min_days: int | None = None,
                 delivery_max_days: int | None = None,
                 free_shipping_threshold_paise: int = 50000,
                 subtotal_paise: int = 0) -> dict:
    """Pincode-prefix based estimate merged with product delivery window."""
    from .. import config
    shipping_file = config.RAW_DIR / "shipping.json"
    zones = json.loads(shipping_file.read_text(encoding="utf-8")) if shipping_file.exists() else {}
    prefix = next((z for z in sorted(zones, key=len, reverse=True) if pincode.startswith(z)), None)
    zone = zones.get(prefix) if prefix else None

    est_min = max(delivery_min_days or 0, zone["min_days"]) if zone else (delivery_min_days or 5)
    est_max = max(delivery_max_days or 0, zone["max_days"]) if zone else (delivery_max_days or 7)
    fee = zone["fee_paise"] if zone else 5900
    if subtotal_paise >= free_shipping_threshold_paise > 0:
        fee = 0
    return {
        "pincode": pincode,
        "zone_city": zone["city"] if zone else "unmapped",
        "estimated_min_days": est_min,
        "estimated_max_days": est_max,
        "shipping_fee_paise": fee,
    }


def get_return_policy(product_id: str) -> dict:
    p = get_product(product_id)
    if "error" in p:
        return p
    days = p.get("return_days")
    fee = p.get("return_fee_paise") or 0
    if days is None:
        return {"product_id": product_id, "policy": "unknown",
                "detail": "merchant has not published a machine-readable return policy"}
    return {
        "product_id": product_id, "policy": "returnable" if days > 0 else "final_sale",
        "return_days": days, "return_fee_paise": fee,
    }


# ---------------------------------------------------------------------------
# Tool 6 — prepare_checkout(cart)  [verified quote; NEVER charges money]
# ---------------------------------------------------------------------------

def prepare_checkout(items: list[dict], pincode: str | None = None) -> dict:
    """items: [{variant_id}] or [{product_id, color, size}]. All prices come
    from the DB (docs/09 rule 2). Returns a verified quote."""
    conn = _conn()
    quote_items: list[dict] = []
    price_verified = True
    inventory_verified = True
    problems: list[str] = []

    for item in items:
        variant = _resolve_item(conn, item)
        if not variant:
            inventory_verified = False
            problems.append(f"variant not found for {item}")
            continue
        prow = conn.execute(
            "SELECT price_paise, title, availability FROM products WHERE product_id = ?",
            (variant["product_id"],)).fetchone()
        if not prow:
            price_verified = False
            problems.append(f"product missing for {variant['variant_id']}")
            continue
        unit_price = variant["price_paise"] if variant["price_paise"] is not None \
            else prow["price_paise"]
        if unit_price is None or unit_price <= 0:
            price_verified = False
            problems.append(f"unverifiable price for {variant['variant_id']}")
        if variant["availability"] != "in_stock" or (
                variant["stock"] is not None and variant["stock"] <= 0):
            inventory_verified = False
            problems.append(f"{variant['variant_id']} not in stock")

        quote_items.append({
            "variant_id": variant["variant_id"],
            "product_id": variant["product_id"],
            "title": prow["title"],
            "color": variant["color"], "size": variant["size"],
            "sku": variant["sku"],
            "unit_price_paise": unit_price,
            "quantity": 1,
        })

    subtotal = sum(i["unit_price_paise"] * i["quantity"] for i in quote_items)
    ship: dict = {"shipping_fee_paise": 0}
    if pincode:
        ship = get_shipping(pincode, subtotal_paise=subtotal)

    quote = CheckoutQuote(
        items=quote_items,
        subtotal_paise=subtotal,
        shipping_paise=ship.get("shipping_fee_paise", 0),
        total_paise=subtotal + ship.get("shipping_fee_paise", 0),
        verification={"price_verified": price_verified and bool(quote_items),
                      "inventory_verified": inventory_verified},
    )
    out = quote.model_dump()
    out["problems"] = problems
    return out


def _resolve_item(conn: sqlite3.Connection, item: dict) -> Optional[dict]:
    if item.get("variant_id"):
        row = conn.execute("SELECT * FROM variants WHERE variant_id = ?",
                           (item["variant_id"],)).fetchone()
        return dict(row) if row else None
    if item.get("sku"):
        row = conn.execute("SELECT * FROM variants WHERE sku = ?", (item["sku"],)).fetchone()
        return dict(row) if row else None
    if item.get("product_id") and (item.get("color") or item.get("size")):
        want = canonical_variant_key(item.get("color"), item.get("size", "-"))
        for cand in _rows(conn, "SELECT * FROM variants WHERE product_id = ?",
                          (item["product_id"],)):
            if canonical_variant_key(cand["color"], cand["size"]) == want:
                return cand
    return None


# Convenience wrapper used by the buyer pipeline ----------------------------

def search_from_constraints(query: str, c: IntentConstraints) -> dict:
    """Deterministic translation of a validated constraint object into tool
    filters. This is the ONLY sanctioned path from intent to SQL (docs/09 rule 3).
    """
    filters: dict[str, Any] = {"limit": MAX_LIMIT}
    if c.category:
        filters["category"] = c.category
    if c.color:
        filters["color"] = c.color
    if c.size:
        filters["size"] = c.size
    if c.brand:
        filters["brand"] = c.brand
    if c.terrain:
        filters["terrain"] = c.terrain
    if c.require_in_stock:
        filters["in_stock"] = True
    return search_products(query=query, filters=filters)


TOOL_SPECS = [
    {"name": "search_products",
     "description": "Search the merchant catalog by query text and structured filters.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"},
         "filters": {"type": "object"}}}},
    {"name": "get_product",
     "description": "Fetch the full canonical product including variants.",
     "input_schema": {"type": "object", "properties": {
         "product_id": {"type": "string"}, "required": ["product_id"]}}},
    {"name": "check_availability",
     "description": "Check stock for a product/variant directly against the database.",
     "input_schema": {"type": "object", "properties": {
         "product_id": {"type": "string"}, "variant_id": {"type": "string"},
         "color": {"type": "string"}, "size": {"type": "string"}}}},
    {"name": "get_shipping",
     "description": "Delivery estimate and fee for a destination pincode.",
     "input_schema": {"type": "object", "properties": {"pincode": {"type": "string"}}}},
    {"name": "get_return_policy",
     "description": "Machine-readable return policy for a product.",
     "input_schema": {"type": "object", "properties": {
         "product_id": {"type": "string"}, "required": ["product_id"]}}},
    {"name": "prepare_checkout",
     "description": "Build a price/inventory-verified checkout quote. Never charges.",
     "input_schema": {"type": "object", "properties": {
         "items": {"type": "array", "items": {"type": "object"}},
         "pincode": {"type": "string"}}}},
]

TOOL_IMPLS = {
    "search_products": lambda **kw: search_products(kw.get("query", ""), kw.get("filters")),
    "get_product": lambda **kw: get_product(kw["product_id"]),
    "check_availability": lambda **kw: check_availability(
        kw["product_id"], kw.get("variant_id"), kw.get("color"), kw.get("size")),
    "get_shipping": lambda **kw: get_shipping(kw["pincode"]),
    "get_return_policy": lambda **kw: get_return_policy(kw["product_id"]),
    "prepare_checkout": lambda **kw: prepare_checkout(kw.get("items", []), kw.get("pincode")),
}


def call_tool(name: str, arguments: dict) -> dict:
    """Single dispatch entrypoint shared by REST API and MCP server."""
    if name not in TOOL_IMPLS:
        return {"error": f"unknown tool: {name}"}
    try:
        return TOOL_IMPLS[name](**arguments)
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}
