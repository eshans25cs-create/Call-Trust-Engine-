"""
Thread-safe audio output buffer and player with instantaneous barge-in flush.
Supports both local sounddevice output and streaming telephony sinks.
"""

import queue
import threading
import logging
from typing import Optional, Callable

logger = logging.getLogger("AudioPlayer")


class AudioPlayer:
    """
    Asynchronous audio queue player with instant interruption flushing.
    """

    def __init__(
        self,
        sample_rate: int = 24000,
        channels: int = 1,
        on_interrupted: Optional[Callable[[], None]] = None,
        use_sounddevice: bool = False
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_interrupted = on_interrupted
        self.use_sounddevice = use_sounddevice

        self._queue: queue.Queue = queue.Queue()
        self._is_playing = False
        self._is_interrupted = threading.Event()
        self._stop_event = threading.Event()
        self._stream = None
        self._worker_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the audio output player thread."""
        self._stop_event.clear()
        self._is_interrupted.clear()

        if self.use_sounddevice:
            try:
                import sounddevice as sd
                self._stream = sd.RawOutputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="int16",
                    blocksize=1024
                )
                self._stream.start()
            except Exception as e:
                logger.warning(f"Failed to initialize local sounddevice output: {e}. Running in non-blocking sink mode.")
                self.use_sounddevice = False

        self._worker_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._worker_thread.start()

    def stop(self) -> None:
        """Stop playback and clean up resources."""
        self._stop_event.set()
        self.interrupt()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def put_audio(self, pcm_bytes: bytes) -> None:
        """Queue raw PCM bytes for playback."""
        if self._is_interrupted.is_set():
            return
        if pcm_bytes:
            self._queue.put(pcm_bytes)

    def interrupt(self) -> None:
        """
        Instantaneous Barge-in / Interruption handler.
        Flushes all queued audio frames immediately and silences active output.
        """
        self._is_interrupted.set()
        # Empty the queue immediately
        try:
            while not self._queue.empty():
                self._queue.get_nowait()
                self._queue.task_done()
        except Exception:
            pass

        self._is_playing = False
        if self.on_interrupted:
            try:
                self.on_interrupted()
            except Exception as e:
                logger.error(f"Error in on_interrupted callback: {e}")

    def reset_interruption(self) -> None:
        """Clear interruption state to accept new incoming model turn."""
        self._is_interrupted.clear()

    @property
    def is_playing(self) -> bool:
        """Return True if there is audio actively being output or queued."""
        return self._is_playing or not self._queue.empty()

    def _playback_loop(self) -> None:
        """Continuous consumer loop."""
        while not self._stop_event.is_set():
            try:
                chunk = self._queue.get(timeout=0.05)
            except queue.Empty:
                self._is_playing = False
                continue

            if self._is_interrupted.is_set():
                self._queue.task_done()
                self._is_playing = False
                continue

            self._is_playing = True
            if self._stream and self.use_sounddevice:
                try:
                    self._stream.write(chunk)
                except Exception as e:
                    logger.error(f"Playback write error: {e}")
            self._queue.task_done()
