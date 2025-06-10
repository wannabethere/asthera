import os
from typing import Dict, List, Optional, Any, Tuple, Union
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_openai import ChatOpenAI
import langchain
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langsmith import Client
import langgraph.graph
from langgraph.graph import END, StateGraph
import numpy as np
from enum import Enum
import json
import re
import chromadb
from app.storage.documents import DocumentChromaStore
# RedisGraph Store is imported separately and kept distinct
# from redis_graph_store import RedisGraphStore
# from strategic_map import StrategicMap



# State modeling
class RetrievalState(BaseModel):
    """State for the KPI recommendation retrieval pipeline."""
    query: str = Field(..., description="Original user query about KPIs or objectives")
    strategic_map_name: str = Field(..., description="Name of the strategic map to query")
    
    # Dataset context fields
    goal: Optional[str] = Field(None, description="Business goal for KPI recommendations")
    dataframe_schema: Optional[Dict[str, Any]] = Field(None, description="Schema of the dataframe columns")
    dataframe_sample: Optional[List[Dict[str, Any]]] = Field(None, description="Sample rows from the dataframe")
    dataframe_stats: Optional[Dict[str, Any]] = Field(None, description="Statistical summary of the dataframe")
    data_context: Optional[str] = Field(None, description="Additional context about the data")
    data_description: Optional[str] = Field(None, description="Description of the dataset")
    domain_context: Optional[str] = Field(None, description="Business domain context")
    
    # Context and retrieval fields
    context: List[Dict[str, Any]] = Field(default_factory=list, description="Retrieved context from the strategic map")
    retrieved_objectives: List[Dict[str, Any]] = Field(default_factory=list, description="Retrieved objectives")
    retrieved_kpis: List[Dict[str, Any]] = Field(default_factory=list, description="Retrieved KPIs")
    strategic_paths: List[Dict[str, Any]] = Field(default_factory=list, description="Strategic paths for relevant objectives")
    related_kpis: List[Dict[str, Any]] = Field(default_factory=list, description="Related KPIs")
    retrieved_insights: List[Document] = Field(default_factory=list, description="Retrieved EDA insights from vector store")
    insights_summary: Optional[str] = Field(default=None, description="Summary of relevant insights")
    goal_context: Optional[Dict[str, Any]] = Field(default=None, description="Context retrieved based on the goal")
    relevant_metrics: Optional[List[Dict[str, str]]] = Field(default=None, description="Metrics identified as relevant for the goal")
    
    # Processing control fields
    corrected_query: Optional[str] = Field(default=None, description="Query after self-correction")
    kpi_recommendations: List[Dict[str, Any]] = Field(default_factory=list, description="Generated KPI recommendations")
    relevance_scores: Dict[str, float] = Field(default_factory=dict, description="Relevance scores for recommendations")
    errors: List[str] = Field(default_factory=list, description="Errors encountered during the process")
    needs_correction: bool = Field(default=False, description="Flag indicating if query needs correction")
    final_response: Optional[str] = Field(default=None, description="Final formatted response")


class NodeType(str, Enum):
    """Types of nodes in the pipeline."""
    GOAL_CONTEXT_FINDER = "goal_context_finder"
    DATASET_METRICS_ANALYZER = "dataset_metrics_analyzer"
    OBJECTIVES_RETRIEVER = "objectives_retriever"
    KPIS_RETRIEVER = "kpis_retriever"
    STRATEGIC_PATH_ANALYZER = "strategic_path_analyzer"
    RELATED_KPIS_FINDER = "related_kpis_finder"
    INSIGHTS_RETRIEVER = "insights_retriever"
    INSIGHTS_SUMMARIZER = "insights_summarizer" 
    QUERY_CORRECTOR = "query_corrector"
    KPI_RECOMMENDER = "kpi_recommender"
    RELEVANCE_SCORER = "relevance_scorer"
    RESPONSE_GENERATOR = "response_generator"


# Configuration
def get_llm(temperature: float = 0.0, model: str = "gpt-4o"):
    """Get the LLM with specified temperature and model."""
    return ChatOpenAI(
        model=model,
        temperature=temperature
    )


# Node implementations
def goal_context_finder(state: RetrievalState, insights_store: DocumentChromaStore) -> Dict:
    """Find relevant context based on the business goal."""
    try:
        # If no explicit goal is provided, use the query as the goal
        goal = state.goal or state.query
        
        # Initialize the insights vector store
        
        # Search for insights related to the goal
        retrieved_insights = insights_store.search(
            query=goal,
            k=3  # Retrieve top 3 relevant insights
        )
        
        # Extract and structure the goal context
        goal_context = {
            "goal": goal,
            "similar_scenarios": [],
            "relevant_insights": []
        }
        
        # Process retrieved insights
        for insight in retrieved_insights:
            # Extract scenario
            scenario = insight.metadata.get("scenario", "Unknown scenario")
            if scenario not in goal_context["similar_scenarios"]:
                goal_context["similar_scenarios"].append(scenario)
            
            # Extract insight information
            insight_data = {
                "title": insight.metadata.get("title", "Untitled insight"),
                "scenario": scenario,
                "content_summary": insight.page_content[:500] + "..." if len(insight.page_content) > 500 else insight.page_content,
                "tags": insight.metadata.get("tags", [])
            }
            
            goal_context["relevant_insights"].append(insight_data)
        
        return {
            "goal_context": goal_context,
            "retrieved_insights": retrieved_insights  # Also store the original insights
        }
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in goal context finder: {str(e)}"]}


