# Åbn den eksisterende database i MySQL Workbench

Ingen ny database skal oprettes. MySQL kører allerede i Docker på din computer.

## Før optagelsen

1. Lad Docker Desktop køre. mysql skal være healthy.
2. Åbn MySQL Workbench fra Windows Start-menuen.
3. På Home: klik + ved Database Connections.
4. Udfyld Caption = Intelligent IoT video, Connection Method = mysql, User Name = iot_user, Host Name or IP Address = 127.0.0.1, Port = 3306, Default Schema = intelligent_iot.
5. Klik Test Connection. Hvis der spørges om password, brug kun værdien efter MYSQL_PASSWORD= i .env. Det er databasepasswordet, ikke API_KEY og ikke MYSQL_ROOT_PASSWORD. Sæt det i passwordfeltet, aldrig i SQL-editoren.
6. Ved en vellykket test: klik OK for at gemme forbindelsen. Åbn derefter forbindelsen fra Home/Connections.
7. Find intelligent_iot i databaseoversigten og udvid Tables. Her skal sensor_readings, domain_events og alarms findes. Opdatér oversigten, hvis listen endnu er tom.
8. Åbn en SQL-editor eller SQL-fane i forbindelsen. Åbn docs/workbench_video.sql som SQL-script, eller kopiér dens SELECT-forespørgsler ind. Brug programmets Run-menu til at køre en markeret forespørgsel. Vis kun én SELECT ad gangen under videoen.

Menuerne i Workbench 26.10 kan se anderledes ud end ældre vejledninger. Ved tvivl: tag et billede af forbindelsesvinduet eller SQL-editoren uden password, før du klikker videre.

## Kontrollér en ny måling fra Postman

Send VIDEO-WT-02 med wind_speed 30 via POST /readings. Notér svarets id uden at vise Authorization/Headers. Skift tilbage til Workbench, og kør SELECT fra sensor_readings igen. Nyeste række står øverst. Kør derefter events- og alarmforespørgslerne. reading_id skal være det samme som svarets id.

Sidste SELECT i workbench_video.sql samler hele forløbet for den seneste VIDEO-WT-02-måling. Den er tom, før denne request er sendt; det er normalt. En normal VIDEO-WT-01-måling på 20 m/s giver kun SensorValueReceived og ingen alarm.

## Undgå hemmeligheder på video

Opret og test forbindelsen før optagelsen. Luk .env og private JSON-filer. Vis ikke forbindelsesindstillinger eller passworddialoger under optagelsen. Hvis login spørges igen under optagelsen, sæt optagelsen på pause og fortsæt først efter login.

Status: TCP/SQL-forbindelsen med iot_user er verificeret fra terminalen. Den grafiske Workbench-forbindelse skal stadig bekræftes af dig. Det er den samme eksisterende database som SQLTools viser.
