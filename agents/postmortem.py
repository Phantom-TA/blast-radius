"""Check that Support wrote the postmortem room document. For scripts/verify.py.

    from agents.postmortem import check_postmortem
    passed, detail = check_postmortem()

Finds the blast-<order id> rooms through the Investigator (Support invites it to
each one), then asks the Gateway API, as the owner, which documents each room
has. It reads as the owner so it never disturbs a running agent's connection.
Run alone, it prints PASS or FAIL: python -m agents.postmortem
"""

import sys

from agents.common.gateway import gateway_session
from agents.common.switch_client import SwitchAgent, SwitchError, find_server_url

DOCUMENT = "postmortem"
ROOM_PREFIX = "blast-"


def check_postmortem(agent_name: str = "investigator") -> tuple[bool, str]:
    try:
        agent = SwitchAgent(agent_name)
        rooms = [room for room in agent.rooms() if room["name"].lstrip("#").startswith(ROOM_PREFIX)]
        if not rooms:
            return False, "no blast-<order id> room yet: Support creates it after the complaint"
        gateway = gateway_session(find_server_url(), interactive=False, quiet=True)
        for room in rooms:
            documents = gateway("GET", f"/rooms/{room['id']}/documents")
            if any(document.get("name") == DOCUMENT for document in documents):
                return True, f"room document \"{DOCUMENT}\" is in #{room['name']}"
        names = ", ".join(f"#{room['name']}" for room in rooms)
        return False, f"no room document named \"{DOCUMENT}\" in {names}"
    except (SwitchError, OSError) as error:
        return False, f"couldn't ask Switch: {error}"
    except SystemExit as error:
        return False, str(error)


if __name__ == "__main__":
    passed, detail = check_postmortem()
    print(f"{'PASS' if passed else 'FAIL'}  Postmortem room document: {detail}")
    sys.exit(0 if passed else 1)
