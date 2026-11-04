"""Stand-ins for Person B's payments_app, with the signatures in blast-radius-context.md section 8.

They keep a small in-memory world (5 double-charged customers, 1 of whom complained)
so the agents can be tested, and run in Switch with BLAST_BACKEND=fake, before the
real code is merged. They refuse the same things the real code refuses.
"""

import re

DB_PATH = "fake.db"
PLACEHOLDERS = ("name", "order_id", "amount")


class RefundError(Exception):
    """The refund was refused. Nothing was changed."""


AFFECTED = [
    {"customer_id": "CUS-1386", "email": "victor.tanaka2@example.com", "name": "Victor Tanaka",
     "order_id": "ORD-100953", "charge_ids": [11, 12], "overcharge_amount": 59.0,
     "complained": True},
    {"customer_id": "CUS-0042", "email": "ana.ruiz@example.com", "name": "Ana Ruiz",
     "order_id": "ORD-100120", "charge_ids": [21, 22], "overcharge_amount": 129.5,
     "complained": False},
    {"customer_id": "CUS-0077", "email": "li.wei@example.com", "name": "Li Wei",
     "order_id": "ORD-100311", "charge_ids": [31, 32, 33], "overcharge_amount": 48.0,
     "complained": False},
    {"customer_id": "CUS-0105", "email": "sam.okafor@example.com", "name": "Sam Okafor",
     "order_id": "ORD-100498", "charge_ids": [41, 42], "overcharge_amount": 15.25,
     "complained": False},
    {"customer_id": "CUS-0230", "email": "mia.berg@example.com", "name": "Mia Berg",
     "order_id": "ORD-100702", "charge_ids": [51, 52], "overcharge_amount": 230.0,
     "complained": False},
]

batches: dict[str, dict] = {}
outbox: list[dict] = []


def reset() -> None:
    batches.clear()
    outbox.clear()


def find_affected_customers(db_path: str) -> list[dict]:
    """Each item: customer_id, email, order_id, charge_ids, overcharge_amount (USD)."""
    return [
        {key: value for key, value in item.items() if key != "name"} for item in AFFECTED
    ]


def summarize(affected: list[dict]) -> dict:
    """Returns {"count": int, "silent_count": int, "total_overcharge": float, "currency": "USD"}"""
    total_cents = sum(round(item["overcharge_amount"] * 100) for item in affected)
    return {
        "count": len(affected),
        "silent_count": sum(1 for item in affected if not item.get("complained")),
        "total_overcharge": total_cents / 100,
        "currency": "USD",
    }


def create_refund_batch(affected: list[dict]) -> str:
    """Creates a batch with status 'pending_approval'. Returns batch_id."""
    if not affected:
        raise RefundError("nothing to refund")
    batch_id = f"rb-fake{len(batches) + 1:04d}"
    batches[batch_id] = {"status": "pending_approval", "items": affected, "approved_by": None}
    return batch_id


def execute_refund_batch(batch_id: str, approved_by: str) -> dict:
    """Refuses unless the status is 'pending_approval' and approved_by is set.
    Marks the refunds done in the database. Returns {"refunded": int, "total": float}."""
    if not approved_by or not approved_by.strip():
        raise RefundError("refusing to refund without an approver")
    batch = batches.get(batch_id)
    if batch is None:
        raise RefundError(f"unknown batch {batch_id}")
    if batch["status"] != "pending_approval":
        raise RefundError(f"batch {batch_id} is {batch['status']}, not pending_approval")
    batch["status"] = "executed"
    batch["approved_by"] = approved_by.strip()
    total_cents = sum(round(item["overcharge_amount"] * 100) for item in batch["items"])
    return {"refunded": len(batch["items"]), "total": total_cents / 100}


def send_apology_emails(batch_id: str, subject: str, body_template: str) -> int:
    """Sends one email per refunded customer to Mailpit (SMTP localhost:1025).
    Returns the count sent. Here the emails go to the in-memory outbox instead."""
    used = set(re.findall(r"\{(\w+)\}", subject + body_template))
    unknown = sorted(used.difference(PLACEHOLDERS))
    if unknown:
        raise ValueError(f"unknown placeholders {unknown}, use only {list(PLACEHOLDERS)}")
    batch = batches.get(batch_id)
    if batch is None:
        raise ValueError(f"unknown batch {batch_id}")
    if batch["status"] != "executed":
        raise ValueError(f"batch {batch_id} is {batch['status']}, refund it before emailing")

    sent = 0
    already = {email["to"] for email in outbox if email["batch_id"] == batch_id}
    names = {item["customer_id"]: item["name"] for item in AFFECTED}
    for item in batch["items"]:
        if item["email"] in already:
            continue
        values = {
            "name": names.get(item["customer_id"], "there"),
            "order_id": item["order_id"],
            "amount": f"${item['overcharge_amount']:,.2f}",
        }

        def fill(text: str) -> str:
            for key, value in values.items():
                text = text.replace(f"{{{key}}}", value)
            return text

        outbox.append({"batch_id": batch_id, "to": item["email"],
                       "subject": fill(subject), "body": fill(body_template)})
        sent += 1
    return sent
