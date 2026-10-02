from pathlib import Path

import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI

from app.config import configure_sentry
from app.services import Order, process_order

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

configure_sentry()

app = FastAPI(title="Sentry Support Demo", version="1.0.0")


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "sentry-support-demo", "status": "ok"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/orders/{order_id}")
async def get_order(order_id: int) -> Order:
    sentry_sdk.set_tag("component", "order-api")
    sentry_sdk.set_context("order", {"id": order_id, "synthetic": True})
    return process_order(order_id)
