"""
Self-RAG Alert Agent Integration Examples and Configuration
This file shows how to integrate the Self-RAG agent with your existing architecture
and provides various pipe operation examples.
"""

from langchain_core.runnables import (
    RunnablePassthrough, RunnableLambda, RunnableParallel, 
    RunnableBranch, RunnableRouter
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from typing import Dict, List, Any, Optional
import asyncio
from enum import Enum

# Configuration for different pipe operation patterns
class PipelineMode(Enum):
    SEQUENTIAL = "sequential"  # Standard Self-RAG pipeline
    PARALLEL = "parallel"     # Parallel processing of multiple aspects
    CONDITIONAL = "conditional"  # Branching based on conditions
    ENSEMBLE = "ensemble"     # Multiple model approaches

class AdvancedSelfRAGPipelines:
    """Advanced pipeline configurations using LangChain pipe operations"""
    
    def __init__(self, agent):
        self.agent = agent
        self.generator_llm = agent.generator_llm
        self.critic_llm = agent.critic_llm
        self.refiner_llm = agent.refiner_llm
    
    def create_sequential_pipeline(self):
        """Standard sequential Self-RAG pipeline (from main agent)"""
        return (
            RunnablePassthrough.assign(context=RunnableLambda(self.agent._retrieve_context))
            | RunnablePassthrough.assign(generated_alert=RunnableLambda(self.agent._generate_alert))
            | RunnablePassthrough.assign(critique=RunnableLambda(self.agent._critique_alert))
            | RunnableLambda(self.agent._refine_alert)
        )
    
    def create_parallel_pipeline(self):
        """Parallel pipeline that processes multiple aspects simultaneously"""
        
        # Define parallel branches
        parallel_branches = RunnableParallel({
            "context": RunnableLambda(self.agent._retrieve_context),
            "user_intent": RunnableLambda(self._extract_user_intent),
            "domain_validation": RunnableLambda(self._validate_domain_context)
        })
        
        # Combine results and generate
        combine_and_generate = (
            RunnableLambda(self._combine_parallel_results)
            | RunnableLambda(self.agent._generate_alert)
        )
        
        # Final pipeline
        return (
            parallel_branches
            | combine_and_generate
            | RunnablePassthrough.assign(critique=RunnableLambda(self.agent._critique_alert))
            | RunnableLambda(self.agent._refine_alert)
        )
    
    def create_conditional_pipeline(self):
        """Conditional pipeline that branches based on input complexity"""
        
        # Define condition checker
        def route_by_complexity(inputs: Dict) -> str:
            request = inputs["request"]
            word_count = len(request.natural_language_input.split())
            
            if word_count < 10:
                return "simple"
            elif word_count < 30:
                return "standard"
            else:
                return "complex"
        
        # Define different branches
        simple_branch = (
            RunnableLambda(self._simple_generation)
            | RunnableLambda(self._basic_validation)
        )
        
        standard_branch = (
            RunnablePassthrough.assign(context=RunnableLambda(self.agent._retrieve_context))
            | RunnableLambda(self.agent._generate_alert)
            | RunnableLambda(self.agent._refine_alert)
        )
        
        complex_branch = (
            RunnablePassthrough.assign(context=RunnableLambda(self.agent._retrieve_context))
            | RunnablePassthrough.assign(generated_alert=RunnableLambda(self.agent._generate_alert))
            | RunnablePassthrough.assign(critique=RunnableLambda(self.agent._critique_alert))
            | RunnableLambda(self._deep_refinement)
        )
        
        # Create conditional pipeline
        return RunnableBranch(
            (lambda x: route_by_complexity(x) == "simple", simple_branch),
            (lambda x: route_by_complexity(x) == "standard", standard_branch),
            complex_branch  # Default case
        )
    
    def create_ensemble_pipeline(self):
        """Ensemble pipeline that uses multiple models/approaches"""
        
        # Generate multiple alert candidates
        ensemble_generation = RunnableParallel({
            "conservative": RunnableLambda(self._conservative_generation),
            "aggressive": RunnableLambda(self._aggressive_generation),
            "balanced": RunnableLambda(self.agent._generate_alert)
        })
        
        # Evaluate and select best candidate
        selection_pipeline = (
            RunnableLambda(self._evaluate_candidates)
            | RunnableLambda(self._select_best_candidate)
        )
        
        return (
            RunnablePassthrough.assign(context=RunnableLambda(self.agent._retrieve_context))
            | ensemble_generation
            | selection_pipeline
            | RunnablePassthrough.assign(critique=RunnableLambda(self.agent._critique_alert))
            | RunnableLambda(self.agent._refine_alert)
        )
    
    # Helper methods for advanced pipelines
    async def _extract_user_intent(self, inputs: Dict) -> Dict[str, Any]:
        """Extract user intent in parallel with context retrieval"""
        request = inputs["request"]
        
        intent_prompt = ChatPromptTemplate.from_template("""
        Analyze the user's intent from this alert request:
        "{input}"
        
        Return JSON with:
        - urgency: low/medium/high
        - metric_category: sales/marketing/operations/finance
        - alert_type: threshold/anomaly/pattern
        - business_impact: low/medium/high
        """)
        
        chain = intent_prompt | self.generator_llm | JsonOutputParser()
        result = await chain.ainvoke({"input": request.natural_language_input})
        return result
    
    async def _validate_domain_context(self, inputs: Dict) -> Dict[str, Any]:
        """Validate domain context in parallel"""
        request = inputs["request"]
        
        # Mock domain validation
        return {
            "domain_valid": True,
            "confidence": 0.9,
            "suggested_improvements": []
        }
    
    def _combine_parallel_results(self, inputs: Dict) -> Dict:
        """Combine results from parallel branches"""
        return {
            "request": inputs["request"] if "request" in inputs else inputs,
            "context": inputs["context"],
            "user_intent": inputs["user_intent"],
            "domain_validation": inputs["domain_validation"]
        }
    
    async def _simple_generation(self, inputs: Dict):
        """Simplified generation for simple requests"""
        # Basic alert generation logic
        request = inputs["request"]
        
        # Mock simple generation
        from self_rag_alert_agent import GeneratedAlert
        return GeneratedAlert(
            alert_name="Simple Alert",
            description="Basic alert configuration",
            metric="default_metric",
            condition_type="greaterthan",
            threshold_value="0",
            schedule="daily",
            notification_channel="email"
        )
    
    async def _basic_validation(self, alert):
        """Basic validation for simple alerts"""
        from self_rag_alert_agent import RefinedAlert, CritiqueResult
        
        critique = CritiqueResult(
            is_valid=True,
            confidence_score=0.8,
            issues=[],
            suggestions=[],
            completeness_score=0.8
        )
        
        sql_structure = self.agent._convert_to_sql_structure(alert)
        
        return RefinedAlert(
            alert=alert,
            critique=critique,
            sql_structure=sql_structure
        )
    
    async def _deep_refinement(self, inputs: Dict):
        """Deep refinement process for complex requests"""
        # Multiple rounds of refinement
        current_alert = inputs["generated_alert"]
        critique = inputs["critique"]
        
        # Implement multiple refinement rounds
        for i in range(3):  # Up to 3 refinement rounds
            if critique.confidence_score > 0.9:
                break
                
            refined_result = await self.agent._refine_alert(inputs)
            current_alert = refined_result.alert
            
            # Re-critique
            critique = await self.agent._critique_alert({
                **inputs,
                "generated_alert": current_alert
            })
        
        return refined_result
    
    async def _conservative_generation(self, inputs: Dict):
        """Conservative alert generation"""
        # Use lower temperature and more restrictive prompts
        conservative_llm = self.generator_llm.bind(temperature=0.0)
        
        prompt = ChatPromptTemplate.from_template("""
        Generate a conservative, safe alert configuration for: {input}
        Focus on proven metrics and standard thresholds.
        """)
        
        chain = prompt | conservative_llm | JsonOutputParser()
        result = await chain.ainvoke({"input": inputs["request"].natural_language_input})
        
        from self_rag_alert_agent import GeneratedAlert
        return GeneratedAlert(**result)
    
    async def _aggressive_generation(self, inputs: Dict):
        """Aggressive alert generation"""
        # Use higher temperature for more creative solutions
        aggressive_llm = self.generator_llm.bind(temperature=0.7)
        
        prompt = ChatPromptTemplate.from_template("""
        Generate an innovative, proactive alert configuration for: {input}
        Consider advanced metrics and intelligent thresholds.
        """)
        
        chain = prompt | aggressive_llm | JsonOutputParser()
        result = await chain.ainvoke({"input": inputs["request"].natural_language_input})
        
        from self_rag_alert_agent import GeneratedAlert
        return GeneratedAlert(**result)
    
    async def _evaluate_candidates(self, inputs: Dict):
        """Evaluate ensemble candidates"""
        candidates = {
            "conservative": inputs["conservative"],
            "aggressive": inputs["aggressive"], 
            "balanced": inputs["balanced"]
        }
        
        # Evaluate each candidate
        evaluations = {}
        for name, candidate in candidates.items():
            # Mock evaluation logic
            evaluations[name] = {
                "candidate": candidate,
                "score": 0.8,  # Would implement actual scoring
                "pros": ["reliable", "tested"],
                "cons": ["conservative"]
            }
        
        return {
            "candidates": candidates,
            "evaluations": evaluations,
            "context": inputs["context"]
        }
    
    def _select_best_candidate(self, inputs: Dict):
        """Select the best candidate from ensemble"""
        evaluations = inputs["evaluations"]
        
        # Select candidate with highest score
        best_candidate = max(evaluations.items(), key=lambda x: x[1]["score"])
        
        return {
            "request": inputs.get("request"),
            "context": inputs["context"],
            "generated_alert": best_candidate[1]["candidate"],
            "selection_reason": f"Selected {best_candidate[0]} with score {best_candidate[1]['score']}"
        }

# Integration with existing SQLModel structure
class SQLModelIntegration:
    """Integration utilities for SQLModel database operations"""
    
    @staticmethod
    def create_database_records(refined_alert, user_id: int = None):
        """Create database records from refined alert"""
        
        from self_rag_alert_agent import AlertCreationSettings, EventOrder, Condition
        
        sql_structure = refined_alert.sql_structure
        
        # Create AlertCreationSettings record
        settings = AlertCreationSettings(
            name=sql_structure["alert_creation_settings"]["name"],
            description=sql_structure["alert_creation_settings"]["description"],
            is_active=sql_structure["alert_creation_settings"]["is_active"]
        )
        
        # Create EventOrder record
        event_order = EventOrder(
            order_label=sql_structure["event_order"]["order_label"],
            schedule=sql_structure["event_order"]["schedule"],
            notification_channel=sql_structure["event_order"]["notification_channel"]
        )
        
        # Create Condition records
        conditions = []
        for cond_data in sql_structure["conditions"]:
            condition = Condition(
                field_name=cond_data["field_name"],
                field_value=cond_data["field_value"],
                condition_type=cond_data["condition_type"]
            )
            conditions.append(condition)
        
        return {
            "settings": settings,
            "event_order": event_order,
            "conditions": conditions
        }
    
    @staticmethod
    def convert_to_legacy_format(refined_alert):
        """Convert to legacy alert format (from original main.py)"""
        
        alert = refined_alert.alert
        
        legacy_conditions = [{
            "conditionType": alert.condition_type,
            "metricselected": alert.metric,
            "schedule": alert.schedule,
            "timecolumn": alert.time_window,
            "value": alert.threshold_value
        }]
        
        # Add filter conditions
        for filter_cond in alert.filter_conditions:
            legacy_conditions.append({
                "conditionType": "equals",
                "metricselected": filter_cond.get("field", ""),
                "schedule": alert.schedule,
                "timecolumn": "default",
                "value": filter_cond.get("value", "")
            })
        
        return {
            "type": "finished",
            "question": f"Monitor {alert.metric}",
            "alertname": alert.alert_name,
            "summary": alert.description,
            "reasoning": f"Generated using Self-RAG with {refined_alert.critique.confidence_score:.2f} confidence",
            "conditions": legacy_conditions,
            "notificationgroup": alert.notification_channel
        }

# Usage examples and testing
async def demo_advanced_pipelines():
    """Demonstrate different pipeline configurations"""
    
    # Mock agent (you would use your actual agent)
    from self_rag_alert_agent import SelfRAGAlertAgent, AlertRequest
    
    agent = SelfRAGAlertAgent()
    advanced_pipelines = AdvancedSelfRAGPipelines(agent)
    
    # Test different pipeline modes
    test_request = AlertRequest(
        natural_language_input="Alert me if sales revenue drops significantly",
        session_id="demo_session"
    )
    
    pipelines = {
        "sequential": advanced_pipelines.create_sequential_pipeline(),
        "parallel": advanced_pipelines.create_parallel_pipeline(),
        "conditional": advanced_pipelines.create_conditional_pipeline(),
        "ensemble": advanced_pipelines.create_ensemble_pipeline()
    }
    
    for name, pipeline in pipelines.items():
        print(f"\n--- Testing {name.upper()} Pipeline ---")
        try:
            result = await pipeline.ainvoke({"request": test_request})
            print(f"✅ {name} pipeline completed successfully")
            print(f"Alert: {result.alert.alert_name}")
            print(f"Confidence: {result.critique.confidence_score}")
        except Exception as e:
            print(f"❌ {name} pipeline failed: {e}")

# Configuration management
class PipelineConfig:
    """Configuration for different pipeline setups"""
    
    PIPELINE_CONFIGS = {
        "development": {
            "mode": PipelineMode.SEQUENTIAL,
            "max_refinements": 1,
            "temperature": 0.1,
            "use_cache": True
        },
        "production": {
            "mode": PipelineMode.PARALLEL,
            "max_refinements": 3,
            "temperature": 0.05,
            "use_cache": True
        },
        "experimental": {
            "mode": PipelineMode.ENSEMBLE,
            "max_refinements": 5,
            "temperature": 0.2,
            "use_cache": False
        }
    }
    
    @classmethod
    def get_config(cls, environment: str = "production"):
        """Get configuration for specific environment"""
        return cls.PIPELINE_CONFIGS.get(environment, cls.PIPELINE_CONFIGS["production"])

# Example FastAPI endpoint that uses advanced pipelines
from fastapi import FastAPI

app = FastAPI()

@app.post("/api/v2/alerts/advanced-generate")
async def advanced_generate_alert(
    request: Dict[str, Any],
    pipeline_mode: str = "sequential"
):
    """Generate alert using advanced pipeline configurations"""
    
    from self_rag_alert_agent import SelfRAGAlertAgent, AlertRequest
    
    agent = SelfRAGAlertAgent()
    advanced_pipelines = AdvancedSelfRAGPipelines(agent)
    
    # Select pipeline based on mode
    pipeline_map = {
        "sequential": advanced_pipelines.create_sequential_pipeline(),
        "parallel": advanced_pipelines.create_parallel_pipeline(),
        "conditional": advanced_pipelines.create_conditional_pipeline(),
        "ensemble": advanced_pipelines.create_ensemble_pipeline()
    }
    
    pipeline = pipeline_map.get(pipeline_mode, advanced_pipelines.create_sequential_pipeline())
    
    alert_request = AlertRequest(
        natural_language_input=request["input"],
        session_id=request.get("session_id")
    )
    
    result = await pipeline.ainvoke({"request": alert_request})
    
    # Convert to both SQLModel and legacy formats
    sql_records = SQLModelIntegration.create_database_records(result)
    legacy_format = SQLModelIntegration.convert_to_legacy_format(result)
    
    return {
        "pipeline_mode": pipeline_mode,
        "result": result.alert.dict(),
        "sql_records": {
            "settings": sql_records["settings"].dict(),
            "event_order": sql_records["event_order"].dict(),
            "conditions": [c.dict() for c in sql_records["conditions"]]
        },
        "legacy_format": legacy_format,
        "confidence": result.critique.confidence_score
    }

if __name__ == "__main__":
    # Run demo
    asyncio.run(demo_advanced_pipelines())