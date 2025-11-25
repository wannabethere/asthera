-- Data Mart: identity_exposure_summary
-- Goal: Create exposure score aggregations for dashboard visualizations
-- Question: How many instances of sensitive identity information exposure are there for each identity?
-- Generated: 20251124_084146

CREATE TABLE identity_exposure_summary AS SELECT ie.identity_id, COUNT(ie.exposure_id) AS total_exposures FROM identity_exposure ie GROUP BY ie.identity_id;