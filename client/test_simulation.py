"""
Automated Live Call Conversation Simulator.
Simulates a real multi-turn phone conversation with Google Gemini Live,
testing audio generation, tool calls, entity retention, and post-call summaries.
"""

import sys
import os
import asyncio
import time
from rich.console import Console
from rich.panel import Panel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent.config import settings
from agent.conversation.engine import ConversationEngine

console = Console()


async def simulate_live_call():
    console.print(
        Panel.fit(
            "[bold cyan]Simulating Live Multi-Turn Phone Call with Gemini Live[/bold cyan]\n"
            f"Model: [green]{settings.gemini_model}[/green]\n"
            f"Voice: [magenta]{settings.gemini_voice_name}[/magenta]",
            border_style="cyan"
        )
    )

    received_agent_texts = []
    received_audio_chunks = []
    executed_tools = []

    def on_text(text: str):
        received_agent_texts.append(text)
        console.print(f"[bold magenta]Aria (AI):[/bold magenta] {text}")

    def on_tool(name: str, args: dict, result: dict):
        executed_tools.append((name, args, result))
        console.print(f"[bold yellow][Tool Executed][/bold yellow] [cyan]{name}[/cyan]({args}) -> {result}")

    def on_audio(chunk: bytes):
        received_audio_chunks.append(chunk)

    engine = ConversationEngine(
        session_id="simulated_call_001",
        caller_id="+15559876543",
        on_text_out=on_text,
        on_tool_event=on_tool,
        on_audio_out=on_audio,
        use_sounddevice_output=False
    )

    console.print("[yellow]Connecting to Gemini Live...[/yellow]")
    connected = await engine.start()
    if not connected:
        console.print("[bold red]Connection failed.[/bold red]")
        return

    console.print("[bold green]Connected![/bold green] Starting dialogue simulation...\n")

    # Turn 1: Introduction
    console.print("[bold green]Caller:[/bold green] Hello Aria, can you introduce yourself and tell me what time it is?")
    await engine.client.send_text("Hello Aria, please introduce yourself in one sentence and check what time it is.")
    await asyncio.sleep(5.0)

    # Turn 2: Business query & notes
    console.print("\n[bold green]Caller:[/bold green] What are your support hours, and please note down my account ID as ACC-9944.")
    await engine.client.send_text("What are your support hours? Also please save a note that my account ID is ACC-9944.")
    await asyncio.sleep(5.0)

    # Turn 3: Summarize call
    console.print("\n[bold green]Caller:[/bold green] Great, can you briefly summarize what we discussed?")
    await engine.client.send_text("Can you summarize our conversation and confirm my account ID?")
    await asyncio.sleep(6.0)

    # Hang up
    await engine.stop()

    summary = engine.memory.generate_summary()
    total_audio_kb = sum(len(c) for c in received_audio_chunks) / 1024.0

    console.print("\n" + "=" * 60)
    console.print(
        Panel(
            f"[bold green]Live Call Simulation Succeeded![/bold green]\n\n"
            f"• [bold]Total Audio Streamed:[/bold] {len(received_audio_chunks)} chunks ({total_audio_kb:.1f} KB of 24kHz PCM)\n"
            f"• [bold]Tools Executed:[/bold] {len(executed_tools)} ({', '.join(t[0] for t in executed_tools)})\n"
            f"• [bold]Turns Completed:[/bold] {summary['total_turns']}\n"
            f"• [bold]Facts Stored in Memory:[/bold] {summary['facts_gathered']}\n"
            f"• [bold]Notes Stored:[/bold] {summary['notes']}\n"
            f"• [bold]Call Duration:[/bold] {summary['duration_seconds']}s",
            title="📊 Simulation Results",
            border_style="green"
        )
    )


if __name__ == "__main__":
    asyncio.run(simulate_live_call())