def dataset_metrics_analyzer(state: RetrievalState) -> Dict:
    """Analyze the dataset schema and identify relevant metrics."""
    try:
        # Check if we have dataset information
        if not state.dataframe_schema and not state.dataframe_sample and not state.dataframe_stats:
            return {"relevant_metrics": []}
        
        # Prepare the input for the LLM
        schema_str = json.dumps(state.dataframe_schema, indent=2) if state.dataframe_schema else "No schema provided"
        
        # Prepare sample data
        sample_str = ""
        if state.dataframe_sample:
            # Format sample rows
            sample_rows = []
            for i, row in enumerate(state.dataframe_sample[:5]):  # Limit to 5 rows
                sample_rows.append(f"Row {i+1}: {json.dumps(row)}")
            sample_str = "\n".join(sample_rows)
        else:
            sample_str = "No sample data provided"
        
        # Prepare stats
        stats_str = json.dumps(state.dataframe_stats, indent=2) if state.dataframe_stats else "No statistics provided"
        
        # Use the goal context to help identify relevant metrics
        goal_context_str = ""
        if state.goal_context:
            goal = state.goal_context.get("goal", "")
            scenarios = ", ".join(state.goal_context.get("similar_scenarios", []))
            
            goal_context_str = f"Goal: {goal}\nSimilar scenarios: {scenarios}\n\n"
            
            # Add insight summaries
            insights = state.goal_context.get("relevant_insights", [])
            if insights:
                insight_summaries = []
                for i, insight in enumerate(insights):
                    insight_summaries.append(f"Insight {i+1}: {insight.get('title')}\nScenario: {insight.get('scenario')}")
                
                goal_context_str += "Relevant insights:\n" + "\n\n".join(insight_summaries)
        
        # Create prompt for metric identification
        metric_prompt = ChatPromptTemplate.from_template("""
        You are a data analytics expert specializing in identifying key metrics and KPIs for business goals.
        Given the schema and sample data from a dataset, identify the most relevant metrics that could be
        calculated to address the business goal.
        
        Business Goal: {goal}
        
        Domain Context: {domain_context}
        
        Data Description: {data_description}
        
        Additional Context: {data_context}
        
        Goal Context:
        {goal_context}
        
        Dataset Schema:
        {schema}
        
        Sample Data:
        {sample}
        
        Dataset Statistics:
        {stats}
        
        Based on this information, identify the most relevant metrics that could be calculated from this dataset
        to address the business goal. For each metric:
        1. Provide a name
        2. Provide a description
        3. Explain how it relates to the business goal
        4. Describe how it could be calculated using the available data columns
        
        Return a JSON array of metrics:
        [
          {{
            "name": "Metric name",
            "description": "Metric description",
            "goal_relevance": "How this metric helps address the business goal",
            "calculation": "How to calculate this metric from the dataset"
          }},
          ...
        ]
        
        Focus on metrics that are both calculable from the given dataset and relevant to the business goal.
        """)
        
        llm = get_llm()
        chain = metric_prompt | llm | StrOutputParser()
        
        # Invoke the chain
        metric_result = chain.invoke({
            "goal": state.goal or "Improve business performance",
            "domain_context": state.domain_context or "General business domain",
            "data_description": state.data_description or "Dataset containing business metrics",
            "data_context": state.data_context or "",
            "goal_context": goal_context_str,
            "schema": schema_str,
            "sample": sample_str,
            "stats": stats_str
        })
        
        # Parse the metrics
        try:
            metrics = json.loads(metric_result)
            if not isinstance(metrics, list):
                metrics = []
        except:
            # Try to extract JSON using regex if direct parsing fails
            import re
            json_match = re.search(r'\[(.*?)\]', metric_result, re.DOTALL)
            if json_match:
                try:
                    metrics = json.loads("[" + json_match.group(1) + "]")
                except:
                    metrics = []
            else:
                metrics = []
        
        return {"relevant_metrics": metrics}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in dataset metrics analyzer: {str(e)}"]}


