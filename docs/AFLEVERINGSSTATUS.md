# Afleveringsstatus og sidste kontrol

## Verificeret på værtscomputeren

- REST API, Pydantic-validering og tærskel over 25 m/s.
- MySQL i separat container med permanent volume.
- Målinger, SensorValueReceived, AnomalyDetected og AlarmCreated i SQL.
- Kvittering af alarmer og AlarmAcknowledged (isolerede automatiske tests).
- API og MySQL overlever genstart med bevarede data.
- 40 pytest-tests består.
- CI for commit ad444b1 er grøn på GitHub.
- SQLTools viser MySQL-tabeller i VS Code.
- HTTPS-gateway svarer med valideret certifikat på den aktuelle LAN-adresse.
- HTTPS uden nøgle afvises; POST med nøgle opretter måling, events og alarm.
- Windows-firewallregel tillader kun LAN-HTTPS-porten fra LocalSubnet.
- MySQL og ukrypteret API er kun tilgængelige via localhost.

## Mangler en kontrol fra dig

### A. En anden computer eller IoT-enhed

1. Brug samme betroede lokale netværk som værtscomputeren.
2. Overfør `certs/iot-local-root.crt` til testcomputeren. Det er et offentligt certifikat; del aldrig CA-private nøgler eller hele Docker-volumen.
3. I Postman: Settings → Certificates → CA Certificates. Tilføj filen, og behold SSL/certifikatkontrol slået til.
4. Brug HTTPS-adressen fra `scripts/start_lan.ps1`, eksempelvis `https://192.168.205.222:8443/health`. Forvent 200 og database connected.
5. POST til samme baseadresse plus `/readings`. Brug `X-API-Key` og body `{"device_id":"DEMO-ANDEN-PC","wind_speed":30}`. Nøglen gives privat til demonstratøren.
6. Kontrollér den nye måling og alarm i SQLTools/Workbench på værtscomputeren.

Gem et billede af svaret uden at vise API-nøglen. Hvis enhederne ikke kan nå hinanden, kan Wi-Fi-netværket have klientisolering. Prøv et betroet privat netværk; åbn ikke routerporte som løsning.

### B. MySQL Workbench

Programmet er installeret, men selve Workbench-visningen er endnu ikke dokumenteret. SQLTools virker allerede.

1. Klik + ved Database Connections.
2. Caption: Intelligent IoT lokal; Connection Method: mysql.
3. User Name: iot_user; Host: 127.0.0.1; Port: 3306; Default Schema: intelligent_iot. Brug .env-værdierne, hvis du har ændret standarderne.
4. Klik Test Connection, og indsæt kun værdien efter MYSQL_PASSWORD= i passwordfeltet. Det aktuelle password ligger i .env; brug ikke et tidligere delt password.
5. Gem og åbn forbindelsen. Kør forespørgslerne fra docs/inspect_mysql.sql.
6. Vis resultaterne for sensor_readings, domain_events og alarms. Tag et billede uden passwords.

## CD og upload

Den nye workflow leverer automatisk et image til GHCR efter bestået CI på main. Dette er Continuous Delivery. Den del er endnu ikke uploadet/kørt og må ikke beskrives som verificeret. Lokal deployment med scripts/deploy_local.ps1 -Lan er verificeret. Automatisk deployment til et permanent miljø er ikke implementeret; hvis underviseren kræver dette, skal driftsmål afklares.

Næste GitHub-upload kræver godkendelse. Den må ikke omfatte .env, certifikatmapper, sessionfiler eller lokale databaser. Den gamle nøgle i historikken er tidligere udskiftet; gamle commits er ikke omskrevet.
