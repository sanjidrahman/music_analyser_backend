import os
from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application Settings
    app_name: str = "Song Rating API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database Configuration
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/song_rating_db"

    # JWT Configuration
    jwt_secret_key: str = "your-super-secret-jwt-key-change-this-in-production"
    access_token_expire_days: int = 7

    # File Upload Configuration
    max_upload_size_mb: int = 50
    allowed_audio_formats: Union[List[str], str] = ["wav", "mp3", "m4a", "flac", "ogg", "webm"]
    min_segment_duration: int = 10
    max_segment_duration: int = 120

    # Storage Configuration
    storage_path: str = "./storage"
    segment_retention_days: int = 7

    # CORS Configuration
    cors_origins: Union[List[str], str] = ["http://localhost:3000", "http://localhost:8080"]

    class Config:
        env_file = ".env"
        case_sensitive = False
        env_parse_none_str = 'null'

    @field_validator("allowed_audio_formats", mode="before")
    @classmethod
    def parse_audio_formats(cls, v):
        if isinstance(v, str):
            return [format.strip().lower() for format in v.split(",")]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("max_upload_size_mb", mode="before")
    @classmethod
    def validate_max_upload_size(cls, v):
        return int(v)

    @field_validator("min_segment_duration", mode="before")
    @classmethod
    def validate_min_segment_duration(cls, v):
        return int(v)

    @field_validator("max_segment_duration", mode="before")
    @classmethod
    def validate_max_segment_duration(cls, v):
        return int(v)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def storage_segments_path(self) -> str:
        return os.path.join(self.storage_path, "segments")

    @property
    def storage_vocals_path(self) -> str:
        return os.path.join(self.storage_path, "vocals")

    @property
    def storage_recordings_path(self) -> str:
        return os.path.join(self.storage_path, "recordings")


# Create global settings instance
settings = Settings()

# Ensure storage directories exist
os.makedirs(settings.storage_segments_path, exist_ok=True)
os.makedirs(settings.storage_vocals_path, exist_ok=True)
os.makedirs(settings.storage_recordings_path, exist_ok=True)