def objectives_retriever(state: RetrievalState) -> Dict:
    """Retrieve objectives based on the query."""
    try:
        # This is a placeholder for actual retrieval
        # In a real implementation, this would connect to RedisGraph or other database
        # to retrieve strategic objectives
        
        # For demonstration, return empty for now
        # (This would be replaced with actual code for retrieving from a database)
        objectives = []
        
        # In the actual implementation, you would use something like:
        # redis_graph_store = RedisGraphStore()
        # strategic_map = StrategicMap(redis_graph_store, state.strategic_map_name)
        # objectives = strategic_map.get_all_objectives()
        
        # For now, simulate with empty list or mock data
        # objectives = [
        #     {
        #         "o": {
        #             "id": 1,
        #             "properties": {
        #                 "name": "Increase Customer Satisfaction",
        #                 "description": "Improve overall customer satisfaction and loyalty"
        #             }
        #         }
        #     },
        #     {
        #         "o": {
        #             "id": 2,
        #             "properties": {
        #                 "name": "Optimize Operational Efficiency",
        #                 "description": "Streamline processes to reduce costs and improve service delivery"
        #             }
        #         }
        #     }
        # ]
        
        return {"retrieved_objectives": objectives}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in objectives retriever: {str(e)}"]}


def kpis_retriever(state: RetrievalState) -> Dict:
    """Retrieve KPIs related to the retrieved objectives."""
    try:
        # This is a placeholder for actual KPI retrieval
        # In a real implementation, this would connect to RedisGraph or other database
        # to retrieve KPIs related to the objectives
        
        # For demonstration, return empty for now
        # (This would be replaced with actual code for retrieving from a database)
        kpis = []
        
        # In the actual implementation, you would use something like:
        # redis_graph_store = RedisGraphStore()
        # strategic_map = StrategicMap(redis_graph_store, state.strategic_map_name)
        # 
        # for objective in state.retrieved_objectives:
        #     objective_id = objective['o']['id']
        #     objective_kpis = strategic_map.get_kpis_for_objective(objective_id)
        #     kpis.extend(objective_kpis)
        
        return {"retrieved_kpis": kpis}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in KPIs retriever: {str(e)}"]}


def strategic_path_analyzer(state: RetrievalState) -> Dict:
    """Analyze strategic paths for the retrieved objectives."""
    try:
        # This is a placeholder for actual strategic path analysis
        # In a real implementation, this would analyze paths in the RedisGraph
        
        # For demonstration, return empty for now
        strategic_paths = []
        
        # In the actual implementation, you would use something like:
        # redis_graph_store = RedisGraphStore()
        # strategic_map = StrategicMap(redis_graph_store, state.strategic_map_name)
        # 
        # for objective in state.retrieved_objectives:
        #     objective_id = objective['o']['id']
        #     path = strategic_map.get_strategic_path(objective_id)
        #     strategic_paths.append({
        #         "objective_id": objective_id,
        #         "path": path
        #     })
        
        return {"strategic_paths": strategic_paths}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in strategic path analyzer: {str(e)}"]}


def related_kpis_finder(state: RetrievalState) -> Dict:
    """Find KPIs related to the retrieved KPIs."""
    try:
        # This is a placeholder for actual related KPI finding
        # In a real implementation, this would find related KPIs in the RedisGraph
        
        # For demonstration, return empty for now
        related_kpis = []
        
        # In the actual implementation, you would use something like:
        # redis_graph_store = RedisGraphStore()
        # strategic_map = StrategicMap(redis_graph_store, state.strategic_map_name)
        # 
        # for kpi in state.retrieved_kpis:
        #     kpi_id = kpi['k']['id']
        #     related = strategic_map.get_related_kpis(kpi_id)
        #     for rel_kpi in related:
        #         if rel_kpi not in related_kpis and rel_kpi not in state.retrieved_kpis:
        #             related_kpis.append(rel_kpi)
        
        return {"related_kpis": related_kpis}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in related KPIs finder: {str(e)}"]}


def insights_retriever(state: RetrievalState, insights_store: DocumentChromaStore) -> Dict:
    """Retrieve relevant insights from the vector store."""
    try:
        # Create search query based on user query and retrieved objectives/KPIs
        search_terms = [state.corrected_query or state.query]
        
        # Add objective names to enhance the search
        for obj in state.retrieved_objectives:
            if 'o' in obj and 'properties' in obj['o']:
                obj_name = obj['o']['properties'].get('name')
                if obj_name:
                    search_terms.append(obj_name)
        
        # Add KPI names to enhance the search
        for kpi in state.retrieved_kpis:
            if 'k' in kpi and 'properties' in kpi['k']:
                kpi_name = kpi['k']['properties'].get('name')
                if kpi_name:
                    search_terms.append(kpi_name)
        
        # Combine search terms into an enhanced query
        enhanced_query = " ".join(search_terms[:5])  # Limit to top 5 terms to avoid overly specific queries
        
        # Search for relevant insights
        retrieved_insights = insights_store.search(
            query=enhanced_query,
            k=5  # Retrieve top 5 relevant insights
        )
        
        return {"retrieved_insights": retrieved_insights}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in insights retriever: {str(e)}"]}


