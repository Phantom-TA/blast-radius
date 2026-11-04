"""Send apology emails for an executed refund batch to the local Mailpit inbox."""

import os
import re
import smtplib
from contextlib import closing
from datetime import datetime, timezone
from email.message import EmailMessage

from payments_app.service.store import connect

FROM_ADDRESS = "support@acme-store.example"
PLACEHOLDERS = ("name", "order_id", "amount")


def _check_placeholders(*templates: str) -> None:
    """The wording is drafted by an agent, so catch a typo before it reaches every customer."""
    used = {word for template in templates for word in re.findall(r"\{(\w+)\}", template)}
    unknown = sorted(used.difference(PLACEHOLDERS))
    if unknown:
        raise ValueError(f"unknown placeholders {unknown}, use only {list(PLACEHOLDERS)}")


def _fill(template: str, customer: dict) -> str:
    """Plain text swap, so a stray brace in the drafted wording can't break the send."""
    # {amount} already includes the dollar sign, so "${amount}" must not show it twice.
    text = template.replace("${amount}", "{amount}")
    for placeholder in PLACEHOLDERS:
        text = text.replace(f"{{{placeholder}}}", customer[placeholder])
    return text


def _customers_to_email(conn, batch_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT r.id, r.customer_id, r.order_id, r.amount_cents, c.name, c.email "
        "FROM refunds r JOIN customers c ON c.id = r.customer_id "
        "WHERE r.batch_id = ? AND r.status = 'refunded' AND r.emailed_at IS NULL "
        "ORDER BY r.id",
        (batch_id,),
    ).fetchall()

    customers = {}
    for row in rows:
        customer = customers.setdefault(
            row["customer_id"],
            {"name": row["name"], "email": row["email"], "orders": [], "cents": 0, "refunds": []},
        )
        customer["orders"].append(row["order_id"])
        customer["cents"] += row["amount_cents"]
        customer["refunds"].append(row["id"])

    return [
        {
            **customer,
            "order_id": ", ".join(dict.fromkeys(customer["orders"])),
            "amount": f"${customer['cents'] / 100:,.2f}",
        }
        for customer in customers.values()
    ]


def send_apology_emails(batch_id: str, subject: str, body_template: str) -> int:
    """Sends one email per refunded customer to Mailpit (SMTP localhost:1025).

    Subject and body may use {name}, {order_id} and {amount}. Refuses a batch that has
    not been executed. Customers already emailed are skipped, so a rerun never repeats
    an email. Returns the count sent.
    """
    _check_placeholders(subject, body_template)
    host = os.environ.get("SMTP_HOST", "localhost")
    port = int(os.environ.get("SMTP_PORT", "1025"))

    with closing(connect()) as conn:
        batch = conn.execute(
            "SELECT status FROM refund_batches WHERE id = ?", (batch_id,)
        ).fetchone()
        if batch is None:
            raise ValueError(f"unknown batch {batch_id}")
        if batch["status"] != "executed":
            raise ValueError(f"batch {batch_id} is {batch['status']}, refund it before emailing")

        customers = _customers_to_email(conn, batch_id)
        if not customers:
            return 0

        with smtplib.SMTP(host, port, timeout=10) as smtp:
            for customer in customers:
                message = EmailMessage()
                message["From"] = FROM_ADDRESS
                message["To"] = customer["email"]
                message["Subject"] = _fill(subject, customer)
                message.set_content(_fill(body_template, customer))
                smtp.send_message(message)
                conn.executemany(
                    "UPDATE refunds SET emailed_at = ? WHERE id = ?",
                    [
                        (datetime.now(timezone.utc).isoformat(timespec="seconds"), refund_id)
                        for refund_id in customer["refunds"]
                    ],
                )
    return len(customers)
