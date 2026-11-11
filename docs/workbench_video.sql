-- Intelligent IoT: videodemonstration i MySQL Workbench
-- Kun læsning. Filen opretter/ændrer/sletter ingen data.
USE intelligent_iot;

-- 1. Bekræft database og tabeller.
SELECT DATABASE() AS aktiv_database;
SHOW TABLES;

-- 2. Vis de nyeste målinger. 0 = normal, 1 = anomali.
SELECT id, device_id, wind_speed, anomaly_detected, created_at
FROM sensor_readings
ORDER BY id DESC
LIMIT 20;

-- 3. Vis hændelserne og deres tilknytning til en måling.
SELECT id, reading_id, device_id, event_type, event_data, created_at
FROM domain_events
ORDER BY id DESC
LIMIT 30;

-- 4. Vis alarmerne.
SELECT id, reading_id, device_id, message, status, created_at
FROM alarms
ORDER BY id DESC
LIMIT 20;

-- 5. Efter VIDEO-requesten fra Postman: vis hele dens forløb.
SELECT r.id AS reading_id, r.device_id, r.wind_speed,
       r.anomaly_detected, e.event_type, a.id AS alarm_id, a.status
FROM sensor_readings AS r
JOIN domain_events AS e ON e.reading_id = r.id
LEFT JOIN alarms AS a ON a.reading_id = r.id
WHERE r.id = (
    SELECT MAX(id) FROM sensor_readings WHERE device_id = 'VIDEO-WT-02'
)
ORDER BY e.id;
-- Sidste SELECT er tom indtil VIDEO-WT-02 er sendt. Det er forventet.
