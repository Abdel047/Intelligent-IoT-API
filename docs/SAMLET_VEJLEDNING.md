# Samlet vejledning — Intelligent IoT API

Dette er din samlede læse- og afleveringsvejledning. Del 1–8 forklarer projektet og videoen. Del 9 samler de faktiske kildefiler med forklaringer. Du skal ikke kopiere hele dokumentet tilbage i projektet eller oprette løsningen igen.

Koden er et øjebliksbillede fra 16. november 2026. Rigtige passwords, API-nøgler, databaser og private certifikater er ikke medtaget.

## 1. Hvad har vi bygget?

En REST API, som modtager vindmålinger, kontrollerer en fast grænse og opretter alarmer. Den fiktive virksomhed Intelligent IoT Solutions kan bruge det til at hjælpe driftspersonalet med at opdage forhold, som kræver handling.

**Forløbet er: måling → kontrol → eventuel alarm → permanent lagring.**

Det er en regelbaseret MVP, ikke en AI-model, der forudsiger maskinfejl. Den kan understøtte vedligeholdelse og hurtig reaktion, men vi har ikke implementeret egentlig fejlprognose.

| Del | Dens opgave |
| --- | --- |
| Postman | Efterligner en sensor og sender målingen. |
| Python | Sproget, som backendkoden er skrevet i. |
| FastAPI | Modtager HTTP-requests og returnerer JSON. |
| Pydantic | Kontrollerer input. |
| Uvicorn | Serverprogrammet, der kører FastAPI. |
| SQLAlchemy | Oversætter mellem Python-objekter og SQL-tabeller. |
| MySQL | Gemmer data permanent. |
| Workbench | Viser MySQL-tabeller og lader dig skrive SQL. |
| Docker | Kører API og MySQL i separate containere. |
| Docker Compose | Starter dem samlet ud fra compose.yaml. |
| Git/GitHub | Versionsstyring og deling af kode. |
| GitHub Actions | Automatisk test, build og publicering. |
| GHCR/Packages | Lager til det færdige Docker-image; det er ikke en kørende API-server. |
| Caddy | Valgfri HTTPS-indgang på lokalnettet. |

## 2. Følg én måling

Postman sender en POST-request til /readings med eksempelvis:

```json
{"device_id":"WT-01","wind_speed":30}
```

1. API'et kontrollerer X-API-Key-headeren.
2. Pydantic kontrollerer, at device_id er udfyldt, og wind_speed er et endeligt tal mellem 0 og 80.
3. Koden beregner `30 > 25`, som er sandt.
4. En måling gemmes i sensor_readings med anomaly_detected = true.
5. SensorValueReceived registreres: målingen er modtaget.
6. AnomalyDetected registreres: grænsen er overskredet.
7. En alarm og AlarmCreated registreres.
8. Transaktionen gemmes, og svaret er 201 Created med id, tidspunkt og resultat.

En transaktion betyder, at hele handlingen gemmes samlet. Hvis noget fejler, rulles handlingen tilbage, så vi undgår delvist gemte forløb.

| Vind | Resultat |
| --- | --- |
| 20 m/s | Normal måling og SensorValueReceived. |
| 25 m/s | Også normal: reglen er OVER 25. |
| 30 m/s | Måling, tre hændelser og alarm. |

Hver ny måling over grænsen giver sin egen alarm. Vi samler ikke automatisk flere overskridelser til én alarm pr. vindmølle.

## 3. Tabellerne og deres sammenhæng

| Tabel | Indhold |
| --- | --- |
| sensor_readings | id, installation, vindhastighed, resultat og tidspunkt. |
| domain_events | Hændelsestype, reference til måling/alarm, device_id, JSON-data og tidspunkt. |
| alarms | Reference til målingen, besked, status og tidspunkter. |

**id** er rækkens unikke nummer, en primærnøgle. **reading_id** henviser til målingens id og er en fremmednøgle. **alarm_id** knytter en hændelse til en alarm, når der er en sådan reference.

**event_data** er JSON-kolonnen i SQL. Det samme felt hedder **payload** i API-svaret. **created_at** er oprettelsestid i UTC. **NULL** betyder ingen registreret værdi.

Status active betyder aktiv alarm. Acknowledged betyder set/kvitteret, ikke at problemet nødvendigvis er repareret. Kvitteringen gemmer AlarmAcknowledged og tidspunktet acknowledged_at.

## 4. Dine endpoints

| Request | Betydning |
| --- | --- |
| GET / | Enkel besked om, at API'et svarer. |
| GET /health | Kontrol af databaseforbindelsen. |
| GET /docs | Swagger-testside. |
| GET /openapi.json | API-beskrivelsen som JSON. |
| POST /readings | Opret og behandl måling. |
| GET /readings | Hent alle målinger. |
| GET /events | Hent hændelser. |
| GET /alarms | Hent aktive alarmer. |
| GET /alarms?status=all | Hent aktive og kvitterede alarmer. |
| GET /alarms?status=acknowledged | Hent kun kvitterede alarmer. |
| PATCH /alarms/{alarm_id}/acknowledge | Kvittér valgt alarm uden body. |

GET henter oplysninger. POST opretter en måling her. PATCH ændrer alarmstatus. Der findes ikke GET /alarms/{id} eller POST-acknowledgement i den nuværende kode.

200 = hentning/handling lykkedes. 201 = måling oprettet. 401 = forkert/manglende nøgle. 404 = ukendt alarm. 422 = ugyldigt input. 503 = databaseproblem.

## 5. Docker, porte og sikkerhed

API og MySQL er separate services. Inde i Docker bruger API'et værtsnavnet mysql og port 3306. Workbench på Windows bruger 127.0.0.1:3306.

| Adresse | Hvad åbner du den med? |
| --- | --- |
| http://127.0.0.1:8000 | Browser: API-forside. |
| http://127.0.0.1:8000/docs | Browser: Swagger. |
| 127.0.0.1:3306 | MySQL Workbench, ikke en browser. |

`mysql_data:/var/lib/mysql` kobler MySQLs datamappe til et permanent Docker-volume. Det bevarer data ved normal genstart/genskabelse med samme volume. Et volume er dog ikke en backup mod sletning eller diskfejl. Brug ikke `docker compose down -v`, hvis du vil bevare data.

