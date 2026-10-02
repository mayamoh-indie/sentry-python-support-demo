import importlib
import sys

import pytest
import sentry_sdk
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from app.services import OrderProcessingError


class MemoryTransport(Transport):
    def __init__(self):
        super().__init__()
        self.envelopes = []

    def capture_envelope(self, envelope):
        self.envelopes.append(envelope)


@pytest.fixture
def demo(monkeypatch):
    # Override shell configuration and .env before importing the application.
    monkeypatch.setenv("SENTRY_DSN", "")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "candidate-demo")
    monkeypatch.setenv("SENTRY_RELEASE", "sentry-support-demo@1.0.0")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "1.0")
    monkeypatch.delenv("SENTRY_SPOTLIGHT", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    transport = MemoryTransport()
    initialize = sentry_sdk.init

    def init_in_memory(**options):
        return initialize(**options, transport=transport)

    monkeypatch.setattr(sentry_sdk, "init", init_in_memory)
    if "app.main" in sys.modules:
        main = importlib.reload(sys.modules["app.main"])
    else:
        main = importlib.import_module("app.main")
    with TestClient(main.app, raise_server_exceptions=False) as client:
        yield client, transport
    sentry_sdk.get_client().close()


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/", {"service": "sentry-support-demo", "status": "ok"}),
        ("/health", {"status": "ok"}),
        (
            "/api/orders/123",
            {"order_id": 123, "item": "demo-notebook", "status": "confirmed"},
        ),
    ],
)
def test_success(demo, path, expected):
    client, _ = demo
    response = client.get(path)
    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.parametrize("order_id", ["abc", "1.5", "null", "%20"])
def test_invalid_order_id(demo, order_id):
    client, transport = demo
    response = client.get(f"/api/orders/{order_id}")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "order_id"]
    assert not any(
        item.headers["type"] == "event"
        for envelope in transport.envelopes
        for item in envelope.items
    )


@pytest.mark.parametrize("order_id", [0, -1])
def test_signed_integer_ids_are_synthetic_orders(demo, order_id):
    client, _ = demo
    response = client.get(f"/api/orders/{order_id}")
    assert response.status_code == 200
    assert response.json()["order_id"] == order_id


def test_failure_is_unhandled(demo):
    client, _ = demo
    with TestClient(client.app) as raising_client:
        with pytest.raises(OrderProcessingError, match="inventory service"):
            raising_client.get("/api/orders/999")


def test_sentry_captures_failure_and_request_context(demo):
    client, transport = demo
    response = client.get("/api/orders/999")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    events = [
        item.payload.json
        for envelope in transport.envelopes
        for item in envelope.items
        if item.headers["type"] == "event"
    ]
    assert len(events) == 1
    event = events[0]
    error = event["exception"]["values"][-1]
    assert error["type"] == "OrderProcessingError"
    assert error["value"] == (
        "Unable to process order because the inventory service returned an invalid state."
    )
    assert error["mechanism"]["handled"] is False
    frames = error["stacktrace"]["frames"]
    app_functions = [f["function"] for f in frames if f["module"].startswith("app.")]
    assert app_functions == ["get_order", "process_order", "validate_inventory"]
    assert all(not f.get("vars") for f in frames)
    assert event["environment"] == "candidate-demo"
    assert event["release"] == "sentry-support-demo@1.0.0"
    assert event["tags"]["component"] == "order-api"
    assert event["contexts"]["order"] == {"id": 999, "synthetic": True}
    assert event["request"]["method"] == "GET"
    assert event["request"]["url"].endswith("/api/orders/999")


def test_tracing_keeps_route_name_and_isolates_order_context(demo):
    client, transport = demo
    client.get("/api/orders/123")
    client.get("/health")
    transactions = [
        item.payload.json
        for envelope in transport.envelopes
        for item in envelope.items
        if item.headers["type"] == "transaction"
    ]
    order = next(t for t in transactions if t["transaction"] == "/api/orders/{order_id}")
    health = next(t for t in transactions if t["transaction"] == "/health")
    assert order["tags"]["component"] == "order-api"
    assert order["contexts"]["order"]["id"] == 123
    assert "order" not in health["contexts"]
    assert "component" not in health.get("tags", {})
