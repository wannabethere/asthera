import os

from app.core.settings import load_dotenv_merged

load_dotenv_merged(final_override=True)

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "Data_services")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "root")

VECTOR_STORE_TYPE = os.getenv("VECTOR_STORE_TYPE", "qdrant")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = os.getenv("QDRANT_PORT", "6333")
QDRANT_URL = os.getenv("QDRANT_URL", "") or None
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "") or None
CHROMA_HOST = os.getenv("CHROMA_HOST", "") or None
CHROMA_PORT = os.getenv("CHROMA_PORT", "8888")

DATABASE_URL = "postgresql+asyncpg://pixentia:FLc%26dL%40M9A5Q7wI%3B@unedadevpostgresql.postgres.database.azure.com:5432/phenom_genai_dataservices"
