"""
Universal Risk Assessment Engine - Core Implementation
Uses LLM-powered transfer learning for domain-agnostic risk assessment
"""

import os
import json
import numpy as np
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import psycopg2
from pgvector.psycopg2 import register_vector
from anthropic import Anthropic
from openai import OpenAI
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

class RiskSpecification(BaseModel):
    """Natural language risk specification"""
    description: str = Field(..., description="Natural language risk description")
    domain: Optional[str] = Field(None, description="Risk domain (hr, security, finance, etc.)")
    entity: Optional[str] = Field(None, description="Entity being assessed")
    outcome: Optional[str] = Field(None, description="Negative outcome to predict")


class RiskParameter(BaseModel):
    """Universal risk parameter"""
    param_name: str
    param_type: str  # 'likelihood_factor', 'impact_factor', 'temporal_factor'
    data_source: str  # table.column
    semantic_meaning: str
    suggested_weight: float
    suggested_decay_function: Optional[str] = None
    decay_rate: Optional[float] = None
    reasoning: str


class RiskAnalysis(BaseModel):
    """LLM analysis of risk request"""
    domain: str
    entity: str
    outcome: str
    risk_classification: str
    likelihood_factors: List[RiskParameter]
    impact_factors: List[RiskParameter]
    temporal_factors: List[RiskParameter]
    similar_risk_patterns: List[str]


class AdaptedParameters(BaseModel):
    """Transfer-learned parameters"""
    likelihood_parameters: List[Dict]
    impact_parameters: List[Dict]
    transfer_confidence: float
    novel_adaptations: List[str]
    source_patterns: List[str]


class RiskResult(BaseModel):
    """Final risk assessment result"""
    entity_id: str
    risk_score: float
    likelihood: float
    impact: float
    risk_level: str
    explanation: str
    recommendations: List[str]
    contributing_factors: Dict
    transfer_confidence: float
    sql_used: Optional[str] = None


# ============================================================================
# UNIVERSAL RISK ENGINE
# ============================================================================

