"""
EVA Platform Utilities
OS detection, platform-branched helpers, known folder resolution.
"""

import os
import platform
import subprocess
from pathlib import Path
from typing import Optional


def get_os() -> str:
    """Return normalized OS name: 'windows', 'macos', or 'linux'."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    return system  # 'windows' or 'linux'


IS_WINDOWS = get_os() == "windows"
IS_MACOS = get_os() == "macos"
IS_LINUX = get_os() == "linux"


# ── Known user folders ──────────────────────────────────────────

def get_known_folders() -> dict[str, Path]:
    """
    Return a mapping of logical folder names to resolved paths.
    Used by file_controller to allowlist accessible directories.
    """
    home = Path.home()
    folders = {
        "desktop": home / "Desktop",
        "downloads": home / "Downloads",
        "documents": home / "Documents",
        "pictures": home / "Pictures",
        "music": home / "Music",
        "videos": home / "Videos",
    }

    if IS_WINDOWS:
        # Windows may redirect known folders; try shell folder resolution
        try:
            import winreg
            shell_key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, shell_key) as key:
                for name, reg_name in [
                    ("desktop", "Desktop"),
                    ("documents", "Personal"),
                    ("pictures", "My Pictures"),
                    ("music", "My Music"),
                    ("videos", "My Video"),
                ]:
                    try:
                        val, _ = winreg.QueryValueEx(key, reg_name)
                        folders[name] = Path(val)
                    except FileNotFoundError:
                        pass
        except ImportError:
            pass

    return {k: v for k, v in folders.items() if v.exists()}


def resolve_user_path(path_str: str) -> Optional[Path]:
    """
    Resolve a user-provided path, with smart folder alias handling.

    Supports:
      - Absolute paths: 'C:\\Users\\user\\Desktop\\test' or 'D:\\AY'
      - Known folder aliases: 'Downloads/EVA', 'Desktop/test', 'docs/report.txt'
      - Home-relative: '~/Documents/file.txt'
      - Environment variables: '%USERPROFILE%/Desktop'

    Returns None only if the path is truly unsafe (outside allowed areas).
    """
    path_str = path_str.strip().strip('"').strip("'")

    # Expand ~ and env vars
    expanded = os.path.expandvars(os.path.expanduser(path_str))

    known = get_known_folders()

    # Aliases for common folder names (case-insensitive)
    ALIASES = {
        "dl": "downloads",
        "download": "downloads",
        "doc": "documents",
        "docs": "documents",
        "pics": "pictures",
        "pic": "pictures",
        "vid": "videos",
        "vids": "videos",
    }

    # Check if the first path component is a known folder name or alias
    parts = Path(expanded).parts
    if parts:
        first = parts[0].lower().rstrip("/\\")

        # Direct folder name match: "Downloads" → known["downloads"]
        if first in known:
            base = known[first]
            rest = Path(*parts[1:]) if len(parts) > 1 else Path()
            return (base / rest).resolve()

        # Alias match: "docs" → known["documents"]
        if first in ALIASES and ALIASES[first] in known:
            base = known[ALIASES[first]]
            rest = Path(*parts[1:]) if len(parts) > 1 else Path()
            return (base / rest).resolve()

    # Try resolving as-is (handles absolute paths like C:\..., D:\...)
    resolved = Path(expanded).resolve()

    # Check against known folders
    for folder_path in known.values():
        try:
            resolved.relative_to(folder_path)
            return resolved
        except ValueError:
            continue

    # Allow the project directory
    project_root = Path(__file__).resolve().parent.parent
    try:
        resolved.relative_to(project_root)
        return resolved
    except ValueError:
        pass

    # Allow any absolute path on existing drives (user explicitly asked)
    # but NOT system folders for safety
    blocked_prefixes = [
        Path(os.environ.get("SYSTEMROOT", "C:\\Windows")),
        Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")),
        Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")),
    ]
    if resolved.is_absolute():
        for blocked in blocked_prefixes:
            try:
                resolved.relative_to(blocked)
                return None  # Block system paths
            except ValueError:
                continue
        return resolved  # Allow other absolute paths

    return None


# ── Process execution helpers ───────────────────────────────────

def run_shell(cmd: str, timeout: int = 30, shell: bool = True) -> tuple[int, str, str]:
    """
    Run a shell command and return (returncode, stdout, stderr).
    """
    try:
        result = subprocess.run(
            cmd, shell=shell, capture_output=True, text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def open_url(url: str) -> None:
    """Open a URL in the default browser."""
    import webbrowser
    webbrowser.open(url)


# ── Network helpers ─────────────────────────────────────────────

def get_local_ip() -> str:
    """Get the machine's LAN IP address."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_hostname() -> str:
    import socket
    return socket.gethostname()
