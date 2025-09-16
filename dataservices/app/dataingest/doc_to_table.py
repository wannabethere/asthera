import uuid
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Tuple
from enum import Enum
import pandas as pd

# External libraries
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# Internal imports
from app.schemas.docs.docmodels import Document, DocumentInsight
from app.storage.documents import DocumentChromaStore

logger = logging.getLogger(__name__)


class ExtractionStatus(Enum):
    """Status of extraction workflow"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    NEEDS_CORRECTION = "needs_correction"
    APPROVED = "approved"
    REJECTED = "rejected"


class EntityType(Enum):
    """Types of structured entities"""
    TABLE = "table"
    LIST = "list"
    KEY_VALUE = "key_value"
    FINANCIAL_DATA = "financial_data"
    METRICS = "metrics"
    SCHEDULE = "schedule"
    CONTACT_INFO = "contact_info"


@dataclass
class StructuredField:
    """Represents a field in a structured entity"""
    name: str
    data_type: str  # string, number, date, boolean, etc.
    value: Any
    confidence: float  # 0.0 to 1.0
    source_text: str  # Original text this was extracted from
    validation_rules: List[str] = field(default_factory=list)
    is_required: bool = False


@dataclass
class StructuredEntity:
    """Represents a structured entity extracted from documents"""
    id: str
    entity_type: EntityType
    title: str
    fields: List[StructuredField]
    metadata: Dict[str, Any]
    confidence_score: float
    source_document_id: str
    extraction_timestamp: str
    created_by: str
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame for tabular entities"""
        if self.entity_type != EntityType.TABLE:
            raise ValueError("Can only convert TABLE entities to DataFrame")
        
        data = {}
        for field in self.fields:
            data[field.name] = [field.value]
        
        return pd.DataFrame(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "id": self.id,
            "entity_type": self.entity_type.value,
            "title": self.title,
            "fields": [asdict(field) for field in self.fields],
            "metadata": self.metadata,
            "confidence_score": self.confidence_score,
            "source_document_id": self.source_document_id,
            "extraction_timestamp": self.extraction_timestamp,
            "created_by": self.created_by
        }


@dataclass
class UserFeedback:
    """User feedback on extracted entities"""
    feedback_id: str
    entity_id: str
    field_corrections: Dict[str, Any]  # field_name -> corrected_value
    comments: str
    approval_status: str  # approve, reject, needs_changes
    feedback_timestamp: str
    user_id: str


@dataclass
class ExtractionWorkflow:
    """Manages the extraction and correction workflow"""
    workflow_id: str
    document_id: str
    status: ExtractionStatus
    entities: List[StructuredEntity]
    feedback_history: List[UserFeedback]
    current_iteration: int
    max_iterations: int
    created_at: str
    updated_at: str
    assigned_to: Optional[str] = None


class TableExtractionSchema(BaseModel):
    """Pydantic schema for structured table extraction"""
    table_title: str = Field(description="Title or caption of the table")
    headers: List[str] = Field(description="Column headers of the table")
    rows: List[List[str]] = Field(description="Table rows as list of lists")
    data_types: List[str] = Field(description="Data type for each column (string, number, date, etc.)")
    confidence_scores: List[float] = Field(description="Confidence score for each column (0.0 to 1.0)")
    metadata: Dict[str, Any] = Field(description="Additional metadata about the table")


class EntityExtractionSchema(BaseModel):
    """Pydantic schema for general entity extraction"""
    entities: List[Dict[str, Any]] = Field(description="List of extracted structured entities")
    entity_types: List[str] = Field(description="Type of each entity")
    confidence_scores: List[float] = Field(description="Confidence score for each entity")
    relationships: List[Dict[str, str]] = Field(description="Relationships between entities")


