"""
Demo test for Feature Engineering Agent

This test demonstrates the feature engineering pipeline with example queries
for both cybersecurity and HR compliance domains. Outputs are saved to tests/output.
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from app.agents.nodes.transform.feature_engineering_agent import run_feature_engineering_pipeline
from app.agents.nodes.transform.domain_config import get_domain_config, CYBERSECURITY_DOMAIN_CONFIG, HR_COMPLIANCE_DOMAIN_CONFIG
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm

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
        **kwargs
    ) -> Dict:
        """
        Process a feature engineering query and return the generated features.
        
        Args:
            user_query: The user's query/question
            project_id: The project ID
            domain_config_name: Domain name (default: "cybersecurity")
            **kwargs: Additional arguments
            
        Returns:
            Dict containing the feature engineering results
        """
        try:
            logger.info(f"Processing feature engineering query: {user_query[:100]}...")
            logger.info(f"Project ID: {project_id}, Domain: {domain_config_name}")
            
            # Get domain config
            domain_config = get_domain_config(domain_config_name)
            
            # Process feature engineering request
            result = await run_feature_engineering_pipeline(
                user_query=user_query,
                project_id=project_id,
                retrieval_helper=self.retrieval_helper,
                domain_config=domain_config,
                **kwargs
            )
            
            logger.info(f"Feature engineering result: {len(result.get('recommended_features', []))} standard features")
            logger.info(f"Risk features: {len(result.get('risk_features', []))}")
            logger.info(f"Impact features: {len(result.get('impact_features', []))}")
            logger.info(f"Likelihood features: {len(result.get('likelihood_features', []))}")
            
            return {
                "status": "success",
                "result": result,
                "query": user_query,
                "domain": domain_config_name,
                "project_id": project_id
            }
            
        except Exception as e:
            logger.error(f"Error processing feature engineering query: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "error": str(e),
                "query": user_query,
                "domain": domain_config_name,
                "project_id": project_id
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
    domain_name: str
) -> Path:
    """Save feature engineering results to markdown and JSON files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create markdown file
    md_file = output_dir / f"feature_engineering_{domain_name}_{query_name}_{timestamp}.md"
    
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# Feature Engineering Pipeline Output\n\n")
        f.write(f"**Generated at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Domain:** {domain_name}\n")
        f.write(f"**Query:** {result.get('query', 'N/A')}\n\n")
        
        # Write recommended features (standard features)
        all_features = result.get('result', {}).get('recommended_features', [])
        f.write(f"## Recommended Features ({len(all_features)} total)\n\n")
        for i, feature in enumerate(all_features, 1):
            f.write(format_feature_output(feature, i))
        
        # Write impact features
        impact_features = result.get('result', {}).get('impact_features', [])
        if impact_features:
            f.write(f"\n## Impact Features ({len(impact_features)} total)\n\n")
            for i, feature in enumerate(impact_features, 1):
                f.write(format_feature_output(feature, i))
        
        # Write likelihood features
        likelihood_features = result.get('result', {}).get('likelihood_features', [])
        if likelihood_features:
            f.write(f"\n## Likelihood Features ({len(likelihood_features)} total)\n\n")
            for i, feature in enumerate(likelihood_features, 1):
                f.write(format_feature_output(feature, i))
        
        # Write risk features
        risk_features = result.get('result', {}).get('risk_features', [])
        if risk_features:
            f.write(f"\n## Risk Features ({len(risk_features)} total)\n\n")
            for i, feature in enumerate(risk_features, 1):
                f.write(format_feature_output(feature, i))
        
        # Write feature dependencies
        dependencies = result.get('result', {}).get('feature_dependencies', {})
        if dependencies:
            f.write(f"\n## Feature Dependencies\n\n")
            f.write(f"```json\n{json.dumps(dependencies, indent=2)}\n```\n\n")
        
        # Write reasoning plan
        reasoning_plan = result.get('result', {}).get('reasoning_plan', {})
        if reasoning_plan:
            f.write(f"\n## Reasoning Plan\n\n")
            f.write(f"```json\n{json.dumps(reasoning_plan, indent=2)}\n```\n\n")
        
        # Write relevancy scores
        relevance_scores = result.get('result', {}).get('relevance_scores', {})
        if relevance_scores:
            f.write(f"\n## Relevance Scores\n\n")
            f.write(f"```json\n{json.dumps(relevance_scores, indent=2)}\n```\n\n")
    
    # Create JSON file
    json_file = output_dir / f"feature_engineering_{domain_name}_{query_name}_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, default=str)
    
    logger.info(f"Results saved to: {md_file}")
    logger.info(f"JSON results saved to: {json_file}")
    
    return md_file


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
            "project_id": "hr_data",
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
            
            if result.get('status') == 'success':
                successful += 1
                print(f"✅ Success: Generated {len(result.get('result', {}).get('recommended_features', []))} standard features")
                
                # Save results to file
                save_results_to_file(
                    result=result,
                    output_dir=output_dir,
                    query_name=test_case['name'],
                    domain_name=test_case['domain']
                )
            else:
                failed += 1
                print(f"❌ Failed: {result.get('error', 'Unknown error')}")
            
            all_results.append({
                "test_case": test_case['name'],
                "domain": test_case['domain'],
                "status": result.get('status'),
                "standard_features_count": len(result.get('result', {}).get('recommended_features', [])) if result.get('status') == 'success' else 0,
                "risk_features_count": len(result.get('result', {}).get('risk_features', [])) if result.get('status') == 'success' else 0,
                "impact_features_count": len(result.get('result', {}).get('impact_features', [])) if result.get('status') == 'success' else 0,
                "likelihood_features_count": len(result.get('result', {}).get('likelihood_features', [])) if result.get('status') == 'success' else 0,
                "error": result.get('error') if result.get('status') == 'error' else None
            })
            
        except Exception as e:
            failed += 1
            logger.error(f"Error in test case {test_case['name']}: {e}")
            import traceback
            traceback.print_exc()
            all_results.append({
                "test_case": test_case['name'],
                "domain": test_case['domain'],
                "status": "error",
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

