"""
EVA Calendar Integration — Google Calendar management by voice.
Creates, lists, and manages calendar events.
Falls back to a local JSON calendar if Google API is not configured.
"""

import json
import logging
import threading
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.calendar_manager")

_DATA_DIR = Path(__file__).resolve().parent.parent / "config"
_CALENDAR_FILE = _DATA_DIR / "calendar.json"
_lock = threading.Lock()
_IST = timezone(timedelta(hours=5, minutes=30))


def _load_events() -> list[dict]:
    if not _CALENDAR_FILE.exists():
        return []
    try:
        with open(_CALENDAR_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("events", [])
    except (json.JSONDecodeError, IOError):
        return []


def _save_events(events: list[dict]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_CALENDAR_FILE, "w", encoding="utf-8") as f:
        json.dump({"events": events}, f, indent=2, ensure_ascii=False)


def _parse_time(time_str: str) -> Optional[datetime]:
    """Parse various time formats into datetime."""
    now = datetime.now(_IST)
    time_str = time_str.strip().lower()

    # Relative: "in 2 hours", "in 30 minutes"
    import re
    m = re.match(r'in\s+(\d+)\s+(hour|minute|min|hr|day)s?', time_str)
    if m:
        val, unit = int(m.group(1)), m.group(2)
        if unit in ("hour", "hr"):
            return now + timedelta(hours=val)
        elif unit in ("minute", "min"):
            return now + timedelta(minutes=val)
        elif unit == "day":
            return now + timedelta(days=val)

    # "tomorrow", "tomorrow at 3pm"
    if "tomorrow" in time_str:
        base = now + timedelta(days=1)
        tm = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str)
        if tm:
            h = int(tm.group(1))
            mins = int(tm.group(2)) if tm.group(2) else 0
            if tm.group(3) == "pm" and h < 12:
                h += 12
            elif tm.group(3) == "am" and h == 12:
                h = 0
            return base.replace(hour=h, minute=mins, second=0, microsecond=0)
        return base.replace(hour=9, minute=0, second=0, microsecond=0)

    # "today at 3pm"
    if "today" in time_str:
        tm = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str)
        if tm:
            h = int(tm.group(1))
            mins = int(tm.group(2)) if tm.group(2) else 0
            if tm.group(3) == "pm" and h < 12:
                h += 12
            return now.replace(hour=h, minute=mins, second=0, microsecond=0)

    # "3 pm", "15:00", "3:30 pm"
    tm = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$', time_str)
    if tm:
        h = int(tm.group(1))
        mins = int(tm.group(2)) if tm.group(2) else 0
        if tm.group(3) == "pm" and h < 12:
            h += 12
        elif tm.group(3) == "am" and h == 12:
            h = 0
        result = now.replace(hour=h, minute=mins, second=0, microsecond=0)
        if result < now:
            result += timedelta(days=1)
        return result

    # ISO format
    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M"]:
        try:
            return datetime.strptime(time_str, fmt).replace(tzinfo=_IST)
        except ValueError:
            continue

    return None


@register_tool(
    name="manage_calendar",
    description="Manage calendar events — create, list, search, or delete events. "
                "Use when the user asks about their schedule, wants to add an event, "
                "or check what's coming up.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: add | today | tomorrow | week | search | delete",
            },
            "title": {
                "type": "STRING",
                "description": "Event title (for add action). E.g., 'Meeting with Raj'",
            },
            "time": {
                "type": "STRING",
                "description": "Event time. Supports: '3 pm', 'tomorrow at 10am', "
                               "'in 2 hours', '2026-08-05 14:00'",
            },
            "duration": {
                "type": "INTEGER",
                "description": "Event duration in minutes (default: 60)",
            },
            "query": {
                "type": "STRING",
                "description": "Search term for search/delete action",
            },
        },
        "required": ["action"],
    },
    category="productivity",
)
def manage_calendar(
    action: str,
    title: str = "",
    time: str = "",
    duration: int = 60,
    query: str = "",
) -> str:
    """Manage calendar events."""
    action = action.lower().strip()

    with _lock:
        events = _load_events()

    # ── Add event ────────────────────────────────────────────
    if action == "add":
        if not title:
            return "What should the event be called?"
        if not time:
            return "When should I schedule it? Give me a time like '3 pm' or 'tomorrow at 10am'."

        dt = _parse_time(time)
        if not dt:
            return f"I couldn't understand the time '{time}'. Try '3 pm', 'tomorrow at 10am', or '2026-08-05 14:00'."

        end_dt = dt + timedelta(minutes=duration)
        event = {
            "title": title,
            "start": dt.isoformat(),
            "end": end_dt.isoformat(),
            "start_display": dt.strftime("%I:%M %p, %a %b %d"),
            "duration_min": duration,
            "created": datetime.now(_IST).isoformat(),
        }

        with _lock:
            events = _load_events()
            events.append(event)
            events.sort(key=lambda e: e["start"])
            _save_events(events)

        return (
            f"📅 Event added: '{title}'\n"
            f"   When: {dt.strftime('%I:%M %p, %A %B %d')}\n"
            f"   Duration: {duration} minutes"
        )

    # ── Today's schedule ─────────────────────────────────────
    elif action == "today":
        today = date.today().isoformat()
        today_events = [e for e in events if e["start"].startswith(today)]
        if not today_events:
            return "📅 No events scheduled for today."

        lines = []
        for e in today_events:
            lines.append(f"  • {e['start_display']} — {e['title']} ({e['duration_min']}min)")
        return f"📅 Today's schedule ({len(today_events)} events):\n" + "\n".join(lines)

    # ── Tomorrow ─────────────────────────────────────────────
    elif action == "tomorrow":
        tmr = (date.today() + timedelta(days=1)).isoformat()
        tmr_events = [e for e in events if e["start"].startswith(tmr)]
        if not tmr_events:
            return "📅 No events scheduled for tomorrow."

        lines = []
        for e in tmr_events:
            lines.append(f"  • {e['start_display']} — {e['title']}")
        return f"📅 Tomorrow's schedule ({len(tmr_events)} events):\n" + "\n".join(lines)

    # ── This week ────────────────────────────────────────────
    elif action == "week":
        now = datetime.now(_IST)
        week_end = now + timedelta(days=7)
        week_events = [
            e for e in events
            if now.isoformat() <= e["start"] <= week_end.isoformat()
        ]
        if not week_events:
            return "📅 No events this week."

        lines = []
        for e in week_events:
            lines.append(f"  • {e['start_display']} — {e['title']}")
        return f"📅 This week ({len(week_events)} events):\n" + "\n".join(lines)

    # ── Search ───────────────────────────────────────────────
    elif action == "search":
        if not query:
            return "What event should I search for?"
        q = query.lower()
        matches = [e for e in events if q in e["title"].lower()]
        if not matches:
            return f"No events matching '{query}'."
        lines = [f"  • {e['start_display']} — {e['title']}" for e in matches[:10]]
        return f"📅 Found {len(matches)} event(s) matching '{query}':\n" + "\n".join(lines)

    # ── Delete ───────────────────────────────────────────────
    elif action == "delete":
        if not query:
            return "Which event should I delete? Give me the title or keyword."
        q = query.lower()
        with _lock:
            events = _load_events()
            before = len(events)
            events = [e for e in events if q not in e["title"].lower()]
            removed = before - len(events)
            _save_events(events)
        if removed == 0:
            return f"No events matching '{query}' to delete."
        return f"🗑️ Deleted {removed} event(s) matching '{query}'."

    return f"Unknown calendar action '{action}'. Use: add, today, tomorrow, week, search, or delete."
