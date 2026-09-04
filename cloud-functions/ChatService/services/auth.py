"""Verify the short-lived FastAPI-issued token scoped to ChatService task intake."""

from __future__ import annotations

import config
import jwt


def verify_bearer(header: str | None) -> dict[str, object]:
    if not config.CHAT_REQUIRE_AUTH:
        return {}
    if not header or not header.lower().startswith("bearer "):
        raise PermissionError("AI服务需要旺序登录授权")
    token = header.split(" ", 1)[1].strip()
    try:
        claims = jwt.decode(
            token,
            config.JWT_SECRET,
            algorithms=["HS256"],
            issuer=config.JWT_ISSUER,
            audience=config.JWT_AUDIENCE,
            options={"require": ["sub", "iat", "exp", "iss", "aud", "scope"]},
        )
    except jwt.PyJWTError as exc:
        raise PermissionError("AI授权无效或已过期") from exc
    if claims.get("scope") != config.JWT_REQUIRED_SCOPE:
        raise PermissionError("AI授权范围无效")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise PermissionError("AI授权身份无效")
    return claims
