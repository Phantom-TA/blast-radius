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
PAYMENTS_URL = f"http://localhost:{os.environ.get('PAYMENTS_PORT', '8400')}"
UP_TIMEOUT_SECONDS = 90
AGENT_START_SECONDS = 3
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


def empty_workspace() -> None:
    """Empty the Fixer's folder but keep it, because Switch runs the Fixer from this path."""
    SERVICE_WORKSPACE.mkdir(parents=True, exist_ok=True)
    # Git marks its object files read-only, which blocks a plain delete on Windows.
    for folder, _, files in os.walk(SERVICE_WORKSPACE):
        for name in files:
            os.chmod(os.path.join(folder, name), stat.S_IWRITE)
    for item in SERVICE_WORKSPACE.iterdir():
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item)
        else:
            item.unlink()


def create_workspace() -> None:
    """Copy the unfixed service into its own git repo. The Fixer agent works here."""
    empty_workspace()
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
    print(f"Created {SERVICE_WORKSPACE} with the unfixed service.")


def cmd_up() -> int:
    if shutil.which("docker") is None:
        print("Docker isn't installed. Install Docker Desktop, then try again.")
        return 1
    (ROOT / "data").mkdir(exist_ok=True)
    if subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd=ROOT).returncode != 0:
        print("docker compose failed. Check Docker Desktop is running and the ports are free.")
        return 1

    deadline = time.monotonic() + UP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if is_up(f"{PAYMENTS_URL}/health") and is_up(f"{MAILPIT_API}/info"):
            print(f"Payment service: {PAYMENTS_URL}  Mailpit inbox: http://localhost:8025")
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


def cmd_rooms() -> int:
    return run_optional_script("switch/import_template.py")


def start_agents() -> dict[str, subprocess.Popen]:
    return {module: subprocess.Popen([PYTHON, "-m", module], cwd=ROOT) for module in AGENT_MODULES}


def stop_agents(processes: dict[str, subprocess.Popen]) -> None:
    for process in processes.values():
        process.terminate()
        process.wait()


def stopped_agent_code(processes: dict[str, subprocess.Popen]) -> int | None:
    """None while every agent is running, otherwise the exit code to report."""
    for module, process in processes.items():
        if process.poll() is not None:
            print(f"{module} stopped with exit code {process.returncode}.")
            return process.returncode or 1
    return None


def watch_agents(processes: dict[str, subprocess.Popen]) -> int:
    print("Agents running. Press Ctrl+C to stop them.")
    while True:
        code = stopped_agent_code(processes)
        if code is not None:
            return code
        time.sleep(1)


def cmd_agents() -> int:
    processes = start_agents()
    try:
        return watch_agents(processes)
    except KeyboardInterrupt:
        return 0
    finally:
        stop_agents(processes)


def cmd_verify() -> int:
    return run_python("scripts/verify.py")


def cmd_reset() -> int:
    empty_workspace()
    empty_mailpit()
    # The seed always picks the same complainer, so a rerun needs that blast room's name again.
    run_optional_script("switch/archive_rooms.py")
    code = cmd_seed()
    print("Now type !reset-all-agents in #support in Mattermost, so Support and Fixer start fresh.")
    return code


def cmd_demo() -> int:
    for step in (cmd_up, cmd_register, cmd_rooms):
        code = step()
        if code != 0:
            return code

    # On their first start the agents only see new messages, so they go before the complaint.
    processes = start_agents()
    try:
        time.sleep(AGENT_START_SECONDS)
        code = stopped_agent_code(processes)
        if code is None:
            code = cmd_scenario()
        return code if code != 0 else watch_agents(processes)
    except KeyboardInterrupt:
        return 0
    finally:
        stop_agents(processes)


COMMANDS = {
    "up": (cmd_up, "start the payment service and Mailpit in Docker"),
    "seed": (cmd_seed, "rebuild the database from the seed"),
    "scenario": (cmd_scenario, "reseed, recreate the Fixer's workspace, post the complaint"),
    "register": (cmd_register, "register the Python agents with Switch"),
    "rooms": (cmd_rooms, "create the rooms and Claude Code agents from the Switch template"),
    "agents": (cmd_agents, "start the Investigator and Treasurer agents"),
    "verify": (cmd_verify, "print PASS or FAIL for the finished demo"),
    "reset": (cmd_reset, "go back to the starting state"),
    "demo": (cmd_demo, "up + register + rooms + agents + scenario"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Blast Radius project commands")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        commands.add_parser(name, help=help_text)
    return COMMANDS[parser.parse_args().command][0]()


if __name__ == "__main__":
    sys.exit(main())
