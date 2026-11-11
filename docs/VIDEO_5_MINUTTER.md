# Video på cirka 5 minutter — klik og manuskript

## Åbn disse programmer i rækkefølge

1. Docker Desktop.
2. VS Code med Postman-panelet og projektet Intelligent-IoT-API.
3. MySQL Workbench, allerede forbundet til Intelligent IoT video.
4. Browser med to faner: http://localhost:8000/docs og https://github.com/Abdel047/Intelligent-IoT-API/actions/runs/43004914248.

Du behøver ikke SQLTools under optagelsen; Workbench er din databasevisning. Brug Alt+Tab til at skifte program. Øv skiftet før optagelsen.

## Gør klar uden at optage

### Docker

Åbn Containers. Klik > ved intelligent-iot, så api og mysql vises. Gateway er den ekstra HTTPS-indgang. Lad programmerne køre. Luk læringspanelet med X, så listen er tydelig.

### Postman i VS Code

Jeg har oprettet VIDEO.local.postman_collection.json med 6 requests og din lokale API-nøgle. Filen er privat og ignoreres af Git. Den delbare kopi postman/VIDEO.postman_collection.json indeholder ingen nøgle.

Importér den private fil før optagelsen: Postman-panelets Import → File → vælg VIDEO.local.postman_collection.json fra projektmappen. Collectionen hedder VIDEO - Intelligent IoT. Hvis import virker, er headers allerede sat op.

Hvis filimport fejler som tidligere, kan requests importeres enkeltvis via cURL. I VS Code-terminalen køres først .\scripts\copy_video_request.ps1 -Request Normal. I Postman vælger du Import → cURL → Ctrl+V → Enter. Gem requesten. Gentag med -Request Alarm, -Request Events og -Request Alarms. Scriptet viser aldrig nøglen, men udklipsholderen indeholder den, så dette gøres før optagelsen.

Kontrollér at requests findes i Postman. Jeg kan kontrollere filerne, men ikke se din Postman-kontos importerede requests. Brug navnene fra collectionen:

- 1 - Normal vind: 20 m/s
- 2 - Hoj vind: 30 m/s
- 3 - Vis domaenehaendelser
- 4 - Vis aktive alarmer
- 5 - Vis alle maalinger
- 6 - Kontroller API og database

POST-requests har Body → raw → JSON klar. Normal: VIDEO-WT-01 med 20 m/s. Høj vind: VIDEO-WT-02 med 30 m/s. Ved optagelsen holder du Body-fanen åben. Åbn ikke Headers, Authorization, collection-variabler, kodeeksport eller private JSON-filer.

Du kan sende øvemålingerne én gang før optagelsen for at afprøve knapperne. Hvert Send giver en ny måling; det er forventet. Ingen tidligere målinger skal slettes.

### Workbench

Følg docs/WORKBENCH_TRIN_FOR_TRIN.md for login før optagelsen. Den eksisterende database er intelligent_iot på 127.0.0.1:3306 med bruger iot_user.

Åbn docs/workbench_video.sql i SQL-editoren. Kør forespørgslerne én gang, så du ved, hvor resultatfelterne vises. Brug Run-menuen for en markeret SELECT. Lad editoren og resultattabellen være åbne. Skriptet er kun SELECT/SHOW/USE og sletter eller ændrer intet.

### GitHub

Log ind før optagelsen, og åbn den grønne kørsel direkte. Åbn jobbet Tests, Docker-build og MySQL-integration. Vis de grønne trin. Den grønne kørsel tilhører commit ad444b1 og bekræfter CI. LAN/CD-konfigurationen er nu også uploadet. Den nyere kørsel https://github.com/Abdel047/Intelligent-IoT-API/actions/runs/43013139741 for commit 68e04c0 har verificeret både CI og publicering af Docker-imaget; brug gerne denne nyere grønne kørsel i videoen.

### Skjul hemmeligheder

Luk .env, private Postman-JSON-filer og forbindelsesdialoger. Skjul VS Codes nederste Output/Terminal-panel med Ctrl+J, når du viser Postman. Luk udklipsholderhistorik og notifikationer. Vis kun requestens URL, Body og Response; selve URL'en indeholder ingen nøgle. Opret login før optagelsen, og sæt optagelsen på pause, hvis et passwordfelt dukker op.

## Selve optagelsen — læs replikkerne højt

### 0:00–0:40 — Docker og forretningsproblem

Klik: Vis Docker Desktop med intelligent-iot udvidet.

Sig:

“Mit projekt er en REST API til Intelligent IoT Solutions. Virksomheden overvåger blandt andet vindmøller. Målet er hurtigt at opdage høje vindhastigheder og oprette en alarm til driftspersonalet. Her kører API'et og MySQL som separate Docker-containere. MySQL bruger et permanent volume, så data ikke forsvinder ved genstart. Den ekstra gateway giver mulighed for HTTPS.”

### 0:40–1:00 — Swagger

