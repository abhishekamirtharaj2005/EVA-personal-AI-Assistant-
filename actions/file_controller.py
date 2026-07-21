"""
EVA File Controller — Safe file operations with allowlisted paths.
Delete uses send2trash for reversibility.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool
from utils.platform_utils import get_known_folders, resolve_user_path

logger = logging.getLogger("eva.actions.file_controller")


def _validate_path(path_str: str) -> tuple[Optional[Path], str]:
    """Validate and resolve a path against allowed directories."""
    resolved = resolve_user_path(path_str)
    if resolved is None:
        known = ", ".join(get_known_folders().keys())
        return None, f"Path '{path_str}' is outside allowed folders ({known})."
    return resolved, ""


@register_tool(
    name="manage_files",
    description="Create, move, copy, rename, list, or delete files and folders. "
                "Limited to user folders (Desktop, Downloads, Documents, Pictures, Music, Videos). "
                "Delete is reversible (sent to recycle bin).",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to perform",
                "enum": ["list", "create_folder", "create_file", "move",
                         "copy", "rename", "delete", "info"],
            },
            "path": {
                "type": "STRING",
                "description": "File or folder path",
            },
            "destination": {
                "type": "STRING",
                "description": "Destination path (for move, copy, rename operations)",
            },
            "content": {
                "type": "STRING",
                "description": "Content for create_file action",
            },
        },
        "required": ["action", "path"],
    },
    category="files",
)
def manage_files(action: str, path: str, destination: str = "",
                 content: str = "") -> str:
    """Perform file operations with safety checks."""
    resolved, err = _validate_path(path)
    if err:
        return err

    try:
        if action == "list":
            if not resolved.exists():
                return f"Path does not exist: {path}"
            if resolved.is_file():
                size = resolved.stat().st_size
                return f"File: {resolved.name} ({_human_size(size)})"

            items = sorted(resolved.iterdir())
            if not items:
                return f"Empty folder: {path}"

            lines = [f"Contents of {resolved.name}/ ({len(items)} items):"]
            for item in items[:50]:  # Limit output
                if item.is_dir():
                    count = sum(1 for _ in item.rglob("*"))
                    lines.append(f"  📁 {item.name}/ ({count} items)")
                else:
                    lines.append(f"  📄 {item.name} ({_human_size(item.stat().st_size)})")
            if len(items) > 50:
                lines.append(f"  ... and {len(items) - 50} more")
            return "\n".join(lines)

        elif action == "create_folder":
            resolved.mkdir(parents=True, exist_ok=True)
            return f"Created folder: {path}"

        elif action == "create_file":
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            return f"Created file: {path} ({len(content)} characters)"

        elif action == "move":
            dest_resolved, err = _validate_path(destination)
            if err:
                return err
            shutil.move(str(resolved), str(dest_resolved))
            return f"Moved {resolved.name} → {destination}"

        elif action == "copy":
            dest_resolved, err = _validate_path(destination)
            if err:
                return err
            if resolved.is_dir():
                shutil.copytree(str(resolved), str(dest_resolved))
            else:
                shutil.copy2(str(resolved), str(dest_resolved))
            return f"Copied {resolved.name} → {destination}"

        elif action == "rename":
            new_path = resolved.parent / destination  # destination = new name
            resolved.rename(new_path)
            return f"Renamed {resolved.name} → {destination}"

        elif action == "delete":
            from send2trash import send2trash
            send2trash(str(resolved))
            return f"Moved to recycle bin: {resolved.name}"

        elif action == "info":
            if not resolved.exists():
                return f"Does not exist: {path}"
            stat = resolved.stat()
            from datetime import datetime
            lines = [
                f"**Name**: {resolved.name}",
                f"**Type**: {'Directory' if resolved.is_dir() else 'File'}",
                f"**Size**: {_human_size(stat.st_size)}",
                f"**Modified**: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')}",
                f"**Created**: {datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M')}",
                f"**Path**: {resolved}",
            ]
            return "\n".join(lines)

        else:
            return f"Unknown action: {action}"

    except PermissionError:
        return f"Permission denied: {path}"
    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"File operation failed: {e}"


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
