"""Opret kun manglende lokale værdier; udskriv aldrig hemmeligheder."""
from pathlib import Path
import secrets

path = Path(__file__).resolve().parents[1] / ".env"
original = path.read_text(encoding="utf-8-sig") if path.exists() else ""
lines = original.splitlines()
existing = {}
for i, line in enumerate(lines):
    if "=" in line and not line.lstrip().startswith("#"):
        key, value = line.split("=", 1)
        existing[key.strip()] = (i, value.strip())
defaults = {
    "API_KEY": secrets.token_urlsafe(32),
    "MYSQL_DATABASE": "intelligent_iot", "MYSQL_USER": "iot_user",
    "MYSQL_PASSWORD": secrets.token_hex(24),
    "MYSQL_ROOT_PASSWORD": secrets.token_hex(24),
    "MYSQL_PUBLISHED_PORT": "3306", "API_PORT": "8000",
}
for key, value in defaults.items():
    if key not in existing:
        lines.append(f"{key}={value}")
    elif not existing[key][1]:
        lines[existing[key][0]] = f"{key}={value}"
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("Lokal .env klar. Eksisterende udfyldte værdier er bevaret. Ingen hemmeligheder vist.")