class StructuredTableExtractor:
    """LLM-based extractor for structured tables and entities"""
    
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.1):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.setup_extraction_chains()
        
    def setup_extraction_chains(self):
        """Set up LangChain extraction chains"""
        
        # Table extraction chain
        table_template = """
        You are an expert at extracting structured tables from documents.
        
        Document Content:
        {content}
        
        Extract all tables from this content. For each table:
        1. Identify the table title/caption
        2. Extract column headers
        3. Extract all data rows
        4. Determine data type for each column
        5. Assign confidence scores (0.0 to 1.0) for each column based on extraction certainty
        6. Include relevant metadata
        
        Be very careful with:
        - Numeric data (preserve decimal places, handle currencies)
        - Dates (identify format and convert consistently)
        - Missing or empty cells (represent as null)
        - Merged cells (distribute content appropriately)
        
        If no clear tables are found, return empty lists.
        
        {format_instructions}
        """
        
        table_prompt = ChatPromptTemplate.from_template(table_template)
        table_parser = PydanticOutputParser(pydantic_object=TableExtractionSchema)
        self.table_chain = table_prompt | self.llm | table_parser
        
        # General entity extraction chain
        entity_template = """
        You are an expert at extracting structured entities from documents.
        
        Document Content:
        {content}
        
        Target Entity Types: {entity_types}
        
        Extract structured entities of the specified types. For each entity:
        1. Identify the entity type (table, list, key-value pairs, metrics, etc.)
        2. Extract all relevant fields and their values
        3. Determine data types for each field
        4. Assign confidence scores based on extraction certainty
        5. Identify relationships between entities
        
        Focus on:
        - Financial data (revenue, costs, margins, etc.)
        - Key metrics and KPIs
        - Contact information
        - Schedules and dates
        - Lists and categories
        - Any structured data that can be organized into fields
        
        {format_instructions}
        """
        
        entity_prompt = ChatPromptTemplate.from_template(entity_template)
        entity_parser = PydanticOutputParser(pydantic_object=EntityExtractionSchema)
        self.entity_chain = entity_prompt | self.llm | entity_parser
        
        # Correction chain for user feedback
        correction_template = """
        You are helping to correct extracted structured data based on user feedback.
        
        Original Extracted Data:
        {original_data}
        
        User Feedback:
        {user_feedback}
        
        User Comments: {comments}
        
        Apply the user's corrections to the data. Maintain the same structure but update:
        1. Field values that the user corrected
        2. Data types if the user indicated they were wrong
        3. Confidence scores (increase for corrected fields)
        4. Any structural changes the user requested
        
        Return the corrected data in the same format as the original.
        
        {format_instructions}
        """
        
        correction_prompt = ChatPromptTemplate.from_template(correction_template)
        self.correction_chain = correction_prompt | self.llm | JsonOutputParser()
    
    def extract_tables(self, content: str) -> List[StructuredEntity]:
        """Extract tables from document content"""
        try:
            logger.info("Extracting tables from document content")
            
            result = self.table_chain.invoke({
                "content": content[:10000],  # Limit content length
                "format_instructions": PydanticOutputParser(pydantic_object=TableExtractionSchema).get_format_instructions()
            })
            
            entities = []
            
            # Convert table schema to StructuredEntity
            if result.headers and result.rows:
                fields = []
                
                # Create fields for each column
                for i, header in enumerate(result.headers):
                    data_type = result.data_types[i] if i < len(result.data_types) else "string"
                    confidence = result.confidence_scores[i] if i < len(result.confidence_scores) else 0.8
                    
                    # Collect all values for this column
                    column_values = []
                    for row in result.rows:
                        if i < len(row):
                            column_values.append(row[i])
                        else:
                            column_values.append(None)
                    
                    field = StructuredField(
                        name=header,
                        data_type=data_type,
                        value=column_values,
                        confidence=confidence,
                        source_text=f"Table column: {header}"
                    )
                    fields.append(field)
                
                entity = StructuredEntity(
                    id=str(uuid.uuid4()),
                    entity_type=EntityType.TABLE,
                    title=result.table_title or "Extracted Table",
                    fields=fields,
                    metadata=result.metadata,
                    confidence_score=sum(result.confidence_scores) / len(result.confidence_scores) if result.confidence_scores else 0.8,
                    source_document_id="",  # Will be set by caller
                    extraction_timestamp=datetime.now().isoformat(),
                    created_by="system"
                )
                entities.append(entity)
            
            logger.info(f"Extracted {len(entities)} table entities")
            return entities
            
        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
            return []
    
    def extract_entities(self, content: str, entity_types: List[EntityType]) -> List[StructuredEntity]:
        """Extract structured entities of specified types"""
        try:
            logger.info(f"Extracting entities of types: {[et.value for et in entity_types]}")
            
            entity_types_str = ", ".join([et.value for et in entity_types])
            
            result = self.entity_chain.invoke({
                "content": content[:10000],
                "entity_types": entity_types_str,
                "format_instructions": PydanticOutputParser(pydantic_object=EntityExtractionSchema).get_format_instructions()
            })
            
            entities = []
            
            for i, entity_data in enumerate(result.entities):
                entity_type_str = result.entity_types[i] if i < len(result.entity_types) else "key_value"
                confidence = result.confidence_scores[i] if i < len(result.confidence_scores) else 0.7
                
                # Convert entity data to StructuredField objects
                fields = []
                for key, value in entity_data.items():
                    field = StructuredField(
                        name=key,
                        data_type=self._infer_data_type(value),
                        value=value,
                        confidence=confidence,
                        source_text=f"Entity field: {key}"
                    )
                    fields.append(field)
                
                entity = StructuredEntity(
                    id=str(uuid.uuid4()),
                    entity_type=EntityType(entity_type_str),
                    title=entity_data.get("title", f"Entity {i+1}"),
                    fields=fields,
                    metadata={"extraction_method": "llm_entity_extraction"},
                    confidence_score=confidence,
                    source_document_id="",  # Will be set by caller
                    extraction_timestamp=datetime.now().isoformat(),
                    created_by="system"
                )
                entities.append(entity)
            
            logger.info(f"Extracted {len(entities)} structured entities")
            return entities
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []
    
    def apply_corrections(self, entity: StructuredEntity, feedback: UserFeedback) -> StructuredEntity:
        """Apply user corrections to an entity"""
        try:
            logger.info(f"Applying corrections to entity {entity.id}")
            
            original_data = entity.to_dict()
            
            result = self.correction_chain.invoke({
                "original_data": json.dumps(original_data, indent=2),
                "user_feedback": json.dumps(feedback.field_corrections, indent=2),
                "comments": feedback.comments,
                "format_instructions": "Return corrected data as JSON"
            })
            
            # Apply corrections to the entity
            for field_name, new_value in feedback.field_corrections.items():
                for field in entity.fields:
                    if field.name == field_name:
                        field.value = new_value
                        field.confidence = min(1.0, field.confidence + 0.1)  # Increase confidence
                        break
            
            # Update metadata
            entity.metadata["corrected"] = True
            entity.metadata["correction_timestamp"] = datetime.now().isoformat()
            entity.metadata["corrected_by"] = feedback.user_id
            
            logger.info(f"Successfully applied corrections to entity {entity.id}")
            return entity
            
        except Exception as e:
            logger.error(f"Error applying corrections: {e}")
            return entity
    
    def _infer_data_type(self, value: Any) -> str:
        """Infer data type from value"""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            # Try to infer from string content
            str_value = str(value).strip()
            if str_value.replace(".", "").replace("-", "").isdigit():
                return "number"
            elif str_value.lower() in ["true", "false", "yes", "no"]:
                return "boolean"
            else:
                return "string"


