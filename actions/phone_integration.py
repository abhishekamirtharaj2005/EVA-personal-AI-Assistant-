"""
EVA Phone Integration — Enhanced phone control via the dashboard WebSocket.
Read notifications, reply to texts, see call history, and remote control.
Extends the existing dashboard with phone-specific commands.
"""

import json
import logging
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.phone_integration")


@register_tool(
    name="phone_control",
    description="Phone integration via EVA's remote dashboard. "
                "Check phone notifications, send quick replies, "
                "get device status, and send files between PC and phone. "
                "Requires phone to be connected via the dashboard QR code.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: status | send_text | clipboard_sync | "
                               "find_phone | battery | open_url",
            },
            "text": {
                "type": "STRING",
                "description": "Text to send to phone clipboard or as message",
            },
            "url": {
                "type": "STRING",
                "description": "URL to open on the phone browser",
            },
        },
        "required": ["action"],
    },
    category="phone",
)
def phone_control(action: str, text: str = "", url: str = "") -> str:
    """Phone integration via dashboard."""
    action = action.lower().strip()

    # Check if dashboard is running and phone is connected
    try:
        from dashboard.server import get_dashboard_server
        server = get_dashboard_server()
        if not server or not server.has_connected_clients():
            return (
                "📱 Phone not connected. To connect:\n"
                "  1. Click the 📱 button in EVA\n"
                "  2. Scan the QR code with your phone\n"
                "  3. Keep the dashboard page open"
            )
    except Exception:
        return (
            "📱 Dashboard server not available. "
            "Make sure EVA is running with the dashboard enabled."
        )

    # ── Status ───────────────────────────────────────────────
    if action == "status":
        try:
            server = get_dashboard_server()
            clients = server.get_client_count()
            return (
                f"📱 Phone Integration Status:\n"
                f"   Connected devices: {clients}\n"
                f"   Dashboard: Active\n"
                f"   Available: send_text, clipboard_sync, find_phone, open_url"
            )
        except Exception as e:
            return f"Status check failed: {e}"

    # ── Send text to phone ───────────────────────────────────
    elif action == "send_text":
        if not text:
            return "What text should I send to your phone?"
        try:
            server = get_dashboard_server()
            server.broadcast({
                "type": "clipboard",
                "content": text,
                "action": "copy",
            })
            return f"📱 Text sent to phone clipboard: '{text[:80]}...'" if len(text) > 80 else f"📱 Text sent to phone: '{text}'"
        except Exception as e:
            return f"Failed to send to phone: {e}"

    # ── Clipboard sync ───────────────────────────────────────
    elif action == "clipboard_sync":
        try:
            import pyperclip
            content = pyperclip.paste() or ""
            if not content.strip():
                return "PC clipboard is empty."

            server = get_dashboard_server()
            server.broadcast({
                "type": "clipboard",
                "content": content[:2000],
                "action": "sync",
            })
            return f"📱 Clipboard synced to phone ({len(content)} chars)."
        except Exception as e:
            return f"Clipboard sync failed: {e}"

    # ── Find phone ───────────────────────────────────────────
    elif action == "find_phone":
        try:
            server = get_dashboard_server()
            server.broadcast({
                "type": "command",
                "action": "ring",
                "duration": 10,
            })
            return "📱🔔 Sent ring command to your phone!"
        except Exception as e:
            return f"Find phone failed: {e}"

    # ── Battery ──────────────────────────────────────────────
    elif action == "battery":
        try:
            server = get_dashboard_server()
            server.broadcast({
                "type": "query",
                "action": "battery",
            })
            return "📱 Battery status requested. Check your phone dashboard for the response."
        except Exception as e:
            return f"Battery check failed: {e}"

    # ── Open URL on phone ────────────────────────────────────
    elif action == "open_url":
        if not url:
            return "Which URL should I open on your phone?"
        try:
            server = get_dashboard_server()
            server.broadcast({
                "type": "command",
                "action": "open_url",
                "url": url,
            })
            return f"📱 Opening on phone: {url}"
        except Exception as e:
            return f"Failed to open URL: {e}"

    return f"Unknown phone action '{action}'. Use: status, send_text, clipboard_sync, find_phone, battery, open_url."
