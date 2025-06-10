from typing import Dict, List, Literal, Optional, Any, Union
from pydantic import AliasChoices, BaseModel, Field
import uuid

from app.agents.nodes.sql.utils.sql_prompts import Configuration
from app.agents.nodes.sql.utils.sql_prompts import AskHistory
from datetime import datetime

class QualityScoring(BaseModel):
    """Base model for quality scoring with common fields and functionality"""
    final_score: float = Field(default=0.0, description="Final quality score between 0 and 1")
    quality_level: str = Field(default="unknown", description="Quality level (excellent, good, fair, poor)")
    improvement_recommendations: Optional[List[str]] = Field(default_factory=None, description="List of recommendations for improvement")
    processing_time_seconds: Optional[float] = Field(default=None, description="Time taken to process the request")
    explanation_quality: Optional[str] = Field(default=None, description="Quality of the explanation provided")
    detected_operation_type: Optional[str] = Field(default=None, description="Type of operation detected")
    attempt_number: int = Field(default=1, description="Number of attempts made")
    reasoning_components: Optional[Dict[str, float]] = Field(default_factory=None, description="Scores for different reasoning components")
    sql_components: Optional[Dict[str, float]] = Field(default_factory=None, description="Scores for different SQL components")
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class AskRequest(BaseModel):
    _query_id: str | None = None
    query: str
    project_id: Optional[str] = None
    mdl_hash: Optional[str] = None
    thread_id: Optional[str] = None
    histories: Optional[list[AskHistory]] = Field(default_factory=list)
    configurations: Optional[Configuration] = Configuration()
    enable_scoring: Optional[bool] = True
    previous_questions: Optional[List[str]] = Field(default_factory=list)
    
    @property
    def query_id(self) -> str:
        return self._query_id or str(uuid.uuid4())

    @query_id.setter
    def query_id(self, query_id: str):
        self._query_id = query_id


class AskResponse(BaseModel):
    query_id: str


class StopAskRequest(BaseModel):
    _query_id: str | None = None
    status: Literal["stopped"]

    @property
    def query_id(self) -> str:
        return self._query_id

    @query_id.setter
    def query_id(self, query_id: str):
        self._query_id = query_id


class StopAskResponse(BaseModel):
    query_id: str


class AskResult(BaseModel):
    sql: str
    type: Literal["llm", "view"] = "llm"
    viewId: Optional[str] = None


class AskError(BaseModel):
    code: Literal["NO_RELEVANT_DATA", "NO_RELEVANT_SQL", "OTHERS"]
    message: str


class AskResultRequest(BaseModel):
    query_id: str


class QualityScoring(BaseModel):
    final_score: float = 0.0
    quality_level: str = "unknown"
    improvement_recommendations: List[str] = Field(default_factory=list)
    processing_time_seconds: Optional[float] = None

class GenerateRequest(BaseModel):
        id: str
        selected_models: list[str]
        user_prompt: str
        mdl: str
        configuration: Optional[Configuration] = Configuration()
        project_id: Optional[str] = None  # this is for tracing purpose

class _AskResultResponse(BaseModel):
    status: Literal[
        "understanding",
        "searching",
        "planning",
        "generating",
        "correcting",
        "finished",
        "failed",
        "stopped",
        "summarizing",
        "reasoning",
        "executing_sql",
        "generating_answer",
    ]
    rephrased_question: Optional[str] = None
    intent_reasoning: Optional[str] = None
    sql_generation_reasoning: Optional[str] = None
    type: Optional[Literal["GENERAL", "TEXT_TO_SQL"]] = None
    retrieved_tables: Optional[List[str]] = None
    response: Optional[List[AskResult]] = None
    invalid_sql: Optional[str] = None
    error: Optional[AskError] = None
    trace_id: Optional[str] = None
    is_followup: Optional[bool] = False
    general_type: Optional[
        Literal["MISLEADING_QUERY", "DATA_ASSISTANCE", "USER_GUIDE"]
    ] = None
    quality_scoring: Optional[Union[QualityScoring, Dict[str, Any], float]] = None


class AskResultResponse(_AskResultResponse):
    is_followup: Optional[bool] = Field(False, exclude=True)
    general_type: Optional[
        Literal["MISLEADING_QUERY", "DATA_ASSISTANCE", "USER_GUIDE"]
    ] = Field(None, exclude=True)


