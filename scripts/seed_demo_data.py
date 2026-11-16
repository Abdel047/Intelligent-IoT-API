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


def seed(session, end):
    # Én atomisk transaktion, og ingen dubletter ved gentaget kørsel.
    if session.scalar(select(Reading.id).where(Reading.device_id.in_(DEVICES)).limit(1)):
        return 0, 0
    count = alarms = 0
    for device, speed, at in samples(end):
        anomalous = speed > 25
        row = Reading(device_id=device, wind_speed=speed, anomaly_detected=anomalous, created_at=at)
        session.add(row)
        session.flush()
        session.add(DomainEvent(event_type="SensorValueReceived", reading_id=row.id, device_id=device,
                               payload={"device_id": device, "wind_speed": speed, "source": "simulated_demo"}, created_at=at))
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
    args = parser.parse_args()
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    end -= timedelta(minutes=end.minute % 15)
    if not args.apply:
        print("Forhåndsvisning: 579 simulerede målinger over 48 timer. Brug --apply for at gemme.")
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
            count, alarms = seed(session, end)
        print(f"Gemt: {count} simulerede målinger og {alarms} alarmer. Eksisterende data er bevaret.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
