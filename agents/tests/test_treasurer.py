from types import SimpleNamespace

import pytest

from agents.common.switch_client import SwitchError
from agents.tests import fakes
from agents.tests.chat import FakeSwitch, message
from agents.treasurer.agent import NOT_THE_OWNER, Treasurer, parse_apology

WORDING = (
    "Subject: Sorry about order {order_id}\n"
    "Hi {name}, we refunded {amount} for order {order_id}."
)


@pytest.fixture
def backend():
    fakes.reset()
    return SimpleNamespace(
        find_affected_customers=fakes.find_affected_customers,
        summarize=fakes.summarize,
        create_refund_batch=fakes.create_refund_batch,
        execute_refund_batch=fakes.execute_refund_batch,
        send_apology_emails=fakes.send_apology_emails,
        db_path=fakes.DB_PATH,
        refusals=(fakes.RefundError, ValueError),
    )


def treasurer(backend, tmp_path, documents=None):
    switch = FakeSwitch(documents)
    return Treasurer(switch, backend, state_file=tmp_path / "treasurer.json"), switch


def test_refuses_an_agent_and_touches_nothing(backend, tmp_path):
    agent, switch = treasurer(backend, tmp_path)
    agent.handle(message("@treasurer prepare refunds", sender="@support:localhost", role=None))
    assert switch.replies[0][1] == NOT_THE_OWNER
    assert fakes.batches == {}


def test_refuses_switch_itself_even_on_behalf_of_a_person(backend, tmp_path):
    agent, switch = treasurer(backend, tmp_path)
    agent.handle(message("@treasurer prepare refunds", kind="platform", role="owner"))
    assert switch.replies[0][1] == NOT_THE_OWNER
    assert fakes.batches == {}


def test_refuses_a_chat_account_no_switch_user_has_claimed(backend, tmp_path):
    agent, switch = treasurer(backend, tmp_path)
    agent.handle(message("@treasurer prepare refunds", sender="@someone:localhost", role=None))
    assert switch.replies[0][1] == NOT_THE_OWNER
    assert fakes.batches == {}


def test_refuses_a_linked_person_who_is_not_the_owner(backend, tmp_path):
    agent, switch = treasurer(backend, tmp_path)
    agent.handle(message("@treasurer prepare refunds", sender="@colleague:localhost",
                         role="member"))
    assert switch.replies[0][1] == NOT_THE_OWNER
    assert fakes.batches == {}


def test_refuses_everyone_when_the_owner_cant_be_looked_up(backend, tmp_path):
    agent, switch = treasurer(backend, tmp_path)
    switch.owner_lookup_error = SwitchError(500, "down")
    agent.handle(message("@treasurer prepare refunds"))
    assert switch.replies[0][1] == NOT_THE_OWNER
    assert fakes.batches == {}


def test_prepare_posts_the_batch_in_finance_approvals_and_wakes_support(backend, tmp_path):
    agent, switch = treasurer(backend, tmp_path)
    agent.handle(message("@treasurer prepare refunds", thread_id="root-7"))

    [batch_id] = fakes.batches
    assert fakes.batches[batch_id]["status"] == "pending_approval"
    [post, pointer] = switch.sent
    assert post["room_id"] == "room-finance"
    assert post["mention"] == ["amiyasingh05"]
    assert f"Refund batch `{batch_id}` is waiting for approval." in post["text"]
    assert "5 customers, $481.75 USD in total" in post["text"]
    assert f"mention me and say: `execute {batch_id}`" in post["text"]
    # Discord turns @treasurer into a raw role code, even inside backticks.
    assert "@treasurer" not in post["text"]
    # And a pointer back in the room that asked, naming the batch for Support.
    assert pointer["room_id"] == "room-blast" and pointer["thread_id"] == "root-7"
    assert pointer["mention"] == ["support"]
    assert f"Batch `{batch_id}` is ready" in pointer["text"]
    assert "waiting for the Finance lead's approval in #finance-approvals" in pointer["text"]


