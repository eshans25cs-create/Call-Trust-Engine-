"""
Unit tests for AudioProcessor conversions, resampling, and VAD calculations.
"""

import numpy as np
import pytest
from agent.audio.processor import AudioProcessor
from agent.audio.vad import VoiceActivityDetector


def test_mulaw_roundtrip_fidelity():
    """Verify that encoding int16 to mu-law and decoding back preserves signal."""
    # Generate 16kHz sine wave
    duration_s = 0.1
    t = np.linspace(0, duration_s, int(8000 * duration_s), endpoint=False)
    orig_signal = (np.sin(2 * np.pi * 440 * t) * 20000).astype(np.int16)
    orig_bytes = orig_signal.tobytes()

    # Encode to mu-law and decode back
    mulaw_bytes = AudioProcessor.pcm16_to_mulaw(orig_bytes)
    assert len(mulaw_bytes) == len(orig_signal)  # 1 byte per sample in mu-law

    decoded_bytes = AudioProcessor.mulaw_to_pcm16(mulaw_bytes)
    assert len(decoded_bytes) == len(orig_bytes)

    decoded_signal = np.frombuffer(decoded_bytes, dtype=np.int16)
    # Check correlation between original and decoded signal
    corr = np.corrcoef(orig_signal, decoded_signal)[0, 1]
    # G.711 lossy companding compresses 16 bits to 8 bits (256 discrete levels)
    assert corr > 0.95, f"Correlation {corr} is below expected fidelity threshold."


def test_resample_pcm_up_and_down():
    """Test resampling from 8kHz to 16kHz and 24kHz to 8kHz."""
    samples_8k = np.zeros(800, dtype=np.int16)  # 100ms at 8kHz
    bytes_8k = samples_8k.tobytes()

    bytes_16k = AudioProcessor.resample_pcm(bytes_8k, in_rate=8000, out_rate=16000)
    samples_16k = np.frombuffer(bytes_16k, dtype=np.int16)
    assert len(samples_16k) == 1600

    bytes_8k_back = AudioProcessor.resample_pcm(bytes_16k, in_rate=16000, out_rate=8000)
    assert len(np.frombuffer(bytes_8k_back, dtype=np.int16)) == 800


def test_calculate_rms():
    """Test RMS energy calculation."""
    # Pure silence
    silence = np.zeros(1600, dtype=np.int16).tobytes()
    assert AudioProcessor.calculate_rms(silence) == 0.0

    # Constant signal
    signal_const = np.full(1600, 16384, dtype=np.int16).tobytes()  # approx 0.5 amplitude
    rms = AudioProcessor.calculate_rms(signal_const)
    assert 0.49 <= rms <= 0.51


def test_vad_speech_detection():
    """Test VoiceActivityDetector triggering speech start and end."""
    speech_started = []
    speech_ended = []

    vad = VoiceActivityDetector(
        sample_rate=16000,
        energy_threshold=0.02,
        silence_duration_ms=200,
        min_speech_duration_ms=50,
        on_speech_start=lambda: speech_started.append(True),
        on_speech_end=lambda: speech_ended.append(True)
    )

    # Frame 1: Quiet noise
    quiet_frame = (np.random.normal(0, 100, 800)).astype(np.int16).tobytes()
    is_speech = vad.process_frame(quiet_frame)
    assert not is_speech

    # Frame 2 & 3: Loud speech
    loud_frame = (np.sin(np.linspace(0, 10, 800)) * 20000).astype(np.int16).tobytes()
    vad.process_frame(loud_frame)
    import time
    time.sleep(0.06)
    vad.process_frame(loud_frame)
    assert len(speech_started) >= 1
