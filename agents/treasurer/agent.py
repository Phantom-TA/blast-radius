"""The Treasurer: builds and executes refund batches. No LLM, and it only obeys its owner.

Its owner is the Finance lead. Two locks keep everyone else away from the money:
1. Switch: its addressing is owner_only ("Only me"), so Switch never delivers anyone
   else's @mention and posts a refusal in the room instead.
2. This code: a message that still arrives from anyone but the owner is refused here.

Commands (anything else gets the help text):
    prepare refunds           build a batch for every affected customer, ask for approval
    execute <batch_id>        refund the batch, approved by whoever sent this, then email
    send emails <batch_id>    email an executed batch again (skips anyone already emailed)
"""

import json
import logging
import re
from pathlib import Path

from agents.common.switch_client import STATE_DIR, Message, SwitchAgent, SwitchError

log = logging.getLogger("treasurer")

FINANCE_ROOM = "finance-approvals"
SUPPORT_AGENT = "support"
APOLOGY_DOCUMENT = "apology-email"
FALLBACK_TEMPLATE = Path(__file__).resolve().parent / "apology_template.md"
STATE_FILE = STATE_DIR / "treasurer.json"
DEFAULT_SUBJECT = "We charged you twice for order {order_id}, and we've refunded you"

PREPARE = re.compile(r"\bprepare\b", re.IGNORECASE)
EXECUTE = re.compile(r"\bexecute\s+(?:batch\s+)?`?([\w-]+)`?", re.IGNORECASE)
EMAILS = re.compile(r"\bsend\s+emails?\s+(?:for\s+)?`?([\w-]+)`?", re.IGNORECASE)

MAIL_DOWN = "I couldn't reach the mail server (is Mailpit running? `make up` starts it)"

HELP = (
    "I handle refunds, and I only take instructions from the Finance lead. Mention me and say:\n"
    "- `prepare refunds` to build a refund batch for approval\n"
    "- `execute <batch id>` to approve and refund it\n"
    "- `send emails <batch id>` to retry the apology emails"
)
NOT_THE_OWNER = (
    "I only take refund instructions from the Finance lead, so I won't act on this."
)


def money(amount: float) -> str:
    return f"${amount:,.2f}"


def parse_apology(text: str) -> tuple[str, str]:
    """A wording document is an optional "Subject: ..." first line, then the body."""
    lines = text.strip().splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).strip()
        return subject or DEFAULT_SUBJECT, body
    return DEFAULT_SUBJECT, text.strip()


