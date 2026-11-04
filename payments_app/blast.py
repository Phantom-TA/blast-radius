"""Find every customer hit by the double charge. Read-only, no LLM, same answer every run."""

from contextlib import closing
from itertools import groupby

from payments_app.service.store import connect

AFFECTED_QUERY = """
SELECT o.id AS order_id, o.customer_id, cu.email, ch.id AS charge_id, ch.amount_cents,
       EXISTS (SELECT 1 FROM complaints WHERE complaints.order_id = o.id) AS complained
FROM orders o
JOIN customers cu ON cu.id = o.customer_id
JOIN charges ch ON ch.order_id = o.id AND ch.status = 'succeeded'
WHERE o.id IN (
    SELECT order_id FROM charges WHERE status = 'succeeded'
    GROUP BY order_id HAVING COUNT(*) > 1
)
ORDER BY o.id, ch.id
"""


def find_affected_customers(db_path: str) -> list[dict]:
    """Each item: customer_id, email, order_id, charge_ids, overcharge_amount (USD), complained.

    charge_ids is oldest first. The first one is the real charge, the rest are duplicates.
    """
    with closing(connect(db_path, read_only=True)) as conn:
        rows = conn.execute(AFFECTED_QUERY).fetchall()

    affected = []
    for order_id, charges in groupby(rows, key=lambda row: row["order_id"]):
        charges = list(charges)
        overcharge_cents = sum(charge["amount_cents"] for charge in charges[1:])
        affected.append(
            {
                "customer_id": charges[0]["customer_id"],
                "email": charges[0]["email"],
                "order_id": order_id,
                "charge_ids": [charge["charge_id"] for charge in charges],
                "overcharge_amount": overcharge_cents / 100,
                "complained": bool(charges[0]["complained"]),
            }
        )
    return affected


def summarize(affected: list[dict]) -> dict:
    """Returns {"count": int, "silent_count": int, "total_overcharge": float, "currency": "USD"}"""
    total_cents = sum(round(item["overcharge_amount"] * 100) for item in affected)
    return {
        "count": len(affected),
        "silent_count": sum(1 for item in affected if not item.get("complained")),
        "total_overcharge": total_cents / 100,
        "currency": "USD",
    }
