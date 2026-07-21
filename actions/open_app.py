"""
EVA App Launcher — Launch applications by name.
Windows: Start Menu scan + registry App Paths.
macOS: open -a / mdfind. Linux: .desktop file scan / xdg-open.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool
from utils.platform_utils import IS_WINDOWS, IS_MACOS, IS_LINUX, run_shell

logger = logging.getLogger("eva.actions.open_app")


def _find_app_windows(name: str) -> Optional[str]:
    """Search for an app on Windows via Start Menu and registry."""
    name_lower = name.lower()

    # 1. Search Start Menu
    start_menu_paths = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]

    for start_path in start_menu_paths:
        if not start_path.exists():
            continue
        for path in start_path.rglob("*.lnk"):
            if name_lower in path.stem.lower():
                return str(path)

    # 2. Search registry App Paths
    try:
        import winreg
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        for hkey in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            try:
                with winreg.OpenKey(hkey, key_path) as key:
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            if name_lower in subkey_name.lower():
                                with winreg.OpenKey(key, subkey_name) as subkey:
                                    val, _ = winreg.QueryValueEx(subkey, "")
                                    return val
                            i += 1
                        except OSError:
                            break
            except OSError:
                continue
    except ImportError:
        pass

    # 3. Try common executable names
    common = {
        "chrome": "chrome.exe", "firefox": "firefox.exe",
        "edge": "msedge.exe", "notepad": "notepad.exe",
        "calculator": "calc.exe", "paint": "mspaint.exe",
        "explorer": "explorer.exe", "cmd": "cmd.exe",
        "powershell": "powershell.exe", "terminal": "wt.exe",
        "vscode": "code.exe", "vs code": "code.exe",
        "spotify": "spotify.exe", "discord": "discord.exe",
        "slack": "slack.exe", "teams": "teams.exe",
        "word": "WINWORD.EXE", "excel": "EXCEL.EXE",
        "powerpoint": "POWERPNT.EXE", "outlook": "OUTLOOK.EXE",
    }

    for key, exe in common.items():
        if name_lower in key or key in name_lower:
            return exe

    return None


@register_tool(
    name="open_application",
    description="Launch an application by name. Works across Windows, macOS, and Linux.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "name": {
                "type": "STRING",
                "description": "The application name to launch (e.g., 'Chrome', 'Spotify', 'VS Code')",
            },
        },
        "required": ["name"],
    },
    category="system",
)
def open_application(name: str) -> str:
    """Launch an application by name."""
    logger.info(f"Launching application: {name}")

    if IS_WINDOWS:
        app_path = _find_app_windows(name)
        if app_path:
            try:
                os.startfile(app_path)
                return f"Launched: {name}"
            except Exception as e:
                return f"Found {name} but failed to launch: {e}"

        # Fallback: try running directly
        code, _, stderr = run_shell(f'start "" "{name}"', timeout=5)
        if code == 0:
            return f"Launched: {name}"
        return f"Couldn't find application '{name}'. Try using the exact app name."

    elif IS_MACOS:
        # Try open -a first
        code, _, stderr = run_shell(f'open -a "{name}"', timeout=5)
        if code == 0:
            return f"Launched: {name}"

        # Fallback: mdfind
        code, stdout, _ = run_shell(
            f'mdfind "kMDItemKind == \'Application\'" | grep -i "{name}" | head -1'
        )
        if code == 0 and stdout:
            run_shell(f'open "{stdout}"')
            return f"Launched: {name}"

        return f"Couldn't find application '{name}'."

    elif IS_LINUX:
        # Try .desktop file scan
        desktop_dirs = [
            Path("/usr/share/applications"),
            Path("/usr/local/share/applications"),
            Path.home() / ".local" / "share" / "applications",
        ]
        for d in desktop_dirs:
            if not d.exists():
                continue
            for f in d.glob("*.desktop"):
                if name.lower() in f.stem.lower():
                    run_shell(f"xdg-open {f}", timeout=5)
                    return f"Launched: {name}"

        # Fallback: try direct command
        code, _, _ = run_shell(f"nohup {name.lower()} &", timeout=3)
        if code == 0:
            return f"Launched: {name}"

        return f"Couldn't find application '{name}'."

    return "Unsupported platform."
