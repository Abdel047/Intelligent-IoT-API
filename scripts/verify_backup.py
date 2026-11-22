"""Gendan SQL-backup i en isoleret, midlertidig MySQL uden porte eller eksisterende volumes."""
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import secrets
import subprocess
import struct
import time

from scripts.rename_devices import TABLES, check_relations


def verify_backup(path, expected, reproduce_old_probe=False):
    name = "iot-backup-check-" + secrets.token_hex(6)
    password = secrets.token_urlsafe(32)
    env = {**os.environ, "MYSQL_ROOT_PASSWORD": password}
    log_path = path.with_suffix("." + datetime.now(timezone.utc).strftime("%H%M%S%f") + ".restore-check.log")
    log = []
    started = False

    def record(label, result):
        log.append(label + "\n" + (result.stdout + result.stderr).decode(errors="replace").replace(password, "[REDACTED]"))

    def mysql(sql):
        return subprocess.run(["docker", "exec", "-i", name, "sh", "-c",
                               'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -u root -N -B --raw restore_check'],
                              input=sql, capture_output=True, timeout=30)

    try:
        result = subprocess.run(["docker", "run", "-d", "--name", name, "--tmpfs", "/var/lib/mysql",
                                 "-e", "MYSQL_ROOT_PASSWORD", "-e", "MYSQL_DATABASE=restore_check", "mysql:8.4"],
                                env=env, capture_output=True, timeout=60)
        if result.returncode:
            record("Containerstart fejlede", result)
            raise RuntimeError("Testcontainer kunne ikke startes; se lokal restore-log.")
        started = True
        sql = gzip.decompress(path.read_bytes())
        if reproduce_old_probe:
            for _ in range(90):
                ping = subprocess.run(["docker", "exec", name, "sh", "-c",
                                       'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqladmin ping -u root --silent'], capture_output=True)
                if ping.returncode == 0:
                    record("Gammel readiness-probe returnerede 0", ping)
                    old = subprocess.run(["docker", "exec", "-i", name, "sh", "-c",
                                          'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -u root restore_check'],
                                         input=sql, capture_output=True)
                    record("Gammel restore-metode: exit " + str(old.returncode), old)
                    print("Gammel restore-probe:", old.returncode, old.stderr.decode(errors="replace").replace(password, "[REDACTED]").strip(), flush=True)
                    if old.returncode == 0:
                        raise RuntimeError("Race kunne ikke reproduceres; brug en ny testcontainer før verifikation.")
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Den gamle readiness-probe blev ikke klar.")
        # mysqladmin ping kan returnere succes trods Access denied. Brug i stedet
        # et autentificeret SELECT på TCP i den forventede database efter init.
        for _ in range(120):
            ready = mysql(b"SELECT 1;")
            if ready.returncode == 0 and ready.stdout.strip() == b"1":
                break
            time.sleep(1)
        else:
            record("Autentificeret readiness fejlede", ready)
            raise RuntimeError("Testdatabasen blev ikke klar; se lokal restore-log.")
        result = mysql(sql)
        if result.returncode:
            record("Restore fejlede", result)
            raise RuntimeError("SQL-restore fejlede; se lokal restore-log.")
        restored = {}
        for table in TABLES:
            pairs = ",".join("'" + col.name + "',`" + col.name + "`" for col in table.columns)
            result = mysql(("SELECT JSON_OBJECT(" + pairs + ") FROM `" + table.name + "` ORDER BY id;").encode())
            if result.returncode:
                record("Tabelkontrol fejlede", result)
                raise RuntimeError("Kunne ikke kontrollere gendannede rækker.")
            rows = [json.loads(line) for line in result.stdout.decode().splitlines()]
            for index, row in enumerate(rows):
                for key in ("created_at", "acknowledged_at"):
                    if row.get(key) is not None:
                        row[key] = datetime.fromisoformat(row[key])
                # MySQL JSON_OBJECT viser FLOAT's binære 32-bit værdi med flere
                # decimaler end PyMySQL-protokollen. Sammenlign de præcise lagrede
                # FLOAT32-bits, ikke tekstformatering eller en løs tolerance.
                if table.name == "sensor_readings" and index < len(expected[table.name]):
                    original = expected[table.name][index]["wind_speed"]
                    if struct.pack("!f", row["wind_speed"]) == struct.pack("!f", original):
                        if row["wind_speed"] != original:
                            log.append("FLOAT32-formatering verificeret: " + repr(row["wind_speed"]) + " = " + repr(original) + " i lagrede bits.")
                        row["wind_speed"] = original
            if rows != expected[table.name]:
                raise ValueError("Restore-indhold afviger fra originalen i " + table.name)
            restored[table.name] = rows
            print("RESTORE BESTÅET:", table.name, len(rows), "rækker; alle felter stemmer.", flush=True)
        check_relations(restored)
        log.append("BESTÅET: alle rækker, ID'er, relationer, JSON og tidspunkter verificeret.")
        return {"status": "BESTÅET", "counts": {key: len(rows) for key, rows in restored.items()}, "log": str(log_path)}
    finally:
        if started:
            result = subprocess.run(["docker", "logs", name], capture_output=True)
            record("MySQL-containerlog", result)
        log_path.write_text("\n\n".join(log), encoding="utf-8")
        if started:
            # Kun den nyoprettede testcontainer med tilfældigt navn fjernes.
            subprocess.run(["docker", "rm", "-f", name], check=True, capture_output=True)
