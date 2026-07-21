"""
EVA Send Message — Send messages via WhatsApp/Telegram using UI automation.
"""

import logging
import time

import pyautogui
import pyperclip

from core.tool_dispatcher import register_tool
from utils.platform_utils import IS_WINDOWS, run_shell

logger = logging.getLogger("eva.actions.send_message")


def _send_via_whatsapp_desktop(contact: str, message: str) -> str:
    """Send message via WhatsApp Desktop using UI automation."""
    try:
        import pygetwindow as gw

        # Try to find and focus WhatsApp window
        windows = gw.getWindowsWithTitle("WhatsApp")
        if not windows:
            # Try to open WhatsApp
            if IS_WINDOWS:
                run_shell('start whatsapp:', timeout=5)
                time.sleep(3)
                windows = gw.getWindowsWithTitle("WhatsApp")

        if not windows:
            return "WhatsApp Desktop is not open. Please open it first."

        window = windows[0]
        if window.isMinimized:
            window.restore()
        window.activate()
        time.sleep(0.5)

        # Click search bar and type contact name
        pyautogui.hotkey("ctrl", "f")  # Open search
        time.sleep(0.5)
        pyperclip.copy(contact)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1)

        # Press Enter to select first matching contact
        pyautogui.press("enter")
        time.sleep(0.5)

        # Type message using clipboard paste (handles Unicode)
        pyperclip.copy(message)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.3)

        # Send
        pyautogui.press("enter")

        return f"Message sent to {contact} via WhatsApp."

    except Exception as e:
        return f"Failed to send WhatsApp message: {e}"


def _send_via_telegram_desktop(contact: str, message: str) -> str:
    """Send message via Telegram Desktop using UI automation."""
    try:
        import pygetwindow as gw

        windows = gw.getWindowsWithTitle("Telegram")
        if not windows:
            if IS_WINDOWS:
                run_shell('start tg:', timeout=5)
                time.sleep(3)
                windows = gw.getWindowsWithTitle("Telegram")

        if not windows:
            return "Telegram Desktop is not open. Please open it first."

        window = windows[0]
        if window.isMinimized:
            window.restore()
        window.activate()
        time.sleep(0.5)

        # Search for contact
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.3)
        pyperclip.copy(contact)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1)

        pyautogui.press("enter")
        time.sleep(0.5)
        pyautogui.press("escape")  # Close search
        time.sleep(0.3)

        # Type and send message
        pyperclip.copy(message)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.3)
        pyautogui.press("enter")

        return f"Message sent to {contact} via Telegram."

    except Exception as e:
        return f"Failed to send Telegram message: {e}"


@register_tool(
    name="send_message",
    description="Send a message to a contact via WhatsApp or Telegram desktop apps. "
                "Uses UI automation — the app must be installed and logged in.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "platform": {
                "type": "STRING",
                "description": "Messaging platform",
                "enum": ["whatsapp", "telegram"],
            },
            "contact": {
                "type": "STRING",
                "description": "Contact name to send to",
            },
            "message": {
                "type": "STRING",
                "description": "Message text to send",
            },
        },
        "required": ["platform", "contact", "message"],
    },
    category="communication",
)
def send_message(platform: str, contact: str, message: str) -> str:
    """Send a message via WhatsApp or Telegram."""
    platform = platform.lower().strip()

    if platform == "whatsapp":
        return _send_via_whatsapp_desktop(contact, message)
    elif platform == "telegram":
        return _send_via_telegram_desktop(contact, message)
    else:
        return f"Unsupported platform: {platform}. Use 'whatsapp' or 'telegram'."
