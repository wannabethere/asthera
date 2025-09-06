#!/usr/bin/env python3
"""
Example usage of the enhanced Alert Orchestrator Pipeline with sample data integration.

This example demonstrates how the alert orchestrator pipeline now fetches sample data
from SQL execution and uses it to generate more realistic and data-driven alerts.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from app.agents.pipelines.writers.alert_orchestrator_pipeline import create_alert_orchestrator_pipeline
from app.agents.pipelines.sql_execution import SQLExecutionPipeline
from app.core.engine import Engine
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_alert_orchestration_with_sample_data():
    """Example of using the alert orchestrator with sample data integration"""
    
    # Mock engine and retrieval helper (replace with actual instances in real usage)
    engine = None  # Replace with actual Engine instance
    retrieval_helper = RetrievalHelper()
    llm = get_llm()
    
    # Create SQL execution pipeline for sample data fetching
    sql_execution_pipeline = SQLExecutionPipeline(
        name="sample_data_fetcher",
        version="1.0.0",
        description="Pipeline for fetching sample data for alert generation",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine
    )
    
    # Create alert orchestrator pipeline with SQL execution integration
    alert_pipeline = create_alert_orchestrator_pipeline(
        engine=engine,
        llm=llm,
        retrieval_helper=retrieval_helper,
        sql_execution_pipeline=sql_execution_pipeline,
        llm_settings={
            "model_name": "gemini-2.0-flash",
            "sql_parser_temp": 0.0,
            "alert_generator_temp": 0.1,
            "critic_temp": 0.0,
            "refiner_temp": 0.2
        }
    )
    
    # Configure the pipeline
    alert_pipeline.enable_sample_data_fetch(True)
    alert_pipeline.set_sample_data_limit(15)  # Fetch 15 sample rows
    alert_pipeline.set_confidence_threshold(0.8)
    
    # Example SQL queries for training completion analysis
    sql_queries = [
        """
        SELECT 
            tr.training_type AS "Training Type", 
            COUNT(CASE WHEN lower(tr.transcript_status) = lower('Assigned') THEN 1 END) AS "Assigned Count", 
            COUNT(CASE WHEN lower(tr.transcript_status) = lower('Completed') THEN 1 END) AS "Completed Count", 
            COUNT(CASE WHEN lower(tr.transcript_status) = lower('Expired') THEN 1 END) AS "Expired Count", 
            (COUNT(CASE WHEN lower(tr.transcript_status) = lower('Assigned') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) AS "Assigned Percentage", 
            (COUNT(CASE WHEN lower(tr.transcript_status) = lower('Completed') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) AS "Completed Percentage", 
            (COUNT(CASE WHEN lower(tr.transcript_status) = lower('Expired') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) AS "Expired Percentage" 
        FROM csod_training_records AS tr 
        GROUP BY tr.training_type
        """,
        """
        SELECT 
            tr.department AS "Department",
            COUNT(*) AS "Total Trainings",
            AVG(CASE WHEN lower(tr.transcript_status) = lower('Completed') THEN 1.0 ELSE 0.0 END) * 100 AS "Completion Rate"
        FROM csod_training_records AS tr 
        WHERE tr.training_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY tr.department
        HAVING COUNT(*) > 5
        """
    ]
    
    # Natural language descriptions
    natural_language_query = "What are the training completion rates by department and training type?"
    alert_request = "Alert me when completion rates drop below 85% or when there are high numbers of expired trainings"
    
    # Status callback to track progress
    def status_callback(status: str, details: Dict[str, Any]):
        logger.info(f"Status Update - {status}: {details}")
    
    try:
        # Run the alert orchestration with sample data integration
        result = await alert_pipeline.run(
            sql_queries=sql_queries,
            natural_language_query=natural_language_query,
            alert_request=alert_request,
            project_id="training_analytics",
            data_description="Training completion and expiry tracking data",
            session_id="training_alert_session_001",
            status_callback=status_callback,
            configuration={
                "enable_sample_data_fetch": True,
                "sample_data_limit": 15,
                "enable_validation": True,
                "default_confidence_threshold": 0.8
            }
        )
        
        # Display results
        logger.info("=== Alert Orchestration Results ===")
        logger.info(f"Success: {result['post_process']['success']}")
        logger.info(f"Total Alerts Generated: {len(result['post_process']['alert_results'])}")
        
        # Display each alert result
        for i, alert_result in enumerate(result['post_process']['alert_results']):
            logger.info(f"\n--- Alert {i+1} ---")
            logger.info(f"Confidence Score: {alert_result['confidence_score']:.2f}")
            logger.info(f"Alert Type: {alert_result['feed_configuration']['condition']['condition_type']}")
            logger.info(f"Metric: {alert_result['feed_configuration']['metric']['measure']}")
            logger.info(f"Threshold: {alert_result['feed_configuration']['condition']['operator']} {alert_result['feed_configuration']['condition']['value']}")
            
            if alert_result.get('critique_notes'):
                logger.info(f"Critique Notes: {alert_result['critique_notes']}")
            
            if alert_result.get('suggestions'):
                logger.info(f"Suggestions: {alert_result['suggestions']}")
        
        # Display combined feed configurations
        combined_feeds = result['post_process']['combined_feed_configurations']
        logger.info(f"\n=== Combined Feed Configurations ===")
        logger.info(f"Total Feeds: {combined_feeds['summary']['total_feeds']}")
        logger.info(f"Condition Types: {combined_feeds['summary']['condition_types']}")
        logger.info(f"Average Confidence: {combined_feeds['summary']['average_confidence']:.2f}")
        
        # Display orchestration metadata
        metadata = result['post_process']['orchestration_metadata']
        logger.info(f"\n=== Orchestration Metadata ===")
        logger.info(f"Execution Time: {metadata['total_execution_time_seconds']:.2f} seconds")
        logger.info(f"Queries Processed: {metadata['total_queries_processed']}")
        logger.info(f"Alerts Generated: {metadata['total_alerts_generated']}")
        logger.info(f"Average Confidence: {metadata['average_confidence_score']:.2f}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in alert orchestration: {str(e)}")
        raise


async def example_without_sample_data():
    """Example showing the difference when sample data is disabled"""
    
    logger.info("\n=== Example: Alert Generation WITHOUT Sample Data ===")
    
    # Mock engine and retrieval helper
    engine = None
    retrieval_helper = RetrievalHelper()
    llm = get_llm()
    
    # Create alert orchestrator pipeline
    alert_pipeline = create_alert_orchestrator_pipeline(
        engine=engine,
        llm=llm,
        retrieval_helper=retrieval_helper
    )
    
    # Disable sample data fetching
    alert_pipeline.enable_sample_data_fetch(False)
    
    # Simple SQL query
    sql_queries = [
        "SELECT department, COUNT(*) as total, AVG(completion_rate) as avg_completion FROM training_records GROUP BY department"
    ]
    
    try:
        result = await alert_pipeline.run(
            sql_queries=sql_queries,
            natural_language_query="Show training completion by department",
            alert_request="Alert when completion rates are low",
            project_id="test_project",
            configuration={"enable_sample_data_fetch": False}
        )
        
        logger.info("Alert generation completed without sample data")
        logger.info(f"Alerts generated: {len(result['post_process']['alert_results'])}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in alert orchestration without sample data: {str(e)}")
        raise


def demonstrate_configuration_options():
    """Demonstrate various configuration options for the alert orchestrator"""
    
    logger.info("\n=== Configuration Options Demo ===")
    
    # Mock instances
    engine = None
    retrieval_helper = RetrievalHelper()
    llm = get_llm()
    
    # Create pipeline
    pipeline = create_alert_orchestrator_pipeline(
        engine=engine,
        llm=llm,
        retrieval_helper=retrieval_helper
    )
    
    # Demonstrate configuration methods
    logger.info("Available configuration methods:")
    logger.info("- enable_sample_data_fetch(enabled: bool)")
    logger.info("- set_sample_data_limit(limit: int)")
    logger.info("- enable_validation(enabled: bool)")
    logger.info("- set_confidence_threshold(threshold: float)")
    logger.info("- enable_alert_generation(enabled: bool)")
    logger.info("- enable_sql_analysis(enabled: bool)")
    
    # Show current configuration
    config = pipeline.get_configuration()
    logger.info(f"\nCurrent configuration: {config}")
    
    # Demonstrate configuration changes
    pipeline.set_sample_data_limit(20)
    pipeline.set_confidence_threshold(0.9)
    pipeline.enable_validation(True)
    
    updated_config = pipeline.get_configuration()
    logger.info(f"Updated configuration: {updated_config}")


if __name__ == "__main__":
    # Run examples
    asyncio.run(example_alert_orchestration_with_sample_data())
    asyncio.run(example_without_sample_data())
    demonstrate_configuration_options()
