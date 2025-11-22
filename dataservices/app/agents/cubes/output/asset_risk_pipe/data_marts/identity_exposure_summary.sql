-- Data Mart: identity_exposure_summary
-- Goal: Create exposure score aggregations for dashboard visualizations
-- Question: How many identity exposure incidents have occurred for each identity, and what is the average severity of these incidents?
-- Generated: 20251120_111506

CREATE TABLE identity_exposure_summary AS SELECT i.identity_id, COUNT(i.exposure_id) AS total_exposure_incidents, AVG(i.severity_level) AS average_severity FROM identity_exposure i GROUP BY i.identity_id;