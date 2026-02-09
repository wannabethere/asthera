#!/usr/bin/env bash
#
# Build product KB index: extract entities + contextual edges, then ingest to vector store.
#
# Prerequisites:
#   - kb-dump-utility preview dir with enriched/ and enriched_vendor/ (or your enriched subdirs)
#   - flowharmonicai/knowledge env: Python with dependencies (for ingest step; extract step needs only stdlib)
#
# Usage:
#   cd flowharmonicai/knowledge && ./scripts/build_product_kb_index.sh
#   # Or with custom paths:
#   KB_PREVIEW_DIR=/path/to/kb-dump-utility/preview \
#   KB_OUTPUT_DIR=/path/to/preview_product_kb \
#   ./scripts/build_product_kb_index.sh
#
# Step-by-step (manual commands):
#   Step 1 - Extract product KB (writes preview_product_kb/):
#     cd flowharmonicai/knowledge
#     export PYTHONPATH=$PWD
#     python3 -m indexing_cli.extract_product_kb_preview \
#       --preview-dir /path/to/kb-dump-utility/preview \
#       --output-dir /path/to/kb-dump-utility/preview_product_kb \
#       --product-key-concepts /path/to/kb-dump-utility/config/product_key_concepts.json
#
#   Step 2 - Ingest product KB preview into ChromaDB:
#     cd flowharmonicai/knowledge
#     python3 -m indexing_cli.ingest_preview_files \
#       --preview-dir /path/to/kb-dump-utility/preview_product_kb \
#       --collection-prefix comprehensive_index \
#       --vector-store chroma
#
#   Optional: Ingest full preview (enriched + metrics + product KB) in one go:
#     python3 -m indexing_cli.ingest_preview_files \
#       --preview-dir /path/to/kb-dump-utility/preview \
#       --enriched-subdirs enriched enriched_vendor \
#       --collection-prefix comprehensive_index
#     # Then ingest product KB preview separately so product entities/edges are included:
#     python3 -m indexing_cli.ingest_preview_files \
#       --preview-dir /path/to/kb-dump-utility/preview_product_kb \
#       --collection-prefix comprehensive_index
#

set -e

# Paths (override with env)
KNOWLEDGE_DIR="${KNOWLEDGE_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
KB_PREVIEW_DIR="${KB_PREVIEW_DIR:-}"
KB_OUTPUT_DIR="${KB_OUTPUT_DIR:-}"
PRODUCT_KEY_CONCEPTS="${PRODUCT_KEY_CONCEPTS:-}"
COLLECTION_PREFIX="${COLLECTION_PREFIX:-comprehensive_index}"
VECTOR_STORE="${VECTOR_STORE:-chroma}"
SKIP_INGEST="${SKIP_INGEST:-}"

# Default kb-dump-utility paths relative to common workspace layout
if [ -z "$KB_PREVIEW_DIR" ]; then
  if [ -d "$KNOWLEDGE_DIR/../../Lexy/kb-dump-utility/preview" ]; then
    KB_PREVIEW_DIR="$(cd "$KNOWLEDGE_DIR/../../Lexy/kb-dump-utility/preview" && pwd)"
  elif [ -d "$KNOWLEDGE_DIR/../kb-dump-utility/preview" ]; then
    KB_PREVIEW_DIR="$(cd "$KNOWLEDGE_DIR/../kb-dump-utility/preview" && pwd)"
  else
    echo "Error: KB_PREVIEW_DIR not set and could not find kb-dump-utility/preview. Set KB_PREVIEW_DIR=/path/to/kb-dump-utility/preview"
    exit 1
  fi
fi

if [ -z "$KB_OUTPUT_DIR" ]; then
  KB_OUTPUT_DIR="$(dirname "$KB_PREVIEW_DIR")/preview_product_kb"
fi

if [ -z "$PRODUCT_KEY_CONCEPTS" ]; then
  KB_CONFIG="$(dirname "$KB_PREVIEW_DIR")/config/product_key_concepts.json"
  if [ -f "$KB_CONFIG" ]; then
    PRODUCT_KEY_CONCEPTS="$KB_CONFIG"
  fi
fi

echo "=============================================="
echo "Step 1: Extract product KB (entities + edges)"
echo "=============================================="
echo "  PREVIEW_DIR (input):  $KB_PREVIEW_DIR"
echo "  OUTPUT_DIR (preview): $KB_OUTPUT_DIR"
echo "  KEY_CONCEPTS config:  ${PRODUCT_KEY_CONCEPTS:-<default>}"
echo ""

cd "$KNOWLEDGE_DIR"
export PYTHONPATH="$KNOWLEDGE_DIR:$PYTHONPATH"

if [ -n "$PRODUCT_KEY_CONCEPTS" ]; then
  python3 -m indexing_cli.extract_product_kb_preview \
    --preview-dir "$KB_PREVIEW_DIR" \
    --output-dir "$KB_OUTPUT_DIR" \
    --product-key-concepts "$PRODUCT_KEY_CONCEPTS"
else
  python3 -m indexing_cli.extract_product_kb_preview \
    --preview-dir "$KB_PREVIEW_DIR" \
    --output-dir "$KB_OUTPUT_DIR"
fi

if [ -n "$SKIP_INGEST" ]; then
  echo "SKIP_INGEST=1: skipping ingest step. Run ingest manually:"
  echo "  cd $KNOWLEDGE_DIR && python3 -m indexing_cli.ingest_preview_files --preview-dir $KB_OUTPUT_DIR --collection-prefix $COLLECTION_PREFIX --vector-store $VECTOR_STORE"
  exit 0
fi

echo ""
echo "=============================================="
echo "Step 2: Ingest preview_product_kb into index"
echo "=============================================="
echo "  PREVIEW_DIR:          $KB_OUTPUT_DIR"
echo "  COLLECTION_PREFIX:    $COLLECTION_PREFIX"
echo "  VECTOR_STORE:        $VECTOR_STORE"
echo ""

python3 -m indexing_cli.ingest_preview_files \
  --preview-dir "$KB_OUTPUT_DIR" \
  --collection-prefix "$COLLECTION_PREFIX" \
  --vector-store "$VECTOR_STORE"

echo ""
echo "Done. Product KB index built from $KB_OUTPUT_DIR"
