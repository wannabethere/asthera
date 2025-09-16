import logging
import time
import asyncio
# Parse the JSON response
import json
import re
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from enum import Enum

logger = logging.getLogger("SelfCorrectingPlanner")

# Configure the data sources available to the planner
class SalesforceObjectType(str, Enum):
    """Salesforce object types available in the system."""
    CONTACT = "Contact"
    OPPORTUNITY = "Opportunity"
    ACCOUNT = "Account"
    LEAD = "Lead"
    TASK = "Task"
    CONVERSION = "Conversion"
    
class GongDataType(str, Enum):
    """Gong data types available in the system."""
    CALL = "Call"
    ACTIVITY = "Activity"
    USER = "User"
    
class DocumentType(str, Enum):
    """Document types available in the system."""
    GOOGLE_DRIVE_PDF = "GoogleDrivePDF"
    GONG_TRANSCRIPT = "GongTranscript"
    
class DataSourceConfig(BaseModel):
    """Configuration for data sources available to the planner."""
    salesforce_objects: List[SalesforceObjectType] = Field(default_factory=list)
    gong_data: List[GongDataType] = Field(default_factory=list)
    document_types: List[DocumentType] = Field(default_factory=list)
    
    @classmethod
    def default_config(cls) -> "DataSourceConfig":
        """Create a default configuration with all data sources enabled."""
        return cls(
            salesforce_objects=[obj for obj in SalesforceObjectType],
            gong_data=[data for data in GongDataType],
            document_types=[doc for doc in DocumentType]
        )
    
    def get_all_sources(self) -> List[str]:
        """Get a list of all available data sources."""
        sources = []
        sources.extend([f"Salesforce.{obj.value}" for obj in self.salesforce_objects])
        sources.extend([f"Gong.{data.value}" for data in self.gong_data])
        sources.extend([f"Document.{doc.value}" for doc in self.document_types])
        return sources
    
    def get_salesforce_schema(self) -> Dict[str, Dict[str, str]]:
        """Get schema information for Salesforce objects."""
        schema = {}
        
        if SalesforceObjectType.CONTACT in self.salesforce_objects:
            schema["Contact"] = {
                "Id": "string",
                "FirstName": "string",
                "LastName": "string",
                "Email": "string",
                "Phone": "string",
                "AccountId": "reference",
                "Title": "string",
                "Department": "string",
                "CreatedDate": "datetime",
                "LastModifiedDate": "datetime"
            }
            
        if SalesforceObjectType.OPPORTUNITY in self.salesforce_objects:
            schema["Opportunity"] = {
                "Id": "string",
                "Name": "string",
                "StageName": "string",
                "CloseDate": "date",
                "Amount": "currency",
                "Probability": "percent",
                "AccountId": "reference",
                "OwnerId": "reference",
                "Type": "string",
                "LeadSource": "string",
                "IsClosed": "boolean",
                "IsWon": "boolean",
                "CreatedDate": "datetime",
                "LastModifiedDate": "datetime"
            }
            
        if SalesforceObjectType.ACCOUNT in self.salesforce_objects:
            schema["Account"] = {
                "Id": "string",
                "Name": "string",
                "Type": "string",
                "Industry": "string",
                "BillingAddress": "address",
                "ShippingAddress": "address",
                "Phone": "string",
                "Website": "url",
                "AnnualRevenue": "currency",
                "NumberOfEmployees": "integer",
                "CreatedDate": "datetime",
                "LastModifiedDate": "datetime"
            }
            
        if SalesforceObjectType.LEAD in self.salesforce_objects:
            schema["Lead"] = {
                "Id": "string",
                "FirstName": "string",
                "LastName": "string",
                "Company": "string",
                "Status": "string",
                "Email": "string",
                "Phone": "string",
                "Industry": "string",
                "Rating": "string",
                "CreatedDate": "datetime",
                "LastModifiedDate": "datetime"
            }
            
        if SalesforceObjectType.TASK in self.salesforce_objects:
            schema["Task"] = {
                "Id": "string",
                "Subject": "string",
                "Status": "string",
                "Priority": "string",
                "WhatId": "reference",
                "WhoId": "reference",
                "OwnerId": "reference",
                "ActivityDate": "date",
                "Description": "textarea",
                "CreatedDate": "datetime",
                "LastModifiedDate": "datetime"
            }
            
        if SalesforceObjectType.CONVERSION in self.salesforce_objects:
            schema["Conversion"] = {
                "Id": "string",
                "LeadId": "reference",
                "ConvertedAccountId": "reference",
                "ConvertedContactId": "reference",
                "ConvertedOpportunityId": "reference",
                "ConversionDate": "datetime",
                "CreatedDate": "datetime",
                "LastModifiedDate": "datetime"
            }
            
        return schema
    
    def get_gong_schema(self) -> Dict[str, Dict[str, str]]:
        """Get schema information for Gong data."""
        schema = {}
        
        if GongDataType.CALL in self.gong_data:
            schema["Call"] = {
                "id": "string",
                "title": "string",
                "date": "datetime",
                "duration": "integer",
                "participants": "array",
                "transcript": "text",
                "sentiment_score": "float",
                "topics": "array",
                "recording_url": "url"
            }
            
        if GongDataType.ACTIVITY in self.gong_data:
            schema["Activity"] = {
                "id": "string",
                "user_id": "string",
                "type": "string",
                "date": "datetime",
                "duration": "integer",
                "metadata": "object"
            }
            
        if GongDataType.USER in self.gong_data:
            schema["User"] = {
                "id": "string",
                "name": "string",
                "email": "string",
                "role": "string",
                "department": "string",
                "manager_id": "string"
            }
            
        return schema
    
    def get_document_schema(self) -> Dict[str, Dict[str, str]]:
        """Get schema information for document types."""
        schema = {}
        
        if DocumentType.GOOGLE_DRIVE_PDF in self.document_types:
            schema["GoogleDrivePDF"] = {
                "id": "string",
                "title": "string",
                "created_date": "datetime",
                "modified_date": "datetime",
                "owner": "string",
                "content": "text",
                "pages": "integer",
                "file_size": "integer",
                "url": "url"
            }
            
        if DocumentType.GONG_TRANSCRIPT in self.document_types:
            schema["GongTranscript"] = {
                "id": "string",
                "call_id": "string",
                "date": "datetime",
                "speaker_turns": "array",
                "content": "text",
                "topics": "array",
                "sentiment": "object"
            }
            
        return schema

