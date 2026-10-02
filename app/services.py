from typing import TypedDict


class Order(TypedDict):
    order_id: int
    item: str
    status: str


class OrderProcessingError(Exception):
    pass


def validate_inventory(state: str) -> None:
    if state != "available":
        raise OrderProcessingError(
            "Unable to process order because the inventory service returned an invalid state."
        )


def process_order(order_id: int) -> Order:
    # Simulate an invalid upstream response without needing an inventory service.
    inventory_state = "unknown" if order_id == 999 else "available"
    validate_inventory(inventory_state)
    return {"order_id": order_id, "item": "demo-notebook", "status": "confirmed"}
