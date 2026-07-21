"""
EVA Reminder — Smart reminder system using native OS schedulers.
Windows: Task Scheduler (schtasks), macOS: LaunchAgent, Linux: systemd timer.
"""

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from core.tool_dispatcher import register_tool
from utils.platform_utils import IS_WINDOWS, IS_MACOS, IS_LINUX, run_shell

logger = logging.getLogger("eva.actions.reminder")

_REMINDER_DIR = Path(__file__).resolve().parent.parent / "config" / "reminders"


def _create_notification_script(title: str, message: str) -> Path:
    """Create a small script that shows a native notification."""
    _REMINDER_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c if c.isalnum() else "_" for c in title)[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_name = f"reminder_{safe_name}_{timestamp}"

    if IS_WINDOWS:
        script_path = _REMINDER_DIR / f"{script_name}.ps1"
        script_content = f"""
Add-Type -AssemblyName System.Windows.Forms
$notification = New-Object System.Windows.Forms.NotifyIcon
$notification.Icon = [System.Drawing.SystemIcons]::Information
$notification.BalloonTipTitle = "{title}"
$notification.BalloonTipText = "{message}"
$notification.Visible = $True
$notification.ShowBalloonTip(10000)
Start-Sleep -Seconds 11
$notification.Dispose()
"""
        script_path.write_text(script_content, encoding="utf-8")

    elif IS_MACOS:
        script_path = _REMINDER_DIR / f"{script_name}.sh"
        script_content = f'''#!/bin/bash
osascript -e 'display notification "{message}" with title "{title}"'
'''
        script_path.write_text(script_content, encoding="utf-8")
        os.chmod(script_path, 0o755)

    else:  # Linux
        script_path = _REMINDER_DIR / f"{script_name}.sh"
        script_content = f'''#!/bin/bash
notify-send "{title}" "{message}" -t 10000
'''
        script_path.write_text(script_content, encoding="utf-8")
        os.chmod(script_path, 0o755)

    return script_path


def _schedule_windows(script_path: Path, run_time: datetime, task_name: str) -> str:
    """Register a one-time task with Windows Task Scheduler."""
    time_str = run_time.strftime("%H:%M")
    date_str = run_time.strftime("%m/%d/%Y")

    cmd = (
        f'schtasks /Create /TN "EVA\\{task_name}" '
        f'/TR "powershell.exe -ExecutionPolicy Bypass -File \\"{script_path}\\"" '
        f'/SC ONCE /ST {time_str} /SD {date_str} /F'
    )

    code, stdout, stderr = run_shell(cmd)
    if code == 0:
        return f"Reminder set for {run_time.strftime('%I:%M %p on %B %d, %Y')}"
    else:
        return f"Failed to schedule reminder: {stderr}"


def _schedule_macos(script_path: Path, run_time: datetime, task_name: str) -> str:
    """Register via launchctl on macOS."""
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    label = f"com.eva.reminder.{task_name}"
    plist_path = plist_dir / f"{label}.plist"

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{script_path}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{run_time.hour}</integer>
        <key>Minute</key>
        <integer>{run_time.minute}</integer>
        <key>Day</key>
        <integer>{run_time.day}</integer>
        <key>Month</key>
        <integer>{run_time.month}</integer>
    </dict>
</dict>
</plist>"""
    plist_path.write_text(plist_content, encoding="utf-8")
    run_shell(f"launchctl load {plist_path}")
    return f"Reminder set for {run_time.strftime('%I:%M %p on %B %d, %Y')}"


def _schedule_linux(script_path: Path, run_time: datetime, task_name: str) -> str:
    """Register via systemd user timer on Linux."""
    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_dir.mkdir(parents=True, exist_ok=True)

    service_name = f"eva-reminder-{task_name}"
    service_path = service_dir / f"{service_name}.service"
    timer_path = service_dir / f"{service_name}.timer"

    service_content = f"""[Unit]
Description=EVA Reminder: {task_name}

[Service]
Type=oneshot
ExecStart={script_path}
"""
    timer_content = f"""[Unit]
Description=EVA Reminder Timer: {task_name}

[Timer]
OnCalendar={run_time.strftime('%Y-%m-%d %H:%M:%S')}
Persistent=true

[Install]
WantedBy=timers.target
"""
    service_path.write_text(service_content, encoding="utf-8")
    timer_path.write_text(timer_content, encoding="utf-8")
    run_shell("systemctl --user daemon-reload")
    run_shell(f"systemctl --user enable --now {service_name}.timer")
    return f"Reminder set for {run_time.strftime('%I:%M %p on %B %d, %Y')}"


@register_tool(
    name="set_reminder",
    description="Set a reminder that will show a notification at a specific time. "
                "Works independently of whether EVA is running.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "title": {
                "type": "STRING",
                "description": "Short title for the reminder",
            },
            "message": {
                "type": "STRING",
                "description": "The reminder message",
            },
            "time_str": {
                "type": "STRING",
                "description": "When to remind, in ISO format (YYYY-MM-DDTHH:MM:SS) or "
                               "natural time like '3:30 PM' (assumes today)",
            },
        },
        "required": ["title", "message", "time_str"],
    },
    category="utility",
)
def set_reminder(title: str, message: str, time_str: str) -> str:
    """Set a reminder using the native OS scheduler."""
    # Parse the time
    try:
        if "T" in time_str:
            run_time = datetime.fromisoformat(time_str)
        else:
            # Try common formats
            for fmt in ["%I:%M %p", "%H:%M", "%I:%M%p"]:
                try:
                    parsed = datetime.strptime(time_str.strip(), fmt)
                    run_time = datetime.now().replace(
                        hour=parsed.hour, minute=parsed.minute, second=0
                    )
                    if run_time < datetime.now():
                        # Assume tomorrow
                        from datetime import timedelta
                        run_time += timedelta(days=1)
                    break
                except ValueError:
                    continue
            else:
                return f"Couldn't parse time '{time_str}'. Use format like '3:30 PM' or '2025-01-15T14:30:00'."
    except Exception as e:
        return f"Invalid time format: {e}"

    safe_name = "".join(c if c.isalnum() else "_" for c in title)[:30]
    task_name = f"{safe_name}_{run_time.strftime('%H%M')}"

    # Create notification script
    script_path = _create_notification_script(title, message)

    # Schedule per OS
    if IS_WINDOWS:
        return _schedule_windows(script_path, run_time, task_name)
    elif IS_MACOS:
        return _schedule_macos(script_path, run_time, task_name)
    elif IS_LINUX:
        return _schedule_linux(script_path, run_time, task_name)
    else:
        return "Unsupported operating system for reminders."
