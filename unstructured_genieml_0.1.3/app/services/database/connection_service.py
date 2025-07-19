from typing import Any

import chromadb
import redis
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import get_settings


class ConnectionService:
    _instance = None
    _postgres_engine = None
    _redis_client = None
    _chroma_client = None
    _embeddings_model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConnectionService, cls).__new__(cls)
        return cls._instance

    @property
    def postgres_engine(self):
        if self._postgres_engine is None:
            settings = get_settings()
            self._postgres_engine = create_engine(settings.postgres_connection_string)
        return self._postgres_engine

    @property
    def postgres_session(self):
        Session = sessionmaker(bind=self.postgres_engine)
        return Session()

    @property
    def redis_client(self) -> redis.Redis:
        if self._redis_client is None:
            settings = get_settings()
            self._redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
        return self._redis_client

    @property
    def chroma_client(self) -> Any:
        if self._chroma_client is None:
            settings = get_settings()
            self._chroma_client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        return self._chroma_client

    @property
    def embeddings_model(self) -> OpenAIEmbeddings:
        if self._embeddings_model is None:
            settings = get_settings()
            self._embeddings_model = OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=SecretStr(settings.OPENAI_API_KEY)
            )
        return self._embeddings_model

    def close_connections(self):
        """Close all database connections"""
        if self._postgres_engine:
            self._postgres_engine.dispose()
            self._postgres_engine = None
        
        if self._redis_client:
            self._redis_client.close()
            self._redis_client = None
        
        # ChromaDB doesn't need explicit closing
        self._chroma_client = None
        self._embeddings_model = None

    def __del__(self):
        """Cleanup connections when the object is destroyed"""
        self.close_connections()

# Create a singleton instance
connection_service = ConnectionService() 