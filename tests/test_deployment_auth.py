"""Local demo accounts versus a hosted service.

Locally the built-in demo passwords remain a development convenience. On a hosted service no default password may
become live: the service must be given real ones, or refuse to start (manager, technician) or leave the account
inactive (sales).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import is_deployed
from app.db import ConfigurationError, LOCAL_DEMO_PASSWORDS, demo_passwords
from app.main import app
from app.passwords import hash_password, verify_password

STRONG = {"DEMO_MANAGER_PASSWORD": "a-long-unique-manager-pw", "DEMO_TECHNICIAN_PASSWORD": "a-long-unique-tech-pw-2"}


# ------------------------------------------------------------------ what counts as deployed

@pytest.mark.parametrize("env,expected", [
    ({}, False), ({"SITESIGNAL_ENV": "local"}, False), ({"SITESIGNAL_ENV": "production"}, True),
    ({"SITESIGNAL_ENV": " Staging "}, True), ({"RENDER": "true"}, True), ({"RENDER": ""}, False)])
def test_is_deployed(env, expected):
    assert is_deployed(env) is expected


# ------------------------------------------------------------------ password resolution

def test_local_falls_back_to_builtin_passwords_with_a_warning(caplog):
    with caplog.at_level("WARNING"):
        got = demo_passwords(env={}, deployed=False)
    assert got == LOCAL_DEMO_PASSWORDS
    assert "DEMO_MANAGER_PASSWORD is not set" in caplog.text
    assert not any(pw in caplog.text for pw in LOCAL_DEMO_PASSWORDS.values())     # the warning names the variable only


def test_local_uses_configured_passwords_when_given():
    got = demo_passwords(env={"DEMO_MANAGER_PASSWORD": "mine"}, deployed=False)
    assert got["manager"] == "mine" and got["technician"] == LOCAL_DEMO_PASSWORDS["technician"]


def test_deployed_without_passwords_refuses_to_start_and_names_the_variables():
    with pytest.raises(ConfigurationError) as err:
        demo_passwords(env={}, deployed=True)
    message = str(err.value)
    assert "DEMO_MANAGER_PASSWORD is not set" in message and "DEMO_TECHNICIAN_PASSWORD is not set" in message
    assert "DEMO_SALES_PASSWORD" not in message                      # sales is optional when deployed


@pytest.mark.parametrize("bad,reason", [("short1", "at least 12"), ("Manager@123", "built-in local demo password")])
def test_deployed_rejects_short_and_builtin_passwords_without_echoing_them(bad, reason):
    env = {**STRONG, "DEMO_MANAGER_PASSWORD": bad}
    with pytest.raises(ConfigurationError, match=reason) as err:
        demo_passwords(env=env, deployed=True)
    assert bad not in str(err.value)


def test_deployed_with_strong_passwords_leaves_sales_inactive_unless_configured():
    got = demo_passwords(env=STRONG, deployed=True)
    assert got["manager"] == STRONG["DEMO_MANAGER_PASSWORD"] and got["sales"] is None
    got = demo_passwords(env={**STRONG, "DEMO_SALES_PASSWORD": "a-long-unique-sales-pw-3"}, deployed=True)
    assert got["sales"] == "a-long-unique-sales-pw-3"


# ------------------------------------------------------------------ what lands in the database

def seeded_users(path):
    with db.connection() as conn:
        return {r["username"]: dict(r) for r in conn.execute("SELECT * FROM users")}


def test_deployed_startup_with_strong_passwords_seeds_only_configured_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "d.db")
    for k, v in STRONG.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("DEMO_SALES_PASSWORD", raising=False)
    monkeypatch.setenv("SITESIGNAL_ENV", "production")
    db.init_db()
    users = seeded_users(tmp_path)
    assert users["manager"]["is_active"] == 1 and users["technician"]["is_active"] == 1
    assert users["sales"]["is_active"] == 0
    assert verify_password(STRONG["DEMO_MANAGER_PASSWORD"], users["manager"]["password_hash"])
    assert not any(verify_password(pw, u["password_hash"]) for u in users.values() for pw in LOCAL_DEMO_PASSWORDS.values())


def test_deployed_startup_without_passwords_raises_and_creates_no_users(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "d.db")
    for k in ("DEMO_MANAGER_PASSWORD", "DEMO_TECHNICIAN_PASSWORD", "DEMO_SALES_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(ConfigurationError):
        db.init_db()
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_deploying_a_database_that_still_has_a_builtin_password_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "d.db")
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("SITESIGNAL_ENV", raising=False)
    for k in ("DEMO_MANAGER_PASSWORD", "DEMO_TECHNICIAN_PASSWORD", "DEMO_SALES_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    db.init_db()                                                  # a local database with the defaults
    monkeypatch.setenv("SITESIGNAL_ENV", "production")
    with pytest.raises(ConfigurationError, match="still has a built-in local demo password"):
        db.init_db()


def test_an_existing_database_with_real_passwords_starts_when_deployed(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "d.db")
    for k, v in STRONG.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("SITESIGNAL_ENV", "production")
    db.init_db()
    db.init_db()                                                  # second start: users exist, none uses a default


def test_inactive_sales_account_cannot_sign_in_on_a_deployed_service(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "d.db")
    for k, v in STRONG.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("DEMO_SALES_PASSWORD", raising=False)
    monkeypatch.setenv("SITESIGNAL_ENV", "production")
    with TestClient(app) as client:
        for pw in list(LOCAL_DEMO_PASSWORDS.values()) + ["", "anything-at-all"]:
            r = client.post("/api/login", json={"username": "sales", "password": pw or "xxxxxx"})
            assert r.status_code == 401
        assert client.post("/api/login", json={"username": "manager", "password": "Manager@123"}).status_code == 401
        ok = client.post("/api/login", json={"username": "manager", "password": STRONG["DEMO_MANAGER_PASSWORD"]})
        assert ok.status_code == 200


def test_the_app_refuses_to_start_when_deployed_without_passwords(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "d.db")
    for k in ("DEMO_MANAGER_PASSWORD", "DEMO_TECHNICIAN_PASSWORD", "DEMO_SALES_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(ConfigurationError):
        with TestClient(app):
            pass


# ------------------------------------------------------------------ nothing public carries a credential

def test_served_and_documented_files_do_not_publish_demo_passwords():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    files = [*root.glob("README.md"), *root.glob("docs/*.md"), *root.glob("frontend/*"), root / "render.yaml", root / ".env.example"]
    leaks = [f"{f.relative_to(root)}: {pw}" for f in files if f.is_file()
             for pw in LOCAL_DEMO_PASSWORDS.values() if pw in f.read_text(encoding="utf-8")]
    assert leaks == []


def test_render_blueprint_declares_the_secrets_as_unsynced_and_marks_the_service_deployed():
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / "render.yaml").read_text(encoding="utf-8")
    for name in ("DEMO_MANAGER_PASSWORD", "DEMO_TECHNICIAN_PASSWORD", "DEMO_SALES_PASSWORD", "GEMINI_API_KEY"):
        block = text.split(f"key: {name}", 1)[1].split("- key:", 1)[0]
        assert "sync: false" in block and "value:" not in block, name
    assert "SITESIGNAL_ENV" in text and "production" in text
