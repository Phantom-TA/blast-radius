"""Rebuild the database from a fixed random seed. Every run produces identical data.

Orders go through the real charge client, so the double charges in the data are
produced by the actual retry behaviour, not inserted by hand.
"""

import json
import random
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from payments_app.blast import find_affected_customers, summarize
from payments_app.service.charge_client import charge_order
from payments_app.service.provider import FakeProvider
from payments_app.service.store import connect, create_db, get_db_path, transaction

SEED = 20261104
ORDER_COUNT = 2000
CUSTOMER_COUNT = 1400
AFFECTED_CUSTOMERS = 313
DECLINED_ORDERS = 40
START = datetime(2026, 10, 1, tzinfo=timezone.utc)
DAYS = 30
RETRY_GAP = timedelta(seconds=20)

COMPLAINER_FILE = Path(__file__).parent / "complainer.json"

FIRST_NAMES = """
Aarav Abigail Adaeze Aisha Akira Alejandro Amara Amelia Ananya Andre Anika Arjun Astrid Ben
Bianca Bo Camila Carlos Chen Chloe Daniel Daria David Diego Divya Elena Eli Emeka Emma Erik
Esther Fatima Felix Gabriel Grace Hana Hannah Hugo Ibrahim Imani Ines Isaac Ivan Jada James
Javier Jin Julia Kai Karim Kavya Keiko Kofi Lars Layla Leo Lina Lucas Maya Mateo Mei Mia
Miguel Mina Nadia Naomi Nikhil Noah Nora Oliver Omar Priya Rafael Rahul Rosa Sam Sara Sofia
Tariq Tessa Thabo Tomas Uma Victor Wei Yara Yuki Zainab Zoe
""".split()

LAST_NAMES = """
Abadi Adeyemi Agarwal Ahmed Almeida Andersen Bauer Becker Bhatt Brown Cabrera Campbell Chen
Costa Das Dubois Eriksson Evans Fernandez Fischer Garcia Gupta Haddad Hansen Hernandez Hoang
Ibrahim Iyer Jackson Jensen Johnson Kaur Khan Kim Kowalski Kumar Larsen Lee Lopez Maina Martin
Mehta Mensah Meyer Miller Mohamed Moreau Murphy Nakamura Nguyen Novak Nwosu Okafor Olsen Ortiz
Park Patel Pereira Petrov Reddy Reyes Rossi Rahman Santos Sato Schmidt Sharma Silva Singh
Smith Sokolov Suzuki Tanaka Taylor Torres Tran Vargas Verma Wagner Walker Wang Weber Wilson
Wong Yamamoto Yilmaz Zhang
""".split()

PRODUCTS = [
    ("USB-C charger", 2400),
    ("Wireless mouse", 2900),
    ("Laptop stand", 3900),
    ("Desk lamp", 4900),
    ("Mechanical keyboard", 8900),
    ("Noise-cancelling headphones", 14900),
    ("Webcam", 6900),
    ("Monitor arm", 7900),
    ("Backpack", 5900),
    ("Office chair cushion", 3400),
    ("Portable SSD", 10900),
    ("Annual software licence", 12000),
]

EMAIL_DOMAINS = ["example.com", "example.org", "example.net"]


def build_customers(rng: random.Random) -> list[dict]:
    customers = []
    seen = {}
    for index in range(CUSTOMER_COUNT):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        handle = f"{first}.{last}".lower()
        seen[handle] = seen.get(handle, 0) + 1
        suffix = seen[handle] if seen[handle] > 1 else ""
        customers.append(
            {
                "id": f"CUS-{1001 + index}",
                "name": f"{first} {last}",
                "email": f"{handle}{suffix}@{rng.choice(EMAIL_DOMAINS)}",
            }
        )
    return customers


def build_orders(rng: random.Random, customers: list[dict]) -> list[dict]:
    times = sorted(
        START + timedelta(seconds=rng.randrange(DAYS * 86400)) for _ in range(ORDER_COUNT)
    )
    orders = []
    for index, created_at in enumerate(times):
        description, amount_cents = rng.choice(PRODUCTS)
        orders.append(
            {
                "id": f"ORD-{100001 + index}",
                "customer_id": rng.choice(customers)["id"],
                "description": description,
                "amount_cents": amount_cents,
                "created_at": created_at,
            }
        )
    return orders


