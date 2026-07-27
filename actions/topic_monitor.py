"""
EVA Topic Monitor — Opt-in background news watcher.
User says "monitor <topic>" → daily DDG News check with
change-detection hashing. Crypto/finance topics are hard-blocked.
"""

import hashlib
import json
import logging
import re
import threading
from datetime import date
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.topic_monitor")

_MONITOR_DIR = Path(__file__).resolve().parent.parent / "config"
_MONITOR_FILE = _MONITOR_DIR / "monitors.json"

# Hard block list — crypto/finance keywords (case-insensitive)
_BLOCKED_KEYWORDS = {
    "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
    "nft", "blockchain", "defi", "token", "altcoin", "dogecoin",
    "solana", "binance", "coinbase", "shiba", "ripple", "xrp",
    "cardano", "polkadot", "avalanche", "litecoin", "polygon",
    "uniswap", "airdrop", "stablecoin", "tether", "usdt",
    # Non-English spellings
    "kripto", "krypto", "крипто", "بیت‌کوین", "ビットコイン",
    "暗号通貨", "仮想通貨",
}


class TopicMonitor:
    """Thread-safe topic monitor with JSON persistence."""

    _instance: Optional["TopicMonitor"] = None

    def __new__(cls) -> "TopicMonitor":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._lock = threading.Lock()
        self._monitors: dict[str, dict] = {}
        self._load()
        self._initialized = True

    # ── Public API ──────────────────────────────────────────────

    def add_topic(self, topic: str) -> str:
        """Add a new topic to monitor. Returns status message."""
        topic = topic.strip()
        if not topic:
            return "Please provide a topic to monitor."

        # Check against hard block list
        words = set(re.findall(r'\w+', topic.lower()))
        blocked = words & _BLOCKED_KEYWORDS
        if blocked:
            return (
                f"Cannot monitor '{topic}' — crypto/finance topics are "
                f"blocked for safety reasons."
            )

        slug = self._slugify(topic)
        if slug in self._monitors:
            return f"Already monitoring: {topic}"

        with self._lock:
            self._monitors[slug] = {
                "topic": topic,
                "added_date": date.today().isoformat(),
                "last_check": "",
                "last_hash": "",
            }
            self._save()

        logger.info(f"Added monitor: {topic} ({slug})")
        return f"Now monitoring: {topic}. I'll check for news daily."

    def remove_topic(self, topic: str) -> str:
        """Remove a monitored topic."""
        slug = self._slugify(topic.strip())
        with self._lock:
            if slug not in self._monitors:
                return f"Not currently monitoring: {topic}"
            del self._monitors[slug]
            self._save()
        logger.info(f"Removed monitor: {topic}")
        return f"Stopped monitoring: {topic}"

    def list_topics(self) -> str:
        """List all monitored topics."""
        with self._lock:
            if not self._monitors:
                return "No topics being monitored."
            lines = ["Currently monitoring:"]
            for slug, data in self._monitors.items():
                t = data.get("topic", slug)
                last = data.get("last_check", "never")
                lines.append(f"  • {t} (last checked: {last or 'never'})")
            return "\n".join(lines)

    def get_active_topics(self) -> list[str]:
        """Return list of active topic names (for proactive context)."""
        with self._lock:
            return [d["topic"] for d in self._monitors.values()]

    def check_all_topics(self) -> list[str]:
        """
        Check all topics that haven't been checked today.
        Returns a list of alert strings for topics with new headlines.
        """
        today = date.today().isoformat()
        alerts: list[str] = []

        with self._lock:
            topics_to_check = [
                (slug, data) for slug, data in self._monitors.items()
                if data.get("last_check") != today
            ]

        for slug, data in topics_to_check:
            topic = data.get("topic", slug)
            try:
                headline = self._fetch_top_headline(topic)
                if not headline:
                    continue

                new_hash = hashlib.md5(
                    headline.encode("utf-8")
                ).hexdigest()[:12]
                old_hash = data.get("last_hash", "")

                with self._lock:
                    if slug in self._monitors:
                        self._monitors[slug]["last_check"] = today
                        self._monitors[slug]["last_hash"] = new_hash
                        self._save()

                if new_hash != old_hash and old_hash:
                    # Hash changed — new headline
                    alerts.append(
                        f"📡 Monitor alert — {topic}: {headline}"
                    )
                    logger.info(f"Topic alert: {topic} — new headline")
                elif not old_hash:
                    # First check — just store hash, no alert
                    logger.info(f"Topic {topic}: initial headline stored")

            except Exception as e:
                logger.warning(f"Monitor check failed for {topic}: {e}")

        return alerts

    # ── Internal ────────────────────────────────────────────────

    @staticmethod
    def _slugify(text: str) -> str:
        return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

    @staticmethod
    def _fetch_top_headline(topic: str) -> Optional[str]:
        """Fetch the top news headline for a topic via DDG News."""
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.news(topic, max_results=1))
                if results:
                    return results[0].get("title", "")
        except Exception as e:
            logger.warning(f"DDG news fetch failed for {topic}: {e}")
        return None

    def _load(self) -> None:
        _MONITOR_DIR.mkdir(parents=True, exist_ok=True)
        if _MONITOR_FILE.exists():
            try:
                with open(_MONITOR_FILE, "r", encoding="utf-8") as f:
                    self._monitors = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._monitors = {}
        else:
            self._monitors = {}

    def _save(self) -> None:
        """Write monitors to disk. Must be called under self._lock."""
        _MONITOR_DIR.mkdir(parents=True, exist_ok=True)
        with open(_MONITOR_FILE, "w", encoding="utf-8") as f:
            json.dump(self._monitors, f, indent=2, ensure_ascii=False)


# Module-level singleton
topic_monitor = TopicMonitor()


# ── Tool Registration ───────────────────────────────────────────

@register_tool(
    name="monitor_topic",
    description="Add, remove, or list background news monitors for topics. "
                "Monitored topics are checked daily for new headlines. "
                "Crypto/finance topics are blocked.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to perform: add, remove, or list",
                "enum": ["add", "remove", "list"],
            },
            "topic": {
                "type": "STRING",
                "description": "The topic to monitor (required for add/remove)",
            },
        },
        "required": ["action"],
    },
    category="monitoring",
)
def monitor_topic(action: str, topic: str = "") -> str:
    """Manage background topic monitors."""
    if action == "add":
        return topic_monitor.add_topic(topic)
    elif action == "remove":
        return topic_monitor.remove_topic(topic)
    elif action == "list":
        return topic_monitor.list_topics()
    else:
        return f"Unknown action: {action}. Use add, remove, or list."
