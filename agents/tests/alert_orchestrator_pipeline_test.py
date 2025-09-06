"""
Test cases for the Alert Orchestrator Pipeline

This file contains unit tests for the AlertOrchestratorPipeline class.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

from app.agents.pipelines.writers.alert_orchestrator_pipeline import (
    AlertOrchestratorPipeline,
    create_alert_orchestrator_pipeline
)
from app.agents.nodes.writers.alerts_agent import SQLAlertResult, SQLAnalysis, LexyFeedConfiguration
from app.core.engine import Engine


class TestAlertOrchestratorPipeline:
    """Test cases for AlertOrchestratorPipeline"""
    
    @pytest.fixture
    def mock_engine(self):
        """Mock engine instance"""
        return Mock(spec=Engine)
    
    @pytest.fixture
    def mock_llm(self):
        """Mock LLM instance"""
        return Mock()
    
    @pytest.fixture
    def mock_retrieval_helper(self):
        """Mock retrieval helper instance"""
        return Mock()
    
    @pytest.fixture
    def mock_alert_agent(self):
        """Mock alert agent instance"""
        mock_agent = Mock()
        mock_agent.generate_alert = AsyncMock()
        mock_agent.create_lexy_api_payload = Mock()
        return mock_agent
    
    @pytest.fixture
    def sample_sql_analysis(self):
        """Sample SQL analysis for testing"""
        return SQLAnalysis(
            tables=["training_records"],
            columns=["training_type", "transcript_status"],
            metrics=["completion_percentage", "expiry_percentage"],
            dimensions=["training_type"],
            filters=[],
            aggregations=[{"column": "transcript_status", "function": "COUNT", "alias": "status_count"}]
        )
    
    @pytest.fixture
    def sample_feed_configuration(self):
        """Sample feed configuration for testing"""
        from app.agents.nodes.writers.alerts_agent import (
            LexyFeedMetric, LexyFeedCondition, LexyFeedNotification, 
            AlertConditionType, ThresholdOperator
        )
        
        return LexyFeedConfiguration(
            metric=LexyFeedMetric(
                domain="training",
                dataset_id="training_dataset",
                measure="completion_percentage",
                aggregation="AVG",
                resolution="Daily",
                filters=[],
                drilldown_dimensions=["training_type"]
            ),
            condition=LexyFeedCondition(
                condition_type=AlertConditionType.THRESHOLD_VALUE,
                threshold_type="based_on_value",
                operator=ThresholdOperator.LESS_THAN,
                value=90.0
            ),
            notification=LexyFeedNotification(
                schedule_type="scheduled",
                metric_name="Training Completion Alert",
                email_addresses=["admin@company.com"],
                subject="Training Completion Below Threshold",
                email_message="Training completion rate has fallen below 90%",
                include_feed_report=True
            ),
            column_selection={"included": ["training_type", "completion_percentage"], "excluded": ["id"]}
        )
    
    @pytest.fixture
    def sample_alert_result(self, sample_sql_analysis, sample_feed_configuration):
        """Sample alert result for testing"""
        return SQLAlertResult(
            feed_configuration=sample_feed_configuration,
            sql_analysis=sample_sql_analysis,
            confidence_score=0.85,
            critique_notes=["Configuration looks good"],
            suggestions=["Consider adding more drilldown dimensions"]
        )
    
    @pytest.fixture
    def alert_pipeline(self, mock_engine, mock_llm, mock_retrieval_helper, mock_alert_agent):
        """Create alert pipeline instance for testing"""
        return AlertOrchestratorPipeline(
            name="test_alert_pipeline",
            version="1.0.0",
            description="Test alert pipeline",
            llm=mock_llm,
            retrieval_helper=mock_retrieval_helper,
            engine=mock_engine,
            alert_agent=mock_alert_agent
        )
    
    def test_pipeline_initialization(self, alert_pipeline):
        """Test pipeline initialization"""
        assert alert_pipeline.name == "test_alert_pipeline"
        assert alert_pipeline.version == "1.0.0"
        assert alert_pipeline.is_initialized is True
        assert alert_pipeline._alert_agent is not None
    
    def test_configuration_management(self, alert_pipeline):
        """Test configuration management"""
        # Test default configuration
        config = alert_pipeline.get_configuration()
        assert "enable_sql_analysis" in config
        assert "enable_alert_generation" in config
        assert "default_confidence_threshold" in config
        
        # Test configuration update
        new_config = {"default_confidence_threshold": 0.9}
        alert_pipeline.update_configuration(new_config)
        updated_config = alert_pipeline.get_configuration()
        assert updated_config["default_confidence_threshold"] == 0.9
    
    def test_metrics_management(self, alert_pipeline):
        """Test metrics management"""
        # Test initial metrics
        metrics = alert_pipeline.get_metrics()
        assert isinstance(metrics, dict)
        
        # Test metrics reset
        alert_pipeline.reset_metrics()
        reset_metrics = alert_pipeline.get_metrics()
        assert len(reset_metrics) == 0
    
    @pytest.mark.asyncio
    async def test_run_pipeline_success(self, alert_pipeline, mock_alert_agent, sample_alert_result):
        """Test successful pipeline execution"""
        # Setup mocks
        mock_alert_agent.generate_alert.return_value = sample_alert_result
        mock_alert_agent.create_lexy_api_payload.return_value = {
            "feed": {"metric": {}, "condition": {}, "notification": {}},
            "confidence": 0.85
        }
        
        # Test data
        sql_queries = ["SELECT * FROM training_records"]
        natural_language_query = "Show training completion rates"
        alert_request = "Alert when completion rate < 90%"
        
        # Run pipeline
        result = await alert_pipeline.run(
            sql_queries=sql_queries,
            natural_language_query=natural_language_query,
            alert_request=alert_request,
            project_id="test_project"
        )
        
        # Verify results
        assert result["post_process"]["success"] is True
        assert "alert_results" in result["post_process"]
        assert "combined_feed_configurations" in result["post_process"]
        assert "orchestration_metadata" in result["post_process"]
        
        # Verify alert agent was called
        mock_alert_agent.generate_alert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_pipeline_validation_filtering(self, alert_pipeline, mock_alert_agent):
        """Test pipeline with validation filtering"""
        # Create alert results with different confidence scores
        high_confidence_result = Mock()
        high_confidence_result.confidence_score = 0.9
        high_confidence_result.feed_configuration = Mock()
        high_confidence_result.sql_analysis = Mock()
        high_confidence_result.critique_notes = []
        high_confidence_result.suggestions = []
        
        low_confidence_result = Mock()
        low_confidence_result.confidence_score = 0.6
        low_confidence_result.feed_configuration = Mock()
        low_confidence_result.sql_analysis = Mock()
        low_confidence_result.critique_notes = []
        low_confidence_result.suggestions = []
        
        # Setup mocks
        mock_alert_agent.generate_alert.side_effect = [high_confidence_result, low_confidence_result]
        mock_alert_agent.create_lexy_api_payload.return_value = {"feed": {}}
        
        # Set high confidence threshold
        alert_pipeline.update_configuration({"default_confidence_threshold": 0.8})
        
        # Test data
        sql_queries = ["SELECT * FROM table1", "SELECT * FROM table2"]
        
        # Run pipeline
        result = await alert_pipeline.run(
            sql_queries=sql_queries,
            natural_language_query="Test query",
            alert_request="Test alert",
            project_id="test_project"
        )
        
        # Verify only high confidence result is included
        assert result["post_process"]["success"] is True
        assert len(result["post_process"]["alert_results"]) == 1  # Only high confidence result
    
    @pytest.mark.asyncio
    async def test_run_pipeline_error_handling(self, alert_pipeline, mock_alert_agent):
        """Test pipeline error handling"""
        # Setup mock to raise exception
        mock_alert_agent.generate_alert.side_effect = Exception("Test error")
        
        # Test data
        sql_queries = ["SELECT * FROM training_records"]
        
        # Run pipeline and expect exception
        with pytest.raises(Exception, match="Test error"):
            await alert_pipeline.run(
                sql_queries=sql_queries,
                natural_language_query="Test query",
                alert_request="Test alert",
                project_id="test_project"
            )
    
    def test_merge_sql_analyses(self, alert_pipeline):
        """Test SQL analysis merging"""
        from app.agents.nodes.writers.alerts_agent import SQLAnalysis
        
        analysis1 = SQLAnalysis(
            tables=["table1"],
            columns=["col1"],
            metrics=["metric1"],
            dimensions=["dim1"],
            filters=[],
            aggregations=[]
        )
        
        analysis2 = SQLAnalysis(
            tables=["table2"],
            columns=["col2"],
            metrics=["metric2"],
            dimensions=["dim2"],
            filters=[],
            aggregations=[]
        )
        
        merged = alert_pipeline._merge_sql_analyses(analysis1, analysis2)
        
        assert "table1" in merged.tables
        assert "table2" in merged.tables
        assert "col1" in merged.columns
        assert "col2" in merged.columns
        assert "metric1" in merged.metrics
        assert "metric2" in merged.metrics
    
    def test_alert_result_to_dict(self, alert_pipeline, sample_alert_result):
        """Test alert result to dictionary conversion"""
        result_dict = alert_pipeline._alert_result_to_dict(sample_alert_result)
        
        assert "feed_configuration" in result_dict
        assert "sql_analysis" in result_dict
        assert "confidence_score" in result_dict
        assert "critique_notes" in result_dict
        assert "suggestions" in result_dict
        assert result_dict["confidence_score"] == 0.85
    
    def test_enable_disable_features(self, alert_pipeline):
        """Test enabling/disabling pipeline features"""
        # Test enabling features
        alert_pipeline.enable_sql_analysis(True)
        alert_pipeline.enable_alert_generation(True)
        alert_pipeline.enable_validation(True)
        
        config = alert_pipeline.get_configuration()
        assert config["enable_sql_analysis"] is True
        assert config["enable_alert_generation"] is True
        assert config["enable_validation"] is True
        
        # Test disabling features
        alert_pipeline.enable_sql_analysis(False)
        alert_pipeline.enable_alert_generation(False)
        alert_pipeline.enable_validation(False)
        
        config = alert_pipeline.get_configuration()
        assert config["enable_sql_analysis"] is False
        assert config["enable_alert_generation"] is False
        assert config["enable_validation"] is False
    
    def test_set_confidence_threshold(self, alert_pipeline):
        """Test setting confidence threshold"""
        # Test valid threshold
        alert_pipeline.set_confidence_threshold(0.7)
        config = alert_pipeline.get_configuration()
        assert config["default_confidence_threshold"] == 0.7
        
        # Test invalid threshold
        with pytest.raises(ValueError, match="Confidence threshold must be between 0.0 and 1.0"):
            alert_pipeline.set_confidence_threshold(1.5)
    
    def test_get_execution_statistics(self, alert_pipeline):
        """Test getting execution statistics"""
        stats = alert_pipeline.get_execution_statistics()
        
        assert "pipeline_metrics" in stats
        assert "configuration" in stats
        assert "alert_agent_available" in stats
        assert "timestamp" in stats
        assert stats["alert_agent_available"] is True


class TestAlertOrchestratorPipelineFactory:
    """Test cases for the factory function"""
    
    @pytest.fixture
    def mock_engine(self):
        """Mock engine instance"""
        return Mock(spec=Engine)
    
    @patch('app.agents.pipelines.writers.alert_orchestrator_pipeline.get_llm')
    @patch('app.agents.pipelines.writers.alert_orchestrator_pipeline.RetrievalHelper')
    @patch('app.agents.pipelines.writers.alert_orchestrator_pipeline.create_llm_instances_from_settings')
    def test_create_alert_orchestrator_pipeline(
        self, 
        mock_create_llm_instances, 
        mock_retrieval_helper_class, 
        mock_get_llm,
        mock_engine
    ):
        """Test factory function"""
        # Setup mocks
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm
        
        mock_retrieval_helper = Mock()
        mock_retrieval_helper_class.return_value = mock_retrieval_helper
        
        mock_llm_instances = (Mock(), Mock(), Mock(), Mock())
        mock_create_llm_instances.return_value = mock_llm_instances
        
        # Create pipeline using factory
        pipeline = create_alert_orchestrator_pipeline(engine=mock_engine)
        
        # Verify pipeline creation
        assert isinstance(pipeline, AlertOrchestratorPipeline)
        assert pipeline.name == "alert_orchestrator_pipeline"
        assert pipeline.version == "1.0.0"
        
        # Verify dependencies were created
        mock_get_llm.assert_called_once()
        mock_retrieval_helper_class.assert_called_once()
        mock_create_llm_instances.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
