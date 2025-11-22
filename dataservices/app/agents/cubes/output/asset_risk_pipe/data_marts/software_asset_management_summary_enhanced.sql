-- Enhanced Data Mart: software_asset_management_summary
-- Generated: 20251120_111506

CREATE TABLE software_asset_management_summary (
    software_name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    total_devices INT NOT NULL DEFAULT 0,
    total_vulnerabilities INT NOT NULL DEFAULT 0,
    total_misconfigurations INT NOT NULL DEFAULT 0,
    business_unit VARCHAR(100),
    environment VARCHAR(50),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (software_name, version),
    CONSTRAINT chk_total_devices CHECK (total_devices >= 0),
    CONSTRAINT chk_total_vulnerabilities CHECK (total_vulnerabilities >= 0),
    CONSTRAINT chk_total_misconfigurations CHECK (total_misconfigurations >= 0)
);

CREATE INDEX idx_software_name ON software_asset_management_summary(software_name);
CREATE INDEX idx_version ON software_asset_management_summary(version);
CREATE INDEX idx_business_unit ON software_asset_management_summary(business_unit);
CREATE INDEX idx_environment ON software_asset_management_summary(environment);

INSERT INTO software_asset_management_summary (software_name, version, total_devices, total_vulnerabilities, total_misconfigurations, business_unit, environment)
SELECT 
    s.software_name, 
    s.version, 
    COUNT(DISTINCT s.device_id) AS total_devices, 
    COUNT(DISTINCT v.vulnerability_id) AS total_vulnerabilities, 
    COUNT(DISTINCT m.misconfiguration_id) AS total_misconfigurations,
    s.business_unit,
    s.environment
FROM 
    software_inventory s 
LEFT JOIN 
    vulnerabilities v ON s.software_id = v.software_id 
LEFT JOIN 
    misconfigurations m ON s.software_id = m.software_id 
GROUP BY 
    s.software_name, s.version, s.business_unit, s.environment;