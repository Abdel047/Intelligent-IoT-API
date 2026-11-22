from copy import deepcopy
from datetime import datetime, timezone
import gzip
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from database import Base, Reading, DomainEvent, Alarm
from scripts.rename_devices import backup_database, check_relations, migrate, renamed, rename_json, snapshot
from scripts.seed_demo_data import seed


@pytest.fixture
def engine():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        row = Reading(device_id="AFLEVERING-02", wind_speed=30, anomaly_detected=True)
        untouched = Reading(device_id="SIM-WIND-01", wind_speed=20, anomaly_detected=False)
        session.add_all([row, untouched])
        session.flush()
        alarm = Alarm(reading_id=row.id, device_id=row.device_id, message="For høj vindhastighed!", status="active")
        session.add(alarm)
        session.flush()
        for kind, payload in [("SensorValueReceived", {"device_id": row.device_id, "wind_speed": 30}),
                              ("AnomalyDetected", {"threshold": 25}), ("AlarmCreated", {"status": "active"})]:
            session.add(DomainEvent(device_id=row.device_id, reading_id=row.id,
                                    alarm_id=alarm.id if kind == "AlarmCreated" else None,
                                    event_type=kind, payload=payload))
    yield engine
    engine.dispose()


def test_migration_preserves_everything_except_names_and_is_idempotent(engine):
    with Session(engine) as session:
        before = snapshot(session)
        expected, counts = renamed(before)
        assert counts["domain_events"]["json_payloads"] == 1
        assert snapshot(session) == before  # Forhåndsvisning skriver intet.
    with Session(engine) as session, session.begin():
        migrate(session)
    with Session(engine) as session, session.begin():
        assert snapshot(session) == expected
        counts, first, second = migrate(session)
        assert first == second
        assert all(value["device_names"] == value["json_payloads"] == 0 for value in counts.values())


def test_json_names_nested_and_similar_names_untouched():
    original = {"device_id": "AFLEVERING-01", "nested": ["Sensor: AFLEVERING-02.", None, 25, True],
                "other": "X-AFLEVERING-01 / AFLEVERING-010 / SIM-WIND-01", "batch": "aflevering-7d-v1"}
    before = deepcopy(original)
    updated = rename_json(original)
    assert original == before
    assert updated["device_id"] == "VINDMOELLE-01"
    assert updated["nested"] == ["Sensor: VINDMOELLE-02.", None, 25, True]
    assert updated["other"] == original["other"] and updated["batch"] == original["batch"]


def test_json_key_collision_is_rejected():
    with pytest.raises(ValueError, match="JSON"):
        rename_json({"AFLEVERING-01": 1, "VINDMOELLE-01": 2})


def test_name_collision_aborts(engine):
    with Session(engine) as session, session.begin():
        session.add(Reading(device_id="VINDMOELLE-02", wind_speed=20, anomaly_detected=False))
    with Session(engine) as session:
        before = snapshot(session)
    with pytest.raises(ValueError, match="allerede"), Session(engine) as session, session.begin():
        migrate(session)
    with Session(engine) as session:
        assert snapshot(session) == before


def test_database_change_since_backup_aborts(engine):
    with pytest.raises(ValueError, match="backup"), Session(engine) as session, session.begin():
        migrate(session, expected_before="not-the-original-fingerprint")


def test_migration_failure_rolls_back_all_changes(engine):
    with Session(engine) as session:
        before = snapshot(session)
    def fail(conn, cursor, statement, parameters, context, many):
        if statement.startswith("UPDATE domain_events"):
            raise RuntimeError("simulated failure after first table update")
    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError), Session(engine) as session, session.begin():
            migrate(session)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    with Session(engine) as session:
        assert snapshot(session) == before


def test_relations_reject_wrong_device_or_alarm(engine):
    with Session(engine) as session:
        before = snapshot(session)
    before["domain_events"][0]["device_id"] = "OTHER"
    with pytest.raises(ValueError, match="reading_id"):
        check_relations(before)
    before["domain_events"][0]["device_id"] = "AFLEVERING-02"
    before["domain_events"][-1]["alarm_id"] = 999
    with pytest.raises(ValueError, match="alarmrelation"):
        check_relations(before)


def test_simulation_does_not_duplicate_after_rename(engine):
    from scripts.seed_demo_data import VINDMOELLE_BATCH
    with Session(engine) as session, session.begin():
        migrate(session)
        seed(session, datetime(2026, 11, 22, tzinfo=timezone.utc), "vindmoelle")
        # Simulér det eksisterende datasæt, der først fik gamle navne.
        for model in (Reading, DomainEvent, Alarm):
            for row in session.query(model).filter(model.device_id.like("VINDMOELLE-%")):
                row.device_id = row.device_id.replace("VINDMOELLE-", "AFLEVERING-")
                if model is DomainEvent and row.event_type == "SensorValueReceived":
                    row.payload = {**row.payload, "device_id": row.device_id}
                    if "demo_batch" in row.payload:
                        assert row.payload["demo_batch"] == VINDMOELLE_BATCH
    with Session(engine) as session, session.begin():
        migrate(session)
    with Session(engine) as session, session.begin():
        assert seed(session, datetime(2026, 11, 23, tzinfo=timezone.utc), "vindmoelle") == (0, 0)


def test_backup_compression_and_failure(tmp_path, monkeypatch):
    import scripts.rename_devices as migration
    sql = b"CREATE TABLE sensor_readings (id INT); INSERT INTO sensor_readings VALUES (1);"
    monkeypatch.setattr(migration.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=sql))
    path, digest = backup_database(tmp_path)
    assert gzip.decompress(path.read_bytes()) == sql and len(digest) == 64
    monkeypatch.setattr(migration.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout=b""))
    with pytest.raises(RuntimeError, match="backup"):
        backup_database(tmp_path)


def test_simulation_requires_migration_before_writing_new_names(engine):
    with pytest.raises(ValueError, match="Migrér"), Session(engine) as session, session.begin():
        seed(session, datetime(2026, 11, 22, tzinfo=timezone.utc), "vindmoelle")
