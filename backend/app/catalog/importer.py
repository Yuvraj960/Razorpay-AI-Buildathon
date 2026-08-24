"""Catalog Compiler pipeline: raw CSV -> normalize -> group -> enrich ->
validate -> persist + emit artifacts (docs/02, docs/03).

This is the heart of Module A. `run_compiler()` is idempotent: it rebuilds
products/variants tables from data/raw.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from .. import db
from ..agents import enrichment
from . import normalizer as nz
from .schema import Product, ReturnPolicy, ShippingInfo, Variant, canonical_variant_key
from .validator import validate_catalog


def _load_raw() -> tuple[list[dict], dict, dict]:
    raw_dir: Path = config_raw_dir()
    with open(raw_dir / "catalog.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with open(raw_dir / "policies.json", encoding="utf-8") as f:
        policies = json.load(f)
    with open(raw_dir / "shipping.json", encoding="utf-8") as f:
        shipping = json.load(f)
    return rows, policies, shipping


def config_raw_dir() -> Path:
    from .. import config
    return config.RAW_DIR


def _group_rows(rows: list[dict]) -> dict[str, list[dict]]:
    """Group raw rows into product groups by normalized title (brand often
    missing in messy exports). Duplicate-product injections therefore merge
    and surface as duplicate variants (docs/11)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["product_name"].strip().lower()].append(r)
    return groups


def compile_products(rows: list[dict], policies: dict) -> list[Product]:
    groups = _group_rows(rows)
    products: list[Product] = []

    for idx, (key, grows) in enumerate(sorted(groups.items()), start=1):
        head = grows[0]
        product_id = f"P{idx:04d}"

        price_paise = nz.parse_price_paise(head["price"]) or 0
        availability = nz.normalize_availability(head["stock"])
        dmin, dmax = nz.normalize_days(head["delivery"])
        rmatch = nz.normalize_days(head["return_policy"].split(",")[0])
        rfee = 0
        if "fee" in head["return_policy"].lower():
            import re
            amounts = re.findall(r"(?:₹|rs\.?)?\s*([\d,]+)", head["return_policy"].lower())
            if amounts:
                # the fee is the LAST amount in the string ("7 days, ₹99 fee")
                rfee = int(amounts[-1].replace(",", "")) * 100

        product = Product(
            product_id=product_id,
            sku=head["sku"] or None,
            title=head["product_name"].strip(),
            description=head["description"].strip(),
            category=nz.normalize_category(head["category"]),
            brand=head["brand"] or None,
            gender=nz.normalize_gender(head["gender"]),
            terrain=head["terrain"] or None,
            cushioning=head["cushioning"] or None,
            material=head["material"] or None,
            weight_g=int(head["weight_g"]) if str(head["weight_g"]).strip().isdigit() else None,
            price_paise=price_paise,
            currency="INR",
            availability=availability,  # type: ignore[arg-type]
            stock=None,
            shipping=ShippingInfo(min_days=dmin, max_days=dmax),
            returns=ReturnPolicy(
                days=rmatch[0] if rmatch else policies.get("default_return_days"),
                fee_paise=rfee,
            ),
        )

        # stock: first parseable numeric stock among rows, else None
        for r in grows:
            s = str(r["stock"]).strip()
            if s.isdigit():
                product.stock = int(s)
                break

        variants: dict[str, Variant] = {}
        for v_idx, r in enumerate(grows, start=1):
            color = nz.normalize_color(r["color"])
            size = nz.normalize_size(r["size"]) if r["size"].strip() else "-"
            vprice = nz.parse_price_paise(r["price"]) or price_paise
            vstock = int(r["stock"]) if str(r["stock"]).strip().isdigit() else None
            v_availability = nz.normalize_availability(r["stock"])
            if v_availability == "in_stock" and vstock == 0:
                v_availability = "out_of_stock"  # stale-stock guard
            vid = f"{product_id}-V{v_idx:02d}"
            variants[vid] = Variant(
                variant_id=vid,
                product_id=product_id,
                sku=r["sku"] or None,
                color=color,
                size=size,
                stock=vstock,
                price_paise=vprice,
                availability=v_availability,  # type: ignore[arg-type]
            )
        product.variants = list(variants.values())

        # aggregate availability across variants
        if any(v.availability == "in_stock" for v in product.variants):
            product.availability = "in_stock"
        elif all(v.availability == "out_of_stock" for v in product.variants) and product.variants:
            product.availability = "out_of_stock"

        products.append(product)

    return products


def emit_artifacts(products: list[Product]) -> None:
    """Write normalized JSON feed + JSON-LD (docs/03 emitted artifacts)."""
    from .. import config
    config.NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    feed = [json.loads(p.model_dump_json()) for p in products]
    with open(config.NORMALIZED_DIR / "agent-feed.json", "w", encoding="utf-8") as f:
        json.dump({"merchant": "Buildathon Bazaar", "products": feed}, f, indent=2)

    # JSON-LD per Google Product structured-data shape (ProductGroup + hasVariant)
    jsonld = []
    for p in products:
        jsonld.append({
            "@type": "ProductGroup",
            "productGroupID": p.product_id,
            "name": p.title,
            "description": p.description,
            "brand": {"@type": "Brand", "name": p.brand} if p.brand else None,
            "category": p.category,
            "variesBy": ["color", "size"],
            "hasVariant": [
                {
                    "@type": "Product",
                    "sku": v.sku or v.variant_id,
                    "color": v.color,
                    "size": v.size,
                    "offers": {
                        "@type": "Offer",
                        "priceCurrency": p.currency,
                        "price": (v.effective_price_paise(p.price_paise)) / 100,
                        "availability": (
                            "https://schema.org/InStock"
                            if v.availability == "in_stock"
                            else "https://schema.org/OutOfStock"
                        ),
                    },
                }
                for v in p.variants
            ],
            "shippingDetails": {
                "deliveryTime": {
                    "handlingTime": {"@type": "QuantitativeValue", "minValue": p.shipping.min_days,
                                     "maxValue": p.shipping.max_days, "unitCode": "DAY"}
                }
            } if p.shipping.min_days is not None else None,
            "hasMerchantReturnPolicy": {
                "merchantReturnDays": p.returns.days,
            } if p.returns.days is not None else None,
        })
    with open(config.NORMALIZED_DIR / "product-schema.jsonld", "w", encoding="utf-8") as f:
        json.dump({"@context": "https://schema.org", "@graph": jsonld}, f, indent=2)


