"""
Demo test for Feature Engineering Agent

This test demonstrates the feature engineering pipeline with example queries
for both cybersecurity and HR compliance domains. Outputs are saved to tests/output.
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.agents.nodes.transform.feature_engineering_agent import run_feature_engineering_pipeline
from app.agents.nodes.transform.domain_config import get_domain_config, CYBERSECURITY_DOMAIN_CONFIG, HR_COMPLIANCE_DOMAIN_CONFIG
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm

# Import transform demo function (handle both relative and absolute imports)
try:
    from demo_transform_sql_rag_agent import run_transform_demo_from_features
except ImportError:
    try:
        from .demo_transform_sql_rag_agent import run_transform_demo_from_features
    except ImportError:
        # If import fails, transform demo will be skipped
        run_transform_demo_from_features = None

# Configure logging
logging.getLogger("app.storage.documents").setLevel(logging.WARNING)
logging.getLogger("agents.app.storage.documents").setLevel(logging.WARNING)

logger = logging.getLogger("lexy-ai-service")


class FeatureEngineeringAgentDemo:
    """Demo class for testing Feature Engineering Agent"""
    
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FeatureEngineeringAgentDemo, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            try:
                # Initialize dependencies
                self.retrieval_helper = RetrievalHelper()
                self._initialized = True
                logger.info("FeatureEngineeringAgentDemo initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize FeatureEngineeringAgentDemo: {e}")
                self._initialization_failed = True
                self._initialized = True

    async def process_feature_engineering_query(
        self,
        user_query: str,
        project_id: str,
        domain_config_name: str = "cybersecurity",
        histories: Optional[List[str]] = None,
        validation_expectations: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict:
        """
        Process a feature engineering query and return the generated features.
        
        This method matches the router's response format:
        - success: bool
        - recommended_features: List[Dict[str, Any]]
        - analytical_intent: Optional[Dict[str, Any]]
        - relevant_schemas: Optional[List[str]]
        - clarifying_questions: Optional[List[str]]
        - reasoning_plan: Optional[Dict[str, Any]]
        - error: Optional[str]
        
        Args:
            user_query: The user's query/question
            project_id: The project ID
            domain_config_name: Domain name (default: "cybersecurity")
            histories: Optional list of previous queries for context
            validation_expectations: Optional list of validation examples
            **kwargs: Additional arguments
            
        Returns:
            Dict matching FeatureRecommendationResponse format
        """
        try:
            logger.info(f"Processing feature engineering query: {user_query[:100]}...")
            logger.info(f"Project ID: {project_id}, Domain: {domain_config_name}")
            
            # Get domain config
            domain_config = get_domain_config(domain_config_name)
            
            # Process feature engineering request (same as router)
            result = await run_feature_engineering_pipeline(
                user_query=user_query,
                project_id=project_id,
                retrieval_helper=self.retrieval_helper,
                domain_config=domain_config,
                histories=histories,
                validation_expectations=validation_expectations,
                **kwargs
            )
            
            # Extract features count for logging
            recommended_features = result.get("recommended_features", [])
            risk_features = result.get("risk_features", [])
            impact_features = result.get("impact_features", [])
            likelihood_features = result.get("likelihood_features", [])
            
            logger.info(f"Feature engineering result: {len(recommended_features)} standard features")
            logger.info(f"Risk features: {len(risk_features)}")
            logger.info(f"Impact features: {len(impact_features)}")
            logger.info(f"Likelihood features: {len(likelihood_features)}")
            
            # Return in router format (FeatureRecommendationResponse)
            return {
                "success": True,
                "recommended_features": recommended_features,
                "analytical_intent": result.get("analytical_intent"),
                "relevant_schemas": result.get("relevant_schemas", []),
                "clarifying_questions": result.get("clarifying_questions", []),
                "reasoning_plan": result.get("reasoning_plan"),
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error processing feature engineering query: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "recommended_features": [],
                "analytical_intent": None,
                "relevant_schemas": [],
                "clarifying_questions": [],
                "reasoning_plan": None,
                "error": str(e)
            }


def format_feature_output(feature: Dict, index: int) -> str:
    """Format a single feature for markdown output"""
    output = f"### {index}. {feature.get('feature_name', 'Unknown')}\n\n"
    output += f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n\n"
    output += f"**Type:** {feature.get('feature_type', 'Unknown')}\n\n"
    
    if feature.get('calculation_logic'):
        output += f"**Calculation Logic:** {feature.get('calculation_logic')}\n\n"
    
    if feature.get('business_context'):
        output += f"**Business Context:** {feature.get('business_context')}\n\n"
    
    if feature.get('soc2_compliance_reasoning'):
        output += f"**SOC2 Compliance Reasoning:** {feature.get('soc2_compliance_reasoning')}\n\n"
    
    if feature.get('transformation_layer'):
        output += f"**Transformation Layer:** {feature.get('transformation_layer')}\n\n"
    
    if feature.get('time_series_type'):
        output += f"**Time Series Type:** {feature.get('time_series_type')}\n\n"
    
    if feature.get('required_fields'):
        output += f"**Required Fields:** {', '.join(feature.get('required_fields', []))}\n\n"
    
    if feature.get('required_schemas'):
        output += f"**Required Schemas:** {', '.join(feature.get('required_schemas', []))}\n\n"
    
    return output


def save_results_to_file(
    result: Dict,
    output_dir: Path,
    query_name: str,
    domain_name: str,
    user_query: str
) -> Path:
    """Save feature engineering results to markdown and JSON files
    
    Args:
        result: Response dict in router format (FeatureRecommendationResponse)
        output_dir: Directory to save output files
        query_name: Name for the query/test case
        domain_name: Domain name
        user_query: Original user query
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create markdown file
    md_file = output_dir / f"feature_engineering_{domain_name}_{query_name}_{timestamp}.md"
    
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# Feature Engineering Pipeline Output\n\n")
        f.write(f"**Generated at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Domain:** {domain_name}\n")
        f.write(f"**Query:** {user_query}\n")
        f.write(f"**Success:** {result.get('success', False)}\n\n")
        
        if result.get('error'):
            f.write(f"**Error:** {result.get('error')}\n\n")
            return md_file
        
        # Write recommended features (matches router format)
        recommended_features = result.get('recommended_features', [])
        f.write(f"## Recommended Features ({len(recommended_features)} total)\n\n")
        for i, feature in enumerate(recommended_features, 1):
            f.write(format_feature_output(feature, i))
        
        # Write analytical intent
        analytical_intent = result.get('analytical_intent')
        if analytical_intent:
            f.write(f"\n## Analytical Intent\n\n")
            f.write(f"```json\n{json.dumps(analytical_intent, indent=2)}\n```\n\n")
        
        # Write relevant schemas
        relevant_schemas = result.get('relevant_schemas', [])
        if relevant_schemas:
            f.write(f"\n## Relevant Schemas\n\n")
            for schema in relevant_schemas:
                f.write(f"- {schema}\n")
            f.write("\n")
        
        # Write clarifying questions
        clarifying_questions = result.get('clarifying_questions', [])
        if clarifying_questions:
            f.write(f"\n## Clarifying Questions\n\n")
            for i, question in enumerate(clarifying_questions, 1):
                f.write(f"{i}. {question}\n")
            f.write("\n")
        
        # Write reasoning plan
        reasoning_plan = result.get('reasoning_plan')
        if reasoning_plan:
            f.write(f"\n## Reasoning Plan\n\n")
            f.write(f"```json\n{json.dumps(reasoning_plan, indent=2)}\n```\n\n")
    
    # Create JSON file (save in router format)
    json_file = output_dir / f"feature_engineering_{domain_name}_{query_name}_{timestamp}.json"
    save_data = {
        "success": result.get('success', False),
        "recommended_features": result.get('recommended_features', []),
        "analytical_intent": result.get('analytical_intent'),
        "relevant_schemas": result.get('relevant_schemas', []),
        "clarifying_questions": result.get('clarifying_questions', []),
        "reasoning_plan": result.get('reasoning_plan'),
        "error": result.get('error'),
        "metadata": {
            "query": user_query,
            "domain": domain_name,
            "timestamp": datetime.now().isoformat()
        }
    }
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, default=str)
    
    logger.info(f"Results saved to: {md_file}")
    logger.info(f"JSON results saved to: {json_file}")
    
    return json_file  # Return JSON file path for transform demo


