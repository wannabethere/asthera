"""
Report Writing Agent with Self-Correcting RAG Architecture

This module implements an intelligent report writing agent that:
1. Takes thread component questions selected for report generation
2. Uses a self-correcting RAG architecture with DocumentChromaStore
3. Evaluates content quality and relevance
4. Incorporates writer actor types and business goals
5. Generates comprehensive, well-structured reports

This version uses DocumentChromaStore for vector operations and is refactored
to the retrieval module for better organization.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

# Import our custom DocumentChromaStore
from app.storage.documents import DocumentChromaStore

logger = logging.getLogger(__name__)


class WriterActorType(str, Enum):
    """Different types of writer personas for report generation"""
    EXECUTIVE = "executive"
    ANALYST = "analyst"
    TECHNICAL = "technical"
    BUSINESS_USER = "business_user"
    DATA_SCIENTIST = "data_scientist"
    CONSULTANT = "consultant"


class ComponentType(str, Enum):
    """Thread component types for report generation"""
    QUESTION = "question"
    DESCRIPTION = "description"
    OVERVIEW = "overview"
    CHART = "chart"
    TABLE = "table"
    METRIC = "metric"
    INSIGHT = "insight"
    NARRATIVE = "narrative"
    ALERT = "alert"


@dataclass
class ThreadComponentData:
    """Data class for thread component information"""
    id: str
    component_type: ComponentType
    sequence_order: int
    question: Optional[str] = None
    description: Optional[str] = None
    overview: Optional[Dict[str, Any]] = None
    chart_config: Optional[Dict[str, Any]] = None
    table_config: Optional[Dict[str, Any]] = None
    configuration: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    final_result: Optional[Dict[str, Any]] = None


@dataclass
class ReportWorkflowData:
    """Data class for report workflow information"""
    id: str
    report_id: Optional[str] = None
    user_id: Optional[str] = None
    state: Optional[str] = None
    current_step: Optional[int] = None
    workflow_metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BusinessGoal(BaseModel):
    """Business goal configuration for report generation"""
    primary_objective: str = Field(..., description="Primary business objective")
    target_audience: List[str] = Field(..., description="Target audience for the report")
    decision_context: str = Field(..., description="Context for decision making")
    success_metrics: List[str] = Field(..., description="Success metrics to track")
    timeframe: str = Field(..., description="Timeframe for the report")
    risk_factors: List[str] = Field(default_factory=list, description="Key risk factors")


class ReportSection(BaseModel):
    """Individual section of the report"""
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content")
    key_insights: List[str] = Field(..., description="Key insights from this section")
    data_sources: List[str] = Field(..., description="Data sources used")
    confidence_score: float = Field(..., description="Confidence in the analysis (0-1)")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    chart_data: Optional[Dict[str, Any]] = Field(default=None, description="Chart visualization data")
    component_id: Optional[str] = Field(default=None, description="Source thread component ID")
    component_type: Optional[str] = Field(default=None, description="Source component type")


class ReportOutline(BaseModel):
    """Report structure outline"""
    executive_summary: str = Field(..., description="Executive summary")
    sections: List[ReportSection] = Field(..., description="Report sections")
    key_findings: List[str] = Field(..., description="Key findings across all sections")
    overall_recommendations: List[str] = Field(..., description="Overall recommendations")
    data_quality_assessment: str = Field(..., description="Assessment of data quality")
    limitations: List[str] = Field(..., description="Limitations of the analysis")


class ReportWritingState(BaseModel):
    """State management for report writing process"""
    workflow_id: str = Field(..., description="Report workflow ID")
    thread_components: List[ThreadComponentData] = Field(..., description="Selected thread components")
    writer_actor: WriterActorType = Field(..., description="Writer actor type")
    business_goal: BusinessGoal = Field(..., description="Business goal configuration")
    current_outline: Optional[ReportOutline] = Field(None, description="Current report outline")
    generated_content: Dict[str, Any] = Field(default_factory=dict, description="Generated content")
    quality_scores: Dict[str, float] = Field(default_factory=dict, description="Quality scores")
    iteration_count: int = Field(default=0, description="Number of iterations")
    max_iterations: int = Field(default=3, description="Maximum iterations for self-correction")


class ContentQualityEvaluator:
    """Evaluates content quality and relevance"""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.quality_prompt = PromptTemplate(
            input_variables=["content", "context", "criteria"],
            template="""
            Evaluate the quality of the following content based on the given criteria:
            
            Content: {content}
            Context: {context}
            Quality Criteria: {criteria}
            
            Provide a score from 0-1 and detailed feedback:
            {{
                "overall_score": 0.85,
                "relevance_score": 0.9,
                "clarity_score": 0.8,
                "accuracy_score": 0.85,
                "actionability_score": 0.9,
                "feedback": "Detailed feedback on strengths and areas for improvement",
                "suggestions": ["Suggestion 1", "Suggestion 2"]
            }}
            """
        )
    
    def evaluate_content(self, content: str, context: str, criteria: List[str]) -> Dict[str, Any]:
        """Evaluate content quality"""
        try:
            # Use modern LangChain pattern: prompt | llm
            chain = self.quality_prompt | self.llm
            result = chain.invoke({
                "content": content,
                "context": context,
                "criteria": "\n".join(criteria)
            })
            
            # Parse the result (assuming it's JSON)
            import json
            # Handle both string and content responses
            content_str = result.content if hasattr(result, 'content') else str(result)
            return json.loads(content_str)
        except Exception as e:
            logger.error(f"Error evaluating content quality: {e}")
            return {
                "overall_score": 0.5,
                "feedback": "Error in quality evaluation",
                "suggestions": ["Review content manually"]
            }


class SelfCorrectingRAG:
    """Self-correcting RAG system for report generation using DocumentChromaStore"""
    
    def __init__(self, llm: ChatOpenAI, embeddings: OpenAIEmbeddings, collection_name: str = "report_writing"):
        self.llm = llm
        self.embeddings = embeddings
        self.collection_name = collection_name
        self.document_store = None
        self.correction_history = []
    
    def build_knowledge_base(self, thread_components: List[ThreadComponentData]) -> None:
        """Build knowledge base from thread components using DocumentChromaStore"""
        documents = []
        
        for component in thread_components:
            # Extract relevant information from each component
            if component.question:
                doc_content = f"Question: {component.question}\n"
                if component.description:
                    doc_content += f"Description: {component.description}\n"
                if component.overview:
                    doc_content += f"Overview: {component.overview}\n"
                if component.chart_config:
                    doc_content += f"Chart: {component.chart_config}\n"
                if component.table_config:
                    doc_content += f"Table: {component.table_config}\n"
                
                # Create document in the format expected by DocumentChromaStore
                doc_data = {
                    "metadata": {
                        "component_id": str(component.id),
                        "component_type": component.component_type.value,
                        "sequence_order": component.sequence_order,
                        "created_at": component.created_at.isoformat() if component.created_at else None,
                        "source": "thread_component"
                    },
                    "data": doc_content
                }
                
                documents.append(doc_data)
        
        # Initialize DocumentChromaStore
        from app.core.dependencies import get_chromadb_client
        persistent_client = get_chromadb_client()
        self.document_store = DocumentChromaStore(
            persistent_client=persistent_client,
            collection_name=self.collection_name,
            tf_idf=True  # Enable TF-IDF for better search
        )
        
        # Add documents to the store
        if documents:
            self.document_store.add_documents(documents)
            logger.info(f"Added {len(documents)} documents to knowledge base")
    
    def retrieve_relevant_context(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant context for a query using DocumentChromaStore"""
        if not self.document_store:
            return []
        
        try:
            # Use semantic search with TF-IDF for better results
            results = self.document_store.semantic_search_with_tfidf(query, k=k)
            
            # Convert results to a format compatible with the existing code
            formatted_results = []
            for result in results:
                # Create a mock Document object for compatibility
                formatted_results.append({
                    "page_content": result["content"],
                    "metadata": result["metadata"],
                    "score": result.get("combined_score", result.get("semantic_score", 0.0))
                })
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return []
    
    def self_correct(self, initial_content: str, feedback: Dict[str, Any]) -> str:
        """Self-correct content based on feedback"""
        correction_prompt = PromptTemplate(
            input_variables=["content", "feedback", "context"],
            template="""
            Based on the feedback below, improve the content while maintaining its core message:
            
            Original Content: {content}
            
            Feedback: {feedback}
            
            Context: {context}
            
            Provide an improved version that addresses the feedback:
            """
        )
        
        try:
            # Use modern LangChain pattern: prompt | llm
            chain = correction_prompt | self.llm
            result = chain.invoke({
                "content": initial_content,
                "feedback": str(feedback),
                "context": "Report generation with self-correction"
            })
            
            # Handle both string and content responses
            corrected_content = result.content if hasattr(result, 'content') else str(result)
            
            # Record correction
            self.correction_history.append({
                "original": initial_content,
                "feedback": feedback,
                "corrected": corrected_content,
                "timestamp": datetime.now().isoformat()
            })
            
            return corrected_content
        except Exception as e:
            logger.error(f"Error in self-correction: {e}")
            return initial_content


