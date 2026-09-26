"""
EVA Spotify Control — Control Spotify playback by voice.
Uses Windows COM (via subprocess) for local Spotify control,
and the Spotify Web API (via spotipy) for search/queue if credentials are configured.

Works without API credentials for basic play/pause/skip via keyboard media keys.
"""

import logging
import subprocess
import time
from typing import Optional

from core.tool_dispatcher import register_tool
from utils.platform_utils import IS_WINDOWS

logger = logging.getLogger("eva.actions.spotify_control")


def _is_spotify_running() -> bool:
    """Check if Spotify is running."""
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Spotify.exe", "/FO", "CSV"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return "Spotify.exe" in result.stdout
        except Exception:
            return False
    return False


def _launch_spotify() -> bool:
    """Launch Spotify if not running."""
    if IS_WINDOWS:
        try:
            # Try AppData location first (most common)
            import os
            appdata = os.environ.get("APPDATA", "")
            spotify_path = os.path.join(appdata, "Spotify", "Spotify.exe")
            if os.path.exists(spotify_path):
                subprocess.Popen(
                    [spotify_path],
                    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                )
                time.sleep(3)
                return True

            # Fallback: Start Menu search
            subprocess.Popen(
                ["powershell", "-Command", "Start-Process spotify:"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f"Failed to launch Spotify: {e}")
            return False
    return False


def _send_media_key(key: str) -> None:
    """Send a media key press via PowerShell (no pyautogui needed)."""
    key_map = {
        "play_pause": "0xB3",  # VK_MEDIA_PLAY_PAUSE
        "next": "0xB0",        # VK_MEDIA_NEXT_TRACK
        "previous": "0xB1",    # VK_MEDIA_PREV_TRACK
        "stop": "0xB2",        # VK_MEDIA_STOP
        "volume_up": "0xAF",   # VK_VOLUME_UP
        "volume_down": "0xAE", # VK_VOLUME_DOWN
        "mute": "0xAD",        # VK_VOLUME_MUTE
    }
    vk = key_map.get(key)
    if not vk:
        return

    ps_script = f"""
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class MediaKeys {{
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
    public static void Press(byte key) {{
        keybd_event(key, 0, 0, UIntPtr.Zero);
        keybd_event(key, 0, 2, UIntPtr.Zero);
    }}
}}
"@
[MediaKeys]::Press({vk})
"""
    try:
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as e:
        logger.error(f"Media key '{key}' failed: {e}")


def _get_current_track() -> Optional[str]:
    """Get the currently playing track title from Spotify's window title."""
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-Process Spotify -ErrorAction SilentlyContinue | "
                 "Where-Object { $_.MainWindowTitle -ne '' }).MainWindowTitle"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            title = result.stdout.strip()
            if title and title != "Spotify" and title != "Spotify Free" and title != "Spotify Premium":
                return title
            return None
        except Exception:
            return None
    return None


def _play_search_via_uri(query: str) -> str:
    """Open a Spotify search URI to play something."""
    import urllib.parse
    encoded = urllib.parse.quote(query)
    try:
        subprocess.Popen(
            ["powershell", "-Command", f"Start-Process 'spotify:search:{encoded}'"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        time.sleep(2)
        return f"Opened Spotify search for '{query}'. The first result should start playing."
    except Exception as e:
        return f"Failed to open Spotify search: {e}"


@register_tool(
    name="control_spotify",
    description="Control Spotify music playback. Use for: playing music, "
                "pausing, skipping tracks, checking what's playing, "
                "playing specific songs/artists/playlists, and volume control. "
                "Spotify will be launched automatically if not running.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to perform: play | pause | next | previous | "
                               "what_playing | search_play | volume_up | volume_down | mute",
            },
            "query": {
                "type": "STRING",
                "description": "Song, artist, playlist, or genre to play (for search_play action). "
                               "E.g., 'lo-fi beats', 'Imagine Dragons', 'chill playlist'",
            },
        },
        "required": ["action"],
    },
    category="media",
)
def control_spotify(action: str, query: str = "") -> str:
    """Control Spotify playback."""
    action = action.lower().strip()

    # Ensure Spotify is running for most actions
    if action != "what_playing" and not _is_spotify_running():
        logger.info("Spotify not running, launching...")
        if not _launch_spotify():
            return "Couldn't launch Spotify. Is it installed?"
        if not _is_spotify_running():
            return "Spotify was launched but may still be loading. Try again in a few seconds."

    # ── Actions ──────────────────────────────────────────────────
    if action in ("play", "resume"):
        _send_media_key("play_pause")
        track = _get_current_track()
        if track:
            return f"▶ Playing: {track}"
        return "▶ Playback resumed."

    elif action == "pause":
        _send_media_key("play_pause")
        return "⏸ Paused."

    elif action in ("next", "skip"):
        _send_media_key("next")
        time.sleep(1)
        track = _get_current_track()
        if track:
            return f"⏭ Skipped. Now playing: {track}"
        return "⏭ Skipped to next track."

    elif action in ("previous", "prev", "back"):
        _send_media_key("previous")
        time.sleep(1)
        track = _get_current_track()
        if track:
            return f"⏮ Previous track: {track}"
        return "⏮ Went back to previous track."

    elif action in ("what_playing", "now_playing", "current"):
        if not _is_spotify_running():
            return "Spotify is not running right now."
        track = _get_current_track()
        if track:
            return f"🎵 Currently playing: {track}"
        return "Spotify is open but nothing seems to be playing."

    elif action in ("search_play", "search", "play_song"):
        if not query:
            return "What would you like me to play? Give me a song, artist, or genre."
        return _play_search_via_uri(query)

    elif action == "volume_up":
        for _ in range(5):  # ~10% increase
            _send_media_key("volume_up")
        return "🔊 Volume up."

    elif action == "volume_down":
        for _ in range(5):
            _send_media_key("volume_down")
        return "🔉 Volume down."

    elif action == "mute":
        _send_media_key("mute")
        return "🔇 Toggled mute."

    else:
        return (
            f"Unknown Spotify action: '{action}'. "
            "Available: play, pause, next, previous, what_playing, search_play, "
            "volume_up, volume_down, mute"
        )
