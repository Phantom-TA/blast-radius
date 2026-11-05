"""Save the rooms' history from a good run as the repo's reference transcript.

    python switch/export_transcript.py

Writes docs/reference-transcript.md, so anyone can read what a full run looks like
without running it. Run it before switch/archive_rooms.py --delete, which removes the
history of the blast room. Runs as the agents' owner through the Gateway API.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.common.gateway import gateway_session  # noqa: E402
from agents.common.switch_client import find_server_url  # noqa: E402

OUTPUT = ROOT / "docs" / "reference-transcript.md"
PAGE_SIZE = 200
HEADER = """# Reference transcript

The room history from a real run of Blast Radius, exported with
`switch/export_transcript.py`. All the customers and payments in it are simulated.
"""


def room_messages(gateway, room_id: str) -> list[dict]:
    """Every message in a room, oldest first. Each page ends at the newest it was asked for."""
    messages = []
    before = None
    while True:
        query = f"?limit={PAGE_SIZE}" + (f"&beforeSeq={before}" if before else "")
        page = gateway("GET", f"/chats/{room_id}/messages{query}")
        messages += page["messages"]
        if not page["hasMore"] or not page["messages"]:
            return sorted(messages, key=lambda message: message["seq"])
        before = min(message["seq"] for message in page["messages"])


def story_rooms(rooms: list[dict]) -> list[dict]:
    """The rooms in the order the story visits them."""
    def wanted(prefix: str) -> list[dict]:
        return [room for room in rooms if room["name"].startswith(prefix)]

    return [*wanted("support"), *wanted("blast-"), *wanted("finance-approvals")]


def render(transcripts: list[tuple[str, list[dict]]]) -> str:
    sections = [HEADER]
    for room_name, messages in transcripts:
        sections.append(f"## #{room_name}\n")
        for message in messages:
            sections.append(f"**{message['sender']['name']}** ({message['sentAt']})\n")
            sections.append(f"{message['body'].strip()}\n")
    return "\n".join(sections)


def main() -> int:
    gateway = gateway_session(find_server_url(), quiet=True)
    rooms = story_rooms(gateway("GET", "/rooms"))
    if not rooms:
        print("No rooms to export yet.")
        return 1
    transcripts = [(room["name"], room_messages(gateway, room["id"])) for room in rooms]
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(render(transcripts), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}: "
          f"{sum(len(messages) for _, messages in transcripts)} messages "
          f"from {len(transcripts)} rooms.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
