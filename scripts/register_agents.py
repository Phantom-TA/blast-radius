"""Register the plain-Python agents with Switch and set who may instruct each one.

Safe to run twice: an agent whose saved key still works is skipped, and its
addressing is set again either way.

    python scripts/register_agents.py --create-key   # once: sign in and make a registration key
    python scripts/register_agents.py                # register investigator, treasurer, customer-sim
"""

import argparse
import getpass
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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
        "owner_and_owner_agents",
    ),
    (
        "treasurer",
        "Treasurer",
        "Builds and executes refund batches. Plain Python, no LLM. Takes instructions from "
        "people only.",
        "owner_only",
    ),
    (
        "customer-sim",
        "Customer (simulated)",
        "Posts the simulated customer's complaint into #support.",
        "owner_only",
    ),
]


def create_registration_key(server_url: str) -> None:
    """Sign in to the Gateway API and create a registration key.

    The local server Switch Console runs has no Gateway web page, so there is no
    API Keys page to click. The password is only sent to your own Switch server.
    """
    print(f"Sign in to Switch at {server_url} (the account you use in Switch Console).")
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )

    def gateway(path: str, body: dict) -> dict:
        request = urllib.request.Request(
            f"{server_url}/gateway{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with opener.open(request, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise SystemExit(f"{path} failed with {error.code}: {error.read().decode()[:300]}")

    gateway("/auth/login", {"email": email, "password": password})
    key = gateway("/api-keys", {"label": "blast-radius registration"})
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRATION_KEY_FILE.write_text(key["key"])
    REGISTRATION_KEY_FILE.chmod(0o600)
    print(f"Saved the registration key to {REGISTRATION_KEY_FILE.relative_to(ROOT)}")


def key_still_works(server_url: str, name: str) -> bool:
    try:
        SwitchAgent(name, server_url).call("list_rooms", bound=False)
        return True
    except SwitchError as error:
        if error.status == 401:
            return False
        raise


def ensure_registered(server_url: str, name: str, display: str, description: str,
                      overwrite: bool) -> None:
    if Credentials.path(name).exists() and not overwrite:
        if key_still_works(server_url, name):
            print(f"{name}: already registered, skipping")
            return
        print(f"{name}: the saved key no longer works, registering again")
        overwrite = True

    if not REGISTRATION_KEY_FILE.exists():
        raise SystemExit("No registration key yet. Run: python scripts/register_agents.py --create-key")
    try:
        credentials = register_agent(
            server_url, REGISTRATION_KEY_FILE.read_text().strip(), name, description, display,
            overwrite=overwrite,
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
    if args.create_key:
        create_registration_key(server_url)
        return 0

    for name, display, description, addressing in AGENTS:
        ensure_registered(server_url, name, display, description, args.overwrite)
        agent = SwitchAgent(name, server_url)
        agent.call("update_agent_detail", {"agent_id": agent.agent_id, "addressing": addressing},
                   bound=False)
        print(f"{name}: addressing set to {addressing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
