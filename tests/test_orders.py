from pathlib import Path

from rag_support_agent.orders import lookup_order


PROJECT_ROOT = Path(__file__).parents[1]
ORDERS_FILE = PROJECT_ROOT / "data" / "orders.json"


def test_valid_order_lookup_normalizes_lowercase_id():
    result = lookup_order(
        ORDERS_FILE,
        " ord-1007 ",
        fields=["order_id", "status", "carrier", "estimated_delivery"],
    )

    assert result["found"] is True
    assert result["data"] == {
        "order_id": "ORD-1007",
        "status": "shipped",
        "carrier": "UPS",
        "estimated_delivery": "2026-08-22",
    }


def test_missing_order_id_does_not_lookup():
    result = lookup_order(ORDERS_FILE, None)

    assert result["found"] is False
    assert result["error"] == "order_id_required"


def test_unknown_order_is_safe_and_recommends_help():
    result = lookup_order(ORDERS_FILE, "ORD-9999")

    assert result["found"] is False
    assert result["error"] == "order_not_found"
    assert result["handoff_recommended"] is True
    assert "status" not in result
    assert "carrier" not in result


def test_lookup_never_returns_private_fields():
    result = lookup_order(ORDERS_FILE, "ORD-1007")
    result_text = repr(result)

    assert "ava.morgan@example.test" not in result_text
    assert "220 King Street" not in result_text
    assert "risk_score" not in result_text
    assert "fraud review" not in result_text.lower()


def test_cancelled_order_drops_stale_delivery_fields():
    result = lookup_order(
        ORDERS_FILE,
        "ORD-1004",
        fields=["order_id", "status", "carrier", "tracking_number", "estimated_delivery"],
    )

    assert result["data"] == {
        "order_id": "ORD-1004",
        "status": "cancelled",
    }


def test_shipped_order_without_eta_keeps_eta_unavailable():
    result = lookup_order(
        ORDERS_FILE,
        "ORD-1011",
        fields=["status", "carrier", "estimated_delivery", "customer_safe_message"],
    )

    assert result["data"]["status"] == "shipped"
    assert result["data"]["carrier"] == "Canada Post"
    assert result["data"]["estimated_delivery"] is None
    assert "not currently available" in result["data"]["customer_safe_message"]


def test_exception_order_recommends_human_help():
    result = lookup_order(ORDERS_FILE, "ORD-1010")

    assert result["data"]["status"] == "exception"
    assert result["handoff_recommended"] is True