def pick_timed_out_orders(rng: random.Random, orders: list[dict]) -> list[dict]:
    """One order each from AFFECTED_CUSTOMERS different customers."""
    orders_by_customer = {}
    for order in orders:
        orders_by_customer.setdefault(order["customer_id"], []).append(order)
    customer_ids = rng.sample(sorted(orders_by_customer), AFFECTED_CUSTOMERS)
    return [rng.choice(orders_by_customer[customer_id]) for customer_id in customer_ids]


def build(db_path: str) -> dict:
    """Write the full data set to db_path and return the complainer's details."""
    rng = random.Random(SEED)
    customers = build_customers(rng)
    orders = build_orders(rng, customers)
    timed_out = pick_timed_out_orders(rng, orders)
    timed_out_ids = {order["id"] for order in timed_out}
    healthy_ids = [order["id"] for order in orders if order["id"] not in timed_out_ids]
    declined_ids = set(rng.sample(healthy_ids, DECLINED_ORDERS))
    complained_order = rng.choice(sorted(timed_out, key=lambda order: order["id"]))

    clock = START

    def now() -> str:
        nonlocal clock
        stamp = clock
        clock += RETRY_GAP
        return stamp.isoformat()

    awaiting_timeout = set(timed_out_ids)

    def should_timeout(order_id: str) -> bool:
        if order_id in awaiting_timeout:
            awaiting_timeout.remove(order_id)
            return True
        return False

    create_db(db_path)
    with closing(connect(db_path)) as conn, transaction(conn):
        conn.executemany("INSERT INTO customers VALUES (:id, :name, :email)", customers)
        provider = FakeProvider(conn, should_timeout=should_timeout, now=now)
        for order in orders:
            clock = order["created_at"]
            conn.execute(
                "INSERT INTO orders VALUES (:id, :customer_id, :description, :amount_cents, :at)",
                {**order, "at": now()},
            )
            if order["id"] in declined_ids:
                conn.execute(
                    "INSERT INTO charges (order_id, amount_cents, status, created_at) "
                    "VALUES (?, ?, 'failed', ?)",
                    (order["id"], order["amount_cents"], now()),
                )
            charge_order(provider, order["id"], order["amount_cents"])
        conn.execute(
            "INSERT INTO complaints (customer_id, order_id) VALUES (?, ?)",
            (complained_order["customer_id"], complained_order["id"]),
        )

    customer = next(c for c in customers if c["id"] == complained_order["customer_id"])
    return {
        "order_id": complained_order["id"],
        "customer_id": customer["id"],
        "customer_name": customer["name"],
        "email": customer["email"],
        "description": complained_order["description"],
        "amount": complained_order["amount_cents"] / 100,
        "currency": "USD",
    }


def save_complainer(complainer: dict) -> None:
    """Skip the write when nothing changed, so git doesn't list the file as modified."""
    if COMPLAINER_FILE.exists():
        if json.loads(COMPLAINER_FILE.read_text(encoding="utf-8")) == complainer:
            return
    with open(COMPLAINER_FILE, "w", encoding="utf-8", newline="\n") as file:
        json.dump(complainer, file, indent=2)
        file.write("\n")


def main() -> None:
    db_path = get_db_path()
    save_complainer(build(db_path))
    complainer = json.loads(COMPLAINER_FILE.read_text(encoding="utf-8"))

    summary = summarize(find_affected_customers(db_path))
    if summary["count"] != AFFECTED_CUSTOMERS:
        raise SystemExit(f"Seed produced {summary['count']} affected, not {AFFECTED_CUSTOMERS}")
    print(f"Seeded {db_path}: {ORDER_COUNT} orders, {CUSTOMER_COUNT} customers")
    print(
        f"Double charged: {summary['count']} customers "
        f"({summary['count'] - summary['silent_count']} complained, "
        f"{summary['silent_count']} silent), ${summary['total_overcharge']:,.2f} overcharged"
    )
    print(f"Complainer: {complainer['customer_name']}, order {complainer['order_id']}")


if __name__ == "__main__":
    main()
