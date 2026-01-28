"""
Tests for Admin UI authentication.

Tests verify password verification, session creation/validation,
and authentication flow.
"""

import time
from unittest.mock import patch

from src.admin.auth import (
    create_session_token,
    sign_session,
    verify_password,
    verify_session,
)


class TestPasswordVerification:
    """Tests for password verification."""

    def test_verify_password_correct(self) -> None:
        """Correct password returns True."""
        with patch("src.admin.auth.get_admin_config") as mock_config:
            mock_config.return_value = {"password": "secret123"}
            assert verify_password("secret123") is True

    def test_verify_password_incorrect(self) -> None:
        """Incorrect password returns False."""
        with patch("src.admin.auth.get_admin_config") as mock_config:
            mock_config.return_value = {"password": "secret123"}
            assert verify_password("wrongpassword") is False

    def test_verify_password_empty_config(self) -> None:
        """Empty password in config returns False."""
        with patch("src.admin.auth.get_admin_config") as mock_config:
            mock_config.return_value = {"password": ""}
            assert verify_password("anything") is False

    def test_verify_password_missing_config(self) -> None:
        """Missing password in config returns False."""
        with patch("src.admin.auth.get_admin_config") as mock_config:
            mock_config.return_value = {}
            assert verify_password("anything") is False


class TestSessionToken:
    """Tests for session token creation."""

    def test_create_session_token_returns_string(self) -> None:
        """Session token is a non-empty string."""
        token = create_session_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_session_token_unique(self) -> None:
        """Each session token is unique."""
        tokens = [create_session_token() for _ in range(10)]
        assert len(set(tokens)) == 10


class TestSessionSigning:
    """Tests for session signing and verification."""

    def test_sign_session_format(self) -> None:
        """Signed session has correct format."""
        with patch("src.admin.auth.get_admin_config") as mock_config:
            mock_config.return_value = {"session_secret": "testsecret"}
            signed = sign_session("token123", 1234567890)

            parts = signed.split(":")
            assert len(parts) == 3
            assert parts[0] == "token123"
            assert parts[1] == "1234567890"
            assert len(parts[2]) == 64  # SHA256 hex digest

    def test_verify_session_valid(self) -> None:
        """Valid session verifies successfully."""
        with patch("src.admin.auth.get_admin_config") as mock_config:
            mock_config.return_value = {
                "session_secret": "testsecret",
                "session_expiry_hours": 24,
            }
            timestamp = int(time.time())
            signed = sign_session("token123", timestamp)

            assert verify_session(signed) is True

    def test_verify_session_expired(self) -> None:
        """Expired session returns False."""
        with patch("src.admin.auth.get_admin_config") as mock_config:
            mock_config.return_value = {
                "session_secret": "testsecret",
                "session_expiry_hours": 1,
            }
            # Session from 2 hours ago
            old_timestamp = int(time.time()) - 7200
            signed = sign_session("token123", old_timestamp)

            assert verify_session(signed) is False

    def test_verify_session_tampered(self) -> None:
        """Tampered session returns False."""
        with patch("src.admin.auth.get_admin_config") as mock_config:
            mock_config.return_value = {
                "session_secret": "testsecret",
                "session_expiry_hours": 24,
            }
            timestamp = int(time.time())
            signed = sign_session("token123", timestamp)

            # Tamper with the signature
            tampered = signed[:-1] + "X"
            assert verify_session(tampered) is False

    def test_verify_session_empty(self) -> None:
        """Empty session returns False."""
        assert verify_session("") is False
        assert verify_session(None) is False

    def test_verify_session_invalid_format(self) -> None:
        """Invalid format returns False."""
        assert verify_session("invalid") is False
        assert verify_session("a:b") is False
        assert verify_session("a:b:c:d") is False

    def test_verify_session_non_numeric_timestamp(self) -> None:
        """Non-numeric timestamp returns False."""
        assert verify_session("token:notanumber:signature") is False
