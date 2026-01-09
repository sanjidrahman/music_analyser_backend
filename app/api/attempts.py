from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..schemas.attempt import AttemptResponse, AttemptSummary
from ..schemas.common import SuccessResponse
from ..utils.security import get_current_user
from ..models.user import User
from ..models.attempt import Attempt
from ..models.segment import Segment
from ..models.recording import Recording

router = APIRouter(prefix="/api/attempts", tags=["attempts"])


@router.get("/", response_model=list[AttemptSummary])
async def get_user_attempts(
    limit: int = Query(50, le=100, ge=1),
    offset: int = Query(0, ge=0),
    segment_id: Optional[int] = Query(None),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    max_score: Optional[float] = Query(None, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's analysis attempts with optional filtering.

    Args:
        limit: Maximum number of attempts to return
        offset: Number of attempts to skip
        segment_id: Optional filter by segment ID
        min_score: Optional minimum overall score filter
        max_score: Optional maximum overall score filter
        current_user: Authenticated user
        db: Database session

    Returns:
        list[AttemptSummary]: List of attempt summaries
    """
    try:
        # Build base query
        query = select(Attempt).where(Attempt.user_id == current_user.id)

        # Apply filters
        if segment_id:
            query = query.where(Attempt.segment_id == segment_id)

        if min_score is not None:
            query = query.where(Attempt.overall_score >= min_score)

        if max_score is not None:
            query = query.where(Attempt.overall_score <= max_score)

        # Order by most recent first
        query = query.order_by(Attempt.created_at.desc())

        # Apply pagination
        query = query.offset(offset).limit(limit)

        # Execute query
        result = await db.execute(query)
        attempts = result.scalars().all()

        # Get related segment and recording info
        attempt_summaries = []
        for attempt in attempts:
            segment = await db.get(Segment, attempt.segment_id)
            recording = await db.get(Recording, attempt.recording_id)

            attempt_summaries.append(AttemptSummary(
                id=attempt.id,
                overall_score=attempt.overall_score,
                pitch_accuracy=attempt.pitch_accuracy,
                rhythm_accuracy=attempt.rhythm_accuracy,
                tone_similarity=attempt.tone_similarity,
                timing_accuracy=attempt.timing_accuracy,
                segment_filename=segment.original_filename if segment else "Unknown",
                recording_filename=recording.original_filename if recording else "Unknown",
                created_at=attempt.created_at
            ))

        return attempt_summaries

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get attempts: {str(e)}"
        )


@router.get("/{attempt_id}", response_model=AttemptResponse)
async def get_attempt(
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get specific attempt details.

    Args:
        attempt_id: Attempt ID
        current_user: Authenticated user
        db: Database session

    Returns:
        AttemptResponse: Detailed attempt information
    """
    try:
        attempt = await db.get(Attempt, attempt_id)
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attempt not found"
            )

        # Check ownership
        if attempt.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this attempt"
            )

        return AttemptResponse(
            id=attempt.id,
            user_id=attempt.user_id,
            segment_id=attempt.segment_id,
            recording_id=attempt.recording_id,
            overall_score=attempt.overall_score,
            pitch_accuracy=attempt.pitch_accuracy,
            rhythm_accuracy=attempt.rhythm_accuracy,
            tone_similarity=attempt.tone_similarity,
            timing_accuracy=attempt.timing_accuracy,
            detailed_analysis=attempt.detailed_analysis,
            duration_warning=attempt.duration_warning,
            analysis_version=attempt.analysis_version,
            created_at=attempt.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get attempt: {str(e)}"
        )


@router.delete("/{attempt_id}", response_model=SuccessResponse)
async def delete_attempt(
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a specific attempt.

    Args:
        attempt_id: Attempt ID
        current_user: Authenticated user
        db: Database session

    Returns:
        SuccessResponse: Deletion confirmation
    """
    try:
        attempt = await db.get(Attempt, attempt_id)
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attempt not found"
            )

        # Check ownership
        if attempt.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this attempt"
            )

        # Delete attempt
        await db.delete(attempt)
        await db.commit()

        return SuccessResponse(
            message="Attempt deleted successfully",
            data={"attempt_id": attempt_id},
            timestamp=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete attempt: {str(e)}"
        )


@router.get("/stats/overview")
async def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's singing statistics overview.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        dict: User statistics
    """
    try:
        # Get user's attempts
        result = await db.execute(
            select(Attempt).where(Attempt.user_id == current_user.id)
        )
        attempts = result.scalars().all()

        if not attempts:
            return {
                "total_attempts": 0,
                "average_score": 0.0,
                "best_score": 0.0,
                "recent_attempts": 0,
                "category_averages": {
                    "pitch_accuracy": 0.0,
                    "rhythm_accuracy": 0.0,
                    "tone_similarity": 0.0,
                    "timing_accuracy": 0.0
                }
            }

        # Calculate statistics
        total_attempts = len(attempts)
        scores = [attempt.overall_score for attempt in attempts]
        average_score = sum(scores) / total_attempts
        best_score = max(scores)

        # Recent attempts (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_attempts = len([a for a in attempts if a.created_at > week_ago])

        # Category averages
        category_averages = {
            "pitch_accuracy": sum(a.pitch_accuracy for a in attempts) / total_attempts,
            "rhythm_accuracy": sum(a.rhythm_accuracy for a in attempts) / total_attempts,
            "tone_similarity": sum(a.tone_similarity for a in attempts) / total_attempts,
            "timing_accuracy": sum(a.timing_accuracy for a in attempts) / total_attempts
        }

        return {
            "total_attempts": total_attempts,
            "average_score": round(average_score, 2),
            "best_score": round(best_score, 2),
            "recent_attempts": recent_attempts,
            "category_averages": {
                k: round(v, 2) for k, v in category_averages.items()
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user stats: {str(e)}"
        )