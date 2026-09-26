"""
EVA Analytics — Track tool usage, conversation patterns, and productivity metrics.
Provides personal analytics like daily activity, most-used tools, and usage trends.
"""

import json
import logging
import threading
import time
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from collections import Counter

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.analytics")

_DATA_DIR = Path(__file__).resolve().parent.parent / "config"
_ANALYTICS_FILE = _DATA_DIR / "analytics.json"
_lock = threading.Lock()
_IST = timezone(timedelta(hours=5, minutes=30))


def _load_data() -> dict:
    if not _ANALYTICS_FILE.exists():
        return {"tool_calls": [], "sessions": [], "conversations": []}
    try:
        with open(_ANALYTICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"tool_calls": [], "sessions": [], "conversations": []}


def _save_data(data: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Keep only last 30 days of data
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    for key in ["tool_calls", "sessions", "conversations"]:
        if key in data:
            data[key] = [
                e for e in data[key]
                if e.get("date", "9999") >= cutoff
            ]
    with open(_ANALYTICS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def log_tool_call(tool_name: str) -> None:
    """Log a tool invocation (called from the dispatcher)."""
    with _lock:
        data = _load_data()
        data["tool_calls"].append({
            "tool": tool_name,
            "date": date.today().isoformat(),
            "time": datetime.now(_IST).strftime("%H:%M"),
            "hour": datetime.now(_IST).hour,
        })
        _save_data(data)


def log_session(duration_minutes: float, turns: int) -> None:
    """Log a completed session."""
    with _lock:
        data = _load_data()
        data["sessions"].append({
            "date": date.today().isoformat(),
            "duration_min": round(duration_minutes, 1),
            "turns": turns,
        })
        _save_data(data)


def log_conversation_turn(speaker: str) -> None:
    """Log a conversation turn."""
    with _lock:
        data = _load_data()
        data["conversations"].append({
            "date": date.today().isoformat(),
            "speaker": speaker,
            "hour": datetime.now(_IST).hour,
        })
        _save_data(data)


@register_tool(
    name="show_analytics",
    description="Show personal usage analytics — which tools are used most, "
                "activity patterns by time of day, daily/weekly stats, "
                "and productivity trends.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "report": {
                "type": "STRING",
                "description": "Report type: overview | tools | activity | trends",
            },
            "days": {
                "type": "INTEGER",
                "description": "Number of days to analyze (default: 7, max: 30)",
            },
        },
        "required": ["report"],
    },
    category="productivity",
)
def show_analytics(report: str = "overview", days: int = 7) -> str:
    """Generate analytics reports."""
    report = report.lower().strip()
    days = min(max(days, 1), 30)
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    with _lock:
        data = _load_data()

    calls = [c for c in data.get("tool_calls", []) if c["date"] >= cutoff]
    sessions = [s for s in data.get("sessions", []) if s["date"] >= cutoff]
    convos = [c for c in data.get("conversations", []) if c["date"] >= cutoff]

    # ── Overview ─────────────────────────────────────────────
    if report == "overview":
        total_calls = len(calls)
        total_sessions = len(sessions)
        total_convos = len(convos)
        total_time = sum(s.get("duration_min", 0) for s in sessions)

        top_tools = Counter(c["tool"] for c in calls).most_common(5)
        top_str = ", ".join(f"{t[0]} ({t[1]}x)" for t in top_tools) or "None"

        # Active hours
        hour_counts = Counter(c.get("hour", 0) for c in calls + convos)
        peak_hour = hour_counts.most_common(1)
        peak_str = f"{peak_hour[0][0]}:00" if peak_hour else "N/A"

        return (
            f"📊 EVA Analytics — Last {days} days:\n\n"
            f"  🔧 Tool calls: {total_calls}\n"
            f"  💬 Conversations: {total_convos} turns\n"
            f"  ⏱️ Total session time: {total_time:.0f} min\n"
            f"  📈 Sessions: {total_sessions}\n\n"
            f"  🏆 Top tools: {top_str}\n"
            f"  ⏰ Peak activity hour: {peak_str}"
        )

    # ── Tool usage breakdown ─────────────────────────────────
    elif report == "tools":
        if not calls:
            return f"No tool usage data in the last {days} days."

        counts = Counter(c["tool"] for c in calls)
        total = len(calls)
        lines = []
        for tool, count in counts.most_common(15):
            pct = count / total * 100
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            lines.append(f"  {bar} {tool}: {count}x ({pct:.0f}%)")

        return (
            f"🔧 Tool Usage — Last {days} days ({total} total calls):\n\n"
            + "\n".join(lines)
        )

    # ── Activity by hour ─────────────────────────────────────
    elif report == "activity":
        all_events = calls + convos
        if not all_events:
            return f"No activity data in the last {days} days."

        hour_counts = Counter(e.get("hour", 0) for e in all_events)
        max_count = max(hour_counts.values()) if hour_counts else 1

        lines = []
        for h in range(24):
            count = hour_counts.get(h, 0)
            bar_len = int(count / max_count * 20) if max_count else 0
            bar = "█" * bar_len
            period = "AM" if h < 12 else "PM"
            display_h = h if h <= 12 else h - 12
            if display_h == 0:
                display_h = 12
            if count > 0:
                lines.append(f"  {display_h:2d}{period} {bar} {count}")

        return (
            f"⏰ Activity by Hour — Last {days} days:\n\n"
            + "\n".join(lines)
        )

    # ── Trends ───────────────────────────────────────────────
    elif report == "trends":
        daily_calls = Counter(c["date"] for c in calls)
        daily_convos = Counter(c["date"] for c in convos)

        lines = []
        for i in range(min(days, 14)):
            d = (date.today() - timedelta(days=i)).isoformat()
            c = daily_calls.get(d, 0)
            v = daily_convos.get(d, 0)
            day_name = (date.today() - timedelta(days=i)).strftime("%a %b %d")
            bar = "█" * min(c + v, 30)
            lines.append(f"  {day_name}: {bar} ({c} tools, {v} msgs)")

        return (
            f"📈 Daily Trends — Last {min(days, 14)} days:\n\n"
            + "\n".join(lines)
        )

    return f"Unknown report '{report}'. Use: overview, tools, activity, or trends."
