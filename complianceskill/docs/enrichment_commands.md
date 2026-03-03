# Step 1: Enrich all control taxonomies (runs in background)
python -m app.ingestion.enrich_control_taxonomy \
    --yaml-dir ../../data/cvedata/risk_control_yaml \
    --output-dir control_taxonomy_enriched \
    --batch-size 10 \
    --max-workers 3

# Step 2: Enrich all metrics registries (runs in background)
python -m app.ingestion.enrich_metric_registry \
    --input-dir path/to/dashboard_agent/registry_config \
    --output-dir metrics_registry_enriched \
    --method hybrid \
    --control-taxonomy control_taxonomy_enriched/soc2_enriched.json \
    --max-workers 3

python -m app.ingestion.enrich_metric_registry \
    --input-dir path/to/metrics_registries \
    --output-dir path/to/enriched \
    --method hybrid \
    --control-taxonomy-dir control_taxonomy_enriched \
    --max-workers 3

# Single file with directory (auto-matches framework)
python -m app.ingestion.enrich_metric_registry \
    --input metrics_registry.json \
    --output metrics_registry_enriched.json \
    --method hybrid \
    --control-taxonomy-dir control_taxonomy_enriched

# Still supports single file path
python -m app.ingestion.enrich_metric_registry \
    --input metrics_registry.json \
    --output metrics_registry_enriched.json \
    --method hybrid \
    --control-taxonomy control_taxonomy_enriched/soc2_enriched.json



# Ingest regular metrics files
python -m app.ingestion.ingest_metrics_registry --metrics-dir /path/to/metrics

# Ingest enriched metrics files
python -m app.ingestion.ingest_metrics_registry --metrics-dir /path/to/enriched --enriched

# Ingest single enriched file
python -m app.ingestion.ingest_metrics_registry --metrics-file metrics_enriched.json --enriched


# Ingest all enriched taxonomy files from a directory
python -m app.ingestion.ingest_control_taxonomy \
    --taxonomy-dir data/cvedata/control_taxonomy_enriched

# Ingest a single file
python -m app.ingestion.ingest_control_taxonomy \
    --taxonomy-file data/cvedata/control_taxonomy_enriched/hipaa_enriched.json

# Reinitialize collection (destructive - deletes existing data)
python -m app.ingestion.ingest_control_taxonomy \
    --taxonomy-dir data/cvedata/control_taxonomy_enriched \
    --reinit-qdrant

# Use custom collection name
python -m app.ingestion.ingest_control_taxonomy \
    --taxonomy-dir data/cvedata/control_taxonomy_enriched \
    --collection-name my_control_taxonomy


    # Run all LEEN DT workflow tests
python tests/test_detection_triage_workflow_leen.py --test all

# Run specific LEEN DT workflow test
python tests/test_detection_triage_workflow_leen.py --test use_case_1

# Run all LEEN dashboard tests
python tests/test_compliance_risk_map_dashboard_leen.py --test all

# Run specific LEEN dashboard test
python tests/test_compliance_risk_map_dashboard_leen.py --test hipaa_risk