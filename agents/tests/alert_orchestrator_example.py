"""
Example usage of the Alert Orchestrator Pipeline

This file demonstrates how to use the AlertOrchestratorPipeline to generate
alert configurations from SQL queries and natural language requests.
"""

import asyncio
import logging
from typing import Dict, Any, List

from app.agents.pipelines.writers.alert_orchestrator_pipeline import (
    AlertOrchestratorPipeline,
    create_alert_orchestrator_pipeline
)
from app.core.engine import Engine
from app.core.dependencies import get_llm
from app.agents.retrieval.retrieval_helper import RetrievalHelper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_alert_orchestration():
    """Example of using the Alert Orchestrator Pipeline"""
    
    # Initialize dependencies
    engine = Engine()  # You'll need to configure this with your actual engine
    llm = get_llm()
    retrieval_helper = RetrievalHelper()
    
    # Create the alert orchestrator pipeline
    alert_pipeline = create_alert_orchestrator_pipeline(
        engine=engine,
        llm=llm,
        retrieval_helper=retrieval_helper,
        llm_settings={
            "model_name": "gemini-2.0-flash",
            "sql_parser_temp": 0.0,
            "alert_generator_temp": 0.1,
            "critic_temp": 0.0,
            "refiner_temp": 0.2
        }
    )
    
    # Example SQL queries for training completion tracking
    sql_queries = [
        """SELECT tr.training_type AS "Training Type", 
               COUNT(CASE WHEN lower(tr.transcript_status) = lower('Assigned') THEN 1 END) AS "Assigned Count", 
               COUNT(CASE WHEN lower(tr.transcript_status) = lower('Completed') THEN 1 END) AS "Completed Count", 
               COUNT(CASE WHEN lower(tr.transcript_status) = lower('Expired') THEN 1 END) AS "Expired Count", 
               (COUNT(CASE WHEN lower(tr.transcript_status) = lower('Assigned') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) AS "Assigned Percentage", 
               (COUNT(CASE WHEN lower(tr.transcript_status) = lower('Completed') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) AS "Completed Percentage", 
               (COUNT(CASE WHEN lower(tr.transcript_status) = lower('Expired') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) AS "Expired Percentage" 
               FROM csod_training_records AS tr GROUP BY tr.training_type""",
        
        """SELECT department, 
               COUNT(*) as total_assignments,
               COUNT(CASE WHEN status = 'Completed' THEN 1 END) as completed_count,
               (COUNT(CASE WHEN status = 'Completed' THEN 1 END) * 100.0 / COUNT(*)) as completion_rate
               FROM training_assignments 
               WHERE assignment_date >= CURRENT_DATE - INTERVAL '30 days'
               GROUP BY department"""
    ]
    
    # Natural language descriptions
    natural_language_query = "What are the training completion rates by department and training type?"
    alert_request = "Alert me when training completion rates fall below 90% or when expiry rates exceed 10%"
    
    # Status callback function for monitoring progress
    def status_callback(status: str, details: Dict[str, Any]):
        logger.info(f"Status Update - {status}: {details}")
    
    try:
        # Run the alert orchestration pipeline
        result = await alert_pipeline.run(
            sql_queries=sql_queries,
            natural_language_query=natural_language_query,
            alert_request=alert_request,
            project_id="training_compliance",
            data_description="Training completion and compliance tracking data",
            session_id="training_alert_session_001",
            status_callback=status_callback,
            configuration={
                "enable_validation": True,
                "default_confidence_threshold": 0.8
            }
        )
        
        # Process results
        if result["post_process"]["success"]:
            logger.info("Alert orchestration completed successfully!")
            
            # Display results
            orchestration_metadata = result["post_process"]["orchestration_metadata"]
            logger.info(f"Total execution time: {orchestration_metadata['total_execution_time_seconds']:.2f} seconds")
            logger.info(f"Total alerts generated: {orchestration_metadata['total_alerts_generated']}")
            logger.info(f"Average confidence: {orchestration_metadata['average_confidence_score']:.2f}")
            
            # Display individual alert results
            alert_results = result["post_process"]["alert_results"]
            for i, alert_result in enumerate(alert_results):
                logger.info(f"\nAlert {i+1}:")
                logger.info(f"  Confidence: {alert_result['confidence_score']:.2f}")
                logger.info(f"  Condition Type: {alert_result['feed_configuration']['condition']['condition_type']}")
                logger.info(f"  Metric: {alert_result['feed_configuration']['metric']['measure']}")
                logger.info(f"  Threshold: {alert_result['feed_configuration']['condition']['operator']} {alert_result['feed_configuration']['condition']['value']}")
            
            # Display combined feed configurations
            combined_configs = result["post_process"]["combined_feed_configurations"]
            logger.info(f"\nCombined Feed Configurations:")
            logger.info(f"  Total feeds: {combined_configs['summary']['total_feeds']}")
            logger.info(f"  Condition types: {combined_configs['summary']['condition_types']}")
            
            return result
        else:
            logger.error("Alert orchestration failed")
            return None
            
    except Exception as e:
        logger.error(f"Error in alert orchestration: {str(e)}")
        return None


async def example_with_custom_configuration():
    """Example with custom pipeline configuration"""
    
    # Initialize dependencies
    engine = Engine()
    llm = get_llm()
    retrieval_helper = RetrievalHelper()
    
    # Create pipeline with custom configuration
    alert_pipeline = create_alert_orchestrator_pipeline(
        engine=engine,
        llm=llm,
        retrieval_helper=retrieval_helper
    )
    
    # Update configuration
    alert_pipeline.update_configuration({
        "enable_sql_analysis": True,
        "enable_alert_generation": True,
        "enable_critique": True,
        "enable_refinement": True,
        "enable_validation": True,
        "default_confidence_threshold": 0.7  # Lower threshold for more alerts
    })
    
    # Example for operational metrics
    sql_queries = [
        """SELECT 
               DATE(created_at) as date,
               COUNT(*) as total_incidents,
               COUNT(CASE WHEN status = 'Resolved' THEN 1 END) as resolved_count,
               AVG(resolution_time_hours) as avg_resolution_time
               FROM incidents 
               WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
               GROUP BY DATE(created_at)
               ORDER BY date"""
    ]
    
    natural_language_query = "Show me daily incident resolution metrics for the past week"
    alert_request = "Alert me when average resolution time exceeds 24 hours or when resolution rate drops below 80%"
    
    try:
        result = await alert_pipeline.run(
            sql_queries=sql_queries,
            natural_language_query=natural_language_query,
            alert_request=alert_request,
            project_id="incident_management",
            data_description="IT incident tracking and resolution data",
            session_id="incident_alert_session"
        )
        
        if result["post_process"]["success"]:
            logger.info("Custom configuration example completed successfully!")
            return result
        else:
            logger.error("Custom configuration example failed")
            return None
            
    except Exception as e:
        logger.error(f"Error in custom configuration example: {str(e)}")
        return None


async def main():
    """Main function to run examples"""
    logger.info("Starting Alert Orchestrator Pipeline Examples")
    
    # Run basic example
    logger.info("\n=== Running Basic Example ===")
    basic_result = await example_alert_orchestration()
    
    # Run custom configuration example
    logger.info("\n=== Running Custom Configuration Example ===")
    custom_result = await example_with_custom_configuration()
    
    logger.info("\nExamples completed!")


if __name__ == "__main__":
    asyncio.run(main())
