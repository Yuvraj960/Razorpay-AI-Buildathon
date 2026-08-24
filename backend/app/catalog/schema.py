"""Canonical commerce schema — the shared Pydantic foundation (docs/03).

Every other module imports from here. The Product/ProductGroup/Variant
structure mirrors Google's structured-data guidance (`ProductGroup` +
`hasVariant`): a product is a group; purchasable units are variants.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Availability = Literal["in_stock", "out_of_stock", "backorder", "unknown"]
ProvenanceSource = Literal["merchant_csv", "merchant_json", "heuristic_inference", "llm_inference"]


class Provenance(BaseModel):
    """Where a field's value came from. AI/heuristic inference must never
    override a verified merchant fact (docs/03, docs/09 rule 5)."""

    source: ProvenanceSource
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    verified: bool = True


class ShippingInfo(BaseModel):
    min_days: Optional[int] = None
    max_days: Optional[int] = None
    free_shipping: Optional[bool] = None


class ReturnPolicy(BaseModel):
    days: Optional[int] = None
    fee_paise: Optional[int] = None  # subunits


class Variant(BaseModel):
    variant_id: str
    product_id: str
    sku: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    stock: Optional[int] = None
    price_paise: Optional[int] = None  # falls back to product price when None
    availability: Availability = "unknown"

    def effective_price_paise(self, product_price_paise: int) -> int:
        return self.price_paise if self.price_paise is not None else product_price_paise


def canonical_variant_key(color: Optional[str], size: Optional[str]) -> str:
    """Canonical key used for exact variant matching.

    The project's canonical failure story is a size-9-vs-size-10 mismatch caused
    by treating numeric sizes as strings; this key normalizes both sides so
    '10' and '10.0' and 10 all resolve identically (docs/13).
    """
    c = (color or "").strip().lower() or "-"
    s_raw = str(size or "").strip().lower()
    try:
        s = str(int(float(s_raw))) if s_raw else "-"
    except ValueError:
        s = s_raw or "-"
    return f"{c}|{s}"


class Product(BaseModel):
    """Canonical product = ProductGroup with variants + policies as first-class objects."""

    product_id: str
    sku: Optional[str] = None
    title: str
    description: str = ""
    category: Optional[str] = None
    brand: Optional[str] = None
    gender: Optional[str] = None
    terrain: Optional[str] = None            # enriched
    cushioning: Optional[str] = None         # enriched
    material: Optional[str] = None           # enriched
    audience: list[str] = Field(default_factory=list)      # enriched
    use_cases: list[str] = Field(default_factory=list)     # enriched
    weight_g: Optional[int] = None
    price_paise: int = 0                     # canonical group price, subunits
    currency: str = "INR"
    availability: Availability = "unknown"
    stock: Optional[int] = None
    shipping: ShippingInfo = Field(default_factory=ShippingInfo)
    returns: ReturnPolicy = Field(default_factory=ReturnPolicy)
    variants: list[Variant] = Field(default_factory=list)
    # field name -> {source, confidence, verified} for AI/heuristic-enriched fields
    provenance: dict[str, dict] = Field(default_factory=dict)

    def find_variant(self, color: Optional[str], size: Optional[str]) -> Optional[Variant]:
        """Exact-match resolution via canonical key — never fuzzy for transactions."""
        want = canonical_variant_key(color, size)
        for v in self.variants:
            if canonical_variant_key(v.color, v.size) == want:
                return v
        return None


# ---------------------------------------------------------------------------
# Buyer-side contracts
# ---------------------------------------------------------------------------

class IntentConstraints(BaseModel):
    """Structured output of intent parsing. The ONLY sanctioned shape that may
    flow from LLM/user language into the query layer (docs/05, docs/09 rule 3)."""

    category: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    brand: Optional[str] = None
    max_price_paise: Optional[int] = None
    terrain: Optional[str] = None
    destination: Optional[str] = None
    delivery_deadline_days: Optional[int] = None   # normalized to relative days
    require_in_stock: bool = False
    free_text: Optional[str] = None                # product nouns for keyword search


class TraceEvent(BaseModel):
    timestamp: str
    stage: str
    detail: str = ""
    candidates_remaining: Optional[int] = None


class CheckoutQuote(BaseModel):
    """Output of prepare_checkout — a verified quote, never a charge (docs/04)."""

    items: list[dict]
    subtotal_paise: int
    shipping_paise: int = 0
    tax_paise: int = 0
    total_paise: int
    currency: str = "INR"
    verification: dict = Field(
        default_factory=lambda: {"price_verified": False, "inventory_verified": False}
    )