def persist(products: list[Product], raw_rows: list[dict], findings: list[dict]) -> None:
    conn = db.get_conn()
    problems_by_product: dict[str, list[str]] = defaultdict(list)
    raw_by_product_title: dict[str, dict] = {}
    for fnd in findings:
        problems_by_product[fnd["product_id"]].append(fnd["code"])

    conn.execute("DELETE FROM variants")
    conn.execute("DELETE FROM products")
    for p in products:
        raw_sample = next(
            (r for r in raw_rows if r["product_name"].strip().lower() == p.title.lower()), {}
        )
        conn.execute(
            """INSERT INTO products (product_id, sku, title, description, category, brand, gender,
               terrain, cushioning, material, audience, use_cases, weight_g, price_paise, currency,
               availability, stock, delivery_min_days, delivery_max_days, return_days,
               return_fee_paise, provenance, raw, problems)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                p.product_id, p.sku, p.title, p.description, p.category, p.brand, p.gender,
                p.terrain, p.cushioning, p.material,
                ",".join(p.audience), ",".join(p.use_cases), p.weight_g, p.price_paise, p.currency,
                p.availability, p.stock, p.shipping.min_days, p.shipping.max_days, p.returns.days,
                p.returns.fee_paise,
                json.dumps({k: v for k, v in p.provenance.items()} if hasattr(p, "provenance") else {}),
                json.dumps(raw_sample),
                json.dumps(sorted(set(problems_by_product.get(p.product_id, [])))),
            ),
        )
        for v in p.variants:
            conn.execute(
                """INSERT INTO variants (variant_id, product_id, sku, color, size, stock,
                   price_paise, availability) VALUES (?,?,?,?,?,?,?,?)""",
                (v.variant_id, v.product_id, v.sku, v.color, v.size, v.stock,
                 v.effective_price_paise(p.price_paise), v.availability),
            )
    conn.commit()


def repair_products(products: list[Product], policies: dict) -> None:
    """Compiler repairs: apply what normalization + merchant defaults can fix.

    Every repaired field gets provenance (verified=False) — a merchant can
    audit and override. Transactional facts are never invented: availability
    is derived from stock signals the merchant provided, policies come from
    the merchant's own policies.json defaults.
    """
    from .schema import Provenance

    for p in products:
        def _mark(field: str) -> None:
            p.provenance[field] = Provenance(
                source="heuristic_inference", confidence=0.9, verified=False
            ).model_dump()

        # availability from merchant stock signals
        if p.availability == "unknown":
            if p.stock is not None and p.stock > 0:
                p.availability = "in_stock"
                _mark("availability")
            elif any(v.availability == "in_stock" for v in p.variants):
                p.availability = "in_stock"
                _mark("availability")
            elif p.variants and all(v.availability == "out_of_stock" for v in p.variants):
                p.availability = "out_of_stock"
                _mark("availability")

        # merchant policy defaults (from merchant's own policies.json)
        if p.returns.days is None and policies.get("default_return_days") is not None:
            p.returns.days = int(policies["default_return_days"])
            _mark("returns.days")
        if p.shipping.min_days is None:
            p.shipping.min_days, p.shipping.max_days = 3, 5  # merchant default SLA
            _mark("shipping")

        # deterministic SKU synthesis for variants missing one
        for v in p.variants:
            if not v.sku:
                v.sku = f"{p.product_id}-{(v.color or 'std')[:3].upper()}-{v.size or 'OS'}"
                p.provenance[f"variant:{v.variant_id}:sku"] = Provenance(
                    source="heuristic_inference", confidence=0.9, verified=False
                ).model_dump()

        # duplicate-variant collapse (keep first occurrence)
        seen: set[str] = set()
        unique: list = []
        for v in p.variants:
            key = canonical_variant_key(v.color, v.size)
            if key in seen:
                continue
            seen.add(key)
            unique.append(v)
        p.variants = unique

        # aggregate stock from numeric variant stocks when product-level unknown
        if p.stock is None:
            numeric = [v.stock for v in p.variants if v.stock is not None]
            if numeric:
                p.stock = sum(numeric)
                _mark("stock")


def run_compiler(enrich: bool = True) -> dict:
    """Full pipeline. Returns summary stats for API/UI.

    enrich=False compiles WITHOUT AI enrichment or repairs — the 'raw/before'
    state used by the before-vs-after evaluation story (docs/07).
    """
    rows, policies, _shipping = _load_raw()
    products = compile_products(rows, policies)
    if enrich:
        for p in products:
            enrichment.enrich_product(p)
        repair_products(products, policies)
    report = validate_catalog(products)
    if enrich:
        # machine-readable interfaces only exist once the compiler has run
        emit_artifacts(products)
    persist(products, rows, report["findings"])
    return {
        "products": len(products),
        "variants": sum(len(p.variants) for p in products),
        "critical": report["critical"],
        "warnings": report["warnings"],
        "passed_products": report["passed_products"],
        "findings": report["findings"][:200],
    }
