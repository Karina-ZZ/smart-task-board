"""Test14: diagnostics must expose locations, not tokens, SQL, or task contents."""
import logging
from typing import Literal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.errors import register_exception_handlers
from app.core.request_context import RequestContextMiddleware


@pytest.mark.parametrize("kind", ["response", "database", "unexpected"])
def test_server_error_diagnostics_are_correlated_and_sanitized(caplog, kind):
    application = FastAPI()
    application.add_middleware(RequestContextMiddleware)
    register_exception_handlers(application)
    sentinel = "PRIVATE_PASSWORD_TOKEN_TASK_CONTENT"

    @application.get("/response/{task_id}", response_model=list[Literal["allowed"]])
    def response_error(task_id: str):
        return [sentinel]

    @application.get("/database/{task_id}")
    def database_error(task_id: str):
        raise IntegrityError(sentinel, {"password": sentinel}, RuntimeError(sentinel))

    @application.get("/unexpected/{task_id}")
    def unexpected_error(task_id: str):
        raise RuntimeError(sentinel)

    caplog.set_level(logging.ERROR, logger="app.core.error_diagnostics")
    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get(
            f"/{kind}/{sentinel}?token={sentinel}",
            headers={"X-Request-ID": "test14-safe-id", "Authorization": f"Bearer {sentinel}"},
        )
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_server_error", "message": "Internal server error",
                  "details": {}}
    }
    assert sentinel not in response.text + caplog.text
    assert "test14-safe-id" in caplog.text
    assert f"/{kind}/{{task_id}}" in caplog.text
    assert '"stack"' in caplog.text
    if kind == "response":
        assert "ResponseValidationError" in caplog.text
        assert "validation_locations" in caplog.text
