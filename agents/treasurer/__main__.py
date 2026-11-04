"""Run the Treasurer: python -m agents.treasurer"""

import logging

from agents.common.backend import load_backend
from agents.common.switch_client import SwitchAgent
from agents.treasurer.agent import Treasurer


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    switch = SwitchAgent("treasurer")
    switch.run(Treasurer(switch, load_backend()).handle)


if __name__ == "__main__":
    main()