Den gamle iot.db er bevaret som SQLite-backup. Den aktuelle MySQL-database ligger i Docker-volumen. iot-dev.db er en separat lokal udviklingsdatabase, som ikke skal forveksles med MySQL.

.env indeholder rigtige hemmeligheder. .env.example indeholder kun feltnavne og standarder. API_KEY, MYSQL_PASSWORD og MYSQL_ROOT_PASSWORD er forskellige ting. .gitignore udelukker lokale hemmeligheder og data fra nye commits. .dockerignore sørger for, at de ikke indbygges i API-imaget.

En gammel API-nøgle findes stadig i Git-historikken, men er udskiftet. Ignore-regler fjerner ikke gamle commits. Del ikke .env eller private Postman-filer.

Den valgfrie LAN-konfiguration tilføjer Caddy med HTTPS på en privat IP-adresse. MySQL forbliver lokal. Klienten skal stole på det offentlige CA-certifikat; private nøgler bliver i Docker-volumen. Den seneste containerstatus viste ingen publiceret gatewayport, så LAN skal startes/kontrolleres igen før brug. En fysisk anden enhed er endnu ikke dokumenteret testet.

## 6. Start og brug

### Din computer

Åbn Docker Desktop og vent på engine. Åbn projektmappen i VS Code og PowerShell-terminalen:

```powershell
docker compose up --build -d
docker compose ps
```

API og MySQL skal være healthy. Hvis de allerede kører korrekt, behøver du ikke bygge igen. Åbn /health og /docs i browseren.

### En ny computer

Klon repositoryet efter invitation. Installér/start Docker Desktop. Opret lokale dependencies og konfiguration:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/prepare_env.py
```

Byg lokalt med standardkommandoen, eller hent den publicerede pakke:

```powershell
docker login ghcr.io -u DIT_GITHUB_BRUGERNAVN
docker compose -f compose.yaml -f compose.image.yaml pull
docker compose -f compose.yaml -f compose.image.yaml up --no-build -d --wait
```

Privat pakke kræver adgang og et GitHub-token med read:packages i loginprompten. Skriv ikke tokenet i kommandoen. Hver installation har egne hemmeligheder og eget databasevolume; dine målinger følger ikke med imaget. Gruppens faktiske adgang/pull skal stadig prøves.

### Postman

Collectionen er postman/Intelligent-IoT.postman_collection.json. Dens api_key skal udfyldes privat. Alternativt opret en request manuelt med metode, URL og headeren X-API-Key. Ved POST vælges Body → raw → JSON.

### Workbench

Forbindelsen er demonstreret i brugerfladen. Brug mysql, host 127.0.0.1, port 3306, bruger iot_user og default schema intelligent_iot. Passwordet findes kun lokalt som MYSQL_PASSWORD i .env.

Under Schemas udvider du intelligent_iot → Tables. Skriv en SELECT i SQL-editoren og klik blå Run. Kør forespørgslen igen efter en ny måling. Resultatet opdaterer ikke sig selv. docs/inspect_mysql.sql indeholder de tre normale SELECTs.

### Tests og CI/CD

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

40 tests har bestået. De bruger separate midlertidige SQLite-databaser og en ufølsom testnøgle. De tester grænsen, validering, events, alarmer, kvittering, rollback, health og persistens ved genåbning. Der er en kendt deprecation-advarsel om httpx i testklienten.

```powershell
.\.venv\Scripts\python.exe scripts/verify_stack.py --restart
```

Dette script tester live MySQL gennem API og SQL. Det opretter tre DEMO-målinger og kontrollerer data efter genstart. Det sletter ikke rækker. Det er tidligere bestået lokalt og i CI.

GitHub Actions gør disse kontroller automatisk på en separat Linux-maskine. Efter bestået CI på main publicerer CD-jobbet imaget til GHCR med commit-tag og latest. Det er Continuous Delivery. Der er ikke automatisk deployment til en permanent server eller Azure.

Verificeret grøn kørsel: https://github.com/Abdel047/Intelligent-IoT-API/actions/runs/43833583581

## 7. Sikker SQL-INSERT til undervisningen

**Følgende er et foreslået eksempel, som endnu ikke er kørt/verificeret. Oprettelsen af dette dokument indsætter ingen data. Øv det med hjælp før videoen.**

Direkte SQL omgår API'ets validering og alarmregel. Derfor bruges en tydeligt mærket normal måling på 20 m/s, og hændelsen indsættes eksplicit i samme transaktion. MySQL opretter ikke automatisk eventet. Dette er en SQL-testregistrering og ikke et kald til sensor-endpointet.

Kør i samme Workbench-forbindelse:

```sql
USE intelligent_iot;
START TRANSACTION;
SET @device = CONCAT('SQL-DEMO-', LEFT(UUID(), 8));

INSERT INTO sensor_readings
    (device_id, wind_speed, anomaly_detected, created_at)
VALUES (@device, 20.0, FALSE, UTC_TIMESTAMP(6));

SET @reading_id = LAST_INSERT_ID();

INSERT INTO domain_events
    (event_type, reading_id, alarm_id, device_id, event_data, created_at)
VALUES
    ('SensorValueReceived', @reading_id, NULL, @device,
     JSON_OBJECT('device_id', @device, 'wind_speed', 20.0,
                 'source', 'workbench_sql_demo'), UTC_TIMESTAMP(6));

