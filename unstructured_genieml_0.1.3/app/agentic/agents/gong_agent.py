import json
from typing import Any, Dict, List, Optional, cast, Union
import asyncio
import logging
from datetime import datetime, timedelta
from pydantic import Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from tqdm import tqdm
import re
from dateutil.relativedelta import relativedelta

from chromadb import Where

from app.agentic.base.base_agent import BaseAgent, AgentState
from app.config.agent_config import chroma_collections
from app.agentic.utils.document_processor import process_retrieved_documents #format_gong_package, format_gong_metadata_summary
from app.agentic.utils.prompt_builder import build_gong_agent_system_prompt, build_human_prompt
from app.agentic.utils.section_extractor import extract_structured_sections, parse_json_list_field
from app.utils.llm_factory import get_default_llm, get_answer_generation_llm
from app.utils.logging_config import setup_agent_logger
from app.agentic.utils.query_parser import parse_time_filter
from app.agentic.utils.query_insights_utils import (
    analyze_query_with_llm,
    get_example_document_structure,
    get_related_chunks,
    safely_parse_json_field,
    extract_participants_and_mentions,
    query_insights_collection
)

# Set up logging using the centralized configuration
logger = setup_agent_logger("GongAgent")

# Silence noisy HTTPX logs from chromadb client
logging.getLogger("httpx").setLevel(logging.WARNING)

class GongAgentState(AgentState):
    """Extended state for Gong-specific processing."""
    call_ids: List[str] = Field(default_factory=list)
    transcript_ids: List[str] = Field(default_factory=list)
    gong_topics: List[str] = Field(default_factory=list)
    section_keywords: List[str] = Field(default_factory=list)  # For specific call sections
    source_type: str = "gong"  # Always set to gong for this agent

