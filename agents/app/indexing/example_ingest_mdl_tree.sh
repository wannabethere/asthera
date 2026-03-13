#!/bin/bash
# Example script for running ingest_mdl_tree from command line

# Navigate to the genieml directory
cd "$(dirname "$0")/../.." || exit 1

# Example 1: Basic usage (project_id will be read from project_metadata.json)
python -m agents.app.indexing.project_reader_mdl_tree \
    --mdl-root "/Users/sameerm/ComplianceSpark/cornerstone_mdls" \
    --collection-prefix "csod_"

# Example 2: With explicit project-id (overrides project_metadata.json)
python -m agents.app.indexing.project_reader_mdl_tree \
    --mdl-root "/Users/sameerm/ComplianceSpark/cornerstone_mdls" \
    --collection-prefix "csod_" \
    --project-id "csod_project"

# Example 3: With preview mode (doesn't write to ChromaDB, just collects preview data)
python -m agents.app.indexing.project_reader_mdl_tree \
    --mdl-root "/Users/sameerm/ComplianceSpark/cornerstone_mdls" \
    --collection-prefix "csod_" \
    --preview

# Example 4: With custom base path
python -m agents.app.indexing.project_reader_mdl_tree \
    --mdl-root "/Users/sameerm/ComplianceSpark/cornerstone_mdls" \
    --collection-prefix "csod_" \
    --base-path "/path/to/custom/base"