SELECT * FROM sensor_readings WHERE id = @reading_id;
SELECT * FROM domain_events WHERE reading_id = @reading_id;
```

Kontrollér resultatet. Kun hvis alt er korrekt, kør separat:

```sql
COMMIT;
```

Ved en fejl før commit: stop og kør `ROLLBACK;` i samme forbindelse. Fortsæt ikke til COMMIT efter en fejlet sætning. Efter COMMIT kan ROLLBACK ikke fortryde de gemte data.

Efter commit: send GET /readings i Postman og find samme id. Det demonstrerer, at API'et læser SQL-data. Det demonstrerer ikke API'ets POST-behandling. Brug POST /readings til automatisk alarmflow ved 30 m/s.

## 8. Opsætning og manuskript til cirka fem minutter

### Åbn programmerne i denne rækkefølge

1. Docker Desktop: Containers → pilen ved intelligent-iot. Vis api og mysql.
2. Postman: to POST-requests og GET /readings klar. Hav Body-fanen åben.
3. MySQL Workbench: log ind før optagelsen, og hav en SQL-editor klar.
4. Browser: http://127.0.0.1:8000/docs og den grønne Actions-kørsel.

Brug Alt+Tab til at skifte og øv det først. Du behøver ikke vise SQLTools, når læreren ønsker Workbench.

### Forbered de to POST-requests

URL: http://127.0.0.1:8000/readings. API-nøglen skal være indstillet privat før optagelsen.

Normal:

```json
{"device_id":"AFLEVERING-01","wind_speed":20}
```

Alarm:

```json
{"device_id":"AFLEVERING-02","wind_speed":30}
```

Hvert Send opretter nye rækker. Id'er vil variere. Slet ikke tidligere data for at opnå bestemte numre.

### Forbered disse tre forespørgsler i Workbench

```sql
SELECT * FROM intelligent_iot.sensor_readings ORDER BY id DESC LIMIT 5;
SELECT * FROM intelligent_iot.domain_events ORDER BY id DESC LIMIT 6;
SELECT * FROM intelligent_iot.alarms ORDER BY id DESC LIMIT 5;
```

Markér én hel SELECT ad gangen og klik Run. Peg på samme id/reading_id som Postman-svaret.

### Manuskript

Planen inkluderer SQL-INSERT-kravet. INSERT fra del 7 skal være afprøvet først, ellers må den ikke fremstilles som verificeret.

| Tid | Hvad du gør | Hvad du siger |
| --- | --- | --- |
| 0:00–0:30 | Vis api og mysql i Docker. | “Jeg har udviklet en REST API til Intelligent IoT Solutions. Den modtager vindmålinger og opretter alarmer ved for høj vind. API og database kører separat i Docker.” |
| 0:30–1:10 | Postman: normal måling på 20, Send, peg på 201 og false. | “Input valideres, og målingen gemmes. Der er ingen anomali og ingen alarm. Præcis 25 meter pr. sekund ville også være normal.” |
| 1:10–1:50 | Postman: måling på 30, Send, peg på true og notér id. | “Nu overskrides grænsen på 25. Derfor registreres en anomali og en alarm. Målingens id kan findes igen i databasen.” |
| 1:50–2:50 | Workbench: kør de tre SELECTs hver for sig. | “Her er målingen i MySQL. Reading-id binder den sammen med SensorValueReceived, AnomalyDetected og AlarmCreated. Alarmen er active. Hele handlingen gemmes i én transaktion.” |
| 2:50–3:40 | Workbench: kør den afprøvede normale INSERT og COMMIT. Postman: GET /readings og find samme id. | “Jeg demonstrerer også direkte SQL-indsættelse og læsning gennem API'et. SQL går uden om Python-reglerne, så dette er en normal testmåling med en eksplicit hændelse. Sensorer skal normalt bruge POST-endpointet.” |
| 3:40–4:35 | Vis grøn Actions-kørsel, test/build-job og CD-job. | “Ved push og pull requests kontrolleres projektet automatisk. 40 tests, Docker-build og MySQL-kontrol har bestået. Der testes også persistens efter genstart. Derefter publiceres et versioneret Docker-image i Packages.” |
| 4:35–5:00 | Vis Docker-volumen eller bliv på grønt resultat. | “Databasen har et permanent volume. Løsningen er en regelbaseret MVP til overvågning og vedligeholdelse. Den er ikke en AI-model, som forudsiger fremtidige maskinfejl.” |

Hvis live genstart skal med: afsæt 30–45 sekunder til `docker compose restart api mysql`, vent på /health og kør SELECT igen. Vis de samme id'er. Forkort andet stof eller aftal lidt mere tid. Brug aldrig -v til denne demonstration.

Hvis adgang/installation fra anden computer skal vises, skal det prøves før optagelsen. At starte en egen installation fra Packages er noget andet end at nå din eksisterende API via LAN.

### Hold hemmeligheder ude af billedet

Luk .env og private JSON-filer. Vis ikke Postmans Headers, Authorization, variabler eller kodeeksport. Luk udklipsholderhistorik og loginprompter. Brug ikke udfyldt `docker compose config` på skærmen; `config --quiet` udskriver ikke konfigurationen. Sæt optagelsen på pause, hvis login er nødvendigt. Skjul VS Codes bundpanel med Ctrl+J, når det forstyrrer.

## 9. Den aktuelle kode — med forklaringer

Nedenfor følger komplette kopier af de delbare kildefiler. Ingen .env, rigtige passwords, databaser eller certifikatnøgler er medtaget. De rigtige projektfiler er den autoritative kode, hvis dokumentet senere bliver forældet.

### 9.1. main.py

API'et og forretningsreglerne. SensorReading validerer input. require_api_key kontrollerer headeren med compare_digest. create_app samler appen, og lifespan starter/lukker databaseforbindelsen. get_session giver hver handling en transaktion. receive_reading gemmer måling og eventuelt alarmflow. Output-klasserne bestemmer JSON-svarets felter. acknowledge_alarm ændrer kun en aktiv alarm én gang. health udfører SELECT 1.

```python
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
```

### 9.2. database.py

Databasemodellerne. Base er grundlaget for tabellerne. Mapped og mapped_column beskriver typer/kolonner. ForeignKey binder tabeller sammen. configured_database_url vælger DATABASE_URL, derefter MySQL eller udviklings-SQLite. URL.create håndterer specialtegn i passwords. UTC_DATETIME bevarer mikrosekunder i MySQL. pool_pre_ping kontrollerer forbindelser ved genbrug; hide_parameters skjuler SQL-parametre i SQLAlchemy-fejl.

```python
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
```

### 9.3. compose.yaml

Hovedopskriften. services beskriver API og MySQL. ports binder kun til localhost. environment sender konfiguration ind. depends_on venter på database-healthcheck ved opstart. mysql_data kobles til datamappen, så data ikke kun ligger i containeren. restart er en genstartspolitik, ikke en backup.

```yaml
name: intelligent-iot
services:
  api:
    build: .
    restart: unless-stopped
    ports:
      - "127.0.0.1:${API_PORT:-8000}:8000"
    environment:
      API_KEY: ${API_KEY:?Kør scripts/prepare_env.py først}
      MYSQL_HOST: mysql
      MYSQL_PORT: "3306"
      MYSQL_DATABASE: ${MYSQL_DATABASE:-intelligent_iot}
      MYSQL_USER: ${MYSQL_USER:-iot_user}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD:?MYSQL_PASSWORD mangler i .env}
    depends_on:
      mysql:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
  mysql:
    image: mysql:8.4
    restart: unless-stopped
    ports:
      - "127.0.0.1:${MYSQL_PUBLISHED_PORT:-3306}:3306"
    environment:
      MYSQL_DATABASE: ${MYSQL_DATABASE:-intelligent_iot}
      MYSQL_USER: ${MYSQL_USER:-iot_user}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD:?MYSQL_PASSWORD mangler i .env}
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD mangler i .env}
    command: ["--character-set-server=utf8mb4", "--collation-server=utf8mb4_unicode_ci", "--default-time-zone=+00:00"]
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD-SHELL", 'MYSQL_PWD="$${MYSQL_PASSWORD}" mysql --protocol=TCP -h 127.0.0.1 -u "$${MYSQL_USER}" "$${MYSQL_DATABASE}" -e "SELECT 1" >/dev/null 2>&1']
      interval: 10s
      timeout: 5s
      retries: 20
      start_period: 60s
