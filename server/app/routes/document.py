from fastapi import APIRouter, UploadFile, File, Form
import logging
from app.settings import get_settings
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import List, Optional
import requests as re

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/document", tags=["document"])
settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@router.post("/upload-file")
async def UploadFile(file: UploadFile = File(...),
                     user_context: Optional[str] = Form(None)):
    response = await sendUploadFiles(file, user_context)
    return response


async def sendUploadFiles(file: UploadFile, user_context: Optional[str]):
    forwarded_files = {
        "file": (file.filename, await file.read(), file.content_type)
    }

    # Optional fields for form-data
    data = {
        'document_type': 'generic',
        'test_mode': 'enabled',
        'user_context': user_context,
    }

    headers = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Origin": "http://40.124.72.73:8023",
        "Referer": "http://40.124.72.73:8023/"
    }

    # Send POST request to the destination API
    response = re.post("http://40.124.72.73:8023/api/documents/", files=forwarded_files,
                       data=data, headers=headers)

    print(response.status_code)
    print(response.text)

    return {
        "status_code": response.status_code,
        "response": response.json()
    }







