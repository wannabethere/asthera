"""
Service layer for Universal Metadata Framework
Provides database integration and API for metadata operations
"""
import logging
from typing import Dict, List, Optional, Any
import asyncpg
from datetime import datetime
import json

from ..agents.metadata_state import MetadataEntry, MetadataPattern, DomainMapping

logger = logging.getLogger(__name__)


class MetadataService:
    """Service for managing universal metadata in PostgreSQL"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        """Initialize with database connection pool"""
        self.db_pool = db_pool
    
    async def save_metadata_entry(self, entry: MetadataEntry) -> int:
        """Save a metadata entry to database"""
        
        async with self.db_pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO domain_risk_metadata (
                    domain_name, framework_name, metadata_category, enum_type,
                    code, description, abbreviation,
                    numeric_score, priority_order, severity_level, weight,
                    risk_score, occurrence_likelihood, consequence_severity,
                    exploitability_score, impact_score,
                    rationale, data_source, calculation_method, data_indicators,
                    parent_code, equivalent_codes,
                    confidence_score, created_by
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                    $12, $13, $14, $15, $16, $17, $18, $19, $20,
                    $21, $22, $23, $24
                )
                ON CONFLICT (domain_name, enum_type, code) 
                DO UPDATE SET
                    description = EXCLUDED.description,
                    numeric_score = EXCLUDED.numeric_score,
                    priority_order = EXCLUDED.priority_order,
                    severity_level = EXCLUDED.severity_level,
                    weight = EXCLUDED.weight,
                    risk_score = EXCLUDED.risk_score,
                    occurrence_likelihood = EXCLUDED.occurrence_likelihood,
                    consequence_severity = EXCLUDED.consequence_severity,
                    rationale = EXCLUDED.rationale,
                    data_indicators = EXCLUDED.data_indicators,
                    confidence_score = EXCLUDED.confidence_score,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """,
                entry.domain_name,
                entry.framework_name,
                entry.metadata_category,
                entry.enum_type,
                entry.code,
                entry.description,
                entry.abbreviation,
                entry.numeric_score,
                entry.priority_order,
                entry.severity_level,
                entry.weight,
                entry.risk_score,
                entry.occurrence_likelihood,
                entry.consequence_severity,
                entry.exploitability_score,
                entry.impact_score,
                entry.rationale,
                entry.data_source,
                entry.calculation_method,
                entry.data_indicators,
                entry.parent_code,
                json.dumps(entry.equivalent_codes) if entry.equivalent_codes else None,
                entry.confidence_score,
                "llm_agent"
            )
            
            return result["id"]
    
    async def save_metadata_entries(self, entries: List[MetadataEntry]) -> List[int]:
        """Save multiple metadata entries"""
        ids = []
        for entry in entries:
            try:
                entry_id = await self.save_metadata_entry(entry)
                ids.append(entry_id)
            except Exception as e:
                logger.error(f"Error saving entry {entry.code}: {str(e)}")
        return ids
    
    async def load_source_metadata(
        self,
        source_domains: List[str],
        metadata_categories: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Load metadata from source domains"""
        
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT 
                    domain_name, framework_name, metadata_category, enum_type,
                    code, description, abbreviation,
                    numeric_score, priority_order, severity_level, weight,
                    risk_score, occurrence_likelihood, consequence_severity,
                    exploitability_score, impact_score,
                    rationale, data_source, calculation_method, data_indicators,
                    parent_code, equivalent_codes,
                    confidence_score, created_at
                FROM domain_risk_metadata
                WHERE domain_name = ANY($1)
            """
            
            params = [source_domains]
            
            if metadata_categories:
                query += " AND metadata_category = ANY($2)"
                params.append(metadata_categories)
            
            query += " ORDER BY priority_order, numeric_score DESC"
            
            rows = await conn.fetch(query, *params)
            
            return [dict(row) for row in rows]
    
    async def save_pattern(self, pattern: MetadataPattern) -> int:
        """Save a learned pattern"""
        
        async with self.db_pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO metadata_patterns (
                    pattern_name, pattern_type, source_domain,
                    description, pattern_structure, pattern_examples,
                    confidence, created_by
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT DO NOTHING
                RETURNING id
            """,
                pattern.pattern_name,
                pattern.pattern_type,
                pattern.source_domain,
                pattern.description,
                json.dumps(pattern.pattern_structure),
                json.dumps(pattern.pattern_examples),
                pattern.confidence,
                "llm_agent"
            )
            
            return result["id"] if result else None
    
    async def save_domain_mapping(self, mapping: DomainMapping) -> int:
        """Save a cross-domain mapping"""
        
        async with self.db_pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO cross_domain_mappings (
                    source_domain, source_code, source_enum_type,
                    target_domain, target_code, target_enum_type,
                    mapping_type, similarity_score, mapping_rationale,
                    confidence, created_by
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (source_domain, source_code, target_domain, target_code)
                DO UPDATE SET
                    similarity_score = EXCLUDED.similarity_score,
                    mapping_rationale = EXCLUDED.mapping_rationale
                RETURNING id
            """,
                mapping.source_domain,
                mapping.source_code,
                mapping.source_enum_type,
                mapping.target_domain,
                mapping.target_code,
                mapping.target_enum_type,
                mapping.mapping_type,
                mapping.similarity_score,
                mapping.mapping_rationale,
                0.8,  # Default confidence
                "llm_agent"
            )
            
            return result["id"]
    
    async def create_generation_session(
        self,
        target_domain: str,
        source_domains: List[str],
        framework_name: Optional[str] = None,
        document_count: int = 0
    ) -> str:
        """Create a metadata generation session"""
        
        async with self.db_pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO metadata_generation_sessions (
                    target_domain, source_domains, framework_name,
                    document_count, status, created_by
                ) VALUES ($1, $2, $3, $4, 'in_progress', $5)
                RETURNING session_id
            """,
                target_domain,
                json.dumps(source_domains),
                framework_name,
                document_count,
                "llm_agent"
            )
            
            return str(result["session_id"])
    
    async def update_generation_session(
        self,
        session_id: str,
        metadata_entries_created: int,
        patterns_applied: List[str],
        confidence_scores: Dict[str, float],
        status: str = "completed"
    ):
        """Update generation session with results"""
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE metadata_generation_sessions
                SET
                    metadata_entries_created = $1,
                    patterns_applied = $2,
                    confidence_scores = $3,
                    status = $4,
                    completed_at = CASE WHEN $4 = 'completed' THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE session_id = $5
            """,
                metadata_entries_created,
                json.dumps(patterns_applied),
                json.dumps(confidence_scores),
                status,
                session_id
            )
    
    async def get_domain_metadata(
        self,
        domain_name: str,
        framework_name: Optional[str] = None,
        metadata_category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get metadata for a specific domain"""
        
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT 
                    id, domain_name, framework_name, metadata_category, enum_type,
                    code, description, abbreviation,
                    numeric_score, priority_order, severity_level, weight,
                    risk_score, occurrence_likelihood, consequence_severity,
                    rationale, data_indicators, confidence_score,
                    created_at, updated_at
                FROM domain_risk_metadata
                WHERE domain_name = $1
            """
            
            params = [domain_name]
            
            if framework_name:
                query += " AND framework_name = $2"
                params.append(framework_name)
            
            if metadata_category:
                query += f" AND metadata_category = ${len(params) + 1}"
                params.append(metadata_category)
            
            query += " ORDER BY priority_order, numeric_score DESC"
            
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def get_cross_domain_mappings(
        self,
        source_domain: str,
        target_domain: str
    ) -> List[Dict[str, Any]]:
        """Get cross-domain mappings between two domains"""
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    id, source_domain, source_code, source_enum_type,
                    target_domain, target_code, target_enum_type,
                    mapping_type, similarity_score, mapping_rationale,
                    created_at
                FROM cross_domain_mappings
                WHERE source_domain = $1 AND target_domain = $2
                ORDER BY similarity_score DESC
            """,
                source_domain,
                target_domain
            )
            
            return [dict(row) for row in rows]