class Treasurer:
    def __init__(self, switch: SwitchAgent, backend, state_file: Path = STATE_FILE):
        self.switch = switch
        self.backend = backend
        self.state_file = state_file

    # Which room asked for each batch, so execute reports back there and finds its wording.
    def _origins(self) -> dict:
        try:
            return json.loads(self.state_file.read_text())
        except FileNotFoundError:
            return {}
        except ValueError:
            log.warning("ignoring unreadable %s", self.state_file)
            return {}

    def _remember(self, batch_id: str, room_id: str) -> None:
        origins = self._origins()
        origins[batch_id] = room_id
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(origins, indent=2))

    def _from_owner(self, person: str | None) -> bool:
        """Fails closed: if Switch can't say who the owner is, nobody moves money."""
        if person is None:
            return False
        try:
            return self.switch.is_owner(person)
        except (SwitchError, OSError) as error:
            log.warning("couldn't look up the owner: %s", error)
            return False

    def handle(self, message: Message) -> None:
        person = self.switch.person_name(message)
        if not self._from_owner(person):
            log.warning("refused %s (kind %s, role %s): not the owner",
                        message.sender_name, message.sender_kind, message.sender_role)
            self.switch.reply(message, NOT_THE_OWNER)
            return

        text = message.text_without_mentions()
        log.info("asked by %s: %s", person, text)
        try:
            if match := EMAILS.search(text):
                self.send_emails(message, match.group(1))
            elif match := EXECUTE.search(text):
                self.execute(message, match.group(1), person)
            elif PREPARE.search(text):
                self.prepare(message, person)
            else:
                self.switch.reply(message, HELP)
        except self.backend.refusals as error:
            self.switch.reply(message, f"I didn't do that: {error}")
        except OSError as error:
            log.warning("mail server unreachable: %s", error)
            self.switch.reply(message, f"I didn't do that: {MAIL_DOWN}")
        except Exception:
            log.exception("failed on %r", text)
            self.switch.reply(
                message, "That failed on my side. The details are in the Treasurer's log."
            )

    def prepare(self, message: Message, person: str) -> None:
        affected = self.backend.find_affected_customers(self.backend.db_path)
        summary = self.backend.summarize(affected)
        if not summary["count"]:
            self.switch.reply(message, "Nothing to refund: no double charges found.")
            return
        batch_id = self.backend.create_refund_batch(affected)
        self._remember(batch_id, message.room_id)

        try:
            finance = self.switch.room_id(FINANCE_ROOM)
        except LookupError:
            # Not in #finance-approvals: ask for the approval where the request came from.
            log.warning("not in #%s, asking for approval in the asking room", FINANCE_ROOM)
            finance = message.room_id
        self.switch.send(
            finance,
            f"Refund batch `{batch_id}` is waiting for approval.\n"
            f"- {summary['count']} customers, {money(summary['total_overcharge'])} "
            f"{summary['currency']} in total (each refund is exactly the duplicate charge)\n"
            f"- Requested by {person} in #{self.switch.room_name(message.room_id)}\n"
            f"- Then I email each customer the approved apology\n\n"
            # No @treasurer here: Discord turns it into a raw role code, even in backticks.
            f"Nothing has been refunded yet. To approve, mention me and say: `execute {batch_id}`",
            mention=[person],
        )
        if finance != message.room_id:
            # Mention Support so it wakes up and carries on.
            self.switch.send(
                message.room_id,
                f"Batch `{batch_id}` is ready: {summary['count']} customers, "
                f"{money(summary['total_overcharge'])}. It is waiting for the Finance lead's "
                f"approval in #{FINANCE_ROOM}.",
                mention=[SUPPORT_AGENT],
                thread_id=message.reply_thread,
            )

    def execute(self, message: Message, batch_id: str, person: str) -> None:
        result = self.backend.execute_refund_batch(batch_id, approved_by=person)
        refunded = (f"Refunded `{batch_id}`, approved by {person}: {result['refunded']} "
                    f"refunds, {money(result['total'])} in total.")
        self.switch.reply(message, refunded + " Sending the apology emails now.")
        try:
            self.send_emails(message, batch_id, refunded=refunded)
        except (*self.backend.refusals, OSError) as error:
            # The money has moved; say so plainly, and how to finish the emails.
            reason = MAIL_DOWN if isinstance(error, OSError) else str(error)
            log.warning("refunded %s but emails failed: %s", batch_id, error)
            failed = (f"The refunds are done, but no apology emails went out: {reason}. "
                      f"Once that's fixed, mention me and say `send emails {batch_id}`.")
            self.switch.reply(message, failed)
            origin = self._origins().get(batch_id)
            if origin and origin != message.room_id:
                self.switch.send(origin, f"{refunded} {failed}", mention=[SUPPORT_AGENT])

    def send_emails(self, message: Message, batch_id: str, refunded: str = "") -> None:
        subject, body, source = self.apology(batch_id)
        sent = self.backend.send_apology_emails(batch_id, subject, body)
        done = f"Sent {sent} apology emails for `{batch_id}`, worded from {source}."
        self.switch.reply(message, done)

        origin = self._origins().get(batch_id)
        if origin and origin != message.room_id:
            # Mention Support so it wakes up and writes the postmortem.
            self.switch.send(origin, " ".join(part for part in (refunded, done) if part),
                             mention=[SUPPORT_AGENT])

    def apology(self, batch_id: str) -> tuple[str, str, str]:
        """The wording: the room document "apology-email" Support wrote, else the template file."""
        origin = self._origins().get(batch_id)
        rooms = [origin] if origin else []
        rooms += [room["id"] for room in self.switch.rooms() if room["id"] not in rooms]
        for room_id in rooms:
            text = self.switch.room_document(room_id, APOLOGY_DOCUMENT)
            if text:
                subject, body = parse_apology(text)
                if not body:
                    raise ValueError(f"the \"{APOLOGY_DOCUMENT}\" document has a subject "
                                     "but no body")
                return subject, body, (f"the room document \"{APOLOGY_DOCUMENT}\" in "
                                       f"#{self.switch.room_name(room_id)}")
        log.warning("no %s document found, using %s", APOLOGY_DOCUMENT, FALLBACK_TEMPLATE.name)
        subject, body = parse_apology(FALLBACK_TEMPLATE.read_text())
        return subject, body, "the standard template (no apology-email document was found)"
