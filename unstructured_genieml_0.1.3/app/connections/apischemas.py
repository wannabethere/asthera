from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Union, List
from uuid import UUID
from datetime import datetime
from enum import Enum
from pydantic import validator

class ConnectionType(str, Enum):
    S3 = "s3"
    GONG = "gong"
    SALESFORCE = "salesforce"
    SLACK = "slack"
    GOOGLE_DRIVE = "google_drive"

class BaseSettings(BaseModel):
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# Connection type specific settings schemas
class S3Settings(BaseSettings):
    # Required fields
    sourceType: str = Field(..., description="Source type identifier")
    streams: List[Dict] = Field(..., description="List of stream configurations")
    bucket: str = Field(..., description="S3 bucket name")
    aws_access_key_id: str = Field(..., description="AWS access key ID")
    aws_secret_access_key: str = Field(..., description="AWS secret access key")
    region_name: str = Field(..., description="AWS region name")
    # Optional fields
    role_arn: Optional[str] = Field(None, description="IAM role ARN for S3 access")
    endpoint: Optional[str] = Field(None, description="Custom S3 endpoint")

class GongSettings(BaseSettings):
    gong_access_key: str = Field(..., description="Gong API access key")
    gong_access_key_secret: str = Field(..., description="Gong API access key secret")
    start_date: Optional[str] = Field(None, description="Optional start date (ISO format)")

class SalesforceSettings(BaseSettings):
    client_id: str = Field(..., description="Salesforce client ID")
    client_secret: str = Field(..., description="Salesforce client secret")
    refresh_token: str = Field(..., description="Salesforce refresh token")
    start_date: Optional[str] = Field(None, description="Optional start date (ISO format)")
    streams_criteria: Optional[List[Dict]] = Field(None, description="Optional list of stream criteria")

class GoogleDriveCredentials(BaseSettings):
    auth_type: str = Field("Service", description="Authentication type (Service)")
    service_account_info: Union[str, Dict[str, Any]] = Field(..., description="The JSON key of the service account to use for authorization, can be a string or object")

class GoogleDriveSettings(BaseSettings):
    sourceType: str = Field(..., description="Source type identifier")
    streams: List[Dict] = Field(..., description="List of Google Drive stream configurations")
    folder_url: str = Field(..., description="URL of the Google Drive folder")
    credentials: GoogleDriveCredentials = Field(..., description="Google Drive credentials")

class SlackSettings(BaseSettings):
    token: str
    start_date: Optional[str] = None
    channels: Optional[list] = None

# Update ConnectionBase to use type-specific settings
class ConnectionBase(BaseModel):
    name: str
    type: ConnectionType
    description: Optional[str] = None
    settings: Union[S3Settings, GongSettings, SalesforceSettings, GoogleDriveSettings, SlackSettings]
    user_id: Optional[str] = None
    role: Optional[str] = None
    version: str = "1.0"

    # Validator to ensure settings match the connection type
    @validator('settings', pre=True)
    def validate_settings(cls, value, values):
        settings_type_map = {
            ConnectionType.S3: S3Settings,
            ConnectionType.GONG: GongSettings,
            ConnectionType.SALESFORCE: SalesforceSettings,
            ConnectionType.GOOGLE_DRIVE: GoogleDriveSettings,
            ConnectionType.SLACK: SlackSettings
        }
        
        conn_type = values.get('type')
        if not conn_type:
            raise ValueError("Connection type must be specified before settings")
            
        expected_settings_type = settings_type_map.get(conn_type)
        if not expected_settings_type:
            raise ValueError(f"Unknown connection type: {conn_type}")
            
        if isinstance(value, dict):
            try:
                return expected_settings_type(**value)
            except Exception as e:
                raise ValueError(f"Invalid settings for connection type {conn_type}: {str(e)}")
        elif isinstance(value, expected_settings_type):
            return value
        else:
            raise ValueError(f"Settings must be a dict or {expected_settings_type.__name__}")

    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        # Convert settings to dict if it's a Pydantic model
        if isinstance(d.get('settings'), BaseSettings):
            d['settings'] = d['settings'].dict()
        return d

    class Config:
        json_schema_extra = {
            "example": {
                "name": "S3 Data Lake",
                "type": "s3",
                "description": "Connection to data lake",
                "settings": {
                    "sourceType": "s3",
                    "bucket": "my-data-lake",
                    "aws_access_key_id": "AKIAXXXXXXXXXXXXXXXX",
                    "aws_secret_access_key": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                    "region_name": "us-east-1"
                },
                "user_id": "user123",
                "role": "admin",
                "version": "1.0"
            }
        }
        json_encoders = {
            BaseSettings: lambda v: v.dict()
        }

class DataSourceIn(BaseModel):
    connector_name: str
    connector_type: str
    description: Optional[str] = None
    config: Dict[str, Any]

class DataSourceOut(DataSourceIn):
    id: UUID
    created_at: datetime

class DataSourceResponse(BaseModel):
    connector_name: str
    connector_type: str
    description: Optional[str] = None
    config: Dict[str, Any]

class ConnectionCreate(ConnectionBase):
    class Config:
        json_schema_extra = {
            "example": {
                "name": "S3 Data Source",
                "type": "s3",
                "description": "Connection to S3 data lake",
                "settings": {
                    "sourceType": "s3",
                    "streams": [
                        {
                            "name": "data",
                            "format": { "filetype": "jsonl" }
                        }
                    ],
                    "bucket": "my-data-lake",
                    "aws_access_key_id": "AKIAXXXXXXXXXXXXXXXX",
                    "aws_secret_access_key": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                    "region_name": "us-east-1"
                },
                "user_id": "user123",
                "role": "admin",
                "version": "1.0"
            }
        }

class ConnectionResponse(ConnectionBase):
    connection_id: UUID
    source_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True