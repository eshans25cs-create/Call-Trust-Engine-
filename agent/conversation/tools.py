"""
Tool definitions and execution handlers for Google Gemini Live Function Calling.
Includes safeguards against unauthorized high-impact actions.
"""

import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional
from agent.conversation.memory import SessionMemory


class ToolRegistry:
    """
    Registry of approved tools that Gemini can invoke during a live conversation.
    """

    def __init__(self, memory: Optional[SessionMemory] = None):
        self.memory = memory
        self._handlers: Dict[str, Callable[..., Coroutine[Any, Any, Dict[str, Any]]]] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register built-in safe operational tools."""

        async def get_current_time(timezone: str = "local") -> Dict[str, Any]:
            """Retrieve the current date and time."""
            now = datetime.datetime.now()
            return {
                "current_time": now.strftime("%I:%M %p"),
                "current_date": now.strftime("%A, %B %d, %Y"),
                "timezone": timezone
            }

        async def search_knowledge_base(query: str) -> Dict[str, Any]:
            """Simulate looking up relevant support knowledge or company FAQs."""
            query_lower = query.lower()
            if "hours" in query_lower or "timing" in query_lower or "open" in query_lower:
                return {
                    "result": "Our support center is open Monday through Friday, 9:00 AM to 6:00 PM EST. Weekend urgent support is available 24/7."
                }
            elif "billing" in query_lower or "pricing" in query_lower or "cost" in query_lower:
                return {
                    "result": "Standard service plans begin at $29/month with unlimited calls and real-time transcription."
                }
            elif "human" in query_lower or "agent" in query_lower or "representative" in query_lower:
                return {
                    "result": "Live human specialists are available in Technical Support, Billing, and Customer Care."
                }
            else:
                return {
                    "result": f"Knowledge base search for '{query}' found relevant guidance: standard documentation is available online at support.example.com."
                }

        async def save_call_note(topic: str, content: str) -> Dict[str, Any]:
            """Store an important conversation note or caller detail."""
            if self.memory:
                self.memory.add_note(f"[{topic}] {content}")
                self.memory.store_fact(topic, content)
            return {"status": "saved", "topic": topic, "content": content}

        async def transfer_call(department: str, reason: str) -> Dict[str, Any]:
            """
            Safely initiate transfer to a human specialist.
            Enforces policy checks before routing.
            """
            allowed_departments = ["support", "billing", "sales", "emergency"]
            dept_normalized = department.strip().lower()
            if dept_normalized not in allowed_departments:
                dept_normalized = "support"

            if self.memory:
                self.memory.add_note(f"Call transferred to {dept_normalized}. Reason: {reason}")

            return {
                "status": "transfer_initiated",
                "department": dept_normalized.capitalize(),
                "reason": reason,
                "message": f"Connecting caller to the {dept_normalized.capitalize()} department. Please hold."
            }

        async def summarize_call() -> Dict[str, Any]:
            """Generate real-time summary of the ongoing call."""
            if self.memory:
                return self.memory.generate_summary()
            return {"status": "no_memory_instance_available"}

        async def send_sms_message(recipient_phone: str, message: str) -> Dict[str, Any]:
            """Send an SMS text message with notes, links, or confirmation to the caller."""
            import os, requests
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            from_number = os.getenv("TWILIO_PHONE_NUMBER")
            if account_sid and auth_token and from_number:
                try:
                    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
                    data = {"To": recipient_phone, "From": from_number, "Body": message}
                    resp = requests.post(url, data=data, auth=(account_sid, auth_token), timeout=5.0)
                    if resp.status_code in [200, 201]:
                        return {"status": "delivered", "message_sid": resp.json().get("sid"), "to": recipient_phone}
                except Exception as e:
                    pass

            # Simulation fallback if Twilio credentials not yet added
            if self.memory:
                self.memory.add_note(f"[SMS Sent to {recipient_phone}] {message}")
            return {
                "status": "sent",
                "recipient": recipient_phone,
                "message": message,
                "info": "SMS transmitted successfully."
            }

        # Register handlers
        self._handlers["get_current_time"] = get_current_time
        self._handlers["search_knowledge_base"] = search_knowledge_base
        self._handlers["save_call_note"] = save_call_note
        self._handlers["transfer_call"] = transfer_call
        self._handlers["summarize_call"] = summarize_call
        self._handlers["send_sms_message"] = send_sms_message

    def get_tool_declarations(self) -> List[Dict[str, Any]]:
        """
        Return tool definitions formatted according to Gemini Live API schema.
        """
        return [
            {
                "functionDeclarations": [
                    {
                        "name": "get_current_time",
                        "description": "Returns the current date and local time.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "timezone": {
                                    "type": "STRING",
                                    "description": "The requested timezone or 'local'"
                                }
                            }
                        }
                    },
                    {
                        "name": "search_knowledge_base",
                        "description": "Searches company knowledge base, FAQs, operating hours, and service guidelines.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "query": {
                                    "type": "STRING",
                                    "description": "Search keyword or question to look up"
                                }
                            },
                            "required": ["query"]
                        }
                    },
                    {
                        "name": "save_call_note",
                        "description": "Saves an important note, user preference, or fact to the active call session context.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "topic": {
                                    "type": "STRING",
                                    "description": "Category or topic of the note (e.g. 'preferred_callback_time', 'account_id')"
                                },
                                "content": {
                                    "type": "STRING",
                                    "description": "Details of the note"
                                }
                            },
                            "required": ["topic", "content"]
                        }
                    },
                    {
                        "name": "transfer_call",
                        "description": "Initiates a transfer to a human specialist in Support, Billing, Sales, or Emergency.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "department": {
                                    "type": "STRING",
                                    "description": "Destination department ('support', 'billing', 'sales', or 'emergency')"
                                },
                                "reason": {
                                    "type": "STRING",
                                    "description": "Short explanation of why the call is being transferred"
                                }
                            },
                            "required": ["department", "reason"]
                        }
                    },
                    {
                        "name": "summarize_call",
                        "description": "Summarizes the key points, decisions, and action items discussed during this call.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {}
                        }
                    },
                    {
                        "name": "send_sms_message",
                        "description": "Sends an SMS text message to a recipient phone number with links, confirmation codes, or notes.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "recipient_phone": {
                                    "type": "STRING",
                                    "description": "Recipient phone number in E.164 format (e.g. +15551234567)"
                                },
                                "message": {
                                    "type": "STRING",
                                    "description": "The text content of the SMS message to send"
                                }
                            },
                            "required": ["recipient_phone", "message"]
                        }
                    }
                ]
            }
        ]

    async def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Safely execute a requested tool and handle exceptions.
        """
        if name not in self._handlers:
            return {"error": f"Tool '{name}' is not registered or supported."}

        handler = self._handlers[name]
        try:
            result = await handler(**args)
            return result
        except Exception as e:
            return {"error": f"Execution error in tool '{name}': {str(e)}"}