volumes:
  mysql_data:
```

### 9.4. Dockerfile

API-imagets byggeopskrift. FROM vælger Python. WORKDIR angiver arbejdsmappe. COPY og RUN installerer pakker og tilføjer kode. USER appuser kører API-processen uden root. CMD starter Uvicorn. EXPOSE beskriver porten; faktisk publicering styres i Compose.

```dockerfile
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser
COPY main.py database.py ./
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 9.5. requirements.txt

Runtimepakker til API'et. PyMySQL er SQLAlchemy-driveren til MySQL. rsa-tilvalget understøtter den anvendte MySQL-autentifikation.

```text
fastapi==0.162.2
uvicorn==0.54.0
SQLAlchemy==2.1.8
PyMySQL[rsa]==1.2.4
```

### 9.6. requirements-dev.txt

Testpakker. -r medtager runtimepakker. pytest udfører tests, og httpx bruges af testklienten.

```text
-r requirements.txt
pytest==9.2.0
httpx==0.28.1
```

### 9.7. .env.example

Feltnavne uden rigtige hemmeligheder. Tomme passwordfelter er med vilje tomme. Den lokale .env er ikke med i dokumentet.

```dotenv
# Kopiér aldrig rigtige hemmeligheder til denne fil.
# Kør scripts/prepare_env.py for at oprette/udfylde den lokale .env sikkert.
API_KEY=
MYSQL_DATABASE=intelligent_iot
MYSQL_USER=iot_user
MYSQL_PASSWORD=
MYSQL_ROOT_PASSWORD=
MYSQL_PUBLISHED_PORT=3306
API_PORT=8000

# Valgfri HTTPS-demo fra andre enheder på samme netværk
# start_lan.ps1 finder den aktuelle private IP-adresse.
LAN_HOST=
LAN_HTTPS_PORT=8443
```

### 9.8. .gitignore

Filer, som ikke skal med i nye Git-commits. Regler fjerner ikke historiske kopier fra gamle commits.

```gitignore
.venv/
__pycache__/
.pytest_cache/
*.py[cod]
.env
.env.*
!.env.example
*.db
*.db-*
*.sqlite
*.sqlite-*
*.sqlite3
*.sqlite3-*
*.local.postman_collection.json

# Lokale certifikater, sessioner og driftskvitteringer
certs/
*.session.sql
*.local.json
```

### 9.9. .dockerignore

En allowliste for Docker-buildet. Lokale databaser og hemmeligheder kommer ikke med i API-imaget.

```text
# Kun de nødvendige kildefiler må indgå i build-context.
**
!Dockerfile
!requirements.txt
!main.py
!database.py
```

### 9.10. tests/test_api.py

Fixtures opretter isolerede testdatabaser og en ufølsom testnøgle. parametrize giver flere testtilfælde for samme funktion. Testene kontrollerer validering, grænser, events, relationer, 401, kvittering, rollback, persistens, health og MySQL-URL. Live MySQL testes separat af verify_stack.py.

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from main import create_app


TEST_API_KEY = "test-only-key-not-for-production-123456789"


@pytest.fixture(autouse=True)
def configure_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", TEST_API_KEY)


@pytest.fixture
def database_url(tmp_path):
    return "sqlite:///" + (tmp_path / "test.db").as_posix()


@pytest.fixture
def client(database_url):
    with TestClient(create_app(database_url), headers={"X-API-Key": TEST_API_KEY}) as client:
        yield client


@pytest.mark.parametrize("speed,anomaly", [(0, False), (20, False), (25, False), (30, True), (80, True)])
def test_reading_and_events(client, speed, anomaly):
    response = client.post("/readings", json={"device_id": "WT-01", "wind_speed": speed})
    assert response.status_code == 201
    reading = response.json()
    assert reading["anomaly_detected"] is anomaly
    assert reading["created_at"].endswith("+00:00")
    assert client.get("/readings").json() == [reading]
    events = client.get("/events").json()
    assert [e["event_type"] for e in events] == (["SensorValueReceived", "AnomalyDetected", "AlarmCreated"] if anomaly else ["SensorValueReceived"])
    assert all(e["reading_id"] == reading["id"] for e in events)
    alarms = client.get("/alarms").json()
    assert len(alarms) == int(anomaly)
    if anomaly:
        assert alarms[0]["reading_id"] == reading["id"]
        assert events[-1]["alarm_id"] == alarms[0]["id"]