async def run_feature_engineering_demo():
    """Run a demo of the Feature Engineering Agent with example queries"""
    
    # Create output directory
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize demo
    demo = FeatureEngineeringAgentDemo()
    
    # Example queries from feature_engineering_agent.py:5030-5043
    test_cases = [
        {
            "name": "cybersecurity_snyk_report",
            "query": """
            Create a report for Snyk that looks at the Critical and High vulnerabilities 
            for SOC2 compliance and provides risk, impact and likelihood metrics. I need to know SLAs, Repos, and Exploitability of the 
            vulnerabilities. Critical = 7 Days, High = 30 days since created and open and their risks.
            Yes use reachability. I want to understand the risk, impact and likelihood metrics for the report as well.
            Generate more than 20 features. 
            """,
            "project_id": "cve_data",
            "domain": "cybersecurity"
        },
        {
            "name": "hr_compliance_training",
            "query": """
            Create a report for HR compliance that tracks training completion rates 
            for GDPR compliance across cornerstone and talent. I need to know completion rates, certification expiry,
            and compliance gaps by department. Critical deadline = 7 days, High = 30 days.
            """,
            "project_id": "csod_risk_attrition",
            "domain": "hr_compliance"
        }
    ]
    
    all_results = []
    successful = 0
    failed = 0
    
    print("=" * 80)
    print("Feature Engineering Agent Demo")
    print("=" * 80)
    print(f"Running {len(test_cases)} test cases...")
    print("=" * 80)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"Test Case {i}/{len(test_cases)}: {test_case['name']}")
        print(f"Domain: {test_case['domain']}")
        print(f"{'='*80}\n")
        
        try:
            result = await demo.process_feature_engineering_query(
                user_query=test_case['query'],
                project_id=test_case['project_id'],
                domain_config_name=test_case['domain']
            )
            
            if result.get('success'):
                successful += 1
                recommended_count = len(result.get('recommended_features', []))
                print(f"✅ Success: Generated {recommended_count} recommended features")
                
                # Save results to file
                json_file = save_results_to_file(
                    result=result,
                    output_dir=output_dir,
                    query_name=test_case['name'],
                    domain_name=test_case['domain'],
                    user_query=test_case['query']
                )
                
                # For cybersecurity domain, automatically run transform demo
                if test_case['domain'] == 'cybersecurity' and json_file and run_transform_demo_from_features:
                    print(f"\n{'='*80}")
                    print("🔄 Automatically running Transform SQL RAG Agent for cybersecurity features...")
                    print(f"{'='*80}\n")
                    try:
                        await run_transform_demo_from_features(str(json_file))
                        print(f"\n✅ Transform demo completed for {test_case['name']}")
                    except Exception as e:
                        logger.error(f"Error running transform demo: {e}")
                        import traceback
                        traceback.print_exc()
                        print(f"\n❌ Transform demo failed for {test_case['name']}: {e}")
                elif test_case['domain'] == 'cybersecurity' and not run_transform_demo_from_features:
                    logger.warning("Transform demo function not available. Skipping transform demo.")
            else:
                failed += 1
                error_msg = result.get('error', 'Unknown error')
                print(f"❌ Failed: {error_msg}")
            
            # Track results (matches router format)
            all_results.append({
                "test_case": test_case['name'],
                "domain": test_case['domain'],
                "success": result.get('success', False),
                "recommended_features_count": len(result.get('recommended_features', [])) if result.get('success') else 0,
                "analytical_intent": result.get('analytical_intent') is not None,
                "relevant_schemas_count": len(result.get('relevant_schemas', [])),
                "clarifying_questions_count": len(result.get('clarifying_questions', [])),
                "reasoning_plan": result.get('reasoning_plan') is not None,
                "error": result.get('error') if not result.get('success') else None
            })
            
        except Exception as e:
            failed += 1
            logger.error(f"Error in test case {test_case['name']}: {e}")
            import traceback
            traceback.print_exc()
            all_results.append({
                "test_case": test_case['name'],
                "domain": test_case['domain'],
                "success": False,
                "recommended_features_count": 0,
                "analytical_intent": False,
                "relevant_schemas_count": 0,
                "clarifying_questions_count": 0,
                "reasoning_plan": False,
                "error": str(e)
            })
    
    # Export summary to JSON file
    summary_file = output_dir / f"feature_engineering_demo_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    summary = {
        "summary": {
            "total_cases": len(test_cases),
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / len(test_cases) * 100) if test_cases else 0,
            "timestamp": datetime.now().isoformat()
        },
        "results": all_results
    }
    
    try:
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\n💾 Summary exported to: {summary_file}")
    except Exception as e:
        logger.error(f"Error exporting summary to file: {e}")
    
    print(f"\n{'='*80}")
    print("END OF RESULTS SUMMARY")
    print(f"{'='*80}")
    print(f"Total Cases: {len(test_cases)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(successful / len(test_cases) * 100) if test_cases else 0:.1f}%")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    # Configure logging level
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the demo
    print("="*80)
    print("Feature Engineering Agent Demo")
    print("="*80)
    print("This demo tests the Feature Engineering Agent with example queries")
    print("for both cybersecurity and HR compliance domains.")
    print("Outputs will be saved to tests/output/")
    print("="*80)
    
    asyncio.run(run_feature_engineering_demo())