class AskFeedbackRequest(BaseModel):
    _query_id: str | None = None
    tables: List[str]
    sql_generation_reasoning: str
    sql: str
    project_id: Optional[str] = None
    configurations: Optional[Configuration] = Configuration()
    enable_scoring: Optional[bool] = True

    @property
    def query_id(self) -> str:
        return self._query_id

    @query_id.setter
    def query_id(self, query_id: str):
        self._query_id = query_id


class AskFeedbackResponse(BaseModel):
    query_id: str


class StopAskFeedbackRequest(BaseModel):
    _query_id: str | None = None
    status: Literal["stopped"]

    @property
    def query_id(self) -> str:
        return self._query_id

    @query_id.setter
    def query_id(self, query_id: str):
        self._query_id = query_id


class StopAskFeedbackResponse(BaseModel):
    query_id: str


class AskFeedbackResultRequest(BaseModel):
    query_id: str


class AskFeedbackResultResponse(BaseModel):
    status: Literal[
        "searching",
        "generating",
        "correcting",
        "finished",
        "failed",
        "stopped",
    ]
    error: Optional[AskError] = None
    response: Optional[List[AskResult]] = None
    trace_id: Optional[str] = None
    quality_scoring: Optional[QualityScoring] = None 


class ChartAdjustmentOption(BaseModel):
    chart_type: Literal[
        "bar", "grouped_bar", "line", "pie", "stacked_bar", "area", "multi_line"
    ]
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    x_offset: Optional[str] = None
    color: Optional[str] = None
    theta: Optional[str] = None


class ChartAdjustmentRequest(BaseModel):
    _query_id: str | None = None
    query: str
    sql: str
    adjustment_option: ChartAdjustmentOption
    chart_schema: dict
    project_id: Optional[str] = None
    thread_id: Optional[str] = None
    configurations: Optional[Configuration] = Configuration()

    @property
    def query_id(self) -> str:
        return self._query_id

    @query_id.setter
    def query_id(self, query_id: str):
        self._query_id = query_id


class ChartAdjustmentResponse(BaseModel):
    query_id: str


# PATCH /v1/chart-adjustments/{query_id}
class StopChartAdjustmentRequest(BaseModel):
    _query_id: str | None = None
    status: Literal["stopped"]

    @property
    def query_id(self) -> str:
        return self._query_id

    @query_id.setter
    def query_id(self, query_id: str):
        self._query_id = query_id


class StopChartAdjustmentResponse(BaseModel):
    query_id: str


# GET /v1/chart-adjustments/{query_id}/result
class ChartAdjustmentError(BaseModel):
    code: Literal["NO_CHART", "OTHERS"]
    message: str


class ChartAdjustmentResultRequest(BaseModel):
    query_id: str


class ChartAdjustmentResult(BaseModel):
    reasoning: str
    chart_type: Literal[
        "line", "bar", "pie", "grouped_bar", "stacked_bar", "area", "multi_line", ""
    ]  # empty string for no chart
    chart_schema: dict


class ChartAdjustmentResultResponse(BaseModel):
    status: Literal[
        "understanding", "fetching", "generating", "finished", "failed", "stopped"
    ]
    response: Optional[ChartAdjustmentResult] = None
    error: Optional[ChartAdjustmentError] = None
    trace_id: Optional[str] = None

class ChartRequest(BaseModel):
    _query_id: str | None = None
    query: str
    sql: str
    project_id: Optional[str] = None
    thread_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    remove_data_from_chart_schema: Optional[bool] = True
    configurations: Optional[Configuration] = Configuration()

    @property
    def query_id(self) -> str:
        return self._query_id

    @query_id.setter
    def query_id(self, query_id: str):
        self._query_id = query_id


class ChartResponse(BaseModel):
    query_id: str


# PATCH /v1/charts/{query_id}
class StopChartRequest(BaseModel):
    _query_id: str | None = None
    status: Literal["stopped"]

    @property
    def query_id(self) -> str:
        return self._query_id

    @query_id.setter
    def query_id(self, query_id: str):
        self._query_id = query_id


class StopChartResponse(BaseModel):
    query_id: str


# GET /v1/charts/{query_id}/result
class ChartError(BaseModel):
    code: Literal["NO_CHART", "OTHERS"]
    message: str


class ChartResultRequest(BaseModel):
    query_id: str


