-- Enhanced Data Mart: identity_exposure_summary
-- Generated: 20251120_111506

CREATE TABLE identity_exposure_summary (
    identity_id UUID NOT NULL,
    total_exposure_incidents INT NOT NULL CHECK (total_exposure_incidents >= 0),
    average_severity DECIMAL(3, 2) CHECK (average_severity >= 0 AND average_severity <= 10),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (identity_id)
);

CREATE INDEX idx_identity_exposure ON identity_exposure_summary (identity_id);
CREATE INDEX idx_last_updated ON identity_exposure_summary (last_updated);

INSERT INTO identity_exposure_summary (identity_id, total_exposure_incidents, average_severity)
SELECT 
    i.identity_id, 
    COUNT(i.exposure_id) AS total_exposure_incidents, 
    AVG(i.severity_level) AS average_severity 
FROM 
    identity_exposure i 
GROUP BY 
    i.identity_id;