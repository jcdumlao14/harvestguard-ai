"""Isolated nonproduction recovery-test service.

This service is deliberately degraded at startup. It exposes only
a health endpoint and one fixed, token-protected recovery endpoint.
It does not access Docker, production services, or business data.
"""
from __future__ import annotations

import hmac
import threading
from typing import Any

from fastapi import FastAPI, Header, HTTPException


SERVICE_ID = "harvestguard-recovery-test"


def create_app(token: str) -> FastAPI:
    if len(token) < 32 or not token.strip():
        raise ValueError(
            "A dedicated recovery-test token of at least 32 characters is required"
        )

    app = FastAPI(
        title="HarvestGuard Isolated Recovery Test Service",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    state: dict[str, Any] = {
        "service_id": SERVICE_ID,
        "status": "degraded",
        "recovery_generation": 0,
    }
    lock = threading.Lock()

    @app.get("/health")
    def health() -> dict[str, Any]:
        with lock:
            return dict(state)

    @app.post("/internal/recover")
    def recover(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        expected = f"Bearer {token}"

        if authorization is None or not hmac.compare_digest(
            authorization, expected
        ):
            raise HTTPException(status_code=401, detail="Unauthorized")

        with lock:
            state["status"] = "healthy"
            state["recovery_generation"] += 1
            return {
                "accepted": True,
                "service_id": state["service_id"],
            }

    return app
