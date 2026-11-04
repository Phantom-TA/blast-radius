import pytest

from payments_app.service.store import connect, create_db

CUSTOMERS = [
    ("CUS-1", "Ana Silva", "ana@example.com"),
    ("CUS-2", "Ben Okafor", "ben@example.com"),
    ("CUS-3", "Chen Wei", "chen@example.com"),
    ("CUS-4", "Dara Khan", "dara@example.com"),
]

# order id, customer, amount, statuses of its charges in the order they happened
ORDERS = [
    ("ORD-1", "CUS-1", 4900, ["succeeded", "succeeded"]),  # double charged, complained
    ("ORD-2", "CUS-2", 10900, ["succeeded", "succeeded"]),  # double charged, silent
    ("ORD-3", "CUS-3", 2900, ["succeeded", "succeeded", "succeeded"]),  # charged three times
    ("ORD-4", "CUS-4", 2400, ["succeeded"]),  # charged once
    ("ORD-5", "CUS-4", 2400, ["succeeded"]),  # same customer and amount, separate order
    ("ORD-6", "CUS-4", 3900, ["failed", "succeeded"]),  # declined, then paid once
]


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "payments.db")
    monkeypatch.setenv("BLAST_DB_PATH", path)
    create_db(path)
    conn = connect(path)
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?)", CUSTOMERS)
    for order_id, customer_id, amount_cents, statuses in ORDERS:
        conn.execute(
            "INSERT INTO orders VALUES (?, ?, 'Test item', ?, '2026-10-01T10:00:00+00:00')",
            (order_id, customer_id, amount_cents),
        )
        for status in statuses:
            conn.execute(
                "INSERT INTO charges (order_id, amount_cents, status, created_at) "
                "VALUES (?, ?, ?, '2026-10-01T10:00:00+00:00')",
                (order_id, amount_cents, status),
            )
    conn.execute("INSERT INTO complaints (customer_id, order_id) VALUES ('CUS-1', 'ORD-1')")
    conn.close()
    return path
