"""
Self-RAG Enhanced Analysis Intent Classification

This implementation incorporates self-RAG (Self-Reflective Retrieval-Augmented Generation) patterns:
1. Self-reflection on retrieval quality (ISREL token)
2. Self-reflection on generation quality (ISSUP, ISUSE tokens)
3. Self-correction mechanisms for poor quality outputs
4. Evaluation framework with pass-through capability

Based on the Self-RAG paper and LangGraph patterns, but implemented without stateful graphs.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
from langchain_core.output_parsers import JsonOutputParser
from enum import Enum

logger = logging.getLogger(__name__)

class QualityScore(Enum):
    """Quality assessment scores"""
    YES = "yes"
    NO = "no"
    RELEVANT = "relevant"
    IRRELEVANT = "irrelevant"
    FULLY_SUPPORTED = "fully_supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    NO_SUPPORT = "no_support"
    USEFUL = "useful"
    NOT_USEFUL = "not_useful"

class SelfRAGAnalysisIntentPlanner:
    """
    Self-RAG enhanced analysis intent planner with self-reflection and self-correction.
    """
    
    def __init__(self, llm, retrieval_helper=None, max_retries=3):
        self.llm = llm
        self.retrieval_helper = retrieval_helper
        self.max_retries = max_retries
        
        # Initialize output parsers
        self.json_parser = JsonOutputParser()
        self.string_parser = StrOutputParser()
    
    async def _assess_retrieval_relevance(
        self,
        question: str,
        retrieved_functions: List[Dict[str, Any]],
        step_context: str = ""
    ) -> Dict[str, Any]:
        """
        ISREL Token: Assess if retrieved functions are relevant to the question.
        
        Args:
            question: The user's question
            retrieved_functions: List of retrieved function definitions
            step_context: Context about the current analysis step
            
        Returns:
            Dictionary with relevance assessment
        """
        try:
            logger.info("Assessing retrieval relevance (ISREL token)")
            
            if not retrieved_functions:
                return {
                    "is_relevant": False,
                    "relevance_score": QualityScore.IRRELEVANT.value,
                    "reasoning": "No functions retrieved",
                    "filtered_functions": []
                }
            
            # Create prompt for relevance assessment
            relevance_prompt = PromptTemplate(
                input_variables=["question", "retrieved_functions", "step_context"],
                template="""
You are a grader assessing whether retrieved functions are relevant to a question.

### QUESTION ###
{question}

### STEP CONTEXT ###
{step_context}

### RETRIEVED FUNCTIONS ###
{retrieved_functions}

### TASK ###
For each retrieved function, determine if it provides useful information to solve the question.

