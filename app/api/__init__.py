from .auth import router as auth_router
from .upload import router as upload_router
from .recording import router as recording_router
from .analysis import router as analysis_router
from .attempts import router as attempts_router
from .segments import router as segments_router
from .audio import router as audio_router

__all__ = ["auth_router", "upload_router", "recording_router", "analysis_router", "attempts_router", "segments_router", "audio_router"]