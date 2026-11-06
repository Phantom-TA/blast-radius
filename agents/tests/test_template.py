"""The Console template is generated from switch/; check it is current and well formed."""

import importlib.util
import re
from pathlib import Path

import yaml

SWITCH_DIR = Path(__file__).resolve().parents[2] / "switch"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_template", SWITCH_DIR / "build_template.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def template() -> dict:
    return yaml.safe_load((SWITCH_DIR / "template.yaml").read_text(encoding="utf-8"))


def test_template_yaml_is_up_to_date():
    assert (SWITCH_DIR / "template.yaml").read_text(encoding="utf-8") == load_builder().build(), (
        "switch/template.yaml is stale. Run: python switch/build_template.py"
    )


def test_template_is_version_2_with_the_rooms_and_agents():
    document = template()
    assert document["version"] == 2
    resources = document["resources"]
    kinds = {key: resource["type"] for key, resource in resources.items()}
    assert kinds == {"support": "agent", "fixer": "agent", "blast_radius": "group",
                     "support_room": "room", "finance_room": "room"}
    assert resources["support_room"]["name"] == "support"
    assert resources["finance_room"]["name"] == "finance-approvals"
    assert "customer-sim" in resources["support_room"]["agents"]
    assert "treasurer" in resources["finance_room"]["agents"]
    assert "@{support.name}" in resources["support_room"]["kickoff"]


def test_every_agent_has_the_required_fields():
    for key, resource in template()["resources"].items():
        if resource["type"] == "agent":
            for field in ("instructions", "provider", "machine", "directory"):
                assert resource.get(field), f"{key} has no {field}"


def test_rooms_and_links_only_name_resources_that_exist():
    resources = template()["resources"]
    rooms = {key for key, resource in resources.items() if resource["type"] == "room"}
    for link in resources["blast_radius"]["links"]:
        assert {link["from"], link["to"]} <= rooms
    for key in rooms:
        assert resources[key]["group"] == "blast_radius"


def test_instructions_are_inlined_and_nothing_is_left_to_include():
    text = (SWITCH_DIR / "template.yaml").read_text(encoding="utf-8")
    assert "@include" not in text.split("\n", 1)[1]
    assert "{{" not in text
    support = template()["resources"]["support"]["instructions"]
    blast_brief = (SWITCH_DIR / "room-instructions" / "blast-room.md").read_text().strip()
    assert support.rstrip().endswith(blast_brief)


def test_apology_placeholders_match_the_ones_the_email_code_accepts():
    support = template()["resources"]["support"]["instructions"]
    placeholders = set(re.findall(r"\{(\w+)\}", support))
    assert {"name", "order_id", "amount"} <= placeholders
    # Nothing else in braces but the two string params: an agent's fields can't use a bridge
    # or room param (the server only resolves those for rooms), and anything else would be
    # filled in.
    assert placeholders == {"name", "order_id", "amount", "support_lead", "finance_lead"}


def test_every_param_an_agent_uses_is_declared():
    document = template()
    for param in ("support_lead", "finance_lead"):
        assert document["params"][param]["type"] == "string"
        assert document["params"][param]["required"] is True


def test_agents_name_people_by_param_not_by_creator():
    # In an agent's instructions Switch fills {$creator} with the Switch account's name
    # ("Admin"), which Discord doesn't know: Support could neither add nor ping the
    # Finance lead. Rooms resolve {$creator} to the chat username, so they keep it.
    resources = template()["resources"]
    for key in ("support", "fixer"):
        assert "{$creator}" not in resources[key]["instructions"]
    assert resources["support_room"]["users"] == ["{$creator}"]


def test_support_pastes_the_apology_where_people_can_read_it():
    # Discord shows a room document only as "created room document …".
    support = template()["resources"]["support"]["instructions"]
    assert "paste the document's whole content as a quote" in support


def test_support_and_fixer_are_open_so_the_support_lead_can_reach_them():
    resources = template()["resources"]
    assert resources["support"]["addressing"] == "anyone"
    assert resources["fixer"]["addressing"] == "anyone"


def test_rooms_are_public_so_both_people_see_them():
    resources = template()["resources"]
    assert resources["support_room"]["channel_type"] == "channel_public"
    assert resources["finance_room"]["channel_type"] == "channel_public"
    assert "channel_type: channel_public" in resources["support"]["instructions"]


def test_the_template_uses_discord_when_it_can_and_mattermost_otherwise():
    assert template()["params"]["bridge"]["default"] == ["Discord", "Mattermost", "$first"]


def test_the_support_lead_approves_the_work_and_the_finance_lead_the_money():
    resources = template()["resources"]
    support = resources["support"]["instructions"]
    assert "@{support_lead} to approve the wording" in support
    assert "ask @{finance_lead} to mention the Treasurer" in support
    assert "ask @{support_lead} to approve the change" in resources["fixer"]["instructions"]


def test_no_instruction_assumes_a_particular_chat_app():
    for key in ("support", "fixer"):
        assert "mattermost" not in template()["resources"][key]["instructions"].lower()


def test_no_word_incident_anywhere_agents_or_people_read():
    for path in [*SWITCH_DIR.rglob("*.md"), SWITCH_DIR / "template.yaml"]:
        for line in path.read_text(encoding="utf-8").lower().splitlines():
            assert "incident" not in line or "never use the word" in line, path
