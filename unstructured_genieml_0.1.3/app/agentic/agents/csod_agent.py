import logging
import json
from typing import Any, Dict, List, Optional, cast
import asyncio
from datetime import datetime
import re

from pydantic import Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from chromadb import Where

from app.agentic.base.base_agent import BaseAgent, AgentState
from app.config.agent_config import chroma_collections
from app.agentic.utils.document_processor import process_retrieved_documents
from app.agentic.utils.prompt_builder import build_human_prompt

# Set up logging
logger = logging.getLogger("CSODAgent")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.info("=== CSODAgent Logger Initialized ===")

# Silence noisy HTTPX logs from chromadb client
logging.getLogger("httpx").setLevel(logging.WARNING)

# Detailed file mappings for CSOD data
FILE_MAPPINGS = {
    "LearningActivities_data.json": {
        "description": "Learning object information",
        "fields": [
            "lo_object_id", 
            "lo_type", 
            "lo_hours", 
            "lo_mastery_score", 
            "lo_active", 
            "lo_create_dt"
        ]
    },
    "transcript_data.json": {
        "description": "User transcript records",
        "fields": [
            "reg_num",
            "user_lo_status_id",
            "user_lo_create_dt",
            "user_lo_min_due_date",
            "user_lo_assigned_comments",
            "user_lo_assigned_dt"
        ]
    },
    "LearningActivities__ilt_session_instructor_data.json": {
        "description": "Instructor information",
        "fields": [
            "ins_schedule_id",
            "ins_instructor_id",
            "ins_instructor_ref",
            "ins_instructor_fullname",
            "ins_instructor_role_id",
            "ins_instructor_approval_required"
        ]
    },
    "vw_rpt_training_ilt_facility_data.json": {
        "description": "Training facility information",
        "fields": [
            "facility_id",
            "facility_title",
            "facility_ref",
            "facility_country",
            "facility_timezone_code",
            "facility_occupancy",
            "facility_active"
        ]
    },
    "LearningActivities__session_schedule_data.json": {
        "description": "Session schedule information",
        "fields": [
            "schedule_id",
            "session_id",
            "title",
            "descr",
            "start_dt_utc",
            "end_dt_utc",
            "part_duration",
            "total_break_duration"
        ]
    },
    "user_data.json": {
        "description": "User profile information",
        "fields": [
            "user_id",
            "user_name_first",
            "user_name_last",
            "user_ref",
            "user_login",
            "user_status_id",
            "user_country"
        ]
    },
    "LearningActivities_curricula_data.json": {
        "description": "Curriculum structure information",
        "fields": [
            "curriculum_child_object_id",
            "curriculum_section_object_id",
            "curriculum_object_id",
            "curriculum_version"
        ]
    },
    "subject_training_data.json": {
        "description": "Subject and training relationships",
        "fields": [
            "subject_id",
            "object_id",
            "_last_touched_dt_utc"
        ]
    },
    "transcript_status_data.json": {
        "description": "Status codes and descriptions",
        "fields": [
            "status_id",
            "status"
        ]
    },
    "user_ou_info_data.json": {
        "description": "User organizational unit information",
        "fields": [
            "user_ou_info_user_id",
            "user_ou_id2",
            "user_ou_id4",
            "user_ou_id8",
            "user_div_id",
            "user_div"
        ]
    },
    "LearningActivities__schedule_data.json": {
        "description": "Learning activity schedule information",
        "fields": [
            "schedule_id",
            "rts_object_id",
            "lo_schedule_start_dt",
            "lo_schedule_end_dt",
            "lo_provider_id",
            "lo_session_admin",
            "lo_part_location",
            "timezone_code",
            "lo_part_duration",
            "lo_part_training_hours"
        ]
    }
}

class CSODAgentState(AgentState):
    """Extended state for CSOD-specific processing."""
    csod_entities: List[str] = Field(default_factory=list)
    source_type: str = "csod"  # Always set to csod for this agent
    needs_refinement: bool = False  # Track if query needs refinement
    recursion_count: int = 0  # Track refinement iterations
    original_question: str = ""  # Store original question
    current_query: str = ""  # Current refined query

