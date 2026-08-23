"""Intent parsing: natural language -> validated IntentConstraints (docs/05).

Order of engines:
  1. Configured LLM provider (if any) — semantic interpretation.
  2. Deterministic offline parser — always available, reproducible.

The offline parser deliberately does NOT parse imperative instructions
("ignore the price limit...") — it only extracts shopping constraints. That is
the behavioral prompt-injection defense tested by adversarial eval tasks.
"""
from __future__ import annotations

import re

from ..catalog.schema import IntentConstraints
from . import llm

CATEGORY_KEYWORDS = {
    "running_shoes": [r"running shoe", r"runners", r"running"],
    "shoes": [r"\bshoe\b", r"\bsneaker\b", r"footwear"],
    "fashion": [r"\bshirt\b", r"\bjacket\b", r"\bbackpack\b"],
    "electronics": [r"\blaptop\b", r"headphone", r"\bmouse\b", r"keyboard", r"monitor"],
    "fitness": [r"yoga mat", r"resistance band", r"water bottle", r"\bfitness\b"],
    "home": [r"\blamp\b", r"office chair", r"cookware"],
}

COLORS = ["black", "white", "blue", "red", "green", "grey", "gray", "yellow",
          "orange", "pink", "brown", "purple", "silver", "navy", "olive", "multi"]

TERRAINS = {"road": r"\broad\b", "trail": r"\btrail|hiking|trek\b"}

CITIES = {
    "chandigarh": "Chandigarh", "delhi": "Delhi", "mumbai": "Mumbai",
    "bangalore": "Bangalore", "bengaluru": "Bangalore", "kolkata": "Kolkata",
    "chennai": "Chennai", "pune": "Pune", "hyderabad": "Hyderabad",
}


def _extract_max_price_paise(query: str) -> int | None:
    m = re.search(
        r"(?:under|below|less than|upto|up to|max(?:imum)?)\s*(?:₹|rs\.?|inr)?\s*"
        r"([\d,]+(?:\.\d+)?)\s*(k)?", query, re.IGNORECASE)
    if not m:
        # bare forms: "below 5k", "budget 5000"
        m = re.search(r"(?:₹|rs\.?)?\s*([\d,]+)\s*k\b", query, re.IGNORECASE)
        if m:
            return int(float(m.group(1).replace(",", "")) * 100_000)
        return None
    value = float(m.group(1).replace(",", ""))
    if m.group(2):  # '5k'
        value *= 1000
    return int(value * 100)


def _extract_size(query: str) -> str | None:
    m = re.search(r"\bsize\s*(\w{1,4})\b", query, re.IGNORECASE)
    if m:
        raw = m.group(1)
        try:
            return str(int(float(raw)))
        except ValueError:
            return raw.upper()
    return None


def _extract_deadline_days(query: str) -> int | None:
    m = re.search(r"within\s+(\d+)\s*day", query, re.IGNORECASE)
    if m:
        return int(m.group(1))
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    m = re.search(r"before\s+(?:next\s+)?(" + "|".join(weekdays) + r")", query, re.IGNORECASE)
    if m:
        from datetime import date, timedelta
        target = weekdays.index(m.group(1).lower())
        today = date.today().weekday()
        delta = (target - today) % 7 or 7
        return delta + 1  # must ARRIVE before that day
    if re.search(r"asap|immediately|today", query, re.IGNORECASE):
        return 1
    return None


PRODUCT_NOUNS = [
    "running shoes", "running shoe", "training shoes", "hiking shoes",
    "sneakers", "shoes", "shirts", "jackets", "backpacks",
    "headphones", "keyboards", "mice", "monitors", "laptops",
    "yoga mats", "resistance bands", "water bottles",
    "lamps", "office chairs", "cookware",
]
# singular fallbacks when plural forms miss
_NOUN_SINGULAR = {"shoes": "shoe", "laptops": "laptop", "headphones": "headphones",
                  "backpacks": "backpack", "jackets": "jacket", "shirts": "shirt"}


_IRREGULAR_SINGULAR = {"mice": "mouse"}


def _depluralize(noun: str) -> str:
    """'laptops' -> 'laptop', 'mice' -> 'mouse' — titles are singular."""
    if noun in _IRREGULAR_SINGULAR:
        return _IRREGULAR_SINGULAR[noun]
    words = [w[:-1] if w.endswith("s") and len(w) > 3 else w
             for w in noun.split()]
    return " ".join(words)


def _extract_free_text(q: str) -> str | None:
    """Product nouns present in the request — feeds keyword search.
    Output is de-pluralized for LIKE matching against product titles."""
    found = [n for n in PRODUCT_NOUNS if n in q]
    if not found:
        return None
    # longest phrase wins per family to avoid 'shoes' duplicating 'running shoes'
    found.sort(key=len, reverse=True)
    kept_orig: list[str] = []
    kept_out: list[str] = []
    for n in found:
        if not any(n in k for k in kept_orig):
            kept_orig.append(n)
            kept_out.append(_depluralize(n))
    return " ".join(kept_out)


def parse_intent_offline(query: str) -> dict:
    q = query.lower()
    out: dict = {}

    free_text = _extract_free_text(q)
    if free_text:
        out["free_text"] = free_text

    for category, patterns in CATEGORY_KEYWORDS.items():
        if any(re.search(p, q) for p in patterns):
            # "running shoes" refines generic "shoes"
            out["category"] = "running_shoes" if category == "shoes" and \
                re.search(r"run", q) else category
            break

    for color in COLORS:
        if re.search(rf"\b{color}\b", q):
            out["color"] = "grey" if color == "gray" else color
            break

    size = _extract_size(q)
    if size:
        out["size"] = size

    price = _extract_max_price_paise(q)
    if price:
        out["max_price_paise"] = price

    for terrain, pattern in TERRAINS.items():
        if re.search(pattern, q):
            out["terrain"] = terrain
            break

    for name, city in CITIES.items():
        if re.search(rf"\b{name}\b", q):
            out["destination"] = city
            break

    days = _extract_deadline_days(q)
    if days:
        out["delivery_deadline_days"] = days

    if re.search(r"in stock|available now|available today", q):
        out["require_in_stock"] = True

    m = re.search(r"\bby\s+(nike|adidas|puma|velocity|zephyr|krafton|auroro|himali)\b", q)
    if m:
        out["brand"] = m.group(1)

    return out


def parse_intent(query: str) -> tuple[IntentConstraints, str]:
    """Returns (constraints, engine_used). LLM first, deterministic fallback."""
    engine = "offline"
    parsed = llm.llm_parse_intent(query)
    if parsed is None:
        parsed = parse_intent_offline(query)
    else:
        engine = config_engine()

    # Defensive normalization: LLM output passes through the same validation;
    # anything unparseable is dropped rather than trusted.
    cleaned = IntentConstraints(**{
        k: v for k, v in parsed.items()
        if k in IntentConstraints.model_fields and v is not None
    })
    return cleaned, engine


def config_engine() -> str:
    from .. import config
    return f"{config.LLM_PROVIDER}:{config.LLM_MODEL}" if config.LLM_MODEL \
        else config.LLM_PROVIDER
