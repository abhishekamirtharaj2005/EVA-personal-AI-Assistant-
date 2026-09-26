"""
EVA Screen Recording — Record screen with optional voice narration.
Uses mss for capture and ffmpeg for encoding.
"""

import logging
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.screen_recorder")

_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "config" / "recordings"
_IST = timezone(timedelta(hours=5, minutes=30))


class ScreenRecorder:
    """Manages screen recording sessions."""

    def __init__(self):
        self._recording = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._output_path: Optional[Path] = None
        self._start_time: float = 0
        self._frame_count: int = 0

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def duration_seconds(self) -> int:
        if not self._recording:
            return 0
        return int(time.time() - self._start_time)

    def start(self, fps: int = 10, output_name: str = "") -> Path:
        """Start recording the screen."""
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        if not output_name:
            timestamp = datetime.now(_IST).strftime("%Y%m%d_%H%M%S")
            output_name = f"eva_recording_{timestamp}"

        self._output_path = _OUTPUT_DIR / f"{output_name}.mp4"
        self._recording = True
        self._stop_event.clear()
        self._start_time = time.time()
        self._frame_count = 0

        self._thread = threading.Thread(
            target=self._record_loop,
            args=(fps,),
            daemon=True,
            name="screen-recorder",
        )
        self._thread.start()
        logger.info(f"Recording started: {self._output_path}")
        return self._output_path

    def stop(self) -> Optional[Path]:
        """Stop recording and return the output file path."""
        if not self._recording:
            return None

        self._recording = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)

        logger.info(
            f"Recording stopped: {self._frame_count} frames, "
            f"{self.duration_seconds}s"
        )
        return self._output_path

    def _record_loop(self, fps: int) -> None:
        """Record screen frames and pipe to ffmpeg."""
        try:
            import mss
            from PIL import Image
            import io

            with mss.mss() as sct:
                monitor = sct.monitors[1]
                width, height = monitor["width"], monitor["height"]

                # Use ffmpeg for encoding
                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-f", "rawvideo",
                    "-vcodec", "rawvideo",
                    "-pix_fmt", "bgra",
                    "-s", f"{width}x{height}",
                    "-r", str(fps),
                    "-i", "-",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "23",
                    "-pix_fmt", "yuv420p",
                    str(self._output_path),
                ]

                try:
                    proc = subprocess.Popen(
                        ffmpeg_cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    )
                except FileNotFoundError:
                    # ffmpeg not available — fallback to PIL frame saving
                    logger.warning("ffmpeg not found, using PIL fallback")
                    self._record_pil_fallback(sct, monitor, fps)
                    return

                frame_interval = 1.0 / fps

                while not self._stop_event.is_set():
                    t0 = time.monotonic()
                    img = sct.grab(monitor)
                    try:
                        proc.stdin.write(img.bgra)
                        self._frame_count += 1
                    except (BrokenPipeError, OSError):
                        break

                    elapsed = time.monotonic() - t0
                    sleep_time = frame_interval - elapsed
                    if sleep_time > 0:
                        self._stop_event.wait(timeout=sleep_time)

                proc.stdin.close()
                proc.wait(timeout=10)

        except Exception as e:
            logger.error(f"Recording error: {e}")
            self._recording = False

    def _record_pil_fallback(self, sct, monitor, fps) -> None:
        """PIL-based fallback when ffmpeg is not available."""
        from PIL import Image
        import io

        frames_dir = _OUTPUT_DIR / "frames"
        frames_dir.mkdir(exist_ok=True)

        frame_interval = 1.0 / fps

        while not self._stop_event.is_set():
            t0 = time.monotonic()
            img = sct.grab(monitor)
            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            pil_img.save(frames_dir / f"frame_{self._frame_count:06d}.jpg", quality=80)
            self._frame_count += 1

            elapsed = time.monotonic() - t0
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                self._stop_event.wait(timeout=sleep_time)

        logger.info(f"Saved {self._frame_count} frames to {frames_dir}")


# Module singleton
_recorder = ScreenRecorder()


@register_tool(
    name="screen_record",
    description="Record the screen as a video. Can start/stop recording. "
                "Use when the user wants to capture their screen, make a tutorial, "
                "or record a demo. Saves as MP4.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: start | stop | status",
            },
            "filename": {
                "type": "STRING",
                "description": "Output filename (without extension). Optional.",
            },
            "fps": {
                "type": "INTEGER",
                "description": "Frames per second (default: 10, max: 30)",
            },
        },
        "required": ["action"],
    },
    category="media",
)
def screen_record(action: str, filename: str = "", fps: int = 10) -> str:
    """Control screen recording."""
    action = action.lower().strip()

    if action == "start":
        if _recorder.is_recording:
            return f"🔴 Already recording ({_recorder.duration_seconds}s). Say 'stop recording' to finish."

        fps = min(max(fps, 5), 30)
        path = _recorder.start(fps, filename)
        return f"🔴 Recording started at {fps} FPS.\n   Output: {path}\n   Say 'stop recording' when done."

    elif action == "stop":
        if not _recorder.is_recording:
            return "No active recording."

        duration = _recorder.duration_seconds
        path = _recorder.stop()

        if path and path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            return (
                f"⏹️ Recording saved!\n"
                f"   Duration: {duration}s\n"
                f"   File: {path}\n"
                f"   Size: {size_mb:.1f} MB"
            )
        return f"⏹️ Recording stopped ({duration}s). Frames saved to output directory."

    elif action == "status":
        if not _recorder.is_recording:
            return "Not currently recording."
        return (
            f"🔴 Recording in progress\n"
            f"   Duration: {_recorder.duration_seconds}s\n"
            f"   Frames: {_recorder._frame_count}\n"
            f"   Output: {_recorder._output_path}"
        )

    return f"Unknown recording action '{action}'. Use: start, stop, or status."
