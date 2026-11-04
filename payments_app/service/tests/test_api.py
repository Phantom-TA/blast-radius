import pytest
from fastapi.testclient import TestClient

from ..api import app
from ..store import connect, create_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "payments.db")
    monkeypatch.setenv("BLAST_DB_PATH", db_path)
    monkeypatch.setenv("PROVIDER_TIMEOUT_RATE", "0")
    create_db(db_path)
    conn = connect(db_path)
    conn.execute("INSERT INTO customers VALUES ('CUS-1', 'Ana Silva', 'ana@example.com')")
    conn.close()
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_order_charges_the_customer(client):
    response = client.post(
        "/orders", json={"customer_id": "CUS-1", "description": "Desk lamp", "amount_cents": 4900}
    )
    assert response.status_code == 201
    order_id = response.json()["order_id"]

    order = client.get(f"/orders/{order_id}").json()
    assert order["customer_id"] == "CUS-1"
    assert [charge["amount_cents"] for charge in order["charges"]] == [4900]


def test_order_ids_count_up(client):
    body = {"customer_id": "CUS-1", "description": "Desk lamp", "amount_cents": 4900}

    assert client.post("/orders", json=body).json()["order_id"] == "ORD-100001"
    assert client.post("/orders", json=body).json()["order_id"] == "ORD-100002"


def test_unknown_customer_is_a_404(client):
    body = {"customer_id": "CUS-404", "description": "Desk lamp", "amount_cents": 4900}

    assert client.post("/orders", json=body).status_code == 404
    assert client.get("/customers/CUS-404").status_code == 404


def test_unknown_order_is_a_404(client):
    assert client.get("/orders/ORD-404").status_code == 404
