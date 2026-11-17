from __future__ import annotations

import logging
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.config import DATABASE_PATH as CONFIG_DATABASE_PATH
from app.config import is_deployed
from app.passwords import hash_password, verify_password

logger = logging.getLogger(__name__)

# Keep this module-level name so tests can safely monkeypatch the database path.
DATABASE_PATH: Path = CONFIG_DATABASE_PATH

# Local development only. These are never used on a hosted service (see demo_passwords) and are not
# documented for users: on any shared machine, set DEMO_*_PASSWORD instead.
LOCAL_DEMO_PASSWORDS = {"manager": "Manager@123", "technician": "Tech@123", "sales": "Sales@123"}
MIN_DEPLOYED_PASSWORD_LENGTH = 12
REQUIRED_WHEN_DEPLOYED = ("manager", "technician")


class ConfigurationError(RuntimeError):
    """The service is configured in a way it must not run with."""


def demo_passwords(env=None, deployed: bool | None = None) -> dict[str, str | None]:
    """Passwords for the seeded demo accounts, by role.

    Local: DEMO_<ROLE>_PASSWORD if set, else the built-in local default (logged as a warning).
    Deployed: manager and technician must be set explicitly, at least 12 characters, and not a built-in
    default, otherwise this raises ConfigurationError. The sales account is optional there; unset means the
    account is created inactive (None), so no default password is ever live on a hosted service.
    Error messages name the variable, never its value.
    """
    env = os.environ if env is None else env
    deployed = is_deployed(env) if deployed is None else deployed
    out: dict[str, str | None] = {}
    problems: list[str] = []
    for role, default in LOCAL_DEMO_PASSWORDS.items():
        name = f"DEMO_{role.upper()}_PASSWORD"
        value = (env.get(name) or "").strip()
        if not deployed:
            if not value:
                logger.warning("%s is not set; using the built-in local demo password for '%s'", name, role)
            out[role] = value or default
        elif not value:
            if role in REQUIRED_WHEN_DEPLOYED:
                problems.append(f"{name} is not set")
            out[role] = None
        elif value in LOCAL_DEMO_PASSWORDS.values():
            problems.append(f"{name} is a built-in local demo password")
        elif len(value) < MIN_DEPLOYED_PASSWORD_LENGTH:
            problems.append(f"{name} must be at least {MIN_DEPLOYED_PASSWORD_LENGTH} characters")
        else:
            out[role] = value
    if problems:
        raise ConfigurationError(
            "Refusing to start a deployed service with unsafe demo credentials: " + "; ".join(problems) + "."
        )
    return out


def _reject_default_passwords_in_existing_users(conn: sqlite3.Connection) -> None:
    """A database created locally and then deployed would carry the built-in passwords with it."""
    for row in conn.execute("SELECT username, password_hash FROM users WHERE is_active = 1"):
        if any(verify_password(default, row["password_hash"]) for default in LOCAL_DEMO_PASSWORDS.values()):
            raise ConfigurationError(
                f"Refusing to start a deployed service: user '{row['username']}' in the existing database "
                "still has a built-in local demo password. Use a fresh database or change the password."
            )


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('manager', 'technician', 'sales')),
                branch_id INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id TEXT NOT NULL REFERENCES users(id),
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT,
                outcome TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        deployed = is_deployed()
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            passwords = demo_passwords(deployed=deployed)
            accounts = [
                ("manager-01", "manager", "Alex Morgan", "manager"),
                ("tech-01", "technician", "Jordan Lee", "technician"),
                ("sales-01", "sales", "Taylor Reed", "sales"),
            ]
            rows = []
            for user_id, username, full_name, role in accounts:
                password = passwords[role]
                # No configured password means an inactive account with an unguessable one.
                rows.append((user_id, username, full_name, hash_password(password or secrets.token_urlsafe(32)),
                             role, 1, 1 if password else 0))
                if not password:
                    logger.warning("No password configured for '%s'; the account is created inactive", username)
            conn.executemany(
                "INSERT INTO users(id, username, full_name, password_hash, role, branch_id, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        elif deployed:
            _reject_default_passwords_in_existing_users(conn)


def write_audit(
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None,
    outcome: str,
    details: str = "",
) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connection() as conn:
        conn.execute(
            "INSERT INTO audit_logs(actor_id, action, resource_type, resource_id, outcome, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (actor_id, action, resource_type, resource_id, outcome, details[:1000], now),
        )