class ReportWritingAgent:
    """Main report writing agent with self-correcting capabilities"""
    
    def __init__(self, 
                 llm: ChatOpenAI = None,
                 embeddings: OpenAIEmbeddings = None,
                 collection_name: str = "report_writing"):
        self.llm = llm or ChatOpenAI(temperature=0.1)
        self.embeddings = embeddings or OpenAIEmbeddings()
        self.collection_name = collection_name
        self.rag_system = SelfCorrectingRAG(self.llm, self.embeddings, collection_name)
        self.quality_evaluator = ContentQualityEvaluator(self.llm)
    
    def generate_report(self, 
                       workflow_data: ReportWorkflowData,
                       thread_components: List[ThreadComponentData],
                       writer_actor: WriterActorType,
                       business_goal: BusinessGoal) -> Dict[str, Any]:
        """Generate comprehensive report using self-correcting RAG"""
        
        # Initialize state
        state = ReportWritingState(
            workflow_id=workflow_data.id,
            thread_components=thread_components,
            writer_actor=writer_actor,
            business_goal=business_goal
        )
        
        # Build knowledge base
        self.rag_system.build_knowledge_base(thread_components)
        
        # Generate initial outline
        outline = self._generate_report_outline(state)
        state.current_outline = outline
        
        # Generate content with self-correction
        final_content = self._generate_content_with_correction(state)
        
        # Final quality assessment
        final_quality = self._assess_final_quality(final_content, state)
        
        return {
            "report_outline": outline.dict(),
            "final_content": final_content,
            "quality_assessment": final_quality,
            "correction_history": self.rag_system.correction_history,
            "generation_metadata": {
                "workflow_id": workflow_data.id,
                "writer_actor": writer_actor.value,
                "business_goal": business_goal.dict(),
                "iterations": state.iteration_count,
                "generated_at": datetime.now().isoformat()
            }
        }
    
    def _generate_report_outline(self, state: ReportWritingState) -> ReportOutline:
        """Generate initial report outline based on thread components"""
        
        # Create component-based sections first
        component_sections = self._create_sections_from_components(state.thread_components)
        
        # Generate executive summary and other metadata
        outline_prompt = PromptTemplate(
            input_variables=["components", "actor", "goal", "sections"],
            template="""
            Create a comprehensive report outline based on the following:
            
            Thread Components: {components}
            Writer Actor Type: {actor}
            Business Goal: {goal}
            Component Sections: {sections}
            
            Generate ONLY the following metadata (do not create additional sections):
            1. Executive Summary - A professional summary that explains the purpose of this training analysis report, what data was analyzed, and key insights for executives and stakeholders
            2. Key Findings - Based on the component sections, extract the most important findings about training completion rates and performance
            3. Overall Recommendations - Based on the component sections, provide actionable recommendations for improving training effectiveness
            4. Data Quality Assessment - Assess the quality and reliability of the training data used in this analysis
            5. Limitations - Identify any limitations or constraints in the analysis
            
            IMPORTANT: 
            - Do NOT create additional sections - use only the provided component sections
            - Focus on training completion analysis and LMS platform effectiveness
            - Make the executive summary suitable for executives, stakeholders, and HR
            - Base all findings and recommendations on the actual component sections provided
            
            Format as JSON with the structure:
            {{
                "executive_summary": "Professional executive summary focusing on training completion analysis and its business impact",
                "key_findings": ["Finding 1 about training completion", "Finding 2 about training effectiveness"],
                "overall_recommendations": ["Recommendation 1 for improving training", "Recommendation 2 for training optimization"],
                "data_quality_assessment": "Assessment of training data quality and reliability",
                "limitations": ["Limitation 1 of the analysis", "Limitation 2 of the data"]
            }}
            """
        )
        
        try:
            # Use modern LangChain pattern: prompt | llm
            chain = outline_prompt | self.llm
            result = chain.invoke({
                "components": self._format_components_for_prompt(state.thread_components),
                "actor": state.writer_actor.value,
                "goal": state.business_goal.dict(),
                "sections": [s["title"] for s in component_sections]
            })
            
            # Handle both string and content responses
            content_str = result.content if hasattr(result, 'content') else str(result)
            
            # Parse the result with better error handling
            import json
            try:
                # Try to extract JSON from the response if it's wrapped in markdown
                if "```json" in content_str:
                    json_start = content_str.find("```json") + 7
                    json_end = content_str.find("```", json_start)
                    if json_end != -1:
                        content_str = content_str[json_start:json_end].strip()
                elif "```" in content_str:
                    json_start = content_str.find("```") + 3
                    json_end = content_str.find("```", json_start)
                    if json_end != -1:
                        content_str = content_str[json_start:json_end].strip()
                
                outline_data = json.loads(content_str)
                
                # Use component-based sections instead of LLM-generated ones
                outline_data["sections"] = component_sections
                
                return ReportOutline(**outline_data)
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON parsing error: {json_err}")
                logger.error(f"Raw content: {content_str[:500]}...")
                return self._create_fallback_outline(state)
            except Exception as validation_err:
                logger.error(f"Validation error creating ReportOutline: {validation_err}")
                logger.error(f"Outline data: {outline_data}")
                return self._create_fallback_outline(state)
        except Exception as e:
            logger.error(f"Error generating outline: {e}")
            return self._create_fallback_outline(state)
    
    def _generate_content_with_correction(self, state: ReportWritingState) -> Dict[str, Any]:
        """Generate content with iterative self-correction"""
        
        while state.iteration_count < state.max_iterations:
            state.iteration_count += 1
            logger.info(f"Generating content iteration {state.iteration_count}")
            
            # Generate content for each section
            content = {}
            for section in state.current_outline.sections:
                section_content = self._generate_section_content(section, state)
                content[section.title] = section_content
            
            # Evaluate quality
            quality_scores = {}
            for title, section_content in content.items():
                quality = self.quality_evaluator.evaluate_content(
                    content=section_content,
                    context=f"Section: {title}",
                    criteria=[
                        "Relevance to business goal",
                        "Clarity and readability",
                        "Data accuracy",
                        "Actionability",
                        "Professional tone appropriate for writer actor"
                    ]
                )
                quality_scores[title] = quality
            
            # Check if quality meets threshold
            overall_score = sum(q.get("overall_score", 0) for q in quality_scores.values()) / len(quality_scores)
            
            if overall_score >= 0.8:  # Quality threshold
                logger.info(f"Quality threshold met: {overall_score}")
                break
            
            # Self-correct if needed
            logger.info(f"Quality below threshold ({overall_score}), self-correcting...")
            for title, section_content in content.items():
                if quality_scores[title].get("overall_score", 0) < 0.8:
                    corrected_content = self.rag_system.self_correct(
                        section_content,
                        quality_scores[title]
                    )
                    content[title] = corrected_content
            
            # Update state
            state.generated_content = content
            state.quality_scores = quality_scores
        
        return content
    
    def _generate_section_content(self, section: ReportSection, state: ReportWritingState) -> str:
        """Generate content for a specific section"""
        
        # Check if this is a chart section
        if section.chart_data:
            return self._generate_chart_section_content(section, state)
        
        content_prompt = PromptTemplate(
            input_variables=["section", "actor", "goal", "context"],
            template="""
            Generate content for the following report section:
            
            Section: {section}
            Writer Actor: {actor}
            Business Goal: {goal}
            Context: {context}
            
            Write professional, engaging content that:
            1. Addresses the business goal
            2. Matches the writer actor's style
            3. Incorporates relevant data and insights
            4. Provides actionable recommendations
            5. Maintains appropriate tone and complexity
            
            Focus on clarity, relevance, and business value.
            """
        )
        
        try:
            # Retrieve relevant context using DocumentChromaStore
            context_results = self.rag_system.retrieve_relevant_context(section.title)
            context_text = "\n".join([result["page_content"] for result in context_results])
            
            # Use modern LangChain pattern: prompt | llm
            chain = content_prompt | self.llm
            result = chain.invoke({
                "section": section.dict(),
                "actor": state.writer_actor.value,
                "goal": state.business_goal.dict(),
                "context": context_text
            })
            
            # Handle both string and content responses
            content = result.content if hasattr(result, 'content') else str(result)
            return content
        except Exception as e:
            logger.error(f"Error generating section content: {e}")
            return f"Error generating content for {section.title}: {str(e)}"
    
    def _generate_chart_section_content(self, section: ReportSection, state: ReportWritingState) -> str:
        """Generate content specifically for chart sections"""
        chart_prompt = PromptTemplate(
            input_variables=["section", "actor", "goal", "chart_data"],
            template="""
            Generate content for a chart section in the report:
            
            Section: {section}
            Writer Actor: {actor}
            Business Goal: {goal}
            Chart Data: {chart_data}
            
            Write content that:
            1. Describes the chart and its key findings
            2. Explains what the data shows
            3. Highlights important trends or patterns
            4. Connects the visualization to business goals
            5. Provides insights based on the chart data
            
            Include a placeholder for the chart: [CHART_PLACEHOLDER]
            
            Focus on making the chart data actionable and relevant to the business goal.
            """
        )
        
        try:
            # Use modern LangChain pattern: prompt | llm
            chain = chart_prompt | self.llm
            result = chain.invoke({
                "section": section.dict(),
                "actor": state.writer_actor.value,
                "goal": state.business_goal.dict(),
                "chart_data": section.chart_data
            })
            
            # Handle both string and content responses
            content = result.content if hasattr(result, 'content') else str(result)
            
            # Add chart data as a structured element
            chart_content = {
                "text": content,
                "chart_data": section.chart_data,
                "component_id": section.component_id,
                "component_type": section.component_type
            }
            
            return chart_content
        except Exception as e:
            logger.error(f"Error generating chart section content: {e}")
            return {
                "text": f"Error generating chart content for {section.title}: {str(e)}",
                "chart_data": section.chart_data,
                "component_id": section.component_id,
                "component_type": section.component_type
            }
    
    def _assess_final_quality(self, content: Dict[str, Any], state: ReportWritingState) -> Dict[str, Any]:
        """Assess final report quality"""
        overall_assessment = {
            "total_sections": len(content),
            "average_quality_score": 0.0,
            "overall_grade": "C",
            "strengths": [],
            "areas_for_improvement": [],
            "business_alignment_score": 0.0,
            "recommendations": []
        }
        
        if state.quality_scores:
            scores = list(state.quality_scores.values())
            overall_assessment["average_quality_score"] = sum(
                s.get("overall_score", 0) for s in scores
            ) / len(scores)
            
            # Determine overall grade
            avg_score = overall_assessment["average_quality_score"]
            if avg_score >= 0.9:
                overall_assessment["overall_grade"] = "A"
            elif avg_score >= 0.8:
                overall_assessment["overall_grade"] = "B"
            elif avg_score >= 0.7:
                overall_assessment["overall_grade"] = "C"
            else:
                overall_assessment["overall_grade"] = "D"
        
        return overall_assessment
    
    def _format_components_for_prompt(self, components: List[ThreadComponentData]) -> str:
        """Format thread components for prompt input"""
        formatted = []
        for comp in sorted(components, key=lambda x: x.sequence_order):
            formatted.append(f"Component {comp.sequence_order}: {comp.component_type.value}")
            if comp.question:
                formatted.append(f"  Question: {comp.question}")
            if comp.description:
                formatted.append(f"  Description: {comp.description}")
            if comp.overview:
                formatted.append(f"  Overview: {comp.overview}")
            if comp.chart_config:
                formatted.append(f"  Chart Config: {comp.chart_config}")
            if hasattr(comp, 'final_result') and comp.final_result:
                post_process = comp.final_result.get('post_process', {})
                visualization = post_process.get('visualization', {})
                if visualization.get('chart_schema'):
                    formatted.append(f"  Chart Schema: {visualization['chart_schema']}")
        
        return "\n".join(formatted)
    
    def _create_sections_from_components(self, thread_components: List[ThreadComponentData]) -> List[Dict[str, Any]]:
        """Create report sections from thread components"""
        sections = []
        
        logger.info(f"Creating sections from {len(thread_components)} thread components")
        for i, component in enumerate(thread_components):
            logger.info(f"Component {i}: id={component.id}, type={component.component_type}, question={component.question}")
            logger.info(f"Component {i}: chart_config={component.chart_config}, final_result={component.final_result is not None}")
            # Extract chart data if available
            chart_data = None
            has_chart_data = False
            
            if component.chart_config:
                chart_data = component.chart_config
                has_chart_data = True
            elif hasattr(component, 'final_result') and component.final_result:
                post_process = component.final_result.get('post_process', {})
                chart_data = post_process.get('visualization', {}).get('chart_schema', {})
                if chart_data:
                    has_chart_data = True
            
            # Create section based on component type and data availability
            if component.component_type == ComponentType.CHART:
                if has_chart_data and chart_data:
                    # Chart section with visualization data
                    section = {
                        "title": f"Training Completion Analysis: {component.question or 'Position-based Completion Rates'}",
                        "content": f"This section presents a comprehensive analysis of training completion rates across different positions within the organization. The visualization below shows completion percentages for each role, providing insights into training effectiveness and areas requiring attention.",
                        "key_insights": [
                            f"Completion rates vary significantly across positions, ranging from {self._extract_min_max_rates(chart_data)}",
                            "Certain roles show consistently higher completion rates, indicating effective training programs",
                            "Areas with lower completion rates may require targeted training interventions"
                        ],
                        "data_sources": ["Training completion data", "Position-based analytics", "LMS platform records"],
                        "confidence_score": 0.85,
                        "recommendations": [
                            "Focus training efforts on positions with lower completion rates",
                            "Analyze successful training programs for positions with high completion rates",
                            "Implement targeted interventions for underperforming areas"
                        ],
                        "chart_data": chart_data,
                        "component_id": component.id,
                        "component_type": component.component_type.value
                    }
                else:
                    # Chart section without data (failed query)
                    section = {
                        "title": f"Training Completion Analysis: {component.question or 'Position-based Completion Rates'}",
                        "content": f"This section was intended to present training completion analysis across different positions. However, the data query encountered an issue and could not be executed successfully. This may be due to data availability, query complexity, or system constraints.",
                        "key_insights": [
                            "Data query execution failed - analysis cannot be completed at this time",
                            "This section requires data access to provide meaningful insights",
                            "Alternative data sources or query modifications may be needed"
                        ],
                        "data_sources": ["Training completion data (unavailable)", "Position-based analytics (unavailable)"],
                        "confidence_score": 0.0,
                        "recommendations": [
                            "Verify data availability and query syntax",
                            "Check system connectivity and permissions",
                            "Consider alternative data sources or simplified queries"
                        ],
                        "chart_data": None,
                        "component_id": component.id,
                        "component_type": component.component_type.value
                    }
            elif component.component_type == ComponentType.TABLE:
                # Table section
                section = {
                    "title": f"Data Table: {component.question or 'Training Data Overview'}",
                    "content": f"This section presents tabular data showing {component.description or 'training completion details'}. The table provides a structured view of the data for detailed analysis.",
                    "key_insights": [f"Table displays {component.question or 'structured training data'}"],
                    "data_sources": [component.description or "Training data analysis"],
                    "confidence_score": 0.8,
                    "recommendations": ["Review table data for patterns and trends"],
                    "chart_data": None,
                    "component_id": component.id,
                    "component_type": component.component_type.value
                }
            elif component.component_type == ComponentType.METRIC:
                # Metric section
                section = {
                    "title": f"Key Performance Metric: {component.question or 'Training Completion Rate'}",
                    "content": f"This section focuses on a key performance metric: {component.description or 'overall training completion rate'}. This metric provides a high-level view of training effectiveness across the organization.",
                    "key_insights": [f"Metric indicates {component.question or 'current performance level'}"],
                    "data_sources": [component.description or "Performance data"],
                    "confidence_score": 0.85,
                    "recommendations": ["Monitor metric trends over time"],
                    "chart_data": None,
                    "component_id": component.id,
                    "component_type": component.component_type.value
                }
            else:
                # Generic section for other component types
                section = {
                    "title": f"{component.component_type.value.title()}: {component.question or 'Training Analysis'}",
                    "content": f"This section provides analysis of {component.description or 'training-related insights'}. The analysis aims to provide actionable insights for improving training effectiveness.",
                    "key_insights": [f"Analysis reveals {component.question or 'key findings about training performance'}"],
                    "data_sources": [component.description or "Training analysis data"],
                    "confidence_score": 0.7,
                    "recommendations": ["Review analysis for actionable insights"],
                    "chart_data": chart_data if chart_data else None,
                    "component_id": component.id,
                    "component_type": component.component_type.value
                }
            
            sections.append(section)
        
        return sections
    
    def _extract_min_max_rates(self, chart_data: Dict[str, Any]) -> str:
        """Extract min and max completion rates from chart data"""
        try:
            if 'data' in chart_data and 'values' in chart_data['data']:
                values = chart_data['data']['values']
                if values and len(values) > 0:
                    rates = [float(v.get('completion_rate', 0)) for v in values if 'completion_rate' in v]
                    if rates:
                        min_rate = min(rates)
                        max_rate = max(rates)
                        return f"{min_rate:.1f}% to {max_rate:.1f}%"
            return "varying percentages"
        except Exception:
            return "varying percentages"
    
    def _create_chart_sections_from_components(self, thread_components: List[ThreadComponentData]) -> List[Dict[str, Any]]:
        """Create chart sections from thread components that have chart data"""
        chart_sections = []
        
        for component in thread_components:
            # Check if component has chart data
            if (component.chart_config or 
                (hasattr(component, 'final_result') and component.final_result and 
                 component.final_result.get('post_process', {}).get('visualization', {}).get('chart_schema'))):
                
                # Extract chart data
                chart_data = None
                if component.chart_config:
                    chart_data = component.chart_config
                elif hasattr(component, 'final_result') and component.final_result:
                    post_process = component.final_result.get('post_process', {})
                    chart_data = post_process.get('visualization', {}).get('chart_schema', {})
                
                if chart_data:
                    chart_section = {
                        "title": f"Chart: {component.question or 'Data Visualization'}",
                        "content": f"Visualization of {component.description or 'data analysis'}",
                        "key_insights": [f"Chart shows {component.question or 'data trends'}"],
                        "data_sources": [component.description or "Data analysis"],
                        "confidence_score": 0.8,  # High confidence for visualizations
                        "recommendations": ["Review chart for insights"],
                        "chart_data": chart_data,
                        "component_id": component.id,
                        "component_type": component.component_type.value
                    }
                    chart_sections.append(chart_section)
        
        return chart_sections
    
    def _create_fallback_outline(self, state: ReportWritingState) -> ReportOutline:
        """Create fallback outline if generation fails"""
        return ReportOutline(
            executive_summary="Executive summary generation failed",
            sections=[
                ReportSection(
                    title="Overview",
                    content="Content generation failed",
                    key_insights=["Review required"],
                    data_sources=["Manual review needed"],
                    confidence_score=0.0
                )
            ],
            key_findings=["Manual review required"],
            overall_recommendations=["Review and regenerate"],
            data_quality_assessment="Assessment failed",
            limitations=["Generation system error"]
        )


