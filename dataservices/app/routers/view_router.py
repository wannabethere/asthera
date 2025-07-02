from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.view_service import create_view, get_view, update_view, delete_view
from app.schemas.view_schemas import ViewCreate, ViewUpdate, ViewRead

router = APIRouter()


@router.post("/views/", response_model=ViewRead, summary="Create a new view.")
async def create(data: ViewCreate, db: Session = Depends(get_db)):
    """Create a new view within a table."""
    return create_view(db, data)


@router.get(
    "/views/{view_id}", response_model=ViewRead, summary="Retrieve a view by its ID."
)
async def read(view_id: str, db: Session = Depends(get_db)):
    """Retrieve a view by its unique ID."""
    view = get_view(db, view_id)
    if not view:
        raise HTTPException(404, "Not found.")
    return view


@router.patch("/views/{view_id}", response_model=ViewRead, summary="Update a view.")
async def update(view_id: str, data: ViewUpdate, db: Session = Depends(get_db)):
    """Partially update a view's details."""
    view = update_view(db, view_id, data)
    if not view:
        raise HTTPException(404, "Not found.")
    return view


@router.delete("/views/{view_id}", summary="Delete a view.")
async def delete(view_id: str, db: Session = Depends(get_db)):
    """Remove a view from the database."""
    if not delete_view(db, view_id):
        raise HTTPException(404, "Not found.")
    return {"message": "Deleted"}
