-- Data Mart: external_exposure_summary
-- Goal: Show attack surface breakdown by OS/software stack, business unit, and environment
-- Question: What are the total external exposures categorized by business unit and environment?
-- Generated: 20251124_084146

CREATE TABLE external_exposure_summary AS SELECT e.business_unit, e.environment, e.exposure_type, COUNT(DISTINCT e.exposure_id) AS total_exposures FROM external_exposure e GROUP BY e.business_unit, e.environment, e.exposure_type;