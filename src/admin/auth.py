"""
Authentication for Admin UI.

Provides simple password-based authentication with session cookies.
"""

import hashlib
import hmac
import secrets
import time
from typing import Any

from fastapi import Cookie, HTTPException, Request, Response

from src.core.config import get_config


def get_admin_config() -> dict[str, Any]:
    """Load admin configuration."""
    config = get_config()
    return config.get("admin", {})


def verify_password(password: str) -> bool:
    """
    Verify password against configured admin password.

    Args:
        password: Password to verify.

    Returns:
        True if password matches.
    """
    admin_config = get_admin_config()
    correct_password = admin_config.get("password", "")

    if not correct_password:
        return False

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(password, correct_password)


def create_session_token() -> str:
    """
    Create a secure session token.

    Returns:
        Random session token.
    """
    return secrets.token_urlsafe(32)


def sign_session(token: str, timestamp: int) -> str:
    """
    Sign a session token with timestamp.

    Args:
        token: Session token.
        timestamp: Unix timestamp.

    Returns:
        Signed session string.
    """
    admin_config = get_admin_config()
    secret = admin_config.get("session_secret", "default-secret")

    data = f"{token}:{timestamp}"
    signature = hmac.new(
        secret.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()

    return f"{token}:{timestamp}:{signature}"


def verify_session(session_value: str) -> bool:
    """
    Verify a signed session.

    Args:
        session_value: Signed session string.

    Returns:
        True if session is valid and not expired.
    """
    if not session_value:
        return False

    try:
        parts = session_value.split(":")
        if len(parts) != 3:
            return False

        token, timestamp_str, signature = parts
        timestamp = int(timestamp_str)

        # Check expiry
        admin_config = get_admin_config()
        expiry_hours = admin_config.get("session_expiry_hours", 24)
        expiry_seconds = expiry_hours * 3600

        if time.time() - timestamp > expiry_seconds:
            return False

        # Verify signature
        expected = sign_session(token, timestamp)
        return hmac.compare_digest(session_value, expected)

    except (ValueError, TypeError):
        return False


def create_session_cookie(response: Response) -> None:
    """
    Create and set session cookie on response.

    Args:
        response: FastAPI response to set cookie on.
    """
    token = create_session_token()
    timestamp = int(time.time())
    session_value = sign_session(token, timestamp)

    admin_config = get_admin_config()
    expiry_hours = admin_config.get("session_expiry_hours", 24)

    response.set_cookie(
        key="admin_session",
        value=session_value,
        max_age=expiry_hours * 3600,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    """
    Clear session cookie.

    Args:
        response: FastAPI response to clear cookie on.
    """
    response.delete_cookie(key="admin_session")


def require_auth(admin_session: str | None = Cookie(default=None)) -> bool:
    """
    Dependency that requires valid authentication.

    Args:
        admin_session: Session cookie value.

    Returns:
        True if authenticated.

    Raises:
        HTTPException: If not authenticated (redirects to login).
    """
    if not verify_session(admin_session):
        raise HTTPException(
            status_code=303,
            headers={"Location": "/admin/login"}
        )
    return True


def get_auth_status(request: Request) -> bool:
    """
    Check if request is authenticated.

    Args:
        request: FastAPI request.

    Returns:
        True if authenticated.
    """
    session = request.cookies.get("admin_session")
    return verify_session(session)