def insights_summarizer(state: RetrievalState) -> Dict:
    """Summarize the retrieved insights for integration into recommendations."""
    try:
        if not state.retrieved_insights:
            return {"insights_summary": "No relevant EDA insights found."}
        
        # Extract content and metadata from retrieved insights
        insights_content = []
        for i, doc in enumerate(state.retrieved_insights):
            insight_text = f"Insight {i+1}: {doc.metadata.get('title', 'Untitled')}\n"
            insight_text += f"Scenario: {doc.metadata.get('scenario', 'Unknown')}\n"
            insight_text += f"Content: {doc.page_content}\n"
            
            # Add tags if available
            tags = doc.metadata.get("tags", [])
            if tags:
                insight_text += f"Tags: {', '.join(tags)}\n"
                
            insights_content.append(insight_text)
        
        # Join all insights for summarization
        all_insights = "\n\n".join(insights_content)
        
        # Create summarization prompt
        summary_prompt = ChatPromptTemplate.from_template("""
        You are a business data analyst preparing a summary of exploratory data analysis insights 
        for a KPI recommendation system. Summarize the following insights, focusing on actionable 
        findings that would be relevant for KPI development and performance tracking.
        
        User Query: {query}
        
        EDA Insights:
        {insights}
        
        Create a concise summary that:
        1. Highlights the most relevant insights for the query
        2. Focuses on data patterns and trends that could inform KPI selection
        3. Notes any methodological approaches from the EDA that could be applied
        4. Integrates findings across multiple insights when appropriate
        
        Your summary should be structured, precise, and focused on how these insights can 
        support data-informed KPI development.
        """)
        
        llm = get_llm()
        chain = summary_prompt | llm | StrOutputParser()
        
        insights_summary = chain.invoke({
            "query": state.corrected_query or state.query,
            "insights": all_insights
        })
        
        return {"insights_summary": insights_summary}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in insights summarizer: {str(e)}"]}


def query_corrector(state: RetrievalState) -> Dict:
    """Correct the query if needed based on the context."""
    # If we already have sufficient context, no need to correct
    if state.retrieved_objectives and state.retrieved_kpis:
        return {"needs_correction": False}
    
    try:
        # Setup context for correction
        objectives_context = "\n".join([
            f"Objective: {obj['o']['properties'].get('name', 'Unnamed')} - "
            f"{obj['o']['properties'].get('description', 'No description')}"
            for obj in state.retrieved_objectives
        ])
        
        kpis_context = "\n".join([
            f"KPI: {kpi['k']['properties'].get('name', 'Unnamed')} - "
            f"{kpi['k']['properties'].get('description', 'No description')}"
            for kpi in state.retrieved_kpis
        ])
        
        # If no objectives or KPIs found, use placeholder or empty context
        if not objectives_context:
            objectives_context = "No strategic objectives retrieved."
        
        if not kpis_context:
            kpis_context = "No KPIs retrieved."
        
        correction_prompt = ChatPromptTemplate.from_template("""
        You are a strategic business analyst. Given the user query and the available strategic context,
        determine if the query needs to be corrected or expanded to better match the available objectives and KPIs.
        
        User Query: {query}
        
        Available Objectives:
        {objectives_context}
        
        Available KPIs:
        {kpis_context}
        
        First, determine if the query needs correction (YES/NO):
        
        If YES, provide the corrected query:
        [Corrected Query]: <corrected query here>
        
        If NO, simply state "No correction needed."
        """)
        
        llm = get_llm()
        chain = correction_prompt | llm | StrOutputParser()
        
        correction_result = chain.invoke({
            "query": state.query,
            "objectives_context": objectives_context,
            "kpis_context": kpis_context
        })
        
        # Extract correction decision and corrected query
        correction_needed = "YES" in correction_result.upper() and "[CORRECTED QUERY]" in correction_result.upper()
        
        if correction_needed:
            # Extract corrected query
            corrected_query_match = re.search(r'\[Corrected Query\]:\s*(.*)', correction_result, re.IGNORECASE)
            if corrected_query_match:
                corrected_query = corrected_query_match.group(1).strip()
                return {
                    "needs_correction": True,
                    "corrected_query": corrected_query
                }
        
        return {"needs_correction": False}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in query corrector: {str(e)}"]}


