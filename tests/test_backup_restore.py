from datetime import datetime
import gzip
import json
from types import SimpleNamespace

from scripts.verify_backup import verify_backup


def test_restore_waits_for_authenticated_database_and_preserves_float_and_utf8(tmp_path, monkeypatch):
    import scripts.verify_backup as module
    at = datetime(2026, 11, 22, 12)
    expected = {
        "sensor_readings": [{"id": 1, "device_id": "VINDMOELLE-01", "wind_speed": 30.1,
                             "anomaly_detected": True, "created_at": at}],
        "domain_events": [{"id": 1, "device_id": "VINDMOELLE-01", "reading_id": 1, "alarm_id": 1,
                           "event_type": "AlarmCreated", "event_data": {"status": "active"}, "created_at": at}],
        "alarms": [{"id": 1, "device_id": "VINDMOELLE-01", "reading_id": 1, "message": "For høj vindhastighed!",
                    "status": "active", "created_at": at, "acknowledged_at": None}],
    }
    backup = tmp_path / "backup.sql.gz"
    backup.write_bytes(gzip.compress(b"CREATE TABLE example (id INT);"))
    probes = []
    def fake_run(args, **kwargs):
        if args[:2] == ["docker", "exec"]:
            assert "--default-character-set=utf8mb4" in args[-1]
            sql = kwargs["input"]
            if sql == b"SELECT 1;":
                probes.append(1)
                return SimpleNamespace(returncode=1 if len(probes) == 1 else 0,
                                       stdout=b"" if len(probes) == 1 else b"1\n", stderr=b"")
            if sql.startswith(b"CREATE"):
                assert len(probes) == 2
                return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
            table = next(name for name in expected if ("FROM `" + name + "`").encode() in sql)
            rows = [dict(row) for row in expected[table]]
            if table == "sensor_readings":
                rows[0]["wind_speed"] = 30.100000381469727
            encoded = "\n".join(json.dumps(row, default=str, ensure_ascii=False) for row in rows).encode()
            return SimpleNamespace(returncode=0, stdout=encoded, stderr=b"")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    result = verify_backup(backup, expected)
    assert result["status"] == "BESTÅET"
    assert result["counts"] == {name: 1 for name in expected}
