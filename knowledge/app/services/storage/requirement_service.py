"""
Storage service for Requirement entities
"""
import logging
from typing import List, Optional
from datetime import datetime

from app.storage.models import Requirement, ControlRequirementMapping
from app.storage.database import DatabaseClient

logger = logging.getLogger(__name__)


class RequirementStorageService:
    """Service for managing Requirement entities"""
    
    def __init__(self, db_client: DatabaseClient):
        """Initialize with database client"""
        self.db_client = db_client
    
    async def save_requirement(self, requirement: Requirement) -> str:
        """Save a requirement to database"""
        await self.db_client.execute("""
            INSERT INTO requirements (
                requirement_id, control_id, requirement_text,
                requirement_type, vector_doc_id, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (requirement_id) DO UPDATE SET
                control_id = EXCLUDED.control_id,
                requirement_text = EXCLUDED.requirement_text,
                requirement_type = EXCLUDED.requirement_type,
                vector_doc_id = EXCLUDED.vector_doc_id,
                updated_at = CURRENT_TIMESTAMP
        """,
            requirement.requirement_id,
            requirement.control_id,
            requirement.requirement_text,
            requirement.requirement_type,
            requirement.vector_doc_id,
            requirement.created_at or datetime.utcnow(),
            datetime.utcnow()
        )
        
        logger.info(f"Saved requirement: {requirement.requirement_id}")
        return requirement.requirement_id
    
    async def save_requirements(self, requirements: List[Requirement]) -> List[str]:
        """Save multiple requirements"""
        ids = []
        for requirement in requirements:
            try:
                req_id = await self.save_requirement(requirement)
                ids.append(req_id)
            except Exception as e:
                logger.error(f"Error saving requirement {requirement.requirement_id}: {str(e)}")
        return ids
    
    async def get_requirement(self, requirement_id: str) -> Optional[Requirement]:
        """Get a requirement by ID"""
        row = await self.db_client.fetchrow("""
            SELECT 
                requirement_id, control_id, requirement_text,
                requirement_type, vector_doc_id, created_at, updated_at
            FROM requirements
            WHERE requirement_id = $1
        """, requirement_id)
        
        if row:
            return Requirement(
                requirement_id=row["requirement_id"],
                control_id=row["control_id"],
                requirement_text=row["requirement_text"],
                requirement_type=row["requirement_type"],
                vector_doc_id=row["vector_doc_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
        return None
    
    async def get_requirements_for_control(self, control_id: str) -> List[Requirement]:
        """Get all requirements for a control"""
        rows = await self.db_client.fetch("""
            SELECT 
                requirement_id, control_id, requirement_text,
                requirement_type, vector_doc_id, created_at, updated_at
            FROM requirements
            WHERE control_id = $1
            ORDER BY requirement_id
        """, control_id)
        
        return [
            Requirement(
                requirement_id=row["requirement_id"],
                control_id=row["control_id"],
                requirement_text=row["requirement_text"],
                requirement_type=row["requirement_type"],
                vector_doc_id=row["vector_doc_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
            for row in rows
        ]
    
    async def save_control_requirement_mapping(
        self,
        mapping: ControlRequirementMapping
    ) -> bool:
        """Save a control-requirement mapping"""
        await self.db_client.execute("""
            INSERT INTO control_requirement_mapping (
                control_id, requirement_id, is_mandatory, created_at
            ) VALUES ($1, $2, $3, $4)
            ON CONFLICT (control_id, requirement_id) DO UPDATE SET
                is_mandatory = EXCLUDED.is_mandatory
        """,
            mapping.control_id,
            mapping.requirement_id,
            mapping.is_mandatory,
            mapping.created_at or datetime.utcnow()
        )
        
        return True

