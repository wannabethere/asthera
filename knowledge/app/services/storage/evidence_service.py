"""
Storage service for EvidenceType entities
"""
import logging
from typing import List, Optional
from datetime import datetime

from app.storage.models import EvidenceType
from app.storage.database import DatabaseClient

logger = logging.getLogger(__name__)


class EvidenceStorageService:
    """Service for managing EvidenceType entities"""
    
    def __init__(self, db_client: DatabaseClient):
        """Initialize with database client"""
        self.db_client = db_client
    
    async def save_evidence_type(self, evidence: EvidenceType) -> str:
        """Save an evidence type to database"""
        await self.db_client.execute("""
            INSERT INTO evidence_types (
                evidence_id, evidence_name, evidence_category,
                collection_method, vector_doc_id, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (evidence_id) DO UPDATE SET
                evidence_name = EXCLUDED.evidence_name,
                evidence_category = EXCLUDED.evidence_category,
                collection_method = EXCLUDED.collection_method,
                vector_doc_id = EXCLUDED.vector_doc_id,
                updated_at = CURRENT_TIMESTAMP
        """,
            evidence.evidence_id,
            evidence.evidence_name,
            evidence.evidence_category,
            evidence.collection_method,
            evidence.vector_doc_id,
            evidence.created_at or datetime.utcnow(),
            datetime.utcnow()
        )
        
        logger.info(f"Saved evidence type: {evidence.evidence_id}")
        return evidence.evidence_id
    
    async def save_evidence_types(self, evidence_types: List[EvidenceType]) -> List[str]:
        """Save multiple evidence types"""
        ids = []
        for evidence in evidence_types:
            try:
                evidence_id = await self.save_evidence_type(evidence)
                ids.append(evidence_id)
            except Exception as e:
                logger.error(f"Error saving evidence {evidence.evidence_id}: {str(e)}")
        return ids
    
    async def get_evidence_type(self, evidence_id: str) -> Optional[EvidenceType]:
        """Get an evidence type by ID"""
        row = await self.db_client.fetchrow("""
            SELECT 
                evidence_id, evidence_name, evidence_category,
                collection_method, vector_doc_id, created_at, updated_at
            FROM evidence_types
            WHERE evidence_id = $1
        """, evidence_id)
        
        if row:
            return EvidenceType(
                evidence_id=row["evidence_id"],
                evidence_name=row["evidence_name"],
                evidence_category=row["evidence_category"],
                collection_method=row["collection_method"],
                vector_doc_id=row["vector_doc_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
        return None
    
    async def get_evidence_by_category(self, category: str) -> List[EvidenceType]:
        """Get all evidence types for a category"""
        rows = await self.db_client.fetch("""
            SELECT 
                evidence_id, evidence_name, evidence_category,
                collection_method, vector_doc_id, created_at, updated_at
            FROM evidence_types
            WHERE evidence_category = $1
            ORDER BY evidence_name
        """, category)
        
        return [
            EvidenceType(
                evidence_id=row["evidence_id"],
                evidence_name=row["evidence_name"],
                evidence_category=row["evidence_category"],
                collection_method=row["collection_method"],
                vector_doc_id=row["vector_doc_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
            for row in rows
        ]

