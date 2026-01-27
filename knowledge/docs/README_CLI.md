# Compliance Document Indexing CLI

CLI tool for indexing compliance documents (SOC2 controls, policies, risk controls) with flags for selective indexing and preview mode.

## Usage

### Preview Mode (Recommended First Step)

Preview mode saves documents to files instead of indexing in the database. This allows you to review the extracted data before committing to the vector database.

```bash
# Preview policies only
python -m indexing_cli.index_compliance \
    --index-policies \
    --policy-pdf path/to/Full\ Policy\ Packet.pdf \
    --preview \
    --preview-dir indexing_preview

# Preview risk controls only
python -m indexing_cli.index_compliance \
    --index-risk-controls \
    --risk-controls-excel path/to/Risk\ and\ Controls.xlsx \
    --preview

# Preview SOC2 controls only
python -m indexing_cli.index_compliance \
    --index-soc2 \
    --soc2-pdf path/to/SOC2_Controls.pdf \
    --preview

# Preview all document types (comprehensive)
python -m indexing_cli.index_compliance \
    --comprehensive \
    --policy-pdf path/to/Full\ Policy\ Packet.pdf \
    --risk-controls-excel path/to/Risk\ and\ Controls.xlsx \
    --soc2-pdf path/to/SOC2_Controls.pdf \
    --preview
```

### Index to Database

After reviewing the preview files and confirming everything looks good, index to the database:

```bash
# Index policies to database
python -m indexing_cli.index_compliance \
    --index-policies \
    --policy-pdf path/to/Full\ Policy\ Packet.pdf

# Index all document types to database
python -m indexing_cli.index_compliance \
    --comprehensive \
    --policy-pdf path/to/Full\ Policy\ Packet.pdf \
    --risk-controls-excel path/to/Risk\ and\ Controls.xlsx \
    --soc2-pdf path/to/SOC2_Controls.pdf
```

## Flags

### Document Type Flags

- `--index-policies`: Index policy documents (requires `--policy-pdf`)
- `--index-risk-controls`: Index risk controls (requires `--risk-controls-excel`)
- `--index-soc2`: Index SOC2 controls (requires `--soc2-pdf` or `--soc2-excel`)
- `--comprehensive`: Index all document types (sets all flags to True)

### File Path Arguments

- `--policy-pdf`: Path to policy PDF file
- `--risk-controls-excel`: Path to risk controls Excel file
- `--soc2-pdf`: Path to SOC2 controls PDF file
- `--soc2-excel`: Path to SOC2 controls Excel file

### Options

- `--preview`: Enable preview mode (saves to files instead of database)
- `--preview-dir`: Directory for preview files (default: `indexing_preview`)
- `--domain`: Domain filter (default: `compliance`)
- `--vector-store`: Vector store type - `chroma` or `qdrant` (default: `chroma`)

## Preview Files

When using `--preview`, files are saved to the preview directory with the following structure:

```
indexing_preview/
├── policy_documents/
│   ├── policy_documents_20240101_120000_compliance_Policy.json
│   └── policy_documents_summary_20240101_120000.txt
├── risk_controls/
│   ├── risk_controls_20240101_120000_compliance_Risk_Management.json
│   └── risk_controls_summary_20240101_120000.txt
└── soc2_controls/
    ├── soc2_controls_20240101_120000_compliance_SOC2.json
    └── soc2_controls_summary_20240101_120000.txt
```

Each JSON file contains:
- Metadata about the indexing run
- All documents with their content and metadata
- Extraction results from pipelines

The summary files provide a human-readable overview.

## Examples

### Step 1: Preview Everything

```bash
python -m indexing_cli.index_compliance \
    --comprehensive \
    --policy-pdf examples/Full\ Policy\ Packet.pdf \
    --risk-controls-excel examples/Risk\ and\ Controls.xlsx \
    --preview
```

### Step 2: Review Preview Files

Check the files in `indexing_preview/` to verify:
- Documents are extracted correctly
- Metadata is accurate
- Extraction pipelines are working as expected

### Step 3: Index to Database

Once satisfied with the preview:

```bash
python -m indexing_cli.index_compliance \
    --comprehensive \
    --policy-pdf examples/Full\ Policy\ Packet.pdf \
    --risk-controls-excel examples/Risk\ and\ Controls.xlsx
```

## Programmatic Usage

You can also use the service programmatically:

```python
from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm

# Preview mode
service = ComprehensiveIndexingService(
    vector_store_type="chroma",
    persistent_client=get_chromadb_client(),
    embeddings_model=get_embeddings_model(),
    llm=get_llm(),
    preview_mode=True,
    preview_output_dir="indexing_preview"
)

# Index with preview
result = await service.index_policy_document(
    file_path="path/to/policy.pdf",
    domain="compliance"
)
# Files saved to indexing_preview/policy_documents/

# Index to database (disable preview)
service.preview_mode = False
result = await service.index_policy_document(
    file_path="path/to/policy.pdf",
    domain="compliance"
)
# Documents indexed to ChromaDB
```

