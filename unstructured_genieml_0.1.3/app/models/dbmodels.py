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
    document: Optional['Document'] = None

@dataclass
class DocumentInsight:
    id: str
    document_id: str
    phrases: List[str]
    insight: Dict
    source_type: str
    document_type: str
    extracted_entities: Dict
    ner_text: str
    event_timestamp: str
    chromadb_ids: List[str]
    event_type: str
    created_by: str
    document: Optional[Document] = None
    enhanced_insights: Optional[Dict] = None



Base = declarative_base()






"""
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

"""
    

class DocumentVersion(Base):
    __tablename__ = 'document_versions1'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    source_type = Column(Text, nullable=False)
    document_type = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    json_metadata = Column(JSON)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    created_by = Column(Text)  # Optional: track who made the change
    
    

class DocumentInsightVersion(Base):
    __tablename__ = 'insight_event_versions1'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    insight_id = Column(UUID(as_uuid=True),  nullable=False)
    version = Column(Integer, nullable=False)
    source_type = Column(Text, nullable=False)
    document_type = Column(Text, nullable=False)
    phrases = Column(ARRAY(Text), nullable=False)
    insight = Column(JSONB)
    extracted_entities = Column(JSONB)
    ner_text = Column(Text)
    event_timestamp = Column(TIMESTAMP(timezone=True), nullable=False)
    chromadb_ids = Column(ARRAY(Text), nullable=False)
    event_type = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    created_by = Column(Text)  # Optional: track who made the change
    
    

