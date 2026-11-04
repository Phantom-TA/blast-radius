"""Post the simulated customer's complaint into #support, as the customer-sim agent.

    python scripts/post_complaint.py              # the order in seed/complainer.json
    python scripts/post_complaint.py ORD-100953   # any order id

The message @mentions Support, because a Switch agent only starts work when a
message addresses it. It goes through POST /agents/{id}/message, which needs no
open connection.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.common.switch_client import SwitchAgent, SwitchError  # noqa: E402

COMPLAINER_FILE = ROOT / "seed" / "complainer.json"
SUPPORT_ROOM = "support"
SUPPORT_AGENT = "support"


def complaint(order_id: str, complainer: dict | None) -> str:
    if complainer and complainer.get("order_id") == order_id:
        return (
            f"@{SUPPORT_AGENT} Hi, I was charged twice for order {order_id} "
            f"({complainer['description']}, ${complainer['amount']:,.2f}). I only bought one. "
            f"Can you refund the extra charge? Thanks, {complainer['customer_name']}"
        )
    return (
        f"@{SUPPORT_AGENT} Hi, I was charged twice for order {order_id}. I only bought one. "
        "Can you refund the extra charge?"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("order_id", nargs="?", help="default: the order in seed/complainer.json")
    args = parser.parse_args()

    complainer = None
    if COMPLAINER_FILE.exists():
        complainer = json.loads(COMPLAINER_FILE.read_text(encoding="utf-8"))
    order_id = args.order_id or (complainer or {}).get("order_id")
    if not order_id:
        print("No order id: seed/complainer.json doesn't exist. Run: python run.py seed, "
              "or pass one: python scripts/post_complaint.py ORD-100953")
        return 1

    agent = SwitchAgent("customer-sim")
    try:
        room_id = agent.room_id(SUPPORT_ROOM)
    except LookupError:
        print(f"customer-sim isn't in a room named {SUPPORT_ROOM}. Import switch/template.yaml "
              "in Switch Console first (see switch/SETUP.md).")
        return 1
    try:
        agent.post(room_id, complaint(order_id, complainer))
    except SwitchError as error:
        print(f"Switch didn't take the complaint: {error}")
        return 1
    print(f"Posted the complaint about {order_id} in #{SUPPORT_ROOM}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
