from typing import Dict, Any, TYPE_CHECKING
import logging
from app.services.servicebase import BaseService
from app.services.sql.ask import AskService
from app.services.sql.question_recommendation import QuestionRecommendation
from app.services.sql.chart import ChartService
from app.services.sql.chart_adjustment import ChartAdjustmentService
from app.services.sql.instructions import InstructionsService
from app.services.sql.sql_helper_services import SQLHelperService
from app.services.writers.dashboard_service import DashboardService
from app.services.writers.alert_service import AlertService, AlertCompatibilityService
from app.services.docs.document_persistence_service import DocumentPersistenceService, create_document_persistence_service
from app.agents.pipelines.pipeline_container import PipelineContainer
from app.indexing.project_reader import ProjectReader
from app.indexing.alert_knowledge_helper import initialize_alert_knowledge_helper
from app.storage.sessionmanager import SessionManager

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.writers.report_service import ReportService
    from app.core.engine import Engine

class SQLServiceContainer:
    """Container class for managing SQL-related and writer services."""
    
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
        """Initialize all SQL and writer services with dependencies from app state.
        
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
        
        # Initialize dashboard service (pure API layer - no database dependencies needed)
        dashboard_service = self.create_dashboard_service()
        self.register_service("dashboard_service", dashboard_service)
        
        # Initialize report service (pure API layer - no database dependencies needed)
        from app.core.engine_provider import EngineProvider
        engine = EngineProvider.get_engine()
        report_service = self.create_report_service(engine=engine)
        self.register_service("report_service", report_service)
        
        # Initialize ProjectReader for alert knowledge base (optional)
        try:
            project_reader = self.create_project_reader()
            self.register_service("project_reader", project_reader)
            
            # Initialize alert knowledge helper with project reader
            initialize_alert_knowledge_helper(project_reader)
        except Exception as e:
            logger.warning(f"Failed to initialize ProjectReader and alert knowledge helper: {e}")
            # Continue without these services
        
        # Initialize document persistence service
        try:
            document_persistence_service = self.create_document_persistence_service(session_manager)
            if session_manager:
                document_persistence_service.session_manager = session_manager
            if doc_store_provider:
                document_persistence_service.doc_store_provider = doc_store_provider
            self.register_service("document_persistence_service", document_persistence_service)
            
            # Store in app state for dependency injection
            app_state.document_persistence_service = document_persistence_service
            
            logger.info("Document persistence service initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize document persistence service: {e}")
            # Continue without document persistence service
            app_state.document_persistence_service = None

        # Initialize alert service (optional)
        try:
            alert_service = self.create_alert_service()
            if session_manager:
                alert_service.session_manager = session_manager
            if doc_store_provider:
                alert_service.doc_store_provider = doc_store_provider
            self.register_service("alert_service", alert_service)
            
            # Initialize alert compatibility service
            alert_compatibility_service = self.create_alert_compatibility_service(alert_service)
            if session_manager:
                alert_compatibility_service.session_manager = session_manager
            if doc_store_provider:
                alert_compatibility_service.doc_store_provider = doc_store_provider
            self.register_service("alert_compatibility_service", alert_compatibility_service)
            
            # Store individual alert services in app state for dependency injection
            app_state.alert_service = alert_service
            app_state.alert_compatibility_service = alert_compatibility_service
            
            logger.info("Alert services initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize alert services: {e}")
            # Continue without alert services
            app_state.alert_service = None
            app_state.alert_compatibility_service = None
    
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
    
    def create_dashboard_service(self) -> DashboardService:
        """Factory method to create a dashboard service instance.
        
        Returns:
            DashboardService instance with all agent pipelines initialized
        """
        return DashboardService()
    
    def create_report_service(self, engine=None):
        """Factory method to create a report service instance.
        
        Args:
            engine: Database engine instance (optional)
        
        Returns:
            ReportService instance with all agent pipelines initialized
        """
        # Lazy import to avoid circular dependencies
        from app.services.writers.report_service import ReportService
        return ReportService(engine=engine)
    
    def create_alert_service(self):
        """Factory method to create an alert service instance.
        
        Returns:
            AlertService instance with all agent pipelines initialized
        """
        # Lazy import to avoid circular dependencies
        from app.services.writers.alert_service import AlertService
        return AlertService(pipeline_container=self.pipeline_container)
    
    def create_alert_compatibility_service(self, alert_service=None):
        """Factory method to create an alert compatibility service instance.
        
        Args:
            alert_service: AlertService instance (optional, will create if not provided)
        
        Returns:
            AlertCompatibilityService instance with all agent pipelines initialized
        """
        # Lazy import to avoid circular dependencies
        from app.services.writers.alert_service import AlertCompatibilityService
        
        if alert_service is None:
            alert_service = self.create_alert_service()
        
        return AlertCompatibilityService(alert_service)
    
    def create_document_persistence_service(self, session_manager: SessionManager):
        """Factory method to create a document persistence service instance.
        
        Args:
            session_manager: SessionManager instance for database operations
        
        Returns:
            DocumentPersistenceService instance
        """
        return create_document_persistence_service(session_manager)

    def create_project_reader(self):
        """Create a ProjectReader instance for alert knowledge base.
        
        Returns:
            ProjectReader instance
        """
        from app.settings import get_settings
        import chromadb
        
        settings = get_settings()
        persistent_client = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
        
        return ProjectReader(
            base_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/sql_meta",
            persistent_client=persistent_client
        )
    
    def get_dashboard_service(self) -> DashboardService:
        """Get the dashboard service instance.
        
        Returns:
            DashboardService instance
        """
        return self.get_service("dashboard_service")
    
    def get_report_service(self):
        """Get the report service instance.
        
        Returns:
            ReportService instance
        """
        return self.get_service("report_service")
    
    def get_alert_service(self):
        """Get the alert service instance.
        
        Returns:
            AlertService instance
        """
        return self.get_service("alert_service")
    
    def get_alert_compatibility_service(self):
        """Get the alert compatibility service instance.
        
        Returns:
            AlertCompatibilityService instance
        """
        return self.get_service("alert_compatibility_service")
    
    def get_document_persistence_service(self):
        """Get the document persistence service instance.
        
        Returns:
            DocumentPersistenceService instance
        """
        return self.get_service("document_persistence_service")
    
    @classmethod
    def get_instance(cls) -> 'SQLServiceContainer':
        """Get the singleton instance of the service container.
        
        Returns:
            SQLServiceContainer instance
        """
        return cls() 