# Utility functions for external use
def create_report_writing_agent(llm: ChatOpenAI = None, collection_name: str = "report_writing") -> ReportWritingAgent:
    """Factory function to create report writing agent"""
    return ReportWritingAgent(llm=llm, collection_name=collection_name)


def generate_report_from_data(workflow_data: ReportWorkflowData,
                             thread_components: List[ThreadComponentData],
                             writer_actor: WriterActorType,
                             business_goal: BusinessGoal,
                             llm: ChatOpenAI = None,
                             collection_name: str = "report_writing") -> Dict[str, Any]:
    """Convenience function to generate report from data classes"""
    agent = create_report_writing_agent(llm, collection_name)
    return agent.generate_report(workflow_data, thread_components, writer_actor, business_goal)


# Example usage function
def example_usage():
    """Example of how to use the refactored agent with DocumentChromaStore"""
    
    # Create sample data
    workflow_data = ReportWorkflowData(
        id="workflow-123",
        report_id="report-456",
        user_id="user-789",
        state="active",
        current_step=1
    )
    
    thread_components = [
        ThreadComponentData(
            id="comp-1",
            component_type=ComponentType.QUESTION,
            sequence_order=1,
            question="What are the key performance indicators for Q4?",
            description="Analysis of Q4 KPIs across all departments"
        ),
        ThreadComponentData(
            id="comp-2",
            component_type=ComponentType.CHART,
            sequence_order=2,
            chart_config={"type": "line", "data": "q4_kpi_data"},
            description="Q4 KPI trend visualization"
        )
    ]
    
    business_goal = BusinessGoal(
        primary_objective="Improve Q4 performance",
        target_audience=["Executives", "Department Heads"],
        decision_context="Q4 planning and resource allocation",
        success_metrics=["KPI improvement", "Resource efficiency"],
        timeframe="Q4 2024"
    )
    
    # Generate report using DocumentChromaStore
    agent = create_report_writing_agent(collection_name="example_report")
    result = agent.generate_report(
        workflow_data=workflow_data,
        thread_components=thread_components,
        writer_actor=WriterActorType.EXECUTIVE,
        business_goal=business_goal
    )
    
    return result


if __name__ == "__main__":
    # Test the refactored agent
    try:
        result = example_usage()
        print("✅ Report generation successful!")
        print(f"📊 Generated {len(result['final_content'])} sections")
        print(f"📈 Quality grade: {result['quality_assessment']['overall_grade']}")
    except Exception as e:
        print(f"❌ Error testing agent: {e}")
        import traceback
        traceback.print_exc()
