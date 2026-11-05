"""A small client for the Switch agent protocol, shared by the Investigator and the Treasurer.

Protocol: https://docs.switchagents.ai/switch-rooms/internals/agent-protocol.md
Checked against Switch server 0.31.0, run by Switch Console 0.40.1.
"""

import asyncio
import json
import logging
import os
import platform
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

log = logging.getLogger("switch")

AGENTS_DIR = Path(__file__).resolve().parent.parent
SECRETS_DIR = AGENTS_DIR / ".secrets"
REGISTRATION_KEY_FILE = SECRETS_DIR / "registration_key"
SERVER_URL_FILE = SECRETS_DIR / "server_url"
STATE_DIR = AGENTS_DIR / ".state"

# Eviction codes after which reconnecting would steal the connection back or can never work.
FINAL_EVICTIONS = {"taken_over", "closed"}
MAX_RECONNECT_DELAY = 30


class SwitchError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(f"Switch answered {status}: {detail}")
        self.status = status
        self.detail = detail


class Stop(Exception):
    """The server told us not to reconnect."""


def console_data_dir() -> Path:
    home = Path.home()
    system = platform.system()
    if system == "Darwin":
        return home / "Library" / "Application Support" / "switchdash"
    if system == "Windows":
        return Path(os.environ.get("APPDATA", home)) / "switchdash"
    return Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "switchdash"


def find_server_url() -> str:
    """SWITCH_URL, else agents/.secrets/server_url, else the local server Switch Console runs.

    Console picks the local server's ports itself and writes them to ports.json.
    """
    if os.environ.get("SWITCH_URL"):
        return os.environ["SWITCH_URL"].rstrip("/")
    if SERVER_URL_FILE.exists():
        return SERVER_URL_FILE.read_text().strip().rstrip("/")
    ports = console_data_dir() / "local-switch-server" / "ports.json"
    if ports.exists():
        return f"http://localhost:{json.loads(ports.read_text())['api']}"
    raise SystemExit(
        "Can't find the Switch server. Start it in Switch Console, or set SWITCH_URL "
        "(for example SWITCH_URL=http://localhost:63238)."
    )


def http_json(method: str, url: str, token: str | None = None, body=None, headers=None):
    request = urllib.request.Request(
        url, data=None if body is None else json.dumps(body).encode(), method=method
    )
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        raise SwitchError(error.code, error.read().decode(errors="replace")[:500]) from None
    return json.loads(raw) if raw else None


@dataclass
class Credentials:
    name: str
    agent_id: str
    api_key: str
    connection_id: str

    @staticmethod
    def path(name: str) -> Path:
        return SECRETS_DIR / f"{name}.json"

    @classmethod
    def load(cls, name: str) -> "Credentials":
        path = cls.path(name)
        if not path.exists():
            raise SystemExit(f"{name} isn't registered yet. Run: python scripts/register_agents.py")
        return cls(**json.loads(path.read_text()))

    def save(self) -> None:
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        path = self.path(self.name)
        path.write_text(json.dumps(asdict(self), indent=2))
        path.chmod(0o600)


def register_agent(
    server_url: str, registration_key: str, name: str, description: str, display_name: str,
    overwrite: bool = False,
) -> Credentials:
    """POST /agents once. The API key comes back only in this response, so save it now."""
    result = http_json(
        "POST",
        f"{server_url}/agents",
        registration_key,
        {
            "name": name,
            "description": description,
            "display_name": display_name,
            "connector_type": "blast-radius-python",
            "integration_profile": {
                "connection_model": "always_on",
                "message_exchange": True,
                "pre_invocation_mediation": [],
                "post_invocation_mediation": [],
                "event_reporting": [],
            },
            "overwrite": overwrite,
        },
    )
    credentials = Credentials(name, result["id"], result["api_key"], str(uuid.uuid4()))
    credentials.save()
    return credentials


