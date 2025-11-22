-- Enhanced Data Mart: asset_exposure_summary
-- Generated: 20251120_111506

CREATE TABLE asset_exposure_summary (
    asset_id INT NOT NULL,
    asset_name VARCHAR(255) NOT NULL,
    total_vulnerability_score DECIMAL(10, 2) DEFAULT 0.00,
    vulnerability_count INT DEFAULT 0,
    total_misconfigurations INT DEFAULT 0,
    total_external_exposure DECIMAL(10, 2) DEFAULT 0.00,
    exposure_score DECIMAL(10, 2) AS (total_vulnerability_score + total_misconfigurations + total_external_exposure) STORED,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_asset_id PRIMARY KEY (asset_id),
    CONSTRAINT chk_vulnerability_count CHECK (vulnerability_count >= 0),
    CONSTRAINT chk_total_vulnerability_score CHECK (total_vulnerability_score >= 0),
    CONSTRAINT chk_total_misconfigurations CHECK (total_misconfigurations >= 0),
    CONSTRAINT chk_total_external_exposure CHECK (total_external_exposure >= 0)
);

CREATE INDEX idx_asset_id ON asset_exposure_summary(asset_id);
CREATE INDEX idx_asset_name ON asset_exposure_summary(asset_name);
CREATE INDEX idx_last_updated ON asset_exposure_summary(last_updated);

INSERT INTO asset_exposure_summary (asset_id, asset_name, total_vulnerability_score, vulnerability_count, total_misconfigurations, total_external_exposure)
SELECT 
    a.asset_id, 
    a.asset_name, 
    COALESCE(SUM(v.severity_score), 0) AS total_vulnerability_score, 
    COUNT(DISTINCT v.vulnerability_id) AS vulnerability_count, 
    COALESCE(SUM(m.configuration_issues), 0) AS total_misconfigurations, 
    COALESCE(SUM(e.external_risk_score), 0) AS total_external_exposure 
FROM 
    assets a 
LEFT JOIN 
    vulnerabilities v ON a.asset_id = v.asset_id 
LEFT JOIN 
    misconfigurations m ON a.asset_id = m.asset_id 
LEFT JOIN 
    external_exposure e ON a.asset_id = e.asset_id 
GROUP BY 
    a.asset_id, a.asset_name;