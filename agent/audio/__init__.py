"""
Audio processing, VAD, and playback primitives for the AI Call Agent.
"""

from agent.audio.processor import AudioProcessor
from agent.audio.vad import VoiceActivityDetector
from agent.audio.player import AudioPlayer

__all__ = ["AudioProcessor", "VoiceActivityDetector", "AudioPlayer"]
