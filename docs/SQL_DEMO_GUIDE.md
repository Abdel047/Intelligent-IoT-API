# SQL-demo: indsæt en normal måling, kontrollér og gem

Dette bruger dine eksisterende tabeller. API-koden ændres ikke. Scriptet er klargjort og kontrolleret mod modellerne, men er **ikke udført mod databasen**.

## 1. Åbn scriptet i Workbench

- Lad API og MySQL køre i Docker.
- Åbn din gemte Workbench-forbindelse til `intelligent_iot`.
- Åbn `docs/sql_demo_insert.sql` som SQL-script, eller kopiér indholdet til en ny SQL-fane.
- Brug en forbindelse uden andet ufærdigt arbejde. Afslut en tidligere demotransaktion før en gentagelse: en ny START TRANSACTION kan afslutte en allerede åben transaktion.

## 2. Kør demoen én gang

Klik **Run** for at udføre scriptet. Hvis noget fejler, stop og kør `ROLLBACK;` i samme forbindelse. Fortsæt ikke med at gemme efter en SQL-fejl.

Scriptet gør dette:

1. `START TRANSACTION` begynder en samlet handling.
2. Et unikt navn, der starter med `SQL-DEMO-`, oprettes.
3. `INSERT INTO sensor_readings` indsætter 20 m/s med `anomaly_detected = FALSE`.
4. `LAST_INSERT_ID()` gemmer målingens id.
5. `INSERT INTO domain_events` opretter præcis ét `SensorValueReceived` med samme `reading_id` og `device_id`.
6. SELECT viser begge rækker samt kontroltal.

Alle nødvendige felter er udfyldt eksplicit. Tidsstempler er UTC. `alarm_id` er NULL, fordi en normal måling ikke har en alarm.

Der er ingen aktiv COMMIT i filen. Selv om Workbench viser AUTO-COMMIT ON, starter `START TRANSACTION` denne eksplicitte transaktion, som du selv skal afslutte. Hold forbindelsen åben og undlad at starte en ny transaktion imens.

## 3. Kontrollér før du gemmer

Resultaterne skal vise:

| Felt | Forventet |
| --- | --- |
| wind_speed | 20 |
| anomaly_detected | 0/false |
| event_type | SensorValueReceived |
| reading_id | Samme som målingens id |
| alarm_id | NULL |
| maalinger_forvent_1 | 1 |
| events_forvent_1 | 1 |
| alarmer_forvent_0 | 0 |

Notér `find_dette_id_i_postman` og det unikke `device_id` fra sidste resultat. Dine id'er bliver ikke nødvendigvis de samme som i tidligere eksempler.

**Workbench kan se de foreløbige rækker i samme forbindelse. API'et skal først kunne se dem efter COMMIT.**

## 4. Gem ELLER fortryd

Hvis alle kontroller er korrekte, skriv dette som en separat kommando i **samme Workbench-forbindelse** og kør kun den:

```sql
COMMIT;
```

Hvis du fortryder eller der kom en fejl, kør i stedet:

```sql
ROLLBACK;
```

Vælg kun én af dem. Kør ikke hele demo-scriptet igen for at gemme. ROLLBACK før commit fortryder kun demotransaktionens nye rækker; eksisterende data ændres ikke. Det er normalt, at der kan komme huller i id-numrene efter rollback. Efter COMMIT kan ROLLBACK ikke fortryde handlingen.

## 5. Find samme måling i Postman

1. Vælg **GET**.
2. Brug `http://127.0.0.1:8000/readings` (eller din konfigurerede API-port, hvis den er ændret).
3. Behold din allerede opsatte API-nøgle som `X-API-Key` i headeren. Det er API_KEY fra .env, ikke databasepasswordet. Vis ikke nøglen i en optagelse.
4. Klik **Send**. Forvent **200 OK**.
5. Find det id eller unikke SQL-DEMO-navn, du noterede fra Workbench. I responsen skal vindhastigheden være 20 og `anomaly_detected` være false.
6. Valgfrit: GET `/events` og find eventet med samme `reading_id`. API'et viser JSON-data under `payload`, mens SQL-kolonnen hedder `event_data`.

API'et har ikke et filter `GET /readings/{id}` eller `?id=...`. Brug den eksisterende liste og find id'et i svaret.

Hvis du får 401, kontrollér API-nøglen privat. Hvis målingen ikke vises, kontrollér først at COMMIT lykkedes, at du har sendt en ny GET, og at API'et bruger samme MySQL-database. Ved ROLLBACK er det forventet, at målingen ikke findes.

## Vigtig forskel mellem SQL og API

Denne demo indsætter direkte i SQL. Den kører **ikke** Pydantic-validering eller API'ets alarmregel. Derfor bruger den en kendt normal værdi på 20 m/s og registrerer eventet eksplicit. `source = workbench_sql_demo` gør oprindelsen tydelig i eventets JSON-data.

Det demonstrerer SQL-skrivning og API-læsning af samme database, ikke et sensor-kald. Vis automatisk `SensorValueReceived → AnomalyDetected → AlarmCreated` separat med **POST /readings** og 30 m/s. Demoen ændrer ikke API'ets funktioner og opretter ingen nye tabeller.
