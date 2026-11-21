"""
Unit tests for FastAPI Telephony Gateway and TwiML generation.
"""

from fastapi.testclient import TestClient
from agent.telephony.gateway import create_telephony_app
from agent.telephony.twiml import generate_twiml_stream_response


def test_twiml_generation():
    """Verify that generated TwiML contains valid Connect and Stream tags."""
    twiml = generate_twiml_stream_response(
        websocket_url="wss://example.com/media-stream",
        greeting_text="Connecting to AI assistant."
    )
    assert "<Response>" in twiml
    assert "<Say" in twiml
    assert '<Stream url="wss://example.com/media-stream" />' in twiml


def test_telephony_app_endpoints():
    """Verify HTTP endpoints on the Telephony Gateway."""
    app = create_telephony_app()
    client = TestClient(app)

    # 1. Health / Landing page
    res = client.get("/")
    assert res.status_code == 200
    assert "Gemini Live Telephony Gateway Active" in res.text

    # 2. Incoming voice webhook
    res = client.post(
        "/voice/incoming",
        data={"CallSid": "CA123456789", "From": "+15559876543"}
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/xml"
    assert "<Stream" in res.text

    # 3. Status callback
    res = client.post(
        "/voice/status",
        data={"CallSid": "CA123456789", "CallStatus": "completed", "CallDuration": "45"}
    )
    assert res.status_code == 200
    assert res.json() == {"status": "received"}
