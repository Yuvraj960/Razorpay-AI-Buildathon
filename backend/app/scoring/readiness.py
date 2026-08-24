"""Readiness scoring: explicit 8-dimension weighted rubric (docs/06).

Fully deterministic from DB state. Same catalog -> same score, always.

Each penalty-driven dimension scores as `weight x clean_share`, where
clean_share is the fraction of products with zero findings in that dimension.
Enrichment coverage feeds attribute quality; emitted artifacts + tool layer
feed machine readability; verified-price in-stock share feeds transaction.
"""
from __future__ import annotations

import json

from .. import db

# Dimension -> weight (must sum to 100) — published rubric, never arbitrary
DIMENSIONS: dict[str, int] = {
    "product_completeness": 20,
    "attribute_quality": 15,
    "variant_correctness": 10,
    "price_inventory_freshness": 15,
    "shipping_clarity": 10,
    "return_policy_clarity": 10,
    "machine_readable_interfaces": 10,
    "transaction_readiness": 10,
}

# finding code -> dimension it pollutes
CODE_DIMENSION = {
    "missing_title": "product_completeness",
    "missing_price": "product_completeness",
    "zero_price": "product_completeness",
    "missing_category": "product_completeness",
    "missing_variant": "product_completeness",
    "missing_stock": "price_inventory_freshness",
    "ambiguous_availability": "price_inventory_freshness",
    "missing_sku": "attribute_quality",
    "missing_brand": "attribute_quality",
    "missing_color": "attribute_quality",
    "missing_size": "attribute_quality",
    "vague_description": "attribute_quality",
    "duplicate_variant": "variant_correctness",
    "missing_delivery": "shipping_clarity",
    "missing_return_policy": "return_policy_clarity",
}

CRITICAL_CODES = {"missing_title", "missing_price", "zero_price", "missing_category",
                  "missing_variant", "missing_stock"}

BANDS = [(90, "AGENT READY"), (75, "READY WITH WARNINGS"),
         (50, "NEEDS WORK"), (0, "AGENT INVISIBLE")]


def compute_readiness() -> dict:
    conn = db.get_conn()
    products = [dict(r) for r in conn.execute("SELECT * FROM products").fetchall()]
    variants = [dict(r) for r in conn.execute("SELECT * FROM variants").fetchall()]
    n = max(len(products), 1)

    # products' stored finding codes
    problems: dict[str, list[str]] = {
        p["product_id"]: json.loads(p["problems"] or "[]") for p in products
    }

    # --- penalty-driven dimensions: weight x clean_share ---
    dim_dirty: dict[str, int] = {dim: 0 for dim in DIMENSIONS}
    for pid, codes in problems.items():
        dirty_dims = {CODE_DIMENSION[c] for c in codes if c in CODE_DIMENSION}
        for dim in dirty_dims:
            dim_dirty[dim] += 1

    # variant correctness also counts products whose variants can't be resolved
    by_product: dict[str, list[dict]] = {}
    for v in variants:
        by_product.setdefault(v["product_id"], []).append(v)
    for pid, vs in by_product.items():
        if not any(v["color"] and v["size"] and v["color"] != "-" for v in vs):
            if "variant_correctness" not in {CODE_DIMENSION.get(c) for c in problems[pid]}:
                dim_dirty["variant_correctness"] += 1

    scores = {}
    for dim, weight in DIMENSIONS.items():
        if dim in ("machine_readable_interfaces", "transaction_readiness"):
            continue
        scores[dim] = round(weight * (1 - min(1.0, dim_dirty[dim] / n)), 1)

    # --- attribute quality also rewards enrichment coverage ---
    enriched = sum(
        1 for p in products
        if p["terrain"] or p["audience"] or p["use_cases"]
    )
    coverage_bonus = DIMENSIONS["attribute_quality"] * 0.3 * (enriched / n)
    scores["attribute_quality"] = round(
        min(DIMENSIONS["attribute_quality"],
            scores["attribute_quality"] + coverage_bonus), 1)

    # --- machine-readable interfaces: artifacts + tool layer ---
    from .. import config
    feed_ok = (config.NORMALIZED_DIR / "agent-feed.json").exists()
    jsonld_ok = (config.NORMALIZED_DIR / "product-schema.jsonld").exists()
    tools_ok = len(variants) > 0
    scores["machine_readable_interfaces"] = round(
        DIMENSIONS["machine_readable_interfaces"]
        * (0.4 * feed_ok + 0.4 * jsonld_ok + 0.2 * tools_ok), 1)

    # --- transaction readiness: verified price + purchasable now ---
    transactable = sum(
        1 for p in products
        if p["availability"] == "in_stock" and p["price_paise"] > 0
    )
    scores["transaction_readiness"] = round(
        DIMENSIONS["transaction_readiness"] * (transactable / n), 1)

    total = round(sum(scores.values()), 1)
    band = next(label for floor, label in BANDS if total >= floor)

    critical_count = sum(
        1 for codes in problems.values() for c in codes if c in CRITICAL_CODES)
    warning_count = sum(len(codes) for codes in problems.values()) - critical_count

    return {
        "total": total,
        "band": band,
        "dimensions": [
            {"dimension": dim, "score": scores[dim], "weight": w,
             "percent": round(scores[dim] / w * 100)}
            for dim, w in DIMENSIONS.items()
        ],
        "counts": {
            "products": len(products),
            "variants": len(variants),
            "critical": critical_count,
            "warnings": warning_count,
            "passed_products": sum(1 for codes in problems.values() if not codes),
        },
    }
