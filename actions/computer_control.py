"""
EVA Computer Control — Keyboard, mouse, and window management.
Uses pyautogui for input and pygetwindow for window focus/list.
"""

import logging
import time
from typing import Optional

import pyautogui
import pyperclip

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.computer_control")

# Safety: don't move mouse to corners (pyautogui failsafe)
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1


@register_tool(
    name="type_text",
    description="Type text using the keyboard. For short text only — use clipboard "
                "paste for long content.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "text": {
                "type": "STRING",
                "description": "The text to type",
            },
            "interval": {
                "type": "NUMBER",
                "description": "Seconds between keystrokes (default 0.02)",
            },
        },
        "required": ["text"],
    },
    category="input",
)
def type_text(text: str, interval: float = 0.02) -> str:
    """Type text character by character."""
    if len(text) > 500:
        # Use clipboard for long text
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        return f"Pasted {len(text)} characters from clipboard."

    pyautogui.typewrite(text, interval=interval) if text.isascii() else _type_unicode(text)
    return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"


def _type_unicode(text: str) -> None:
    """Handle Unicode text by using clipboard paste."""
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")


@register_tool(
    name="press_keys",
    description="Press keyboard keys or key combinations (shortcuts). "
                "Examples: 'enter', 'ctrl+c', 'alt+tab', 'win+d'.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "keys": {
                "type": "STRING",
                "description": "Key or key combination (e.g., 'ctrl+c', 'enter', 'alt+f4')",
            },
        },
        "required": ["keys"],
    },
    category="input",
)
def press_keys(keys: str) -> str:
    """Press a key or key combination."""
    keys_lower = keys.lower().strip()

    # Handle key combos like "ctrl+c"
    if "+" in keys_lower:
        parts = [k.strip() for k in keys_lower.split("+")]
        # Map common names
        key_map = {
            "ctrl": "ctrl", "control": "ctrl",
            "alt": "alt", "option": "alt",
            "shift": "shift",
            "win": "win", "windows": "win", "cmd": "command", "command": "command",
            "enter": "enter", "return": "enter",
            "tab": "tab", "esc": "escape", "escape": "escape",
            "space": "space", "backspace": "backspace",
            "delete": "delete", "del": "delete",
        }
        mapped = [key_map.get(k, k) for k in parts]
        pyautogui.hotkey(*mapped)
        return f"Pressed: {keys}"
    else:
        key_map = {
            "enter": "enter", "return": "enter",
            "tab": "tab", "esc": "escape", "escape": "escape",
            "space": "space", "backspace": "backspace",
            "delete": "delete", "del": "delete",
            "up": "up", "down": "down", "left": "left", "right": "right",
            "home": "home", "end": "end",
            "pageup": "pageup", "pagedown": "pagedown",
        }
        key = key_map.get(keys_lower, keys_lower)
        pyautogui.press(key)
        return f"Pressed: {keys}"


@register_tool(
    name="click_mouse",
    description="Click the mouse at a specific position or at the current position. "
                "Coordinates are in pixels from top-left corner.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "x": {
                "type": "INTEGER",
                "description": "X coordinate in pixels",
            },
            "y": {
                "type": "INTEGER",
                "description": "Y coordinate in pixels",
            },
            "button": {
                "type": "STRING",
                "description": "Mouse button: 'left', 'right', or 'middle'",
                "enum": ["left", "right", "middle"],
            },
            "clicks": {
                "type": "INTEGER",
                "description": "Number of clicks (1 for single, 2 for double)",
            },
        },
        "required": [],
    },
    category="input",
)
def click_mouse(x: int = None, y: int = None,
                button: str = "left", clicks: int = 1) -> str:
    """Click the mouse."""
    if x is not None and y is not None:
        pyautogui.click(x, y, button=button, clicks=clicks)
        return f"Clicked at ({x}, {y}) with {button} button"
    else:
        pyautogui.click(button=button, clicks=clicks)
        pos = pyautogui.position()
        return f"Clicked at current position ({pos.x}, {pos.y})"


@register_tool(
    name="focus_window",
    description="Switch focus to a specific application window, or list all open windows.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "title": {
                "type": "STRING",
                "description": "Window title or partial match to focus. "
                               "Omit to list all windows.",
            },
        },
        "required": [],
    },
    category="input",
)
def focus_window(title: str = "") -> str:
    """Focus a window by title or list all windows."""
    try:
        import pygetwindow as gw
    except ImportError:
        return "Window management not available (pygetwindow not installed)."

    if not title:
        # List all windows
        windows = [w.title for w in gw.getAllWindows() if w.title.strip()]
        if not windows:
            return "No open windows found."
        return "Open windows:\n" + "\n".join(f"- {w}" for w in windows[:20])

    # Find and focus
    matches = gw.getWindowsWithTitle(title)
    if not matches:
        # Try partial match
        all_windows = gw.getAllWindows()
        matches = [w for w in all_windows if title.lower() in w.title.lower()]

    if not matches:
        return f"No window found matching '{title}'."

    window = matches[0]
    try:
        if window.isMinimized:
            window.restore()
        window.activate()
        return f"Focused window: {window.title}"
    except Exception as e:
        return f"Found window '{window.title}' but couldn't focus it: {e}"
