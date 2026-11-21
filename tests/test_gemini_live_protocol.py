"""
Unit tests for Gemini Live BidiGenerateContent protocol messages.
"""

import base64
from agent.live.protocol import GeminiLiveProtocol


def test_build_setup_message():
    """Verify setup message complies with Gemini Live API specification."""
    msg = GeminiLiveProtocol.build_setup_message(
        model="models/gemini-2.5-flash",
        system_instruction="You are a helpful assistant.",
        voice_name="Aoede"
    )

    assert "setup" in msg
    setup = msg["setup"]
    assert setup["model"] == "models/gemini-2.5-flash"
    assert setup["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert setup["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Aoede"
    assert setup["systemInstruction"]["parts"][0]["text"] == "You are a helpful assistant."


def test_build_audio_chunk_message():
    """Verify realtimeInput mediaChunks packaging."""
    dummy_audio = b"\x00\x01\x02\x03" * 100
    msg = GeminiLiveProtocol.build_audio_chunk_message(dummy_audio, rate=16000)

    assert "realtimeInput" in msg
    chunks = msg["realtimeInput"]["mediaChunks"]
    assert len(chunks) == 1
    assert chunks[0]["mimeType"] == "audio/pcm;rate=16000"
    decoded = base64.b64decode(chunks[0]["data"])
    assert decoded == dummy_audio


def test_parse_server_audio_message():
    """Verify unpacking of serverContent audio chunks and text."""
    dummy_audio = b"\x10\x20\x30\x40" * 50
    b64_audio = base64.b64encode(dummy_audio).decode("ascii")

    server_msg = {
        "serverContent": {
            "modelTurn": {
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "audio/pcm;rate=24000",
                            "data": b64_audio
                        }
                    },
                    {
                        "text": "Hello, how can I assist you today?"
                    }
                ]
            },
            "turnComplete": True
        }
    }

    parsed = GeminiLiveProtocol.parse_server_message(server_msg)
    assert len(parsed["audio_chunks"]) == 1
    assert parsed["audio_chunks"][0] == dummy_audio
    assert parsed["text_parts"] == ["Hello, how can I assist you today?"]
    assert parsed["turn_complete"] is True
    assert parsed["interrupted"] is False


def test_parse_tool_call_message():
    """Verify parsing of server-initiated function calls."""
    server_msg = {
        "toolCall": {
            "functionCalls": [
                {
                    "id": "call_12345",
                    "name": "get_current_time",
                    "args": {"timezone": "EST"}
                }
            ]
        }
    }

    parsed = GeminiLiveProtocol.parse_server_message(server_msg)
    assert len(parsed["tool_calls"]) == 1
    tc = parsed["tool_calls"][0]
    assert tc["id"] == "call_12345"
    assert tc["name"] == "get_current_time"
    assert tc["args"] == {"timezone": "EST"}
