"""
EVA Computer Settings — Volume, brightness, WiFi, power controls.
Platform-branched: pycaw (Windows), osascript (macOS), amixer (Linux).
"""

import logging
import platform

from core.tool_dispatcher import register_tool
from utils.platform_utils import IS_WINDOWS, IS_MACOS, IS_LINUX, run_shell

logger = logging.getLogger("eva.actions.computer_settings")


# ── Volume Control ──────────────────────────────────────────────

def _set_volume_windows(level: int) -> str:
    """Set volume using pycaw (Windows Core Audio)."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
        )
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        return f"Volume set to {level}%"
    except Exception as e:
        return f"Failed to set volume: {e}"


def _get_volume_windows() -> int:
    """Get current volume level on Windows."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
        )
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        return int(volume.GetMasterVolumeLevelScalar() * 100)
    except Exception:
        return -1


def _set_volume_macos(level: int) -> str:
    code, _, stderr = run_shell(f"osascript -e 'set volume output volume {level}'")
    return f"Volume set to {level}%" if code == 0 else f"Failed: {stderr}"


def _set_volume_linux(level: int) -> str:
    code, _, stderr = run_shell(f"amixer set Master {level}%")
    if code != 0:
        code, _, stderr = run_shell(f"pactl set-sink-volume @DEFAULT_SINK@ {level}%")
    return f"Volume set to {level}%" if code == 0 else f"Failed: {stderr}"


@register_tool(
    name="set_volume",
    description="Set the system volume level (0-100) or mute/unmute.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "level": {
                "type": "INTEGER",
                "description": "Volume level from 0 to 100",
            },
            "mute": {
                "type": "BOOLEAN",
                "description": "True to mute, False to unmute (optional)",
            },
        },
        "required": [],
    },
    category="system",
)
def set_volume(level: int = -1, mute: bool = None) -> str:
    """Set system volume or mute/unmute."""
    if mute is not None:
        if IS_WINDOWS:
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(
                    IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                )
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                volume.SetMute(mute, None)
                return "Muted" if mute else "Unmuted"
            except Exception as e:
                return f"Failed to mute: {e}"
        elif IS_MACOS:
            cmd = "set volume with output muted" if mute else "set volume without output muted"
            run_shell(f"osascript -e '{cmd}'")
            return "Muted" if mute else "Unmuted"
        else:
            toggle = "mute" if mute else "unmute"
            run_shell(f"amixer set Master {toggle}")
            return "Muted" if mute else "Unmuted"

    if level < 0:
        # Report current volume
        if IS_WINDOWS:
            vol = _get_volume_windows()
            return f"Current volume: {vol}%" if vol >= 0 else "Couldn't read volume."
        return "Please specify a volume level (0-100)."

    level = max(0, min(100, level))

    if IS_WINDOWS:
        return _set_volume_windows(level)
    elif IS_MACOS:
        return _set_volume_macos(level)
    elif IS_LINUX:
        return _set_volume_linux(level)
    return "Unsupported platform."


# ── Brightness Control ──────────────────────────────────────────

@register_tool(
    name="set_brightness",
    description="Set the screen brightness level (0-100).",
    parameters={
        "type": "OBJECT",
        "properties": {
            "level": {
                "type": "INTEGER",
                "description": "Brightness level from 0 to 100",
            },
        },
        "required": ["level"],
    },
    category="system",
)
def set_brightness(level: int) -> str:
    """Set screen brightness."""
    level = max(0, min(100, level))

    if IS_WINDOWS:
        code, _, stderr = run_shell(
            f'powershell -Command "(Get-WmiObject -Namespace root/WMI '
            f'-Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"'
        )
        return f"Brightness set to {level}%" if code == 0 else f"Failed: {stderr}"
    elif IS_MACOS:
        # Requires brightness CLI tool
        code, _, _ = run_shell(f"brightness {level / 100.0}")
        return f"Brightness set to {level}%"
    elif IS_LINUX:
        code, _, _ = run_shell(f"xrandr --output $(xrandr | head -2 | tail -1 | cut -d' ' -f1) --brightness {level / 100.0}")
        return f"Brightness set to {level}%"
    return "Unsupported platform."


# ── WiFi Control ────────────────────────────────────────────────

@register_tool(
    name="toggle_wifi",
    description="Enable or disable WiFi, or get current WiFi status.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "enable": {
                "type": "BOOLEAN",
                "description": "True to enable WiFi, False to disable. Omit for status.",
            },
        },
        "required": [],
    },
    category="system",
)
def toggle_wifi(enable: bool = None) -> str:
    """Toggle WiFi on/off or report status."""
    if IS_WINDOWS:
        if enable is None:
            code, stdout, _ = run_shell("netsh wlan show interfaces")
            if "connected" in stdout.lower():
                return "WiFi is connected."
            return "WiFi is disconnected."
        action = "enable" if enable else "disable"
        code, _, stderr = run_shell(f'netsh interface set interface "Wi-Fi" {action}')
        return f"WiFi {action}d." if code == 0 else f"Failed: {stderr}"
    elif IS_MACOS:
        if enable is None:
            code, stdout, _ = run_shell("networksetup -getairportnetwork en0")
            return stdout
        action = "on" if enable else "off"
        run_shell(f"networksetup -setairportpower en0 {action}")
        return f"WiFi turned {action}."
    return "WiFi control not implemented for this platform."
