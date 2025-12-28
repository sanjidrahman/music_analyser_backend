from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models.segment import Segment
from ..models.user import User
from ..models.attempt import Attempt
from ..schemas.segment import SegmentResponse
from ..utils.security import get_current_user
from ..services.file_service import FileService

router = APIRouter(prefix="/api", tags=["segments"])


@router.get("/segments", response_model=List[SegmentResponse])
async def list_segments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List segments for the current authenticated user.

    This endpoint requires authentication and returns only segments belonging to the current user.

    Args:
        current_user: Authenticated user (required)
        db: Database session

    Returns:
        List[SegmentResponse]: List of user's segments
    """
    try:
        # Query only the current user's segments
        query = select(Segment).where(Segment.user_id == current_user.id)

        # Order by most recent first
        query = query.order_by(Segment.created_at.desc())

        result = await db.execute(query)
        segments = result.scalars().all()

        return [
            SegmentResponse(
                id=segment.id,
                user_id=segment.user_id,
                file_path=segment.file_path,
                vocal_file_path=segment.vocal_file_path,
                duration=segment.duration,
                start_time=segment.start_time,
                end_time=segment.end_time,
                original_filename=segment.original_filename,
                file_format=segment.file_format,
                sample_rate=segment.sample_rate,
                channels=segment.channels,
                created_at=segment.created_at,
                expires_at=segment.expires_at
            )
            for segment in segments
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve segments: {str(e)}"
        )


@router.get("/segments/{segment_id}", response_model=SegmentResponse)
async def get_segment(
    segment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific segment by ID.

    Args:
        segment_id: ID of the segment to retrieve
        current_user: Optional authenticated user
        db: Database session

    Returns:
        SegmentResponse: Segment details

    Raises:
        HTTPException: If segment not found or access denied
    """
    try:
        query = select(Segment).where(Segment.id == segment_id)
        result = await db.execute(query)
        segment = result.scalar_one_or_none()

        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Segment not found"
            )

        # Check access permissions - user can only access their own segments (or admin)
        if segment.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only access your own segments"
            )

        return SegmentResponse(
            id=segment.id,
            user_id=segment.user_id,
            file_path=segment.file_path,
            vocal_file_path=segment.vocal_file_path,
            duration=segment.duration,
            start_time=segment.start_time,
            end_time=segment.end_time,
            original_filename=segment.original_filename,
            file_format=segment.file_format,
            sample_rate=segment.sample_rate,
            channels=segment.channels,
            created_at=segment.created_at,
            expires_at=segment.expires_at
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve segment: {str(e)}"
        )


@router.delete("/segments/{segment_id}")
async def delete_segment(
    segment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a specific segment along with all associated attempts.

    Args:
        segment_id: ID of the segment to delete
        current_user: Authenticated user
        db: Database session

    Returns:
        dict: Success message with count of deleted attempts

    Raises:
        HTTPException: If segment not found or access denied
    """
    try:
        query = select(Segment).where(Segment.id == segment_id)
        result = await db.execute(query)
        segment = result.scalar_one_or_none()

        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Segment not found"
            )

        if segment.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only delete your own segments"
            )

        # Find and delete associated attempts
        attempts_result = await db.execute(
            select(Attempt).where(Attempt.segment_id == segment_id)
        )
        related_attempts = attempts_result.scalars().all()

        # Delete associated attempts first
        attempts_deleted = 0
        for attempt in related_attempts:
            await db.delete(attempt)
            attempts_deleted += 1

        # Delete files from filesystem
        try:
            await FileService.delete_file(segment.file_path)
            if segment.vocal_file_path:
                await FileService.delete_file(segment.vocal_file_path)
        except Exception:
            # Continue with database deletion even if file deletion fails
            pass

        # Delete the segment itself
        await db.delete(segment)
        await db.commit()

        return {"message": f"Segment and {attempts_deleted} associated attempt(s) deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete segment: {str(e)}"
        )