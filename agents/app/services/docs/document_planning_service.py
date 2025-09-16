import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime

# Import document models and services
from app.services.docs.docmodels import Document, DocumentInsight
from app.services.docs.document_persistence_service import DocumentPersistenceService
from app.storage.documents import DocumentChromaStore

# Import the enhanced planner and executor
from app.agents.nodes.docs.enhanced_document_planner import (
    EnhancedDocumentPlanner, DocumentPlan, DocumentRetrievalResult, 
    RetrievalGrade, DocumentPlanningStrategy
)
from app.agents.nodes.docs.document_plan_executor import DocumentPlanExecutor, ExecutionResult

logger = logging.getLogger("DocumentPlanningService")

@dataclass
class DocumentPlanningResponse:
    """Complete response from document planning service"""
    question: str
    reframed_question: str
    strategy: DocumentPlanningStrategy
    confidence: float
    retrieval_grade: RetrievalGrade
    documents_found: int
    execution_successful: bool
    final_answer: str
    execution_time: float
    plan_steps: List[Dict[str, Any]]
    retrieval_analysis: Dict[str, Any]
    recommendations: List[str]

class DocumentPlanningService:
    """
    Unified service that combines document planning and execution
    """
    
    def __init__(self,
                 document_service: DocumentPersistenceService = None,
                 chroma_store: DocumentChromaStore = None,
                 llm=None):
        
        # Initialize services
        self.document_service = document_service
        self.chroma_store = chroma_store
        self.llm = llm
        
        # Initialize planner and executor
        self.planner = EnhancedDocumentPlanner(
            retrieval_service=None,  # Will be set below
            llm=llm
        )
        
        self.executor = DocumentPlanExecutor(
            document_service=document_service,
            chroma_store=chroma_store,
            llm=llm
        )
        
        # Set up retrieval service for planner
        from app.agents.nodes.docs.enhanced_document_planner import DocumentRetrievalService
        self.retrieval_service = DocumentRetrievalService(
            document_service=document_service,
            chroma_store=chroma_store
        )
        self.planner.retrieval_service = self.retrieval_service
    
    async def answer_question(self,
                            question: str,
                            document_type: Optional[str] = None,
                            source_type: Optional[str] = None,
                            domain_id: Optional[str] = None,
                            max_documents: int = 25,
                            chat_history: Optional[List[Dict[str, Any]]] = None) -> DocumentPlanningResponse:
        """
        Answer a question using document planning and execution
        
        Args:
            question: The user's question
            document_type: Filter by document type
            source_type: Filter by source type
            domain_id: Filter by domain
            max_documents: Maximum number of documents to retrieve
            chat_history: Optional conversation history
            
        Returns:
            DocumentPlanningResponse with complete answer and analysis
        """
        logger.info(f"Answering question: {question}")
        
        start_time = datetime.now()
        
        try:
            # Step 1: Create document plan
            plan = await self.planner.plan(
                question=question,
                document_type=document_type,
                source_type=source_type,
                domain_id=domain_id,
                max_documents=max_documents,
                chat_history=chat_history
            )
            
            logger.info(f"Generated plan with strategy: {plan.strategy}")
            logger.info(f"Retrieval grade: {plan.retrieval_result.retrieval_grade}")
            logger.info(f"Documents found: {len(plan.retrieval_result.documents)}")
            
            # Step 2: Execute the plan
            execution_results = await self.executor.execute_plan(plan)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Step 3: Format response
            response = self._format_response(
                question, plan, execution_results, execution_time
            )
            
            logger.info(f"Question answered successfully in {execution_time:.2f} seconds")
            return response
            
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Return error response
            return DocumentPlanningResponse(
                question=question,
                reframed_question=question,
                strategy=DocumentPlanningStrategy.CONTENT_SUMMARIZATION,
                confidence=0.0,
                retrieval_grade=RetrievalGrade.INSUFFICIENT,
                documents_found=0,
                execution_successful=False,
                final_answer=f"I encountered an error while processing your question: {str(e)}",
                execution_time=execution_time,
                plan_steps=[],
                retrieval_analysis={"error": str(e)},
                recommendations=["Please try rephrasing your question", "Check if documents are available"]
            )
    
    def _format_response(self,
                        question: str,
                        plan: DocumentPlan,
                        execution_results: Dict[str, Any],
                        execution_time: float) -> DocumentPlanningResponse:
        """Format the complete response"""
        
        # Format plan steps
        plan_steps = []
        for step in plan.steps:
            plan_steps.append({
                "step_number": step.step_number,
                "action": step.action,
                "reasoning": step.reasoning,
                "target_documents": step.target_documents,
                "expected_output": step.expected_output
            })
        
        # Format retrieval analysis
        retrieval_analysis = {
            "retrieval_grade": plan.retrieval_result.retrieval_grade.value,
            "documents_found": len(plan.retrieval_result.documents),
            "relevance_scores": plan.retrieval_result.relevance_scores,
            "coverage_analysis": plan.retrieval_result.coverage_analysis,
            "gaps_identified": plan.retrieval_result.gaps_identified
        }
        
        # Get recommendations
        recommendations = plan.retrieval_result.recommendations.copy()
        if not execution_results.get("execution_successful", False):
            recommendations.append("Consider simplifying your question")
            recommendations.append("Try different search terms")
        
        return DocumentPlanningResponse(
            question=question,
            reframed_question=plan.reframed_question,
            strategy=plan.strategy,
            confidence=plan.confidence,
            retrieval_grade=plan.retrieval_result.retrieval_grade,
            documents_found=len(plan.retrieval_result.documents),
            execution_successful=execution_results.get("execution_successful", False),
            final_answer=execution_results.get("final_answer", "No answer generated"),
            execution_time=execution_time,
            plan_steps=plan_steps,
            retrieval_analysis=retrieval_analysis,
            recommendations=recommendations
        )
    
    async def get_document_analysis(self,
                                  document_ids: List[str],
                                  analysis_type: str = "comprehensive") -> Dict[str, Any]:
        """
        Get detailed analysis of specific documents
        
        Args:
            document_ids: List of document IDs to analyze
            analysis_type: Type of analysis to perform
            
        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Analyzing {len(document_ids)} documents with type: {analysis_type}")
        
        try:
            # Retrieve documents
            documents = []
            for doc_id in document_ids:
                if self.document_service:
                    doc = await self.document_service.get_document_by_id(doc_id)
                    if doc:
                        documents.append(doc)
            
            if not documents:
                return {
                    "error": "No documents found",
                    "requested_ids": document_ids,
                    "found_documents": 0
                }
            
            # Create a mock retrieval result
            from app.agents.nodes.docs.enhanced_document_planner import DocumentRetrievalResult, RetrievalGrade
            retrieval_result = DocumentRetrievalResult(
                documents=documents,
                insights=[],
                retrieval_grade=RetrievalGrade.GOOD,
                relevance_scores=[0.8] * len(documents),
                coverage_analysis={"total_docs": len(documents), "coverage_score": 1.0},
                gaps_identified=[],
                recommendations=[]
            )
            
            # Create analysis plan
            from app.agents.nodes.docs.enhanced_document_planner import DocumentPlanStep, DocumentPlanningStrategy
            from app.agents.nodes.docs.document_plan_executor import DocumentPlanExecutor
            
            if analysis_type == "comprehensive":
                steps = [
                    DocumentPlanStep(
                        step_number=1,
                        action="analyze_document_content",
                        parameters={"focus": "comprehensive", "depth": "detailed"},
                        reasoning="Perform comprehensive analysis of all documents",
                        target_documents=document_ids,
                        expected_output="Detailed content analysis"
                    )
                ]
            elif analysis_type == "structured":
                steps = [
                    DocumentPlanStep(
                        step_number=1,
                        action="identify_structured_content",
                        parameters={"content_types": ["tables", "lists", "key_value_pairs"]},
                        reasoning="Identify structured content in documents",
                        target_documents=document_ids,
                        expected_output="Structured content identified"
                    ),
                    DocumentPlanStep(
                        step_number=2,
                        action="extract_structured_data",
                        parameters={"preserve_structure": True},
                        reasoning="Extract structured data from documents",
                        target_documents=document_ids,
                        expected_output="Structured data extracted"
                    )
                ]
            else:
                steps = [
                    DocumentPlanStep(
                        step_number=1,
                        action="summarize_document_content",
                        parameters={"max_length": 500},
                        reasoning="Summarize document content",
                        target_documents=document_ids,
                        expected_output="Document summaries"
                    )
                ]
            
            # Execute analysis
            executor = DocumentPlanExecutor(
                document_service=self.document_service,
                chroma_store=self.chroma_store,
                llm=self.llm
            )
            
            # Create mock plan for execution
            from app.agents.nodes.docs.enhanced_document_planner import DocumentPlan
            mock_plan = DocumentPlan(
                original_question=f"Analyze documents with type: {analysis_type}",
                reframed_question=f"Analyze documents with type: {analysis_type}",
                strategy=DocumentPlanningStrategy.COMPREHENSIVE_ANALYSIS,
                confidence=0.8,
                steps=steps,
                retrieval_result=retrieval_result
            )
            
            execution_results = await executor.execute_plan(mock_plan)
            
            return {
                "analysis_type": analysis_type,
                "documents_analyzed": len(documents),
                "execution_successful": execution_results.get("execution_successful", False),
                "results": execution_results.get("execution_results", []),
                "final_analysis": execution_results.get("final_answer", "Analysis completed")
            }
            
        except Exception as e:
            logger.error(f"Error analyzing documents: {e}")
            return {
                "error": str(e),
                "analysis_type": analysis_type,
                "documents_analyzed": 0
            }
    
    async def search_documents(self,
                             query: str,
                             document_type: Optional[str] = None,
                             source_type: Optional[str] = None,
                             domain_id: Optional[str] = None,
                             max_documents: int = 10) -> Dict[str, Any]:
        """
        Search for documents without full planning/execution
        
        Args:
            query: Search query
            document_type: Filter by document type
            source_type: Filter by source type
            domain_id: Filter by domain
            max_documents: Maximum number of documents to return
            
        Returns:
            Dictionary with search results
        """
        logger.info(f"Searching documents with query: {query}")
        
        try:
            # Use retrieval service to get documents
            retrieval_result = await self.retrieval_service.retrieve_documents(
                query=query,
                document_type=document_type,
                source_type=source_type,
                domain_id=domain_id,
                max_documents=max_documents
            )
            
            # Format results
            search_results = {
                "query": query,
                "total_found": len(retrieval_result.documents),
                "retrieval_grade": retrieval_result.retrieval_grade.value,
                "documents": [
                    {
                        "id": str(doc.document_id),
                        "type": doc.document_type,
                        "source": doc.source_type,
                        "created_at": doc.created_at.isoformat() if doc.created_at else None,
                        "domain_id": doc.domain_id,
                        "content_preview": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
                    }
                    for doc in retrieval_result.documents
                ],
                "relevance_scores": retrieval_result.relevance_scores,
                "coverage_analysis": retrieval_result.coverage_analysis,
                "gaps_identified": retrieval_result.gaps_identified,
                "recommendations": retrieval_result.recommendations
            }
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return {
                "error": str(e),
                "query": query,
                "total_found": 0,
                "documents": []
            }
    
    async def get_planning_insights(self,
                                  question: str,
                                  document_type: Optional[str] = None,
                                  source_type: Optional[str] = None,
                                  domain_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get insights about how the planner would approach a question
        
        Args:
            question: The question to analyze
            document_type: Filter by document type
            source_type: Filter by source type
            domain_id: Filter by domain
            
        Returns:
            Dictionary with planning insights
        """
        logger.info(f"Getting planning insights for question: {question}")
        
        try:
            # Create plan without execution
            plan = await self.planner.plan(
                question=question,
                document_type=document_type,
                source_type=source_type,
                domain_id=domain_id,
                max_documents=10  # Use smaller number for insights
            )
            
            # Analyze the plan
            insights = {
                "question": question,
                "reframed_question": plan.reframed_question,
                "recommended_strategy": plan.strategy.value,
                "confidence": plan.confidence,
                "retrieval_grade": plan.retrieval_result.retrieval_grade.value,
                "documents_available": len(plan.retrieval_result.documents),
                "plan_steps": [
                    {
                        "step_number": step.step_number,
                        "action": step.action,
                        "reasoning": step.reasoning,
                        "target_documents": len(step.target_documents)
                    }
                    for step in plan.steps
                ],
                "retrieval_analysis": {
                    "coverage_score": plan.retrieval_result.coverage_analysis.get("coverage_score", 0),
                    "avg_relevance": plan.retrieval_result.coverage_analysis.get("avg_relevance", 0),
                    "gaps_identified": plan.retrieval_result.gaps_identified,
                    "recommendations": plan.retrieval_result.recommendations
                },
                "estimated_complexity": self._estimate_complexity(plan),
                "suggested_improvements": self._suggest_improvements(plan)
            }
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting planning insights: {e}")
            return {
                "error": str(e),
                "question": question,
                "insights_available": False
            }
    
    def _estimate_complexity(self, plan: DocumentPlan) -> str:
        """Estimate the complexity of the plan"""
        if plan.strategy == DocumentPlanningStrategy.COMPREHENSIVE_ANALYSIS:
            return "high"
        elif plan.strategy in [DocumentPlanningStrategy.COMPARATIVE_ANALYSIS, 
                              DocumentPlanningStrategy.STRUCTURED_EXTRACTION]:
            return "medium"
        else:
            return "low"
    
    def _suggest_improvements(self, plan: DocumentPlan) -> List[str]:
        """Suggest improvements for the plan"""
        suggestions = []
        
        if plan.retrieval_result.retrieval_grade in [RetrievalGrade.POOR, RetrievalGrade.INSUFFICIENT]:
            suggestions.append("Consider refining the search query for better document retrieval")
            suggestions.append("Try different document types or source types")
        
        if plan.confidence < 0.5:
            suggestions.append("The question might be too complex - consider breaking it down")
            suggestions.append("Provide more context or specific requirements")
        
        if len(plan.retrieval_result.documents) < 3:
            suggestions.append("More documents might be needed for comprehensive analysis")
            suggestions.append("Consider expanding the search scope")
        
        if not suggestions:
            suggestions.append("The plan looks good - no specific improvements needed")
        
        return suggestions

# Example usage and testing
async def test_document_planning_service():
    """Test the document planning service"""
    
    # Create service (with mock dependencies in real usage)
    service = DocumentPlanningService()
    
    # Test question answering
    question = "What are the key financial metrics in the quarterly reports?"
    
    try:
        response = await service.answer_question(
            question=question,
            document_type="financial_report",
            max_documents=10
        )
        
        print(f"Question: {response.question}")
        print(f"Strategy: {response.strategy}")
        print(f"Confidence: {response.confidence}")
        print(f"Documents found: {response.documents_found}")
        print(f"Execution successful: {response.execution_successful}")
        print(f"Final answer: {response.final_answer}")
        print(f"Execution time: {response.execution_time:.2f} seconds")
        
    except Exception as e:
        print(f"Error testing service: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_document_planning_service())
