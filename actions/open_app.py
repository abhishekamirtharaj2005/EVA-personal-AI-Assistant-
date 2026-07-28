"""
EVA App Launcher — Launch applications by name.
Windows: Start Menu scan, registry App Paths, UWP/Store apps, PowerShell fallback.
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

# ── Common app names → executable mapping ───────────────────────
_COMMON_APPS = {
    # Browsers
    "chrome": "chrome.exe", "google chrome": "chrome.exe",
    "firefox": "firefox.exe", "brave": "brave.exe",
    "edge": "msedge.exe", "microsoft edge": "msedge.exe",
    "opera": "opera.exe",
    # System
    "notepad": "notepad.exe", "calculator": "calc.exe",
    "paint": "mspaint.exe", "explorer": "explorer.exe",
    "file explorer": "explorer.exe", "cmd": "cmd.exe",
    "command prompt": "cmd.exe", "powershell": "powershell.exe",
    "terminal": "wt.exe", "windows terminal": "wt.exe",
    "task manager": "taskmgr.exe", "control panel": "control.exe",
    "snipping tool": "snippingtool.exe",
    "device manager": "devmgmt.msc", "disk management": "diskmgmt.msc",
    # Dev tools
    "vscode": "code.exe", "vs code": "code.exe",
    "visual studio code": "code.exe",
    # Communication
    "spotify": "spotify.exe", "discord": "discord.exe",
    "slack": "slack.exe", "teams": "teams.exe",
    "microsoft teams": "teams.exe", "zoom": "zoom.exe",
    "telegram": "telegram.exe", "whatsapp": "whatsapp.exe",
    # Office
    "word": "WINWORD.EXE", "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE", "outlook": "OUTLOOK.EXE",
    "onenote": "ONENOTE.EXE",
    # Media
    "vlc": "vlc.exe", "obs": "obs64.exe",
    "obs studio": "obs64.exe",
    # Gaming
    "steam": "steam.exe", "epic games": "EpicGamesLauncher.exe",
    # Utils
    "git bash": "git-bash.exe", "winrar": "winrar.exe",
    "7zip": "7zFM.exe",
}

# UWP/Store apps — shell:AppsFolder IDs
_UWP_APPS = {
    "settings": "ms-settings:",
    "windows settings": "ms-settings:",
    "store": "ms-windows-store:",
    "microsoft store": "ms-windows-store:",
    "maps": "bingmaps:",
    "camera": "microsoft.windows.camera:",
    "photos": "ms-photos:",
    "mail": "outlookmail:",
    "calendar": "outlookcal:",
    "alarm": "ms-clock:",
    "clock": "ms-clock:",
    "weather": "bingweather:",
    "news": "bingnews:",
    "xbox": "xbox:",
    "feedback hub": "feedback-hub:",
}


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

    # 3. Common executable names
    for key, exe in _COMMON_APPS.items():
        if name_lower in key or key in name_lower:
            return exe

    return None


def _try_uwp_protocol(name: str) -> Optional[str]:
    """Check if the app name matches a UWP protocol URI."""
    name_lower = name.lower()
    for key, protocol in _UWP_APPS.items():
        if name_lower in key or key in name_lower:
            return protocol
    return None


def _launch_via_powershell_search(name: str) -> bool:
    """
    Use PowerShell to search installed UWP/Store apps and launch.
    This catches apps like Instagram, TikTok, Netflix, etc.
    Writes a temp .ps1 script to avoid shell escaping issues.
    """
    import tempfile
    script_content = (
        f'$app = Get-StartApps | Where-Object {{ $_.Name -like "*{name}*" }} '
        f'| Select-Object -First 1\n'
        f'if ($app) {{\n'
        f'  Start-Process "shell:AppsFolder\\$($app.AppID)"\n'
        f'  Write-Output "LAUNCHED:$($app.Name)"\n'
        f'}} else {{\n'
        f'  Write-Output "NOT_FOUND"\n'
        f'}}\n'
    )
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.ps1', delete=False, dir=os.environ.get('TEMP')
        ) as f:
            f.write(script_content)
            script_path = f.name

        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", script_path],
            capture_output=True, text=True, timeout=15,
        )

        # Clean up temp script
        try:
            os.unlink(script_path)
        except OSError:
            pass

        output = result.stdout.strip()
        if output.startswith("LAUNCHED:"):
            launched_name = output.split(":", 1)[1]
            logger.info(f"Launched UWP app via PowerShell: {launched_name}")
            return True
    except Exception as e:
        logger.warning(f"PowerShell UWP search failed: {e}")
    return False


@register_tool(
    name="open_application",
    description="Launch an application by name. Works across Windows, macOS, and Linux. "
                "Supports desktop apps, Windows Store/UWP apps, and system settings.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "name": {
                "type": "STRING",
                "description": "The application name to launch (e.g., 'Chrome', 'Instagram', 'Settings', 'VS Code')",
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
        # 1. Check UWP protocol URIs first (Settings, Store, etc.)
        protocol = _try_uwp_protocol(name)
        if protocol:
            try:
                os.startfile(protocol)
                return f"Launched: {name}"
            except Exception as e:
                logger.warning(f"UWP protocol launch failed: {e}")

        # 2. Search Start Menu shortcuts + registry + common apps
        app_path = _find_app_windows(name)
        if app_path:
            try:
                os.startfile(app_path)
                return f"Launched: {name}"
            except Exception as e:
                logger.warning(f"Found {name} but startfile failed: {e}")

        # 3. Try PowerShell Get-StartApps (catches all UWP/Store apps)
        if _launch_via_powershell_search(name):
            return f"Launched: {name}"

        # 4. Fallback: try running directly via start command
        code, _, stderr = run_shell(f'start "" "{name}"', timeout=5)
        if code == 0:
            return f"Launched: {name}"

        # 5. Last resort: Win+S search simulation
        try:
            import pyautogui
            import time
            pyautogui.hotkey('win')
            time.sleep(0.5)
            pyautogui.typewrite(name, interval=0.03)
            time.sleep(0.8)
            pyautogui.press('enter')
            return f"Searching and launching: {name}"
        except Exception as e:
            logger.warning(f"Win search fallback failed: {e}")

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


# ── Process name mapping for close ──────────────────────────────
_PROCESS_NAMES = {
    "chrome": "chrome", "google chrome": "chrome",
    "firefox": "firefox", "brave": "brave",
    "edge": "msedge", "microsoft edge": "msedge",
    "notepad": "notepad", "calculator": "calculatorapp",
    "paint": "mspaint", "explorer": "explorer",
    "file explorer": "explorer", "cmd": "cmd",
    "powershell": "powershell", "terminal": "windowsterminal",
    "vscode": "code", "vs code": "code", "visual studio code": "code",
    "spotify": "spotify", "discord": "discord",
    "slack": "slack", "teams": "teams", "zoom": "zoom",
    "telegram": "telegram", "whatsapp": "whatsapp",
    "word": "winword", "excel": "excel",
    "powerpoint": "powerpnt", "outlook": "outlook",
    "vlc": "vlc", "obs": "obs64", "obs studio": "obs64",
    "steam": "steam", "task manager": "taskmgr",
    "settings": "systemsettings",
    "instagram": "instagram",
    "netflix": "netflix",
}


def _get_process_name(app_name: str) -> str:
    """Map friendly app name to process name."""
    name_lower = app_name.lower().strip()
    return _PROCESS_NAMES.get(name_lower, name_lower)


@register_tool(
    name="close_application",
    description="Close/kill a running application by name. Use when the user asks to close, quit, exit, or kill an app.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "name": {
                "type": "STRING",
                "description": "The application name to close (e.g., 'Chrome', 'Spotify', 'Instagram')",
            },
        },
        "required": ["name"],
    },
    category="system",
)
def close_application(name: str) -> str:
    """Close a running application by name."""
    logger.info(f"Closing application: {name}")
    process_name = _get_process_name(name)

    if IS_WINDOWS:
        # Try taskkill with image name (graceful first, then force)
        # Try exact exe name
        code, stdout, stderr = run_shell(
            f'taskkill /IM "{process_name}.exe" /F', timeout=5
        )
        if code == 0:
            return f"Closed: {name}"

        # Try with wildcard — match partial process names
        code, stdout, stderr = run_shell(
            f'powershell -NoProfile -Command "'
            f"Get-Process | Where-Object {{ $_.ProcessName -like '*{process_name}*' }} | "
            f'Stop-Process -Force"',
            timeout=8,
        )
        if code == 0:
            return f"Closed: {name}"

        # Check if the process was actually running
        code2, stdout2, _ = run_shell(
            f'tasklist /FI "IMAGENAME eq {process_name}.exe"', timeout=5
        )
        if process_name.lower() not in stdout2.lower():
            return f"{name} doesn't appear to be running."

        return f"Couldn't close {name}. It may require admin privileges."

    elif IS_MACOS:
        # Try osascript quit first (graceful)
        code, _, _ = run_shell(
            f'osascript -e \'tell application "{name}" to quit\'', timeout=5
        )
        if code == 0:
            return f"Closed: {name}"
        # Force kill
        code, _, _ = run_shell(f'pkill -f "{process_name}"', timeout=5)
        if code == 0:
            return f"Force closed: {name}"
        return f"Couldn't find running application '{name}'."

    elif IS_LINUX:
        code, _, _ = run_shell(f'pkill -f "{process_name}"', timeout=5)
        if code == 0:
            return f"Closed: {name}"
        return f"Couldn't find running application '{name}'."

    return "Unsupported platform."
