"""
Deep Research capabilities for feature engineering agents.

This module contains:
- DeepResearchReviewAgent: Reviews recommendations and relevancy scores
- Shared deep research utilities
"""

import re
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from app.agents.transform.feature_engineering_types import (
    FeatureEngineeringState,
    track_llm_call
)
from app.agents.transform.domain_config import DomainConfiguration

logger = logging.getLogger("lexy-ai-service")


class DeepResearchReviewAgent:
    """Deep Research Agent: Reviews recommendations and relevancy scores to ensure quality and completeness"""
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """
        Deep Research Review: Review all recommendations, relevancy scores, and ensure:
        1. All identified controls have corresponding features
        2. Natural language questions are detailed and executable
        3. Medallion architecture classification is correct
        4. Features align with user goals and examples
        5. Overall quality and completeness
        """
        
        domain_config = self._get_domain_config_from_state(state)
        user_query = state.get("user_query", "")
        analytical_intent = state.get("analytical_intent", {})
        features = state.get("recommended_features", [])
        identified_controls = state.get("identified_controls", [])
        relevance_scores = state.get("relevance_scores", {})
        feature_dependencies = state.get("feature_dependencies", {})
        validation_expectations = state.get("validation_expectations", [])
        
        system_prompt = f"""You are a deep research review expert for compliance risk estimation, monitoring, and reporting.

Your task is to review the entire feature engineering output and provide:
1. Quality assessment of recommendations
2. Coverage analysis (do all controls have features?)
3. Natural language question quality (are they detailed and executable?)
4. Medallion architecture validation (silver vs gold classification)
5. Alignment with user goals
6. Improvement recommendations

REVIEW CRITERIA:
1. Control Coverage: Every identified control should have at least 1 feature
2. Natural Language Questions: Must be detailed, step-by-step, executable (like demo examples)
3. Medallion Architecture: 
   - SILVER: Basic transformations from raw data
   - GOLD: Complex calculations requiring other transformations/aggregations
4. Goal Alignment: Features should directly support risk estimation, monitoring, and reporting
5. Quality: Based on relevancy scores, identify low-quality features that need improvement

Provide a comprehensive review with:
- Overall assessment
- Coverage gaps (missing controls)
- Quality issues (low scores, unclear questions)
- Architecture misclassifications
- Specific improvement recommendations"""

        features_text = "\n".join([
            f"{i+1}. {f.get('feature_name', 'Unknown')}\n"
            f"   Control: {f.get('compliance_reasoning', 'N/A')[:100]}\n"
            f"   NLQ: {f.get('natural_language_question', 'N/A')[:150]}\n"
            f"   Layer: {f.get('transformation_layer', 'N/A')}\n"
            f"   Score: {relevance_scores.get('feature_scores', [{}])[i].get('score', 'N/A') if i < len(relevance_scores.get('feature_scores', [])) else 'N/A'}"
            for i, f in enumerate(features)
        ])
        
        controls_text = "\n".join([
            f"{i+1}. {c.get('control_id', 'UNKNOWN')}: {c.get('control_name', 'N/A')}\n"
            f"   Key Measures: {', '.join(c.get('key_measures', [])[:3])}"
            for i, c in enumerate(identified_controls)
        ])
        
        expectations_text = ""
        if validation_expectations:
            expectations_text = "\n\nVALIDATION EXPECTATIONS:\n"
            for i, exp in enumerate(validation_expectations, 1):
                expectations_text += f"{i}. {exp}\n"
        
        prompt = f"""
USER QUERY: {user_query}

ANALYTICAL INTENT:
{analytical_intent}

IDENTIFIED CONTROLS ({len(identified_controls)}):
{controls_text}

RECOMMENDED FEATURES ({len(features)}):
{features_text}

RELEVANCE SCORES:
Overall Score: {relevance_scores.get('overall_score', 'N/A')}
Goal Alignment: {relevance_scores.get('goal_alignment', 'N/A')}
{expectations_text}

FEATURE DEPENDENCIES:
Total Steps: {feature_dependencies.get('total_steps', 'N/A')}
Calculation Sequence: {len(feature_dependencies.get('calculation_sequence', []))} groups

REVIEW QUESTIONS:
1. Do all identified controls have corresponding features?
2. Are natural language questions detailed and executable (like demo examples)?
3. Are medallion architecture classifications correct (silver vs gold)?
4. Are there any low-quality features (score < 0.7) that need improvement?
5. Are there any missing features for key compliance controls?
6. Do features align with user goals for risk estimation, monitoring, and reporting?

Provide a comprehensive review with specific recommendations."""

        try:
            response = await track_llm_call(
                agent_name="DeepResearchReviewAgent",
                llm=self.llm,
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ],
                state=state,
                step_name="deep_research_review"
            )
            
            review_content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse review and extract recommendations
            review_summary = self._parse_review(review_content, features, identified_controls, relevance_scores)
            
            state["deep_research_review"] = {
                "review_content": review_content,
                "review_summary": review_summary,
                "coverage_gaps": review_summary.get("coverage_gaps", []),
                "quality_issues": review_summary.get("quality_issues", []),
                "improvement_recommendations": review_summary.get("improvement_recommendations", [])
            }
            
            state["messages"].append(AIMessage(
                content=f"Deep research review completed: {review_summary.get('overall_assessment', 'Review completed')}",
                name="DeepResearchReviewAgent"
            ))
            state["next_agent"] = "end"
            
        except Exception as e:
            logger.error(f"Error in DeepResearchReviewAgent: {e}")
            state["deep_research_review"] = {
                "review_content": f"Review error: {str(e)}",
                "review_summary": {
                    "overall_assessment": "Review completed with errors",
                    "coverage_gaps": [],
                    "quality_issues": [],
                    "improvement_recommendations": []
                }
            }
            # Route to file writing (workflow will handle routing based on whether file_writer is enabled)
            state["next_agent"] = "write_output_file"
        
        return state
    
    def _parse_review(self, content: str, features: List[Dict[str, Any]], controls: List[Dict[str, Any]], scores: Dict[str, Any]) -> Dict[str, Any]:
        """Parse review content and extract structured information"""
        review_summary = {
            "overall_assessment": "",
            "coverage_gaps": [],
            "quality_issues": [],
            "improvement_recommendations": []
        }
        
        # Extract overall assessment
        assessment_match = re.search(r'(?:Overall|Assessment|Summary)[:\s]+([^\n]+(?:\n[^\n]+)*)', content, re.IGNORECASE)
        if assessment_match:
            review_summary["overall_assessment"] = assessment_match.group(1).strip()[:500]
        else:
            review_summary["overall_assessment"] = content[:500]
        
        # Extract coverage gaps
        coverage_match = re.search(r'(?:Coverage|Gaps|Missing)[:\s]+([^\n]+(?:\n[^\n]+)*)', content, re.IGNORECASE)
        if coverage_match:
            gaps_text = coverage_match.group(1)
            gaps = re.findall(r'[-•*]\s*([^\n]+)', gaps_text)
            review_summary["coverage_gaps"] = [g.strip() for g in gaps[:10]]
        
        # Extract quality issues
        quality_match = re.search(r'(?:Quality|Issues|Problems)[:\s]+([^\n]+(?:\n[^\n]+)*)', content, re.IGNORECASE)
        if quality_match:
            issues_text = quality_match.group(1)
            issues = re.findall(r'[-•*]\s*([^\n]+)', issues_text)
            review_summary["quality_issues"] = [i.strip() for i in issues[:10]]
        
        # Extract recommendations
        rec_match = re.search(r'(?:Recommendations|Improvements|Suggestions)[:\s]+([^\n]+(?:\n[^\n]+)*)', content, re.IGNORECASE)
        if rec_match:
            rec_text = rec_match.group(1)
            recs = re.findall(r'[-•*]\s*([^\n]+)', rec_text)
            review_summary["improvement_recommendations"] = [r.strip() for r in recs[:10]]
        
        # Check control coverage
        control_ids = {c.get("control_id", "") for c in controls}
        feature_controls = set()
        for f in features:
            compliance_reasoning = f.get("compliance_reasoning", "") or f.get("soc2_compliance_reasoning", "")
            # Extract control IDs from compliance reasoning
            for cid in control_ids:
                if cid in compliance_reasoning:
                    feature_controls.add(cid)
        
        missing_controls = control_ids - feature_controls
        if missing_controls:
            review_summary["coverage_gaps"].append(f"Missing features for controls: {', '.join(missing_controls)}")
        
        # Check for low-quality features
        feature_scores = scores.get("feature_scores", [])
        low_quality = [fs for fs in feature_scores if fs.get("score", 1.0) < 0.7]
        if low_quality:
            review_summary["quality_issues"].append(f"{len(low_quality)} features have scores below 0.7")
        
        return review_summary

