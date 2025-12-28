import numpy as np
import librosa
from scipy.spatial.distance import cosine
from scipy.signal.windows import hann
from fastdtw import fastdtw
from typing import Dict, Any, List, Tuple
import warnings

from ..utils.exceptions import ProcessingError

# Suppress warnings
warnings.filterwarnings('ignore')

import scipy.signal
scipy.signal.hann = hann

class AudioAnalyzer:
    """Service for analyzing audio similarity between reference and user recordings."""

    @staticmethod
    def load_and_preprocess_audio(file_path: str, target_sr: int = 22050) -> Tuple[np.ndarray, int]:
        """
        Load and preprocess audio file for analysis.

        Args:
            file_path: Path to audio file
            target_sr: Target sample rate

        Returns:
            tuple: (audio_data, sample_rate)
        """
        try:
            # Load audio with consistent sample rate
            audio_data, sr = librosa.load(file_path, sr=target_sr, mono=True)

            # Trim silence from beginning and end
            audio_data, _ = librosa.effects.trim(audio_data, top_db=20)

            # Normalize audio
            if np.max(np.abs(audio_data)) > 0:
                audio_data = audio_data / np.max(np.abs(audio_data))

            return audio_data, sr
        except Exception as e:
            raise ProcessingError(f"Failed to load audio file {file_path}: {str(e)}")

    @staticmethod
    def extract_pitch(audio_data: np.ndarray, sr: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Extract pitch using librosa's pyin algorithm.

        Args:
            audio_data: Audio signal
            sr: Sample rate

        Returns:
            tuple: (pitch_values, times, confidence_scores)
        """
        try:
            # Use pYIN for pitch tracking
            pitch_values, voiced_flags, voiced_probs = librosa.pyin(
                audio_data,
                fmin=librosa.note_to_hz('C2'),
                fmax=librosa.note_to_hz('C7'),
                sr=sr,
                frame_length=2048,
                hop_length=512
            )

            # Get time stamps
            times = librosa.frames_to_time(
                np.arange(len(pitch_values)),
                sr=sr,
                hop_length=512
            )

            # Clean up pitch values (replace NaN with 0)
            pitch_values = np.nan_to_num(pitch_values, nan=0.0)

            return pitch_values, times, voiced_probs

        except Exception as e:
            raise ProcessingError(f"Failed to extract pitch: {str(e)}")

    @staticmethod
    def extract_mfcc(audio_data: np.ndarray, sr: int, n_mfcc: int = 13) -> np.ndarray:
        """
        Extract MFCC features for timbre analysis.

        Args:
            audio_data: Audio signal
            sr: Sample rate
            n_mfcc: Number of MFCC coefficients

        Returns:
            np.ndarray: MFCC features
        """
        try:
            # Extract MFCC features
            mfcc = librosa.feature.mfcc(
                y=audio_data,
                sr=sr,
                n_mfcc=n_mfcc,
                hop_length=512
            )

            # Compute deltas and delta-deltas
            mfcc_delta = librosa.feature.delta(mfcc)
            mfcc_delta2 = librosa.feature.delta(mfcc, order=2)

            # Combine all features
            combined_features = np.vstack([mfcc, mfcc_delta, mfcc_delta2])

            return combined_features

        except Exception as e:
            raise ProcessingError(f"Failed to extract MFCC features: {str(e)}")

    @staticmethod
    def extract_tempo_and_beats(audio_data: np.ndarray, sr: int) -> Tuple[float, np.ndarray]:
        """
        Extract tempo and beat positions.

        Args:
            audio_data: Audio signal
            sr: Sample rate

        Returns:
            tuple: (tempo, beat_times)
        """
        try:
            # Extract tempo and beat frames
            tempo, beat_frames = librosa.beat.beat_track(
                y=audio_data,
                sr=sr,
                hop_length=512
            )

            # Convert beat frames to time
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)

            return float(tempo), beat_times

        except Exception as e:
            raise ProcessingError(f"Failed to extract tempo and beats: {str(e)}")

    @staticmethod
    def compare_pitch_sequences(
        ref_pitch: np.ndarray,
        user_pitch: np.ndarray,
        ref_times: np.ndarray,
        user_times: np.ndarray
    ) -> Dict[str, Any]:
        """
        Compare pitch sequences using Dynamic Time Warping.

        Args:
            ref_pitch: Reference pitch sequence
            user_pitch: User pitch sequence
            ref_times: Reference time stamps
            user_times: User time stamps

        Returns:
            dict: Pitch comparison results
        """
        try:
            # Remove zero values (unvoiced segments)
            ref_mask = ref_pitch > 0
            user_mask = user_pitch > 0

            if not np.any(ref_mask) or not np.any(user_mask):
                return {
                    "pitch_similarity": 0.0,
                    "notes_matched": 0,
                    "notes_total": 1,
                    "pitch_over_time": []
                }

            ref_pitch_clean = ref_pitch[ref_mask]
            ref_times_clean = ref_times[ref_mask]
            user_pitch_clean = user_pitch[user_mask]
            user_times_clean = user_times[user_mask]

            # Use Dynamic Time Warping to align sequences
            try:
                distance, path = fastdtw(
                    ref_pitch_clean.reshape(-1, 1),
                    user_pitch_clean.reshape(-1, 1),
                    dist=2  # Euclidean distance
                )
            except:
                # Fallback: simple linear interpolation
                distance = np.mean((ref_pitch_clean - user_pitch_clean) ** 2)
                path = list(zip(range(len(ref_pitch_clean)), range(len(user_pitch_clean))))

            # Calculate pitch similarity (0-100)
            max_possible_distance = (librosa.note_to_hz('C7') - librosa.note_to_hz('C2')) ** 2
            pitch_similarity = max(0, 100 - (distance / len(path) / max_possible_distance * 100))

            # Calculate notes matched
            tolerance_semitones = 1  # Allow 1 semitone tolerance
            notes_matched = 0
            pitch_over_time = []

            for i, j in path[::10]:  # Sample every 10th point for efficiency
                if i < len(ref_pitch_clean) and j < len(user_pitch_clean):
                    ref_note = librosa.hz_to_midi(ref_pitch_clean[i])
                    user_note = librosa.hz_to_midi(user_pitch_clean[j])

                    if abs(ref_note - user_note) <= tolerance_semitones:
                        notes_matched += 1

                    pitch_over_time.append({
                        "time": float(ref_times_clean[i]),
                        "ref_pitch": float(ref_pitch_clean[i]),
                        "user_pitch": float(user_pitch_clean[j]),
                        "difference_semitones": float(ref_note - user_note)
                    })

            return {
                "pitch_similarity": pitch_similarity,
                "notes_matched": notes_matched,
                "notes_total": len(ref_pitch_clean),
                "pitch_over_time": pitch_over_time
            }

        except Exception as e:
            raise ProcessingError(f"Failed to compare pitch sequences: {str(e)}")

    @staticmethod
    def compare_rhythm(ref_tempo: float, user_tempo: float, ref_beats: np.ndarray, user_beats: np.ndarray) -> Dict[str, Any]:
        """
        Compare rhythmic patterns.

        Args:
            ref_tempo: Reference tempo
            user_tempo: User tempo
            ref_beats: Reference beat times
            user_beats: User beat times

        Returns:
            dict: Rhythm comparison results
        """
        try:
            # Tempo similarity (0-100)
            tempo_diff = abs(ref_tempo - user_tempo)
            tempo_similarity = max(0, 100 - (tempo_diff / ref_tempo * 100))

            # Beat alignment
            if len(ref_beats) > 0 and len(user_beats) > 0:
                # Simple beat alignment score based on timing differences
                min_length = min(len(ref_beats), len(user_beats))
                timing_errors = []

                for i in range(min_length):
                    expected_time = ref_beats[i]
                    actual_time = user_beats[i]
                    timing_errors.append(abs(actual_time - expected_time))

                avg_timing_error = np.mean(timing_errors)
                beat_alignment = max(0, 100 - (avg_timing_error * 1000))  # Convert to ms
            else:
                beat_alignment = 0

            return {
                "tempo_similarity": tempo_similarity,
                "tempo_difference": tempo_diff,
                "beat_alignment": beat_alignment,
                "rhythm_accuracy": (tempo_similarity + beat_alignment) / 2
            }

        except Exception as e:
            raise ProcessingError(f"Failed to compare rhythm: {str(e)}")

    @staticmethod
    def compare_timbre(ref_mfcc: np.ndarray, user_mfcc: np.ndarray) -> float:
        """
        Compare timbre using MFCC features.

        Args:
            ref_mfcc: Reference MFCC features
            user_mfcc: User MFCC features

        Returns:
            float: Timbre similarity (0-100)
        """
        try:
            # Average MFCC features over time
            ref_avg = np.mean(ref_mfcc, axis=1)
            user_avg = np.mean(user_mfcc, axis=1)

            # Calculate cosine similarity
            similarity = 1 - cosine(ref_avg, user_avg)

            # Convert to 0-100 scale
            return max(0, similarity * 100)

        except Exception as e:
            raise ProcessingError(f"Failed to compare timbre: {str(e)}")

    @staticmethod
    def analyze_singing_similarity(
        reference_file: str,
        user_file: str
    ) -> Dict[str, Any]:
        """
        Complete analysis of singing similarity between reference and user recordings.

        Args:
            reference_file: Path to reference audio file
            user_file: Path to user recording

        Returns:
            dict: Comprehensive analysis results
        """
        try:
            # Load audio files
            ref_audio, sr = AudioAnalyzer.load_and_preprocess_audio(reference_file)
            user_audio, _ = AudioAnalyzer.load_and_preprocess_audio(user_file, sr)

            # Extract features from reference
            ref_pitch, ref_times, ref_confidence = AudioAnalyzer.extract_pitch(ref_audio, sr)
            ref_mfcc = AudioAnalyzer.extract_mfcc(ref_audio, sr)
            ref_tempo, ref_beats = AudioAnalyzer.extract_tempo_and_beats(ref_audio, sr)

            # Extract features from user recording
            user_pitch, user_times, user_confidence = AudioAnalyzer.extract_pitch(user_audio, sr)
            user_mfcc = AudioAnalyzer.extract_mfcc(user_audio, sr)
            user_tempo, user_beats = AudioAnalyzer.extract_tempo_and_beats(user_audio, sr)

            # Compare pitch
            pitch_analysis = AudioAnalyzer.compare_pitch_sequences(
                ref_pitch, user_pitch, ref_times, user_times
            )

            # Compare rhythm
            rhythm_analysis = AudioAnalyzer.compare_rhythm(
                ref_tempo, user_tempo, ref_beats, user_beats
            )

            # Compare timbre
            timbre_similarity = AudioAnalyzer.compare_timbre(ref_mfcc, user_mfcc)

            # Calculate timing accuracy (duration match)
            ref_duration = len(ref_audio) / sr
            user_duration = len(user_audio) / sr
            duration_diff = abs(ref_duration - user_duration)
            timing_accuracy = max(0, 100 - (duration_diff / ref_duration * 100))

            # Calculate weighted overall score
            pitch_score = pitch_analysis["pitch_similarity"]
            rhythm_score = rhythm_analysis["rhythm_accuracy"]
            tone_score = timbre_similarity
            timing_score = timing_accuracy

            overall_score = (
                pitch_score * 0.4 +      # 40% pitch accuracy
                rhythm_score * 0.3 +     # 30% rhythm accuracy
                tone_score * 0.2 +       # 20% tone similarity
                timing_score * 0.1       # 10% timing
            )

            return {
                "overall_score": overall_score,
                "pitch_accuracy": pitch_score,
                "rhythm_accuracy": rhythm_score,
                "tone_similarity": tone_score,
                "timing_accuracy": timing_score,
                "detailed_analysis": {
                    "pitch": {
                        "similarity": pitch_score,
                        "notes_matched": pitch_analysis["notes_matched"],
                        "notes_total": pitch_analysis["notes_total"],
                        "pitch_over_time": pitch_analysis["pitch_over_time"]
                    },
                    "rhythm": {
                        "similarity": rhythm_score,
                        "tempo_difference": rhythm_analysis["tempo_difference"],
                        "beat_alignment": rhythm_analysis["beat_alignment"],
                        "ref_tempo": ref_tempo,
                        "user_tempo": user_tempo
                    },
                    "timbre": {
                        "similarity": tone_score
                    },
                    "timing": {
                        "similarity": timing_score,
                        "ref_duration": ref_duration,
                        "user_duration": user_duration,
                        "duration_difference": duration_diff
                    }
                }
            }

        except Exception as e:
            raise ProcessingError(f"Failed to analyze singing similarity: {str(e)}")