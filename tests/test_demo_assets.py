from fastapi.testclient import TestClient

from app.main import app


def test_dashboard_opens_with_guided_demo_as_primary_entry_point():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert 'id="demoPanel"' in response.text
    assert 'data-panel="demo"' in response.text
    assert 'id="runGuidedDemoBtn"' in response.text
    assert 'id="runGeminiDemoBtn"' in response.text


def test_demo_script_is_served_from_static_assets():
    with TestClient(app) as client:
        response = client.get("/static/demo_script.md")
    assert response.status_code == 200
    assert "90-second recruiter demo script" in response.text
    assert "synthetic" in response.text.lower()
