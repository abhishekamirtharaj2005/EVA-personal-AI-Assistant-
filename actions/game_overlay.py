"""
EVA Game Overlay — Minimal transparent overlay for gaming mode.
Shows a small floating HUD that stays on top during games,
with voice-only interaction and minimal visual footprint.
"""

import logging
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.game_overlay")

# State
_overlay_active = False


@register_tool(
    name="game_mode",
    description="Toggle gaming overlay mode. When active, EVA switches to a "
                "minimal transparent overlay that doesn't interfere with games. "
                "Voice commands still work. Notifications are suppressed. "
                "Use when the user starts gaming or wants minimal UI.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: on | off | status",
            },
            "suppress_notifications": {
                "type": "BOOLEAN",
                "description": "Whether to suppress system notifications (default: true)",
            },
        },
        "required": ["action"],
    },
    category="gaming",
)
def game_mode(action: str, suppress_notifications: bool = True) -> str:
    """Toggle game overlay mode."""
    global _overlay_active
    action = action.lower().strip()

    if action == "on":
        if _overlay_active:
            return "🎮 Game mode is already active."

        _overlay_active = True

        # Minimize the main EVA window and activate overlay
        try:
            from ui.main_window import get_main_window
            win = get_main_window()
            if win and hasattr(win, 'activate_game_overlay'):
                win.activate_game_overlay()
            elif win:
                win.showMinimized()
        except Exception as e:
            logger.debug(f"Game overlay UI: {e}")

        # Suppress Windows notifications
        if suppress_notifications:
            try:
                import subprocess
                # Enable Focus Assist (DND mode)
                subprocess.run(
                    ["powershell", "-Command",
                     "Set-ItemProperty -Path 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings' "
                     "-Name 'NOC_GLOBAL_SETTING_TOASTS_ENABLED' -Value 0 -Type DWord -Force"],
                    capture_output=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception as e:
                logger.debug(f"Notification suppress: {e}")

        # Disable proactive mode during gaming
        try:
            from actions.proactive import get_proactive_engine
            get_proactive_engine().set_enabled(False)
        except Exception:
            pass

        logger.info("Game mode activated")
        return (
            "🎮 Game mode activated!\n"
            "  • EVA minimized to overlay\n"
            "  • Notifications suppressed\n"
            "  • Proactive check-ins paused\n"
            "  • Voice commands still active\n"
            "  Say 'game mode off' when you're done."
        )

    elif action == "off":
        if not _overlay_active:
            return "🎮 Game mode is not active."

        _overlay_active = False

        # Restore main window
        try:
            from ui.main_window import get_main_window
            win = get_main_window()
            if win and hasattr(win, 'deactivate_game_overlay'):
                win.deactivate_game_overlay()
            elif win:
                win.showNormal()
                win.raise_()
        except Exception as e:
            logger.debug(f"Game overlay restore: {e}")

        # Restore notifications
        try:
            import subprocess
            subprocess.run(
                ["powershell", "-Command",
                 "Set-ItemProperty -Path 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings' "
                 "-Name 'NOC_GLOBAL_SETTING_TOASTS_ENABLED' -Value 1 -Type DWord -Force"],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass

        # Re-enable proactive mode
        try:
            from actions.proactive import get_proactive_engine
            get_proactive_engine().set_enabled(True)
        except Exception:
            pass

        logger.info("Game mode deactivated")
        return "🎮 Game mode off. EVA is back to full mode."

    elif action == "status":
        return f"🎮 Game mode: {'Active' if _overlay_active else 'Inactive'}"

    return f"Unknown game mode action '{action}'. Use: on, off, status."
