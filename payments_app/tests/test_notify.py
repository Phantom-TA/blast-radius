import email
import socket
from contextlib import closing

import pytest
from aiosmtpd.controller import Controller

from payments_app.blast import find_affected_customers
from payments_app.notify import send_apology_emails
from payments_app.refunds import create_refund_batch, execute_refund_batch
from payments_app.service.store import connect

SUBJECT = "About order {order_id}"
BODY = "Hi {name}, we refunded {amount} for {order_id}."


class Inbox:
    def __init__(self):
        self.messages = []

    async def handle_DATA(self, server, session, envelope):
        self.messages.append(email.message_from_bytes(envelope.content))
        return "250 OK"


@pytest.fixture
def inbox(monkeypatch):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    handler = Inbox()
    controller = Controller(handler, hostname="127.0.0.1", port=port)
    controller.start()
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", str(port))
    yield handler
    controller.stop()


@pytest.fixture
def batch_id(db_path):
    return create_refund_batch(find_affected_customers(db_path))


def test_sends_one_email_per_refunded_customer(db_path, batch_id, inbox):
    execute_refund_batch(batch_id, "tushar")

    assert send_apology_emails(batch_id, SUBJECT, BODY) == 3
    assert sorted(message["To"] for message in inbox.messages) == [
        "ana@example.com",
        "ben@example.com",
        "chen@example.com",
    ]


def test_fills_in_the_template_for_each_customer(db_path, batch_id, inbox):
    execute_refund_batch(batch_id, "tushar")
    send_apology_emails(batch_id, SUBJECT, BODY)

    message = next(m for m in inbox.messages if m["To"] == "chen@example.com")
    assert message["Subject"] == "About order ORD-3"
    assert "Hi Chen Wei, we refunded $58.00 for ORD-3." in message.get_payload()


def test_dollar_sign_before_amount_is_not_doubled(db_path, batch_id, inbox):
    execute_refund_batch(batch_id, "tushar")
    send_apology_emails(batch_id, SUBJECT, "We refunded ${amount} to you.")

    message = next(m for m in inbox.messages if m["To"] == "chen@example.com")
    assert "We refunded $58.00 to you." in message.get_payload()


def test_stray_braces_in_the_wording_are_left_alone(db_path, batch_id, inbox):
    execute_refund_batch(batch_id, "tushar")
    send_apology_emails(batch_id, SUBJECT, "Sorry {name} {not a placeholder}")

    assert "{not a placeholder}" in inbox.messages[0].get_payload()


def test_unknown_placeholder_stops_before_any_email_is_sent(db_path, batch_id, inbox):
    execute_refund_batch(batch_id, "tushar")

    with pytest.raises(ValueError, match="customer_name"):
        send_apology_emails(batch_id, SUBJECT, "Hi {customer_name}, sorry about that.")

    assert inbox.messages == []


def test_non_ascii_wording_survives_delivery(db_path, batch_id, inbox):
    execute_refund_batch(batch_id, "tushar")
    send_apology_emails(batch_id, "We’re sorry — {order_id}", "Hi {name} — we’re sorry.")

    message = next(m for m in inbox.messages if m["To"] == "ana@example.com")
    body = message.get_payload(decode=True).decode("utf-8")
    assert "Hi Ana Silva — we’re sorry." in body


def test_rerun_never_repeats_an_email(db_path, batch_id, inbox):
    execute_refund_batch(batch_id, "tushar")
    send_apology_emails(batch_id, SUBJECT, BODY)

    assert send_apology_emails(batch_id, SUBJECT, BODY) == 0
    assert len(inbox.messages) == 3


def test_refuses_a_batch_that_is_not_refunded_yet(db_path, batch_id, inbox):
    with pytest.raises(ValueError):
        send_apology_emails(batch_id, SUBJECT, BODY)

    assert inbox.messages == []


def test_refuses_an_unknown_batch(db_path, inbox):
    with pytest.raises(ValueError):
        send_apology_emails("rb-nope", SUBJECT, BODY)


def test_two_orders_for_one_customer_get_one_email(db_path, inbox):
    with closing(connect(db_path)) as conn:
        conn.execute("UPDATE orders SET customer_id = 'CUS-1' WHERE id = 'ORD-2'")
    batch_id = create_refund_batch(find_affected_customers(db_path))
    execute_refund_batch(batch_id, "tushar")

    assert send_apology_emails(batch_id, SUBJECT, BODY) == 2
    message = next(m for m in inbox.messages if m["To"] == "ana@example.com")
    assert "$158.00" in message.get_payload()
    assert "ORD-1, ORD-2" in message.get_payload()
