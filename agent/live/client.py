"""
Asynchronous WebSocket Client for Google Gemini Multimodal Live API.
"""

import json
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional
import websockets

from agent.config import settings
from agent.live.protocol import GeminiLiveProtocol

logger = logging.getLogger("GeminiLiveClient")


class GeminiLiveClient:
    """
    Manages the real-time bidirectional WebSocket connection with Gemini Live API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        voice_name: Optional[str] = None,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        on_audio_received: Optional[Callable[[bytes], None]] = None,
        on_text_received: Optional[Callable[[str], None]] = None,
        on_turn_complete: Optional[Callable[[], None]] = None,
        on_interrupted: Optional[Callable[[], None]] = None,
        on_tool_call: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
    ):
        self.api_key = api_key or settings.gemini_api_key.get_secret_value()
        self.model = model or settings.gemini_model
        self.voice_name = voice_name or settings.gemini_voice_name
        self.system_instruction = system_instruction or settings.get_system_instruction()
        self.tools = tools

        # Callbacks
        self.on_audio_received = on_audio_received
        self.on_text_received = on_text_received
        self.on_turn_complete = on_turn_complete
        self.on_interrupted = on_interrupted
        self.on_tool_call = on_tool_call

        # State
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._receive_task: Optional[asyncio.Task] = None
        self.is_connected = False
        self.setup_complete = asyncio.Event()

    async def connect(self) -> bool:
        """
        Establish WebSocket connection and complete the Gemini Live setup handshake.
        """
        # Construct endpoint URL with API key
        uri = f"{settings.gemini_live_uri}?key={self.api_key}"
        logger.info(f"Connecting to Gemini Live API with model={self.model}, voice={self.voice_name}...")

        try:
            self.websocket = await websockets.connect(
                uri,
                max_size=10 * 1024 * 1024,
                ping_interval=20,
                ping_timeout=20
            )
            self.is_connected = True

            # Send Setup Message
            setup_msg = GeminiLiveProtocol.build_setup_message(
                model=self.model,
                system_instruction=self.system_instruction,
                voice_name=self.voice_name,
                response_modalities=["AUDIO"],
                tools=self.tools
            )
            await self.websocket.send(json.dumps(setup_msg))

            # Start background receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())

            # Wait for setup confirmation from server
            try:
                await asyncio.wait_for(self.setup_complete.wait(), timeout=10.0)
                logger.info("Gemini Live session initialized successfully!")
                return True
            except asyncio.TimeoutError:
                logger.warning("Setup handshake timeout; continuing in optimistic state.")
                return True

        except Exception as e:
            logger.error(f"Failed to connect to Gemini Live: {e}")
            self.is_connected = False
            return False

    async def send_audio(self, pcm16_bytes: bytes, rate: int = 16000) -> None:
        """
        Stream a 16-bit Linear PCM audio chunk to Gemini.
        """
        if not self.is_connected or not self.websocket:
            return

        msg = GeminiLiveProtocol.build_audio_chunk_message(pcm16_bytes, rate=rate)
        try:
            await self.websocket.send(json.dumps(msg))
        except Exception as e:
            logger.error(f"Error sending audio chunk: {e}")

    async def send_text(self, text: str, turn_complete: bool = True) -> None:
        """
        Send text content to Gemini.
        """
        if not self.is_connected or not self.websocket:
            return

        msg = GeminiLiveProtocol.build_text_message(text, turn_complete=turn_complete)
        try:
            await self.websocket.send(json.dumps(msg))
        except Exception as e:
            logger.error(f"Error sending text turn: {e}")

    async def send_tool_response(self, call_id: str, name: str, result: Dict[str, Any]) -> None:
        """
        Send function execution results back to Gemini.
        """
        if not self.is_connected or not self.websocket:
            return

        msg = GeminiLiveProtocol.build_tool_response_message(call_id, name, result)
        try:
            await self.websocket.send(json.dumps(msg))
        except Exception as e:
            logger.error(f"Error sending tool response: {e}")

    async def disconnect(self) -> None:
        """
        Gracefully terminate the WebSocket session.
        """
        self.is_connected = False
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None
        logger.info("Disconnected from Gemini Live API.")

    async def _receive_loop(self) -> None:
        """
        Continuous message processing loop.
        """
        try:
            while self.is_connected and self.websocket:
                raw_message = await self.websocket.recv()
                if not raw_message:
                    continue

                try:
                    data = json.loads(raw_message)
                except Exception:
                    continue

                parsed = GeminiLiveProtocol.parse_server_message(data)

                if parsed["is_setup_complete"]:
                    self.setup_complete.set()

                # Dispatch audio chunks
                if parsed["audio_chunks"] and self.on_audio_received:
                    for chunk in parsed["audio_chunks"]:
                        self.on_audio_received(chunk)

                # Dispatch text / transcription parts
                if parsed["text_parts"] and self.on_text_received:
                    full_text = " ".join(parsed["text_parts"])
                    self.on_text_received(full_text)

                # Dispatch tool calls
                if parsed["tool_calls"] and self.on_tool_call:
                    for tc in parsed["tool_calls"]:
                        self.on_tool_call(tc["id"], tc["name"], tc["args"])

                # Dispatch interruption notifications
                if parsed["interrupted"] and self.on_interrupted:
                    self.on_interrupted()

                # Dispatch turn complete
                if parsed["turn_complete"] and self.on_turn_complete:
                    self.on_turn_complete()

        except websockets.exceptions.ConnectionClosed:
            logger.info("Gemini Live WebSocket connection closed by remote.")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Exception in Gemini Live receive loop: {e}")
        finally:
            self.is_connected = False
