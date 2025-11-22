-- Enhanced Data Mart: external_exposure_risk_summary
-- Generated: 20251120_111506

CREATE TABLE external_exposure_risk_summary (
    risk_category VARCHAR(255) NOT NULL,
    total_exposures INT NOT NULL,
    total_potential_impact DECIMAL(18, 2) NOT NULL,
    os_software_stack VARCHAR(255),
    business_unit VARCHAR(255),
    environment VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (risk_category, os_software_stack, business_unit, environment),
    CONSTRAINT chk_total_exposures CHECK (total_exposures >= 0),
    CONSTRAINT chk_total_potential_impact CHECK (total_potential_impact >= 0)
);

CREATE INDEX idx_risk_category ON external_exposure_risk_summary (risk_category);
CREATE INDEX idx_os_software_stack ON external_exposure_risk_summary (os_software_stack);
CREATE INDEX idx_business_unit ON external_exposure_risk_summary (business_unit);
CREATE INDEX idx_environment ON external_exposure_risk_summary (environment);

INSERT INTO external_exposure_risk_summary (risk_category, total_exposures, total_potential_impact, os_software_stack, business_unit, environment)
SELECT 
    e.risk_category, 
    COUNT(DISTINCT e.exposure_id) AS total_exposures, 
    SUM(e.potential_impact) AS total_potential_impact,
    e.os_software_stack,
    e.business_unit,
    e.environment
FROM 
    external_exposure e 
GROUP BY 
    e.risk_category, e.os_software_stack, e.business_unit, e.environment;