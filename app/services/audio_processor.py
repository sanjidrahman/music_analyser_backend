import os
import tempfile
import shutil
import librosa
import soundfile as sf
import numpy as np
from typing import Optional, Tuple

from ..config import settings
from ..utils.exceptions import ProcessingError


class AudioProcessor:
    """Handle audio file loading, segment extraction, and vocal separation."""

    @staticmethod
    def load_audio(file_path: str) -> Tuple[np.ndarray, int]:
        """Load audio file and return (audio_data, sample_rate)."""
        try:
            audio_data, sample_rate = librosa.load(file_path, sr=None, mono=False)
            return audio_data, sample_rate
        except Exception as e:
            raise ProcessingError(f"Failed to load audio: {str(e)}")

    @staticmethod
    def get_audio_info(file_path: str) -> dict:
        """Get audio duration, sample rate, and channels."""
        duration = librosa.get_duration(path=file_path)
        audio_data, sample_rate = AudioProcessor.load_audio(file_path)
        channels = 1 if audio_data.ndim == 1 else audio_data.shape[0]

        return {
            "duration": duration,
            "sample_rate": sample_rate,
            "channels": channels
        }

    @staticmethod
    def extract_segment(
        input_path: str,
        output_path: str,
        start_time: float,
        end_time: float
    ) -> float:
        """Extract a segment from audio file and return actual duration."""
        audio_data, sample_rate = AudioProcessor.load_audio(input_path)

        # Convert time to samples
        start_sample = int(start_time * sample_rate)
        end_sample = int(end_time * sample_rate)

        # Handle mono vs stereo
        if audio_data.ndim == 1:
            audio_length = len(audio_data)
            segment_data = audio_data[start_sample:end_sample]
        else:
            audio_length = audio_data.shape[1]
            segment_data = audio_data[:, start_sample:end_sample]

        # Ensure valid bounds
        start_sample = max(0, min(start_sample, audio_length))
        end_sample = max(start_sample, min(end_sample, audio_length))

        # Save segment as WAV
        if segment_data.ndim > 1:
            sf.write(output_path, segment_data.T, sample_rate)
            actual_duration = segment_data.shape[1] / sample_rate
        else:
            sf.write(output_path, segment_data, sample_rate)
            actual_duration = len(segment_data) / sample_rate

        return actual_duration

    @staticmethod
    def separate_vocals(input_path: str, vocals_output_path: str) -> bool:
        """Separate vocals using Spleeter. Returns True if successful."""
        try:
            from spleeter.separator import Separator

            separator = Separator('spleeter:2stems')
            
            with tempfile.TemporaryDirectory() as temp_dir:
                separator.separate_to_file(input_path, temp_dir)
                
                input_filename = os.path.splitext(os.path.basename(input_path))[0]
                vocals_path = os.path.join(temp_dir, input_filename, "vocals.wav")
                
                if os.path.exists(vocals_path):
                    os.rename(vocals_path, vocals_output_path)
                    return True

            return False

        except ImportError:
            shutil.copy2(input_path, vocals_output_path)
            return True
        except Exception as e:
            raise ProcessingError(f"Failed to separate vocals: {str(e)}")

    @staticmethod
    def process_song(
        input_path: str,
        output_segment_path: str,
        output_vocals_path: str,
        start_time: float,
        end_time: float
    ) -> dict:
        """
        Complete pipeline: extract segment + separate vocals.
        Returns processing info.
        """
        # Get audio info
        audio_info = AudioProcessor.get_audio_info(input_path)

        # Validate segment duration
        segment_duration = end_time - start_time

        if segment_duration < settings.min_segment_duration:
            raise ProcessingError(
                f"Segment too short ({segment_duration:.1f}s). "
                f"Minimum: {settings.min_segment_duration}s"
            )

        if segment_duration > settings.max_segment_duration:
            raise ProcessingError(
                f"Segment too long ({segment_duration:.1f}s). "
                f"Maximum: {settings.max_segment_duration}s"
            )

        # Extract segment
        actual_duration = AudioProcessor.extract_segment(
            input_path,
            output_segment_path,
            start_time,
            end_time
        )

        # Separate vocals
        vocals_success = AudioProcessor.separate_vocals(
            output_segment_path,
            output_vocals_path
        )

        return {
            "segment_duration": actual_duration,
            "original_duration": audio_info["duration"],
            "sample_rate": audio_info["sample_rate"],
            "channels": audio_info["channels"],
            "vocals_separated": vocals_success
        }