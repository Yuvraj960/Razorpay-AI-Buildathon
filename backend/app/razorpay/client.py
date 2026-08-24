"""Razorpay API client (docs/08).

Test Mode in live operation. RAZORPAY_MODE=mock simulates the order/payment
lifecycle locally so the demo runs without credentials; signature verification
is identical in both modes (real HMAC math against the configured secret).
"""
from __future__ import annotations

import hashlib
import hmac

import requests

from .. import config

API_BASE = "https://api.razorpay.com/v1"


class RazorpayError(Exception):
    pass


def is_live() -> bool:
    return config.RAZORPAY_MODE == "live" and bool(
        config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET)


def _auth() -> tuple[str, str]:
    if not (config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET):
        raise RazorpayError("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not configured")
    return config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET


def _post(path: str, payload: dict) -> dict:
    key_id, secret = _auth()
    resp = requests.post(
        f"{API_BASE}{path}", json=payload, auth=(key_id, secret), timeout=30)
    if resp.status_code >= 400:
        raise RazorpayError(f"{path} -> {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _get(path: str) -> dict:
    key_id, secret = _auth()
    resp = requests.get(f"{API_BASE}{path}", auth=(key_id, secret), timeout=30)
    if resp.status_code >= 400:
        raise RazorpayError(f"{path} -> {resp.status_code}: {resp.text[:300]}")
    return resp.json()


# --- signature utilities (shared by checkout callback + webhooks) ----------

def payment_signature(order_id: str, payment_id: str, secret: str | None = None) -> str:
    """HMAC-SHA256 over 'order_id|payment_id' — what Checkout returns and what
    the server must recompute (docs/08 §2)."""
    msg = f"{order_id}|{payment_id}"
    key = (secret or config.RAZORPAY_KEY_SECRET or "mock_secret").encode()
    return hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()


def verify_payment_signature(order_id: str, payment_id: str,
                             received_signature: str) -> bool:
    expected = payment_signature(order_id, payment_id)
    return hmac.compare_digest(expected, received_signature or "")


def webhook_signature(raw_body: bytes, secret: str | None = None) -> str:
    """HMAC-SHA256 over the RAW request body — never over parsed JSON."""
    key = (secret or config.RAZORPAY_WEBHOOK_SECRET or "mock_webhook_secret").encode()
    return hmac.new(key, raw_body, hashlib.sha256).hexdigest()


def verify_webhook_signature(raw_body: bytes, received: str,
                             secret: str | None = None) -> bool:
    expected = webhook_signature(raw_body, secret)
    return hmac.compare_digest(expected, received or "")


def public_key_id() -> str:
    """The only credential safe for the frontend (docs/09 rule 1)."""
    return config.RAZORPAY_KEY_ID or "rzp_test_mock"
