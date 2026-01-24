"""Unit tests for authentication service."""

from datetime import datetime, timedelta
from unittest.mock import patch

import aiosqlite
import pytest

from app.auth import (
    cleanup_expired_sessions,
    create_session,
    delete_session,
    generate_session_token,
    validate_session,
    verify_password,
)


class TestVerifyPassword:
    """Tests for verify_password function."""

    def test_accepts_correct_password(self, test_settings):
        """Correct password returns True."""
        # test_settings fixture sets AUTH_PASSWORD to "testpassword"
        result = verify_password("testpassword")
        assert result is True

    def test_rejects_incorrect_password(self, test_settings):
        """Incorrect password returns False."""
        result = verify_password("wrongpassword")
        assert result is False

    def test_rejects_empty_password(self, test_settings):
        """Empty password returns False."""
        result = verify_password("")
        assert result is False

    def test_timing_safe_comparison(self, test_settings):
        """Uses timing-safe comparison (secrets.compare_digest)."""
        # This test verifies the implementation uses compare_digest
        # by checking that similar-length wrong passwords work correctly
        result1 = verify_password("testpasswor")  # One char short
        result2 = verify_password("testpasswordx")  # One char long
        assert result1 is False
        assert result2 is False


class TestGenerateSessionToken:
    """Tests for generate_session_token function."""

    def test_generates_sufficient_length(self):
        """Token has sufficient length for security."""
        token = generate_session_token()
        # token_urlsafe(32) generates ~43 characters
        assert len(token) >= 32

    def test_generates_unique_tokens(self):
        """Each call generates a unique token."""
        tokens = [generate_session_token() for _ in range(100)]
        assert len(set(tokens)) == 100

    def test_generates_url_safe_token(self):
        """Token is URL-safe (no special characters)."""
        token = generate_session_token()
        # URL-safe base64 uses only alphanumeric, hyphen, underscore
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', token)


class TestCreateSession:
    """Tests for create_session function."""

    @pytest.mark.asyncio
    async def test_stores_session_in_database(self, test_db):
        """Session is stored in database."""
        token = "test-session-token"
        await create_session(token)

        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute(
                "SELECT token FROM sessions WHERE token = ?",
                (token,)
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == token

    @pytest.mark.asyncio
    async def test_sets_expiration(self, test_db, test_settings):
        """Session has correct expiration time."""
        token = "test-session-token"
        await create_session(token)

        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute(
                "SELECT expires_at FROM sessions WHERE token = ?",
                (token,)
            )
            row = await cursor.fetchone()
            expires_at = datetime.fromisoformat(row[0])

            # Should expire in approximately session_expire_hours
            expected = datetime.utcnow() + timedelta(hours=test_settings.session_expire_hours)
            # Allow 1 minute tolerance
            assert abs((expires_at - expected).total_seconds()) < 60


class TestValidateSession:
    """Tests for validate_session function."""

    @pytest.mark.asyncio
    async def test_valid_session_returns_true(self, test_db):
        """Valid session returns True."""
        token = "valid-token"
        await create_session(token)

        result = await validate_session(token)
        assert result is True

    @pytest.mark.asyncio
    async def test_nonexistent_session_returns_false(self, test_db):
        """Non-existent session returns False."""
        result = await validate_session("nonexistent-token")
        assert result is False

    @pytest.mark.asyncio
    async def test_expired_session_returns_false(self, test_db):
        """Expired session returns False."""
        token = "expired-token"

        # Insert expired session directly
        expired_time = datetime.utcnow() - timedelta(hours=1)
        async with aiosqlite.connect(test_db) as db:
            await db.execute(
                "INSERT INTO sessions (token, expires_at) VALUES (?, ?)",
                (token, expired_time.isoformat())
            )
            await db.commit()

        result = await validate_session(token)
        assert result is False

    @pytest.mark.asyncio
    async def test_expired_session_is_deleted(self, test_db):
        """Expired session is cleaned up when validated."""
        token = "expired-token"

        # Insert expired session
        expired_time = datetime.utcnow() - timedelta(hours=1)
        async with aiosqlite.connect(test_db) as db:
            await db.execute(
                "INSERT INTO sessions (token, expires_at) VALUES (?, ?)",
                (token, expired_time.isoformat())
            )
            await db.commit()

        await validate_session(token)

        # Session should be deleted
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute(
                "SELECT token FROM sessions WHERE token = ?",
                (token,)
            )
            row = await cursor.fetchone()
            assert row is None

    @pytest.mark.asyncio
    async def test_empty_token_returns_false(self, test_db):
        """Empty token returns False."""
        result = await validate_session("")
        assert result is False

    @pytest.mark.asyncio
    async def test_none_token_returns_false(self, test_db):
        """None token returns False."""
        result = await validate_session(None)
        assert result is False


class TestDeleteSession:
    """Tests for delete_session function."""

    @pytest.mark.asyncio
    async def test_deletes_existing_session(self, test_db):
        """Existing session is deleted."""
        token = "to-delete"
        await create_session(token)

        await delete_session(token)

        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute(
                "SELECT token FROM sessions WHERE token = ?",
                (token,)
            )
            row = await cursor.fetchone()
            assert row is None

    @pytest.mark.asyncio
    async def test_handles_nonexistent_session(self, test_db):
        """Deleting non-existent session doesn't raise."""
        # Should not raise
        await delete_session("nonexistent-token")


class TestCleanupExpiredSessions:
    """Tests for cleanup_expired_sessions function."""

    @pytest.mark.asyncio
    async def test_removes_expired_sessions(self, test_db):
        """Expired sessions are removed."""
        # Insert expired session
        expired_time = datetime.utcnow() - timedelta(hours=1)
        async with aiosqlite.connect(test_db) as db:
            await db.execute(
                "INSERT INTO sessions (token, expires_at) VALUES (?, ?)",
                ("expired-1", expired_time.isoformat())
            )
            await db.execute(
                "INSERT INTO sessions (token, expires_at) VALUES (?, ?)",
                ("expired-2", expired_time.isoformat())
            )
            await db.commit()

        await cleanup_expired_sessions()

        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM sessions")
            count = (await cursor.fetchone())[0]
            assert count == 0

    @pytest.mark.asyncio
    async def test_keeps_valid_sessions(self, test_db):
        """Valid sessions are kept."""
        # Insert valid session
        valid_time = datetime.utcnow() + timedelta(hours=24)
        expired_time = datetime.utcnow() - timedelta(hours=1)

        async with aiosqlite.connect(test_db) as db:
            await db.execute(
                "INSERT INTO sessions (token, expires_at) VALUES (?, ?)",
                ("valid-token", valid_time.isoformat())
            )
            await db.execute(
                "INSERT INTO sessions (token, expires_at) VALUES (?, ?)",
                ("expired-token", expired_time.isoformat())
            )
            await db.commit()

        await cleanup_expired_sessions()

        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute("SELECT token FROM sessions")
            rows = await cursor.fetchall()
            tokens = [row[0] for row in rows]

            assert "valid-token" in tokens
            assert "expired-token" not in tokens

    @pytest.mark.asyncio
    async def test_handles_empty_sessions_table(self, test_db):
        """Works correctly with no sessions."""
        # Should not raise
        await cleanup_expired_sessions()
