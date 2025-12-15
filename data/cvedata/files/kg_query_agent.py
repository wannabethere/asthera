"""
Knowledge Graph Query Agent for Vulnerability Analytics
========================================================

This module uses the knowledge graph built by kg_builder.py to:
1. Parse natural language queries
2. Identify required calculation paths
3. Determine which functions to call
4. Generate SQL query instructions
5. Provide step-by-step guidance for query execution

The agent acts as an intelligent intermediary between natural language
and SQL, using the knowledge graph to plan optimal query execution.

Author: Vulnerability Analytics Team
Date: 2024-11-29
"""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
import json
import logging
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# QUERY INSTRUCTION MODELS
# =============================================================================

class QueryComplexity(Enum):
    """Query complexity levels"""
    SIMPLE = "simple"           # Single entity, single function
    MODERATE = "moderate"       # Multiple entities, single function
    COMPLEX = "complex"         # Multiple entities, multiple functions
    ADVANCED = "advanced"       # Multi-hop paths, composite calculations


@dataclass
class QueryIntent:
    """Represents the parsed intent of a natural language query"""
    original_query: str
    intent_type: str  # risk_analysis, vulnerability_assessment, breach_analysis, etc.
    complexity: QueryComplexity
    
    # Entities involved
    primary_entity: str
    related_entities: List[str] = field(default_factory=list)
    
    # Filters detected
    filters: Dict[str, Any] = field(default_factory=dict)
    
    # Aggregations detected
    group_by: List[str] = field(default_factory=list)
    order_by: List[Tuple[str, str]] = field(default_factory=list)  # (column, direction)
    limit: Optional[int] = None
    
    # Temporal aspects
    time_window: Optional[str] = None
    
    # Confidence scores
    confidence: float = 0.0


@dataclass
class CalculationStep:
    """Represents a single step in a calculation plan"""
    step_number: int
    description: str
    function_name: str
    input_attributes: List[str]
    output_name: str
    sql_fragment: str
    depends_on_steps: List[int] = field(default_factory=list)


@dataclass
class QueryPlan:
    """Complete plan for executing a query"""
    query_intent: QueryIntent
    
    # Calculation path
    calculation_path_id: str
    calculation_path_name: str
    calculation_steps: List[CalculationStep]
    
    # Required data
    required_entities: List[str]
    required_attributes: List[str]
    required_functions: List[str]
    
    # SQL components
    base_table: str
    joins: List[str]
    where_clauses: List[str]
    group_by_clause: Optional[str]
    order_by_clause: Optional[str]
    limit_clause: Optional[str]
    
    # Generated SQL
    final_sql: str
    
    # Explanation
    explanation: str
    chain_of_thought: List[str]


@dataclass
class QueryInstruction:
    """Complete instruction set for executing a query"""
    query: str
    query_plan: QueryPlan
    
    # Instructions
    instructions: str
    step_by_step_guide: List[str]
    
    # Alternative approaches
    alternative_paths: List[str] = field(default_factory=list)
    
    # Metadata
    estimated_complexity: str
    estimated_execution_time: str
    requires_materialized_views: List[str] = field(default_factory=list)


# =============================================================================
# KNOWLEDGE GRAPH QUERY AGENT
# =============================================================================

