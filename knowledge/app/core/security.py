"""
API token security for Knowledge App.

When API_SECURITY_ENABLED is True, requests to protected paths must include
a token that is in API_PROVISIONED_TOKENS (.env, comma-separated list).
Validation is membership-only: the token must be in the provisioned list.

Tokens can be OAuth-style encoded (org, team, iat, valid_sec) via encode_oauth_token(),
or any string you add to API_PROVISIONED_TOKENS.

Token can be sent as:
  - Header: Authorization: Bearer <token>
  - Header: X-API-Token: <token>
"""
import base64
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

__all__ = [
    "encode_oauth_token",
    "decode_oauth_token",
    "validate_oauth_payload",
    "APITokenMiddleware",
    "PUBLIC_PATHS",
]

# Paths that do not require a token even when security is enabled
PUBLIC_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/health",
}

# OAuth-style payload keys
OAUTH_PAYLOAD_KEYS = ("org", "team", "iat", "valid_sec")


def encode_oauth_token(org: str, team: str, iat: int, valid_sec: int) -> str:
    """
    Encode a simulated OAuth token (org, team, issued-at timestamp, validity seconds).
    Returns base64url-encoded JSON (no signature; simulated).
    """
    payload = {"org": org, "team": team, "iat": iat, "valid_sec": valid_sec}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def decode_oauth_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode base64url token to payload dict, or None if invalid."""
    try:
        padded = token + "=" * (4 - len(token) % 4)
        raw = base64.urlsafe_b64decode(padded)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def validate_oauth_payload(payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Check payload has required keys and is not expired.
    Returns (valid, error_message). error_message is None if valid.
    """
    if not isinstance(payload, dict):
        return False, "Invalid token payload"
    for key in OAUTH_PAYLOAD_KEYS:
        if key not in payload:
            return False, f"Token missing field: {key}"
    iat = payload["iat"]
    valid_sec = payload["valid_sec"]
    if not isinstance(iat, (int, float)) or not isinstance(valid_sec, (int, float)):
        return False, "Token iat/valid_sec must be numbers"
    now = int(time.time())
    if iat + valid_sec < now:
        return False, "Token expired"
    return True, None


def _get_token_from_request(request: Request) -> Optional[str]:
    """Extract token from Authorization: Bearer or X-API-Token header."""
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.headers.get("X-API-Token", "").strip() or None


def is_protected_path(path: str) -> bool:
    """True if path is under /api/ and not in PUBLIC_PATHS."""
    if path in PUBLIC_PATHS:
        return False
    if path.startswith("/api/"):
        return True
    return False


def validate_token(request: Request) -> Tuple[bool, Optional[str]]:
    """
    Check if request is allowed.
    Returns (allowed, error_message). error_message is None if allowed.
    When security is on, only tokens in API_PROVISIONED_TOKENS (.env) are accepted.
    """
    from app.core.settings import get_settings
    settings = get_settings()
    if not settings.API_SECURITY_ENABLED:
        return True, None
    provisioned = settings.get_provisioned_tokens()
    if not provisioned:
        logger.warning("API_SECURITY_ENABLED is True but API_PROVISIONED_TOKENS is empty")
        return False, "API security is enabled but no provisioned tokens configured"
    token = _get_token_from_request(request)
    if not token:
        return False, "Missing API token. Use Authorization: Bearer <token> or X-API-Token: <token>"
    if token not in provisioned:
        return False, "Invalid or expired API token"
    return True, None


class APITokenMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces API token for protected paths when API_SECURITY_ENABLED is True."""

    async def dispatch(self, request: Request, call_next):
        if not is_protected_path(request.url.path):
            return await call_next(request)
        allowed, error = validate_token(request)
        if not allowed:
            return JSONResponse(
                status_code=401,
                content={"detail": error or "Unauthorized"},
            )
        return await call_next(request)