def kpi_recommender(state: RetrievalState) -> Dict:
    """Generate KPI recommendations based on the retrieved context."""
    try:
        # Prepare context for the recommendation model
        objectives_context = "\n".join([
            f"Objective: {obj['o']['properties'].get('name', 'Unnamed')} - "
            f"{obj['o']['properties'].get('description', 'No description')}"
            for obj in state.retrieved_objectives
        ]) or "No specific strategic objectives retrieved."
        
        kpis_context = "\n".join([
            f"KPI: {kpi['k']['properties'].get('name', 'Unnamed')} - "
            f"Description: {kpi['k']['properties'].get('description', 'No description')}, "
            f"Current: {kpi['k']['properties'].get('current', 'N/A')}, "
            f"Target: {kpi['k']['properties'].get('target', 'N/A')}, "
            f"Unit: {kpi['k']['properties'].get('unit', 'N/A')}"
            for kpi in state.retrieved_kpis + state.related_kpis
        ]) or "No existing KPIs retrieved."
        
        strategic_paths_context = []
        for path_info in state.strategic_paths:
            path_str = f"Strategic Path for Objective ID {path_info['objective_id']}:\n"
            path_nodes = []
            for node in path_info.get('path', []):
                node_name = node.get('name', 'Unnamed')
                node_desc = node.get('description', 'No description')
                path_nodes.append(f"- {node_name}: {node_desc}")
            path_str += "\n".join(path_nodes)
            strategic_paths_context.append(path_str)
            
        strategic_paths_str = "\n\n".join(strategic_paths_context) or "No strategic paths retrieved."
        
        # Include insights from EDA if available
        insights_context = state.insights_summary if state.insights_summary else "No relevant EDA insights available."
        
        # Include dataset metrics if available
        metrics_context = ""
        if state.relevant_metrics:
            metrics_list = []
            for metric in state.relevant_metrics:
                metric_str = f"Metric: {metric.get('name', 'Unnamed metric')}\n"
                metric_str += f"Description: {metric.get('description', 'No description')}\n"
                metric_str += f"Goal Relevance: {metric.get('goal_relevance', 'N/A')}\n"
                metric_str += f"Calculation: {metric.get('calculation', 'N/A')}"
                metrics_list.append(metric_str)
            
            metrics_context = "Relevant Metrics from Dataset:\n\n" + "\n\n".join(metrics_list)
        else:
            metrics_context = "No specific dataset metrics identified."
        
        # Include goal context if available
        goal_context_str = ""
        if state.goal_context:
            goal = state.goal_context.get("goal", "")
            scenarios = ", ".join(state.goal_context.get("similar_scenarios", []))
            
            goal_context_str = f"Business Goal: {goal}\n\nSimilar scenarios: {scenarios}"
        else:
            goal_context_str = f"Business Goal: {state.goal or state.query}"
        
        # Include dataset information if available
        dataset_context = ""
        if state.dataframe_schema or state.data_description:
            dataset_context = "Dataset Information:\n"
            if state.data_description:
                dataset_context += f"Description: {state.data_description}\n"
            if state.dataframe_schema:
                dataset_context += f"Schema: {json.dumps(state.dataframe_schema, indent=2)[:500]}...\n"
        else:
            dataset_context = "No specific dataset information provided."
        
        recommendation_prompt = ChatPromptTemplate.from_template("""
        You are a strategic business analyst specializing in KPI development and performance management.
        Based on the user's query, the strategic context, data analysis insights, and available dataset, 
        generate recommendations for KPIs that would help measure and track progress towards the relevant
        strategic objectives and business goals.
        
        User Query: {query}
        
        {goal_context}
        
        {dataset_context}
        
        Relevant Strategic Objectives:
        {objectives_context}
        
        Existing KPIs:
        {kpis_context}
        
        Strategic Paths:
        {strategic_paths}
        
        Data Analysis Insights:
        {insights_context}
        
        {metrics_context}
        
        Generate comprehensive KPI recommendations that:
        1. Address the user's specific query and business goal
        2. Align with the strategic objectives
        3. Complement existing KPIs
        4. Incorporate relevant data analysis insights
        5. Can be calculated or derived from the available dataset metrics
        6. Follow best practices for KPI design (SMART criteria)
        
        For each recommended KPI, provide:
        - Name
        - Description
        - Suggested target (if applicable)
        - Measurement unit (if applicable)
        - Justification (how it connects to objectives and business goals)
        - Implementation considerations
        - Data source considerations (based on dataset and EDA insights)
        - Calculation methodology (using available data metrics)
        
        Format each recommendation as a structured JSON object. Return a JSON array of recommendations:
        
        [
          {{
            "name": "KPI Name",
            "description": "Detailed description",
            "target": "Suggested target value",
            "unit": "Unit of measurement",
            "justification": "How this KPI connects to objectives and goals",
            "implementation": "Implementation considerations",
            "data_source": "Data source considerations based on available dataset",
            "calculation": "How to calculate this KPI using the dataset metrics"
          }},
          ...
        ]
        """)
        
        llm = get_llm(temperature=0.2)  # Slightly higher temperature for creative recommendations
        chain = recommendation_prompt | llm | StrOutputParser()
        
        recommendation_result = chain.invoke({
            "query": state.corrected_query or state.query,
            "goal_context": goal_context_str,
            "dataset_context": dataset_context,
            "objectives_context": objectives_context,
            "kpis_context": kpis_context,
            "strategic_paths": strategic_paths_str,
            "insights_context": insights_context,
            "metrics_context": metrics_context
        })
        
        # Parse the recommendations
        try:
            kpi_recommendations = json.loads(recommendation_result)
            if not isinstance(kpi_recommendations, list):
                raise ValueError("Recommendations should be a list")
        except Exception as e:
            # Fallback if JSON parsing fails
            return {"errors": state.errors + [f"Error parsing KPI recommendations: {str(e)}"]}
        
        return {"kpi_recommendations": kpi_recommendations}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in KPI recommender: {str(e)}"]}


