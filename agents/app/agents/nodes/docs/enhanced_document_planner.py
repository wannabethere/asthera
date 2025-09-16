import logging
import time
import asyncio
import json
import re
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

# Import document models and services
from app.services.docs.docmodels import Document, DocumentInsight, DocumentVersion, DocumentInsightVersion
from app.services.docs.document_persistence_service import DocumentPersistenceService
from app.storage.documents import DocumentChromaStore

logger = logging.getLogger("EnhancedDocumentPlanner")

class RetrievalGrade(Enum):
    """Grades for document retrieval quality"""
    EXCELLENT = "excellent"  # Highly relevant, comprehensive
    GOOD = "good"           # Relevant, some gaps
    FAIR = "fair"           # Partially relevant, significant gaps
    POOR = "poor"           # Low relevance, major gaps
    INSUFFICIENT = "insufficient"  # No relevant documents found

class DocumentRetrievalResult(BaseModel):
    """Result of document retrieval with grading"""
    documents: List[Document]
    insights: List[DocumentInsight]
    retrieval_grade: RetrievalGrade
    relevance_scores: List[float]
    coverage_analysis: Dict[str, Any]
    gaps_identified: List[str]
    recommendations: List[str]

class DocumentRetrievalService:
    """Service for retrieving and grading documents using docmodels"""
    
    def __init__(self, 
                 document_service: DocumentPersistenceService = None,
                 chroma_store: DocumentChromaStore = None):
        self.document_service = document_service
        self.chroma_store = chroma_store
        
    async def retrieve_documents(self, 
                                query: str,
                                document_type: Optional[str] = None,
                                source_type: Optional[str] = None,
                                domain_id: Optional[str] = None,
                                max_documents: int = 25) -> DocumentRetrievalResult:
        """
        Retrieve documents using multiple strategies and grade the results
        
        Args:
            query: Search query
            document_type: Filter by document type
            source_type: Filter by source type
            domain_id: Filter by domain
            max_documents: Maximum number of documents to retrieve
            
        Returns:
            DocumentRetrievalResult with graded retrieval
        """
        logger.info(f"Retrieving documents for query: {query}")
        
        # Strategy 1: Database search using DocumentPersistenceService
        db_documents = []
        if self.document_service:
            try:
                db_documents = await self.document_service.search_documents(
                    query=query,
                    document_type=document_type,
                    source_type=source_type,
                    domain_id=domain_id,
                    limit=max_documents // 2
                )
                logger.info(f"Retrieved {len(db_documents)} documents from database")
            except Exception as e:
                logger.error(f"Error retrieving documents from database: {e}")
        
        # Strategy 2: Vector search using ChromaDB
        vector_documents = []
        vector_insights = []
        if self.chroma_store:
            try:
                # Search for document insights
                search_results = self.chroma_store.semantic_search(
                    query=query,
                    k=max_documents // 2,
                    where={"document_type": document_type} if document_type else None
                )
                
                # Extract document IDs and retrieve full documents
                doc_ids = set()
                for result in search_results:
                    if "document_id" in result.get("metadata", {}):
                        doc_ids.add(result["metadata"]["document_id"])
                
                # Retrieve full documents for found IDs
                for doc_id in doc_ids:
                    if self.document_service:
                        doc = await self.document_service.get_document_by_id(doc_id)
                        if doc:
                            vector_documents.append(doc)
                            
            except Exception as e:
                logger.error(f"Error retrieving documents from vector store: {e}")
        
        # Combine and deduplicate results
        all_documents = self._deduplicate_documents(
            db_documents + vector_documents
        )[:max_documents]
        
        # Grade the retrieval
        grade_result = await self._grade_retrieval(query, all_documents)
        
        return DocumentRetrievalResult(
            documents=all_documents,
            insights=vector_insights,
            retrieval_grade=grade_result["grade"],
            relevance_scores=grade_result["relevance_scores"],
            coverage_analysis=grade_result["coverage_analysis"],
            gaps_identified=grade_result["gaps_identified"],
            recommendations=grade_result["recommendations"]
        )
    
    
    def _deduplicate_documents(self, documents: List[Document]) -> List[Document]:
        """Remove duplicate documents based on document_id"""
        seen_ids = set()
        unique_docs = []
        for doc in documents:
            if doc.document_id not in seen_ids:
                seen_ids.add(doc.document_id)
                unique_docs.append(doc)
        return unique_docs
    
    async def _grade_retrieval(self, query: str, documents: List[Document]) -> Dict[str, Any]:
        """Grade the quality of document retrieval"""
        if not documents:
            return {
                "grade": RetrievalGrade.INSUFFICIENT,
                "relevance_scores": [],
                "coverage_analysis": {"total_docs": 0, "coverage_score": 0.0},
                "gaps_identified": ["No documents found"],
                "recommendations": ["Try broader search terms", "Check document availability"]
            }
        
        # Calculate relevance scores using simple text similarity
        relevance_scores = []
        query_words = set(query.lower().split())
        
        for doc in documents:
            doc_words = set(doc.content.lower().split())
            # Calculate Jaccard similarity
            intersection = len(query_words.intersection(doc_words))
            union = len(query_words.union(doc_words))
            similarity = intersection / union if union > 0 else 0
            relevance_scores.append(similarity)
        
        # Determine grade based on scores
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        max_relevance = max(relevance_scores) if relevance_scores else 0
        
        if avg_relevance >= 0.3 and max_relevance >= 0.5:
            grade = RetrievalGrade.EXCELLENT
        elif avg_relevance >= 0.2 and max_relevance >= 0.4:
            grade = RetrievalGrade.GOOD
        elif avg_relevance >= 0.1 and max_relevance >= 0.3:
            grade = RetrievalGrade.FAIR
        elif max_relevance >= 0.1:
            grade = RetrievalGrade.POOR
        else:
            grade = RetrievalGrade.INSUFFICIENT
        
        # Analyze coverage
        coverage_analysis = {
            "total_docs": len(documents),
            "avg_relevance": avg_relevance,
            "max_relevance": max_relevance,
            "coverage_score": min(1.0, len(documents) / 10)  # Normalize to 0-1
        }
        
        # Identify gaps and generate recommendations
        gaps_identified = []
        recommendations = []
        
        if grade in [RetrievalGrade.POOR, RetrievalGrade.INSUFFICIENT]:
            gaps_identified.append("Low relevance scores")
            recommendations.append("Refine search query with more specific terms")
        
        if len(documents) < 5:
            gaps_identified.append("Limited document coverage")
            recommendations.append("Expand search scope or check document availability")
        
        if max_relevance < 0.3:
            gaps_identified.append("No highly relevant documents found")
            recommendations.append("Consider alternative search strategies or data sources")
        
        return {
            "grade": grade,
            "relevance_scores": relevance_scores,
            "coverage_analysis": coverage_analysis,
            "gaps_identified": gaps_identified,
            "recommendations": recommendations
        }

