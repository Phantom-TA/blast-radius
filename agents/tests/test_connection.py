"""The WebSocket loop under stress: pings, repeats, evictions, refusals, crashes, drops."""

import asyncio
import json

import pytest

from agents.common import switch_client
from agents.common.switch_client import Credentials, Stop, SwitchAgent


class FakeSocket:
    def __init__(self, frames):
        self.frames = [json.dumps(frame) for frame in frames]
        self.sent = []

    async def send(self, text):
        self.sent.append(json.loads(text))

    def __aiter__(self):
        return self._frames()

    async def _frames(self):
        for frame in self.frames:
            yield frame


class FakeConnect:
    """Stands in for websockets' connect(): each call opens the next scripted socket."""

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.urls = []
        self.sockets = []

    def __call__(self, url, additional_headers=None):
        self.urls.append(url)
        script = self.scripts.pop(0)
        connect = self

        class Opened:
            async def __aenter__(self):
                if isinstance(script, BaseException):
                    raise script
                socket = FakeSocket(script)
                connect.sockets.append(socket)
                return socket

            async def __aexit__(self, *exc):
                return False

        return Opened()


def message_frame(sequence, body, addressed=True):
    return {
        "event": "message", "id": sequence,
        "data": {"room_id": "room-1", "payload": {
            "addressed": addressed, "sender": "@amiyasingh05:localhost",
            "sender_name": "amiyasingh05", "sender_role": "owner",
            "message_id": f"msg-{sequence}", "body": body,
        }},
    }


@pytest.fixture
def agent(monkeypatch, tmp_path):
    credentials = Credentials("investigator", "agent-1", "key", "conn-1")
    monkeypatch.setattr(Credentials, "load", classmethod(lambda cls, name: credentials))
    monkeypatch.setattr(switch_client, "STATE_DIR", tmp_path)

    real_sleep = asyncio.sleep

    async def no_wait(seconds):
        await real_sleep(0)

    monkeypatch.setattr(switch_client.asyncio, "sleep", no_wait)
    return SwitchAgent("investigator", "http://localhost:63238")


def serve(agent, monkeypatch, scripts, handle):
    connect = FakeConnect(scripts)
    monkeypatch.setattr(switch_client, "connect", connect)

    async def go():
        await asyncio.wait_for(agent._serve(handle), timeout=5)

    asyncio.run(go())
    return connect


STOP = {"event": "evicted", "data": {"code": "closed", "reason": "test over"}}


def test_answers_every_ping_with_a_pong_carrying_the_cursor(agent, monkeypatch):
    connect = serve(agent, monkeypatch, [[
        {"event": "connection_state", "data": {"cursor": 7, "generation": 2, "rooms": []}},
        {"event": "ping", "data": {}},
        {"event": "ping", "data": {}},
        STOP,
    ]], handle=lambda message: None)
    assert connect.sockets[0].sent == [{"type": "pong", "cursor": 7}] * 2


def listen_and_work(agent, monkeypatch, frames, handle, until):
    """Read one scripted socket, then let the worker finish until until() holds."""
    async def run():
        monkeypatch.setattr(switch_client, "connect", FakeConnect([frames]))
        queue = asyncio.Queue()
        worker = asyncio.create_task(agent._work(queue, handle))
        await agent._listen(queue)
        for _ in range(200):
            if until():
                break
            await asyncio.sleep(0.01)
        worker.cancel()

    asyncio.run(run())


def test_handles_only_addressed_messages_and_each_one_once(agent, monkeypatch):
    handled = []
    frames = [
        message_frame(1, "@investigator first"),
        message_frame(1, "@investigator first"),  # the same event delivered twice
        message_frame(2, "just chatter", addressed=False),
        message_frame(3, "@investigator second"),
    ]
    listen_and_work(agent, monkeypatch, frames, lambda message: handled.append(message.body),
                    until=lambda: agent.cursor == 3)
    assert handled == ["@investigator first", "@investigator second"]
    assert agent.cursor == 3


def test_a_handler_that_crashes_does_not_stop_the_next_message(agent, monkeypatch):
    handled = []

    def handle(message):
        handled.append(message.body)
        if "boom" in message.body:
            raise RuntimeError("boom")

    listen_and_work(agent, monkeypatch, [message_frame(1, "boom"), message_frame(2, "after")],
                    handle, until=lambda: agent.cursor == 2)
    assert handled == ["boom", "after"]
    # Past the crash too, so a restart doesn't replay the message that crashed it.
    assert agent.cursor == 2


def test_the_cursor_is_saved_only_after_a_message_is_handled(agent, monkeypatch):
    listen_and_work(agent, monkeypatch, [message_frame(5, "@investigator hi")],
                    lambda message: None, until=lambda: agent.cursor == 5)
    assert agent.cursor_file.read_text() == "5"


@pytest.mark.parametrize("code", ["taken_over", "closed"])
def test_a_final_eviction_stops_without_reconnecting(agent, monkeypatch, code):
    connect = serve(agent, monkeypatch, [[{"event": "evicted", "data": {"code": code}}]],
                    handle=lambda message: None)
    assert len(connect.urls) == 1


def test_any_other_eviction_reconnects_from_the_cursor(agent, monkeypatch):
    connect = serve(agent, monkeypatch, [
        [{"event": "connection_state", "data": {"cursor": 9, "generation": 4, "rooms": []}},
         {"event": "evicted", "data": {"code": "superseded"}}],
        [STOP],
    ], handle=lambda message: None)
    assert len(connect.urls) == 2
    assert "start_from=9" in connect.urls[1] and "expected_generation=4" in connect.urls[1]


def test_a_refusal_stops(agent, monkeypatch):
    connect = serve(agent, monkeypatch, [
        [{"event": "refused", "data": {"status": 401, "detail": "bad key"}}],
    ], handle=lambda message: None)
    assert len(connect.urls) == 1


def test_a_dropped_or_unreachable_server_is_retried(agent, monkeypatch):
    connect = serve(agent, monkeypatch, [
        ConnectionRefusedError("server down"),
        OSError("network changed"),
        [STOP],
    ], handle=lambda message: None)
    assert len(connect.urls) == 3


def test_a_gap_moves_the_cursor_to_where_the_server_resumed(agent, monkeypatch):
    serve(agent, monkeypatch, [[{"event": "gap", "data": {"resumed_at": 40}}, STOP]],
          handle=lambda message: None)
    assert agent.cursor == 40


def test_stop_is_an_exception_the_loop_ends_on():
    assert issubclass(Stop, Exception)
