"""
Minimal base for Transform SQL RAG Agent in knowledge app.

PlaybookDrivenTransformAgent extends this class. The full TransformSQLRAGAgent
implementation lives in the agents app; this stub provides the constructor
and attributes used by the playbook-driven agent.
"""
from typing import Any, Optional

from app.core.engine_provider import DatabaseEngine
from app.core.provider import DocumentStoreProvider
from app.agents.data.retrieval_helper import RetrievalHelper


class TransformSQLRAGAgent:
    """Base transform SQL RAG agent: holds llm, engine, and document/retrieval dependencies."""

    def __init__(
        self,
        llm: Any,
        engine: DatabaseEngine,
        embeddings: Any = None,
        max_iterations: int = 5,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        retrieval_helper: Optional[RetrievalHelper] = None,
        **kwargs: Any,
    ):
        self.llm = llm
        self.engine = engine
        self.embeddings = embeddings
        self.max_iterations = max_iterations
        self.document_store_provider = document_store_provider
        self.retrieval_helper = retrieval_helper
        for k, v in kwargs.items():
            setattr(self, k, v)
