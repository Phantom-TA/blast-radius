"""Sign in to Switch's Gateway API as the agents' owner (a person, not an agent).

Some things only an owner may do: create a registration key, set an agent's
addressing, read a room's documents without joining it as an agent. The password
is only sent to your own Switch server.
"""

import getpass
import http.cookiejar
import json
import urllib.error
import urllib.request
from typing import Callable

from agents.common.switch_client import console_data_dir

Gateway = Callable[..., dict]


def console_admin_login(server_url: str) -> tuple[str, str] | None:
    """The admin account Switch Console made for its local server, if that's the server in use."""
    env_file = console_data_dir() / "local-switch-server" / "native" / "run" / "switch-core.env"
    if not env_file.exists():
        return None
    env = dict(
        line.split("=", 1)
        for line in env_file.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    if env.get("GATEWAY_PUBLIC_URL", "").rstrip("/") != server_url:
        return None
    if not env.get("GATEWAY_ADMIN_EMAIL") or not env.get("GATEWAY_ADMIN_PASSWORD"):
        return None
    return env["GATEWAY_ADMIN_EMAIL"], env["GATEWAY_ADMIN_PASSWORD"]


def gateway_session(server_url: str, interactive: bool = True, quiet: bool = False) -> Gateway:
    """Sign in; returns call(method, path, body=None) for paths under /gateway.

    Uses the Console-managed server's admin account when it can find it. Otherwise
    it asks for an email and password, or with interactive=False raises SystemExit.
    """
    login = console_admin_login(server_url)
    if login:
        email, password = login
        if not quiet:
            print(f"Signing in to {server_url} as {email} (Switch Console's local admin).")
    elif interactive:
        print(f"Sign in to Switch at {server_url} (the account that owns the agents).")
        email = input("Email: ").strip()
        password = getpass.getpass("Password: ")
    else:
        raise SystemExit(f"No Switch Console admin login found for {server_url}.")
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )

    def gateway(method: str, path: str, body: dict | None = None, timeout: float = 30) -> dict:
        request = urllib.request.Request(
            f"{server_url}/gateway{path}",
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with opener.open(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raise SystemExit(f"{path} failed with {error.code}: {error.read().decode()[:300]}")
        return json.loads(raw) if raw else {}

    gateway("POST", "/auth/login", {"email": email, "password": password})
    return gateway
