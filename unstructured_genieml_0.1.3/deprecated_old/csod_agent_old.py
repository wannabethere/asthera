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
        ],
        "entity_types": {
            "topics": "Main subject matters covered (e.g., leadership, excel, python)",
            "audience": "Target audience for this learning (e.g., managers, new hires)",
            "skills": "Skills being taught (e.g., communication, coding, analysis)",
            "difficulty_level": "Level of difficulty (e.g., beginner, intermediate, advanced)",
            "methods": "Teaching methods used (e.g., case studies, roleplay, lecture)",
            "theme": "Thematic focus (e.g., compliance, technical, soft skills)",
            "keywords": "Key terms related to this learning"
        }
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
        ],
        "entity_types": {
            "status_type": "Type of status (e.g., approval, completion, waitlist)",
            "deadline_status": "Status related to deadline (e.g., upcoming, overdue, complete)",
            "assignment_reason": "Reason for assignment (e.g., compliance, career development)",
            "assignment_source": "Who/what assigned this (e.g., manager, system, self)",
            "priority_level": "Priority level implied (e.g., high, medium, low)",
            "skills_addressed": "Skills this learning addresses",
            "time_commitment": "Time commitment required"
        }
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
        ],
        "entity_types": {
            "instructor_full_name": "Full name of instructor",
            "instructor_role_type": "Type of instructor role (e.g., primary, assistant)",
            "approval_requirements": "What approval is needed",
            "expertise_areas": "Areas of expertise based on name/info",
            "instructor_category": "Category of instructor (e.g., internal, external)"
        }
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
        ],
        "entity_types": {
            "location_type": "Type of location (e.g., office, hotel, campus)",
            "region": "Geographic region (e.g., EMEA, APAC, North America)",
            "venue_capacity": "Capacity category (e.g., small, medium, large)",
            "facility_status": "Current status of facility",
            "timezone_region": "Region based on timezone",
            "country_grouping": "Country categorization (e.g., domestic, international)"
        }
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
        ],
        "entity_types": {
            "session_topics": "Main topics covered in this session",
            "session_format": "Format of the session (e.g., workshop, lecture, hybrid)",
            "time_of_day": "When session occurs (e.g., morning, afternoon, evening)",
            "duration_category": "Length category (e.g., short, half-day, full-day)",
            "session_type": "Type of session (e.g., intro, advanced, recap)",
            "keywords": "Key terms from description or title"
        }
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
        ],
        "entity_types": {
            "full_name": "User's full name",
            "region": "Geographic region (e.g., EMEA, APAC, North America)",
            "account_status": "Status of the user account",
            "likely_language": "Likely primary language based on name/country",
            "name_format": "Format of name (e.g., Western, Eastern)",
            "user_category": "Category of user based on available info"
        }
    },
    "LearningActivities_curricula_data.json": {
        "description": "Curriculum structure information",
        "fields": [
            "curriculum_child_object_id",
            "curriculum_section_object_id",
            "curriculum_object_id",
            "curriculum_version"
        ],
        "entity_types": {
            "curriculum_structure": "Structure type (e.g., hierarchical, sequential, modular)",
            "relationship_type": "Type of relationship between objects",
            "version_status": "Status based on version (e.g., current, legacy, draft)",
            "complexity_level": "Complexity of curriculum structure"
        }
    },
    "subject_training_data.json": {
        "description": "Subject and training relationships",
        "fields": [
            "subject_id",
            "object_id",
            "_last_touched_dt_utc"
        ],
        "entity_types": {
            "subject_category": "Category of subject",
            "update_status": "Status based on last update time",
            "relationship_type": "Type of relationship between subject and training",
            "usage_pattern": "Pattern of usage based on timestamps"
        }
    },
    "transcript_status_data.json": {
        "description": "Status codes and descriptions",
        "fields": [
            "status_id",
            "status"
        ],
        "entity_types": {
            "status_category": "Category of status (e.g., approval, completion, administrative)",
            "completion_related": "Whether status relates to completion (true/false)",
            "action_required": "Whether action is required (true/false)",
            "status_impact": "Impact of this status (e.g., blocking, informational)",
            "stakeholder": "Who this status is relevant for (e.g., learner, admin, instructor)"
        }
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
        ],
        "entity_types": {
            "org_hierarchy_depth": "Depth in org hierarchy (e.g., shallow, medium, deep)",
            "division_type": "Type of division if available",
            "org_complexity": "Complexity of organizational structure",
            "reporting_structure": "Structure of reporting relationships"
        }
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
        ],
        "entity_types": {
            "schedule_type": "Type of schedule (e.g., one-time, recurring, flexible)",
            "time_of_day": "When session occurs (e.g., morning, afternoon, evening)",
            "duration_category": "Length category (e.g., short, half-day, full-day)",
            "location_category": "Category of location",
            "admin_role": "Role of the administrator",
            "provider_category": "Category of provider",
            "region": "Geographic region based on location/timezone"
        }
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
            
            # Query the csod_datasets collection
            logger.info(f"[CSODAgent.retrieve_documents] Querying csod_datasets collection")
            
            # Set up filter for CSOD data
            # Note: We're not using a specific filter as we want to query across all CSOD documents
            
            # Set up a search limit
            search_limit = self.config.single_collection_search_limit
            
            # Perform the query
            documents = chroma_db.query_collection_with_relevance_scores(
                collection_name="csod_datasets",
                query_texts=[enhanced_query],
                n_results=search_limit
            )
            
            logger.info(f"[CSODAgent.retrieve_documents] Retrieved {len(documents)} documents from csod_datasets")
            
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
                        collection_name="csod_datasets",
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
                'collection': "csod_datasets",
                'metadata': metadata,
                'relevance_score': doc.get('relevance_score', 0.0),
                'source_type': "csod"
            }
            
            # Add source file information if available
            source_file = metadata.get('sourceFile', '')
            if source_file:
                processed_doc['source_file'] = source_file
                
                # Add file mapping information if available
                if source_file in FILE_MAPPINGS:
                    processed_doc['file_info'] = FILE_MAPPINGS[source_file]
                    
                    # Try to infer entity types if not already extracted
                    if not metadata.get('extractedEntities') and isinstance(content, dict):
                        # Entity extraction was skipped, so let's try to infer from content
                        inferred_entities = self._infer_entities_from_content(
                            content, 
                            source_file, 
                            FILE_MAPPINGS[source_file]
                        )
                        if inferred_entities:
                            processed_doc['inferred_entities'] = inferred_entities
            
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
                
                # Check if the document has inferred entities or extracted entities that match our query
                inferred_entities = activity.get('inferred_entities', {})
                audience = inferred_entities.get('audience', [])
                topics = inferred_entities.get('topics', [])
                
                # Add bonus score for management/leadership related activities
                has_leadership_content = False
                activity_content = activity.get('content', {})
                if isinstance(activity_content, dict):
                    lo_type = str(activity_content.get('lo_type', '')).lower()
                    if any(term in lo_type for term in ['lead', 'manage', 'supervis', 'executive']):
                        has_leadership_content = True
                        entity_score += 0.15
                
                # Add bonus score for inferred audience matching "managers"
                if 'managers' in audience or 'new managers' in audience:
                    entity_score += 0.25
                
                # Add bonus score for leadership topics
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
        
        # Set a reasonable limit based on expected usage
        max_packages = 500  # Limit to top 500 packages (increased from 100)
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
        
        # Log the results of our advanced processing
        logger.info(f"[_process_retrieved_documents] Processed {len(documents)} documents into {len(document_packages)} packages")
        logger.info(f"[_process_retrieved_documents] Selected {len(top_packages)} top packages resulting in {len(final_docs)} final documents")
        
        # Return the enhanced document list
        return final_docs
    
    def _infer_entities_from_content(self, content: Dict[str, Any], source_file: str, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempt to infer entity types from content based on file mapping.
        
        Args:
            content: The document content
            source_file: Source file name
            file_info: File mapping information
            
        Returns:
            Dictionary of inferred entities
        """
        inferred_entities = {}
        
        try:
            # For learning activities, try to infer audience, topics, etc.
            if source_file == "LearningActivities_data.json":
                # Check for audience indicators in any text fields
                lo_type = content.get('lo_type', '')
                if isinstance(lo_type, str):
                    lo_type_lower = lo_type.lower()
                    
                    # Check for management-related terms
                    if any(term in lo_type_lower for term in ["manage", "leader", "supervis", "executive"]):
                        inferred_entities['audience'] = ["managers"]
                        
                        # Check specifically for new manager indicators
                        if any(term in lo_type_lower for term in ["new", "first-time", "beginning", "intro", "basic"]):
                            inferred_entities['audience'].append("new managers")
                    
                    # Check for other common audiences
                    elif any(term in lo_type_lower for term in ["sales", "selling"]):
                        inferred_entities['audience'] = ["sales staff"]
                    elif any(term in lo_type_lower for term in ["technical", "engineer", "developer"]):
                        inferred_entities['audience'] = ["technical staff"]
                    elif any(term in lo_type_lower for term in ["onboard", "orientation", "new hire"]):
                        inferred_entities['audience'] = ["new employees"]
                
                # Infer topics from any available fields
                topics = []
                for field, value in content.items():
                    if isinstance(value, str) and len(value) > 3:
                        # Common topics to check for
                        common_topics = ["leadership", "management", "communication", "technical", 
                                        "compliance", "soft skills", "team building", "strategy"]
                        
                        value_lower = value.lower()
                        for topic in common_topics:
                            if topic in value_lower and topic not in topics:
                                topics.append(topic)
                
                if topics:
                    inferred_entities['topics'] = topics
            
            # For transcript data, try to infer status, assignment reason, etc.
            elif source_file == "transcript_data.json":
                # Check for assignment reasons in comments
                comments = content.get('user_lo_assigned_comments', '')
                if isinstance(comments, str) and comments:
                    comments_lower = comments.lower()
                    
                    # Look for assignment reasons
                    if any(term in comments_lower for term in ["compliance", "required", "mandatory"]):
                        inferred_entities['assignment_reason'] = ["compliance"]
                    elif any(term in comments_lower for term in ["develop", "growth", "career"]):
                        inferred_entities['assignment_reason'] = ["career development"]
                    elif any(term in comments_lower for term in ["manager", "supervisor"]):
                        inferred_entities['assignment_source'] = ["manager"]
        
        except Exception as e:
            # If inference fails, just return empty dict
            return {}
        
        return inferred_entities
    
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
            
            # Add entity types if available
            if 'entity_types' in info:
                file_mappings_text += "Potential entity types:\n"
                for entity_type, description in info['entity_types'].items():
                    file_mappings_text += f"- {entity_type}: {description}\n"
        
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
        The ChromaDB collection "csod_datasets" has documents from multiple source files. Each source file contains different types of data:
        {file_mappings_text}

        Each document contains:

        1. `document_id`: A UUID string serving as the unique identifier for each document

        2. Original data fields (varies by file type as described above)

        3. `metadata` object containing:
           - `extractedEntities`: JSON object with entity types as keys (structure depends on file type)
           - `sourceFile`: String with the original filename
           - `sourceType`: String description of the file type (e.g., "User organizational unit information")
           - `recordIndex`: Integer indicating the record's position in the original file
        
        4. Some documents might have `inferred_entities` that were determined algorithmically. 
           These are best-effort inferences that should be treated as factual information.
        
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
            
            # Add audience information if available
            inferred_entities = doc.get('inferred_entities', {})
            if inferred_entities:
                audience = inferred_entities.get('audience', [])
                if audience:
                    context += f"Audience: {', '.join(audience)}\n"
                
                topics = inferred_entities.get('topics', [])
                if topics:
                    context += f"Topics: {', '.join(topics)}\n"
            
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
        
        # 1. Initialize agent state
        state = CSODAgentState(
            question=question,
            original_question=question,  # Store original question
            current_query=question,      # Initialize current query
            document_ids=document_ids or [],
            topics=topics or [],
            keywords=keywords or [],
            additional_context=additional_context or {},
            chat_history=messages,
            source_type=self.source_type
        )
        
        # 2. Retrieve relevant documents with initial query
        state.retrieved_documents = await self.retrieve_documents(state)
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
        
        # 5. Refine query and retrieve new documents if needed
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
            
            # Retrieve documents with refined query
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
            logger.info(f"[{self.__class__.__name__}.run_agent] Retrieving documents with refined query: '{refined_query}'")
            refined_docs = await self.retrieve_documents(refined_state)
            
            # Check if refined results are better
            if len(refined_docs) > 0:
                # If we got documents from the refined query, use them
                logger.info(f"[{self.__class__.__name__}.run_agent] Retrieved {len(refined_docs)} documents with refined query")
                state.retrieved_documents = refined_docs
            else:
                # If refinement yielded no results, use original results
                logger.warning(f"[{self.__class__.__name__}.run_agent] Refined query yielded no results, using original documents")
        else:
            if not sufficiency_analysis.get('sufficient', True):
                logger.info(f"[{self.__class__.__name__}.run_agent] Documents insufficient but skipping refinement: " +
                           f"confidence={sufficiency_analysis.get('confidence', 0)}, recursion={state.recursion_count}")
            else:
                logger.info(f"[{self.__class__.__name__}.run_agent] Documents sufficient, no refinement needed")
        
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
            
            # Enhanced preprocessing to organize documents by source file
            source_file_groups = {}
            # Also track leadership-focused content for specific audience questions
            leadership_docs = []
            management_targeted_docs = []
            
            for doc in state.retrieved_documents:
                # Group by source file
                source_file = doc.get('source_file', doc.get('metadata', {}).get('sourceFile', 'unknown'))
                if source_file not in source_file_groups:
                    source_file_groups[source_file] = []
                source_file_groups[source_file].append(doc)
                
                # Track documents with leadership content or manager targeting
                if doc.get('has_leadership_content', False):
                    leadership_docs.append(doc)
                
                # Check for manager targeting in inferred entities
                inferred_entities = doc.get('inferred_entities', {})
                if inferred_entities:
                    audience = inferred_entities.get('audience', [])
                    if 'managers' in audience or 'new managers' in audience:
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
            
            # Format documents for the prompt with priority ordering
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
            
            # Then add all other docs
            for doc in state.retrieved_documents:
                if doc not in ordered_docs:
                    ordered_docs.append(doc)
            
            # Format the ordered documents
            formatted_docs = self.format_documents_for_context(ordered_docs)
            
            # Get system prompt
            system_prompt = self.build_system_prompt()
            
            # Build human prompt with enhanced context about document sufficiency
            human_prompt = self.build_human_prompt(
                question=state.question,
                context=formatted_docs,
                additional_context=state.additional_context
            )
            
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(self.config.llm_request_delay)
            
            # Generate answer with LLM
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt)
                ]
            )
            
            # Extract content from response
            answer = response.content if hasattr(response, 'content') and isinstance(response.content, str) else str(response)
            
            logger.info(f"[CSODAgent.generate_answer] Generated answer of length {len(answer)}")
            
            return answer
        
        except Exception as e:
            logger.error(f"[CSODAgent.generate_answer] Error generating answer: {e}")
            return f"I encountered an error while analyzing the CSOD data: {str(e)}. Please try again or contact support if the issue persists." 