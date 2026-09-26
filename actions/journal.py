"""
EVA Daily Journal — Auto-generate conversation summaries and maintain a searchable journal.
Extends session memory with full conversation logging and Gemini-powered summarization.
"""

import json
import logging
import threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.journal")

_DATA_DIR = Path(__file__).resolve().parent.parent / "config"
_JOURNAL_FILE = _DATA_DIR / "journal.json"
_lock = threading.Lock()

_IST = timezone(timedelta(hours=5, minutes=30))


def _load_journal() -> list[dict]:
    """Load journal entries from disk."""
    if not _JOURNAL_FILE.exists():
        return []
    try:
        with open(_JOURNAL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("entries", [])
    except (json.JSONDecodeError, IOError):
        return []


def _save_journal(entries: list[dict]) -> None:
    """Save journal to disk."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_JOURNAL_FILE, "w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f, indent=2, ensure_ascii=False)


class ConversationLogger:
    """Collects conversation turns during a session for end-of-day summarization."""

    _instance: Optional["ConversationLogger"] = None

    def __new__(cls) -> "ConversationLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._lock = threading.Lock()
        self._turns: list[dict] = []
        self._session_start: str = datetime.now(_IST).isoformat()
        self._initialized = True

    def log_turn(self, speaker: str, text: str) -> None:
        """Log a conversation turn."""
        if not text or len(text.strip()) < 2:
            return
        with self._lock:
            self._turns.append({
                "speaker": speaker,
                "text": text.strip()[:500],
                "time": datetime.now(_IST).strftime("%I:%M %p"),
            })

    def get_turns(self) -> list[dict]:
        """Get all logged turns."""
        with self._lock:
            return list(self._turns)

    def get_summary_text(self) -> str:
        """Get a plain text dump of the conversation for summarization."""
        with self._lock:
            if not self._turns:
                return ""
            lines = []
            for t in self._turns:
                lines.append(f"[{t['time']}] {t['speaker']}: {t['text']}")
            return "\n".join(lines)

    def clear(self) -> None:
        """Clear the current session log."""
        with self._lock:
            self._turns = []
            self._session_start = datetime.now(_IST).isoformat()

    @property
    def turn_count(self) -> int:
        with self._lock:
            return len(self._turns)


# Singleton
conversation_logger = ConversationLogger()


def save_daily_entry(summary: str, highlights: str = "") -> None:
    """Save a journal entry for today (called at shutdown or manually)."""
    today = date.today().isoformat()

    with _lock:
        entries = _load_journal()

        entry = {
            "date": today,
            "date_display": datetime.now(_IST).strftime("%A, %B %d, %Y"),
            "summary": summary[:800],
            "highlights": highlights[:400],
            "turn_count": conversation_logger.turn_count,
            "created_at": datetime.now(_IST).isoformat(),
        }

        # Check if today already has an entry — append to it
        existing = next((e for e in entries if e["date"] == today), None)
        if existing:
            existing["summary"] += f"\n\n--- Later ---\n{summary[:400]}"
            existing["turn_count"] += conversation_logger.turn_count
            if highlights:
                existing["highlights"] += f"; {highlights[:200]}"
        else:
            entries.append(entry)

        # Keep last 90 days
        cutoff = (date.today() - timedelta(days=90)).isoformat()
        entries = [e for e in entries if e["date"] >= cutoff]

        _save_journal(entries)
        logger.info(f"Journal entry saved for {today}")


@register_tool(
    name="journal",
    description="Access EVA's daily journal — view past conversation summaries, "
                "search through history, add personal notes, or see what you "
                "discussed on a specific date.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: today | yesterday | list | search | note | stats",
            },
            "query": {
                "type": "STRING",
                "description": "Search term for search action, or note text for note action.",
            },
            "days": {
                "type": "INTEGER",
                "description": "Number of past days to show (for list action, default: 7)",
            },
        },
        "required": ["action"],
    },
    category="memory",
)
def journal(action: str, query: str = "", days: int = 7) -> str:
    """Access and manage the daily journal."""
    action = action.lower().strip()

    with _lock:
        entries = _load_journal()

    # ── Today's journal ──────────────────────────────────────
    if action == "today":
        today = date.today().isoformat()
        entry = next((e for e in entries if e["date"] == today), None)

        # Include current session info
        current_turns = conversation_logger.turn_count
        current_summary = ""
        if current_turns > 0:
            current_summary = (
                f"\n\nCurrent session: {current_turns} conversation turns so far."
            )

        if entry:
            return (
                f"📔 Journal — {entry['date_display']}:\n\n"
                f"{entry['summary']}"
                f"{current_summary}"
            )
        elif current_turns > 0:
            return (
                f"📔 Today ({date.today().strftime('%A, %B %d')}):\n"
                f"No saved journal entry yet, but we've had {current_turns} "
                f"conversation turns this session."
            )
        return "No journal entry for today yet."

    # ── Yesterday ────────────────────────────────────────────
    elif action == "yesterday":
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        entry = next((e for e in entries if e["date"] == yesterday), None)
        if entry:
            return (
                f"📔 Journal — {entry['date_display']}:\n\n"
                f"{entry['summary']}"
            )
        return "No journal entry for yesterday."

    # ── List recent entries ──────────────────────────────────
    elif action == "list":
        days = min(max(days, 1), 90)
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        recent = [e for e in entries if e["date"] >= cutoff]
        recent.reverse()  # newest first

        if not recent:
            return f"No journal entries in the last {days} days."

        lines = []
        for e in recent[:15]:
            preview = e["summary"][:100].replace("\n", " ")
            lines.append(
                f"  📅 {e['date_display']}: {preview}..."
            )
        return f"📔 Journal — Last {days} days ({len(recent)} entries):\n\n" + "\n".join(lines)

    # ── Search journal ───────────────────────────────────────
    elif action == "search":
        if not query:
            return "What should I search for in your journal?"

        query_lower = query.lower()
        matches = [
            e for e in entries
            if query_lower in e.get("summary", "").lower()
            or query_lower in e.get("highlights", "").lower()
        ]

        if not matches:
            return f"No journal entries matching '{query}'."

        matches.reverse()
        lines = []
        for e in matches[:10]:
            preview = e["summary"][:120].replace("\n", " ")
            lines.append(f"  📅 {e['date_display']}: {preview}...")

        return (
            f"📔 Found {len(matches)} entries matching '{query}':\n\n"
            + "\n".join(lines)
        )

    # ── Add a personal note ──────────────────────────────────
    elif action == "note":
        if not query:
            return "What note would you like to add to today's journal?"

        today = date.today().isoformat()
        with _lock:
            entries_w = _load_journal()
            existing = next((e for e in entries_w if e["date"] == today), None)
            if existing:
                existing["summary"] += f"\n\n📝 Note: {query}"
            else:
                entries_w.append({
                    "date": today,
                    "date_display": datetime.now(_IST).strftime("%A, %B %d, %Y"),
                    "summary": f"📝 Note: {query}",
                    "highlights": "",
                    "turn_count": 0,
                    "created_at": datetime.now(_IST).isoformat(),
                })
            _save_journal(entries_w)

        return f"📝 Note added to today's journal: \"{query}\""

    # ── Stats ────────────────────────────────────────────────
    elif action == "stats":
        total = len(entries)
        if total == 0:
            return "No journal entries yet. We'll start logging as we chat!"

        total_turns = sum(e.get("turn_count", 0) for e in entries)
        date_range = f"{entries[0].get('date_display', '?')} to {entries[-1].get('date_display', '?')}"

        # Streak calculation
        today = date.today()
        streak = 0
        for i in range(90):
            d = (today - timedelta(days=i)).isoformat()
            if any(e["date"] == d for e in entries):
                streak += 1
            else:
                break

        return (
            f"📊 Journal Stats:\n"
            f"  • Total entries: {total}\n"
            f"  • Total conversations: ~{total_turns} turns\n"
            f"  • Date range: {date_range}\n"
            f"  • Current streak: {streak} day(s)"
        )

    else:
        return f"Unknown journal action '{action}'. Use: today, yesterday, list, search, note, or stats."
