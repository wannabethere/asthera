-- Data Mart: external_exposure_risk_summary
-- Goal: Show attack surface breakdown by OS/software stack, business unit, and environment
-- Question: What are the total external exposures categorized by risk type, and what is their potential impact?
-- Generated: 20251120_111506

CREATE TABLE external_exposure_risk_summary AS SELECT e.risk_category, COUNT(DISTINCT e.exposure_id) AS total_exposures, SUM(e.potential_impact) AS total_potential_impact FROM external_exposure e GROUP BY e.risk_category;