class DocumentPlanningStrategy(str, Enum):
    """Document-specific planning strategies"""
    COMPREHENSIVE_ANALYSIS = "comprehensive_analysis"  # Full document analysis
    FOCUSED_EXTRACTION = "focused_extraction"         # Extract specific information
    COMPARATIVE_ANALYSIS = "comparative_analysis"     # Compare across documents
    TIMELINE_ANALYSIS = "timeline_analysis"           # Time-based analysis
    METADATA_ANALYSIS = "metadata_analysis"           # Focus on document metadata
    CONTENT_SUMMARIZATION = "content_summarization"   # Summarize document content
    STRUCTURED_EXTRACTION = "structured_extraction"   # Extract structured data

class DocumentPlanStep(BaseModel):
    """A step in the document analysis plan"""
    step_number: int
    action: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str
    target_documents: List[str] = Field(default_factory=list)  # Document IDs to focus on
    expected_output: str = ""

class DocumentPlan(BaseModel):
    """Plan for document-based question answering"""
    original_question: str
    reframed_question: str
    strategy: DocumentPlanningStrategy
    confidence: float = Field(ge=0.0, le=1.0)
    steps: List[DocumentPlanStep] = Field(default_factory=list)
    retrieval_result: DocumentRetrievalResult
    fallback_plan: Optional["DocumentPlan"] = None

