"""Deterministic catalog validation — findings feed the readiness score (docs/06).

Pure functions over canonical Product objects. No LLM involvement ever.
"""
from __future__ import annotations

from collections import Counter

from .schema import Product

# Finding codes are stable identifiers consumed by scoring/readiness.py
CRITICAL_CODES = {
    "missing_title", "missing_price", "missing_stock", "missing_category",
    "missing_variant", "zero_price",
}
WARNING_CODES = {
    "missing_sku", "missing_brand", "missing_color", "missing_size",
    "missing_delivery", "missing_return_policy", "ambiguous_availability",
    "duplicate_variant", "vague_description",
}


def validate_product(product: Product) -> list[dict]:
    """Return list of {code, severity, product_id, detail} findings."""
    findings: list[dict] = []

    def add(code: str, severity: str, detail: str = "") -> None:
        findings.append({
            "code": code, "severity": severity,
            "product_id": product.product_id, "detail": detail,
        })

    if not product.title.strip():
        add("missing_title", "critical")
    if product.price_paise <= 0:
        add("missing_price" if product.price_paise == 0 else "zero_price", "critical")
    if product.availability == "unknown":
        # cannot even determine stock semantics — transaction-blocking
        add("missing_stock", "critical")
        add("ambiguous_availability", "warning")
    elif product.stock is None:
        # purchasable but count unknown — agent can still transact
        add("ambiguous_availability", "warning")
    if not product.category or product.category in ("general", "uncategorized"):
        add("missing_category", "critical")
    if not product.variants:
        add("missing_variant", "critical")
    if product.shipping.min_days is None or product.shipping.max_days is None:
        add("missing_delivery", "warning")
    if product.returns.days is None:
        add("missing_return_policy", "warning")

    if not any(v.sku for v in product.variants):
        if not product.sku:
            add("missing_sku", "warning")

    if not product.brand:
        add("missing_brand", "warning")

    if all(v.color is None for v in product.variants):
        add("missing_color", "warning")
    sized = [v for v in product.variants if v.size not in (None, "-", "")]
    if product.variants and not sized and _expects_sizes(product.category):
        add("missing_size", "warning")

    key_counts = Counter(
        f"{(v.color or '').lower()}|{(v.size or '').lower()}" for v in product.variants
    )
    for key, n in key_counts.items():
        if n > 1:
            add("duplicate_variant", "warning", f"{n}x variant '{key}'")

    if len(product.description.strip()) < 40:
        add("vague_description", "warning")

    return findings


def _expects_sizes(category: str | None) -> bool:
    return category in ("shoes", "fashion")


def validate_catalog(products: list[Product]) -> dict:
    all_findings: list[dict] = []
    for p in products:
        all_findings.extend(validate_product(p))
    by_severity = Counter(f["severity"] for f in all_findings)
    return {
        "findings": all_findings,
        "critical": by_severity.get("critical", 0),
        "warnings": by_severity.get("warning", 0),
        # products with zero findings count as passed
        "passed_products": sum(
            1 for p in products
            if not any(f["product_id"] == p.product_id for f in all_findings)
        ),
        "total_products": len(products),
    }
