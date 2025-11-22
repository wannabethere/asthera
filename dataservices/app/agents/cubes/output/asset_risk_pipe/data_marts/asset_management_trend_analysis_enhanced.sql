-- Enhanced Data Mart: asset_management_trend_analysis
-- Generated: 20251120_111506

CREATE TABLE asset_management_trend_analysis (
    asset_id INT NOT NULL,
    asset_type VARCHAR(50) NOT NULL,
    acquisition_date DATE NOT NULL,
    depreciation_value DECIMAL(10, 2) NOT NULL,
    total_risk_score DECIMAL(10, 2) NOT NULL,
    total_vulnerabilities INT NOT NULL,
    total_misconfigurations INT NOT NULL,
    total_external_exposures INT NOT NULL,
    total_identity_exposures INT NOT NULL,
    month DATE NOT NULL,
    risk_breach_likelihood DECIMAL(5, 4) GENERATED ALWAYS AS (total_risk_score / NULLIF(total_vulnerabilities, 0)) STORED,
    risk_breach_score DECIMAL(10, 2) GENERATED ALWAYS AS (total_risk_score * 0.1) STORED,
    CONSTRAINT pk_asset_id PRIMARY KEY (asset_id, month),
    CONSTRAINT chk_depreciation_value CHECK (depreciation_value >= 0),
    CONSTRAINT chk_acquisition_date CHECK (acquisition_date <= CURRENT_DATE),
    CONSTRAINT chk_total_risk_score CHECK (total_risk_score >= 0),
    CONSTRAINT chk_total_vulnerabilities CHECK (total_vulnerabilities >= 0),
    CONSTRAINT chk_total_misconfigurations CHECK (total_misconfigurations >= 0),
    CONSTRAINT chk_total_external_exposures CHECK (total_external_exposures >= 0),
    CONSTRAINT chk_total_identity_exposures CHECK (total_identity_exposures >= 0)
);

CREATE INDEX idx_asset_id ON asset_management_trend_analysis(asset_id);
CREATE INDEX idx_month ON asset_management_trend_analysis(month);

INSERT INTO asset_management_trend_analysis
SELECT
    a.asset_id,
    a.asset_type,
    a.acquisition_date,
    a.depreciation_value,
    SUM(v.risk_score) AS total_risk_score,
    COUNT(DISTINCT v.vulnerability_id) AS total_vulnerabilities,
    COUNT(DISTINCT m.misconfiguration_id) AS total_misconfigurations,
    COUNT(DISTINCT e.exposure_id) AS total_external_exposures,
    COUNT(DISTINCT i.identity_exposure_id) AS total_identity_exposures,
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * (n.n) AS month
FROM assets a
LEFT JOIN vulnerabilities v ON a.asset_id = v.asset_id
LEFT JOIN misconfigurations m ON a.asset_id = m.asset_id
LEFT JOIN external_exposure e ON a.asset_id = e.asset_id
LEFT JOIN identity_exposure i ON a.asset_id = i.asset_id
JOIN generate_series(0, 11) n ON TRUE
WHERE a.acquisition_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
GROUP BY a.asset_id, a.asset_type, a.acquisition_date, a.depreciation_value, month
ORDER BY month;