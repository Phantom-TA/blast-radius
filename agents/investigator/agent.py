"""The Investigator: finds every customer the double charge hit. Read-only, no LLM.

Whatever it is asked, it runs the same database check and posts the same kind of
answer, so the numbers in the room are identical on every run.
"""

import logging

from agents.common.switch_client import Message, SwitchAgent

log = logging.getLogger("investigator")
TOP_ROWS = 5


def money(amount: float) -> str:
    return f"${amount:,.2f}"


def report(backend) -> str:
    """The result post: counts and total from summarize(), plus the five biggest overcharges."""
    affected = backend.find_affected_customers(backend.db_path)
    summary = backend.summarize(affected)
    if not summary["count"]:
        return "No double charges found. Every order has at most one successful charge."

    complained = summary["count"] - summary["silent_count"]
    lines = [
        f"**{summary['count']} customers were double charged**, "
        f"{money(summary['total_overcharge'])} {summary['currency']} in total.",
        f"{complained} complained. **{summary['silent_count']} have not said anything yet.**",
        "",
        f"Biggest {min(TOP_ROWS, summary['count'])} overcharges:",
        "",
        "| Customer | Email | Order | Charges | Overcharge |",
        "|---|---|---|---|---|",
    ]
    biggest = sorted(affected, key=lambda item: (-item["overcharge_amount"], item["order_id"]))
    for item in biggest[:TOP_ROWS]:
        lines.append(
            f"| {item['customer_id']} | {item['email']} | {item['order_id']} "
            f"| {len(item['charge_ids'])} | {money(item['overcharge_amount'])} |"
        )
    lines += ["", "Read-only check of the payments database. Nothing was changed."]
    return "\n".join(lines)


class Investigator:
    def __init__(self, switch: SwitchAgent, backend):
        self.switch = switch
        self.backend = backend

    def handle(self, message: Message) -> None:
        log.info("asked by %s: %s", message.sender_name, message.body)
        try:
            text = report(self.backend)
        except self.backend.refusals as error:
            text = f"I couldn't read the payments database: {error}"
        except Exception:
            log.exception("check failed")
            text = "The check failed on my side. The details are in the Investigator's log."
        # Mention whoever asked: a Switch agent only wakes when it is addressed, so
        # without this Support would never hear the answer and the story would stall.
        self.switch.send(message.room_id, text, mention=[message.sender_name],
                         thread_id=message.reply_thread)
