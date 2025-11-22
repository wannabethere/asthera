-- Enhanced Data Mart: software_asset_usage_summary
-- Generated: 20251120_111506

CREATE TABLE software_asset_usage_summary (
    software_id INT NOT NULL,
    software_name VARCHAR(255) NOT NULL,
    total_devices_used INT NOT NULL,
    total_usage_hours DECIMAL(10, 2) NOT NULL,
    exposure_score DECIMAL(10, 2) GENERATED ALWAYS AS (CASE WHEN total_usage_hours > 0 THEN total_devices_used / total_usage_hours ELSE 0 END) STORED,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (software_id),
    CONSTRAINT chk_usage_hours CHECK (total_usage_hours >= 0),
    CONSTRAINT chk_devices_used CHECK (total_devices_used >= 0)
);

CREATE INDEX idx_software_name ON software_asset_usage_summary (software_name);
CREATE INDEX idx_total_usage_hours ON software_asset_usage_summary (total_usage_hours);

INSERT INTO software_asset_usage_summary (software_id, software_name, total_devices_used, total_usage_hours)
SELECT 
    s.software_id, 
    s.software_name, 
    COUNT(DISTINCT s.device_id) AS total_devices_used, 
    SUM(s.usage_hours) AS total_usage_hours 
FROM 
    software_inventory s 
GROUP BY 
    s.software_id, 
    s.software_name;