"""Import switch/template.yaml into Switch without clicking through Switch Console.

    python switch/import_template.py           # check it, then create the agents and rooms
    python switch/import_template.py --check   # only ask Switch whether it would work
    python switch/import_template.py --update  # give the existing agents the current instructions
    python switch/import_template.py --support-lead tushar  # name the second person on Discord

It does what Console's Templates page does: as the owner, it sends the document
to the Gateway API (POST /gateway/rooms/from-template-document), and the server
creates the Support and Fixer agents on this machine, then #support and
#finance-approvals. Run scripts/register_agents.py first: the rooms name the
Python agents it registers.

Whoever runs this is the Finance lead. The Support lead defaults to the same person,
which is the one-person path; BLAST_SUPPORT_LEAD does the same as --support-lead.
"""

import argparse
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.common.gateway import gateway_session  # noqa: E402
from agents.common.switch_client import SwitchAgent, find_server_url  # noqa: E402

TEMPLATE = ROOT / "switch" / "template.yaml"
GROUP = "Blast Radius"
ROOMS = {"support", "finance-approvals"}
WORKSPACE = ROOT / "demo-workspace" / "payments-service"
# The apology placeholders are meant to stay as written: the Treasurer's emails fill them.
EXPECTED_WARNINGS = {"name", "order_id", "amount"}


def pick_bridge(bridges: list[dict]) -> str:
    """The messaging app's display name: Discord if connected, then Mattermost, else the first."""
    if not bridges:
        raise SystemExit("This Switch server has no messaging app. In Switch Console, turn on "
                         "'Also run Mattermost' on the server's page (Docker must be running).")
    for platform in ("discord", "mattermost"):
        for bridge in bridges:
            if bridge["type"] == platform:
                return bridge["display_name"]
    return bridges[0]["display_name"]


def default_bridge() -> str:
    return pick_bridge(SwitchAgent("customer-sim").call("list_bridges", bound=False))


def owner_username(context: dict, bridge: str) -> str:
    """The owner's username on this messaging app, which is what {$creator} becomes there."""
    for app in context["messaging_apps"]["connected"]:
        if app["name"] == bridge and app.get("your_usernames"):
            return app["your_usernames"][0]
    raise SystemExit(f"Your {bridge} account isn't linked yet (see switch/SETUP.md, step 2).")


def add_support_lead(gateway, username: str) -> None:
    """Add the Support lead to the rooms.

    Done here rather than in the template's users list, which would name one person
    twice on the one-person path. The rooms are public, so failing here isn't fatal.
    """
    for room in gateway("GET", "/rooms"):
        if room["name"] in ROOMS:
            try:
                gateway("POST", f"/rooms/{room['id']}/users", {"user_names": [username]})
                print(f"Added {username} to #{room['name']}.")
            except SystemExit as error:
                print(f"Couldn't add {username} to #{room['name']}: {error}")


def update_instructions(gateway, document: str, creator: str, support_lead: str) -> int:
    """Put the template's current instructions and addressing on the agents it created earlier.

    Console fills {$creator} in when it creates an agent; this fills it the same way.
    """
    sim = SwitchAgent("customer-sim")
    agents = {agent["name"]: agent["id"] for agent in sim.call("list_agents", bound=False)}
    resources = yaml.safe_load(document)["resources"]
    for key, resource in resources.items():
        if resource["type"] != "agent":
            continue
        name = resource["name"]
        if name not in agents:
            print(f"{name} doesn't exist yet; run this script without --update first.")
            return 1
        if resource.get("addressing") == "anyone":
            gateway("PUT", f"/agents/{agents[name]}/addressing-policy", {"policy": None})
        current = gateway("GET", f"/management/agents/{agents[name]}")["definition"]
        instructions = (resource["instructions"]
                        .replace("{$creator}", creator)
                        .replace("{support_lead}", support_lead))
        if current.get("instructions") == instructions:
            print(f"{name}: instructions already current")
            continue
        gateway("PATCH", f"/management/agents/{agents[name]}",
                {"definition": {**current, "instructions": instructions}})
        print(f"{name}: instructions updated. Type !reset @{name} in a room it's in "
              "so a running session picks them up.")
    return 0


def already_imported() -> bool:
    try:
        SwitchAgent("customer-sim").room_id("support")
        return True
    except LookupError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only validate the template")
    parser.add_argument("--update", action="store_true",
                        help="refresh the instructions of agents this template created")
    parser.add_argument("--workspace", type=Path, default=WORKSPACE,
                        help="the Fixer's folder (default: demo-workspace/payments-service)")
    parser.add_argument("--bridge",
                        help="messaging app display name (default: Discord's, else Mattermost's)")
    parser.add_argument("--support-lead", default=os.environ.get("BLAST_SUPPORT_LEAD"),
                        help="the Support lead's chat username (default: you)")
    args = parser.parse_args()

    gateway = gateway_session(find_server_url())
    document = TEMPLATE.read_text(encoding="utf-8")
    result = gateway("POST", "/templates/validate", {"content": document})
    problems = result["errors"] + [
        warning for warning in result["warnings"] if warning.get("subject") not in EXPECTED_WARNINGS
    ]
    for problem in problems:
        print(f"- {problem['code']}: {problem['message']}")
    if not result["ok"] or result["blocked"]:
        print("Switch would refuse this template.")
        return 1
    print("Switch accepts the template.")
    if args.check:
        return 0

    bridge = args.bridge or default_bridge()
    context = SwitchAgent("customer-sim").call("get_my_context", bound=False)
    creator = owner_username(context, bridge)
    support_lead = args.support_lead or creator
    if args.update:
        return update_instructions(gateway, document, creator, support_lead)

    if already_imported():
        print("Already imported: customer-sim is in #support. Nothing to do. "
              "To use another messaging app, see switch/SETUP.md.")
        return 0

    # A group left over from an earlier import (its rooms gone) would make the name
    # "Blast Radius" ambiguous, and Support could no longer file its rooms under it.
    for group in gateway("GET", "/room-groups"):
        if group.get("name") == GROUP and not group.get("room_count"):
            gateway("DELETE", f"/room-groups/{group['id']}")
            print(f"Removed an empty \"{GROUP}\" group left over from an earlier import.")

    workspace = args.workspace.resolve()
    if not workspace.exists():
        # make scenario recreates it with the payment service; the Fixer only starts
        # working there once it is addressed.
        workspace.mkdir(parents=True)
        print(f"Created {workspace} for now. `make scenario` fills it.")

    gateway("POST", "/rooms/from-template-document", {
        "template": document,
        "template_name": "Blast Radius",
        # The server doesn't pick a default bridge the way Console's form does, so name it.
        "inputs": {"workspace": str(workspace), "bridge": bridge, "support_lead": support_lead},
    })
    print(f"Created the support and fixer agents, #support and #finance-approvals on {bridge}. "
          "Support's kickoff is in #support.")
    if support_lead != creator:
        add_support_lead(gateway, support_lead)
    return 0


if __name__ == "__main__":
    sys.exit(main())
