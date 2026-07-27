"""
EVA Session Memory
End-of-session summary storage with consume-once retrieval.
Summaries are saved to a JSON file and popped on next startup
briefing so each summary is used exactly once.
"""

import json
import logging
import threading
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger("eva.memory.session")

_SESSION_DIR = Path(__file__).resolve().parent.parent / "config"
_SESSION_FILE = _SESSION_DIR / "sessions.json"
_MAX_SESSIONS = 3


class SessionMemory:
    """Thread-safe session summary store (singleton)."""

    _instance: Optional["SessionMemory"] = None

    def __new__(cls) -> "SessionMemory":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._lock = threading.Lock()
        self._sessions: list[dict] = []
        self._load()
        self._initialized = True

    # ── Public API ──────────────────────────────────────────────

    def append_session(self, summary: str, language: str = "") -> None:
        """
        Append a session summary, truncated to ~280 chars.
        Keeps only the last _MAX_SESSIONS entries.
        """
        truncated = summary[:280].strip()
        if not truncated:
            return

        entry = {
            "date": date.today().isoformat(),
            "summary": truncated,
            "language": language or "en",
        }

        with self._lock:
            self._sessions.append(entry)
            # Cap at last N entries
            if len(self._sessions) > _MAX_SESSIONS:
                self._sessions = self._sessions[-_MAX_SESSIONS:]
            self._save()

        logger.info(f"Session summary saved ({len(truncated)} chars)")

    def pop_latest(self) -> Optional[dict]:
        """
        Read and remove the most recent session entry.
        Returns None if no sessions are stored.
        Consume-once: the entry is deleted after retrieval.
        """
        with self._lock:
            if not self._sessions:
                return None
            entry = self._sessions.pop()
            self._save()

        logger.info(f"Popped session from {entry.get('date', '?')}")
        return entry

    def get_all(self) -> list[dict]:
        """Return all stored sessions (read-only copy)."""
        with self._lock:
            return list(self._sessions)

    # ── Internal ────────────────────────────────────────────────

    def _load(self) -> None:
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
        if _SESSION_FILE.exists():
            try:
                with open(_SESSION_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._sessions = data.get("sessions", [])
            except (json.JSONDecodeError, IOError):
                self._sessions = []
        else:
            self._sessions = []

    def _save(self) -> None:
        """Write sessions to disk. Must be called under self._lock."""
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
        with open(_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump({"sessions": self._sessions}, f,
                      indent=2, ensure_ascii=False)


# Module-level singleton
session_memory = SessionMemory()
