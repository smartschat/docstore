"""Integration tests for authentication flow."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

import aiosqlite
from fastapi.testclient import TestClient


class TestLoginFlow:
    """Test complete login flow."""

    def test_login_creates_session_and_sets_cookie(self, client):
        """Login with correct password creates session and sets cookie."""
        response = client.post(
            "/api/auth/login",
            json={"password": "testpassword"}
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "session" in response.cookies

    def test_login_invalid_password_returns_401(self, client):
        """Login with incorrect password returns 401."""
        response = client.post(
            "/api/auth/login",
            json={"password": "wrongpassword"}
        )

        assert response.status_code == 401
        assert "session" not in response.cookies

    def test_authenticated_user_can_access_protected_routes(self, client):
        """After login, user can access protected routes."""
        # Login first
        login_response = client.post(
            "/api/auth/login",
            json={"password": "testpassword"}
        )
        assert login_response.status_code == 200

        # Access protected route
        response = client.get("/api/documents")

        assert response.status_code == 200
        assert "items" in response.json()


class TestLogoutFlow:
    """Test complete logout flow."""

    def test_logout_clears_session_and_cookie(self, client):
        """Logout clears session and cookie."""
        # Login first
        login_response = client.post(
            "/api/auth/login",
            json={"password": "testpassword"}
        )
        assert login_response.status_code == 200

        # Logout
        logout_response = client.post("/api/auth/logout")

        assert logout_response.status_code == 200

    def test_after_logout_cannot_access_protected_routes(self, client, test_db):
        """After logout, user cannot access protected routes with old token."""
        # Login first
        login_response = client.post(
            "/api/auth/login",
            json={"password": "testpassword"}
        )
        assert login_response.status_code == 200
        session_token = login_response.cookies.get("session")

        # Logout
        logout_response = client.post("/api/auth/logout")
        assert logout_response.status_code == 200

        # Try to access protected route with new client (no cookies)
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as new_client:
            # Use the old session token
            new_client.cookies.set("session", session_token)
            response = new_client.get("/api/documents")

            assert response.status_code == 401


class TestSessionValidation:
    """Test session validation."""

    def test_protected_route_without_auth_returns_401(self, client):
        """Accessing protected route without authentication returns 401."""
        # Clear cookies and try to access protected route
        client.cookies.clear()
        response = client.get("/api/documents")

        assert response.status_code == 401

    def test_invalid_session_token_returns_401(self, client):
        """Invalid session token returns 401."""
        client.cookies.set("session", "invalid-token-123")
        response = client.get("/api/documents")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_session_returns_401(self, client, test_db):
        """Expired session returns 401."""
        # Create an expired session directly in the database
        expired_token = "expired-test-token-123"
        expired_time = datetime.utcnow() - timedelta(hours=1)

        async with aiosqlite.connect(test_db) as db:
            await db.execute(
                "INSERT INTO sessions (token, expires_at) VALUES (?, ?)",
                (expired_token, expired_time.isoformat())
            )
            await db.commit()

        # Try to access protected route
        client.cookies.set("session", expired_token)
        response = client.get("/api/documents")

        assert response.status_code == 401
