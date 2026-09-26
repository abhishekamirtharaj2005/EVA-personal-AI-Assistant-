"""
EVA Quiz / Study Mode — Flashcard-based learning with spaced repetition.
EVA quizzes you on topics, tracks your progress, and uses SM-2 algorithm
for optimal review scheduling.
"""

import json
import logging
import random
import threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.study_mode")

_DATA_DIR = Path(__file__).resolve().parent.parent / "config"
_FLASHCARDS_FILE = _DATA_DIR / "flashcards.json"
_lock = threading.Lock()
_IST = timezone(timedelta(hours=5, minutes=30))


def _load_cards() -> list[dict]:
    if not _FLASHCARDS_FILE.exists():
        return []
    try:
        with open(_FLASHCARDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("cards", [])
    except (json.JSONDecodeError, IOError):
        return []


def _save_cards(cards: list[dict]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_FLASHCARDS_FILE, "w", encoding="utf-8") as f:
        json.dump({"cards": cards}, f, indent=2, ensure_ascii=False)


def _sm2_update(card: dict, quality: int) -> dict:
    """
    SM-2 spaced repetition algorithm.
    quality: 0 (fail) to 5 (perfect recall)
    """
    ef = card.get("ease_factor", 2.5)
    interval = card.get("interval", 1)
    reps = card.get("repetitions", 0)

    if quality >= 3:  # Correct
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = int(interval * ef)
        reps += 1
    else:  # Incorrect
        reps = 0
        interval = 1

    ef = max(1.3, ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))

    card["ease_factor"] = round(ef, 2)
    card["interval"] = interval
    card["repetitions"] = reps
    card["next_review"] = (date.today() + timedelta(days=interval)).isoformat()
    card["last_reviewed"] = date.today().isoformat()
    card["total_reviews"] = card.get("total_reviews", 0) + 1
    return card