def relevance_scorer(state: RetrievalState) -> Dict:
    """Score the relevance of KPI recommendations."""
    try:
        if not state.kpi_recommendations:
            return {"relevance_scores": {}}
        
        scoring_prompt = ChatPromptTemplate.from_template("""
        You are a strategic business analyst. Your task is to score the relevance of KPI recommendations
        to the user's query and the strategic objectives.
        
        User Query: {query}
        
        Strategic Objectives:
        {objectives_context}
        
        KPI Recommendation to Score:
        {recommendation}
        
        Score the recommendation on the following criteria:
        1. Relevance to Query (0-10): How directly does it address the user's specific question?
        2. Strategic Alignment (0-10): How well does it connect to strategic objectives?
        3. Measurability (0-10): How clear and measurable is the KPI?
        4. Actionability (0-10): How actionable are the insights from this KPI?
        5. Value-Added (0-10): Does this KPI add unique value not covered by existing KPIs?
        
        Provide a score for each criterion and a brief justification.
        Then calculate an overall score as the weighted average:
        Overall = (Relevance×0.3 + Alignment×0.3 + Measurability×0.15 + Actionability×0.15 + Value×0.1)
        
        Return a JSON object with the scores:
        
        {
          "relevance": X,
          "alignment": X,
          "measurability": X,
          "actionability": X,
          "value_added": X,
          "overall": X,
          "justification": "Brief explanation of scores"
        }
        """)
        
        llm = get_llm()
        chain = scoring_prompt | llm | StrOutputParser()
        
        # Prepare objectives context
        objectives_context = "\n".join([
            f"Objective: {obj['o']['properties'].get('name', 'Unnamed')} - "
            f"{obj['o']['properties'].get('description', 'No description')}"
            for obj in state.retrieved_objectives
        ]) or "No specific strategic objectives retrieved."
        
        relevance_scores = {}
        
        # Score each recommendation
        for idx, recommendation in enumerate(state.kpi_recommendations):
            recommendation_str = json.dumps(recommendation, indent=2)
            
            scoring_result = chain.invoke({
                "query": state.corrected_query or state.query,
                "objectives_context": objectives_context,
                "recommendation": recommendation_str
            })
            
            # Parse the scores
            try:
                scores = json.loads(scoring_result)
                if not isinstance(scores, dict):
                    raise ValueError("Scores should be a dictionary")
                    
                # Ensure the overall score is a number
                if isinstance(scores.get("overall"), str):
                    try:
                        scores["overall"] = float(scores["overall"])
                    except:
                        scores["overall"] = 0.0
                    
                relevance_scores[f"recommendation_{idx}"] = scores
                
            except Exception as e:
                # If parsing fails, assign a default score
                relevance_scores[f"recommendation_{idx}"] = {
                    "overall": 5.0,  # Default middle score
                    "error": str(e)
                }
        
        return {"relevance_scores": relevance_scores}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in relevance scorer: {str(e)}"]}


def response_generator(state: RetrievalState) -> Dict:
    """Generate the final response with KPI recommendations."""
    try:
        # Sort recommendations by relevance score
        scored_recommendations = []
        for idx, recommendation in enumerate(state.kpi_recommendations):
            score_key = f"recommendation_{idx}"
            if score_key in state.relevance_scores:
                overall_score = state.relevance_scores[score_key].get("overall", 0.0)
                scored_recommendations.append((recommendation, overall_score))
        
        # Sort by score in descending order
        scored_recommendations.sort(key=lambda x: x[1], reverse=True)
        
        # Prepare sorted recommendations for the final response
        sorted_recommendations = [rec for rec, _ in scored_recommendations]
        
        # Generate final response
        response_prompt = ChatPromptTemplate.from_template("""
        You are a strategic business analyst providing KPI recommendations to the user.
        
        User Query: {query}
        
        Business Goal: {goal}
        
        Recommended KPIs (in order of relevance):
        {recommendations}
        
        Strategic Context:
        {strategic_context}
        
        Dataset Context:
        {dataset_context}
        
        Data Analysis Insights:
        {insights_context}
        
        Relevant Metrics:
        {metrics_context}
        
        Create a comprehensive response that:
        1. Addresses the user's specific query and business goal
        2. Presents the KPI recommendations clearly and in order of relevance
        3. Explains how these KPIs align with strategic objectives
        4. Highlights how the recommendations are based on the available dataset
        5. Explains how data analysis insights informed the recommendations
        6. Provides implementation guidance including data source and calculation methodology
        
        Keep your response well-structured and business-oriented, focusing on practical application.
        Include examples of how each KPI would be calculated using the available dataset metrics.
        """)
        
        # Prepare strategic context
        strategic_context = "\n".join([
            f"Objective: {obj['o']['properties'].get('name', 'Unnamed')} - "
            f"{obj['o']['properties'].get('description', 'No description')}"
            for obj in state.retrieved_objectives
        ]) or "No specific strategic objectives retrieved."
        
        # Prepare strategic paths if available
        if state.strategic_paths:
            strategic_paths_context = []
            for path_info in state.strategic_paths:
                if path_info.get('path'):
                    path_str = f"Strategic Path for Objective ID {path_info['objective_id']}:\n"
                    path_nodes = []
                    for node in path_info.get('path', []):
                        node_name = node.get('name', 'Unnamed')
                        node_desc = node.get('description', 'No description')
                        path_nodes.append(f"- {node_name}: {node_desc}")
                    path_str += "\n".join(path_nodes)
                    strategic_paths_context.append(path_str)
            
            strategic_context += "\n\n" + "\n\n".join(strategic_paths_context)
        
        llm = get_llm(temperature=0.2)  # Slightly higher temperature for natural response
        chain = response_prompt | llm | StrOutputParser()
        
        recommendations_str = json.dumps(sorted_recommendations, indent=2)
        
        # Include insights summary in the response
        insights_context = state.insights_summary if state.insights_summary else "No relevant EDA insights available."
        
        # Prepare dataset context
        dataset_context = ""
        if state.dataframe_schema or state.data_description:
            dataset_context = "Dataset Information:\n"
            if state.data_description:
                dataset_context += f"Description: {state.data_description}\n"
            if state.dataframe_schema:
                dataset_context += "Schema: Available columns for KPI calculation\n"
        else:
            dataset_context = "No specific dataset information provided."
        
        # Prepare metrics context
        metrics_context = ""
        if state.relevant_metrics:
            metrics_list = []
            for metric in state.relevant_metrics:
                metrics_list.append(f"- {metric.get('name')}: {metric.get('description')}")
            
            metrics_context = "\n".join(metrics_list)
        else:
            metrics_context = "No specific dataset metrics identified."
        
        final_response = chain.invoke({
            "query": state.corrected_query or state.query,
            "goal": state.goal or state.query,
            "recommendations": recommendations_str,
            "strategic_context": strategic_context,
            "dataset_context": dataset_context,
            "insights_context": insights_context,
            "metrics_context": metrics_context
        })
        
        return {"final_response": final_response}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in response generator: {str(e)}"]}


