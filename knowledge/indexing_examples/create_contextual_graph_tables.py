#!/usr/bin/env python3
"""
Script to create contextual graph tables in PostgreSQL.
Run this before ingesting contextual edges to PostgreSQL.

Usage:
    python create_contextual_graph_tables.py
"""
import asyncio
import logging
from pathlib import Path

from app.core.dependencies import get_database_pool

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SQL_MIGRATION = """
-- Create contexts table
CREATE TABLE IF NOT EXISTS contexts (
    context_id SERIAL PRIMARY KEY,
    context_type VARCHAR(100) NOT NULL DEFAULT 'organizational_situational',
    context_name VARCHAR(255) NOT NULL UNIQUE,
    context_definition JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on context_name for faster lookups
CREATE INDEX IF NOT EXISTS idx_contexts_context_name ON contexts(context_name);
CREATE INDEX IF NOT EXISTS idx_contexts_context_type ON contexts(context_type);

-- Create contextual_relationships table
CREATE TABLE IF NOT EXISTS contextual_relationships (
    id SERIAL PRIMARY KEY,
    source_entity_id VARCHAR(255) NOT NULL,
    relationship_type VARCHAR(100) NOT NULL,
    target_entity_id VARCHAR(255) NOT NULL,
    context_id INTEGER NOT NULL REFERENCES contexts(context_id) ON DELETE CASCADE,
    strength FLOAT DEFAULT 0.0,
    confidence FLOAT DEFAULT 0.0,
    reasoning TEXT,
    valid_from TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint to prevent duplicates
    UNIQUE(source_entity_id, relationship_type, target_entity_id, context_id)
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_contextual_relationships_source ON contextual_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_contextual_relationships_target ON contextual_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_contextual_relationships_type ON contextual_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_contextual_relationships_context ON contextual_relationships(context_id);
CREATE INDEX IF NOT EXISTS idx_contextual_relationships_composite ON contextual_relationships(source_entity_id, relationship_type, target_entity_id);

-- Add comments to tables
COMMENT ON TABLE contexts IS 'Stores organizational and situational contexts for the contextual graph';
COMMENT ON TABLE contextual_relationships IS 'Stores relationships between entities in the contextual graph';
"""


async def create_tables():
    """Create contextual graph tables in PostgreSQL."""
    try:
        db_pool = await get_database_pool()
        logger.info("Connected to database")
        
        async with db_pool.acquire() as conn:
            # Execute migration
            await conn.execute(SQL_MIGRATION)
            logger.info("✓ Created contextual graph tables")
            
            # Verify tables exist
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('contexts', 'contextual_relationships')
                ORDER BY table_name
            """)
            
            if len(tables) == 2:
                logger.info("✓ Verified tables exist:")
                for table in tables:
                    logger.info(f"  - {table['table_name']}")
            else:
                logger.warning(f"Expected 2 tables, found {len(tables)}")
                
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(create_tables())
