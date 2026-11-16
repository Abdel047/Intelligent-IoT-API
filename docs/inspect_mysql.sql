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
