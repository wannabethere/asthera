import json
from typing import Any, Dict, List, Optional, cast
import asyncio
import logging
from datetime import datetime, timedelta
from pydantic import Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from tqdm import tqdm
from chromadb import Where
import re

from app.agentic.base.base_agent import BaseAgent, AgentState
from app.agentic.utils.extraction_retriever import EnhancedExtractionRetriever
from app.config.agent_config import chroma_collections
from app.agentic.utils.document_processor import extract_insights_from_metadata
from app.agentic.utils.prompt_builder import build_salesforce_agent_system_prompt, build_human_prompt
from app.utils.llm_factory import get_default_llm, get_answer_generation_llm
from app.utils.logging_config import setup_agent_logger
from app.agentic.utils.query_parser import extract_potential_company_names, extract_potential_ids

# Set up logging using the centralized configuration
logger = setup_agent_logger("SalesforceAgent")

class SalesforceAgentState(AgentState):
    """Extended state for Salesforce-specific processing."""
    opportunity_ids: List[str] = Field(default_factory=list)
    account_ids: List[str] = Field(default_factory=list)
    salesforce_topics: List[str] = Field(default_factory=list)
    source_type: str = "salesforce"  # Always set to salesforce for this agent

class SalesforceAgent(BaseAgent):
    """
    Agent specialized for retrieving and processing Salesforce data.
    Focuses on opportunities, accounts, pipeline, and sales metrics.
    """

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """Initialize the Salesforce agent."""
        if llm is None:
            llm = get_default_llm(task_name="salesforce_agent_initialization")
            logger.info(f"[SalesforceAgent.__init__] Initialized with default LLM model: {llm.model_name}")
        else:
            logger.info(f"[SalesforceAgent.__init__] Initialized with provided LLM model: {llm.model_name}")
        super().__init__(llm=llm, source_type="salesforce")
        
        # Salesforce-specific configurations
        self.default_topics = [
            "opportunity", "deal", "pipeline", "forecast", 
            "revenue", "account", "sales", "stage"
        ]
        self.default_keywords = [
            "close date", "amount", "stage", "probability", 
            "win", "lost", "qualified", "negotiation"
        ]
        
        # Initialize the enhanced retriever with the collection from global config
        try:
            self.enhanced_retriever = EnhancedExtractionRetriever(
                collection_name=chroma_collections.insights_collection, 
                use_remote_chroma=True
            )
            logger.info(f"Enhanced extraction retriever initialized with collection: {chroma_collections.insights_collection}")
        except Exception as e:
            logger.error(f"Failed to initialize enhanced retriever: {e}")
            self.enhanced_retriever = None
    
    async def retrieve_documents(self, state: AgentState) -> List[Dict[str, Any]]:
        """
        Retrieve Salesforce documents based on the query.
        Implements a multi-step filtering process: first, it will fetch up to 500 insights and semantically prune them to the top 250; 
        next, for each of these insights, it will fetch all associated chunks and calculate an aggregate relevance score; 
        finally, it will sort the insights by this new score, select the top 125, and return a flattened list of documents 
        containing only these top insights and their chunks.
        
        Args:
            state: The current agent state
            
        Returns:
            List of retrieved Salesforce documents
        """
        try:
            logger.info(f"[SalesforceAgent.retrieve_documents] Starting document retrieval for query: '{state.question}'")
            
            # Check if we have the enhanced retriever
            if self.enhanced_retriever is None:
                logger.warning("Enhanced retriever not available, falling back to standard retrieval")
                return await self._fallback_retrieve_documents(state)
            
            # Extract conversation ID from state if available
            conversation_id = state.additional_context.get("conversation_id", None)
            if not conversation_id and hasattr(state, "chat_history") and state.chat_history:
                # Try to extract from chat history
                first_msg = state.chat_history[0] if state.chat_history else {}
                conversation_id = first_msg.get("thread_id", None)
            
            # Ensure we have Salesforce-specific topics
            topics = state.topics or self.default_topics
            
            # IMPROVED QUERY ENHANCEMENT:
            # 1. Start with the question (which might be a specialized query)
            query_parts = [state.question]

            # 2. Extract key terms from the question to avoid redundancy
            question_terms = set(state.question.lower().split())

            # 3. Add Salesforce-specific terms only if they're not already in the question
            sfdc_terms = ["opportunity", "deal", "pipeline", "forecast", "revenue", "account", "salesforce"]
            for term in sfdc_terms:
                if term not in question_terms:
                    query_parts.append(term)

            # 4. Add topics that aren't already in the question
            for topic in topics:
                if topic.lower() not in question_terms and topic not in query_parts:
                    query_parts.append(topic)

            # 5. Join unique terms and create enhanced query
            enhanced_query = " ".join(query_parts)
            
            logger.info(f"[SalesforceAgent.retrieve_documents] Built enhanced query: '{enhanced_query}'")
            
            # 1. Handle specific document IDs if provided
            if state.document_ids:
                logger.info(f"[SalesforceAgent.retrieve_documents] Using specific document IDs: {state.document_ids}")
                return await self._retrieve_by_document_ids(state.document_ids)
                
            # Import required utilities here to avoid circular imports
            from app.utils.chromadb import ChromaDB
            # Initialize with WARNING log level to reduce noise
            chroma_db = ChromaDB(log_level="WARNING")
            
            # STEP 1: Broad query to get up to 500 insights
            initial_insights = []
            
            try:
                logger.info(f"[SalesforceAgent.retrieve_documents] Performing broad query to get up to 500 insights")
                
                # Extract potential company names, opportunity IDs, and account IDs from the query
                company_names = extract_potential_company_names(state.question)
                opportunity_ids = extract_potential_ids(state.question, "opportunity")
                account_ids = extract_potential_ids(state.question, "account")
                
                logger.info(f"[SalesforceAgent.retrieve_documents] Extracted entities - Companies: {company_names}, Opportunity IDs: {opportunity_ids}, Account IDs: {account_ids}")
                
                # First, try direct ID-based searches if IDs are found in the query (highest precision)
                if opportunity_ids:
                    for opp_id in opportunity_ids:
                        try:
                            # Try exact opportunity ID match first
                            direct_opp_results = chroma_db.query_collection_with_relevance_scores(
                                collection_name=chroma_collections.insights_collection,
                                query_texts=[""],  # Empty query for ID-based search
                                n_results=100,  # Use high fixed value like GongAgent does
                                where={"metadata.sfdc_opportunity_id": {"$eq": opp_id}}
                            )
                            
                            if direct_opp_results:
                                logger.info(f"[SalesforceAgent.retrieve_documents] Found {len(direct_opp_results)} insights with exact opportunity ID: {opp_id}")
                                initial_insights.extend(direct_opp_results)
                        except Exception as id_err:
                            logger.warning(f"[SalesforceAgent.retrieve_documents] Error searching by opportunity ID {opp_id}: {id_err}")
                
                if account_ids and not initial_insights:  # Only check accounts if we didn't find opportunities
                    for acc_id in account_ids:
                        try:
                            # Try exact account ID match
                            direct_acc_results = chroma_db.query_collection_with_relevance_scores(
                                collection_name=chroma_collections.insights_collection,
                                query_texts=[""],  # Empty query for ID-based search
                                n_results=100,  # Use high fixed value like GongAgent does
                                where={"metadata.sfdc_account_id": {"$eq": acc_id}}
                            )
                            
                            if direct_acc_results:
                                logger.info(f"[SalesforceAgent.retrieve_documents] Found {len(direct_acc_results)} insights with exact account ID: {acc_id}")
                                initial_insights.extend(direct_acc_results)
                        except Exception as id_err:
                            logger.warning(f"[SalesforceAgent.retrieve_documents] Error searching by account ID {acc_id}: {id_err}")
                
                # Second, if we have company names, try name-specific searches
                if company_names and len(initial_insights) < 50:
                    for company_name in company_names:
                        if len(company_name) < 3:
                            continue
                            
                        # Try multiple fields that might contain the company name
                        search_fields = [
                            "metadata.sfdc_name",  # Opportunity name
                            "metadata.sfdc_account_name",  # Account name
                            "document"  # Full document text
                        ]
                        
                        for field in search_fields:
                            try:
                                # First try exact match on specific fields
                                exact_field_query = {field: {"$eq": company_name}}
                                # Cast to Where type for ChromaDB
                                company_exact_results = chroma_db.query_collection_with_relevance_scores(
                                    collection_name=chroma_collections.insights_collection,
                                    query_texts=[""],  # Empty query for field-based search
                                    n_results=100,  # Use high fixed value like GongAgent does
                                    where=cast(Where, {"$and": [{"source_type": {"$eq": "salesforce"}}, exact_field_query]})
                                )
                                
                                if company_exact_results:
                                    logger.info(f"[SalesforceAgent.retrieve_documents] Found {len(company_exact_results)} insights with exact match on {field}: '{company_name}'")
                                    initial_insights.extend(company_exact_results)
                                    break  # Stop after finding exact matches
                            except Exception as field_err:
                                logger.warning(f"[SalesforceAgent.retrieve_documents] Error searching exact match on {field}: {field_err}")
                        
                        # If we still have few results, try semantic search with the company name
                        if len(initial_insights) < 50:
                            try:
                                # Create multiple search variations to overcome the 15-result limit
                                search_variations = [
                                    f"{company_name} opportunity salesforce",
                                    f"salesforce {company_name}",
                                    f"{company_name} deal pipeline",
                                    f"{company_name} forecast account"
                                ]
                                
                                # Log that we're using multiple search variations
                                logger.info(f"[SalesforceAgent.retrieve_documents] Using {len(search_variations)} search variations to overcome 15-result limit")
                                
                                # Run multiple searches with different variations
                                for variation in search_variations:
                                    company_results = chroma_db.query_collection_with_relevance_scores(
                                        collection_name=chroma_collections.insights_collection,
                                        query_texts=[variation],
                                        n_results=500,  # Use high fixed value like GongAgent does
                                        where={"source_type": {"$eq": "salesforce"}}
                                    )
                                    
                                    if company_results:
                                        logger.info(f"[SalesforceAgent.retrieve_documents] Found {len(company_results)} insights with variation: '{variation}'")
                                        initial_insights.extend(company_results)
                            except Exception as company_err:
                                logger.warning(f"[SalesforceAgent.retrieve_documents] Error in semantic search for company '{company_name}': {company_err}")
                
                # Third, if we still have too few results, use multiple standard query variations
                if len(initial_insights) < 100:
                    try:
                        # Create different query variations to overcome the 15-result limit
                        query_variations = [
                            enhanced_query,
                            f"salesforce {state.question}",
                            f"opportunity {state.question}",
                            f"{state.question} account pipeline"
                        ]
                        
                        logger.info(f"[SalesforceAgent.retrieve_documents] Using {len(query_variations)} standard query variations")
                        
                        # Run multiple searches with different variations
                        for i, variation in enumerate(query_variations):
                            standard_results = chroma_db.query_collection_with_relevance_scores(
                                collection_name=chroma_collections.insights_collection,
                                query_texts=[variation],
                                n_results=500,  # Use high fixed value like GongAgent does
                                where={"source_type": {"$eq": "salesforce"}}
                            )
                            
                            logger.info(f"[SalesforceAgent.retrieve_documents] Found {len(standard_results)} insights with standard query variation {i+1}")
                            
                            # Combine with existing results, avoiding duplicates
                            seen_ids = {doc.get('document_id', doc.get('id', '')) for doc in initial_insights if isinstance(doc, dict) and (doc.get('document_id') or doc.get('id'))}
                            for doc in standard_results:
                                if not isinstance(doc, dict):
                                    continue
                                doc_id = doc.get('document_id', doc.get('id', ''))
                                if doc_id and doc_id not in seen_ids:
                                    initial_insights.append(doc)
                                    seen_ids.add(doc_id)
                    except Exception as query_err:
                        logger.warning(f"[SalesforceAgent.retrieve_documents] Error in standard query variations: {query_err}")
                
                # Fourth, if still no results, try document_type as fallback
                if not initial_insights:
                    logger.info(f"[SalesforceAgent.retrieve_documents] No results from previous methods, trying document_type search")
                    
                    fallback_results = chroma_db.query_collection_with_relevance_scores(
                        collection_name=chroma_collections.insights_collection,
                        query_texts=[enhanced_query],
                        n_results=500,  # Use high fixed value like GongAgent does
                        where={"document_type": {"$eq": "sfdc_opportunity_insights"}}
                    )
                    
                    if fallback_results:
                        logger.info(f"[SalesforceAgent.retrieve_documents] Found {len(fallback_results)} insights with document_type fallback")
                        initial_insights.extend(fallback_results)
                
                # Remove duplicates based on document_id
                if initial_insights:
                    unique_docs = {}
                    for doc in initial_insights:
                        if not isinstance(doc, dict):
                            continue
                        doc_id = None
                        if 'document_id' in doc:
                            doc_id = doc['document_id']
                        elif 'id' in doc:
                            doc_id = doc['id']
                        
                        if doc_id:
                            unique_docs[doc_id] = doc
                    
                    initial_insights = list(unique_docs.values())
                    logger.info(f"[SalesforceAgent.retrieve_documents] After deduplication: {len(initial_insights)} unique insights")
                
            except Exception as insights_err:
                logger.warning(f"[SalesforceAgent.retrieve_documents] Error searching {chroma_collections.insights_collection}: {insights_err}")
            
            # If no insights found at all, try a last resort search without filters
            if not initial_insights:
                try:
                    logger.info(f"[SalesforceAgent.retrieve_documents] No insights found, trying last resort search")
                    
                    last_resort_query = enhanced_query
                    # Add company names to the query if available
                    if company_names:
                        last_resort_query = f"{' '.join(company_names)} {last_resort_query}"
                    
                    last_resort_results = chroma_db.query_collection(
                        collection_name=chroma_collections.insights_collection,
                        query_texts=[last_resort_query],
                        n_results=100
                    )
                    
                    if last_resort_results:
                        logger.info(f"[SalesforceAgent.retrieve_documents] Found {len(last_resort_results)} insights with last resort search")
                        # Convert to standard format with relevance scores
                        for i, doc in enumerate(last_resort_results):
                            # Add decreasing relevance scores as a dict value, not trying to modify a string
                            if isinstance(doc, dict):
                                doc['relevance_score'] = 1.0 - (i * 0.01)
                        initial_insights = last_resort_results
                except Exception as last_err:
                    logger.warning(f"[SalesforceAgent.retrieve_documents] Error in last resort search: {last_err}")
            
            # STEP 2: Winnow down to top 250 insights by relevance score - Log before and after
            logger.info(f"[SalesforceAgent.retrieve_documents] Before winnowing: {len(initial_insights)} insights")
            
            # Check if we have dict objects with relevance_score
            valid_insights = [ins for ins in initial_insights if isinstance(ins, dict) and 'relevance_score' in ins]
            logger.info(f"[SalesforceAgent.retrieve_documents] Valid insights with relevance_score: {len(valid_insights)}")
            
            if len(valid_insights) > 0:
                top_250_insights = sorted(
                    valid_insights, 
                    key=lambda x: x.get('relevance_score', 0), 
                    reverse=True
                )[:250]
                logger.info(f"[SalesforceAgent.retrieve_documents] After winnowing: {len(top_250_insights)} insights")
            else:
                # If no valid insights with relevance_score, just use what we have
                if isinstance(initial_insights, list):
                    top_250_insights = initial_insights[:250]
                else:
                    # Handle case where initial_insights might not be a list
                    top_250_insights = []
                logger.info(f"[SalesforceAgent.retrieve_documents] Using {len(top_250_insights)} insights without sorting")
            
            # STEP 3: Create a combined query from the metadata of the top insights
            insight_keywords = set()
            # Frequency counter for terms to identify the most common ones
            term_frequency = {}
            
            # First pass: count term frequencies across insights
            for insight in top_250_insights:
                metadata = insight.get('metadata', {})
                insight_terms = set()  # Collect unique terms per insight first
                
                # Extract opportunity and account names
                opportunity_name = metadata.get('sfdc_name', '')
                account_name = metadata.get('sfdc_account_name', '')
                
                if opportunity_name:
                    insight_terms.add(opportunity_name.lower())
                if account_name:
                    insight_terms.add(account_name.lower())
                
                # Extract other key metadata fields
                for field in ['sfdc_stage_name', 'sfdc_lead_source', 'sfdc_type']:
                    if field in metadata and metadata[field]:
                        insight_terms.add(metadata[field].lower())
                
                # Update global frequency counter with this insight's terms
                for term in insight_terms:
                    if term and len(term) > 2:
                        term_frequency[term] = term_frequency.get(term, 0) + 1
            
            # Second pass: select only high-frequency terms and those that appear in the original query
            # This focuses on terms that are both common across insights and relevant to the question
            query_terms = enhanced_query.lower().split()
            selected_terms = []
            
            # Add terms that appear in at least 5% of insights (high frequency)
            min_frequency = max(2, len(top_250_insights) * 0.05)  # At least 2 occurrences or 5% of insights
            common_terms = [term for term, freq in term_frequency.items() if freq >= min_frequency]
            selected_terms.extend(common_terms[:100])  # Limit to top 100 common terms
            
            # Add terms that appear in both the original query and metadata (direct relevance)
            query_relevant_terms = [term for term in term_frequency if any(query_term in term or term in query_term for query_term in query_terms)]
            selected_terms.extend(query_relevant_terms[:50])  # Limit to top 50 query-relevant terms
            
            # Ensure we don't have duplicates
            selected_terms = list(set(selected_terms))
            
            # Final safety cap to prevent massive queries (max 150 terms)
            if len(selected_terms) > 150:
                selected_terms = selected_terms[:150]
            
            combined_keyword_str = " ".join(selected_terms)
            combined_enhanced_query = f"{enhanced_query} {combined_keyword_str}"
            logger.info(f"[SalesforceAgent.retrieve_documents] Created combined query with {len(selected_terms)} selected high-value terms from top insights.")
            
            # STEP 4: Create insight packages and calculate aggregate scores
            insight_packages = []
            for insight in tqdm(top_250_insights, desc="Processing insights, fetching chunks, and scoring"):
                doc_id = insight.get('document_id', insight.get('id', ''))
                if not doc_id:
                    continue

                metadata = insight.get('metadata', {})
                opportunity_id = metadata.get('sfdc_opportunity_id', '')
                if not opportunity_id:
                    opportunity_id = doc_id
                
                # Get all chunks for this opportunity
                all_chunks_for_insight = []
                try:
                    # Try to get chunks by opportunity_id first
                    if opportunity_id:
                        # First try metadata.sfdc_opportunity_id
                        all_chunks_for_insight = chroma_db.query_collection_with_relevance_scores(
                            collection_name=chroma_collections.chunks_collection,
                            query_texts=[""],
                            n_results=100,  # Use high fixed value like GongAgent does
                            where={"metadata.sfdc_opportunity_id": {"$eq": opportunity_id}}
                        )
                        
                        # If no results, try direct opportunity_id field
                        if not all_chunks_for_insight:
                            all_chunks_for_insight = chroma_db.query_collection_with_relevance_scores(
                                collection_name=chroma_collections.chunks_collection,
                                query_texts=[""],
                                n_results=100,  # Use high fixed value like GongAgent does
                                where={"opportunity_id": {"$eq": opportunity_id}}
                            )
                    
                    # If still no chunks found, try using document_id as parent_doc_id
                    if not all_chunks_for_insight and doc_id:
                        # Try standard parent_doc_id first
                        all_chunks_for_insight = chroma_db.query_collection_with_relevance_scores(
                            collection_name=chroma_collections.chunks_collection,
                            query_texts=[""],
                            n_results=100,  # Use high fixed value like GongAgent does
                            where={"parent_doc_id": {"$eq": doc_id}}
                        )
                        
                        # If still no results, try with sfdc_ prefix
                        if not all_chunks_for_insight:
                            sfdc_parent_id = f"sfdc_{doc_id}" if not doc_id.startswith("sfdc_") else doc_id
                            all_chunks_for_insight = chroma_db.query_collection_with_relevance_scores(
                                collection_name=chroma_collections.chunks_collection,
                                query_texts=[""],
                                n_results=100,  # Use high fixed value like GongAgent does
                                where={"parent_doc_id": {"$eq": sfdc_parent_id}}
                            )
                    
                    logger.info(f"[SalesforceAgent.retrieve_documents] Found {len(all_chunks_for_insight)} chunks for opportunity {opportunity_id}")
                    
                except Exception as chunk_err:
                    logger.warning(f"[SalesforceAgent.retrieve_documents] Error fetching chunks for {opportunity_id}: {chunk_err}")
                
                # Get the top chunk's relevance score using the combined enhanced query
                top_chunk_score = 0
                if opportunity_id:
                    try:
                        # Try metadata.sfdc_opportunity_id first
                        top_chunk_list = chroma_db.query_collection_with_relevance_scores(
                            collection_name=chroma_collections.chunks_collection,
                            query_texts=[combined_enhanced_query],
                            n_results=1,
                            where={"metadata.sfdc_opportunity_id": {"$eq": opportunity_id}}
                        )
                        
                        # If no results, try direct opportunity_id field
                        if not top_chunk_list:
                            top_chunk_list = chroma_db.query_collection_with_relevance_scores(
                                collection_name=chroma_collections.chunks_collection,
                                query_texts=[combined_enhanced_query],
                                n_results=1,
                                where={"opportunity_id": {"$eq": opportunity_id}}
                            )
                        
                        # If still no results, try using document_id as parent_doc_id
                        if not top_chunk_list and doc_id:
                            top_chunk_list = chroma_db.query_collection_with_relevance_scores(
                                collection_name=chroma_collections.chunks_collection,
                                query_texts=[combined_enhanced_query],
                                n_results=1,
                                where={"parent_doc_id": {"$eq": doc_id}}
                            )
                        
                        if top_chunk_list:
                            top_chunk_score = top_chunk_list[0].get('relevance_score', 0)
                    except Exception as score_err:
                        logger.warning(f"[SalesforceAgent.retrieve_documents] Error getting top chunk score: {score_err}")
                
                # Calculate an aggregate score - weight insights more than chunks
                insight_score = insight.get('relevance_score', 0)
                chunk_count_bonus = min(0.1, len(all_chunks_for_insight) * 0.01)  # Small bonus for having more chunks
                aggregate_score = (insight_score * 0.6) + (top_chunk_score * 0.3) + chunk_count_bonus

                # Store the complete package
                insight_packages.append({
                    'insight': insight,
                    'chunks': all_chunks_for_insight,
                    'aggregate_score': aggregate_score,
                    'chunk_count': len(all_chunks_for_insight)
                })
                
            # STEP 5: Sort packages by aggregate score and winnow down to top 125
            sorted_packages = sorted(insight_packages, key=lambda p: p['aggregate_score'], reverse=True)
            # Ensure we're getting more than just 15 packages
            top_packages = sorted_packages[:125]
            
            # Log detailed information about the top packages
            logger.info(f"[SalesforceAgent.retrieve_documents] Winnowed down to top {len(top_packages)} insight packages based on aggregate score.")
            for i, pkg in enumerate(top_packages[:5]):  # Log first 5 packages for debugging
                insight = pkg['insight']
                if not isinstance(insight, dict):
                    continue
                doc_id = insight.get('document_id', 'unknown')
                metadata = insight.get('metadata', {})
                opp_name = metadata.get('sfdc_name', 'Unknown')
                chunk_count = pkg['chunk_count']
                score = pkg['aggregate_score']
                logger.info(f"[SalesforceAgent.retrieve_documents] Top package {i+1}: {opp_name}, ID={doc_id}, Score={score:.4f}, Chunks={chunk_count}")

            # STEP 6: Flatten the packages into the final document list
            all_documents = []
            insight_count = 0
            chunk_count = 0
            
            # Keep track of total documents added for debugging
            for package in top_packages:
                if not isinstance(package, dict) or not isinstance(package.get('insight'), dict):
                    continue
                    
                # Update the insight's relevance score with our calculated aggregate score
                package['insight']['relevance_score'] = package['aggregate_score']
                all_documents.append(package['insight'])
                insight_count += 1
                
                # Add all chunks from this package
                chunks = package.get('chunks', [])
                all_documents.extend(chunks)
                chunk_count += len(chunks)
            
            # Log the number of documents retrieved
            logger.info(f"[SalesforceAgent.retrieve_documents] Retrieved {len(all_documents)} total documents after flattening packages: {insight_count} insights and {chunk_count} chunks")
            
            # Add detailed logging of retrieved documents
            for i, doc in enumerate(all_documents[:10]):  # Log only first 10 to avoid excessive output
                if not isinstance(doc, dict):
                    continue
                doc_id = doc.get('document_id', doc.get('id', 'unknown'))
                metadata = doc.get('metadata', {})
                doc_type = metadata.get('document_type', 'unknown')
                source = metadata.get('source', 'unknown')
                relevance = doc.get('relevance_score', 0)
                
                logger.info(f"[SalesforceAgent.retrieve_documents] Doc {i+1}: ID={doc_id}, Type={doc_type}, Source={source}, Relevance={relevance:.4f}")
                
                # Log additional metadata that might be useful
                sfdc_keys = [k for k in metadata.keys() if k.startswith('sfdc_') or k in ['opportunity_id', 'account_id', 'amount', 'stage']]
                if sfdc_keys:
                    sfdc_data = {k: metadata.get(k) for k in sfdc_keys}
                    logger.info(f"[SalesforceAgent.retrieve_documents] SFDC metadata: {json.dumps(sfdc_data)}")
            
            # Process the documents to extract additional metadata if needed
            processed_docs = self._process_retrieved_documents(all_documents)
            
            # Final check to ensure we're not limiting results unnecessarily 
            logger.info(f"[SalesforceAgent.retrieve_documents] Final processed document count: {len(processed_docs)}")
            
            # Sort by relevance score
            processed_docs.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            return processed_docs
            
        except Exception as e:
            logger.error(f"[SalesforceAgent.retrieve_documents] Error retrieving documents: {e}")
            import traceback
            logger.error(f"[SalesforceAgent.retrieve_documents] Traceback: {traceback.format_exc()}")
            # Fallback to standard retrieval
            return await self._fallback_retrieve_documents(state)
    
    async def _fallback_retrieve_documents(self, state: AgentState) -> List[Dict[str, Any]]:
        """Fallback document retrieval using standard ChromaDB when enhanced retriever fails."""
        try:
            logger.info(f"[SalesforceAgent._fallback_retrieve_documents] Using fallback retrieval")
            
            # Import required utilities here to avoid circular imports
            from app.utils.chromadb import ChromaDB
            # Initialize with WARNING log level to reduce noise
            chroma_db = ChromaDB(log_level="WARNING")
            
            # Prepare Salesforce-specific query terms - similar to GongAgent's approach
            sfdc_terms = ["opportunity", "deal", "pipeline", "forecast", "revenue", "account", "salesforce"]
            topics = state.topics or self.default_topics
            
            # Combine the user's question with the predefined terms and extracted topics
            all_query_parts = [state.question] + sfdc_terms + topics
            enhanced_query = " ".join(list(dict.fromkeys(all_query_parts))) # Join unique terms
            
            logger.info(f"[SalesforceAgent._fallback_retrieve_documents] Built enhanced query: '{enhanced_query}'")
            
            # 1. Handle specific document IDs if provided
            if state.document_ids:
                logger.info(f"[SalesforceAgent._fallback_retrieve_documents] Using specific document IDs: {state.document_ids}")
                return await self._retrieve_by_document_ids(state.document_ids)
            
            # 2. Set up strict source_type filter for Salesforce data
            where_filter = {"source_type": {"$eq": "salesforce"}}
            
            # 3. Search for Salesforce documents in insights collection
            sfdc_docs = []
            
            # Search by document_type for SFDC insights
            try:
                # Use config for n_results value
                sfdc_results = chroma_db.query_collection_with_relevance_scores(
                    collection_name=chroma_collections.insights_collection,
                    query_texts=[enhanced_query],
                    n_results=500,  # Use high fixed value like GongAgent does
                    where={"document_type": {"$eq": "sfdc_opportunity_insights"}}
                )
                
                for doc in sfdc_results:
                    doc['collection'] = chroma_collections.insights_collection
                    # Process document to extract metadata insights
                    processed_doc = extract_insights_from_metadata(doc)
                    sfdc_docs.append(processed_doc)
            except Exception as type_err:
                logger.warning(f"Error searching by document_type: {type_err}")
            
            # Search by source_type as fallback
            if len(sfdc_docs) < 20:
                try:
                    # Use config for n_results value
                    source_results = chroma_db.query_collection_with_relevance_scores(
                        collection_name=chroma_collections.insights_collection,
                        query_texts=[enhanced_query],
                        n_results=500,  # Use high fixed value like GongAgent does
                        where={"source_type": {"$eq": "salesforce"}}
                    )
                    
                    for doc in source_results:
                        # Avoid duplicates
                        if not any(existing.get('id') == doc.get('id') for existing in sfdc_docs):
                            doc['collection'] = chroma_collections.insights_collection
                            # Process document to extract metadata insights
                            processed_doc = extract_insights_from_metadata(doc)
                            sfdc_docs.append(processed_doc)
                            
                except Exception as source_err:
                    logger.warning(f"Error searching by source_type: {source_err}")
            
            # Try searching by company names if we have few results
            company_names = extract_potential_company_names(state.question)
            if company_names and len(sfdc_docs) < 10:
                logger.info(f"[SalesforceAgent._fallback_retrieve_documents] Searching for {len(company_names)} extracted company names")
                
                for company_name in company_names:
                    # Skip very short or common terms
                    if len(company_name) < 3 or company_name.lower() in ["the", "and", "inc", "llc"]:
                        continue
                        
                    # Create a company name search query
                    company_query = f"{company_name} salesforce"
                    logger.info(f"[SalesforceAgent._fallback_retrieve_documents] Searching for company: '{company_query}'")
                    
                    try:
                        # Search for company name
                        company_results = chroma_db.query_collection_with_relevance_scores(
                            collection_name=chroma_collections.insights_collection,
                            query_texts=[company_query],
                            n_results=100,  # Use high fixed value like GongAgent does
                            where={"source_type": {"$eq": "salesforce"}}
                        )
                        
                        if company_results:
                            logger.info(f"[SalesforceAgent._fallback_retrieve_documents] Found {len(company_results)} documents for company '{company_name}'")
                            
                            # Add new documents but avoid duplicates
                            existing_ids = {doc.get('id') for doc in sfdc_docs}
                            for doc in company_results:
                                if doc.get('id') not in existing_ids:
                                    doc['collection'] = chroma_collections.insights_collection
                                    processed_doc = extract_insights_from_metadata(doc)
                                    sfdc_docs.append(processed_doc)
                                    existing_ids.add(doc.get('id'))
                    except Exception as company_err:
                        logger.warning(f"Error searching for company {company_name}: {company_err}")
            
            # If we have few results, try a broader search specifically for customer names
            if len(sfdc_docs) < 5:
                logger.info(f"[SalesforceAgent._fallback_retrieve_documents] Few results found, trying broader search for customer names")
                
                # Strip out salesforce-specific terms to focus on customer name
                question_parts = state.question.lower().split()
                # Remove common words that aren't likely to be part of company names
                common_words = ["the", "and", "or", "in", "on", "at", "with", "for", "about", "from", "to"]
                filtered_parts = [word for word in question_parts if word not in common_words and len(word) > 2]
                
                # Create a simple name search query
                name_query = " ".join(filtered_parts)
                logger.info(f"[SalesforceAgent._fallback_retrieve_documents] Searching for potential customer names: '{name_query}'")
                
                try:
                    # Execute a broader search with just the potential customer name terms
                    name_results = chroma_db.query_collection_with_relevance_scores(
                        collection_name=chroma_collections.insights_collection,
                        query_texts=[name_query],
                        n_results=500,  # Use high fixed value like GongAgent does
                        where={"source_type": {"$eq": "salesforce"}}
                    )
                    
                    logger.info(f"[SalesforceAgent._fallback_retrieve_documents] Name search found {len(name_results)} documents")
                    
                    # Add new documents but avoid duplicates
                    existing_ids = {doc.get('id') for doc in sfdc_docs}
                    for doc in name_results:
                        if doc.get('id') not in existing_ids:
                            doc['collection'] = chroma_collections.insights_collection
                            processed_doc = extract_insights_from_metadata(doc)
                            sfdc_docs.append(processed_doc)
                            existing_ids.add(doc.get('id'))
                            
                except Exception as name_err:
                    logger.warning(f"Error searching by name: {name_err}")
            
            # Process and structure the documents
            processed_docs = self._process_retrieved_documents(sfdc_docs)
            logger.info(f"[SalesforceAgent._fallback_retrieve_documents] Retrieved {len(processed_docs)} documents")
            
            # Add detailed logging of retrieved documents in fallback method
            for i, doc in enumerate(processed_docs):
                doc_id = doc.get('document_id', 'unknown')
                doc_type = doc.get('document_type', 'unknown')
                collection = doc.get('collection', 'unknown')
                relevance = doc.get('relevance_score', 0)
                
                logger.info(f"[SalesforceAgent._fallback_retrieve_documents] Doc {i+1}: ID={doc_id}, Type={doc_type}, Collection={collection}, Relevance={relevance:.4f}")
                
                # Log additional metadata that might be useful
                metadata = doc.get('metadata', {})
                if metadata:
                    important_keys = ['sfdc_opportunity_id', 'sfdc_name', 'sfdc_amount', 'sfdc_stage_name', 'account_id', 'account_name']
                    filtered_metadata = {k: metadata.get(k) for k in important_keys if k in metadata}
                    if filtered_metadata:
                        logger.info(f"[SalesforceAgent._fallback_retrieve_documents] Important metadata: {json.dumps(filtered_metadata)}")
            
            # Sort by relevance score
            processed_docs.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            return processed_docs
            
        except Exception as e:
            logger.error(f"[SalesforceAgent._fallback_retrieve_documents] Error: {e}")
            return []
    
    def _extract_potential_company_names(self, query: str) -> List[str]:
        """
        Extract potential company or customer names from a query.
        This helps with identifying specific company mentions like "Electronic Arts" or "EA".
        
        Args:
            query: The user's question
            
        Returns:
            A list of potential company name phrases
        """
        # Convert to lowercase for easier processing
        query_lower = query.lower()
        
        # Common words to exclude from company name extraction
        common_words = [
            "the", "and", "or", "in", "on", "at", "with", "for", "about", "from", "to",
            "how", "what", "when", "where", "why", "who", "which", "that", "this", "these", 
            "those", "their", "our", "your", "my", "his", "her", "its", "their"
        ]
        
        # Common words that indicate a company might follow
        company_indicators = ["company", "client", "customer", "account", "opportunity", "deal"]
        
        potential_names = []
        
        # Split into words
        words = query_lower.replace("?", "").replace(".", "").replace(",", "").split()
        
        # Look for capitalized phrases in the original query (potential proper nouns)
        words_original = query.split()
        for i in range(len(words_original)):
            # Check if word starts with capital letter (potential company name)
            if i < len(words_original) and words_original[i][0:1].isupper():
                # Try to capture multi-word company names
                name_parts = [words_original[i]]
                j = i + 1
                # Continue adding words if they start with a capital letter or are connecting words
                while j < len(words_original) and (
                    words_original[j][0:1].isupper() or 
                    words_original[j].lower() in ["and", "of", "the", "&"]):
                    name_parts.append(words_original[j])
                    j += 1
                
                if len(name_parts) > 0:
                    potential_names.append(" ".join(name_parts))
        
        # Look for words after company indicators
        for i in range(len(words) - 1):
            if words[i] in company_indicators and i < len(words) - 1:
                # Extract the next word(s) that aren't common words
                next_words = []
                j = i + 1
                while j < len(words) and words[j] not in common_words:
                    next_words.append(words[j])
                    j += 1
                
                if next_words:
                    potential_names.append(" ".join(next_words))
        
        # Look for potential acronyms (all caps in original query)
        for word in query.split():
            if word.isupper() and len(word) >= 2 and len(word) <= 5:
                potential_names.append(word)
        
        # Extract potentially standalone words that aren't common words
        # and are long enough to be company names
        standalone_words = []
        for word in words:
            if (word not in common_words and len(word) >= 4 and 
                word not in company_indicators):
                standalone_words.append(word)
        
        # Add standalone words as potential names
        potential_names.extend(standalone_words)
        
        # Remove duplicates and very short terms
        filtered_names = list(set([name for name in potential_names if len(name) > 2]))
        
        logger.info(f"[_extract_potential_company_names] Extracted potential company names: {filtered_names}")
        
        return filtered_names

    def _extract_potential_ids(self, query: str, id_type: str = "opportunity") -> List[str]:
        """
        Extract potential Salesforce IDs from the query.
        
        Args:
            query: The user's question
            id_type: Type of ID to extract ("opportunity" or "account")
            
        Returns:
            A list of potential ID strings
        """
        # Standard Salesforce ID patterns
        # Opportunity IDs typically start with '006'
        # Account IDs typically start with '001'
        sf_id_pattern = r'\b\w{15,18}\b'  # Salesforce IDs are 15 or 18 chars
        
        # Look for explicit mentions with labels
        explicit_patterns = {
            "opportunity": [
                r'opportunity id:?\s*(\w{15,18})',
                r'opportunity id\s+is\s+(\w{15,18})',
                r'opportunity\s*#\s*(\w{15,18})',
                r'opp id:?\s*(\w{15,18})',
                r'opp\s*#\s*(\w{15,18})'
            ],
            "account": [
                r'account id:?\s*(\w{15,18})',
                r'account id\s+is\s+(\w{15,18})',
                r'account\s*#\s*(\w{15,18})'
            ]
        }
        
        found_ids = []
        
        # Check for explicit ID mentions first
        patterns_to_check = explicit_patterns.get(id_type, [])
        for pattern in patterns_to_check:
            matches = re.finditer(pattern, query.lower())
            for match in matches:
                if match.group(1):
                    found_ids.append(match.group(1))
        
        # If no explicit mentions, look for any Salesforce-like IDs
        if not found_ids:
            matches = re.finditer(sf_id_pattern, query)
            for match in matches:
                potential_id = match.group(0)
                # Apply some validation based on ID type
                if id_type == "opportunity" and (potential_id.startswith("006") or potential_id.startswith("00Q")):
                    found_ids.append(potential_id)
                elif id_type == "account" and potential_id.startswith("001"):
                    found_ids.append(potential_id)
                # If no specific type validation passes but it's long enough, include it as a fallback
                elif len(potential_id) >= 15:
                    found_ids.append(potential_id)
        
        return found_ids

    async def _retrieve_by_document_ids(self, document_ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieve specific Salesforce documents by their IDs."""
        logger.info(f"[SalesforceAgent._retrieve_by_document_ids] Retrieving documents by IDs: {document_ids}")
        
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
                        logger.info(f"[SalesforceAgent._retrieve_by_document_ids] Found document directly: {doc_id}")
                        for doc in direct_docs:
                            doc['collection'] = chroma_collections.documents_collection
                            # Process document to extract metadata
                            processed_doc = extract_insights_from_metadata(doc)
                            all_docs.append(processed_doc)
                    else:
                        # Look in insights collection for Salesforce data
                        insights_docs = chroma_db.query_collection_with_relevance_scores(
                            collection_name=chroma_collections.insights_collection,
                            query_texts=[""],  # Empty query to just retrieve by ID
                            n_results=1,
                            where={"document_id": {"$eq": doc_id}}
                        )
                        
                        if insights_docs:
                            logger.info(f"[SalesforceAgent._retrieve_by_document_ids] Found document in {chroma_collections.insights_collection}: {doc_id}")
                            for doc in insights_docs:
                                doc['collection'] = chroma_collections.insights_collection
                                processed_doc = extract_insights_from_metadata(doc)
                                all_docs.append(processed_doc)
                        else:
                            # Look in chunks collection for Salesforce data
                            sfdc_docs = chroma_db.query_collection_with_relevance_scores(
                                collection_name=chroma_collections.chunks_collection,
                                query_texts=[""],  # Empty query to just retrieve by ID
                                n_results=100,  # Use high fixed value like GongAgent does
                                where={"document_id": {"$eq": doc_id}, "source_type": {"$eq": "salesforce"}}
                            )
                            
                            if sfdc_docs:
                                logger.info(f"[SalesforceAgent._retrieve_by_document_ids] Found document in {chroma_collections.chunks_collection}: {doc_id}")
                                for doc in sfdc_docs:
                                    doc['collection'] = chroma_collections.chunks_collection
                                    # Process document to extract metadata
                                    processed_doc = extract_insights_from_metadata(doc)
                                    all_docs.append(processed_doc)
                except Exception as e:
                    logger.warning(f"[SalesforceAgent._retrieve_by_document_ids] Error retrieving document {doc_id}: {e}")
            
            # Process and structure the documents
            processed_docs = self._process_retrieved_documents(all_docs)
            logger.info(f"[SalesforceAgent._retrieve_by_document_ids] Retrieved {len(processed_docs)} documents by ID")
            
            # Add detailed logging of documents retrieved by ID
            for i, doc in enumerate(processed_docs):
                doc_id = doc.get('document_id', 'unknown')
                doc_type = doc.get('document_type', 'unknown')
                collection = doc.get('collection', 'unknown')
                
                logger.info(f"[SalesforceAgent._retrieve_by_document_ids] Doc {i+1}: ID={doc_id}, Type={doc_type}, Collection={collection}")
                
                # Log opportunity-specific details if available
                if doc.get('opportunity_id'):
                    opp_details = {
                        'opportunity_id': doc.get('opportunity_id'),
                        'opportunity_name': doc.get('opportunity_name', ''),
                        'is_closed': doc.get('is_closed', False),
                        'is_won': doc.get('is_won', False),
                        'close_date': doc.get('close_date', '')
                    }
                    logger.info(f"[SalesforceAgent._retrieve_by_document_ids] Opportunity details: {json.dumps(opp_details)}")
            
            # Sort by relevance score
            processed_docs.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            return processed_docs
            
        except Exception as e:
            logger.error(f"[SalesforceAgent._retrieve_by_document_ids] Error: {e}")
            return []
    
    def _process_retrieved_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process retrieved documents to standardize format and extract metadata."""
        processed_docs = []
        
        for doc in documents:
            # Extract metadata
            metadata = doc.get('metadata', {})
            
            # Determine document type
            doc_type = metadata.get('document_type', '')
            if not doc_type:
                doc_type = 'sfdc_document'
            
            # Extract content
            content = doc.get('content', doc.get('document', ''))
            
            # Create processed document
            processed_doc = {
                'document_id': doc.get('document_id', metadata.get('document_id', doc.get('id', 'unknown'))),
                'document_type': doc_type,
                'content': content,
                'collection': doc.get('collection', 'unknown'),
                'metadata': metadata,
                'relevance_score': doc.get('relevance_score', 0.0),
                'source_type': 'salesforce'  # Explicitly mark as Salesforce
            }
            
            # Extract opportunity details if available
            if 'sfdc_opportunity_id' in metadata:
                processed_doc['opportunity_id'] = metadata['sfdc_opportunity_id']
                processed_doc['opportunity_name'] = metadata.get('sfdc_name', '')
                processed_doc['is_closed'] = metadata.get('is_closed', False)
                processed_doc['is_won'] = metadata.get('is_won', False)
                processed_doc['close_date'] = metadata.get('close_date', '')
            
            processed_docs.append(processed_doc)
        
        # Sort by relevance score
        processed_docs.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return processed_docs
    
    async def generate_answer(self, state: AgentState) -> str:
        """
        Generate an answer based on retrieved Salesforce documents or SQL results.
        
        Args:
            state: The current agent state with retrieved documents or SQL results
            
        Returns:
            Generated answer text
        """
        # Check if we have SQL results in additional_context
        sql_results = None
        opportunity_names = []
        if hasattr(state, 'additional_context') and state.additional_context:
            sql_results = state.additional_context.get('sql_results', [])
            opportunity_names = state.additional_context.get('opportunity_names', [])

        # If we have SQL results, use them directly instead of retrieved documents
        if sql_results:
            logger.info(f"[SalesforceAgent.generate_answer] Using {len(sql_results)} SQL results directly")
            return await self._generate_answer_from_sql(state.question, sql_results, opportunity_names, state)

        # Fall back to document-based answer generation if no SQL results
        logger.info(f"[SalesforceAgent.generate_answer] Generating answer from {len(state.retrieved_documents)} documents")
        
        if not state.retrieved_documents:
            return "I couldn't find any relevant Salesforce data to answer your question. Please provide more details or try a different question."
        
        # Get the original question and current query (which might be refined)
        original_question = state.question
        current_query = getattr(state, 'current_query', state.question)
        
        # Check if we have additional context with a refined query flag
        is_refined_query = False
        if hasattr(state, 'additional_context') and state.additional_context:
            is_refined_query = state.additional_context.get('refined_query', False)
            
        logger.info(f"[SalesforceAgent.generate_answer] Original question: '{original_question}'")
        if is_refined_query:
            logger.info(f"[SalesforceAgent.generate_answer] Refined query: '{current_query}'")
        
        # Organize documents by type and relationships
        organized_docs = {
            'insights': [],           # Will hold all sfdc_insights documents
            'chunks': {},             # Will map opportunity_id to list of chunks
            'other_documents': []     # Will hold all other document types
        }
        
        # First pass: categorize documents
        for doc in state.retrieved_documents:
            # Extract document type information
            doc_type = doc.get('document_type', '').lower()
            collection = doc.get('collection', '')
            
            # Simple insight detection based on type or collection
            is_insight = ('insight' in doc_type or doc_type == 'sfdc_opportunity_insights')
            
            if is_insight:
                organized_docs['insights'].append(doc)
            elif ('chunk' in doc_type or doc_type == 'sfdc_chunk'):
                # Group chunks by opportunity_id
                opp_id = doc.get('opportunity_id', '')
                if not opp_id:
                    # Try to get from metadata
                    metadata = doc.get('metadata', {})
                    opp_id = metadata.get('sfdc_opportunity_id', '')
                
                if opp_id:
                    if opp_id not in organized_docs['chunks']:
                        organized_docs['chunks'][opp_id] = []
                    organized_docs['chunks'][opp_id].append(doc)
                else:
                    # If we can't determine opportunity_id, treat as other document
                    organized_docs['other_documents'].append(doc)
            else:
                organized_docs['other_documents'].append(doc)
        
        # Build structured context from documents
        context_parts = ["## SALESFORCE DATA"]
        
        # Add insights first with their structured content
        if organized_docs['insights']:
            context_parts.append("\n### OPPORTUNITY INSIGHTS")
            
            for doc in organized_docs['insights'][:10]:  # Limit to top 10 insights
                doc_id = doc.get('document_id', 'unknown')
                opp_name = doc.get('opportunity_name', doc.get('metadata', {}).get('sfdc_name', f"Opportunity {doc_id}"))
                close_date = doc.get('close_date', doc.get('metadata', {}).get('close_date', 'Unknown date'))
                stage = doc.get('metadata', {}).get('sfdc_stage_name', 'Unknown stage')
                amount = doc.get('metadata', {}).get('sfdc_amount', 'Unknown amount')
                
                context_parts.append(f"\n#### {opp_name} (Stage: {stage}, Amount: {amount}, Close Date: {close_date})")
                context_parts.append(f"Document ID: {doc_id}")
                
                # Add metadata summary
                metadata = doc.get('metadata', {})
                meta_summary = []
                
                # Add special metadata fields with more readable format
                for key in ['sfdc_account_name', 'sfdc_owner_name', 'sfdc_lead_source']:
                    if key in metadata:
                        label = key.replace('sfdc_', '').replace('_', ' ').title()
                        meta_summary.append(f"{label}: {metadata[key]}")
                
                if meta_summary:
                    context_parts.append("\n#### Metadata Summary")
                    context_parts.extend(meta_summary)
                
                # Add content of the insight
                content = doc.get('content', '')
                if isinstance(content, dict):
                    content = content.get('text', str(content))
                
                context_parts.append("\n#### Insight Content")
                context_parts.append(content)
                
                # Add associated chunks
                opp_id = doc.get('opportunity_id', metadata.get('sfdc_opportunity_id', ''))
                if opp_id and opp_id in organized_docs['chunks']:
                    context_parts.append("\n#### Associated Opportunity Details")
                    chunks = organized_docs['chunks'][opp_id]
                    
                    # Include all chunks (limit to 10 per opportunity)
                    for i, chunk in enumerate(chunks[:10]):
                        chunk_content = chunk.get('content', '')
                        if isinstance(chunk_content, dict):
                            chunk_content = chunk_content.get('text', str(chunk_content))
                        context_parts.append(f"\nDetail {i+1}/{len(chunks[:10])}:")
                        context_parts.append(chunk_content)
        
        # Process orphan chunks (chunks without matched insights)
        orphan_chunks = {}
        for opp_id, chunks in organized_docs['chunks'].items():
            if not any(doc.get('opportunity_id') == opp_id or doc.get('metadata', {}).get('sfdc_opportunity_id') == opp_id for doc in organized_docs['insights']):
                orphan_chunks[opp_id] = chunks
        
        if orphan_chunks:
            context_parts.append("\n## ADDITIONAL OPPORTUNITY DETAILS")
            for opp_id, chunks in orphan_chunks.items():
                opp_name = chunks[0].get('metadata', {}).get('sfdc_name', f"Opportunity {opp_id}")
                context_parts.append(f"\n### {opp_name}")
                context_parts.append(f"Opportunity ID: {opp_id}")
                context_parts.append(f"Number of details: {len(chunks)}")
                
                # Include limited chunks
                for i, chunk in enumerate(chunks[:5]):  # Limit to first 5 chunks
                    chunk_content = chunk.get('content', '')
                    if isinstance(chunk_content, dict):
                        chunk_content = chunk_content.get('text', str(chunk_content))
                    context_parts.append(f"\nDetail {i+1}/{len(chunks[:5])}:")
                    context_parts.append(chunk_content)
        
        # Process other documents
        if organized_docs['other_documents']:
            context_parts.append("\n## OTHER SALESFORCE DATA")
            for doc in organized_docs['other_documents'][:5]:  # Limit to top 5
                doc_id = doc.get('document_id', 'unknown')
                doc_type = doc.get('document_type', 'unknown')
                
                context_parts.append(f"\n### Document {doc_id} ({doc_type})")
                
                # Get content
                content = doc.get('content', '')
                if isinstance(content, dict):
                    content = content.get('text', str(content))
                
                context_parts.append(content)
        
        # Format structured sections for easier LLM processing
        context_parts.append("\n## STRUCTURED INSIGHTS")
        
        # Extract opportunity information in a structured format
        if organized_docs['insights']:
            context_parts.append("\n### Key Opportunity Data")
            
            for doc in organized_docs['insights']:
                metadata = doc.get('metadata', {})
                opp_name = doc.get('opportunity_name', metadata.get('sfdc_name', 'Unnamed Opportunity'))
                opp_id = doc.get('opportunity_id', metadata.get('sfdc_opportunity_id', 'Unknown ID'))
                
                # Extract structured information
                structured_data = {
                    "Name": opp_name,
                    "ID": opp_id,
                    "Stage": metadata.get('sfdc_stage_name', 'Unknown'),
                    "Amount": metadata.get('sfdc_amount', 'Unknown'),
                    "Close Date": metadata.get('close_date', metadata.get('sfdc_close_date', 'Unknown')),
                    "Account": metadata.get('sfdc_account_name', 'Unknown'),
                    "Owner": metadata.get('sfdc_owner_name', 'Unknown'),
                    "Probability": metadata.get('sfdc_probability', 'Unknown'),
                    "Is Closed": metadata.get('is_closed', False),
                    "Is Won": metadata.get('is_won', False)
                }
                
                context_parts.append(f"\n#### {opp_name}")
                for key, value in structured_data.items():
                    if value not in ('Unknown', ''):
                        context_parts.append(f"- **{key}**: {value}")
        
        # Combine all context
        context = "\n".join(context_parts)
        
        try:
            # Use shared utility for system prompt
            system_prompt = build_salesforce_agent_system_prompt()
            
            # Use shared utility to build human prompt
            human_prompt = build_human_prompt(
                question=original_question,
                context=context,
                current_query=current_query,
                is_refined_query=is_refined_query,
                additional_context=getattr(state, 'additional_context', {})
            )
            
            # Get the appropriate LLM for answer generation
            llm = get_answer_generation_llm()
            logger.info(f"[SalesforceAgent.generate_answer] Using model for answer generation: {llm.model_name}")

            # Add a small delay to avoid rate limiting
            await asyncio.sleep(0.3)
            
            # Invoke LLM
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])
            
            if isinstance(response.content, str):
                return response.content
            else:
                logger.warning("[SalesforceAgent.generate_answer] LLM response content is not a string")
                return "I encountered an issue processing the Salesforce data. Please try again with a more specific question."
                
        except Exception as e:
            logger.error(f"[SalesforceAgent.generate_answer] Error generating answer: {e}")
            return f"I encountered an error analyzing the Salesforce data: {str(e)}. Please try again with a different question."

    async def _generate_answer_from_sql(self, question: str, sql_results: List[Dict[str, Any]], opportunity_names: List[str], state: AgentState) -> str:
        """
        Generate an answer directly from SQL results without document retrieval.

        Args:
            question: The user's question
            sql_results: List of SQL result rows
            opportunity_names: List of opportunity names extracted from SQL results
            state: The current agent state

        Returns:
            Generated answer text
        """
        try:
            logger.info(f"[SalesforceAgent._generate_answer_from_sql] Generating answer from {len(sql_results)} SQL results")

            # Build structured context from SQL results
            context_parts = ["## SALESFORCE SQL DATA"]

            # Format the SQL results into a readable table
            if sql_results:
                # Add a section for the SQL data
                context_parts.append("\n### SQL QUERY RESULTS")

                # Get all possible keys from all results
                all_keys = set()
                for row in sql_results:
                    all_keys.update(row.keys())

                # Prioritize important keys to show first
                priority_keys = ['id', 'name', 'amount', 'stage', 'close_date', 'probability', 'account_name', 'owner_name', 'is_closed', 'is_won']
                ordered_keys = [k for k in priority_keys if k in all_keys]
                ordered_keys.extend([k for k in all_keys if k not in priority_keys])

                # Format as a markdown table
                header_row = "| " + " | ".join(ordered_keys) + " |"
                separator_row = "| " + " | ".join(["---" for _ in ordered_keys]) + " |"
                context_parts.append(header_row)
                context_parts.append(separator_row)

                # Add data rows
                for row in sql_results[:20]:  # Limit to first 20 rows to avoid context overflow
                    data_row = "| " + " | ".join([str(row.get(k, "")) for k in ordered_keys]) + " |"
                    context_parts.append(data_row)

                # If there are more than 20 rows, add a note
                if len(sql_results) > 20:
                    context_parts.append(f"\n*Note: Showing 20 of {len(sql_results)} total results*")

            # Add a summary section with key metrics
            context_parts.append("\n### SUMMARY METRICS")

            # Calculate summary metrics
            total_opportunities = len(sql_results)
            total_amount = sum(float(row.get('amount', 0)) for row in sql_results if row.get('amount'))
            won_opportunities = sum(1 for row in sql_results if row.get('is_won'))
            open_opportunities = sum(1 for row in sql_results if not row.get('is_closed'))

            # Add summary metrics
            context_parts.append(f"- Total Opportunities: {total_opportunities}")
            context_parts.append(f"- Total Amount: ${total_amount:,.2f}")
            context_parts.append(f"- Won Opportunities: {won_opportunities}")
            context_parts.append(f"- Open Opportunities: {open_opportunities}")

            # Add opportunity details in a more readable format
            context_parts.append("\n### OPPORTUNITY DETAILS")

            for i, row in enumerate(sql_results[:10]):  # Limit to first 10 opportunities for detail view
                name = row.get('name', f"Opportunity {i+1}")
                amount = row.get('amount', 'Unknown')
                if amount != 'Unknown':
                    try:
                        amount = f"${float(amount):,.2f}"
                    except (ValueError, TypeError):
                        pass

                stage = row.get('stage', row.get('stage_name', 'Unknown'))
                close_date = row.get('close_date', 'Unknown')
                account = row.get('account_name', 'Unknown')

                context_parts.append(f"\n#### {name}")
                context_parts.append(f"- Amount: {amount}")
                context_parts.append(f"- Stage: {stage}")
                context_parts.append(f"- Close Date: {close_date}")
                context_parts.append(f"- Account: {account}")

                # Add any other important fields
                for key, value in row.items():
                    if key not in ['name', 'amount', 'stage', 'stage_name', 'close_date', 'account_name'] and value:
                        # Format the key name for better readability
                        formatted_key = key.replace('_', ' ').title()
                        context_parts.append(f"- {formatted_key}: {value}")

            # If there are more than 10 opportunities, add a note
            if len(sql_results) > 10:
                context_parts.append(f"\n*Note: Showing details for 10 of {len(sql_results)} total opportunities*")

            # Combine all context
            context = "\n".join(context_parts)

            # Use shared utility for system prompt
            system_prompt = build_salesforce_agent_system_prompt()

            # Add special instructions for SQL-based answers
            system_prompt += "\n\nYou are working with direct SQL query results from Salesforce. Focus on providing precise answers based on this structured data rather than document retrieval. Make sure to highlight key metrics and trends in the data."

            # Use shared utility to build human prompt
            human_prompt = build_human_prompt(
                question=question,
                context=context,
                current_query=question,
                is_refined_query=False,
                additional_context=getattr(state, 'additional_context', {})
            )

            # Get the appropriate LLM for answer generation
            llm = get_answer_generation_llm()
            logger.info(f"[SalesforceAgent._generate_answer_from_sql] Using model for answer generation: {llm.model_name}")

            # Add a small delay to avoid rate limiting
            await asyncio.sleep(0.3)

            # Invoke LLM
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])

            if isinstance(response.content, str):
                return response.content
            else:
                logger.warning("[SalesforceAgent._generate_answer_from_sql] LLM response content is not a string")
                return "I encountered an issue processing the Salesforce SQL data. Please try again with a more specific question."

        except Exception as e:
            logger.error(f"[SalesforceAgent._generate_answer_from_sql] Error generating answer from SQL: {e}")
            import traceback
            logger.error(f"[SalesforceAgent._generate_answer_from_sql] Traceback: {traceback.format_exc()}")
            return f"I encountered an error analyzing the Salesforce SQL data: {str(e)}. Please try again with a different question."