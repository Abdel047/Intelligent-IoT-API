"""Tilføj tydeligt simulerede tidsserier uden at ændre eksisterende data."""
import argparse
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from database import Reading, DomainEvent, Alarm, make_engine

DEVICES = ("SIM-WIND-01", "SIM-WIND-02", "SIM-WIND-03")


def samples(end):
    """Tre installationer, hvert kvarter i 48 timer; rolige forløb og korte vindstød."""
    for i in range(193):
        at = end - timedelta(minutes=15 * (192 - i))
        for device, offset in zip(DEVICES, (0, 1, 2)):
            baseline = 13 + offset * 1.7 + 3.8 * math.sin(i / 15 + offset * .5)
            variation = 1.1 * math.sin(i / 3.7 + offset)
            gust = (15 if offset == 0 else 8) * math.exp(-((i - 145) / 6) ** 2)
            yield device, round(max(0, baseline + variation + gust), 1), at


AFLEVERING_DEVICES = ("AFLEVERING-01", "AFLEVERING-02")
AFLEVERING_BATCH = "aflevering-7d-v1"


def aflevering_samples(end):
    """150 simulerede observationer inden for syv dage, heraf seks vindstød."""
    span = timedelta(days=7, minutes=-30)
    for i in range(75):
        at = end - span + span * (i / 74)
        for offset, device in enumerate(AFLEVERING_DEVICES):
            speed = round(16 + offset + 4.3 * math.sin(i / 6 + offset * .4)
                          + 1.3 * math.sin(i / 2.1 + offset), 1)
            if i in ((1, 18, 42, 63) if offset == 0 else (25, 52)):
                speed = (28, 31)[offset] + (i % 3)
            yield device, float(speed), at


def seed(session, end, profile="standard", limit=None):
    """Caller owns the transaction. A fixed batch and sample index allow safe resume."""
    existing = set()
    if profile == "aflevering":
        payloads = session.scalars(select(DomainEvent.payload).where(
            DomainEvent.device_id.in_(AFLEVERING_DEVICES),
            DomainEvent.event_type == "SensorValueReceived"))
        for payload in payloads:
            if payload.get("demo_batch") == AFLEVERING_BATCH:
                existing.add(payload["sample_index"])
                end = datetime.fromisoformat(payload["series_end"])
        source = aflevering_samples(end)
    else:
        if session.scalar(select(Reading.id).where(Reading.device_id.in_(DEVICES)).limit(1)):
            return 0, 0
        source = samples(end)
    count = alarms = 0
    for index, (device, speed, at) in enumerate(source):
        if index in existing:
            continue
        if limit is not None and count >= limit:
            break
        metadata = ({"demo_batch": AFLEVERING_BATCH, "sample_index": index,
                     "series_end": end.isoformat()} if profile == "aflevering" else {})
        anomalous = speed > 25
        row = Reading(device_id=device, wind_speed=speed, anomaly_detected=anomalous, created_at=at)
        session.add(row)
        session.flush()
        session.add(DomainEvent(event_type="SensorValueReceived", reading_id=row.id, device_id=device,
                               payload={"device_id": device, "wind_speed": speed, "source": "simulated_demo", **metadata}, created_at=at))
        if anomalous:
            session.add(DomainEvent(event_type="AnomalyDetected", reading_id=row.id, device_id=device,
                                   payload={"wind_speed": speed, "threshold": 25, "rule": "wind_speed > 25"}, created_at=at))
            alarm = Alarm(reading_id=row.id, device_id=device, message="For høj vindhastighed!", status="active", created_at=at)
            session.add(alarm)
            session.flush()
            session.add(DomainEvent(event_type="AlarmCreated", reading_id=row.id, alarm_id=alarm.id,
                                   device_id=device, payload={"status": "active"}, created_at=at))
            alarms += 1
        count += 1
    return count, alarms


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Gem de simulerede målinger i den eksisterende MySQL-database")
    parser.add_argument("--profile", choices=("standard", "aflevering"), default="standard")
    parser.add_argument("--limit", type=int, help="Tilføj højst dette antal nye målinger (pilotkørsel)")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit skal være mindst 1")
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    end -= timedelta(minutes=end.minute % 15)
    if not args.apply:
        print("Forhåndsvisning: " + ("150 simulerede målinger over 7 dage til AFLEVERING-01/02." if args.profile == "aflevering" else "579 simulerede målinger over 48 timer.") + " Brug --apply for at gemme.")
        return
    values = {}
    for line in (Path(__file__).resolve().parents[1] / ".env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    url = URL.create("mysql+pymysql", username=values["MYSQL_USER"], password=values["MYSQL_PASSWORD"],
                     host="127.0.0.1", port=int(values.get("MYSQL_PUBLISHED_PORT", "3306")),
                     database=values.get("MYSQL_DATABASE", "intelligent_iot"), query={"charset": "utf8mb4"})
    engine = make_engine(url)
    try:
        with Session(engine) as session, session.begin():
            # MySQL advisory lock serializes concurrent runs without schema changes.
            from sqlalchemy import text
            if session.scalar(text("SELECT GET_LOCK('iot_demo_seed', 10)")) != 1:
                raise RuntimeError("Et andet demoscript kører. Prøv igen senere.")
            count, alarms = seed(session, end, args.profile, args.limit)
        print(f"Gemt: {count} simulerede målinger og {alarms} alarmer. Eksisterende data er bevaret.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
