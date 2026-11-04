"""Import switch/template.yaml into Switch without clicking through Switch Console.

    python switch/import_template.py           # check it, then create the agents and rooms
    python switch/import_template.py --check   # only ask Switch whether it would work

It does what Console's Templates page does: as the owner, it sends the document
to the Gateway API (POST /gateway/rooms/from-template-document), and the server
creates the Support and Fixer agents on this machine, then #support and
#finance-approvals. Run scripts/register_agents.py first: the rooms name the
Python agents it registers.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.common.gateway import gateway_session  # noqa: E402
from agents.common.switch_client import SwitchAgent, find_server_url  # noqa: E402

TEMPLATE = ROOT / "switch" / "template.yaml"
WORKSPACE = ROOT / "demo-workspace" / "payments-service"
# The apology placeholders are meant to stay as written: the Treasurer's emails fill them.
EXPECTED_WARNINGS = {"name", "order_id", "amount"}


def default_bridge() -> str:
    """The messaging app's display name: Mattermost when the server has it, else the first."""
    bridges = SwitchAgent("customer-sim").call("list_bridges", bound=False)
    if not bridges:
        raise SystemExit("This Switch server has no messaging app. In Switch Console, turn on "
                         "'Also run Mattermost' on the server's page (Docker must be running).")
    chosen = next((bridge for bridge in bridges if bridge["type"] == "mattermost"), bridges[0])
    return chosen["display_name"]


def already_imported() -> bool:
    try:
        SwitchAgent("customer-sim").room_id("support")
        return True
    except LookupError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only validate the template")
    parser.add_argument("--workspace", type=Path, default=WORKSPACE,
                        help="the Fixer's folder (default: demo-workspace/payments-service)")
    parser.add_argument("--bridge", help="messaging app display name (default: Mattermost's)")
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

    if already_imported():
        print("Already imported: customer-sim is in #support. Nothing to do.")
        return 0

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
        "inputs": {"workspace": str(workspace), "bridge": args.bridge or default_bridge()},
    })
    print("Created the support and fixer agents, #support and #finance-approvals. "
          "Support's kickoff is in #support.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
