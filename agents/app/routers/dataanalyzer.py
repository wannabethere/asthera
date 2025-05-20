import io
import uuid
import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
from fastapi import APIRouter, File, UploadFile, Query, Path, HTTPException

# Import the DataFrameAnalyzer from datasetanalyzer.py
from app.agents.graphs.dataframeanalyzer import DataFrameAnalyzer
# Import the DataFrameQAGenerator from dataanalyzer.py
from app.agents.graphs.dataframeanalyzer import DataFrameQAGenerator

# Define models
class ChatMessage:
    def __init__(self, role, content, metadata=None):
        self.role = role
        self.content = content
        self.metadata = metadata or {}
    
    def to_thread_message(self, message_id):
        return {
            "id": message_id,
            "role": self.role,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": datetime.datetime.now().isoformat()
        }

class DataFrameQueryRequest:
    def __init__(self, query, analysis_id=None, thread_id=None, kpi_context=None):
        self.query = query
        self.analysis_id = analysis_id
        self.thread_id = thread_id
        self.kpi_context = kpi_context or {}

class DataFrameQueryResponse:
    def __init__(self, thread_id, query, query_type, answer, kpis=None, code_examples=None, errors=None, metadata=None):
        self.thread_id = thread_id
        self.query = query
        self.query_type = query_type
        self.answer = answer
        self.kpis = kpis
        self.code_examples = code_examples
        self.errors = errors or []
        self.metadata = metadata or {}

# Create router
router = APIRouter()

# Create a store for analysis results
analysis_results_store = {}

# Create an instance of DataFrameQAGenerator
dataframe_qa_generator = DataFrameQAGenerator()

# Thread management functions
def get_thread(thread_id):
    # In a real app, this would fetch from a database
    return {"id": thread_id, "name": f"Thread {thread_id}"}

def create_thread(name):
    # In a real app, this would create in a database
    thread_id = uuid.uuid4().int % 100000
    return thread_id

def save_thread_messages(thread_id, messages):
    # In a real app, this would save to a database
    print(f"Saving {len(messages)} messages to thread {thread_id}")
    return True

@router.post("/api/dataframe/analyze", response_model=Dict[str, Any])
async def analyze_dataframe(
    file: UploadFile = File(...),
    description: Optional[str] = Query(None, description="Description of the dataset")
) -> Dict[str, Any]:
    """Analyze a dataframe and suggest functions using LangGraph."""
    # Read the uploaded file
    if file.filename.endswith('.csv'):
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
    elif file.filename.endswith(('.xlsx', '.xls')):
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a CSV or Excel file."
        )
    
    # Analyze the dataframe with LangGraph
    analyzer = DataFrameAnalyzer(df)
    analysis_result = analyzer.analyze_with_langgraph()
    
    # Convert to dict for response
    result_dict = analysis_result  # This is already a dict from the implementation
    
    # Add file information
    result_dict["filename"] = file.filename
    result_dict["description"] = description
    
    # Generate a unique ID for this analysis
    analysis_id = str(uuid.uuid4())
    
    # Store the analysis result
    analysis_results_store[analysis_id] = result_dict
    
    # Add the ID to the response
    result_dict["analysis_id"] = analysis_id
    
    return result_dict

