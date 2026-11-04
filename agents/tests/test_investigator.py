from types import SimpleNamespace

from agents.investigator.agent import Investigator, report
from agents.tests import fakes
from agents.tests.chat import FakeSwitch, message

BACKEND = SimpleNamespace(
    find_affected_customers=fakes.find_affected_customers,
    summarize=fakes.summarize,
    db_path=fakes.DB_PATH,
    refusals=(fakes.RefundError, ValueError, FileNotFoundError),
)


def test_report_has_counts_total_and_top_five():
    text = report(BACKEND)
    assert "**5 customers were double charged**, $481.75 USD in total." in text
    assert "1 complained. **4 have not said anything yet.**" in text
    rows = [line for line in text.splitlines() if line.startswith("| CUS-")]
    assert len(rows) == 5
    # Biggest overcharge first.
    assert rows[0].startswith("| CUS-0230 | mia.berg@example.com | ORD-100702 | 2 | $230.00 |")
    assert rows[-1].startswith("| CUS-0105 ")


def test_report_lists_only_five_rows_when_there_are_more():
    many = [dict(item, order_id=f"ORD-{i}") for i, item in enumerate(fakes.AFFECTED * 3)]
    backend = SimpleNamespace(**(BACKEND.__dict__ | {"find_affected_customers": lambda _: many}))
    text = report(backend)
    assert "**15 customers" in text
    assert len([line for line in text.splitlines() if line.startswith("| CUS-")]) == 5


def test_report_when_nobody_is_affected():
    backend = SimpleNamespace(**(BACKEND.__dict__ | {"find_affected_customers": lambda _: []}))
    assert report(backend).startswith("No double charges found")


def test_replies_in_the_thread_that_asked():
    switch = FakeSwitch()
    asked = message("@investigator how many customers were hit?", kind="agent")
    Investigator(switch, BACKEND).handle(asked)
    [(replied_to, text)] = switch.replies
    assert replied_to is asked
    assert "5 customers were double charged" in text


def test_a_missing_database_is_explained_without_a_stack_trace():
    def missing(_):
        raise FileNotFoundError("No database at data/payments.db. Run: python run.py seed")

    backend = SimpleNamespace(**(BACKEND.__dict__ | {"find_affected_customers": missing}))
    switch = FakeSwitch()
    Investigator(switch, backend).handle(message("@investigator check"))
    [(_, text)] = switch.replies
    assert text == ("I couldn't read the payments database: "
                    "No database at data/payments.db. Run: python run.py seed")
