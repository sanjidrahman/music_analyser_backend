import numpy as np
import librosa
from scipy.spatial.distance import cosine, euclidean
from scipy.signal.windows import hann
from fastdtw import fastdtw
from typing import Dict, Any, List, Tuple
import warnings

from ..utils.exceptions import ProcessingError

# Suppress warnings
warnings.filterwarnings("ignore")

import scipy.signal

scipy.signal.hann = hann


class AudioAnalyzer:
    """Service for analyzing audio similarity between reference and user recordings."""

    @staticmethod
    def load_and_preprocess_audio(
        file_path: str, target_sr: int = 22050
    ) -> Tuple[np.ndarray, int]:
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
    def extract_pitch(
        audio_data: np.ndarray, sr: int
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Extract pitch using librosa's piptrack algorithm (more robust than pyin).

        Args:
            audio_data: Audio signal
            sr: Sample rate

        Returns:
            tuple: (pitch_values, times, magnitudes)
        """
        try:
            # Use piptrack for more reliable pitch tracking
            pitches, magnitudes = librosa.piptrack(
                y=audio_data,
                sr=sr,
                hop_length=512,
                fmin=librosa.note_to_hz("C2"),
                fmax=librosa.note_to_hz("C7"),
            )

            # Extract pitch values at each time frame
            pitch_values = []
            for t in range(pitches.shape[1]):
                index = magnitudes[:, t].argmax()
                pitch = pitches[index, t]
                pitch_values.append(pitch if pitch > 0 else 0)

            pitch_values = np.array(pitch_values)

            # Get time stamps
            times = librosa.frames_to_time(
                np.arange(len(pitch_values)), sr=sr, hop_length=512
            )

            # Get magnitude values
            magnitude_values = np.max(magnitudes, axis=0)

            return pitch_values, times, magnitude_values

        except Exception as e:
            # Fallback to pyin if piptrack fails
            try:
                pitch_values, voiced_flags, voiced_probs = librosa.pyin(
                    audio_data,
                    fmin=librosa.note_to_hz("C2"),
                    fmax=librosa.note_to_hz("C7"),
                    sr=sr,
                    frame_length=2048,
                    hop_length=512,
                )

                times = librosa.frames_to_time(
                    np.arange(len(pitch_values)), sr=sr, hop_length=512
                )

                pitch_values = np.nan_to_num(pitch_values, nan=0.0)
                return pitch_values, times, voiced_probs
            except:
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
            np.ndarray: MFCC features (normalized)
        """
        try:
            # Extract MFCC features
            mfcc = librosa.feature.mfcc(
                y=audio_data, sr=sr, n_mfcc=n_mfcc, hop_length=512
            )

            # Compute deltas and delta-deltas
            mfcc_delta = librosa.feature.delta(mfcc)
            mfcc_delta2 = librosa.feature.delta(mfcc, order=2)

            # Combine all features
            combined_features = np.vstack([mfcc, mfcc_delta, mfcc_delta2])

            # Normalize per coefficient (important for accurate comparison)
            normalized_features = (
                combined_features - np.mean(combined_features, axis=1, keepdims=True)
            ) / (np.std(combined_features, axis=1, keepdims=True) + 1e-8)

            return normalized_features

        except Exception as e:
            raise ProcessingError(f"Failed to extract MFCC features: {str(e)}")

    @staticmethod
    def extract_tempo_and_beats(
        audio_data: np.ndarray, sr: int
    ) -> Tuple[float, np.ndarray]:
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
                y=audio_data, sr=sr, hop_length=512
            )

            # Convert beat frames to time
            beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=512)

            return float(tempo), beat_times

        except Exception as e:
            raise ProcessingError(f"Failed to extract tempo and beats: {str(e)}")

    @staticmethod
    def extract_onset_strength(audio_data: np.ndarray, sr: int) -> np.ndarray:
        """
        Extract onset strength envelope for rhythm analysis.

        Args:
            audio_data: Audio signal
            sr: Sample rate

        Returns:
            np.ndarray: Onset strength envelope
        """
        try:
            onset_env = librosa.onset.onset_strength(
                y=audio_data, sr=sr, hop_length=512
            )
            return onset_env
        except Exception as e:
            raise ProcessingError(f"Failed to extract onset strength: {str(e)}")

    @staticmethod
    def extract_chroma(audio_data: np.ndarray, sr: int) -> np.ndarray:
        """
        Extract chroma features for harmonic content analysis.

        Args:
            audio_data: Audio signal
            sr: Sample rate

        Returns:
            np.ndarray: Chroma features
        """
        try:
            chroma = librosa.feature.chroma_cqt(y=audio_data, sr=sr, hop_length=512)
            return chroma
        except Exception as e:
            raise ProcessingError(f"Failed to extract chroma features: {str(e)}")

    @staticmethod
    def compare_pitch_sequences(
        ref_pitch: np.ndarray,
        user_pitch: np.ndarray,
        ref_times: np.ndarray,
        user_times: np.ndarray,
        ref_duration: float,
        user_duration: float,
    ) -> Dict[str, Any]:
        """
        Compare pitch sequences with full reference visualization.
        
        ✅ NEW APPROACH: Analyze full reference but show where user stopped singing
        - User pitch shown for duration they sang
        - Zero/null values shown after user stops
        - Full reference context preserved

        Args:
            ref_pitch: Reference pitch sequence
            user_pitch: User pitch sequence
            ref_times: Reference time stamps
            user_times: User time stamps
            ref_duration: Reference total duration
            user_duration: User recording duration

        Returns:
            dict: Pitch comparison results with full reference visualization
        """
        try:
            # Remove zero values (unvoiced segments) for ANALYSIS only
            ref_mask = ref_pitch > 0
            user_mask = user_pitch > 0

            if not np.any(ref_mask) or not np.any(user_mask):
                return {
                    "pitch_similarity": 0.0,
                    "notes_matched": 0,
                    "notes_total": 1,
                    "pitch_over_time": [],
                    "avg_semitone_error": 0.0,
                }

            # Get clean pitches for analysis (only the overlapping portion)
            ref_pitch_clean = ref_pitch[ref_mask]
            ref_times_clean = ref_times[ref_mask]
            user_pitch_clean = user_pitch[user_mask]
            user_times_clean = user_times[user_mask]

            # ✅ NEW: For ANALYSIS, only compare the overlapping duration
            # Truncate reference to user duration for fair scoring
            ref_analysis_mask = ref_times_clean <= user_duration
            ref_pitch_for_analysis = ref_pitch_clean[ref_analysis_mask]
            ref_times_for_analysis = ref_times_clean[ref_analysis_mask]

            # Convert to semitones for better comparison
            ref_semitones = 12 * np.log2(ref_pitch_for_analysis / 440.0)
            user_semitones = 12 * np.log2(user_pitch_clean / 440.0)

            # Use DTW or direct mapping based on duration similarity
            duration_ratio = len(user_semitones) / len(ref_semitones) if len(ref_semitones) > 0 else 0
            
            if 0.8 <= duration_ratio <= 1.2:
                # Close durations - use DTW
                try:
                    distance, path = fastdtw(
                        ref_semitones.reshape(-1, 1),
                        user_semitones.reshape(-1, 1),
                        dist=euclidean,
                    )
                except:
                    min_len = min(len(ref_semitones), len(user_semitones))
                    path = list(zip(range(min_len), range(min_len)))
            else:
                # Different durations - use direct mapping
                min_len = min(len(ref_semitones), len(user_semitones))
                path = list(zip(range(min_len), range(min_len)))

            # Calculate semitone errors for scoring
            semitone_errors = []
            notes_matched = 0
            tolerance_semitones = 1.0

            for i, j in path:
                if i < len(ref_semitones) and j < len(user_semitones):
                    error = abs(ref_semitones[i] - user_semitones[j])
                    semitone_errors.append(error)
                    if error <= tolerance_semitones:
                        notes_matched += 1

            # Calculate scores based on analyzed portion
            avg_error = np.mean(semitone_errors) if semitone_errors else 0
            pitch_similarity = max(0, 100 * np.exp(-avg_error / 2))

            # ✅ NEW: Create pitch_over_time with FULL reference but show where user stopped
            pitch_over_time = []
            
            # Sample reference times evenly (up to 100 points across FULL duration)
            max_points = 100
            ref_indices = np.linspace(0, len(ref_times) - 1, min(max_points, len(ref_times)), dtype=int)
            
            for ref_idx in ref_indices:
                ref_time = float(ref_times[ref_idx])
                ref_pitch_val = float(ref_pitch[ref_idx])
                
                # Find corresponding user pitch at this time
                if ref_time <= user_duration:
                    # User was still singing at this time
                    # Find closest user pitch value
                    user_time_diffs = np.abs(user_times - ref_time)
                    closest_user_idx = np.argmin(user_time_diffs)
                    
                    if user_time_diffs[closest_user_idx] < 0.5:  # Within 0.5s
                        user_pitch_val = float(user_pitch[closest_user_idx])
                        
                        # Calculate difference if both have valid pitches
                        if ref_pitch_val > 0 and user_pitch_val > 0:
                            ref_semi = 12 * np.log2(ref_pitch_val / 440.0)
                            user_semi = 12 * np.log2(user_pitch_val / 440.0)
                            diff_semitones = abs(ref_semi - user_semi)
                        else:
                            diff_semitones = 0.0
                    else:
                        # No close user pitch found
                        user_pitch_val = 0.0
                        diff_semitones = 0.0
                else:
                    # ✅ User stopped singing - show zero/null
                    user_pitch_val = 0.0  # Or None/null in frontend
                    diff_semitones = 0.0
                
                pitch_over_time.append({
                    "time": ref_time,
                    "ref_pitch": ref_pitch_val,
                    "user_pitch": user_pitch_val,
                    "difference_semitones": float(diff_semitones),
                    "user_singing": ref_time <= user_duration  # ✅ NEW: Flag to indicate if user was singing
                })

            return {
                "pitch_similarity": float(pitch_similarity),
                "notes_matched": int(notes_matched),
                "notes_total": len(path),
                "pitch_over_time": pitch_over_time,
                "avg_semitone_error": float(avg_error),
                "user_duration": float(user_duration),
                "ref_duration": float(ref_duration),
            }

        except Exception as e:
            raise ProcessingError(f"Failed to compare pitch sequences: {str(e)}")

    @staticmethod
    def compare_rhythm(
        ref_tempo: float,
        user_tempo: float,
        ref_beats: np.ndarray,
        user_beats: np.ndarray,
        ref_onset: np.ndarray,
        user_onset: np.ndarray,
    ) -> Dict[str, Any]:
        """
        Compare rhythmic patterns with improved beat alignment.

        Args:
            ref_tempo: Reference tempo
            user_tempo: User tempo
            ref_beats: Reference beat times
            user_beats: User beat times
            ref_onset: Reference onset strength
            user_onset: User onset strength

        Returns:
            dict: Rhythm comparison results
        """
        try:
            # 1. Tempo similarity (0-100)
            tempo_diff = abs(ref_tempo - user_tempo)
            tempo_similarity = max(0, 100 - (tempo_diff / ref_tempo * 100) * 2)

            # 2. Onset pattern correlation
            min_len = min(len(ref_onset), len(user_onset))
            if min_len > 0:
                ref_onset_norm = ref_onset[:min_len] / (
                    np.max(ref_onset[:min_len]) + 1e-8
                )
                user_onset_norm = user_onset[:min_len] / (
                    np.max(user_onset[:min_len]) + 1e-8
                )

                onset_correlation = np.corrcoef(ref_onset_norm, user_onset_norm)[0, 1]
                onset_score = max(0, onset_correlation * 100)
            else:
                onset_score = 0

            # 3. Beat alignment
            if len(ref_beats) > 0 and len(user_beats) > 0:
                min_beats = min(len(ref_beats), len(user_beats))

                # Scale user beats to match reference duration
                ref_duration = ref_beats[-1] if len(ref_beats) > 0 else 1
                user_duration = user_beats[-1] if len(user_beats) > 0 else 1

                if user_duration > 0:
                    user_beats_scaled = user_beats * (ref_duration / user_duration)
                else:
                    user_beats_scaled = user_beats

                # Calculate timing errors
                timing_errors = []
                for i in range(min_beats):
                    expected_time = ref_beats[i]
                    actual_time = user_beats_scaled[min(i, len(user_beats_scaled) - 1)]
                    timing_errors.append(abs(actual_time - expected_time))

                if timing_errors:
                    avg_timing_error = np.mean(timing_errors)
                    beat_alignment = max(0, 100 - (avg_timing_error * 500))
                else:
                    beat_alignment = 0
            else:
                beat_alignment = 0

            # Combined rhythm accuracy
            rhythm_accuracy = (
                tempo_similarity * 0.4 + onset_score * 0.3 + beat_alignment * 0.3
            )

            return {
                "tempo_similarity": float(tempo_similarity),
                "tempo_difference": float(tempo_diff),
                "beat_alignment": float(beat_alignment),
                "onset_correlation": float(onset_score),
                "rhythm_accuracy": float(rhythm_accuracy),
            }

        except Exception as e:
            raise ProcessingError(f"Failed to compare rhythm: {str(e)}")

    @staticmethod
    def compare_timbre(ref_mfcc: np.ndarray, user_mfcc: np.ndarray) -> Dict[str, Any]:
        """
        Compare timbre using MFCC features with improved analysis.

        Args:
            ref_mfcc: Reference MFCC features
            user_mfcc: User MFCC features

        Returns:
            dict: Timbre comparison results
        """
        try:
            # Align sequences to same length
            min_len = min(ref_mfcc.shape[1], user_mfcc.shape[1])
            ref_mfcc_aligned = ref_mfcc[:, :min_len]
            user_mfcc_aligned = user_mfcc[:, :min_len]

            # Frame-by-frame similarity
            frame_similarities = []
            for i in range(min_len):
                ref_frame = ref_mfcc_aligned[:, i]
                user_frame = user_mfcc_aligned[:, i]

                cos_sim = np.dot(ref_frame, user_frame) / (
                    np.linalg.norm(ref_frame) * np.linalg.norm(user_frame) + 1e-8
                )
                frame_similarities.append(cos_sim)

            avg_frame_similarity = (
                np.mean(frame_similarities) if frame_similarities else 0
            )

            # Overall distribution similarity
            ref_avg = np.mean(ref_mfcc, axis=1)
            user_avg = np.mean(user_mfcc, axis=1)

            overall_similarity = 1 - cosine(ref_avg, user_avg)

            # Combine both measures
            timbre_similarity = (
                avg_frame_similarity * 0.6 + overall_similarity * 0.4
            ) * 100

            return {
                "similarity": float(max(0, timbre_similarity)),
                "frame_similarity": float(avg_frame_similarity * 100),
                "overall_similarity": float(overall_similarity * 100),
            }

        except Exception as e:
            raise ProcessingError(f"Failed to compare timbre: {str(e)}")

    @staticmethod
    def compare_timing(
        ref_chroma: np.ndarray,
        user_chroma: np.ndarray,
        ref_duration: float,
        user_duration: float,
    ) -> Dict[str, Any]:
        """
        Compare timing and synchronization using chroma features.

        Args:
            ref_chroma: Reference chroma features
            user_chroma: User chroma features
            ref_duration: Reference duration
            user_duration: User duration

        Returns:
            dict: Timing comparison results
        """
        try:
            # Duration similarity
            duration_diff = abs(ref_duration - user_duration)
            duration_score = max(0, 100 - (duration_diff / ref_duration * 100) * 2)

            # Chroma synchronization (only for overlapping portion)
            min_len = min(ref_chroma.shape[1], user_chroma.shape[1])
            if min_len > 0:
                ref_chroma_aligned = ref_chroma[:, :min_len]
                user_chroma_aligned = user_chroma[:, :min_len]

                chroma_similarities = []
                for i in range(min_len):
                    ref_frame = ref_chroma_aligned[:, i]
                    user_frame = user_chroma_aligned[:, i]

                    sim = np.dot(ref_frame, user_frame) / (
                        np.linalg.norm(ref_frame) * np.linalg.norm(user_frame) + 1e-8
                    )
                    chroma_similarities.append(sim)

                avg_chroma_sim = (
                    np.mean(chroma_similarities) if chroma_similarities else 0
                )
                sync_score = max(0, avg_chroma_sim * 100)
            else:
                sync_score = 0

            # Combined timing accuracy
            timing_accuracy = duration_score * 0.4 + sync_score * 0.6

            return {
                "timing_accuracy": float(timing_accuracy),
                "duration_similarity": float(duration_score),
                "synchronization": float(sync_score),
                "ref_duration": float(ref_duration),
                "user_duration": float(user_duration),
                "duration_difference": float(duration_diff),
            }

        except Exception as e:
            raise ProcessingError(f"Failed to compare timing: {str(e)}")

    @staticmethod
    def analyze_singing_similarity(
        reference_file: str, user_file: str
    ) -> Dict[str, Any]:
        """
        Complete analysis of singing similarity between reference and user recordings.
        
        ✅ NEW APPROACH: Full reference visualization with clear indication of where user stopped
        - Analyzes only overlapping portion for fair scoring
        - Shows full reference for context
        - Shows user pitch as zero after they stop singing

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

            # Calculate durations
            ref_duration = len(ref_audio) / sr
            user_duration = len(user_audio) / sr
            
            # Check duration mismatch
            duration_ratio = user_duration / ref_duration if ref_duration > 0 else 0
            duration_warning = None
            
            if duration_ratio < 0.5:
                duration_warning = {
                    "type": "critical",
                    "message": f"Recording is very incomplete ({user_duration:.1f}s of {ref_duration:.1f}s)",
                    "coverage": f"{duration_ratio * 100:.1f}%",
                    "recommendation": "Please record the full segment for accurate analysis"
                }
            elif duration_ratio < 0.8:
                duration_warning = {
                    "type": "warning",
                    "message": f"Recording is incomplete ({user_duration:.1f}s of {ref_duration:.1f}s)",
                    "coverage": f"{duration_ratio * 100:.1f}%",
                    "recommendation": "For best results, record the full segment"
                }
            
            # ✅ NEW: Extract features from FULL reference (no truncation)
            ref_pitch, ref_times, ref_confidence = AudioAnalyzer.extract_pitch(
                ref_audio, sr
            )
            
            # For other features, truncate to user duration for fair scoring
            ref_audio_for_scoring = ref_audio[:int(user_duration * sr)]
            
            ref_mfcc = AudioAnalyzer.extract_mfcc(ref_audio_for_scoring, sr)
            ref_tempo, ref_beats = AudioAnalyzer.extract_tempo_and_beats(ref_audio_for_scoring, sr)
            ref_onset = AudioAnalyzer.extract_onset_strength(ref_audio_for_scoring, sr)
            ref_chroma = AudioAnalyzer.extract_chroma(ref_audio_for_scoring, sr)

            # Extract features from user recording
            user_pitch, user_times, user_confidence = AudioAnalyzer.extract_pitch(
                user_audio, sr
            )
            user_mfcc = AudioAnalyzer.extract_mfcc(user_audio, sr)
            user_tempo, user_beats = AudioAnalyzer.extract_tempo_and_beats(
                user_audio, sr
            )
            user_onset = AudioAnalyzer.extract_onset_strength(user_audio, sr)
            user_chroma = AudioAnalyzer.extract_chroma(user_audio, sr)

            # Compare pitch (with full reference visualization)
            pitch_analysis = AudioAnalyzer.compare_pitch_sequences(
                ref_pitch, user_pitch, ref_times, user_times, ref_duration, user_duration
            )

            # Compare other features (using truncated reference for scoring)
            rhythm_analysis = AudioAnalyzer.compare_rhythm(
                ref_tempo, user_tempo, ref_beats, user_beats, ref_onset, user_onset
            )

            timbre_analysis = AudioAnalyzer.compare_timbre(ref_mfcc, user_mfcc)

            timing_analysis = AudioAnalyzer.compare_timing(
                ref_chroma, user_chroma, ref_duration, user_duration  # Use user_duration for both
            )

            # Extract final scores
            pitch_score = pitch_analysis["pitch_similarity"]
            rhythm_score = rhythm_analysis["rhythm_accuracy"]
            tone_score = timbre_analysis["similarity"]
            timing_score = timing_analysis["timing_accuracy"]

            # Calculate weighted overall score
            overall_score = (
                pitch_score * 0.30
                + rhythm_score * 0.25
                + tone_score * 0.25
                + timing_score * 0.20
            )

            result = {
                "overall_score": float(overall_score),
                "pitch_accuracy": float(pitch_score),
                "rhythm_accuracy": float(rhythm_score),
                "tone_similarity": float(tone_score),
                "timing_accuracy": float(timing_score),
                "detailed_analysis": {
                    "pitch": {
                        "similarity": float(pitch_score),
                        "notes_matched": int(pitch_analysis["notes_matched"]),
                        "notes_total": int(pitch_analysis["notes_total"]),
                        "avg_semitone_error": float(
                            pitch_analysis["avg_semitone_error"]
                        ),
                        "pitch_over_time": pitch_analysis["pitch_over_time"],
                        "user_duration": float(user_duration),
                        "ref_duration": float(ref_duration),
                    },
                    "rhythm": {
                        "similarity": float(rhythm_score),
                        "tempo_difference": float(rhythm_analysis["tempo_difference"]),
                        "beat_alignment": float(rhythm_analysis["beat_alignment"]),
                        "onset_correlation": float(
                            rhythm_analysis["onset_correlation"]
                        ),
                        "ref_tempo": float(ref_tempo),
                        "user_tempo": float(user_tempo),
                    },
                    "timbre": {
                        "similarity": float(tone_score),
                        "frame_similarity": float(timbre_analysis["frame_similarity"]),
                        "overall_similarity": float(
                            timbre_analysis["overall_similarity"]
                        ),
                    },
                    "timing": {
                        "similarity": float(timing_score),
                        "duration_similarity": float(
                            timing_analysis["duration_similarity"]
                        ),
                        "synchronization": float(timing_analysis["synchronization"]),
                        "ref_duration": float(ref_duration),
                        "user_duration": float(user_duration),
                        "duration_difference": float(
                            timing_analysis["duration_difference"]
                        ),
                    },
                },
            }
            
            if duration_warning:
                result["duration_warning"] = duration_warning
            
            return result

        except Exception as e:
            raise ProcessingError(f"Failed to analyze singing similarity: {str(e)}")