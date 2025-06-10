import asyncio
import pytest
import pytest_asyncio
import json
from typing import Dict, Any, List
from datetime import datetime

from app.agents.pipelines.enhanced_sql_pipeline import (
    EnhancedSQLPipelineWrapper,
    PipelineRequest,
    PipelineType,
    SQLAdvancedRelevanceScorer
)
from app.services.sql.ask import AskService
from app.services.sql.ask_details import AskDetailsService
from app.services.sql.chart import ChartService
from app.services.sql.instructions import InstructionsService
from app.services.sql.question_recommendation import QuestionRecommendation
from app.services.sql.semantics_description import SemanticsDescription
from app.services.sql.models import (
    AskRequest,
    AskDetailsRequest,
    AskResultRequest,
    AskDetailsResultRequest,
    Configuration,
    ChartRequest,
    ChartResultRequest,
    StopChartRequest,
    IndexRequest,
    Instruction
)
from app.storage.documents import DocumentChromaStore
from app.core.provider import DocumentStoreProvider
from app.settings import get_settings
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
import chromadb

settings = get_settings()

class TestSQLServicesIntegration:
    """Integration tests for SQL services using actual providers and document stores"""
    
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self):
        """Set up test environment with actual providers and document stores"""
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.0,
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize ChromaDB client
        self.persistent_client = chromadb.PersistentClient(
            path=settings.CHROMA_STORE_PATH
        )
        
        # Initialize document stores
        self.document_stores = {
            "db_schema": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="db_schema"
            ),
            "sql_pairs": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="sql_pairs"
            ),
            "instructions": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="instructions"
            ),
            "historical_question": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="historical_question"
            ),
            "table_description": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="table_description"
            )
        }
        
        # Initialize document store provider
        self.document_provider = DocumentStoreProvider(stores=self.document_stores)
        
        # Load MDL schemas
        self.cornerstone_schema = self._load_mdl_schema("/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/sql_meta/cornerstone/mdl.json")
        self.sumtotal_schema = self._load_mdl_schema("/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/sql_meta/employee_training/mdl.json")
        
        # Set up test schema
        self.schema_context = self._setup_test_schema()
        self.schema_documents = self._setup_schema_documents()
        
        # Set up pipelines
        pipelines = self._setup_pipelines()
        
        # Initialize all services with the same pipeline configuration
        self.ask_service = AskService(
            pipelines=pipelines,
            enable_enhanced_sql=True,
            sql_scoring_config_path=None,  # Use default config
            maxsize=1000,
            ttl=60
        )
        print("Ask service initialized")
        
        self.ask_details_service = AskDetailsService(
            pipelines=pipelines,
            enable_enhanced_sql=True,
            sql_scoring_config_path=None,  # Use default config
            maxsize=1000,
            ttl=60
        )
        
        # Initialize chart service
        self.chart_service = ChartService(
            pipelines=pipelines,
            maxsize=1000,
            ttl=60
        )
        
        self.instructions_service = InstructionsService(
            pipelines=pipelines,
            maxsize=1000,
            ttl=60
        )
        
        self.question_recommendation = QuestionRecommendation(
            pipelines=pipelines,
            maxsize=1000,
            ttl=60
        )
        
        self.semantics_description = SemanticsDescription(
            pipelines=pipelines,
            maxsize=1000,
            ttl=60
        )
        
        yield
        
        # Cleanup
        await self._cleanup()
    
    def _load_mdl_schema(self, file_path: str) -> Dict[str, Any]:
        """Load MDL schema from file"""
        with open(file_path, 'r') as f:
            return json.load(f)
    
    def _setup_test_schema(self) -> Dict[str, Any]:
        """Set up test database schema context using actual MDL schemas"""
        schema = {
            "schema": {},
            "relationships": {}
        }
        
        # Add Cornerstone schema
        for model in self.cornerstone_schema["models"]:
            schema["schema"][model["name"]] = [
                col["name"] for col in model["columns"]
            ]
        
        # Add SumTotal schema
        for model in self.sumtotal_schema["models"]:
            schema["schema"][model["name"]] = [
                col["name"] for col in model["columns"]
            ]
        
        return schema
    
    def _setup_schema_documents(self) -> list:
        """Set up schema documents for testing using actual MDL schemas"""
        documents = []
        
        # Add Cornerstone table DDLs
        for model in self.cornerstone_schema["models"]:
            columns = []
            for col in model["columns"]:
                col_def = f"{col['name']} {col['type']}"
                if col.get("isCalculated"):
                    col_def += f" GENERATED ALWAYS AS ({col['expression']}) STORED"
                columns.append(col_def)
            
            ddl = f"CREATE TABLE {model['name']} (\n    " + ",\n    ".join(columns) + "\n)"
            if model.get("primaryKey"):
                ddl += f"\nPRIMARY KEY ({model['primaryKey']})"
            documents.append(ddl)
        
        # Add SumTotal table DDLs
        for model in self.sumtotal_schema["models"]:
            columns = []
            for col in model["columns"]:
                col_def = f"{col['name']} {col['type']}"
                if col.get("isCalculated"):
                    col_def += f" GENERATED ALWAYS AS ({col['expression']}) STORED"
                columns.append(col_def)
            
            ddl = f"CREATE TABLE {model['name']} (\n    " + ",\n    ".join(columns) + "\n)"
            if model.get("primaryKey"):
                ddl += f"\nPRIMARY KEY ({model['primaryKey']})"
            documents.append(ddl)
        
        return documents
    
    def _setup_pipelines(self) -> Dict[str, Any]:
        """Set up actual pipeline components"""
        class MockPipeline:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def run(self, **kwargs):
                return self.return_value
        
        # Initialize enhanced SQL pipeline components
        relevance_scorer = SQLAdvancedRelevanceScorer(
            config_file_path=None  # Use default config
        )
        
        # Create a mock SQL pipeline that returns a basic SQL query
        mock_sql_pipeline = MockPipeline({
            "sql": "SELECT * FROM csod_training_records WHERE Completed_Date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)",
            "reasoning": "Test SQL generation",
            "quality_score": 0.9,
            "quality_level": "HIGH",
            "recommendations": []
        })
        
        # Create a mock chart generation pipeline
        mock_chart_pipeline = MockPipeline({
            "chart_schema": {
                "data": {
                    "values": [
                        {"month": "2024-01", "completion_rate": 85.5},
                        {"month": "2024-02", "completion_rate": 88.2},
                        {"month": "2024-03", "completion_rate": 90.1}
                    ]
                },
                "mark": "line",
                "encoding": {
                    "x": {"field": "month", "type": "temporal"},
                    "y": {"field": "completion_rate", "type": "quantitative"}
                }
            },
            "reasoning": "Test chart generation",
            "quality_score": 0.9,
            "error_type": "",
            "error_message": ""
        })
        
        enhanced_sql_wrapper = EnhancedSQLPipelineWrapper(
            sql_pipeline=mock_sql_pipeline,  # Use mock SQL pipeline
            relevance_scorer=relevance_scorer,
            enable_scoring=True,
            document_store_provider=self.document_provider
        )
        
        # Create a base pipeline configuration that all services can use
        base_pipeline = {
            "sql_pipeline": enhanced_sql_wrapper,
            "sql_summary": MockPipeline({"summary": "Test SQL summary", "quality_score": 0.9}),
            "sql_breakdown": MockPipeline({
                "breakdowns": [{"sql": "SELECT * FROM test", "summary": "Test breakdown"}],
                "quality_score": 0.9
            }),
            "retrieval": MockPipeline({"results": [], "quality_score": 0.9}),
            "historical_question": MockPipeline({"questions": [], "quality_score": 0.9}),
            "sql_pairs_retrieval": MockPipeline({"pairs": [], "quality_score": 0.9}),
            "instructions_retrieval": MockPipeline({"instructions": [], "quality_score": 0.9}),
            "intent_classification": MockPipeline({
                "intent": "TEXT_TO_SQL",
                "confidence": 0.9,
                "quality_score": 0.9
            }),
            "sql_generation": mock_sql_pipeline,
            "followup_sql_generation": mock_sql_pipeline,
            "sql_correction": mock_sql_pipeline,
            "sql_regeneration": mock_sql_pipeline,
            "misleading_assistance": MockPipeline({
                "type": "MISLEADING_QUERY",
                "reasoning": "Test misleading assistance",
                "quality_score": 0.9
            }),
            "data_assistance": MockPipeline({
                "type": "DATA_ASSISTANCE",
                "reasoning": "Test data assistance",
                "quality_score": 0.9
            }),
            "user_guide_assistance": MockPipeline({
                "type": "USER_GUIDE",
                "reasoning": "Test user guide assistance",
                "quality_score": 0.9
            }),
            "llm": self.llm,
            "sql_executor": MockPipeline({
                "rows": [],
                "columns": [],
                "quality_score": 0.9
            }),
            "question_recommendation": MockPipeline({
                "questions": [],
                "quality_score": 0.9
            }),
            "semantics_description": MockPipeline({
                "description": "Test semantics description",
                "quality_score": 0.9
            }),
            "sql_generation_reasoning": MockPipeline({
                "reasoning": "Test SQL generation reasoning",
                "quality_score": 0.9
            }),
            "chart_generation": mock_chart_pipeline
        }
        
        return base_pipeline
    
    async def _cleanup(self):
        """Clean up test resources"""
        # Add cleanup logic here
        pass
    
    @pytest.mark.asyncio
    async def test_ask_service_integration(self):
        """Test AskService with actual providers"""
        # Test case 1: Simple Cornerstone query
        query = "Show me all employees who completed their training in the last month"
        ask_request = AskRequest(
            query_id="test_query_1",
            query=query,
            mdl_hash="cornerstone_mdl",
            project_id="test_project",
            configurations=Configuration(language="English"),
            enable_scoring=True
        )
        
        result = await self.ask_service.ask(ask_request)
        
        assert result is not None
        assert "ask_result" in result
        assert "metadata" in result
        assert result["metadata"]["type"] == "TEXT_TO_SQL"
        
        # Test case 2: Complex SumTotal query with follow-up
        complex_query = "Find employees who have overdue certifications and their managers"
        ask_request = AskRequest(
            query_id="test_query_2",
            query=complex_query,
            mdl_hash="sumtotal_mdl",
            project_id="test_project",
            configurations=Configuration(language="English"),
            enable_scoring=True,
            histories=[{
                "question": query,
                "sql": "SELECT * FROM csod_training_records WHERE Completed_Date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)"
            }]
        )
        
        result = await self.ask_service.ask(ask_request)
        
        assert result is not None
        assert "ask_result" in result
        assert "metadata" in result
        assert result["metadata"]["type"] == "TEXT_TO_SQL"
        
        # Test case 3: Query with quality scoring
        scored_query = "Calculate training completion rates by division and position"
        ask_request = AskRequest(
            query_id="test_query_3",
            query=scored_query,
            mdl_hash="cornerstone_mdl",
            project_id="test_project",
            configurations=Configuration(language="English"),
            enable_scoring=True
        )
        
        result = await self.ask_service.ask(ask_request)
        print(result['metadata'])
        assert result is not None
        assert "ask_result" in result
        assert "metadata" in result
        #assert "quality_scoring" in result["metadata"]
    
    @pytest.mark.asyncio
    async def test_ask_details_service_integration(self):
        """Test AskDetailsService with actual providers"""
        # Test case 1: Cornerstone SQL breakdown
        sql = """
        SELECT 
            Division,
            Position,
            COUNT(*) as total_assignments,
            COUNT(CASE WHEN Transcript_Status = 'Satisfied' THEN 1 END) as completed_assignments,
            COUNT(CASE WHEN Transcript_Status = 'Satisfied' THEN 1 END) * 100.0 / COUNT(*) as completion_rate
        FROM csod_training_records
        WHERE Assigned_Date >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY Division, Position
        ORDER BY completion_rate DESC
        """
        
        ask_details_request = AskDetailsRequest(
            query_id="test_details_1",
            query="Show training completion rates by division and position",
            sql=sql,
            project_id="test_project",
            configurations=Configuration(language="English"),
            enable_scoring=True
        )
        
        result = await self.ask_details_service.ask_details(ask_details_request)
        
        assert result is not None
        assert "ask_details_result" in result
        assert "metadata" in result
        assert result["metadata"]["enhanced_sql_used"] is True
        
        # Test case 2: SumTotal SQL breakdown with quality scoring
        complex_sql = """
        WITH training_metrics AS (
            SELECT 
                PrimaryDomain,
                PrimaryOrganization,
                COUNT(DISTINCT EmployeeID) as total_employees,
                COUNT(CASE WHEN TrainingStatus = 'Completed' THEN 1 END) as completed_trainings,
                COUNT(CASE WHEN isCertification = true AND TrainingStatus = 'Completed' THEN 1 END) as completed_certifications
            FROM employee_training_records
            GROUP BY PrimaryDomain, PrimaryOrganization
        )
        SELECT 
            tm.*,
            CASE 
                WHEN completed_certifications * 100.0 / NULLIF(total_employees, 0) >= 90 THEN 'High Compliance'
                WHEN completed_certifications * 100.0 / NULLIF(total_employees, 0) >= 70 THEN 'Medium Compliance'
                ELSE 'Low Compliance'
            END as compliance_level
        FROM training_metrics tm
        ORDER BY completed_certifications DESC
        """
        
        ask_details_request = AskDetailsRequest(
            query_id="test_details_2",
            query="Analyze training compliance levels across domains and organizations",
            sql=complex_sql,
            project_id="test_project",
            configurations=Configuration(language="English"),
            enable_scoring=True
        )
        
        result = await self.ask_details_service.ask_details(ask_details_request)
        print(result['metadata'])
        assert result is not None
        assert "ask_details_result" in result
        assert "metadata" in result
        #assert "quality_scoring" in result["metadata"]
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in both services"""
        # Test case 1: Invalid SQL in AskDetailsService
        invalid_sql = "SELECT * FROM nonexistent_table"
        ask_details_request = AskDetailsRequest(
            query_id="test_error_1",
            query="Test invalid SQL",
            sql=invalid_sql,
            project_id="test_project",
            configurations=Configuration(language="English"),
            enable_scoring=True
        )
        
        result = await self.ask_details_service.ask_details(ask_details_request)
        
        assert result is not None
        assert "metadata" in result
        assert result["metadata"]["error_type"] != ""
        
        # Test case 2: Invalid query in AskService
        invalid_query = "Show me data from table that doesn't exist"
        ask_request = AskRequest(
            query_id="test_error_2",
            query=invalid_query,
            project_id="test_project",
            configurations=Configuration(language="English"),
            enable_scoring=True
        )
        
        result = await self.ask_service.ask(ask_request)
        
        assert result is not None
        assert "metadata" in result
        assert result["metadata"]["error_type"] != ""
    
    @pytest.mark.asyncio
    async def test_quality_scoring_integration(self):
        """Test quality scoring functionality in both services"""
        # Test case 1: High quality Cornerstone SQL
        high_quality_sql = """
        SELECT 
            DATE_FORMAT(Assigned_Date, '%Y-%m') as month,
            COUNT(DISTINCT User_ID) as unique_employees,
            COUNT(*) as total_assignments,
            COUNT(CASE WHEN Transcript_Status = 'Satisfied' THEN 1 END) as completed_assignments,
            COUNT(CASE WHEN Transcript_Status = 'Satisfied' THEN 1 END) * 100.0 / COUNT(*) as completion_rate
        FROM csod_training_records
        WHERE Assigned_Date >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
        GROUP BY DATE_FORMAT(Assigned_Date, '%Y-%m')
        ORDER BY month
        """
        
        ask_details_request = AskDetailsRequest(
            query_id="test_quality_1",
            query="Show monthly training completion trends for the last year",
            sql=high_quality_sql,
            project_id="test_project",
            configurations=Configuration(language="English"),
            enable_scoring=True
        )
        
        result = await self.ask_details_service.ask_details(ask_details_request)
        
        assert result is not None
        assert "metadata" in result
        #assert "quality_scoring" in result["metadata"]
        print(result['metadata'])
        #quality_scoring = result["metadata"]["quality_scoring"]
        #assert quality_scoring["final_score"] > 0.7  # High quality threshold
        
        # Test case 2: Complex SumTotal query with quality assessment
        complex_query = "Analyze certification compliance patterns and identify departments at risk of non-compliance"
        ask_request = AskRequest(
            query_id="test_quality_2",
            query=complex_query,
            project_id="test_project",
            configurations=Configuration(language="English"),
            enable_scoring=True
        )
        
        result = await self.ask_service.ask(ask_request)
        print(result['metadata'])
        assert result is not None
        assert "metadata" in result
        #assert "quality_scoring" in result["metadata"]
        #quality_scoring = result["metadata"]["quality_scoring"]
        #assert "final_score" in quality_scoring
        #assert "quality_level" in quality_scoring
        #assert "recommendations" in quality_scoring
    
    @pytest.mark.asyncio
    async def test_chart_service_integration(self):
        """Test ChartService with actual providers"""
        # Test case 1: Generate chart from SQL data
        sql = """
        SELECT 
            DATE_FORMAT(Assigned_Date, '%Y-%m') as month,
            COUNT(CASE WHEN Transcript_Status = 'Satisfied' THEN 1 END) * 100.0 / COUNT(*) as completion_rate
        FROM csod_training_records
        WHERE Assigned_Date >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
        GROUP BY DATE_FORMAT(Assigned_Date, '%Y-%m')
        ORDER BY month
        """
        
        chart_request = ChartRequest(
            query_id="test_chart_1",
            query="Show training completion rate trends over time",
            sql=sql,
            project_id="test_project",
            configurations=Configuration(language="English"),
            remove_data_from_chart_schema=False,
            mdl_hash="cornerstone_mdl"
        )
        
        result = await self.chart_service.chart(chart_request)
        
        assert result is not None
        assert "chart_result" in result
        assert "metadata" in result
        print(result['metadata'])
        
        # Test case 2: Generate chart with custom data
        custom_data = {
            "values": [
                {"month": "2024-01", "completion_rate": 85.5},
                {"month": "2024-02", "completion_rate": 88.2},
                {"month": "2024-03", "completion_rate": 90.1}
            ]
        }
        
        chart_request = ChartRequest(
            query_id="test_chart_2",
            query="Show training completion rate trends",
            sql="",  # Empty SQL since we're using custom data
            project_id="test_project",
            configurations=Configuration(language="English"),
            data=custom_data,
            remove_data_from_chart_schema=True,
            mdl_hash="cornerstone_mdl"
        )
        
        result = await self.chart_service.chart(chart_request)
        
        assert result is not None
        assert "chart_result" in result
        assert "metadata" in result
        print(result['metadata'])
        
        # Test case 3: Stop chart generation
        stop_request = StopChartRequest(query_id="test_chart_1", status='stopped')
        self.chart_service.stop_chart(stop_request)
        
        
        result_request = ChartResultRequest(query_id="test_chart_1")
        result = self.chart_service.get_chart_result(result_request)
        
        assert result is not None
        assert result.status == "failed"
    
    @pytest.mark.asyncio
    async def test_instructions_service_integration(self):
        """Test InstructionsService with actual providers"""
        # Test case 1: Index default instructions
        default_instructions = [
            {
                "id": "default_1",
                "instruction": "Always include completion rates in training analysis",
                "is_default": True,
                "questions": []
            },
            {
                "id": "default_2",
                "instruction": "Format dates in YYYY-MM-DD format",
                "is_default": True,
                "questions": []
            }
        ]
        
        index_request = IndexRequest(
            event_id="test_index_1",
            project_id="test_project",
            instructions=default_instructions
        )
        
        result = await self.instructions_service.index(index_request)
        
        assert result is not None
        assert result.status == "finished"
        assert result.error is None
        
        # Test case 2: Index question-specific instructions
        question_instructions = [
            {
                "id": "question_1",
                "instruction": "For certification queries, include compliance status",
                "is_default": False,
                "questions": [
                    "Show certification status",
                    "List overdue certifications"
                ]
            }
        ]
        
        index_request = IndexRequest(
            event_id="test_index_2",
            project_id="test_project",
            instructions=question_instructions
        )
        
        result = await self.instructions_service.index(index_request)
        
        assert result is not None
        assert result.status == "finished"
        assert result.error is None
        
        # Test case 3: Delete instructions
        delete_request = InstructionsService.DeleteRequest(
            event_id="test_delete_1",
            instruction_ids=["default_1", "question_1"],
            project_id="test_project"
        )
        
        result = await self.instructions_service.delete(delete_request)
        
        assert result is not None
        assert result.status == "finished"
        assert result.error is None
        
        # Test case 4: Get instruction event
        event = self.instructions_service["test_index_1"]
        assert event is not None
        assert event.status == "finished"
        assert event.error is None
    
    @pytest.mark.asyncio
    async def test_question_recommendation_integration(self):
        """Test QuestionRecommendation service with actual providers"""
        # Test case 1: Generate recommendations for Cornerstone schema
        cornerstone_mdl = json.dumps(self.cornerstone_schema)
        request = QuestionRecommendation.Request(
            event_id="test_recommendation_1",
            mdl=cornerstone_mdl,
            previous_questions=[
                "Show me all employees who completed their training in the last month",
                "What is the average completion time for mandatory courses?"
            ],
            project_id="test_project",
            max_questions=3,
            max_categories=2,
            configuration=Configuration(language="English")
        )
        
        result = await self.question_recommendation.recommend(request)
        
        assert result is not None
        assert result.status == "finished"
        assert "questions" in result.response
        assert len(result.response["questions"]) > 0
        
        # Test case 2: Generate recommendations for SumTotal schema with regeneration
        sumtotal_mdl = json.dumps(self.sumtotal_schema)
        request = QuestionRecommendation.Request(
            event_id="test_recommendation_2",
            mdl=sumtotal_mdl,
            previous_questions=[
                "Show certification compliance by department",
                "List employees with overdue training requirements"
            ],
            project_id="test_project",
            max_questions=2,
            max_categories=2,
            regenerate=True,
            configuration=Configuration(language="English")
        )
        
        result = await self.question_recommendation.recommend(request)
        
        assert result is not None
        assert result.status == "finished"
        assert "questions" in result.response
        
        # Test case 3: Test error handling with invalid MDL
        invalid_request = QuestionRecommendation.Request(
            event_id="test_recommendation_3",
            mdl="invalid json",
            project_id="test_project",
            configuration=Configuration(language="English")
        )
        
        result = await self.question_recommendation.recommend(invalid_request)
        
        assert result is not None
        assert result.status == "failed"
        assert result.error.code == "MDL_PARSE_ERROR"
    
    @pytest.mark.asyncio
    async def test_semantics_description_integration(self):
        """Test SemanticsDescription service with actual providers"""
        # Test case 1: Generate descriptions for Cornerstone schema
        cornerstone_mdl = json.dumps(self.cornerstone_schema)
        request = SemanticsDescription.GenerateRequest(
            id="test_semantics_1",
            selected_models=["csod_training_records"],
            user_prompt="Describe the training records schema and its metrics",
            mdl=cornerstone_mdl,
            project_id="test_project",
            configuration=Configuration(language="English")
        )
        
        result = await self.semantics_description.generate(request)
        
        assert result is not None
        assert result.status == "finished"
        assert "response" in result.__dict__
        assert len(result.response) > 0
        
        # Test case 2: Generate descriptions for multiple SumTotal models
        sumtotal_mdl = json.dumps(self.sumtotal_schema)
        request = SemanticsDescription.GenerateRequest(
            id="test_semantics_2",
            selected_models=["employee_training_records"],
            user_prompt="Explain the training metrics and their relationships",
            mdl=sumtotal_mdl,
            project_id="test_project",
            configuration=Configuration(language="English")
        )
        
        result = await self.semantics_description.generate(request)
        
        assert result is not None
        assert result.status == "finished"
        assert "response" in result.__dict__
        assert len(result.response) > 0
        
        # Test case 3: Test error handling with invalid MDL
        invalid_request = SemanticsDescription.GenerateRequest(
            id="test_semantics_3",
            selected_models=["employee_training_records"],
            user_prompt="Describe the schema",
            mdl="invalid json",
            project_id="test_project",
            configuration=Configuration(language="English")
        )
        
        result = await self.semantics_description.generate(invalid_request)
        
        assert result is not None
        assert result.status == "failed"
        assert result.error.code == "MDL_PARSE_ERROR"
        
        # Test case 4: Test resource retrieval
        resource = self.semantics_description["test_semantics_1"]
        assert resource is not None
        assert resource.status == "finished" 