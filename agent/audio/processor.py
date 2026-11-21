"""
Audio format converter, resampler, and gain controller for live call audio.
Supports bidirectional conversion between:
- Telephony G.711 µ-law (8kHz)
- Gemini Live PCM (16kHz in, 24kHz out, 16-bit signed mono little-endian)
- System microphone/speaker audio (16kHz / 24kHz / 48kHz)
"""

import math
import numpy as np
from scipy import signal
from typing import Tuple


# Precomputed G.711 µ-law decode table (8-bit µ-law -> 16-bit signed int)
# ITU-T G.711 standard specification
def _build_mulaw_tables() -> Tuple[np.ndarray, np.ndarray]:
    """Generate exact G.711 mu-law decode table (256 entries) and fast encode table."""
    # Decode table: map uint8 (0..255) to int16 (-32768..32767)
    decode_table = np.zeros(256, dtype=np.int16)
    for i in range(256):
        inverted = ~i & 0xFF
        sign = inverted & 0x80
        exponent = (inverted >> 4) & 0x07
        mantissa = inverted & 0x0F
        sample = ((mantissa << 3) + 0x84) << exponent
        sample -= 0x84
        if sign == 0:
            sample = -sample
        decode_table[i] = np.clip(sample, -32768, 32767)

    # Encode lookup table: for 16-bit values mapped to 8-bit mulaw
    # Standard G.711 mu-law compression equation
    # y = sgn(x) * ln(1 + mu*|x|) / ln(1 + mu) where mu = 255
    bias = 0x84
    clip = 32635
    encode_lut = np.zeros(65536, dtype=np.uint8)
    for sample in range(-32768, 32768):
        sign = 0x80 if sample >= 0 else 0x00
        mag = abs(sample)
        if mag > clip:
            mag = clip
        mag += bias
        
        exponent = 7
        for exp in range(8):
            if mag <= (0x1F << (exp + 3)):
                exponent = exp
                break
        
        mantissa = (mag >> (exponent + 3)) & 0x0F
        byte_val = ~(sign | (exponent << 4) | mantissa) & 0xFF
        encode_lut[sample + 32768] = byte_val

    return decode_table, encode_lut


_MULAW_DECODE_TABLE, _MULAW_ENCODE_TABLE = _build_mulaw_tables()


class AudioProcessor:
    """
    High-performance audio processor for real-time streaming pipelines.
    """

    @staticmethod
    def mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
        """
        Convert G.711 mu-law audio (8kHz) to 16-bit signed Linear PCM (8kHz).
        """
        if not mulaw_bytes:
            return b""
        raw_uint8 = np.frombuffer(mulaw_bytes, dtype=np.uint8)
        pcm_int16 = _MULAW_DECODE_TABLE[raw_uint8]
        return pcm_int16.tobytes()

    @staticmethod
    def pcm16_to_mulaw(pcm_bytes: bytes) -> bytes:
        """
        Convert 16-bit signed Linear PCM to 8-bit G.711 mu-law.
        """
        if not pcm_bytes:
            return b""
        pcm_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
        # Shift int16 values (-32768..32767) to index (0..65535)
        indices = (pcm_int16.astype(np.int32) + 32768).astype(np.uint16)
        mulaw_uint8 = _MULAW_ENCODE_TABLE[indices]
        return mulaw_uint8.tobytes()

    @staticmethod
    def resample_pcm(pcm_bytes: bytes, in_rate: int, out_rate: int) -> bytes:
        """
        Resample 16-bit mono PCM bytes from in_rate to out_rate using polyphase filter.
        """
        if not pcm_bytes or in_rate == out_rate:
            return pcm_bytes

        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        if len(samples) == 0:
            return b""

        gcd = math.gcd(in_rate, out_rate)
        up = out_rate // gcd
        down = in_rate // gcd

        resampled = signal.resample_poly(samples, up, down)
        resampled_int16 = np.clip(resampled, -32768, 32767).astype(np.int16)
        return resampled_int16.tobytes()

    @classmethod
    def telephony_to_gemini(cls, mulaw_8k_bytes: bytes) -> bytes:
        """
        Full inbound pipeline for telephony:
        G.711 mu-law 8kHz -> Linear PCM 16-bit 16kHz (Gemini Live standard).
        """
        pcm16_8k = cls.mulaw_to_pcm16(mulaw_8k_bytes)
        pcm16_16k = cls.resample_pcm(pcm16_8k, in_rate=8000, out_rate=16000)
        return pcm16_16k

    @classmethod
    def gemini_to_telephony(cls, pcm16_24k_bytes: bytes) -> bytes:
        """
        Full outbound pipeline for telephony:
        Gemini output (24kHz 16-bit PCM) -> G.711 mu-law 8kHz.
        """
        pcm16_8k = cls.resample_pcm(pcm16_24k_bytes, in_rate=24000, out_rate=8000)
        mulaw_8k = cls.pcm16_to_mulaw(pcm16_8k)
        return mulaw_8k

    @classmethod
    def gemini_to_speaker(cls, pcm16_24k_bytes: bytes, target_rate: int = 16000) -> bytes:
        """
        Convert Gemini output (24kHz) to target speaker rate (e.g. 16kHz or 48kHz).
        """
        if target_rate == 24000:
            return pcm16_24k_bytes
        return cls.resample_pcm(pcm16_24k_bytes, in_rate=24000, out_rate=target_rate)

    @staticmethod
    def calculate_rms(pcm_bytes: bytes) -> float:
        """
        Calculate normalized RMS (Root Mean Square) energy of 16-bit PCM buffer (0.0 to 1.0).
        """
        if not pcm_bytes:
            return 0.0
        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        mean_square = np.mean(samples ** 2)
        return float(np.sqrt(mean_square)) if mean_square > 0 else 0.0

    @staticmethod
    def apply_gain(pcm_bytes: bytes, gain_factor: float) -> bytes:
        """
        Apply software volume gain multiplier to 16-bit PCM audio.
        """
        if not pcm_bytes or gain_factor == 1.0:
            return pcm_bytes
        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        samples = np.clip(samples * gain_factor, -32768, 32767).astype(np.int16)
        return samples.tobytes()
