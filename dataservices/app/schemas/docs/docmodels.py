import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import (
    ARRAY,
    JSON,
    Column,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.ext.declarative import declarative_base


@dataclass
class Document:
    id: uuid.UUID
    document_id: uuid.UUID
    version: int
    content: str
    json_metadata: Dict
    source_type: str
    document_type: str
    created_at: datetime
    created_by: Optional[str] = None
    domain_id: Optional[str] = None
    document: Optional['Document'] = None

@dataclass
class DocumentInsight:
    id: str
    document_id: str
    source_type: str
    document_type: str
    event_timestamp: str
    chromadb_ids: List[str]
    event_type: str
    created_by: str
    domain_id: Optional[str] = None
    document: Optional[Document] = None
    # Simplified structure with key data
    chunk_content: Optional[str] = None  # Main chunk content as text
    key_phrases: Optional[List[str]] = None  # Interesting phrases and key terms
    # Flexible insights structure for additional extraction data
    insights: Optional[Dict] = None  # Additional insights JSON for complex extractions
    extraction_config: Optional[Dict] = None  # Configuration used for extraction
    extraction_date: Optional[str] = None

Base = declarative_base()


"""
-- Original schema
CREATE TABLE document_versions1 (
    id UUID NOT NULL,
    document_id UUID NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    json_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_by TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
);

CREATE TABLE insight_event_versions1 (
    id UUID NOT NULL,
    insight_id UUID NOT NULL,
    version INTEGER NOT NULL,
    phrases TEXT[] NOT NULL,
    insight JSONB,
    extracted_entities JSONB,
    ner_text TEXT,
    event_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    chromadb_ids TEXT[] NOT NULL,
    event_type TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_by TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY (insight_id) REFERENCES insight_events (id) ON DELETE CASCADE
);

-- Simplified schema with chunk_content and key_phrases as main columns
-- Migration script to add new columns and remove redundant ones:
ALTER TABLE doc_insight_versions 
ADD COLUMN IF NOT EXISTS chunk_content TEXT,
ADD COLUMN IF NOT EXISTS key_phrases TEXT[],
ADD COLUMN IF NOT EXISTS insights JSONB,
ADD COLUMN IF NOT EXISTS extraction_config JSONB,
ADD COLUMN IF NOT EXISTS extraction_date TIMESTAMP WITH TIME ZONE;

-- Optional: Remove redundant columns after migrating data
-- ALTER TABLE doc_insight_versions DROP COLUMN IF EXISTS phrases;
-- ALTER TABLE doc_insight_versions DROP COLUMN IF EXISTS insight;
-- ALTER TABLE doc_insight_versions DROP COLUMN IF EXISTS extracted_entities;
-- ALTER TABLE doc_insight_versions DROP COLUMN IF EXISTS ner_text;

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_insight_chunk_content ON doc_insight_versions USING GIN (to_tsvector('english', chunk_content));
CREATE INDEX IF NOT EXISTS idx_insight_key_phrases ON doc_insight_versions USING GIN (key_phrases);
CREATE INDEX IF NOT EXISTS idx_insight_insights ON doc_insight_versions USING GIN (insights);
CREATE INDEX IF NOT EXISTS idx_insight_extraction_config ON doc_insight_versions USING GIN (extraction_config);
CREATE INDEX IF NOT EXISTS idx_insight_extraction_date ON doc_insight_versions (extraction_date);
CREATE INDEX IF NOT EXISTS idx_insight_document_type ON doc_insight_versions (document_type);
CREATE INDEX IF NOT EXISTS idx_insight_source_type ON doc_insight_versions (source_type);

-- Example queries for the simplified structure:
-- SELECT * FROM doc_insight_versions WHERE chunk_content ILIKE '%revenue%';
-- SELECT * FROM doc_insight_versions WHERE 'KPI' = ANY(key_phrases);
-- SELECT * FROM doc_insight_versions WHERE key_phrases && ARRAY['financial', 'metrics'];
-- SELECT * FROM doc_insight_versions WHERE insights ? 'business_intelligence';
-- SELECT * FROM doc_insight_versions WHERE insights->'business_intelligence' ? 'kpis';

"""
    

class DocumentVersion(Base):
    __tablename__ = 'doc_versions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    source_type = Column(Text, nullable=False)
    document_type = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    json_metadata = Column(JSON)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    created_by = Column(Text)  # Optional: track who made the change
    domain_id = Column(Text)  # Domain ID for multi-tenant support
    
    
class DocumentInsightVersion(Base):
    __tablename__ = 'doc_insight_versions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    insight_id = Column(UUID(as_uuid=True),  nullable=False)
    document_id = Column(UUID(as_uuid=True), nullable=False)  # Reference to document
    version = Column(Integer, nullable=False)
    source_type = Column(Text, nullable=False)
    document_type = Column(Text, nullable=False)
    event_timestamp = Column(TIMESTAMP(timezone=True), nullable=False)
    chromadb_ids = Column(ARRAY(Text), nullable=False)
    event_type = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    created_by = Column(Text)  # Optional: track who made the change
    domain_id = Column(Text)  # Domain ID for multi-tenant support
    # Simplified structure with key data
    chunk_content = Column(Text)  # Main chunk content as text
    key_phrases = Column(ARRAY(Text))  # Interesting phrases and key terms
    # Flexible insights structure for additional extraction data
    insights = Column(JSONB)  # Additional insights JSON for complex extractions
    extraction_config = Column(JSONB)  # Configuration used for extraction
    extraction_date = Column(TIMESTAMP(timezone=True))
    
    

