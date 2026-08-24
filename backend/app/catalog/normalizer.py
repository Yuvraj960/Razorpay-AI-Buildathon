"""Schema normalization: messy merchant values -> canonical (docs/03).

All pure functions, unit-testable:
    "₹4,999"      -> 499900 paise
    "Available"   -> "in_stock"
    "blk"/"Black" -> "black"
"""
from __future__ import annotations

import re
from typing import Optional

COLOR_ALIASES = {
    "blk": "black", "blck": "black", "kala": "black",
    "wht": "white", "safed": "white",
    "blu": "blue", "neela": "blue", "navy": "blue",
    "red": "red", "laal": "red", "maroon": "red",
    "grn": "green", "hara": "green", "olive": "green",
    "gry": "grey", "gray": "grey", "slate": "grey",
    "ylw": "yellow", "peela": "yellow",
    "org": "orange", "narangi": "orange",
    "pnk": "pink", "gulabi": "pink",
    "brn": "brown", "bhura": "brown", "tan": "brown",
    "silvr": "silver", "silver": "silver",
    "multi": "multicolor", "multicolour": "multicolor",
}

STOCK_SYNONYMS = {
    "available": "in_stock", "in stock": "in_stock", "instock": "in_stock",
    "yes": "in_stock", "y": "in_stock", "true": "in_stock", "1": "in_stock",
    "in-stock": "in_stock", "ready": "in_stock",
    "out of stock": "out_of_stock", "oos": "out_of_stock", "sold out": "out_of_stock",
    "no": "out_of_stock", "n": "out_of_stock", "false": "out_of_stock", "0": "out_of_stock",
    "backorder": "backorder", "pre-order": "backorder", "preorder": "backorder",
}

_GENDER = {"men": "men", "mens": "men", "m": "men", "women": "women", "womens": "women",
           "w": "women", "unisex": "unisex", "kids": "kids"}


def normalize_color(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    if s in COLOR_ALIASES:
        return COLOR_ALIASES[s]
    # strip common suffix noise: "matte black", "space grey "
    for token in s.replace("-", " ").split():
        if token in COLOR_ALIASES:
            return COLOR_ALIASES[token]
        if token in {"black", "white", "blue", "red", "green", "grey", "yellow",
                     "orange", "pink", "brown", "purple", "beige", "teal"}:
            return token
    return s


def normalize_availability(raw: Optional[str]) -> str:
    if raw is None:
        return "unknown"
    s = str(raw).strip().lower()
    return STOCK_SYNONYMS.get(s, "unknown")


def normalize_gender(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    return _GENDER.get(str(raw).strip().lower())


def parse_price_paise(raw) -> Optional[int]:
    """Parse messy INR price strings into subunits.

    Handles: 4999 | '₹4,999' | '4999 INR' | 'Rs. 4999' | '4999.50' | '4,999.00'
    Returns paise (subunits). ₹4,999 -> 499900.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(round(float(raw) * 100))
    s = str(raw).strip().lower()
    s = re.sub(r"(inr|rs\.?|rupees|₹)", "", s).strip()
    s = s.replace(",", "").replace(" ", "")
    m = re.search(r"\d+(\.\d+)?", s)
    if not m:
        return None
    value = float(m.group())
    # Heuristic: merchants sometimes write paise already (499900). Treat values
    # >= 100000 as suspicious only when they carry no decimals AND are exact
    # multiples of 100 AND exceed a plausible rupee ceiling — otherwise rupees.
    if value >= 1_000_000 and value % 100 == 0:
        return int(value)  # likely already in paise
    return int(round(value * 100))


def normalize_size(raw) -> Optional[str]:
    """Canonical sizes: numeric sizes lose trailing .0 ('10.0'->'10');
    letter sizes are uppercased ('m'->'M')."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return str(int(float(s.lower())))
    except ValueError:
        return s.upper()


def normalize_days(raw) -> tuple[Optional[int], Optional[int]]:
    """'2-4 days' / '2 to 4' / '3 days' -> (min,max)."""
    if raw is None:
        return None, None
    s = str(raw).strip().lower()
    m = re.search(r"(\d+)\s*(?:-|to|–)\s*(\d+)", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"\d+", s)
    if m:
        d = int(m.group())
        return d, d
    return None, None


def normalize_category(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "footwear": "shoes", "shoe": "shoes", "running_shoes": "running_shoes",
        "apparel": "fashion", "clothing": "fashion",
        "electronics": "electronics", "home": "home", "fitness": "fitness",
    }
    return aliases.get(s, s or None)
