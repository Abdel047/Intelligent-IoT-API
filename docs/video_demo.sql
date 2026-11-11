-- Kun læsning. Kør efter de to VIDEO-målinger er sendt fra Postman.
USE intelligent_iot;
SELECT id, device_id, wind_speed, anomaly_detected, created_at
FROM sensor_readings
WHERE device_id IN ('VIDEO-WT-01', 'VIDEO-WT-02')
ORDER BY id DESC;

SELECT id, reading_id, device_id, event_type, created_at
FROM domain_events
WHERE device_id IN ('VIDEO-WT-01', 'VIDEO-WT-02')
ORDER BY id DESC;

SELECT id, reading_id, device_id, message, status, created_at
FROM alarms
WHERE device_id IN ('VIDEO-WT-01', 'VIDEO-WT-02')
ORDER BY id DESC;
