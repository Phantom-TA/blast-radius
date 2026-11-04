"""Build and execute refund batches. Amounts always come from the database, never from an LLM."""

import hashlib
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from payments_app.service.store import connect, transaction


class RefundError(Exception):
    """The refund was refused. Nothing was changed."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _batch_id(duplicate_charge_ids: list[int]) -> str:
    """Same set of charges, same id, so the batch is not created twice by a rerun."""
    joined = ",".join(str(charge_id) for charge_id in sorted(duplicate_charge_ids))
    return f"rb-{hashlib.sha256(joined.encode()).hexdigest()[:12]}"


def _refund_rows(conn: sqlite3.Connection, item: dict) -> list[dict]:
    """Check one affected order against the database and list its duplicate charges."""
    order_id = item["order_id"]
    if not item["charge_ids"]:
        raise RefundError(f"order {order_id} has no charges listed")
    first_charge_id, *duplicate_ids = sorted(item["charge_ids"])
    rows = []
    for charge_id in [first_charge_id, *duplicate_ids]:
        charge = conn.execute(
            "SELECT ch.amount_cents, ch.status, ch.order_id, o.customer_id FROM charges ch "
            "JOIN orders o ON o.id = ch.order_id WHERE ch.id = ?",
            (charge_id,),
        ).fetchone()
        if charge is None or charge["order_id"] != order_id:
            raise RefundError(f"charge {charge_id} does not belong to order {order_id}")
        if charge["status"] != "succeeded":
            raise RefundError(f"charge {charge_id} is {charge['status']}, cannot refund it")
        if charge["customer_id"] != item["customer_id"]:
            raise RefundError(f"order {order_id} does not belong to {item['customer_id']}")
        if charge_id != first_charge_id:
            rows.append(
                {
                    "customer_id": charge["customer_id"],
                    "order_id": order_id,
                    "charge_id": charge_id,
                    "amount_cents": charge["amount_cents"],
                }
            )

    if sum(row["amount_cents"] for row in rows) != round(item["overcharge_amount"] * 100):
        raise RefundError(f"order {order_id}: overcharge does not match the charges on record")
    return rows


def create_refund_batch(affected: list[dict]) -> str:
    """Creates a batch with status 'pending_approval'. Returns batch_id.

    A charge can only ever belong to one batch.
    """
    with closing(connect()) as conn, transaction(conn):
        rows = [row for item in affected for row in _refund_rows(conn, item)]
        if not rows:
            raise RefundError("nothing to refund")

        batch_id = _batch_id([row["charge_id"] for row in rows])
        if conn.execute("SELECT 1 FROM refund_batches WHERE id = ?", (batch_id,)).fetchone():
            return batch_id

        conn.execute(
            "INSERT INTO refund_batches (id, status, created_at) "
            "VALUES (?, 'pending_approval', ?)",
            (batch_id, _now()),
        )
        try:
            conn.executemany(
                "INSERT INTO refunds "
                "(batch_id, customer_id, order_id, charge_id, amount_cents, status) "
                "VALUES (:batch_id, :customer_id, :order_id, :charge_id, :amount_cents, "
                "'pending')",
                [{**row, "batch_id": batch_id} for row in rows],
            )
        except sqlite3.IntegrityError as error:
            raise RefundError("a charge in this batch is already in another batch") from error
    return batch_id


def execute_refund_batch(batch_id: str, approved_by: str) -> dict:
    """Refuses unless the status is 'pending_approval' and approved_by is set.

    Marks the refunds done in the database. Returns {"refunded": int, "total": float}.
    """
    if not approved_by or not approved_by.strip():
        raise RefundError("refusing to refund without an approver")

    with closing(connect()) as conn, transaction(conn):
        batch = conn.execute(
            "SELECT status FROM refund_batches WHERE id = ?", (batch_id,)
        ).fetchone()
        if batch is None:
            raise RefundError(f"unknown batch {batch_id}")
        if batch["status"] != "pending_approval":
            raise RefundError(f"batch {batch_id} is {batch['status']}, not pending_approval")

        refunds = conn.execute(
            "SELECT charge_id, amount_cents FROM refunds WHERE batch_id = ?", (batch_id,)
        ).fetchall()
        refunded_at = _now()
        for refund in refunds:
            updated = conn.execute(
                "UPDATE charges SET status = 'refunded' WHERE id = ? AND status = 'succeeded'",
                (refund["charge_id"],),
            )
            if updated.rowcount != 1:
                raise RefundError(f"charge {refund['charge_id']} was already refunded")

        conn.execute(
            "UPDATE refunds SET status = 'refunded', refunded_at = ? WHERE batch_id = ?",
            (refunded_at, batch_id),
        )
        conn.execute(
            "UPDATE refund_batches SET status = 'executed', approved_by = ?, executed_at = ? "
            "WHERE id = ?",
            (approved_by.strip(), refunded_at, batch_id),
        )

    return {
        "refunded": len(refunds),
        "total": sum(refund["amount_cents"] for refund in refunds) / 100,
    }