@pytest.mark.parametrize("payload", [
    {"device_id": "WT-01", "wind_speed": -1},
    {"device_id": "WT-01", "wind_speed": 81},
    {"device_id": "WT-01", "wind_speed": "NaN"},
    {"device_id": "WT-01", "wind_speed": "Infinity"},
    {"device_id": "WT-01", "wind_speed": "abc"},
    {"device_id": "", "wind_speed": 20},
    {"device_id": "   ", "wind_speed": 20},
    {"device_id": "x" * 101, "wind_speed": 20},
    {"wind_speed": 20},
])
def test_invalid_input(client, payload):
    assert client.post("/readings", json=payload).status_code == 422
    assert client.get("/readings").json() == []
    assert client.get("/events").json() == []
    assert client.get("/alarms").json() == []


def test_acknowledgement(client):
    client.post("/readings", json={"device_id": "WT-01", "wind_speed": 30})
    alarm_id = client.get("/alarms").json()[0]["id"]
    url = f"/alarms/{alarm_id}/acknowledge"
    result = client.patch(url)
    assert result.status_code == 200
    assert result.json()["status"] == "acknowledged"
    assert result.json()["acknowledged_at"].endswith("+00:00")
    assert client.patch(url).json() == result.json()
    assert client.get("/alarms").json() == []
    assert len(client.get("/alarms?status=acknowledged").json()) == 1
    assert len(client.get("/alarms?status=all").json()) == 1
    assert [e["event_type"] for e in client.get("/events").json()].count("AlarmAcknowledged") == 1
    assert client.patch("/alarms/999999/acknowledge").status_code == 404
    assert client.get("/alarms?status=invalid").status_code == 422


def test_persistence_after_restart(database_url):
    with TestClient(create_app(database_url), headers={"X-API-Key": TEST_API_KEY}) as first:
        first.post("/readings", json={"device_id": "WT-01", "wind_speed": 30})
        alarm_id = first.get("/alarms").json()[0]["id"]
        first.patch(f"/alarms/{alarm_id}/acknowledge")
        before = [first.get(path).json() for path in ["/readings", "/events", "/alarms?status=all"]]
    with TestClient(create_app(database_url), headers={"X-API-Key": TEST_API_KEY}) as second:
        after = [second.get(path).json() for path in ["/readings", "/events", "/alarms?status=all"]]
    assert before == after
    assert len(after[0]) == 1
    assert len(after[1]) == 4
    assert after[2][0]["status"] == "acknowledged"


def test_transaction_rolls_back(client):
    def fail_event_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO domain_events"):
            import sqlite3
            raise OperationalError(statement, parameters, sqlite3.OperationalError("simulated failure"))
    # Simulér en databasefejl under lagring af events.
    event.listen(client.app.state.engine, "before_cursor_execute", fail_event_insert)
    try:
        response = client.post("/readings", json={"device_id": "WT-01", "wind_speed": 30})
        assert response.status_code == 503
        assert "simulated failure" not in response.text
    finally:
        event.remove(client.app.state.engine, "before_cursor_execute", fail_event_insert)
    assert client.get("/readings").json() == []
    assert client.get("/events").json() == []
    assert client.get("/alarms").json() == []


@pytest.mark.parametrize("method,path", [
    ("GET", "/readings"), ("GET", "/events"), ("GET", "/alarms"),
    ("POST", "/readings"), ("PATCH", "/alarms/1/acknowledge"),
])
@pytest.mark.parametrize("key", [None, "incorrect-key", ""])
def test_unauthorized_requests(client, method, path, key):
    client.headers.pop("X-API-Key")
    headers = {} if key is None else {"X-API-Key": key}
    response = client.request(method, path, headers=headers,
                              json={"device_id": "WT-01", "wind_speed": 30} if method == "POST" else None)
    assert response.status_code == 401
    assert TEST_API_KEY not in response.text
    client.headers["X-API-Key"] = TEST_API_KEY
    assert client.get("/readings").json() == []
    assert client.get("/events").json() == []
    assert client.get("/alarms?status=all").json() == []


@pytest.mark.parametrize("key", [None, "", "short", " " * 40])
def test_missing_configuration_fails_startup(database_url, monkeypatch, key):
    if key is None:
        monkeypatch.delenv("API_KEY", raising=False)
    else:
        monkeypatch.setenv("API_KEY", key)
    with pytest.raises(RuntimeError, match="API_KEY"):
        with TestClient(create_app(database_url)):
            pass


def test_public_home_and_security_documentation(client):
    client.headers.pop("X-API-Key")
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/readings"]["post"]["security"] == [{"APIKeyHeader": []}]
    assert "security" not in schema["paths"]["/"]["get"]


def test_health_checks_database(client, monkeypatch):
    assert client.get("/health").json() == {"status": "ok", "database": "connected"}
    def unavailable():
        raise OperationalError("SELECT 1", {}, Exception("private connection detail"))
    monkeypatch.setattr(client.app.state.engine, "connect", unavailable)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy"}
    assert "private" not in response.text


def test_event_device_id_and_payload(client):
    response = client.post("/readings", json={"device_id": "WT-03", "wind_speed": 30})
    assert response.status_code == 201
    for record in client.get("/events").json():
        assert record["device_id"] == "WT-03"
        assert isinstance(record["payload"], dict)


def test_mysql_url_handles_special_password_characters(monkeypatch):
    from database import configured_database_url
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MYSQL_HOST", "mysql")
    monkeypatch.setenv("MYSQL_USER", "iot_user")
    monkeypatch.setenv("MYSQL_PASSWORD", "test-only-@:/?#pass")
    monkeypatch.setenv("MYSQL_DATABASE", "intelligent_iot")
    url = configured_database_url()
    assert url.drivername == "mysql+pymysql"
    assert url.host == "mysql"
    assert url.password == "test-only-@:/?#pass"
    assert url.database == "intelligent_iot"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///explicit-test.db")
    assert configured_database_url() == "sqlite:///explicit-test.db"
```

### 9.11. .github/workflows/ci.yml

GitHubs pipeline. on angiver hvornår den starter. test-and-build kontrollerer kode og MySQL i Ubuntu. Der genereres egne midlertidige CI-hemmeligheder. deliver-image afhænger af bestået test og kører kun ved push til main. Det kortlivede GITHUB_TOKEN logger ind i GHCR. Imaget tagges med commit-id og latest. Det er publicering, ikke automatisk deployment til en permanent server.

```yaml
name: CI - tests og Docker

