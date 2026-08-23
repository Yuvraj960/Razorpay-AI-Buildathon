"""Central configuration — everything comes from environment variables.

Never hard-code provider names, model names, or keys in code (AGENTS.md rule 7).
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    # Load repo-root .env if present (works for local dev and docker alike)
    _root = Path(__file__).resolve().parents[2]
    load_dotenv(_root / ".env")
except ImportError:  # pragma: no cover - dotenv is a hard dep, but be safe
    pass


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


LLM_PROVIDER = _env("LLM_PROVIDER", "offline")          # offline | openai | gemini
LLM_MODEL = _env("LLM_MODEL")

OPENAI_API_KEY = _env("OPENAI_API_KEY")
GEMINI_API_KEY = _env("GEMINI_API_KEY")

RAZORPAY_KEY_ID = _env("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = _env("RAZORPAY_KEY_SECRET")       # SERVER ONLY
RAZORPAY_WEBHOOK_SECRET = _env("RAZORPAY_WEBHOOK_SECRET")
RAZORPAY_MODE = _env("RAZORPAY_MODE", "mock")           # live | mock

DATABASE_URL = _env("DATABASE_URL", "sqlite:///./data/app.db")
CATALOG_SEED = int(_env("CATALOG_SEED", "42") or "42")

BACKEND_URL = _env("BACKEND_URL", "http://localhost:8000")

# Repo layout anchors
BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
NORMALIZED_DIR = DATA_DIR / "normalized"
TEST_CASES_DIR = DATA_DIR / "test_cases"
EVAL_DIR = REPO_ROOT / "eval"

# Razorpay amounts are ALWAYS currency subunits: ₹4,999 -> 499900
SUBUNIT_FACTOR = 100


def rupees_to_subunits(amount) -> int:
    """Convert an INR amount to paise (subunits). Accepts numbers or messy
    merchant strings ('₹4,999'). Regression-tested."""
    if isinstance(amount, str):
        from .catalog.normalizer import parse_price_paise
        paise = parse_price_paise(amount)
        if paise is None:
            raise ValueError(f"unparseable amount: {amount!r}")
        return paise
    value = float(amount)
    if value < 0:
        raise ValueError(f"negative amount not allowed: {amount}")
    return int(round(value * SUBUNIT_FACTOR))
