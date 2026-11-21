"""
Unit tests for SessionMemory and ToolRegistry execution.
"""

import pytest
from agent.conversation.memory import SessionMemory
from agent.conversation.tools import ToolRegistry


def test_session_memory_lifecycle():
    """Verify memory tracking, facts, turns, summary, and clearing."""
    mem = SessionMemory(session_id="call_test_01", caller_id="+15551234567")
    mem.set_caller_name("Alice Johnson")
    mem.store_fact("account_tier", "Enterprise")
    mem.add_note("Customer inquired about international roaming.")
    mem.add_unanswered_question("Can international roaming be activated on SIM 2?")

    mem.record_turn("agent", "Hello Alice, how can I assist you?")
    mem.record_turn("user", "I need to know about international roaming.")

    summary = mem.generate_summary()
    assert summary["session_id"] == "call_test_01"
    assert summary["caller_name"] == "Alice Johnson"
    assert summary["total_turns"] == 2
    assert summary["facts_gathered"]["account_tier"] == "Enterprise"
    assert len(summary["unresolved_items"]) == 1

    # Clear memory
    mem.clear()
    assert len(mem.turns) == 0
    assert len(mem.facts) == 0
    assert mem.caller_name is None


@pytest.mark.asyncio
async def test_tool_registry_execution():
    """Test safe execution of registered tools."""
    mem = SessionMemory(session_id="call_tool_test")
    registry = ToolRegistry(memory=mem)

    # 1. get_current_time
    time_res = await registry.execute_tool("get_current_time", {"timezone": "UTC"})
    assert "current_time" in time_res
    assert "current_date" in time_res

    # 2. search_knowledge_base
    kb_res = await registry.execute_tool("search_knowledge_base", {"query": "what are your hours?"})
    assert "9:00 AM" in kb_res["result"]

    # 3. save_call_note
    note_res = await registry.execute_tool("save_call_note", {"topic": "priority", "content": "high"})
    assert note_res["status"] == "saved"
    assert mem.facts.get("priority") == "high"

    # 4. transfer_call
    transfer_res = await registry.execute_tool("transfer_call", {"department": "billing", "reason": "overcharge dispute"})
    assert transfer_res["status"] == "transfer_initiated"
    assert transfer_res["department"] == "Billing"

    # 5. Unknown tool
    err_res = await registry.execute_tool("non_existent_tool", {})
    assert "error" in err_res
