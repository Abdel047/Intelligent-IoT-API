-- SQL-demo til den eksisterende MySQL-database.
-- Kør kun denne fil manuelt i MySQL Workbench.
-- Den indeholder INGEN aktiv COMMIT, DELETE, UPDATE eller ændring af tabeller.
-- Afslut en eventuel tidligere demotransaktion, før du kører filen igen.

USE intelligent_iot;

-- 1. Begynd en samlet handling. Behold samme forbindelse indtil afslutningen.
START TRANSACTION;

-- Unikt navn gør det nemt at finde netop denne test igen.
SET @demo_device_id = CONCAT('SQL-DEMO-', UUID());
SET @demo_created_at = UTC_TIMESTAMP(6);

-- 2. En normal måling: 20 er ikke over tærsklen på 25 m/s.
INSERT INTO sensor_readings
    (device_id, wind_speed, anomaly_detected, created_at)
VALUES
    (@demo_device_id, 20.0, FALSE, @demo_created_at);

-- Gem målingens id FØR eventet indsættes, da begge tabeller har egne id'er.
SET @demo_reading_id = LAST_INSERT_ID();

-- 3. Gem modtagelseshændelsen manuelt i samme transaktion.
-- event_data er SQL-kolonnen; det tilsvarende API-felt hedder payload.
INSERT INTO domain_events
    (event_type, reading_id, alarm_id, device_id, event_data, created_at)
VALUES
    ('SensorValueReceived', @demo_reading_id, NULL, @demo_device_id,
     JSON_OBJECT('device_id', @demo_device_id,
                 'wind_speed', 20.0,
                 'source', 'workbench_sql_demo'),
     @demo_created_at);

-- 4. Se målingen og eventet FØR du beslutter at gemme.
SELECT id, device_id, wind_speed, anomaly_detected, created_at
FROM sensor_readings
WHERE id = @demo_reading_id;

SELECT id, event_type, reading_id, alarm_id, device_id, event_data, created_at
FROM domain_events
WHERE reading_id = @demo_reading_id;

-- Forvent samme reading_id, én måling, ét event og nul alarmer.
SELECT @demo_reading_id AS find_dette_id_i_postman,
       @demo_device_id AS find_dette_device_id_i_postman,
       (SELECT COUNT(*) FROM sensor_readings WHERE id = @demo_reading_id) AS maalinger_forvent_1,
       (SELECT COUNT(*) FROM domain_events WHERE reading_id = @demo_reading_id) AS events_forvent_1,
       (SELECT COUNT(*) FROM alarms WHERE reading_id = @demo_reading_id) AS alarmer_forvent_0;

-- STOP HER. Kør ikke hele filen igen for at gemme.
-- Hvis ALT er korrekt: skriv COMMIT; som en NY kommando i SAMME forbindelse.
-- Hvis du fortryder, eller en sætning fejlede: skriv ROLLBACK; i stedet.
-- COMMIT og ROLLBACK er kun nævnt i kommentarer, så Run All ikke gemmer automatisk.
-- Efter COMMIT kan ROLLBACK ikke fortryde de gemte rækker.
