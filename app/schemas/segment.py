from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime


class SegmentCreate(BaseModel):
    start_time: Optional[float] = 0.0
    end_time: Optional[float] = None
    original_filename: str
    file_format: str

    @validator('start_time')
    def validate_start_time(cls, v):
        if v < 0:
            raise ValueError('Start time cannot be negative')
        return v

    @validator('end_time')
    def validate_end_time(cls, v, values):
        if v is not None and 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be greater than start time')
        return v


class SegmentResponse(BaseModel):
    id: int
    user_id: Optional[int]
    file_path: str
    vocal_file_path: Optional[str]
    duration: float
    start_time: float
    end_time: float
    original_filename: str
    file_format: str
    sample_rate: Optional[int]
    channels: Optional[int]
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class SupportedFormatsResponse(BaseModel):
    formats: list[str]
    max_size_mb: int
    min_duration_seconds: int
    max_duration_seconds: int