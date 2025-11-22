-- Enhanced Data Mart: software_asset_management_trend_analysis
-- Generated: 20251120_111506

CREATE TABLE software_asset_management_trend_analysis (
    software_id INT NOT NULL,
    software_name VARCHAR(255) NOT NULL,
    license_type VARCHAR(50) NOT NULL,
    total_devices INT NOT NULL DEFAULT 0,
    total_misconfigurations INT NOT NULL DEFAULT 0,
    total_external_exposures INT NOT NULL DEFAULT 0,
    month DATE NOT NULL,
    breach_risk_score DECIMAL(5, 2) GENERATED ALWAYS AS (
        CASE 
            WHEN total_misconfigurations > 10 THEN 1.0
            WHEN total_external_exposures > 5 THEN 0.75
            ELSE 0.5
        END
    ) STORED,
    likelihood_score DECIMAL(5, 2) GENERATED ALWAYS AS (
        CASE 
            WHEN total_devices > 100 THEN 0.9
            WHEN total_devices BETWEEN 50 AND 100 THEN 0.7
            ELSE 0.3
        END
    ) STORED,
    CONSTRAINT pk_software_asset PRIMARY KEY (software_id, month),
    CONSTRAINT chk_total_devices CHECK (total_devices >= 0),
    CONSTRAINT chk_total_misconfigurations CHECK (total_misconfigurations >= 0),
    CONSTRAINT chk_total_external_exposures CHECK (total_external_exposures >= 0)
);

CREATE INDEX idx_software_id ON software_asset_management_trend_analysis(software_id);
CREATE INDEX idx_month ON software_asset_management_trend_analysis(month);

INSERT INTO software_asset_management_trend_analysis
SELECT
    s.software_id,
    s.software_name,
    s.license_type,
    COUNT(DISTINCT s.device_id) AS total_devices,
    SUM(m.misconfiguration_count) AS total_misconfigurations,
    COUNT(DISTINCT e.exposure_id) AS total_external_exposures,
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * (n.n) AS month
FROM software_inventory s
LEFT JOIN misconfigurations m ON s.software_id = m.software_id
LEFT JOIN external_exposure e ON s.software_id = e.software_id
JOIN generate_series(0, 11) n ON TRUE
WHERE s.installation_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
GROUP BY s.software_id, s.software_name, s.license_type, month
ORDER BY month;