@router.post("/api/dataframe/query", response_model=Dict[str, Any])
async def query_dataframe(query_request: DataFrameQueryRequest) -> Dict[str, Any]:
    """Query a dataframe for KPIs and insights."""
    # Check if the analysis ID exists
    if query_request.analysis_id and query_request.analysis_id not in analysis_results_store:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis result with ID {query_request.analysis_id} not found"
        )
    
    # Get or create thread
    thread_id = None
    
    if query_request.thread_id:
        try:
            thread_id = int(query_request.thread_id)
            # Check if thread exists
            thread = get_thread(thread_id)
            if not thread:
                raise HTTPException(
                    status_code=404,
                    detail=f"Thread with ID {thread_id} not found"
                )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid thread ID format"
            )
    else:
        # Create a new thread
        thread_name = f"Dataframe Query: {query_request.query[:30]}..."
        thread_id = create_thread(thread_name)
    
    # Create user message
    user_message = ChatMessage(
        role="user",
        content=query_request.query,
        metadata={"query_type": "dataframe_query"}
    )
    
    # Save user message to thread
    save_thread_messages(thread_id, [user_message.to_thread_message(str(uuid.uuid4()))])
    
    # Get the analysis result
    analysis_result = analysis_results_store.get(query_request.analysis_id)
    
    if not analysis_result:
        raise HTTPException(
            status_code=400,
            detail="No analysis result provided. Please upload and analyze a dataframe first."
        )
    
    # Process query with QA generator
    qa_result = dataframe_qa_generator.answer_question(
        query=query_request.query,
        analysis_result=analysis_result,
        kpi_context=query_request.kpi_context
    )
    
    # Create assistant message with the answer
    assistant_message = ChatMessage(
        role="assistant",
        content=qa_result["answer"],
        metadata={
            "query_type": qa_result["query_type"],
            "has_kpis": bool(qa_result.get("generated_kpis")),
            "has_code": bool(qa_result.get("code_examples"))
        }
    )
    
    # Save assistant message to thread
    save_thread_messages(thread_id, [assistant_message.to_thread_message(str(uuid.uuid4()))])
    
    # Create response
    response = {
        "thread_id": str(thread_id),
        "query": query_request.query,
        "query_type": qa_result["query_type"],
        "answer": qa_result["answer"],
        "kpis": qa_result.get("generated_kpis"),
        "code_examples": qa_result.get("code_examples", []),
        "errors": qa_result.get("errors", []),
        "metadata": {
            "analysis_id": query_request.analysis_id
        }
    }
    
    return response

# Additional endpoints for specific KPI types
@router.post("/api/dataframe/timeseries-kpis", response_model=Dict[str, Any])
async def get_timeseries_kpis(
    analysis_id: str = Query(...),
    thread_id: Optional[str] = Query(None),
    specific_metrics: Optional[List[str]] = Query(None)
):
    """Get time series KPI recommendations for a dataframe."""
    query = "Give me probable timeseries KPIs for this dataset"
    
    if specific_metrics:
        metrics_str = ", ".join(specific_metrics)
        query += f" focusing on these metrics: {metrics_str}"
    
    kpi_context = {"focused_metrics": specific_metrics} if specific_metrics else None
    
    request = DataFrameQueryRequest(
        query=query,
        analysis_id=analysis_id,
        thread_id=thread_id,
        kpi_context=kpi_context
    )
    
    return await query_dataframe(request)

@router.post("/api/dataframe/categorical-kpis", response_model=Dict[str, Any])
async def get_categorical_kpis(
    analysis_id: str = Query(...),
    thread_id: Optional[str] = Query(None),
    segmentation_columns: Optional[List[str]] = Query(None)
):
    """Get categorical/segmentation KPI recommendations."""
    query = "Give me probable categorical KPIs for segmentation analysis of this dataset"
    
    if segmentation_columns:
        columns_str = ", ".join(segmentation_columns)
        query += f" using these columns for segmentation: {columns_str}"
    
    kpi_context = {"segmentation_columns": segmentation_columns} if segmentation_columns else None
    
    request = DataFrameQueryRequest(
        query=query,
        analysis_id=analysis_id,
        thread_id=thread_id,
        kpi_context=kpi_context
    )
    
    return await query_dataframe(request)

@router.post("/api/dataframe/correlation-kpis", response_model=Dict[str, Any])
async def get_correlation_kpis(
    analysis_id: str = Query(...),
    thread_id: Optional[str] = Query(None),
    metrics_pairs: Optional[List[List[str]]] = Query(None)
):
    """Get correlation-based KPI recommendations."""
    query = "Give me probable correlation-based KPIs for this dataset"
    
    if metrics_pairs:
        pairs_str = ", ".join([f"{pair[0]} and {pair[1]}" for pair in metrics_pairs])
        query += f" focusing on these metric pairs: {pairs_str}"
    
    kpi_context = {"metrics_pairs": metrics_pairs} if metrics_pairs else None
    
    request = DataFrameQueryRequest(
        query=query,
        analysis_id=analysis_id,
        thread_id=thread_id,
        kpi_context=kpi_context
    )
    
    return await query_dataframe(request)

@router.get("/api/dataframe/analysis/{analysis_id}", response_model=Dict[str, Any])
async def get_dataframe_analysis(analysis_id: str = Path(...)):
    """Get a dataframe analysis result by ID."""
    if analysis_id not in analysis_results_store:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis result with ID {analysis_id} not found"
        )
    
    return analysis_results_store[analysis_id]