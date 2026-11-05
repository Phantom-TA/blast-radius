"""Archive or delete the rooms a run leaves behind, so the next run starts clean.

    python switch/archive_rooms.py              # archive every blast-<order id> room
    python switch/archive_rooms.py gonogo-      # archive rooms whose name starts with gonogo-
    python switch/archive_rooms.py --list       # only show what would be archived
    python switch/archive_rooms.py --delete     # delete the rooms and their chat channels

Support creates one blast-<order id> room per complaint, and the seed always
picks the same order, so a second run would ask for a room that already exists.
Archiving keeps its history and documents (it can be unarchived); it just takes
it out of the way. Runs as the agents' owner through the Gateway API.

Archiving leaves the Discord channel in place, so reruns stack up channels with the
same name. --delete removes the room and its channel, for a clean take. That can't be
undone: the room's history and documents go too.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.common.gateway import gateway_session  # noqa: E402
from agents.common.switch_client import find_server_url  # noqa: E402


def clear_rooms(gateway, rooms: list[dict], delete: bool = False) -> None:
    room_ids = [room["id"] for room in rooms]
    if delete:
        gateway("POST", "/rooms/bulk-delete", {"room_ids": room_ids, "retire_channel": True})
    else:
        gateway("POST", "/rooms/bulk-archive", {"room_ids": room_ids, "archived": True})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("prefix", nargs="?", default="blast-", help="room name prefix")
    parser.add_argument("--list", action="store_true", help="show the rooms, change nothing")
    parser.add_argument("--delete", action="store_true",
                        help="delete the rooms and their chat channels, history included")
    args = parser.parse_args()

    gateway = gateway_session(find_server_url(), quiet=True)
    rooms = [room for room in gateway("GET", "/rooms") if room["name"].startswith(args.prefix)]
    if not rooms:
        print(f"No rooms named {args.prefix}... to clear.")
        return 0
    verb = "delete" if args.delete else "archive"
    label = f"Would {verb}" if args.list else f"{verb[:-1].capitalize()}ing"
    for room in rooms:
        print(f"{label} #{room['name']}")
    if not args.list:
        clear_rooms(gateway, rooms, delete=args.delete)
    return 0


if __name__ == "__main__":
    sys.exit(main())
