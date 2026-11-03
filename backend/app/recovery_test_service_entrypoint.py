"""Environment-configured startup for the isolated recovery-test service."""
from __future__ import annotations

import os

from app.recovery_test_service import create_app as build_app


def create_app():
    token = os.environ.get("HARVESTGUARD_RECOVERY_TEST_TOKEN", "")
    return build_app(token=token)
