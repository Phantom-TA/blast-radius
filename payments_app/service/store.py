"""SQLite storage shared by the payment service and the logic modules."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE
);

CREATE TABLE orders (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    description TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE charges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL REFERENCES orders(id),
    amount_cents INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('succeeded', 'failed', 'refunded')),
    idempotency_key TEXT UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    order_id TEXT NOT NULL REFERENCES orders(id)
);

CREATE TABLE refund_batches (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('pending_approval', 'executed')),
    approved_by TEXT,
    created_at TEXT NOT NULL,
    executed_at TEXT
);

CREATE TABLE refunds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL REFERENCES refund_batches(id),
    customer_id TEXT NOT NULL REFERENCES customers(id),
    order_id TEXT NOT NULL REFERENCES orders(id),
    charge_id INTEGER NOT NULL UNIQUE REFERENCES charges(id),
    amount_cents INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'refunded')),
    refunded_at TEXT,
    emailed_at TEXT
);
"""


def get_db_path() -> str:
    return os.environ.get("BLAST_DB_PATH") or "data/payments.db"


def create_db(db_path: str) -> None:
    """Replace whatever is at db_path with an empty database."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.close()


def connect(db_path: str | None = None, read_only: bool = False) -> sqlite3.Connection:
    """Open an existing database. Writes commit immediately unless inside transaction()."""
    path = Path(db_path or get_db_path())
    if not path.exists():
        raise FileNotFoundError(f"No database at {path}. Run: python run.py seed")
    mode = "ro" if read_only else "rw"
    conn = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode={mode}", uri=True, isolation_level=None, timeout=10
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    """All-or-nothing block that also keeps other writers out until it ends."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
