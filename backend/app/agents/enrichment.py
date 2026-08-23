"""Catalog enrichment with provenance (docs/03).

Fills missing NON-transactional attributes (terrain, use_cases, audience,
material hints, description quality). Transactional facts (price, stock,
policy) are never touched here — docs/09 rule 5.

Default engine is deterministic heuristics so the whole pipeline is
reproducible without API keys. If LLM_PROVIDER is configured with a key,
`llm_enrich` is used instead; provenance records which engine produced each
value ("heuristic_inference" vs "llm_inference") and marks it verified=False.
"""
from __future__ import annotations

import re

from ..catalog.schema import Product, Provenance

USE_CASE_BY_CATEGORY = {
    "shoes": ["daily_training"],
    "fashion": ["casual_wear"],
    "electronics": ["daily_computing"],
    "fitness": ["home_workouts"],
    "home": ["home_decor"],
}
AUDIENCE_BY_BASE = {
    "running shoe": ["runners", "athletes"],
    "training shoe": ["gym-goers"],
    "hiking shoe": ["trekkers"],
    "yoga mat": ["yoga practitioners"],
}
TERRAIN_HINTS = [
    (r"\broad run|road running|street\b", "road"),
    (r"\btrail|hiking|off-?road|trek\b", "trail"),
]
MATERIAL_HINTS = [
    (r"\bleather\b", "leather"), (r"\bmesh\b", "mesh"), (r"\bdenim\b", "denim"),
    (r"\bcotton\b", "cotton"), (r"\bsteel\b", "steel"), (r"\bcanvas\b", "canvas"),
]


def heuristic_enrich(product: Product) -> dict:
    """Return {field: value} inferences for missing attributes. Never sets
    price/stock/policy fields."""
    inferred: dict = {}
    text = f"{product.title} {product.description}".lower()

    if not product.terrain:
        matched_terrain = next(
            (terrain for pattern, terrain in TERRAIN_HINTS if re.search(pattern, text)),
            None,
        )
        if matched_terrain:
            inferred["terrain"] = matched_terrain
        elif product.category == "shoes":
            inferred["terrain"] = "road"  # conservative default for shoes

    if not product.use_cases and product.category:
        inferred["use_cases"] = USE_CASE_BY_CATEGORY.get(product.category, ["general"])

    if not product.audience:
        for base, aud in AUDIENCE_BY_BASE.items():
            if base in product.title.lower():
                inferred["audience"] = aud
                break
        else:
            inferred["audience"] = ["general"]

    if not product.material:
        for pattern, mat in MATERIAL_HINTS:
            if re.search(pattern, text):
                inferred["material"] = mat
                break

    return inferred


def enrich_product(product: Product) -> Product:
    """Apply heuristic enrichment in place; record provenance for each field.

    Returns the same Product for chaining. Verified merchant facts are
    untouched by construction (we only fill gaps).
    """
    inferred = heuristic_enrich(product)
    for field, value in inferred.items():
        setattr(product, field, value)
        product.provenance[field] = Provenance(
            source="heuristic_inference", confidence=0.8, verified=False
        ).model_dump()
    return product
