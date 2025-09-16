import logging
import time
import datetime
import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Annotated, Sequence, Union
import asyncio
import uuid
from datetime import datetime, timedelta

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
import operator
from enum import Enum

from chromadb import Collection
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Import document planning components
from .enhanced_document_planner import (
    EnhancedDocumentPlanner, DocumentPlan, DocumentPlanningStrategy, 
    RetrievalGrade, DocumentRetrievalResult
)
from .document_plan_executor import DocumentPlanExecutor

from app.services.docs.document_schemas import DocumentType
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings

# Removed SFDC imports - using dedicated SQL agents instead

if TYPE_CHECKING:
    from langgraph.graph.graph import CompiledGraph

# Enhanced logger setup
logger = logging.getLogger("EnhancedSelfRAGAgent")
logger.setLevel(logging.DEBUG)


import time


def checkpoint(title: str, last_checkpoint_time: float) -> float:
    """
    Record a checkpoint with the given title and log the elapsed time since the last checkpoint.
    """
    current_time = time.time()
    elapsed = current_time - last_checkpoint_time
    
    print(
        f"Checkpoint: {title} | Elapsed: {elapsed:.4f}s"
    )
    return current_time

# Define state types
class QueryType(str, Enum):
    INITIAL = "initial"
    REFINED = "refined"

class DocumentSource(BaseModel):
    document_id: str
    document_type: str
    relevance_score: float = Field(default=0.0)
    tfidf_score: float = Field(default=0.0)
    source_type: str = Field(default="document")  # document, web, sfdc
    
class RetrievedDocument(BaseModel):
    document_id: str
    document_type: str
    content: dict
    relevance_score: float = Field(default=0.0)
    tfidf_score: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    insights: List[Dict[str, Any]] = Field(default_factory=list)
    source_type: str = Field(default="document")
    web_url: Optional[str] = None
    citation_info: Dict[str, Any] = Field(default_factory=dict)

class WebSearchResult(BaseModel):
    title: str
    content: str
    url: str
    relevance_score: float = Field(default=0.0)
    source_type: str = Field(default="web")

class QuestionType(str, Enum):
    """Types of questions to determine retrieval strategy"""
    SUMMARY = "summary"           # Requires full documents for comprehensive overview
    SPECIFIC = "specific"         # Requires specific chunks for targeted information
    COMPARATIVE = "comparative"   # Requires multiple documents for comparison
    ANALYTICAL = "analytical"     # Requires detailed analysis of specific content

class RetrievalStrategy(str, Enum):
    """Retrieval strategies based on question type"""
    CHUNKS_ONLY = "chunks_only"      # Use TF-IDF chunks for specific queries
    FULL_DOCS = "full_docs"          # Use full documents for summary queries
    HYBRID = "hybrid"                # Use both chunks and full docs

class DocumentGrade(str, Enum):
    """Grades for document relevance and quality"""
    EXCELLENT = "excellent"      # Highly relevant, high quality
    GOOD = "good"               # Relevant, good quality
    FAIR = "fair"               # Somewhat relevant, moderate quality
    POOR = "poor"               # Low relevance or quality
    INSUFFICIENT = "insufficient" # Not relevant or very low quality

class EnhancedSelfRAGState(BaseModel):
    """Enhanced state for the Self-RAG document chat agent."""
    model_config = {"arbitrary_types_allowed": True}
    
    question: str
    source: str
    chat_history: List[Dict[str, Any]] = Field(default_factory=list)
    current_query: str = ""
    query_type: QueryType = QueryType.INITIAL
    question_type: QuestionType = QuestionType.SPECIFIC
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.CHUNKS_ONLY
    
    # Document retrieval results
    retrieved_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
    selected_documents: List[RetrievedDocument] = Field(default_factory=list)
    document_grades: Dict[str, DocumentGrade] = Field(default_factory=dict)
    
    # Web search and other sources
    web_search_results: List[WebSearchResult] = Field(default_factory=list)
    
    # Processing state
    context: str = ""
    reflection: str = ""
    needs_more_info: bool = False
    answer: str = ""
    final_answer: str = ""
    document_ids: List[str] = Field(default_factory=list)
    recursion_count: int = Field(default=0)
    
    # New fields for enhanced functionality
    document_plan: Optional[DocumentPlan] = Field(default=None, exclude=True)
    tfidf_vectorizer: Optional[TfidfVectorizer] = Field(default=None, exclude=True)
    tfidf_matrix: Optional[np.ndarray] = Field(default=None, exclude=True)
    chunk_scores: List[float] = Field(default_factory=list)
    action_taken: str = ""
    metadata_summary: Dict[str, Any] = Field(default_factory=dict)

