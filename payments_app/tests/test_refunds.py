from contextlib import closing

import pytest

from payments_app.blast import find_affected_customers
from payments_app.refunds import RefundError, create_refund_batch, execute_refund_batch
from payments_app.service.store import connect


def rows(db_path, query):
    with closing(connect(db_path, read_only=True)) as conn:
        return [dict(row) for row in conn.execute(query)]


@pytest.fixture
def batch_id(db_path):
    return create_refund_batch(find_affected_customers(db_path))


def test_create_makes_a_pending_batch_of_duplicate_charges(db_path, batch_id):
    assert rows(db_path, "SELECT status FROM refund_batches") == [{"status": "pending_approval"}]
    refunds = rows(db_path, "SELECT charge_id, amount_cents, status FROM refunds ORDER BY id")
    assert [refund["charge_id"] for refund in refunds] == [2, 4, 6, 7]
    assert [refund["amount_cents"] for refund in refunds] == [4900, 10900, 2900, 2900]
    assert {refund["status"] for refund in refunds} == {"pending"}


def test_create_does_not_move_any_money(db_path, batch_id):
    assert rows(db_path, "SELECT id FROM charges WHERE status = 'refunded'") == []


def test_create_twice_returns_the_same_batch(db_path, batch_id):
    assert create_refund_batch(find_affected_customers(db_path)) == batch_id
    assert len(rows(db_path, "SELECT id FROM refund_batches")) == 1


def test_create_refuses_a_charge_already_in_another_batch(db_path, batch_id):
    affected = find_affected_customers(db_path)

    with pytest.raises(RefundError):
        create_refund_batch(affected[:1])


def test_create_refuses_an_amount_that_does_not_match_the_database(db_path):
    affected = find_affected_customers(db_path)
    affected[0]["overcharge_amount"] = 5000.0

    with pytest.raises(RefundError):
        create_refund_batch(affected)
    assert rows(db_path, "SELECT id FROM refund_batches") == []


def test_create_refuses_a_charge_from_another_order(db_path):
    affected = find_affected_customers(db_path)
    affected[0]["charge_ids"] = [1, 4]

    with pytest.raises(RefundError):
        create_refund_batch(affected)


def test_create_refuses_an_order_with_a_failed_charge_in_the_list(db_path):
    item = {
        "customer_id": "CUS-4",
        "order_id": "ORD-6",
        "charge_ids": [11, 10],
        "overcharge_amount": 39.0,
    }

    with pytest.raises(RefundError):
        create_refund_batch([item])
    assert rows(db_path, "SELECT id FROM refunds") == []


def test_create_refuses_an_order_with_no_charges_listed(db_path):
    affected = find_affected_customers(db_path)
    affected[0]["charge_ids"] = []

    with pytest.raises(RefundError):
        create_refund_batch(affected)


def test_create_refuses_an_order_that_has_already_been_refunded(db_path):
    affected = find_affected_customers(db_path)
    execute_refund_batch(create_refund_batch(affected), "tushar")

    with pytest.raises(RefundError):
        create_refund_batch(affected)


def test_create_refuses_an_empty_batch(db_path):
    with pytest.raises(RefundError):
        create_refund_batch([])


def test_execute_refunds_only_the_duplicates(db_path, batch_id):
    result = execute_refund_batch(batch_id, "tushar")

    assert result == {"refunded": 4, "total": 216.0}
    refunded = rows(db_path, "SELECT id FROM charges WHERE status = 'refunded' ORDER BY id")
    assert [charge["id"] for charge in refunded] == [2, 4, 6, 7]
    batch = rows(db_path, "SELECT status, approved_by FROM refund_batches")[0]
    assert batch == {"status": "executed", "approved_by": "tushar"}
    assert find_affected_customers(db_path) == []


@pytest.mark.parametrize("approver", ["", "   ", None])
def test_execute_refuses_without_an_approver(db_path, batch_id, approver):
    with pytest.raises(RefundError):
        execute_refund_batch(batch_id, approver)

    assert rows(db_path, "SELECT id FROM charges WHERE status = 'refunded'") == []


def test_execute_refuses_an_unknown_batch(db_path):
    with pytest.raises(RefundError):
        execute_refund_batch("rb-nope", "tushar")


def test_execute_twice_never_refunds_twice(db_path, batch_id):
    execute_refund_batch(batch_id, "tushar")

    with pytest.raises(RefundError):
        execute_refund_batch(batch_id, "tushar")

    assert len(rows(db_path, "SELECT id FROM refunds WHERE status = 'refunded'")) == 4


def test_execute_rolls_back_everything_if_one_charge_is_already_refunded(db_path, batch_id):
    with closing(connect(db_path)) as conn:
        conn.execute("UPDATE charges SET status = 'refunded' WHERE id = 7")

    with pytest.raises(RefundError):
        execute_refund_batch(batch_id, "tushar")

    assert rows(db_path, "SELECT id FROM charges WHERE status = 'refunded'") == [{"id": 7}]
    assert rows(db_path, "SELECT status FROM refund_batches") == [{"status": "pending_approval"}]
