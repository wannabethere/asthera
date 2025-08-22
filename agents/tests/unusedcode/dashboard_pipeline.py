from typing import Any, Optional, Dict
from langchain_openai import ChatOpenAI
import asyncio
import json

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.provider import DocumentStoreProvider
from app.core.dependencies import get_llm, get_doc_store_provider

from app.agents.nodes.writers.dashboard_service import DashboardConditionalFormattingService


class ConditionalFormattingPipeline(AgentPipeline):
    """Pipeline for conditional formatting that integrates with existing architecture"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: DocumentStoreProvider,
        engine: Optional[Any] = None
    ):
        super().__init__(
            name="Conditional Formatting Pipeline",
            version="1.0",
            description="Pipeline for translating natural language to dashboard conditional formatting configurations",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        
        # Initialize service
        self.service = DashboardConditionalFormattingService(
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider
        )
        
        self._initialized = True
    
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run the conditional formatting pipeline"""
        query = kwargs.get("query", "")
        dashboard_context = kwargs.get("dashboard_context", {})
        project_id = kwargs.get("project_id", "default")
        additional_context = kwargs.get("additional_context", {})
        time_filters = kwargs.get("time_filters", {})
        
        return await self.service.process_conditional_formatting_request(
            query=query,
            dashboard_context=dashboard_context,
            project_id=project_id,
            additional_context=additional_context,
            time_filters=time_filters
        )





def create_conditional_formatting_pipeline(
    llm: Optional[ChatOpenAI] = None,
    retrieval_helper: Optional[RetrievalHelper] = None,
    document_store_provider: Optional[DocumentStoreProvider] = None,
    engine: Optional[Any] = None
) -> ConditionalFormattingPipeline:
    """Factory function to create conditional formatting pipeline"""
    
    if not llm:
        llm = get_llm()
    
    if not retrieval_helper:
        retrieval_helper = RetrievalHelper()
    
    if not document_store_provider:
        document_store_provider = get_doc_store_provider()
    
    return ConditionalFormattingPipeline(
        llm=llm,
        retrieval_helper=retrieval_helper,
        document_store_provider=document_store_provider,
        engine=engine
    )



# Example usage
async def example_usage():
    """Example of how to use the conditional formatting service"""
    
    # Initialize service
    service = create_conditional_formatting_service()
    
    # Dashboard context
    dashboard_context = {
        "charts": [
            {
                "chart_id": "sales_chart",
                "type": "bar",
                "columns": ["region", "sales_amount", "date"],
                "query": "Show sales by region"
            },
            {
                "chart_id": "performance_chart", 
                "type": "line",
                "columns": ["month", "performance_score", "target"],
                "query": "Show performance trends"
            }
        ],
        "available_columns": ["region", "sales_amount", "date", "month", "performance_score", "target", "status"],
        "data_types": {
            "sales_amount": "numeric",
            "performance_score": "numeric", 
            "date": "datetime",
            "month": "datetime",
            "region": "categorical",
            "status": "categorical"
        }
    }
    
    # Natural language query
    query = """
    I want to highlight all sales amounts greater than $10,000 in green, 
    and filter the dashboard to show only active status records from the last 30 days.
    Also, make the performance chart show data only for the current year.
    """
    
    # Additional context
    additional_context = {
        "user_preferences": {
            "highlight_color": "green",
            "default_period": "last_30_days"
        }
    }
    
    # Time filters
    time_filters = {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "period": "current_year"
    }
    
    # Process request
    result = await service.process_conditional_formatting_request(
        query=query,
        dashboard_context=dashboard_context,
        project_id="example_project",
        additional_context=additional_context,
        time_filters=time_filters
    )
    
    print("Result:", json.dumps(result, indent=2))
    
    # The result will contain:
    # - success: bool
    # - configuration: DashboardConfiguration object
    # - chart_configurations: Dict with SQL expansion and chart adjustment configs
    # - metadata: Processing metadata
    
    return result


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())
