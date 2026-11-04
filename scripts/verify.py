"""Print PASS or FAIL for each thing a finished demo must have produced."""

import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from payments_app.service.store import connect  # noqa: E402
from seed.seed import AFFECTED_CUSTOMERS  # noqa: E402

SERVICE_WORKSPACE = ROOT / "demo-workspace" / "payments-service"
MAILPIT_MESSAGES = "http://localhost:8025/api/v1/messages?limit=1"
PYTEST_TESTS_FAILED = 1

# Runs inside the Fixer's workspace: one timeout, one retry, then count the charges.
RETRY_PROBE = """
import os, tempfile
from service.charge_client import charge_order
from service.provider import FakeProvider
from service.store import connect, create_db

folder = tempfile.mkdtemp()
path = os.path.join(folder, "probe.db")
create_db(path)
conn = connect(path)
conn.execute("INSERT INTO customers VALUES ('CUS-1', 'Probe', 'probe@example.com')")
conn.execute(
    "INSERT INTO orders VALUES ('ORD-1', 'CUS-1', 'Probe', 1000, '2026-01-01T00:00:00+00:00')"
)
pending_timeouts = ["ORD-1"]


def should_timeout(order_id):
    if order_id in pending_timeouts:
        pending_timeouts.remove(order_id)
        return True
    return False


charge_order(FakeProvider(conn, should_timeout=should_timeout), "ORD-1", 1000)
print(conn.execute("SELECT COUNT(*) FROM charges").fetchone()[0])
conn.close()
"""


def run_in_workspace(*command: str) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=SERVICE_WORKSPACE, capture_output=True, text=True)


def last_line(result: subprocess.CompletedProcess) -> str:
    lines = (result.stdout + result.stderr).strip().splitlines()
    return lines[-1] if lines else "no output"


def changed_files() -> list[str]:
    changed = run_in_workspace("git", "diff", "--name-only", "baseline").stdout.splitlines()
    untracked = run_in_workspace(
        "git", "ls-files", "--others", "--exclude-standard"
    ).stdout.splitlines()
    return changed + untracked


def is_test_file(name: str) -> bool:
    return Path(name).name.startswith("test_") and name.endswith(".py")


def pytest_exit_code_on_original_code(changed: list[str]) -> int:
    """Run the Fixer's tests with the original code put back, in a scratch copy."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        scratch = Path(folder) / "payments-service"
        shutil.copytree(
            SERVICE_WORKSPACE,
            scratch,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"),
        )
        for name in changed:
            original = subprocess.run(
                ["git", "show", f"baseline:{name}"], cwd=SERVICE_WORKSPACE, capture_output=True
            )
            if not is_test_file(name) and original.returncode == 0:
                (scratch / name).write_bytes(original.stdout)
        return subprocess.run(
            [sys.executable, "-m", "pytest", "-q"], cwd=scratch, capture_output=True
        ).returncode


def check_fix() -> tuple[bool, str]:
    if not SERVICE_WORKSPACE.exists():
        return False, "demo-workspace/payments-service doesn't exist. Run: python run.py scenario"

    tests = run_in_workspace(sys.executable, "-m", "pytest", "-q")
    if tests.returncode != 0:
        return False, f"tests fail in the workspace: {last_line(tests)}"

    probe = run_in_workspace(sys.executable, "-c", RETRY_PROBE)
    if probe.returncode != 0:
        return False, f"retry probe crashed: {last_line(probe)}"
    charges = probe.stdout.strip()
    if charges != "1":
        return False, f"a timeout plus a retry still creates {charges} charges, expected 1"

    changed = changed_files()
    if not any(is_test_file(name) for name in changed):
        return False, "bug is fixed but no test file was added or changed"

    exit_code = pytest_exit_code_on_original_code(changed)
    if exit_code == 0:
        return False, "bug is fixed but the new test also passes on the buggy code"
    if exit_code != PYTEST_TESTS_FAILED:
        return False, "the new test can't run on the original code, so it proves nothing yet"
    return True, "tests pass, retry creates 1 charge, regression test fails on the buggy code"


def check_refunds() -> tuple[bool, str]:
    try:
        conn = connect(read_only=True)
    except FileNotFoundError as error:
        return False, str(error)

    with closing(conn):
        charges = conn.execute(
            "SELECT id, order_id, amount_cents, status FROM charges "
            "WHERE status IN ('succeeded', 'refunded') ORDER BY id"
        ).fetchall()
        refunds = conn.execute(
            "SELECT charge_id, customer_id, amount_cents FROM refunds WHERE status = 'refunded'"
        ).fetchall()

    paid_orders = set()
    duplicates = {}
    for charge in charges:
        if charge["order_id"] in paid_orders:
            duplicates[charge["id"]] = charge["amount_cents"]
        paid_orders.add(charge["order_id"])
    expected_total = sum(duplicates.values()) / 100

    refunded_ids = [refund["charge_id"] for refund in refunds]
    if len(refunded_ids) != len(set(refunded_ids)):
        return False, "a charge was refunded more than once"
    if {refund["charge_id"]: refund["amount_cents"] for refund in refunds} != duplicates:
        return False, f"{len(refunds)} of {len(duplicates)} duplicate charges correctly refunded"
    if {charge["id"] for charge in charges if charge["status"] == "refunded"} != set(duplicates):
        return False, "the charges marked refunded are not exactly the duplicates"

    customers = len({refund["customer_id"] for refund in refunds})
    if customers != AFFECTED_CUSTOMERS:
        return False, f"{customers} customers refunded, expected {AFFECTED_CUSTOMERS}"
    return True, f"{customers} customers refunded, ${expected_total:,.2f} total"


def check_emails() -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(MAILPIT_MESSAGES, timeout=5) as response:
            total = json.load(response)["total"]
    except (urllib.error.URLError, OSError):
        return False, "Mailpit isn't reachable on port 8025. Run: python run.py up"
    if total != AFFECTED_CUSTOMERS:
        return False, f"{total} emails in Mailpit, expected {AFFECTED_CUSTOMERS}"
    return True, f"{total} emails in Mailpit"


def main() -> int:
    checks = [
        ("Bug fixed with a regression test", check_fix),
        ("Refunds correct with no double refunds", check_refunds),
        ("Apology emails delivered", check_emails),
    ]
    all_passed = True
    for name, check in checks:
        passed, detail = check()
        all_passed = all_passed and passed
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {detail}")

    # TODO(Person A): add a check that the postmortem room document exists in Switch.
    print("TODO  Postmortem room document: check to be added with the Switch side")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