class DataSourceMetadata(BaseModel):
    """Base metadata about a data source in the system."""
    source_id: str
    source_type: str
    
class DocumentMetadata(DataSourceMetadata):
    """Metadata about a document in the system."""
    title: Optional[str] = None
    date: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    document_type: Optional[DocumentType] = None
    file_size: Optional[int] = None
    page_count: Optional[int] = None
    
class SalesforceMetadata(DataSourceMetadata):
    """Metadata about a Salesforce object in the system."""
    object_type: SalesforceObjectType
    name: Optional[str] = None
    created_date: Optional[str] = None
    last_modified_date: Optional[str] = None
    owner: Optional[str] = None
    related_ids: Dict[str, str] = Field(default_factory=dict)
    
class GongMetadata(DataSourceMetadata):
    """Metadata about a Gong data object in the system."""
    data_type: GongDataType
    title: Optional[str] = None
    date: Optional[str] = None
    duration: Optional[int] = None
    participants: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    
class FunctionDefinition(BaseModel):
    """Definition of a function available to the planner."""
    name: str
    description: str
    parameters: Dict[str, Any]
    example_usage: Optional[str] = None
    applicable_sources: List[str] = Field(default_factory=list)

class PlanningStrategy(str, Enum):
    """Different strategies the planner can use."""
    DIRECT = "direct"           # Direct answer when confident
    DOCUMENT_RETRIEVAL = "document_retrieval"  # Retrieve specific documents
    SALESFORCE_QUERY = "salesforce_query"  # Query Salesforce objects
    GONG_ANALYSIS = "gong_analysis"  # Analyze Gong call data
    MULTI_HOP = "multi_hop"     # Multiple retrieval steps
    COMPARISON = "comparison"   # Compare multiple documents/sources
    TIMELINE = "timeline"       # Time-based analysis
    NUMERICAL = "numerical"     # Calculation-based
    CROSS_SOURCE = "cross_source"  # Combine data from multiple sources
    
class PlanStep(BaseModel):
    """A single step in the execution plan."""
    step_number: int
    action: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str
    
    def dict(self):
        """Convert to dictionary."""
        return {
            "step_number": self.step_number,
            "action": self.action,
            "parameters": self.parameters,
            "reasoning": self.reasoning
        }

class Plan(BaseModel):
    """The execution plan for answering a question."""
    original_question: str
    reframed_question: str
    strategy: PlanningStrategy
    confidence: float = Field(ge=0.0, le=1.0)
    steps: List[PlanStep] = Field(default_factory=list)
    fallback_plan: Optional["Plan"] = None
    
    def dict(self):
        """Convert to dictionary."""
        result = {
            "original_question": self.original_question,
            "reframed_question": self.reframed_question,
            "strategy": self.strategy,
            "confidence": self.confidence,
            "steps": [step.dict() for step in self.steps]
        }
        if self.fallback_plan:
            result["fallback_plan"] = self.fallback_plan.dict()
        return result

