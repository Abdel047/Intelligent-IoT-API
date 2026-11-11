"""Databaseopsætning og tabeller. Tidspunkter gemmes som UTC."""
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DEFAULT_DATABASE_URL = "sqlite:///" + (Path(__file__).resolve().parent / "iot-dev.db").as_posix()


# MySQL gemmer UTC uden tidszone; bevar mikrosekunder ligesom i SQLite.
UTC_DATETIME = DateTime(timezone=True).with_variant(DATETIME(fsp=6), "mysql")


def configured_database_url():
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    if os.getenv("MYSQL_HOST"):
        return URL.create(
            "mysql+pymysql", username=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"], host=os.environ["MYSQL_HOST"],
            port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.getenv("MYSQL_DATABASE", "intelligent_iot"),
            query={"charset": "utf8mb4"},
        )
    return DEFAULT_DATABASE_URL


def utc_now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Reading(Base):
    __tablename__ = "sensor_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(100), index=True)
    wind_speed: Mapped[float] = mapped_column(Float)
    anomaly_detected: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(UTC_DATETIME, default=utc_now)


class Alarm(Base):
    __tablename__ = "alarms"
    id: Mapped[int] = mapped_column(primary_key=True)
    reading_id: Mapped[int] = mapped_column(ForeignKey("sensor_readings.id"), unique=True)
    device_id: Mapped[str] = mapped_column(String(100), index=True)
    message: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(UTC_DATETIME, default=utc_now)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME, nullable=True)


class DomainEvent(Base):
    __tablename__ = "domain_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    reading_id: Mapped[int] = mapped_column(ForeignKey("sensor_readings.id"), index=True)
    alarm_id: Mapped[int | None] = mapped_column(ForeignKey("alarms.id"), nullable=True)
    device_id: Mapped[str] = mapped_column(String(100), index=True)
    # Bevar API-feltet payload; den fysiske SQL-kolonne hedder event_data.
    payload: Mapped[dict] = mapped_column("event_data", JSON)
    created_at: Mapped[datetime] = mapped_column(UTC_DATETIME, default=utc_now)


def make_engine(url):
    is_sqlite = str(url).startswith("sqlite")
    engine = create_engine(url, pool_pre_ping=True, hide_parameters=True,
                           connect_args={"check_same_thread": False, "timeout": 15} if is_sqlite
                           else {"connect_timeout": 10})
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine
