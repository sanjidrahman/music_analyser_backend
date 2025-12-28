from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RecordingCreate(BaseModel):
    original_filename: str
    file_format: str


class RecordingResponse(BaseModel):
    id: int
    user_id: Optional[int]
    segment_id: Optional[int]
    file_path: str
    vocal_file_path: Optional[str]
    duration: float
    original_filename: str
    file_format: str
    sample_rate: Optional[int]
    channels: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True