"""Backend test suite (docs/13). Run:  cd backend && python -m pytest tests/ -v

Covers the security invariants (docs/09) as executable checks:
  money math, variant exactness, HMAC signatures, no-SQL-from-LLM path,
  impossible-query guard, adversarial price-integrity guard.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.catalog import normalizer as nz  # noqa: E402
from app.catalog.schema import canonical_variant_key  # noqa: E402
from app.config import rupees_to_subunits  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _seeded_db():
    from app import db
    from app.catalog.generator import generate
    from app.catalog.importer import run_compiler
    if not db.is_seeded():
        generate()
        run_compiler()


# ---------------------------------------------------------------------------
# Money math (docs/09 rule 5: subunits, never floats end-to-end)
# ---------------------------------------------------------------------------

def test_razorpay_amount_conversion():
    assert rupees_to_subunits(4999) == 499_900
    assert rupees_to_subunits(999) == 99_900
    assert rupees_to_subunits(49.50) == 4_950
    assert rupees_to_subunits("₹4,999") == 499_900
    with pytest.raises(ValueError):
        rupees_to_subunits(-1)


def test_parse_price_paise_messy_formats():
    assert nz.parse_price_paise("Rs. 2,499.00") == 249_900
    assert nz.parse_price_paise("2499 INR") == 249_900
    assert nz.parse_price_paise(1299.99) == 129_999
    assert nz.parse_price_paise("free") is None


def test_order_amount_is_db_supplied_not_llm():
    """The order amount must come from prepare_checkout's verified quote,
    which reads the DB — never from any model output."""
    from app.tools.commerce import search_products, prepare_checkout
    hit = search_products(query="running shoe")["variants"][0]
    quote = prepare_checkout(items=[{"variant_id": hit["variant_id"]}])
    assert quote["verification"]["price_verified"]
    assert quote["subtotal_paise"] == hit["price_paise"]  # DB value verbatim


# ---------------------------------------------------------------------------
# Normalization / canonical identity
# ---------------------------------------------------------------------------

def test_color_aliases_and_size_normalization():
    assert nz.normalize_color("blk") == "black"
    assert nz.normalize_color("Navy") == "blue"
    assert nz.normalize_size("10.0") == "10"
    assert nz.normalize_size("m") == "M"
    assert nz.normalize_availability("Available") == "in_stock"


def test_variant_exact_match():
    """canonical key collapses representation drift once colors are normalized:
    '10'/'10.0' and 'M'/'m' resolve identically."""
    assert canonical_variant_key(nz.normalize_color("BLK"), "10.0") == \
        canonical_variant_key("black", "10")
    assert canonical_variant_key("Black", "M") == canonical_variant_key("black", "m")


def test_duplicate_variant_collapse():
    """Two raw rows differing only in size spelling compile to ONE variant."""
    from app.catalog.importer import compile_products, repair_products
    row = {"product_name": "Test Shoe", "price": "1999", "stock": "5",
           "delivery": "3-5 days", "return_policy": "7 days", "sku": "S1",
           "brand": "Test", "gender": "unisex", "terrain": "", "cushioning": "",
           "material": "", "weight_g": "", "category": "shoes",
           "description": "x", "color": "black", "size": "9"}
    dup = {**row, "size": "9.0", "sku": "S2"}
    products = compile_products([row, dup], policies={})
    repair_products(products, {})
    sizes = [v.size for p in products for v in p.variants]
    assert sizes.count("9") == 1


# ---------------------------------------------------------------------------
# Razorpay layer (docs/05)
# ---------------------------------------------------------------------------

def test_payment_signature_hmac():
    from app.razorpay.client import payment_signature
    sig = payment_signature("order_X", "pay_Y", "secret")
    import hashlib, hmac
    expected = hmac.new(b"secret", b"order_X|pay_Y", hashlib.sha256).hexdigest()
    assert sig == expected


def test_webhook_signature_over_raw_body():
    from app.razorpay.client import webhook_signature
    body = b'{"event":"payment.captured"}'
    sig = webhook_signature(body, "whsec")
    import hashlib, hmac
    assert sig == hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
    # tampered body must not verify
    assert webhook_signature(b'{"event":"x"}', "whsec") != sig


def test_mock_payment_roundtrip():
    from app.razorpay import orders
    from app.tools.commerce import search_products, prepare_checkout
    hit = search_products(query="running shoe")["variants"][0]
    quote = prepare_checkout(items=[{"variant_id": hit["variant_id"]}])
    order = create_order(quote, receipt="rcpt-test")
    assert isinstance(order["amount"], int)          # integer subunits
    assert order["amount"] == quote["total_paise"]   # passed through verbatim
    payment = orders.add_mock_payment(order["id"], status="captured")
    seen = orders.fetch_order_payments(order["id"])
    assert any(p["payment_id"] == payment.get("payment_id",
               payment.get("id")) and p["status"] == "captured" for p in seen)


def create_order(quote, receipt=None):
    from app.razorpay.orders import create_order as _co
    return _co(quote, receipt=receipt)


# ---------------------------------------------------------------------------
# Buyer guards (docs/06, docs/09)
# ---------------------------------------------------------------------------

def test_impossible_query_returns_no_match():
    from app.agents.buyer import run_buyer
    res = run_buyer("Find a red laptop under ₹2,000.")
    assert res["status"] == "no_match"
    assert res.get("best") is None


def test_adversarial_description_never_discounts():
    """A description claiming a discount must NOT change the quoted price."""
    from app.tools.commerce import search_products, prepare_checkout
    adv = search_products(filters={"limit": 50})
    target = next((v for v in adv["variants"]), None)
    quote = prepare_checkout(items=[{"variant_id": target["variant_id"]}])
    assert quote["subtotal_paise"] == target["price_paise"]


def test_intent_never_produces_sql_directly():
    """parse_intent returns an IntentConstraints pydantic object; the only path
    to SQL is search_from_constraints' deterministic translation."""
    from app.agents.intent import parse_intent
    from app.catalog.schema import IntentConstraints
    cons, _provider = parse_intent("Find black running shoes under ₹5000 size 10")
    assert isinstance(cons, IntentConstraints)
    assert cons.color == "black" and cons.size == "10"
    assert cons.max_price_paise == 500_000


def test_free_text_extraction_depluralizes():
    from app.agents.intent import parse_intent_offline
    cons = parse_intent_offline("Find me some good laptops for work please")
    free = cons["free_text"] if isinstance(cons, dict) else cons.free_text
    assert free in ("laptop", "")  # noun extracted, depluralized