@dataclass
class Message:
    room_id: str
    sender: str
    sender_name: str
    body: str
    message_id: str
    thread_id: str | None
    sequence: int
    # "platform" when Switch itself posted it; otherwise absent (None), for people
    # and agents alike, so it can't tell a person from an agent on its own.
    sender_kind: str | None = None
    # "owner", "admin" or "member" when a person that a Switch user has claimed sent
    # it. None for an agent, for Switch itself, and for an unlinked chat account.
    sender_role: str | None = None

    @classmethod
    def from_event(cls, frame: dict) -> "Message":
        data = frame["data"]
        payload = data["payload"]
        return cls(
            room_id=data["room_id"],
            sender=payload.get("sender", ""),
            sender_name=payload.get("sender_name") or payload.get("sender", ""),
            body=payload.get("body", ""),
            message_id=payload.get("message_id", ""),
            thread_id=payload.get("thread_id"),
            sequence=frame["id"],
            sender_kind=payload.get("sender_kind"),
            sender_role=payload.get("sender_role"),
        )

    @property
    def reply_thread(self) -> str:
        return self.thread_id or self.message_id

    def text_without_mentions(self) -> str:
        return re.sub(r"@[\w.\-]+", "", self.body).strip()


PERSON_ROLES = {"owner", "admin", "member"}


def person_name(message: Message) -> str | None:
    """The sender's chat username if a person Switch recognises sent the message, else None.

    Switch puts the person's workspace role on every message it delivers from a
    claimed person, and nothing on a message from an agent or from Switch itself.
    The name is the chat username, so it also works in an @mention.
    """
    if message.sender_kind == "platform" or message.sender_role not in PERSON_ROLES:
        return None
    return message.sender_name or None


