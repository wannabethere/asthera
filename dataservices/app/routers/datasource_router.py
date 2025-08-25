from fastapi import APIRouter, Depends
from app.service.datasource_service import ConnectionService
from app.service.models import connection_details, SupportedDatabasesResponse
from app.schemas.dbmodels import DataSources
from app.core.dependencies import get_async_db_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from app.routers.project_workflow import get_token
from app.service.share_permissions import SharePermissions
logger = logging.getLogger(__name__)

router = APIRouter()



@router.get("/datasources")
async def get_datasources(db: AsyncSession = Depends(get_async_db_session),token: str = Depends(get_token)):
    """
    Returns a list of all active data sources.
    """
    user= await SharePermissions()._validate_user(token)
    result = await db.execute(select(DataSources))
    datasources = result.scalars().all()
    return datasources


@router.get("/datasources/supportedDatabases", response_model=SupportedDatabasesResponse)
async def get_supported_databases(
    db: AsyncSession = Depends(get_async_db_session),
    token: str = Depends(get_token)
) -> SupportedDatabasesResponse:
    """
    Returns a simple list of supported, active database types.
    """
    user= await SharePermissions()._validate_user(token)
    result = await db.execute(
        select(DataSources.database_type).where(DataSources.is_active == True)
    )
    database_list = [row for row in result.scalars().all()]

    return SupportedDatabasesResponse(supported_databases=database_list)


@router.post("/connections/createConnections")
async def create_connections(
    connection_details: connection_details, db: AsyncSession = Depends(get_async_db_session),token: str = Depends(get_token)
):
    """
    Creates a new connection to a database.
    """
    user= await SharePermissions()._validate_user(token)
    testservice = ConnectionService(db)
    return await testservice.create_connection(connection_details,user['id'])


@router.get("/connections/getAllConnections")
async def get_all_connections(db: AsyncSession = Depends(get_async_db_session),token: str = Depends(get_token)):
    """
    Returns a list of all active connections.
    """
    user= await SharePermissions()._validate_user(token)
    testservice = ConnectionService(db)
    return await testservice.get_all_connections(user['id'])


@router.get("/connections/{connectionId}/ERD")
async def get_Connection_ERD(connectionId, db: AsyncSession = Depends(get_async_db_session),token: str = Depends(get_token)):
    """
    Returns the ERD for a specific connection.
    """
    user= await SharePermissions()._validate_user(token)
    service = ConnectionService(db)

    return await service.get_ERD_By_ConnectionID(connectionId,user['id'])