class UniversalRiskEngine:
    """
    LLM-powered universal risk assessment engine
    Uses transfer learning to work across any domain
    """
    
    def __init__(self, 
                 anthropic_api_key: str = None,
                 openai_api_key: str = None,
                 db_conn_string: str = None):
        """Initialize the risk engine"""
        
        self.anthropic_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.db_conn_string = db_conn_string or os.getenv("DATABASE_URL")
        
        if not all([self.anthropic_key, self.openai_key, self.db_conn_string]):
            raise ValueError("Missing required configuration. Check API keys and database connection.")
        
        # Initialize clients
        self.claude = Anthropic(api_key=self.anthropic_key)
        self.openai = OpenAI(api_key=self.openai_key)
        
        # Database connection
        self.conn = psycopg2.connect(self.db_conn_string)
        register_vector(self.conn)
        
        logger.info("UniversalRiskEngine initialized successfully")
    
    
    def understand_risk_request(self, 
                               specification: RiskSpecification,
                               schema_context: Dict) -> RiskAnalysis:
        """
        Use LLM to understand risk request and map to universal risk patterns
        
        Args:
            specification: Natural language risk specification
            schema_context: Available data schema
            
        Returns:
            Structured risk analysis
        """
        
        prompt = f"""You are a universal risk assessment expert. Analyze this risk calculation request:

REQUEST: {specification.description}
DOMAIN: {specification.domain or 'Not specified - please infer'}

AVAILABLE DATA SCHEMA:
{json.dumps(schema_context, indent=2)}

Your task:
1. Identify the risk domain (HR, Security, Finance, Operations, Compliance, etc.)
2. Identify the entity being assessed (employee, asset, customer, vendor, etc.)
3. Identify the negative outcome we're trying to predict (attrition, exploitation, churn, etc.)
4. Extract risk-relevant parameters from the schema
5. Map to universal risk dimensions:
   - LIKELIHOOD factors (what makes the outcome more/less likely)
   - IMPACT factors (how severe would the outcome be)
   - TEMPORAL factors (time-dependent risk patterns)
6. Suggest parameter weights based on risk theory and domain knowledge
7. Suggest decay functions for temporal factors

IMPORTANT: Only suggest parameters that exist in the provided schema.

Return your analysis in this EXACT JSON format:
{{
  "domain": "string (hr|security|finance|operations|compliance|other)",
  "entity": "string (employee|asset|customer|vendor|process|etc)", 
  "outcome": "string (attrition|exploitation|churn|disruption|violation|etc)",
  "risk_classification": "string (operational|strategic|financial|compliance|reputational)",
  "likelihood_factors": [
    {{
      "param_name": "descriptive_name",
      "param_type": "likelihood_factor",
      "data_source": "table_name.column_name",
      "semantic_meaning": "what this represents semantically",
      "suggested_weight": 0.35,
      "reasoning": "why this matters for likelihood"
    }}
  ],
  "impact_factors": [
    {{
      "param_name": "descriptive_name",
      "param_type": "impact_factor",
      "data_source": "table_name.column_name",
      "semantic_meaning": "what this represents",
      "suggested_weight": 0.30,
      "reasoning": "why this matters for impact"
    }}
  ],
  "temporal_factors": [
    {{
      "param_name": "descriptive_name",
      "param_type": "temporal_factor",
      "data_source": "table_name.column_name",
      "semantic_meaning": "temporal pattern",
      "suggested_decay_function": "exponential",
      "decay_rate": 30.0,
      "reasoning": "how time affects this factor"
    }}
  ],
  "similar_risk_patterns": [
    "describe 2-3 patterns from other domains that might apply"
  ]
}}

Provide ONLY the JSON, no other text."""

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extract JSON from response
            response_text = response.content[0].text
            
            # Find JSON in response (might have markdown fences)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            analysis_dict = json.loads(response_text.strip())
            
            # Convert to Pydantic model
            likelihood_factors = [RiskParameter(**f) for f in analysis_dict['likelihood_factors']]
            impact_factors = [RiskParameter(**f) for f in analysis_dict['impact_factors']]
            temporal_factors = [RiskParameter(**f) for f in analysis_dict.get('temporal_factors', [])]
            
            analysis = RiskAnalysis(
                domain=analysis_dict['domain'],
                entity=analysis_dict['entity'],
                outcome=analysis_dict['outcome'],
                risk_classification=analysis_dict['risk_classification'],
                likelihood_factors=likelihood_factors,
                impact_factors=impact_factors,
                temporal_factors=temporal_factors,
                similar_risk_patterns=analysis_dict.get('similar_risk_patterns', [])
            )
            
            logger.info(f"Risk analysis completed: {analysis.domain} - {analysis.outcome}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error in understand_risk_request: {e}")
            raise
    
    
    def generate_embeddings(self, text: str) -> np.ndarray:
        """
        Generate embeddings for semantic similarity
        
        Args:
            text: Text to embed
            
        Returns:
            1536-dimensional embedding vector
        """
        try:
            response = self.openai.embeddings.create(
                input=text,
                model="text-embedding-3-large"
            )
            
            embedding = np.array(response.data[0].embedding)
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    
    def find_similar_risk_patterns(self, 
                                   analysis: RiskAnalysis,
                                   limit: int = 5) -> List[Dict]:
        """
        Find similar risk patterns using semantic search
        Transfer learning from similar domains
        
        Args:
            analysis: Risk analysis from LLM
            limit: Number of similar patterns to retrieve
            
        Returns:
            List of similar risk patterns
        """
        try:
            # Create embedding from risk analysis
            risk_description = f"""
            Domain: {analysis.domain}
            Entity: {analysis.entity}
            Outcome: {analysis.outcome}
            Classification: {analysis.risk_classification}
            Factors: {', '.join([f.semantic_meaning for f in analysis.likelihood_factors])}
            """
            
            embedding = self.generate_embeddings(risk_description)
            
            # Vector similarity search
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT 
                    id,
                    domain,
                    pattern_name,
                    pattern_description,
                    parameter_template,
                    prediction_accuracy,
                    transferability_score,
                    embedding_vector <=> %s::vector as similarity
                FROM risk_patterns
                ORDER BY embedding_vector <=> %s::vector
                LIMIT %s
            """, (embedding.tolist(), embedding.tolist(), limit))
            
            results = cursor.fetchall()
            
            similar_patterns = []
            for row in results:
                similar_patterns.append({
                    'id': row[0],
                    'domain': row[1],
                    'pattern_name': row[2],
                    'description': row[3],
                    'parameter_template': row[4],
                    'accuracy': float(row[5]) if row[5] else 0.0,
                    'transferability': float(row[6]) if row[6] else 0.0,
                    'similarity': float(row[7])
                })
            
            logger.info(f"Found {len(similar_patterns)} similar patterns")
            return similar_patterns
            
        except Exception as e:
            logger.error(f"Error finding similar patterns: {e}")
            return []
    
    
    def transfer_learn_parameters(self, 
                                  analysis: RiskAnalysis,
                                  similar_patterns: List[Dict]) -> AdaptedParameters:
        """
        Use transfer learning to adapt parameters from similar domains
        
        Args:
            analysis: Risk analysis for target domain
            similar_patterns: Similar patterns from other domains
            
        Returns:
            Adapted parameters with transfer learning
        """
        
        if not similar_patterns:
            # No similar patterns, use LLM suggestions directly
            return self._format_parameters_from_analysis(analysis)
        
        # Use LLM to adapt parameters from similar patterns
        prompt = f"""You are adapting risk assessment parameters from similar domains using transfer learning.

TARGET RISK:
{analysis.model_dump_json(indent=2)}

SIMILAR PATTERNS FROM OTHER DOMAINS:
{json.dumps(similar_patterns, indent=2)}

