"""
TwiML (Twilio Markup Language) generator for connecting incoming/outgoing calls
to bidirectional audio streams.
"""

from typing import Optional


def generate_twiml_stream_response(
    websocket_url: str,
    greeting_text: Optional[str] = None
) -> str:
    """
    Generate TwiML XML to establish bidirectional streaming with our server.
    """
    greeting_xml = ""
    if greeting_text:
        greeting_xml = f"<Say voice='Polly.Amy'>{greeting_text}</Say>"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    {greeting_xml}
    <Connect>
        <Stream url="{websocket_url}" />
    </Connect>
</Response>"""
    return twiml.strip()
