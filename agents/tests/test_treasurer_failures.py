"""The Treasurer when things go wrong: wrong senders, wrong commands, broken mail, bad wording."""

from types import SimpleNamespace

import pytest

from agents.tests import fakes
from agents.tests.chat import FakeSwitch, message
from agents.treasurer.agent import HELP, MAIL_DOWN, NOT_THE_OWNER, Treasurer

WORDING = "Subject: Sorry about {order_id}\nHi {name}, we refunded {amount}."


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


@pytest.fixture
def run(backend, tmp_path):
    """A Treasurer, its chat, and a helper that sends it a message from the person."""
    switch = FakeSwitch({("room-blast", "apology-email"): WORDING})
    agent = Treasurer(switch, backend, state_file=tmp_path / "treasurer.json")

    def say(text, **kwargs):
        agent.handle(message(text, **kwargs))
        return switch.replies[-1][1] if switch.replies else None

    return SimpleNamespace(agent=agent, switch=switch, say=say)


def prepared(run) -> str:
    run.say("@treasurer prepare refunds")
    [batch_id] = fakes.batches
    return batch_id


# Who may ask

@pytest.mark.parametrize("role", [None, "", "guest", "agent"])
def test_anything_but_a_recognised_person_is_refused(run, role):
    assert run.say("@treasurer prepare refunds", sender="@x:localhost", role=role) == NOT_THE_OWNER
    assert fakes.batches == {}


def test_an_agent_cannot_execute_a_batch_the_owner_prepared(run):
    batch_id = prepared(run)
    assert run.say(f"@treasurer execute {batch_id}", sender="@support:localhost",
                   role=None) == NOT_THE_OWNER
    assert fakes.batches[batch_id]["status"] == "pending_approval"
    assert fakes.outbox == []


def test_the_support_lead_cannot_execute_a_batch_either(run):
    batch_id = prepared(run)
    assert run.say(f"@treasurer execute {batch_id}", sender="@colleague:localhost",
                   role=None) == NOT_THE_OWNER
    assert fakes.batches[batch_id]["status"] == "pending_approval"


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_the_owner_may_approve_whatever_their_workspace_role(run, role):
    batch_id = prepared(run)
    run.say(f"@treasurer execute {batch_id}", role=role)
    assert fakes.batches[batch_id]["status"] == "executed"
    assert fakes.batches[batch_id]["approved_by"] == "amiyasingh05"


# What they say

@pytest.mark.parametrize("text", [
    "@treasurer", "@treasurer hello", "@treasurer execute", "@treasurer refund everyone now",
])
def test_unclear_requests_get_the_help_text_and_change_nothing(run, text):
    assert run.say(text) == HELP
    assert fakes.batches == {}


@pytest.mark.parametrize("text", [
    "@treasurer PREPARE REFUNDS",
    "@treasurer @investigator please prepare the refunds",
    "@treasurer prepare",
])
def test_prepare_is_understood_however_it_is_written(run, text):
    run.say(text)
    assert len(fakes.batches) == 1


@pytest.mark.parametrize("template", [
    "@treasurer execute {id}", "@treasurer execute batch {id}", "@treasurer execute `{id}`",
    "@treasurer Execute {id} please",
])
def test_execute_is_understood_however_it_is_written(run, template):
    batch_id = prepared(run)
    run.say(template.format(id=batch_id))
    assert fakes.batches[batch_id]["status"] == "executed"


# Doing things twice, or in the wrong order

def test_preparing_twice_gives_the_same_batch(run):
    first = prepared(run)
    run.say("@treasurer prepare refunds")
    assert list(fakes.batches) == [first]
    assert run.switch.sent[-2]["text"].startswith(f"Refund batch `{first}`")
    assert run.switch.sent[-1]["text"].startswith(f"Batch `{first}` is ready")


def test_execute_before_prepare_is_refused(run):
    assert run.say("@treasurer execute rb-000000000000") == (
        "I didn't do that: unknown batch rb-000000000000"
    )


def test_preparing_after_everyone_was_refunded_finds_nothing(run):
    batch_id = prepared(run)
    run.say(f"@treasurer execute {batch_id}")
    assert run.say("@treasurer prepare refunds") == "Nothing to refund: no double charges found."
    assert len(fakes.batches) == 1


