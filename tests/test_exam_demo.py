"""Den delbare Postman-collections requests mod en isoleret FastAPI-testdatabase."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from main import create_app


def test_postman_examples_and_swagger_match_exam_flow(tmp_path, monkeypatch):
    key = "isolated-exam-test-api-key-1234567890123456"
    monkeypatch.setenv("API_KEY", key)
    collection = json.loads((Path(__file__).resolve().parents[1] / "postman" /
                             "Intelligent-IoT.postman_collection.json").read_text(encoding="utf-8"))
    assert next(v["value"] for v in collection["variable"] if v["key"] == "api_key") == ""
    posts = [item for item in collection["item"] if item["request"]["method"] == "POST"]
    with TestClient(create_app("sqlite:///" + (tmp_path / "exam.db").as_posix()),
                    headers={"X-API-Key": key}) as client:
        readings = []
        for item in posts:
            body = json.loads(item["request"]["body"]["raw"])
            response = client.post("/readings", json=body)
            assert response.status_code == (422 if body["wind_speed"] < 0 else 201)
            if response.status_code == 201:
                readings.append(response.json())
        assert [(r["device_id"], r["wind_speed"], r["anomaly_detected"]) for r in readings] == [
            ("VINDMOELLE-01", 20, False), ("VINDMOELLE-02", 30, True)]
        alarms = client.get("/alarms").json()
        assert len(alarms) == 1 and alarms[0]["reading_id"] == readings[1]["id"]
        assert client.patch(f"/alarms/{alarms[0]['id']}/acknowledge").json()["status"] == "acknowledged"
        events = client.get("/events").json()
        assert [e["event_type"] for e in events if e["reading_id"] == readings[0]["id"]] == ["SensorValueReceived"]
        assert [e["event_type"] for e in events if e["reading_id"] == readings[1]["id"]] == [
            "SensorValueReceived", "AnomalyDetected", "AlarmCreated", "AlarmAcknowledged"]
        schema = client.get("/openapi.json").json()
        assert schema["components"]["schemas"]["SensorReading"]["properties"]["device_id"]["examples"] == [
            "VINDMOELLE-01", "VINDMOELLE-02"]
