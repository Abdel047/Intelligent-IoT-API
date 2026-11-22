# Afleveringsstatus — 22. november 2026

## Samlet status: BESTÅET for den lokale eksamens-MVP

| Kontrolpunkt | Status | Resultat |
| --- | --- | --- |
| Frisk backup og fuld MySQL-restore | BESTÅET | Alle 777 målinger, 843 hændelser og 32 alarmer genskabt i en separat MySQL 8.4-container. Alle felter, relationer, danske tegn og FLOAT32-værdier stemmer. |
| Navnemigrering i den rigtige database | BESTÅET | 156 målinger, 175 hændelser og 9 alarmer omdøbt; 156 JSON-payloads opdateret. Kun de to godkendte sensorer er ændret. |
| Bevarelse af oprindelige data | BESTÅET | Alle oprindelige rækker er sammenlignet med backupgrundlaget. ID'er, tider, værdier og relationer er bevaret. SIM-WIND og øvrige installationer er uændrede. |
| Automatiske tests | BESTÅET | 64 pytest-tests, inklusive rollback, JSON, navnekollision, idempotens, restore-readiness, UTF-8, FLOAT32, alarmregel, API-adgang og dashboard. |
| Postman-collection → FastAPI | BESTÅET | Den delbare collection kørt med Newman 6.2.1: 9 requests, 5 assertions, 0 fejl. Dette er en automatisk Postman-collection-kørsel, ikke klik i Postman-appen. |
| Normal måling 20 m/s | BESTÅET | VINDMOELLE-01, reading_id 778: gemt med SensorValueReceived, ingen alarm. |
| Høj måling 30 m/s | BESTÅET | VINDMOELLE-02, reading_id 779: SensorValueReceived → AnomalyDetected → AlarmCreated. Alarm 33 tilhører målingen. |
| Alarmkvittering | BESTÅET | Kun den nye testalarm 33 er kvitteret; AlarmAcknowledged oprettet. Ingen gamle alarmer ændret af testen. |
| MySQL og SELECT-forespørgsler | BESTÅET | Samme reading_id'er, hændelser og alarm fundet direkte i MySQL. docs/inspect_mysql.sql har SELECTs til de nye navne. |
| Ny grafisk Workbench-kontrol | IKKE VERIFICERET | Data og forbindelsen er verificeret via SQL; Workbench-vinduet er ikke automatisk betjent. Åbn de opdaterede SELECTs under demonstrationen. |
| Dashboard mod rigtig MySQL | BESTÅET | Login, Online-status, begge vindmøllenavne, graf/perioder, måling 778/779, hændelsesforløb og kvitteret alarm verificeret i Edge. Ingen JavaScript-fejl; mobilbredde kontrolleret. |
| Docker Compose og lokal build | BESTÅET | Build/start og health checks virker. API og MySQL kommunikerer. Databaseport og lokal API-port bindes kun til localhost. |
| Persistens ved Docker-genstart | BESTÅET | API og MySQL genstartet normalt. Fingerprint af alle rækker er identisk før/efter. Ingen volumes slettet. |
| Data efter alle tests | BESTÅET | 779 målinger, 848 hændelser og 33 alarmer: præcis 2 nye målinger, 5 nye events inklusive kvittering og 1 ny alarm. |
| API-adgang og hemmeligheder | BESTÅET | X-API-Key, dashboard-session og CSRF dækkes af tests. Private Newman-filer er fjernet efter testen; backup/logs ligger uden for Git. Hemmelighedskontrol før commit er bestået. |
| Repository og branch | BESTÅET | Abdel047/Intelligent-IoT-API, main. Den lokale usporede .vscode/launch.json holdes uden for commit. |
| GitHub Actions / GHCR for navneændringen | BESTÅET | Test/build, MySQL-integration, genstart og CD er grønne. Commit-tag, latest og revision-label er kontrolleret. Se publiceringen nedenfor. |
| Offentlig deployment / anden fysisk computer | IKKE VERIFICERET | GHCR publicerer et image; det er ikke en offentlig API-server. Lokal løsning er kontrolleret. |

## Backup og databevarelse

Frisk anvendt backup uden for repositoryet:
`C:\Users\Bruger\.codex\backups\Intelligent-IoT-API\before-device-rename-20261122T165644825401Z.sql.gz`

