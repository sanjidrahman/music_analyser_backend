import os
import uuid
import shutil
from datetime import datetime, timedelta
from typing import Optional
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import settings
from ..models.user import User
from ..models.segment import Segment
from ..models.recording import Recording
from ..utils.dependencies import validate_audio_file, generate_unique_filename
from ..utils.exceptions import ValidationError, FileNotFoundError


class FileService:
    """Service for file management operations."""

    @staticmethod
    async def save_uploaded_file(
        file: UploadFile,
        storage_dir: str,
        user: Optional[User] = None
    ) -> tuple[str, str]:
        """
        Save uploaded file to storage directory.

        Returns:
            tuple: (filename, file_path)
        """
        validate_audio_file(file)

        # Generate unique filename
        filename = generate_unique_filename(file.filename)
        file_path = os.path.join(storage_dir, filename)

        # Ensure directory exists
        os.makedirs(storage_dir, exist_ok=True)

        # Save file
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise ValidationError(f"Failed to save file: {str(e)}")
        finally:
            file.file.close()

        return filename, file_path

    @staticmethod
    async def create_segment_record(
        db: AsyncSession,
        user_id: Optional[int],
        file_path: str,
        vocal_file_path: Optional[str],
        duration: float,
        start_time: float,
        end_time: float,
        original_filename: str,
        file_format: str,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None
    ) -> Segment:
        """Create a segment record in the database."""
        expires_at = datetime.utcnow() + timedelta(days=settings.segment_retention_days)

        segment = Segment(
            user_id=user_id,
            file_path=file_path,
            vocal_file_path=vocal_file_path,
            duration=duration,
            start_time=start_time,
            end_time=end_time,
            original_filename=original_filename,
            file_format=file_format,
            sample_rate=sample_rate,
            channels=channels,
            expires_at=expires_at
        )

        db.add(segment)
        await db.commit()
        await db.refresh(segment)
        return segment

    @staticmethod
    async def create_recording_record(
        db: AsyncSession,
        user_id: Optional[int],
        segment_id: Optional[int],
        file_path: str,
        vocal_file_path: Optional[str],
        duration: float,
        original_filename: str,
        file_format: str,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None
    ) -> Recording:
        """Create a recording record in the database."""
        recording = Recording(
            user_id=user_id,
            segment_id=segment_id,
            file_path=file_path,
            vocal_file_path=vocal_file_path,
            duration=duration,
            original_filename=original_filename,
            file_format=file_format,
            sample_rate=sample_rate,
            channels=channels
        )

        db.add(recording)
        await db.commit()
        await db.refresh(recording)
        return recording

    @staticmethod
    async def delete_file(file_path: str) -> None:
        """Delete file from filesystem."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            raise FileNotFoundError(f"Failed to delete file: {str(e)}")

    @staticmethod
    async def cleanup_expired_files(db: AsyncSession) -> int:
        """Clean up expired segment files and their records."""
        # Find expired segments
        expired_segments = await db.execute(
            select(Segment).where(
                Segment.expires_at < datetime.utcnow()
            )
        )
        expired_segments = expired_segments.scalars().all()

        deleted_count = 0
        for segment in expired_segments:
            try:
                # Delete files
                await FileService.delete_file(segment.file_path)
                if segment.vocal_file_path:
                    await FileService.delete_file(segment.vocal_file_path)

                # Delete database record
                await db.delete(segment)
                deleted_count += 1
            except Exception:
                # Log error but continue with other files
                continue

        await db.commit()
        return deleted_count

    @staticmethod
    async def delete_recording_files(recording: Recording) -> None:
        """Delete recording and its vocal files from filesystem."""
        try:
            # Delete main recording file
            await FileService.delete_file(recording.file_path)

            # Delete vocal file if it exists
            if recording.vocal_file_path:
                await FileService.delete_file(recording.vocal_file_path)
        except Exception as e:
            raise FileNotFoundError(f"Failed to delete recording files: {str(e)}")

    @staticmethod
    def get_file_info(file_path: str) -> dict:
        """Get file information."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        stat = os.stat(file_path)
        return {
            "path": file_path,
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime),
            "modified": datetime.fromtimestamp(stat.st_mtime)
        }