# Main graph builder
def build_kpi_recommendation_graph():
    """Build the LangGraph for KPI recommendations."""
    # Define the graph
    workflow = StateGraph(RetrievalState)
    
    # Add nodes
    workflow.add_node(NodeType.GOAL_CONTEXT_FINDER, goal_context_finder)
    workflow.add_node(NodeType.DATASET_METRICS_ANALYZER, dataset_metrics_analyzer)
    workflow.add_node(NodeType.OBJECTIVES_RETRIEVER, objectives_retriever)
    workflow.add_node(NodeType.KPIS_RETRIEVER, kpis_retriever)
    workflow.add_node(NodeType.STRATEGIC_PATH_ANALYZER, strategic_path_analyzer)
    workflow.add_node(NodeType.RELATED_KPIS_FINDER, related_kpis_finder)
    workflow.add_node(NodeType.INSIGHTS_RETRIEVER, insights_retriever)
    workflow.add_node(NodeType.INSIGHTS_SUMMARIZER, insights_summarizer)
    workflow.add_node(NodeType.QUERY_CORRECTOR, query_corrector)
    workflow.add_node(NodeType.KPI_RECOMMENDER, kpi_recommender)
    workflow.add_node(NodeType.RELEVANCE_SCORER, relevance_scorer)
    workflow.add_node(NodeType.RESPONSE_GENERATOR, response_generator)
    
    # Define the edges
    # Start with goal context and dataset analysis
    workflow.add_edge(NodeType.GOAL_CONTEXT_FINDER, NodeType.DATASET_METRICS_ANALYZER)
    workflow.add_edge(NodeType.DATASET_METRICS_ANALYZER, NodeType.OBJECTIVES_RETRIEVER)
    
    # Continue with the existing flow
    workflow.add_edge(NodeType.OBJECTIVES_RETRIEVER, NodeType.KPIS_RETRIEVER)
    workflow.add_edge(NodeType.KPIS_RETRIEVER, NodeType.QUERY_CORRECTOR)
    
    # Conditional edge from query_corrector
    workflow.add_conditional_edges(
        NodeType.QUERY_CORRECTOR,
        # If needs correction, go back to objectives retriever with corrected query
        {
            lambda state: state.needs_correction: NodeType.OBJECTIVES_RETRIEVER,
            lambda state: not state.needs_correction: NodeType.STRATEGIC_PATH_ANALYZER,
        }
    )
    
    workflow.add_edge(NodeType.STRATEGIC_PATH_ANALYZER, NodeType.RELATED_KPIS_FINDER)
    workflow.add_edge(NodeType.RELATED_KPIS_FINDER, NodeType.INSIGHTS_RETRIEVER)
    workflow.add_edge(NodeType.INSIGHTS_RETRIEVER, NodeType.INSIGHTS_SUMMARIZER)
    workflow.add_edge(NodeType.INSIGHTS_SUMMARIZER, NodeType.KPI_RECOMMENDER)
    workflow.add_edge(NodeType.KPI_RECOMMENDER, NodeType.RELEVANCE_SCORER)
    workflow.add_edge(NodeType.RELEVANCE_SCORER, NodeType.RESPONSE_GENERATOR)
    workflow.add_edge(NodeType.RESPONSE_GENERATOR, END)
    
    # Set the entry point
    workflow.set_entry_point(NodeType.GOAL_CONTEXT_FINDER)
    
    # Compile the graph
    return workflow.compile()


