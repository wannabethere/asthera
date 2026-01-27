"""
Minimal ChromaDB diagnostic to find where segfault occurs
"""
import sys
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable telemetry
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
os.environ['CHROMA_TELEMETRY_IMPL'] = 'none'

logger.info("Step 1: Python version and imports")
logger.info(f"Python version: {sys.version}")

try:
    logger.info("Step 2: Import chromadb")
    import chromadb
    logger.info(f"✓ ChromaDB version: {chromadb.__version__}")
except Exception as e:
    logger.error(f"✗ Failed to import chromadb: {e}")
    sys.exit(1)

try:
    logger.info("Step 3: Get settings from app.core.settings")
    from app.core.settings import get_settings
    settings = get_settings()
    logger.info(f"✓ Settings loaded")
    logger.info(f"  CHROMA_STORE_PATH: {settings.CHROMA_STORE_PATH}")
except Exception as e:
    logger.error(f"✗ Failed to get settings: {e}")
    sys.exit(1)

try:
    logger.info("Step 4: Create PersistentClient with path")
    from pathlib import Path
    chroma_path = Path(settings.CHROMA_STORE_PATH)
    logger.info(f"  Path exists: {chroma_path.exists()}")
    logger.info(f"  Path: {chroma_path}")
    
    # Check for corrupted database files
    if chroma_path.exists():
        db_file = chroma_path / "chroma.sqlite3"
        logger.info(f"  DB file exists: {db_file.exists()}")
        if db_file.exists():
            import os
            size = os.path.getsize(db_file)
            logger.info(f"  DB file size: {size} bytes")
    
    client = chromadb.PersistentClient(
        path=str(chroma_path)
    )
    logger.info(f"✓ PersistentClient created successfully")
except Exception as e:
    logger.error(f"✗ Failed to create PersistentClient: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    logger.info("Step 5: List collections")
    collections = client.list_collections()
    logger.info(f"✓ Found {len(collections)} collections")
    for col in collections[:5]:  # Show first 5
        try:
            count = col.count()
            logger.info(f"  - {col.name}: {count} documents")
        except Exception as e:
            logger.warning(f"  - {col.name}: Error getting count - {e}")
except Exception as e:
    logger.error(f"✗ Failed to list collections: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    logger.info("Step 6: Test getting table_descriptions collection")
    collection = client.get_collection("table_descriptions")
    count = collection.count()
    logger.info(f"✓ table_descriptions collection: {count} documents")
except Exception as e:
    logger.warning(f"  table_descriptions: {e}")

try:
    logger.info("Step 7: Import embeddings model")
    from app.core.dependencies import get_embeddings_model
    embeddings = get_embeddings_model()
    logger.info(f"✓ Embeddings model loaded")
except Exception as e:
    logger.error(f"✗ Failed to load embeddings: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("\n" + "="*80)
logger.info("✓ ALL DIAGNOSTIC STEPS PASSED!")
logger.info("ChromaDB is working correctly.")
logger.info("="*80)
