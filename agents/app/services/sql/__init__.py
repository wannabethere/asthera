from datetime import datetime
from typing import Optional

import orjson
import pytz
from pydantic import BaseModel

class SSEEvent(BaseModel):
    class SSEEventMessage(BaseModel):
        message: str

        def to_dict(self):
            return {"message": self.message}

    data: SSEEventMessage

    def serialize(self):
        return f"data: {orjson.dumps(self.data.to_dict()).decode()}\n\n"


# Put the services imports here to avoid circular imports and make them accessible directly to the rest of packages
from .ask import AskService 
from .ask_details import AskDetailsService  
from .chart import ChartService  
from .chart_adjustment import ChartAdjustmentService 
from .question_recommendation import QuestionRecommendation  
from .relationship_recommendation import RelationshipRecommendation
from .semantics_description import SemanticsDescription  
from .semantics_preparation import SemanticsPreparationService
from .instructions import InstructionsService 


__all__ = [
    "AskService",
    "AskDetailsService",
    "ChartService",
    "ChartAdjustmentService",
    "QuestionRecommendation",
    "RelationshipRecommendation",
    "SemanticsDescription",
    "SemanticsPreparationService",
    "InstructionsService",
]
