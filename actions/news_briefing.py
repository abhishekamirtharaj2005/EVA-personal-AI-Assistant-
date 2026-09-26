"""
EVA News Briefing 2.0 — Personalized multi-topic daily news aggregation.
Curates news based on user interests stored in memory and monitored topics.
"""

import logging
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.news_briefing")


def _get_user_interests() -> list[str]:
    """Get user interests from memory and monitored topics."""
    interests = []

    # From memory
    try:
        from memory.memory_manager import memory
        for key in ["interests", "hobbies", "topics", "field", "work"]:
            val = memory.recall(key=key, category="preferences")
            if val and val != "No matching memories found.":
                interests.append(val.split(":")[-1].strip())
    except Exception:
        pass

    # From monitored topics
    try:
        from actions.topic_monitor import topic_monitor
        topics = topic_monitor.get_active_topics()
        interests.extend(topics)
    except Exception:
        pass

    # Deduplicate
    seen = set()
    unique = []
    for i in interests:
        lower = i.lower()
        if lower not in seen:
            seen.add(lower)
            unique.append(i)

    return unique or ["technology", "world news"]


def _fetch_topic_news(topic: str) -> str:
    """Fetch news for a single topic."""
    try:
        from actions.web_search import search_web
        return search_web(query=f"latest {topic} news today", mode="news")
    except Exception as e:
        return f"Failed to fetch {topic} news: {e}"


@register_tool(
    name="news_briefing",
    description="Personalized multi-topic news briefing. Fetches latest news "
                "based on user interests stored in memory. Use for morning "
                "briefings or when user asks 'what's new' or 'any news'. "
                "Can also brief on specific topics.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "topics": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Specific topics to brief on. If empty, uses user's "
                               "interests from memory. E.g., ['AI', 'cricket', 'stocks']",
            },
            "format": {
                "type": "STRING",
                "description": "Briefing format: full (detailed) | quick (headlines only) | voice (optimized for speaking)",
            },
        },
        "required": [],
    },
    category="information",
)
def news_briefing(topics: list[str] = None, format: str = "voice") -> str:
    """Generate personalized news briefing."""
    from datetime import datetime, timedelta, timezone
    _IST = timezone(timedelta(hours=5, minutes=30))

    if not topics:
        topics = _get_user_interests()

    # Limit to 5 topics to avoid rate limits
    topics = topics[:5]

    now = datetime.now(_IST)
    greeting = ""
    hour = now.hour
    if 5 <= hour < 12:
        greeting = "Good morning! "
    elif 12 <= hour < 17:
        greeting = "Good afternoon! "
    elif 17 <= hour < 22:
        greeting = "Good evening! "

    format = format.lower().strip()

    sections = []
    for topic in topics:
        logger.info(f"Fetching news: {topic}")
        news = _fetch_topic_news(topic)
        if news and "failed" not in news.lower():
            if format == "quick":
                # Just first 200 chars
                sections.append(f"📰 {topic.upper()}:\n{news[:200]}...")
            else:
                sections.append(f"📰 {topic.upper()}:\n{news[:500]}")

    if not sections:
        return (
            f"{greeting}I tried to fetch news but couldn't get results. "
            "This might be a rate limit issue. Try again in a minute."
        )

    header = (
        f"{greeting}Here's your personalized briefing for "
        f"{now.strftime('%A, %B %d')}:\n\n"
    )

    return header + "\n\n".join(sections)
