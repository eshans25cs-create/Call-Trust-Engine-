"""
Interactive Real-Time Duplex Voice CLI for Gemini Live Call Agent.
Provides full two-way voice conversation through microphone and speaker
with live barge-in interruption, transcript display, and tool tracking.
"""

import os
import sys
import time
import asyncio
import logging

# Ensure project root is on sys.path and cwd is project directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
try:
    os.chdir(PROJECT_ROOT)
except Exception:
    pass

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from typing import Any, Dict
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent.config import settings
from agent.audio.processor import AudioProcessor
from agent.conversation.engine import ConversationEngine

# Suppress debug logs in CLI mode
logging.basicConfig(level=logging.WARNING)
console = Console()


def format_volume_meter(rms: float, bar_width: int = 15) -> str:
    """Format an RMS volume float (0.0 to 1.0) as a visual volume bar."""
    filled = min(bar_width, int(rms * bar_width * 10))
    bar = "█" * filled + "░" * (bar_width - filled)
    return bar


async def run_live_voice_call():
    """
    Run full-duplex live audio conversation between the user and Gemini Live.
    """
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Gemini Live Call Agent — Real-Time Voice Console[/bold cyan]\n"
            f"[bold white]Model:[/bold white] [green]{settings.gemini_model}[/green]\n"
            f"[bold white]Voice:[/bold white] [magenta]{settings.gemini_voice_name}[/magenta]\n"
            f"[bold white]Persona:[/bold white] [yellow]{settings.agent_name}[/yellow] ({settings.agent_role})\n"
            f"[bold white]Interruption Support:[/bold white] [cyan]Enabled (Instant Barge-in)[/cyan]\n\n"
            f"[dim]Controls: Speak naturally. Say 'goodbye' or press Ctrl+C to hang up.[/dim]",
            title="[Active Call Session]",
            border_style="cyan"
        )
    )

    # Callbacks for live events
    def handle_text_out(text: str):
        console.print(f"[bold magenta]{settings.agent_name}:[/bold magenta] {text}")

    def handle_user_speaking(is_speaking: bool):
        if is_speaking:
            console.print("[dim green][Caller speaking...][/dim green]")
        else:
            console.print("[dim][Caller paused.][/dim]")

    def handle_interruption():
        console.print("[bold red][Barge-in] You interrupted the agent — speech playback cleared![/bold red]")

    def handle_tool_event(name: str, args: Dict[str, Any], result: Any):
        console.print(f"[bold yellow][Tool Invocated][/bold yellow] [cyan]{name}[/cyan]({args}) -> {result}")

    session_id = f"cli_voice_{int(time.time())}"
    engine = ConversationEngine(
        session_id=session_id,
        caller_id="Local Test User",
        on_text_out=handle_text_out,
        on_user_speaking=handle_user_speaking,
        on_interrupted=handle_interruption,
        on_tool_event=handle_tool_event,
        use_sounddevice_output=True
    )

    console.print("[yellow]Connecting to Google Gemini Live API...[/yellow]")
    started = await engine.start()
    if not started:
        console.print("[bold red]❌ Failed to connect to Gemini Live. Check your API key and network.[/bold red]")
        return

    console.print("[bold green]✅ Connected and Ready![/bold green] You may speak now.\n")

    input_stream = None
    audio_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    use_mic = True

    try:
        import sounddevice as sd

        # Show detected audio devices
        default_in = sd.query_devices(kind="input")
        default_out = sd.query_devices(kind="output")
        console.print(f"[dim]Input Device:  {default_in['name']}[/dim]")
        console.print(f"[dim]Output Device: {default_out['name']}[/dim]\n")

        def audio_callback(indata, frames, time_info, status):
            if status:
                pass
            raw_bytes = bytes(indata)
            loop.call_soon_threadsafe(audio_queue.put_nowait, raw_bytes)

        chunk_size = int(settings.input_sample_rate * (settings.chunk_duration_ms / 1000.0))
        input_stream = sd.RawInputStream(
            samplerate=settings.input_sample_rate,
            channels=1,
            dtype="int16",
            blocksize=chunk_size,
            callback=audio_callback
        )
        input_stream.start()

    except Exception as e:
        console.print(f"[bold yellow]⚠️ Microphone access warning: {e}.[/bold yellow]")
        console.print("[dim]Simulating initial caller greeting...[/dim]")
        use_mic = False

    async def mic_feeder():
        """Feed captured mic audio chunks into conversation engine."""
        try:
            while engine.is_running:
                chunk = await audio_queue.get()
                await engine.feed_audio(chunk)
                audio_queue.task_done()
        except asyncio.CancelledError:
            pass

    feeder_task = asyncio.create_task(mic_feeder())

    if not use_mic:
        # Automated probe greeting
        await engine.client.send_text("Hello Aria, please introduce yourself in one short sentence.")
        await asyncio.sleep(6)

    try:
        # Keep running until user terminates
        while engine.is_running:
            await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Call ended by caller.[/yellow]")
    finally:
        if input_stream:
            try:
                input_stream.stop()
                input_stream.close()
            except Exception:
                pass
        feeder_task.cancel()
        await engine.stop()

        # Display Call Summary
        summary = engine.memory.generate_summary()
        summary_table = Table(title="📋 Call Summary", border_style="green", show_header=True)
        summary_table.add_column("Metric / Property", style="cyan")
        summary_table.add_column("Value", style="white")

        summary_table.add_row("Session ID", summary["session_id"])
        summary_table.add_row("Caller", summary["caller_id"])
        summary_table.add_row("Identified Name", summary["caller_name"])
        summary_table.add_row("Duration", f"{summary['duration_seconds']} seconds")
        summary_table.add_row("Total Turns", str(summary["total_turns"]))
        summary_table.add_row("Facts Gathered", str(summary["facts_gathered"]))
        summary_table.add_row("Notes", "; ".join(summary["notes"]) if summary["notes"] else "None")
        summary_table.add_row("Unresolved Items", "; ".join(summary["unresolved_items"]) if summary["unresolved_items"] else "None")

        console.print()
        console.print(summary_table)


if __name__ == "__main__":
    try:
        asyncio.run(run_live_voice_call())
    except KeyboardInterrupt:
        sys.exit(0)
