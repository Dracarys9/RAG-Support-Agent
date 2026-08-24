from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


SAFE_FIELDS = {
    "order_id",
    "membership_tier",
    "items",
    "placed_at",
    "status",
    "status_updated_at",
    "shipped_at",
    "delivered_at",
    "carrier",
    "tracking_number",
    "estimated_delivery",
    "customer_safe_message",
}

STALE_DELIVERY_FIELDS = {
    "shipped_at",
    "delivered_at",
    "carrier",
    "tracking_number",
    "estimated_delivery",
}


def normalize_order_id(value: str | None) -> str:
    """Normalize harmless input differences without guessing a different ID."""
    if value is None:
        return ""

    cleaned = re.sub(r"[^A-Z0-9-]", "", value.strip().upper())
    compact_match = re.fullmatch(r"ORD(\d{4})", cleaned)
    if compact_match:
        return f"ORD-{compact_match.group(1)}"
    return cleaned


def _safe_items(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": item.get("name"),
            "quantity": item.get("quantity"),
            "final_sale": item.get("final_sale"),
        }
        for item in items
    ]


def _safe_order(order: dict[str, Any], fields: Iterable[str] | None) -> dict[str, Any]:
    requested = set(fields) if fields is not None else set(SAFE_FIELDS)
    requested &= SAFE_FIELDS

    status = order.get("status")
    if status in {"cancelled", "returned"}:
        requested -= STALE_DELIVERY_FIELDS

    safe: dict[str, Any] = {}
    for field in SAFE_FIELDS:
        if field not in requested:
            continue
        if field == "items":
            safe[field] = _safe_items(order.get("items", []))
        else:
            safe[field] = order.get(field)
    return safe


def load_orders(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load the mock order snapshot and index it by its stored order ID."""
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {order["order_id"]: order for order in payload["orders"]}


def lookup_order(
    path: str | Path,
    order_id: str | None,
    fields: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Look up one order and return a customer-safe result."""
    normalized_id = normalize_order_id(order_id)
    if not normalized_id:
        return {
            "found": False,
            "error": "order_id_required",
            "message": "Please provide your order ID so I can check it.",
        }

    if not re.fullmatch(r"ORD-\d{4}", normalized_id):
        return {
            "found": False,
            "error": "invalid_order_id",
            "order_id": normalized_id,
            "message": "Please check the order ID. It should look like ORD-1007.",
        }

    orders = load_orders(path)
    order = orders.get(normalized_id)
    if order is None:
        return {
            "found": False,
            "error": "order_not_found",
            "order_id": normalized_id,
            "message": "That order was not found. Please check the order ID or contact support.",
            "handoff_recommended": True,
        }

    result: dict[str, Any] = {
        "found": True,
        "data": _safe_order(order, fields),
    }
    if order.get("status") == "exception":
        result["handoff_recommended"] = True
    return result
