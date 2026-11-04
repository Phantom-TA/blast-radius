"""Run the Investigator: python -m agents.investigator"""

import logging

from agents.common.backend import load_backend
from agents.common.switch_client import SwitchAgent
from agents.investigator.agent import Investigator


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    switch = SwitchAgent("investigator")
    switch.run(Investigator(switch, load_backend()).handle)


if __name__ == "__main__":
    main()