class SwitchAgent:
    """One registered agent: its HTTP calls, plus a WebSocket that delivers what addresses it."""

    def __init__(self, name: str, server_url: str | None = None):
        self.credentials = Credentials.load(name)
        self.server_url = server_url or find_server_url()
        self.cursor_file = STATE_DIR / f"{name}.cursor"
        # Resume where the last run stopped, so a restart doesn't miss what came meanwhile.
        self.cursor = int(self.cursor_file.read_text()) if self.cursor_file.exists() else 0
        self.generation = None
        self._queued_up_to = self.cursor

    def _advance(self, cursor: int) -> None:
        if cursor > self.cursor:
            self.cursor = cursor
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            self.cursor_file.write_text(str(cursor))

    @property
    def name(self) -> str:
        return self.credentials.name

    @property
    def agent_id(self) -> str:
        return self.credentials.agent_id

    def _agent_url(self, suffix: str) -> str:
        return f"{self.server_url}/agents/{self.agent_id}{suffix}"

    def call(self, operation: str, args: dict | None = None, bound: bool = True):
        """POST /agents/{id}/ops/{operation}, arguments unwrapped in the body.

        bound sends the connection id, which ties the call to the room the connection
        is in. Leave it off before the socket is open: an unknown connection id is a 409.
        """
        headers = {"X-Switch-Connection-Id": self.credentials.connection_id} if bound else {}
        result = http_json(
            "POST",
            self._agent_url(f"/ops/{operation}"),
            self.credentials.api_key,
            args or {},
            headers,
        )
        return result["result"]

    def post(self, room_id: str, text: str) -> None:
        """POST /agents/{id}/message: a top-level message, no connection needed."""
        http_json(
            "POST",
            self._agent_url("/message"),
            self.credentials.api_key,
            {"room_id": room_id, "content": text},
        )

    def connect_to_room(self, room_id: str) -> dict:
        """Bind this connection to one room. post_message and document loads act on that room."""
        return self.call(
            "connect_to_room", {"room_id": room_id, "include_general_instructions": False}
        )

    def reply(self, message: Message, text: str) -> None:
        """Answer in the thread of the message that asked."""
        self.connect_to_room(message.room_id)
        self.call("post_message", {"body": text, "thread_id": message.reply_thread})

    def rooms(self) -> list[dict]:
        """The rooms this agent is in and that aren't archived, each {id, name, description}.

        list_rooms names the id room_id; this copies it to id.
        """
        return [
            {**room, "id": room["room_id"]}
            for room in self.call("list_rooms", bound=False)
            if not room.get("archived")
        ]

    def room_id(self, name: str) -> str:
        for room in self.rooms():
            if room["name"].lstrip("#") == name.lstrip("#"):
                return room["id"]
        raise LookupError(f"{self.name} isn't in a room named {name}")

    def room_name(self, room_id: str) -> str:
        for room in self.rooms():
            if room["id"] == room_id:
                return room["name"]
        return room_id

    def person_name(self, message: Message) -> str | None:
        return person_name(message)

    def sender_is_person(self, message: Message) -> bool:
        return person_name(message) is not None

    def is_owner(self, name: str) -> bool:
        """Whether this chat username is one of the accounts this agent's owner has linked."""
        context = self.call("get_my_context", bound=False)
        usernames = (
            username
            for app in context["messaging_apps"]["connected"]
            for username in app.get("your_usernames", [])
        )
        return name.casefold() in {username.casefold() for username in usernames}

    def send(self, room_id: str, text: str, mention: list[str] | None = None,
             thread_id: str | None = None) -> None:
        """Post into a room. Names in mention are @mentioned, which notifies them."""
        self.connect_to_room(room_id)
        if mention:
            try:
                self.call("send_targeted_message",
                          {"body": text, "target_names": mention, "thread_id": thread_id})
                return
            except SwitchError as error:
                if "Targets not in room" not in error.detail:
                    raise
                # Someone on Discord can post in a public channel without being a room
                # participant, and Switch refuses to target them. The answer still goes out.
                log.info("%s not in room %s, naming them instead", mention, room_id)
                text = " ".join(f"@{name}" for name in mention) + " " + text
        self.call("post_message", {"body": text, "thread_id": thread_id})

    def room_document(self, room_id: str, name: str) -> str | None:
        """The content of the room document with this name, or None if the room has none."""
        documents = self.connect_to_room(room_id).get("documents") or []
        for document in documents:
            if document.get("name") == name:
                loaded = self.call("load_internal_documents", {"ids": [document["id"]]})
                return loaded[0]["content"]
        return None

    def run(self, handle: Callable[[Message], None]) -> None:
        """Serve forever: answer pings, reconnect after drops, hand addressed messages to handle."""
        asyncio.run(self._serve(handle))

    def _socket_url(self) -> str:
        params = {
            "connection_id": self.credentials.connection_id,
            "scope": "all",
            "filter": "addressed",
            "client": "blast-radius",
        }
        if self.cursor:
            params["start_from"] = self.cursor
        if self.generation is not None:
            params["expected_generation"] = self.generation
        socket_base = re.sub(r"^http", "ws", self.server_url)
        query = urllib.parse.urlencode(params)
        return f"{socket_base}/agents/{self.agent_id}/connection/ws?{query}"

    async def _serve(self, handle: Callable[[Message], None]) -> None:
        queue: asyncio.Queue[Message] = asyncio.Queue()
        worker = asyncio.create_task(self._work(queue, handle))
        delay = 1
        try:
            while True:
                try:
                    await self._listen(queue)
                    delay = 1
                except Stop as stop:
                    log.error("%s: stopping, %s", self.name, stop)
                    return
                except (OSError, ConnectionClosed, InvalidHandshake) as error:
                    log.warning("%s: connection dropped (%s)", self.name, error)
                log.info("%s: reconnecting in %ss", self.name, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, MAX_RECONNECT_DELAY)
        finally:
            worker.cancel()

    async def _listen(self, queue: asyncio.Queue) -> None:
        headers = {"Authorization": f"Bearer {self.credentials.api_key}"}
        async with connect(self._socket_url(), additional_headers=headers) as socket:
            async for raw in socket:
                frame = json.loads(raw)
                kind = frame.get("event")
                data = frame.get("data") or {}
                if kind == "ping":
                    await socket.send(json.dumps({"type": "pong", "cursor": self.cursor}))
                elif kind == "connection_state":
                    self._advance(data.get("cursor") or 0)
                    self.generation = data.get("generation")
                    log.info("%s: connected, covering %d rooms", self.name, len(data.get("rooms", [])))
                elif kind == "gap":
                    self._advance(data.get("resumed_at") or 0)
                elif kind == "evicted":
                    if data.get("code") in FINAL_EVICTIONS:
                        raise Stop(f"evicted: {data.get('code')} {data.get('reason')}")
                    return
                elif kind == "refused":
                    raise Stop(f"refused: {data.get('status')} {data.get('detail')}")
                elif kind == "message" and frame.get("id", 0) > self._queued_up_to:
                    self._queued_up_to = frame["id"]
                    if data.get("payload", {}).get("addressed"):
                        queue.put_nowait(Message.from_event(frame))
                    else:
                        self._advance(frame["id"])

    async def _work(self, queue: asyncio.Queue, handle: Callable[[Message], None]) -> None:
        """Handle one message at a time, off the socket loop, so pings never wait on work."""
        while True:
            message = await queue.get()
            try:
                await asyncio.to_thread(handle, message)
            except Exception:
                log.exception("%s: failed on message %s", self.name, message.message_id)
            self._advance(message.sequence)
