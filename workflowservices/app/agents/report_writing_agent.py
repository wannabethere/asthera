"""
Report Writing Agent with Self-Correcting RAG Architecture

This module implements an intelligent report writing agent that:
1. Takes thread component questions selected for report generation
2. Uses a self-correcting RAG architecture with LangChain agents
3. Evaluates content quality and relevance
4. Incorporates writer actor types and business goals
5. Generates comprehensive, well-structured reports

This version is completely independent of database models and can operate
with any data structure that matches the defined data classes.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.agents.agent import AgentFinish
from langchain.agents.format_scratchpad import format_log_to_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.tools import BaseTool, tool
from langchain.retrievers import ChromaRetriever
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.schema.document import Document
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

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
    """Evaluates content quality and relevance using prompt chaining"""
    
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
        
        # Create prompt chain using LCEL
        self.quality_chain = self.quality_prompt | self.llm
    
    def evaluate_content(self, content: str, context: str, criteria: List[str]) -> Dict[str, Any]:
        """Evaluate content quality using prompt chaining"""
        try:
            result = self.quality_chain.invoke({
                "content": content,
                "context": context,
                "criteria": "\n".join(criteria)
            })
            
            # Parse the result (assuming it's JSON)
            import json
            return json.loads(result.content)
        except Exception as e:
            logger.error(f"Error evaluating content quality: {e}")
            return {
                "overall_score": 0.5,
                "feedback": "Error in quality evaluation",
                "suggestions": ["Review content manually"]
            }


class SelfCorrectingRAG:
    """Self-correcting RAG system for report generation using prompt chaining"""
    
    def __init__(self, llm: ChatOpenAI, embeddings: OpenAIEmbeddings):
        self.llm = llm
        self.embeddings = embeddings
        self.vectorstore = None
        self.retriever = None
        self.correction_history = []
        
        # Create correction prompt chain using LCEL
        self.correction_prompt = PromptTemplate(
            input_variables=["content", "feedback", "context"],
            template="""
            Based on the feedback below, improve the content while maintaining its core message:
            
            Original Content: {content}
            
            Feedback: {feedback}
            
            Context: {context}
            
            Provide an improved version that addresses the feedback:
            """
        )
        self.correction_chain = self.correction_prompt | self.llm
    
    def build_knowledge_base(self, thread_components: List[ThreadComponentData]) -> None:
        """Build knowledge base from thread components"""
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
                
                documents.append(Document(
                    page_content=doc_content,
                    metadata={
                        "component_id": str(component.id),
                        "component_type": component.component_type.value,
                        "sequence_order": component.sequence_order,
                        "created_at": component.created_at.isoformat() if component.created_at else None
                    }
                ))
        
        # Create vector store
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        split_docs = text_splitter.split_documents(documents)
        self.vectorstore = Chroma.from_documents(
            documents=split_docs,
            embedding=self.embeddings
        )
        self.retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": 5}
        )
    
    def retrieve_relevant_context(self, query: str) -> List[Document]:
        """Retrieve relevant context for a query"""
        if not self.retriever:
            return []
        
        try:
            return self.retriever.get_relevant_documents(query)
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return []
    
    def self_correct(self, initial_content: str, feedback: Dict[str, Any]) -> str:
        """Self-correct content based on feedback using prompt chaining"""
        try:
            corrected_content = self.correction_chain.invoke({
                "content": initial_content,
                "feedback": str(feedback),
                "context": "Report generation with self-correction"
            })
            
            # Record correction
            self.correction_history.append({
                "original": initial_content,
                "feedback": feedback,
                "corrected": corrected_content.content,
                "timestamp": datetime.now().isoformat()
            })
            
            return corrected_content.content
        except Exception as e:
            logger.error(f"Error in self-correction: {e}")
            return initial_content


class ReportWritingAgent:
    """Main report writing agent with self-correcting capabilities using prompt chaining"""
    
    def __init__(self, 
                 llm: ChatOpenAI = None,
                 embeddings: OpenAIEmbeddings = None):
        self.llm = llm or ChatOpenAI(temperature=0.1)
        self.embeddings = embeddings or OpenAIEmbeddings()
        self.rag_system = SelfCorrectingRAG(self.llm, self.embeddings)
        self.quality_evaluator = ContentQualityEvaluator(self.llm)
        
        # Create prompt chains using LCEL
        self._setup_prompt_chains()
    
    def _setup_prompt_chains(self):
        """Setup all prompt chains using LCEL"""
        
        # Outline generation chain
        self.outline_prompt = PromptTemplate(
            input_variables=["components", "actor", "goal"],
            template="""
            Create a comprehensive report outline based on the following:
            
            Thread Components: {components}
            Writer Actor Type: {actor}
            Business Goal: {goal}
            
            Generate a structured outline with:
            1. Executive Summary
            2. Main Sections (based on component types)
            3. Key Findings
            4. Recommendations
            5. Data Quality Assessment
            6. Limitations
            
            Format as JSON with the structure:
            {{
                "executive_summary": "Brief overview",
                "sections": [
                    {{
                        "title": "Section Title",
                        "key_insights": ["Insight 1", "Insight 2"],
                        "data_sources": ["Source 1"],
                        "recommendations": ["Rec 1"]
                    }}
                ],
                "key_findings": ["Finding 1", "Finding 2"],
                "overall_recommendations": ["Overall Rec 1"],
                "data_quality_assessment": "Assessment text",
                "limitations": ["Limitation 1"]
            }}
            """
        )
        self.outline_chain = self.outline_prompt | self.llm
        
        # Section content generation chain
        self.content_prompt = PromptTemplate(
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
        self.content_chain = self.content_prompt | self.llm
    
    def generate_report(self, 
                       workflow_data: ReportWorkflowData,
                       thread_components: List[ThreadComponentData],
                       writer_actor: WriterActorType,
                       business_goal: BusinessGoal) -> Dict[str, Any]:
        """Generate comprehensive report using self-correcting RAG with prompt chaining"""
        
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
        """Generate initial report outline using prompt chaining"""
        try:
            result = self.outline_chain.invoke({
                "components": self._format_components_for_prompt(state.thread_components),
                "actor": state.writer_actor.value,
                "goal": state.business_goal.dict()
            })
            
            # Parse the result
            import json
            outline_data = json.loads(result.content)
            return ReportOutline(**outline_data)
        except Exception as e:
            logger.error(f"Error generating outline: {e}")
            return self._create_fallback_outline(state)
    
    def _generate_content_with_correction(self, state: ReportWritingState) -> Dict[str, Any]:
        """Generate content with iterative self-correction using prompt chaining"""
        
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
        """Generate content for a specific section using prompt chaining"""
        try:
            # Retrieve relevant context
            context_docs = self.rag_system.retrieve_relevant_context(section.title)
            context_text = "\n".join([doc.page_content for doc in context_docs])
            
            result = self.content_chain.invoke({
                "section": section.dict(),
                "actor": state.writer_actor.value,
                "goal": state.business_goal.dict(),
                "context": context_text
            })
            
            return result.content
        except Exception as e:
            logger.error(f"Error generating section content: {e}")
            return f"Error generating content for {section.title}: {str(e)}"
    
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
        
        return "\n".join(formatted)
    
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
def create_report_writing_agent(llm: ChatOpenAI = None) -> ReportWritingAgent:
    """Factory function to create report writing agent"""
    return ReportWritingAgent(llm=llm)


def generate_report_from_data(workflow_data: ReportWorkflowData,
                             thread_components: List[ThreadComponentData],
                             writer_actor: WriterActorType,
                             business_goal: BusinessGoal,
                             llm: ChatOpenAI = None) -> Dict[str, Any]:
    """Convenience function to generate report from data classes"""
    agent = create_report_writing_agent(llm)
    return agent.generate_report(workflow_data, thread_components, writer_actor, business_goal)


# Example usage function
def example_usage():
    """Example of how to use the refactored agent"""
    
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
    
    # Generate report
    agent = create_report_writing_agent()
    result = agent.generate_report(
        workflow_data=workflow_data,
        thread_components=thread_components,
        writer_actor=WriterActorType.EXECUTIVE,
        business_goal=business_goal
    )
    
    return result
