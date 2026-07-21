"""
EVA Proactive Engine — Idle-triggered engagement.
Tracks last interaction time; past threshold, assembles context and
lets the model decide whether to say anything.
"""

import logging
import time
from datetime import datetime
from typing import Optional, Callable

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.proactive")


class ProactiveEngine:
    """Manages idle-time proactive engagement."""

    def __init__(self, idle_threshold: int = 120):
        self._last_interaction: float = time.time()
        self._idle_threshold: int = idle_threshold  # seconds
        self._enabled: bool = True
        self._last_proactive: float = 0
        self._proactive_cooldown: int = 300  # 5 min between proactive turns
        self._speak_callback: Optional[Callable] = None

    def touch(self) -> None:
        """Record a user interaction (resets idle timer)."""
        self._last_interaction = time.time()

    @property
    def idle_seconds(self) -> float:
        return time.time() - self._last_interaction

    @property
    def is_idle(self) -> bool:
        return (
            self._enabled
            and self.idle_seconds >= self._idle_threshold
            and (time.time() - self._last_proactive) >= self._proactive_cooldown
        )

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_threshold(self, seconds: int) -> None:
        self._idle_threshold = seconds

    def mark_proactive_fired(self) -> None:
        """Record that a proactive turn was just issued."""
        self._last_proactive = time.time()

    def build_context(self) -> str:
        """
        Assemble a small context bundle for the model to decide
        whether to initiate conversation.
        """
        now = datetime.now()
        parts = [
            f"Current time: {now.strftime('%I:%M %p, %A %B %d')}",
            f"User has been idle for {int(self.idle_seconds)} seconds.",
        ]

        # Time-of-day context
        hour = now.hour
        if 5 <= hour < 12:
            parts.append("It's morning.")
        elif 12 <= hour < 17:
            parts.append("It's afternoon.")
        elif 17 <= hour < 21:
            parts.append("It's evening.")
        else:
            parts.append("It's nighttime.")

        # System context
        try:
            from actions.system_monitor import get_metrics_dict
            metrics = get_metrics_dict()
            if metrics.get("cpu", 0) > 80:
                parts.append(f"CPU usage is high: {metrics['cpu']}%")
            if metrics.get("ram", 0) > 85:
                parts.append(f"RAM usage is high: {metrics['ram']}%")
        except Exception:
            pass

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
