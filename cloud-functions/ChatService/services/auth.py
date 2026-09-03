"""Optional JWT verification shared with LoginService."""

from __future__ import annotations

import jwt

import config


def verify_bearer(header: str | None) -> dict[str, object]:
    if not config.CHAT_REQUIRE_AUTH:
        return {}
    if not header or not header.lower().startswith("bearer "):
        raise PermissionError("AI服务需要登录")
    token = header.split(" ", 1)[1].strip()
    try:
        return jwt.decode(
            token,
            config.JWT_SECRET,
            algorithms=["HS256"],
            issuer=config.JWT_ISSUER,
            audience=config.JWT_AUDIENCE,
        )
    except jwt.PyJWTError as exc:
        raise PermissionError("AI登录状态无效或已过期") from exc