class CSODAgent(BaseAgent):
    """
    Agent specialized for retrieving and processing CSOD data.
    Focuses on CSOD-related datasets.
    """

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """Initialize the CSOD agent."""
        super().__init__(llm=llm, source_type="csod")
        
        # CSOD-specific configurations
        self.default_topics = [
            "user", "transcript", "learning", "activity", 
            "organizational", "unit", "training"
        ]
        self.default_keywords = [
            "learning_object", "user_data", "training", "completion", 
            "assignment", "course", "certification"
        ]
        
        # Add mapping of audience-related keywords for inference
        self.audience_keywords = {
            "new managers": ["new manager", "first-time manager", "junior manager", "leadership basics", "new supervisor", "management onboarding"],
            "managers": ["manager", "supervisor", "leadership", "team lead", "management", "executive"],
            "new hires": ["onboarding", "new employee", "orientation", "new hire", "starter"],
            "technical staff": ["technical", "engineer", "developer", "IT", "programming"],
            "sales": ["sales", "selling", "customer acquisition", "deal", "pipeline"],
            "customer service": ["customer service", "support", "client interaction"]
        }
    
    async def retrieve_documents(self, state: AgentState) -> List[Dict[str, Any]]:
        """
        Retrieve CSOD documents based on the query.
        
        Args:
            state: The current agent state
            
        Returns:
            List of retrieved CSOD documents
        """
        try:
            logger.info(f"[CSODAgent.retrieve_documents] Starting document retrieval for query: '{state.question}'")
            
            # Import required utilities here to avoid circular imports
            from app.utils.chromadb import ChromaDB
            # Initialize with WARNING log level to reduce noise
            chroma_db = ChromaDB(log_level="WARNING")
            
            # Check for specific additional context
            additional_context = {}
            if hasattr(state, 'additional_context') and state.additional_context:
                additional_context = state.additional_context
            
            # Get topics passed from the state
            topics = state.topics if state.topics else self.default_topics
            
            # Log what topics we're using
            logger.info(f"[CSODAgent.retrieve_documents] Using {len(topics)} topics: {topics}")
            
            # Prepare CSOD-specific query terms
            csod_terms = ["learning", "transcript", "user", "training", "course"]
            
            # Add audience-related terms if the query is about target audiences
            audience_related = any(term in state.question.lower() for term in ["target", "audience", "for whom", "designed for", "intended for"])
            if audience_related:
                logger.info(f"[CSODAgent.retrieve_documents] Detected audience-related query")
                
                # Extract potential audience targets from the question
                question_lower = state.question.lower()
                audience_terms = []
                
                for audience, keywords in self.audience_keywords.items():
                    if any(keyword in question_lower for keyword in keywords):
                        # Only add the main audience category and at most 2 specific keywords
                        audience_terms.append(audience)
                        matched_keywords = [kw for kw in keywords if kw in question_lower]
                        if matched_keywords:
                            audience_terms.extend(matched_keywords[:2])  # Limit to 2 most relevant keywords
                
                if audience_terms:
                    # Remove duplicates while preserving order
                    audience_terms = list(dict.fromkeys(audience_terms))
                    logger.info(f"[CSODAgent.retrieve_documents] Added focused audience terms: {audience_terms}")
                    csod_terms.extend(audience_terms)
            
            # Combine the user's question with carefully selected terms and topics
            # Remove redundancy in topics and csod_terms
            unique_topics = [t for t in topics if t.lower() not in [ct.lower() for ct in csod_terms]]
            
            # Build query parts in order of importance
            all_query_parts = [state.question]  # Original question is most important
            
            # Add up to 5 most relevant CSOD terms
            if len(csod_terms) > 5:
                csod_terms = csod_terms[:5]
            all_query_parts.extend(csod_terms)
            
            # Add up to 5 most relevant topics if not already covered
            if len(unique_topics) > 5:
                unique_topics = unique_topics[:5]
            all_query_parts.extend(unique_topics)
            
            # Join unique terms with weights emphasizing question
            enhanced_query = state.question + " " + " ".join(list(dict.fromkeys(csod_terms + unique_topics)))
            
            logger.info(f"[CSODAgent.retrieve_documents] Built enhanced query: '{enhanced_query}'")

            # Handle specific document IDs if provided
            if state.document_ids:
                logger.info(f"[CSODAgent.retrieve_documents] Using specific document IDs: {state.document_ids}")
                return await self._retrieve_by_document_ids(state.document_ids)
            
            # Query the csod_datasets1 collection (new standardized metadata structure)
            logger.info(f"[CSODAgent.retrieve_documents] Querying csod_datasets1 collection")
            
            # Set up filter for CSOD data
            # Note: We're not using a specific filter as we want to query across all CSOD documents
            
            # Set up a search limit - use config value directly without hardcoded override
            search_limit = self.config.single_collection_search_limit
            logger.info(f"[CSODAgent.retrieve_documents] Using search limit of {search_limit} from config")
            
            # Perform the query
            documents = chroma_db.query_collection_with_relevance_scores(
                collection_name="csod_datasets1",
                query_texts=[enhanced_query],
                n_results=search_limit
            )
            
            logger.info(f"[CSODAgent.retrieve_documents] Retrieved {len(documents)} documents from csod_datasets1")
            
            # Process the documents
            return self._process_retrieved_documents(documents)
            
        except Exception as e:
            logger.error(f"[CSODAgent.retrieve_documents] Error retrieving documents: {e}")
            import traceback
            logger.error(f"[CSODAgent.retrieve_documents] Traceback: {traceback.format_exc()}")
            return []
    
    async def _retrieve_by_document_ids(self, document_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieve documents by their IDs.
        
        Args:
            document_ids: List of document IDs
            
        Returns:
            List of retrieved documents
        """
        try:
            logger.info(f"[CSODAgent._retrieve_by_document_ids] Retrieving {len(document_ids)} documents by ID")
            
            from app.utils.chromadb import ChromaDB
            chroma_db = ChromaDB(log_level="WARNING")
            
            documents = []
            for doc_id in document_ids:
                try:
                    results = chroma_db.query_collection_with_relevance_scores(
                        collection_name="csod_datasets1",
                        query_texts=[""],
                        n_results=1,
                        where={"document_id": {"$eq": doc_id}}
                    )
                    
                    if results:
                        documents.extend(results)
                        logger.info(f"[CSODAgent._retrieve_by_document_ids] Retrieved document: {doc_id}")
                    else:
                        logger.warning(f"[CSODAgent._retrieve_by_document_ids] Document not found: {doc_id}")
                except Exception as e:
                    logger.error(f"[CSODAgent._retrieve_by_document_ids] Error retrieving document {doc_id}: {e}")
            
            logger.info(f"[CSODAgent._retrieve_by_document_ids] Retrieved {len(documents)} documents by ID")
            
            return self._process_retrieved_documents(documents)
        except Exception as e:
            logger.error(f"[CSODAgent._retrieve_by_document_ids] Error retrieving documents by ID: {e}")
            return []
    
    def _process_retrieved_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process retrieved documents to standardize format and extract metadata.
        Enhanced to infer entity types based on file mappings and apply advanced scoring.
        
        Args:
            documents: The raw retrieved documents
            
        Returns:
            Processed documents
        """
        processed_docs = []
        
        # Step 1: Basic processing and entity inference
        for doc in documents:
            # Extract metadata
            metadata = doc.get('metadata', {})
            
            # Extract content
            content = doc.get('content', doc.get('document', ''))
            
            # Create processed document
            processed_doc = {
                'document_id': doc.get('document_id', metadata.get('document_id', doc.get('id', 'unknown'))),
                'document_type': metadata.get('document_type', 'csod_document'),
                'content': content,
                'collection': "csod_datasets1",
                'metadata': metadata,
                'relevance_score': doc.get('relevance_score', 0.0),
                'source_type': "csod"
            }
            
            # Add source file information
            source_file = metadata.get('source_file', '')
            if source_file:
                processed_doc['source_file'] = source_file
                
                # Add file mapping information if available
                if source_file in FILE_MAPPINGS:
                    processed_doc['file_info'] = FILE_MAPPINGS[source_file]
                    
                    # Use standardized entities from metadata structure
                    # Get data from standardized metadata
                    extracted_entities = {}
                    
                    # Add entities if available
                    if metadata.get('entities'):
                        entities_data = metadata.get('entities', [])
                        
                        # Handle string format (JSON string)
                        if isinstance(entities_data, str):
                            try:
                                # Try to parse as JSON if it's a string
                                import json
                                parsed_entities = json.loads(entities_data)
                                if isinstance(parsed_entities, list):
                                    # If it's a list of strings (names/values)
                                    extracted_entities['names'] = parsed_entities
                                else:
                                    # If it's some other structure, store as is
                                    extracted_entities['parsed_entities'] = parsed_entities
                            except json.JSONDecodeError:
                                # If not valid JSON, store as raw string
                                extracted_entities['raw_entity_string'] = entities_data
                        # Handle list format
                        elif isinstance(entities_data, list):
                            for entity in entities_data:
                                if isinstance(entity, dict):
                                    # Standard entity dict with type/value
                                    entity_type = entity.get('type', '')
                                    entity_value = entity.get('value', '')
                                    if entity_type and entity_value:
                                        if entity_type not in extracted_entities:
                                            extracted_entities[entity_type] = []
                                        if entity_value not in extracted_entities[entity_type]:
                                            extracted_entities[entity_type].append(entity_value)
                                elif isinstance(entity, str):
                                    # Simple string entities go into 'names' category
                                    if 'names' not in extracted_entities:
                                        extracted_entities['names'] = []
                                    if entity not in extracted_entities['names']:
                                        extracted_entities['names'].append(entity)
                    
                    # Add topics if available
                    if metadata.get('topics'):
                        extracted_entities['topics'] = metadata.get('topics')
                    
                    # Add keywords if available
                    if metadata.get('keywords'):
                        extracted_entities['keywords'] = metadata.get('keywords')
                        
                    # Add organizational info if available
                    if metadata.get('organizational_relationships'):
                        extracted_entities['organizational_relationships'] = metadata.get('organizational_relationships')
                        
                    # Add divisions if available
                    if metadata.get('divisions'):
                        extracted_entities['divisions'] = metadata.get('divisions')
                        
                    if extracted_entities:
                        processed_doc['extracted_entities'] = extracted_entities
            
            processed_docs.append(processed_doc)
        
        # Step 2: Group documents by source file and identify relationships
        source_file_groups = {}
        for doc in processed_docs:
            source_file = doc.get('source_file', 'unknown')
            if source_file not in source_file_groups:
                source_file_groups[source_file] = []
            source_file_groups[source_file].append(doc)
        
        # Step 3: Advanced scoring and prioritization
        # Create document packages based on related data
        document_packages = []
        
        # Process learning activities first (most important for most queries)
        learning_activities = source_file_groups.get('LearningActivities_data.json', [])
        if learning_activities:
            # For each learning activity, try to find related data
            for activity in learning_activities:
                activity_id = activity.get('document_id', '')
                lo_object_id = None
                
                # Extract lo_object_id from content if possible
                if isinstance(activity.get('content', {}), dict):
                    lo_object_id = activity.get('content', {}).get('lo_object_id')
                
                # Find related documents (transcripts, curricula, etc.)
                related_docs = []
                
                # Find related curriculum data
                curricula_docs = source_file_groups.get('LearningActivities_curricula_data.json', [])
                for curr_doc in curricula_docs:
                    curr_content = curr_doc.get('content', {})
                    if isinstance(curr_content, dict):
                        if (curr_content.get('curriculum_child_object_id') == lo_object_id or 
                            curr_content.get('curriculum_object_id') == lo_object_id):
                            related_docs.append(curr_doc)
                
                # Find related schedule data
                schedule_docs = source_file_groups.get('LearningActivities__schedule_data.json', [])
                for sched_doc in schedule_docs:
                    sched_content = sched_doc.get('content', {})
                    if isinstance(sched_content, dict):
                        if sched_content.get('rts_object_id') == lo_object_id:
                            related_docs.append(sched_doc)
                
                # Find related transcript data (user completions)
                transcript_docs = source_file_groups.get('transcript_data.json', [])
                related_transcripts = []
                for trans_doc in transcript_docs:
                    # Limited to 5 related transcripts for performance
                    if len(related_transcripts) >= 5:
                        break
                    # If any reference to this learning object exists in the transcript
                    trans_content_str = str(trans_doc.get('content', {}))
                    if lo_object_id and lo_object_id in trans_content_str:
                        related_transcripts.append(trans_doc)
                
                related_docs.extend(related_transcripts[:5])
                
                # Calculate advanced relevance score
                base_score = activity.get('relevance_score', 0.0)
                
                # Enhance score based on related documents
                related_docs_score = sum(doc.get('relevance_score', 0.0) for doc in related_docs) / (len(related_docs) + 1) if related_docs else 0
                
                # Enhanced score based on inferred entities and content fields
                entity_score = 0.0
                
                # Check standardized metadata for leadership content
                has_leadership_content = False
                metadata = activity.get('metadata', {})
                
                # Check topics
                topics = metadata.get('topics', [])
                if any(topic.lower() in ['leadership', 'management', 'executive'] for topic in topics):
                    has_leadership_content = True
                    entity_score += 0.15
                
                # Check entities
                entities = metadata.get('entities', [])
                
                # Handle entities based on their type
                if isinstance(entities, list):
                    for entity in entities:
                        if isinstance(entity, dict):
                            # Check topic entities
                            if entity.get('type') == 'topic' and entity.get('value', '').lower() in ['leadership', 'management', 'executive']:
                                has_leadership_content = True
                                entity_score += 0.15
                                break
                            # Check audience entities
                            if entity.get('type') == 'audience' and entity.get('value', '').lower() in ['managers', 'executives', 'leadership']:
                                has_leadership_content = True
                                entity_score += 0.15
                                break
                elif isinstance(entities, str):
                    # If entities is a string (likely JSON), check for leadership keywords
                    entities_lower = entities.lower()
                    if any(keyword in entities_lower for keyword in ['leadership', 'management', 'executive', 'managers']):
                        has_leadership_content = True
                        entity_score += 0.15
                
                # Add bonus score for extracted audience matching "managers"
                extracted_entities = activity.get('extracted_entities', {})
                audience = extracted_entities.get('audience', [])
                if 'managers' in audience or 'new managers' in audience:
                    entity_score += 0.25
                
                # Add bonus score for leadership topics
                topics = extracted_entities.get('topics', [])
                if any(topic in ['leadership', 'management', 'team building'] for topic in topics):
                    entity_score += 0.15
                
                # Combined weighted score (similar to Gong's formula)
                composite_score = (base_score * 0.5) + (related_docs_score * 0.3) + (entity_score * 0.2)
                
                # Create package
                document_packages.append({
                    'primary_doc': activity,
                    'related_docs': related_docs,
                    'score': composite_score,
                    'has_leadership_content': has_leadership_content,
                    'source_file': 'LearningActivities_data.json'
                })
        
        # Process any remaining source file groups that might be relevant
        for source_file, docs in source_file_groups.items():
            # Skip learning activities as we've already processed them
            if source_file == 'LearningActivities_data.json':
                continue
                
            # Skip files that are usually not directly relevant to queries
            if source_file in ['user_data.json', 'transcript_status_data.json']:
                continue
                
            # For each document, create a simple package
            for doc in docs:
                base_score = doc.get('relevance_score', 0.0)
                
                # Apply source file specific bonuses
                file_bonus = 0.0
                if source_file == 'LearningActivities_curricula_data.json':
                    file_bonus = 0.1  # Curriculum data is often relevant
                
                composite_score = base_score + file_bonus
                
                # Create package with this document as primary
                document_packages.append({
                    'primary_doc': doc,
                    'related_docs': [],
                    'score': composite_score,
                    'has_leadership_content': False,
                    'source_file': source_file
                })
        
        # Step 4: Sort packages by composite score and filter to most relevant
        sorted_packages = sorted(document_packages, key=lambda p: p.get('score', 0), reverse=True)
        
        # Stricter limit to avoid context length issues
        max_packages = 200  # Limit to top 200 packages
        top_packages = sorted_packages[:max_packages]
        
        # Step 5: Rebuild the final document list from selected packages
        final_docs = []
        
        # First add all primary docs
        for package in top_packages:
            # Update the primary doc with the composite score
            primary_doc = package['primary_doc']
            primary_doc['composite_score'] = package['score']
            primary_doc['has_related_docs'] = len(package['related_docs']) > 0
            
            # Add flags to help with answer generation
            if package.get('has_leadership_content', False):
                primary_doc['has_leadership_content'] = True
            
            final_docs.append(primary_doc)
            
            # Add related docs (limited to conserve context)
            for related_doc in package['related_docs'][:3]:  # Limit to 3 related docs per package
                if related_doc not in final_docs:  # Avoid duplicates
                    final_docs.append(related_doc)
        
        # Strict final limit to prevent context length issues
        if len(final_docs) > 250:
            logger.info(f"[_process_retrieved_documents] Applying strict final limit: reducing from {len(final_docs)} to 250 documents")
            
            # Sort again by composite score for final selection
            final_docs = sorted(
                final_docs, 
                key=lambda x: x.get('composite_score', x.get('relevance_score', 0)), 
                reverse=True
            )[:250]
        
        # Log the results of our advanced processing
        logger.info(f"[_process_retrieved_documents] Processed {len(documents)} documents into {len(document_packages)} packages")
        logger.info(f"[_process_retrieved_documents] Selected {len(top_packages)} top packages resulting in {len(final_docs)} final documents")
        
        # Return the enhanced document list
        return final_docs
    
    # The _infer_entities_from_content method has been removed as we're now only using 
    # the standardized metadata structure, not inferring entities from content.
    
    def format_documents_for_context(self, documents: List[Dict[str, Any]], reduce_tokens: bool = False) -> str:
        """
        Format documents for inclusion in the prompt context.
        Enhanced with token reduction capabilities to avoid context length limits.
        
        Args:
            documents: List of documents to format
            reduce_tokens: Whether to apply aggressive token reduction techniques
            
        Returns:
            Formatted document string
        """
        if not documents:
            return "No documents found."
        
        formatted_docs = []
        
        # Standardized document limits for context formatting
        # These are smaller than processing limits to ensure content fits in prompt
        standard_token_reduction_threshold = 100  # Always apply reduction above this
        max_docs_with_reduction = 80  # Maximum docs when reducing tokens
        max_docs_without_reduction = 150  # Maximum docs when not reducing tokens
        
        # Always apply token reduction when we have more than threshold documents
        if len(documents) > standard_token_reduction_threshold:
            reduce_tokens = True
            logger.info(f"[format_documents_for_context] Automatically enabling token reduction for {len(documents)} documents")
        
        # Set max content length based on token reduction setting
        max_content_length = 80 if reduce_tokens else 300
        max_metadata_fields = 3 if reduce_tokens else 10
        
        # Cap the number of documents to include based on token reduction setting
        max_docs = max_docs_with_reduction if reduce_tokens else max_docs_without_reduction
        if len(documents) > max_docs:
            logger.info(f"[format_documents_for_context] Limiting from {len(documents)} to {max_docs} documents to prevent context length issues")
            # Sort by composite_score or relevance_score
            sorted_docs = sorted(
                documents, 
                key=lambda x: x.get('composite_score', x.get('relevance_score', 0)), 
                reverse=True
            )
            documents = sorted_docs[:max_docs]
        
        # Track unique document types to avoid redundancy
        seen_document_types = set()
        
        for i, doc in enumerate(documents):
            # Skip if over limit when reducing tokens
            max_docs_to_format = max_docs_with_reduction if reduce_tokens else max_docs
            if i >= max_docs_to_format:
                break
                
            # Get basic document information
            doc_id = doc.get('document_id', 'unknown')
            source_file = doc.get('source_file', doc.get('metadata', {}).get('source_file', 'unknown'))
            doc_type = doc.get('document_type', doc.get('metadata', {}).get('document_type', 'unknown'))
            
            # Create unique key for document type tracking
            doc_type_key = f"{source_file}:{doc_type}"
            
            # For token reduction, skip redundant document types after seeing a few
            # More aggressive skipping to reduce context length
            if reduce_tokens:
                # Count how many of this type we've seen
                type_count = sum(1 for key in seen_document_types if key.startswith(f"{source_file}:"))
                # Skip after we've seen more than 20 of the same source file type
                if type_count > 15 and doc_type_key in seen_document_types:  # Reduced from 20 to 15
                    continue
                # Even more aggressive: if we've already seen 10 of this exact type, skip it
                if doc_type_key in seen_document_types and type_count > 8:  # Reduced from 10 to 8
                    continue
                # If we're past 50 documents, be extremely selective
                if i > 40 and doc_type_key in seen_document_types:  # Reduced from 50 to 40
                    continue
                
            # Track this document type
            seen_document_types.add(doc_type_key)
            
            # Start formatting this document
            doc_string = f"Document {i+1}:\n"
            doc_string += f"ID: {doc_id}\n"
            doc_string += f"Type: {doc_type}\n"
            doc_string += f"Source: {source_file}\n"
            
            # Add relevance score if available
            relevance_score = doc.get('composite_score', doc.get('relevance_score', 0))
            if relevance_score:
                doc_string += f"Relevance: {relevance_score:.4f}\n"
            
            # Add metadata selectively (only key fields to save tokens)
            metadata = doc.get('metadata', {})
            if metadata and not reduce_tokens:
                doc_string += "Metadata:\n"
                
                # Only include important metadata fields
                important_fields = ['topics', 'recordIndex', 'document_type']
                field_count = 0
                
                for key in important_fields:
                    if key in metadata and field_count < max_metadata_fields:
                        value = metadata[key]
                        if isinstance(value, (list, dict)):
                            value = str(value)[:100]  # Truncate long lists/dicts
                        doc_string += f"  {key}: {value}\n"
                        field_count += 1
            
            # Add extracted entities if available - important for analysis
            extracted_entities = doc.get('extracted_entities', {})
            if extracted_entities:
                doc_string += "Entities:\n"
                
                # Prioritize certain entity types
                priority_entities = ['audience', 'topics', 'keywords']
                field_count = 0
                
                # First add priority entities
                for key in priority_entities:
                    if key in extracted_entities and field_count < max_metadata_fields:
                        values = extracted_entities[key]
                        if values:
                            doc_string += f"  {key}: {', '.join(str(v) for v in values)}\n"
                            field_count += 1
                
                # Then add other entities if space allows
                if field_count < max_metadata_fields:
                    for key, values in extracted_entities.items():
                        if key not in priority_entities and field_count < max_metadata_fields:
                            if values:
                                doc_string += f"  {key}: {', '.join(str(v) for v in values)}\n"
                                field_count += 1
            
            # Add content
            content = doc.get('content', {})
            if content:
                # For token reduction, be more aggressive in truncating
                if isinstance(content, dict):
                    # Only include key fields from content dictionaries
                    doc_string += "Content:\n"
                    field_count = 0
                    max_fields = 5 if reduce_tokens else 10
                    
                    # Prioritize specific important fields
                    important_fields = ['lo_type', 'lo_object_id', 'title', 'descr', 'lo_active', 'status']
                    
                    # First add important fields
                    for key in important_fields:
                        if key in content and field_count < max_fields:
                            value = content[key]
                            if value is not None:
                                # Truncate long values
                                if isinstance(value, str) and len(value) > max_content_length:
                                    value = value[:max_content_length] + "..."
                                doc_string += f"  {key}: {value}\n"
                                field_count += 1
                    
                    # Then add other fields if space allows
                    for key, value in content.items():
                        if key not in important_fields and field_count < max_fields and value is not None:
                            # Truncate long values
                            if isinstance(value, str) and len(value) > max_content_length:
                                value = value[:max_content_length] + "..."
                            doc_string += f"  {key}: {value}\n"
                            field_count += 1
                            
                            # Exit early if we've added enough fields
                            if field_count >= max_fields:
                                break
                else:
                    # For string content, just truncate
                    content_str = str(content)
                    if len(content_str) > max_content_length:
                        content_str = content_str[:max_content_length] + "..."
                    doc_string += f"Content: {content_str}\n"
            
            # Add file info if available
            file_info = doc.get('file_info', {})
            if file_info and not reduce_tokens:  # Skip file info when reducing tokens
                description = file_info.get('description', '')
                if description:
                    doc_string += f"File description: {description}\n"
            
            formatted_docs.append(doc_string)
            
            # Add a separator between documents
            formatted_docs.append("-" * 40)
        
        # If we truncated the list due to token reduction, add a note
        if reduce_tokens and len(documents) > max_docs_with_reduction:
            formatted_docs.append(f"Note: Showing {max_docs_with_reduction} out of {len(documents)} total documents to stay within token limits.")
            
        joined_content = "\n".join(formatted_docs)
        
        # Final safeguard against exceeding context length
        max_allowed_length = 70000  # Reduced from 80000 to 70000 characters (~17.5k tokens)
        if len(joined_content) > max_allowed_length:
            logger.warning(f"[format_documents_for_context] Context still too large ({len(joined_content)} chars), applying emergency truncation")
            # Reduced initial context and prioritize most relevant content at the end
            joined_content = joined_content[:8000] + "\n\n[...TRUNCATED FOR CONTEXT LENGTH...]\n\n" + joined_content[-62000:]
            
        return joined_content
    
    def build_system_prompt(self) -> str:
        """
        Build the system prompt for the CSOD agent.
        Enhanced with file mapping information to provide better context.
        
        Returns:
            System prompt text
        """
        # Generate a formatted version of the file mappings for the prompt
        file_mappings_text = ""
        
        for file_name, info in FILE_MAPPINGS.items():
            file_mappings_text += f"\n**{file_name}**: {info['description']}\n"
            file_mappings_text += "Fields: " + ", ".join(info['fields']) + "\n"
        
        return f"""
        You are an expert CSOD (Cornerstone OnDemand) Learning Management System analyst.
        
        Today's date is {datetime.now().strftime("%B %d, %Y")}.
        
        Your task is to analyze CSOD datasets and provide confident, decisive insights based on the user's query.
        
        CRITICAL INSTRUCTION: Be COMPREHENSIVE in your responses. Include EVERY relevant learning activity, course, or curriculum in the data that matches the query. Never limit your response to just one or two examples (use maximum 15).
        
        First, determine if the query is:
        1. A factual question (e.g., "What learning activities are available?", "How many users completed course XYZ?")
        2. An analytical question requiring insights (e.g., "What learning activities are targeted at new managers?", "How effective are our compliance courses?")
        
        For factual questions:
        - Answer the specific question directly and concisely at the beginning of your response
        - Include only the relevant data points that directly answer the question
        - Present facts with confidence when they are explicitly stated in the data
        - Use tables to organize numeric or categorical data
        
        For analytical questions:
        - Begin with a DEFINITIVE answer - NOT "based on the available data" or similar qualifiers
        - LIST ALL RELEVANT LEARNING ACTIVITIES - not just the top 1-2 examples
        - Provide a comprehensive catalog that includes at minimum 5-10 relevant items when available
        - When asked about specific target audiences (like managers):
          * If learning activities have management keywords/content, present them as "learning activities for managers"
          * DO NOT repeatedly mention "inference" or "no explicit targeting" - make confident assertions
          * Focus on what IS available rather than what ISN'T
        - Present your findings in organized sections with clear headings
        
        AVOID THESE PHRASES:
        - "Based on the available data..."
        - "While there is no explicit mention..."
        - "The data doesn't explicitly state..."
        - "It's challenging to determine..."
        - "The current dataset lacks..."
        
        USE THESE KINDS OF PHRASES INSTEAD:
        - "The key learning activities for new managers are..."
        - "New managers should take these courses:"
        - "The management curriculum includes..."
        - "Leadership training available for managers consists of..."
        
        CSOD Data Structure:
        The ChromaDB collection "csod_datasets1" has documents from multiple source files. Each source file contains different types of data:
        {file_mappings_text}

        Each document contains:

        1. `document_id`: A UUID string serving as the unique identifier for each document

        2. Original data fields (varies by file type as described above)

        3. `metadata` object with standardized structure containing:
           - `document_id`: The unique identifier for the document
           - `document_type`: The type of CSOD document (e.g., "csod_user_ou_info_data")
           - `source_type`: Always "csod" for these documents
           - `source_file`: String with the original filename
           - `recordIndex`: Integer indicating the record's position in the original file
           - `event_type`: Usually "extraction" for these documents
           - `entities`: Array of structured entities with type and value fields
                Common entity types include:
                - topics: Main subject matters covered (e.g., leadership, excel)
                - audience: Target audience (e.g., managers, new hires)
                - skills: Skills being taught (e.g., communication, coding)
                - difficulty_level: Level of difficulty (e.g., beginner, advanced)
                - methods: Teaching methods used (e.g., case studies, lecture)
                - theme: Thematic focus (e.g., compliance, technical)
                - keywords: Key terms related to this learning
                - status_type: Type of status (e.g., approval, completion)
                - instructor_role_type: Type of instructor role 
                - location_type: Type of location (e.g., office, hotel)
                - session_format: Format of the session (e.g., workshop, lecture)
           - `keywords`: Array of keywords relevant to the document
           - `topics`: Array of topics relevant to the document
           - `organizational_relationships`: Array of organizational relationships
           - `divisions`: Object containing division information
        
        4. Documents have `extracted_entities` that are structured from the metadata.
           These should be treated as factual information for analysis.
        
        To create your response, follow these steps:

        Step 1: Analyze the retrieved documents thoroughly
        - Identify ALL information relevant to the question, not just top examples
        - Check for explicit entity information in metadata
        - Look for patterns in content fields when entity extraction is missing
        - Examine relationships between different document types
        
        Step 2: Formulate your response with appropriate sections:
        - For factual questions: Direct answer → Comprehensive evidence → Additional context
        - For analytical questions: Definitive answer → COMPLETE LIST of options → Details on each option
        
        Response format guidelines:
        - Use clear markdown structure with headers (##, ###), bullet points, and tables where appropriate
        - Begin with a concise, definitive answer to the main question 
        - For learning activities, present ALL relevant items as a clear, numbered list with types and descriptions
        - Group similar activities under sub-headings if there are many to improve readability
        - When presenting multiple activities, organize them in a logical structure (e.g., by relevance, type, or popularity)
        - Use tables for comparing multiple courses when appropriate
        - If relevant, include a "Recommended Path" section that outlines the ideal sequence of activities
        
        ALWAYS INCLUDE:
        - ALL learning activities that match the query criteria
        - ALL courses that could be relevant to the audience in question
        - ALL training programs that fit the topic being asked about
        
        NEVER LIMIT your response to just the top few examples - be thorough and comprehensive.
        
        IMPORTANT REMINDER: You are only analyzing data from the CSOD (Cornerstone OnDemand) system, which is a Learning Management System (LMS). 
        Focus on learning-related data including user organizational units, transcripts, learning activities, 
        and other training-related information.
        """
    
    async def analyze_document_sufficiency(self, question: str, documents: List[Dict[str, Any]], original_question: str = None) -> Dict[str, Any]:
        """
        Analyze if the retrieved documents are sufficient to answer the question properly.
        
        Args:
            question: The user's question or current query
            documents: The retrieved documents
            original_question: The original user question (if different from current query)
            
        Returns:
            Dict with sufficiency analysis results
        """
        logger.info(f"[analyze_document_sufficiency] Analyzing document sufficiency for question: '{question}'")
        
        # Use original question if provided (for more accurate analysis)
        analysis_question = original_question or question
        
        # Set up a simple analysis if no documents
        if not documents:
            logger.warning("[analyze_document_sufficiency] No documents to analyze")
            return {
                "sufficient": False,
                "reasoning": "No documents were retrieved for this query.",
                "missing_aspects": ["Complete information not available"],
                "suggested_search_terms": ["Try more general terms"],
                "confidence": 1.0  # High confidence when no documents
            }
        
        # Prepare analysis context
        context = f"ORIGINAL QUESTION: {analysis_question}\n"
        if question != analysis_question:
            context += f"CURRENT QUERY: {question}\n"
        
        context += "\nDOCUMENT OVERVIEW:\n"
        
        # Add top document snippets
        top_docs = sorted(documents, key=lambda x: x.get('composite_score', x.get('relevance_score', 0)), reverse=True)[:5]
        
        # Group documents by source file
        doc_types = {}
        for doc in documents:
            source_file = doc.get('source_file', 'unknown')
            if source_file not in doc_types:
                doc_types[source_file] = 0
            doc_types[source_file] += 1
        
        # Add document type distribution
        context += "Document distribution:\n"
        for source_file, count in doc_types.items():
            file_info = FILE_MAPPINGS.get(source_file, {}).get('description', 'Unknown type')
            context += f"- {source_file}: {count} documents ({file_info})\n"
        
        # Add document snippets
        context += "\nTOP DOCUMENT PREVIEWS:\n"
        for i, doc in enumerate(top_docs):
            source_file = doc.get('source_file', 'unknown')
            doc_id = doc.get('document_id', 'unknown')
            
            # Extract content preview
            content = doc.get('content', {})
            content_preview = str(content)[:200] + "..." if len(str(content)) > 200 else str(content)
            
            context += f"Document {i+1} ({source_file}):\n"
            context += f"ID: {doc_id}\n"
            context += f"Score: {doc.get('composite_score', doc.get('relevance_score', 0)):.4f}\n"
            
            # Add audience and topic information if available in metadata
            metadata = doc.get('metadata', {})
            
            # Check for topics in metadata
            topics = metadata.get('topics', [])
            if topics:
                context += f"Topics: {', '.join(topics)}\n"
                
            # Check for audience entities
            entities = metadata.get('entities', [])
            audience_values = []
            
            # Handle different entity formats
            if isinstance(entities, list):
                for entity in entities:
                    if isinstance(entity, dict) and entity.get('type') == 'audience':
                        audience_values.append(entity.get('value', ''))
            elif isinstance(entities, str):
                try:
                    # Try to parse JSON string
                    import json
                    parsed_entities = json.loads(entities)
                    if isinstance(parsed_entities, list):
                        # If it's a simple list of strings, add them all as potential names
                        audience_values.extend([e for e in parsed_entities if isinstance(e, str)])
                except json.JSONDecodeError:
                    # If not valid JSON, ignore
                    pass
            
            if audience_values:
                context += f"Audience: {', '.join(audience_values)}\n"
                
            # Also check extracted entities
            extracted_entities = doc.get('extracted_entities', {})
            if extracted_entities:
                if not topics and extracted_entities.get('topics'):
                    context += f"Topics: {', '.join(extracted_entities.get('topics'))}\n"
                if not audience_values and extracted_entities.get('audience'):
                    context += f"Audience: {', '.join(extracted_entities.get('audience'))}\n"
            
            context += f"Content preview: {content_preview}\n\n"
        
        # System prompt for analysis
        system_prompt = f"""
        You are an expert document analyzer for Learning Management System (LMS) data.
        Your task is to evaluate if the retrieved documents are sufficient to answer the user's question thoroughly.
        
        Focus on:
        1. Coverage - do the documents address all aspects of the question?
        2. Depth - is there enough detailed information to provide a complete answer?
        3. Relevance - are the documents directly relevant to the question?
        4. Quality - is the information in the documents of high quality?
        
        The question is about CSOD (Cornerstone OnDemand) learning management system data.
        
        Use a BALANCED approach to your assessment:
        - Be reasonably strict but not overly perfectionist
        - Consider if the documents provide enough to give a useful answer, not a perfect one
        - If there are SOME relevant documents with decent information, consider it sufficient
        - Only mark as insufficient if there is a clear lack of relevant information
        
        Your output should be a JSON with the following structure:
        {{
            "sufficient": true/false,
            "reasoning": "Your reasoning here",
            "missing_aspects": ["aspect1", "aspect2"],  // List missing information if insufficient
            "suggested_search_terms": ["term1", "term2"],  // Terms that might help find better documents
            "confidence": 0.0-1.0  // How confident you are in this assessment (0.0 = very uncertain, 1.0 = very certain)
        }}
        
        IMPORTANT: Respond with ONLY the JSON - no additional text, explanations, or formatting.
        """
        
        # Human message with context
        human_prompt = f"""
        Please analyze if these documents are sufficient to answer the question properly.
        
        {context}
        
        Analysis as JSON:
        """
        
        try:
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(self.config.llm_request_delay)
            
            # Call LLM for analysis
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt)
                ]
            )
            
            # Extract response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON
            try:
                # Find JSON object in response
                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    result = json.loads(json_str)
                else:
                    # Try to parse the whole response as JSON
                    result = json.loads(response_text)
                
                # Ensure confidence field exists
                if 'confidence' not in result:
                    result['confidence'] = 0.7  # Default medium-high confidence
                
                logger.info(f"[analyze_document_sufficiency] Sufficiency analysis: {result.get('sufficient', False)}")
                logger.info(f"[analyze_document_sufficiency] Reasoning: {result.get('reasoning', 'No reasoning provided')}")
                logger.info(f"[analyze_document_sufficiency] Confidence: {result.get('confidence', 0.7)}")
                
                return result
            except json.JSONDecodeError:
                logger.error(f"[analyze_document_sufficiency] Failed to parse JSON from response: {response_text}")
                return {
                    "sufficient": True,  # Default to True if parsing fails
                    "reasoning": "Failed to parse analysis results, proceeding with available documents.",
                    "missing_aspects": [],
                    "suggested_search_terms": [],
                    "confidence": 0.5  # Medium confidence when parsing fails
                }
        
        except Exception as e:
            logger.error(f"[analyze_document_sufficiency] Error during sufficiency analysis: {e}")
            return {
                "sufficient": True,  # Default to True on error
                "reasoning": "Error during analysis, proceeding with available documents.",
                "missing_aspects": [],
                "suggested_search_terms": [],
                "confidence": 0.5  # Medium confidence when error occurs
            }
    
    async def refine_query(self, question: str, original_question: str, analysis: Dict[str, Any]) -> str:
        """
        Refine the query based on document sufficiency analysis.
        
        Args:
            question: Current query
            original_question: Original user question
            analysis: Document sufficiency analysis
            
        Returns:
            Refined query
        """
        logger.info(f"[refine_query] Refining query: '{question}'")
        
        # Prepare context for refinement
        missing_aspects = analysis.get('missing_aspects', [])
        suggested_terms = analysis.get('suggested_search_terms', [])
        
        # Combine missing aspects and suggested terms
        refinement_context = ""
        if missing_aspects:
            refinement_context += f"Missing information: {', '.join(missing_aspects)}\n"
        if suggested_terms:
            refinement_context += f"Suggested search terms: {', '.join(suggested_terms)}\n"
        
        # System prompt for refinement
        system_prompt = f"""
        You are an expert at refining search queries for Learning Management System (LMS) data.
        Your task is to reformulate a query to improve document retrieval results.
        
        The query is about CSOD (Cornerstone OnDemand) learning management system data.
        
        RULES FOR REFORMULATION:
        1. Maintain the core intent of the original question
        2. Add specificity based on missing aspects
        3. Incorporate suggested search terms when relevant
        4. Use general LMS terminology (learning objects, curricula, courses, training)
        5. Keep the query concise (1-2 sentences maximum)
        6. Focus on retrievable factual information, not analysis
        
        DO NOT:
        - Change the fundamental question being asked
        - Add complex analysis requirements
        - Make the query overly specific if it will limit results
        
        Your output should be ONLY the refined query - no explanations or additional text.
        """
        
        # Human message with context
        human_prompt = f"""
        Original question: {original_question}
        Current query: {question}
        
        {refinement_context}
        
        Please provide a refined query that will help retrieve more relevant documents:
        """
        
        try:
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(self.config.llm_request_delay)
            
            # Call LLM for refinement
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt)
                ]
            )
            
            # Extract response
            refined_query = response.content if hasattr(response, 'content') else str(response)
            
            # Clean up response - remove any markdown or extra formatting
            refined_query = refined_query.strip()
            # Remove quotes if present
            if (refined_query.startswith('"') and refined_query.endswith('"')) or \
               (refined_query.startswith("'") and refined_query.endswith("'")):
                refined_query = refined_query[1:-1]
            
            logger.info(f"[refine_query] Original query: '{question}'")
            logger.info(f"[refine_query] Refined query: '{refined_query}'")
            
            return refined_query
            
        except Exception as e:
            logger.error(f"[refine_query] Error refining query: {e}")
            return question  # Return original query on error
    
    async def run_agent(
        self, 
        messages: List[Dict[str, Any]], 
        question: str,
        document_ids: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run the agent's full workflow from question to answer.
        Enhanced with query refinement based on document sufficiency.
        
        Args:
            messages: List of previous messages in the conversation
            question: The user's current question or prompt
            document_ids: Optional list of specific document IDs to use
            topics: Optional list of topics for search
            keywords: Optional list of keywords for search
            additional_context: Optional additional context data
            
        Returns:
            The agent's response with answer and messages
        """
        logger.info(f"[{self.__class__.__name__}.run_agent] Processing question: '{question}'")
        
        # Check if there's a processed query in additional_context
        processed_query = question
        if additional_context and "processed_query" in additional_context:
            processed_query = additional_context["processed_query"]
            logger.info(f"[{self.__class__.__name__}.run_agent] Using processed query: '{processed_query}'")
        
        # 1. Initialize agent state
        state = CSODAgentState(
            question=processed_query,  # Use processed query as the main question
            original_question=question,  # Store original question
            current_query=processed_query,  # Initialize current query with processed
            document_ids=document_ids or [],
            topics=topics or [],
            keywords=keywords or [],
            additional_context=additional_context or {},
            chat_history=messages,
            source_type=self.source_type
        )
        
        # 2. Retrieve relevant documents with initial query
        initial_documents = await self.retrieve_documents(state)
        state.retrieved_documents = initial_documents
        logger.info(f"[{self.__class__.__name__}.run_agent] Retrieved {len(state.retrieved_documents)} documents")
        
        # 3. Analyze document sufficiency
        sufficiency_analysis = await self.analyze_document_sufficiency(
            question=state.current_query,
            documents=state.retrieved_documents,
            original_question=state.original_question
        )
        
        # 4. Determine if refinement is needed
        max_refinements = 2  # Maximum number of refinement iterations
        confidence_threshold = 0.7  # Minimum confidence to trust the analysis
        
        # Check if refinement should be attempted based on analysis
        should_refine = (
            not sufficiency_analysis.get('sufficient', True) and  # Documents insufficient
            sufficiency_analysis.get('confidence', 0) >= confidence_threshold and  # Confident in analysis
            not document_ids and  # No specific document IDs provided
            state.recursion_count < max_refinements  # Under max refinement limit
        )
        
        # 5. Refine query and retrieve additional documents if needed
        if should_refine:
            logger.info(f"[{self.__class__.__name__}.run_agent] Document sufficiency analysis indicates refinement needed")
            state.recursion_count += 1
            state.needs_refinement = True
            
            # Refine the query
            refined_query = await self.refine_query(
                question=state.current_query,
                original_question=state.original_question,
                analysis=sufficiency_analysis
            )
            
            # Update current query
            state.current_query = refined_query
            
            # Store refinement info in additional context
            if not state.additional_context:
                state.additional_context = {}
            
            state.additional_context['refined_query'] = True
            state.additional_context['refinement_iteration'] = state.recursion_count
            state.additional_context['refinement_reason'] = sufficiency_analysis.get('reasoning', '')
            state.additional_context['original_query'] = state.original_question
            
            # Preserve high-quality documents from initial retrieval
            preserved_docs = []
            if state.retrieved_documents:
                # Sort by relevance score
                sorted_docs = sorted(
                    state.retrieved_documents, 
                    key=lambda x: x.get('composite_score', x.get('relevance_score', 0)), 
                    reverse=True
                )
                
                # Keep top 25% of documents or at least 50, whichever is greater
                num_to_preserve = max(int(len(sorted_docs) * 0.25), min(50, len(sorted_docs)))
                preserved_docs = sorted_docs[:num_to_preserve]
                logger.info(f"[{self.__class__.__name__}.run_agent] Preserving {len(preserved_docs)} high-quality documents from initial retrieval")
            
            # Retrieve new documents with refined query
            refined_state = CSODAgentState(
                question=refined_query,
                original_question=state.original_question,
                current_query=refined_query,
                document_ids=state.document_ids,
                topics=state.topics,
                keywords=state.keywords,
                additional_context=state.additional_context,
                chat_history=state.chat_history,
                source_type=state.source_type,
                recursion_count=state.recursion_count
            )
            
            # Retrieve new documents with refined query
            logger.info(f"[{self.__class__.__name__}.run_agent] Retrieving additional documents with refined query: '{refined_query}'")
            refined_docs = await self.retrieve_documents(refined_state)
            
            # Limit refined documents to a reasonable number before combining
            if refined_docs:
                # Sort refined docs by relevance
                sorted_refined_docs = sorted(
                    refined_docs,
                    key=lambda x: x.get('composite_score', x.get('relevance_score', 0)),
                    reverse=True
                )
                
                # Cap refined documents to 200 to avoid excessive growth during refinement
                max_refined_docs = 200
                if len(sorted_refined_docs) > max_refined_docs:
                    logger.info(f"[{self.__class__.__name__}.run_agent] Limiting refined documents from {len(sorted_refined_docs)} to {max_refined_docs}")
                    refined_docs = sorted_refined_docs[:max_refined_docs]
            
            # Combine preserved and new documents, avoiding duplicates
            if refined_docs:
                # Create a set of existing document IDs to avoid duplicates
                existing_ids = {doc.get('document_id') for doc in preserved_docs if doc.get('document_id')}
                initial_num_docs = len(preserved_docs)
                
                # Track number of new documents added
                new_docs_count = 0
                
                # Add new documents that aren't duplicates
                for doc in refined_docs:
                    doc_id = doc.get('document_id')
                    if doc_id and doc_id not in existing_ids:
                        preserved_docs.append(doc)
                        existing_ids.add(doc_id)
                        new_docs_count += 1
                
                logger.info(f"[{self.__class__.__name__}.run_agent] Added {new_docs_count} new documents from refined query")
                
                # Apply early limiting to combined documents if they exceed threshold
                # This prevents the combined set from growing too large
                max_combined_docs = 300
                if len(preserved_docs) > max_combined_docs:
                    logger.info(f"[{self.__class__.__name__}.run_agent] Combined documents exceed limit ({len(preserved_docs)}), reducing to {max_combined_docs}")
                    # Sort by composite score to keep most relevant
                    preserved_docs = sorted(
                        preserved_docs,
                        key=lambda x: x.get('composite_score', x.get('relevance_score', 0)),
                        reverse=True
                    )[:max_combined_docs]
                
                # Update state with combined documents
                state.retrieved_documents = preserved_docs
                logger.info(f"[{self.__class__.__name__}.run_agent] Combined document set now has {len(state.retrieved_documents)} documents")
            else:
                # If refinement yielded no new results, use preserved documents
                logger.warning(f"[{self.__class__.__name__}.run_agent] Refined query yielded no new documents, using preserved high-quality documents")
                state.retrieved_documents = preserved_docs
        else:
            if not sufficiency_analysis.get('sufficient', True):
                logger.info(f"[{self.__class__.__name__}.run_agent] Documents insufficient but skipping refinement: " +
                           f"confidence={sufficiency_analysis.get('confidence', 0)}, recursion={state.recursion_count}")
            else:
                logger.info(f"[{self.__class__.__name__}.run_agent] Documents sufficient, no refinement needed")
        
        # Winnow down documents to prevent context length issues
        max_docs_for_answer = 250  # Standardized limit for answer generation
        if len(state.retrieved_documents) > max_docs_for_answer:
            logger.info(f"[{self.__class__.__name__}.run_agent] Winnowing {len(state.retrieved_documents)} documents down to {max_docs_for_answer} for answer generation")
            
            # Sort documents by relevance score to keep most relevant ones
            sorted_docs = sorted(
                state.retrieved_documents, 
                key=lambda x: x.get('composite_score', x.get('relevance_score', 0)), 
                reverse=True
            )
            
            # Preserve the top documents
            state.retrieved_documents = sorted_docs[:max_docs_for_answer]
            logger.info(f"[{self.__class__.__name__}.run_agent] Kept top {max_docs_for_answer} most relevant documents for answer generation")
        
        # Final emergency limit no longer needed as we strictly control document count at each step
        # But keep as a final safeguard with a consistent limit
        emergency_limit = 200
        if len(state.retrieved_documents) > emergency_limit:
            logger.warning(f"[{self.__class__.__name__}.run_agent] EMERGENCY LIMIT: Still have {len(state.retrieved_documents)} documents, force limiting to {emergency_limit}")
            # Sort documents by relevance score to keep most relevant ones
            sorted_docs = sorted(
                state.retrieved_documents, 
                key=lambda x: x.get('composite_score', x.get('relevance_score', 0)), 
                reverse=True
            )
            # Apply aggressive limit to avoid context length issues
            state.retrieved_documents = sorted_docs[:emergency_limit]
        
        # 6. Generate answer from documents
        answer = await self.generate_answer(state)
        logger.info(f"[{self.__class__.__name__}.run_agent] Generated answer")
        
        # 7. Format response
        response = self.format_response(answer, state.retrieved_documents)
        
        return response
    
    async def generate_answer(self, state: AgentState) -> str:
        """
        Generate an answer based on the retrieved documents.
        
        Args:
            state: Current agent state with retrieved documents
            
        Returns:
            Generated answer string
        """
        try:
            logger.info(f"[CSODAgent.generate_answer] Generating answer from {len(state.retrieved_documents)} documents")
            
            if not state.retrieved_documents:
                return "I couldn't find any relevant CSOD data to answer your question. Please try refining your query or check if the CSOD datasets contain the information you're looking for."
            
            # Document count thresholds for processing - aligned with run_agent limits
            package_filtering_threshold = 100  # Apply package-based filtering when exceeding this
            max_processed_docs = 200  # Maximum number of documents after package filtering
            max_final_docs = 150  # Final limit for document inclusion in prompt
            
            # Apply package-based filtering to preserve document relationships while reducing size
            if len(state.retrieved_documents) > package_filtering_threshold:
                logger.info(f"[CSODAgent.generate_answer] Applying package-based filtering to {len(state.retrieved_documents)} documents")
                
                # 1. Organize documents by type and relationships
                learning_activities_map = {}  # Map of learning_activity_id -> learning activity doc
                curricula_by_parent = {}      # Map of parent_id -> list of curriculum docs
                schedules_by_parent = {}      # Map of parent_id -> list of schedule docs
                transcripts_by_parent = {}    # Map of parent_id -> list of transcript docs
                other_documents = []          # Docs that don't fit into the package structure
                
                # First pass: categorize documents
                for doc in state.retrieved_documents:
                    source_file = doc.get('source_file', doc.get('metadata', {}).get('source_file', 'unknown'))
                    content = doc.get('content', {})
                    doc_id = doc.get('document_id', '')
                    
                    # Extract learning object ID if available
                    lo_object_id = None
                    if isinstance(content, dict):
                        lo_object_id = content.get('lo_object_id')
                    
                    # Categorize document based on source file
                    if 'LearningActivities_data.json' in source_file:
                        if doc_id:
                            learning_activities_map[doc_id] = doc
                            # Also store by lo_object_id if available for relationship linking
                            if lo_object_id:
                                learning_activities_map[str(lo_object_id)] = doc
                    elif 'LearningActivities_curricula_data.json' in source_file:
                        # Try to extract parent IDs for curricula
                        curriculum_parent_id = None
                        if isinstance(content, dict):
                            # Try different fields that might contain the parent relationship
                            curriculum_parent_id = content.get('curriculum_object_id') or content.get('curriculum_child_object_id')
                        
                        if curriculum_parent_id:
                            curriculum_parent_id = str(curriculum_parent_id)
                            if curriculum_parent_id not in curricula_by_parent:
                                curricula_by_parent[curriculum_parent_id] = []
                            curricula_by_parent[curriculum_parent_id].append(doc)
                        else:
                            other_documents.append(doc)
                    elif 'LearningActivities__schedule_data.json' in source_file or 'LearningActivities__session_schedule_data.json' in source_file:
                        # Try to extract parent IDs for schedules
                        schedule_parent_id = None
                        if isinstance(content, dict):
                            schedule_parent_id = content.get('rts_object_id') or content.get('lo_object_id')
                        
                        if schedule_parent_id:
                            schedule_parent_id = str(schedule_parent_id)
                            if schedule_parent_id not in schedules_by_parent:
                                schedules_by_parent[schedule_parent_id] = []
                            schedules_by_parent[schedule_parent_id].append(doc)
                        else:
                            other_documents.append(doc)
                    elif 'transcript_data.json' in source_file:
                        # For transcript data, we need to extract the learning object ID from the content
                        # This might be in various fields, so we need to check content as string
                        transcript_parent_id = None
                        content_str = str(content)
                        
                        # If we have learning activities, check if any of their IDs appear in the transcript content
                        for la_id in learning_activities_map.keys():
                            if la_id and la_id in content_str:
                                transcript_parent_id = la_id
                                break
                        
                        if transcript_parent_id:
                            if transcript_parent_id not in transcripts_by_parent:
                                transcripts_by_parent[transcript_parent_id] = []
                            transcripts_by_parent[transcript_parent_id].append(doc)
                        else:
                            other_documents.append(doc)
                    else:
                        other_documents.append(doc)
                
                # Log results of categorization
                logger.info(f"[CSODAgent.generate_answer] Categorized {len(learning_activities_map)} learning activities, "
                           f"{sum(len(docs) for docs in curricula_by_parent.values())} curricula, "
                           f"{sum(len(docs) for docs in schedules_by_parent.values())} schedules, "
                           f"{sum(len(docs) for docs in transcripts_by_parent.values())} transcripts, "
                           f"and {len(other_documents)} other documents")
                
                # 2. Create activity packages (learning activity + related docs)
                activity_packages = []
                for activity_id, activity in learning_activities_map.items():
                    # Get related documents
                    related_curricula = curricula_by_parent.get(activity_id, [])
                    related_schedules = schedules_by_parent.get(activity_id, [])
                    related_transcripts = transcripts_by_parent.get(activity_id, [])
                    
                    # If we have any related documents, this is a good package
                    has_related_docs = len(related_curricula) > 0 or len(related_schedules) > 0 or len(related_transcripts) > 0
                    
                    # Calculate aggregate package score
                    activity_score = activity.get('composite_score', activity.get('relevance_score', 0))
                    
                    # Calculate avg related doc scores - prioritize packages with more relevant related docs
                    related_docs = related_curricula + related_schedules + related_transcripts
                    related_scores = [doc.get('relevance_score', 0) for doc in related_docs]
                    avg_related_score = sum(related_scores) / len(related_scores) if related_scores else 0
                    
                    # Calculate completeness score based on having different types of related docs
                    # This rewards packages that have multiple types of related information
                    completeness_score = 0.0
                    if related_curricula:
                        completeness_score += 0.3
                    if related_schedules:
                        completeness_score += 0.4
                    if related_transcripts:
                        completeness_score += 0.3
                    
                    # Leadership content bonus
                    leadership_bonus = 0.0
                    # Check standardized metadata for leadership content
                    metadata = activity.get('metadata', {})
                    # Check topics
                    topics = metadata.get('topics', [])
                    if any(topic.lower() in ['leadership', 'management', 'executive'] for topic in topics):
                        leadership_bonus = 0.2
                    
                    # Combined score with weights
                    package_score = (activity_score * 0.5) + (avg_related_score * 0.2) + (completeness_score * 0.2) + leadership_bonus
                    
                    # Create the package
                    activity_packages.append({
                        'activity': activity,
                        'curricula': related_curricula,
                        'schedules': related_schedules,
                        'transcripts': related_transcripts[:3],  # Reduce from 5 to 3 transcripts per package to control growth
                        'score': package_score,
                        'has_related_docs': has_related_docs,
                        'activity_id': activity_id
                    })
                
                # 3. Sort packages by score and select top packages
                sorted_packages = sorted(activity_packages, key=lambda p: p['score'], reverse=True)
                
                # Calculate a dynamic package limit based on estimated document count
                # Each package contains 1 activity + curricula + schedules + transcripts
                avg_docs_per_package = 1  # Start with 1 for the activity itself
                if activity_packages:
                    # Calculate average additional docs per package
                    total_related = sum(len(p['curricula']) + len(p['schedules']) + len(p['transcripts']) for p in activity_packages)
                    avg_related = total_related / len(activity_packages) if activity_packages else 0
                    avg_docs_per_package += min(avg_related, 4)  # Cap at maximum 4 related docs per package
                
                # Target max_processed_docs with estimated avg_docs_per_package
                target_packages = int(max_processed_docs / max(avg_docs_per_package, 1))
                # Ensure we have a reasonable number (between 25-50) of packages
                max_packages = min(max(target_packages, 25), 50, len(sorted_packages))
                
                top_packages = sorted_packages[:max_packages]
                logger.info(f"[CSODAgent.generate_answer] Selected top {len(top_packages)} packages with estimated {avg_docs_per_package:.1f} docs per package")
                
                # 4. Rebuild the filtered document list
                filtered_docs = []
                
                # First add all learning activities from top packages
                seen_ids = set()
                for package in top_packages:
                    activity = package['activity']
                    activity_id = package['activity_id']
                    
                    # Only add if not already added (avoid duplicates from multiple ID mappings)
                    if activity_id not in seen_ids:
                        filtered_docs.append(activity)
                        seen_ids.add(activity_id)
                    
                    # Add related documents - limit to most relevant if there are many
                    for doc_list in [package['curricula'], package['schedules'], package['transcripts']]:
                        # Add up to 2 docs from each category per package
                        if doc_list:
                            # Sort by relevance
                            sorted_list = sorted(doc_list, key=lambda x: x.get('relevance_score', 0), reverse=True)
                            # Take top 2
                            filtered_docs.extend(sorted_list[:2])
                
                # 5. Add high-relevance documents from other categories if we have room
                # Calculate how many docs we can still add
                max_other_docs = max(0, max_processed_docs - len(filtered_docs))
                max_other_docs = min(max_other_docs, 30)  # Cap at 30 other docs
                
                if other_documents and max_other_docs > 0:
                    # Sort other documents by relevance score
                    sorted_others = sorted(
                        other_documents, 
                        key=lambda x: x.get('composite_score', x.get('relevance_score', 0)), 
                        reverse=True
                    )
                    # Add top other documents
                    filtered_docs.extend(sorted_others[:max_other_docs])
                
                logger.info(f"[CSODAgent.generate_answer] Filtered to {len(filtered_docs)} documents from {len(top_packages)} learning activity packages and {min(max_other_docs, len(other_documents))} other documents")
                
                # Update the documents in state for processing
                state.retrieved_documents = filtered_docs
            
            # Enhanced preprocessing to organize documents by source file
            source_file_groups = {}
            # Also track leadership-focused content for specific audience questions
            leadership_docs = []
            management_targeted_docs = []
            
            for doc in state.retrieved_documents:
                # Group by source file
                source_file = doc.get('source_file', doc.get('metadata', {}).get('source_file', 'unknown'))
                if source_file not in source_file_groups:
                    source_file_groups[source_file] = []
                source_file_groups[source_file].append(doc)
                
                # Track documents with leadership content or manager targeting
                if doc.get('has_leadership_content', False):
                    leadership_docs.append(doc)
                
                # Check for manager targeting in all entity sources
                management_targeted = False
                
                # Check extracted entities from standardized metadata
                extracted_entities = doc.get('extracted_entities', {})
                if extracted_entities:
                    audience = extracted_entities.get('audience', [])
                    if 'managers' in audience or 'new managers' in audience:
                        management_targeted = True
                
                # Check metadata entities directly as another option
                if not management_targeted:
                    metadata = doc.get('metadata', {})
                    entities = metadata.get('entities', [])
                    
                    # Handle different entity formats
                    if isinstance(entities, list):
                        for entity in entities:
                            if isinstance(entity, dict) and entity.get('type') == 'audience' and entity.get('value') in ['managers', 'new managers']:
                                management_targeted = True
                                break
                    elif isinstance(entities, str):
                        # For string entities, check if it contains manager-related keywords
                        entities_lower = entities.lower()
                        if any(keyword in entities_lower for keyword in ['manager', 'executive', 'leadership']):
                            management_targeted = True
                
                if management_targeted:
                    management_targeted_docs.append(doc)
            
            # Add summary of document distribution to additional context
            if not hasattr(state, 'additional_context') or not state.additional_context:
                state.additional_context = {}
                        
            source_distribution = []
            for source_file, docs in source_file_groups.items():
                file_info = FILE_MAPPINGS.get(source_file, {}).get('description', 'Unknown type')
                source_distribution.append(f"{source_file} ({len(docs)} documents): {file_info}")
            
            state.additional_context['source_distribution'] = source_distribution
            
            # Add refinement information to context
            if hasattr(state, 'original_question') and state.original_question != state.question:
                state.additional_context['original_question'] = state.original_question
            
            if hasattr(state, 'current_query') and state.current_query != state.question:
                state.additional_context['current_query'] = state.current_query
            
            if hasattr(state, 'recursion_count') and state.recursion_count > 0:
                state.additional_context['refinement_count'] = state.recursion_count
            
            # Add information about audience targeting
            if management_targeted_docs:
                state.additional_context['management_targeted_docs'] = len(management_targeted_docs)
                
            if leadership_docs:
                state.additional_context['leadership_docs'] = len(leadership_docs)
            
            # Format documents for the prompt with priority ordering and token reduction
            # Start with manager-targeted docs, then leadership docs, then others
            ordered_docs = []
            
            # First add explicitly manager-targeted docs
            for doc in management_targeted_docs:
                if doc not in ordered_docs:
                    ordered_docs.append(doc)
            
            # Then add leadership-content docs
            for doc in leadership_docs:
                if doc not in ordered_docs:
                    ordered_docs.append(doc)
            
            # Then add other high-relevance docs (sorted by score)
            remaining_docs = [doc for doc in state.retrieved_documents if doc not in ordered_docs]
            sorted_remaining = sorted(remaining_docs, key=lambda x: x.get('composite_score', x.get('relevance_score', 0)), reverse=True)
            
            # Ensure we don't exceed max_final_docs limit for context handling
            max_remaining_slots = max(0, max_final_docs - len(ordered_docs))
            ordered_docs.extend(sorted_remaining[:max_remaining_slots])
            
            logger.info(f"[CSODAgent.generate_answer] Using {len(ordered_docs)}/{len(state.retrieved_documents)} documents for answer generation")
            
            # Format the ordered documents with token reduction
            # Always enable token reduction for consistency
            formatted_docs = self.format_documents_for_context(ordered_docs, reduce_tokens=True)
            
            # Create organized document groups for better context
            organized_docs = self._organize_documents_by_type(ordered_docs)
            
            # Build structured context from organized document groups
            context_parts = ["## CSOD LEARNING MANAGEMENT DATA"]
            
            # Special handling for LearningActivities data which is most important
            if 'LearningActivities_data.json' in source_file_groups:
                activities_docs = source_file_groups['LearningActivities_data.json']
                # Sort by relevance
                sorted_activities = sorted(activities_docs, key=lambda x: x.get('composite_score', x.get('relevance_score', 0)), reverse=True)
                # Take top activities (limit to 20 for context size)
                top_activities = sorted_activities[:20]
                
                context_parts.append("\n### LEARNING ACTIVITIES")
                for i, doc in enumerate(top_activities):
                    doc_id = doc.get('document_id', f"Activity_{i+1}")
                    
                    # Add activity title/ID
                    context_parts.append(f"\n#### Activity: {doc_id}")
                    
                    # Add metadata
                    context_parts.append("Metadata:")
                    
                    # Add extracted entities if available
                    extracted_entities = doc.get('extracted_entities', {})
                    if extracted_entities:
                        for entity_type, values in extracted_entities.items():
                            if values:
                                context_parts.append(f"- {entity_type}: {', '.join(str(v) for v in values)}")
                    
                    # Add content (only key fields)
                    content = doc.get('content', {})
                    if isinstance(content, dict):
                        context_parts.append("\nContent:")
                        important_fields = ['lo_type', 'lo_object_id', 'lo_hours', 'lo_mastery_score', 'lo_active']
                        for field in important_fields:
                            if field in content:
                                value = content.get(field)
                                context_parts.append(f"- {field}: {value}")
            
            # Add session schedule data
            if 'LearningActivities__session_schedule_data.json' in source_file_groups:
                schedule_docs = source_file_groups['LearningActivities__session_schedule_data.json']
                sorted_schedules = sorted(schedule_docs, key=lambda x: x.get('composite_score', x.get('relevance_score', 0)), reverse=True)
                top_schedules = sorted_schedules[:15]  # Limit to 15
                
                context_parts.append("\n### SESSION SCHEDULES")
                for i, doc in enumerate(top_schedules):
                    doc_id = doc.get('document_id', f"Schedule_{i+1}")
                    
                    # Get content with key schedule fields
                    content = doc.get('content', {})
                    if isinstance(content, dict):
                        title = content.get('title', f"Session {i+1}")
                        context_parts.append(f"\n#### {title}")
                        
                        # Add key schedule fields
                        important_fields = ['schedule_id', 'session_id', 'start_dt_utc', 'end_dt_utc', 
                                          'part_duration', 'total_break_duration']
                        
                        for field in important_fields:
                            if field in content:
                                value = content.get(field)
                                context_parts.append(f"- {field}: {value}")
            
            # Add transcript data if available
            if 'transcript_data.json' in source_file_groups:
                transcript_docs = source_file_groups['transcript_data.json']
                sorted_transcripts = sorted(transcript_docs, key=lambda x: x.get('composite_score', x.get('relevance_score', 0)), reverse=True)
                top_transcripts = sorted_transcripts[:10]  # Limit to 10
                
                context_parts.append("\n### USER TRANSCRIPTS")
                for i, doc in enumerate(top_transcripts):
                    doc_id = doc.get('document_id', f"Transcript_{i+1}")
                    
                    # Get content with key transcript fields
                    content = doc.get('content', {})
                    if isinstance(content, dict):
                        context_parts.append(f"\n#### Transcript: {doc_id}")
                        
                        # Add key transcript fields
                        important_fields = ['reg_num', 'user_lo_status_id', 'user_lo_create_dt', 
                                          'user_lo_min_due_date', 'user_lo_assigned_dt']
                        
                        for field in important_fields:
                            if field in content:
                                value = content.get(field)
                                context_parts.append(f"- {field}: {value}")
            
            # Add other important document types
            for source_file, docs in source_file_groups.items():
                # Skip files we've already processed
                if source_file in ['LearningActivities_data.json', 
                                'LearningActivities__session_schedule_data.json', 
                                'transcript_data.json']:
                    continue
                
                # Limit to 10 documents per file type
                sorted_docs = sorted(docs, key=lambda x: x.get('composite_score', x.get('relevance_score', 0)), reverse=True)
                top_docs = sorted_docs[:10]
                
                if top_docs:
                    file_info = FILE_MAPPINGS.get(source_file, {}).get('description', 'Unknown type')
                    context_parts.append(f"\n### {file_info.upper()}")
                    
                    for i, doc in enumerate(top_docs):
                        doc_id = doc.get('document_id', f"Doc_{i+1}")
                        
                        # Add document title/ID
                        context_parts.append(f"\n#### Document: {doc_id}")
                        
                        # Add content (limited)
                        content = doc.get('content', {})
                        if isinstance(content, dict):
                            # Get the 5 most important fields
                            context_parts.append("Content:")
                            field_count = 0
                            for key, value in content.items():
                                if field_count < 5:
                                    context_parts.append(f"- {key}: {value}")
                                    field_count += 1
                                else:
                                    break
            
            # Combine all context parts
            context = "\n".join(context_parts)
            
            # Calculate context length
            context_length = len(context)
            logger.info(f"[CSODAgent.generate_answer] Context length: {context_length} characters")
            
            # If context is still too large, truncate aggressively 
            if context_length > 80000:  # Rough character count proxy for token limit
                logger.warning(f"[CSODAgent.generate_answer] Context too large ({context_length} chars), truncating")
                
                # Truncate to 80000 characters - this is approximate and conservative
                context = context[:80000] + "\n\n[TRUNCATED: Context was too large. Showing partial content.]"
            
            # Get system prompt
            system_prompt = self.build_system_prompt()
            
            # Build human prompt with enhanced context about document sufficiency
            human_prompt = self.build_human_prompt(
                question=state.question,
                context=context,
                additional_context=state.additional_context
            )
            
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(self.config.llm_request_delay)
            
            # Generate answer with LLM
            logger.info(f"[CSODAgent.generate_answer] Generating answer with context length: {len(context)}")

            # Call the LLM
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])
            
            # Extract content from response
            answer = response.content if hasattr(response, 'content') and isinstance(response.content, str) else str(response)
            
            logger.info(f"[CSODAgent.generate_answer] Generated answer of length {len(answer)}")
            
            return answer
        
        except Exception as e:
            logger.error(f"[CSODAgent.generate_answer] Error generating answer: {e}")
            return f"I encountered an error while analyzing the CSOD data: {str(e)}. Please try again or contact support if the issue persists."
            
    def _organize_documents_by_type(self, documents: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Organize documents by type for better context structure.
        
        Args:
            documents: List of documents to organize
            
        Returns:
            Dictionary of documents organized by type
        """
        organized = {
            'learning_activities': [],
            'session_schedules': [],
            'transcripts': [],
            'curricula': [],
            'users': [],
            'other': []
        }
        
        for doc in documents:
            source_file = doc.get('source_file', '')
            
            if 'LearningActivities_data.json' in source_file:
                organized['learning_activities'].append(doc)
            elif 'LearningActivities__session_schedule_data.json' in source_file:
                organized['session_schedules'].append(doc)
            elif 'transcript_data.json' in source_file:
                organized['transcripts'].append(doc)
            elif 'LearningActivities_curricula_data.json' in source_file:
                organized['curricula'].append(doc)
            elif 'user_data.json' in source_file or 'user_ou_info_data.json' in source_file:
                organized['users'].append(doc)
            else:
                organized['other'].append(doc)
                
        # Sort each category by relevance
        for category in organized:
            organized[category] = sorted(
                organized[category], 
                key=lambda x: x.get('composite_score', x.get('relevance_score', 0)), 
                reverse=True
            )
            
            # Apply limits to each category to prevent context bloat
            if category == 'learning_activities':
                # More documents for learning activities as they're typically most important
                organized[category] = organized[category][:50]  
            elif category == 'session_schedules':
                organized[category] = organized[category][:30]
            elif category == 'transcripts':
                organized[category] = organized[category][:20]
            else:
                # Stricter limits for other categories
                organized[category] = organized[category][:15]
            
        return organized 