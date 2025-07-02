# Pydantic schema for metric
# /app/schemas/metric_schemas.py

from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class MetricBase(BaseModel):
    table_id: UUID
    name: str
    metric_sql: str
    description: Optional[str] = None
    display_name: Optional[str] = None


class MetricCreate(MetricBase):
    pass


class MetricUpdate(BaseModel):
    metric_sql: Optional[str] = None
    description: Optional[str] = None


class MetricRead(MetricBase):
    metric_id: UUID

    class Config:
        from_attributes = True
