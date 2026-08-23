"""Razorpay webhooks (docs/08 §5): payment.captured / payment.failed /
order.paid — HMAC-SHA256 verified over the RAW request body."""
import json
import logging

from fastapi import APIRouter, Header, Request

from ..razorpay import client

logger = logging.getLogger("webhooks")
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

HANDLED_EVENTS = {"payment.captured", "payment.failed", "order.paid"}


@router.post("/razorpay")
async def razorpay_webhook(request: Request,
                           x_razorpay_signature: str = Header(default="")):
    raw = await request.body()  # raw bytes — never verify over parsed JSON

    if not client.verify_webhook_signature(raw, x_razorpay_signature):
        logger.warning("webhook signature verification FAILED")
        return {"error": "invalid_signature"}, 400

    event = json.loads(raw.decode("utf-8", errors="replace"))
    event_type = event.get("event", "unknown")
    payload = (event.get("payload") or {}).get("payment") or \
              (event.get("payload") or {}).get("order") or {}
    entity = payload.get("entity", {})

    if event_type in HANDLED_EVENTS:
        from .. import db
        conn = db.get_conn()
        conn.execute(
            """INSERT INTO audit_log (user_intent, razorpay_order_id, payment_id,
               decision) VALUES (?,?,?,?)""",
            (f"webhook:{event_type}",
             entity.get("order_id"),
             entity.get("id"),
             f"webhook_{event_type.split('.')[1]}"))
        conn.commit()

    return {"status": "handled", "event": event_type}
