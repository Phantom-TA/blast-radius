"""The parts of the switch/ scripts that decide something, tested without a server."""

import importlib.util
from pathlib import Path

import pytest

SWITCH_DIR = Path(__file__).resolve().parents[2] / "switch"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SWITCH_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


import_template = load("import_template")
archive_rooms = load("archive_rooms")
export_transcript = load("export_transcript")

DISCORD = {"type": "discord", "display_name": "Blast Radius Server"}
MATTERMOST = {"type": "mattermost", "display_name": "Mattermost"}
SLACK = {"type": "slack", "display_name": "Our Slack"}


class FakeGateway:
    def __init__(self, rooms=None, fail_on=None):
        self.rooms = rooms or []
        self.fail_on = fail_on
        self.calls = []

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if self.fail_on and self.fail_on in path:
            raise SystemExit(f"{path} failed with 400")
        return self.rooms if method == "GET" else {}


def context(*apps):
    return {"messaging_apps": {"connected": [
        {"name": name, "your_usernames": usernames} for name, usernames in apps
    ]}}


@pytest.mark.parametrize("bridges, expected", [
    ([MATTERMOST, DISCORD], "Blast Radius Server"),
    ([DISCORD], "Blast Radius Server"),
    ([MATTERMOST], "Mattermost"),
    ([SLACK, MATTERMOST], "Mattermost"),
    ([SLACK], "Our Slack"),
])
def test_pick_bridge_prefers_discord_then_mattermost(bridges, expected):
    assert import_template.pick_bridge(bridges) == expected


def test_pick_bridge_says_what_to_do_when_there_is_none():
    with pytest.raises(SystemExit, match="Also run Mattermost"):
        import_template.pick_bridge([])


def test_owner_username_is_the_one_on_the_chosen_app():
    linked = context(("Mattermost", ["amiya-mm"]), ("Blast Radius Server", ["amiya-discord"]))
    assert import_template.owner_username(linked, "Blast Radius Server") == "amiya-discord"
    assert import_template.owner_username(linked, "Mattermost") == "amiya-mm"


def test_owner_username_refuses_an_app_that_is_not_linked():
    with pytest.raises(SystemExit, match="isn't linked yet"):
        import_template.owner_username(context(("Mattermost", [])), "Mattermost")


def test_support_lead_is_added_to_the_two_rooms_only():
    rooms = [{"id": "1", "name": "support"}, {"id": "2", "name": "finance-approvals"},
             {"id": "3", "name": "town-square"}]
    gateway = FakeGateway(rooms)
    import_template.add_support_lead(gateway, "tushar")
    posts = [call for call in gateway.calls if call[0] == "POST"]
    assert posts == [
        ("POST", "/rooms/1/users", {"user_names": ["tushar"]}),
        ("POST", "/rooms/2/users", {"user_names": ["tushar"]}),
    ]


def test_failing_to_add_the_support_lead_does_not_stop_the_setup(capsys):
    gateway = FakeGateway([{"id": "1", "name": "support"}], fail_on="/users")
    import_template.add_support_lead(gateway, "tushar")
    assert "Couldn't add tushar to #support" in capsys.readouterr().out


def chat_message(seq, body="Hello", name="support"):
    return {"seq": seq, "body": body, "sentAt": "2026-11-05T10:00:00Z", "sender": {"name": name}}


def test_room_messages_reads_every_page_and_returns_oldest_first():
    pages = [
        {"messages": [chat_message(3), chat_message(4)], "hasMore": True},
        {"messages": [chat_message(1), chat_message(2)], "hasMore": False},
    ]
    requested = []

    def gateway(method, path):
        requested.append(path)
        return pages.pop(0)

    messages = export_transcript.room_messages(gateway, "room-1")
    assert [message["seq"] for message in messages] == [1, 2, 3, 4]
    assert requested == ["/chats/room-1/messages?limit=200",
                         "/chats/room-1/messages?limit=200&beforeSeq=3"]


def test_story_rooms_follow_the_story_and_skip_the_rest():
    rooms = [{"name": "finance-approvals"}, {"name": "town-square"},
             {"name": "blast-ORD-100953"}, {"name": "support"}]
    assert [room["name"] for room in export_transcript.story_rooms(rooms)] == [
        "support", "blast-ORD-100953", "finance-approvals",
    ]


def test_render_names_each_room_and_sender():
    text = export_transcript.render([("support", [chat_message(1, "Charged twice", "tushar")])])
    assert "## #support" in text
    assert "**tushar** (2026-11-05T10:00:00Z)" in text
    assert "Charged twice" in text
    assert "simulated" in text


def test_archiving_keeps_the_room_and_deleting_retires_its_channel():
    rooms = [{"id": "1", "name": "blast-ORD-100953"}]
    gateway = FakeGateway()
    archive_rooms.clear_rooms(gateway, rooms)
    archive_rooms.clear_rooms(gateway, rooms, delete=True)
    assert gateway.calls == [
        ("POST", "/rooms/bulk-archive", {"room_ids": ["1"], "archived": True}),
        ("POST", "/rooms/bulk-delete", {"room_ids": ["1"], "retire_channel": True}),
    ]
