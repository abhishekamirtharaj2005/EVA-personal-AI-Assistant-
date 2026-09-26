"""
EVA Telegram Bot Bridge — Send and receive Telegram messages through EVA.
Uses python-telegram-bot for the Telegram Bot API.
Auto-replies can be enabled so EVA responds to messages while you're away.
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Callable

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.telegram_bridge")

_IST = timezone(timedelta(hours=5, minutes=30))


class TelegramBridge:
    """Manages Telegram bot communication."""

    def __init__(self):
        self._bot = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._messages: list[dict] = []
        self._auto_reply = False
        self._auto_reply_msg = "I'm currently away. I'll get back to you soon! — EVA"
        self._on_message: Optional[Callable] = None
        self._max_messages = 50

    def configure(self, token: str) -> bool:
        """Configure the Telegram bot with a token."""
        try:
            import requests
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getMe",
                timeout=10
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                self._token = token
                bot_info = resp.json()["result"]
                logger.info(f"Telegram bot configured: @{bot_info['username']}")
                return True
            return False
        except Exception as e:
            logger.error(f"Telegram config failed: {e}")
            return False

    def start_polling(self, on_message: Optional[Callable] = None) -> None:
        """Start polling for new messages in background."""
        self._on_message = on_message
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="telegram-poll"
        )
        self._thread.start()
        logger.info("Telegram polling started")

    def stop(self) -> None:
        self._running = False

    def send_message(self, chat_id: str, text: str) -> bool:
        """Send a message to a Telegram chat."""
        try:
            import requests
            resp = requests.post(
                f"https://api.telegram.org/bot{self._token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def get_recent_messages(self, count: int = 5) -> list[dict]:
        """Get recent incoming messages."""
        return self._messages[-count:]

    def _poll_loop(self) -> None:
        """Long-poll for updates."""
        import requests
        offset = 0
        while self._running:
            try:
                resp = requests.get(
                    f"https://api.telegram.org/bot{self._token}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                    timeout=35,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        msg = update.get("message", {})
                        if msg.get("text"):
                            entry = {
                                "from": msg.get("from", {}).get("first_name", "Unknown"),
                                "username": msg.get("from", {}).get("username", ""),
                                "chat_id": msg["chat"]["id"],
                                "text": msg["text"],
                                "time": datetime.now(_IST).strftime("%I:%M %p"),
                                "date": datetime.now(_IST).isoformat(),
                            }
                            self._messages.append(entry)
                            if len(self._messages) > self._max_messages:
                                self._messages = self._messages[-self._max_messages:]

                            logger.info(f"Telegram msg from {entry['from']}: {entry['text'][:50]}")

                            # Auto-reply if enabled
                            if self._auto_reply:
                                self.send_message(
                                    str(entry["chat_id"]),
                                    self._auto_reply_msg
                                )

                            # Notify EVA
                            if self._on_message:
                                self._on_message(entry)

            except Exception as e:
                logger.debug(f"Telegram poll: {e}")
                time.sleep(5)

            time.sleep(1)


# Module singleton
_bridge = TelegramBridge()


@register_tool(
    name="telegram",
    description="Send and receive Telegram messages through EVA's bot. "
                "Actions: read (see recent messages), send (reply to a user), "
                "auto_reply (enable/disable auto-responses while away). "
                "Requires telegram_bot_token in settings.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: read | send | auto_reply_on | auto_reply_off | status",
            },
            "message": {
                "type": "STRING",
                "description": "Message to send (for send action)",
            },
            "to": {
                "type": "STRING",
                "description": "Username or chat_id to send to (for send action)",
            },
            "count": {
                "type": "INTEGER",
                "description": "Number of messages to read (default: 5)",
            },
        },
        "required": ["action"],
    },
    category="communication",
)
def telegram(
    action: str,
    message: str = "",
    to: str = "",
    count: int = 5,
) -> str:
    """Manage Telegram messaging."""
    from memory.config_manager import config

    action = action.lower().strip()
    token = config.get("telegram_bot_token", "")

    if not token:
        return (
            "Telegram not configured. Add your telegram_bot_token in Settings. "
            "Create a bot via @BotFather on Telegram to get a token."
        )

    # Ensure bot is configured
    if not hasattr(_bridge, '_token') or not _bridge._token:
        if not _bridge.configure(token):
            return "Failed to connect to Telegram. Check your bot token."
        _bridge.start_polling()

    if action == "read":
        msgs = _bridge.get_recent_messages(min(count, 20))
        if not msgs:
            return "📱 No recent Telegram messages."

        lines = []
        for m in msgs:
            lines.append(
                f"  💬 {m['from']} (@{m['username']}) at {m['time']}:\n"
                f"     {m['text'][:200]}"
            )
        return f"📱 Last {len(msgs)} Telegram message(s):\n\n" + "\n\n".join(lines)

    elif action == "send":
        if not to:
            return "Who should I send the message to? Give me a chat_id or username."
        if not message:
            return "What message should I send?"

        # Try to find chat_id from recent messages
        chat_id = to
        for m in _bridge._messages:
            if m.get("username", "").lower() == to.lower().strip("@"):
                chat_id = str(m["chat_id"])
                break

        if _bridge.send_message(chat_id, message):
            return f"✅ Telegram message sent to {to}."
        return f"❌ Failed to send message to {to}."

    elif action == "auto_reply_on":
        _bridge._auto_reply = True
        return "🤖 Auto-reply enabled. I'll respond to Telegram messages for you."

    elif action == "auto_reply_off":
        _bridge._auto_reply = False
        return "🤖 Auto-reply disabled."

    elif action == "status":
        return (
            f"📱 Telegram Status:\n"
            f"  Connected: {'Yes' if _bridge._running else 'No'}\n"
            f"  Messages cached: {len(_bridge._messages)}\n"
            f"  Auto-reply: {'On' if _bridge._auto_reply else 'Off'}"
        )

    return f"Unknown Telegram action '{action}'. Use: read, send, auto_reply_on, auto_reply_off, status."
