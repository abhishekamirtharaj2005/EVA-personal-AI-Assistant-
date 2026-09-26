"""
EVA Expense Tracker — Log expenses by voice, categorize, and get summaries.
Uses a lightweight JSON store (no SQLite dependency needed).
"""

import json
import logging
import threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.expense_tracker")

_DATA_DIR = Path(__file__).resolve().parent.parent / "config"
_EXPENSES_FILE = _DATA_DIR / "expenses.json"
_lock = threading.Lock()

# IST timezone
_IST = timezone(timedelta(hours=5, minutes=30))

# Auto-categorization keywords
_CATEGORY_HINTS = {
    "food": ["food", "lunch", "dinner", "breakfast", "snack", "restaurant",
             "zomato", "swiggy", "pizza", "burger", "coffee", "tea", "chai",
             "biryani", "dosa", "groceries", "grocery", "vegetables", "fruits"],
    "transport": ["uber", "ola", "cab", "taxi", "auto", "bus", "train",
                  "metro", "petrol", "fuel", "diesel", "gas", "parking"],
    "shopping": ["amazon", "flipkart", "myntra", "shopping", "clothes",
                 "shoes", "electronics", "gadget", "phone", "laptop"],
    "entertainment": ["movie", "netflix", "spotify", "game", "concert",
                      "theatre", "cinema", "subscription", "ott"],
    "health": ["medicine", "doctor", "hospital", "gym", "pharmacy",
               "medical", "health", "dental", "eye"],
    "bills": ["electricity", "water", "internet", "wifi", "rent",
              "phone bill", "mobile", "recharge", "gas bill"],
    "education": ["book", "course", "tuition", "udemy", "college",
                  "school", "exam", "study", "stationery"],
}


