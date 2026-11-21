"""
Outbound Phone Call Dispatcher for Gemini Live AI Agent.
Initiates an outbound phone call to a recipient's phone number using Twilio / SIP REST API,
connecting them directly to the real-time Gemini Live conversational engine when answered.
"""

import sys
import argparse
import logging
import requests
from typing import Optional
from agent.config import settings

logger = logging.getLogger("OutboundCaller")


def make_outbound_call(
    to_phone_number: str,
    from_phone_number: Optional[str] = None,
    twilio_account_sid: Optional[str] = None,
    twilio_auth_token: Optional[str] = None,
    webhook_url: Optional[str] = None
) -> dict:
    """
    Trigger an outbound call using Twilio Voice REST API.
    When the recipient answers, Twilio requests webhook_url,
    which answers with TwiML and connects the live Gemini media stream.
    """
    import os
    account_sid = twilio_account_sid or os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = twilio_auth_token or os.getenv("TWILIO_AUTH_TOKEN")
    from_number = from_phone_number or os.getenv("TWILIO_PHONE_NUMBER")
    base_url = webhook_url or f"{settings.public_base_url.rstrip('/')}/voice/incoming"

    if not account_sid or not auth_token or not from_number:
        raise ValueError(
            "Missing Twilio credentials. Please set TWILIO_ACCOUNT_SID, "
            "TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER in your .env file."
        )

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
    data = {
        "To": to_phone_number,
        "From": from_number,
        "Url": base_url,
        "StatusCallback": f"{settings.public_base_url.rstrip('/')}/voice/status",
        "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"],
        "StatusCallbackMethod": "POST"
    }

    response = requests.post(url, data=data, auth=(account_sid, auth_token))
    if response.status_code in [200, 201]:
        call_info = response.json()
        logger.info(f"Outbound call initiated! CallSid: {call_info.get('sid')}")
        return call_info
    else:
        logger.error(f"Failed to place outbound call: {response.status_code} {response.text}")
        response.raise_for_status()
        return {}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initiate outbound call with Gemini Live Agent")
    parser.add_argument("--to", required=True, help="Recipient phone number (e.g. +15551234567)")
    parser.add_argument("--from-number", default=None, help="Your Twilio phone number")
    args = parser.parse_args()

    try:
        print(f"Calling {args.to} via Gemini Live Gateway...")
        res = make_outbound_call(to_phone_number=args.to, from_phone_number=args.from_number)
        print(f"Call placed successfully! Call SID: {res.get('sid')}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