class WorkflowManager:
    """Manages extraction workflows and user feedback"""
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        self.active_workflows: Dict[str, ExtractionWorkflow] = {}
    
    def create_workflow(self, document_id: str, assigned_to: Optional[str] = None, 
                       max_iterations: int = 3) -> ExtractionWorkflow:
        """Create a new extraction workflow"""
        workflow = ExtractionWorkflow(
            workflow_id=str(uuid.uuid4()),
            document_id=document_id,
            status=ExtractionStatus.PENDING,
            entities=[],
            feedback_history=[],
            current_iteration=0,
            max_iterations=max_iterations,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            assigned_to=assigned_to
        )
        
        self.active_workflows[workflow.workflow_id] = workflow
        logger.info(f"Created workflow {workflow.workflow_id} for document {document_id}")
        
        return workflow
    
    def submit_feedback(self, workflow_id: str, entity_id: str, 
                       field_corrections: Dict[str, Any], comments: str,
                       approval_status: str, user_id: str) -> bool:
        """Submit user feedback for an entity"""
        if workflow_id not in self.active_workflows:
            logger.error(f"Workflow {workflow_id} not found")
            return False
        
        workflow = self.active_workflows[workflow_id]
        
        feedback = UserFeedback(
            feedback_id=str(uuid.uuid4()),
            entity_id=entity_id,
            field_corrections=field_corrections,
            comments=comments,
            approval_status=approval_status,
            feedback_timestamp=datetime.now().isoformat(),
            user_id=user_id
        )
        
        workflow.feedback_history.append(feedback)
        workflow.updated_at = datetime.now().isoformat()
        
        # Update workflow status based on feedback
        if approval_status == "approve":
            if all(self._is_entity_approved(entity.id, workflow) for entity in workflow.entities):
                workflow.status = ExtractionStatus.APPROVED
        elif approval_status == "reject":
            workflow.status = ExtractionStatus.REJECTED
        else:
            workflow.status = ExtractionStatus.NEEDS_CORRECTION
            workflow.current_iteration += 1
        
        logger.info(f"Submitted feedback for entity {entity_id} in workflow {workflow_id}")
        return True
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a workflow"""
        if workflow_id not in self.active_workflows:
            return None
        
        workflow = self.active_workflows[workflow_id]
        
        return {
            "workflow_id": workflow.workflow_id,
            "status": workflow.status.value,
            "current_iteration": workflow.current_iteration,
            "max_iterations": workflow.max_iterations,
            "entities_count": len(workflow.entities),
            "pending_feedback": self._get_pending_feedback_count(workflow),
            "last_updated": workflow.updated_at
        }
    
    def _is_entity_approved(self, entity_id: str, workflow: ExtractionWorkflow) -> bool:
        """Check if an entity has been approved"""
        entity_feedback = [f for f in workflow.feedback_history if f.entity_id == entity_id]
        if not entity_feedback:
            return False
        
        latest_feedback = max(entity_feedback, key=lambda x: x.feedback_timestamp)
        return latest_feedback.approval_status == "approve"
    
    def _get_pending_feedback_count(self, workflow: ExtractionWorkflow) -> int:
        """Count entities awaiting feedback"""
        approved_entities = set()
        for feedback in workflow.feedback_history:
            if feedback.approval_status == "approve":
                approved_entities.add(feedback.entity_id)
        
        return len(workflow.entities) - len(approved_entities)


class StructuredExtractionService:
    """Main service for structured extraction with workflow management"""
    
    def __init__(self, extractor: StructuredTableExtractor = None, 
                 workflow_manager: WorkflowManager = None,
                 chroma_store: DocumentChromaStore = None):
        self.extractor = extractor or StructuredTableExtractor()
        self.workflow_manager = workflow_manager or WorkflowManager()
        self.chroma_store = chroma_store
    
    def start_extraction_workflow(self, document: Document, 
                                 entity_types: List[EntityType] = None,
                                 assigned_to: Optional[str] = None) -> ExtractionWorkflow:
        """Start a new structured extraction workflow"""
        
        # Create workflow
        workflow = self.workflow_manager.create_workflow(
            document_id=str(document.id),
            assigned_to=assigned_to
        )
        
        # Perform initial extraction
        entities = []
        
        # Extract tables
        table_entities = self.extractor.extract_tables(document.content)
        for entity in table_entities:
            entity.source_document_id = str(document.id)
        entities.extend(table_entities)
        
        # Extract other entity types if specified
        if entity_types:
            other_entities = self.extractor.extract_entities(document.content, entity_types)
            for entity in other_entities:
                entity.source_document_id = str(document.id)
            entities.extend(other_entities)
        
        # Add entities to workflow
        workflow.entities = entities
        workflow.status = ExtractionStatus.AWAITING_REVIEW
        workflow.updated_at = datetime.now().isoformat()
        
        logger.info(f"Started extraction workflow {workflow.workflow_id} with {len(entities)} entities")
        
        return workflow
    
    def submit_user_feedback(self, workflow_id: str, entity_id: str,
                           corrections: Dict[str, Any], comments: str = "",
                           approval: str = "needs_changes", user_id: str = "user") -> bool:
        """Submit user feedback and apply corrections"""
        
        success = self.workflow_manager.submit_feedback(
            workflow_id=workflow_id,
            entity_id=entity_id,
            field_corrections=corrections,
            comments=comments,
            approval_status=approval,
            user_id=user_id
        )
        
        if success and corrections:
            # Apply corrections to the entity
            workflow = self.workflow_manager.active_workflows[workflow_id]
            entity = next((e for e in workflow.entities if e.id == entity_id), None)
            
            if entity:
                feedback = workflow.feedback_history[-1]  # Latest feedback
                corrected_entity = self.extractor.apply_corrections(entity, feedback)
                
                # Update entity in workflow
                for i, e in enumerate(workflow.entities):
                    if e.id == entity_id:
                        workflow.entities[i] = corrected_entity
                        break
        
        return success
    
    def get_extraction_results(self, workflow_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get extraction results for a workflow"""
        if workflow_id not in self.workflow_manager.active_workflows:
            return None
        
        workflow = self.workflow_manager.active_workflows[workflow_id]
        
        return [entity.to_dict() for entity in workflow.entities]
    
    def finalize_workflow(self, workflow_id: str) -> bool:
        """Finalize and store approved entities"""
        if workflow_id not in self.workflow_manager.active_workflows:
            return False
        
        workflow = self.workflow_manager.active_workflows[workflow_id]
        
        if workflow.status != ExtractionStatus.APPROVED:
            logger.warning(f"Cannot finalize workflow {workflow_id} - status is {workflow.status}")
            return False
        
        # Store entities in ChromaDB if available
        if self.chroma_store:
            for entity in workflow.entities:
                self._store_entity_in_chromadb(entity)
        
        # Store in database if available
        if self.workflow_manager.db_manager:
            for entity in workflow.entities:
                self.workflow_manager.db_manager.store_structured_entity(entity)
        
        # Clean up workflow
        del self.workflow_manager.active_workflows[workflow_id]
        
        logger.info(f"Finalized workflow {workflow_id} with {len(workflow.entities)} entities")
        return True
    
    def _store_entity_in_chromadb(self, entity: StructuredEntity):
        """Store structured entity in ChromaDB"""
        try:
            # Convert entity to searchable text
            searchable_text = f"{entity.title}\n"
            for field in entity.fields:
                searchable_text += f"{field.name}: {field.value}\n"
            
            # Store as document
            doc_data = {
                "metadata": {
                    "entity_id": entity.id,
                    "entity_type": entity.entity_type.value,
                    "source_document_id": entity.source_document_id,
                    "extraction_timestamp": entity.extraction_timestamp,
                    "confidence_score": entity.confidence_score
                },
                "data": searchable_text
            }
            
            self.chroma_store.add_documents([doc_data])
            
        except Exception as e:
            logger.error(f"Error storing entity in ChromaDB: {e}")


