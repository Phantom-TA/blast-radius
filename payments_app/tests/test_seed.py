from contextlib import closing

import pytest

from payments_app.blast import find_affected_customers, summarize
from payments_app.service.store import connect
from seed.seed import AFFECTED_CUSTOMERS, ORDER_COUNT, build


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("seed") / "payments.db")
    return path, build(path)


def dump(path):
    with closing(connect(path, read_only=True)) as conn:
        return [
            [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1")]
            for table in ("customers", "orders", "charges", "complaints")
        ]


def test_exact_numbers(seeded):
    path, _ = seeded
    affected = find_affected_customers(path)
    summary = summarize(affected)

    assert summary["count"] == AFFECTED_CUSTOMERS
    assert summary["silent_count"] == AFFECTED_CUSTOMERS - 1
    assert len({item["customer_id"] for item in affected}) == AFFECTED_CUSTOMERS
    assert len(dump(path)[1]) == ORDER_COUNT


def test_complainer_is_one_of_the_affected(seeded):
    path, complainer = seeded
    complained = [item for item in find_affected_customers(path) if item["complained"]]

    assert [item["order_id"] for item in complained] == [complainer["order_id"]]


def test_two_runs_give_identical_data(seeded, tmp_path):
    path, complainer = seeded
    second_path = str(tmp_path / "second.db")

    assert build(second_path) == complainer
    assert dump(second_path) == dump(path)
