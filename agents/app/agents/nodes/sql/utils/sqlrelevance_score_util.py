import re
import json
import os
import logging
from typing import Dict, List, Tuple, Any, Optional
from enum import Enum
import datetime

logger = logging.getLogger("sql-relevance-scorer")


class SQLReasoningQuality(Enum):
    """SQL reasoning quality levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class SQLComplexityLevel(Enum):
    """SQL complexity levels"""
    SIMPLE = "simple"          # Single table, basic SELECT
    MODERATE = "moderate"      # Multiple tables, JOINs
    COMPLEX = "complex"        # Subqueries, CTEs, window functions
    ADVANCED = "advanced"      # Complex nested queries, multiple CTEs


class SQLRelevanceConfig:
    """Configuration class for SQL relevance scoring"""
    
    DEFAULT_CONFIG = {
        "reasoning_weight": 0.6,
        "sql_quality_weight": 0.4,
        "terminology_value": 0.02,
        "schema_relevance_weight": 0.3,
        "query_correctness_weight": 0.4,
        "reasoning_depth_weight": 0.3,
        
        "length_score_thresholds": {
            "comprehensive": {"threshold": 100, "score": 0.25},
            "detailed": {"threshold": 50, "score": 0.20},
            "adequate": {"threshold": 25, "score": 0.15},
            "minimal": {"threshold": 10, "score": 0.10},
            "insufficient": {"score": 0.05}
        },
        
        "sql_operations": {
            "basic_sql": {
                "terms": ["select", "from", "where", "group by", "order by", "having",
                         "insert", "update", "delete", "create", "alter", "drop"],
                "max_score": 0.15,
                "min_match_threshold": 2
            },
            "advanced_sql": {
                "terms": ["join", "inner join", "left join", "right join", "full join",
                         "union", "union all", "intersect", "except", "cte", "with",
                         "window function", "partition by", "row_number", "rank", "dense_rank",
                         "lead", "lag", "first_value", "last_value"],
                "max_score": 0.25,
                "min_match_threshold": 1
            },
            "sql_functions": {
                "terms": ["count", "sum", "avg", "min", "max", "concat", "substring", "length",
                         "upper", "lower", "trim", "coalesce", "case when", "cast", "convert",
                         "date", "datetime", "timestamp", "extract", "datepart"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "schema_understanding": {
                "terms": ["table", "column", "primary key", "foreign key", "index", "constraint",
                         "relationship", "schema", "database", "view", "materialized view"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "query_optimization": {
                "terms": ["index", "performance", "optimization", "explain", "execution plan",
                         "cost", "cardinality", "selectivity", "statistics", "hint"],
                "max_score": 0.15,
                "min_match_threshold": 1
            }
        },
        
        "reasoning_patterns": [
            r"first.*(?:identify|find|select).*(?:then|next|followed by)",
            r"step\s*\d+.*(?:analyze|examine|check)",
            r"(?:based on|given).*(?:schema|table structure)",
            r"(?:join|connect|link).*(?:tables|entities)",
            r"(?:filter|where|condition).*(?:to|for).*(?:get|obtain|retrieve)",
            r"(?:group|aggregate).*(?:by|using).*(?:to|for).*(?:calculate|compute)",
            r"(?:order|sort).*(?:by|using).*(?:to|for).*(?:display|show|present)"
        ],
        
        "sql_complexity_indicators": {
            "simple": {
                "patterns": [r"select.*from.*where", r"select.*from(?!.*join)", r"insert into.*values"],
                "score_bonus": 0.05
            },
            "moderate": {
                "patterns": [r"join", r"group by", r"having", r"union", r"subquery"],
                "score_bonus": 0.10
            },
            "complex": {
                "patterns": [r"with.*as.*\(", r"window function", r"partition by", r"cte"],
                "score_bonus": 0.15
            },
            "advanced": {
                "patterns": [r"recursive", r"multiple.*cte", r"nested.*subquer", r"complex.*join"],
                "score_bonus": 0.20
            }
        },
        
        "error_handling_indicators": [
            r"(?:handle|check|validate).*(?:null|missing|empty)",
            r"(?:prevent|avoid).*(?:error|exception)",
            r"(?:data type|type conversion|casting)",
            r"(?:edge case|boundary condition)",
            r"(?:validation|verification|constraint)"
        ],
        
        "schema_awareness_bonus": 0.25,
        "multi_step_reasoning_bonus": 0.20,
        "error_correction_bonus": 0.15
    }
    
    @classmethod
    def load_from_file(cls, file_path: str = None) -> dict:
        """Load configuration from JSON file with fallback to defaults"""
        config = cls.DEFAULT_CONFIG.copy()
        
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    file_config = json.load(f)
                    cls._deep_update(config, file_config)
                logger.info(f"Loaded SQL relevance config from {file_path}")
            except Exception as e:
                logger.warning(f"Error loading config file: {e}, using defaults")
        
        return config
    
    @staticmethod
    def _deep_update(original: dict, update: dict) -> dict:
        """Recursively update dictionary"""
        for key, value in update.items():
            if key in original and isinstance(original[key], dict) and isinstance(value, dict):
                SQLRelevanceConfig._deep_update(original[key], value)
            else:
                original[key] = value
        return original


class SQLAdvancedRelevanceScorer:
    """
    Advanced relevance scoring system for SQL RAG agents based on GRPO methodology.
    Evaluates reasoning quality, SQL correctness, schema awareness, and complexity handling.
    """
    
    def __init__(self, config_file_path: str = None, schema_context: dict = None):
        """
        Initialize the SQL relevance scoring system
        
        Args:
            config_file_path: Path to configuration JSON file
            schema_context: Database schema information
        """
        self.config = SQLRelevanceConfig.load_from_file(config_file_path)
        self.schema_context = schema_context or {}
        
        # Extract key parameters
        self.reasoning_weight = self.config.get("reasoning_weight", 0.6)
        self.sql_quality_weight = self.config.get("sql_quality_weight", 0.4)
        self.terminology_value = self.config.get("terminology_value", 0.02)
        
        # Initialize schema understanding
        self.known_tables = set()
        self.known_columns = set()
        self._extract_schema_elements()
    
    def _extract_schema_elements(self):
        """Extract table and column names from schema context"""
        if not self.schema_context:
            return
        
        # Extract from various schema formats
        if "schema" in self.schema_context:
            schema = self.schema_context["schema"]
            if isinstance(schema, dict):
                for table_name, columns in schema.items():
                    self.known_tables.add(table_name.lower())
                    if isinstance(columns, list):
                        self.known_columns.update([col.lower() for col in columns])
        
        # Extract from database metadata
        if "tables" in self.schema_context:
            tables = self.schema_context["tables"]
            if isinstance(tables, list):
                for table in tables:
                    if isinstance(table, dict):
                        self.known_tables.add(table.get("name", "").lower())
                        if "columns" in table:
                            self.known_columns.update([col.get("name", "").lower() 
                                                     for col in table["columns"]])
    
    def _extract_reasoning_section(self, model_output: str) -> str:
        """Extract reasoning section from model output"""
        patterns = [
            (r"### REASONING ###\s*(.*?)(?=###|$)", re.DOTALL),
            (r"REASONING:\s*(.*?)(?=SQL:|PLAN:|$)", re.DOTALL),
            (r"Let's think step by step[.:]?\s*(.*?)(?=SQL:|PLAN:|$)", re.DOTALL),
            (r"Step-by-step reasoning[.:]?\s*(.*?)(?=SQL:|QUERY:|$)", re.DOTALL)
        ]
        
        for pattern, flags in patterns:
            match = re.search(pattern, model_output, flags)
            if match:
                return match.group(1).strip()
        
        # If no specific reasoning section found, return first part before SQL
        if "SELECT" in model_output.upper() or "WITH" in model_output.upper():
            parts = re.split(r'(?i)(SELECT|WITH)', model_output, 1)
            if len(parts) > 1:
                return parts[0].strip()
        
        return model_output[:500]  # Fallback to first 500 chars
    
    def _extract_sql_section(self, model_output: str) -> str:
        """Extract SQL query from model output"""
        # Look for SQL in JSON format
        json_match = re.search(r'\{\s*"sql"\s*:\s*"([^"]+)"\s*\}', model_output, re.IGNORECASE)
        if json_match:
            return json_match.group(1)
        
        # Look for SQL queries (SELECT, WITH, INSERT, UPDATE, DELETE)
        sql_patterns = [
            r'```sql\s*(.*?)\s*```',
            r'```\s*((?:SELECT|WITH|INSERT|UPDATE|DELETE).*?)```',
            r'((?:SELECT|WITH|INSERT|UPDATE|DELETE)(?:[^;]|;(?!\s*$))*)',
        ]
        
        for pattern in sql_patterns:
            matches = re.findall(pattern, model_output, re.IGNORECASE | re.DOTALL)
            if matches:
                return matches[0].strip()
        
        return ""
    
    def _calculate_reasoning_length_score(self, reasoning: str) -> float:
        """Calculate score based on reasoning length and depth"""
        word_count = len(reasoning.split())
        thresholds = self.config.get("length_score_thresholds", {})
        
        for level, config in thresholds.items():
            if level == "insufficient":
                continue
            threshold = config.get("threshold", 0)
            if word_count >= threshold:
                return config.get("score", 0.1)
        
        return thresholds.get("insufficient", {}).get("score", 0.05)
    
    def _detect_sql_operation_type(self, reasoning: str, sql: str) -> Tuple[str, dict]:
        """Detect the primary SQL operation type from reasoning and SQL"""
        combined_text = (reasoning + " " + sql).lower()
        operations = self.config.get("sql_operations", {})
        
        scores = {}
        for op_name, op_config in operations.items():
            terms = op_config.get("terms", [])
            count = sum(1 for term in terms if term.lower() in combined_text)
            min_threshold = op_config.get("min_match_threshold", 1)
            
            if count >= min_threshold:
                scores[op_name] = count
        
        if scores:
            best_operation = max(scores.items(), key=lambda x: x[1])
            return best_operation[0], operations.get(best_operation[0], {})
        
        return "basic_sql", operations.get("basic_sql", {})
    
    def _calculate_sql_terminology_score(self, reasoning: str, sql: str) -> dict:
        """Calculate score based on SQL-specific terminology usage"""
        operation_type, operation_config = self._detect_sql_operation_type(reasoning, sql)
        
        if not operation_config:
            return {
                "name": "basic_sql_terminology",
                "score": 0.05,
                "term_count": 0,
                "operation_type": "basic_sql"
            }
        
        terms = operation_config.get("terms", [])
        max_score = operation_config.get("max_score", 0.15)
        
        combined_text = (reasoning + " " + sql).lower()
        term_count = sum(1 for term in terms if term.lower() in combined_text)
        
        score = min(max_score, term_count * self.terminology_value)
        
        return {
            "name": f"{operation_type}_terminology",
            "score": score,
            "term_count": term_count,
            "operation_type": operation_type
        }
    
    def _calculate_reasoning_structure_score(self, reasoning: str) -> float:
        """Calculate score based on reasoning structure and organization"""
        lines = [line.strip() for line in reasoning.split('\n') if line.strip()]
        
        # Base score for number of logical steps
        if len(lines) >= 5:
            base_score = 0.20
        elif len(lines) >= 3:
            base_score = 0.15
        elif len(lines) >= 2:
            base_score = 0.10
        else:
            base_score = 0.05
        
        # Bonus for structured reasoning patterns
        pattern_score = 0.0
        reasoning_patterns = self.config.get("reasoning_patterns", [])
        
        for pattern in reasoning_patterns:
            if re.search(pattern, reasoning, re.IGNORECASE):
                pattern_score += 0.03
        
        return min(0.25, base_score + pattern_score)
    
    def _calculate_schema_awareness_score(self, reasoning: str, sql: str) -> float:
        """Calculate score based on schema awareness and table/column usage"""
        if not self.known_tables and not self.known_columns:
            return 0.0
        
        combined_text = (reasoning + " " + sql).lower()
        schema_bonus = self.config.get("schema_awareness_bonus", 0.25)
        
        # Check for table mentions
        table_mentions = sum(1 for table in self.known_tables 
                           if table in combined_text)
        
        # Check for column mentions
        column_mentions = sum(1 for column in self.known_columns 
                            if column in combined_text)
        
        # Schema understanding terms
        schema_terms = self.config.get("sql_operations", {}).get("schema_understanding", {}).get("terms", [])
        schema_term_count = sum(1 for term in schema_terms if term.lower() in combined_text)
        
        # Calculate score
        total_mentions = table_mentions + column_mentions + schema_term_count
        return min(schema_bonus, total_mentions * 0.03)
    
    def _calculate_complexity_handling_score(self, reasoning: str, sql: str) -> float:
        """Calculate score based on SQL complexity handling"""
        combined_text = (reasoning + " " + sql).lower()
        complexity_indicators = self.config.get("sql_complexity_indicators", {})
        
        max_bonus = 0.0
        detected_complexity = "simple"
        
        for complexity_level, config in complexity_indicators.items():
            patterns = config.get("patterns", [])
            bonus = config.get("score_bonus", 0.05)
            
            for pattern in patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    if bonus > max_bonus:
                        max_bonus = bonus
                        detected_complexity = complexity_level
                    break
        
        return max_bonus
    
    def _calculate_error_handling_awareness_score(self, reasoning: str) -> float:
        """Calculate score based on error handling and edge case awareness"""
        error_indicators = self.config.get("error_handling_indicators", [])
        
        mention_count = sum(1 for indicator in error_indicators 
                          if re.search(indicator, reasoning, re.IGNORECASE))
        
        return min(0.15, mention_count * 0.05)
    
    def _calculate_multi_step_reasoning_score(self, reasoning: str) -> float:
        """Calculate score for multi-step reasoning quality"""
        # Look for numbered steps or sequential indicators
        step_patterns = [
            r'\d+\.\s+',  # 1. 2. 3.
            r'step\s+\d+',  # step 1, step 2
            r'first.*then.*(?:finally|lastly)',
            r'initially.*next.*(?:then|finally)',
            r'(?:first|second|third|fourth|fifth).*(?:step|stage)'
        ]
        
        step_count = 0
        for pattern in step_patterns:
            matches = re.findall(pattern, reasoning, re.IGNORECASE)
            step_count += len(matches)
        
        multi_step_bonus = self.config.get("multi_step_reasoning_bonus", 0.20)
        
        if step_count >= 4:
            return multi_step_bonus
        elif step_count >= 3:
            return multi_step_bonus * 0.8
        elif step_count >= 2:
            return multi_step_bonus * 0.6
        else:
            return 0.0
    
    def _assess_sql_correctness(self, sql: str) -> dict:
        """Assess basic SQL correctness and structure"""
        if not sql.strip():
            return {"score": 0.0, "issues": ["Empty SQL query"]}
        
        issues = []
        score = 0.5  # Base score for having SQL
        
        # Check for basic SQL structure
        sql_upper = sql.upper()
        
        # Must have a primary command
        primary_commands = ["SELECT", "INSERT", "UPDATE", "DELETE", "WITH"]
        if any(cmd in sql_upper for cmd in primary_commands):
            score += 0.2
        else:
            issues.append("Missing primary SQL command")
        
        # Check for FROM clause if SELECT
        if "SELECT" in sql_upper and "FROM" not in sql_upper:
            issues.append("SELECT without FROM clause")
            score -= 0.1
        
        # Check for balanced parentheses
        if sql.count('(') != sql.count(')'):
            issues.append("Unbalanced parentheses")
            score -= 0.1
        
        # Check for basic syntax issues
        if sql.strip().endswith(','):
            issues.append("Query ends with comma")
            score -= 0.05
        
        # Bonus for proper formatting
        if re.search(r'\n\s+', sql):  # Has indentation
            score += 0.05
        
        # Bonus for comments
        if '--' in sql or '/*' in sql:
            score += 0.05
        
        return {
            "score": max(0.0, min(1.0, score)),
            "issues": issues
        }
    
    def score_sql_reasoning(self, model_output: str, original_query: str, 
                          schema_context: dict = None) -> dict:
        """
        Main scoring method for SQL reasoning and generation
        
        Args:
            model_output: Complete output from the SQL model
            original_query: Original natural language query
            schema_context: Database schema information
            
        Returns:
            Dictionary with detailed scoring components and final score
        """
        # Update schema context if provided
        if schema_context:
            self.schema_context.update(schema_context)
            self._extract_schema_elements()
        
        # Extract reasoning and SQL sections
        reasoning = self._extract_reasoning_section(model_output)
        sql_query = self._extract_sql_section(model_output)
        
        # Calculate reasoning component scores
        length_score = self._calculate_reasoning_length_score(reasoning)
        
        terminology_result = self._calculate_sql_terminology_score(reasoning, sql_query)
        terminology_score = terminology_result["score"]
        detected_operation = terminology_result["operation_type"]
        
        structure_score = self._calculate_reasoning_structure_score(reasoning)
        schema_awareness_score = self._calculate_schema_awareness_score(reasoning, sql_query)
        complexity_score = self._calculate_complexity_handling_score(reasoning, sql_query)
        error_handling_score = self._calculate_error_handling_awareness_score(reasoning)
        multi_step_score = self._calculate_multi_step_reasoning_score(reasoning)
        
        # Calculate SQL quality scores
        sql_correctness_result = self._assess_sql_correctness(sql_query)
        sql_correctness_score = sql_correctness_result["score"]
        
        # Combine reasoning scores
        reasoning_components = {
            "length_score": length_score,
            f"{detected_operation}_terminology_score": terminology_score,
            "structure_score": structure_score,
            "schema_awareness_score": schema_awareness_score,
            "complexity_handling_score": complexity_score,
            "error_handling_score": error_handling_score,
            "multi_step_reasoning_score": multi_step_score
        }
        
        combined_reasoning_score = sum(reasoning_components.values())
        
        # SQL quality components
        sql_components = {
            "sql_correctness_score": sql_correctness_score,
            "sql_issues": sql_correctness_result["issues"]
        }
        
        # Calculate final weighted score
        reasoning_weighted = combined_reasoning_score * self.reasoning_weight
        sql_weighted = sql_correctness_score * self.sql_quality_weight
        
        final_score = min(1.0, reasoning_weighted + sql_weighted)
        
        # Determine quality level
        if final_score >= 0.8:
            quality_level = SQLReasoningQuality.EXCELLENT
        elif final_score >= 0.6:
            quality_level = SQLReasoningQuality.GOOD
        elif final_score >= 0.4:
            quality_level = SQLReasoningQuality.FAIR
        else:
            quality_level = SQLReasoningQuality.POOR
        
        return {
            "extracted_reasoning": reasoning,
            "extracted_sql": sql_query,
            "reasoning_components": reasoning_components,
            "sql_components": sql_components,
            "combined_reasoning_score": combined_reasoning_score,
            "reasoning_weighted_score": reasoning_weighted,
            "sql_weighted_score": sql_weighted,
            "final_relevance_score": final_score,
            "quality_level": quality_level.value,
            "detected_operation_type": detected_operation,
            "weights_used": {
                "reasoning_weight": self.reasoning_weight,
                "sql_quality_weight": self.sql_quality_weight
            },
            "metadata": {
                "timestamp": datetime.datetime.now().isoformat(),
                "original_query": original_query,
                "schema_tables_known": len(self.known_tables),
                "schema_columns_known": len(self.known_columns)
            }
        }
    
    def score_sql_correction_quality(self, original_sql: str, corrected_sql: str, 
                                   error_message: str, reasoning: str) -> dict:
        """
        Score the quality of SQL error correction
        
        Args:
            original_sql: Original (incorrect) SQL
            corrected_sql: Corrected SQL
            error_message: Original error message
            reasoning: Reasoning for the correction
            
        Returns:
            Dictionary with correction quality scores
        """
        # Basic correction assessment
        original_assessment = self._assess_sql_correctness(original_sql)
        corrected_assessment = self._assess_sql_correctness(corrected_sql)
        
        improvement_score = corrected_assessment["score"] - original_assessment["score"]
        
        # Check if specific error was addressed
        error_addressed_score = 0.0
        if error_message:
            error_keywords = re.findall(r'\b\w+\b', error_message.lower())
            reasoning_lower = reasoning.lower()
            
            addressed_keywords = sum(1 for keyword in error_keywords 
                                   if keyword in reasoning_lower)
            
            if error_keywords:
                error_addressed_score = min(0.3, addressed_keywords / len(error_keywords))
        
        # Reasoning quality for correction
        correction_reasoning_score = self._calculate_reasoning_structure_score(reasoning)
        
        # Bonus for maintaining original intent
        intent_preservation_score = 0.2 if len(corrected_sql) > len(original_sql) * 0.7 else 0.1
        
        correction_bonus = self.config.get("error_correction_bonus", 0.15)
        
        total_correction_score = min(1.0, 
            improvement_score + 
            error_addressed_score + 
            correction_reasoning_score + 
            intent_preservation_score + 
            correction_bonus
        )
        
        return {
            "improvement_score": improvement_score,
            "error_addressed_score": error_addressed_score,
            "correction_reasoning_score": correction_reasoning_score,
            "intent_preservation_score": intent_preservation_score,
            "total_correction_score": total_correction_score,
            "original_sql_score": original_assessment["score"],
            "corrected_sql_score": corrected_assessment["score"],
            "original_issues": original_assessment["issues"],
            "remaining_issues": corrected_assessment["issues"]
        }
    
    def get_improvement_recommendations(self, scoring_result: dict) -> List[str]:
        """
        Generate improvement recommendations based on scoring results
        
        Args:
            scoring_result: Result from score_sql_reasoning method
            
        Returns:
            List of specific improvement recommendations
        """
        recommendations = []
        components = scoring_result.get("reasoning_components", {})
        final_score = scoring_result.get("final_relevance_score", 0.0)
        
        # General recommendations based on score
        if final_score < 0.4:
            recommendations.append("Overall reasoning quality needs significant improvement")
        
        # Specific component recommendations
        if components.get("length_score", 0) < 0.1:
            recommendations.append("Provide more detailed step-by-step reasoning")
        
        if components.get("structure_score", 0) < 0.1:
            recommendations.append("Organize reasoning into clear, numbered steps")
        
        if components.get("schema_awareness_score", 0) < 0.1:
            recommendations.append("Reference specific table and column names from the schema")
        
        if components.get("multi_step_reasoning_score", 0) < 0.1:
            recommendations.append("Break down complex queries into multiple logical steps")
        
        if components.get("error_handling_score", 0) < 0.05:
            recommendations.append("Consider edge cases and error handling in the reasoning")
        
        # SQL-specific recommendations
        sql_components = scoring_result.get("sql_components", {})
        if sql_components.get("sql_correctness_score", 0) < 0.5:
            recommendations.append("Improve SQL syntax and structure")
            
            issues = sql_components.get("sql_issues", [])
            for issue in issues[:3]:  # Show top 3 issues
                recommendations.append(f"Fix SQL issue: {issue}")
        
        # Operation-specific recommendations  
        operation_type = scoring_result.get("detected_operation_type", "")
        if "basic" in operation_type:
            recommendations.append("Consider using more advanced SQL features when appropriate")
        
        return recommendations[:5]  # Return top 5 recommendations





# Example usage and testing
async def test_sql_relevance_scoring():
    """Test the SQL relevance scoring system"""
    
    # Initialize scorer with schema context
    schema_context = {
        "schema": {
            "customers": ["customer_id", "name", "email", "signup_date"],
            "orders": ["order_id", "customer_id", "order_date", "total_amount"],
            "products": ["product_id", "name", "category", "price"]
        }
    }
    
    scorer = SQLAdvancedRelevanceScorer(schema_context=schema_context)
    
    # Test case 1: Good reasoning and SQL
    model_output_good = """
    ### REASONING ###
    To find customers who made orders in the last 30 days, I need to:
    1. First, identify the relevant tables: customers and orders
    2. Join these tables on customer_id to connect customer information with their orders
    3. Filter orders by order_date to only include recent orders (last 30 days)
    4. Use DISTINCT to avoid duplicate customers if they made multiple orders
    5. Select customer information to return the result
    
    ### SQL ###
    SELECT DISTINCT c.customer_id, c.name, c.email
    FROM customers c
    INNER JOIN orders o ON c.customer_id = o.customer_id
    WHERE o.order_date >= CURRENT_DATE - INTERVAL '30 days'
    ORDER BY c.name;
    """
    
    query_good = "Find all customers who made orders in the last 30 days"
    result_good = scorer.score_sql_reasoning(model_output_good, query_good)
    
    print("=== Good Example Results ===")
    print(f"Final Score: {result_good['final_relevance_score']:.3f}")
    print(f"Quality Level: {result_good['quality_level']}")
    print("Reasoning Components:")
    for component, score in result_good['reasoning_components'].items():
        print(f"  {component}: {score:.3f}")
    
    # Test case 2: Poor reasoning and SQL
    model_output_poor = """
    Get customers with orders.
    
    SELECT * FROM customers, orders;
    """
    
    query_poor = "Find customers with recent orders"
    result_poor = scorer.score_sql_reasoning(model_output_poor, query_poor)
    
    print("\n=== Poor Example Results ===")
    print(f"Final Score: {result_poor['final_relevance_score']:.3f}")
    print(f"Quality Level: {result_poor['quality_level']}")
    
    # Get recommendations
    recommendations = scorer.get_improvement_recommendations(result_poor)
    print("Improvement Recommendations:")
    for i, rec in enumerate(recommendations, 1):
        print(f"  {i}. {rec}")
    
    # Test correction scoring
    original_sql = "SELECT * FROM customer WHERE id = ?"
    corrected_sql = "SELECT * FROM customers WHERE customer_id = 1"
    error_msg = "Table 'customer' doesn't exist"
    reasoning = "The error indicates that table 'customer' doesn't exist. Looking at the schema, the correct table name is 'customers' (plural). Also, the column should be 'customer_id' based on the schema."
    
    correction_result = scorer.score_sql_correction_quality(
        original_sql, corrected_sql, error_msg, reasoning
    )
    
    print(f"\n=== Correction Quality Score ===")
    print(f"Total Correction Score: {correction_result['total_correction_score']:.3f}")
    print(f"Improvement: {correction_result['improvement_score']:.3f}")
    
    return result_good, result_poor, correction_result


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_sql_relevance_scoring())