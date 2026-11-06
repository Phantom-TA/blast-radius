"""The parts of the switch/ scripts that decide something, tested without a server."""

import importlib.util
from pathlib import Path

import pytest
import yaml

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


def test_the_import_fills_every_param_the_template_requires():
    document = yaml.safe_load((SWITCH_DIR / "template.yaml").read_text(encoding="utf-8"))
    required = {name for name, param in document["params"].items()
                if param.get("required") and "default" not in param}
    inputs = import_template.template_inputs(Path("/w"), "Discord", "strider5791", "phantom8817")
    assert required <= set(inputs)
    assert inputs["finance_lead"] == "strider5791"
    assert inputs["support_lead"] == "phantom8817"


def test_fill_people_puts_both_chat_usernames_in():
    text = "@{finance_lead} prepares refunds; @{support_lead} approves the fix."
    assert import_template.fill_people(text, "strider5791", "phantom8817") == (
        "@strider5791 prepares refunds; @phantom8817 approves the fix."
    )


class GroupGateway:
    """Answers /room-groups and /rooms separately, and records the changes."""

    def __init__(self, groups, rooms):
        self.groups, self.rooms, self.changes = groups, rooms, []

    def __call__(self, method, path, body=None):
        if method == "GET":
            return self.groups if path == "/room-groups" else self.rooms
        self.changes.append((method, path, body))
        return {}


def group(group_id, name="Blast Radius", room_count=0):
    return {"id": group_id, "name": name, "room_count": room_count,
            "created_at": "2026-11-05 06:46:33+00:00"}


def test_leftover_groups_are_the_ones_with_no_live_room():
    groups = [group("old"), group("live"), group("other", name="Payments")]
    rooms = [{"group_id": "live"}, {"group_id": "old", "archived": True}]
    assert [g["id"] for g in import_template.leftover_groups(groups, rooms)] == ["old"]


def test_an_empty_leftover_group_is_deleted_and_one_with_archived_rooms_renamed():
    gateway = GroupGateway([group("empty"), group("archived", room_count=5)], rooms=[])
    import_template.clear_leftover_groups(gateway)
    assert gateway.changes == [
        ("DELETE", "/room-groups/empty", None),
        ("PATCH", "/room-groups/archived", {"name": "Blast Radius (earlier, 2026-11-05)"}),
    ]


def test_a_group_in_use_is_left_alone():
    gateway = GroupGateway([group("live", room_count=2)], rooms=[{"group_id": "live"}])
    import_template.clear_leftover_groups(gateway)
    assert gateway.changes == []


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


def entry(entry_id, timestamp, body="Hello", name="support", kind="message"):
    return {"id": entry_id, "kind": kind, "sender_name": name, "body": body,
            "timestamp": timestamp}


def thread(root, *replies):
    return {"root": root, "replies": list(replies)}


class ContextReader:
    """Answers read_context from a list of pages, and records what it was asked."""

    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def call(self, operation, args, bound=True):
        self.asked.append((operation, args, bound))
        return self.pages.pop(0)


def test_room_messages_reads_every_page_and_returns_oldest_first():
    reader = ContextReader([
        {"threads": [thread(entry("c", 3000), entry("d", 4000))], "truncated": True,
         "oldest_timestamp": 3000},
        {"threads": [thread(entry("a", 1000)), thread(entry("b", 2000))], "truncated": False,
         "oldest_timestamp": 1000},
    ])
    messages = export_transcript.room_messages(reader, "room-1")
    assert [message["id"] for message in messages] == ["a", "b", "c", "d"]
    assert reader.asked == [
        ("read_context", {"room_id": "room-1", "limit": 200}, False),
        ("read_context", {"room_id": "room-1", "limit": 200,
                          "before": "1970-01-01T00:00:03+00:00"}, False),
    ]


def test_room_messages_skips_joins_and_never_repeats_a_message():
    reader = ContextReader([{
        "threads": [thread(entry("a", 1000)), thread(entry("a", 1000)),
                    thread(entry("j", 2000, kind="room_join"))],
        "truncated": False,
    }])
    assert [message["id"] for message in export_transcript.room_messages(reader, "r")] == ["a"]


def test_room_messages_stops_if_the_pages_stop_moving_back():
    page = {"threads": [thread(entry("a", 1000))], "truncated": True, "oldest_timestamp": 1000}
    reader = ContextReader([dict(page), dict(page)])
    assert len(export_transcript.room_messages(reader, "r")) == 1
    assert len(reader.asked) == 2


def test_each_room_is_read_by_an_agent_that_belongs_to_it():
    assert export_transcript.READERS == (
        ("support", "customer-sim"), ("blast-", "investigator"),
        ("finance-approvals", "treasurer"),
    )


def test_render_names_each_room_and_sender():
    text = export_transcript.render(
        [("support", [entry("a", 1000, "Charged twice", "phantom8817")])]
    )
    assert "## #support" in text
    assert "**phantom8817** (1970-01-01 00:00:01 UTC)" in text
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


def test_template_import_waits_longer_than_a_normal_gateway_call():
    # Creating the agents and rooms took about 80 seconds on a slow computer;
    # a 30 second wait gave up while the server was still working.
    assert import_template.TEMPLATE_TIMEOUT >= 300
