"""
EVA Health & Fitness Tracker — Track water intake, exercise, sleep, and
health habits. Provides daily summaries and periodic reminders.
"""

import json
import logging
import threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.health_tracker")

_DATA_DIR = Path(__file__).resolve().parent.parent / "config"
_HEALTH_FILE = _DATA_DIR / "health.json"
_lock = threading.Lock()
_IST = timezone(timedelta(hours=5, minutes=30))

# Daily targets
_TARGETS = {
    "water": 8,        # glasses
    "steps": 10000,
    "sleep": 8,        # hours
    "exercise": 30,    # minutes
    "screen_break": 8, # breaks
}


def _load_data() -> dict:
    if not _HEALTH_FILE.exists():
        return {"days": {}}
    try:
        with open(_HEALTH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"days": {}}


def _save_data(data: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Keep only last 90 days
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    data["days"] = {k: v for k, v in data["days"].items() if k >= cutoff}
    with open(_HEALTH_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _get_today(data: dict) -> dict:
    """Get or create today's entry."""
    today = date.today().isoformat()
    if today not in data["days"]:
        data["days"][today] = {
            "water": 0,
            "steps": 0,
            "sleep": 0,
            "exercise": 0,
            "screen_break": 0,
            "meals": [],
            "mood": "",
            "notes": [],
            "weight": 0,
        }
    return data["days"][today]


def _progress_bar(current: float, target: float) -> str:
    """Create a visual progress bar."""
    pct = min(current / target, 1.0) if target > 0 else 0
    filled = int(pct * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"{bar} {current}/{target} ({pct*100:.0f}%)"


@register_tool(
    name="health_tracker",
    description="Track health and fitness — water intake, exercise, sleep, steps, "
                "meals, mood, weight, and screen breaks. Get daily summaries "
                "and progress towards goals.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: log | summary | history | goals | weight",
            },
            "metric": {
                "type": "STRING",
                "description": "What to log: water | exercise | sleep | steps | "
                               "meal | mood | screen_break | weight",
            },
            "value": {
                "type": "NUMBER",
                "description": "Value to log. Water=glasses, exercise=minutes, "
                               "sleep=hours, steps=count, weight=kg",
            },
            "note": {
                "type": "STRING",
                "description": "Additional note. For meal: describe what you ate. "
                               "For mood: how you're feeling (great/good/okay/bad)",
            },
            "days": {
                "type": "INTEGER",
                "description": "Number of days for history (default: 7)",
            },
        },
        "required": ["action"],
    },
    category="health",
)
def health_tracker(
    action: str,
    metric: str = "",
    value: float = 0,
    note: str = "",
    days: int = 7,
) -> str:
    """Track health metrics."""
    action = action.lower().strip()
    metric = metric.lower().strip()

    with _lock:
        data = _load_data()

    # ── Log a metric ─────────────────────────────────────────
    if action == "log":
        if not metric:
            return "What should I log? Options: water, exercise, sleep, steps, meal, mood, screen_break, weight"

        today = _get_today(data)

        if metric == "water":
            amount = int(value) if value > 0 else 1
            today["water"] += amount
            _save_data(data)
            return (
                f"💧 Logged {amount} glass(es) of water.\n"
                f"   Today: {_progress_bar(today['water'], _TARGETS['water'])}"
            )

        elif metric == "exercise":
            minutes = int(value) if value > 0 else 30
            today["exercise"] += minutes
            _save_data(data)
            return (
                f"🏃 Logged {minutes} min of exercise.\n"
                f"   Today: {_progress_bar(today['exercise'], _TARGETS['exercise'])}"
            )

        elif metric == "sleep":
            hours = value if value > 0 else 8
            today["sleep"] = hours
            _save_data(data)
            return (
                f"😴 Logged {hours}h of sleep.\n"
                f"   Target: {_progress_bar(hours, _TARGETS['sleep'])}"
            )

        elif metric == "steps":
            count = int(value) if value > 0 else 0
            today["steps"] = count
            _save_data(data)
            return (
                f"👣 Logged {count:,} steps.\n"
                f"   Goal: {_progress_bar(count, _TARGETS['steps'])}"
            )

        elif metric == "meal":
            meal_desc = note or "Meal logged"
            today["meals"].append({
                "desc": meal_desc,
                "time": datetime.now(_IST).strftime("%I:%M %p"),
            })
            _save_data(data)
            return f"🍽️ Meal logged: {meal_desc} at {datetime.now(_IST).strftime('%I:%M %p')}"

        elif metric == "mood":
            mood = note or ("great" if value >= 4 else "good" if value >= 3 else "okay")
            today["mood"] = mood
            _save_data(data)
            emoji = {"great": "😊", "good": "🙂", "okay": "😐", "bad": "😔"}.get(mood, "🙂")
            return f"{emoji} Mood logged: {mood}"

        elif metric == "screen_break":
            today["screen_break"] += 1
            _save_data(data)
            return (
                f"👀 Screen break logged!\n"
                f"   Today: {_progress_bar(today['screen_break'], _TARGETS['screen_break'])}"
            )

        elif metric == "weight":
            if value <= 0:
                return "What's your weight (in kg)?"
            today["weight"] = value
            _save_data(data)
            return f"⚖️ Weight logged: {value} kg"

        return f"Unknown metric '{metric}'."

    # ── Daily summary ────────────────────────────────────────
    elif action == "summary":
        today_key = date.today().isoformat()
        if today_key not in data["days"]:
            return "No health data logged today yet. Start by logging something!"

        today = data["days"][today_key]
        lines = [
            f"🏥 Health Summary — {date.today().strftime('%A, %B %d')}:\n",
            f"  💧 Water: {_progress_bar(today.get('water', 0), _TARGETS['water'])}",
            f"  🏃 Exercise: {_progress_bar(today.get('exercise', 0), _TARGETS['exercise'])} min",
            f"  😴 Sleep: {_progress_bar(today.get('sleep', 0), _TARGETS['sleep'])} hours",
            f"  👣 Steps: {_progress_bar(today.get('steps', 0), _TARGETS['steps'])}",
            f"  👀 Screen breaks: {_progress_bar(today.get('screen_break', 0), _TARGETS['screen_break'])}",
        ]

        if today.get("mood"):
            lines.append(f"  🎭 Mood: {today['mood']}")
        if today.get("weight"):
            lines.append(f"  ⚖️ Weight: {today['weight']} kg")
        if today.get("meals"):
            meals = ", ".join(m["desc"] for m in today["meals"])
            lines.append(f"  🍽️ Meals: {meals}")

        return "\n".join(lines)

    # ── History ──────────────────────────────────────────────
    elif action == "history":
        days = min(max(days, 1), 30)
        lines = [f"📊 Health History — Last {days} days:\n"]

        for i in range(days):
            d = (date.today() - timedelta(days=i)).isoformat()
            day_data = data["days"].get(d, {})
            if day_data:
                day_name = (date.today() - timedelta(days=i)).strftime("%a %b %d")
                w = day_data.get("water", 0)
                e = day_data.get("exercise", 0)
                s = day_data.get("sleep", 0)
                lines.append(f"  {day_name}: 💧{w} 🏃{e}min 😴{s}h")

        return "\n".join(lines) if len(lines) > 1 else "No health history yet."

    # ── Goals ────────────────────────────────────────────────
    elif action == "goals":
        lines = ["🎯 Daily Health Goals:\n"]
        for metric, target in _TARGETS.items():
            unit = {"water": "glasses", "steps": "steps", "sleep": "hours",
                    "exercise": "minutes", "screen_break": "breaks"}.get(metric, "")
            lines.append(f"  • {metric}: {target} {unit}")
        return "\n".join(lines)

    return f"Unknown health action '{action}'. Use: log, summary, history, goals."