class GongAgent(BaseAgent):
    """
    Agent specialized for retrieving and processing Gong transcript data.
    Focuses on call transcripts, customer conversations, and sales interactions.
    """

    def __init__(self, llm: Optional[Any] = None):
        """Initialize the Gong agent."""
        if llm is None:
            llm = get_default_llm(task_name="gong_agent_initialization")
            logger.info(f"[GongAgent.__init__] Initialized with default LLM model")
        else:
            model_name = getattr(llm, 'model_name', str(llm))
            logger.info(f"[GongAgent.__init__] Initialized with provided LLM model: {model_name}")
        super().__init__(llm=llm, source_type="gong")
        
        # Gong-specific configurations
        self.default_topics = [
            "call", "transcript", "conversation", "objection", 
            "pain_point", "feature", "action_item", "competitor"
        ]
        self.default_keywords = [
            "discussed", "mentioned", "said", "asked", 
            "concern", "interest", "question", "next steps"
        ]
        self.default_section_keywords = [
            "Customer Pain Points", "Product Features", "Objections", 
            "Action Items", "Competitors", "Decision Criteria"
        ]
    
    async def retrieve_documents(self, state: AgentState) -> List[Dict[str, Any]]:
        """
        Retrieve Gong documents based on the query.
        Implements a multi-step filtering process: first, it will fetch up to 500 insights and semantically prune them to the top 250; next, for each of these insights, it will fetch all associated chunks and calculate an aggregate relevance score; finally, it will sort the insights by this new score, select the top 125, and return a flattened list of documents containing only these top insights and their chunks.
        
        Args:
            state: The current agent state
            
        Returns:
            List of retrieved Gong documents
        """
        try:
            logger.info(f"[GongAgent.retrieve_documents] Starting document retrieval for query: '{state.question}'")
            
            # Import required utilities here to avoid circular imports
            from app.utils.chromadb import ChromaDB
            # Initialize with WARNING log level to reduce noise
            chroma_db = ChromaDB(log_level="WARNING")
            
            # Check for specific additional context
            additional_context = {}
            if hasattr(state, 'additional_context') and state.additional_context:
                additional_context = state.additional_context
            
            # Extract section_keywords if provided in additional context
            section_keywords = []
            if 'section_keywords' in additional_context:
                section_keywords = additional_context['section_keywords']
            
            # For GongAgentState specific attributes
            if isinstance(state, GongAgentState):
                if state.section_keywords:
                    section_keywords.extend(state.section_keywords)
            
            # Log section keywords if available
            if section_keywords:
                logger.info(f"[GongAgent.retrieve_documents] Using {len(section_keywords)} section keywords for filtering: {section_keywords[:5]}...")
            
            # Use LLM to analyze the query and determine relevant topics and metadata fields
            document_structure = get_example_document_structure()
            llm_analysis = analyze_query_with_llm(
                query=state.question,
                document_structure=document_structure,
                user_topics=state.topics if state.topics else None
            )

            # Extract topics from LLM analysis
            topics = []
            if "search_terms" in llm_analysis:
                topics = llm_analysis["search_terms"]
                logger.info(f"[GongAgent.retrieve_documents] Using {len(topics)} topics from LLM analysis: {topics}")
            elif state.topics:
                topics = state.topics
                logger.info(f"[GongAgent.retrieve_documents] Using {len(topics)} specific topics from state: {topics}")
            else:
                # Only use default topics if none were provided
                topics = self.default_topics
                logger.info(f"[GongAgent.retrieve_documents] No specific topics provided, using {len(topics)} default topics")
            
            # Store the topics in the state for later use
            state.topics = topics
            
            # We don't need to build an enhanced query anymore as we're using the original query directly
            # The query_insights_collection function will handle topic integration internally
            
            logger.info(f"[GongAgent.retrieve_documents] Using original query: '{state.question}'")

            # 1. Handle specific document IDs if provided
            if state.document_ids:
                logger.info(f"[GongAgent.retrieve_documents] Using specific document IDs: {state.document_ids}")
                return await self._retrieve_by_document_ids(state.document_ids, state)
            
            # 2. Parse temporal query parameters
            time_range = parse_time_filter(state.question, topics)
            logger.info(f"[GongAgent.retrieve_documents] Detected time range: {time_range}")
            
            # 3. Set up combined filter for Gong data with time constraints
            now = datetime.now()
            logger.info(f"[GongAgent.retrieve_documents] Current date: {now.strftime('%Y-%m-%d')}")
            
            # Default 120-day filter as the maximum allowable time range
            max_range_timestamp = (now - timedelta(days=120)).timestamp()
            min_timestamp = max_range_timestamp  # Start with the 120-day limit
            
            # If a specific time range was detected, further narrow down within the 120-day window
            if time_range:
                # Calculate the specific time range timestamp
                specific_timestamp = now.timestamp()  # Initialize with current time
                
                if time_range['unit'] == 'days':
                    specific_timestamp = (now - timedelta(days=time_range['value'])).timestamp()
                    specific_date = (now - timedelta(days=time_range['value'])).strftime('%Y-%m-%d')
                    logger.info(f"[GongAgent.retrieve_documents] Calculated {time_range['value']} days ago as: {specific_date}")
                elif time_range['unit'] == 'weeks':
                    specific_timestamp = (now - timedelta(days=time_range['value'] * 7)).timestamp()
                    specific_date = (now - timedelta(days=time_range['value'] * 7)).strftime('%Y-%m-%d')
                    logger.info(f"[GongAgent.retrieve_documents] Calculated {time_range['value']} weeks ago as: {specific_date}")
                elif time_range['unit'] == 'months':
                    # Calculate more precise month timestamps using calendar month logic
                    date_n_months_ago = now - relativedelta(months=time_range['value'])
                    specific_timestamp = date_n_months_ago.timestamp()
                    specific_date = date_n_months_ago.strftime('%Y-%m-%d')
                    logger.info(f"[GongAgent.retrieve_documents] Calculated {time_range['value']} months ago as: {specific_date}")
                
                # Ensure we never go beyond the 120-day limit (take the more recent timestamp)
                min_timestamp = max(specific_timestamp, max_range_timestamp)
                
                # Convert min_timestamp back to date for logging
                min_date = datetime.fromtimestamp(min_timestamp).strftime('%Y-%m-%d')
                logger.info(f"[GongAgent.retrieve_documents] Final timestamp for {time_range['expression']}: {min_date} (after applying 120-day limit)")
                
                logger.info(f"[GongAgent.retrieve_documents] Narrowed time range to: {time_range['expression']} within the 120-day window")
            
            # Debug logs for the query parameters
            logger.info(f"[GongAgent.retrieve_documents] Using time filter from {datetime.fromtimestamp(min_timestamp).strftime('%Y-%m-%d')} to present (120-day maximum)")
            
            # Set up simple time filter using date_timestamp
            time_filter = {"date_timestamp": {"$gte": float(min_timestamp)}}
            
            # Set up combined filter with source_type and date
            combined_filter = {
                "$and": [
                    {"source_type": {"$eq": "gong"}},
                    time_filter
                ]
            }
            
            # PHASE 1: Add metadata-driven pre-filtering based on query content
            metadata_filter = {}

            # Check for insight type mentions in the query
            question_lower = state.question.lower()

            # Map query terms to metadata fields
            insight_type_mapping = {
                "pain point": "pain_points",
                "pain points": "pain_points",
                "challenges": "pain_points",
                "problems": "pain_points",
                "objection": "objections",
                "objections": "objections",
                "concern": "objections",
                "concerns": "objections",
                "feature": "product_features",
                "features": "product_features",
                "product feature": "product_features",
                "product features": "product_features",
                "action item": "action_items",
                "action items": "action_items",
                "next steps": "action_items",
                "follow up": "action_items",
                "competitor": "competitors",
                "competitors": "competitors",
                "competition": "competitors",
                "decision criteria": "decision_criteria",
                "criteria": "decision_criteria",
                "decision factor": "decision_criteria",
                "use case": "use_cases",
                "use cases": "use_cases",
                "buyer role": "buyer_roles",
                "buyer roles": "buyer_roles",
                "stakeholder": "buyer_roles"
            }

            # Check for matches and add to metadata filter
            detected_filters = []
            for query_term, metadata_field in insight_type_mapping.items():
                if query_term in question_lower:
                    # We don't directly filter on these fields since they're stored as JSON strings
                    # Instead, we'll use them for post-retrieval filtering
                    detected_filters.append(metadata_field)
                    logger.info(f"[GongAgent.retrieve_documents] Detected {query_term} in query, will prioritize {metadata_field}")

            # Store detected filters in state for post-retrieval processing
            if detected_filters:
                if not hasattr(state, 'additional_context') or not state.additional_context:
                    state.additional_context = {}
                state.additional_context['metadata_filters'] = detected_filters
                logger.info(f"[GongAgent.retrieve_documents] Added metadata filters: {detected_filters}")

            # STEP 1: Broad query to get up to 500 insights
            initial_insights = []
            detected_time_range = None
            if time_range:
                detected_time_range = time_range.copy()  # Save for later filtering
                
            if "cross_reference_opportunities" in additional_context:
                cr_opps = additional_context["cross_reference_opportunities"]
                if cr_opps:
                    logger.info(f"[GongAgent.retrieve_documents] Prefiltering by opportunity names: {cr_opps}")

                    # First try exact matching by gong_title
                    initial_insights = chroma_db.query_collection_with_relevance_scores(
                        collection_name=chroma_collections.insights_collection,
                        query_texts=cr_opps,
                        n_results=500,
                        where=cast(Where, {"metadata.gong_title": {"$in": cr_opps}})
                    )
                    logger.info(f"[GongAgent.retrieve_documents] Found {len(initial_insights)} insights with exact title matches")

                    # If no exact matches found, try semantic search for gong_call_insights
                    if not initial_insights:
                        logger.info(f"[GongAgent.retrieve_documents] No exact matches found, trying semantic search for similar call titles")

                        semantic_insights = []
                        for opp_name in cr_opps:
                            # Search for semantically similar gong_call_insights documents
                            semantic_results = chroma_db.query_collection_with_relevance_scores(
                                collection_name=chroma_collections.insights_collection,
                                query_texts=[opp_name],
                                where=cast(Where, {
                                    "$and": [
                                        {"source_type": {"$eq": "gong"}},
                                        {"document_type": {"$eq": "gong_call_insights"}}
                                    ]
                                }),
                                n_results=10  # Get top 10 semantic matches per opportunity name
                            )

                            if semantic_results:
                                logger.info(f"[GongAgent.retrieve_documents] Found {len(semantic_results)} semantic matches for '{opp_name}':")
                                for i, result in enumerate(semantic_results[:3]):  # Log top 3 matches
                                    metadata = result.get('metadata', {})
                                    gong_title = metadata.get('gong_title', 'No title')
                                    distance = result.get('distance', 0)
                                    relevance = result.get('relevance_score', 0)
                                    logger.info(f"[GongAgent.retrieve_documents]   {i+1}. '{gong_title}' (relevance: {relevance:.4f})")

                                semantic_insights.extend(semantic_results)

                        # Remove duplicates based on document_id and sort by relevance
                        seen_ids = set()
                        unique_semantic_insights = []
                        for insight in semantic_insights:
                            doc_id = insight.get('document_id', '')
                            if doc_id and doc_id not in seen_ids:
                                seen_ids.add(doc_id)
                                unique_semantic_insights.append(insight)

                        # Sort by relevance score and take top results
                        unique_semantic_insights.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
                        initial_insights = unique_semantic_insights[:500]  # Cap at 500 as per original logic

                        logger.info(f"[GongAgent.retrieve_documents] After deduplication, using {len(initial_insights)} semantically similar insights")

                    if not initial_insights:
                        logger.info(f"[GongAgent.retrieve_documents] No exact or semantic matches found for opportunity names")
                else:
                    logger.info("[GongAgent.retrieve_documents] cross_reference_opportunities provided but empty → skipping retrieval")
                    return []
            else:
                try:
                    logger.info(f"[GongAgent.retrieve_documents] Using direct insights querying approach from query_insights.py")

                    # Set debug mode to true to get more detailed logging
                    debug_mode = True
                    logger.info(f"[GongAgent.retrieve_documents] Debug mode: {debug_mode}")

                    # Log the configured collection names - we ONLY use these collections
                    logger.info(f"[GongAgent.retrieve_documents] Using insights collection: {chroma_collections.insights_collection}")
                    logger.info(f"[GongAgent.retrieve_documents] Using chunks collection: {chroma_collections.chunks_collection}")

                    # Make sure the ChromaDB client is initialized
                    if chroma_db.client is None:
                        logger.info(f"[GongAgent.retrieve_documents] ChromaDB client is None, initializing connection")
                        chroma_db._connect_client()
                        if chroma_db.client is None:
                            raise Exception("Failed to initialize ChromaDB client connection")

                    # Use the query_insights_collection function to get insights
                    # This uses the LLM-driven approach from query_insights.py
                    filtered_insights, query_llm_analysis = query_insights_collection(
                        chroma_client=chroma_db,  # Pass the ChromaDB instance instead of just the client
                        query_text=state.question,
                        user_topics=topics,
                        insights_collection_name=chroma_collections.insights_collection,
                        n_results=500,  # Get up to 500 insights
                        debug=debug_mode  # Enable verbose debugging
                    )

                    # Log detailed information about the results
                    logger.info(f"[GongAgent.retrieve_documents] query_insights_collection returned {len(filtered_insights)} results")

                    if filtered_insights:
                        # Log the first few results for debugging
                        logger.info("[GongAgent.retrieve_documents] Top filtered insights:")
                        for i, insight in enumerate(filtered_insights[:3]):
                            doc_id = insight.get('document_id', 'unknown')
                            score = insight.get('relevance_score', 0)
                            metadata = insight.get('metadata', {})
                            title = metadata.get('title', metadata.get('gong_title', 'No title'))
                            logger.info(f"  {i+1}. '{title}' (ID: {doc_id}, score: {score:.4f})")
                    else:
                        logger.warning("[GongAgent.retrieve_documents] No insights found in collection")
                        # Log the search parameters for debugging
                        logger.info(f"[GongAgent.retrieve_documents] Search parameters: collection={chroma_collections.insights_collection}, query={state.question}, topics={topics}")

                        # Check if the collection exists and has documents
                        try:
                            test_results = chroma_db.client.get_collection(chroma_collections.insights_collection).peek(limit=5)
                            if test_results and test_results.get('ids'):
                                logger.info(f"[GongAgent.retrieve_documents] Collection {chroma_collections.insights_collection} exists and contains {len(test_results.get('ids', []))} documents")
                            else:
                                logger.warning(f"[GongAgent.retrieve_documents] Collection {chroma_collections.insights_collection} exists but appears to be empty")
                        except Exception as peek_err:
                            logger.error(f"[GongAgent.retrieve_documents] Error checking collection: {peek_err}")

                    # Apply time filtering if needed
                    if detected_time_range and filtered_insights:
                        logger.info(f"[GongAgent.retrieve_documents] Post-processing to enforce time filter: {detected_time_range['expression']}")
                        time_filtered_insights = []

                        # Filter insights by date
                        for insight in filtered_insights:
                            metadata = insight.get('metadata', {})
                            date_timestamp = metadata.get('date_timestamp')

                            try:
                                if isinstance(date_timestamp, str):
                                    date_timestamp = float(date_timestamp)

                                # Check if timestamp is within our range
                                if float(date_timestamp) >= min_timestamp:
                                    time_filtered_insights.append(insight)
                            except (ValueError, TypeError) as e:
                                # Skip documents with invalid timestamps
                                pass

                        # Log results
                        filtered_count = len(time_filtered_insights)
                        original_count = len(filtered_insights)

                        logger.info(f"[GongAgent.retrieve_documents] Post-processing filtered insights from {original_count} to {filtered_count} based on time criteria")

                        # Use the filtered insights
                        initial_insights = time_filtered_insights
                    else:
                        # Use all insights if no time filtering
                        initial_insights = filtered_insights

                    # Store time range information for the LLM prompt
                    if not hasattr(state, 'additional_context') or not state.additional_context:
                        state.additional_context = {}

                    if detected_time_range:
                        state.additional_context['time_range'] = detected_time_range
                        from_date = datetime.fromtimestamp(min_timestamp).strftime('%B %d, %Y')
                        to_date = now.strftime('%B %d, %Y')
                        state.additional_context['date_range'] = f"{from_date} to {to_date}"
                        state.additional_context['enforce_time_filter'] = True

                        # Set flag if we ended up with no data after time filtering
                        if len(initial_insights) == 0:
                            state.additional_context['empty_time_filtered_results'] = True
                            logger.warning(f"[GongAgent.retrieve_documents] No documents available for the requested time period: {detected_time_range['expression']}")

                    logger.info(f"[GongAgent.retrieve_documents] Retrieved {len(initial_insights)} insights using query_insights_collection")

                except Exception as insights_err:
                    logger.warning(f"[GongAgent.retrieve_documents] Error using query_insights_collection: {insights_err}")
                    logger.info(f"[GongAgent.retrieve_documents] Falling back to original retrieval method")

                    # Fallback to the original retrieval method
                    try:
                        logger.info(f"[GongAgent.retrieve_documents] Performing broad query to get up to 500 insights")

                        initial_insights = chroma_db.query_collection_with_relevance_scores(
                            collection_name=chroma_collections.insights_collection,
                            query_texts=[state.question],
                            n_results=500,
                            where=cast(Where, combined_filter)
                        )

                        logger.info(f"[GongAgent.retrieve_documents] Found {len(initial_insights)} initial insights with time filter")

                        # If no results with time filter, try source_type only
                        if not initial_insights:
                            logger.info(f"[GongAgent.retrieve_documents] No insights with time filter, falling back to source_type only")

                            # Fallback to source_type only
                            initial_insights = chroma_db.query_collection_with_relevance_scores(
                                collection_name=chroma_collections.insights_collection,
                                query_texts=[state.question],
                                n_results=500,
                                where={"source_type": {"$eq": "gong"}}
                            )

                            logger.info(f"[GongAgent.retrieve_documents] Found {len(initial_insights)} insights with source_type only")

                            # Apply post-processing only during fallback to filter by date
                            if detected_time_range and initial_insights:
                                logger.info(f"[GongAgent.retrieve_documents] Post-processing to enforce time filter: {detected_time_range['expression']}")
                                filtered_insights = []

                                # Filter insights by date
                                for insight in initial_insights:
                                    metadata = insight.get('metadata', {})
                                    date_timestamp = metadata.get('date_timestamp')

                                    try:
                                        if isinstance(date_timestamp, str):
                                            date_timestamp = float(date_timestamp)

                                        # Check if timestamp is within our range
                                        if float(date_timestamp) >= min_timestamp:
                                            filtered_insights.append(insight)
                                    except (ValueError, TypeError) as e:
                                        # Skip documents with invalid timestamps
                                        pass

                                # Log results
                                filtered_count = len(filtered_insights)
                                original_count = len(initial_insights)

                                logger.info(f"[GongAgent.retrieve_documents] Post-processing filtered insights from {original_count} to {filtered_count} based on time criteria")

                                # Use the filtered insights
                                initial_insights = filtered_insights
                    
                    except Exception as fallback_err:
                        logger.error(f"[GongAgent.retrieve_documents] Error in fallback retrieval: {fallback_err}")
                        return []
            
            # STEP 2: Winnow down to top 250 insights
            top_250_insights = sorted(
                initial_insights,
                key=lambda x: x.get('relevance_score', 0),
                reverse=True
            )[:250]
            
            # Check if we have any insights before proceeding
            if not top_250_insights:
                logger.warning("[GongAgent.retrieve_documents] No insights found matching the query")
                return []

            ids = [insight.get('document_id') for insight in top_250_insights]
            texts = [insight.get('content', '') for insight in top_250_insights]
            logger.info(f"[GongAgent.retrieve_documents] Top 250 insights selected, now batching chunk lookup…")

            # PHASE 2: Apply MMR re-ranking to get a more diverse set of insights
            try:
                # Only apply MMR if we have enough insights to make it worthwhile
                if len(top_250_insights) > 50:
                    logger.info(f"[GongAgent.retrieve_documents] Applying MMR re-ranking to {len(top_250_insights)} insights")

                    # Convert insights to format needed for MMR
                    mmr_candidates = []
                    for insight in top_250_insights:
                        # Create a document-like object with text and metadata
                        mmr_candidates.append({
                            'page_content': insight.get('content', ''),
                            'metadata': {
                                'document_id': insight.get('document_id', ''),
                                'relevance_score': insight.get('relevance_score', 0)
                            }
                        })

                    # Apply MMR algorithm manually
                    # This is a simplified version of MMR that promotes diversity
                    mmr_selected = []
                    remaining_candidates = mmr_candidates.copy()

                    # Parameters for MMR
                    lambda_param = 0.7  # Balance between relevance and diversity (higher = more relevance)
                    target_size = min(50, len(mmr_candidates))  # Select top 50 or fewer

                    # Helper function to calculate similarity between documents
                    def calculate_similarity(doc1, doc2):
                        # Simple overlap similarity based on shared words
                        words1 = set(doc1['page_content'].lower().split())
                        words2 = set(doc2['page_content'].lower().split())

                        if not words1 or not words2:
                            return 0

                        overlap = len(words1.intersection(words2))
                        similarity = overlap / min(len(words1), len(words2))
                        return similarity

                    # Select first document based on highest relevance
                    first_doc = max(remaining_candidates, key=lambda x: x['metadata']['relevance_score'])
                    mmr_selected.append(first_doc)
                    remaining_candidates.remove(first_doc)

                    # Select remaining documents using MMR
                    while len(mmr_selected) < target_size and remaining_candidates:
                        max_mmr_score = -1
                        max_mmr_doc = None

                        for doc in remaining_candidates:
                            # Relevance component
                            relevance = doc['metadata']['relevance_score']

                            # Diversity component - max similarity to any selected document
                            max_similarity = 0
                            for selected_doc in mmr_selected:
                                similarity = calculate_similarity(doc, selected_doc)
                                max_similarity = max(max_similarity, similarity)

                            # MMR score combines relevance and diversity
                            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity

                            if mmr_score > max_mmr_score:
                                max_mmr_score = mmr_score
                                max_mmr_doc = doc

                        if max_mmr_doc:
                            mmr_selected.append(max_mmr_doc)
                            remaining_candidates.remove(max_mmr_doc)
                        else:
                            break

                    # Convert back to original format
                    mmr_insight_ids = [doc['metadata']['document_id'] for doc in mmr_selected]
                    mmr_insights = [insight for insight in top_250_insights if insight.get('document_id', '') in mmr_insight_ids]

                    logger.info(f"[GongAgent.retrieve_documents] MMR re-ranking selected {len(mmr_insights)} diverse insights")

                    # Use MMR insights instead of original top insights
                    top_250_insights = mmr_insights

                    # Update ids and texts lists
                    ids = [insight.get('document_id') for insight in top_250_insights]
                    texts = [insight.get('content', '') for insight in top_250_insights]
            except Exception as mmr_error:
                logger.warning(f"[GongAgent.retrieve_documents] Error applying MMR re-ranking: {mmr_error}. Continuing with original ranking.")
                # Continue with original ranking if MMR fails

            # STEP 3: Process chunks in smaller batches instead of all at once
            # Make sure the ChromaDB client is initialized before accessing collections
            if chroma_db.client is None:
                logger.info(f"[GongAgent.retrieve_documents] ChromaDB client is None, initializing connection")
                chroma_db._connect_client()
                if chroma_db.client is None:
                    raise Exception("Failed to initialize ChromaDB client connection")

            chunks_collection = chroma_db.client.get_collection(name=chroma_collections.chunks_collection)
            logger.info(f"[GongAgent.retrieve_documents] Querying chunks for {len(top_250_insights)} insights in batches...")

            # Define batch size for processing
            BATCH_SIZE = 25
            insight_packages = []

            # Debug counter for total chunks found
            total_chunks_found = 0
            insights_with_chunks = 0
            insights_without_chunks = 0

            # Process in batches with tqdm progress bar
            batch_count = (len(top_250_insights) + BATCH_SIZE - 1) // BATCH_SIZE
            for i in tqdm(range(0, len(top_250_insights), BATCH_SIZE),
                          desc="Processing insight batches",
                          total=batch_count,
                          unit="batch"):
                batch_end = min(i + BATCH_SIZE, len(top_250_insights))
                batch_insights = top_250_insights[i:batch_end]

                logger.info(f"[GongAgent.retrieve_documents] Processing batch {i//BATCH_SIZE + 1}/{batch_count}: insights {i+1}-{batch_end}")

                # Process each insight to find its chunks
                for insight in batch_insights:
                    insight_id = insight.get('document_id', '')
                    insight_score = insight.get('relevance_score', 0)

                    if not insight_id:
                        # Skip insights without IDs
                        continue

                    # Use the improved get_related_chunks function to find all related chunks
                    logger.info(f"[GongAgent.retrieve_documents] Looking for chunks related to document ID: {insight_id}")
                    # print(f"\n==== CHUNK LOOKUP DEBUGGING ====")
                    # print(f"Looking for chunks for insight ID: {insight_id}")
                    # print(f"Using chunks collection: {chroma_collections.chunks_collection}")

                    # Try direct collection access first to verify the collection exists
                    try:
                        chunks_collection = chroma_db.client.get_collection(name=chroma_collections.chunks_collection)
                        # print(f"Successfully accessed chunks collection: {chroma_collections.chunks_collection}")
                        # Peek at collection to see if it contains any documents
                        peek_results = chunks_collection.peek(limit=1)
                        if peek_results and peek_results.get("ids"):
                            # print(f"Chunks collection contains documents. First ID: {peek_results['ids'][0]}")
                            pass
                        else:
                            # print(f"WARNING: Chunks collection appears to be empty!")
                            pass
                    except Exception as e:
                        # print(f"Error accessing chunks collection: {e}")
                        pass

                    chunks = get_related_chunks(
                        chroma_client=chroma_db.client,
                        doc_id=insight_id,
                        chunks_collection_name=chroma_collections.chunks_collection,
                        debug=True  # Enable debug logging
                    )

                    # Convert chunks to the format expected by the rest of the code
                    formatted_chunks = []
                    if chunks:
                        #logger.info(f"[DEBUG] Found {len(chunks)} chunks for insight ID: {insight_id}")
                        insights_with_chunks += 1
                        total_chunks_found += len(chunks)

                        for chunk in chunks:
                            chunk_doc = {
                                'document_id': chunk['id'],
                                'document_type': chunk['metadata'].get('document_type', 'gong_chunk'),  # Use the document_type from metadata
                                'content': chunk['content'],
                                'metadata': chunk['metadata'],
                                'collection': chroma_collections.chunks_collection,
                                'parent_doc_id': insight_id,
                                'relevance_score': 0.5  # Default score to be updated later
                            }
                            formatted_chunks.append(chunk_doc)
                    else:
                        logger.info(f"[DEBUG] No chunks found for insight ID: {insight_id}")
                        insights_without_chunks += 1

                    # PHASE 3: Improve joint insight+chunk scoring
                    if formatted_chunks:
                        # Calculate chunk scores by semantic similarity to the query
                        chunk_scores = []

                        try:
                            # Query for chunk relevance scores
                            chunk_ids = [chunk['document_id'] for chunk in formatted_chunks]
                            chunk_texts = [chunk['content'] for chunk in formatted_chunks]

                            # Only perform semantic scoring if we have enough chunks
                            if len(chunk_ids) >= 2:
                                # Get semantic relevance scores for chunks
                                chunk_results = chroma_db.query_by_ids_with_relevance(
                                    collection_name=chroma_collections.chunks_collection,
                                    ids=chunk_ids,
                                    query_texts=[state.question],
                                )

                                # Extract scores from results
                                if chunk_results:
                                    for chunk in formatted_chunks:
                                        chunk_id = chunk['document_id']
                                        # Find matching result
                                        for result in chunk_results:
                                            if result.get('document_id') == chunk_id:
                                                chunk['relevance_score'] = result.get('relevance_score', 0.5)
                                                chunk_scores.append(chunk['relevance_score'])
                                                break
                                        else:
                                            # If no match found, use default score
                                            chunk['relevance_score'] = 0.5
                                            chunk_scores.append(0.5)
                                else:
                                    # If no results, use default scores
                                    for chunk in formatted_chunks:
                                        chunk['relevance_score'] = 0.5
                                        chunk_scores.append(0.5)
                            else:
                                # For single chunks, use a decent default score
                                for chunk in formatted_chunks:
                                    chunk['relevance_score'] = 0.6  # Slightly higher than default
                                    chunk_scores.append(0.6)

                        except Exception as scoring_err:
                            logger.warning(f"[GongAgent.retrieve_documents] Error scoring chunks: {scoring_err}")
                            # Use default scores if scoring fails
                            for chunk in formatted_chunks:
                                chunk['relevance_score'] = 0.5
                                chunk_scores.append(0.5)

                        # Calculate average chunk score
                        avg_chunk_score = sum(chunk_scores) / len(chunk_scores) if chunk_scores else 0.5

                        # Calculate max chunk score for highly relevant excerpts
                        max_chunk_score = max(chunk_scores) if chunk_scores else 0.5

                        # Dynamic weighting based on chunk quality
                        # If max chunk is very relevant, give it more weight
                        if max_chunk_score > 0.8:
                            # Emphasize the best chunk when it's highly relevant
                            chunk_weight = 0.4
                            max_weight = 0.2
                            insight_weight = 0.4
                        else:
                            # Otherwise use more balanced weights
                            chunk_weight = 0.3
                            max_weight = 0.1
                            insight_weight = 0.6

                        # Calculate aggregate score with dynamic weighting
                        aggregate_score = (
                            insight_weight * insight_score +
                            chunk_weight * avg_chunk_score +
                            max_weight * max_chunk_score
                        )

                        # Add the insight and its chunks to the packages
                        insight_packages.append({
                            'insight': insight,
                            'chunks': formatted_chunks,
                            'aggregate_score': aggregate_score,
                            'num_chunks': len(formatted_chunks),
                            'avg_chunk_score': avg_chunk_score,
                            'max_chunk_score': max_chunk_score
                        })
                    else:
                        # No chunks found, use insight score only
                        insight_packages.append({
                            'insight': insight,
                            'chunks': [],
                            'aggregate_score': insight_score,
                            'num_chunks': 0,
                            'avg_chunk_score': 0,
                            'max_chunk_score': 0
                        })

            # STEP 5: Sort + pick top 125 packages
            sorted_packages = sorted(insight_packages, key=lambda p: p['aggregate_score'], reverse=True)
            top_packages = sorted_packages[:125]
            logger.info(f"[GongAgent.retrieve_documents] Winnowed down to top {len(top_packages)} insight packages based on aggregate score.")

            # STEP 6: Store packages in state and create flattened list for backward compatibility
            # Update insight relevance scores with aggregate scores
            for pkg in top_packages:
                pkg['insight']['relevance_score'] = pkg['aggregate_score']

            # Store packages in state to avoid reconstruction later
            state.insight_packages = top_packages

            # Create flattened document list for backward compatibility
            all_documents = []
            for pkg in top_packages:
                all_documents.append(pkg['insight'])
                all_documents.extend(pkg['chunks'])
            
            # STEP 7: No filtering - keep all chunks for each insight
            logger.info(f"[GongAgent.retrieve_documents] Keeping all {len(all_documents)} documents without chunk filtering")
            logger.info(f"[GongAgent.retrieve_documents] Stored {len(top_packages)} insight packages in state")
            
            # Process and structure the documents
            processed_docs = self._process_retrieved_documents(all_documents)
            logger.info(f"[GongAgent.retrieve_documents] Retrieved {len(processed_docs)} documents")
            return processed_docs
            
        except Exception as e:
            logger.error(f"[GongAgent.retrieve_documents] Error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _retrieve_by_document_ids(self, document_ids: List[str], state: Optional[AgentState] = None) -> List[Dict[str, Any]]:
        """Retrieve specific Gong documents by their IDs."""
        logger.info(f"[GongAgent._retrieve_by_document_ids] Retrieving documents by IDs: {document_ids}")
        
        try:
            # Import required utilities here to avoid circular imports
            from app.utils.chromadb import ChromaDB
            # Initialize with WARNING log level to reduce noise
            chroma_db = ChromaDB(log_level="WARNING")
            
            # Process document IDs
            all_docs = []
            for doc_id in document_ids:
                try:
                    # Try to get the document directly first
                    direct_docs = chroma_db.query_collection_with_relevance_scores(
                        collection_name=chroma_collections.documents_collection,
                        query_texts=[""],  # Empty query to just retrieve by ID
                        n_results=1,  # Just need the one document
                        where={"document_id": {"$eq": doc_id}}
                    )
                    
                    if direct_docs:
                        logger.info(f"[GongAgent._retrieve_by_document_ids] Found document directly: {doc_id}")
                        for doc in direct_docs:
                            doc['collection'] = chroma_collections.documents_collection
                            all_docs.append(doc)
                    else:
                        # Look in gong_insights
                        insights_docs = chroma_db.query_collection_with_relevance_scores(
                            collection_name=chroma_collections.insights_collection,
                            query_texts=[""],  # Empty query to just retrieve by ID
                            n_results=self.config.sfdc_query_limit,
                            where={"document_id": {"$eq": doc_id}}
                        )
                        
                        if insights_docs:
                            logger.info(f"[GongAgent._retrieve_by_document_ids] Found document in {chroma_collections.insights_collection}: {doc_id}")
                            for doc in insights_docs:
                                doc['collection'] = chroma_collections.insights_collection
                                all_docs.append(doc)
                        
                        # Use the improved get_related_chunks function to find all related chunks
                        #logger.info(f"[GongAgent._retrieve_by_document_ids] Looking for chunks related to document ID: {doc_id}")
                        # print(f"\n==== CHUNK LOOKUP DEBUGGING (by document ID) ====")
                        # print(f"Looking for chunks for document ID: {doc_id}")
                        # print(f"Using chunks collection: {chroma_collections.chunks_collection}")
                        
                        chunks = get_related_chunks(
                            chroma_client=chroma_db.client,
                            doc_id=doc_id,
                            chunks_collection_name=chroma_collections.chunks_collection,
                            debug=True  # Enable debug logging
                        )
                        
                        if chunks:
                            logger.info(f"[GongAgent._retrieve_by_document_ids] Found {len(chunks)} chunks for document ID: {doc_id}")
                            for chunk in chunks:
                                # Convert to the format expected by the rest of the code
                                chunk_doc = {
                                    'document_id': chunk['id'],
                                    'document_type': chunk['metadata'].get('document_type', 'gong_chunk'),  # Use the document_type from metadata
                                    'content': chunk['content'],
                                    'metadata': chunk['metadata'],
                                    'collection': chroma_collections.chunks_collection,
                                    'parent_doc_id': doc_id
                                }
                                all_docs.append(chunk_doc)
                        else:
                            logger.info(f"[GongAgent._retrieve_by_document_ids] No chunks found for document ID: {doc_id}")
                except Exception as e:
                    logger.warning(f"[GongAgent._retrieve_by_document_ids] Error retrieving document {doc_id}: {e}")
            
            # Create insight packages for documents retrieved by ID
            # Group documents by parent/insight relationship
            insights_by_id = {}
            chunks_by_parent = {}

            for doc in all_docs:
                doc_type = doc.get('document_type', '').lower()
                collection = doc.get('collection', '')
                metadata = doc.get('metadata', {})

                # Check if this is an insight
                is_insight = (
                    'insight' in doc_type or
                    collection == 'gong_insights' or
                    doc_type == 'gong_call_insights' or
                    metadata.get('document_type', '').lower() == 'gong_call_insights'
                )

                if is_insight:
                    doc_id = doc.get('document_id', '')
                    if doc_id:
                        insights_by_id[doc_id] = doc
                else:
                    # This is likely a chunk
                    parent_id = metadata.get('parent_document_id',
                               metadata.get('consistent_doc_id',
                               doc.get('parent_document_id',
                               metadata.get('parent_doc_id',
                               doc.get('parent_doc_id', '')))))

                    if not parent_id and '_chunk' in doc.get('document_id', ''):
                        parent_id = doc.get('document_id', '').split('_chunk')[0]

                    if parent_id:
                        if parent_id not in chunks_by_parent:
                            chunks_by_parent[parent_id] = []
                        chunks_by_parent[parent_id].append(doc)

            # Create packages from the grouped documents
            insight_packages = []
            for insight_id, insight in insights_by_id.items():
                chunks = chunks_by_parent.get(insight_id, [])

                # Also check for chunks with normalized ID
                if insight_id.startswith('gong_'):
                    normalized_id = insight_id.replace('gong_', '', 1)
                    if normalized_id in chunks_by_parent:
                        chunks.extend(chunks_by_parent[normalized_id])
                elif not insight_id.startswith('gong_'):
                    normalized_id = f"gong_{insight_id}"
                    if normalized_id in chunks_by_parent:
                        chunks.extend(chunks_by_parent[normalized_id])

                # Sort chunks by chunk_index if available
                try:
                    sorted_chunks = sorted(
                        chunks,
                        key=lambda x: int(
                            x.get('chunk_index',
                                x.get('metadata', {}).get('chunk_index',
                                    x.get('chunk_num',
                                        x.get('metadata', {}).get('chunk_num', 0)
                                    )
                                )
                            ) if str(x.get('chunk_index',
                                    x.get('metadata', {}).get('chunk_index',
                                        x.get('chunk_num',
                                            x.get('metadata', {}).get('chunk_num', 0)
                                        )
                                    )
                                )).isdigit() else 0
                        )
                    )
                except Exception:
                    sorted_chunks = chunks

                insight_packages.append({
                    'insight': insight,
                    'chunks': sorted_chunks,
                    'aggregate_score': insight.get('relevance_score', 1.0),  # Use 1.0 for direct ID retrieval
                    'num_chunks': len(sorted_chunks),
                    'avg_chunk_score': 1.0,
                    'max_chunk_score': 1.0
                })

            # Store packages in state if state is provided
            if state is not None:
                state.insight_packages = insight_packages
                logger.info(f"[GongAgent._retrieve_by_document_ids] Created {len(insight_packages)} insight packages from ID retrieval")

            # Process and structure the documents
            processed_docs = self._process_retrieved_documents(all_docs)
            logger.info(f"[GongAgent._retrieve_by_document_ids] Retrieved {len(processed_docs)} documents by ID")
            
            return processed_docs
            
        except Exception as e:
            logger.error(f"[GongAgent._retrieve_by_document_ids] Error: {e}")
            return []
    
    def _process_retrieved_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process retrieved documents to standardize format and extract metadata."""
        # Count document types before processing
        doc_types_before = {}
        for doc in documents:
            doc_type = doc.get('document_type', 'unknown').lower()
            doc_types_before[doc_type] = doc_types_before.get(doc_type, 0) + 1

        logger.info(f"[DEBUG] Before processing: Document types: {doc_types_before}")

        # Use the common function with our source_type
        processed_docs = process_retrieved_documents(documents, self.source_type)
        
        # Count document types after processing
        doc_types_after = {}
        for doc in processed_docs:
            doc_type = doc.get('document_type', 'unknown').lower()
            doc_types_after[doc_type] = doc_types_after.get(doc_type, 0) + 1

        logger.info(f"[DEBUG] After processing: Document types: {doc_types_after}")

        # Add Gong-specific processing
        for doc in processed_docs:
            doc_type = doc.get('document_type', '')
            content = doc.get('content', '')
            
            # For insights, extract structured sections
            if 'insight' in doc_type.lower() or doc.get('collection', '') == 'gong_insights':
                if isinstance(content, str) and content:
                    doc['structured_content'] = extract_structured_sections(content)
                    
                # Process all relevant metadata fields
                metadata = doc.get('metadata', {})

                # Standard list fields
                list_fields = [
                    'topics', 'keywords', 'entities', 'categories',
                    'action_items', 'buyer_roles', 'competitors', 'decision_criteria',
                    'pain_points', 'product_features', 'objections', 'use_cases'
                ]

                for field in list_fields:
                    doc[field] = parse_json_list_field(metadata.get(field, '[]'))
                
                # Add title and date fields consistently
                doc['title'] = metadata.get('title', '')
                doc['gong_title'] = metadata.get('title', '')
                doc['date'] = metadata.get('date', '')
                doc['gong_date'] = metadata.get('date', '')
                doc['gong_call_id'] = metadata.get('gong_call_id', '')

                # Add URL if available
                if 'url' in metadata:
                    doc['url'] = metadata.get('url', '')
        
        return processed_docs
    
    async def generate_answer(self, state: AgentState) -> str:
        """
        Generate an answer based on retrieved Gong documents.
        
        Args:
            state: The current agent state with retrieved documents
            
        Returns:
            Generated answer text
        """
        try:
            logger.info(f"[GongAgent.generate_answer] Generating answer from {len(state.retrieved_documents)} documents")
            
            if not state.retrieved_documents:
                # Check if this is due to time filtering
                if hasattr(state, 'additional_context') and state.additional_context:
                    if state.additional_context.get('empty_time_filtered_results', False):
                        time_expression = state.additional_context.get('time_range', {}).get('expression', 'the specified time period')
                        return f"I couldn't find any Gong call data for {time_expression}. This may be because no calls were recorded during this time frame, or the data hasn't been indexed yet. Please try a different time range or a broader query."
                
                return "I couldn't find any relevant Gong call data to answer your question. Please provide more details or try a different question."
            
            # PHASE 5: Classify question as factual vs analytical
            question_lower = state.question.lower()
            is_factual = bool(re.match(r"^(who|when|what|which|how many|did|was|were|are)\b", question_lower))

            logger.info(f"[GongAgent.generate_answer] Question classified as {'FACTUAL' if is_factual else 'ANALYTICAL'}")

            # Create a map of call ID to title and date from all retrieved documents
            call_info_map = {}
            for doc in state.retrieved_documents:
                metadata = doc.get('metadata', {})
                # Try both title fields
                title = metadata.get('title', metadata.get('gong_title', ''))
                # Try both date fields
                date = metadata.get('date', metadata.get('gong_date', ''))

                # Determine the base call ID from either parent_doc_id (chunks) or document_id (insights)
                base_id = metadata.get('parent_doc_id') or metadata.get('document_id')
                if not base_id or not title:
                    continue

                # Normalize the ID by removing any "gong_" prefix
                normalized_id = base_id.replace('gong_', '')
                
                # Store info if not already present, giving priority to existing entries (likely from insights)
                if normalized_id not in call_info_map:
                    call_info_map[normalized_id] = {'title': title, 'date': date}

            # Check if we have additional context with a refined query flag
            is_refined_query = False
            if hasattr(state, 'additional_context') and state.additional_context:
                is_refined_query = state.additional_context.get('refined_query', False)
            
            # PHASE 4: Use stored insight packages instead of reconstructing them
            if hasattr(state, 'insight_packages') and state.insight_packages:
                logger.info(f"[GongAgent.generate_answer] Using {len(state.insight_packages)} pre-computed insight packages from state")
                # Use the packages directly from state - they're already sorted and trimmed
                top_packages = state.insight_packages[:30]  # Limit to top 30 for context
                logger.info(f"[GongAgent.generate_answer] Using top {len(top_packages)} packages for context generation")
            else:
                # Fallback: reconstruct packages if not available (for backward compatibility)
                logger.warning(f"[GongAgent.generate_answer] No pre-computed packages found, falling back to reconstruction")
                
                # Organize documents by type and relationships
                insights_map = {}  # Map of insight_id -> insight
                chunks_by_parent = {}  # Map of parent_id -> list of chunks
                
                # First pass: categorize documents
                for doc in state.retrieved_documents:
                    doc_type = doc.get('document_type', '').lower()
                    collection = doc.get('collection', '')
                    metadata = doc.get('metadata', {})
                    
                    # Enhanced insight detection
                    is_insight = (
                        'insight' in doc_type or 
                        collection == 'gong_insights' or 
                        doc_type == 'gong_call_insights' or
                        metadata.get('document_type', '').lower() == 'gong_call_insights'
                    )
                    
                    if is_insight:
                        doc_id = doc.get('document_id', '')
                        if doc_id:
                            insights_map[doc_id] = doc
                            # Also map without 'gong_' prefix for better matching
                            if doc_id.startswith('gong_'):
                                normalized_id = doc_id.replace('gong_', '', 1)
                                insights_map[normalized_id] = doc
                    
                    # Enhanced chunk detection
                    elif ('chunk' in doc_type or 
                          'vectordb' in doc_type or  # This will catch 'gong_vectordb'
                          collection == 'chunks' or  # This will catch chunks collection
                          doc_type == 'gong_vectordb' or  # Explicit check for gong_vectordb
                          metadata.get('document_type', '').lower() == 'gong_vectordb'):  # Check metadata too
                        
                        # Try all possible parent ID fields
                        parent_id = metadata.get('parent_document_id',
                                   metadata.get('consistent_doc_id',
                                   doc.get('parent_document_id',
                                   metadata.get('parent_doc_id',
                                   doc.get('parent_doc_id', '')))))
                        
                        # Extract from document ID pattern as last resort
                        if not parent_id and '_chunk' in doc.get('document_id', ''):
                            parent_id = doc.get('document_id', '').split('_chunk')[0]

                        if parent_id:
                            if parent_id not in chunks_by_parent:
                                chunks_by_parent[parent_id] = []
                            chunks_by_parent[parent_id].append(doc)
                
                # Create insight packages (insight + its chunks)
                insight_packages = []
                for insight_id, insight in insights_map.items():
                    # Get chunks directly associated with this insight ID
                    chunks = chunks_by_parent.get(insight_id, [])

                    # Also check for chunks with normalized ID
                    if insight_id.startswith('gong_'):
                        normalized_id = insight_id.replace('gong_', '', 1)
                        if normalized_id in chunks_by_parent:
                            chunks.extend(chunks_by_parent[normalized_id])
                    elif not insight_id.startswith('gong_'):
                        normalized_id = f"gong_{insight_id}"
                        if normalized_id in chunks_by_parent:
                            chunks.extend(chunks_by_parent[normalized_id])

                    # Sort chunks by chunk_index if available
                    try:
                        sorted_chunks = sorted(
                            chunks, 
                            key=lambda x: int(
                                x.get('chunk_index',
                                    x.get('metadata', {}).get('chunk_index',
                                        x.get('chunk_num',
                                            x.get('metadata', {}).get('chunk_num', 0)
                                        )
                                    )
                                ) if str(x.get('chunk_index',
                                        x.get('metadata', {}).get('chunk_index',
                                            x.get('chunk_num',
                                                x.get('metadata', {}).get('chunk_num', 0)
                                            )
                                        )
                                    )).isdigit() else 0
                            )
                        )
                    except Exception:
                        sorted_chunks = chunks

                    # Calculate relevance score
                    insight_score = insight.get('relevance_score', 0)

                    # Calculate chunk scores
                    chunk_scores = [chunk.get('relevance_score', 0) for chunk in sorted_chunks]
                    avg_chunk_score = sum(chunk_scores) / len(chunk_scores) if chunk_scores else 0
                    max_chunk_score = max(chunk_scores) if chunk_scores else 0

                    # Calculate aggregate score with emphasis on insight score
                    aggregate_score = (insight_score * 0.6) + (avg_chunk_score * 0.3) + (max_chunk_score * 0.1)

                    insight_packages.append({
                        'insight': insight,
                        'chunks': sorted_chunks,
                        'score': aggregate_score,
                        'insight_score': insight_score,
                        'avg_chunk_score': avg_chunk_score,
                        'max_chunk_score': max_chunk_score
                    })
                
                # Sort packages by score and take top packages
                sorted_packages = sorted(insight_packages, key=lambda p: p.get('score', 0), reverse=True)
                
                # Limit to top packages for context
                max_packages = min(15, len(sorted_packages))  # Limit to top 15 packages
                top_packages = sorted_packages[:max_packages]
                
                logger.info(f"[GongAgent.generate_answer] Reconstructed {len(top_packages)} packages from {len(sorted_packages)} total")

            # Build structured context from top packages
            context_parts = []

            # Format each package using our new formatting function
            for package in top_packages:
                insight = package['insight']
                chunks = package['chunks']
                
                # Format the package using the new utility function - content exactly as-is
                formatted_package = format_gong_package(insight, chunks)
                context_parts.append(formatted_package)
                
                # Add separator between packages
                context_parts.append("")
            
            # Combine all context parts
            context = "\n".join(context_parts)
            
            # Use the standard prompt with MEDDIC instructions for all questions
            system_prompt = build_gong_agent_system_prompt()

            # Build the human prompt with question type classification
            additional_context = getattr(state, 'additional_context', {}) or {}
            # Add factual question classification to additional context
            additional_context['is_factual_question'] = is_factual

            human_prompt = build_human_prompt(
                question=state.question, 
                context=context,
                current_query=getattr(state, 'current_query', ''),
                is_refined_query=is_refined_query,
                additional_context=additional_context
            )
            
            # Get the appropriate LLM for answer generation
            llm = get_answer_generation_llm()
            model_name = getattr(llm, 'model_name', str(llm))
            logger.info(f"[GongAgent.generate_answer] Using model for answer generation: {model_name}")

            # Generate the answer
            logger.info(f"[GongAgent.generate_answer] Generating answer with context length: {len(context)}")

            # Print the filled-in prompts for debugging
            # print("\n==== SYSTEM PROMPT ====")
            # print(system_prompt)
            print("\n==== HUMAN PROMPT ====")
            print(human_prompt)
            print("\n=======================")

            # Call the LLM
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])
            
            # Ensure we return a string (response.content could be a string or an object)
            if hasattr(response, 'content'):
                if isinstance(response.content, str):
                    return response.content
                else:
                    # Convert to string if not a string
                    return str(response.content)
            else:
                # Fallback if content not available
                return f"I analyzed {len(state.retrieved_documents)} documents but couldn't generate a proper response."
        
        except Exception as e:
            logger.error(f"[GongAgent.generate_answer] Error generating answer: {e}")
            return f"I encountered an error while generating the answer: {str(e)}. Please try again or contact support if the issue persists."