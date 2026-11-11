import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import select, update, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import Alarm, Base, configured_database_url, DomainEvent, Reading, make_engine, utc_now

logger = logging.getLogger("uvicorn.error")
THRESHOLD = 25
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(request: Request, supplied: str | None = Depends(api_key_header)):
    expected = request.app.state.api_key
    if supplied is None or not secrets.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Manglende eller forkert API-nøgle.",
                            headers={"WWW-Authenticate": "APIKey"})


class SensorReading(BaseModel):
    device_id: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")
    wind_speed: float = Field(ge=0, le=80, allow_inf_nan=False)


class TimestampOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime

    @field_serializer("created_at", check_fields=False)
    def serialize_timestamp(self, value):
        # SQLite returnerer naive datetime-værdier; alle gemte værdier er UTC.
        return value.replace(tzinfo=timezone.utc).isoformat()


class ReadingOutput(TimestampOutput):
    id: int
    device_id: str
    wind_speed: float
    anomaly_detected: bool


class AlarmOutput(TimestampOutput):
    id: int
    reading_id: int
    device_id: str
    message: str
    status: str
    acknowledged_at: datetime | None

    @field_serializer("acknowledged_at")
    def serialize_acknowledged_at(self, value):
        return value.replace(tzinfo=timezone.utc).isoformat() if value else None


class EventOutput(TimestampOutput):
    id: int
    event_type: str
    reading_id: int
    alarm_id: int | None
    payload: dict
    device_id: str


def get_session(request: Request):
    # En transaktion: enten gemmes hele handlingen, eller også rulles alt tilbage.
    with Session(request.app.state.engine) as session:
        with session.begin():
            yield session


def create_app(database_url: str | None = None):
    @asynccontextmanager
    async def lifespan(app):
        api_key = os.getenv("API_KEY", "")
        if len(api_key.strip()) < 32 or api_key != api_key.strip():
            raise RuntimeError("Angiv API_KEY som miljøvariabel med mindst 32 tegn uden indledende/afsluttende mellemrum.")
        app.state.api_key = api_key
        engine = make_engine(database_url or configured_database_url())
        app.state.engine = engine
        try:
            try:
                Base.metadata.create_all(engine)
            except SQLAlchemyError:
                logger.error("Kunne ikke klargøre databasen ved opstart.")
                raise RuntimeError("Databasen kunne ikke åbnes. Kontrollér konfiguration og database-status.") from None
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Intelligent IoT API", lifespan=lifespan)

    router = APIRouter(dependencies=[Depends(require_api_key)])

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error("Databasehandlingen fejlede (%s)", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Databasen er midlertidigt utilgængelig. Prøv igen senere."})

    @app.get("/")
    def home():
        return {"message": "Intelligent IoT API virker!"}

    @app.get("/health", summary="Kontrollér API og database")
    def health(request: Request):
        try:
            with request.app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "unhealthy"})
        return {"status": "ok", "database": "connected"}

    @router.post("/readings", response_model=ReadingOutput, status_code=201,
              summary="Gem måling og kontrollér tærsklen på 25 m/s")
    def receive_reading(reading: SensorReading, session: Session = Depends(get_session, scope="function")):
        anomaly = reading.wind_speed > THRESHOLD
        result = Reading(**reading.model_dump(), anomaly_detected=anomaly)
        session.add(result)
        session.flush()
        session.add(DomainEvent(event_type="SensorValueReceived", reading_id=result.id, device_id=reading.device_id,
                                payload=reading.model_dump()))
        if anomaly:
            session.add(DomainEvent(event_type="AnomalyDetected", reading_id=result.id, device_id=reading.device_id,
                                    payload={"wind_speed": reading.wind_speed, "threshold": THRESHOLD, "rule": "wind_speed > 25"}))
            alarm = Alarm(reading_id=result.id, device_id=reading.device_id, message="For høj vindhastighed!", status="active")
            session.add(alarm)
            session.flush()
            session.add(DomainEvent(event_type="AlarmCreated", reading_id=result.id, device_id=reading.device_id,
                                    alarm_id=alarm.id, payload={"status": "active"}))
        session.flush()
        response = ReadingOutput.model_validate(result)
        logger.info("Måling registreret: id=%s, anomaly=%s", result.id, anomaly)
        return response

    @router.get("/readings", response_model=list[ReadingOutput])
    def get_readings(session: Session = Depends(get_session, scope="function")):
        return [ReadingOutput.model_validate(row) for row in session.scalars(select(Reading).order_by(Reading.id))]

    @router.get("/events", response_model=list[EventOutput], summary="Vis gemte domænehændelser i rækkefølge")
    def get_events(session: Session = Depends(get_session, scope="function")):
        return [EventOutput.model_validate(row) for row in session.scalars(select(DomainEvent).order_by(DomainEvent.id))]

    @router.get("/alarms", response_model=list[AlarmOutput])
    def get_alarms(status: Literal["active", "acknowledged", "all"] = Query("active"),
                   session: Session = Depends(get_session, scope="function")):
        query = select(Alarm).order_by(Alarm.id)
        if status != "all":
            query = query.where(Alarm.status == status)
        return [AlarmOutput.model_validate(row) for row in session.scalars(query)]

    @router.patch("/alarms/{alarm_id}/acknowledge", response_model=AlarmOutput,
               summary="Kvittér en alarm; gentagelser opretter ikke ekstra hændelser")
    def acknowledge_alarm(alarm_id: int, session: Session = Depends(get_session, scope="function")):
        # Betinget UPDATE sikrer, at kun én anmodning registrerer overgangen.
        changed = session.execute(update(Alarm).where(Alarm.id == alarm_id, Alarm.status == "active")
                                  .values(status="acknowledged", acknowledged_at=utc_now())).rowcount
        alarm = session.get(Alarm, alarm_id)
        if alarm is None:
            raise HTTPException(status_code=404, detail="Alarmen findes ikke.")
        if changed:
            session.add(DomainEvent(event_type="AlarmAcknowledged", reading_id=alarm.reading_id,
                                    alarm_id=alarm.id, device_id=alarm.device_id, payload={"status": "acknowledged"}))
        session.flush()
        if changed:
            logger.info("Alarm kvitteret: id=%s", alarm.id)
        return AlarmOutput.model_validate(alarm)

    app.include_router(router)
    return app


app = create_app()
