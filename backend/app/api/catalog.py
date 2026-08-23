"""Catalog + readiness API (docs/03, docs/06)."""
from fastapi import APIRouter

from ..agents.enrichment import heuristic_enrich
from ..catalog.importer import run_compiler
from ..catalog.schema import Product, ReturnPolicy, ShippingInfo
from ..scoring.readiness import compute_readiness
from ..tools import commerce

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _product_from_row(row: dict) -> Product:
    return Product(
        product_id=row["product_id"], sku=row["sku"], title=row["title"],
        description=row["description"] or "", category=row["category"],
        brand=row["brand"], gender=row["gender"], terrain=row["terrain"],
        cushioning=row["cushioning"], material=row["material"],
        audience=(row.get("audience") or "").split(",") if row.get("audience") else [],
        use_cases=(row.get("use_cases") or "").split(",") if row.get("use_cases") else [],
        weight_g=row.get("weight_g"), price_paise=row["price_paise"],
        currency=row["currency"], availability=row["availability"],
        stock=row.get("stock"),
        shipping=ShippingInfo(min_days=row["delivery_min_days"],
                              max_days=row["delivery_max_days"]),
        returns=ReturnPolicy(days=row["return_days"], fee_paise=row["return_fee_paise"]),
    )


@router.get("/products")
def list_products(limit: int = 50, offset: int = 0):
    from .. import db
    conn = db.get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT product_id, title, category, brand, price_paise, availability, stock,"
        " delivery_min_days, delivery_max_days, return_days, problems"
        " FROM products ORDER BY product_id LIMIT ? OFFSET ?", (limit, offset))]
    total = conn.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
    for r in rows:
        r["problems"] = [c for c in (r.pop("problems") or "[]").strip("[]").replace('"', '').split(",")
                         if c.strip()]
    return {"total": total, "products": rows}


@router.get("/products/{product_id}")
def get_product(product_id: str):
    return commerce.get_product(product_id)


@router.post("/import")
def import_catalog():
    """Run the full compiler pipeline over data/raw (docs/02)."""
    return run_compiler()


@router.get("/readiness")
def readiness():
    score = compute_readiness()
    # before/after: also show what raw (pre-enrichment) state looked like is
    # handled by eval; here we expose current compiled-state scoring only.
    return score


@router.get("/findings/{product_id}")
def findings(product_id: str):
    from .. import db
    conn = db.get_conn()
    row = conn.execute("SELECT problems FROM products WHERE product_id = ?",
                       (product_id,)).fetchone()
    if not row:
        return {"error": "not found"}
    import json as _json
    codes = _json.loads(row["problems"] or "[]")
    return {"product_id": product_id, "findings": codes}
