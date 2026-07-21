"""
EVA Game Updater — Steam game management.
Locates Steam install, enumerates installed games, triggers updates via steam:// URLs.
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool
from utils.platform_utils import IS_WINDOWS, IS_MACOS, IS_LINUX

logger = logging.getLogger("eva.actions.game_updater")


def _find_steam_path() -> Optional[Path]:
    """Find the Steam installation directory."""
    if IS_WINDOWS:
        # Check common locations + registry
        common_paths = [
            Path("C:/Program Files (x86)/Steam"),
            Path("C:/Program Files/Steam"),
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Steam",
        ]
        for p in common_paths:
            if p.exists():
                return p

        # Try registry
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\WOW6432Node\Valve\Steam") as key:
                val, _ = winreg.QueryValueEx(key, "InstallPath")
                return Path(val)
        except (ImportError, OSError):
            pass

    elif IS_MACOS:
        path = Path.home() / "Library" / "Application Support" / "Steam"
        if path.exists():
            return path

    elif IS_LINUX:
        for p in [
            Path.home() / ".steam" / "steam",
            Path.home() / ".local" / "share" / "Steam",
        ]:
            if p.exists():
                return p

    return None


def _get_library_folders(steam_path: Path) -> list[Path]:
    """Get all Steam library folders."""
    folders = [steam_path]
    vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"

    if vdf_path.exists():
        try:
            content = vdf_path.read_text(encoding="utf-8", errors="replace")
            # Parse VDF format for paths
            paths = re.findall(r'"path"\s+"([^"]+)"', content)
            for p in paths:
                lib_path = Path(p.replace("\\\\", "\\"))
                if lib_path.exists() and lib_path not in folders:
                    folders.append(lib_path)
        except Exception as e:
            logger.warning(f"Failed to parse libraryfolders.vdf: {e}")

    return folders


def _get_installed_games(steam_path: Path) -> list[dict]:
    """Enumerate installed Steam games from manifest files."""
    games = []
    libraries = _get_library_folders(steam_path)

    for lib in libraries:
        steamapps = lib / "steamapps"
        if not steamapps.exists():
            continue

        for manifest in steamapps.glob("appmanifest_*.acf"):
            try:
                content = manifest.read_text(encoding="utf-8", errors="replace")
                app_id_match = re.search(r'"appid"\s+"(\d+)"', content)
                name_match = re.search(r'"name"\s+"([^"]+)"', content)
                state_match = re.search(r'"StateFlags"\s+"(\d+)"', content)
                size_match = re.search(r'"SizeOnDisk"\s+"(\d+)"', content)

                if app_id_match and name_match:
                    games.append({
                        "app_id": app_id_match.group(1),
                        "name": name_match.group(1),
                        "state": state_match.group(1) if state_match else "0",
                        "size_bytes": int(size_match.group(1)) if size_match else 0,
                    })
            except Exception:
                continue

    return sorted(games, key=lambda g: g["name"])


@register_tool(
    name="update_games",
    description="List installed Steam games or trigger updates. "
                "Can update specific games or check for updates.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'list' to list games, 'update' to trigger an update",
                "enum": ["list", "update"],
            },
            "game_name": {
                "type": "STRING",
                "description": "Game name to update (for 'update' action). "
                               "Partial match supported.",
            },
        },
        "required": ["action"],
    },
    category="utility",
)
def update_games(action: str, game_name: str = "") -> str:
    """Manage Steam games."""
    steam_path = _find_steam_path()
    if not steam_path:
        return "Steam installation not found."

    games = _get_installed_games(steam_path)
    if not games:
        return "No Steam games found."

    if action == "list":
        lines = [f"Installed Steam games ({len(games)}):"]
        for g in games:
            size_gb = g["size_bytes"] / (1024 ** 3) if g["size_bytes"] else 0
            lines.append(f"  🎮 {g['name']} (ID: {g['app_id']}, {size_gb:.1f} GB)")
        return "\n".join(lines)

    elif action == "update":
        if not game_name:
            # Update all
            import webbrowser
            webbrowser.open("steam://validate/0")
            return "Triggered Steam to check for updates on all games."

        # Find matching game
        matches = [g for g in games if game_name.lower() in g["name"].lower()]
        if not matches:
            return f"No game matching '{game_name}' found."

        game = matches[0]
        import webbrowser
        webbrowser.open(f"steam://validate/{game['app_id']}")
        return f"Triggered update/validation for: {game['name']}"

    return f"Unknown action: {action}"
