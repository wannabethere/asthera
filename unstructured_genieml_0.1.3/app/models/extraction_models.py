"""
Models used in document extraction and analysis pipelines.
These models represent the data structures used during document processing and analysis.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class DocumentChunk:
    """Represents a chunk of a document for processing"""
    chunk_id: str
    content: str
    metadata: Dict[str, Any]


@dataclass
class BusinessEntity:
    """Represents a business entity extracted from text"""
    name: str
    entity_type: str  # company, product, service, metric, etc.
    attributes: Dict[str, Any]  # additional properties of the entity
    mentions: List[str]  # contexts where this entity is mentioned
    relevance_score: float  # how relevant this entity is to the question (0.0-1.0)


@dataclass
class ExtractedPhrase:
    """Represents an important phrase with sentiment and context"""
    text: str
    sentiment: str  # positive, negative, neutral
    importance_score: float  # 0.0 to 1.0
    source_context: str
    category: Optional[str] = None


@dataclass
class ChunkAnalysisResult:
    """Complete analysis results for a document chunk"""
    chunk_id: str
    business_entities: List[BusinessEntity]
    key_phrases: List[ExtractedPhrase]
    sentiment_phrases: List[ExtractedPhrase]
    overall_sentiment: str
    analysis_timestamp: str


@dataclass
class AnalysisResult:
    """Temporary container for document analysis results before storage in ChromaDB"""
    result_id: str
    document_id: str
    source_type: str
    doc_type: str
    entities: List[Dict[str, Any]]
    key_phrases: List[Dict[str, Any]]
    sentiment: Dict[str, Any]
    total_chunks_analyzed: int
    analysis_timestamp: str
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class AnalysisDocument:
    """Temporary container for document metadata during analysis"""
    document_id: str
    content: str
    metadata: Dict[str, Any]
    source_type: str
    doc_type: str
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now() 