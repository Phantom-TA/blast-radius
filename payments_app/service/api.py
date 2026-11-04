"""HTTP API for the fake payment service."""

import os
import random
from contextlib import closing
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .charge_client import ChargeFailed, charge_order
from .provider import FakeProvider
from .store import connect, transaction

app = FastAPI(title="Payments Service")


class NewOrder(BaseModel):
    customer_id: str
    description: str
    amount_cents: int = Field(gt=0)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/customers/{customer_id}")
def get_customer(customer_id: str):
    with closing(connect(read_only=True)) as conn:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "customer not found")
    return dict(row)


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    with closing(connect(read_only=True)) as conn:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if order is None:
            raise HTTPException(404, "order not found")
        charges = conn.execute(
            "SELECT id, amount_cents, status, created_at FROM charges "
            "WHERE order_id = ? ORDER BY id",
            (order_id,),
        ).fetchall()
    return {**dict(order), "charges": [dict(charge) for charge in charges]}


@app.post("/orders", status_code=201)
def create_order(new_order: NewOrder):
    timeout_rate = float(os.environ.get("PROVIDER_TIMEOUT_RATE", "0.05"))
    with closing(connect()) as conn:
        if not conn.execute(
            "SELECT 1 FROM customers WHERE id = ?", (new_order.customer_id,)
        ).fetchone():
            raise HTTPException(404, "customer not found")
        with transaction(conn):
            last = conn.execute("SELECT MAX(id) AS id FROM orders").fetchone()["id"]
            number = int(last.removeprefix("ORD-")) + 1 if last else 100001
            order_id = f"ORD-{number}"
            conn.execute(
                "INSERT INTO orders (id, customer_id, description, amount_cents, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    order_id,
                    new_order.customer_id,
                    new_order.description,
                    new_order.amount_cents,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
        provider = FakeProvider(conn, should_timeout=lambda _: random.random() < timeout_rate)
        try:
            charge_id = charge_order(provider, order_id, new_order.amount_cents)
        except ChargeFailed as error:
            raise HTTPException(502, str(error))
    return {"order_id": order_id, "charge_id": charge_id}