SHA256: `d015b8594097dbec9e0c7e80c40b91c1e6ed1e698829d6664eeaf4e3600a228b`.

Samme mappe indeholder restore-log og migrationskvittering. Backupen er faktisk importeret i en separat MySQL-container før navnemigreringen. Testcontaineren brugte midlertidig lagring uden eksisterende volumes og uden publicerede porte; kun denne testcontainer blev fjernet bagefter.

Navnene blev ændret fra AFLEVERING-01/02 til VINDMOELLE-01/02 i én transaktion. Alle rækker blev efterkontrolleret mod den forventede transformation inden COMMIT. Gamle navne findes fortsat i selve migrationsmappingen og testfixtures, fordi de skal kunne migrere og teste den gamle version. De vises ikke længere som sensornavne i den eksisterende database eller de aktuelle eksempler.

Den faste simulationsmarkør `aflevering-7d-v1` bevares som historisk batch-ID for at undgå dubletter. Det er ikke et sensornavn. SIM-WIND-01/02/03 bevares som separate historiske, simulerede installationer.

## Forklaring på den rettede restorefejl

Den gamle test brugte mysqladmin ping som klarsignal. Den kommando returnerede 0, selv om root-login endnu ikke var klar, og SQL-importen fik ERROR 1045: Access denied. Containerloggen og den gentagne fejl er gemt lokalt. Testen venter nu på et autentificeret SELECT 1 over TCP i den forventede database.

Verifikationen bruger desuden eksplicit utf8mb4, så danske alarmtekster kan læses, og præcis sammenligning af lagrede FLOAT32-bits. MySQL JSON_OBJECT kan vise flere decimaler end PyMySQL, selv når de lagrede bits er identiske. Ingen databaseværdier blev afrundet eller ændret for at få testen til at bestå.

## Øvrige rettelser og begrænsninger

- Postman vælger alarmen via den returnerede 30 m/s-målings reading_id frem for den første gamle alarm. Gamle testvariabler nulstilles før en ny høj måling.
- Dashboardets API-kort skifter også til Offline ved forbindelsestab og tilbage til Online ved genetablering.
- Swagger, dashboard, simulationsscript, Postman-eksempler, tests, README og relevante SQL/dokumenter bruger de nye sensornavne.
- Perioden 7 dage er rullende: gamle punkter falder naturligt ud. Vælg Alle for hele historikken.
- Én ikke-blokerende deprecation-advarsel om httpx i testklienten består; der er ikke ændret afhængigheder blot for at skjule den.
- Dashboardet er regelbaseret overvågning med simulerede data, ikke en AI-model der forudsiger maskinfejl.
- Gruppemedlemmers individuelle GitHub/GHCR-adgang og LAN-adgang er ikke nytestet.

## Klar til video

Den lokale løsning er klar til en cirka fem minutter lang demo med Docker → Postman 20/30 → MySQL SELECT → dashboard → GitHub Actions. Vis ikke .env, passwords eller API-nøgler. Workbench og Postman kan åbnes før optagelsen; indsæt adgangsoplysninger privat.

## Verificeret funktionel publicering

- Funktionelt release-commit: `a5576f35a22ce7b216a24044fbf13a940cfee812`.
- Grøn GitHub Actions-kørsel: [45047181205](https://github.com/Abdel047/Intelligent-IoT-API/actions/runs/45047181205). Begge jobs er completed/success.
- Image: `ghcr.io/abdel047/intelligent-iot-api:a5576f35a22ce7b216a24044fbf13a940cfee812`.
- SHA-tag og latest havde identiske manifests ved kontrollen. Imagets org.opencontainers.image.revision matcher præcist release-commit.
- Alle syv runtime-/afhængighedsfiler er sammenlignet mellem kildekoden, den kørende lokale API-container og det hentede GHCR-image; de matcher med normaliserede linjeskift.
- Rapporten afsluttes i et separat dokumentationscommit uden ændringer i runtime-koden. Hvert push på main testes og publiceres af samme workflow; den nyeste leverings konkrete SHA fremgår af repositoryets Actions og imagets revision-label. Et senere dokumentationscommit ændrer ikke ovenstående funktionelle release eller datamigreringen.
- GHCR er distribution af Docker-images, ikke deployment til en offentlig server.
