"""
Test suite for the AskService class in app.services.sql.ask
"""

import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List

from app.services.sql.ask import AskService
from app.services.sql.models import (
    AskRequest,
    AskResult,
    AskResultResponse,
    AskError,
    Configuration,
    QualityScoring,
    StopAskRequest
)
from app.agents.pipelines.base import Pipeline

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create console handler with formatting
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class TestAskService:
    """Test cases for AskService class"""
    
    @pytest.fixture
    def mock_pipelines(self):
        """Create mock pipeline objects for testing"""
        logger.info("Setting up mock pipelines")
        pipelines = {
            "historical_question": Mock(spec=Pipeline),
            "sql_pairs_retrieval": Mock(spec=Pipeline),
            "instructions_retrieval": Mock(spec=Pipeline),
            "intent_classification": Mock(spec=Pipeline),
            "retrieval": Mock(spec=Pipeline),
            "sql_generation_reasoning": Mock(spec=Pipeline),
            "followup_sql_generation_reasoning": Mock(spec=Pipeline),
            "sql_generation": Mock(spec=Pipeline),
            "followup_sql_generation": Mock(spec=Pipeline),
            "sql_correction": Mock(spec=Pipeline),
            "sql_regeneration": Mock(spec=Pipeline),
            "misleading_assistance": Mock(spec=Pipeline),
            "data_assistance": Mock(spec=Pipeline),
            "user_guide_assistance": Mock(spec=Pipeline),
            "sql_functions_retrieval": Mock(spec=Pipeline)
        }
        
        # Set up default mock responses
        for pipeline_name, pipeline in pipelines.items():
            logger.debug(f"Configuring mock responses for {pipeline_name}")
            pipeline.run = AsyncMock(return_value={
                "formatted_output": {"documents": []},
                "post_process": {}
            })
            pipeline.get_streaming_results = AsyncMock(return_value=[])
        
        return pipelines
    
    @pytest.fixture
    def ask_service(self, mock_pipelines):
        """Create AskService instance with mock pipelines"""
        logger.info("Initializing AskService with mock pipelines")
        return AskService(
            pipelines=mock_pipelines,
            allow_intent_classification=True,
            allow_sql_generation_reasoning=True,
            enable_enhanced_sql=True
        )
    
    @pytest.mark.asyncio
    async def test_ask_with_historical_question(self, ask_service, mock_pipelines):
        """Test ask with historical question match"""
        logger.info("Testing ask with historical question match")
        
        # Setup mock response for historical question
        mock_pipelines["historical_question"].run.return_value = {
            "formatted_output": {
                "documents": [{
                    "statement": "SELECT * FROM customers",
                    "viewId": None
                }]
            }
        }
        logger.debug("Configured historical question mock response")
        
        # Create test request
        request = AskRequest(
            _query_id="test123",
            query="Show me all customers",
            project_id="proj123",
            mdl_hash= "id",
            configurations=Configuration(language="English"),
            histories=[],
            enable_scoring=True
        )
        
        logger.debug(f"Created test request with query_id: {request.query_id}")
        
        # Execute ask
        logger.info("Executing ask request")
        result = await ask_service.ask(request)
        
        # Verify results
        logger.info("Verifying results")
        assert "ask_result" in result
        assert len(result["ask_result"]) == 1
        assert result["ask_result"][0].sql == "SELECT * FROM customers"
        assert result["metadata"]["type"] == "TEXT_TO_SQL"
        logger.info("Test completed successfully")
    
    @pytest.mark.asyncio
    async def test_ask_with_intent_classification(self, ask_service, mock_pipelines):
        """Test ask with intent classification"""
        logger.info("Testing ask with intent classification")
        
        # Setup mock responses
        mock_pipelines["historical_question"].run.return_value = {
            "formatted_output": {"documents": []}
        }
        
        mock_pipelines["intent_classification"].run.return_value = {
            "post_process": {
                "intent": "MISLEADING_QUERY",
                "rephrased_question": "What data do you have about customers?",
                "reasoning": "Query is too vague",
                "db_schemas": []
            }
        }
        logger.debug("Configured intent classification mock responses")
        
        # Create test request
        request = AskRequest(
            _query_id="test123",
            query="Tell me about customers",
            project_id="proj123",
            mdl_hash="id",
            configurations=Configuration(language="English"),
            histories=[],
            enable_scoring=True
        )
        logger.debug(f"Created test request with query_id: {request.query_id}")
        
        # Execute ask
        logger.info("Executing ask request")
        result = await ask_service.ask(request)
        
        # Verify results
        logger.info("Verifying results")
        assert result["metadata"]["type"] == "MISLEADING_QUERY"
        assert "ask_result" in result
        assert len(result["ask_result"]) == 0  # Check for empty ask_result
        logger.info("Test completed successfully")
    
    @pytest.mark.asyncio
    async def test_ask_with_sql_generation(self, ask_service, mock_pipelines):
        """Test ask with SQL generation"""
        logger.info("Testing ask with SQL generation")
        
        # Setup mock responses
        mock_pipelines["historical_question"].run.return_value = {
            "formatted_output": {"documents": []}
        }
        
        mock_pipelines["intent_classification"].run.return_value = {
            "post_process": {
                "intent": "TEXT_TO_SQL",
                "rephrased_question": "Show me all customers",
                "reasoning": "Direct SQL query",
                "db_schemas": []
            }
        }
        
        mock_pipelines["retrieval"].run.return_value = {
            "construct_retrieval_results": {
                "retrieval_results": [
                    {
                        "table_name": "customers",
                        "table_ddl": "CREATE TABLE customers (id INT, name VARCHAR(100))"
                    }
                ]
            }
        }
        
        # Mock sql_generation_reasoning to return a string in post_process
        mock_pipelines["sql_generation_reasoning"].run.return_value = {
            "post_process": "We need to select all columns from the customers table"
        }
        
        mock_pipelines["sql_generation"].run.return_value = {
            "post_process": {
                "valid_generation_results": [
                    {
                        "sql": "SELECT * FROM customers"
                    }
                ]
            }
        }

        # Mock sql_functions_retrieval
        mock_pipelines["sql_functions_retrieval"].run.return_value = {
            "formatted_output": {"documents": []}
        }
        logger.debug("Configured SQL generation mock responses")
        
        # Create test request
        request = AskRequest(
            _query_id="test123",
            query="Show me all customers",
            project_id="proj123",
            mdl_hash="id",
            configurations=Configuration(language="English"),
            histories=[],
            enable_scoring=True
        )
        logger.debug(f"Created test request with query_id: {request.query_id}")
        
        # Execute ask
        logger.info("Executing ask request")
        result = await ask_service.ask(request)
        
        # Verify results
        logger.info("Verifying results")
        assert "ask_result" in result
        assert len(result["ask_result"]) == 1
        assert result["ask_result"][0].sql == "SELECT * FROM customers"
        assert result["metadata"]["type"] == "TEXT_TO_SQL"
        logger.info("Test completed successfully")
    
    @pytest.mark.asyncio
    async def test_ask_with_error_handling(self, ask_service, mock_pipelines):
        """Test ask with error handling"""
        logger.info("Testing ask with error handling")
        
        # Setup mock to raise exception
        mock_pipelines["historical_question"].run.side_effect = Exception("Test error")
        logger.debug("Configured mock to raise test error")
        
        # Create test request
        request = AskRequest(
            query_id="test123",
            query="Show me all customers",
            project_id="proj123",
            mdl_hash= "id",
            configurations=Configuration(language="English"),
            histories=[],
            enable_scoring=True
        )
        logger.debug(f"Created test request with query_id: {request.query_id}")
        
        # Execute ask
        logger.info("Executing ask request")
        result = await ask_service.ask(request)
        
        # Verify error handling
        logger.info("Verifying error handling")
        assert result["metadata"]["error_type"] == "OTHERS"
        assert "Test error" in result["metadata"]["error_message"]
        logger.info("Test completed successfully")
    
    @pytest.mark.asyncio
    async def test_ask_with_enhanced_sql(self, ask_service, mock_pipelines):
        """Test ask with enhanced SQL pipeline"""
        logger.info("Testing ask with enhanced SQL pipeline")
        
        # Setup mock responses for enhanced SQL pipeline
        mock_pipelines["historical_question"].run.return_value = {
            "formatted_output": {"documents": []}
        }
        
        mock_pipelines["intent_classification"].run.return_value = {
            "post_process": {
                "intent": "TEXT_TO_SQL",
                "rephrased_question": "Show me all customers",
                "reasoning": "Direct SQL query",
                "db_schemas": []
            }
        }
        
        mock_pipelines["retrieval"].run.return_value = {
            "construct_retrieval_results": {
                "retrieval_results": [
                    {
                        "table_name": "customers",
                        "table_ddl": "CREATE TABLE customers (id INT, name VARCHAR(100))"
                    }
                ]
            }
        }
        logger.debug("Configured enhanced SQL pipeline mock responses")
        
        # Create test request with enhanced SQL enabled
        request = AskRequest(
            query_id="test123",
            query="Show me all customers",
            project_id="proj123",
            mdl_hash= "id",
            configurations=Configuration(language="English"),
            histories=[],
            enable_scoring=True
        )
        logger.debug(f"Created test request with query_id: {request.query_id}")
        
        # Execute ask
        logger.info("Executing ask request")
        result = await ask_service.ask(request)
        
        # Verify enhanced SQL pipeline was used
        logger.info("Verifying enhanced SQL pipeline usage")
        assert result["metadata"]["enhanced_sql_used"] == True
        logger.info("Test completed successfully")
    
    def test_stop_ask(self, ask_service):
        """Test stop_ask functionality"""
        logger.info("Testing stop_ask functionality")
        
        # Create stop request
        stop_request = StopAskRequest(
            status="stopped"
        )
        stop_request.query_id = "test123"
        logger.debug(f"Created stop request for query_id: {stop_request.query_id}")
        
        # Stop the ask
        logger.info("Stopping ask request")
        ask_service.stop_ask(stop_request)
        
        # Verify ask was stopped
        logger.info("Verifying ask was stopped")
        result = ask_service.get_ask_result(stop_request)
        assert result.status == "stopped"
        logger.info("Test completed successfully") 