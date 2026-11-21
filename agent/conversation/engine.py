"""
Core Conversation Engine orchestrating audio input, Gemini Live Bidi streaming,
barge-in interruption handling, session memory, and tool execution.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from agent.config import settings
from agent.audio.processor import AudioProcessor
from agent.audio.vad import VoiceActivityDetector
from agent.audio.player import AudioPlayer
from agent.conversation.memory import SessionMemory
from agent.conversation.tools import ToolRegistry
from agent.live.client import GeminiLiveClient

logger = logging.getLogger("ConversationEngine")


class ConversationEngine:
    """
    End-to-end conversation coordinator for live voice calls.
    """

    def __init__(
        self,
        session_id: str,
        caller_id: Optional[str] = None,
        on_audio_out: Optional[Callable[[bytes], None]] = None,
        on_text_out: Optional[Callable[[str], None]] = None,
        on_user_speaking: Optional[Callable[[bool], None]] = None,
        on_interrupted: Optional[Callable[[], None]] = None,
        on_tool_event: Optional[Callable[[str, Dict[str, Any], Any], None]] = None,
        use_sounddevice_output: bool = False
    ):
        self.session_id = session_id
        self.caller_id = caller_id or "Anonymous Caller"
        self.on_audio_out = on_audio_out
        self.on_text_out = on_text_out
        self.on_user_speaking = on_user_speaking
        self.on_interrupted = on_interrupted
        self.on_tool_event = on_tool_event

        # Session memory & tools
        self.memory = SessionMemory(session_id=session_id, caller_id=self.caller_id)
        self.tools = ToolRegistry(memory=self.memory)

        # Output audio player with instant barge-in support
        self.player = AudioPlayer(
            sample_rate=settings.output_sample_rate,
            channels=1,
            on_interrupted=self._handle_local_interruption,
            use_sounddevice=use_sounddevice_output
        )

        # Voice Activity Detector for caller speech & barge-in
        self.vad = VoiceActivityDetector(
            sample_rate=settings.input_sample_rate,
            energy_threshold=settings.vad_energy_threshold,
            silence_duration_ms=settings.vad_silence_duration_ms,
            on_speech_start=self._on_caller_speech_start,
            on_speech_end=self._on_caller_speech_end
        )

        # Gemini Live Client
        self.client = GeminiLiveClient(
            model=settings.gemini_model,
            voice_name=settings.gemini_voice_name,
            system_instruction=settings.get_system_instruction(),
            tools=self.tools.get_tool_declarations(),
            on_audio_received=self._on_model_audio,
            on_text_received=self._on_model_text,
            on_turn_complete=self._on_model_turn_complete,
            on_interrupted=self._on_model_interrupted,
            on_tool_call=self._on_tool_call_received
        )

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.is_running = False

    async def start(self) -> bool:
        """Initialize and start the live conversation engine."""
        self._loop = asyncio.get_running_loop()
        self.is_running = True
        self.player.start()

        success = await self.client.connect()
        if not success:
            logger.error("Failed to connect conversation engine to Gemini Live.")
            self.player.stop()
            self.is_running = False
            return False

        logger.info(f"ConversationEngine started for session {self.session_id}")
        return True

    async def stop(self) -> None:
        """Stop the conversation engine and flush resources."""
        self.is_running = False
        self.player.stop()
        await self.client.disconnect()
        logger.info(f"ConversationEngine stopped for session {self.session_id}")

    async def feed_audio(self, pcm16_16k_bytes: bytes) -> None:
        """
        Feed an incoming 16kHz PCM audio frame from the caller.
        Runs VAD, handles interruptions, and forwards to Gemini Live.
        """
        if not self.is_running:
            return

        # Process frame through VAD
        self.vad.process_frame(pcm16_16k_bytes)

        # Forward audio to Gemini Live
        await self.client.send_audio(pcm16_16k_bytes, rate=settings.input_sample_rate)

    def _on_caller_speech_start(self) -> None:
        """
        Triggered when caller starts speaking.
        If the model or player is currently outputting speech, trigger BARGE-IN!
        """
        if self.on_user_speaking:
            self.on_user_speaking(True)

        if self.player.is_playing:
            logger.info("Caller interrupted model speech (barge-in detected)!")
            self.player.interrupt()
            if self.on_interrupted:
                self.on_interrupted()
            # If loop is available, we can send an empty turn or interruption signal
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.client.send_text(""),
                    self._loop
                )

    def _on_caller_speech_end(self) -> None:
        """Triggered when caller stops speaking after a voiced utterance."""
        logger.debug("Caller speech pause detected.")
        if self.on_user_speaking:
            self.on_user_speaking(False)

    def _on_model_audio(self, pcm24k_bytes: bytes) -> None:
        """
        Received a raw 24kHz PCM audio chunk from Gemini.
        """
        # Reset any past interruption state for this new turn
        self.player.reset_interruption()

        # Send to local speaker player if enabled
        self.player.put_audio(pcm24k_bytes)

        # Send to external sink (e.g. Telephony WebSocket queue)
        if self.on_audio_out:
            try:
                self.on_audio_out(pcm24k_bytes)
            except Exception as e:
                logger.error(f"Error in on_audio_out handler: {e}")

    def _on_model_text(self, text: str) -> None:
        """Model transcript segment received."""
        logger.info(f"[Agent]: {text}")
        self.memory.record_turn(speaker="agent", text=text)
        if self.on_text_out:
            self.on_text_out(text)

    def _on_model_turn_complete(self) -> None:
        """Model finished speaking current turn."""
        logger.debug("Model turn completed.")

    def _on_model_interrupted(self) -> None:
        """Gemini confirmed it halted its generation due to an interruption."""
        logger.info("Gemini Live confirmed turn was interrupted.")
        self.player.interrupt()
        if self.on_interrupted:
            self.on_interrupted()

    def _handle_local_interruption(self) -> None:
        """Callback when local player flushes its buffer."""
        pass

    def _on_tool_call_received(self, call_id: str, name: str, args: Dict[str, Any]) -> None:
        """
        Gemini requested tool execution.
        Schedules async execution and returns result.
        """
        logger.info(f"Tool call requested: {name}({args}) [id={call_id}]")
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._execute_and_reply_tool(call_id, name, args),
                self._loop
            )

    async def _execute_and_reply_tool(self, call_id: str, name: str, args: Dict[str, Any]) -> None:
        """Execute tool and send response back to Gemini."""
        result = await self.tools.execute_tool(name, args)
        logger.info(f"Tool {name} executed. Result: {result}")
        if self.on_tool_event:
            self.on_tool_event(name, args, result)
        await self.client.send_tool_response(call_id, name, result)
