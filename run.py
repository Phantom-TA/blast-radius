"""One entry point for every project command. Works the same on Windows and Linux."""

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVICE_SOURCE = ROOT / "payments_app" / "service"
WORKSPACE = ROOT / "demo-workspace"
SERVICE_WORKSPACE = WORKSPACE / "payments-service"
MAILPIT_API = "http://localhost:8025/api/v1"
PAYMENTS_HEALTH = "http://localhost:8000/health"
UP_TIMEOUT_SECONDS = 90
VENV_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
AGENT_MODULES = ["agents.investigator", "agents.treasurer"]


def run_python(*args: str) -> int:
    return subprocess.run([PYTHON, *args], cwd=ROOT).returncode


def run_optional_script(relative_path: str) -> int:
    """Run a script Person A owns, or skip it with a message if it isn't there yet."""
    if not (ROOT / relative_path).exists():
        print(f"Skipping {relative_path}: it doesn't exist yet (Switch side of the project).")
        return 0
    return run_python(relative_path)


def is_up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2):
            return True
    except (urllib.error.URLError, OSError):
        return False


def empty_mailpit() -> None:
    request = urllib.request.Request(
        f"{MAILPIT_API}/messages",
        data=json.dumps({}).encode(),
        headers={"Content-Type": "application/json"},
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(request, timeout=5):
            print("Emptied the Mailpit inbox.")
    except (urllib.error.URLError, OSError):
        print("Mailpit isn't running, so the inbox wasn't emptied. Start it with: python run.py up")


def remove_workspace() -> None:
    """Git marks its object files read-only, which blocks a plain delete on Windows."""
    if not WORKSPACE.exists():
        return
    for folder, _, files in os.walk(WORKSPACE):
        for name in files:
            os.chmod(os.path.join(folder, name), stat.S_IWRITE)
    shutil.rmtree(WORKSPACE)


def create_workspace() -> None:
    """Copy the unfixed service into its own git repo. The Fixer agent works here."""
    remove_workspace()
    SERVICE_WORKSPACE.mkdir(parents=True)
    shutil.copytree(
        SERVICE_SOURCE, SERVICE_WORKSPACE / "service", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copy(ROOT / "payments_app" / "requirements.txt", SERVICE_WORKSPACE)
    (SERVICE_WORKSPACE / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")

    for args in (
        ["init", "-b", "main"],
        ["config", "user.name", "Payments Team"],
        ["config", "user.email", "payments-team@acme-store.example"],
        ["config", "commit.gpgsign", "false"],
        ["add", "."],
        ["commit", "-m", "Payment service"],
        ["tag", "baseline"],
    ):
        subprocess.run(["git", *args], cwd=SERVICE_WORKSPACE, check=True, capture_output=True)
    print(f"Created {SERVICE_WORKSPACE.relative_to(ROOT)} with the unfixed service.")


def cmd_up() -> int:
    if shutil.which("docker") is None:
        print("Docker isn't installed. Install Docker Desktop, then try again.")
        return 1
    (ROOT / "data").mkdir(exist_ok=True)
    if subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd=ROOT).returncode != 0:
        print("docker compose failed. Is Docker Desktop running?")
        return 1

    deadline = time.monotonic() + UP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if is_up(PAYMENTS_HEALTH) and is_up(f"{MAILPIT_API}/info"):
            print("Payment service: http://localhost:8000  Mailpit inbox: http://localhost:8025")
            return 0
        time.sleep(1)
    print(f"Services did not answer within {UP_TIMEOUT_SECONDS}s. Check: docker compose logs")
    return 1


def cmd_seed() -> int:
    return run_python("-m", "seed.seed")


def cmd_scenario() -> int:
    code = cmd_seed()
    if code != 0:
        return code
    create_workspace()
    empty_mailpit()
    return run_optional_script("scripts/post_complaint.py")


def cmd_register() -> int:
    return run_optional_script("scripts/register_agents.py")


def cmd_agents() -> int:
    if not (ROOT / "agents").is_dir():
        print("Skipping agents: the agents folder doesn't exist yet (Switch side of the project).")
        return 0
    processes = [subprocess.Popen([PYTHON, "-m", module], cwd=ROOT) for module in AGENT_MODULES]
    print("Agents running. Press Ctrl+C to stop them.")
    try:
        return max(process.wait() for process in processes)
    except KeyboardInterrupt:
        for process in processes:
            process.terminate()
        return 0


def cmd_verify() -> int:
    return run_python("scripts/verify.py")


def cmd_reset() -> int:
    remove_workspace()
    empty_mailpit()
    return cmd_seed()


def cmd_demo() -> int:
    for step in (cmd_up, cmd_register, cmd_scenario, cmd_agents):
        code = step()
        if code != 0:
            return code
    return 0


COMMANDS = {
    "up": (cmd_up, "start the payment service and Mailpit in Docker"),
    "seed": (cmd_seed, "rebuild the database from the seed"),
    "scenario": (cmd_scenario, "reseed, recreate the Fixer's workspace, post the complaint"),
    "register": (cmd_register, "register the Python agents with Switch"),
    "agents": (cmd_agents, "start the Investigator and Treasurer agents"),
    "verify": (cmd_verify, "print PASS or FAIL for the finished demo"),
    "reset": (cmd_reset, "go back to the starting state"),
    "demo": (cmd_demo, "up + register + scenario + agents"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Blast Radius project commands")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        commands.add_parser(name, help=help_text)
    return COMMANDS[parser.parse_args().command][0]()


if __name__ == "__main__":
    sys.exit(main())
