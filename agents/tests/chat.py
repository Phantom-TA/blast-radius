"""A stand-in for SwitchAgent that records what an agent would say, for the tests."""

from agents.common.switch_client import Message, person_name

ROOMS = {"room-blast": "blast-ORD-100953", "room-finance": "finance-approvals"}
PEOPLE = {"@amiyasingh05:localhost": "amiyasingh05"}


class FakeSwitch:
    def __init__(self, documents: dict | None = None):
        self.replies: list[tuple[Message, str]] = []
        self.sent: list[dict] = []
        # {(room_id, document name): content}
        self.documents = documents or {}

    def reply(self, message: Message, text: str) -> None:
        self.replies.append((message, text))

    def send(self, room_id, text, mention=None, thread_id=None) -> None:
        self.sent.append({"room_id": room_id, "text": text, "mention": mention,
                          "thread_id": thread_id})

    def rooms(self) -> list[dict]:
        return [{"id": room_id, "name": name} for room_id, name in ROOMS.items()]

    def room_id(self, name: str) -> str:
        return next(room_id for room_id, room in ROOMS.items() if room == name)

    def room_name(self, room_id: str) -> str:
        return ROOMS.get(room_id, room_id)

    def person_name(self, message: Message) -> str | None:
        return person_name(message)  # the real rule, not a copy

    def room_document(self, room_id: str, name: str) -> str | None:
        return self.documents.get((room_id, name))


def message(body: str, sender: str = "@amiyasingh05:localhost", role: str | None = "owner",
            kind: str | None = None, room_id: str = "room-blast",
            thread_id: str | None = None) -> Message:
    """A message as Switch delivers it. A person has a role; an agent has none."""
    return Message(
        room_id=room_id,
        sender=sender,
        sender_name=PEOPLE.get(sender, "support"),
        body=body,
        message_id="msg-1",
        thread_id=thread_id,
        sequence=1,
        sender_kind=kind,
        sender_role=role,
    )