# Example API interface
class StructuredExtractionAPI:
    """API interface for structured extraction workflow"""
    
    def __init__(self, service: StructuredExtractionService):
        self.service = service
    
    def extract_structured_data(self, document: Document, entity_types: List[str] = None) -> Dict[str, Any]:
        """API endpoint to start extraction"""
        entity_type_enums = []
        if entity_types:
            entity_type_enums = [EntityType(et) for et in entity_types if et in EntityType.__members__]
        
        workflow = self.service.start_extraction_workflow(document, entity_type_enums)
        
        return {
            "workflow_id": workflow.workflow_id,
            "status": workflow.status.value,
            "entities": [entity.to_dict() for entity in workflow.entities]
        }
    
    def submit_corrections(self, workflow_id: str, entity_id: str, 
                         corrections: Dict[str, Any], approval: str = "needs_changes") -> Dict[str, Any]:
        """API endpoint to submit corrections"""
        success = self.service.submit_user_feedback(
            workflow_id=workflow_id,
            entity_id=entity_id,
            corrections=corrections,
            approval=approval
        )
        
        status = self.service.workflow_manager.get_workflow_status(workflow_id)
        
        return {
            "success": success,
            "workflow_status": status
        }
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """API endpoint to get workflow status"""
        return self.service.workflow_manager.get_workflow_status(workflow_id) or {"error": "Workflow not found"}
    
    def finalize_extraction(self, workflow_id: str) -> Dict[str, Any]:
        """API endpoint to finalize extraction"""
        success = self.service.finalize_workflow(workflow_id)
        
        return {"success": success, "message": "Workflow finalized" if success else "Failed to finalize"}


