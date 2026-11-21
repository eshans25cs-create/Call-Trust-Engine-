"""
Message definitions and helpers for Gemini Multimodal Live API (BidiGenerateContent).
"""

import base64
from typing import Any, Dict, List, Optional


class GeminiLiveProtocol:
    """
    Serializer and deserializer for Gemini Live Bidirectional WebSocket messages.
    """

    @staticmethod
    def build_setup_message(
        model: str,
        system_instruction: str,
        voice_name: str = "Aoede",
        response_modalities: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Build the initial handshake setup message required by Gemini Live.
        """
        if response_modalities is None:
            response_modalities = ["AUDIO"]

        setup_dict: Dict[str, Any] = {
            "model": model,
            "generationConfig": {
                "responseModalities": response_modalities,
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice_name
                        }
                    }
                }
            },
            "systemInstruction": {
                "parts": [
                    {"text": system_instruction}
                ]
            }
        }

        if tools:
            setup_dict["tools"] = tools

        return {"setup": setup_dict}

    @staticmethod
    def build_audio_chunk_message(pcm16_bytes: bytes, rate: int = 16000) -> Dict[str, Any]:
        """
        Encode raw 16-bit linear PCM audio into a realtimeInput mediaChunk message.
        """
        b64_audio = base64.b64encode(pcm16_bytes).decode("ascii")
        return {
            "realtimeInput": {
                "mediaChunks": [
                    {
                        "mimeType": f"audio/pcm;rate={rate}",
                        "data": b64_audio
                    }
                ]
            }
        }

    @staticmethod
    def build_text_message(text: str, turn_complete: bool = True) -> Dict[str, Any]:
        """
        Send a text turn from client.
        """
        return {
            "clientContent": {
                "turns": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": text}
                        ]
                    }
                ],
                "turnComplete": turn_complete
            }
        }

    @staticmethod
    def build_tool_response_message(call_id: str, name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send the result of a tool/function call execution back to Gemini.
        """
        return {
            "toolResponse": {
                "functionResponses": [
                    {
                        "id": call_id,
                        "name": name,
                        "response": {
                            "result": result
                        }
                    }
                ]
            }
        }

    @staticmethod
    def parse_server_message(msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and unpack incoming server message from Gemini Live.
        Extracts:
        - audio_chunks: list of raw PCM bytes
        - text_parts: list of transcribed text strings
        - turn_complete: boolean
        - interrupted: boolean
        - tool_calls: list of function call dicts with id, name, args
        """
        result = {
            "is_setup_complete": "setupComplete" in msg,
            "audio_chunks": [],
            "text_parts": [],
            "thought_parts": [],
            "turn_complete": False,
            "interrupted": False,
            "tool_calls": []
        }

        # Handle serverContent
        if "serverContent" in msg:
            content = msg["serverContent"]
            if content.get("interrupted"):
                result["interrupted"] = True
            if content.get("turnComplete"):
                result["turn_complete"] = True

            model_turn = content.get("modelTurn", {})
            parts = model_turn.get("parts", [])
            for part in parts:
                if "inlineData" in part:
                    inline = part["inlineData"]
                    data_b64 = inline.get("data", "")
                    if data_b64:
                        audio_bytes = base64.b64decode(data_b64)
                        result["audio_chunks"].append(audio_bytes)
                if "text" in part:
                    text_val = part["text"]
                    if part.get("thought"):
                        result["thought_parts"].append(text_val)
                    else:
                        result["text_parts"].append(text_val)

        # Handle toolCall
        if "toolCall" in msg:
            tool_call = msg["toolCall"]
            for fn in tool_call.get("functionCalls", []):
                result["tool_calls"].append({
                    "id": fn.get("id"),
                    "name": fn.get("name"),
                    "args": fn.get("args", {})
                })

        return result