on:
  push:
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test-and-build:
    name: Tests, Docker-build og MySQL-integration
    runs-on: ubuntu-latest
    timeout-minutes: 20
    env:
      COMPOSE_PROJECT_NAME: intelligent-iot-ci
    steps:
      - name: Hent projektet
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false

      - name: Installer Python 3.13
        uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7
        with:
          python-version: '3.13'
          cache: pip
          cache-dependency-path: |
            requirements.txt
            requirements-dev.txt

      - name: Installer Python-pakker
        run: python -m pip install -r requirements-dev.txt

      - name: Kør isolerede tests
        run: python -m pytest -q

      - name: Opret midlertidig CI-konfiguration
        run: python scripts/prepare_env.py

      - name: Kontrollér Compose-konfiguration
        run: docker compose config --quiet

      - name: Byg Docker-imaget
        run: docker compose build api

      - name: Start API og MySQL i CI
        run: docker compose up --no-build -d --wait --wait-timeout 180

      - name: Kontrollér API, MySQL og data efter genstart
        run: python scripts/verify_stack.py --restart

      - name: Stop CI-containere
        if: always()
        run: docker compose down --remove-orphans

  deliver-image:
    name: CD - lever testet Docker-image til GHCR
    needs: test-and-build
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: read
      packages: write
    steps:
      - name: Hent den testede kode
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false

      - name: Byg versioneret release-image
        shell: bash
        run: |
          image="ghcr.io/${GITHUB_REPOSITORY,,}"
          echo "RELEASE_IMAGE=$image" >> "$GITHUB_ENV"
          docker build --label "org.opencontainers.image.source=https://github.com/$GITHUB_REPOSITORY" --label "org.opencontainers.image.revision=$GITHUB_SHA" --tag "$image:$GITHUB_SHA" --tag "$image:latest" .

      - name: Log ind i GitHub Container Registry
        env:
          GHCR_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin

      - name: Lever Docker-image
        run: |
          docker push "$RELEASE_IMAGE:$GITHUB_SHA"
          docker push "$RELEASE_IMAGE:latest"
          echo "### Testet image klar" >> "$GITHUB_STEP_SUMMARY"
          echo "Image: \`$RELEASE_IMAGE:$GITHUB_SHA\`" >> "$GITHUB_STEP_SUMMARY"

      - name: Log ud af registry
        if: always()
        run: docker logout ghcr.io
```

### 9.12. compose.image.yaml

Overstyrer API'ets image til den publicerede pakke. Brug pull og up --no-build sammen med hovedfilen.

```yaml
# Brug det færdige image fra GitHub Packages i stedet for at bygge lokalt.
# Start med --no-build som beskrevet i README.
services:
  api:
    image: ${API_IMAGE:-ghcr.io/abdel047/intelligent-iot-api:latest}
```

### 9.13. compose.lan.yaml

Valgfri HTTPS-gateway. Binder gatewayens port til en bestemt privat IP. Basisfilens MySQL og HTTP-port forbliver på localhost.

```yaml
# Valgfrit HTTPS-lag. API og MySQL beholder deres localhost-bindinger.
services:
  gateway:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "${LAN_HOST:?Kør scripts/start_lan.ps1 først}:${LAN_HTTPS_PORT:-8443}:443"
    environment:
      LAN_HOST: ${LAN_HOST:?LAN_HOST mangler}
    volumes:
      - ./deploy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      api:
        condition: service_healthy
volumes:
  caddy_data:
  caddy_config:
```

### 9.14. deploy/Caddyfile

Caddys HTTPS-konfiguration. tls internal bruger lokal CA. Klienter skal stole på det offentlige rodcertifikat. reverse_proxy sender trafik videre til api:8000. default_sni hjælper klienter, som forbinder via IP uden SNI. Caddys admin-API er slået fra.

```text
{
    auto_https disable_redirects
    skip_install_trust
    admin off
    default_sni {$LAN_HOST}
}