class SelfCorrectingPlanner:
    """
    A planner that analyzes user questions and develops optimal retrieval strategies.
    Integrates with vector stores for semantic search and example retrieval.
    Configured with specific data sources available in the system.
    """
    
    def __init__(
        self, 
        data_source_config: Optional[DataSourceConfig] = None,
        llm: Optional[ChatOpenAI] = None,
        max_documents: int = 25
    ):
        """
        Initialize the planner.
        
        Args:
            data_source_config: Configuration of available data sources
            llm: Language model for planning
            max_documents: Maximum number of documents to retrieve per source
        """
        self.llm = llm or ChatOpenAI(model="gpt-4o", temperature=0)
        self.data_source_config = data_source_config or DataSourceConfig.default_config()
        self.max_documents = max_documents
        
    async def plan(
        self, 
        question: str,
        metadata_store,  # Vector store interface
        function_examples_store,  # Vector store interface
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> Plan:
        """
        Create a plan for answering the user's question.
        
        Args:
            question: The user's question
            metadata_store: Vector store containing metadata for all data sources
            function_examples_store: Vector store containing function usage examples
            chat_history: Optional conversation history
            
        Returns:
            A Plan object with the execution strategy
        """
        # Step 1: Analyze the question to identify key entities, intents, and constraints
        question_analysis = await self._analyze_question(question, chat_history)
        
        # Step 2: Determine which data sources are relevant to this question
        relevant_sources = await self._identify_relevant_sources(
            question, 
            question_analysis
        )
        
        # Step 3: Retrieve relevant metadata based on the question and identified sources
        relevant_metadata = await self._retrieve_relevant_metadata(
            question, 
            question_analysis,
            relevant_sources,
            metadata_store
        )
        
        # Step 4: Retrieve relevant function examples
        relevant_functions = await self._retrieve_relevant_functions(
            question, 
            question_analysis,
            relevant_sources,
            function_examples_store
        )
        
        # Step 5: Generate an execution plan
        plan = await self._generate_plan(
            question,
            question_analysis,
            relevant_sources,
            relevant_metadata,
            relevant_functions
        )
        
        # Step 6: Validate and potentially correct the plan
        corrected_plan = await self._validate_and_correct_plan(plan, relevant_sources)
        
        return corrected_plan
        
    async def _identify_relevant_sources(
        self,
        question: str,
        question_analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Identify which data sources are most relevant to the question.
        
        Args:
            question: The user's question
            question_analysis: Analysis of the question
            
        Returns:
            Dictionary mapping source names to relevance scores
        """
        system_prompt = """You are an expert at determining which data sources are relevant to a user's question.
        Your task is to analyze the question and identify which of the available data sources would be most useful
        for answering it.
        
        For each data source, assign a relevance score from 0.0 to 1.0, where:
        - 0.0 means completely irrelevant
        - 1.0 means highly relevant and essential
        
        Consider:
        1. Explicit mentions of source types (e.g., "Salesforce opportunities", "Gong calls")
        2. Question type and what information would be needed to answer it
        3. Entities mentioned and where information about them would be stored
        4. Temporal aspects and which sources would have that historical data
        
        Format your response as a JSON object mapping source names to relevance scores.
        """
        
        # List all available sources from the configuration
        available_sources = self.data_source_config.get_all_sources()
        
        try:
            # Get the schemas for the different source types
            salesforce_schema = self.data_source_config.get_salesforce_schema()
            gong_schema = self.data_source_config.get_gong_schema()
            document_schema = self.data_source_config.get_document_schema()
            
            # Combine all schemas for context
            all_schemas = {
                "Salesforce": salesforce_schema,
                "Gong": gong_schema,
                "Documents": document_schema
            }
            
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"""
                    Question: {question}
                    
                    Question Analysis: {question_analysis}
                    
                    Available Data Sources: {available_sources}
                    
                    Source Schemas: {all_schemas}
                    
                    Please determine the relevance of each data source for this question.
                    """)
                ]
            )
            
            # Parse the JSON response
            import json
            import re
            
            # Extract JSON from the response
            json_match = re.search(r'{.*}', str(response.content), re.DOTALL)
            if json_match:
                relevance_scores = json.loads(json_match.group(0))
                
                # Filter out irrelevant sources (score < 0.2)
                relevant_sources = {
                    source: score for source, score in relevance_scores.items() 
                    if score >= 0.2
                }
                
                return relevant_sources
            else:
                # If parsing fails, return all sources with default relevance
                logger.error("Failed to parse source relevance from LLM response")
                return {source: 0.5 for source in available_sources}
                
        except Exception as e:
            logger.error(f"Error identifying relevant sources: {e}")
            # Return all sources with default relevance
            return {source: 0.5 for source in available_sources}
    
    async def _analyze_question(
        self, 
        question: str,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Analyze the question to extract key elements needed for planning.
        
        Args:
            question: The user's question
            chat_history: Optional conversation history
            
        Returns:
            Dictionary with analysis results
        """
        system_prompt = """You are an expert question analyzer for a document retrieval system.
        Your task is to analyze the user's question and extract key information that will help with document retrieval.
        
        Analyze the question for:
        1. Key entities (companies, products, people, etc.)
        2. Temporal aspects (time periods, dates, before/after relationships)
        3. Question type (factual, comparative, analytical, etc.)
        4. Required information types (numerical data, transcripts, sales information)
        5. Any implicit assumptions or constraints
        
        Format your response as a JSON object with these keys.
        """
        
        context = {
            "question": question
        }
        
        if chat_history:
            # Format chat history for context
            formatted_history = []
            for msg in chat_history[-5:]:  # Include last 5 messages for context
                role = "user" if msg.get("message_type") == "human" else "assistant"
                formatted_history.append(f"{role}: {msg.get('message_content', '')}")
            
            context["chat_history"] = "\n".join(formatted_history)
        
        try:
            analysis_response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Here is the question to analyze:\n\n{question}\n\nProvide your analysis:")
                ]
            )
            
            # Parse the JSON response
            import json
            import re
            
            # Extract JSON from the response
            json_match = re.search(r'{.*}', str(analysis_response.content), re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(0))
                return analysis
            else:
                logger.error("Failed to extract JSON from analysis response")
                return {
                    "key_entities": [],
                    "temporal_aspects": {},
                    "question_type": "unknown",
                    "required_information": [],
                    "constraints": []
                }
                
        except Exception as e:
            logger.error(f"Error analyzing question: {e}")
            return {
                "key_entities": [],
                "temporal_aspects": {},
                "question_type": "unknown",
                "required_information": [],
                "constraints": []
            }
    
    async def _retrieve_relevant_metadata(
        self,
        question: str,
        question_analysis: Dict[str, Any],
        relevant_sources: Dict[str, float],
        metadata_store
    ) -> Dict[str, List[Union[DocumentMetadata, SalesforceMetadata, GongMetadata]]]:
        """
        Retrieve relevant metadata based on the question and identified relevant sources.
        
        Args:
            question: The original question
            question_analysis: The analysis of the question
            relevant_sources: Dictionary of relevant sources with their scores
            metadata_store: Vector store with metadata for all data sources
            
        Returns:
            Dictionary mapping source types to lists of relevant metadata
        """
        # Convert key entities and constraints into search terms
        search_terms = []
        
        # Add key entities
        for entity in question_analysis.get("key_entities", []):
            search_terms.append(entity)
            
        # Add temporal terms if they exist
        temporal = question_analysis.get("temporal_aspects", {})
        if temporal.get("start_date"):
            search_terms.append(temporal.get("start_date"))
        if temporal.get("end_date"):
            search_terms.append(temporal.get("end_date"))
        if temporal.get("period"):
            search_terms.append(temporal.get("period"))
            
        # Create an enhanced search query
        enhanced_query = f"{question} {' '.join(search_terms)}"
        
        # Group sources by type (Salesforce, Gong, Document)
        source_groups = {
            "Salesforce": [],
            "Gong": [],
            "Document": []
        }
        
        for source, score in relevant_sources.items():
            source_type, _ = source.split(".", 1)
            source_groups[source_type].append(source)
        
        # Results will be organized by source type
        results = {
            "Salesforce": [],
            "Gong": [],
            "Document": []
        }
        
        # Search each source group and retrieve relevant metadata
        for group_name, sources in source_groups.items():
            if not sources:
                continue
                
            # Create a filter to search only within these sources
            source_filter = {"source_type": {"$in": sources}}
            
            # Use the semantic search functionality of the vector store
            search_results = metadata_store.semantic_search(
                query=enhanced_query,
                filter=source_filter,
                top_k=min(self.max_documents, 5 * len(sources))  # Get more results for more sources, but respect max limit
            )
            
            # Convert search results to appropriate metadata objects
            for result in search_results:
                try:
                    metadata = result["metadata"]
                    source_type = metadata.get("source_type", "").split(".", 1)[0]
                    
                    if source_type == "Salesforce":
                        metadata_obj = SalesforceMetadata(**metadata)
                        results["Salesforce"].append(metadata_obj)
                    elif source_type == "Gong":
                        metadata_obj = GongMetadata(**metadata)
                        results["Gong"].append(metadata_obj)
                    elif source_type == "Document":
                        metadata_obj = DocumentMetadata(**metadata)
                        results["Document"].append(metadata_obj)
                        
                except Exception as e:
                    logger.error(f"Error converting search result to metadata object: {e}")
        
        return results
    
    async def _retrieve_relevant_functions(
        self,
        question: str,
        question_analysis: Dict[str, Any],
        relevant_sources: Dict[str, float],
        function_examples_store
    ) -> List[FunctionDefinition]:
        """
        Retrieve relevant function examples based on the question and identified sources.
        
        Args:
            question: The original question
            question_analysis: The analysis of the question
            relevant_sources: Dictionary of relevant sources with their scores
            function_examples_store: Vector store with function examples
            
        Returns:
            List of relevant function definitions
        """
        # Create a search query based on the question and analysis
        required_info = question_analysis.get("required_information", [])
        question_type = question_analysis.get("question_type", "unknown")
        
        # Enhance the search query with specific terms based on question type
        query_enhancers = {
            "factual": "retrieve fact information",
            "comparative": "compare data",
            "analytical": "analyze data",
            "numerical": "calculate metrics",
            "timeline": "time-based analysis"
        }
        
        enhanced_query = f"{question} {query_enhancers.get(question_type, '')}"
        
        # Add required information types
        for info_type in required_info:
            enhanced_query += f" {info_type}"
            
        # Add top relevant sources to the query
        top_sources = sorted(relevant_sources.items(), key=lambda x: x[1], reverse=True)[:3]
        for source, score in top_sources:
            enhanced_query += f" {source}"
        
        # Create a filter to find functions that are applicable to the relevant sources
        source_filter = {"applicable_sources": {"$in": list(relevant_sources.keys())}}
        
        # Use the semantic search functionality
        search_results = function_examples_store.semantic_search(
            query=enhanced_query,
            filter=source_filter,
            top_k=min(7, self.max_documents // 3)  # Use a portion of max_documents for functions
        )
        
        # Convert search results to FunctionDefinition objects
        relevant_functions = []
        for result in search_results:
            try:
                function = FunctionDefinition(**result["metadata"])
                
                # Check if this function is applicable to our relevant sources
                applicable_to_relevant = False
                for source in function.applicable_sources:
                    if source in relevant_sources:
                        applicable_to_relevant = True
                        break
                        
                if applicable_to_relevant or not function.applicable_sources:
                    relevant_functions.append(function)
                    
            except Exception as e:
                logger.error(f"Error converting search result to FunctionDefinition: {e}")
                
        return relevant_functions
    
    async def _generate_plan(
        self,
        question: str,
        question_analysis: Dict[str, Any],
        relevant_sources: Dict[str, float],
        all_metadata: Dict[str, List[Any]],
        relevant_functions: List[FunctionDefinition]
    ) -> Plan:
        """
        Generate an execution plan based on the question and retrieved information.
        
        Args:
            question: The original question
            question_analysis: The analysis of the question
            relevant_sources: Dictionary of relevant sources with their scores
            all_metadata: Dictionary mapping source types to metadata lists
            relevant_functions: Relevant function definitions
            
        Returns:
            Execution plan
        """
        system_prompt = """You are an expert planner for a data retrieval and analysis system.
        Your task is to create a step-by-step plan to answer the user's question using the available 
        data sources, metadata, and functions.
        
        Consider:
        1. What data sources would be most relevant to answer the question
        2. What retrieval strategy would be most effective
        3. What functions would be most helpful
        4. How to reframe the question to get better results
        5. What steps should be taken in what order
        6. When cross-source analysis is needed (e.g., connecting Salesforce data with Gong calls)
        
        Create a plan with:
        - A reframed version of the original question
        - A retrieval strategy
        - A confidence score (0.0-1.0)
        - A list of steps to execute
        - A fallback plan if the main strategy fails
        
        Format your response as a JSON object matching this structure:
        {
            "reframed_question": "Better version of the question",
            "strategy": "One of: direct, document_retrieval, salesforce_query, gong_analysis, multi_hop, comparison, timeline, numerical, cross_source",
            "confidence": 0.85,
            "steps": [
                {
                    "step_number": 1,
                    "action": "function_name",
                    "parameters": {"param1": "value1"},
                    "reasoning": "Why this step is necessary"
                }
            ],
            "fallback_plan": {
                "reframed_question": "Alternative question",
                "strategy": "alternative_strategy",
                "steps": [...]
            }
        }
        """
        
        # Prepare the context for relevant sources
        source_context = []
        for source, score in sorted(relevant_sources.items(), key=lambda x: x[1], reverse=True):
            source_context.append(f"- {source}: relevance score {score:.2f}")
        
        # Prepare the context for metadata
        metadata_context = []
        
        # Add Salesforce metadata
        if all_metadata["Salesforce"]:
            metadata_context.append("Salesforce Objects:")
            for i, meta in enumerate(all_metadata["Salesforce"][:3]):  # Limit to top 3 for context
                metadata_context.append(f"  Object {i+1}:")
                metadata_context.append(f"    ID: {meta.source_id}")
                metadata_context.append(f"    Type: {meta.object_type.value}")
                if meta.name:
                    metadata_context.append(f"    Name: {meta.name}")
                if meta.created_date:
                    metadata_context.append(f"    Created: {meta.created_date}")
                if meta.related_ids:
                    metadata_context.append(f"    Related IDs: {meta.related_ids}")
                metadata_context.append("")
        
        # Add Gong metadata
        if all_metadata["Gong"]:
            metadata_context.append("Gong Data:")
            for i, meta in enumerate(all_metadata["Gong"][:3]):  # Limit to top 3 for context
                metadata_context.append(f"  Item {i+1}:")
                metadata_context.append(f"    ID: {meta.source_id}")
                metadata_context.append(f"    Type: {meta.data_type.value}")
                if meta.title:
                    metadata_context.append(f"    Title: {meta.title}")
                if meta.date:
                    metadata_context.append(f"    Date: {meta.date}")
                if meta.participants:
                    metadata_context.append(f"    Participants: {', '.join(meta.participants)}")
                metadata_context.append("")
        
        # Add Document metadata
        if all_metadata["Document"]:
            metadata_context.append("Documents:")
            for i, meta in enumerate(all_metadata["Document"][:3]):  # Limit to top 3 for context
                metadata_context.append(f"  Document {i+1}:")
                metadata_context.append(f"    ID: {meta.source_id}")
                metadata_context.append(f"    Type: {meta.source_type}")
                if meta.title:
                    metadata_context.append(f"    Title: {meta.title}")
                if meta.date:
                    metadata_context.append(f"    Date: {meta.date}")
                if meta.summary:
                    metadata_context.append(f"    Summary: {meta.summary}")
                metadata_context.append("")
        
        # Prepare the context for functions
        function_context = []
        for i, func in enumerate(relevant_functions[:5]):  # Limit to top 5 for context
            function_context.append(f"Function {i+1}:")
            function_context.append(f"  Name: {func.name}")
            function_context.append(f"  Description: {func.description}")
            function_context.append(f"  Parameters: {func.parameters}")
            if func.applicable_sources:
                function_context.append(f"  Applicable to: {', '.join(func.applicable_sources)}")
            if func.example_usage:
                function_context.append(f"  Example: {func.example_usage}")
            function_context.append("")
        
        # Prepare schemas for the relevant sources
        schema_context = []
        
        # Get Salesforce schema if relevant
        if any(source.startswith("Salesforce.") for source in relevant_sources):
            salesforce_schema = self.data_source_config.get_salesforce_schema()
            schema_context.append("Salesforce Schemas:")
            for obj_name, fields in salesforce_schema.items():
                schema_context.append(f"  {obj_name}:")
                for field_name, field_type in list(fields.items())[:5]:  # Limit fields for brevity
                    schema_context.append(f"    {field_name}: {field_type}")
                schema_context.append("    ...")  # Indicate more fields exist
                schema_context.append("")
        
        # Get Gong schema if relevant
        if any(source.startswith("Gong.") for source in relevant_sources):
            gong_schema = self.data_source_config.get_gong_schema()
            schema_context.append("Gong Schemas:")
            for data_name, fields in gong_schema.items():
                schema_context.append(f"  {data_name}:")
                for field_name, field_type in list(fields.items())[:5]:  # Limit fields for brevity
                    schema_context.append(f"    {field_name}: {field_type}")
                schema_context.append("    ...")  # Indicate more fields exist
                schema_context.append("")
        
        # Get Document schema if relevant
        if any(source.startswith("Document.") for source in relevant_sources):
            document_schema = self.data_source_config.get_document_schema()
            schema_context.append("Document Schemas:")
            for doc_name, fields in document_schema.items():
                schema_context.append(f"  {doc_name}:")
                for field_name, field_type in list(fields.items())[:5]:  # Limit fields for brevity
                    schema_context.append(f"    {field_name}: {field_type}")
                schema_context.append("    ...")  # Indicate more fields exist
                schema_context.append("")
        
        # Combine all context
        context = (
            f"Question: {question}\n\n"
            f"Question Analysis: {question_analysis}\n\n"
            f"Relevant Sources:\n{chr(10).join(source_context)}\n\n"
            f"Available Metadata:\n{chr(10).join(metadata_context)}\n\n"
            f"Available Functions:\n{chr(10).join(function_context)}\n\n"
            f"Source Schemas:\n{chr(10).join(schema_context)}"
        )
        
        try:
            plan_response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Please create a plan for answering this question:\n\n{context}")
                ]
            )
            
            # Parse the JSON response
            import json
            import re
            
            # Extract JSON from the response
            json_match = re.search(r'{.*}', str(plan_response.content), re.DOTALL)
            if json_match:
                plan_dict = json.loads(json_match.group(0))
                
                # Convert to Plan object
                # First handle the fallback plan if it exists
                fallback = None
                if "fallback_plan" in plan_dict and plan_dict["fallback_plan"]:
                    fallback_dict = plan_dict.pop("fallback_plan")
                    fallback_steps = []
                    
                    for step in fallback_dict.get("steps", []):
                        fallback_steps.append(PlanStep(**step))
                    
                    fallback = Plan(
                        original_question=question,
                        reframed_question=fallback_dict.get("reframed_question", question),
                        strategy=fallback_dict.get("strategy", PlanningStrategy.DIRECT),
                        confidence=fallback_dict.get("confidence", 0.5),
                        steps=fallback_steps,
                        fallback_plan=None
                    )
                
                # Handle the main plan
                steps = []
                for step in plan_dict.get("steps", []):
                    steps.append(PlanStep(**step))
                
                plan = Plan(
                    original_question=question,
                    reframed_question=plan_dict.get("reframed_question", question),
                    strategy=plan_dict.get("strategy", PlanningStrategy.DIRECT),
                    confidence=plan_dict.get("confidence", 0.7),
                    steps=steps,
                    fallback_plan=fallback
                )
                
                return plan
            else:
                logger.error("Failed to extract JSON from plan response")
                # Return a basic default plan
                return Plan(
                    original_question=question,
                    reframed_question=question,
                    strategy=PlanningStrategy.DIRECT,
                    confidence=0.3,
                    steps=[
                        PlanStep(
                            step_number=1,
                            action="retrieve_documents",
                            parameters={"query": question},
                            reasoning="Default fallback plan"
                        )
                    ]
                )
                
        except Exception as e:
            logger.error(f"Error generating plan: {e}")
            # Return a basic default plan
            return Plan(
                original_question=question,
                reframed_question=question,
                strategy=PlanningStrategy.DIRECT,
                confidence=0.3,
                steps=[
                    PlanStep(
                        step_number=1,
                        action="retrieve_documents",
                        parameters={"query": question},
                        reasoning="Default fallback plan due to error"
                    )
                ]
            )
    
    async def _validate_and_correct_plan(
        self, 
        plan: Plan, 
        relevant_sources: Dict[str, float]
    ) -> Plan:
        """
        Validate the generated plan and correct it if necessary.
        
        Args:
            plan: The generated execution plan
            relevant_sources: Dictionary of relevant sources with their scores
            
        Returns:
            Potentially corrected plan
        """
        system_prompt = """You are an expert validator for retrieval plans.
        Your task is to analyze a proposed plan and identify any potential issues or improvements.
        
        Check for:
        1. Are the steps logical and in the correct order?
        2. Are there any missing steps?
        3. Are the function parameters correct and complete?
        4. Is the reframed question better than the original?
        5. Is the confidence score appropriate?
        6. Are the most relevant data sources being utilized effectively?
        7. Is cross-source analysis needed where different data sources need to be connected?
        
        If the plan is good, return it unchanged.
        If you find issues, correct them and return the improved plan.
        
        Format your response as a JSON object matching the input structure.
        """
        
        try:
            # Convert plan to dict for the LLM
            plan_dict = {
                "original_question": plan.original_question,
                "reframed_question": plan.reframed_question,
                "strategy": plan.strategy,
                "confidence": plan.confidence,
                "steps": [step.dict() for step in plan.steps],
            }
            
            if plan.fallback_plan:
                plan_dict["fallback_plan"] = {
                    "reframed_question": plan.fallback_plan.reframed_question,
                    "strategy": plan.fallback_plan.strategy,
                    "confidence": plan.fallback_plan.confidence,
                    "steps": [step.dict() for step in plan.fallback_plan.steps],
                }
            
            # Include the relevant sources information
            context = {
                "plan": plan_dict,
                "relevant_sources": relevant_sources
            }
            
            validation_response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Please validate this plan with the following context:\n\n{context}")
                ]
            )
            
            # Extract JSON from the response
            json_match = re.search(r'{.*}', str(validation_response.content), re.DOTALL)
            if json_match:
                corrected_dict = json.loads(json_match.group(0))
                
                # Convert to Plan object
                # First handle the fallback plan if it exists
                fallback = None
                if "fallback_plan" in corrected_dict and corrected_dict["fallback_plan"]:
                    fallback_dict = corrected_dict.pop("fallback_plan")
                    fallback_steps = []
                    
                    for step in fallback_dict.get("steps", []):
                        fallback_steps.append(PlanStep(**step))
                    
                    fallback = Plan(
                        original_question=plan.original_question,
                        reframed_question=fallback_dict.get("reframed_question", plan.original_question),
                        strategy=fallback_dict.get("strategy", PlanningStrategy.DIRECT),
                        confidence=fallback_dict.get("confidence", 0.5),
                        steps=fallback_steps,
                        fallback_plan=None
                    )
                
                # Handle the main plan
                steps = []
                for step in corrected_dict.get("steps", []):
                    steps.append(PlanStep(**step))
                
                corrected_plan = Plan(
                    original_question=plan.original_question,
                    reframed_question=corrected_dict.get("reframed_question", plan.reframed_question),
                    strategy=corrected_dict.get("strategy", plan.strategy),
                    confidence=corrected_dict.get("confidence", plan.confidence),
                    steps=steps,
                    fallback_plan=fallback
                )
                
                return corrected_plan
            else:
                logger.error("Failed to extract JSON from validation response")
                return plan  # Return the original plan if validation fails
                
        except Exception as e:
            logger.error(f"Error validating plan: {e}")
            return plan  # Return the original plan if validation fails


