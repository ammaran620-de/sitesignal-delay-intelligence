from __future__ import annotations

import pytest

from app import db
from app.tools import get_audit_logs


@pytest.fixture()
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "sitesignal-test.db")
    db.init_db()
    return tmp_path / "sitesignal-test.db"


def test_demo_roles_are_seeded(isolated_database):
    with db.connection() as conn:
        users = {row["username"]: row["role"] for row in conn.execute("SELECT username, role FROM users")}
    assert users == {"manager": "manager", "technician": "technician", "sales": "sales"}


def test_audit_events_are_persisted(isolated_database):
    db.write_audit("manager-01", "test_action", "construction_project", "SS-DEMO-001", "allowed", "test detail")
    with db.connection() as conn:
        row = conn.execute("SELECT action, outcome, details FROM audit_logs").fetchone()
    assert row["action"] == "test_action"
    assert row["outcome"] == "allowed"
    assert row["details"] == "test detail"


def test_only_manager_can_view_audit_log(isolated_database):
    db.write_audit("manager-01", "login", "session", None, "success")
    manager = {"id": "manager-01", "role": "manager", "branch_id": 1}
    technician = {"id": "tech-01", "role": "technician", "branch_id": 1}
    assert len(get_audit_logs(manager)) == 1
    with pytest.raises(PermissionError):
        get_audit_logs(technician)


def test_audit_log_is_branch_scoped(isolated_database):
    # A second manager belongs to a different branch.
    from app.passwords import hash_password
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO users(id, username, full_name, password_hash, role, branch_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("manager-02", "manager-two", "Casey Patel", hash_password("Branch@123"), "manager", 2),
        )
    db.write_audit("manager-01", "branch_one_action", "project", None, "allowed")
    result = get_audit_logs({"id": "manager-02", "role": "manager", "branch_id": 2})
    assert result == []
