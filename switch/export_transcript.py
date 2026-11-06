"""Save the rooms' history from a good run as the repo's reference transcript.

    python switch/export_transcript.py

Writes docs/reference-transcript.md, so anyone can read what a full run looks like
without running it. Run it before make reset, while the blast room is still live.

It reads through the Python agents, one that belongs to each room, because Switch only
lets a room's members read it and the owner's login isn't a member. read_context takes
a room id, so this needs no open connection and doesn't disturb a running agent.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.common.switch_client import SwitchAgent, SwitchError  # noqa: E402

OUTPUT = ROOT / "docs" / "reference-transcript.md"
PAGE_SIZE = 200
# The rooms in the order the story visits them, each with an agent that is a member.
READERS = (("support", "customer-sim"), ("blast-", "investigator"),
           ("finance-approvals", "treasurer"))
HEADER = """# Reference transcript

The room history from a real run of Blast Radius, exported with
`switch/export_transcript.py`. All the customers and payments in it are simulated.
"""


def as_time(milliseconds: int) -> datetime:
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)


def room_messages(agent, room_id: str) -> list[dict]:
    """Every message in a room, oldest first. read_context pages backwards through time."""
    messages = {}
    before = None
    while True:
        args = {"room_id": room_id, "limit": PAGE_SIZE}
        if before:
            args["before"] = before
        page = agent.call("read_context", args, bound=False)
        for thread in page["threads"]:
            for entry in (thread["root"], *thread["replies"]):
                if entry["kind"] == "message":
                    messages[entry["id"]] = entry
        oldest = page.get("oldest_timestamp")
        next_before = as_time(oldest).isoformat() if oldest else None
        if not page["truncated"] or next_before in (None, before):
            return sorted(messages.values(), key=lambda message: message["timestamp"])
        before = next_before


def render(transcripts: list[tuple[str, list[dict]]]) -> str:
    sections = [HEADER]
    for room_name, messages in transcripts:
        sections.append(f"## #{room_name}\n")
        for message in messages:
            sent = as_time(message["timestamp"]).strftime("%Y-%m-%d %H:%M:%S UTC")
            sections.append(f"**{message['sender_name']}** ({sent})\n")
            body = (message.get("body") or "").strip() or "(no text)"
            sections.append(f"{body}\n")
    return "\n".join(sections)


def main() -> int:
    transcripts = []
    try:
        for prefix, reader in READERS:
            agent = SwitchAgent(reader)
            for room in agent.rooms():
                if room["name"].lstrip("#").startswith(prefix):
                    transcripts.append((room["name"], room_messages(agent, room["id"])))
    except SwitchError as error:
        print(f"Couldn't read the rooms: {error}")
        return 1
    if not transcripts:
        print("No rooms to export yet.")
        return 1
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(render(transcripts), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}: "
          f"{sum(len(messages) for _, messages in transcripts)} messages "
          f"from {len(transcripts)} rooms.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
