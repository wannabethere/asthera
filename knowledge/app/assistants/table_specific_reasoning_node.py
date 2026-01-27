"""
Table-Specific Reasoning Node for Data Assistance

This node processes each curated table separately to find related metrics/KPIs/aggregations
from the breakdown for each table. It provides table-specific insights and recommendations.
"""
import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
import json

from .state import ContextualAssistantState

logger = logging.getLogger(__name__)


class TableSpecificReasoningNode:
    """Node that processes each curated table separately to find related metrics/KPIs/aggregations"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o"
    ):
        """
        Initialize the table-specific reasoning node
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)
        self.json_parser = JsonOutputParser()
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """
        Process each curated table separately to find related metrics/KPIs/aggregations
        
        This node:
        1. Takes curated tables from MDL reasoning
        2. For each table, finds related metrics/KPIs/aggregations from the breakdown
        3. Provides table-specific insights and recommendations
        4. Combines all table-specific reasoning into a comprehensive view
        """
        query = state.get("query", "")
        curated_tables = state.get("mdl_curated_tables", []) or state.get("suggested_tables", [])
        data_knowledge = state.get("data_knowledge", {})
        deep_research_review = state.get("deep_research_review", {})
        user_context = state.get("user_context", {})
        actor_type = state.get("actor_type", "consultant")
        
        if not query:
            logger.warning("TableSpecificReasoningNode: No query provided, skipping table-specific reasoning")
            return state
        
        if not curated_tables:
            logger.warning("TableSpecificReasoningNode: No curated tables, skipping table-specific reasoning")
            return state
        
        try:
            logger.info(f"TableSpecificReasoningNode: Starting table-specific reasoning for {len(curated_tables)} tables")
            
            # Extract available data
            schemas = data_knowledge.get("schemas", [])
            existing_metrics = data_knowledge.get("metrics", [])
            features = data_knowledge.get("features", [])
            controls = data_knowledge.get("controls", [])
            framework = data_knowledge.get("framework")
            
            # Get recommended features from deep research
            recommended_features = deep_research_review.get("recommended_features", [])
            
            # Process each table separately
            table_specific_insights = []
            
            for table_info in curated_tables:
                table_name = table_info.get("table_name", "")
                if not table_name:
                    continue
                
                logger.info(f"TableSpecificReasoningNode: Processing table: {table_name}")
                
                # Find schema for this table
                table_schema = None
                for schema in schemas:
                    if schema.get("table_name") == table_name:
                        table_schema = schema
                        break
                
                # Find related features for this table
                related_features = [
                    f for f in features + recommended_features
                    if table_name.lower() in str(f.get("related_tables", [])).lower() or
                       table_name.lower() in str(f.get("question", "")).lower() or
                       table_name.lower() in str(f.get("description", "")).lower()
                ]
                
                # Find related metrics for this table
                related_metrics = [
                    m for m in existing_metrics
                    if table_name.lower() in str(m.get("metric_name", "")).lower() or
                       table_name.lower() in str(m.get("description", "")).lower() or
                       table_name.lower() in str(m.get("metric_sql", "")).lower()
                ]
                
                # Generate table-specific reasoning
                table_insight = await self._reason_about_table(
                    query=query,
                    table_name=table_name,
                    table_info=table_info,
                    table_schema=table_schema,
                    related_features=related_features,
                    related_metrics=related_metrics,
                    controls=controls,
                    framework=framework
                )
                
                if table_insight:
                    table_specific_insights.append(table_insight)
            
            # Combine all table-specific insights
            combined_insights = self._combine_table_insights(table_specific_insights)
            
            # Store table-specific reasoning in state
            state["table_specific_reasoning"] = {
                "table_insights": table_specific_insights,
                "combined_insights": combined_insights,
                "total_tables_processed": len(table_specific_insights)
            }
            
            # Update data_knowledge with table-specific metrics/KPIs
            table_specific_features = []
            for insight in table_specific_insights:
                table_metrics = insight.get("recommended_metrics", [])
                for metric in table_metrics:
                    metric["source_table"] = insight.get("table_name")
                    metric["source"] = "table_specific_reasoning"
                    table_specific_features.append(metric)
            
            # Merge with existing features
            if "data_knowledge" not in state:
                state["data_knowledge"] = {}
            
            existing_features = state["data_knowledge"].get("features", [])
            all_features = {}
            
            # Add existing features
            for feature in existing_features:
                feature_name = feature.get("feature_name", "")
                if feature_name:
                    all_features[feature_name] = feature
            
            # Add table-specific features
            for feature in table_specific_features:
                feature_name = feature.get("feature_name", "")
                if feature_name:
                    if feature_name not in all_features:
                        all_features[feature_name] = feature
                    else:
                        # Merge - keep table-specific if it has more detail
                        existing = all_features[feature_name]
                        if feature.get("description") and len(feature.get("description", "")) > len(existing.get("description", "")):
                            all_features[feature_name] = feature
            
            state["data_knowledge"]["features"] = list(all_features.values())
            
            state["current_node"] = "table_reasoning"
            state["next_node"] = "data_assistance_qa"
            
            logger.info(f"TableSpecificReasoningNode: Processed {len(table_specific_insights)} tables, "
                       f"found {len(table_specific_features)} table-specific metrics/KPIs")
            
        except Exception as e:
            logger.error(f"TableSpecificReasoningNode: Error in table-specific reasoning: {str(e)}", exc_info=True)
            # Continue anyway - don't fail the entire workflow
            state["table_specific_reasoning"] = {
                "table_insights": [],
                "combined_insights": {},
                "total_tables_processed": 0,
                "error": str(e)
            }
            state["next_node"] = "data_assistance_qa"
            state["current_node"] = "table_reasoning"
        
        return state
    
    async def _reason_about_table(
        self,
        query: str,
        table_name: str,
        table_info: Dict[str, Any],
        table_schema: Optional[Dict[str, Any]],
        related_features: List[Dict[str, Any]],
        related_metrics: List[Dict[str, Any]],
        controls: List[Dict[str, Any]],
        framework: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Reason about a specific table to find related metrics/KPIs/aggregations"""
        
        try:
            # Format table schema
            schema_text = ""
            if table_schema:
                table_ddl = table_schema.get("table_ddl", "")
                schema_text = f"Table Schema:\n{table_ddl[:1000]}"
            else:
                schema_text = f"Table: {table_name}\nDescription: {table_info.get('description', 'No description available')}"
            
            # Format related features
            features_text = ""
            if related_features:
                features_text = "\nRelated Features/KPIs:\n"
                for f in related_features[:5]:
                    feature_name = f.get("feature_name") or f.get("display_name", "Unknown")
                    question = f.get("question") or f.get("natural_language_question", "")
                    features_text += f"- {feature_name}: {question[:150]}\n"
            else:
                features_text = "No related features found"
            
            # Format related metrics
            metrics_text = ""
            if related_metrics:
                metrics_text = "\nRelated Metrics:\n"
                for m in related_metrics[:5]:
                    metric_name = m.get("metric_name") or m.get("name", "Unknown")
                    description = m.get("description", "")
                    metrics_text += f"- {metric_name}: {description[:150]}\n"
            else:
                metrics_text = "No related metrics found"
            
            # Format controls
            controls_text = ""
            if controls:
                controls_text = "\nRelevant Controls:\n"
                for c in controls[:3]:
                    if isinstance(c, dict):
                        control_obj = c.get("control") or c
                        control_id = control_obj.get("control_id", "Unknown")
                        control_name = control_obj.get("control_name", "")
                        controls_text += f"- {control_id}: {control_name}\n"
            else:
                controls_text = "No controls specified"
            
            # Build prompt
            system_prompt = """You are an expert at analyzing database tables to find related metrics, KPIs, and aggregations.

Given a user question and a specific table, your task is to:
1. Analyze how this table relates to the question
2. Identify what metrics/KPIs/aggregations can be derived from this table
3. Recommend specific calculations or queries that would help answer the question
4. Identify any related features or metrics that are already available

Focus on providing actionable recommendations specific to this table.

Return JSON with:
- table_name: Name of the table
- relevance_to_question: How relevant this table is to answering the question (0.0 to 1.0)
- recommended_metrics: List of metric objects, each with:
  - feature_name: Name of the metric/KPI
  - natural_language_question: Natural language question describing what needs to be calculated
  - feature_type: Type (e.g., 'kpi', 'metric', 'aggregation', 'calculation')
  - description: What this metric measures and why it's relevant
  - calculation_approach: How to calculate this metric (SQL-like description or natural language)
  - related_columns: List of column names from the table that would be used
- insights: Key insights about how this table helps answer the question
- data_quality_notes: Any notes about data quality or availability for this table
"""
            
            prompt = f"""
User Question: {query}

Table Information:
{schema_text}

{features_text}

{metrics_text}

{controls_text}

Framework: {framework or 'Not specified'}

Analyze this table and recommend metrics/KPIs/aggregations that would help answer the user's question.
Focus on what can be calculated from this specific table.
"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            
            # Call LLM
            logger.debug(f"TableSpecificReasoningNode: Calling LLM for table {table_name}...")
            response = await self.llm.ainvoke(messages)
            
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Try to parse as JSON
            try:
                # Extract JSON from response if it's wrapped in markdown code blocks
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    content = content[json_start:json_end].strip()
                elif "```" in content:
                    json_start = content.find("```") + 3
                    json_end = content.find("```", json_start)
                    content = content[json_start:json_end].strip()
                
                result = json.loads(content)
                result["table_name"] = table_name  # Ensure table_name is set
                return result
            except json.JSONDecodeError:
                logger.warning(f"TableSpecificReasoningNode: LLM response not in JSON format for table {table_name}, creating fallback")
                # Create fallback result
                return {
                    "table_name": table_name,
                    "relevance_to_question": 0.5,
                    "recommended_metrics": [],
                    "insights": content[:500],
                    "data_quality_notes": ""
                }
        
        except Exception as e:
            logger.error(f"TableSpecificReasoningNode: Error reasoning about table {table_name}: {str(e)}", exc_info=True)
            return None
    
    def _combine_table_insights(self, table_insights: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine insights from all tables into a comprehensive view"""
        
        combined = {
            "total_tables": len(table_insights),
            "total_metrics": 0,
            "high_relevance_tables": [],
            "all_recommended_metrics": [],
            "key_insights": [],
            "data_quality_summary": []
        }
        
        for insight in table_insights:
            table_name = insight.get("table_name", "")
            relevance = insight.get("relevance_to_question", 0.0)
            metrics = insight.get("recommended_metrics", [])
            insights = insight.get("insights", "")
            data_quality = insight.get("data_quality_notes", "")
            
            combined["total_metrics"] += len(metrics)
            combined["all_recommended_metrics"].extend(metrics)
            
            if relevance >= 0.7:
                combined["high_relevance_tables"].append({
                    "table_name": table_name,
                    "relevance": relevance,
                    "metrics_count": len(metrics)
                })
            
            if insights:
                combined["key_insights"].append({
                    "table": table_name,
                    "insight": insights
                })
            
            if data_quality:
                combined["data_quality_summary"].append({
                    "table": table_name,
                    "note": data_quality
                })
        
        return combined
