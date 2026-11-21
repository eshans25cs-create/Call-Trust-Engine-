"""
Session Memory and Context Management for the Real-Time AI Call Agent.
Tracks conversational facts, user intent, action items, and call summaries.
"""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TurnRecord(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    speaker: str  # "user" or "agent"
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionMemory:
    """
    In-memory state and conversation memory for an active phone call session.
    Automatically respects privacy by default (discards audio, ephemerally holds context).
    """

    def __init__(self, session_id: str, caller_id: Optional[str] = None):
        self.session_id = session_id
        self.caller_id = caller_id or "Anonymous Caller"
        self.caller_name: Optional[str] = None
        self.start_time = time.time()
        self.turns: List[TurnRecord] = []
        self.facts: Dict[str, str] = {}
        self.notes: List[str] = []
        self.unanswered_questions: List[str] = []
        self.is_active = True

    def record_turn(self, speaker: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a conversational turn."""
        if not text.strip():
            return
        turn = TurnRecord(
            speaker=speaker,
            text=text.strip(),
            metadata=metadata or {}
        )
        self.turns.append(turn)

    def set_caller_name(self, name: str) -> None:
        """Set caller identified name."""
        self.caller_name = name
        self.facts["caller_name"] = name

    def store_fact(self, key: str, value: str) -> None:
        """Store an important fact identified during the call."""
        self.facts[key] = value

    def add_note(self, note: str) -> None:
        """Append an operational note during the call."""
        self.notes.append(note)

    def add_unanswered_question(self, question: str) -> None:
        """Track questions needing resolution or human follow-up."""
        self.unanswered_questions.append(question)

    def resolve_question(self, question: str) -> None:
        """Remove a resolved question from tracking."""
        if question in self.unanswered_questions:
            self.unanswered_questions.remove(question)

    def get_duration_seconds(self) -> float:
        """Return call duration in seconds."""
        return time.time() - self.start_time

    def generate_summary(self) -> Dict[str, Any]:
        """
        Generate a structured summary of the call session.
        """
        turn_count = len(self.turns)
        user_turns = sum(1 for t in self.turns if t.speaker == "user")
        agent_turns = sum(1 for t in self.turns if t.speaker == "agent")

        return {
            "session_id": self.session_id,
            "caller_id": self.caller_id,
            "caller_name": self.caller_name or "Not Provided",
            "duration_seconds": round(self.get_duration_seconds(), 2),
            "total_turns": turn_count,
            "user_turns": user_turns,
            "agent_turns": agent_turns,
            "facts_gathered": self.facts,
            "notes": self.notes,
            "unresolved_items": self.unanswered_questions,
            "transcript_snippet": [
                f"{t.speaker.capitalize()}: {t.text}" for t in self.turns[-6:]
            ] if self.turns else []
        }

    def clear(self) -> None:
        """
        Wipe all session memory to comply with privacy and retention policies.
        """
        self.turns.clear()
        self.facts.clear()
        self.notes.clear()
        self.unanswered_questions.clear()
        self.caller_name = None
        self.is_active = False
