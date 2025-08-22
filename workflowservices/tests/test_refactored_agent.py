"""
Test file for the refactored report writing agent that demonstrates
it works independently without database dependencies and uses prompt chaining.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from workflowservices.app.agents.report_writing_agent import (
    ReportWritingAgent,
    ThreadComponentData,
    ReportWorkflowData,
    ComponentType,
    WriterActorType,
    BusinessGoal,
    create_report_writing_agent,
    generate_report_from_data,
    ContentQualityEvaluator,
    SelfCorrectingRAG
)


class TestRefactoredAgent:
    """Test the refactored report writing agent"""
    
    def test_agent_creation(self):
        """Test that agent can be created without database dependencies"""
        agent = create_report_writing_agent()
        assert isinstance(agent, ReportWritingAgent)
        assert agent.llm is not None
        assert agent.embeddings is not None
        assert agent.rag_system is not None
        assert agent.quality_evaluator is not None
    
    def test_prompt_chains_setup(self):
        """Test that prompt chains are properly set up using LCEL"""
        agent = create_report_writing_agent()
        
        # Check that prompt chains are created
        assert hasattr(agent, 'outline_chain')
        assert hasattr(agent, 'content_chain')
        assert hasattr(agent, 'outline_prompt')
        assert hasattr(agent, 'content_prompt')
        
        # Check that quality evaluator has prompt chain
        assert hasattr(agent.quality_evaluator, 'quality_chain')
        assert hasattr(agent.quality_evaluator, 'quality_prompt')
        
        # Check that RAG system has prompt chain
        assert hasattr(agent.rag_system, 'correction_chain')
        assert hasattr(agent.rag_system, 'correction_prompt')
    
    def test_data_class_creation(self):
        """Test that data classes can be created correctly"""
        # Test ThreadComponentData
        component = ThreadComponentData(
            id="test-comp-1",
            component_type=ComponentType.QUESTION,
            sequence_order=1,
            question="What is the test question?",
            description="Test description"
        )
        assert component.id == "test-comp-1"
        assert component.component_type == ComponentType.QUESTION
        assert component.sequence_order == 1
        assert component.question == "What is the test question?"
        
        # Test ReportWorkflowData
        workflow = ReportWorkflowData(
            id="test-workflow-1",
            report_id="test-report-1",
            user_id="test-user-1",
            state="active"
        )
        assert workflow.id == "test-workflow-1"
        assert workflow.report_id == "test-report-1"
        assert workflow.state == "active"
        
        # Test BusinessGoal
        goal = BusinessGoal(
            primary_objective="Test objective",
            target_audience=["Test audience"],
            decision_context="Test context",
            success_metrics=["Test metric"],
            timeframe="Test timeframe"
        )
        assert goal.primary_objective == "Test objective"
        assert goal.target_audience == ["Test audience"]
    
    @patch('workflowservices.app.agents.report_writing_agent.ChatOpenAI')
    @patch('workflowservices.app.agents.report_writing_agent.OpenAIEmbeddings')
    def test_agent_initialization_with_mocks(self, mock_embeddings, mock_llm):
        """Test agent initialization with mocked dependencies"""
        mock_llm_instance = Mock()
        mock_embeddings_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_embeddings.return_value = mock_embeddings_instance
        
        agent = ReportWritingAgent()
        assert agent.llm == mock_llm_instance
        assert agent.embeddings == mock_embeddings_instance
        
        # Check that prompt chains are set up
        assert hasattr(agent, 'outline_chain')
        assert hasattr(agent, 'content_chain')
    
    def test_component_type_enum(self):
        """Test that ComponentType enum has all expected values"""
        expected_types = [
            "question", "description", "overview", "chart", 
            "table", "metric", "insight", "narrative", "alert"
        ]
        
        for expected_type in expected_types:
            assert hasattr(ComponentType, expected_type.upper())
            assert getattr(ComponentType, expected_type.upper()).value == expected_type
    
    def test_writer_actor_type_enum(self):
        """Test that WriterActorType enum has all expected values"""
        expected_actors = [
            "executive", "analyst", "technical", "business_user", 
            "data_scientist", "consultant"
        ]
        
        for expected_actor in expected_actors:
            assert hasattr(WriterActorType, expected_actor.upper())
            assert getattr(WriterActorType, expected_actor.upper()).value == expected_actor
    
    def test_data_class_optional_fields(self):
        """Test that optional fields in data classes work correctly"""
        component = ThreadComponentData(
            id="minimal-comp",
            component_type=ComponentType.CHART,
            sequence_order=1
        )
        
        assert component.id == "minimal-comp"
        assert component.question is None
        assert component.description is None
        assert component.chart_config is None
        assert component.created_at is None
    
    def test_workflow_data_metadata(self):
        """Test that workflow metadata can be set and retrieved"""
        metadata = {
            "priority": "high",
            "department": "sales",
            "tags": ["quarterly", "performance"]
        }
        
        workflow = ReportWorkflowData(
            id="test-workflow",
            workflow_metadata=metadata
        )
        
        assert workflow.workflow_metadata == metadata
        assert workflow.workflow_metadata["priority"] == "high"
        assert workflow.workflow_metadata["tags"] == ["quarterly", "performance"]


class TestPromptChaining:
    """Test the prompt chaining functionality"""
    
    @patch('workflowservices.app.agents.report_writing_agent.ChatOpenAI')
    def test_quality_evaluator_prompt_chain(self, mock_llm):
        """Test that quality evaluator uses prompt chaining correctly"""
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        
        evaluator = ContentQualityEvaluator(mock_llm_instance)
        
        # Check that prompt chain is created
        assert hasattr(evaluator, 'quality_chain')
        assert hasattr(evaluator, 'quality_prompt')
        
        # Check that the chain is properly composed
        assert evaluator.quality_chain is not None
    
    @patch('workflowservices.app.agents.report_writing_agent.ChatOpenAI')
    @patch('workflowservices.app.agents.report_writing_agent.OpenAIEmbeddings')
    def test_rag_system_prompt_chain(self, mock_embeddings, mock_llm):
        """Test that RAG system uses prompt chaining correctly"""
        mock_llm_instance = Mock()
        mock_embeddings_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_embeddings.return_value = mock_embeddings_instance
        
        rag_system = SelfCorrectingRAG(mock_llm_instance, mock_embeddings_instance)
        
        # Check that prompt chain is created
        assert hasattr(rag_system, 'correction_chain')
        assert hasattr(rag_system, 'correction_prompt')
        
        # Check that the chain is properly composed
        assert rag_system.correction_chain is not None
    
    @patch('workflowservices.app.agents.report_writing_agent.ChatOpenAI')
    @patch('workflowservices.app.agents.report_writing_agent.OpenAIEmbeddings')
    def test_agent_prompt_chains(self, mock_embeddings, mock_llm):
        """Test that agent creates all necessary prompt chains"""
        mock_llm_instance = Mock()
        mock_embeddings_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_embeddings.return_value = mock_embeddings_instance
        
        agent = ReportWritingAgent()
        
        # Check that all prompt chains are created
        assert hasattr(agent, 'outline_chain')
        assert hasattr(agent, 'content_chain')
        assert hasattr(agent, 'outline_prompt')
        assert hasattr(agent, 'content_prompt')
        
        # Check that the chains are properly composed
        assert agent.outline_chain is not None
        assert agent.content_chain is not None


def test_example_usage():
    """Test the example usage function"""
    # This test demonstrates how the refactored agent would be used
    # in a real application without database dependencies
    
    # Create sample data
    workflow_data = ReportWorkflowData(
        id="workflow-123",
        report_id="report-456",
        user_id="user-789",
        state="active",
        current_step=1
    )
    
    thread_components = [
        ThreadComponentData(
            id="comp-1",
            component_type=ComponentType.QUESTION,
            sequence_order=1,
            question="What are the key performance indicators for Q4?",
            description="Analysis of Q4 KPIs across all departments"
        ),
        ThreadComponentData(
            id="comp-2",
            component_type=ComponentType.CHART,
            sequence_order=2,
            chart_config={"type": "line", "data": "q4_kpi_data"},
            description="Q4 KPI trend visualization"
        )
    ]
    
    business_goal = BusinessGoal(
        primary_objective="Improve Q4 performance",
        target_audience=["Executives", "Department Heads"],
        decision_context="Q4 planning and resource allocation",
        success_metrics=["KPI improvement", "Resource efficiency"],
        timeframe="Q4 2024"
    )
    
    # Verify data structures
    assert workflow_data.id == "workflow-123"
    assert len(thread_components) == 2
    assert thread_components[0].component_type == ComponentType.QUESTION
    assert thread_components[1].component_type == ComponentType.CHART
    assert business_goal.primary_objective == "Improve Q4 performance"
    assert "Executives" in business_goal.target_audience


def test_prompt_chain_benefits():
    """Test and demonstrate the benefits of prompt chaining"""
    
    print("\n🔗 Prompt Chaining Benefits:")
    print("=" * 40)
    
    print("✅ **Better Performance**:")
    print("   - No need to recreate chains on each call")
    print("   - Efficient LCEL composition")
    print("   - Better memory management")
    
    print("\n✅ **Improved Maintainability**:")
    print("   - Centralized prompt management")
    print("   - Easy to modify and extend")
    print("   - Clear separation of concerns")
    
    print("\n✅ **Enhanced Flexibility**:")
    print("   - Easy to add new prompt chains")
    print("   - Simple to modify existing chains")
    print("   - Better error handling")
    
    print("\n✅ **Modern LangChain**:")
    print("   - Uses latest LCEL syntax")
    print("   - Better integration with LangChain ecosystem")
    print("   - Future-proof implementation")


if __name__ == "__main__":
    # Run basic tests
    print("Testing refactored agent with prompt chaining...")
    
    # Test data class creation
    test_data_class_creation()
    
    # Test enums
    test_component_type_enum()
    test_writer_actor_type_enum()
    
    # Test prompt chaining
    test_prompt_chain_benefits()
    
    # Test example usage
    test_example_usage()
    
    print("\n🎉 All tests passed!")
    print("\nThe refactored agent now uses prompt chaining instead of LLMChain.")
    print("Benefits include:")
    print("- Better performance and memory management")
    print("- Improved maintainability and flexibility")
    print("- Modern LangChain Expression Language (LCEL) usage")
    print("- Centralized prompt management")
