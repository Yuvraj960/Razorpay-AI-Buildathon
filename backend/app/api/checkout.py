"""Checkout API: verified quote -> Razorpay Order -> Checkout -> server-side
signature verification -> payment status (docs/08, docs/09 audit trail)."""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import db
from ..razorpay import client, orders, payment_links
from ..tools import commerce

router = APIRouter(prefix="/api/checkout", tags=["checkout"])


class QuoteRequest(BaseModel):
    items: list[dict] = Field(..., description="[{variant_id}] or [{sku}] or "
                               "[{product_id, color, size}]")
    pincode: str | None = None


class OrderRequest(QuoteRequest):
    pass


class VerifyRequest(BaseModel):
    order_id: str
    payment_id: str
    signature: str


class PaymentLinkRequest(QuoteRequest):
    description: str = "Agent Commerce order"


def _audit(**kw) -> None:
    conn = db.get_conn()
    conn.execute(
        """INSERT INTO audit_log (user_intent, selected_product, selected_variant,
           price_verified, inventory_verified, shipping_verified, policy_verified,
           razorpay_order_id, payment_id, decision)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (kw.get("user_intent"), kw.get("selected_product"), kw.get("selected_variant"),
         int(bool(kw.get("price_verified"))), int(bool(kw.get("inventory_verified"))),
         int(bool(kw.get("shipping_verified"))), int(bool(kw.get("policy_verified"))),
         kw.get("razorpay_order_id"), kw.get("payment_id"), kw.get("decision", "approved")))
    conn.commit()


@router.post("/quote")
def quote(request: QuoteRequest):
    """prepare_checkout exposed over REST — verified quote, never a charge."""
    return commerce.prepare_checkout(request.items, request.pincode)


@router.post("/order")
def create_order(request: OrderRequest):
    """Server-side order creation (docs/08 §1). Amount comes from the DB via
    prepare_checkout — request body carries only item identifiers."""
    q = commerce.prepare_checkout(request.items, request.pincode)
    if not q["verification"]["price_verified"] or not q["verification"]["inventory_verified"]:
        return {"error": "verification_failed", "quote": q}
    try:
        order = orders.create_order(
            q, notes={"product_id": q["items"][0]["product_id"] if q["items"] else ""})
    except client.RazorpayError as e:
        return {"error": "razorpay_error", "detail": str(e)}
    _audit(selected_product=q["items"][0]["product_id"] if q["items"] else None,
           selected_variant=q["items"][0].get("variant_id") if q["items"] else None,
           price_verified=q["verification"]["price_verified"],
           inventory_verified=q["verification"]["inventory_verified"],
           razorpay_order_id=order["id"], decision="order_created")
    return {"order": order, "quote": q,
            "mode": "live" if client.is_live() else "mock",
            "public_key_id": client.public_key_id()}


@router.post("/verify")
def verify_payment(request: VerifyRequest):
    """Server-side signature verification (docs/08 §2)."""
    ok = client.verify_payment_signature(
        request.order_id, request.payment_id, request.signature)
    payments = orders.fetch_order_payments(request.order_id)
    captured = any(p["status"] in ("captured", "authorized") for p in payments) \
        if payments else False
    _audit(razorpay_order_id=request.order_id, payment_id=request.payment_id,
           decision="verified" if ok and captured else "rejected")
    return {
        "signature_verified": ok,
        "payment_status": payments[0]["status"] if payments else "unknown",
        "captured": captured,
        "evidence": {
            "order_created": True,
            "payment_received": bool(payments),
            "signature_verified": ok,
            "status_verified": captured,
        },
    }


@router.post("/payment-link")
def payment_link(request: PaymentLinkRequest):
    q = commerce.prepare_checkout(request.items, request.pincode)
    if not q["verification"]["price_verified"]:
        return {"error": "verification_failed", "quote": q}
    link = payment_links.create_payment_link(q, request.description)
    return {"payment_link": link, "quote": q}


@router.post("/mock/capture")
def mock_capture(order_id: str):
    """Mock-mode helper: simulates the gateway capturing a test payment so the
    full verify chain is demonstrable without live credentials."""
    if client.is_live():
        return {"error": "mock endpoints disabled in live mode"}
    payment = orders.add_mock_payment(order_id, status="captured")
    sig = client.payment_signature(order_id, payment["payment_id"])
    return {"payment": payment, "signature": sig}