https://{$LAN_HOST}, https://localhost {
    tls internal
    reverse_proxy api:8000
}
```

### 9.15. scripts/prepare_env.py

Opretter/udfylder kun manglende eller tomme lokale .env-værdier. Eksisterende udfyldte passwords bevares, og indholdet udskrives ikke.

```python
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
```

### 9.16. scripts/verify_stack.py

Live integrationstest. Sender 15, 25 og 30 m/s via HTTP og kontrollerer SQL. --restart kontrollerer de samme data efter genstart. Scriptet opretter nye DEMO-data; det er ikke en ren læsekontrol.

```python
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
```

### 9.17. scripts/start_lan.ps1

Finder privat IPv4, opdaterer lokale LAN-felter, starter HTTPS-laget og eksporterer kun det offentlige CA-certifikat. Det installerer ikke certifikatet på andre enheder.

```powershell
param([string]$Address)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not $Address) {
    $network = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1
    $Address = $network.IPv4Address.IPAddress
}
$parsed = $null
if (-not [System.Net.IPAddress]::TryParse($Address, [ref]$parsed) -or $parsed.AddressFamily -ne 'InterNetwork') {
    throw 'Kunne ikke finde en IPv4-adresse. Brug -Address med computerens lokale IP.'
}
$bytes = $parsed.GetAddressBytes()
$isPrivate = $bytes[0] -eq 10 -or ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or ($bytes[0] -eq 192 -and $bytes[1] -eq 168)
if (-not $isPrivate) { throw 'LAN-demoen kræver en privat lokal IPv4-adresse.' }
if (-not (Get-NetIPAddress -IPAddress $Address -ErrorAction SilentlyContinue)) { throw 'Adressen tilhører ikke denne computer.' }
$envFile = Join-Path $projectRoot '.env'
$content = [System.IO.File]::ReadAllText($envFile)
if ($content -match '(?m)^LAN_HOST=') { $content = [regex]::Replace($content, '(?m)^LAN_HOST=.*', "LAN_HOST=$Address") }
else { $content = $content.TrimEnd() + "`nLAN_HOST=$Address`n" }
if ($content -notmatch '(?m)^LAN_HTTPS_PORT=') { $content = $content.TrimEnd() + "`nLAN_HTTPS_PORT=8443`n" }
[System.IO.File]::WriteAllText($envFile, $content, [System.Text.UTF8Encoding]::new($false))
$env:LAN_HOST = $Address
& docker compose -f compose.yaml -f compose.lan.yaml config --quiet
if ($LASTEXITCODE -ne 0) { throw 'LAN-konfiguration kunne ikke valideres.' }
& docker compose -f compose.yaml -f compose.lan.yaml up -d --wait --wait-timeout 180
if ($LASTEXITCODE -ne 0) { throw 'LAN-services kunne ikke startes.' }
New-Item -ItemType Directory -Path (Join-Path $projectRoot 'certs') -Force | Out-Null
$copied = $false
for ($attempt = 0; $attempt -lt 15; $attempt++) {
    & docker compose -f compose.yaml -f compose.lan.yaml cp gateway:/data/caddy/pki/authorities/local/root.crt certs/iot-local-root.crt 2>$null
    if ($LASTEXITCODE -eq 0) { $copied = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $copied) { throw 'Kunne ikke hente det offentlige rodcertifikat.' }
$portLine = ($content -split "`n" | Where-Object { $_.StartsWith('LAN_HTTPS_PORT=') })
$port = ($portLine -split '=', 2)[1].Trim()
Write-Output "HTTPS klar på https://${Address}:$port/docs"
Write-Output 'Rodcertifikat: certs/iot-local-root.crt. Del kun denne offentlige certifikatfil, aldrig private nøgler.'
Write-Output 'Åbn firewall med scripts/enable_lan_firewall.ps1 som administrator før test fra en anden computer.'
```

### 9.18. scripts/enable_lan_firewall.ps1

Kræver administrator. Åbner kun den valgte HTTPS-port på den valgte lokale adresse fra LocalSubnet. -Remove fjerner projektets regel. Der åbnes ingen database- eller routerport.

```powershell
# Kør som administrator. Åbner kun HTTPS-porten fra det lokale subnet.
param([switch]$Remove)
try {
$ErrorActionPreference = 'Stop'
$ruleName = 'Intelligent-IoT-HTTPS-LAN'
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw 'Kør dette script i PowerShell som administrator.' }
if ($Remove) {
    Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    Write-Output 'LAN-firewallreglen er fjernet.'
    exit
}
$values = @{}
Get-Content -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) '.env') | ForEach-Object {
    if ($_ -match '^([A-Z_]+)=(.*)$') { $values[$matches[1]] = $matches[2].Trim() }
}
$address = $values['LAN_HOST']
$port = [int]$values['LAN_HTTPS_PORT']
if ($port -lt 1024 -or $port -gt 65535) { throw 'LAN-port skal være mellem 1024 og 65535.' }
if (-not (Get-NetIPAddress -IPAddress $address -ErrorAction SilentlyContinue)) { throw 'LAN_HOST er ikke en lokal IP-adresse.' }
$existing = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    $existing | Set-NetFirewallRule -Enabled True -Direction Inbound -Action Allow -Profile Any
    $existing | Get-NetFirewallPortFilter | Set-NetFirewallPortFilter -Protocol TCP -LocalPort $port
    $existing | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -LocalAddress $address -RemoteAddress LocalSubnet
} else {
    New-NetFirewallRule -Name $ruleName -DisplayName 'Intelligent IoT: HTTPS fra lokalnet' -Direction Inbound -Action Allow -Protocol TCP -LocalAddress $address -LocalPort $port -RemoteAddress LocalSubnet -Profile Any | Out-Null
}
Write-Output "Firewall klar: kun TCP $port på $address fra LocalSubnet. Databaseporten er ikke åbnet."

    @{ status = 'ok' } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'firewall-status.local.json')
} catch {
    @{ status = 'error'; message = $_.Exception.Message } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'firewall-status.local.json')
    exit 1
}
```

### 9.19. scripts/deploy_local.ps1

Kontrolleret lokal opdatering. Validerer Compose, bygger/start services og kontrollerer health. -Lan medtager gatewayen. Der slettes ingen volumes eller hentes nye Git-commits.

```powershell
# Kontrolleret lokal deployment af de kildefiler, der allerede er i projektmappen.
param([switch]$Lan)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.env')) { throw 'Kør scripts/prepare_env.py først.' }
$composeArgs = @('compose', '-f', 'compose.yaml')
if ($Lan) { $composeArgs += @('-f', 'compose.lan.yaml') }
& docker @composeArgs config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose-konfiguration fejlede; deployment afbrudt.' }
& docker @composeArgs up --build -d --wait --wait-timeout 180
if ($LASTEXITCODE -ne 0) { throw 'Deployment fejlede; kontrollér containerstatus. Volumes er ikke slettet.' }
$apiPort = '8000'
Get-Content -LiteralPath '.env' | ForEach-Object {
    if ($_ -match '^API_PORT=(.+)$') { $apiPort = $matches[1].Trim() }
}
$health = Invoke-RestMethod -Uri "http://127.0.0.1:$apiPort/health"
if ($health.status -ne 'ok') { throw 'Database-healthcheck bestod ikke.' }
Write-Output 'Lokal deployment gennemført. API og database er klar, og volume er bevaret.'
```

### 9.20. docs/inspect_mysql.sql

De almindelige SELECT-forespørgsler. USE vælger database. SELECT læser kolonner. ORDER BY id DESC sætter nyeste række øverst. Ingen data ændres.

```sql
-- Vælg den eksisterende database.
USE intelligent_iot;

-- Målinger: 0 = normal, 1 = over grænsen på 25 m/s.
SELECT id, device_id, wind_speed, anomaly_detected, created_at
FROM sensor_readings
ORDER BY id DESC;

-- Domænehændelser. reading_id henviser til målingens id.
SELECT id, reading_id, device_id, event_type, event_data, created_at
FROM domain_events
ORDER BY id DESC;