class ChartResult(BaseModel):
    reasoning: str
    chart_type: Literal[
        "line", "bar", "pie", "grouped_bar", "stacked_bar", "area", "multi_line", ""
    ]  # empty string for no chart
    chart_schema: dict


class ChartResultResponse(BaseModel):
    status: Literal["fetching", "generating", "finished", "failed", "stopped"]
    response: Optional[ChartResult] = None
    error: Optional[ChartError] = None
    trace_id: Optional[str] = None

class Instruction(BaseModel):
        id: str
        instruction: str
        questions: List[str]
        # This is used to identify the default instruction needed to be retrieved for the project
        is_default: bool = False

class Error(BaseModel):
    code: Literal["OTHERS", "MDL_PARSE_ERROR", "RESOURCE_NOT_FOUND"]
    message: str

class Event(BaseModel):
    event_id: str
    status: Literal["indexing", "deleting", "finished", "failed"] = "indexing"
    error: Optional[Error] = None
    response: Optional[dict] = {"questions": {}}
    trace_id: Optional[str] = None

class IndexRequest(BaseModel):
    event_id: str
    instructions: List["Instruction"]
    project_id: Optional[str] = None


class Input(BaseModel):
    id: str
    mdl: str
    project_id: Optional[str] = None  # this is for tracing purpose
    configuration: Optional[Configuration] = Configuration()


class Resource(BaseModel):
    id: str
    status: Literal["generating", "finished", "failed"] = "generating"
    response: Optional[dict] = None
    error: Optional[Error] = None
    trace_id: Optional[str] = None

# POST /v1/semantics-preparations
class SemanticsPreparationRequest(BaseModel):
    mdl: str
    # don't recommend to use id as a field name, but it's used in the API spec
    # so we need to support as a choice, and will remove it in the future
    mdl_hash: str = Field(validation_alias=AliasChoices("mdl_hash", "id"))
    project_id: Optional[str] = None


class SemanticsPreparationResponse(BaseModel):
    # don't recommend to use id as a field name, but it's used in the API spec
    # so we need to support as a choice, and will remove it in the future
    mdl_hash: str = Field(serialization_alias="id")


# GET /v1/semantics-preparations/{mdl_hash}/status
class SemanticsPreparationStatusRequest(BaseModel):
    # don't recommend to use id as a field name, but it's used in the API spec
    # so we need to support as a choice, and will remove it in the future
    mdl_hash: str = Field(validation_alias=AliasChoices("mdl_hash", "id"))


class SemanticsPreparationStatusResponse(BaseModel):
    class SemanticsPreparationError(BaseModel):
        code: Literal["OTHERS"]
        message: str

    status: Literal["indexing", "finished", "failed"]
    error: Optional[SemanticsPreparationError] = None

class SQLBreakdown(BaseModel):
    sql: str
    summary: str
    cte_name: str


# POST /v1/ask-details
class AskDetailsRequest(BaseModel):
    _query_id: Optional[str] | None = None
    query: str
    sql: str
    mdl_hash: Optional[str] = None
    thread_id: Optional[str] = None
    project_id: Optional[str] = None
    configurations: Configuration = Configuration()
    # Added field for enhanced SQL pipeline
    enable_scoring: Optional[bool] = True

    @property
    def query_id(self) -> str:
        return self._query_id

    @query_id.setter
    def query_id(self, query_id: str):
        self._query_id = query_id


class AskDetailsResponse(BaseModel):
    query_id: str


# GET /v1/ask-details/{query_id}/result
class AskDetailsResultRequest(BaseModel):
    query_id: str


# Added model for quality scoring
class QualityScoring(BaseModel):
    final_score: float = 0.0
    quality_level: str = "unknown"
    improvement_recommendations: List[str] = []
    processing_time_seconds: Optional[float] = None
    explanation_quality: Optional[str] = None


class AskDetailsResultResponse(BaseModel):
    class AskDetailsResponseDetails(BaseModel):
        description: str
        steps: List[SQLBreakdown]

    class AskDetailsError(BaseModel):
        code: Literal["NO_RELEVANT_SQL", "OTHERS"]
        message: str

    status: Literal["understanding", "searching", "generating", "finished", "failed"]
    response: Optional[AskDetailsResponseDetails] = None
    error: Optional[AskDetailsError] = None
    trace_id: Optional[str] = None
    # Added field for enhanced SQL pipeline
    quality_scoring: Optional[QualityScoring] = None