from typing import Dict, Any
from app.services.servicebase import BaseService
from app.services.sql.ask import AskService
from app.services.sql.question_recommendation import QuestionRecommendation
from app.services.sql.chart import ChartService
from app.services.sql.chart_adjustment import ChartAdjustmentService
from app.services.sql.instructions import InstructionsService
from app.services.sql.sql_helper_services import SQLHelperService
from app.services.writers.dashboard_service import DashboardService
from app.agents.pipelines.pipeline_container import PipelineContainer

class SQLServiceContainer:
    """Container class for managing SQL-related services."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SQLServiceContainer, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # Dictionary to store service instances
        self._services: Dict[str, BaseService] = {}
        self._initialized = True
    
    def initialize_services(self, app_state) -> None:
        """Initialize all SQL services with dependencies from app state.
        
        Args:
            app_state: FastAPI app state containing dependencies
        """
        # Get dependencies from app state if available
        self.pipeline_container = PipelineContainer.initialize()
        session_manager = getattr(app_state, 'session_manager', None)
        doc_store_provider = getattr(app_state, 'doc_store_provider', None)
        
        
        # Initialize and register services
        ask_service = AskService()
        if session_manager:
            ask_service.session_manager = session_manager
        if doc_store_provider:
            ask_service.doc_store_provider = doc_store_provider
        self.register_service("ask_service", ask_service)
        
        question_recommendation = QuestionRecommendation()
        if session_manager:
            question_recommendation.session_manager = session_manager
        if doc_store_provider:
            question_recommendation.doc_store_provider = doc_store_provider
        self.register_service("question_recommendation", question_recommendation)

        # Initialize chart service
        chart_service = ChartService()
        if session_manager:
            chart_service.session_manager = session_manager
        if doc_store_provider:
            chart_service.doc_store_provider = doc_store_provider
        self.register_service("chart_service", chart_service)

        # Initialize chart adjustment service
        chart_adjustment_service = ChartAdjustmentService()
        if session_manager:
            chart_adjustment_service.session_manager = session_manager
        if doc_store_provider:
            chart_adjustment_service.doc_store_provider = doc_store_provider
        self.register_service("chart_adjustment_service", chart_adjustment_service)

        # Initialize instructions service
        instructions_service = InstructionsService()
        if session_manager:
            instructions_service.session_manager = session_manager
        if doc_store_provider:
            instructions_service.doc_store_provider = doc_store_provider
        self.register_service("instructions_service", instructions_service)

        # Initialize SQL helper service
        sql_helper_service = SQLHelperService(pipeline_container=self.pipeline_container)
        if session_manager:
            sql_helper_service.session_manager = session_manager
        if doc_store_provider:
            sql_helper_service.doc_store_provider = doc_store_provider
        self.register_service("sql_helper_service", sql_helper_service)
        
        # Initialize dashboard service
        dashboard_service = DashboardService()
        if session_manager:
            dashboard_service.session_manager = session_manager
        if doc_store_provider:
            dashboard_service.doc_store_provider = doc_store_provider
        self.register_service("dashboard_service", dashboard_service)
    
    def get_service(self, service_name: str) -> BaseService:
        """Get a service instance by name.
        
        Args:
            service_name: Name of the service to retrieve
            
        Returns:
            Service instance
        """
        if service_name not in self._services:
            raise ValueError(f"Service {service_name} not found")
        return self._services[service_name]
    
    def register_service(self, service_name: str, service: BaseService) -> None:
        """Register a new service instance.
        
        Args:
            service_name: Name to register the service under
            service: Service instance to register
        """
        self._services[service_name] = service
    
    def get_all_services(self) -> Dict[str, BaseService]:
        """Get all registered services.
        
        Returns:
            Dictionary of all registered services
        """
        return self._services.copy()
    
    @classmethod
    def get_instance(cls) -> 'SQLServiceContainer':
        """Get the singleton instance of the service container.
        
        Returns:
            SQLServiceContainer instance
        """
        return cls() 