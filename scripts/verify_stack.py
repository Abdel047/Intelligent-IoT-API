"""Integrationstest af den kørende Docker-løsning. Opretter tre DEMO-målinger; sletter intet."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restart", action="store_true", help="Genstart Compose-services og kontrollér persistens")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    values = {}
    for line in (root / ".env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    base = "http://127.0.0.1:" + values.get("API_PORT", "8000")

    def request(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data,
            headers={"X-API-Key": values["API_KEY"], "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.load(response)

    assert request("/health")["status"] == "ok"
    prefix = "DEMO-" + uuid.uuid4().hex[:8]
    readings = []
    for speed in (15, 25, 30):
        result = request("/readings", {"device_id": f"{prefix}-{speed}", "wind_speed": speed})
        assert result["anomaly_detected"] == (speed > 25)
        readings.append(result)
    ids = [reading["id"] for reading in readings]
    url = URL.create("mysql+pymysql", username=values["MYSQL_USER"],
        password=values["MYSQL_PASSWORD"], host="127.0.0.1",
        port=int(values.get("MYSQL_PUBLISHED_PORT", "3306")),
        database=values["MYSQL_DATABASE"], query={"charset": "utf8mb4"})
    engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 10})

    def check_sql():
        with engine.connect() as connection:
            for reading in readings:
                params = {"id": reading["id"]}
                stored = connection.execute(text("SELECT device_id, wind_speed FROM sensor_readings WHERE id=:id"), params).one()
                assert stored.device_id == reading["device_id"]
                events = connection.execute(text("SELECT event_type FROM domain_events WHERE reading_id=:id ORDER BY id"), params).scalars().all()
                expected = ["SensorValueReceived", "AnomalyDetected", "AlarmCreated"] if reading["anomaly_detected"] else ["SensorValueReceived"]
                assert events == expected
                count = connection.execute(text("SELECT COUNT(*) FROM alarms WHERE reading_id=:id"), params).scalar_one()
                assert count == int(reading["anomaly_detected"])

    check_sql()
    print("BESTÅET: 15/25/30 m/s verificeret via API og direkte i MySQL. Måling-ID'er:", ids)
    if args.restart:
        docker = shutil.which("docker")
        if not docker:
            raise RuntimeError("docker skal være i terminalens PATH")
        subprocess.run([docker, "compose", "restart"], cwd=root, check=True)
        deadline = time.monotonic() + 120
        while True:
            try:
                if request("/health")["status"] == "ok":
                    break
            except (OSError, ValueError):
                pass
            if time.monotonic() > deadline:
                raise RuntimeError("Docker-løsningen blev ikke klar efter genstart")
            time.sleep(2)
        engine.dispose()
        check_sql()
        assert set(ids).issubset({r["id"] for r in request("/readings")})
        print("BESTÅET: De samme målinger, events og alarm findes efter Docker-genstart.")
    engine.dispose()


if __name__ == "__main__":
    # Ingen traceback med forbindelsesoplysninger ved fejl.
    try:
        main()
    except Exception as exc:
        print(f"FEJL ({type(exc).__name__}). Kontrollér Docker-status, porte og lokale .env-værdier.")
        raise SystemExit(1)
