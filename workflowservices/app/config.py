import os

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "Data_services")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "root")

DATABASE_URL = "postgresql+asyncpg://pixentia:FLc%26dL%40M9A5Q7wI%3B@unedadevpostgresql.postgres.database.azure.com:5432/phenom_gen_ai"
