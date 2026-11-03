from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.config import DATABASE_PATH as CONFIG_DATABASE_PATH
from app.passwords import hash_password

# Keep this module-level name so tests can safely monkeypatch the database path.
DATABASE_PATH: Path = CONFIG_DATABASE_PATH


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
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            # Local defaults preserve the out-of-box development experience.
            # On Render, set unique secret values for the manager and technician
            # accounts in the service environment; never publish those values.
            manager_password = os.getenv("DEMO_MANAGER_PASSWORD", "Manager@123")
            technician_password = os.getenv("DEMO_TECHNICIAN_PASSWORD", "Tech@123")
            sales_password = os.getenv("DEMO_SALES_PASSWORD", "Sales@123")
            users = [
                ("manager-01", "manager", "Alex Morgan", hash_password(manager_password), "manager", 1, 1),
                ("tech-01", "technician", "Jordan Lee", hash_password(technician_password), "technician", 1, 1),
                ("sales-01", "sales", "Taylor Reed", hash_password(sales_password), "sales", 1, 1),
            ]
            conn.executemany(
                "INSERT INTO users(id, username, full_name, password_hash, role, branch_id, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                users,
            )


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
