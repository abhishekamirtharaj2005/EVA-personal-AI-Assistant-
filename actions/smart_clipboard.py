"""
EVA Smart Clipboard — Watches clipboard, detects content type, and offers
contextual actions. Integrates as a tool EVA can call, and provides a
background watcher for proactive clipboard suggestions.
"""

import logging
import re
import threading
import time
from typing import Optional, Callable

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.smart_clipboard")


def _detect_content_type(text: str) -> tuple[str, str]:
    """Detect clipboard content type and return (type, suggestion)."""
    text = text.strip()
    if not text:
        return "empty", ""

    # URL
    if re.match(r'https?://', text):
        return "url", f"I see a URL: {text[:80]}. Want me to open or summarize it?"

    # Email address
    if re.match(r'^[\w.-]+@[\w.-]+\.\w+$', text):
        return "email", f"That's an email address: {text}. Want me to send an email?"

    # Error / Stack trace
    error_keywords = ["Error", "Exception", "Traceback", "TypeError",
                      "ValueError", "at line", "SyntaxError", "undefined",
                      "NullPointer", "FATAL", "failed"]
    if any(kw in text for kw in error_keywords):
        return "error", "That looks like an error. Want me to debug it?"

    # Code
    code_indicators = ["def ", "class ", "import ", "function ", "const ",
                       "var ", "let ", "return ", "if (", "for (", "=>",
                       "public ", "private ", "#include", "package "]
    if any(ind in text for ind in code_indicators):
        return "code", "That looks like code. Want me to explain or review it?"

    # JSON
    if (text.startswith("{") and text.endswith("}")) or \
       (text.startswith("[") and text.endswith("]")):
        try:
            import json
            json.loads(text)
            return "json", "That's valid JSON. Want me to format or analyze it?"
        except Exception:
            pass

    # Phone number
    if re.match(r'^[\+]?[\d\s\-\(\)]{7,15}$', text):
        return "phone", f"That's a phone number: {text}. Want me to search who it belongs to?"

    # File path
    if re.match(r'^[A-Z]:\\|^/', text) or '\\' in text:
        return "path", f"That's a file path: {text[:80]}. Want me to open or analyze it?"

    # Short text — possibly a search query
    if len(text) < 100:
        return "query", f"Copied: '{text}'. Want me to search for this?"

    # Long text
    return "text", f"Copied {len(text)} chars. Want me to summarize or translate it?"


class ClipboardWatcher:
    """Background thread that monitors clipboard changes."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_content = ""
        self._on_change: Optional[Callable] = None
        self._enabled = False

    def start(self, on_change: Callable) -> None:
        """Start watching the clipboard."""
        self._on_change = on_change
        self._enabled = True
        self._running = True
        self._thread = threading.Thread(
            target=self._watch_loop, daemon=True, name="clipboard-watcher"
        )
        self._thread.start()
        logger.info("Clipboard watcher started")

    def stop(self) -> None:
        self._running = False
        self._enabled = False

    def _watch_loop(self) -> None:
        import pyperclip
        self._last_content = pyperclip.paste() or ""

        while self._running:
            try:
                current = pyperclip.paste() or ""
                if current != self._last_content and current.strip():
                    self._last_content = current
                    content_type, suggestion = _detect_content_type(current)
                    if self._on_change and suggestion:
                        self._on_change(content_type, current, suggestion)
            except Exception:
                pass
            time.sleep(1.5)


# Module singleton
clipboard_watcher = ClipboardWatcher()


@register_tool(
    name="smart_clipboard",
    description="Analyze clipboard contents, detect content type, and perform "
                "contextual actions. Actions: analyze (detect & suggest), copy "
                "(copy text to clipboard), paste (read clipboard).",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: analyze | copy | paste",
            },
            "text": {
                "type": "STRING",
                "description": "Text to copy to clipboard (for copy action)",
            },
        },
        "required": ["action"],
    },
    category="utility",
)
def smart_clipboard(action: str, text: str = "") -> str:
    """Smart clipboard operations."""
    import pyperclip
    action = action.lower().strip()

    if action == "analyze":
        content = pyperclip.paste() or ""
        if not content.strip():
            return "Clipboard is empty."
        content_type, suggestion = _detect_content_type(content)
        preview = content[:200].replace("\n", " ")
        return (
            f"📋 Clipboard ({content_type}, {len(content)} chars):\n"
            f"Content: {preview}{'...' if len(content) > 200 else ''}\n"
            f"{suggestion}"
        )

    elif action == "copy":
        if not text:
            return "What should I copy to the clipboard?"
        pyperclip.copy(text)
        return f"📋 Copied to clipboard ({len(text)} chars)."

    elif action == "paste":
        content = pyperclip.paste() or ""
        if not content.strip():
            return "Clipboard is empty."
        return f"📋 Clipboard contents ({len(content)} chars):\n{content[:500]}"

    return f"Unknown clipboard action '{action}'. Use: analyze, copy, or paste."
