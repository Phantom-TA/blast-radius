"""Put the Python agents back into their rooms so they show up under their own names in chat.

    python switch/rejoin_agents.py          # every room investigator, treasurer, customer-sim are in
    python switch/rejoin_agents.py --list   # only show what it would do

Switch gives each agent a bot account in Mattermost and adds that bot to a room's
channel when the agent joins the room. If Mattermost wasn't running when the agents
were registered, the bots were created later (on the next server start), after the
agents had already joined their rooms, so the bots never joined the channels. The
agents' posts then show under the owner's name, or not at all.

Taking each agent out of the room and adding it straight back makes Switch add its bot
to the channel. History and room documents are untouched; each agent posts a short
greeting again. Runs as the agents' owner through the Gateway API.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.common.gateway import gateway_session  # noqa: E402
from agents.common.switch_client import Credentials, SwitchAgent, find_server_url  # noqa: E402

AGENTS = ["investigator", "treasurer", "customer-sim"]
# Channels Mattermost made itself; the agents don't work there.
SKIP_PREFIX = "Local Mattermost:"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="show the rooms, change nothing")
    args = parser.parse_args()

    gateway = None if args.list else gateway_session(find_server_url(), quiet=True)
    for name in AGENTS:
        agent_id = Credentials.load(name).agent_id
        rooms = [room for room in SwitchAgent(name).rooms()
                 if not room["name"].startswith(SKIP_PREFIX)]
        for room in rooms:
            if args.list:
                print(f"Would rejoin {name} to #{room['name']}")
                continue
            gateway("DELETE", f"/rooms/{room['id']}/agents/{agent_id}")
            gateway("POST", f"/rooms/{room['id']}/agents", {"agent_ids": [agent_id]})
            print(f"Rejoined {name} to #{room['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
