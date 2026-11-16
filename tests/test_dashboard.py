import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from main import create_app

TEST_PASSWORD = "dashboard-test-password-123456"
TEST_KEY = "dashboard-api-test-key-12345678901234567890"


@pytest.fixture
def dashboard(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", TEST_KEY)
    monkeypatch.setenv("DASHBOARD_PASSWORD", TEST_PASSWORD)
    with TestClient(create_app("sqlite:///" + (tmp_path / "dashboard-test.db").as_posix())) as client:
        yield client


def sign_in(client):
    response = client.post("/dashboard/login", json={"password": TEST_PASSWORD})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_shell_and_assets_do_not_expose_secrets(dashboard):
    for path in ["/dashboard", "/dashboard/assets/style.css", "/dashboard/assets/app.js"]:
        response = dashboard.get(path)
        assert response.status_code == 200
        assert TEST_KEY not in response.text
        assert TEST_PASSWORD not in response.text
        assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in dashboard.get("/dashboard").headers["content-security-policy"]


def test_private_data_requires_session_and_original_api_still_requires_key(dashboard):
    assert dashboard.get("/dashboard/data").status_code == 401
    assert dashboard.post("/dashboard/readings", json={"device_id": "WT", "wind_speed": 20}).status_code == 401
    sign_in(dashboard)
    assert dashboard.get("/readings").status_code == 401
    data = dashboard.get("/dashboard/data")
    assert data.status_code == 200
    assert data.json()["docker"] == {"api": "unavailable", "mysql": "unavailable", "gateway": "unavailable"}
    assert data.json()["database_status"] == "connected"
    assert TEST_KEY not in data.text and TEST_PASSWORD not in data.text


def test_password_and_login_rate_limit(dashboard):
    for _ in range(5):
        assert dashboard.post("/dashboard/login", json={"password": "wrong"}).status_code == 401
    assert dashboard.post("/dashboard/login", json={"password": TEST_PASSWORD}).status_code == 429
    assert dashboard.get("/dashboard/data").status_code == 401


def test_cross_origin_login_and_writes_are_blocked(dashboard):
    assert dashboard.post("/dashboard/login", json={"password": TEST_PASSWORD}, headers={"Origin": "https://other.example"}).status_code == 403
    headers = sign_in(dashboard)
    headers["Origin"] = "https://other.example"
    assert dashboard.post("/dashboard/readings", json={"device_id": "WT", "wind_speed": 30}, headers=headers).status_code == 403
    assert dashboard.get("/dashboard/data").json()["readings"] == []


def test_session_cookie_and_logout_revoke_access(dashboard):
    response = dashboard.post("/dashboard/login", json={"password": TEST_PASSWORD})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/dashboard" in cookie
    token = dashboard.cookies.get("iot_dashboard_session")
    csrf = {"X-CSRF-Token": response.json()["csrf_token"]}
    assert dashboard.post("/dashboard/logout").status_code == 403
    assert dashboard.post("/dashboard/logout", headers=csrf).status_code == 200
    assert dashboard.get("/dashboard/data", headers={"Cookie": "iot_dashboard_session=" + token}).status_code == 401


def test_mutations_use_existing_event_flow_and_require_csrf(dashboard):
    headers = sign_in(dashboard)
    normal = {"device_id": "DASH-20", "wind_speed": 20}
    assert dashboard.post("/dashboard/readings", json=normal).status_code == 403
    assert dashboard.post("/dashboard/readings", json=normal, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    response = dashboard.post("/dashboard/readings", json=normal, headers=headers)
    assert response.status_code == 201 and response.json()["anomaly_detected"] is False
    assert dashboard.post("/dashboard/readings", json={"device_id": "DASH-30", "wind_speed": 30}, headers=headers).status_code == 201
    data = dashboard.get("/dashboard/data").json()
    assert len(data["readings"]) == 2
    assert len(data["events"]) == 4
    assert len(data["alarms"]) == 1
    reading_id = data["alarms"][0]["reading_id"]
    assert [e["event_type"] for e in data["events"] if e["reading_id"] == reading_id] == ["SensorValueReceived", "AnomalyDetected", "AlarmCreated"]
    alarm_id = data["alarms"][0]["id"]
    assert dashboard.patch(f"/dashboard/alarms/{alarm_id}/acknowledge").status_code == 403
    assert dashboard.patch(f"/dashboard/alarms/{alarm_id}/acknowledge", headers=headers).status_code == 200
    data = dashboard.get("/dashboard/data").json()
    assert data["alarms"][0]["status"] == "acknowledged"
    assert data["events"][-1]["event_type"] == "AlarmAcknowledged"
    assert dashboard.post("/dashboard/readings", json={"device_id": "", "wind_speed": -1}, headers=headers).status_code == 422
    assert len(dashboard.get("/dashboard/data").json()["readings"]) == 2


def test_dashboard_is_disabled_without_own_password(dashboard, monkeypatch):
    monkeypatch.delenv("DASHBOARD_PASSWORD")
    assert dashboard.post("/dashboard/login", json={"password": TEST_PASSWORD}).status_code == 503
    assert dashboard.get("/dashboard/data").status_code == 401


def test_disconnected_database_is_not_shown_as_healthy(dashboard, monkeypatch):
    sign_in(dashboard)
    def offline():
        raise OperationalError("SELECT 1", {}, Exception("private details"))
    monkeypatch.setattr(dashboard.app.state.engine, "connect", offline)
    response = dashboard.get("/dashboard/data")
    assert response.status_code == 200
    assert response.json()["database_status"] == "disconnected"
    assert "private details" not in response.text


def test_https_cookie_is_secure(dashboard):
    response = dashboard.post("/dashboard/login", json={"password": TEST_PASSWORD}, headers={"X-Forwarded-Proto": "https"})
    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()


def test_new_login_revokes_previous_cookie(dashboard):
    sign_in(dashboard)
    old_token = dashboard.cookies.get("iot_dashboard_session")
    sign_in(dashboard)
    assert dashboard.get("/dashboard/session").status_code == 200
    assert dashboard.get("/dashboard/session", headers={"Cookie": "iot_dashboard_session=" + old_token}).status_code == 401
