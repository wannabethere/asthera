from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from typing import List, Optional
import traceback
from app.service.models import TimeColumnCreate, TimeColumnUpdate, TimeColumnResponse
from app.schemas.dbmodels import TimeColumns
from app.schemas.dbmodels import Table, SQLColumn
import asyncio

class TimeColumnService:
    
    async def get_by_id(self, db: AsyncSession, time_column_id: str):
        """Get time column by ID"""
        try:
            result = await db.execute(
                select(TimeColumns).where(TimeColumns.time_column_id == time_column_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            traceback.print_exc()
            raise e
    
    async def get_all(self, db: AsyncSession) -> List:
        """Get all time columns"""
        try:
            result = await db.execute(select(TimeColumns))
            return result.scalars().all()
        except Exception as e:
            traceback.print_exc()
            raise e
    
    async def create_time_column(self, db: AsyncSession, data, commit: bool = True):
        """Create new time column"""
        try:
            # Validate foreign keys exist
            table_result = await db.execute(select(Table).where(Table.table_id == data.table_id))
            if not table_result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail=f"Table {data.table_id} not found")
            
            column_result = await db.execute(select(SQLColumn).where(SQLColumn.column_id == data.column_id))
            column_result = column_result.scalar_one_or_none()
            if not column_result:
                raise HTTPException(status_code=400, detail=f"Column {data.column_id} not found")
            
            # Check if time_column_id already exists
            existing = await db.execute(
                select(TimeColumns).where(TimeColumns.column_id == data.column_id)
            )
            existing = existing.scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=409, detail="Time column ID already exists")
            
            # Create new record
            time_column = TimeColumns(
                table_id=data.table_id,
                column_id=data.column_id,
                time_column_name=column_result.name,
                time_column_type=data.time_column_type,
                time_column_format=data.time_column_format,
                time_column_description=data.time_column_description,
                granularity=data.granularity
            )
            db.add(time_column)
            
            # Only commit if requested (for batch operations, we handle commit separately)
            if commit:
                await db.commit()
                await db.refresh(time_column)
            
            return time_column
            
        except HTTPException:
            if commit:
                await db.rollback()
            raise
        except IntegrityError as e:
            if commit:
                await db.rollback()
            traceback.print_exc()
            raise HTTPException(status_code=409, detail="Database constraint violation")
        except Exception as e:
            if commit:
                await db.rollback()
            traceback.print_exc()
            raise e
    
    async def create_time_column_List(self, db: AsyncSession, data: List):
        """Create multiple time columns in a single transaction"""
        try:
            created_time_columns = []
            
            # Process each item sequentially within the same transaction
            for item in data:
                # Create without committing (commit=False)
                time_column = await self.create_time_column(db, item, commit=False)
                created_time_columns.append(time_column)
            
            # Commit all at once
            await db.commit()
            
            # Refresh all created objects
            for time_column in created_time_columns:
                await db.refresh(time_column)
            
            return created_time_columns
            
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to create time columns: {str(e)}")
    
    async def update(self, db: AsyncSession, time_column_id: str, data):
        """Update time column"""
        try:            
            # Get existing record
            result = await db.execute(
                select(TimeColumns).where(TimeColumns.time_column_id == time_column_id)
            )
            time_column = result.scalar_one_or_none()
            if not time_column:
                return None
            
            # Get update data excluding None values
            update_data = data.dict(exclude_unset=True)
            
            # Validate foreign keys if being updated
            if 'table_id' in update_data:
                table_result = await db.execute(select(Table).where(Table.table_id == update_data['table_id']))
                if not table_result.scalar_one_or_none():
                    raise HTTPException(status_code=400, detail=f"Table {update_data['table_id']} not found")
            
            if 'column_id' in update_data:
                column_result = await db.execute(select(SQLColumn).where(SQLColumn.column_id == update_data['column_id']))
                if not column_result.scalar_one_or_none():
                    raise HTTPException(status_code=400, detail=f"Column {update_data['column_id']} not found")
            
            # Update fields
            for field, value in update_data.items():
                setattr(time_column, field, value)
            
            await db.commit()
            await db.refresh(time_column)
            return time_column
            
        except HTTPException:
            await db.rollback()
            raise
        except IntegrityError as e:
            await db.rollback()
            traceback.print_exc()
            raise HTTPException(status_code=409, detail="Database constraint violation")
        except Exception as e:
            await db.rollback()
            traceback.print_exc()
            raise e
    
    async def delete(self, db: AsyncSession, time_column_id: str) -> bool:
        """Delete time column"""
        try:            
            result = await db.execute(
                select(TimeColumns).where(TimeColumns.time_column_id == time_column_id)
            )
            time_column = result.scalar_one_or_none()
            if not time_column:
                return False
            
            await db.delete(time_column)
            await db.commit()
            return True
            
        except Exception as e:
            await db.rollback()
            traceback.print_exc()
            raise e