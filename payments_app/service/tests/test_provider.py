import pytest

from ..provider import FakeProvider, ProviderTimeout
from ..store import connect, create_db


@pytest.fixture
def conn(tmp_path):
    db_path = str(tmp_path / "payments.db")
    create_db(db_path)
    conn = connect(db_path)
    conn.execute("INSERT INTO customers VALUES ('CUS-1', 'Ana Silva', 'ana@example.com')")
    conn.execute(
        "INSERT INTO orders VALUES ('ORD-1', 'CUS-1', 'Desk lamp', 4900, '2026-10-01T10:00:00+00:00')"
    )
    yield conn
    conn.close()


def charge_rows(conn):
    return conn.execute("SELECT * FROM charges").fetchall()


def test_charge_records_a_successful_charge(conn):
    charge_id = FakeProvider(conn).charge("ORD-1", 4900)

    rows = charge_rows(conn)
    assert [row["id"] for row in rows] == [charge_id]
    assert rows[0]["amount_cents"] == 4900
    assert rows[0]["status"] == "succeeded"


def test_timeout_still_records_the_charge(conn):
    provider = FakeProvider(conn, should_timeout=lambda order_id: True)

    with pytest.raises(ProviderTimeout):
        provider.charge("ORD-1", 4900)

    assert len(charge_rows(conn)) == 1


def test_repeat_idempotency_key_returns_the_original_charge(conn):
    provider = FakeProvider(conn)

    first = provider.charge("ORD-1", 4900, idempotency_key="key-1")
    second = provider.charge("ORD-1", 4900, idempotency_key="key-1")

    assert first == second
    assert len(charge_rows(conn)) == 1