Klik: Alt+Tab til browseren. Vælg fanen http://localhost:8000/docs. Vis endpointlisten uden at åbne Authorize.

Sig:

“FastAPI giver automatisk denne Swagger-dokumentation. Den beskriver mine endpoints til målinger, events og alarmer. Dataendpoints er beskyttet med en API-nøgle.”

### 1:00–1:45 — Normal måling i Postman

Klik: Alt+Tab til VS Code. Åbn Postman-panelet. Vælg 1 - Normal vind: 20 m/s. Vis Body og klik Send. Peg på 201 og anomaly_detected false.

Sig:

“Nu sender jeg en måling på 20 meter pr. sekund. Device-id fortæller, hvilken installation den kommer fra. API'et validerer input og gemmer målingen. Status 201 betyder, at den er oprettet. Anomaly detected er false, så der oprettes ingen alarm. Præcis 25 meter pr. sekund ville også være normal.”

### 1:45–2:30 — Måling med alarm

Klik: Vælg 2 - Hoj vind: 30 m/s. Vis Body og klik Send. Notér svarets id; det varierer fra gang til gang. Peg på anomaly_detected true.

Sig:

“Nu sender jeg 30 meter pr. sekund. Det er over grænsen på 25. Derfor er anomaly detected true. Systemet registrerer SensorValueReceived, AnomalyDetected og AlarmCreated. Det er en fast forretningsregel, ikke en AI-model, som forudsiger fejl.”

### 2:30–3:45 — Vis de samme data i MySQL Workbench

Klik: Alt+Tab til Workbench. Kør målings-SELECT fra workbench_video.sql igen. Den nye VIDEO-WT-02-række står øverst. Vis samme id og vindhastighed 30 som Postman-svaret. Kør derefter events-SELECT og alarm-SELECT.

Sig:

“Her ser vi data direkte i MySQL. Den nyeste måling har samme id som svaret i Postman. Events-tabellen viser de hændelser, som behandlingen har skabt. Reading-id knytter dem til målingen. Alarms-tabellen indeholder alarmen fra overskridelsen. En normal måling bliver også gemt, men giver ingen alarm. Måling, hændelser og alarm gemmes i én transaktion, så vi undgår delvist gemte forløb.”

Hvis du er tryg ved SQL: kør sidste SELECT i filen for at vise tre events og alarmen samlet for seneste VIDEO-WT-02. Ellers spring den over; de tre almindelige SELECTs er tilstrækkelige.

### 3:45–4:35 — Grøn CI på GitHub

Klik: Alt+Tab til browseren. Åbn GitHub Actions-fanen. Vis grønt resultat og trinnene Kør isolerede tests, Byg Docker-imaget og Kontrollér API, MySQL og data efter genstart.

Sig:

“GitHub Actions kontrollerer projektet automatisk ved push og pull requests. Denne kørsel er grøn. Den har kørt 40 tests, bygget Docker-imaget og startet API og MySQL i et separat testmiljø. Den kontrollerer også, at målinger, events og alarmer stadig findes efter genstart. Testmiljøet bruger sine egne hemmeligheder og ikke min lokale database.”

### 4:35–5:00 — Afrunding og begrænsninger

Klik: Bliv på det grønne resultat, eller vend tilbage til Workbench-tabellen.

Sig:

“Jeg har demonstreret input fra Postman, behandling i API'et og output gemt i en separat MySQL-database. Løsningen er en teknisk MVP til overvågning. Mulige forbedringer er bedre alarmregler, brugerroller og et permanent driftsmiljø. Adgang fra en anden fysisk enhed skal stadig demonstreres særskilt.”

## Hvis du også skal vise live genstart

Indsæt 30–45 sekunder før GitHub-delen og forkort introduktionen. I en tom VS Code-terminal køres docker compose restart api mysql. Vent på at http://localhost:8000/health svarer igen, og kør målings-SELECT i Workbench igen. De samme id'er skal stadig findes. Forbindelsen i Workbench kan skulle åbnes igen efter genstart; øv dette før optagelsen. Slet aldrig volumes.

Dette live-trin er valgfrit i den korte video; persistens er allerede verificeret i integrationstesten på GitHub. Sig kun, at du viser en live genstart, hvis du faktisk gør det.

## Hvis noget går galt

- 401 i Postman: stop optagelsen og ret API-nøglen privat.
- Connection refused: kontrollér Docker Desktop før næste forsøg.
- Tomt Workbench-resultat: kør SELECT igen. Sidste VIDEO-SELECT er tom, indtil VIDEO-WT-02 er sendt.
- Passworddialog: sæt optagelsen på pause og log ind uden at vise .env.
- Knapper ser anderledes ud i din Workbench-version: øv navigationen først og send et billede af SQL-editoren uden hemmeligheder, så vi kan tilpasse klikkene.

Videofilerne er senere uploadet efter godkendelse sammen med LAN/CD-ændringerne. Ingen eksisterende data er slettet.