def _load_expenses() -> list[dict]:
    """Load expenses from disk."""
    if not _EXPENSES_FILE.exists():
        return []
    try:
        with open(_EXPENSES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("expenses", [])
    except (json.JSONDecodeError, IOError):
        return []


def _save_expenses(expenses: list[dict]) -> None:
    """Save expenses to disk."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_EXPENSES_FILE, "w", encoding="utf-8") as f:
        json.dump({"expenses": expenses}, f, indent=2, ensure_ascii=False)


def _auto_categorize(description: str) -> str:
    """Guess category from description keywords."""
    desc_lower = description.lower()
    for category, keywords in _CATEGORY_HINTS.items():
        for kw in keywords:
            if kw in desc_lower:
                return category
    return "other"


def _format_currency(amount: float) -> str:
    """Format amount with ₹ symbol."""
    if amount == int(amount):
        return f"₹{int(amount)}"
    return f"₹{amount:.2f}"


@register_tool(
    name="track_expense",
    description="Track personal expenses. Log new expenses by voice, view spending "
                "summaries (today, this week, this month), list recent transactions, "
                "or check spending by category.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: log | summary | list | delete_last | category_breakdown",
            },
            "amount": {
                "type": "NUMBER",
                "description": "Amount spent (for log action). E.g., 500, 99.50",
            },
            "description": {
                "type": "STRING",
                "description": "What was the expense for (for log action). "
                               "E.g., 'lunch at Dominos', 'Uber to office'",
            },
            "category": {
                "type": "STRING",
                "description": "Category: food | transport | shopping | entertainment | "
                               "health | bills | education | other. Auto-detected if not provided.",
            },
            "period": {
                "type": "STRING",
                "description": "Time period for summary/list: today | week | month | all (default: month)",
            },
        },
        "required": ["action"],
    },
    category="productivity",
)
def track_expense(
    action: str,
    amount: float = 0,
    description: str = "",
    category: str = "",
    period: str = "month",
) -> str:
    """Manage expense tracking."""
    action = action.lower().strip()

    with _lock:
        expenses = _load_expenses()

        # ── Log a new expense ────────────────────────────────────
        if action == "log":
            if amount <= 0:
                return "How much did you spend? I need an amount."
            if not description:
                return "What was the expense for? Give me a brief description."

            if not category:
                category = _auto_categorize(description)
            else:
                category = category.lower().strip()

            entry = {
                "amount": amount,
                "description": description,
                "category": category,
                "date": datetime.now(_IST).isoformat(),
                "date_str": datetime.now(_IST).strftime("%d %b %Y, %I:%M %p"),
            }
            expenses.append(entry)
            _save_expenses(expenses)

            logger.info(f"Expense logged: {_format_currency(amount)} — {description} [{category}]")
            return (
                f"💰 Logged: {_format_currency(amount)} for {description} "
                f"(category: {category})"
            )

        # ── Spending summary ─────────────────────────────────────
        elif action == "summary":
            filtered = _filter_by_period(expenses, period)
            if not filtered:
                return f"No expenses recorded for {period}."

            total = sum(e["amount"] for e in filtered)
            count = len(filtered)

            # Category breakdown
            cats = {}
            for e in filtered:
                c = e.get("category", "other")
                cats[c] = cats.get(c, 0) + e["amount"]

            breakdown = "\n".join(
                f"  • {cat}: {_format_currency(amt)}"
                for cat, amt in sorted(cats.items(), key=lambda x: -x[1])
            )

            return (
                f"📊 Spending summary ({period}):\n"
                f"Total: {_format_currency(total)} across {count} transaction(s)\n\n"
                f"By category:\n{breakdown}"
            )

        # ── List recent expenses ─────────────────────────────────
        elif action == "list":
            filtered = _filter_by_period(expenses, period)
            if not filtered:
                return f"No expenses recorded for {period}."

            recent = filtered[-10:]  # last 10
            recent.reverse()
            lines = []
            for e in recent:
                lines.append(
                    f"  • {_format_currency(e['amount'])} — {e['description']} "
                    f"[{e.get('category', '?')}] ({e.get('date_str', '')})"
                )
            total = sum(e["amount"] for e in filtered)
            return (
                f"📋 Recent expenses ({period}, total: {_format_currency(total)}):\n"
                + "\n".join(lines)
            )

        # ── Delete last entry ────────────────────────────────────
        elif action == "delete_last":
            if not expenses:
                return "No expenses to delete."
            removed = expenses.pop()
            _save_expenses(expenses)
            return (
                f"🗑️ Deleted: {_format_currency(removed['amount'])} — "
                f"{removed['description']}"
            )

        # ── Category breakdown ───────────────────────────────────
        elif action == "category_breakdown":
            filtered = _filter_by_period(expenses, period)
            if not filtered:
                return f"No expenses for {period}."

            cats = {}
            for e in filtered:
                c = e.get("category", "other")
                if c not in cats:
                    cats[c] = {"total": 0, "count": 0}
                cats[c]["total"] += e["amount"]
                cats[c]["count"] += 1

            total = sum(c["total"] for c in cats.values())
            lines = []
            for cat, data in sorted(cats.items(), key=lambda x: -x[1]["total"]):
                pct = (data["total"] / total * 100) if total else 0
                lines.append(
                    f"  • {cat}: {_format_currency(data['total'])} "
                    f"({data['count']} items, {pct:.0f}%)"
                )

            return (
                f"📊 Category breakdown ({period}):\n"
                f"Total: {_format_currency(total)}\n" + "\n".join(lines)
            )

        else:
            return (
                f"Unknown expense action '{action}'. "
                "Use: log, summary, list, delete_last, or category_breakdown"
            )


def _filter_by_period(expenses: list[dict], period: str) -> list[dict]:
    """Filter expenses by time period."""
    now = datetime.now(_IST)
    period = period.lower().strip()

    if period == "today":
        today_str = now.strftime("%d %b %Y")
        return [e for e in expenses if today_str in e.get("date_str", "")]
    elif period == "week":
        week_ago = now - timedelta(days=7)
        return [
            e for e in expenses
            if _parse_date(e) and _parse_date(e) >= week_ago
        ]
    elif period in ("month", "this_month"):
        return [
            e for e in expenses
            if _parse_date(e) and _parse_date(e).month == now.month
            and _parse_date(e).year == now.year
        ]
    elif period == "all":
        return expenses
    else:
        # Default to month
        return [
            e for e in expenses
            if _parse_date(e) and _parse_date(e).month == now.month
        ]


def _parse_date(entry: dict) -> Optional[datetime]:
    """Parse the ISO date from an expense entry."""
    try:
        return datetime.fromisoformat(entry["date"])
    except (KeyError, ValueError):
        return None
