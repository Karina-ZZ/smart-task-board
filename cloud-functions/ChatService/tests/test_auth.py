"""DEV-18 ChatService auth contract: accept only FastAPI-issued task-intake tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
import os

os.environ["CHAT_REQUIRE_AUTH"] = "true"
os.environ["WANGXU_AI_JWT_SECRET"] = "chat-service-test-secret-with-at-least-32-characters"
os.environ["WANGXU_AI_JWT_ISSUER"] = "smart-task-board"
os.environ["WANGXU_AI_JWT_AUDIENCE"] = "wangxu-chat"

import jwt  # noqa: E402

from services.auth import verify_bearer  # noqa: E402

now = datetime.now(UTC)
base_claims = {
    "sub": "E1001",
    "iss": "smart-task-board",
    "aud": "wangxu-chat",
    "scope": "task-intake",
    "iat": now,
    "exp": now + timedelta(minutes=5),
}
secret = os.environ["WANGXU_AI_JWT_SECRET"]
token = jwt.encode(base_claims, secret, algorithm="HS256")
assert verify_bearer(f"Bearer {token}")["sub"] == "E1001"

bad_scope = jwt.encode({**base_claims, "scope": "admin"}, secret, algorithm="HS256")
try:
    verify_bearer(f"Bearer {bad_scope}")
except PermissionError:
    pass
else:
    raise AssertionError("ChatService must reject tokens outside task-intake scope")

try:
    verify_bearer(None)
except PermissionError:
    pass
else:
    raise AssertionError("ChatService must reject missing bearer tokens when auth is enabled")

print("ChatService test_auth.py: PASS")