# Tavily search tool
@tool
async def tavily_web_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search the web using Tavily API for additional information.
    
    Args:
        query: Search query
        max_results: Maximum number of results to return
        
    Returns:
        List of web search results
    """
    try:
        # Import tavily here to avoid dependency issues
        from tavily import TavilyClient
        
        # Initialize Tavily client
        tavily = TavilyClient(api_key=get_settings().TAVILY_API_KEY)
        
        # Perform search
        search_results = tavily.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=True,
            include_raw_content=True
        )
        
        # Format results
        formatted_results = []
        for result in search_results.get("results", []):
            formatted_results.append({
                "title": result.get("title", ""),
                "content": result.get("content", ""),
                "url": result.get("url", ""),
                "score": result.get("score", 0.0),
                "published_date": result.get("published_date", ""),
                "raw_content": result.get("raw_content", "")
            })
        
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error in Tavily web search: {e}")
        return []

class TFIDFChunkRanker:
    """TF-IDF based chunk ranking for document relevance with caching"""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=500,  # Reduced for faster processing
            stop_words='english',
            ngram_range=(1, 2),
            min_df=2,  # Ignore terms that appear in less than 2 documents
            max_df=0.95  # Ignore terms that appear in more than 95% of documents
        )
        self.tfidf_matrix = None
        self.fitted = False
        self._cache = {}  # Cache for repeated queries
    
    def fit_transform(self, documents: List[str]) -> np.ndarray:
        """Fit TF-IDF vectorizer and transform documents"""
        try:
            self.tfidf_matrix = self.vectorizer.fit_transform(documents)
            self.fitted = True
            return self.tfidf_matrix
        except Exception as e:
            logger.error(f"Error fitting TF-IDF vectorizer: {e}")
            return np.array([])
    
    def get_relevance_scores(self, query: str, documents: List[str]) -> List[float]:
        """Get relevance scores for documents based on query with caching"""
        if not self.fitted or self.tfidf_matrix is None:
            return [0.0] * len(documents)
        
        # Check cache first
        cache_key = f"{query}_{len(documents)}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # Transform query
            query_vector = self.vectorizer.transform([query])
            
            # Calculate cosine similarity
            similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
            
            scores = similarities.tolist()
            
            # Cache the result (limit cache size)
            if len(self._cache) < 100:  # Keep cache manageable
                self._cache[cache_key] = scores
            
            return scores
        except Exception as e:
            logger.error(f"Error calculating TF-IDF scores: {e}")
            return [0.0] * len(documents)

class FastDocumentGrader:
    """Fast document grader using heuristics instead of LLM calls"""
    
    def __init__(self):
        self.keyword_weights = {
            'excellent': ['comprehensive', 'detailed', 'complete', 'thorough', 'specific'],
            'good': ['relevant', 'useful', 'important', 'key', 'main'],
            'fair': ['some', 'partial', 'limited', 'basic'],
            'poor': ['unclear', 'vague', 'incomplete', 'brief']
        }
    
    def grade_documents_fast(self, question: str, documents: List[Dict[str, Any]]) -> Dict[str, DocumentGrade]:
        """Grade documents using fast heuristics"""
        grades = {}
        question_words = set(question.lower().split())
        
        for i, doc in enumerate(documents):
            content = self._extract_text_content(doc)
            content_lower = content.lower()
            
            # Calculate relevance score based on keyword overlap
            content_words = set(content_lower.split())
            overlap = len(question_words.intersection(content_words))
            relevance_score = overlap / len(question_words) if question_words else 0
            
            # Calculate quality score based on content characteristics
            quality_score = self._calculate_quality_score(content)
            
            # Combine scores
            combined_score = (relevance_score * 0.7) + (quality_score * 0.3)
            
            # Determine grade
            if combined_score > 0.7:
                grade = DocumentGrade.EXCELLENT
            elif combined_score > 0.5:
                grade = DocumentGrade.GOOD
            elif combined_score > 0.3:
                grade = DocumentGrade.FAIR
            elif combined_score > 0.1:
                grade = DocumentGrade.POOR
            else:
                grade = DocumentGrade.INSUFFICIENT
            
            grades[str(i)] = grade
        
        return grades
    
    def _extract_text_content(self, doc: Dict[str, Any]) -> str:
        """Extract text content from document"""
        content = doc.get('content', '')
        if isinstance(content, dict):
            for field in ['text', 'content', 'transcript', 'body', 'data']:
                if field in content and content[field]:
                    return str(content[field])
            return str(content)
        return str(content)
    
    def _calculate_quality_score(self, content: str) -> float:
        """Calculate quality score based on content characteristics"""
        if not content:
            return 0.0
        
        # Length factor (longer content is generally better)
        length_score = min(len(content.split()) / 100, 1.0)
        
        # Keyword quality factor
        quality_keywords = sum(1 for word in self.keyword_weights['excellent'] if word in content.lower())
        quality_score = min(quality_keywords / 5, 1.0)
        
        # Structure factor (sentences, paragraphs)
        sentence_count = content.count('.') + content.count('!') + content.count('?')
        structure_score = min(sentence_count / 10, 1.0)
        
        return (length_score * 0.4) + (quality_score * 0.3) + (structure_score * 0.3)

class DocumentGrader:
    """Grades documents based on relevance and quality with fast fallback"""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.fast_grader = FastDocumentGrader()
        self._use_fast_grading = True  # Use fast grading by default
    
    async def grade_documents(self, question: str, documents: List[Dict[str, Any]]) -> Dict[str, DocumentGrade]:
        """Grade documents based on relevance to the question with fast fallback"""
        if not documents:
            return {}
        
        # Use fast grading by default for performance
        if self._use_fast_grading:
            logger.info("[grade_documents] Using fast heuristic grading")
            return self.fast_grader.grade_documents_fast(question, documents)
        
        # Fallback to LLM grading for high-priority requests
        logger.info("[grade_documents] Using LLM-based grading")
        grades = {}
        
        try:
            # Prepare document summaries for grading (limit to avoid token limits)
            doc_summaries = []
            for i, doc in enumerate(documents[:10]):  # Limit to 10 docs for LLM
                content = doc.get('content', '')
                if isinstance(content, dict):
                    # Extract text from various content fields
                    text = ""
                    for field in ['text', 'content', 'transcript', 'body', 'data']:
                        if field in content and content[field]:
                            text = str(content[field])
                            break
                    if not text:
                        text = str(content)
                else:
                    text = str(content)
                
                # Truncate for grading
                text_preview = text[:300] + "..." if len(text) > 300 else text
                doc_summaries.append(f"Document {i}: {text_preview}")
            
            # Create grading prompt
            system_prompt = """You are an expert document grader. Grade each document based on its relevance to the user's question.
            
            Grade each document as one of:
            - excellent: Highly relevant, directly answers the question
            - good: Relevant, provides useful information
            - fair: Somewhat relevant, may have some useful information
            - poor: Low relevance, limited useful information
            - insufficient: Not relevant or very low quality
            
            Return a JSON object mapping document indices to grades.
            Example: {"0": "excellent", "1": "good", "2": "fair"}
            """
            
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Question: {question}\n\nDocuments:\n" + "\n\n".join(doc_summaries))
            ])
            
            # Parse grades from response
            if isinstance(response.content, str):
                import json
                import re
                
                json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if json_match:
                    grade_dict = json.loads(json_match.group(0))
                    
                    # Convert string grades to enum values
                    for doc_idx, grade_str in grade_dict.items():
                        try:
                            grades[doc_idx] = DocumentGrade(grade_str.lower())
                        except ValueError:
                            grades[doc_idx] = DocumentGrade.FAIR
                            
        except Exception as e:
            logger.error(f"Error grading documents with LLM: {e}")
            # Fallback to fast grading
            return self.fast_grader.grade_documents_fast(question, documents)
        
        return grades
    
    def get_grade_score(self, grade: DocumentGrade) -> float:
        """Convert grade to numerical score"""
        grade_scores = {
            DocumentGrade.EXCELLENT: 1.0,
            DocumentGrade.GOOD: 0.8,
            DocumentGrade.FAIR: 0.6,
            DocumentGrade.POOR: 0.4,
            DocumentGrade.INSUFFICIENT: 0.2
        }
        return grade_scores.get(grade, 0.5)

class EnhancedSelfRAGAgent:
    """
    Enhanced Self-RAG agent with document planning, TF-IDF ranking, and web search
    """
    
    def __init__(self, llm: Optional[ChatOpenAI] = None, performance_mode: str = "balanced"):
        """Initialize the Enhanced SelfRAG Agent.
        
        Args:
            llm: Language model for processing
            performance_mode: "fast", "balanced", or "quality"
                - fast: Maximum speed, minimal LLM calls
                - balanced: Good speed with reasonable quality
                - quality: Maximum quality, more LLM calls
        """
        self.agent = None
        self.llm = llm or ChatOpenAI(model="gpt-4o", temperature=0)
        self.performance_mode = performance_mode
        self.source_types_supported = [
            DocumentType.GONG_TRANSCRIPT,
            DocumentType.GENERIC
        ]
        
        # Initialize document planning components
        self.document_planner = EnhancedDocumentPlanner(llm=self.llm)
        self.document_executor = DocumentPlanExecutor(llm=self.llm)
        self.tfidf_ranker = TFIDFChunkRanker()
        self.document_grader = DocumentGrader(llm=self.llm)
        
        # Initialize DocumentChromaStore for document retrieval
        from app.core.dependencies import get_chromadb_client
        persistent_client = get_chromadb_client()
        self.doc_store = DocumentChromaStore(
            persistent_client=persistent_client,
            collection_name="documents",
            tf_idf=True
        )
        
        # Configure performance settings
        self._configure_performance_settings()
        
        # Initialize Tavily search
        self.tavily_search = tavily_web_search
    
    def _configure_performance_settings(self):
        """Configure performance settings based on mode"""
        if self.performance_mode == "fast":
            # Fast mode: minimal LLM calls, heuristic grading
            self.document_grader._use_fast_grading = True
            self.max_documents = 10
            self.max_chunks = 20
            self.use_web_search = False
            self.use_reflection = False
        elif self.performance_mode == "balanced":
            # Balanced mode: some LLM calls, reasonable limits
            self.document_grader._use_fast_grading = True
            self.max_documents = 15
            self.max_chunks = 30
            self.use_web_search = True
            self.use_reflection = True
        else:  # quality mode
            # Quality mode: more LLM calls, higher limits
            self.document_grader._use_fast_grading = False
            self.max_documents = 25
            self.max_chunks = 50
            self.use_web_search = True
            self.use_reflection = True
        
    # Removed SFDC table methods - using dedicated SQL agents instead
    
    def _init_graph(self) -> "CompiledGraph":
        """Initialize the enhanced Self-RAG workflow graph."""
        start_time = time.time()
        checkpoint_time = checkpoint("Initializing Enhanced SelfRAG Agent", start_time)
        
        # Get API key from settings
        settings = get_settings()
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")

        # Store the latest state for error recovery
        self.latest_state = None
       
        checkpoint_time = checkpoint("Initialized ChatOpenAI model", checkpoint_time)
        
        # Create the state graph for the Self-RAG workflow
        workflow = StateGraph(EnhancedSelfRAGState)
        
        # Define the nodes (enhanced with document planning and grading)
        workflow.add_node("plan_documents", self._plan_documents)
        workflow.add_node("retrieve_chunks", self._retrieve_chunks)
        workflow.add_node("retrieve_full_documents", self._retrieve_full_documents)
        workflow.add_node("grade_documents", self._grade_documents)
        workflow.add_node("rank_with_tfidf", self._rank_with_tfidf)
        workflow.add_node("web_search_fallback", self._web_search_fallback)
        workflow.add_node("analyze_retrieval", self._analyze_retrieval)
        workflow.add_node("query_formation", self._query_formation)
        workflow.add_node("generate_enhanced_answer", self._generate_enhanced_answer)
        workflow.add_node("reflect", self._reflect)
        workflow.add_node("finalize", self._finalize)
        workflow.add_node("check_recursion", self._check_recursion_limit)
        
        # Define the edges
        workflow.set_entry_point("plan_documents")
        
        # After planning, decide retrieval strategy based on planner's recommendation
        workflow.add_conditional_edges(
            "plan_documents",
            self._determine_retrieval_strategy_from_plan,
            {
                RetrievalStrategy.CHUNKS_ONLY: "retrieve_chunks",
                RetrievalStrategy.FULL_DOCS: "retrieve_full_documents",
                RetrievalStrategy.HYBRID: "retrieve_chunks"
            }
        )
        
        # After chunk retrieval, grade documents
        workflow.add_edge("retrieve_chunks", "grade_documents")
        
        # After full document retrieval, grade documents
        workflow.add_edge("retrieve_full_documents", "grade_documents")
        
        # After grading, rank with TF-IDF
        workflow.add_edge("grade_documents", "rank_with_tfidf")
        
        # After ranking, check if we need web search
        workflow.add_conditional_edges(
            "rank_with_tfidf",
            self._needs_web_search,
            {
                True: "web_search_fallback",
                False: "analyze_retrieval"
            }
        )
        
        # After web search, go to analysis
        workflow.add_edge("web_search_fallback", "analyze_retrieval")
        
        # After analysis, check recursion count
        workflow.add_edge("analyze_retrieval", "check_recursion")
        
        # Based on recursion check, decide whether to continue or end
        workflow.add_conditional_edges(
            "check_recursion",
            self._is_recursion_limit_reached,
            {
                True: "finalize",
                False: "analyze_retrieval_decision"
            }
        )
        
        # Add decision point after analyze_retrieval
        workflow.add_node("analyze_retrieval_decision", lambda x: x)
        
        # Based on analysis, decide whether to refine the query or proceed
        workflow.add_conditional_edges(
            "analyze_retrieval_decision",
            self._should_refine_query,
            {
                True: "query_formation",
                False: "generate_enhanced_answer"
            }
        )
        
        # If we refined the query, go back to retrieval
        workflow.add_edge("query_formation", "retrieve_chunks")
        
        # After generating the answer, reflect on it
        workflow.add_edge("generate_enhanced_answer", "reflect")
        
        # Based on reflection, decide whether to finalize or go back for more information
        workflow.add_conditional_edges(
            "reflect",
            self._is_answer_sufficient,
            {
                True: "finalize",
                False: "query_formation"
            }
        )
        
        # Finalize is the end of the process
        workflow.add_edge("finalize", END)
        
        # Compile the graph
        self.agent = workflow.compile()
        checkpoint_time = checkpoint("Compiled Enhanced Self-RAG workflow graph", checkpoint_time)
        
        return self.agent
    
    # Node implementations
    
    def _determine_retrieval_strategy_from_plan_logic(self, plan: DocumentPlan, question: str) -> RetrievalStrategy:
        """Determine retrieval strategy based on planner's analysis and document characteristics."""
        logger.info(f"[_determine_retrieval_strategy_from_plan_logic] Analyzing plan for retrieval strategy")
        
        # Check if plan exists
        if not plan:
            logger.info("[_determine_retrieval_strategy_from_plan_logic] No plan available, defaulting to chunks")
            return RetrievalStrategy.CHUNKS_ONLY
        
        # Analyze question characteristics
        question_lower = question.lower()
        summary_keywords = [
            "summary", "overview", "comprehensive", "complete", "all", "everything",
            "main findings", "key points", "highlights", "summary of", "overview of"
        ]
        
        specific_keywords = [
            "what is", "how much", "when did", "where is", "who is", "specific",
            "exact", "precise", "particular", "specific value", "specific number"
        ]
        
        # Check for summary indicators
        is_summary_question = any(keyword in question_lower for keyword in summary_keywords)
        
        # Check for specific indicators
        is_specific_question = any(keyword in question_lower for keyword in specific_keywords)
        
        # Analyze document characteristics from plan
        documents = plan.retrieval_result.documents if plan.retrieval_result else []
        document_count = len(documents)
        retrieval_grade = plan.retrieval_result.retrieval_grade if plan.retrieval_result else RetrievalGrade.POOR
        
        # Analyze document types and content
        has_diverse_documents = len(set(doc.get('document_type', '') for doc in documents)) > 1
        avg_doc_length = 0
        if documents:
            lengths = []
            for doc in documents:
                content = doc.get('content', '')
                if isinstance(content, dict):
                    text = str(content.get('text', content.get('content', '')))
                else:
                    text = str(content)
                lengths.append(len(text.split()))
            avg_doc_length = sum(lengths) / len(lengths) if lengths else 0
        
        # Decision logic
        if is_summary_question and document_count <= 5 and avg_doc_length > 500:
            # Summary question with few, long documents - use full docs
            logger.info("[_determine_retrieval_strategy_from_plan_logic] Summary question with few long docs -> FULL_DOCS")
            return RetrievalStrategy.FULL_DOCS
            
        elif is_specific_question or retrieval_grade in [RetrievalGrade.EXCELLENT, RetrievalGrade.GOOD]:
            # Specific question or high-quality retrieval - use chunks
            logger.info("[_determine_retrieval_strategy_from_plan_logic] Specific question or high-quality retrieval -> CHUNKS_ONLY")
            return RetrievalStrategy.CHUNKS_ONLY
            
        elif document_count > 10 or has_diverse_documents:
            # Many documents or diverse types - use chunks for better precision
            logger.info("[_determine_retrieval_strategy_from_plan_logic] Many/diverse documents -> CHUNKS_ONLY")
            return RetrievalStrategy.CHUNKS_ONLY
            
        elif avg_doc_length < 300:
            # Short documents - use full docs
            logger.info("[_determine_retrieval_strategy_from_plan_logic] Short documents -> FULL_DOCS")
            return RetrievalStrategy.FULL_DOCS
            
        else:
            # Default to chunks for better precision
            logger.info("[_determine_retrieval_strategy_from_plan_logic] Default case -> CHUNKS_ONLY")
            return RetrievalStrategy.CHUNKS_ONLY
    
    def _determine_retrieval_strategy_from_plan(self, state: EnhancedSelfRAGState) -> RetrievalStrategy:
        """Determine retrieval strategy based on the document plan."""
        return state.retrieval_strategy
    
    async def _retrieve_chunks(self, state: EnhancedSelfRAGState) -> EnhancedSelfRAGState:
        """Retrieve document chunks using TF-IDF for specific queries with performance optimizations."""
        logger.info(f"[_retrieve_chunks] Retrieving chunks for question: {state.question}")
        
        try:
            # Use document planning to get relevant documents
            if state.document_plan and state.document_plan.retrieval_result.documents:
                # Use documents from the plan
                documents = state.document_plan.retrieval_result.documents
                logger.info(f"[_retrieve_chunks] Using {len(documents)} documents from plan")
                
                # Use planner's retrieval quality to determine chunk size
                retrieval_grade = state.document_plan.retrieval_result.retrieval_grade
                if retrieval_grade in [RetrievalGrade.EXCELLENT, RetrievalGrade.GOOD]:
                    chunk_size = 300  # Smaller chunks for high-quality retrieval
                else:
                    chunk_size = 500  # Standard chunks for lower quality
                    
            else:
                # Fallback to regular retrieval
                query = state.current_query or state.question
                documents = self._get_documents_query(query, 25)
                logger.info(f"[_retrieve_chunks] Retrieved {len(documents)} documents from query")
                chunk_size = 500  # Default chunk size
            
            # Limit documents for performance (process top 15 most relevant)
            documents = documents[:15]
            
            # Extract chunks from documents in parallel
            chunks = await self._extract_chunks_parallel(documents, chunk_size)
            
            state.retrieved_chunks = chunks
            logger.info(f"[_retrieve_chunks] Extracted {len(chunks)} chunks from {len(documents)} documents (chunk_size: {chunk_size})")
            
        except Exception as e:
            logger.error(f"[_retrieve_chunks] Error retrieving chunks: {e}")
            state.retrieved_chunks = []
        
        return state
    
    async def _extract_chunks_parallel(self, documents: List[Dict[str, Any]], chunk_size: int) -> List[Dict[str, Any]]:
        """Extract chunks from documents in parallel for better performance"""
        import asyncio
        
        async def extract_doc_chunks(doc):
            """Extract chunks from a single document"""
            content = doc.get('content', '')
            if isinstance(content, dict):
                # Extract text from various content fields
                text = ""
                for field in ['text', 'content', 'transcript', 'body', 'data']:
                    if field in content and content[field]:
                        text = str(content[field])
                        break
                if not text:
                    text = str(content)
            else:
                text = str(content)
            
            # Split into chunks
            words = text.split()
            doc_chunks = []
            for i in range(0, len(words), chunk_size):
                chunk_text = ' '.join(words[i:i + chunk_size])
                if chunk_text.strip():
                    doc_chunks.append({
                        'document_id': doc.get('document_id', ''),
                        'document_type': doc.get('document_type', 'generic'),
                        'content': chunk_text,
                        'chunk_index': i // chunk_size,
                        'metadata': doc.get('metadata', {}),
                        'relevance_score': doc.get('relevance_score', 0.0),
                        'source_document': doc
                    })
            return doc_chunks
        
        # Process documents in parallel (limit concurrency)
        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent operations
        
        async def process_with_semaphore(doc):
            async with semaphore:
                return await extract_doc_chunks(doc)
        
        # Execute parallel chunk extraction
        tasks = [process_with_semaphore(doc) for doc in documents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results and filter out exceptions
        chunks = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Error extracting chunks from document: {result}")
            else:
                chunks.extend(result)
        
        return chunks
    
    async def _grade_documents(self, state: EnhancedSelfRAGState) -> EnhancedSelfRAGState:
        """Grade documents based on relevance and quality."""
        logger.info(f"[_grade_documents] Grading documents")
        
        # Determine which documents to grade
        documents_to_grade = []
        if state.retrieval_strategy == RetrievalStrategy.CHUNKS_ONLY:
            documents_to_grade = state.retrieved_chunks
        else:
            documents_to_grade = state.retrieved_documents
        
        if not documents_to_grade:
            logger.warning("[_grade_documents] No documents to grade")
            return state
        
        try:
            # Grade documents
            grades = await self.document_grader.grade_documents(state.question, documents_to_grade)
            state.document_grades = grades
            
            # Log grading results
            grade_counts = {}
            for grade in grades.values():
                grade_counts[grade.value] = grade_counts.get(grade.value, 0) + 1
            
            logger.info(f"[_grade_documents] Graded {len(grades)} documents: {grade_counts}")
            
        except Exception as e:
            logger.error(f"[_grade_documents] Error grading documents: {e}")
            # Default grades
            for i in range(len(documents_to_grade)):
                state.document_grades[str(i)] = DocumentGrade.FAIR
        
        return state
    
    async def _plan_documents(self, state: EnhancedSelfRAGState) -> EnhancedSelfRAGState:
        """Create a document plan using the enhanced planner and determine retrieval strategy."""
        logger.info(f"[_plan_documents] Creating document plan for question: {state.question}")
        
        try:
            # Create document plan
            plan = await self.document_planner.plan(
                question=state.question,
                document_type=None,  # Let planner determine
                source_type=state.source,
                max_documents=25,
                chat_history=state.chat_history
            )
            
            state.document_plan = plan
            state.action_taken = f"Created {plan.strategy.value} plan with {plan.confidence:.2f} confidence"
            
            # Determine retrieval strategy based on planner's analysis
            retrieval_strategy = self._determine_retrieval_strategy_from_plan_logic(plan, state.question)
            state.retrieval_strategy = retrieval_strategy
            
            logger.info(f"[_plan_documents] Plan created: {plan.strategy} with confidence {plan.confidence}")
            logger.info(f"[_plan_documents] Retrieval grade: {plan.retrieval_result.retrieval_grade}")
            logger.info(f"[_plan_documents] Documents found: {len(plan.retrieval_result.documents)}")
            logger.info(f"[_plan_documents] Determined retrieval strategy: {retrieval_strategy}")
            
        except Exception as e:
            logger.error(f"[_plan_documents] Error creating plan: {e}")
            # Create a basic plan as fallback
            state.document_plan = None
            state.retrieval_strategy = RetrievalStrategy.CHUNKS_ONLY  # Default to chunks
            state.action_taken = "Failed to create plan, using basic chunk retrieval"
        
        return state
    
    async def _retrieve_documents(self, state: EnhancedSelfRAGState) -> EnhancedSelfRAGState:
        """Retrieve documents based on the plan or query."""
        logger.info(f"[_retrieve_documents] Retrieving documents")
        
        if state.document_plan and state.document_plan.retrieval_result.documents:
            # Use documents from the plan
            logger.info(f"[_retrieve_documents] Using {len(state.document_plan.retrieval_result.documents)} documents from plan")
            state.retrieved_documents = [
                {
                    'document_id': str(doc.document_id),
                    'document_type': doc.document_type,
                    'content': doc.content,
                    'metadata': {},
                    'relevance_score': 0.8,  # Default score
                    'collection': 'planned'
                }
                for doc in state.document_plan.retrieval_result.documents
            ]
        else:
            # Fallback to regular retrieval
            logger.info(f"[_retrieve_documents] Using fallback retrieval")
            query = state.current_query or state.question
            state.retrieved_documents = self._get_documents_query(query, 25)
        
        logger.info(f"[_retrieve_documents] Retrieved {len(state.retrieved_documents)} documents")
        return state
    
    async def _rank_with_tfidf(self, state: EnhancedSelfRAGState) -> EnhancedSelfRAGState:
        """Rank documents/chunks using TF-IDF for better relevance scoring."""
        logger.info(f"[_rank_with_tfidf] Ranking with TF-IDF")
        
        # Determine what to rank based on retrieval strategy
        items_to_rank = []
        if state.retrieval_strategy == RetrievalStrategy.CHUNKS_ONLY:
            items_to_rank = state.retrieved_chunks
            logger.info(f"[_rank_with_tfidf] Ranking {len(items_to_rank)} chunks")
        else:
            items_to_rank = state.retrieved_documents
            logger.info(f"[_rank_with_tfidf] Ranking {len(items_to_rank)} documents")
        
        if not items_to_rank:
            logger.warning("[_rank_with_tfidf] No items to rank")
            return state
        
        try:
            # Extract texts for TF-IDF
            texts = []
            for item in items_to_rank:
                content = item.get('content', '')
                if isinstance(content, dict):
                    # Extract text from various content fields
                    text = ""
                    for field in ['text', 'content', 'transcript', 'body', 'data']:
                        if field in content and content[field]:
                            text = str(content[field])
                            break
                    if not text:
                        text = str(content)
                else:
                    text = str(content)
                texts.append(text)
            
            # Fit TF-IDF and get scores
            query = state.current_query or state.question
            tfidf_scores = self.tfidf_ranker.get_relevance_scores(query, texts)
            
            # Update items with TF-IDF scores and document grades
            for i, item in enumerate(items_to_rank):
                tfidf_score = tfidf_scores[i] if i < len(tfidf_scores) else 0.0
                item['tfidf_score'] = tfidf_score
                
                # Get document grade score
                grade_score = 0.5  # Default
                if str(i) in state.document_grades:
                    grade_score = self.document_grader.get_grade_score(state.document_grades[str(i)])
                
                # Combine scores: semantic (40%) + TF-IDF (40%) + grade (20%)
                semantic_score = item.get('relevance_score', 0.0)
                combined_score = (semantic_score * 0.4) + (tfidf_score * 0.4) + (grade_score * 0.2)
                item['combined_score'] = combined_score
                
                # Add grade information
                if str(i) in state.document_grades:
                    item['document_grade'] = state.document_grades[str(i)].value
            
            # Sort by combined score
            items_to_rank.sort(key=lambda x: x.get('combined_score', 0.0), reverse=True)
            
            # Update state with ranked items
            if state.retrieval_strategy == RetrievalStrategy.CHUNKS_ONLY:
                state.retrieved_chunks = items_to_rank
                logger.info(f"[_rank_with_tfidf] Chunks ranked, top scores: {[chunk.get('combined_score', 0.0) for chunk in items_to_rank[:3]]}")
            else:
                state.retrieved_documents = items_to_rank
                logger.info(f"[_rank_with_tfidf] Documents ranked, top scores: {[doc.get('combined_score', 0.0) for doc in items_to_rank[:3]]}")
            
        except Exception as e:
            logger.error(f"[_rank_with_tfidf] Error ranking items: {e}")
        
        return state
    
    def _needs_web_search(self, state: EnhancedSelfRAGState) -> bool:
        """Determine if web search is needed based on document quality and performance settings."""
        # Skip web search in fast mode
        if not self.use_web_search:
            logger.info("[_needs_web_search] Web search disabled in fast mode")
            return False
        
        # Check available sources
        available_sources = 0
        avg_score = 0.0
        
        if state.retrieval_strategy == RetrievalStrategy.CHUNKS_ONLY:
            available_sources = len(state.retrieved_chunks)
            if state.retrieved_chunks:
                top_scores = [chunk.get('combined_score', 0.0) for chunk in state.retrieved_chunks[:3]]
                avg_score = sum(top_scores) / len(top_scores) if top_scores else 0.0
        else:
            available_sources = len(state.retrieved_documents)
            if state.retrieved_documents:
                top_scores = [doc.get('combined_score', 0.0) for doc in state.retrieved_documents[:3]]
                avg_score = sum(top_scores) / len(top_scores) if top_scores else 0.0
        
        # Adjust thresholds based on performance mode
        if self.performance_mode == "fast":
            min_sources = 1
            min_score = 0.2
        elif self.performance_mode == "balanced":
            min_sources = 2
            min_score = 0.3
        else:  # quality mode
            min_sources = 3
            min_score = 0.4
        
        # Check if we have sufficient high-quality sources
        if available_sources == 0:
            needs_search = True
        elif available_sources < min_sources:
            needs_search = True
        elif avg_score < min_score:
            needs_search = True
        else:
            needs_search = False
        
        logger.info(f"[_needs_web_search] Sources: {available_sources}, avg score: {avg_score:.3f}, needs web search: {needs_search}")
        return needs_search
    
    async def _web_search_fallback(self, state: EnhancedSelfRAGState) -> EnhancedSelfRAGState:
        """Perform web search as fallback when documents are insufficient."""
        logger.info(f"[_web_search_fallback] Performing web search for query: {state.question}")
        
        try:
            # Use Tavily search
            web_results = await self.tavily_search(state.question, max_results=5)
            
            # Convert to WebSearchResult objects
            state.web_search_results = [
                WebSearchResult(
                    title=result.get("title", ""),
                    content=result.get("content", ""),
                    url=result.get("url", ""),
                    relevance_score=result.get("score", 0.0)
                )
                for result in web_results
            ]
            
            logger.info(f"[_web_search_fallback] Found {len(state.web_search_results)} web results")
            state.action_taken += f" + Web search ({len(state.web_search_results)} results)"
            
        except Exception as e:
            logger.error(f"[_web_search_fallback] Error in web search: {e}")
            state.web_search_results = []
        
        return state
    
    async def _analyze_retrieval(self, state: EnhancedSelfRAGState) -> EnhancedSelfRAGState:
        """Analyze the retrieval results including web search."""
        logger.info("[_analyze_retrieval] Analyzing retrieval results")
        
        # Combine document and web results for analysis
        total_sources = len(state.retrieved_documents) + len(state.web_search_results)
        
        if total_sources == 0:
            state.reflection = "No relevant sources found in documents or web search."
            return state
        
        # Analyze document quality
        doc_scores = [doc.get('combined_score', 0.0) for doc in state.retrieved_documents]
        avg_doc_score = sum(doc_scores) / len(doc_scores) if doc_scores else 0.0
        
        # Analyze web search quality
        web_scores = [result.relevance_score for result in state.web_search_results]
        avg_web_score = sum(web_scores) / len(web_scores) if web_scores else 0.0
        
        # Determine overall quality
        if avg_doc_score >= 0.5 or avg_web_score >= 0.7:
            state.reflection = f"Good quality sources found. Document avg: {avg_doc_score:.2f}, Web avg: {avg_web_score:.2f}"
        elif avg_doc_score >= 0.3 or avg_web_score >= 0.5:
            state.reflection = f"Moderate quality sources found. Document avg: {avg_doc_score:.2f}, Web avg: {avg_web_score:.2f}"
        else:
            state.reflection = f"Low quality sources. Document avg: {avg_doc_score:.2f}, Web avg: {avg_web_score:.2f}. May need query refinement."
        
        logger.info(f"[_analyze_retrieval] Analysis complete: {state.reflection}")
        return state
    
    async def _retrieve_full_documents(self, state: EnhancedSelfRAGState) -> EnhancedSelfRAGState:
        """Retrieve full content of selected documents (limited to 5 for summary questions)."""
        logger.info(f"[_retrieve_full_documents] Retrieving full content for summary question")
        
        selected_docs = []
        
        # Use documents from planner if available, otherwise use retrieved_documents
        if state.document_plan and state.document_plan.retrieval_result.documents:
            documents = state.document_plan.retrieval_result.documents
            logger.info(f"[_retrieve_full_documents] Using {len(documents)} documents from plan")
        else:
            documents = state.retrieved_documents
            logger.info(f"[_retrieve_full_documents] Using {len(documents)} documents from retrieval")
        
        # For summary questions, limit to 5 documents
        max_docs = 5
        top_docs = documents[:max_docs]
        
        logger.info(f"[_retrieve_full_documents] Processing {len(top_docs)} documents (limited to {max_docs} for summary)")
        
        for doc in top_docs:
            try:
                doc_id = doc.get('document_id', '')
                doc_type = doc.get('document_type', 'generic')
                
                # Create RetrievedDocument with enhanced metadata
                retrieved_doc = RetrievedDocument(
                    document_id=doc_id,
                    document_type=doc_type,
                    content=doc.get('content', {}),
                    relevance_score=doc.get('relevance_score', 0.0),
                    tfidf_score=doc.get('tfidf_score', 0.0),
                    metadata=doc.get('metadata', {}),
                    insights=doc.get('insights', []),
                    source_type="document",
                    citation_info={
                        "source": "document",
                        "document_id": doc_id,
                        "document_type": doc_type,
                        "relevance_score": doc.get('combined_score', 0.0),
                        "document_grade": doc.get('document_grade', 'fair'),
                        "planner_grade": state.document_plan.retrieval_result.retrieval_grade.value if state.document_plan else "unknown"
                    }
                )
                selected_docs.append(retrieved_doc)
                
            except Exception as e:
                logger.error(f"Error processing document {doc.get('document_id', 'unknown')}: {e}")
        
        # Add web search results as documents (limit to 2 for summary)
        for i, web_result in enumerate(state.web_search_results[:2]):
            web_doc = RetrievedDocument(
                document_id=f"web_{i}",
                document_type="web",
                content={"text": web_result.content, "title": web_result.title},
                relevance_score=web_result.relevance_score,
                tfidf_score=0.0,
                metadata={"url": web_result.url, "title": web_result.title},
                insights=[],
                source_type="web",
                web_url=web_result.url,
                citation_info={
                    "source": "web",
                    "url": web_result.url,
                    "title": web_result.title,
                    "relevance_score": web_result.relevance_score
                }
            )
            selected_docs.append(web_doc)
        
        state.selected_documents = selected_docs
        logger.info(f"[_retrieve_full_documents] Retrieved {len(selected_docs)} full documents for summary")
        return state
    
    async def _generate_enhanced_answer(self, state: EnhancedSelfRAGState) -> EnhancedSelfRAGState:
        """Generate enhanced answer with formatted output and metadata."""
        logger.info("[_generate_enhanced_answer] Generating enhanced answer")
        
        system_prompt = """You are an expert document analyst that provides comprehensive, well-formatted answers.
        
        Based on the retrieved documents, web search results, and any additional data, provide a detailed answer to the user's question.
        
        Your response should include:
        1. A clear, structured answer to the question
        2. Specific citations and references
        3. Metadata about sources used
        4. Confidence level in the answer
        5. Any limitations or gaps in information
        
        Format your response as JSON with this structure:
        {
            "answer": "Main answer content in markdown format",
            "sources": [
                {
                    "type": "document|web|sfdc",
                    "id": "source_id",
                    "title": "source_title",
                    "url": "source_url_if_available",
                    "relevance_score": 0.85,
                    "excerpt": "relevant_excerpt"
                }
            ],
            "metadata": {
                "confidence": 0.85,
                "sources_used": 5,
                "document_sources": 3,
                "web_sources": 2,
                "limitations": ["list of limitations if any"]
            },
            "action_summary": "Brief summary of actions taken"
        }
        """
        
        # Prepare context based on retrieval strategy
        context_parts = []
        
        if state.retrieval_strategy == RetrievalStrategy.CHUNKS_ONLY:
            # Add chunk context
            context_parts.append("--- Relevant Document Chunks ---")
            for i, chunk in enumerate(state.retrieved_chunks[:10]):  # Limit to top 10 chunks
                context_parts.append(f"Chunk {i+1} (Document: {chunk.get('document_id', 'unknown')}):")
                context_parts.append(f"Relevance: {chunk.get('combined_score', 0.0):.2f}")
                context_parts.append(f"Grade: {chunk.get('document_grade', 'fair')}")
                context_parts.append(f"Content: {chunk.get('content', '')[:300]}...")
                context_parts.append("")
        else:
            # Add full document context
            for doc in state.selected_documents:
                if doc.source_type == "document":
                    context_parts.append(f"--- Document: {doc.document_id} ---")
                    context_parts.append(f"Type: {doc.document_type}")
                    context_parts.append(f"Relevance: {doc.relevance_score:.2f}")
                    context_parts.append(f"Grade: {doc.citation_info.get('document_grade', 'fair')}")
                    context_parts.append(f"Content: {str(doc.content)[:500]}...")
                    if doc.metadata:
                        context_parts.append(f"Metadata: {doc.metadata}")
                elif doc.source_type == "web":
                    context_parts.append(f"--- Web Source: {doc.metadata.get('title', 'Unknown')} ---")
                    context_parts.append(f"URL: {doc.web_url}")
                    context_parts.append(f"Relevance: {doc.relevance_score:.2f}")
                    context_parts.append(f"Content: {str(doc.content)[:500]}...")
        
        # Add web search results if available
        if state.web_search_results:
            context_parts.append("--- Web Search Results ---")
            for i, web_result in enumerate(state.web_search_results[:3]):
                context_parts.append(f"Web Source {i+1}: {web_result.title}")
                context_parts.append(f"URL: {web_result.url}")
                context_parts.append(f"Relevance: {web_result.relevance_score:.2f}")
                context_parts.append(f"Content: {web_result.content[:300]}...")
                context_parts.append("")
        
        context = "\n".join(context_parts)
        
        try:
            answer_response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Question: {state.question}\n\nContext:\n{context}\n\nGenerate enhanced answer:")
            ])
            
            if isinstance(answer_response.content, str):
                # Try to parse JSON response
                try:
                    json_match = re.search(r'\{.*\}', answer_response.content, re.DOTALL)
                    if json_match:
                        answer_data = json.loads(json_match.group(0))
                        state.answer = answer_data.get("answer", answer_response.content)
                        state.metadata_summary = answer_data.get("metadata", {})
                    else:
                        state.answer = answer_response.content
                        state.metadata_summary = self._create_metadata_summary(state)
                except json.JSONDecodeError:
                    state.answer = answer_response.content
                    state.metadata_summary = self._create_metadata_summary(state)
            else:
                state.answer = "I couldn't generate a proper answer based on the available information."
                state.metadata_summary = {"confidence": 0.3, "sources_used": 0}
                
        except Exception as e:
            logger.error(f"Error generating enhanced answer: {e}")
            state.answer = f"I encountered an error while analyzing your question. Please try again."
            state.metadata_summary = {"confidence": 0.1, "sources_used": 0}
        
        return state
    
    def _create_metadata_summary(self, state: EnhancedSelfRAGState) -> Dict[str, Any]:
        """Create comprehensive metadata summary for the response."""
        return {
            "question_type": state.question_type.value,
            "retrieval_strategy": state.retrieval_strategy.value,
            "documents_used": len(state.selected_documents),
            "chunks_used": len(state.retrieved_chunks) if state.retrieval_strategy == RetrievalStrategy.CHUNKS_ONLY else 0,
            "web_sources_used": len(state.web_search_results),
            "action_taken": state.action_taken,
            "document_grades": {k: v.value for k, v in state.document_grades.items()},
            "planner_info": {
                "strategy": state.document_plan.strategy.value if state.document_plan else "none",
                "confidence": state.document_plan.confidence if state.document_plan else 0.0,
                "retrieval_grade": state.document_plan.retrieval_result.retrieval_grade.value if state.document_plan and state.document_plan.retrieval_result else "unknown"
            },
            "citations": []
        }
    
    # Helper methods (implementations from original agent)
    def _get_documents_query(self, query: str, n_results: int = 25) -> List[Dict[str, Any]]:
        """Query the document store for documents matching the query using DocumentChromaStore."""
        logger.info(f"Querying documents with query: '{query}'")
        
        try:
            # Use time-based filtering for recent documents
            now = datetime.now()
            timestamp_120_days_ago = (now - timedelta(days=120)).timestamp()
            logger.info(f"Filtering documents newer than {timestamp_120_days_ago} ({datetime.fromtimestamp(timestamp_120_days_ago)})")
            
            # Query documents with time-based filtering
            try:
                results = self.doc_store.semantic_search(
                    query=query,
                    n_results=n_results,
                    filter={"date_timestamp": {"$gt": timestamp_120_days_ago}}
                )
                
                # If no results with timestamp filter, fall back to unfiltered search
                if not results or len(results) == 0:
                    logger.warning("No results found with date_timestamp filter, falling back to unfiltered search")
                    results = self.doc_store.semantic_search(
                        query=query,
                        n_results=n_results
                    )
                    
            except Exception as filter_err:
                logger.error(f"Error with date-filtered query: {filter_err}, falling back to unfiltered query")
                results = self.doc_store.semantic_search(
                    query=query,
                    n_results=n_results
                )
            
            logger.info(f"Found {len(results)} results from DocumentChromaStore")
            
            # Convert results to expected format
            documents = []
            for result in results:
                doc = {
                    'document_id': result.get('document_id', ''),
                    'document_type': result.get('document_type', 'generic'),
                    'content': result.get('content', {}),
                    'metadata': result.get('metadata', {}),
                    'relevance_score': result.get('relevance_score', 0.0),
                    'collection': 'documents'  # DocumentChromaStore uses documents collection
                }
                documents.append(doc)
            
            # Log relevance score statistics
            if documents:
                rel_scores = [doc.get('relevance_score', 0) for doc in documents]
                logger.info(f"Relevance scores - min: {min(rel_scores):.4f}, max: {max(rel_scores):.4f}, avg: {sum(rel_scores)/len(rel_scores):.4f}")
                logger.info(f"Top 5 relevance scores: {rel_scores[:5]}")
            
            # Sort documents by relevance score
            sorted_documents = sorted(documents, key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            logger.info(f"Total documents found: {len(sorted_documents)}")
            return sorted_documents
            
        except Exception as e:
            logger.error(f"Error querying DocumentChromaStore: {e}")
            return []
    
    # Other helper methods from original agent (abbreviated for space)
    def _should_refine_query(self, state: EnhancedSelfRAGState) -> bool:
        """Determine if we should refine the query based on the analysis."""
        logger.info("[_should_refine_query] Evaluating if query refinement is needed")
        
        # Skip refinement if specific document IDs are provided
        if state.document_ids:
            logger.info("[_should_refine_query] Specific document IDs provided, skipping refinement")
            return False
        
        # Check available sources based on retrieval strategy
        available_sources = 0
        avg_score = 0.0
        
        if state.retrieval_strategy == RetrievalStrategy.CHUNKS_ONLY:
            available_sources = len(state.retrieved_chunks)
            if state.retrieved_chunks:
                scores = [chunk.get('combined_score', 0.0) for chunk in state.retrieved_chunks[:10]]
                avg_score = sum(scores) / len(scores) if scores else 0.0
        else:
            available_sources = len(state.retrieved_documents)
            if state.retrieved_documents:
                scores = [doc.get('combined_score', 0.0) for doc in state.retrieved_documents[:5]]
                avg_score = sum(scores) / len(scores) if scores else 0.0
        
        # Check if we have enough relevant sources
        if available_sources < 2:
            logger.info("[_should_refine_query] Too few sources retrieved, refinement needed")
            return True
            
        # Check if the relevance scores are too low
        if avg_score < 0.3:
            logger.info(f"[_should_refine_query] Low average score: {avg_score:.3f}, refinement needed")
            return True
            
        # If there's a clear indication in the reflection that we need to refine
        if "not relevant" in state.reflection.lower() or "reformulate" in state.reflection.lower():
            logger.info("[_should_refine_query] Reflection indicates need for refinement")
            return True
            
        logger.info("[_should_refine_query] Retrieval results are sufficient, no refinement needed")
        return False
    
    # Removed SFDC data checking - using dedicated SQL agents instead
    
    def _is_recursion_limit_reached(self, state: EnhancedSelfRAGState) -> bool:
        """Check if recursion limit is reached."""
        return state.recursion_count >= 2
    
    def _is_answer_sufficient(self, state: EnhancedSelfRAGState) -> bool:
        """Determine if the answer is sufficient."""
        return not state.needs_more_info
    
    async def _check_recursion_limit(self, state: EnhancedSelfRAGState) -> EnhancedSelfRAGState:
        """Check recursion limit."""
        state.recursion_count += 1
        return state
    
    async def _query_formation(self, state: EnhancedSelfRAGState) -> EnhancedSelfRAGState:
        """Reformulate the query."""
        if state.recursion_count >= 2:
            return state
        
        state.recursion_count += 1
        
        system_prompt = """You are an expert at query reformulation.
        Reformulate the query to be more specific and targeted.
        Use these words in your reformulation: ["opportunity", "deal", "sales", "pipeline", "forecast", 
                        "revenue", "salesforce", "account", "close date", "account","lead","activity","task","contact","associate","sales rep"]
        Return only the reformulated query as plain text."""
        
        try:
            query_response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Original question: {state.question}\nPrevious query: {state.current_query}\nReformulate:")
            ])
            
            if isinstance(query_response.content, str):
                state.current_query = query_response.content.strip()
                state.query_type = QueryType.REFINED
        except Exception as e:
            logger.error(f"Error reformulating query: {e}")
        
        return state
    
    # Removed SFDC query methods - using dedicated SQL agents instead
    
    async def _reflect(self, state: EnhancedSelfRAGState) -> EnhancedSelfRAGState:
        """Reflect on the answer quality."""
        # Skip reflection in fast mode
        if not self.use_reflection:
            logger.info("[_reflect] Reflection disabled in fast mode")
            state.reflection = "Reflection skipped for performance"
            state.needs_more_info = False
            return state
        
        system_prompt = """Evaluate if the answer properly addresses the user's question.
        Consider completeness, accuracy, and source support.
        Return JSON: {"sufficient": true/false, "reasoning": "explanation"}"""
        
        try:
            reflection_response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Question: {state.question}\nAnswer: {state.answer}\nEvaluate:")
            ])
            
            if isinstance(reflection_response.content, str):
                json_match = re.search(r'\{.*\}', reflection_response.content, re.DOTALL)
                if json_match:
                    reflection = json.loads(json_match.group(0))
                    state.reflection = reflection.get("reasoning", "")
                    state.needs_more_info = not reflection.get("sufficient", True)
        except Exception as e:
            logger.error(f"Error reflecting on answer: {e}")
            state.needs_more_info = False
        
        return state
    
    async def _finalize(self, state: EnhancedSelfRAGState) -> EnhancedSelfRAGState:
        """Finalize the answer with enhanced formatting."""
        if state.needs_more_info:
            state.final_answer = state.answer + "\n\n*Note: Some information might be missing or incomplete.*"
        else:
            state.final_answer = state.answer
        
        # Add metadata summary
        if state.metadata_summary:
            metadata_text = f"\n\n--- Analysis Summary ---\n"
            metadata_text += f"Confidence: {state.metadata_summary.get('confidence', 0.0):.1%}\n"
            metadata_text += f"Sources Used: {state.metadata_summary.get('sources_used', 0)}\n"
            metadata_text += f"Action Taken: {state.action_taken}\n"
            
            if state.metadata_summary.get('limitations'):
                metadata_text += f"Limitations: {', '.join(state.metadata_summary['limitations'])}\n"
            
            state.final_answer += metadata_text
        
        return state
    
    # Main execution method
    async def run_agent(
        self, 
        messages: List[Dict[str, Any]], 
        question: str, 
        source_type: Union[DocumentType, str],
        document_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run the enhanced agent with the given messages and prompt."""
        start_time = time.time()
        logger.info("="*50)
        logger.info(f"ENHANCED SELF-RAG AGENT STARTED - Question: '{question}'")
        logger.info(f"Source type: {source_type}")
        logger.info(f"Chat history length: {len(messages)}")
        if document_ids:
            logger.info(f"Using specific document IDs: {document_ids}")
        logger.info("="*50)
        
        # Initialize the agent if it doesn't exist
        if self.agent is None:
            logger.info("Initializing Enhanced Self-RAG agent graph")
            self.agent = self._init_graph()
            logger.info("Enhanced Self-RAG agent graph initialized successfully")

        # Convert source_type to string
        source = source_type.value if isinstance(source_type, DocumentType) else source_type

        # Prepare initial state
        state = EnhancedSelfRAGState(
            question=question,
            chat_history=messages,
            current_query=question,
            source=source,
            document_ids=document_ids or []
        )
        
        self.latest_state = state
        logger.info(f"Initial state created with question: {question}")
        
        # Run the agent
        try:
            logger.info(f"Starting enhanced agent execution with question: {question}")
            result = await self.agent.ainvoke(state)
            logger.info(f"Enhanced agent execution completed")
            
            # Format the response
            response = self._format_enhanced_response(result)
            logger.info(f"Formatted enhanced response")
            
            return response
            
        except Exception as e:
            logger.error(f"ERROR IN ENHANCED SELF-RAG AGENT: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Return error response
            return {
                "messages": [
                    {
                        "message_type": "ai",
                        "message_content": f"I encountered an error while processing your request: {str(e)}. Please try again.",
                        "message_id": f"ai_error_{int(time.time())}",
                        "message_extra": {}
                    }
                ]
            }
    
    def _format_enhanced_response(self, result: Any) -> Dict[str, Any]:
        """Format the enhanced agent's response."""
        if not isinstance(result, EnhancedSelfRAGState):
            logger.error(f"Unexpected result type: {type(result)}")
            return {
                "messages": [
                    {
                        "message_type": "ai",
                        "message_content": "I encountered an error processing your request. Please try again.",
                        "message_id": f"ai_error_{int(time.time())}",
                        "message_extra": {}
                    }
                ]
            }
        
        # Create enhanced response with metadata
        message_content = result.final_answer
        
        # Add source citations
        citations = []
        for doc in result.selected_documents:
            if doc.source_type == "document":
                citations.append({
                    "type": "document",
                    "id": doc.document_id,
                    "title": f"Document {doc.document_id}",
                    "relevance_score": doc.relevance_score
                })
            elif doc.source_type == "web":
                citations.append({
                    "type": "web",
                    "url": doc.web_url,
                    "title": doc.metadata.get("title", "Web Source"),
                    "relevance_score": doc.relevance_score
                })
        
        # Add citations as JSON
        if citations:
            message_content += f"\n\n```json\n{{'sources': {citations}}}\n```"
        
        # Create the response message
        response = {
            "messages": [
                {
                    "message_type": "ai",
                    "message_content": message_content,
                    "message_id": f"ai_{int(time.time())}",
                    "message_extra": {
                        "metadata": result.metadata_summary,
                        "action_taken": result.action_taken,
                        "sources_count": len(result.selected_documents)
                    }
                }
            ]
        }
        
        return response
