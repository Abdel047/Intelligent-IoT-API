import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from main import create_app


TEST_API_KEY = "test-only-key-not-for-production-123456789"


@pytest.fixture(autouse=True)
def configure_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", TEST_API_KEY)


@pytest.fixture
def database_url(tmp_path):
    return "sqlite:///" + (tmp_path / "test.db").as_posix()


@pytest.fixture
def client(database_url):
    with TestClient(create_app(database_url), headers={"X-API-Key": TEST_API_KEY}) as client:
        yield client


@pytest.mark.parametrize("speed,anomaly", [(0, False), (20, False), (25, False), (30, True), (80, True)])
def test_reading_and_events(client, speed, anomaly):
    response = client.post("/readings", json={"device_id": "WT-01", "wind_speed": speed})
    assert response.status_code == 201
    reading = response.json()
    assert reading["anomaly_detected"] is anomaly
    assert reading["created_at"].endswith("+00:00")
    assert client.get("/readings").json() == [reading]
    events = client.get("/events").json()
    assert [e["event_type"] for e in events] == (["SensorValueReceived", "AnomalyDetected", "AlarmCreated"] if anomaly else ["SensorValueReceived"])
    assert all(e["reading_id"] == reading["id"] for e in events)
    alarms = client.get("/alarms").json()
    assert len(alarms) == int(anomaly)
    if anomaly:
        assert alarms[0]["reading_id"] == reading["id"]
        assert events[-1]["alarm_id"] == alarms[0]["id"]


@pytest.mark.parametrize("payload", [
    {"device_id": "WT-01", "wind_speed": -1},
    {"device_id": "WT-01", "wind_speed": 81},
    {"device_id": "WT-01", "wind_speed": "NaN"},
    {"device_id": "WT-01", "wind_speed": "Infinity"},
    {"device_id": "WT-01", "wind_speed": "abc"},
    {"device_id": "", "wind_speed": 20},
    {"device_id": "   ", "wind_speed": 20},
    {"device_id": "x" * 101, "wind_speed": 20},
    {"wind_speed": 20},
])
def test_invalid_input(client, payload):
    assert client.post("/readings", json=payload).status_code == 422
    assert client.get("/readings").json() == []
    assert client.get("/events").json() == []
    assert client.get("/alarms").json() == []


def test_acknowledgement(client):
    client.post("/readings", json={"device_id": "WT-01", "wind_speed": 30})
    alarm_id = client.get("/alarms").json()[0]["id"]
    url = f"/alarms/{alarm_id}/acknowledge"
    result = client.patch(url)
    assert result.status_code == 200
    assert result.json()["status"] == "acknowledged"
    assert result.json()["acknowledged_at"].endswith("+00:00")
    assert client.patch(url).json() == result.json()
    assert client.get("/alarms").json() == []
    assert len(client.get("/alarms?status=acknowledged").json()) == 1
    assert len(client.get("/alarms?status=all").json()) == 1
    assert [e["event_type"] for e in client.get("/events").json()].count("AlarmAcknowledged") == 1
    assert client.patch("/alarms/999999/acknowledge").status_code == 404
    assert client.get("/alarms?status=invalid").status_code == 422


def test_persistence_after_restart(database_url):
    with TestClient(create_app(database_url), headers={"X-API-Key": TEST_API_KEY}) as first:
        first.post("/readings", json={"device_id": "WT-01", "wind_speed": 30})
        alarm_id = first.get("/alarms").json()[0]["id"]
        first.patch(f"/alarms/{alarm_id}/acknowledge")
        before = [first.get(path).json() for path in ["/readings", "/events", "/alarms?status=all"]]
    with TestClient(create_app(database_url), headers={"X-API-Key": TEST_API_KEY}) as second:
        after = [second.get(path).json() for path in ["/readings", "/events", "/alarms?status=all"]]
    assert before == after
    assert len(after[0]) == 1
    assert len(after[1]) == 4
    assert after[2][0]["status"] == "acknowledged"


def test_transaction_rolls_back(client):
    def fail_event_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO domain_events"):
            import sqlite3
            raise OperationalError(statement, parameters, sqlite3.OperationalError("simulated failure"))
    # Simulér en databasefejl under lagring af events.
    event.listen(client.app.state.engine, "before_cursor_execute", fail_event_insert)
    try:
        response = client.post("/readings", json={"device_id": "WT-01", "wind_speed": 30})
        assert response.status_code == 503
        assert "simulated failure" not in response.text
    finally:
        event.remove(client.app.state.engine, "before_cursor_execute", fail_event_insert)
    assert client.get("/readings").json() == []
    assert client.get("/events").json() == []
    assert client.get("/alarms").json() == []


@pytest.mark.parametrize("method,path", [
    ("GET", "/readings"), ("GET", "/events"), ("GET", "/alarms"),
    ("POST", "/readings"), ("PATCH", "/alarms/1/acknowledge"),
])
@pytest.mark.parametrize("key", [None, "incorrect-key", ""])
def test_unauthorized_requests(client, method, path, key):
    client.headers.pop("X-API-Key")
    headers = {} if key is None else {"X-API-Key": key}
    response = client.request(method, path, headers=headers,
                              json={"device_id": "WT-01", "wind_speed": 30} if method == "POST" else None)
    assert response.status_code == 401
    assert TEST_API_KEY not in response.text
    client.headers["X-API-Key"] = TEST_API_KEY
    assert client.get("/readings").json() == []
    assert client.get("/events").json() == []
    assert client.get("/alarms?status=all").json() == []


@pytest.mark.parametrize("key", [None, "", "short", " " * 40])
def test_missing_configuration_fails_startup(database_url, monkeypatch, key):
    if key is None:
        monkeypatch.delenv("API_KEY", raising=False)
    else:
        monkeypatch.setenv("API_KEY", key)
    with pytest.raises(RuntimeError, match="API_KEY"):
        with TestClient(create_app(database_url)):
            pass


def test_public_home_and_security_documentation(client):
    client.headers.pop("X-API-Key")
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/readings"]["post"]["security"] == [{"APIKeyHeader": []}]
    assert "security" not in schema["paths"]["/"]["get"]


def test_health_checks_database(client, monkeypatch):
    assert client.get("/health").json() == {"status": "ok", "database": "connected"}
    def unavailable():
        raise OperationalError("SELECT 1", {}, Exception("private connection detail"))
    monkeypatch.setattr(client.app.state.engine, "connect", unavailable)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy"}
    assert "private" not in response.text


def test_event_device_id_and_payload(client):
    response = client.post("/readings", json={"device_id": "WT-03", "wind_speed": 30})
    assert response.status_code == 201
    for record in client.get("/events").json():
        assert record["device_id"] == "WT-03"
        assert isinstance(record["payload"], dict)


def test_mysql_url_handles_special_password_characters(monkeypatch):
    from database import configured_database_url
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MYSQL_HOST", "mysql")
    monkeypatch.setenv("MYSQL_USER", "iot_user")
    monkeypatch.setenv("MYSQL_PASSWORD", "test-only-@:/?#pass")
    monkeypatch.setenv("MYSQL_DATABASE", "intelligent_iot")
    url = configured_database_url()
    assert url.drivername == "mysql+pymysql"
    assert url.host == "mysql"
    assert url.password == "test-only-@:/?#pass"
    assert url.database == "intelligent_iot"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///explicit-test.db")
    assert configured_database_url() == "sqlite:///explicit-test.db"
