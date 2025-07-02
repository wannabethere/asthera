from sqlalchemy.orm import Session
from app.service.dbmodel import Metric
from app.schemas.metric_schemas import MetricCreate, MetricUpdate, MetricRead


from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

def create_metric(db: Session, data: MetricCreate) -> Metric:
    """Create a new Metric."""
    metric = Metric(**data.model_dump())
    db.add(metric)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if 'uq_metrics_table_name' in str(e.orig):
            raise HTTPException(status_code=409, detail="A metric with this name already exists for this table.")
        raise
    db.refresh(metric)
    return MetricRead.model_validate(metric)


def get_metric(db: Session, metric_id: str) -> Metric:
    """Retrieve a Metric by its ID."""
    return db.query(Metric).filter_by(metric_id=metric_id).first()


def update_metric(db: Session, metric_id: str, data: MetricUpdate) -> Metric:
    """Partially update a Metric's attributes."""
    metric = get_metric(db, metric_id)
    if not metric:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(metric, field, value)

    db.commit()
    db.refresh(metric)
    return metric


def delete_metric(db: Session, metric_id: str) -> bool:
    """Remove a Metric from the database."""
    metric = get_metric(db, metric_id)
    if metric:
        db.delete(metric)
        db.commit()
        return True
    return False
