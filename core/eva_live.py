"""
EVA Live — Gemini Live session orchestrator.
The heart of the app: manages bidirectional audio, tool calls,
proactive mode, system monitoring, and dashboard integration.
"""

import asyncio
import logging
import threading
import time
from typing import Optional, Any

from google import genai
from google.genai import types

from core.audio_manager import AudioManager
from core.tool_dispatcher import dispatch, load_all_tools, get_all_declarations
from core.system_prompt import build_system_prompt
from memory.config_manager import config
from memory.memory_manager import memory
from memory.session_memory import session_memory

logger = logging.getLogger("eva.live")


class EvaLive:
    """
    Async orchestrator managing one Gemini Live session with
    concurrent tasks for audio I/O, tool dispatch, monitoring, and more.
    """

    def __init__(self, ui_signals: Optional[Any] = None):
        self._ui = ui_signals  # MainWindow signal references
        self._session = None
        self._client = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._audio = None
        self._running = False
        # Queues are created lazily in start() where an event loop exists
        self._dashboard_queue: Optional[asyncio.Queue] = None
        self._phone_audio_queue: Optional[asyncio.Queue] = None

        # State
        self._is_speaking = False
        self._last_interaction_time = time.time()
        self._interrupted = False
        self._conversation_log: list[str] = []  # Recent turns for session summary

    async def start(self) -> None:
        """Initialize and start all concurrent tasks."""
        self._loop = asyncio.get_running_loop()
        self._running = True

        # Create async queues inside the running event loop
        self._dashboard_queue = asyncio.Queue()
        self._phone_audio_queue = asyncio.Queue()

        # Load all tool modules
        load_all_tools()
        logger.info("All tools loaded")

        # Wire up vision module's reference to this instance
        try:
            from actions.screen_processor import set_eva_live_ref
            set_eva_live_ref(self)
        except Exception:
            pass

        # Initialize audio manager
        self._audio = AudioManager(loop=self._loop)
        self._audio.on_amplitude(self._on_amplitude)

        # Initialize Gemini client
        api_key = config.get("api_key", "")
        if not api_key:
            logger.error("No API key configured!")
            self._emit_log("No API key configured. Please set up EVA first.", "error")
            return

        self._client = genai.Client(api_key=api_key)

        # Build session config
        system_prompt = build_system_prompt()
        tool_declarations = get_all_declarations()

        # Build tools list for Gemini
        tools = []
        if tool_declarations:
            tools.append(types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=d["name"],
                        description=d["description"],
                        parameters=d.get("parameters"),
                    )
                    for d in tool_declarations
                ]
            ))

        voice_name = config.get("voice_name", "Aoede")
        session_config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            system_instruction=types.Content(
                parts=[types.Part(text=system_prompt)]
            ),
            tools=tools,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
                )
            ),
        )

        # Connect to Gemini Live
        model = config.get("preferred_model", "gemini-3.1-flash-live-preview")
        logger.info(f"Connecting to Gemini Live ({model})...")
        self._emit_log("Connecting to Gemini Live...", "system")

        try:
            async with self._client.aio.live.connect(
                model=model, config=session_config
            ) as session:
                self._session = session
                logger.info("Gemini Live session established")
                self._emit_log("Connected! EVA is ready.", "system")
                self._emit_state("idle")

                # Start audio streams
                self._audio.start_input()
                self._audio.start_output()

                # Launch all concurrent tasks
                tasks = [
                    asyncio.create_task(self._send_audio_task(), name="send_audio"),
                    asyncio.create_task(self._receive_task(), name="receive"),
                    asyncio.create_task(self._play_audio_task(), name="play_audio"),
                    asyncio.create_task(self._system_monitor_task(), name="sys_monitor"),
                    asyncio.create_task(self._proactive_mode_task(), name="proactive"),
                    asyncio.create_task(self._dashboard_command_task(), name="dashboard_cmd"),
                    asyncio.create_task(self._relay_phone_audio_task(), name="phone_audio"),
                    asyncio.create_task(self._topic_monitor_task(), name="topic_monitor"),
                ]

                # Send startup briefing
                asyncio.create_task(self._startup_briefing())

                try:
                    await asyncio.gather(*tasks)
                except asyncio.CancelledError:
                    logger.info("Tasks cancelled, shutting down")
                except Exception as e:
                    logger.exception(f"Task error: {e}")
                finally:
                    self._running = False
                    self._audio.stop()

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self._emit_log(f"Connection failed: {e}", "error")
            return

    async def stop(self) -> None:
        """Stop all tasks, save session summary, and close."""
        self._running = False

        # Generate and save session summary before teardown
        await self._save_session_summary()

        if self._audio:
            self._audio.stop()
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass
        logger.info("EVA Live stopped")

    # ── Audio Send Task ─────────────────────────────────────────

    async def _send_audio_task(self) -> None:
        """Continuously send mic PCM chunks to Gemini Live."""
        while self._running:
            try:
                chunk = await asyncio.wait_for(
                    self._audio.get_input_chunk(), timeout=1.0
                )
                if self._session and chunk:
                    await self._session.send_realtime_input(
                        audio=types.Blob(
                            data=chunk,
                            mime_type="audio/pcm;rate=16000"
                        )
                    )
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.warning(f"Send audio error: {e}")
                await asyncio.sleep(0.5)

    # ── Receive Task ────────────────────────────────────────────

    async def _receive_task(self) -> None:
        """Parse all server events: transcript, audio, tool calls, turn control."""
        while self._running:
            try:
                async for response in self._session.receive():
                    self._handle_response(response)
            except Exception as e:
                logger.error(f"Receive error: {e}")
                await asyncio.sleep(1.0)

    def _handle_response(self, response) -> None:
        """Route a single server response to the appropriate handler."""
        try:
            # Audio data
            if response.data:
                self._is_speaking = True
                self._emit_state("speaking")
                self._audio.enqueue_output(response.data)

            # Server content (text transcript)
            if hasattr(response, 'server_content') and response.server_content:
                sc = response.server_content
                if hasattr(sc, 'model_turn') and sc.model_turn:
                    for part in sc.model_turn.parts:
                        if hasattr(part, 'text') and part.text:
                            # Track for session summary
                            self._conversation_log.append(f"EVA: {part.text}")
                            if len(self._conversation_log) > 20:
                                self._conversation_log = self._conversation_log[-20:]
                            self._emit_log(f"EVA: {part.text}", "assistant")

                # Turn complete
                if hasattr(sc, 'turn_complete') and sc.turn_complete:
                    self._is_speaking = False
                    self._emit_state("idle")

                # Interrupted
                if hasattr(sc, 'interrupted') and sc.interrupted:
                    self._is_speaking = False
                    self._audio.interrupt()
                    self._emit_state("idle")

            # Tool calls
            if hasattr(response, 'tool_call') and response.tool_call:
                self._emit_state("thinking")
                asyncio.create_task(self._execute_tools(response.tool_call))

        except Exception as e:
            logger.warning(f"Response handling error: {e}")

    # ── Tool Execution ──────────────────────────────────────────

    async def _execute_tools(self, tool_call) -> None:
        """Execute tool calls and send responses back to Gemini."""
        responses = []

        for fc in tool_call.function_calls:
            logger.info(f"Tool call: {fc.name}({fc.args})")
            self._emit_log(f"🔧 Calling: {fc.name}", "tool")

            result = await dispatch(fc.name, dict(fc.args) if fc.args else {})

            result_str = str(result.get("result", result.get("error", "No result")))
            self._emit_log(f"🔧 [{fc.name}]: {result_str[:200]}", "tool")

            responses.append(
                types.FunctionResponse(
                    name=fc.name,
                    id=fc.id,
                    response=result,
                )
            )

        # Send all tool responses back
        try:
            await self._session.send_tool_response(function_responses=responses)
        except Exception as e:
            logger.error(f"Failed to send tool response: {e}")

        self._emit_state("speaking")


    # ── Playback Task ───────────────────────────────────────────

    async def _play_audio_task(self) -> None:
        """Drain the audio output queue to speakers."""
        await self._audio.drain_output_queue()

    # ── System Monitor Task ─────────────────────────────────────

    async def _system_monitor_task(self) -> None:
        """Poll system metrics and alert on threshold breaches."""
        interval = config.get("system_monitor_interval", 30)

        while self._running:
            await asyncio.sleep(interval)

            try:
                from actions.system_monitor import get_metrics_dict
                metrics = await asyncio.get_running_loop().run_in_executor(
                    None, get_metrics_dict
                )

                # Emit to UI
                if self._ui:
                    self._ui.update_metrics_signal.emit(
                        metrics.get("cpu", 0), metrics.get("ram", 0),
                        metrics.get("gpu", 0), metrics.get("temp", 0),
                    )

                # Check thresholds
                alerts = []
                if metrics.get("cpu", 0) > config.get("cpu_alert_threshold", 90):
                    alerts.append(f"CPU is at {metrics['cpu']:.0f}%")
                if metrics.get("ram", 0) > config.get("ram_alert_threshold", 90):
                    alerts.append(f"RAM is at {metrics['ram']:.0f}%")
                if metrics.get("temp", 0) > config.get("temp_alert_threshold", 85):
                    alerts.append(f"Temperature is {metrics['temp']:.0f}°C")

                if alerts and self._session:
                    alert_msg = "System alert: " + ", ".join(alerts)
                    self._emit_log(f"⚠ {alert_msg}", "system")

            except Exception as e:
                logger.warning(f"Monitor error: {e}")

    # ── Proactive Mode Task ─────────────────────────────────────

    async def _proactive_mode_task(self) -> None:
        """Idle-triggered proactive engagement with rotating focus."""
        if not config.get("proactive_mode", True):
            return

        from actions.proactive import get_proactive_engine
        engine = get_proactive_engine()
        engine.set_threshold(config.get("proactive_idle_seconds", 300))

        while self._running:
            await asyncio.sleep(10)

            if engine.is_idle and self._session and not self._is_speaking:
                # Build rich context including recent conversation
                context = engine.build_context()

                # Append recent conversation turns (last 6-8)
                if self._conversation_log:
                    recent = self._conversation_log[-8:]
                    context += "\n\n--- Recent Conversation ---\n"
                    context += "\n".join(recent)

                engine.mark_proactive_fired()

                try:
                    prompt = (
                        f"[PROACTIVE CHECK-IN]\n"
                        f"The user has been idle. Here's the full context:\n\n"
                        f"{context}\n\n"
                        f"Based on this context, decide whether to say something "
                        f"brief and useful, or stay completely silent. "
                        f"Do NOT call any tools."
                    )
                    await self._session.send_client_content(
                        turns=[types.Content(
                            role="user",
                            parts=[types.Part(text=prompt)]
                        )],
                        turn_complete=True,
                    )
                except Exception as e:
                    logger.warning(f"Proactive engagement failed: {e}")

    # ── Dashboard Command Task ──────────────────────────────────

    async def _dashboard_command_task(self) -> None:
        """Process text commands injected from the remote dashboard."""
        while self._running:
            try:
                command = await asyncio.wait_for(
                    self._dashboard_queue.get(), timeout=2.0
                )
                if self._session:
                    self._emit_log(f"📱 Remote: {command}", "user")
                    await self._session.send_client_content(
                        turns=[types.Content(
                            role="user",
                            parts=[types.Part(text=command)]
                        )],
                        turn_complete=True,
                    )
                    self._last_interaction_time = time.time()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.warning(f"Dashboard command error: {e}")

    # ── Phone Audio Relay Task ──────────────────────────────────

    async def _relay_phone_audio_task(self) -> None:
        """Bridge phone microphone WebSocket audio into the live session."""
        while self._running:
            try:
                audio_data = await asyncio.wait_for(
                    self._phone_audio_queue.get(), timeout=2.0
                )
                if self._session:
                    await self._session.send_realtime_input(
                        audio=types.Blob(
                            data=audio_data,
                            mime_type="audio/pcm;rate=16000"
                        )
                    )
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.warning(f"Phone audio relay error: {e}")

    # ── Topic Monitor Task ──────────────────────────────────────

    async def _topic_monitor_task(self) -> None:
        """Periodically check monitored topics for new headlines."""
        # Wait for session to fully initialize
        await asyncio.sleep(60)

        while self._running:
            try:
                from actions.topic_monitor import topic_monitor
                alerts = await asyncio.get_running_loop().run_in_executor(
                    None, topic_monitor.check_all_topics
                )
                if alerts and self._session:
                    alert_text = "\n".join(alerts)
                    self._emit_log(f"📡 Topic alerts: {len(alerts)}", "system")
                    await self._session.send_client_content(
                        turns=[types.Content(
                            role="user",
                            parts=[types.Part(
                                text=(
                                    f"Background monitor alerts:\n{alert_text}\n\n"
                                    f"Briefly inform the user about these updates. "
                                    f"Keep it concise — 1-2 sentences per alert."
                                )
                            )]
                        )],
                        turn_complete=True,
                    )
            except Exception as e:
                logger.warning(f"Topic monitor error: {e}")

            # Check every 30 minutes
            await asyncio.sleep(1800)

    # ── Startup Briefing ────────────────────────────────────────

    async def _startup_briefing(self) -> None:
        """Send a greeting after session stabilizes, with previous session callback."""
        await asyncio.sleep(3)

        assistant_name = config.get("assistant_name", "EVA")
        user_name = config.get("user_name", "User")

        # Pop previous session summary (consume-once)
        prev_session = session_memory.pop_latest()

        if self._session:
            from datetime import datetime, timezone, timedelta
            ist = timezone(timedelta(hours=5, minutes=30))
            time_str = datetime.now(ist).strftime('%I:%M %p')

            greeting = (
                f"Greet {user_name} warmly as {assistant_name}. "
                f"The current time is {time_str} IST. Mention the time naturally. "
                f"Keep it brief and natural — 2-3 sentences max."
            )
            if config.get("morning_briefing", True):
                greeting += " If it's morning, offer a morning briefing."

            if prev_session:
                summary = prev_session.get('summary', '')
                prev_date = prev_session.get('date', '')
                greeting += (
                    f"\n\nLast session ({prev_date}), you discussed: "
                    f"{summary}. Reference it naturally if relevant — "
                    f"a brief callback like 'Last time we talked about...'"
                )

            try:
                await self._session.send_client_content(
                    turns=[types.Content(
                        role="user",
                        parts=[types.Part(text=greeting)]
                    )],
                    turn_complete=True,
                )
            except Exception as e:
                logger.warning(f"Greeting failed: {e}")

    # ── Session Summary ─────────────────────────────────────────

    async def _save_session_summary(self) -> None:
        """Generate a 1-2 sentence session summary and persist it."""
        if not self._conversation_log:
            return

        try:
            from core.llm_router import smart_generate

            # Take last ~10 conversation turns
            recent = self._conversation_log[-10:]
            transcript = "\n".join(recent)

            prompt = (
                f"Summarize this conversation in 1-2 sentences (max 280 chars). "
                f"Focus on what was discussed or accomplished. "
                f"Write in the same language the conversation used.\n\n"
                f"{transcript}"
            )

            result = await asyncio.get_running_loop().run_in_executor(
                None, lambda: smart_generate(prompt)
            )

            if result and "unavailable" not in result.lower():
                language = config.get("language", "en")
                session_memory.append_session(result.strip(), language)
                logger.info("Session summary saved")

        except Exception as e:
            logger.warning(f"Session summary generation failed: {e}")

    # ── External API ────────────────────────────────────────────

    def inject_text_command(self, text: str) -> None:
        """Inject a text command into the session (from UI or dashboard)."""
        if self._loop:
            self._loop.call_soon_threadsafe(
                self._dashboard_queue.put_nowait, text
            )

    def inject_phone_audio(self, data: bytes) -> None:
        """Inject phone mic audio data."""
        if self._loop:
            self._loop.call_soon_threadsafe(
                self._phone_audio_queue.put_nowait, data
            )

    def interrupt(self) -> None:
        """Handle barge-in: flush audio and signal the session."""
        if self._audio:
            self._audio.interrupt()
        self._is_speaking = False
        self._emit_state("idle")

    # ── UI Signal Helpers ───────────────────────────────────────

    def _on_amplitude(self, source: str, amplitude: float) -> None:
        if self._ui:
            self._ui.update_amplitude_signal.emit(source, amplitude)

    def _emit_state(self, state: str) -> None:
        if self._ui:
            self._ui.update_state_signal.emit(state)

    def _emit_log(self, text: str, source: str) -> None:
        if self._ui:
            self._ui.add_log_signal.emit(text, source)
