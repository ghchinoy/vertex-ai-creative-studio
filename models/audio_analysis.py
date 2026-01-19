# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Audio analysis using librosa and parselmouth."""

import os
import tempfile

import librosa
import numpy as np
import parselmouth
from parselmouth.praat import call
from pydantic import BaseModel

from common.storage import download_from_gcs


class AudioMetrics(BaseModel):
    mean_pitch_hz: float = 0.0
    pitch_std_hz: float = 0.0
    pitch_range_hz: float = 0.0
    jitter_percent: float = 0.0
    shimmer_db: float = 0.0
    hnr_db: float = 0.0
    estimated_tempo_bpm: float = 0.0
    duration_sec: float = 0.0


def analyze_audio_file(gcs_uri: str) -> AudioMetrics:
    """Analyzes an audio file from GCS to extract technical metrics.
    """
    # Download audio bytes from GCS
    audio_bytes = download_from_gcs(gcs_uri)

    metrics = AudioMetrics()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
        temp_audio.write(audio_bytes)
        temp_audio_path = temp_audio.name

    try:
        # --- Parselmouth Analysis (Pitch, Voice Quality) ---
        snd = parselmouth.Sound(temp_audio_path)
        pitch = snd.to_pitch()
        pitch_values = pitch.selected_array["frequency"]
        voiced_pitch = pitch_values[pitch_values > 0]

        if len(voiced_pitch) > 0:
            metrics.mean_pitch_hz = float(np.mean(voiced_pitch))
            metrics.pitch_std_hz = float(np.std(voiced_pitch))
            metrics.pitch_range_hz = float(np.max(voiced_pitch) - np.min(voiced_pitch))

        # Voice quality metrics
        try:
            point_process = call(snd, "To PointProcess (periodic, cc)", 75, 500)
            jitter = (
                call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3) * 100
            )
            shimmer = call(
                [snd, point_process],
                "Get shimmer (local)",
                0,
                0,
                0.0001,
                0.02,
                1.3,
                1.6,
            )
            hnr = call(snd, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0).values.mean()

            metrics.jitter_percent = float(jitter) if not np.isnan(jitter) else 0.0
            metrics.shimmer_db = float(shimmer) if not np.isnan(shimmer) else 0.0
            metrics.hnr_db = float(hnr) if not np.isnan(hnr) else 0.0
        except Exception as e:
            print(f"Warning: Voice quality analysis failed: {e}")

        # --- Librosa Analysis (Rhythm, Duration) ---
        try:
            y, sr = librosa.load(temp_audio_path)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            if isinstance(tempo, np.ndarray):
                tempo = tempo[0]
            metrics.estimated_tempo_bpm = float(tempo)
            metrics.duration_sec = float(librosa.get_duration(y=y, sr=sr))
        except Exception as e:
            print(f"Warning: Librosa analysis failed: {e}")

    finally:
        # Clean up temp file
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

    return metrics
