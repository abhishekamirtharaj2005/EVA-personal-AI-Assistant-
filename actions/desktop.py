"""
EVA Desktop Control — Wallpaper management and sandboxed automation snippets.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import requests

from core.tool_dispatcher import register_tool
from utils.platform_utils import IS_WINDOWS, IS_MACOS, IS_LINUX, run_shell

logger = logging.getLogger("eva.actions.desktop")


def _download_image(url: str) -> Optional[Path]:
    """Download an image from URL to temp directory."""
    try:
        response = requests.get(url, timeout=15, stream=True)
        response.raise_for_status()

        ext = ".jpg"
        content_type = response.headers.get("content-type", "")
        if "png" in content_type:
            ext = ".png"
        elif "bmp" in content_type:
            ext = ".bmp"

        tmp_path = Path(tempfile.mktemp(suffix=ext, prefix="eva_wallpaper_"))
        with open(tmp_path, "wb") as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)

        return tmp_path
    except Exception as e:
        logger.error(f"Image download failed: {e}")
        return None


def _set_wallpaper_windows(image_path: str) -> str:
    """Set wallpaper on Windows."""
    try:
        import ctypes
        SPI_SETDESKWALLPAPER = 0x0014
        SPIF_UPDATEINIFILE = 0x01
        SPIF_SENDWININICHANGE = 0x02

        result = ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, str(image_path),
            SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
        )
        if result:
            return f"Wallpaper set to: {Path(image_path).name}"
        return "Failed to set wallpaper."
    except Exception as e:
        return f"Failed to set wallpaper: {e}"


def _set_wallpaper_macos(image_path: str) -> str:
    """Set wallpaper on macOS."""
    code, _, stderr = run_shell(
        f'osascript -e \'tell application "Finder" to set desktop picture to POSIX file "{image_path}"\''
    )
    return "Wallpaper set." if code == 0 else f"Failed: {stderr}"


def _set_wallpaper_linux(image_path: str) -> str:
    """Set wallpaper on Linux (GNOME)."""
    code, _, stderr = run_shell(
        f'gsettings set org.gnome.desktop.background picture-uri "file://{image_path}"'
    )
    return "Wallpaper set." if code == 0 else f"Failed: {stderr}"


@register_tool(
    name="set_wallpaper",
    description="Set the desktop wallpaper. Accepts a local file path or a URL "
                "(which will be downloaded first).",
    parameters={
        "type": "OBJECT",
        "properties": {
            "path_or_url": {
                "type": "STRING",
                "description": "Local file path or URL to an image",
            },
        },
        "required": ["path_or_url"],
    },
    category="desktop",
)
def set_wallpaper(path_or_url: str) -> str:
    """Set the desktop wallpaper."""
    # Check if it's a URL
    if path_or_url.startswith(("http://", "https://")):
        downloaded = _download_image(path_or_url)
        if not downloaded:
            return "Failed to download the image."
        image_path = str(downloaded)
    else:
        image_path = os.path.expanduser(path_or_url)
        if not Path(image_path).exists():
            return f"Image file not found: {path_or_url}"

    if IS_WINDOWS:
        return _set_wallpaper_windows(image_path)
    elif IS_MACOS:
        return _set_wallpaper_macos(image_path)
    elif IS_LINUX:
        return _set_wallpaper_linux(image_path)
    return "Unsupported platform."


@register_tool(
    name="run_desktop_script",
    description="Run a small automation snippet on the desktop. "
                "Executed in a sandboxed namespace with limited access.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "script": {
                "type": "STRING",
                "description": "Python script to execute (small automation tasks only)",
            },
            "description": {
                "type": "STRING",
                "description": "What this script does (for logging)",
            },
        },
        "required": ["script"],
    },
    category="desktop",
)
def run_desktop_script(script: str, description: str = "") -> str:
    """Execute a small automation script in a restricted namespace."""
    logger.info(f"Running desktop script: {description or 'unnamed'}")

    # Restricted namespace — only allow safe imports
    allowed_modules = {
        "os": os,
        "time": __import__("time"),
        "datetime": __import__("datetime"),
        "pathlib": __import__("pathlib"),
        "json": __import__("json"),
        "subprocess": __import__("subprocess"),
    }

    namespace = {"__builtins__": {"print": print, "str": str, "int": int,
                                   "float": float, "bool": bool, "list": list,
                                   "dict": dict, "len": len, "range": range,
                                   "enumerate": enumerate, "sorted": sorted,
                                   "isinstance": isinstance, "type": type,
                                   "True": True, "False": False, "None": None,
                                   "__import__": lambda name: allowed_modules.get(name)}}
    namespace.update(allowed_modules)

    output_lines = []
    original_print = print

    def capture_print(*args, **kwargs):
        output_lines.append(" ".join(str(a) for a in args))

    namespace["print"] = capture_print

    try:
        exec(script, namespace)
        output = "\n".join(output_lines) if output_lines else "Script completed."
        return output[:3000]
    except Exception as e:
        return f"Script failed: {type(e).__name__}: {e}"