-- Alarmer og eventuelt tidspunkt for kvittering.
SELECT id, reading_id, device_id, message, status, created_at, acknowledged_at
FROM alarms
ORDER BY id DESC;
```

### 9.21. postman/Intelligent-IoT.postman_collection.json

Delbare requests med tom api_key. Udfyld din lokale nøgle privat i Postman. Requesten til aktive alarmer kan vælge alarm_id til næste kvittering; kontrollér hvilken alarm du vælger. Kør ikke hele collectionen, hvis du ikke ønsker nye målinger og kvitteringer.

```json
{
  "info": {
    "name": "Intelligent IoT API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    "description": "Delbar collection uden hemmeligheder. Sæt api_key lokalt i Postman før brug. POST og PATCH ændrer data."
  },
  "auth": {
    "type": "apikey",
    "apikey": [
      {
        "key": "key",
        "value": "X-API-Key",
        "type": "string"
      },
      {
        "key": "value",
        "value": "{{api_key}}",
        "type": "string"
      },
      {
        "key": "in",
        "value": "header",
        "type": "string"
      }
    ]
  },
  "variable": [
    {
      "key": "base_url",
      "value": "http://127.0.0.1:8000",
      "type": "string"
    },
    {
      "key": "api_key",
      "value": "",
      "type": "string"
    },
    {
      "key": "alarm_id",
      "value": "",
      "type": "string"
    }
  ],
  "item": [
    {
      "name": "0. Kontrollér API og database",
      "request": {
        "method": "GET",
        "header": [],
        "auth": {
          "type": "noauth"
        },
        "url": "{{base_url}}/health"
      }
    },
    {
      "name": "1. Se gemte målinger",
      "request": {
        "method": "GET",
        "header": [],
        "url": "{{base_url}}/readings"
      }
    },
    {
      "name": "2. Send normal måling (20 m/s)",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "url": "{{base_url}}/readings",
        "body": {
          "mode": "raw",
          "raw": "{\n  \"device_id\": \"WT-02\",\n  \"wind_speed\": 20\n}",
          "options": {
            "raw": {
              "language": "json"
            }
          }
        }
      }
    },
    {
      "name": "3. Send måling med alarm (30 m/s)",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "url": "{{base_url}}/readings",
        "body": {
          "mode": "raw",
          "raw": "{\n  \"device_id\": \"WT-01\",\n  \"wind_speed\": 30\n}",
          "options": {
            "raw": {
              "language": "json"
            }
          }
        }
      }
    },
    {
      "name": "4. Se domænehændelser",
      "request": {
        "method": "GET",
        "header": [],
        "url": "{{base_url}}/events"
      }
    },
    {
      "name": "5. Se aktive alarmer og vælg første",
      "request": {
        "method": "GET",
        "header": [],
        "url": "{{base_url}}/alarms"
      },
      "event": [
        {
          "listen": "test",
          "script": {
            "type": "text/javascript",
            "exec": [
              "if (pm.response.code === 200) {",
              "  const alarms = pm.response.json();",
              "  if (alarms.length > 0) {",
              "    pm.collectionVariables.set(\"alarm_id\", String(alarms[0].id));",
              "  } else {",
              "    pm.collectionVariables.set(\"alarm_id\", \"\");",
              "  }",
              "}"
            ]
          }
        }
      ]
    },
    {
      "name": "6. Kvittér valgt alarm",
      "request": {
        "method": "PATCH",
        "header": [],
        "url": "{{base_url}}/alarms/{{alarm_id}}/acknowledge"
      },
      "event": [
        {
          "listen": "prerequest",
          "script": {
            "type": "text/javascript",
            "exec": [
              "if (!pm.collectionVariables.get(\"alarm_id\")) {",
              "  throw new Error(\"Kør først request 3 og derefter request 5 for at vælge en aktiv alarm.\");",
              "}"
            ]
          }
        }
      ]
    },
    {
      "name": "7. Se hele alarmhistorikken",
      "request": {
        "method": "GET",
        "header": [],
        "url": "{{base_url}}/alarms?status=all"
      }
    },
    {
      "name": "8. Prøv ugyldig måling (forvent 422)",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "url": "{{base_url}}/readings",
        "body": {
          "mode": "raw",
          "raw": "{\n  \"device_id\": \"WT-01\",\n  \"wind_speed\": -1\n}",
          "options": {
            "raw": {
              "language": "json"
            }
          }
        }
      }
    }
  ]
}
```

### 9.22. .vscode/settings.json

SQLTools-forbindelsen uden password. Tilpas lokale standarder, hvis gruppen vælger en anden port eller bruger.

```json
{
  "sqltools.connections": [
    {
      "name": "Intelligent IoT - MySQL (nyt login)",
      "driver": "MySQL",
      "server": "127.0.0.1",
      "port": 3306,
      "database": "intelligent_iot",
      "username": "iot_user",
      "mysqlOptions": {
        "ssl": false
      },
      "previewLimit": 50
    }
  ]
}
```

### 9.23. .vscode/extensions.json

Anbefaler SQLTools og MySQL-driveren. De er valgfrie databaseværktøjer og ikke nødvendige for containerdrift.

```json
{
  "recommendations": [
    "mtxr.sqltools",
    "mtxr.sqltools-driver-mysql"
  ]
}
```

## 10. Status og din læserækkefølge

Senest verificeret: lokal API/MySQL, alle tre tabeller i Workbench, 40 tests, persistens og grøn GitHub CI/CD med imagepublicering. Senest tilføjede demodata gav 36 målinger, 68 events og 16 alarmer. Tallene ændrer sig, når nye requests sendes; de er ikke et fast krav.

Stadig ikke dokumenteret: den foreslåede SQL-INSERT i del 7, gruppens faktiske adgang/pull på en anden computer og fysisk LAN-adgang. Der er ikke Azure, rate limiting, individuelle brugerkonti, pagination eller skemamigreringer. Events behandles synkront i samme API-handling og er ikke en ekstern eventbus.

Læs i denne rækkefølge:

1. Del 1–4: forklar højt, hvad der sker ved 20 og 30 m/s.
2. Find THRESHOLD og receive_reading i main.py.
3. Find de tre tabelklasser i database.py.
4. Send en måling og find samme id i Workbench.
5. Find services, ports og mysql_data i Compose.
6. Sammenlign GitHubs grønne trin med workflowfilen.
7. Afprøv INSERT med hjælp, før det kommer på video.
8. Øv programskift og manuskript uden at optage først.

Dette dokument er den eneste nye fil fra denne opgave. Selve appen, Docker-konfigurationen og databasen er ikke ændret. Ingen push er udført.
