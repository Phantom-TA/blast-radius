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
    # Anything else in braces must be a template value, so Console fills it in.
    assert placeholders - {"name", "order_id", "amount"} <= {"bridge"}


def test_no_word_incident_anywhere_agents_or_people_read():
    for path in [*SWITCH_DIR.rglob("*.md"), SWITCH_DIR / "template.yaml"]:
        for line in path.read_text(encoding="utf-8").lower().splitlines():
            assert "incident" not in line or "never use the word" in line, path
