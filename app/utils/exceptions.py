from fastapi import HTTPException, status


class MusicAnalyzerException(Exception):
    """Base exception for the application."""
    pass


class AuthenticationError(MusicAnalyzerException):
    """Raised when authentication fails."""
    pass


class FileNotFoundError(MusicAnalyzerException):
    """Raised when a file is not found."""
    pass


class ValidationError(MusicAnalyzerException):
    """Raised when validation fails."""
    pass


class ProcessingError(MusicAnalyzerException):
    """Raised when audio processing fails."""
    pass


class DatabaseError(MusicAnalyzerException):
    """Raised when database operations fail."""
    pass


def create_http_exception(status_code: int, detail: str) -> HTTPException:
    """Create a standardized HTTPException."""
    return HTTPException(
        status_code=status_code,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"} if status_code == status.HTTP_401_UNAUTHORIZED else None
    )