Your task:
1. Identify which parameters from similar patterns can transfer to this new risk
2. Adapt the weights and decay functions based on domain differences
3. Combine insights from multiple similar patterns
4. Explain your reasoning for transfer decisions

Return adapted parameters in this EXACT JSON format:
{{
  "likelihood_parameters": [
    {{
      "param_name": "string",
      "param_value_source": "table.column",
      "param_weight": 0.35,
      "max_value": 100.0,
      "decay_function": "exponential",
      "decay_rate": 30.0,
      "time_delta": 0,
      "inverse": false,
      "transfer_reasoning": "how/why this transfers from similar patterns"
    }}
  ],
  "impact_parameters": [
    {{
      "param_name": "string",
      "param_value_source": "table.column",
      "param_weight": 0.30,
      "max_value": 100.0,
      "impact_category": "direct",
      "amplification_factor": 1.0,
      "transfer_reasoning": "how/why this transfers"
    }}
  ],
  "transfer_confidence": 0.82,
  "novel_adaptations": ["list any new insights specific to this domain"],
  "source_patterns": ["pattern_ids used"]
}}

Provide ONLY the JSON, no other text."""

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extract JSON
            response_text = response.content[0].text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            adapted_dict = json.loads(response_text.strip())
            
            adapted_params = AdaptedParameters(**adapted_dict)
            
            logger.info(f"Transfer learning completed with confidence: {adapted_params.transfer_confidence}")
            return adapted_params
            
        except Exception as e:
            logger.error(f"Error in transfer_learn_parameters: {e}")
            # Fallback to direct analysis
            return self._format_parameters_from_analysis(analysis)
    
    
    def _format_parameters_from_analysis(self, analysis: RiskAnalysis) -> AdaptedParameters:
        """
        Format parameters directly from LLM analysis (no transfer learning)
        """
        likelihood_params = []
        for factor in analysis.likelihood_factors:
            likelihood_params.append({
                "param_name": factor.param_name,
                "param_value_source": factor.data_source,
                "param_weight": factor.suggested_weight,
                "max_value": 100.0,
                "decay_function": "none",
                "decay_rate": 1.0,
                "time_delta": 0,
                "inverse": False,
                "transfer_reasoning": factor.reasoning
            })
        
        impact_params = []
        for factor in analysis.impact_factors:
            impact_params.append({
                "param_name": factor.param_name,
                "param_value_source": factor.data_source,
                "param_weight": factor.suggested_weight,
                "max_value": 100.0,
                "impact_category": "direct",
                "amplification_factor": 1.0,
                "transfer_reasoning": factor.reasoning
            })
        
        return AdaptedParameters(
            likelihood_parameters=likelihood_params,
            impact_parameters=impact_params,
            transfer_confidence=0.7,
            novel_adaptations=[],
            source_patterns=[]
        )
    
    
    def store_pattern_for_future_transfer(self,
                                         analysis: RiskAnalysis,
                                         params: AdaptedParameters,
                                         outcome_accuracy: Optional[float] = None) -> int:
        """
        Store successful risk pattern for future transfer learning
        
        Args:
            analysis: Risk analysis
            params: Adapted parameters
            outcome_accuracy: Actual accuracy if known
            
        Returns:
            Pattern ID
        """
        try:
            pattern_description = f"""
            {analysis.domain} - {analysis.outcome} risk assessment.
            Entity: {analysis.entity}
            Classification: {analysis.risk_classification}
            """
            
            embedding = self.generate_embeddings(pattern_description)
            
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO risk_patterns (
                    domain,
                    pattern_name,
                    pattern_description,
                    risk_type,
                    embedding_vector,
                    parameter_template,
                    prediction_accuracy,
                    transferability_score
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                analysis.domain,
                f"{analysis.entity}_{analysis.outcome}_risk",
                pattern_description,
                analysis.outcome,
                embedding.tolist(),
                json.dumps(params.model_dump()),
                outcome_accuracy or 0.0,
                params.transfer_confidence
            ))
            
            self.conn.commit()
            pattern_id = cursor.fetchone()[0]
            
            logger.info(f"Stored pattern {pattern_id} for future transfer learning")
            return pattern_id
            
        except Exception as e:
            logger.error(f"Error storing pattern: {e}")
            self.conn.rollback()
            raise
    
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_risk_engine() -> UniversalRiskEngine:
    """
    Create a new risk engine instance with environment configuration
    """
    return UniversalRiskEngine()


if __name__ == "__main__":
    # Example usage
    engine = create_risk_engine()
    
    # Test risk specification
    spec = RiskSpecification(
        description="Calculate employee attrition risk based on training engagement and manager relationships",
        domain="hr"
    )
    
    # Mock schema context
    schema_context = {
        "tables": ["transcript_csod", "user_csod"],
        "columns": ["completion_rate", "overdue_ratio", "days_since_last_login"]
    }
    
    # Analyze risk
    analysis = engine.understand_risk_request(spec, schema_context)
    print(f"Analysis: {analysis.model_dump_json(indent=2)}")
    
    engine.close()
