"""Orders API + payment lifecycle (docs/08 §1, §4).

Amounts ALWAYS come from the DB-derived checkout quote in subunits
(docs/09 rule 2). The LLM never supplies money here — the caller passes a
verified quote from tools.commerce.prepare_checkout.
"""
from __future__ import annotations

import secrets
import time

from . import client


def create_order(quote: dict, receipt: str | None = None,
                 notes: dict | None = None) -> dict:
    """Create a Razorpay order from a verified prepare_checkout quote."""
    from .. import config
    if not quote.get("verification", {}).get("price_verified"):
        raise client.RazorpayError(
            "refusing to create order: price not verified (docs/09 rule 2)")
    if not quote.get("verification", {}).get("inventory_verified"):
        raise client.RazorpayError(
            "refusing to create order: inventory not verified")

    payload = {
        # quote totals are ALREADY subunits; never multiply again
        "amount": int(quote["total_paise"]),
        "currency": quote.get("currency", "INR"),
        "receipt": receipt or f"agent_order_{int(time.time())}",
        "notes": {"source": "agent-commerce", **(notes or {})},
    }

    if client.is_live():
        order = client._post("/orders", payload)
    else:
        # mock mode: same shape as the real API response
        order = {
            "id": f"order_mock{secrets.token_hex(7)}",
            "amount": payload["amount"],
            "currency": payload["currency"],
            "receipt": payload["receipt"],
            "status": "created",
            "mock": True,
        }
    return order


def fetch_order_payments(order_id: str) -> list[dict]:
    """GET /orders/:id/payments — verify payment status server-side (§4)."""
    if client.is_live() and not order_id.startswith("order_mock"):
        data = client._get(f"/orders/{order_id}/payments")
        return data.get("items", [])
    return _mock_payments(order_id)


def _mock_payments(order_id: str) -> list[dict]:
    """Mock store: payments recorded by api/checkout.py simulate_capture."""
    from .. import db  # local import to avoid cycle
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT payment_id, status, amount FROM mock_payments WHERE order_id = ?",
        (order_id,)).fetchall()
    return [dict(r) for r in rows]


def add_mock_payment(order_id: str, status: str = "captured") -> dict:
    from .. import db
    conn = db.get_conn()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS mock_payments (
             payment_id TEXT PRIMARY KEY, order_id TEXT, status TEXT,
             amount INTEGER, created_at TEXT DEFAULT (datetime('now')))"""
    )
    payment = {
        "payment_id": f"pay_mock{secrets.token_hex(7)}",
        "order_id": order_id,
        "status": status,
    }
    conn.execute(
        "INSERT OR REPLACE INTO mock_payments (payment_id, order_id, status) VALUES (?,?,?)",
        (payment["payment_id"], order_id, status))
    conn.commit()
    return payment
