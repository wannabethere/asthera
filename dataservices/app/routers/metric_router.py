from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.metric_service import (
    create_metric,
    get_metric,
    update_metric,
    delete_metric,
)
from app.schemas.metric_schemas import MetricCreate, MetricUpdate, MetricRead

router = APIRouter()


@router.post("/metrics/", response_model=MetricRead, summary="Create a new metric.")
async def create(data: MetricCreate, db: Session = Depends(get_db)):
    """Create a new metric within a table."""
    return create_metric(db, data)


@router.get(
    "/metrics/{metric_id}",
    response_model=MetricRead,
    summary="Retrieve a metric by its ID.",
)
async def read(metric_id: str, db: Session = Depends(get_db)):
    """Retrieve a metric by its unique ID."""
    metric = get_metric(db, metric_id)
    if not metric:
        raise HTTPException(404, "Not found.")
    return metric


@router.patch(
    "/metrics/{metric_id}", response_model=MetricRead, summary="Update a metric."
)
async def update(metric_id: str, data: MetricUpdate, db: Session = Depends(get_db)):
    """Partially update a metric's details."""
    metric = update_metric(db, metric_id, data)
    if not metric:
        raise HTTPException(404, "Not found.")
    return metric


@router.delete("/metrics/{metric_id}", summary="Delete a metric.")
async def delete(metric_id: str, db: Session = Depends(get_db)):
    """Remove a metric from the database."""
    if not delete_metric(db, metric_id):
        raise HTTPException(404, "Not found.")
    return {"message": "Deleted"}