@register_tool(
    name="study_mode",
    description="Flashcard-based study system with spaced repetition. "
                "Add flashcards, get quizzed, track progress. "
                "EVA remembers what you got right/wrong and schedules reviews optimally.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: add | quiz | review | list | stats | generate | delete",
            },
            "topic": {
                "type": "STRING",
                "description": "Topic/subject for the flashcard or quiz. "
                               "E.g., 'Python', 'History', 'Biology'",
            },
            "question": {
                "type": "STRING",
                "description": "Question for the flashcard (for add action)",
            },
            "answer": {
                "type": "STRING",
                "description": "Answer for the flashcard (for add action)",
            },
            "card_id": {
                "type": "INTEGER",
                "description": "Card index for review/delete (0-based)",
            },
            "quality": {
                "type": "INTEGER",
                "description": "Self-rated recall quality 0-5 for review "
                               "(0=forgot, 3=correct with effort, 5=perfect)",
            },
            "count": {
                "type": "INTEGER",
                "description": "Number of cards to generate or quiz (default: 5)",
            },
        },
        "required": ["action"],
    },
    category="education",
)
def study_mode(
    action: str,
    topic: str = "",
    question: str = "",
    answer: str = "",
    card_id: int = -1,
    quality: int = 3,
    count: int = 5,
) -> str:
    """Manage flashcards and study sessions."""
    action = action.lower().strip()

    with _lock:
        cards = _load_cards()

    # ── Add a card ───────────────────────────────────────────
    if action == "add":
        if not question:
            return "What's the question for the flashcard?"
        if not answer:
            return "What's the answer?"

        card = {
            "question": question,
            "answer": answer,
            "topic": topic or "General",
            "created": date.today().isoformat(),
            "ease_factor": 2.5,
            "interval": 1,
            "repetitions": 0,
            "next_review": date.today().isoformat(),
            "last_reviewed": None,
            "total_reviews": 0,
        }
        with _lock:
            cards = _load_cards()
            cards.append(card)
            _save_cards(cards)

        return (
            f"🎓 Flashcard added ({topic or 'General'}):\n"
            f"   Q: {question}\n   A: {answer}\n"
            f"   Total cards: {len(cards)}"
        )

    # ── Quiz mode ────────────────────────────────────────────
    elif action == "quiz":
        today = date.today().isoformat()

        # Filter by topic if specified
        eligible = cards
        if topic:
            eligible = [c for c in cards if c.get("topic", "").lower() == topic.lower()]

        # Get cards due for review
        due = [c for c in eligible if c.get("next_review", "0") <= today]

        if not due:
            if not eligible:
                return f"No flashcards found{' for ' + topic if topic else ''}. Add some first!"
            return f"🎉 No cards due for review! Next review: {min(c.get('next_review', '9999') for c in eligible)}"

        # Pick random cards
        quiz_cards = random.sample(due, min(count, len(due)))

        lines = []
        for i, card in enumerate(quiz_cards):
            idx = cards.index(card)
            lines.append(
                f"\n📝 Card #{idx}:\n"
                f"   Topic: {card.get('topic', 'General')}\n"
                f"   Q: {card['question']}\n"
                f"   A: ||{card['answer']}||\n"
                f"   (Rate yourself 0-5 with: study review card_id={idx} quality=N)"
            )

        return (
            f"🎓 Quiz Time! {len(quiz_cards)} card(s) due:\n"
            + "\n".join(lines)
        )

    # ── Review a card ────────────────────────────────────────
    elif action == "review":
        if card_id < 0 or card_id >= len(cards):
            return f"Invalid card ID. You have {len(cards)} cards (0-{len(cards)-1})."

        quality = max(0, min(5, quality))
        card = cards[card_id]
        card = _sm2_update(card, quality)
        cards[card_id] = card

        with _lock:
            _save_cards(cards)

        status = "✅ Correct!" if quality >= 3 else "❌ Needs review"
        return (
            f"{status} Card #{card_id} reviewed.\n"
            f"   Next review: {card['next_review']}\n"
            f"   Interval: {card['interval']} days\n"
            f"   Total reviews: {card['total_reviews']}"
        )

    # ── List cards ───────────────────────────────────────────
    elif action == "list":
        if not cards:
            return "No flashcards yet. Add some with 'add flashcard' command."

        filtered = cards
        if topic:
            filtered = [c for c in cards if c.get("topic", "").lower() == topic.lower()]

        if not filtered:
            return f"No cards for topic '{topic}'."

        lines = []
        for i, card in enumerate(filtered):
            idx = cards.index(card)
            lines.append(
                f"  #{idx} [{card.get('topic', 'General')}] "
                f"Q: {card['question'][:60]}... "
                f"(reviews: {card.get('total_reviews', 0)}, "
                f"next: {card.get('next_review', '?')})"
            )

        return (
            f"🎓 Flashcards ({len(filtered)}):\n" + "\n".join(lines[:20])
        )

    # ── Stats ────────────────────────────────────────────────
    elif action == "stats":
        if not cards:
            return "No flashcards yet."

        total = len(cards)
        today = date.today().isoformat()
        due = len([c for c in cards if c.get("next_review", "0") <= today])
        reviewed = sum(c.get("total_reviews", 0) for c in cards)
        topics = set(c.get("topic", "General") for c in cards)
        mastered = len([c for c in cards if c.get("interval", 0) >= 21])

        return (
            f"🎓 Study Stats:\n"
            f"  📚 Total cards: {total}\n"
            f"  📝 Due for review: {due}\n"
            f"  ✅ Total reviews: {reviewed}\n"
            f"  🏆 Mastered (21+ day interval): {mastered}\n"
            f"  📂 Topics: {', '.join(sorted(topics))}"
        )

    # ── Generate cards from topic ────────────────────────────
    elif action == "generate":
        if not topic:
            return "What topic should I create flashcards for?"
        return (
            f"To generate flashcards about '{topic}', I'll create {count} questions. "
            f"Please give me the specific subtopic or chapter you want to study, "
            f"and I'll create Q&A pairs for you."
        )

    # ── Delete ───────────────────────────────────────────────
    elif action == "delete":
        if card_id < 0 or card_id >= len(cards):
            return f"Invalid card ID. You have {len(cards)} cards."
        removed = cards.pop(card_id)
        with _lock:
            _save_cards(cards)
        return f"🗑️ Deleted card: {removed['question'][:60]}"

    return f"Unknown study action '{action}'. Use: add, quiz, review, list, stats, generate, delete."
