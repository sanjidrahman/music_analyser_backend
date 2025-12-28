from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime
    path: Optional[str] = None


class SuccessResponse(BaseModel):
    message: str
    data: Optional[Any] = None
    timestamp: datetime