class KnowledgeGraphQueryAgent:
    """Agent that uses knowledge graph to plan and instruct SQL generation"""
    
    def __init__(self, kg_directory: str = "./chromadb_kg_builder"):
        """Initialize agent with knowledge graph from ChromaDB"""
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=kg_directory
        ))
        
        # Load collections
        self.collections = {
            "entity_schemas": self.client.get_collection("kg_entity_schemas"),
            "calculation_paths": self.client.get_collection("kg_calculation_paths"),
            "function_definitions": self.client.get_collection("kg_function_definitions"),
            "attribute_dependencies": self.client.get_collection("kg_attribute_dependencies")
        }
        
        logger.info("KnowledgeGraphQueryAgent initialized")
    
    # =========================================================================
    # QUERY PARSING
    # =========================================================================
    
    def parse_query(self, natural_language_query: str) -> QueryIntent:
        """Parse natural language query to determine intent"""
        
        query_lower = natural_language_query.lower()
        
        # Determine intent type
        intent_type = self._determine_intent_type(query_lower)
        
        # Determine primary entity
        primary_entity = self._identify_primary_entity(query_lower)
        
        # Extract filters
        filters = self._extract_filters(query_lower)
        
        # Extract aggregations
        group_by, order_by, limit = self._extract_aggregations(query_lower)
        
        # Extract time window
        time_window = self._extract_time_window(query_lower)
        
        # Determine complexity
        complexity = self._determine_complexity(intent_type, filters, group_by)
        
        # Calculate confidence
        confidence = self._calculate_confidence(primary_entity, intent_type)
        
        return QueryIntent(
            original_query=natural_language_query,
            intent_type=intent_type,
            complexity=complexity,
            primary_entity=primary_entity,
            filters=filters,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            time_window=time_window,
            confidence=confidence
        )
    
    def _determine_intent_type(self, query: str) -> str:
        """Determine the type of query intent"""
        intent_patterns = {
            "risk_analysis": ["risk", "risky", "dangerous", "threat level"],
            "vulnerability_assessment": ["vulnerability", "cve", "exploit", "weakness"],
            "exploitability": ["exploit", "attack", "how easy", "difficulty"],
            "impact_analysis": ["impact", "damage", "effect", "consequence"],
            "breach_analysis": ["breach", "attack vector", "threat method"],
            "time_series": ["trend", "over time", "historical", "evolution", "forecast"],
            "compliance": ["compliance", "sla", "policy", "audit"],
            "patch_analysis": ["patch", "fix", "remediation", "update"],
            "asset_inventory": ["assets", "devices", "systems", "inventory"],
            "software_analysis": ["software", "application", "package", "program"]
        }
        
        for intent, patterns in intent_patterns.items():
            if any(pattern in query for pattern in patterns):
                return intent
        
        return "general_query"
    
    def _identify_primary_entity(self, query: str) -> str:
        """Identify the primary entity being queried"""
        entity_keywords = {
            "Asset": ["asset", "device", "system", "host", "server", "workstation"],
            "Vulnerability": ["vulnerability", "cve", "exploit", "weakness"],
            "Software": ["software", "application", "package", "program"],
            "BreachMethod": ["breach", "attack vector", "threat method"]
        }
        
        for entity, keywords in entity_keywords.items():
            if any(keyword in query for keyword in keywords):
                return entity
        
        return "Asset"  # Default
    
    def _extract_filters(self, query: str) -> Dict[str, Any]:
        """Extract filter conditions from query"""
        filters = {}
        
        # Severity filters
        if "critical" in query:
            if "mission critical" in query:
                filters["impact_class"] = "Mission Critical"
            else:
                filters["severity"] = "CRITICAL"
        elif "high" in query and "severity" in query:
            filters["severity"] = "HIGH"
        
        # Network filters
        if "perimeter" in query:
            filters["propagation_class"] = "Perimeter"
        elif "core" in query:
            filters["propagation_class"] = "Core"
        
        # State filters
        if "active" in query:
            filters["state"] = "ACTIVE"
        
        # CISA filters
        if "cisa" in query or "known exploit" in query:
            filters["has_cisa_exploit"] = True
        
        # Attack vector filters
        if "network" in query and ("attack" in query or "vector" in query):
            filters["attack_vector"] = "N"
        
        # Patch filters
        if "unpatched" in query:
            filters["has_patch_available"] = True
        
        return filters
    
    def _extract_aggregations(self, query: str) -> Tuple[List[str], List[Tuple[str, str]], Optional[int]]:
        """Extract aggregation requirements"""
        group_by = []
        order_by = []
        limit = None
        
        # Group by detection
        if "per asset" in query or "each asset" in query or "by asset" in query:
            group_by.extend(["asset_id", "asset_name"])
        elif "per cve" in query or "each cve" in query or "by cve" in query:
            group_by.append("cve_id")
        elif "per software" in query or "by software" in query:
            group_by.extend(["vendor", "product", "version"])
        
        # Order by detection
        if "highest risk" in query or "most risky" in query:
            order_by.append(("risk_score", "DESC"))
        elif "lowest risk" in query:
            order_by.append(("risk_score", "ASC"))
        elif "most recent" in query or "latest" in query:
            order_by.append(("detected_time", "DESC"))
        elif "oldest" in query:
            order_by.append(("detected_time", "ASC"))
        
        # Limit detection
        if "top 10" in query:
            limit = 10
        elif "top 20" in query:
            limit = 20
        elif "top 50" in query:
            limit = 50
        elif "top" in query:
            limit = 10
        
        return group_by, order_by, limit
    
    def _extract_time_window(self, query: str) -> Optional[str]:
        """Extract time window from query"""
        if "last 24 hours" in query or "past day" in query:
            return "1 day"
        elif "last 7 days" in query or "past week" in query:
            return "7 days"
        elif "last 30 days" in query or "past month" in query:
            return "30 days"
        elif "last 90 days" in query:
            return "90 days"
        
        return None
    
    def _determine_complexity(self, intent_type: str, filters: Dict, group_by: List[str]) -> QueryComplexity:
        """Determine query complexity"""
        complexity_score = 0
        
        # Intent complexity
        complex_intents = ["breach_analysis", "time_series", "compliance"]
        if intent_type in complex_intents:
            complexity_score += 2
        
        # Filter complexity
        complexity_score += len(filters)
        
        # Aggregation complexity
        if group_by:
            complexity_score += 1
        
        # Determine level
        if complexity_score <= 2:
            return QueryComplexity.SIMPLE
        elif complexity_score <= 4:
            return QueryComplexity.MODERATE
        elif complexity_score <= 6:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.ADVANCED
    
    def _calculate_confidence(self, primary_entity: str, intent_type: str) -> float:
        """Calculate confidence in query understanding"""
        confidence = 0.5
        
        if primary_entity != "Asset":  # Successfully identified specific entity
            confidence += 0.2
        
        if intent_type != "general_query":  # Successfully identified intent
            confidence += 0.3
        
        return min(confidence, 1.0)
    
    # =========================================================================
    # CALCULATION PATH SELECTION
    # =========================================================================
    
    def find_calculation_paths(self, query_intent: QueryIntent) -> List[Dict]:
        """Find relevant calculation paths from knowledge graph"""
        
        # Build search query
        search_query = f"{query_intent.intent_type} {query_intent.primary_entity}"
        
        # Search calculation paths
        results = self.collections["calculation_paths"].query(
            query_texts=[search_query],
            n_results=5,
            where={"source_entity": query_intent.primary_entity} if query_intent.primary_entity else None
        )
        
        return results
    
    def select_best_path(self, query_intent: QueryIntent, path_results: Dict) -> Dict:
        """Select the best calculation path for the query"""
        
        if not path_results.get("ids"):
            return None
        
        # For now, select the top result
        # In production, implement more sophisticated selection logic
        return {
            "path_id": path_results["ids"][0][0],
            "metadata": path_results["metadatas"][0][0],
            "document": path_results["documents"][0][0],
            "distance": path_results["distances"][0][0]
        }
    
    # =========================================================================
    # QUERY PLAN GENERATION
    # =========================================================================
    
    def generate_query_plan(self, query_intent: QueryIntent) -> QueryPlan:
        """Generate complete query execution plan"""
        
        # Find calculation paths
        path_results = self.find_calculation_paths(query_intent)
        
        # Select best path
        selected_path = self.select_best_path(query_intent, path_results)
        
        if not selected_path:
            # Fallback plan
            return self._generate_fallback_plan(query_intent)
        
        # Extract path metadata
        path_metadata = selected_path["metadata"]
        
        # Build calculation steps
        calculation_steps = self._build_calculation_steps(path_metadata)
        
        # Generate SQL components
        base_table, joins, where_clauses = self._generate_sql_components(query_intent, path_metadata)
        
        # Build GROUP BY clause
        group_by_clause = None
        if query_intent.group_by:
            group_by_clause = f"GROUP BY {', '.join(query_intent.group_by)}"
        
        # Build ORDER BY clause
        order_by_clause = None
        if query_intent.order_by:
            order_parts = [f"{col} {direction}" for col, direction in query_intent.order_by]
            order_by_clause = f"ORDER BY {', '.join(order_parts)}"
        
        # Build LIMIT clause
        limit_clause = None
        if query_intent.limit:
            limit_clause = f"LIMIT {query_intent.limit}"
        
        # Generate final SQL
        final_sql = self._generate_final_sql(
            base_table, joins, where_clauses, 
            group_by_clause, order_by_clause, limit_clause,
            calculation_steps
        )
        
        # Generate explanation
        explanation = self._generate_explanation(query_intent, selected_path, calculation_steps)
        
        # Generate chain of thought
        chain_of_thought = self._generate_chain_of_thought(query_intent, calculation_steps)
        
        return QueryPlan(
            query_intent=query_intent,
            calculation_path_id=path_metadata.get("path_id", "unknown"),
            calculation_path_name=path_metadata.get("path_name", "Unknown Path"),
            calculation_steps=calculation_steps,
            required_entities=json.loads(path_metadata.get("requires_entities", "[]")),
            required_attributes=json.loads(path_metadata.get("source_attributes", "[]")),
            required_functions=json.loads(path_metadata.get("requires_functions", "[]")),
            base_table=base_table,
            joins=joins,
            where_clauses=where_clauses,
            group_by_clause=group_by_clause,
            order_by_clause=order_by_clause,
            limit_clause=limit_clause,
            final_sql=final_sql,
            explanation=explanation,
            chain_of_thought=chain_of_thought
        )
    
    def _build_calculation_steps(self, path_metadata: Dict) -> List[CalculationStep]:
        """Build calculation steps from path metadata"""
        steps = []
        
        target_function = path_metadata.get("target_function", "")
        source_attributes = json.loads(path_metadata.get("source_attributes", "[]"))
        
        if target_function:
            step = CalculationStep(
                step_number=1,
                description=f"Calculate {target_function.replace('calculate_', '')}",
                function_name=target_function,
                input_attributes=source_attributes,
                output_name=path_metadata.get("output_name", "calculated_value"),
                sql_fragment=f"{target_function}(...) as {path_metadata.get('output_name', 'calculated_value')}"
            )
            steps.append(step)
        
        return steps
    
    def _generate_sql_components(
        self, 
        query_intent: QueryIntent, 
        path_metadata: Dict
    ) -> Tuple[str, List[str], List[str]]:
        """Generate base SQL components"""
        
        # Determine base table based on calculation path
        calculation_type = path_metadata.get("calculation_type", "")
        
        if calculation_type == "risk" or calculation_type == "comprehensive_risk":
            base_table = "mv_vulnerability_risk_scores vrs"
            joins = [
                "JOIN assets a ON vrs.nuid = a.nuid AND vrs.dev_id = a.dev_id"
            ]
        elif calculation_type == "exploitability" or calculation_type == "impact":
            base_table = "mv_enriched_vulnerability_instances vi"
            joins = []
        elif calculation_type == "breach_likelihood":
            base_table = "mv_asset_breach_likelihood abl"
            joins = [
                "JOIN assets a ON abl.nuid = a.nuid AND abl.dev_id = a.dev_id"
            ]
        elif calculation_type == "time_series":
            base_table = "mv_vulnerability_timeseries ts"
            joins = []
        else:
            base_table = "assets a"
            joins = []
        
        # Build WHERE clauses
        where_clauses = []
        for key, value in query_intent.filters.items():
            if isinstance(value, bool):
                where_clauses.append(f"{key} = {str(value).upper()}")
            elif isinstance(value, str):
                where_clauses.append(f"{key} = '{value}'")
            else:
                where_clauses.append(f"{key} = {value}")
        
        # Add time window filter
        if query_intent.time_window:
            where_clauses.append(f"detected_time >= CURRENT_DATE - INTERVAL '{query_intent.time_window}'")
        
        return base_table, joins, where_clauses
    
    def _generate_final_sql(
        self,
        base_table: str,
        joins: List[str],
        where_clauses: List[str],
        group_by_clause: Optional[str],
        order_by_clause: Optional[str],
        limit_clause: Optional[str],
        calculation_steps: List[CalculationStep]
    ) -> str:
        """Generate final SQL query"""
        
        sql_parts = ["SELECT"]
        
        # Add select columns (simplified)
        sql_parts.append("    *")
        
        # Add calculation functions
        for step in calculation_steps:
            sql_parts.append(f"    , {step.sql_fragment}")
        
        # Add FROM
        sql_parts.append(f"FROM {base_table}")
        
        # Add JOINs
        for join in joins:
            sql_parts.append(join)
        
        # Add WHERE
        if where_clauses:
            sql_parts.append("WHERE")
            sql_parts.append("    " + "\n    AND ".join(where_clauses))
        
        # Add GROUP BY
        if group_by_clause:
            sql_parts.append(group_by_clause)
        
        # Add ORDER BY
        if order_by_clause:
            sql_parts.append(order_by_clause)
        
        # Add LIMIT
        if limit_clause:
            sql_parts.append(limit_clause)
        
        return "\n".join(sql_parts)
    
    def _generate_explanation(
        self, 
        query_intent: QueryIntent, 
        selected_path: Dict,
        calculation_steps: List[CalculationStep]
    ) -> str:
        """Generate human-readable explanation"""
        
        explanation = f"""
Query Analysis:
- Original Query: {query_intent.original_query}
- Intent Type: {query_intent.intent_type}
- Complexity: {query_intent.complexity.value}
- Primary Entity: {query_intent.primary_entity}
- Confidence: {query_intent.confidence:.2f}

Selected Calculation Path:
- Path: {selected_path['metadata'].get('path_name', 'Unknown')}
- Type: {selected_path['metadata'].get('calculation_type', 'Unknown')}

Calculation Steps:
"""
        for step in calculation_steps:
            explanation += f"{step.step_number}. {step.description} using {step.function_name}\n"
        
        explanation += f"\nFilters Applied: {len(query_intent.filters)}"
        for key, value in query_intent.filters.items():
            explanation += f"\n  - {key} = {value}"
        
        return explanation
    
    def _generate_chain_of_thought(
        self,
        query_intent: QueryIntent,
        calculation_steps: List[CalculationStep]
    ) -> List[str]:
        """Generate step-by-step reasoning"""
        
        cot = []
        
        cot.append(f"1. Identified query intent: {query_intent.intent_type}")
        cot.append(f"2. Primary entity: {query_intent.primary_entity}")
        cot.append(f"3. Extracted {len(query_intent.filters)} filter conditions")
        
        if calculation_steps:
            cot.append(f"4. Selected calculation path with {len(calculation_steps)} steps")
            for step in calculation_steps:
                cot.append(f"   - Step {step.step_number}: {step.description}")
        
        if query_intent.group_by:
            cot.append(f"5. Group results by: {', '.join(query_intent.group_by)}")
        
        if query_intent.order_by:
            cot.append(f"6. Sort results by: {', '.join([f'{col} {dir}' for col, dir in query_intent.order_by])}")
        
        if query_intent.limit:
            cot.append(f"7. Limit results to top {query_intent.limit}")
        
        return cot
    
    def _generate_fallback_plan(self, query_intent: QueryIntent) -> QueryPlan:
        """Generate fallback plan when no path is found"""
        
        return QueryPlan(
            query_intent=query_intent,
            calculation_path_id="fallback",
            calculation_path_name="Generic Query",
            calculation_steps=[],
            required_entities=[query_intent.primary_entity],
            required_attributes=[],
            required_functions=[],
            base_table="assets a",
            joins=[],
            where_clauses=[],
            group_by_clause=None,
            order_by_clause=None,
            limit_clause=None,
            final_sql="-- Fallback: No specific calculation path found",
            explanation="No specific calculation path found in knowledge graph",
            chain_of_thought=["Unable to find matching calculation path"]
        )
    
    # =========================================================================
    # INSTRUCTION GENERATION
    # =========================================================================
    
    def generate_instructions(self, natural_language_query: str) -> QueryInstruction:
        """Generate complete instructions for query execution"""
        
        # Parse query
        query_intent = self.parse_query(natural_language_query)
        
        # Generate query plan
        query_plan = self.generate_query_plan(query_intent)
        
        # Generate instructions
        instructions = self._format_instructions(query_plan)
        
        # Generate step-by-step guide
        step_by_step_guide = self._generate_step_by_step_guide(query_plan)
        
        # Find alternative paths
        alternative_paths = self._find_alternative_paths(query_intent)
        
        # Estimate complexity and execution time
        estimated_complexity = query_intent.complexity.value
        estimated_execution_time = self._estimate_execution_time(query_plan)
        
        # Identify required materialized views
        required_views = self._identify_required_views(query_plan)
        
        return QueryInstruction(
            query=natural_language_query,
            query_plan=query_plan,
            instructions=instructions,
            step_by_step_guide=step_by_step_guide,
            alternative_paths=alternative_paths,
            estimated_complexity=estimated_complexity,
            estimated_execution_time=estimated_execution_time,
            requires_materialized_views=required_views
        )
    
    def _format_instructions(self, query_plan: QueryPlan) -> str:
        """Format instructions for human/LLM consumption"""
        
        instructions = f"""
QUERY EXECUTION INSTRUCTIONS
=============================

Intent: {query_plan.query_intent.intent_type}
Complexity: {query_plan.query_intent.complexity.value}

CALCULATION PATH: {query_plan.calculation_path_name}

REQUIRED FUNCTIONS:
{chr(10).join([f"  - {func}" for func in query_plan.required_functions])}

REQUIRED ATTRIBUTES:
{chr(10).join([f"  - {attr}" for attr in query_plan.required_attributes[:10]])}

SQL STRUCTURE:
1. Base Table: {query_plan.base_table}
2. Joins: {len(query_plan.joins)} joins required
3. Filters: {len(query_plan.where_clauses)} filter conditions
4. Aggregations: {'Yes' if query_plan.group_by_clause else 'No'}

EXPLANATION:
{query_plan.explanation}
"""
        return instructions
    
    def _generate_step_by_step_guide(self, query_plan: QueryPlan) -> List[str]:
        """Generate step-by-step execution guide"""
        
        guide = []
        
        guide.append("Step 1: Identify base data source")
        guide.append(f"  → Use table/view: {query_plan.base_table}")
        
        if query_plan.joins:
            guide.append("Step 2: Join related entities")
            for i, join in enumerate(query_plan.joins, 1):
                guide.append(f"  → Join {i}: {join}")
        
        if query_plan.where_clauses:
            guide.append(f"Step 3: Apply {len(query_plan.where_clauses)} filter conditions")
            for clause in query_plan.where_clauses:
                guide.append(f"  → Filter: {clause}")
        
        if query_plan.calculation_steps:
            guide.append("Step 4: Execute calculations")
            for step in query_plan.calculation_steps:
                guide.append(f"  → {step.description}")
                guide.append(f"    Function: {step.function_name}")
                guide.append(f"    Inputs: {', '.join(step.input_attributes[:5])}")
                guide.append(f"    Output: {step.output_name}")
        
        if query_plan.group_by_clause:
            guide.append("Step 5: Group and aggregate results")
            guide.append(f"  → {query_plan.group_by_clause}")
        
        if query_plan.order_by_clause:
            guide.append("Step 6: Sort results")
            guide.append(f"  → {query_plan.order_by_clause}")
        
        if query_plan.limit_clause:
            guide.append("Step 7: Limit results")
            guide.append(f"  → {query_plan.limit_clause}")
        
        return guide
    
    def _find_alternative_paths(self, query_intent: QueryIntent) -> List[str]:
        """Find alternative calculation paths"""
        
        # Search for alternative paths
        results = self.collections["calculation_paths"].query(
            query_texts=[query_intent.intent_type],
            n_results=3,
            where={"source_entity": query_intent.primary_entity} if query_intent.primary_entity else None
        )
        
        alternatives = []
        if results.get("metadatas"):
            for metadata in results["metadatas"][0][1:]:  # Skip first (already selected)
                alternatives.append(metadata.get("path_name", "Unknown Path"))
        
        return alternatives
    
    def _estimate_execution_time(self, query_plan: QueryPlan) -> str:
        """Estimate query execution time"""
        
        complexity_score = 0
        
        # Factor in joins
        complexity_score += len(query_plan.joins) * 2
        
        # Factor in filters
        complexity_score += len(query_plan.where_clauses)
        
        # Factor in calculations
        complexity_score += len(query_plan.calculation_steps) * 3
        
        # Factor in aggregations
        if query_plan.group_by_clause:
            complexity_score += 2
        
        # Estimate time
        if complexity_score <= 5:
            return "< 1 second"
        elif complexity_score <= 10:
            return "1-5 seconds"
        elif complexity_score <= 15:
            return "5-10 seconds"
        else:
            return "> 10 seconds"
    
    def _identify_required_views(self, query_plan: QueryPlan) -> List[str]:
        """Identify required materialized views"""
        
        required_views = []
        
        base_table = query_plan.base_table
        
        if "mv_vulnerability_risk_scores" in base_table:
            required_views.append("mv_vulnerability_risk_scores")
        if "mv_enriched_vulnerability_instances" in base_table:
            required_views.append("mv_enriched_vulnerability_instances")
        if "mv_asset_breach_likelihood" in base_table:
            required_views.append("mv_asset_breach_likelihood")
        if "mv_vulnerability_timeseries" in base_table:
            required_views.append("mv_vulnerability_timeseries")
        
        return required_views
    
    # =========================================================================
    # EXPORT INSTRUCTIONS
    # =========================================================================
    
    def export_instruction_to_json(self, instruction: QueryInstruction, output_path: str):
        """Export instruction to JSON file"""
        
        instruction_dict = {
            "query": instruction.query,
            "instructions": instruction.instructions,
            "step_by_step_guide": instruction.step_by_step_guide,
            "sql": instruction.query_plan.final_sql,
            "chain_of_thought": instruction.query_plan.chain_of_thought,
            "estimated_complexity": instruction.estimated_complexity,
            "estimated_execution_time": instruction.estimated_execution_time,
            "required_functions": instruction.query_plan.required_functions,
            "required_attributes": instruction.query_plan.required_attributes,
            "requires_materialized_views": instruction.requires_materialized_views,
            "alternative_paths": instruction.alternative_paths
        }
        
        with open(output_path, 'w') as f:
            json.dump(instruction_dict, f, indent=2)
        
        logger.info(f"Exported instruction to {output_path}")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution function"""
    
    # Initialize agent
    agent = KnowledgeGraphQueryAgent(kg_directory="./chromadb_kg_builder")
    
    print("=" * 80)
    print("VULNERABILITY ANALYTICS KNOWLEDGE GRAPH QUERY AGENT")
    print("=" * 80)
    
    # Example queries
    example_queries = [
        "Which Mission Critical assets have CRITICAL vulnerabilities with Network attack vectors?",
        "Calculate the exploitability score for all active vulnerabilities",
        "Show me breach method likelihoods for Perimeter assets",
        "What is the comprehensive risk score for assets with unpatched vulnerabilities?",
        "Show vulnerability trends over the last 30 days"
    ]
    
    print("\nProcessing example queries...\n")
    
    for i, query in enumerate(example_queries, 1):
        print(f"\n{'='*80}")
        print(f"QUERY {i}: {query}")
        print('='*80)
        
        # Generate instructions
        instruction = agent.generate_instructions(query)
        
        # Display results
        print("\nINSTRUCTIONS:")
        print(instruction.instructions)
        
        print("\nSTEP-BY-STEP GUIDE:")
        for step in instruction.step_by_step_guide:
            print(step)
        
        print("\nGENERATED SQL:")
        print(instruction.query_plan.final_sql)
        
        print("\nCHAIN OF THOUGHT:")
        for thought in instruction.query_plan.chain_of_thought:
            print(f"  {thought}")
        
        print(f"\nESTIMATED COMPLEXITY: {instruction.estimated_complexity}")
        print(f"ESTIMATED EXECUTION TIME: {instruction.estimated_execution_time}")
        
        if instruction.alternative_paths:
            print(f"\nALTERNATIVE PATHS:")
            for alt in instruction.alternative_paths:
                print(f"  - {alt}")
        
        # Export to JSON
        output_path = f"query_instruction_{i}.json"
        agent.export_instruction_to_json(instruction, output_path)
        print(f"\n✓ Exported to {output_path}")
    
    print("\n" + "=" * 80)
    print("✓ All queries processed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()
