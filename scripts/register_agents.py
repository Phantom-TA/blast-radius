"""Register the plain-Python agents with Switch and set who may instruct each one.

Safe to run twice: an agent whose saved key still works is skipped, and its
addressing is set again either way.

    python scripts/register_agents.py               # register investigator, treasurer, customer-sim
    python scripts/register_agents.py --create-key  # only make a new registration key

Registering needs a registration key and setting addressing needs the agents'
owner, so it signs in to the Gateway API as that person: on the local server
Switch Console runs, with Console's own admin login; anywhere else it asks.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.common.gateway import gateway_session  # noqa: E402
from agents.common.switch_client import (  # noqa: E402
    REGISTRATION_KEY_FILE,
    SECRETS_DIR,
    Credentials,
    SwitchAgent,
    SwitchError,
    find_server_url,
    register_agent,
)

# name, display name, description, addressing
AGENTS = [
    (
        "investigator",
        "Investigator",
        "Finds every customer hit by the double charge. Plain Python, read-only, no LLM.",
        "anyone",
    ),
    (
        "treasurer",
        "Treasurer",
        "Builds and executes refund batches. Plain Python, no LLM. Takes instructions from "
        "its owner, the Finance lead, and nobody else.",
        "owner_only",
    ),
    (
        "customer-sim",
        "Customer (simulated)",
        "Posts the simulated customer's complaint into #support.",
        "owner_only",
    ),
]


# The rules Switch stores for each addressing choice. owner_only is Console's "Only me"
# (switch_core.addressing.owner_only_policy): the owner, and no other person or agent.
# anyone clears the policy, which is Console's "Anyone": a teammate on Discord with no
# Switch account can talk to the agent, because an open policy never asks who they are.
ADDRESSING_POLICIES = {
    "owner_only": {"rules": [{"users": [], "agents": [], "owner": True}]},
    "anyone": None,
}


def create_registration_key(gateway) -> str:
    """Create a registration key through the Gateway API and save it.

    The local server Switch Console runs has no Gateway web page, so there is no
    API Keys page to click.
    """
    key = gateway("POST", "/api-keys", {"label": "blast-radius registration"})
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRATION_KEY_FILE.write_text(key["key"])
    REGISTRATION_KEY_FILE.chmod(0o600)
    print(f"Saved the registration key to {REGISTRATION_KEY_FILE.relative_to(ROOT)}")
    return key["key"]


def key_still_works(server_url: str, name: str) -> bool:
    try:
        SwitchAgent(name, server_url).call("list_rooms", bound=False)
        return True
    except SwitchError as error:
        if error.status == 401:
            return False
        raise


def ensure_registered(server_url: str, gateway, name: str, display: str, description: str,
                      overwrite: bool) -> None:
    if Credentials.path(name).exists() and not overwrite:
        if key_still_works(server_url, name):
            print(f"{name}: already registered, skipping")
            return
        print(f"{name}: the saved key no longer works, registering again")
        overwrite = True

    if REGISTRATION_KEY_FILE.exists():
        registration_key = REGISTRATION_KEY_FILE.read_text().strip()
    else:
        registration_key = create_registration_key(gateway)
    try:
        credentials = register_agent(
            server_url, registration_key, name, description, display, overwrite=overwrite
        )
    except SwitchError as error:
        if error.status == 409:
            raise SystemExit(
                f"{name} already exists on the server but its key isn't saved here. "
                "Rerun with --overwrite to issue a new key."
            )
        raise
    print(f"{name}: registered as {credentials.agent_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--create-key", action="store_true", help="sign in and make a registration key")
    parser.add_argument("--overwrite", action="store_true", help="re-register and issue new API keys")
    args = parser.parse_args()

    server_url = find_server_url()
    gateway = gateway_session(server_url)
    if args.create_key:
        create_registration_key(gateway)
        return 0

    for name, display, description, _ in AGENTS:
        ensure_registered(server_url, gateway, name, display, description, args.overwrite)

    # An agent can't change its own addressing; its owner sets it through the Gateway API.
    for name, _, _, addressing in AGENTS:
        agent_id = Credentials.load(name).agent_id
        gateway("PUT", f"/agents/{agent_id}/addressing-policy",
                {"policy": ADDRESSING_POLICIES[addressing]})
        print(f"{name}: addressing set to {addressing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