class EnhancedDocumentPlanner:
    """
    Enhanced planner that uses docmodels for document retrieval, grading, and planning
    """
    
    def __init__(self, 
                 retrieval_service: DocumentRetrievalService = None,
                 llm: Optional[ChatOpenAI] = None,
                 max_documents: int = 25):
        self.retrieval_service = retrieval_service or DocumentRetrievalService()
        self.llm = llm or ChatOpenAI(model="gpt-4o", temperature=0)
        self.max_documents = max_documents
        
    async def plan(self, 
                   question: str,
                   document_type: Optional[str] = None,
                   source_type: Optional[str] = None,
                   domain_id: Optional[str] = None,
                   chat_history: Optional[List[Dict[str, Any]]] = None) -> DocumentPlan:
        """
        Create a comprehensive plan for answering a question using documents
        
        Args:
            question: The user's question
            document_type: Filter by document type
            source_type: Filter by source type
            domain_id: Filter by domain
            chat_history: Optional conversation history
            
        Returns:
            DocumentPlan with retrieval results and execution steps
        """
        logger.info(f"Creating document plan for question: {question}")
        
        # Step 1: Retrieve and grade documents
        retrieval_result = await self.retrieval_service.retrieve_documents(
            query=question,
            document_type=document_type,
            source_type=source_type,
            domain_id=domain_id,
            max_documents=self.max_documents
        )
        
        # Step 2: Analyze question and determine strategy
        question_analysis = await self._analyze_question(question, chat_history)
        
        # Step 3: Generate plan based on retrieval quality and question type
        plan = await self._generate_document_plan(
            question, 
            question_analysis, 
            retrieval_result
        )
        
        # Step 4: Validate and potentially correct the plan
        corrected_plan = await self._validate_document_plan(plan, retrieval_result)
        
        return corrected_plan
    
    async def _analyze_question(self, 
                               question: str,
                               chat_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Analyze the question to determine document analysis requirements"""
        system_prompt = """You are an expert at analyzing questions to determine what type of document analysis is needed.
        
        Analyze the question for:
        1. Question type (factual, analytical, comparative, temporal, etc.)
        2. Required information types (specific data, summaries, comparisons, etc.)
        3. Document processing needs (full text analysis, metadata analysis, structured extraction)
        4. Complexity level (simple lookup, multi-step analysis, cross-document synthesis)
        5. Expected output format (list, table, narrative, structured data)
        
        Format your response as a JSON object with these keys.
        """
        
        context = {"question": question}
        if chat_history:
            formatted_history = []
            for msg in chat_history[-3:]:  # Include last 3 messages
                role = "user" if msg.get("message_type") == "human" else "assistant"
                formatted_history.append(f"{role}: {msg.get('message_content', '')}")
            context["chat_history"] = "\n".join(formatted_history)
        
        try:
            analysis_response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Analyze this question: {question}")
            ])
            
            # Parse JSON response
            json_match = re.search(r'{.*}', str(analysis_response.content), re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                logger.error("Failed to extract JSON from question analysis")
                return {
                    "question_type": "factual",
                    "required_information": ["general_content"],
                    "processing_needs": ["full_text_analysis"],
                    "complexity_level": "simple",
                    "expected_output": "narrative"
                }
                
        except Exception as e:
            logger.error(f"Error analyzing question: {e}")
            return {
                "question_type": "factual",
                "required_information": ["general_content"],
                "processing_needs": ["full_text_analysis"],
                "complexity_level": "simple",
                "expected_output": "narrative"
            }
    
    async def _generate_document_plan(self, 
                                    question: str,
                                    question_analysis: Dict[str, Any],
                                    retrieval_result: DocumentRetrievalResult) -> DocumentPlan:
        """Generate a plan based on question analysis and retrieval results"""
        
        # Determine strategy based on retrieval quality and question type
        strategy = self._determine_strategy(question_analysis, retrieval_result)
        
        # Generate steps based on strategy
        steps = await self._generate_plan_steps(
            question, question_analysis, retrieval_result, strategy
        )
        
        # Reframe question for better document analysis
        reframed_question = await self._reframe_question(question, retrieval_result)
        
        # Calculate confidence based on retrieval quality
        confidence = self._calculate_confidence(retrieval_result, question_analysis)
        
        return DocumentPlan(
            original_question=question,
            reframed_question=reframed_question,
            strategy=strategy,
            confidence=confidence,
            steps=steps,
            retrieval_result=retrieval_result
        )
    
    def _determine_strategy(self, 
                          question_analysis: Dict[str, Any],
                          retrieval_result: DocumentRetrievalResult) -> DocumentPlanningStrategy:
        """Determine the best strategy based on question and retrieval quality"""
        
        question_type = question_analysis.get("question_type", "factual")
        processing_needs = question_analysis.get("processing_needs", [])
        grade = retrieval_result.retrieval_grade
        
        # Strategy selection logic
        if "structured_extraction" in processing_needs:
            return DocumentPlanningStrategy.STRUCTURED_EXTRACTION
        elif "comparative" in question_type or "compare" in question_type.lower():
            return DocumentPlanningStrategy.COMPARATIVE_ANALYSIS
        elif "timeline" in question_type or "temporal" in question_type:
            return DocumentPlanningStrategy.TIMELINE_ANALYSIS
        elif grade in [RetrievalGrade.EXCELLENT, RetrievalGrade.GOOD]:
            return DocumentPlanningStrategy.COMPREHENSIVE_ANALYSIS
        elif "metadata" in processing_needs:
            return DocumentPlanningStrategy.METADATA_ANALYSIS
        elif grade == RetrievalGrade.FAIR:
            return DocumentPlanningStrategy.FOCUSED_EXTRACTION
        else:
            return DocumentPlanningStrategy.CONTENT_SUMMARIZATION
    
    async def _generate_plan_steps(self, 
                                 question: str,
                                 question_analysis: Dict[str, Any],
                                 retrieval_result: DocumentRetrievalResult,
                                 strategy: DocumentPlanningStrategy) -> List[DocumentPlanStep]:
        """Generate specific steps for the document analysis plan"""
        
        steps = []
        doc_ids = [str(doc.document_id) for doc in retrieval_result.documents]
        
        if strategy == DocumentPlanningStrategy.COMPREHENSIVE_ANALYSIS:
            steps.extend([
                DocumentPlanStep(
                    step_number=1,
                    action="analyze_document_content",
                    parameters={"focus": "main_topics", "depth": "comprehensive"},
                    reasoning="Perform comprehensive analysis of all retrieved documents",
                    target_documents=doc_ids,
                    expected_output="Detailed content analysis with key insights"
                ),
                DocumentPlanStep(
                    step_number=2,
                    action="extract_relevant_information",
                    parameters={"query": question, "relevance_threshold": 0.7},
                    reasoning="Extract information directly relevant to the question",
                    target_documents=doc_ids,
                    expected_output="Relevant information extracted from documents"
                ),
                DocumentPlanStep(
                    step_number=3,
                    action="synthesize_answer",
                    parameters={"format": "comprehensive", "include_sources": True},
                    reasoning="Synthesize comprehensive answer from all sources",
                    target_documents=doc_ids,
                    expected_output="Complete answer with source citations"
                )
            ])
            
        elif strategy == DocumentPlanningStrategy.FOCUSED_EXTRACTION:
            # Focus on most relevant documents
            top_doc_ids = doc_ids[:3] if len(doc_ids) > 3 else doc_ids
            
            steps.extend([
                DocumentPlanStep(
                    step_number=1,
                    action="identify_most_relevant_documents",
                    parameters={"max_docs": 3, "relevance_threshold": 0.5},
                    reasoning="Focus on most relevant documents due to limited retrieval quality",
                    target_documents=top_doc_ids,
                    expected_output="List of most relevant documents"
                ),
                DocumentPlanStep(
                    step_number=2,
                    action="extract_specific_information",
                    parameters={"query": question, "precision": "high"},
                    reasoning="Extract specific information from focused document set",
                    target_documents=top_doc_ids,
                    expected_output="Specific information relevant to question"
                ),
                DocumentPlanStep(
                    step_number=3,
                    action="generate_focused_answer",
                    parameters={"format": "focused", "acknowledge_limitations": True},
                    reasoning="Generate focused answer acknowledging retrieval limitations",
                    target_documents=top_doc_ids,
                    expected_output="Focused answer with limitations noted"
                )
            ])
            
        elif strategy == DocumentPlanningStrategy.COMPARATIVE_ANALYSIS:
            steps.extend([
                DocumentPlanStep(
                    step_number=1,
                    action="analyze_document_metadata",
                    parameters={"focus": "document_types", "group_by": "source_type"},
                    reasoning="Analyze document metadata to understand document types and sources",
                    target_documents=doc_ids,
                    expected_output="Document metadata analysis"
                ),
                DocumentPlanStep(
                    step_number=2,
                    action="extract_comparative_data",
                    parameters={"query": question, "comparison_fields": ["content", "metadata"]},
                    reasoning="Extract data for comparison across documents",
                    target_documents=doc_ids,
                    expected_output="Comparative data extracted from documents"
                ),
                DocumentPlanStep(
                    step_number=3,
                    action="perform_comparison",
                    parameters={"comparison_type": "cross_document", "format": "structured"},
                    reasoning="Perform detailed comparison across documents",
                    target_documents=doc_ids,
                    expected_output="Structured comparison results"
                ),
                DocumentPlanStep(
                    step_number=4,
                    action="synthesize_comparative_answer",
                    parameters={"format": "comparative", "highlight_differences": True},
                    reasoning="Synthesize comparative answer highlighting key differences",
                    target_documents=doc_ids,
                    expected_output="Comparative answer with key differences highlighted"
                )
            ])
            
        elif strategy == DocumentPlanningStrategy.STRUCTURED_EXTRACTION:
            steps.extend([
                DocumentPlanStep(
                    step_number=1,
                    action="identify_structured_content",
                    parameters={"content_types": ["tables", "lists", "key_value_pairs"]},
                    reasoning="Identify structured content in documents",
                    target_documents=doc_ids,
                    expected_output="Structured content identified"
                ),
                DocumentPlanStep(
                    step_number=2,
                    action="extract_structured_data",
                    parameters={"query": question, "preserve_structure": True},
                    reasoning="Extract structured data relevant to question",
                    target_documents=doc_ids,
                    expected_output="Structured data extracted"
                ),
                DocumentPlanStep(
                    step_number=3,
                    action="format_structured_answer",
                    parameters={"format": "structured", "include_metadata": True},
                    reasoning="Format answer as structured data",
                    target_documents=doc_ids,
                    expected_output="Structured answer with metadata"
                )
            ])
            
        else:  # Default strategy
            steps.extend([
                DocumentPlanStep(
                    step_number=1,
                    action="summarize_document_content",
                    parameters={"max_length": 500, "focus": question},
                    reasoning="Summarize document content relevant to question",
                    target_documents=doc_ids,
                    expected_output="Document content summaries"
                ),
                DocumentPlanStep(
                    step_number=2,
                    action="generate_answer",
                    parameters={"format": "narrative", "include_sources": True},
                    reasoning="Generate narrative answer from document summaries",
                    target_documents=doc_ids,
                    expected_output="Narrative answer with source references"
                )
            ])
        
        return steps
    
    async def _reframe_question(self, 
                              question: str,
                              retrieval_result: DocumentRetrievalResult) -> str:
        """Reframe the question for better document analysis"""
        
        if retrieval_result.retrieval_grade in [RetrievalGrade.EXCELLENT, RetrievalGrade.GOOD]:
            return question  # No need to reframe if retrieval is good
        
        # Reframe for better document analysis
        system_prompt = """You are an expert at reframing questions to work better with available documents.
        
        Given a question and information about document retrieval quality, reframe the question to:
        1. Work better with the available documents
        2. Be more specific if the original was too broad
        3. Be more general if the original was too specific
        4. Focus on information that's likely to be in the documents
        
        Return only the reframed question, no additional text.
        """
        
        context = f"""
        Original question: {question}
        Retrieval grade: {retrieval_result.retrieval_grade.value}
        Documents found: {len(retrieval_result.documents)}
        Gaps identified: {', '.join(retrieval_result.gaps_identified)}
        """
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=context)
            ])
            
            return str(response.content).strip()
            
        except Exception as e:
            logger.error(f"Error reframing question: {e}")
            return question
    
    def _calculate_confidence(self, 
                            retrieval_result: DocumentRetrievalResult,
                            question_analysis: Dict[str, Any]) -> float:
        """Calculate confidence score based on retrieval quality and question complexity"""
        
        base_confidence = {
            RetrievalGrade.EXCELLENT: 0.9,
            RetrievalGrade.GOOD: 0.7,
            RetrievalGrade.FAIR: 0.5,
            RetrievalGrade.POOR: 0.3,
            RetrievalGrade.INSUFFICIENT: 0.1
        }[retrieval_result.retrieval_grade]
        
        # Adjust based on question complexity
        complexity = question_analysis.get("complexity_level", "simple")
        if complexity == "complex":
            base_confidence *= 0.8
        elif complexity == "simple":
            base_confidence *= 1.1
        
        # Adjust based on document count
        doc_count = len(retrieval_result.documents)
        if doc_count < 3:
            base_confidence *= 0.8
        elif doc_count > 10:
            base_confidence *= 1.1
        
        return min(1.0, max(0.0, base_confidence))
    
    async def _validate_document_plan(self, 
                                    plan: DocumentPlan,
                                    retrieval_result: DocumentRetrievalResult) -> DocumentPlan:
        """Validate and potentially correct the document plan"""
        
        # Simple validation - could be enhanced with LLM-based validation
        if not plan.steps:
            # Add default step if no steps generated
            plan.steps = [
                DocumentPlanStep(
                    step_number=1,
                    action="analyze_documents",
                    parameters={"query": plan.original_question},
                    reasoning="Default analysis step",
                    target_documents=[str(doc.document_id) for doc in retrieval_result.documents],
                    expected_output="Document analysis results"
                )
            ]
        
        # Ensure all steps have target documents
        doc_ids = [str(doc.document_id) for doc in retrieval_result.documents]
        for step in plan.steps:
            if not step.target_documents:
                step.target_documents = doc_ids
        
        return plan

# Example usage and testing
async def test_enhanced_planner():
    """Test the enhanced document planner"""
    
    # Create mock services (in real usage, these would be properly initialized)
    retrieval_service = DocumentRetrievalService()
    
    # Create planner
    planner = EnhancedDocumentPlanner(retrieval_service=retrieval_service)
    
    # Test with a sample question
    question = "What are the key financial metrics mentioned in the quarterly reports?"
    
    try:
        plan = await planner.plan(
            question=question,
            document_type="financial_report",
            max_documents=10
        )
        
        print(f"Generated plan with strategy: {plan.strategy}")
        print(f"Reframed question: {plan.reframed_question}")
        print(f"Confidence: {plan.confidence}")
        print(f"Retrieval grade: {plan.retrieval_result.retrieval_grade}")
        print(f"Documents found: {len(plan.retrieval_result.documents)}")
        print("\nPlan steps:")
        for step in plan.steps:
            print(f"  Step {step.step_number}: {step.action}")
            print(f"    Reasoning: {step.reasoning}")
            print(f"    Target documents: {len(step.target_documents)}")
            print()
            
    except Exception as e:
        print(f"Error testing planner: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_enhanced_planner())
