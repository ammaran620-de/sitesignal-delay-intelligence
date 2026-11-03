from fastapi.testclient import TestClient

from app import db
from app.main import app


def test_manager_can_read_project_and_run_recovery_but_sales_is_denied(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "sitesignal_api_test.db")
    with TestClient(app) as client:
        manager_login = client.post("/api/login", json={"username": "manager", "password": "Manager@123"})
        assert manager_login.status_code == 200
        manager_headers = {"Authorization": f"Bearer {manager_login.json()['access_token']}"}

        overview = client.get("/api/construction/overview", headers=manager_headers)
        assert overview.status_code == 200
        assert overview.json()["metrics"]["completion_delay_days"] == 2

        recovery = client.post("/api/construction/recovery/REC-001", headers=manager_headers)
        assert recovery.status_code == 200
        assert recovery.json()["simulation"]["days_recovered_vs_delayed_schedule"] == 1

        technician_login = client.post("/api/login", json={"username": "technician", "password": "Tech@123"})
        assert technician_login.status_code == 200
        technician_headers = {"Authorization": f"Bearer {technician_login.json()['access_token']}"}
        technician_overview = client.get("/api/construction/overview", headers=technician_headers)
        assert technician_overview.status_code == 200
        technician_recovery = client.post("/api/construction/recovery/REC-001", headers=technician_headers)
        assert technician_recovery.status_code == 403

        sales_login = client.post("/api/login", json={"username": "sales", "password": "Sales@123"})
        assert sales_login.status_code == 200
        sales_headers = {"Authorization": f"Bearer {sales_login.json()['access_token']}"}
        denied = client.get("/api/construction/overview", headers=sales_headers)
        assert denied.status_code == 403
