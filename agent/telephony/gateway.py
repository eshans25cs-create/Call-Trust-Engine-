"""
FastAPI & WebSocket Telephony Gateway for Twilio, Telnyx, and SIP Media Streams.
Connects real cellular and landline phone calls directly to the Gemini Live AI Agent.
"""

import asyncio
import base64
import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from agent.config import settings
from agent.audio.processor import AudioProcessor
from agent.conversation.engine import ConversationEngine
from agent.telephony.twiml import generate_twiml_stream_response

logger = logging.getLogger("TelephonyGateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.loop = asyncio.get_running_loop()
    yield


def create_telephony_app() -> FastAPI:
    """
    Factory creating the FastAPI telephony gateway application.
    """
    app = FastAPI(
        title="Gemini Live Telephony Gateway",
        description="Bidirectional real-time telephony stream bridge for Google Gemini Live",
        version="1.0.0",
        lifespan=lifespan
    )

    # Active call engines keyed by stream_sid
    active_sessions: Dict[str, ConversationEngine] = {}

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return f"""
        <html>
            <head><title>Gemini Live AI Call Agent</title></head>
            <body style="font-family:sans-serif; padding: 2rem;">
                <h2>Gemini Live Telephony Gateway Active</h2>
                <p>Status: <strong>Online</strong></p>
                <p>Voice Persona: <strong>{settings.gemini_voice_name}</strong></p>
                <p>AI Model: <strong>{settings.gemini_model}</strong></p>
                <p>Webhook URL for Inbound Calls: <code>{settings.public_base_url}/voice/incoming</code></p>
                <p>Media Stream Endpoint: <code>{settings.public_base_url.replace('http', 'ws')}/media-stream</code></p>
            </body>
        </html>
        """

    @app.post("/voice/incoming")
    async def incoming_call(request: Request) -> Response:
        """
        Twilio / SIP Voice Webhook.
        Answers incoming phone call and connects it to the bidirectional media stream.
        """
        form_data = await request.form()
        caller = form_data.get("From", "Unknown Caller")
        call_sid = form_data.get("CallSid", "UnknownSid")
        logger.info(f"Incoming call received: CallSid={call_sid}, From={caller}")

        # Derive WebSocket URL
        base_url = settings.public_base_url.rstrip("/")
        ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://") + "/media-stream"

        greeting = None
        if settings.enable_ai_disclosure:
            greeting = f"Hello. You are speaking with {settings.agent_name}, an automated AI voice assistant. This call is processed in real time."

        twiml_response = generate_twiml_stream_response(
            websocket_url=ws_url,
            greeting_text=greeting
        )
        return Response(content=twiml_response, media_type="application/xml")

    @app.post("/voice/status")
    async def call_status(request: Request) -> Dict[str, str]:
        """Track call completion status."""
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        call_status = form_data.get("CallStatus")
        call_duration = form_data.get("CallDuration")
        logger.info(f"Call {call_sid} status update: {call_status} (Duration: {call_duration}s)")
        return {"status": "received"}

    @app.websocket("/media-stream")
    async def media_stream_endpoint(websocket: WebSocket):
        """
        Bidirectional audio streaming WebSocket endpoint.
        Receives G.711 mu-law 8kHz audio from telephone carrier,
        translates to 16kHz PCM, and delivers 24kHz -> 8kHz AI audio back.
        """
        await websocket.accept()
        logger.info("Telephony Media Stream WebSocket connected.")

        stream_sid: Optional[str] = None
        call_sid: Optional[str] = None
        engine: Optional[ConversationEngine] = None

        async def send_audio_to_telephony(pcm24k_bytes: bytes) -> None:
            """Callback from ConversationEngine when Gemini outputs speech."""
            if not stream_sid:
                return

            # Convert 24kHz PCM from Gemini to 8kHz mu-law for telephone
            mulaw_bytes = AudioProcessor.gemini_to_telephony(pcm24k_bytes)
            if not mulaw_bytes:
                return

            payload = base64.b64encode(mulaw_bytes).decode("ascii")
            media_msg = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {
                    "payload": payload
                }
            }
            try:
                await websocket.send_text(json.dumps(media_msg))
            except Exception as e:
                logger.error(f"Error sending audio to telephony stream: {e}")

        async def send_clear_to_telephony() -> None:
            """Flush audio buffer on the carrier side when caller barges in."""
            if not stream_sid:
                return
            clear_msg = {
                "event": "clear",
                "streamSid": stream_sid
            }
            try:
                await websocket.send_text(json.dumps(clear_msg))
                logger.info(f"Sent 'clear' event to carrier for stream {stream_sid}")
            except Exception as e:
                logger.error(f"Error sending clear to telephony: {e}")

        try:
            while True:
                message_text = await websocket.receive_text()
                if not message_text:
                    continue

                msg = json.loads(message_text)
                event = msg.get("event")

                if event == "connected":
                    logger.info("Carrier protocol connected event received.")

                elif event == "start":
                    start_data = msg.get("start", {})
                    stream_sid = msg.get("streamSid")
                    call_sid = start_data.get("callSid", "CallSid_Unknown")
                    custom_params = start_data.get("customParameters", {})
                    caller_id = custom_params.get("From", "Caller")

                    logger.info(f"Stream started: streamSid={stream_sid}, callSid={call_sid}")

                    # Initialize ConversationEngine for this call
                    engine = ConversationEngine(
                        session_id=call_sid,
                        caller_id=caller_id,
                        on_audio_out=lambda data: websocket.app.state.loop.create_task(send_audio_to_telephony(data)),
                        use_sounddevice_output=False
                    )

                    # Wire interruption to telephony clear event
                    orig_on_speech_start = engine.vad.on_speech_start
                    def hooked_speech_start():
                        if orig_on_speech_start:
                            orig_on_speech_start()
                        if engine.player.is_playing:
                            websocket.app.state.loop.create_task(send_clear_to_telephony())
                    engine.vad.on_speech_start = hooked_speech_start

                    # Start engine
                    started = await engine.start()
                    if started and stream_sid:
                        active_sessions[stream_sid] = engine
                    else:
                        logger.error("Failed to start engine for live phone call.")
                        await websocket.close()
                        break

                elif event == "media":
                    if not engine or not engine.is_running:
                        continue

                    media_info = msg.get("media", {})
                    b64_payload = media_info.get("payload")
                    if not b64_payload:
                        continue

                    # Decode mu-law from carrier and resample to 16kHz PCM for Gemini
                    mulaw_bytes = base64.b64decode(b64_payload)
                    pcm16_16k = AudioProcessor.telephony_to_gemini(mulaw_bytes)

                    # Feed into ConversationEngine
                    await engine.feed_audio(pcm16_16k)

                elif event == "stop":
                    logger.info(f"Stream stopped by caller: streamSid={stream_sid}")
                    break

        except WebSocketDisconnect:
            logger.info("Carrier media stream WebSocket disconnected.")
        except Exception as e:
            logger.error(f"Error in media stream loop: {e}")
        finally:
            if stream_sid and stream_sid in active_sessions:
                eng = active_sessions.pop(stream_sid)
                summary = eng.memory.generate_summary()
                logger.info(f"Call Summary for {stream_sid}: {json.dumps(summary, indent=2)}")
                await eng.stop()

    return app


if __name__ == "__main__":
    import uvicorn
    app = create_telephony_app()
    uvicorn.run(app, host=settings.telephony_host, port=settings.telephony_port)
