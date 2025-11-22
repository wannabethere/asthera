-- Enhanced Data Mart: attack_surface_summary_by_os_software
-- Generated: 20251120_111506

CREATE TABLE attack_surface_summary_by_os_software (
    business_unit VARCHAR(100) NOT NULL,
    environment VARCHAR(50) NOT NULL,
    os VARCHAR(50) NOT NULL,
    software_stack VARCHAR(100) NOT NULL,
    total_assets INT NOT NULL DEFAULT 0,
    total_vulnerabilities INT NOT NULL DEFAULT 0,
    total_misconfigurations INT NOT NULL DEFAULT 0,
    total_exposures INT NOT NULL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (business_unit, environment, os, software_stack),
    CONSTRAINT chk_total_assets CHECK (total_assets >= 0),
    CONSTRAINT chk_total_vulnerabilities CHECK (total_vulnerabilities >= 0),
    CONSTRAINT chk_total_misconfigurations CHECK (total_misconfigurations >= 0),
    CONSTRAINT chk_total_exposures CHECK (total_exposures >= 0)
);

CREATE INDEX idx_business_unit ON attack_surface_summary_by_os_software (business_unit);
CREATE INDEX idx_environment ON attack_surface_summary_by_os_software (environment);
CREATE INDEX idx_os ON attack_surface_summary_by_os_software (os);
CREATE INDEX idx_software_stack ON attack_surface_summary_by_os_software (software_stack);

INSERT INTO attack_surface_summary_by_os_software (business_unit, environment, os, software_stack, total_assets, total_vulnerabilities, total_misconfigurations, total_exposures)
SELECT 
    a.business_unit, 
    a.environment, 
    a.os, 
    a.software_stack, 
    COUNT(DISTINCT a.asset_id) AS total_assets, 
    COUNT(DISTINCT v.vulnerability_id) AS total_vulnerabilities, 
    COUNT(DISTINCT m.misconfiguration_id) AS total_misconfigurations, 
    COUNT(DISTINCT e.exposure_id) AS total_exposures 
FROM 
    assets a 
LEFT JOIN 
    vulnerabilities v ON a.asset_id = v.asset_id 
LEFT JOIN 
    misconfigurations m ON a.asset_id = m.asset_id 
LEFT JOIN 
    external_exposure e ON a.asset_id = e.asset_id 
GROUP BY 
    a.business_unit, a.environment, a.os, a.software_stack;