class PlanExecutor:
    """
    Executes a plan generated by the SelfCorrectingPlanner.
    """
    
    def __init__(
        self, 
        data_source_config: Optional[DataSourceConfig] = None,
        llm: Optional[ChatOpenAI] = None,
        max_documents: int = 25
    ):
        """
        Initialize the executor.
        
        Args:
            data_source_config: Configuration of available data sources
            llm: Language model for answer generation
            max_documents: Maximum number of documents to retrieve per source
        """
        self.llm = llm or ChatOpenAI(model="gpt-4o", temperature=0)
        self.data_source_config = data_source_config or DataSourceConfig.default_config()
        self.max_documents = max_documents
        
    async def execute_plan(
        self,
        plan: Plan,
        data_stores: Dict[str, Any],  # Dictionary of various data stores
        function_registry: Dict[str, Callable]
    ) -> Dict[str, Any]:
        """
        Execute a plan and return the results.
        
        Args:
            plan: The plan to execute
            data_stores: Dictionary of various data stores (document, metadata, etc.)
            function_registry: Dictionary mapping function names to their implementations
            
        Returns:
            Results of the plan execution
        """
        # Initialize results
        results = {
            "original_question": plan.original_question,
            "reframed_question": plan.reframed_question,
            "strategy": plan.strategy,
            "execution_results": [],
            "data_sources_used": set(),  # Track which data sources were used
            "final_answer": None,
            "used_fallback": False
        }
        
        # Execute each step in the plan
        success = True
        for step in plan.steps:
            step_result = await self._execute_step(step, data_stores, function_registry, results)
            
            # Add execution result
            results["execution_results"].append({
                "step_number": step.step_number,
                "action": step.action,
                "success": step_result["success"],
                "result": step_result["result"]
            })
            
            # Update data sources used
            if "data_sources" in step_result:
                results["data_sources_used"].update(step_result["data_sources"])
            
            if not step_result["success"]:
                success = False
                break
        
        # If main plan failed and fallback exists, execute fallback
        if not success and plan.fallback_plan:
            results["used_fallback"] = True
            fallback_results = await self.execute_plan(plan.fallback_plan, data_stores, function_registry)
            results["fallback_results"] = fallback_results
            results["final_answer"] = fallback_results["final_answer"]
            # Merge data sources used from fallback
            results["data_sources_used"].update(fallback_results["data_sources_used"])
        else:
            # Generate final answer based on execution results
            results["final_answer"] = await self._generate_final_answer(plan, results)
        
        # Convert data_sources_used from set to list for JSON serialization
        results["data_sources_used"] = list(results["data_sources_used"])
        
        return results
    
    async def _execute_step(
        self, 
        step: PlanStep,
        data_stores: Dict[str, Any],
        function_registry: Dict[str, Callable],
        previous_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single step in the plan.
        
        Args:
            step: The step to execute
            data_stores: Dictionary of various data stores
            function_registry: Dictionary mapping function names to their implementations
            previous_results: Results from previous steps
            
        Returns:
            Result of the step execution
        """
        try:
            # Check if the function exists in the registry
            if step.action not in function_registry:
                return {
                    "success": False,
                    "result": f"Function '{step.action}' not found in registry",
                    "data_sources": []
                }
                
            # Get the function
            function = function_registry[step.action]
            
            # Track which data sources this step uses
            data_sources_used = []
            
            # Determine which data sources this function might access based on naming conventions
            if "salesforce" in step.action.lower():
                data_sources_used.extend([
                    source for source in self.data_source_config.get_all_sources() 
                    if source.startswith("Salesforce.")
                ])
            elif "gong" in step.action.lower():
                data_sources_used.extend([
                    source for source in self.data_source_config.get_all_sources() 
                    if source.startswith("Gong.")
                ])
            elif "document" in step.action.lower() or "pdf" in step.action.lower():
                data_sources_used.extend([
                    source for source in self.data_source_config.get_all_sources() 
                    if source.startswith("Document.")
                ])
            
            # If specific sources are mentioned in parameters, add those
            for param_name, param_value in step.parameters.items():
                if param_name in ["source_type", "object_type", "data_type", "document_type"]:
                    if isinstance(param_value, str):
                        # Check if this is a fully qualified source name (with prefix)
                        if "." in param_value:
                            data_sources_used.append(param_value)
                        else:
                            # Try to determine the prefix based on parameter name
                            if "document" in param_name:
                                data_sources_used.append(f"Document.{param_value}")
                            elif "salesforce" in param_name or "object" in param_name:
                                data_sources_used.append(f"Salesforce.{param_value}")
                            elif "gong" in param_name:
                                data_sources_used.append(f"Gong.{param_value}")
                    elif isinstance(param_value, list):
                        for value in param_value:
                            if isinstance(value, str):
                                if "." in value:
                                    data_sources_used.append(value)
                                else:
                                    # Use same prefix logic as above
                                    if "document" in param_name:
                                        data_sources_used.append(f"Document.{value}")
                                    elif "salesforce" in param_name or "object" in param_name:
                                        data_sources_used.append(f"Salesforce.{value}")
                                    elif "gong" in param_name:
                                        data_sources_used.append(f"Gong.{value}")
            
            # Add the data_stores to the parameters
            # This allows functions to access any needed data store
            step_params = {**step.parameters, "data_stores": data_stores}
            
            # Add context from previous steps' results
            if "context" not in step_params:
                step_params["context"] = {}
                
            # Add previous step results to context if they exist
            if previous_results and "execution_results" in previous_results:
                step_params["context"]["previous_steps"] = previous_results["execution_results"]
            
            # Execute the function with parameters
            result = await function(**step_params)
            
            return {
                "success": True,
                "result": result,
                "data_sources": data_sources_used
            }
            
        except Exception as e:
            logger.error(f"Error executing step {step.step_number}: {e}")
            return {
                "success": False,
                "result": f"Error: {str(e)}",
                "data_sources": []
            }
    
    async def _generate_final_answer(
        self,
        plan: Plan,
        execution_results: Dict[str, Any]
    ) -> str:
        """
        Generate a final answer based on the execution results.
        
        Args:
            plan: The executed plan
            execution_results: Results from executing the plan
            
        Returns:
            Final answer to the user's question
        """
        system_prompt = """You are an expert at synthesizing information to answer questions.
        Your task is to create a clear, concise answer to the user's original question
        based on the execution results of a retrieval plan.
        
        Your answer should:
        1. Directly address the original question
        2. Synthesize information from all relevant retrieval steps
        3. Cite specific data sources when referencing information
        4. Acknowledge connections between different data sources when relevant
        5. Be well-structured and easy to understand
        6. Acknowledge any limitations or uncertainties
        
        For each data source type, use the appropriate citation format:
        - Salesforce: "According to Salesforce [Object Type: ID]"
        - Gong: "Based on Gong call data [Call ID]"
        - Documents: "As stated in [Document Title, ID]"
        """
        
        try:
            # Prepare a context summary of the execution results
            step_results_summary = []
            for result in execution_results["execution_results"]:
                step_results_summary.append(f"Step {result['step_number']} ({result['action']}):")
                if result["success"]:
                    # Truncate very long results
                    result_str = str(result["result"])
                    if len(result_str) > 500:
                        result_str = result_str[:500] + "... [truncated]"
                    step_results_summary.append(f"  Success: {result_str}")
                else:
                    step_results_summary.append(f"  Failed: {result['result']}")
                step_results_summary.append("")
            
            # List the data sources used
            data_sources_used = execution_results.get("data_sources_used", [])
            data_sources_context = []
            if data_sources_used:
                data_sources_context.append("Data sources used:")
                for source in data_sources_used:
                    data_sources_context.append(f"- {source}")
                data_sources_context.append("")
            
            # Combine context
            context = (
                f"Original question: {plan.original_question}\n\n"
                f"Reframed question: {plan.reframed_question}\n\n"
                f"Strategy used: {plan.strategy}\n\n"
                f"{''.join(data_sources_context)}"
                f"Execution results:\n{''.join(step_results_summary)}\n\n"
            )
            
            answer_response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Please provide a comprehensive answer based on these execution results:\n\n{context}")
                ]
            )
            
            return str(answer_response.content)
            
        except Exception as e:
            logger.error(f"Error generating final answer: {e}")
            return "I encountered an error while generating the answer to your question. Please try asking again."


# Create a mock function registry for testing purposes
def build_mock_function_registry() -> Dict[str, Callable]:
    """Build a registry of mock functions for testing."""
    
    async def search_metadata(**kwargs):
        """Mock implementation of search_metadata."""
        return {"results": ["Mock metadata search result"]}
    
    async def retrieve_document(**kwargs):
        """Mock implementation of retrieve_document."""
        return {"content": "Mock document content"}
    
    async def query_salesforce(**kwargs):
        """Mock implementation of query_salesforce."""
        return {"results": ["Mock Salesforce query result"]}
    
    async def analyze_document(**kwargs):
        """Mock implementation of analyze_document."""
        return {"analysis": "Mock document analysis"}
    
    return {
        "search_metadata": search_metadata,
        "retrieve_document": retrieve_document,
        "query_salesforce": query_salesforce,
        "analyze_document": analyze_document
    }


# Mock VectorStore for testing purposes
class MockVectorStore:
    """A mock vector store for testing."""
    
    def semantic_search(self, query, filter=None, top_k=10):
        """
        Mock implementation of semantic search.
        
        Args:
            query: The search query
            filter: Optional filter
            top_k: Number of results to return
            
        Returns:
            Dictionary with mock search results
        """
        print(f"Mock search for: {query}")
        print(f"Filter: {filter}")
        print(f"Top K: {top_k}")
        
        # Return mock results
        return {
            "results": [
                {
                    "id": "doc1",
                    "score": 0.95,
                    "metadata": {
                        "source_id": "doc1",
                        "source_type": "Document.GoogleDrivePDF",
                        "title": "Mock Document 1",
                        "date": "2023-01-01",
                        "summary": "This is a mock document for testing"
                    }
                },
                {
                    "id": "opp1",
                    "score": 0.85,
                    "metadata": {
                        "source_id": "opp1",
                        "source_type": "Salesforce.Opportunity",
                        "object_type": "Opportunity",
                        "name": "Mock Opportunity 1",
                        "created_date": "2023-02-15"
                    }
                },
                {
                    "id": "call1",
                    "score": 0.75,
                    "metadata": {
                        "source_id": "call1",
                        "source_type": "Gong.Call",
                        "data_type": "Call",
                        "title": "Mock Call 1",
                        "date": "2023-03-10",
                        "participants": ["John Doe", "Jane Smith"]
                    }
                }
            ]
        }


# Example usage
async def test_planner():
    """Test the SelfCorrectingPlanner with mock data."""
    # Create data source configuration
    data_source_config = DataSourceConfig(
        salesforce_objects=[
            SalesforceObjectType.OPPORTUNITY,
            SalesforceObjectType.ACCOUNT
        ],
        gong_data=[GongDataType.CALL],
        document_types=[DocumentType.GOOGLE_DRIVE_PDF]
    )
    
    # Create the planner
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    planner = SelfCorrectingPlanner(data_source_config=data_source_config, llm=llm)
    
    # Create mock stores
    metadata_store = MockVectorStore()
    function_examples_store = MockVectorStore()
    
    # Generate a plan
    question = "Show me all Gong calls with Company XYZ where they mentioned our new product, and check if they have any open opportunities in Salesforce."
    plan = await planner.plan(
        question=question,
        metadata_store=metadata_store,
        function_examples_store=function_examples_store
    )
    
    # Print the plan
    print(f"Generated plan with strategy: {plan.strategy}")
    print(f"Reframed question: {plan.reframed_question}")
    print(f"Confidence: {plan.confidence}")
    print("Steps:")
    for step in plan.steps:
        print(f"  Step {step.step_number}: {step.action}")
        print(f"    Parameters: {step.parameters}")
        print(f"    Reasoning: {step.reasoning}")
    
    # Create the executor
    executor = PlanExecutor(data_source_config=data_source_config, llm=llm)
    
    # Create a data stores dictionary
    data_stores = {
        "metadata_store": metadata_store,
        "document_store": {"search": metadata_store},
        "salesforce_connector": {"query": lambda q: {"results": []}},
        "gong_connector": {"search": lambda q: {"results": []}}
    }
    
    # Execute the plan
    results = await executor.execute_plan(
        plan=plan,
        data_stores=data_stores,
        function_registry=build_mock_function_registry()
    )
    
    # Print the results
    print("\nExecution results:")
    print(f"Final answer: {results['final_answer']}")
    print(f"Data sources used: {results['data_sources_used']}")


if __name__ == "__main__":
    # Run the test
    import asyncio
    asyncio.run(test_planner())