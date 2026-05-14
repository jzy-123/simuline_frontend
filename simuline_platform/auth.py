from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from fastapi import Request


COOKIE_NAME = "simuline_session"
SESSION_SECONDS = int(os.getenv("SIMULINE_PLATFORM_SESSION_SECONDS", "28800"))
USERNAME = os.getenv("SIMULINE_PLATFORM_USER", "admin")
PASSWORD = os.getenv("SIMULINE_PLATFORM_PASSWORD", "simuline123")
PASSWORD_SHA256 = os.getenv("SIMULINE_PLATFORM_PASSWORD_SHA256", "")
SECRET_KEY = os.getenv("SIMULINE_PLATFORM_SECRET", secrets.token_urlsafe(32))
COOKIE_SECURE = os.getenv("SIMULINE_PLATFORM_COOKIE_SECURE", "0") == "1"


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(payload: str) -> str:
    digest = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64encode(digest)


def _password_matches(password: str) -> bool:
    if PASSWORD_SHA256:
        digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(digest, PASSWORD_SHA256)
    return hmac.compare_digest(password, PASSWORD)


def authenticate_user(username: str, password: str) -> dict[str, str] | None:
    if not hmac.compare_digest(username.strip(), USERNAME):
        return None
    if not _password_matches(password):
        return None
    return {"username": USERNAME}


def create_session_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": int(time.time()) + SESSION_SECONDS,
    }
    payload_text = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{payload_text}.{_sign(payload_text)}"


def verify_session_token(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    payload_text, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(payload_text)):
        return None
    try:
        payload = json.loads(_b64decode(payload_text).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    if payload.get("sub") != USERNAME:
        return None
    return {"username": payload["sub"], "expires_at": payload["exp"]}


def current_user_from_request(request: Request) -> dict[str, Any] | None:
    return verify_session_token(request.cookies.get(COOKIE_NAME))
