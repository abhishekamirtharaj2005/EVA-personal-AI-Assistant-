"""
EVA Focus Mode — Block distracting apps and websites during work sessions.
Monitors running processes and closes blacklisted applications.
"""

import logging
import subprocess
import threading
import time
from typing import Optional

from core.tool_dispatcher import register_tool
from utils.platform_utils import IS_WINDOWS

logger = logging.getLogger("eva.actions.focus_mode")


class FocusSession:
    """Manages an active focus session with app blocking."""

    def __init__(self):
        self._active: bool = False
        self._blocked_apps: list[str] = []
        self._duration_minutes: int = 0
        self._start_time: float = 0.0
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def remaining_minutes(self) -> int:
        if not self._active:
            return 0
        elapsed = (time.time() - self._start_time) / 60
        remaining = self._duration_minutes - elapsed
        return max(0, int(remaining))

    @property
    def blocked_apps(self) -> list[str]:
        return list(self._blocked_apps)

    def start(self, apps: list[str], duration: int) -> None:
        """Start a focus session."""
        self._blocked_apps = [a.lower().strip() for a in apps]
        self._duration_minutes = duration
        self._start_time = time.time()
        self._active = True
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="focus-mode"
        )
        self._thread.start()
        logger.info(
            f"Focus mode started: {duration}min, blocking: {self._blocked_apps}"
        )

    def stop(self) -> None:
        """End the focus session."""
        self._active = False
        self._stop_event.set()
        self._blocked_apps = []
        logger.info("Focus mode ended.")

    def _monitor_loop(self) -> None:
        """Background loop that monitors and closes blocked apps."""
        while not self._stop_event.is_set():
            # Check time limit
            elapsed = (time.time() - self._start_time) / 60
            if elapsed >= self._duration_minutes:
                logger.info("Focus mode time expired.")
                self._active = False
                break

            # Kill blocked apps
            self._enforce_blocks()

            # Check every 3 seconds
            self._stop_event.wait(timeout=3)

    def _enforce_blocks(self) -> None:
        """Close any running instances of blocked apps."""
        if not IS_WINDOWS:
            return

        for app_name in self._blocked_apps:
            exe_names = _resolve_exe_name(app_name)
            for exe in exe_names:
                try:
                    result = subprocess.run(
                        ["tasklist", "/FI", f"IMAGENAME eq {exe}", "/FO", "CSV"],
                        capture_output=True, text=True, timeout=5,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    if exe.lower() in result.stdout.lower():
                        subprocess.run(
                            ["taskkill", "/IM", exe, "/F"],
                            capture_output=True, timeout=5,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                        logger.info(f"Focus: Blocked {exe}")
                except Exception as e:
                    logger.debug(f"Focus check error for {exe}: {e}")


def _resolve_exe_name(app_name: str) -> list[str]:
    """Map common app names to their executable names."""
    mapping = {
        "youtube": ["chrome.exe", "msedge.exe", "firefox.exe"],  # Browser-based
        "reddit": ["chrome.exe", "msedge.exe", "firefox.exe"],
        "twitter": ["chrome.exe", "msedge.exe", "firefox.exe"],
        "instagram": ["chrome.exe", "msedge.exe", "firefox.exe"],
        "facebook": ["chrome.exe", "msedge.exe", "firefox.exe"],
        "tiktok": ["chrome.exe", "msedge.exe", "firefox.exe"],
        "discord": ["Discord.exe", "Update.exe"],
        "telegram": ["Telegram.exe"],
        "whatsapp": ["WhatsApp.exe"],
        "spotify": ["Spotify.exe"],
        "steam": ["steam.exe", "steamwebhelper.exe"],
        "epic": ["EpicGamesLauncher.exe"],
        "games": ["steam.exe", "EpicGamesLauncher.exe"],
        "netflix": ["chrome.exe", "msedge.exe"],
    }

    lower = app_name.lower()
    if lower in mapping:
        return mapping[lower]

    # Try direct exe name
    if not lower.endswith(".exe"):
        return [f"{lower}.exe"]
    return [lower]


# Module singleton
_session = FocusSession()


def get_focus_session() -> FocusSession:
    return _session


# Default distraction lists
_PRESETS = {
    "social": ["discord", "telegram", "whatsapp", "twitter", "instagram"],
    "entertainment": ["spotify", "steam", "epic", "netflix"],
    "all": ["discord", "telegram", "whatsapp", "spotify", "steam", "epic"],
}


@register_tool(
    name="focus_mode",
    description="Activate or deactivate focus mode that blocks distracting apps. "
                "When active, EVA monitors and closes blacklisted applications. "
                "Use when the user wants to focus, study, or work without distractions.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: start | stop | status",
            },
            "apps": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "List of apps to block. E.g., ['discord', 'spotify', 'steam']. "
                               "Or use presets: 'social', 'entertainment', 'all'.",
            },
            "duration": {
                "type": "INTEGER",
                "description": "Focus duration in minutes (default: 60, max: 480).",
            },
        },
        "required": ["action"],
    },
    category="productivity",
)
def focus_mode(
    action: str,
    apps: list[str] = None,
    duration: int = 60,
) -> str:
    """Control focus mode."""
    action = action.lower().strip()

    if action == "start":
        if _session.is_active:
            return (
                f"Focus mode is already active with {_session.remaining_minutes} "
                f"minutes remaining. Blocking: {', '.join(_session.blocked_apps)}. "
                f"Say 'stop focus mode' to end it early."
            )

        # Resolve app list
        if not apps:
            apps = _PRESETS["all"]
        else:
            resolved = []
            for a in apps:
                a_lower = a.lower().strip()
                if a_lower in _PRESETS:
                    resolved.extend(_PRESETS[a_lower])
                else:
                    resolved.append(a_lower)
            apps = list(set(resolved))

        duration = min(max(duration, 5), 480)  # 5 min to 8 hours

        _session.start(apps, duration)
        hours = duration // 60
        mins = duration % 60
        time_str = f"{hours}h {mins}m" if hours else f"{mins} minutes"

        return (
            f"🎯 Focus mode activated for {time_str}. "
            f"Blocking: {', '.join(apps)}. "
            f"I'll close these apps if they open. Say 'end focus mode' to stop."
        )

    elif action == "stop":
        if not _session.is_active:
            return "Focus mode is not active."
        remaining = _session.remaining_minutes
        _session.stop()
        return f"🎯 Focus mode ended. You had {remaining} minutes remaining. Nice work!"

    elif action == "status":
        if not _session.is_active:
            return "Focus mode is not active. Want me to start one?"
        return (
            f"🎯 Focus mode active — {_session.remaining_minutes} minutes remaining. "
            f"Blocking: {', '.join(_session.blocked_apps)}"
        )

    else:
        return f"Unknown focus action '{action}'. Use: start, stop, or status."
