"""
EVA Multi-Monitor Awareness — Detect multiple monitors and perform
per-monitor operations: screenshots, window placement, info.
"""

import logging
from typing import Optional

from core.tool_dispatcher import register_tool
from utils.platform_utils import IS_WINDOWS

logger = logging.getLogger("eva.actions.multi_monitor")


def _get_monitors() -> list[dict]:
    """Get info about all connected monitors."""
    monitors = []
    try:
        import mss
        with mss.mss() as sct:
            for i, mon in enumerate(sct.monitors):
                if i == 0:
                    continue  # Skip the virtual/combined monitor
                monitors.append({
                    "index": i,
                    "left": mon["left"],
                    "top": mon["top"],
                    "width": mon["width"],
                    "height": mon["height"],
                    "primary": i == 1,
                })
    except Exception as e:
        logger.error(f"Monitor detection failed: {e}")
    return monitors


def _screenshot_monitor(index: int) -> Optional[str]:
    """Take a screenshot of a specific monitor and save it."""
    try:
        import mss
        from PIL import Image
        from pathlib import Path
        from datetime import datetime, timedelta, timezone

        _IST = timezone(timedelta(hours=5, minutes=30))
        output_dir = Path(__file__).resolve().parent.parent / "config" / "screenshots"
        output_dir.mkdir(parents=True, exist_ok=True)

        with mss.mss() as sct:
            if index < 1 or index >= len(sct.monitors):
                return None
            monitor = sct.monitors[index]
            img = sct.grab(monitor)

            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            timestamp = datetime.now(_IST).strftime("%Y%m%d_%H%M%S")
            filepath = output_dir / f"monitor{index}_{timestamp}.png"
            pil_img.save(str(filepath))
            return str(filepath)
    except Exception as e:
        logger.error(f"Monitor screenshot failed: {e}")
        return None


def _move_window(window_title: str, monitor_index: int) -> str:
    """Move a window to a specific monitor."""
    if not IS_WINDOWS:
        return "Window management only supported on Windows."

    monitors = _get_monitors()
    if monitor_index < 1 or monitor_index > len(monitors):
        return f"Invalid monitor index. You have {len(monitors)} monitor(s)."

    target = monitors[monitor_index - 1]

    try:
        import subprocess
        # Use PowerShell to move window
        ps_script = f"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinAPI {{
    [DllImport("user32.dll")]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    [DllImport("user32.dll")]
    public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}}
"@

$procs = Get-Process | Where-Object {{ $_.MainWindowTitle -like '*{window_title}*' }} | Select-Object -First 1
if ($procs) {{
    $hwnd = $procs.MainWindowHandle
    [WinAPI]::ShowWindow($hwnd, 9)
    [WinAPI]::MoveWindow($hwnd, {target['left']}, {target['top']}, {target['width'] // 2}, {target['height'] // 2}, $true)
    [WinAPI]::SetForegroundWindow($hwnd)
    Write-Output "Moved"
}} else {{
    Write-Output "NotFound"
}}
"""
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout.strip()
        if output == "Moved":
            return f"✅ Moved '{window_title}' to monitor {monitor_index}."
        return f"Window '{window_title}' not found."
    except Exception as e:
        return f"Failed to move window: {e}"


@register_tool(
    name="multi_monitor",
    description="Multi-monitor operations — detect monitors, take per-monitor screenshots, "
                "move windows between monitors. Use when the user asks about their monitors, "
                "wants to move windows, or screenshot a specific screen.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: list | screenshot | move_window",
            },
            "monitor": {
                "type": "INTEGER",
                "description": "Monitor index (1-based). 1 = primary monitor.",
            },
            "window": {
                "type": "STRING",
                "description": "Window title to move (for move_window action). "
                               "Partial match supported. E.g., 'Chrome', 'VS Code'",
            },
        },
        "required": ["action"],
    },
    category="system",
)
def multi_monitor(action: str, monitor: int = 1, window: str = "") -> str:
    """Multi-monitor management."""
    action = action.lower().strip()

    # ── List monitors ────────────────────────────────────────
    if action == "list":
        monitors = _get_monitors()
        if not monitors:
            return "🖥️ No monitors detected (or mss not available)."
        if len(monitors) == 1:
            m = monitors[0]
            return (
                f"🖥️ Single monitor detected:\n"
                f"   Resolution: {m['width']}x{m['height']}\n"
                f"   Position: ({m['left']}, {m['top']})"
            )

        lines = [f"🖥️ {len(monitors)} monitors detected:\n"]
        for m in monitors:
            primary = " ⭐ PRIMARY" if m["primary"] else ""
            lines.append(
                f"  Monitor {m['index']}: {m['width']}x{m['height']} "
                f"at ({m['left']},{m['top']}){primary}"
            )
        return "\n".join(lines)

    # ── Screenshot specific monitor ──────────────────────────
    elif action == "screenshot":
        path = _screenshot_monitor(monitor)
        if path:
            return f"📸 Screenshot saved: {path}"
        return f"Failed to screenshot monitor {monitor}."

    # ── Move window ──────────────────────────────────────────
    elif action == "move_window":
        if not window:
            return "Which window should I move? Give me the app name."
        return _move_window(window, monitor)

    return f"Unknown multi-monitor action '{action}'. Use: list, screenshot, move_window."
