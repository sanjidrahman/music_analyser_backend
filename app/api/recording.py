import os
import shutil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..config import settings
from ..schemas.recording import RecordingResponse
from ..schemas.common import SuccessResponse
from ..services.file_service import FileService
from ..services.audio_processor import AudioProcessor
from ..utils.security import get_optional_user
from ..utils.exceptions import ValidationError, ProcessingError
from ..models.user import User
from ..models.segment import Segment
from ..models.recording import Recording

router = APIRouter(prefix="/api/recording", tags=["recording"])


@router.post("/upload", response_model=RecordingResponse)
async def upload_recording(
    file: UploadFile = File(...),
    segment_id: int = Form(...),
    file_type: str = Form(...),
    start_time: Optional[float] = Form(None),
    end_time: Optional[float] = Form(None),
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a user recording or audio file for analysis.

    This endpoint can work without authentication for file upload,
    but authenticated users will have the recordings associated with their account.

    A segment_id is required to associate the recording with the original segment for analysis.

    For file_type="audio": start_time and end_time are REQUIRED to extract segment.
    For file_type="recording": start_time and end_time are OPTIONAL.
        - If provided: extracts segment from recording
        - If not provided: processes full recording (but recording duration must not exceed segment duration)

    Args:
        file: User recording or audio file
        segment_id: Required associated segment ID for analysis
        file_type: Type of file - "recording" or "audio"
        start_time: Start time for segment extraction in seconds (required for audio, optional for recording)
        end_time: End time for segment extraction in seconds (required for audio, optional for recording)
        current_user: Optional authenticated user
        db: Database session

    Returns:
        RecordingResponse: Created recording information with vocal separation
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )

        # Validate file_type
        if file_type not in ["recording", "audio"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_type must be either 'recording' or 'audio'"
            )

        # Validate start_time and end_time for audio files
        if file_type == "audio":
            if start_time is None or end_time is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_time and end_time are required for file_type='audio'"
                )

        # Validate segment_id
        result = await db.execute(select(Segment).where(Segment.id == segment_id))
        segment = result.scalar_one_or_none()
        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Segment with ID {segment_id} not found"
            )

        # Get file extension and validate audio format
        file_extension = os.path.splitext(file.filename)[1].lower().lstrip('.')
        if file_extension not in settings.allowed_audio_formats:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format. Allowed formats: {', '.join(settings.allowed_audio_formats)}"
            )

        # Save uploaded file temporarily
        temp_dir = os.path.join(settings.storage_path, "temp")
        os.makedirs(temp_dir, exist_ok=True)

        temp_filename, temp_file_path = await FileService.save_uploaded_file(
            file, temp_dir, current_user
        )

        try:
            # Get audio info for validation
            audio_info = AudioProcessor.get_audio_info(temp_file_path)

            # Generate output filenames
            recording_filename = f"recording_{temp_filename}"
            vocal_filename = f"vocals_{temp_filename}"

            recording_file_path = os.path.join(settings.storage_recordings_path, recording_filename)
            vocal_file_path = os.path.join(settings.storage_vocals_path, vocal_filename)

            # Ensure output directories exist
            os.makedirs(settings.storage_recordings_path, exist_ok=True)
            os.makedirs(settings.storage_vocals_path, exist_ok=True)

            # Process based on whether start_time/end_time are provided
            if start_time is not None and end_time is not None:
                # Segment extraction requested
                # Validate end_time
                if end_time > audio_info["duration"]:
                    end_time = audio_info["duration"]

                # Extract segment and separate vocals
                processing_results = AudioProcessor.process_song(
                    temp_file_path,
                    recording_file_path,
                    vocal_file_path,
                    start_time,
                    end_time
                )
            else:
                # No segment extraction - process full recording
                # Validate recording duration against segment duration
                if file_type == "recording":
                    if audio_info["duration"] > segment.duration:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Recording duration ({audio_info['duration']:.2f}s) exceeds segment duration ({segment.duration:.2f}s)"
                        )

                # Copy full recording and separate vocals
                shutil.copy2(temp_file_path, recording_file_path)
                vocals_separated = AudioProcessor.separate_vocals(
                    temp_file_path,
                    vocal_file_path
                )

                processing_results = {
                    "segment_duration": audio_info["duration"],
                    "sample_rate": audio_info["sample_rate"],
                    "channels": audio_info["channels"],
                    "vocals_separated": vocals_separated
                }

            # Create recording record in database
            user_id = current_user.id if current_user else None
            recording = await FileService.create_recording_record(
                db=db,
                user_id=user_id,
                segment_id=segment_id,
                file_path=recording_file_path,
                vocal_file_path=vocal_file_path if processing_results["vocals_separated"] else None,
                duration=processing_results["segment_duration"],
                original_filename=file.filename,
                file_format=file_extension,
                file_type=file_type,
                sample_rate=processing_results["sample_rate"],
                channels=processing_results["channels"]
            )

            return RecordingResponse(
                id=recording.id,
                user_id=recording.user_id,
                segment_id=recording.segment_id,
                file_path=recording.file_path,
                vocal_file_path=recording.vocal_file_path,
                duration=recording.duration,
                original_filename=recording.original_filename,
                file_format=recording.file_format,
                file_type=recording.file_type,
                sample_rate=recording.sample_rate,
                channels=recording.channels,
                created_at=recording.created_at
            )

        finally:
            # Clean up temporary file
            try:
                os.remove(temp_file_path)
            except:
                pass

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ProcessingError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Audio processing failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recording upload failed: {str(e)}"
        )


@router.get("/", response_model=list[RecordingResponse])
async def get_recordings(
    segment_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user recordings.

    Args:
        segment_id: Optional filter by segment ID
        current_user: Optional authenticated user
        db: Database session

    Returns:
        list[RecordingResponse]: List of recordings
    """
    try:
        # Build query
        query = select(Recording)

        # Filter by user if authenticated
        if current_user:
            query = query.where(Recording.user_id == current_user.id)

        # Filter by segment_id if provided
        if segment_id:
            query = query.where(Recording.segment_id == segment_id)

        # Execute query
        result = await db.execute(query.order_by(Recording.created_at.desc()))
        recordings = result.scalars().all()

        return [
            RecordingResponse(
                id=recording.id,
                user_id=recording.user_id,
                segment_id=recording.segment_id,
                file_path=recording.file_path,
                vocal_file_path=recording.vocal_file_path,
                duration=recording.duration,
                original_filename=recording.original_filename,
                file_format=recording.file_format,
                file_type=recording.file_type,
                sample_rate=recording.sample_rate,
                channels=recording.channels,
                created_at=recording.created_at
            )
            for recording in recordings
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recordings: {str(e)}"
        )


@router.get("/{recording_id}", response_model=RecordingResponse)
async def get_recording(
    recording_id: int,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get specific recording information.

    Args:
        recording_id: Recording ID
        current_user: Optional authenticated user
        db: Database session

    Returns:
        RecordingResponse: Recording information
    """
    try:
        result = await db.execute(select(Recording).where(Recording.id == recording_id))
        recording = result.scalar_one_or_none()

        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found"
            )

        # Check ownership if authenticated
        if current_user and recording.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this recording"
            )

        return RecordingResponse(
            id=recording.id,
            user_id=recording.user_id,
            segment_id=recording.segment_id,
            file_path=recording.file_path,
            vocal_file_path=recording.vocal_file_path,
            duration=recording.duration,
            original_filename=recording.original_filename,
            file_format=recording.file_format,
            file_type=recording.file_type,
            sample_rate=recording.sample_rate,
            channels=recording.channels,
            created_at=recording.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recording: {str(e)}"
        )