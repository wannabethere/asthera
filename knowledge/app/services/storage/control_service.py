"""
Storage service for Control entities
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.storage.models import Control
from app.storage.database import DatabaseClient

logger = logging.getLogger(__name__)


class ControlStorageService:
    """Service for managing Control entities"""
    
    def __init__(self, db_client: DatabaseClient):
        """Initialize with database client"""
        self.db_client = db_client
    
    async def save_control(self, control: Control) -> str:
        """Save a control to database"""
        await self.db_client.execute("""
            INSERT INTO controls (
                control_id, framework, control_name, control_description,
                category, vector_doc_id, embedding_version,
                created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (control_id) DO UPDATE SET
                framework = EXCLUDED.framework,
                control_name = EXCLUDED.control_name,
                control_description = EXCLUDED.control_description,
                category = EXCLUDED.category,
                vector_doc_id = EXCLUDED.vector_doc_id,
                embedding_version = EXCLUDED.embedding_version,
                updated_at = CURRENT_TIMESTAMP
        """,
            control.control_id,
            control.framework,
            control.control_name,
            control.control_description,
            control.category,
            control.vector_doc_id,
            control.embedding_version,
            control.created_at or datetime.utcnow(),
            datetime.utcnow()
        )
        
        logger.info(f"Saved control: {control.control_id}")
        return control.control_id
    
    async def save_controls(self, controls: List[Control]) -> List[str]:
        """Save multiple controls"""
        ids = []
        for control in controls:
            try:
                control_id = await self.save_control(control)
                ids.append(control_id)
            except Exception as e:
                logger.error(f"Error saving control {control.control_id}: {str(e)}")
        return ids
    
    async def get_control(self, control_id: str) -> Optional[Control]:
        """Get a control by ID"""
        row = await self.db_client.fetchrow("""
            SELECT 
                control_id, framework, control_name, control_description,
                category, vector_doc_id, embedding_version,
                created_at, updated_at
            FROM controls
            WHERE control_id = $1
        """, control_id)
        
        if row:
            return Control(
                control_id=row["control_id"],
                framework=row["framework"],
                control_name=row["control_name"],
                control_description=row["control_description"],
                category=row["category"],
                vector_doc_id=row["vector_doc_id"],
                embedding_version=row["embedding_version"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
        return None
    
    async def get_controls_by_framework(self, framework: str) -> List[Control]:
        """Get all controls for a framework"""
        rows = await self.db_client.fetch("""
            SELECT 
                control_id, framework, control_name, control_description,
                category, vector_doc_id, embedding_version,
                created_at, updated_at
            FROM controls
            WHERE framework = $1
            ORDER BY control_id
        """, framework)
        
        return [
            Control(
                control_id=row["control_id"],
                framework=row["framework"],
                control_name=row["control_name"],
                control_description=row["control_description"],
                category=row["category"],
                vector_doc_id=row["vector_doc_id"],
                embedding_version=row["embedding_version"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
            for row in rows
        ]
    
    async def update_vector_doc_id(self, control_id: str, vector_doc_id: str) -> bool:
        """Update the vector document ID for a control"""
        result = await self.db_client.execute("""
            UPDATE controls
            SET vector_doc_id = $1, updated_at = CURRENT_TIMESTAMP
            WHERE control_id = $2
        """, vector_doc_id, control_id)
        
        return result == "UPDATE 1"
    
    async def delete_control(self, control_id: str) -> bool:
        """Delete a control (cascades to requirements and measurements)"""
        result = await self.db_client.execute("""
            DELETE FROM controls WHERE control_id = $1
        """, control_id)
        
        return result == "DELETE 1"