### OUTPUT FORMAT ###
Provide your response as a JSON object:
{{
    "is_relevant": true/false,
    "relevance_score": "relevant" or "irrelevant",
    "reasoning": "Brief explanation of your assessment",
    "function_assessments": [
        {{
            "function_name": "function_name",
            "is_relevant": true/false,
            "relevance_reasoning": "Why this function is or isn't relevant"
        }}
    ],
    "filtered_functions": [list of relevant functions only]
}}
"""
            )
            
            # Format retrieved functions for the prompt
            functions_text = json.dumps(retrieved_functions, indent=2)
            
            # Generate assessment
            relevance_chain = relevance_prompt | self.llm | self.json_parser
            assessment = await relevance_chain.ainvoke({
                "question": question,
                "retrieved_functions": functions_text,
                "step_context": step_context
            })
            
            logger.info(f"Retrieval relevance assessment: {assessment.get('relevance_score')}")
            return assessment
            
        except Exception as e:
            logger.error(f"Error in retrieval relevance assessment: {e}")
            return {
                "is_relevant": False,
                "relevance_score": QualityScore.IRRELEVANT.value,
                "reasoning": f"Error in assessment: {str(e)}",
                "filtered_functions": []
            }
    
    async def _assess_generation_support(
        self,
        question: str,
        generation: Dict[str, Any],
        supporting_functions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        ISSUP Token: Assess if the generation is supported by the retrieved functions.
        
        Args:
            question: The user's question
            generation: The generated analysis plan or reasoning
            supporting_functions: Functions that should support the generation
            
        Returns:
            Dictionary with support assessment
        """
        try:
            logger.info("Assessing generation support (ISSUP token)")
            
            support_prompt = PromptTemplate(
                input_variables=["question", "generation", "supporting_functions"],
                template="""
You are a grader assessing whether a generated analysis plan is supported by available functions.

### QUESTION ###
{question}

### GENERATED ANALYSIS ###
{generation}

### SUPPORTING FUNCTIONS ###
{supporting_functions}

### TASK ###
Determine if all verification-worthy statements in the generation are supported by the available functions.

### OUTPUT FORMAT ###
Provide your response as a JSON object:
{{
    "is_supported": true/false,
    "support_score": "fully_supported", "partially_supported", or "no_support",
    "reasoning": "Brief explanation of your assessment",
    "unsupported_statements": [list of statements not supported by functions],
    "supported_statements": [list of statements that are supported],
    "missing_functions": [list of functions that would be needed for full support]
}}
"""
            )
            
            # Format inputs for the prompt
            generation_text = json.dumps(generation, indent=2)
            functions_text = json.dumps(supporting_functions, indent=2)
            
            # Generate assessment
            support_chain = support_prompt | self.llm | self.json_parser
            assessment = await support_chain.ainvoke({
                "question": question,
                "generation": generation_text,
                "supporting_functions": functions_text
            })
            
            logger.info(f"Generation support assessment: {assessment.get('support_score')}")
            return assessment
            
        except Exception as e:
            logger.error(f"Error in generation support assessment: {e}")
            return {
                "is_supported": False,
                "support_score": QualityScore.NO_SUPPORT.value,
                "reasoning": f"Error in assessment: {str(e)}",
                "unsupported_statements": [],
                "supported_statements": [],
                "missing_functions": []
            }
    
    async def _assess_generation_usefulness(
        self,
        question: str,
        generation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        ISUSE Token: Assess if the generation is useful for answering the question.
        
        Args:
            question: The user's question
            generation: The generated analysis plan or reasoning
            
        Returns:
            Dictionary with usefulness assessment
        """
        try:
            logger.info("Assessing generation usefulness (ISUSE token)")
            
            usefulness_prompt = PromptTemplate(
                input_variables=["question", "generation"],
                template="""
You are a grader assessing whether a generated analysis plan is useful for answering a question.

### QUESTION ###
{question}

### GENERATED ANALYSIS ###
{generation}

### TASK ###
Determine if the generation is a useful response to the question.

### OUTPUT FORMAT ###
Provide your response as a JSON object:
{{
    "is_useful": true/false,
    "usefulness_score": "useful" or "not_useful",
    "reasoning": "Brief explanation of your assessment",
    "usefulness_factors": [list of factors that make it useful or not],
    "improvement_suggestions": [list of suggestions to improve usefulness]
}}
"""
            )
            
            # Format generation for the prompt
            generation_text = json.dumps(generation, indent=2)
            
            # Generate assessment
            usefulness_chain = usefulness_prompt | self.llm | self.json_parser
            assessment = await usefulness_chain.ainvoke({
                "question": question,
                "generation": generation_text
            })
            
            logger.info(f"Generation usefulness assessment: {assessment.get('usefulness_score')}")
            return assessment
            
        except Exception as e:
            logger.error(f"Error in generation usefulness assessment: {e}")
            return {
                "is_useful": False,
                "usefulness_score": QualityScore.NOT_USEFUL.value,
                "reasoning": f"Error in assessment: {str(e)}",
                "usefulness_factors": [],
                "improvement_suggestions": []
            }
    
    async def _self_correct_generation(
        self,
        question: str,
        original_generation: Dict[str, Any],
        assessment_results: Dict[str, Any],
        available_functions: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Self-correct the generation based on assessment results.
        
        Args:
            question: The user's question
            original_generation: The original generation that needs correction
            assessment_results: Results from all assessments
            available_functions: Available functions for correction
            
        Returns:
            Dictionary with corrected generation
        """
        try:
            logger.info("Self-correcting generation based on assessments")
            
            correction_prompt = PromptTemplate(
                input_variables=[
                    "question", "original_generation", "assessment_results", 
                    "available_functions"
                ],
                template="""
You are a self-correcting AI that improves analysis plans based on quality assessments.

### QUESTION ###
{question}

### ORIGINAL GENERATION ###
{original_generation}

### ASSESSMENT RESULTS ###
{assessment_results}

### AVAILABLE FUNCTIONS ###
{available_functions}

### TASK ###
Based on the assessment results, improve the original generation to address:
1. Any relevance issues with retrieved functions
2. Any support issues with the analysis plan
3. Any usefulness issues with the response

### OUTPUT FORMAT ###
Provide your response as a JSON object:
{{
    "corrected_generation": {{
        "rephrased_question": "Improved question if needed",
        "intent_type": "analysis_type",
        "confidence_score": 0.0-1.0,
        "reasoning": "Improved reasoning",
        "reasoning_plan": [improved reasoning plan steps],
        "suggested_functions": [improved function suggestions]
    }},
    "correction_summary": "Summary of what was corrected",
    "improvements_made": [list of specific improvements],
    "confidence_improvement": 0.0-1.0
}}
"""
            )
            
            # Format inputs for the prompt
            generation_text = json.dumps(original_generation, indent=2)
            assessment_text = json.dumps(assessment_results, indent=2)
            functions_text = json.dumps(available_functions or [], indent=2)
            
            # Generate correction
            correction_chain = correction_prompt | self.llm | self.json_parser
            correction = await correction_chain.ainvoke({
                "question": question,
                "original_generation": generation_text,
                "assessment_results": assessment_text,
                "available_functions": functions_text
            })
            
            logger.info(f"Self-correction completed: {correction.get('correction_summary')}")
            return correction
            
        except Exception as e:
            logger.error(f"Error in self-correction: {e}")
            return {
                "corrected_generation": original_generation,
                "correction_summary": f"Error in correction: {str(e)}",
                "improvements_made": [],
                "confidence_improvement": 0.0
            }
    
    async def _evaluate_step_quality_grpo(
        self,
        step: Dict[str, Any],
        question: str,
        context: Dict[str, Any],
        reference_standards: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Evaluate individual step quality using GRPO (Group Relative Policy Optimization).
        
        Args:
            step: The analysis step to evaluate
            question: The user's question
            context: Additional context for evaluation
            reference_standards: Reference standards for comparison
            
        Returns:
            Dictionary with GRPO evaluation results for the step
        """
        try:
            logger.info(f"Evaluating step quality with GRPO: {step.get('step_title', 'Unknown')}")
            
            # Create GRPO evaluation prompt
            grpo_prompt = PromptTemplate(
                input_variables=["step", "question", "context", "reference_standards"],
                template="""
You are a GRPO (Group Relative Policy Optimization) evaluator assessing the quality of an analysis step.

### STEP TO EVALUATE ###
{step}

### QUESTION CONTEXT ###
{question}

### ADDITIONAL CONTEXT ###
{context}

### REFERENCE STANDARDS ###
{reference_standards}

### GRPO EVALUATION CRITERIA ###
Evaluate this step on the following dimensions using a 0-1 scale:

1. **Relevance (R)**: How relevant is this step to answering the question?
2. **Completeness (C)**: How complete is the step description and requirements?
3. **Feasibility (F)**: How feasible is this step given available data and functions?
4. **Clarity (Cl)**: How clear and actionable is the step description?
5. **Technical Accuracy (TA)**: How technically accurate are the data requirements and approach?
6. **Innovation (I)**: How innovative or sophisticated is the approach?
7. **Efficiency (E)**: How efficient would this step be in practice?

### GRPO SCORING METHODOLOGY ###
- Score each dimension from 0.0 to 1.0
- Calculate weighted average based on importance weights
- Compare against reference standards if available
- Apply group relative scoring (how does this compare to similar steps?)

### OUTPUT FORMAT ###
Provide your response as a JSON object:
{{
    "step_id": "step_identifier",
    "step_title": "step_title",
    "dimension_scores": {{
        "relevance": 0.0-1.0,
        "completeness": 0.0-1.0,
        "feasibility": 0.0-1.0,
        "clarity": 0.0-1.0,
        "technical_accuracy": 0.0-1.0,
        "innovation": 0.0-1.0,
        "efficiency": 0.0-1.0
    }},
    "weighted_scores": {{
        "relevance_weight": 0.25,
        "completeness_weight": 0.20,
        "feasibility_weight": 0.20,
        "clarity_weight": 0.15,
        "technical_accuracy_weight": 0.10,
        "innovation_weight": 0.05,
        "efficiency_weight": 0.05
    }},
    "overall_step_score": 0.0-1.0,
    "group_relative_score": 0.0-1.0,
    "strengths": ["list of step strengths"],
    "weaknesses": ["list of step weaknesses"],
    "improvement_suggestions": ["list of specific improvements"],
    "reference_comparison": {{
        "better_than_reference": true/false,
        "reference_score": 0.0-1.0,
        "improvement_margin": 0.0-1.0
    }},
    "evaluation_confidence": 0.0-1.0,
    "evaluation_notes": "Additional evaluation insights"
}}
"""
            )
            
            # Format inputs for the prompt
            step_text = json.dumps(step, indent=2)
            context_text = json.dumps(context, indent=2)
            reference_text = json.dumps(reference_standards or {}, indent=2)
            
            # Generate GRPO evaluation
            grpo_chain = grpo_prompt | self.llm | self.json_parser
            grpo_result = await grpo_chain.ainvoke({
                "step": step_text,
                "question": question,
                "context": context_text,
                "reference_standards": reference_text
            })
            
            # Calculate additional GRPO metrics
            dimension_scores = grpo_result.get("dimension_scores", {})
            weighted_scores = grpo_result.get("weighted_scores", {})
            
            # Calculate weighted average
            weighted_sum = sum(
                dimension_scores.get(dim, 0.0) * weighted_scores.get(f"{dim}_weight", 0.0)
                for dim in ["relevance", "completeness", "feasibility", "clarity", 
                           "technical_accuracy", "innovation", "efficiency"]
            )
            
            grpo_result["calculated_weighted_score"] = weighted_sum
            grpo_result["grpo_rank"] = self._calculate_grpo_rank(weighted_sum)
            
            logger.info(f"GRPO step evaluation completed - Score: {weighted_sum:.3f}, Rank: {grpo_result['grpo_rank']}")
            return grpo_result
            
        except Exception as e:
            logger.error(f"Error in GRPO step evaluation: {e}")
            return {
                "step_id": step.get("step_number", "unknown"),
                "step_title": step.get("step_title", "Unknown"),
                "dimension_scores": {},
                "overall_step_score": 0.0,
                "group_relative_score": 0.0,
                "strengths": [],
                "weaknesses": [f"Evaluation error: {str(e)}"],
                "improvement_suggestions": [],
                "evaluation_confidence": 0.0,
                "evaluation_notes": f"Error in GRPO evaluation: {str(e)}"
            }
    
    def _calculate_grpo_rank(self, score: float) -> str:
        """
        Calculate GRPO rank based on score.
        
        Args:
            score: The calculated score (0.0-1.0)
            
        Returns:
            String rank (A+, A, B+, B, C+, C, D, F)
        """
        if score >= 0.95:
            return "A+"
        elif score >= 0.90:
            return "A"
        elif score >= 0.85:
            return "B+"
        elif score >= 0.80:
            return "B"
        elif score >= 0.75:
            return "C+"
        elif score >= 0.70:
            return "C"
        elif score >= 0.60:
            return "D"
        else:
            return "F"
    
    async def _evaluate_overall_quality_grpo(
        self,
        question: str,
        final_result: Dict[str, Any],
        step_evaluations: List[Dict[str, Any]],
        assessment_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate overall analysis quality using GRPO methodology.
        
        Args:
            question: The user's question
            final_result: The final analysis result
            step_evaluations: Individual step evaluations
            assessment_history: History of all assessments made
            
        Returns:
            Dictionary with overall GRPO evaluation results
        """
        try:
            logger.info("Evaluating overall quality with GRPO")
            
            # Calculate overall metrics from step evaluations
            step_scores = [eval_result.get("overall_step_score", 0.0) for eval_result in step_evaluations]
            group_relative_scores = [eval_result.get("group_relative_score", 0.0) for eval_result in step_evaluations]
            
            overall_step_score = sum(step_scores) / len(step_scores) if step_scores else 0.0
            overall_group_relative_score = sum(group_relative_scores) / len(group_relative_scores) if group_relative_scores else 0.0
            
            # Calculate additional GRPO metrics
            corrections_applied = len([a for a in assessment_history if a.get("correction_applied", False)])
            total_assessments = len(assessment_history)
            
            # Calculate GRPO improvement factor
            improvement_factor = 1.0 + (corrections_applied * 0.1)  # 10% improvement per correction
            
            # Calculate final GRPO score
            final_grpo_score = (overall_step_score * 0.6 + overall_group_relative_score * 0.4) * improvement_factor
            final_grpo_score = min(final_grpo_score, 1.0)  # Cap at 1.0
            
            # Calculate confidence score
            confidence_score = final_result.get("confidence_score", 0.0)
            feasibility_score = final_result.get("feasibility_score", 0.0)
            
            # Calculate completeness score
            reasoning_plan = final_result.get("reasoning_plan", [])
            suggested_functions = final_result.get("suggested_functions", [])
            completeness_score = min(1.0, (len(reasoning_plan) * 0.3 + len(suggested_functions) * 0.1))
            
            # Calculate accuracy score based on self-RAG assessments
            accuracy_score = 1.0 - (corrections_applied * 0.2)  # Reduce accuracy for each correction needed
            accuracy_score = max(0.0, accuracy_score)
            
            # Create comprehensive GRPO evaluation
            grpo_evaluation = {
                "grpo_methodology": "Group Relative Policy Optimization",
                "overall_grpo_score": final_grpo_score,
                "grpo_rank": self._calculate_grpo_rank(final_grpo_score),
                "step_evaluations": step_evaluations,
                "step_metrics": {
                    "total_steps": len(step_evaluations),
                    "average_step_score": overall_step_score,
                    "average_group_relative_score": overall_group_relative_score,
                    "step_score_variance": self._calculate_variance(step_scores),
                    "best_step_score": max(step_scores) if step_scores else 0.0,
                    "worst_step_score": min(step_scores) if step_scores else 0.0
                },
                "quality_dimensions": {
                    "relevance": self._calculate_dimension_average(step_evaluations, "relevance"),
                    "completeness": completeness_score,
                    "feasibility": feasibility_score,
                    "clarity": self._calculate_dimension_average(step_evaluations, "clarity"),
                    "technical_accuracy": self._calculate_dimension_average(step_evaluations, "technical_accuracy"),
                    "innovation": self._calculate_dimension_average(step_evaluations, "innovation"),
                    "efficiency": self._calculate_dimension_average(step_evaluations, "efficiency")
                },
                "self_rag_metrics": {
                    "total_assessments": total_assessments,
                    "corrections_applied": corrections_applied,
                    "correction_rate": corrections_applied / max(total_assessments, 1),
                    "improvement_factor": improvement_factor,
                    "self_reflection_effectiveness": 1.0 - (corrections_applied / max(total_assessments, 1))
                },
                "confidence_metrics": {
                    "confidence_score": confidence_score,
                    "feasibility_score": feasibility_score,
                    "completeness_score": completeness_score,
                    "accuracy_score": accuracy_score,
                    "overall_confidence": (confidence_score + feasibility_score + completeness_score + accuracy_score) / 4
                },
                "grpo_insights": {
                    "strengths": self._extract_common_strengths(step_evaluations),
                    "weaknesses": self._extract_common_weaknesses(step_evaluations),
                    "improvement_priorities": self._identify_improvement_priorities(step_evaluations),
                    "recommendations": self._generate_grpo_recommendations(final_grpo_score, step_evaluations)
                },
                "evaluation_metadata": {
                    "evaluation_timestamp": "2024-01-01T00:00:00Z",  # Placeholder
                    "grpo_version": "1.0",
                    "evaluation_confidence": self._calculate_evaluation_confidence(step_evaluations),
                    "reference_available": False  # Can be enhanced with reference data
                }
            }
            
            logger.info(f"GRPO overall evaluation completed - Score: {final_grpo_score:.3f}, Rank: {grpo_evaluation['grpo_rank']}")
            return grpo_evaluation
            
        except Exception as e:
            logger.error(f"Error in GRPO overall evaluation: {e}")
            return {
                "grpo_methodology": "Group Relative Policy Optimization",
                "overall_grpo_score": 0.0,
                "grpo_rank": "F",
                "error": str(e),
                "evaluation_metadata": {
                    "evaluation_timestamp": "2024-01-01T00:00:00Z",
                    "grpo_version": "1.0",
                    "evaluation_confidence": 0.0
                }
            }
    
    def _calculate_variance(self, scores: List[float]) -> float:
        """Calculate variance of scores."""
        if len(scores) < 2:
            return 0.0
        mean = sum(scores) / len(scores)
        return sum((x - mean) ** 2 for x in scores) / len(scores)
    
    def _calculate_dimension_average(self, step_evaluations: List[Dict[str, Any]], dimension: str) -> float:
        """Calculate average score for a specific dimension across all steps."""
        scores = []
        for eval_result in step_evaluations:
            dimension_scores = eval_result.get("dimension_scores", {})
            if dimension in dimension_scores:
                scores.append(dimension_scores[dimension])
        return sum(scores) / len(scores) if scores else 0.0
    
    def _extract_common_strengths(self, step_evaluations: List[Dict[str, Any]]) -> List[str]:
        """Extract common strengths across all step evaluations."""
        all_strengths = []
        for eval_result in step_evaluations:
            all_strengths.extend(eval_result.get("strengths", []))
        
        # Count frequency and return most common
        from collections import Counter
        strength_counts = Counter(all_strengths)
        return [strength for strength, count in strength_counts.most_common(5)]
    
    def _extract_common_weaknesses(self, step_evaluations: List[Dict[str, Any]]) -> List[str]:
        """Extract common weaknesses across all step evaluations."""
        all_weaknesses = []
        for eval_result in step_evaluations:
            all_weaknesses.extend(eval_result.get("weaknesses", []))
        
        # Count frequency and return most common
        from collections import Counter
        weakness_counts = Counter(all_weaknesses)
        return [weakness for weakness, count in weakness_counts.most_common(5)]
    
    def _identify_improvement_priorities(self, step_evaluations: List[Dict[str, Any]]) -> List[str]:
        """Identify improvement priorities based on step evaluations."""
        priorities = []
        
        # Find steps with lowest scores
        low_score_steps = [eval_result for eval_result in step_evaluations 
                          if eval_result.get("overall_step_score", 0.0) < 0.7]
        
        if low_score_steps:
            priorities.append("Focus on improving low-scoring steps")
        
        # Find common weaknesses
        common_weaknesses = self._extract_common_weaknesses(step_evaluations)
        if common_weaknesses:
            priorities.extend(common_weaknesses[:3])
        
        return priorities
    
    def _generate_grpo_recommendations(self, grpo_score: float, step_evaluations: List[Dict[str, Any]]) -> List[str]:
        """Generate GRPO-based recommendations for improvement."""
        recommendations = []
        
        if grpo_score < 0.7:
            recommendations.append("Overall analysis quality needs significant improvement")
        elif grpo_score < 0.8:
            recommendations.append("Analysis quality is acceptable but can be improved")
        else:
            recommendations.append("Analysis quality is good, maintain current standards")
        
        # Add step-specific recommendations
        for eval_result in step_evaluations:
            if eval_result.get("overall_step_score", 0.0) < 0.7:
                step_title = eval_result.get("step_title", "Unknown step")
                recommendations.append(f"Improve {step_title} - consider better data requirements or approach")
        
        return recommendations
    
    def _calculate_evaluation_confidence(self, step_evaluations: List[Dict[str, Any]]) -> float:
        """Calculate confidence in the evaluation results."""
        if not step_evaluations:
            return 0.0
        
        confidence_scores = [eval_result.get("evaluation_confidence", 0.5) for eval_result in step_evaluations]
        return sum(confidence_scores) / len(confidence_scores)
    
    async def _evaluate_analysis_quality(
        self,
        question: str,
        final_result: Dict[str, Any],
        assessment_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate the overall quality of the analysis using GRPO methodology.
        
        Args:
            question: The user's question
            final_result: The final analysis result
            assessment_history: History of all assessments made
            
        Returns:
            Dictionary with GRPO evaluation results
        """
        try:
            logger.info("Evaluating analysis quality with GRPO methodology")
            
            # Get reasoning plan for step-by-step evaluation
            reasoning_plan = final_result.get("reasoning_plan", [])
            step_evaluations = []
            
            # Evaluate each step individually
            for step in reasoning_plan:
                step_evaluation = await self._evaluate_step_quality_grpo(
                    step=step,
                    question=question,
                    context={
                        "dataframe_description": final_result.get("dataframe_description", ""),
                        "available_columns": final_result.get("required_data_columns", []),
                        "intent_type": final_result.get("intent_type", ""),
                        "confidence_score": final_result.get("confidence_score", 0.0)
                    }
                )
                step_evaluations.append(step_evaluation)
            
            # Evaluate overall quality using GRPO
            grpo_evaluation = await self._evaluate_overall_quality_grpo(
                question=question,
                final_result=final_result,
                step_evaluations=step_evaluations,
                assessment_history=assessment_history
            )
            
            logger.info(f"GRPO analysis quality evaluation completed - Score: {grpo_evaluation.get('overall_grpo_score', 0.0):.3f}")
            return grpo_evaluation
            
        except Exception as e:
            logger.error(f"Error in GRPO analysis quality evaluation: {e}")
            return {
                "grpo_methodology": "Group Relative Policy Optimization",
                "overall_grpo_score": 0.0,
                "grpo_rank": "F",
                "error": str(e),
                "evaluation_metadata": {
                    "evaluation_timestamp": "2024-01-01T00:00:00Z",
                    "grpo_version": "1.0",
                    "evaluation_confidence": 0.0
                }
            }
    
    async def _step1_question_analysis_with_self_rag(
        self,
        question: str,
        dataframe_description: str = "",
        dataframe_summary: str = "",
        available_columns: List[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        STEP 1: Question analysis with self-RAG reflection and correction.
        """
        try:
            logger.info("Step 1: Question analysis with self-RAG")
            
            # Original question analysis (simplified version)
            step1_prompt = PromptTemplate(
                input_variables=["question", "dataframe_description", "dataframe_summary", "available_columns"],
                template="""
You are an expert data analyst performing STEP 1 of a multi-step analysis process.

### TASK ###
Analyze the user's question and create a high-level reasoning plan for data analysis.

### USER QUESTION ###
{question}

### DATAFRAME CONTEXT ###
**Description:** {dataframe_description}
**Summary:** {dataframe_summary}
**Available Columns:** {available_columns}

### STEP 1 REQUIREMENTS ###
1. **Rephrase the question** to be more specific and actionable
2. **Classify the intent** into one of these categories:
   - time_series_analysis: Analyze data patterns over time periods
   - trend_analysis: Analyze trends, growth patterns, forecasting
   - segmentation_analysis: Group users/data into meaningful segments
   - cohort_analysis: Analyze user behavior and retention over time
   - funnel_analysis: Analyze user conversion funnels and drop-off points
   - risk_analysis: Analyze financial risk metrics and volatility
   - anomaly_detection: Identify outliers and unusual patterns
   - metrics_calculation: Calculate basic statistics and aggregations
   - operations_analysis: Perform statistical tests and operations
3. **Generate a reasoning plan** with 2-5 high-level steps that break down the analysis
4. **Identify required data columns** needed for the analysis
5. **Assess feasibility** and provide confidence score

### OUTPUT FORMAT ###
Provide your response as a JSON object:
{{
    "rephrased_question": "Rephrased version of the user's question",
    "intent_type": "one of the analysis types above",
    "confidence_score": 0.0-1.0,
    "reasoning": "Brief explanation of your analysis approach",
    "required_data_columns": ["column1", "column2", "column3"],
    "clarification_needed": "Any questions or clarifications needed",
    "can_be_answered": true/false,
    "feasibility_score": 0.0-1.0,
    "missing_columns": ["column1", "column2"] if any columns are missing,
    "available_alternatives": ["alternative1", "alternative2"] if any,
    "data_suggestions": "Suggestions for data preparation or collection",
    "reasoning_plan": [
        {{
            "step_number": 1,
            "step_title": "Data Preparation",
            "step_description": "Clean and prepare the dataset for analysis",
            "data_requirements": ["date_column", "value_column"]
        }}
    ]
}}
"""
            )
            
            # Generate initial analysis
            step1_chain = step1_prompt | self.llm | self.json_parser
            initial_result = await step1_chain.ainvoke({
                "question": question,
                "dataframe_description": dataframe_description,
                "dataframe_summary": dataframe_summary,
                "available_columns": available_columns or []
            })
            
            # Self-RAG: Assess usefulness of the generation
            usefulness_assessment = await self._assess_generation_usefulness(
                question=question,
                generation=initial_result
            )
            
            # If not useful, attempt self-correction
            if usefulness_assessment.get("usefulness_score") == QualityScore.NOT_USEFUL.value:
                logger.info("Initial generation not useful, attempting self-correction")
                
                correction_result = await self._self_correct_generation(
                    question=question,
                    original_generation=initial_result,
                    assessment_results={"usefulness": usefulness_assessment},
                    available_functions=[]
                )
                
                if correction_result.get("confidence_improvement", 0) > 0:
                    initial_result = correction_result.get("corrected_generation", initial_result)
                    logger.info("Self-correction applied successfully")
            
            # Add self-RAG metadata
            initial_result["self_rag_metadata"] = {
                "usefulness_assessment": usefulness_assessment,
                "correction_applied": usefulness_assessment.get("usefulness_score") == QualityScore.NOT_USEFUL.value,
                "confidence_improvement": correction_result.get("confidence_improvement", 0) if 'correction_result' in locals() else 0
            }
            
            logger.info(f"Step 1 completed with self-RAG - Intent: {initial_result.get('intent_type')}, Confidence: {initial_result.get('confidence_score')}")
            return initial_result
            
        except Exception as e:
            logger.error(f"Error in Step 1 question analysis with self-RAG: {e}")
            return {
                "rephrased_question": question,
                "intent_type": "unsupported_analysis",
                "confidence_score": 0.0,
                "reasoning": f"Error in question analysis: {str(e)}",
                "required_data_columns": [],
                "clarification_needed": "System error occurred",
                "can_be_answered": False,
                "feasibility_score": 0.0,
                "missing_columns": [],
                "available_alternatives": [],
                "data_suggestions": "System error occurred",
                "reasoning_plan": [],
                "self_rag_metadata": {
                    "usefulness_assessment": {"usefulness_score": "error"},
                    "correction_applied": False,
                    "confidence_improvement": 0.0
                }
            }
    
    async def _step2_function_lookup_with_self_rag(
        self,
        reasoning_plan: List[Dict[str, Any]],
        question: str,
        available_columns: List[str],
        dataframe_description: str = "",
        dataframe_summary: str = ""
    ) -> Dict[str, Any]:
        """
        STEP 2: Function lookup with self-RAG reflection on retrieval quality.
        """
        try:
            logger.info("Step 2: Function lookup with self-RAG")
            
            if not self.retrieval_helper:
                logger.warning("No retrieval helper available, using fallback function selection")
                return self._get_fallback_function_selection(reasoning_plan)
            
            step_function_matches = {}
            assessment_history = []
            
            for step in reasoning_plan:
                step_number = step.get('step_number', 1)
                step_title = step.get('step_title', '')
                step_description = step.get('step_description', '')
                
                logger.info(f"Looking up functions for Step {step_number}: {step_title}")
                
                # Create a focused query for this specific step
                step_query = f"{step_title} {step_description} {question}"
                
                try:
                    # Get function definitions for this step
                    function_result = await self.retrieval_helper.get_function_definition_by_query(
                        query=step_query,
                        similarity_threshold=0.3,
                        top_k=5
                    )
                    
                    retrieved_functions = function_result.get("function_definitions", []) if function_result else []
                    
                    # Self-RAG: Assess relevance of retrieved functions
                    relevance_assessment = await self._assess_retrieval_relevance(
                        question=question,
                        retrieved_functions=retrieved_functions,
                        step_context=f"Step {step_number}: {step_title} - {step_description}"
                    )
                    
                    # Filter functions based on relevance assessment
                    if relevance_assessment.get("is_relevant", False):
                        filtered_functions = relevance_assessment.get("filtered_functions", retrieved_functions)
                        step_function_matches[step_number] = filtered_functions
                        logger.info(f"Found {len(filtered_functions)} relevant functions for Step {step_number}")
                    else:
                        step_function_matches[step_number] = []
                        logger.warning(f"No relevant functions found for Step {step_number}")
                    
                    # Record assessment
                    assessment_history.append({
                        "step_number": step_number,
                        "assessment_type": "retrieval_relevance",
                        "assessment_result": relevance_assessment,
                        "correction_applied": not relevance_assessment.get("is_relevant", False)
                    })
                    
                except Exception as e:
                    logger.error(f"Error looking up functions for Step {step_number}: {e}")
                    step_function_matches[step_number] = []
                    assessment_history.append({
                        "step_number": step_number,
                        "assessment_type": "retrieval_relevance",
                        "assessment_result": {"error": str(e)},
                        "correction_applied": False
                    })
            
            return {
                "step_function_matches": step_function_matches,
                "total_steps": len(reasoning_plan),
                "steps_with_functions": len([s for s in step_function_matches.values() if s]),
                "assessment_history": assessment_history,
                "self_rag_metadata": {
                    "retrieval_assessments": assessment_history,
                    "total_assessments": len(assessment_history),
                    "corrections_applied": len([a for a in assessment_history if a.get("correction_applied", False)])
                }
            }
            
        except Exception as e:
            logger.error(f"Error in Step 2 function lookup with self-RAG: {e}")
            return {
                "step_function_matches": {},
                "total_steps": len(reasoning_plan),
                "steps_with_functions": 0,
                "assessment_history": [],
                "self_rag_metadata": {
                    "retrieval_assessments": [],
                    "total_assessments": 0,
                    "corrections_applied": 0
                },
                "error": str(e)
            }
    
    def _get_fallback_function_selection(self, reasoning_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get fallback function selection when retrieval helper is not available.
        """
        step_function_matches = {}
        
        for step in reasoning_plan:
            step_number = step.get('step_number', 1)
            step_title = step.get('step_title', '').lower()
            
            # Simple keyword-based function selection
            functions = []
            
            if any(keyword in step_title for keyword in ['group', 'aggregate', 'sum', 'mean']):
                functions = [
                    {"function_name": "GroupBy", "pipe_name": "MetricsPipe", "description": "Group and aggregate data"},
                    {"function_name": "Sum", "pipe_name": "MetricsPipe", "description": "Calculate sum"},
                    {"function_name": "Mean", "pipe_name": "MetricsPipe", "description": "Calculate mean"}
                ]
            elif any(keyword in step_title for keyword in ['rolling', 'moving', 'window', 'variance']):
                functions = [
                    {"function_name": "moving_variance", "pipe_name": "MovingAggrPipe", "description": "Calculate moving variance"},
                    {"function_name": "rolling_window", "pipe_name": "TimeSeriesPipe", "description": "Apply rolling window operations"}
                ]
            elif any(keyword in step_title for keyword in ['time', 'date', 'trend', 'forecast']):
                functions = [
                    {"function_name": "variance_analysis", "pipe_name": "TimeSeriesPipe", "description": "Analyze variance over time"},
                    {"function_name": "calculate_statistical_trend", "pipe_name": "TrendPipe", "description": "Calculate statistical trends"}
                ]
            
            step_function_matches[step_number] = functions
        
        return {
            "step_function_matches": step_function_matches,
            "total_steps": len(reasoning_plan),
            "steps_with_functions": len([s for s in step_function_matches.values() if s]),
            "assessment_history": [],
            "self_rag_metadata": {
                "retrieval_assessments": [],
                "total_assessments": 0,
                "corrections_applied": 0
            }
        }
    
    async def classify_intent_with_self_rag(
        self,
        question: str,
        dataframe_description: str = "",
        dataframe_summary: str = "",
        available_columns: List[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main method that orchestrates the self-RAG enhanced analysis process.
        """
        try:
            logger.info("Starting self-RAG enhanced analysis process")
            
            # Step 1: Question analysis with self-RAG
            step1_result = await self._step1_question_analysis_with_self_rag(
                question=question,
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary,
                available_columns=available_columns or [],
                project_id=project_id
            )
            
            if not step1_result.get("can_be_answered", False):
                logger.warning("Step 1 determined question cannot be answered")
                return step1_result
            
            reasoning_plan = step1_result.get("reasoning_plan", [])
            if not reasoning_plan:
                logger.warning("No reasoning plan generated in Step 1")
                return step1_result
            
            # Step 2: Function lookup with self-RAG
            step2_result = await self._step2_function_lookup_with_self_rag(
                reasoning_plan=reasoning_plan,
                question=question,
                available_columns=available_columns or [],
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary
            )
            
            step_function_matches = step2_result.get("step_function_matches", {})
            assessment_history = step2_result.get("assessment_history", [])
            
            # Extract suggested functions from step function matches
            suggested_functions = []
            for step_functions in step_function_matches.values():
                for func in step_functions:
                    if func.get('function_name'):
                        pipe_name = func.get('pipe_name', 'Unknown')
                        function_name = func['function_name']
                        suggested_functions.append(f"{function_name}: {func.get('description', 'unknown_operation')} ({pipe_name})")
            
            # Combine all results
            final_result = {
                **step1_result,  # Include Step 1 results
                "step2_result": step2_result,  # Include Step 2 results
                "suggested_functions": suggested_functions,
                "total_steps": len(reasoning_plan),
                "steps_with_functions": step2_result.get("steps_with_functions", 0),
                "self_rag_metadata": {
                    "step1_metadata": step1_result.get("self_rag_metadata", {}),
                    "step2_metadata": step2_result.get("self_rag_metadata", {}),
                    "total_assessments": len(assessment_history),
                    "corrections_applied": len([a for a in assessment_history if a.get("correction_applied", False)])
                }
            }
            
            # Evaluation (pass-through for now)
            evaluation_result = await self._evaluate_analysis_quality(
                question=question,
                final_result=final_result,
                assessment_history=assessment_history
            )
            
            final_result["evaluation"] = evaluation_result
            
            logger.info(f"Self-RAG enhanced analysis completed - {len(reasoning_plan)} reasoning steps, {step2_result.get('steps_with_functions', 0)} with functions, {len(assessment_history)} assessments")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in self-RAG enhanced analysis process: {e}")
            return {
                "rephrased_question": question,
                "intent_type": "unsupported_analysis",
                "confidence_score": 0.0,
                "reasoning": f"Error in analysis process: {str(e)}",
                "required_data_columns": [],
                "clarification_needed": "System error occurred",
                "can_be_answered": False,
                "feasibility_score": 0.0,
                "missing_columns": [],
                "available_alternatives": [],
                "data_suggestions": "System error occurred",
                "reasoning_plan": [],
                "suggested_functions": [],
                "self_rag_metadata": {
                    "step1_metadata": {"error": str(e)},
                    "step2_metadata": {"error": str(e)},
                    "total_assessments": 0,
                    "corrections_applied": 0
                },
                "evaluation": {
                    "overall_quality": "error",
                    "confidence_score": 0.0,
                    "evaluation_notes": f"Error in analysis: {str(e)}"
                },
                "error": str(e)
            }
