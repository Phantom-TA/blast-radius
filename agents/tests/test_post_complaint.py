import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "post_complaint.py"
spec = importlib.util.spec_from_file_location("post_complaint", SCRIPT)
post_complaint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(post_complaint)

COMPLAINER = {
    "order_id": "ORD-100953",
    "customer_name": "Victor Tanaka",
    "description": "Backpack",
    "amount": 59.0,
}


def test_complaint_from_the_seeded_complainer_mentions_support():
    assert post_complaint.complaint("ORD-100953", COMPLAINER) == (
        "@support Hi, I was charged twice for order ORD-100953 (Backpack, $59.00). "
        "I only bought one. Can you refund the extra charge? Thanks, Victor Tanaka"
    )


def test_complaint_for_another_order_leaves_out_the_details():
    text = post_complaint.complaint("ORD-1", COMPLAINER)
    assert text.startswith("@support Hi, I was charged twice for order ORD-1.")
    assert "Victor" not in text
