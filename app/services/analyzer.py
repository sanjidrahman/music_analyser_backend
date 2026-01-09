import warnings
import numpy as np
import librosa
import scipy.signal
from scipy.spatial.distance import cosine, euclidean
from scipy.signal.windows import hann
from fastdtw import fastdtw
from typing import Dict, Any, Tuple

from ..utils.exceptions import ProcessingError

# Suppress warnings
warnings.filterwarnings("ignore")

# Fix scipy.signal.hann compatibility
scipy.signal.hann = hann


class AudioAnalyzer:
    """Service for analyzing audio similarity between reference and user recordings."""

    @staticmethod
    def load_and_preprocess_audio(
        file_path: str, target_sr: int = 22050
    ) -> Tuple[np.ndarray, int]:
        try:
            audio_data, sr = librosa.load(file_path, sr=target_sr, mono=True)
            audio_data, _ = librosa.effects.trim(audio_data, top_db=20)
            if np.max(np.abs(audio_data)) > 0:
                audio_data = audio_data / np.max(np.abs(audio_data))
            return audio_data, sr
        except Exception as e:
            raise ProcessingError(f"Failed to load audio file {file_path}: {str(e)}")

    @staticmethod
    def analyze_singing_similarity(
        reference_file: str, user_file: str
    ) -> Dict[str, Any]:
        """
        Comprehensive analysis comparing user recording to reference using DTW alignment.
        """
        try:
            # 1. Load audio and determine physical durations
            y_ref, sr = AudioAnalyzer.load_and_preprocess_audio(reference_file)
            y_user, _ = AudioAnalyzer.load_and_preprocess_audio(user_file, sr)

            ref_duration = float(librosa.get_duration(y=y_ref, sr=sr))
            user_duration = float(librosa.get_duration(y=y_user, sr=sr))

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

            # 2. Extract Alignment Features (Chroma CENS)
            chroma_ref = librosa.feature.chroma_cens(y=y_ref, sr=sr)
            chroma_user = librosa.feature.chroma_cens(y=y_user, sr=sr)

            # 3. Dynamic Time Warping (DTW)
            _, path = fastdtw(chroma_ref.T, chroma_user.T, dist=euclidean)
            path = np.array(path)

            # 4. Pitch Analysis (F0)
            hop_length = 512
            f0_ref, voiced_ref, _ = librosa.pyin(
                y_ref,
                fmin=librosa.note_to_hz("C2"),
                fmax=librosa.note_to_hz("C7"),
                sr=sr,
                hop_length=hop_length,
            )
            f0_user, voiced_user, _ = librosa.pyin(
                y_user,
                fmin=librosa.note_to_hz("C2"),
                fmax=librosa.note_to_hz("C7"),
                sr=sr,
                hop_length=hop_length,
            )

            # 5. Process Pitch & Timing Aligned Data with STRICT CUTOFF
            pitch_over_time = []
            semitone_errors = []
            notes_matched = 0

            # Sub-sample path for visualization
            for idx_ref, idx_user in path[::5]:
                # Calculate time based on the reference timeline
                current_time = float(idx_ref * hop_length / sr)

                p_ref = (
                    float(f0_ref[idx_ref])
                    if idx_ref < len(voiced_ref) and voiced_ref[idx_ref]
                    else 0.0
                )

                # Logic Fix: If current_time exceeds physical user_duration, force pitch to None
                if current_time <= user_duration:
                    p_user = (
                        float(f0_user[idx_user])
                        if idx_user < len(voiced_user) and voiced_user[idx_user]
                        else 0.0
                    )
                else:
                    p_user = None  # This will become 'null' in JSON, breaking the line in the chart

                diff_semi = 0.0
                if p_ref > 0 and p_user is not None and p_user > 0:
                    diff_semi = abs(12 * np.log2(p_user / p_ref))
                    semitone_errors.append(diff_semi)
                    if diff_semi < 0.5:
                        notes_matched += 1

                pitch_over_time.append(
                    {
                        "time": round(current_time, 3),
                        "ref_pitch": round(p_ref, 2),
                        "user_pitch": round(p_user, 2) if p_user is not None else None,
                        "difference_semitones": round(diff_semi, 2),
                        "user_singing": bool(p_user is not None and p_user > 0),
                    }
                )

            # 6. Rhythm & Timbre Features
            ref_tempo, _ = librosa.beat.beat_track(y=y_ref, sr=sr)
            user_tempo, _ = librosa.beat.beat_track(y=y_user, sr=sr)
            onset_ref = librosa.onset.onset_strength(y=y_ref, sr=sr)
            onset_user = librosa.onset.onset_strength(y=y_user, sr=sr)

            # Timbre via MFCC
            mfcc_ref = librosa.feature.mfcc(y=y_ref, sr=sr, n_mfcc=13)
            mfcc_user = librosa.feature.mfcc(y=y_user, sr=sr, n_mfcc=13)
            mfcc_user_warped = mfcc_user[:, path[:, 1]]
            mfcc_ref_warped = mfcc_ref[:, path[:, 0]]

            # 7. Final Scoring
            pitch_score = (
                max(0, 100 - (np.mean(semitone_errors) * 15)) if semitone_errors else 0
            )

            ideal_path = np.linspace(0, path[-1, 1], len(path))
            sync_error = np.mean(np.abs(path[:, 1] - ideal_path))
            timing_score = max(0, 100 - (sync_error * 0.5))

            tone_sim_frames = [
                1 - cosine(mfcc_ref_warped[:, i], mfcc_user_warped[:, i])
                for i in range(mfcc_ref_warped.shape[1])
            ]
            tone_score = np.mean(tone_sim_frames) * 100

            tempo_acc = max(0, 100 - abs(ref_tempo - user_tempo))
            min_o = min(len(onset_ref), len(onset_user))
            onset_corr = np.corrcoef(onset_ref[:min_o], onset_user[:min_o])[0, 1]
            rhythm_score = (tempo_acc * 0.5) + (max(0, onset_corr) * 50)

            overall_score = (
                (pitch_score * 0.4)
                + (rhythm_score * 0.2)
                + (tone_score * 0.2)
                + (timing_score * 0.2)
            )

            # 8. Result Construction
            result = {
                "overall_score": float(round(overall_score, 2)),
                "pitch_accuracy": float(round(pitch_score, 2)),
                "rhythm_accuracy": float(round(rhythm_score, 2)),
                "tone_similarity": float(round(tone_score, 2)),
                "timing_accuracy": float(round(timing_score, 2)),
                "detailed_analysis": {
                    "pitch": {
                        "similarity": float(round(pitch_score, 2)),
                        "notes_matched": int(notes_matched),
                        "notes_total": int(len(semitone_errors)),
                        "avg_semitone_error": (
                            float(round(np.mean(semitone_errors), 4))
                            if semitone_errors
                            else 0.0
                        ),
                        "pitch_over_time": pitch_over_time,
                        "user_duration": float(user_duration),
                        "ref_duration": float(ref_duration),
                    },
                    "rhythm": {
                        "similarity": float(round(rhythm_score, 2)),
                        "tempo_difference": float(
                            round(abs(ref_tempo - user_tempo), 2)
                        ),
                        "beat_alignment": float(round(timing_score, 2)),
                        "onset_correlation": (
                            float(round(onset_corr, 4))
                            if not np.isnan(onset_corr)
                            else 0.0
                        ),
                        "ref_tempo": float(ref_tempo),
                        "user_tempo": float(user_tempo),
                    },
                    "timbre": {
                        "similarity": float(round(tone_score, 2)),
                        "frame_similarity": float(
                            round(np.median(tone_sim_frames) * 100, 2)
                        ),
                        "overall_similarity": float(round(tone_score, 2)),
                    },
                    "timing": {
                        "similarity": float(round(timing_score, 2)),
                        "duration_similarity": float(
                            round(
                                (
                                    min(ref_duration, user_duration)
                                    / max(ref_duration, user_duration)
                                )
                                * 100,
                                2,
                            )
                        ),
                        "synchronization": float(round(timing_score, 2)),
                        "ref_duration": float(ref_duration),
                        "user_duration": float(user_duration),
                        "duration_difference": float(
                            round(abs(ref_duration - user_duration), 2)
                        ),
                    },
                },
            }

            # Add duration warning if exists
            if duration_warning:
                result["duration_warning"] = duration_warning

            return result

        except Exception as e:
            raise ProcessingError(f"Failed to analyze singing similarity: {str(e)}")