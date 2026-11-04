"""Archive the rooms a run leaves behind, so the next run starts clean.

    python switch/archive_rooms.py              # archive every blast-<order id> room
    python switch/archive_rooms.py gonogo-      # archive rooms whose name starts with gonogo-
    python switch/archive_rooms.py --list       # only show what would be archived

Support creates one blast-<order id> room per complaint, and the seed always
picks the same order, so a second run would ask for a room that already exists.
Archiving keeps its history and documents (it can be unarchived); it just takes
it out of the way. Runs as the agents' owner through the Gateway API.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.common.gateway import gateway_session  # noqa: E402
from agents.common.switch_client import find_server_url  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("prefix", nargs="?", default="blast-", help="room name prefix")
    parser.add_argument("--list", action="store_true", help="show the rooms, change nothing")
    args = parser.parse_args()

    gateway = gateway_session(find_server_url(), quiet=True)
    rooms = [room for room in gateway("GET", "/rooms") if room["name"].startswith(args.prefix)]
    if not rooms:
        print(f"No rooms named {args.prefix}... to archive.")
        return 0
    for room in rooms:
        print(f"{'Would archive' if args.list else 'Archiving'} #{room['name']}")
    if not args.list:
        gateway("POST", "/rooms/bulk-archive",
                {"room_ids": [room["id"] for room in rooms], "archived": True})
    return 0


if __name__ == "__main__":
    sys.exit(main())