# Function to add sample insights for testing
def add_sample_insights(insights_store: DocumentChromaStore):
    """Add sample insights to the vector store for testing purposes."""
    
    
    
    sample_insights = [
        Document(
            page_content="""
            Our analysis of operational efficiency revealed:
            
            1. Process completion times followed a right-skewed distribution with outliers causing 40% of delays.
            2. Resource utilization showed significant idle capacity (23%) during peak demand periods.
            3. Handoff delays between departments accounted for 45% of total process time.
            4. Automated processes showed 3.5x higher consistency in completion times vs. manual processes.
            5. Batch processing of similar requests improved efficiency by 28% compared to individual processing.
            
            Analysis included process mining, queuing theory modeling, and discrete event simulation.
            """,
            metadata={
                "title": "Operational Efficiency Metrics",
                "scenario": "operational efficiency improvement",
                "tags": ["operations", "efficiency", "process", "optimization", "throughput"]
            }
        ),
        Document(
            page_content="""
            Our exploratory analysis of employee engagement data found:
            
            1. Team size showed a negative correlation with engagement scores (r=-0.42).
            2. Regular 1:1 meetings with managers corresponded to 27% higher engagement.
            3. Remote workers reported 12% higher satisfaction but 8% lower connection to company culture.
            4. Career development opportunities were the strongest predictor of retention (p<0.001).
            5. Engagement scores dropped predictably at specific tenure milestones (1 year, 3 years, 5 years).
            
            Methods included multivariate regression, factor analysis, and predictive modeling.
            """,
            metadata={
                "title": "Employee Engagement Factors",
                "scenario": "employee engagement improvement",
                "tags": ["HR", "engagement", "retention", "satisfaction", "culture"]
            }
        ),
        Document(
            page_content="""
            Our EDA of supply chain performance and resilience revealed:
            
            1. Single-source suppliers created vulnerability points in 34% of the supply network.
            2. Geographic concentration showed 68% of critical components originating from two regions.
            3. Lead time variability increased exponentially (r²=0.91) with distance from tier-1 suppliers.
            4. Inventory levels showed suboptimal patterns with excess stock (32% above optimal) for low-risk items.
            5. Demand forecast accuracy decreased sharply beyond a 60-day horizon.
            
            Analysis techniques included network modeling, Monte Carlo simulation, and time series forecasting.
            """,
            metadata={
                "title": "Supply Chain Resilience Analysis",
                "scenario": "supply chain optimization",
                "tags": ["supply chain", "logistics", "inventory", "risk", "forecasting"]
            }
        )
    ]
    insights_store.add_documents(sample_insights)
    print("Added sample insights to the vector store.")


# Main RAG function with preserved interface
def get_kpi_recommendations(
    query: str, 
    strategic_map_name: str,
    goal: Optional[str] = None,
    dataframe_schema: Optional[Dict[str, Any]] = None,
    dataframe_sample: Optional[List[Dict[str, Any]]] = None,
    dataframe_stats: Optional[Dict[str, Any]] = None,
    data_context: Optional[str] = None,
    data_description: Optional[str] = None,
    domain_context: Optional[str] = None
):
    """Get KPI recommendations based on a query, strategic map, and dataset information.
    
    Args:
        query: User query for KPI recommendations
        strategic_map_name: Name of the strategic map
        goal: Business goal for KPI recommendations
        dataframe_schema: Schema of the dataframe columns
        dataframe_sample: Sample rows from the dataframe
        dataframe_stats: Statistical summary of the dataframe
        data_context: Additional context about the data
        data_description: Description of the dataset
        domain_context: Business domain context
        
    Returns:
        KPI recommendations as a formatted response
    """
    # Initialize the graph
    graph = build_kpi_recommendation_graph()
    
    # Create initial state
    initial_state = RetrievalState(
        query=query,
        strategic_map_name=strategic_map_name,
        goal=goal,
        dataframe_schema=dataframe_schema,
        dataframe_sample=dataframe_sample,
        dataframe_stats=dataframe_stats,
        data_context=data_context,
        data_description=data_description,
        domain_context=domain_context
    )
    
    # Execute the graph
    result = graph.invoke(initial_state)
    
    # Return the final response
    if result.final_response:
        return result.final_response
    else:
        # Handle error case
        error_messages = result.errors if result.errors else ["Unknown error occurred"]
        return f"Error generating KPI recommendations: {'; '.join(error_messages)}"


# Example usage
if __name__ == "__main__":
    # Add sample insights to the vector store
    add_sample_insights()
    
    # Example query
    query = "What KPIs should we implement to improve our customer satisfaction?"
    strategic_map_name = "company_strategy"
    
    # Get recommendations
    recommendations = get_kpi_recommendations(query, strategic_map_name)
    
    print(recommendations)