if __name__ == "__main__":
    # Example usage
    from app.models.dbmodels import Document
    
    # Create document
    document = Document(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        version=1,
        content="""
        Financial Report Q1 2024
        
        Revenue by Quarter:
        Q1 2023: $45.2M
        Q2 2023: $52.1M
        Q3 2023: $48.9M
        Q4 2023: $61.3M
        Q1 2024: $58.7M
        
        Key Metrics:
        - Customer Acquisition Cost: $125
        - Lifetime Value: $2,400
        - Monthly Recurring Revenue: $12.3M
        - Churn Rate: 2.1%
        """,
        json_metadata={},
        source_type="upload",
        document_type="financial_report",
        created_at=datetime.now()
    )
    
    # Initialize service
    service = StructuredExtractionService()
    
    # Start extraction workflow
    workflow = service.start_extraction_workflow(
        document=document,
        entity_types=[EntityType.TABLE, EntityType.FINANCIAL_DATA, EntityType.METRICS]
    )
    
    print(f"Started workflow: {workflow.workflow_id}")
    print(f"Extracted {len(workflow.entities)} entities")
    
    # Simulate user feedback
    if workflow.entities:
        entity = workflow.entities[0]
        print(f"\nReviewing entity: {entity.title}")
        
        # Submit corrections
        corrections = {
            "Q1 2024": "$59.2M"  # User corrects a value
        }
        
        service.submit_user_feedback(
            workflow_id=workflow.workflow_id,
            entity_id=entity.id,
            corrections=corrections,
            comments="Updated Q1 2024 revenue to reflect final numbers",
            approval="approve"
        )
        
        print("Submitted user feedback and corrections")
        
        # Check status
        status = service.workflow_manager.get_workflow_status(workflow.workflow_id)
        print(f"Workflow status: {status}")