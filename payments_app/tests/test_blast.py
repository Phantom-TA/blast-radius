from payments_app.blast import find_affected_customers, summarize
from payments_app.service.store import connect


def test_finds_only_orders_with_more_than_one_successful_charge(db_path):
    affected = find_affected_customers(db_path)

    assert [item["order_id"] for item in affected] == ["ORD-1", "ORD-2", "ORD-3"]


def test_item_fields(db_path):
    item = find_affected_customers(db_path)[0]

    assert item == {
        "customer_id": "CUS-1",
        "email": "ana@example.com",
        "order_id": "ORD-1",
        "charge_ids": [1, 2],
        "overcharge_amount": 49.0,
        "complained": True,
    }


def test_overcharge_counts_every_extra_charge(db_path):
    charged_three_times = find_affected_customers(db_path)[2]

    assert charged_three_times["overcharge_amount"] == 58.0


def test_refunded_duplicates_are_no_longer_affected(db_path):
    conn = connect(db_path)
    conn.execute("UPDATE charges SET status = 'refunded' WHERE id = 2")
    conn.close()

    assert [item["order_id"] for item in find_affected_customers(db_path)] == ["ORD-2", "ORD-3"]


def test_summarize(db_path):
    assert summarize(find_affected_customers(db_path)) == {
        "count": 3,
        "silent_count": 2,
        "total_overcharge": 216.0,
        "currency": "USD",
    }


def test_summarize_handles_cents_exactly():
    affected = [{"overcharge_amount": 0.1}, {"overcharge_amount": 0.2}]

    assert summarize(affected)["total_overcharge"] == 0.3


def test_summarize_nothing_affected():
    assert summarize([]) == {
        "count": 0,
        "silent_count": 0,
        "total_overcharge": 0.0,
        "currency": "USD",
    }