def test_executing_twice_refunds_and_emails_once(run):
    batch_id = prepared(run)
    run.say(f"@treasurer execute {batch_id}")
    second = run.say(f"@treasurer execute {batch_id}")
    assert second == f"I didn't do that: batch {batch_id} is executed, not pending_approval"
    assert len(fakes.outbox) == 5


# Mail and wording

def test_mail_server_down_after_refunding_says_the_money_moved_and_how_to_finish(run, backend):
    batch_id = prepared(run)

    def no_mail(*args):
        raise ConnectionRefusedError(61, "Connection refused")

    backend.send_apology_emails = no_mail
    reply = run.say(f"@treasurer execute {batch_id}", room_id="room-finance")
    assert reply == (f"The refunds are done, but no apology emails went out: {MAIL_DOWN}. "
                     f"Once that's fixed, mention me and say `send emails {batch_id}`.")
    assert fakes.batches[batch_id]["status"] == "executed"
    # The room the batch came from hears it too.
    assert "The refunds are done, but no apology emails went out" in run.switch.sent[-1]["text"]

    backend.send_apology_emails = fakes.send_apology_emails
    assert run.say(f"@treasurer send emails {batch_id}").startswith(
        f"Sent 5 apology emails for `{batch_id}`")


def test_mail_server_down_on_a_retry_is_explained(run, backend):
    batch_id = prepared(run)
    run.say(f"@treasurer execute {batch_id}")

    def no_mail(*args):
        raise OSError("timed out")

    backend.send_apology_emails = no_mail
    assert run.say(f"@treasurer send emails {batch_id}") == f"I didn't do that: {MAIL_DOWN}"


def test_a_wording_typo_stops_every_email_and_a_fixed_wording_sends_them(run):
    run.switch.documents[("room-blast", "apology-email")] = "Subject: Hi\nDear {firstname}"
    batch_id = prepared(run)
    reply = run.say(f"@treasurer execute {batch_id}")
    assert reply.startswith("The refunds are done, but no apology emails went out: "
                            "unknown placeholders ['firstname']")
    assert fakes.outbox == []

    run.switch.documents[("room-blast", "apology-email")] = WORDING
    assert run.say(f"@treasurer send emails {batch_id}").startswith("Sent 5 apology emails")
    assert len(fakes.outbox) == 5


def test_a_wording_with_only_a_subject_is_refused(run):
    run.switch.documents[("room-blast", "apology-email")] = "Subject: Sorry\n\n"
    batch_id = prepared(run)
    reply = run.say(f"@treasurer execute {batch_id}")
    assert "the \"apology-email\" document has a subject but no body" in reply
    assert fakes.outbox == []


def test_emails_for_a_batch_nobody_executed_are_refused(run):
    batch_id = prepared(run)
    assert run.say(f"@treasurer send emails {batch_id}") == (
        f"I didn't do that: batch {batch_id} is pending_approval, refund it before emailing"
    )


# The Treasurer's own surroundings

def test_without_finance_approvals_it_asks_for_approval_where_it_was_asked(run, monkeypatch):
    def no_room(name):
        raise LookupError(name)

    monkeypatch.setattr(run.switch, "room_id", no_room)
    batch_id = prepared(run)
    [post] = run.switch.sent
    assert post["room_id"] == "room-blast"
    assert post["mention"] == ["amiyasingh05"]
    assert f"`execute {batch_id}`" in post["text"]


def test_a_corrupt_state_file_is_ignored(run):
    run.agent.state_file.write_text("{not json")
    batch_id = prepared(run)
    run.say(f"@treasurer execute {batch_id}")
    assert fakes.batches[batch_id]["status"] == "executed"


def test_an_unexpected_error_gives_no_stack_trace(run, backend):
    def broken(_):
        raise KeyError("overcharge_amount")

    backend.find_affected_customers = broken
    assert run.say("@treasurer prepare refunds") == (
        "That failed on my side. The details are in the Treasurer's log."
    )


def test_it_answers_in_the_thread_it_was_asked_in(run):
    run.agent.handle(message("@treasurer hello", thread_id="root-7"))
    replied_to, _ = run.switch.replies[-1]
    assert replied_to.reply_thread == "root-7"
