"""
Feature: WeCom Mini Program identity client.
Responsibilities: cache application access tokens and exchange wx.qy.login codes for WeCom identity.
Does not own: employee mapping, authorization, or Smart Task Board session issuance.
Plan task: DEV-18 / WeCom authentication baseline.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import Settings

JsonGet = Callable[[str, float], dict[str, object]]
TOKEN_INVALID_ERRCODES = {40014, 42001}


class WeComUpstreamError(RuntimeError):
    """Raised when WeCom rejects or cannot complete an identity request."""

    def __init__(self, message: str, *, errcode: int | None = None) -> None:
        super().__init__(message)
        self.errcode = errcode


@dataclass(frozen=True)
class WeComSessionIdentity:
    """Identity facts returned by WeCom code2Session."""

    user_id: str
    corp_id: str


@dataclass
class _AccessToken:
    value: str
    expires_at: datetime

    def is_usable(self, now: datetime) -> bool:
        # Keep a small safety window so requests do not race token expiration.
        return self.expires_at > now + timedelta(seconds=60)


def _json_get(url: str, timeout_seconds: float) -> dict[str, object]:
    request = Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        # The configured base URL is validated server-side and defaults to WeCom HTTPS.
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        # urllib exposes several transport exceptions; sanitize at this boundary.
        raise WeComUpstreamError("WeCom request failed") from exc
    if not isinstance(payload, dict):
        raise WeComUpstreamError("WeCom returned an invalid response")
    return payload


class WeComClient:
    """Small synchronous client for the two WeCom calls required by Mini Program sign-in."""

    def __init__(self, settings: Settings, *, json_get: JsonGet | None = None) -> None:
        self.settings = settings
        self._json_get = json_get or _json_get
        self._access_token: _AccessToken | None = None
        self._token_lock = Lock()

    @property
    def _base_url(self) -> str:
        return self.settings.wecom_api_base_url.rstrip("/")

    def clear_access_token(self) -> None:
        with self._token_lock:
            self._access_token = None

    def _fetch_access_token(self) -> str:
        secret = self.settings.wecom_app_secret
        if secret is None:
            raise WeComUpstreamError("WeCom application secret is not configured")
        query = urlencode(
            {
                "corpid": self.settings.wecom_corp_id,
                "corpsecret": secret.get_secret_value(),
            }
        )
        payload = self._json_get(
            f"{self._base_url}/cgi-bin/gettoken?{query}",
            float(self.settings.wecom_request_timeout_seconds),
        )
        errcode = int(payload.get("errcode", 0) or 0)
        if errcode != 0:
            raise WeComUpstreamError("WeCom access token request was rejected", errcode=errcode)
        token = str(payload.get("access_token") or "").strip()
        expires_in = int(payload.get("expires_in", 0) or 0)
        if not token or expires_in <= 0:
            raise WeComUpstreamError("WeCom access token response was incomplete")
        self._access_token = _AccessToken(
            value=token,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
        )
        return token

    def access_token(self) -> str:
        now = datetime.now(UTC)
        with self._token_lock:
            if self._access_token is not None and self._access_token.is_usable(now):
                return self._access_token.value
            return self._fetch_access_token()

    def _code_to_session_once(self, code: str, access_token: str) -> dict[str, object]:
        query = urlencode(
            {
                "access_token": access_token,
                "js_code": code,
                "grant_type": "authorization_code",
            }
        )
        return self._json_get(
            f"{self._base_url}/cgi-bin/miniprogram/jscode2session?{query}",
            float(self.settings.wecom_request_timeout_seconds),
        )

    def code_to_session(self, code: str) -> WeComSessionIdentity:
        normalized_code = code.strip()
        if not normalized_code:
            raise WeComUpstreamError("WeCom login code is empty")
        payload = self._code_to_session_once(normalized_code, self.access_token())
        errcode = int(payload.get("errcode", 0) or 0)
        if errcode in TOKEN_INVALID_ERRCODES:
            self.clear_access_token()
            payload = self._code_to_session_once(normalized_code, self.access_token())
            errcode = int(payload.get("errcode", 0) or 0)
        if errcode != 0:
            raise WeComUpstreamError("WeCom login code was rejected", errcode=errcode)

        user_id = str(payload.get("userid") or "").strip()
        corp_id = str(payload.get("corpid") or "").strip()
        if not user_id or not corp_id:
            raise WeComUpstreamError("WeCom login response did not contain an enterprise member")
        return WeComSessionIdentity(user_id=user_id, corp_id=corp_id)
