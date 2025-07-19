import os
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import httpx
from datetime import datetime
import json
import logging
from . import models
from .apischemas import ConnectionCreate, ConnectionResponse, ConnectionType, DataSourceResponse, BaseSettings
from app.utils.postgres_manager import postgres_manager
from . import airbyte_sync_service
from .airbyte_sync_service import SyncConnectionRequest, CheckConnectionRequest, CheckConnectionResponse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/unstructured",
    tags=["connections"]
)

# Database dependency
def get_db():
    try:
        yield postgres_manager.session
    finally:
        postgres_manager.close()

@router.get("/connections/", response_model=List[ConnectionResponse])
async def list_connections(db: Session = Depends(get_db)):
    """List all connections"""
    try:
        connections = db.query(models.connections).all()
        return [
            ConnectionResponse(
                connection_id=conn.id,
                name=conn.name,
                type=ConnectionType(conn.type),
                description=conn.description,
                settings=conn.settings,
                source_id=conn.source_id,
                user_id=conn.user_id,
                role=conn.role,
                version=conn.version,
                created_at=conn.created_at,
                updated_at=conn.updated_at
            ) for conn in connections
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/connections/", response_model=ConnectionResponse, status_code=201)
async def create_connection(connection: ConnectionCreate, db: Session = Depends(get_db)):
    """Create a new connection with optional Airbyte integration"""
    try:
        logger.info(f"Creating connection of type: {connection.type}")
        logger.info(f"Connection details: {json.dumps(connection.dict(), indent=2)}")
        
        # First, create the source in Airbyte if it's a supported connector type
        source_id = None
        settings = connection.settings
        if isinstance(settings, BaseSettings):
            settings_dict = settings.dict()
        else:
            settings_dict = settings if isinstance(settings, dict) else dict(settings)
        
        # service_account_info is a stringified JSON for Google Drive
        if connection.type == ConnectionType.GOOGLE_DRIVE:
            credentials = settings_dict.get("credentials", {})
            sa_info = credentials.get("service_account_info")

            if isinstance(sa_info, dict):
                try:
                    credentials["service_account_info"] = json.dumps(sa_info)
                    settings_dict["credentials"] = credentials
                    logger.info("Converted service_account_info dict to JSON string.")
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid service_account_info dict: {str(e)}"
                    )
            elif isinstance(sa_info, str):
                try:
                    json.loads(sa_info)  # Validate stringified JSON
                    logger.info("Validated stringified service_account_info is valid JSON.")
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"service_account_info string is not valid JSON: {str(e)}"
                    )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="service_account_info must be either a dict or a valid JSON string."
                )
            
        if connection.type in [ConnectionType.S3, ConnectionType.GONG, ConnectionType.GOOGLE_DRIVE, ConnectionType.SALESFORCE]:
            logger.info(f"Creating source in Airbyte for connector type: {connection.type}")
            
            # Create sync request
            sync_request = SyncConnectionRequest(
                connector_name=connection.name,
                connector_type=connection.type,
                description=connection.description,
                config=settings_dict
            )
            
            # Call Airbyte sync service
            try:
                airbyte_response = await airbyte_sync_service.create_sync_connection(sync_request)
                source_id = airbyte_response.source_id
                logger.info(f"Successfully created Airbyte source with ID: {source_id}")
                
                # If successful, add source_id to settings
                settings_dict["source_id"] = source_id
                
            except Exception as e:
                logger.error(f"Failed to create Airbyte source: {str(e)}")
                # Continue with connection creation even if Airbyte fails
                # This allows the user to manually configure Airbyte later
        
        # Create connection record
        logger.info("Creating connection record in database")
        conn = models.connections.insert().values(
            name=connection.name,
            type=connection.type,
            description=connection.description,
            settings=settings_dict,
            source_id=source_id,
            user_id=connection.user_id,
            role=connection.role,
            version=connection.version
        ).returning(models.connections)
        
        result = db.execute(conn)
        db.commit()
        new_conn = result.first()
        
        if not new_conn:
            error_msg = "Failed to create connection"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
            
        logger.info(f"Successfully created connection with ID: {new_conn.id}")
        return ConnectionResponse(
            connection_id=new_conn.id,
            name=new_conn.name,
            type=ConnectionType(new_conn.type),
            description=new_conn.description,
            settings=new_conn.settings,
            source_id=new_conn.source_id,
            user_id=new_conn.user_id,
            role=new_conn.role,
            version=new_conn.version,
            created_at=new_conn.created_at,
            updated_at=new_conn.updated_at
        )
    except Exception as e:
        error_msg = f"Error in create_connection: {str(e)}"
        logger.error(error_msg)
        db.rollback()
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/connections/{connection_id}", response_model=ConnectionResponse)
async def get_connection(connection_id: str, db: Session = Depends(get_db)):
    """Get a specific connection"""
    try:
        conn = db.query(models.connections).filter(models.connections.c.id == connection_id).first()
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        return ConnectionResponse(
            connection_id=conn.id,
            name=conn.name,
            type=ConnectionType(conn.type),
            description=conn.description,
            settings=conn.settings,
            source_id=conn.source_id,
            user_id=conn.user_id,
            role=conn.role,
            version=conn.version,
            created_at=conn.created_at,
            updated_at=conn.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/connections/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: str,
    connection: ConnectionCreate,
    db: Session = Depends(get_db)
):
    """Update an existing connection"""
    try:
        # Check if connection exists
        existing = db.query(models.connections).filter(models.connections.c.id == connection_id).first()
        if not existing:
            raise HTTPException(status_code=404, detail="Connection not found")

        # Convert settings to dict if needed
        settings = connection.settings
        if isinstance(settings, BaseSettings):
            settings_dict = settings.dict()
        else:
            settings_dict = settings if isinstance(settings, dict) else dict(settings)

        # Update connection
        update_stmt = models.connections.update().where(
            models.connections.c.id == connection_id
        ).values(
            name=connection.name,
            type=connection.type,
            description=connection.description,
            settings=settings_dict,
            user_id=connection.user_id,
            role=connection.role,
            version=connection.version,
            updated_at=datetime.utcnow()
        ).returning(models.connections)
        
        result = db.execute(update_stmt)
        db.commit()
        updated_conn = result.first()
        
        if not updated_conn:
            raise HTTPException(status_code=500, detail="Failed to update connection")
            
        return ConnectionResponse(
            connection_id=updated_conn.id,
            name=updated_conn.name,
            type=ConnectionType(updated_conn.type),
            description=updated_conn.description,
            settings=updated_conn.settings,
            source_id=updated_conn.source_id,
            user_id=updated_conn.user_id,
            role=updated_conn.role,
            version=updated_conn.version,
            created_at=updated_conn.created_at,
            updated_at=updated_conn.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/connections/{connection_id}")
async def delete_connection(connection_id: str, db: Session = Depends(get_db)):
    """Delete a connection"""
    try:
        # Check if connection exists
        conn = db.query(models.connections).filter(models.connections.c.id == connection_id).first()
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        # Check if this connection has an Airbyte source_id
        if conn.source_id:
            source_id = conn.source_id
            logger.info(f"Deleting Airbyte source with ID: {source_id}")
            try:
                # Call Airbyte delete function
                await airbyte_sync_service.delete_source(source_id)
                logger.info(f"Successfully deleted Airbyte source with ID: {source_id}")
            except Exception as e:
                logger.error(f"Error deleting Airbyte source {source_id}: {str(e)}")
                # Continue with connection deletion even if Airbyte deletion fails

        # Delete the connection from database
        delete_stmt = models.connections.delete().where(models.connections.c.id == connection_id)
        db.execute(delete_stmt)
        db.commit()
        
        return {"message": f"Connection {connection_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting connection {connection_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/data-sources/", response_model=List[DataSourceResponse])
async def list_data_sources(db: Session = Depends(get_db)):
    """List all data sources"""
    try:
        sources = db.query(models.data_sources).all()
        return [
            DataSourceResponse(
                connector_name=source.connector_name,
                connector_type=source.connector_type,
                description=source.description,
                config=source.config
            ) for source in sources
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/connections/{connection_id}/check", response_model=CheckConnectionResponse)
async def check_connection_status(connection_id: str, db: Session = Depends(get_db)):
    """Check the status of a connection in Airbyte"""
    try:
        # Check if connection exists
        conn = db.query(models.connections).filter(models.connections.c.id == connection_id).first()
        if not conn:
            logger.error(f"Connection {connection_id} not found in database")
            raise HTTPException(status_code=404, detail="Connection not found")
        
        # Check if this connection has an Airbyte source_id
        if not conn.source_id:
            logger.error(f"Connection {connection_id} does not have an associated Airbyte source_id")
            raise HTTPException(
                status_code=400, 
                detail="Connection does not have an associated Airbyte source"
            )
            
        logger.info(f"Checking connection status for source_id: {conn.source_id}")
        
        # Create check request
        check_request = CheckConnectionRequest(source_id=conn.source_id)
        
        # Call Airbyte check connection function
        try:
            result = await airbyte_sync_service.check_connection(check_request)
            logger.info(f"Connection check result: {result.status}")
            return result
        except HTTPException as e:
            logger.error(f"HTTPException checking connection status: {e.status_code}: {e.detail}")
            raise e
        except Exception as e:
            error_msg = f"Error checking connection status: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
            
    except HTTPException as e:
        raise e
    except Exception as e:
        error_msg = f"Error in check_connection_status: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)