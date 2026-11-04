from agents.common.switch_client import Credentials, Message, SwitchAgent


def frame(**payload):
    return {
        "event": "message",
        "id": 42,
        "data": {
            "room_id": "room-1",
            "payload": {
                "addressed": True,
                "sender": "@amiyasingh05:localhost",
                "sender_name": "amiyasingh05",
                "message_id": "msg-9",
                "body": "@treasurer execute rb-123",
                **payload,
            },
        },
    }


def test_message_from_event():
    message = Message.from_event(frame(sender_role="owner", thread_id="root-1"))
    assert message.room_id == "room-1"
    assert message.sender == "@amiyasingh05:localhost"
    assert message.sender_kind is None
    assert message.sender_role == "owner"
    assert message.sequence == 42
    assert message.reply_thread == "root-1"
    assert message.text_without_mentions() == "execute rb-123"


def test_a_top_level_message_is_answered_in_its_own_thread():
    assert Message.from_event(frame()).reply_thread == "msg-9"


def test_socket_url_reuses_the_connection_id_and_resumes_from_the_cursor(monkeypatch, tmp_path):
    from agents.common import switch_client

    credentials = Credentials("treasurer", "agent-1", "key", "conn-1")
    monkeypatch.setattr(Credentials, "load", classmethod(lambda cls, name: credentials))
    monkeypatch.setattr(switch_client, "STATE_DIR", tmp_path)
    agent = SwitchAgent("treasurer", "http://localhost:63238")
    url = agent._socket_url()
    assert url.startswith("ws://localhost:63238/agents/agent-1/connection/ws?")
    assert "connection_id=conn-1" in url and "filter=addressed" in url
    assert "start_from" not in url

    agent.cursor, agent.generation = 17, 3
    url = agent._socket_url()
    assert "start_from=17" in url and "expected_generation=3" in url


def test_the_cursor_survives_a_restart(monkeypatch, tmp_path):
    from agents.common import switch_client

    credentials = Credentials("investigator", "agent-1", "key", "conn-1")
    monkeypatch.setattr(Credentials, "load", classmethod(lambda cls, name: credentials))
    monkeypatch.setattr(switch_client, "STATE_DIR", tmp_path)

    first = SwitchAgent("investigator", "http://localhost:63238")
    assert first.cursor == 0
    first._advance(25)
    first._advance(20)  # cursors only move forward
    assert first.cursor == 25

    second = SwitchAgent("investigator", "http://localhost:63238")
    assert second.cursor == 25
    assert "start_from=25" in second._socket_url()


def test_rooms_have_an_id_and_leave_out_archived_ones(monkeypatch, tmp_path):
    from agents.common import switch_client

    credentials = Credentials("customer-sim", "agent-1", "key", "conn-1")
    monkeypatch.setattr(Credentials, "load", classmethod(lambda cls, name: credentials))
    monkeypatch.setattr(switch_client, "STATE_DIR", tmp_path)
    agent = SwitchAgent("customer-sim", "http://localhost:63238")
    # The shape list_rooms answers with on switch-core 0.31.0.
    listed = [
        {"room_id": "r1", "name": "support", "description": "", "connected": False,
         "archived": False},
        {"room_id": "r2", "name": "blast-ORD-1", "description": "", "connected": False,
         "archived": True},
    ]
    monkeypatch.setattr(agent, "call", lambda operation, args=None, bound=True: listed)
    assert [room["id"] for room in agent.rooms()] == ["r1"]
    assert agent.room_id("#support") == "r1"
    assert agent.room_name("r1") == "support"
