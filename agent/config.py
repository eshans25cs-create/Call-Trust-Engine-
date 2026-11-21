"""
Configuration management for the Real-Time Gemini AI Call Agent.
"""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Gemini API Credentials
    gemini_api_key: SecretStr = Field(
        ...,
        alias="GEMINI_API_KEY",
        description="Google Gemini API Key"
    )

    # Gemini Live Model & Endpoint
    # Verified official Gemini Live bidirectional streaming model:
    # models/gemini-2.5-flash-native-audio-latest
    gemini_model: str = Field(
        default="models/gemini-2.5-flash-native-audio-latest",
        alias="GEMINI_MODEL",
        description="Gemini model name for bidirectional streaming"
    )
    
    gemini_live_uri: str = Field(
        default="wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent",
        alias="GEMINI_LIVE_URI",
        description="Gemini Multimodal Live API WebSocket endpoint"
    )

    # Voice Persona: Aoede, Puck, Charon, Kore, Fenrir
    gemini_voice_name: Literal["Aoede", "Puck", "Charon", "Kore", "Fenrir"] = Field(
        default="Aoede",
        alias="GEMINI_VOICE_NAME",
        description="Voice persona name for audio synthesis"
    )

    # Agent Persona
    agent_name: str = Field(
        default="Aria",
        alias="AGENT_NAME",
        description="Name of the AI call agent"
    )
    agent_role: str = Field(
        default="helpful real-time voice call assistant",
        alias="AGENT_ROLE",
        description="Operational role of the AI agent"
    )

    # Audio Sample Rates & Frame Sizes
    input_sample_rate: int = Field(
        default=16000,
        alias="INPUT_SAMPLE_RATE",
        description="Sample rate sent to Gemini Live (16kHz PCM)"
    )
    output_sample_rate: int = Field(
        default=24000,
        alias="OUTPUT_SAMPLE_RATE",
        description="Sample rate received from Gemini Live (24kHz PCM)"
    )
    telephony_sample_rate: int = Field(
        default=8000,
        alias="TELEPHONY_SAMPLE_RATE",
        description="Sample rate used by telephony systems (8kHz G.711 µ-law)"
    )
    chunk_duration_ms: int = Field(
        default=50,
        description="Audio frame chunk duration in milliseconds (20-100ms)"
    )

    # Voice Activity Detection (VAD) & Barge-in
    vad_energy_threshold: float = Field(
        default=0.015,
        alias="VAD_ENERGY_THRESHOLD",
        description="RMS threshold to classify incoming audio frame as active human speech"
    )
    vad_silence_duration_ms: int = Field(
        default=600,
        alias="VAD_SILENCE_DURATION_MS",
        description="Silence duration required to detect end of speech turn"
    )

    # Telephony Gateway Server
    telephony_host: str = Field(
        default="0.0.0.0",
        alias="TELEPHONY_HOST",
        description="Host interface for the telephony WebSocket server"
    )
    telephony_port: int = Field(
        default=8000,
        alias="TELEPHONY_PORT",
        description="Port for the telephony server"
    )
    public_base_url: str = Field(
        default="http://localhost:8000",
        alias="PUBLIC_BASE_URL",
        description="Public base URL (or ngrok domain) for telephony webhooks"
    )

    # Legal & Privacy Safeguards
    enable_ai_disclosure: bool = Field(
        default=True,
        description="Disclose that the caller is speaking with an AI agent"
    )
    persist_transcripts: bool = Field(
        default=False,
        description="Persist call logs or discard upon session completion"
    )

    def get_system_instruction(self) -> str:
        """
        Generate dynamic system instruction for the live conversational agent.
        """
        return (
            f"You are {self.agent_name}, a {self.agent_role}. "
            "You are conducting a live, spoken conversation over a phone call.\n\n"
            "Key Spoken Dialogue Rules:\n"
            "1. Be natural, polite, and conversational. Do not sound robotic.\n"
            "2. Keep responses brief and concise (usually 1 to 2 sentences per turn), "
            "allowing natural back-and-forth conversation.\n"
            "3. Ask clarifying questions when user requests are ambiguous.\n"
            "4. Acknowledge when you don't know something instead of inventing facts.\n"
            "5. If the caller asks who or what you are, clearly disclose that you are an AI assistant.\n"
            "6. When performing tasks (checking time, looking up notes, scheduling, or transferring), "
            "use the provided tools accurately.\n"
            "7. Never agree to financial transactions, medical diagnoses, or legal advice without directing "
            "the user to human authorities."
        )


settings = Settings()
