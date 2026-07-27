"""
EVA Screen Processor — Screen capture + webcam vision analysis.
Instant acknowledgment: returns a quick "looking now" response so EVA
speaks while capturing. The real analysis follows as a second turn.
"""

import base64
import io
import logging
import threading
import time
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.screen_processor")

# ── Cooldown & busy state ───────────────────────────────────────
_COOLDOWN = 4.0  # seconds between captures
_busy = False
_busy_since = 0.0  # monotonic timestamp
_busy_lock = threading.Lock()

# Reference to the EvaLive instance (set at startup)
_eva_live_ref = None


def set_eva_live_ref(ref) -> None:
    """Set the EvaLive instance reference for injecting vision results."""
    global _eva_live_ref
    _eva_live_ref = ref


def _capture_screen() -> Optional[bytes]:
    """Capture the primary screen as a JPEG byte array."""
    try:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Compress to JPEG for efficiency
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70, optimize=True)
            return buffer.getvalue()
    except Exception as e:
        logger.error(f"Screen capture failed: {e}")
        return None


def _capture_webcam() -> Optional[bytes]:
    """Capture a single frame from the default webcam as JPEG."""
    try:
        import cv2

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return None

        ret, frame = cap.read()
        cap.release()

        if not ret:
            return None

        # Encode as JPEG
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return buffer.tobytes()
    except Exception as e:
        logger.error(f"Webcam capture failed: {e}")
        return None


def _analyze_image(image_bytes: bytes, prompt: str) -> str:
    """Send an image to Gemini (or Ollama fallback) for vision analysis."""
    try:
        from core.llm_router import smart_generate
        result = smart_generate(prompt, image_bytes=image_bytes)
        return result
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return f"Image analysis failed: {str(e)}"


def _background_capture_and_analyze(
    capture_fn, prompt: str, source_label: str
) -> None:
    """
    Run capture + analysis in a background thread, then inject the
    result back into the live session as a follow-up turn.
    """
    global _busy

    try:
        image_bytes = capture_fn()
        if image_bytes is None:
            result = f"Failed to capture {source_label}."
        else:
            result = _analyze_image(image_bytes, prompt)

        # Inject the real analysis as a follow-up message
        if _eva_live_ref:
            _eva_live_ref.inject_text_command(
                f"[VISION RESULT — {source_label}]\n"
                f"Here is the actual analysis of what you see:\n\n"
                f"{result}\n\n"
                f"Now describe this to the user naturally. "
                f"Do NOT say you were 'looking' — just share the findings."
            )
        else:
            logger.warning("No EvaLive ref — cannot inject vision result")

    except Exception as e:
        logger.error(f"Background {source_label} analysis failed: {e}")
    finally:
        with _busy_lock:
            _busy = False


@register_tool(
    name="analyze_screen",
    description="Capture and analyze what's currently on the user's screen. "
                "Use when the user asks 'what's on my screen', 'read this', 'look at this'.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "What to analyze or look for on the screen",
            },
        },
        "required": [],
    },
    category="vision",
    cooldown_seconds=4.0,
)
def analyze_screen(prompt: str = "Describe what you see on the screen in detail.") -> str:
    """
    Capture the screen and analyze it with Gemini vision.
    Returns an immediate acknowledgment; real analysis follows as a second turn.
    """
    global _busy, _busy_since

    with _busy_lock:
        if _busy and (time.monotonic() - _busy_since) < _COOLDOWN:
            return (
                "I'm still processing the previous capture. "
                "Please wait a moment before asking again."
            )
        _busy = True
        _busy_since = time.monotonic()

    # Spawn background thread for capture + analysis
    thread = threading.Thread(
        target=_background_capture_and_analyze,
        args=(_capture_screen, prompt, "screen"),
        daemon=True,
    )
    thread.start()

    # Return immediate acknowledgment
    return (
        "[ACK] Tell the user in ONE short natural sentence that you are "
        "looking at their screen right now. Do NOT describe or guess any "
        "content — the actual analysis will arrive in the next message."
    )


@register_tool(
    name="analyze_webcam",
    description="Capture and analyze what the webcam sees. "
                "Use when the user asks 'look at me', 'what do you see', 'can you see me'.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "What to analyze or describe from the webcam",
            },
        },
        "required": [],
    },
    category="vision",
    cooldown_seconds=4.0,
)
def analyze_webcam(prompt: str = "Describe what you see through the webcam.") -> str:
    """
    Capture from the webcam and analyze with Gemini vision.
    Returns an immediate acknowledgment; real analysis follows as a second turn.
    """
    global _busy, _busy_since

    with _busy_lock:
        if _busy and (time.monotonic() - _busy_since) < _COOLDOWN:
            return (
                "I'm still processing the previous capture. "
                "Please wait a moment before asking again."
            )
        _busy = True
        _busy_since = time.monotonic()

    # Spawn background thread for capture + analysis
    thread = threading.Thread(
        target=_background_capture_and_analyze,
        args=(_capture_webcam, prompt, "webcam"),
        daemon=True,
    )
    thread.start()

    # Return immediate acknowledgment
    return (
        "[ACK] Tell the user in ONE short natural sentence that you are "
        "looking through their camera right now. Do NOT describe or guess "
        "any content — the actual analysis will arrive in the next message."
    )


def get_screen_image_bytes() -> Optional[bytes]:
    """Utility: get raw screen capture bytes (for other modules/UI)."""
    return _capture_screen()


def get_webcam_image_bytes() -> Optional[bytes]:
    """Utility: get raw webcam frame bytes (for other modules/UI)."""
    return _capture_webcam()
