"""
EVA Proactive Engine — Context-aware, time-aware, non-repeating check-ins.
Two independent gates (silence + cooldown), rotating focus modes,
rich context snapshot with memory/topics/conversation.
"""

import logging
import time
from datetime import datetime
from typing import Optional, Callable

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.proactive")


def _get_period_label(hour: int) -> str:
    """Derive a human-readable period label from the hour."""
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 22:
        return "evening"
    else:
        return "late night"


class ProactiveEngine:
    """Manages idle-time proactive engagement with rotating focus."""

    # Focus mode descriptions (cycled via counter % 3)
    _FOCUS_MODES = [
        (
            "Ask about their active projects or goals from memory. "
            "Reference something specific you know about them."
        ),
        (
            "Do a time-of-day wellbeing check-in. If it's late, suggest "
            "rest. If morning, be energizing. Match the mood to the hour."
        ),
        (
            "Share a genuinely interesting fact, suggestion, or idea "
            "based on what you know about the user's interests."
        ),
    ]

    def __init__(self, min_silence_secs: int = 900,
                 check_cooldown: int = 1200):
        # Dual-gate timers using monotonic clock
        self._last_interaction: float = time.monotonic()
        self._last_proactive: float = 0.0
        self._min_silence_secs: int = min_silence_secs    # 15 min default
        self._check_cooldown: int = check_cooldown         # 20 min default

        self._enabled: bool = True
        self._focus_counter: int = 0
        self._speak_callback: Optional[Callable] = None

    def touch(self) -> None:
        """Record a user interaction (resets silence timer)."""
        self._last_interaction = time.monotonic()

    @property
    def silence_seconds(self) -> float:
        """Seconds since the user last spoke."""
        return time.monotonic() - self._last_interaction

    @property
    def cooldown_seconds_remaining(self) -> float:
        """Seconds remaining before proactive can fire again."""
        elapsed = time.monotonic() - self._last_proactive
        return max(0, self._check_cooldown - elapsed)

    @property
    def is_idle(self) -> bool:
        """Check both gates: silence threshold AND cooldown elapsed."""
        now = time.monotonic()
        silence_ok = (now - self._last_interaction) >= self._min_silence_secs
        cooldown_ok = (now - self._last_proactive) >= self._check_cooldown
        return self._enabled and silence_ok and cooldown_ok

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_threshold(self, seconds: int) -> None:
        self._min_silence_secs = seconds

    def mark_proactive_fired(self) -> None:
        """Record that a proactive turn was just issued."""
        self._last_proactive = time.monotonic()
        self._focus_counter += 1

    @property
    def current_focus_mode(self) -> int:
        """Current focus mode index (0, 1, or 2)."""
        return self._focus_counter % 3

    def build_context(self) -> str:
        """
        Assemble a rich context snapshot for the model to decide
        whether to initiate conversation.
        """
        now = datetime.now()
        hour = now.hour
        period = _get_period_label(hour)

        parts = [
            f"Current time: {now.strftime('%I:%M %p, %A %B %d')}",
            f"Time period: {period}",
            f"User has been silent for {int(self.silence_seconds)} seconds.",
        ]

        # Long-term memory
        try:
            from memory.memory_manager import memory
            mem_block = memory.format_memory_for_prompt()
            if mem_block and mem_block != "No memories stored yet.":
                parts.append(f"\n--- User Memory ---\n{mem_block}")
        except Exception:
            pass

        # Active monitored topics
        try:
            from actions.topic_monitor import topic_monitor
            topics = topic_monitor.get_active_topics()
            if topics:
                parts.append(
                    f"\nActive monitored topics: {', '.join(topics)}"
                )
        except Exception:
            pass

        # System context (high resource usage)
        try:
            from actions.system_monitor import get_metrics_dict
            metrics = get_metrics_dict()
            if metrics.get("cpu", 0) > 80:
                parts.append(f"CPU usage is high: {metrics['cpu']}%")
            if metrics.get("ram", 0) > 85:
                parts.append(f"RAM usage is high: {metrics['ram']}%")
        except Exception:
            pass

        # Focus mode instruction
        focus_idx = self.current_focus_mode
        focus_instruction = self._FOCUS_MODES[focus_idx]
        parts.append(f"\n--- Focus for this check-in (mode {focus_idx}) ---")
        parts.append(focus_instruction)

        # Constraints
        parts.append(
            "\n--- Rules ---\n"
            "• 1-2 sentences max.\n"
            "• Speak in the user's language.\n"
            "• Do NOT call any tools.\n"
            "• Stay silent (say nothing) if nothing useful comes to mind."
        )

        return "\n".join(parts)


# Module-level singleton
_engine = ProactiveEngine()


def get_proactive_engine() -> ProactiveEngine:
    """Get the singleton proactive engine instance."""
    return _engine


# Register a no-op tool so the model can call it (routing table entry)
@register_tool(
    name="proactive_check",
    description="Internal: Check if the user has been idle and decide whether "
                "to initiate a conversation. Only called by the proactive engine.",
    parameters={
        "type": "OBJECT",
        "properties": {},
        "required": [],
    },
    category="internal",
)
def proactive_check() -> str:
    """This is called by the proactive system, not directly by the model."""
    return _engine.build_context()
