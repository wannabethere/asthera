from fastapi import APIRouter, Depends, HTTPException
from app.core.dependencies import get_async_db_session
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from app.routers.project_workflow import get_token
from app.service.share_permissions import SharePermissions
from app.service.models import TimeColumnCreate, TimeColumnUpdate, TimeColumnResponse
from app.service.timecolumn_service import TimeColumnService
from app.core.dependencies import get_async_db_session
import traceback
from typing import List, Union
logger = logging.getLogger(__name__)


time_column_router = APIRouter()

def time_column_service():
    return TimeColumnService()


@time_column_router.get("/time-columns/{time_column_id}", response_model=TimeColumnResponse)
async def get_time_column(time_column_id: str, db: AsyncSession = Depends(get_async_db_session),token: str = Depends(get_token),time_column_service: TimeColumnService = Depends(time_column_service)):
    try:
        user= await SharePermissions()._validate_user(token)
        result = await time_column_service.get_by_id(db, time_column_id)
        if not result:
            raise HTTPException(status_code=404, detail="Time column not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@time_column_router.get("/time-columns", response_model=List[TimeColumnResponse])
async def get_all_time_columns(db: AsyncSession = Depends(get_async_db_session),token: str = Depends(get_token),time_column_service: TimeColumnService = Depends(time_column_service)):
    try:
        user= await SharePermissions()._validate_user(token)
        return await time_column_service.get_all(db)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@time_column_router.post("/time-columns", response_model=Union[TimeColumnResponse, List[TimeColumnResponse]])
async def create_time_column(data: Union[TimeColumnCreate, List[TimeColumnCreate]], db: AsyncSession = Depends(get_async_db_session),token: str = Depends(get_token),time_column_service: TimeColumnService = Depends(time_column_service)):
    try:
        user= await SharePermissions()._validate_user(token)
        if isinstance(data, list):
            return await time_column_service.create_time_column_List(db, data)
        else:
            return await time_column_service.create_time_column(db, data)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@time_column_router.patch("/time-columns/{time_column_id}", response_model=TimeColumnResponse)
async def update_time_column(time_column_id: str, data: TimeColumnUpdate, db: AsyncSession = Depends(get_async_db_session),token: str = Depends(get_token),time_column_service: TimeColumnService = Depends(time_column_service)):
    try:
        user= await SharePermissions()._validate_user(token)
        result = await time_column_service.update(db, time_column_id, data)
        if not result:
            raise HTTPException(status_code=404, detail="Time column not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@time_column_router.delete("/time-columns/{time_column_id}")
async def delete_time_column(time_column_id: str, db: AsyncSession = Depends(get_async_db_session),token: str = Depends(get_token),time_column_service: TimeColumnService = Depends(time_column_service)):
    try:
        user= await SharePermissions()._validate_user(token)
        success = await time_column_service.delete(db, time_column_id)
        if not success:
            raise HTTPException(status_code=404, detail="Time column not found")
        return {"message": "Time column deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

        
        