"""Payment Links API — the fallback transaction path (docs/08 §3)."""
from __future__ import annotations

import secrets

from . import client


def create_payment_link(quote: dict, description: str = "Agent Commerce order",
                        customer_contact: dict | None = None) -> dict:
    payload: dict = {
        "amount": int(quote["total_paise"]),   # already subunits
        "currency": quote.get("currency", "INR"),
        "accept_partial": False,
        "description": description,
        "reference_id": f"agent_{secrets.token_hex(5)}",
    }
    if customer_contact:
        payload["customer"] = customer_contact

    if client.is_live():
        return client._post("/payment_links", payload)
    return {
        "id": f"plink_mock{secrets.token_hex(7)}",
        "short_url": f"https://rzp.io/i/mock{secrets.token_hex(4)}",
        "amount": payload["amount"],
        "currency": payload["currency"],
        "status": "created",
        "mock": True,
    }
