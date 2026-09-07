"""Test14: safe diagnostics for unexpected response/database failures.

Log correlation ID, route template, exception class, and stack locations only.
Never serialize exception messages, SQL, locals, bodies, headers, or error inputs.
"""
import json
import logging
from pathlib import Path
from traceback import extract_tb

from fastapi import Request
from fastapi.exceptions import ResponseValidationError

from app.core.request_context import _is_valid_request_id

logger = logging.getLogger(__name__)
_SAFE_LOCATIONS = frozenset({
    "response", "body", "recent_tasks", "items", "task", "nodes", "allowed_actions",
    "report_cycle", "task_version", "status",
})


def log_server_failure(request: Request, exc: Exception) -> None:
    """Keep the public error envelope unchanged and retain diagnostic locations."""
    request_id = getattr(request.state, "request_id", None)
    route = request.scope.get("route")
    data = {
        "request_id": request_id if _is_valid_request_id(request_id) else None,
        "route": getattr(route, "path", "<unmatched>"),
        "method": request.method,
        "exception_type": type(exc).__name__,
        "stack": [
            {"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
            for frame in extract_tb(exc.__traceback__)[-12:]
        ],
    }
    if isinstance(exc, ResponseValidationError):
        data["validation_locations"] = [
            [
                part if isinstance(part, int) or part in _SAFE_LOCATIONS else "<field>"
                for part in item.get("loc", ())
            ]
            for item in exc.errors()[:10]
        ]
    # logging.exception/str(exc) would expose SQL parameters and Pydantic inputs.
    logger.error("server_failure %s", json.dumps(data, ensure_ascii=True))
