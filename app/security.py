from __future__ import annotations

import secrets
from typing import Any

from fastapi import Header, HTTPException, status

from app.db import connection
from app.passwords import verify_password

# Demo sessions live in memory and are invalidated when the server restarts.
# This is intentionally a local portfolio demo, not production authentication.
_SESSIONS: dict[str, str] = {}
def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = username
    return token


def revoke_session(token: str) -> None:
    _SESSIONS.pop(token, None)


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to continue.")

    token = authorization.split(" ", 1)[1].strip()
    username = _SESSIONS.get(token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Sign in again.")

    with connection() as conn:
        row = conn.execute(
            "SELECT id, username, full_name, role, branch_id FROM users WHERE username = ? AND is_active = 1",
            (username,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is unavailable.")
    return dict(row)
