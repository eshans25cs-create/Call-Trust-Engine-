"""
Live end-to-end integration test connecting to Gemini Live API over WebSocket.
Verifies API authentication, handshake, and bidirectional audio streaming.
"""

import sys
import os
import asyncio
import time
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.config import settings
from agent.live.client import GeminiLiveClient


@pytest.mark.asyncio
async def test_gemini_live_e2e_audio_stream():
    """Verify live bidirectional audio exchange with Gemini Live endpoint."""
    received_audio_chunks = []
    received_transcripts = []
    turn_completed_event = asyncio.Event()

    client = GeminiLiveClient(
        model=settings.gemini_model,
        voice_name=settings.gemini_voice_name,
        system_instruction="You are a live telephone assistant. When greeted, reply with one short sentence: 'Voice pipeline is fully operational.'",
        on_audio_received=lambda chunk: received_audio_chunks.append(chunk),
        on_text_received=lambda text: received_transcripts.append(text),
        on_turn_complete=lambda: turn_completed_event.set()
    )

    start_time = time.time()
    connected = await client.connect()
    assert connected, "Failed to connect and complete handshake with Gemini Live WebSocket."

    # Send a prompt turn requesting speech output
    await client.send_text("Hello agent, test prompt. Confirm audio status in one short sentence.")

    # Wait for turn completion or timeout
    try:
        await asyncio.wait_for(turn_completed_event.wait(), timeout=12.0)
    except asyncio.TimeoutError:
        pass

    await client.disconnect()
    total_latency = (time.time() - start_time) * 1000.0

    print(f"\n--- Live Gemini Live API Probe Results ---")
    print(f"Connected: {connected}")
    print(f"Audio Chunks Received: {len(received_audio_chunks)}")
    total_audio_bytes = sum(len(c) for c in received_audio_chunks)
    print(f"Total Audio Bytes (24kHz PCM): {total_audio_bytes} bytes")
    if received_transcripts:
        print(f"Transcript: {' '.join(received_transcripts)}")
    print(f"Total Turn Time: {total_latency:.1f}ms")

    assert len(received_audio_chunks) > 0, "No audio chunks received from Gemini Live API."
    assert total_audio_bytes > 0, "Audio stream bytes were empty."


if __name__ == "__main__":
    asyncio.run(test_gemini_live_e2e_audio_stream())
