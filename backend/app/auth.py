"""Simple password-based authentication."""

import secrets
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite
from fastapi import Cookie, HTTPException, status, Request, Response

from app.config import get_settings

settings = get_settings()


def verify_password(plain_password: str) -> bool:
    """Check if the provided password matches the configured password."""
    return secrets.compare_digest(plain_password, settings.auth_password)


def generate_session_token() -> str:
    """Generate a secure random session token."""
    return secrets.token_urlsafe(32)


async def create_session(token: str) -> None:
    """Store a new session in the database."""
    expires_at = datetime.utcnow() + timedelta(hours=settings.session_expire_hours)

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "INSERT INTO sessions (token, expires_at) VALUES (?, ?)",
            (token, expires_at.isoformat())
        )
        await db.commit()


async def validate_session(token: str) -> bool:
    """Check if a session token is valid and not expired."""
    if not token:
        return False

    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute(
            "SELECT expires_at FROM sessions WHERE token = ?",
            (token,)
        )
        row = await cursor.fetchone()

        if not row:
            return False

        expires_at = datetime.fromisoformat(row[0])
        if expires_at < datetime.utcnow():
            # Clean up expired session
            await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
            await db.commit()
            return False

        return True


async def delete_session(token: str) -> None:
    """Remove a session from the database."""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
        await db.commit()


async def cleanup_expired_sessions() -> None:
    """Remove all expired sessions."""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "DELETE FROM sessions WHERE expires_at < ?",
            (datetime.utcnow().isoformat(),)
        )
        await db.commit()


async def get_current_session(
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias="session")
) -> str:
    """Dependency to get and validate the current session."""
    # Also check Authorization header for API clients
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        session_token = auth_header[7:]

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    if not await validate_session(session_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    return session_token


def set_session_cookie(response: Response, token: str) -> None:
    """Set the session cookie on the response."""
    # In development (debug=True or no HTTPS), don't require secure cookies
    # secure=False allows cookies over HTTP for local development
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=False,  # Set to True in production behind HTTPS proxy
        samesite="lax",
        max_age=settings.session_expire_hours * 3600,
    )


def clear_session_cookie(response: Response) -> None:
    """Remove the session cookie."""
    response.delete_cookie(key="session")
