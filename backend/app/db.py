"""SQLite access layer. Module A owns the schema (AGENTS.md §3)."""
import sqlite3
import threading
from pathlib import Path

from . import config

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    product_id      TEXT PRIMARY KEY,
    sku             TEXT,
    title           TEXT NOT NULL,
    description     TEXT,
    category        TEXT,
    brand           TEXT,
    gender          TEXT,
    terrain         TEXT,            -- enriched: road|trail|mixed
    cushioning      TEXT,            -- enriched: high|medium|low
    material        TEXT,            -- enriched
    audience        TEXT,            -- enriched: csv string
    use_cases       TEXT,            -- enriched: csv string
    weight_g        INTEGER,
    price_paise     INTEGER NOT NULL DEFAULT 0,   -- canonical price in subunits
    currency        TEXT NOT NULL DEFAULT 'INR',
    availability    TEXT NOT NULL DEFAULT 'unknown',
    stock           INTEGER,
    delivery_min_days INTEGER,
    delivery_max_days INTEGER,
    return_days     INTEGER,
    return_fee_paise INTEGER,
    provenance      TEXT NOT NULL DEFAULT '{}',   -- json: field -> {source, confidence, verified}
    raw             TEXT NOT NULL DEFAULT '{}',   -- original messy row for before/after
    problems        TEXT NOT NULL DEFAULT '[]'    -- json list of validator finding codes
);

CREATE TABLE IF NOT EXISTS variants (
    variant_id   TEXT PRIMARY KEY,
    product_id   TEXT NOT NULL REFERENCES products(product_id),
    sku          TEXT,
    color        TEXT,
    size         TEXT,
    stock        INTEGER,
    price_paise  INTEGER,
    availability TEXT NOT NULL DEFAULT 'unknown'
);

CREATE TABLE IF NOT EXISTS buyer_runs (
    run_id      TEXT PRIMARY KEY,
    query       TEXT,
    trace       TEXT NOT NULL DEFAULT '[]',   -- json list of trace events
    result      TEXT NOT NULL DEFAULT '{}',   -- final buyer result object
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT DEFAULT (datetime('now')),
    user_intent  TEXT,
    selected_product TEXT,
    selected_variant TEXT,
    price_verified    INTEGER,
    inventory_verified INTEGER,
    shipping_verified INTEGER,
    policy_verified   INTEGER,
    razorpay_order_id TEXT,
    payment_id        TEXT,
    decision          TEXT
);

CREATE INDEX IF NOT EXISTS idx_variants_product ON variants(product_id);
CREATE INDEX IF NOT EXISTS idx_variants_color_size ON variants(color, size);
"""


def _db_path() -> Path:
    url = config.DATABASE_URL
    if url.startswith("sqlite:///"):
        return Path(url[len("sqlite:///"):])
    return config.DATA_DIR / "app.db"


def get_conn() -> sqlite3.Connection:
    """Per-thread connection; SQLite + FastAPI threadpool safety."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        path = _db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        conn.commit()
        _local.conn = conn
    return conn


def reset_db() -> None:
    conn = get_conn()
    for table in ("variants", "products", "buyer_runs", "audit_log", "mock_payments"):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.executescript(SCHEMA)
    conn.commit()


def is_seeded() -> bool:
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) AS n FROM products").fetchone()
    return row["n"] > 0
