"""Shared fixtures. Nothing here calls Gemini or touches the network, and no test depends on a real .env."""
from __future__ import annotations

import pytest

from app import db

# Test-only values, set explicitly so no test relies on the built-in local defaults.
TEST_PASSWORDS = {
    "DEMO_MANAGER_PASSWORD": "test-manager-pass-1",
    "DEMO_TECHNICIAN_PASSWORD": "test-technician-pass-2",
    "DEMO_SALES_PASSWORD": "test-sales-pass-3",
}

MANAGER = {"id": "manager-01", "username": "manager", "full_name": "Alex Morgan", "role": "manager", "branch_id": 1}
TECHNICIAN = {"id": "tech-01", "username": "technician", "full_name": "Jordan Lee", "role": "technician", "branch_id": 1}
SALES = {"id": "sales-01", "username": "sales", "full_name": "Taylor Reed", "role": "sales", "branch_id": 1}


@pytest.fixture()
def demo_env(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("SITESIGNAL_ENV", raising=False)
    for name, value in TEST_PASSWORDS.items():
        monkeypatch.setenv(name, value)
    return TEST_PASSWORDS


@pytest.fixture()
def database(tmp_path, monkeypatch, demo_env):
    """A fresh seeded database in a temp directory."""
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "test.db")
    db.init_db()
    return tmp_path / "test.db"


def audit_rows():
    with db.connection() as conn:
        return [dict(r) for r in conn.execute("SELECT actor_id, action, resource_id, outcome FROM audit_logs ORDER BY id")]
