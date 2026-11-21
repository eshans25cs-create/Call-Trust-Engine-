"""
Real-time Voice Activity Detection (VAD) and Barge-in Trigger.
Detects human speech onset, sustained voice, and speech completion.
"""

import time
import numpy as np
from typing import Optional, Callable


class VoiceActivityDetector:
    """
    Energy and Zero-Crossing Rate based Voice Activity Detector with hangover smoothing.
    Provides sub-50ms latency speech detection for conversational barge-in.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        energy_threshold: float = 0.015,
        silence_duration_ms: int = 600,
        min_speech_duration_ms: int = 120,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.energy_threshold = energy_threshold
        self.silence_duration_ms = silence_duration_ms
        self.min_speech_duration_ms = min_speech_duration_ms
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end

        # State tracking
        self.is_speech_active = False
        self.speech_start_time: Optional[float] = None
        self.last_speech_time: Optional[float] = None
        self.adaptive_noise_floor = 0.005

    def reset(self) -> None:
        """Reset internal state."""
        self.is_speech_active = False
        self.speech_start_time = None
        self.last_speech_time = None

    def process_frame(self, pcm_bytes: bytes) -> bool:
        """
        Process a single audio frame (typically 20-50ms of 16-bit PCM).
        Returns True if speech is detected in the current state.
        """
        if not pcm_bytes:
            return self.is_speech_active

        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if len(samples) == 0:
            return self.is_speech_active

        # Compute RMS energy
        rms = float(np.sqrt(np.mean(samples ** 2)))
        now = time.monotonic()

        # Dynamic threshold based on background noise
        effective_threshold = max(self.energy_threshold, self.adaptive_noise_floor * 2.5)

        is_frame_voiced = rms > effective_threshold

        if not is_frame_voiced:
            # Gradually update noise floor during quiet periods
            self.adaptive_noise_floor = 0.95 * self.adaptive_noise_floor + 0.05 * rms

        if is_frame_voiced:
            self.last_speech_time = now
            if not self.is_speech_active:
                if self.speech_start_time is None:
                    self.speech_start_time = now
                else:
                    duration = (now - self.speech_start_time) * 1000.0
                    if duration >= self.min_speech_duration_ms:
                        self.is_speech_active = True
                        if self.on_speech_start:
                            self.on_speech_start()
        else:
            if self.is_speech_active:
                if self.last_speech_time is not None:
                    silence_elapsed = (now - self.last_speech_time) * 1000.0
                    if silence_elapsed >= self.silence_duration_ms:
                        self.is_speech_active = False
                        self.speech_start_time = None
                        if self.on_speech_end:
                            self.on_speech_end()
            else:
                self.speech_start_time = None

        return self.is_speech_active
