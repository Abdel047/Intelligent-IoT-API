"""Kontrollér navnemigrering; --apply kræver særskilt godkendelse og tager backup."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select, update
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from database import Reading, DomainEvent, Alarm, make_engine

ROOT = Path(__file__).resolve().parents[1]
NAMES = {"AFLEVERING-01": "VINDMOELLE-01", "AFLEVERING-02": "VINDMOELLE-02"}
TABLES = (Reading.__table__, DomainEvent.__table__, Alarm.__table__)
PATTERN = re.compile(r"(?<![\w-])(?:" + "|".join(map(re.escape, NAMES)) + r")(?![\w-])")


def rename_json(value):
    """Erstat kun hele navne; bevar JSON-typer og andre sensornavne."""
    if isinstance(value, str):
        return PATTERN.sub(lambda match: NAMES[match.group()], value)
    if isinstance(value, list):
        return [rename_json(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            new_key = rename_json(key)
            if new_key in result:
                raise ValueError("Navneændring ville overskrive en JSON-nøgle.")
            result[new_key] = rename_json(item)
        return result
    return value


def snapshot(session, lock=False):
    result = {}
    for table in TABLES:
        query = select(table).order_by(table.c.id)
        if lock:
            query = query.with_for_update()
        result[table.name] = [dict(row) for row in session.execute(query).mappings()]
    return result


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def renamed(data):
    result = deepcopy(data)
    counts = {}
    for table, rows in result.items():
        names = payloads = 0
        for row in rows:
            if row["device_id"] in NAMES:
                row["device_id"] = NAMES[row["device_id"]]
                names += 1
            if table == "domain_events":
                changed = rename_json(row["event_data"])
                if changed != row["event_data"]:
                    row["event_data"] = changed
                    payloads += 1
        counts[table] = {"rows": len(rows), "device_names": names, "json_payloads": payloads}
    return result, counts


def check_relations(data):
    readings = {row["id"]: row for row in data["sensor_readings"]}
    alarms = {row["id"]: row for row in data["alarms"]}
    for row in data["alarms"] + data["domain_events"]:
        if row["reading_id"] not in readings or row["device_id"] != readings[row["reading_id"]]["device_id"]:
            raise ValueError("Uoverensstemmelse mellem reading_id og device_id; undersøg før migrering.")
    for row in data["domain_events"]:
        if row["alarm_id"] is not None:
            alarm = alarms.get(row["alarm_id"])
            if alarm is None or alarm["reading_id"] != row["reading_id"]:
                raise ValueError("Uoverensstemmelse i alarmrelation; undersøg før migrering.")


def migrate(session, expected_before=None):
    """Ingen commit her: kaldende transaktion ruller alle ændringer tilbage ved fejl."""
    before = snapshot(session, lock=True)
    if expected_before is not None and fingerprint(before) != expected_before:
        raise ValueError("Databasen ændrede sig under backup. Tag ny backup og prøv igen.")
    present = {row["device_id"] for row in before["sensor_readings"]}
    if any(old in present and new in present for old, new in NAMES.items()):
        raise ValueError("Både gammelt og nyt navn findes allerede. Afklar før sammenlægning.")
    check_relations(before)
    expected, counts = renamed(before)
    for table in TABLES:
        for old, new in zip(before[table.name], expected[table.name]):
            values = {key: value for key, value in new.items() if value != old[key]}
            if values:
                session.execute(update(table).where(table.c.id == old["id"]).values(**values))
    after = snapshot(session)
    # Samme IDs, antal, tidspunkter, relationer og data undtagen de godkendte navne.
    if after != expected:
        raise ValueError("Efterkontrol fejlede; alle ændringer rulles tilbage.")
    check_relations(after)
    return counts, fingerprint(before), fingerprint(after)


def local_engine():
    values = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return make_engine(URL.create("mysql+pymysql", username=values["MYSQL_USER"], password=values["MYSQL_PASSWORD"],
                                  host="127.0.0.1", port=int(values.get("MYSQL_PUBLISHED_PORT", "3306")),
                                  database=values.get("MYSQL_DATABASE", "intelligent_iot"), query={"charset": "utf8mb4"}))


def backup_database(directory):
    """Fuld SQL-backup uden passwords i argumenter/output; fejl afbryder migreringen."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("before-device-rename-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".sql.gz")
    command = ['docker', 'compose', 'exec', '-T', 'mysql', 'sh', '-c',
               'MYSQL_PWD="$MYSQL_PASSWORD" exec mysqldump -u "$MYSQL_USER" --single-transaction --no-tablespaces --set-gtid-purged=OFF "$MYSQL_DATABASE"']
    result = subprocess.run(command, cwd=ROOT, capture_output=True)
    if result.returncode or b"CREATE TABLE" not in result.stdout or b"INSERT INTO" not in result.stdout:
        raise RuntimeError("MySQL-backup fejlede. Ingen migrering udført.")
    with path.open("xb") as target:
        target.write(gzip.compress(result.stdout))
    if gzip.decompress(path.read_bytes()) != result.stdout:
        raise RuntimeError("Backup kunne ikke verificeres. Ingen migrering udført.")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Efter godkendelse: tag backup og udfør migreringen")
    args = parser.parse_args()
    engine = local_engine()
    try:
        with Session(engine) as session:
            before = snapshot(session)
            check_relations(before)
            _, counts = renamed(before)
        if not args.apply:
            print(json.dumps({"mode": "READ_ONLY", "changes": counts, "before_sha256": fingerprint(before)}, indent=2))
            return
        # Brugeren skal godkende først. Stop API'et under backup og migrering;
        # fingerprint-kontrollen afbryder, hvis andre klienter ændrer data under backup.
        directory = Path.home() / ".codex" / "backups" / "Intelligent-IoT-API"
        backup, digest = backup_database(directory)
        from scripts.verify_backup import verify_backup
        restore = verify_backup(backup, before)
        with Session(engine) as session, session.begin():
            counts, original, after = migrate(session, fingerprint(before))
        receipt = {"backup": str(backup), "backup_sha256": digest, "before_sha256": original,
                   "after_sha256": after, "restore_verification": restore,
                   "changes": counts, "status": "COMMITTED"}
        backup.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(json.dumps(receipt, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Ingen forbindelsesstrenge, SQL-parametre eller rå subprocess-output.
        print("FEJL:", type(error).__name__, "Migrering ikke bekræftet; kontrollér backup og databasen før gentagelse.")
        raise SystemExit(1)