def test_execute_refunds_then_emails_with_the_room_document(backend, tmp_path):
    agent, switch = treasurer(backend, tmp_path,
                              documents={("room-blast", "apology-email"): WORDING})
    agent.handle(message("@treasurer prepare refunds"))
    [batch_id] = fakes.batches
    switch.sent.clear()

    agent.handle(message(f"@treasurer execute {batch_id}", room_id="room-finance"))

    assert fakes.batches[batch_id] == {**fakes.batches[batch_id], "status": "executed",
                                       "approved_by": "amiyasingh05"}
    assert len(fakes.outbox) == 5
    first = fakes.outbox[0]
    assert first["subject"] == "Sorry about order ORD-100953"
    assert first["body"] == "Hi Victor Tanaka, we refunded $59.00 for order ORD-100953."
    texts = [text for _, text in switch.replies]
    assert texts[-2].startswith(f"Refunded `{batch_id}`, approved by amiyasingh05: 5 refunds, "
                                "$481.75 in total.")
    assert texts[-1] == (f"Sent 5 apology emails for `{batch_id}`, worded from the room "
                         "document \"apology-email\" in #blast-ORD-100953.")
    # The room the batch came from hears the result too.
    [report] = switch.sent
    assert report["room_id"] == "room-blast"
    assert report["mention"] == ["support"]  # so Support wakes and writes the postmortem
    assert "Sent 5 apology emails" in report["text"]


def test_execute_without_a_wording_document_uses_the_template(backend, tmp_path):
    agent, switch = treasurer(backend, tmp_path)
    agent.handle(message("@treasurer prepare refunds"))
    [batch_id] = fakes.batches
    agent.handle(message(f"@treasurer execute {batch_id}"))
    assert len(fakes.outbox) == 5
    assert fakes.outbox[0]["subject"].startswith("We charged you twice for order ORD-100953")
    assert "the standard template" in switch.replies[-1][1]


def test_a_second_execute_is_refused_and_sends_nothing_more(backend, tmp_path):
    agent, switch = treasurer(backend, tmp_path)
    agent.handle(message("@treasurer prepare refunds"))
    [batch_id] = fakes.batches
    agent.handle(message(f"@treasurer execute {batch_id}"))
    agent.handle(message(f"@treasurer execute {batch_id}"))
    assert switch.replies[-1][1] == (
        f"I didn't do that: batch {batch_id} is executed, not pending_approval"
    )
    assert len(fakes.outbox) == 5


def test_send_emails_retries_only_the_missing_ones(backend, tmp_path):
    agent, switch = treasurer(backend, tmp_path)
    agent.handle(message("@treasurer prepare refunds"))
    [batch_id] = fakes.batches
    agent.handle(message(f"@treasurer execute {batch_id}"))
    agent.handle(message(f"@treasurer send emails {batch_id}"))
    assert switch.replies[-1][1].startswith(f"Sent 0 apology emails for `{batch_id}`")
    assert len(fakes.outbox) == 5


def test_a_bad_placeholder_in_the_wording_is_refused(backend, tmp_path):
    agent, switch = treasurer(backend, tmp_path,
                              documents={("room-blast", "apology-email"): "Hi {first_name}"})
    agent.handle(message("@treasurer prepare refunds"))
    [batch_id] = fakes.batches
    agent.handle(message(f"@treasurer execute {batch_id}"))
    assert "unknown placeholders ['first_name']" in switch.replies[-1][1]
    assert fakes.outbox == []


def test_unknown_batch_is_refused(backend, tmp_path):
    agent, switch = treasurer(backend, tmp_path)
    agent.handle(message("@treasurer execute rb-nope"))
    assert switch.replies[-1][1] == "I didn't do that: unknown batch rb-nope"


def test_anything_else_gets_help(backend, tmp_path):
    agent, switch = treasurer(backend, tmp_path)
    agent.handle(message("@treasurer hello"))
    assert "prepare refunds" in switch.replies[0][1]


def test_parse_apology_with_and_without_a_subject_line():
    assert parse_apology(WORDING) == (
        "Sorry about order {order_id}", "Hi {name}, we refunded {amount} for order {order_id}."
    )
    subject, body = parse_apology("Hi {name}")
    assert subject.startswith("We charged you twice")
    assert body == "Hi {name}"


def test_the_fallback_template_only_uses_known_placeholders():
    import re

    from agents.treasurer.agent import FALLBACK_TEMPLATE

    used = set(re.findall(r"\{(\w+)\}", FALLBACK_TEMPLATE.read_text()))
    assert used <= set(fakes.PLACEHOLDERS)
