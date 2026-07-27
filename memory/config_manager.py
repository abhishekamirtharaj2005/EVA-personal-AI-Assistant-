"""
EVA Configuration Manager
Persists API keys, assistant/user names, accent color, toggles to JSON.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

# Default config directory alongside the project root
_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_SETTINGS_FILE = _CONFIG_DIR / "settings.json"

_DEFAULTS = {
    # ── API Keys ──────────────────────────────────────────
    "api_key": "",               # Gemini API key (primary)
    "openai_api_key": "",        # OpenAI API key
    "anthropic_api_key": "",     # Anthropic API key

    # ── Identity ──────────────────────────────────────────
    "assistant_name": "EVA",
    "user_name": "User",

    # ── Model & Voice ─────────────────────────────────────
    "preferred_model": "gemini-3.1-flash-live-preview",
    "voice_name": "Aoede",       # Aoede, Charon, Fenrir, Kore, Puck
    "tts_enabled": True,

    # ── Appearance ────────────────────────────────────────
    "accent_hue": 180,           # HSL hue 0-360, default cyan
    "accent_color": "#00ffd5",   # Neon cyan
    "theme_mode": "cyberpunk",   # cyberpunk | neon | minimal

    # ── Behavior ──────────────────────────────────────────
    "morning_briefing": True,
    "proactive_mode": True,
    "proactive_idle_seconds": 300,
    "hotkey_push_to_talk": "ctrl+space",

    # ── System Monitor ────────────────────────────────────
    "system_monitor_interval": 30,
    "cpu_alert_threshold": 90,
    "ram_alert_threshold": 90,
    "gpu_alert_threshold": 90,
    "temp_alert_threshold": 85,

    # ── Local LLM (Ollama) ────────────────────────────────
    "ollama_enabled": True,
    "ollama_url": "http://localhost:11434",
    "ollama_model": "",             # Auto-detect if blank
    "ollama_vision_model": "",      # Auto-detect if blank

    # ── Misc ──────────────────────────────────────────────
    "clipboard_min_chars": 10,
    "dashboard_port": 8765,
    "auto_start": False,
    "first_run": True,
    "language": "",
    "city": "",
}


class ConfigManager:
    """Thread-safe JSON-backed configuration store."""

    _instance: Optional["ConfigManager"] = None

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self) -> None:
        if self._loaded:
            return
        self._data: dict[str, Any] = {}
        self._load()
        self._loaded = True

    # ── public API ──────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Return config value, falling back to built-in default."""
        return self._data.get(key, _DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        """Set a config value and persist to disk."""
        self._data[key] = value
        self._save()

    def update(self, **kwargs: Any) -> None:
        """Bulk-set multiple keys and persist once."""
        self._data.update(kwargs)
        self._save()

    def is_first_run(self) -> bool:
        return self.get("first_run", True) or not self.get("api_key")

    def complete_setup(self, api_key: str, user_name: str = "",
                       assistant_name: str = "") -> None:
        """Called after the first-run wizard finishes."""
        updates: dict[str, Any] = {"api_key": api_key, "first_run": False}
        if user_name:
            updates["user_name"] = user_name
        if assistant_name:
            updates["assistant_name"] = assistant_name
        self.update(**updates)

    def as_dict(self) -> dict[str, Any]:
        """Return a merged view of defaults + overrides (read-only copy)."""
        merged = dict(_DEFAULTS)
        merged.update(self._data)
        return merged

    # ── persistence ─────────────────────────────────────────────

    def _load(self) -> None:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if _SETTINGS_FILE.exists():
            try:
                with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)


# Module-level singleton shortcut
config = ConfigManager()
