"""
EVA Screen Processor — Screen capture + webcam vision analysis.
Captures screen/webcam, compresses, sends to Gemini for analysis.
"""

import base64
import io
import logging
import time
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.screen_processor")

_last_screen_capture = 0.0
_last_webcam_capture = 0.0
_COOLDOWN = 5.0  # seconds between captures


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
    """Send an image to Gemini for vision analysis."""
    try:
        import google.generativeai as genai
        from memory.config_manager import config

        api_key = config.get("api_key")
        if not api_key:
            return "Error: No API key configured."

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        response = model.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": image_b64},
        ])

        if response and response.text:
            return response.text
        return "I captured the image but couldn't analyze it."
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return f"Image analysis failed: {str(e)}"


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
    cooldown_seconds=5.0,
)
def analyze_screen(prompt: str = "Describe what you see on the screen in detail.") -> str:
    """Capture the screen and analyze it with Gemini vision."""
    global _last_screen_capture
    now = time.time()
    if now - _last_screen_capture < _COOLDOWN:
        return "Screen was just analyzed. Please wait a moment before asking again."
    _last_screen_capture = now

    image_bytes = _capture_screen()
    if image_bytes is None:
        return "Failed to capture the screen."

    return _analyze_image(image_bytes, prompt)


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
    cooldown_seconds=5.0,
)
def analyze_webcam(prompt: str = "Describe what you see through the webcam.") -> str:
    """Capture from the webcam and analyze with Gemini vision."""
    global _last_webcam_capture
    now = time.time()
    if now - _last_webcam_capture < _COOLDOWN:
        return "Webcam was just analyzed. Please wait a moment."
    _last_webcam_capture = now

    image_bytes = _capture_webcam()
    if image_bytes is None:
        return "Failed to access the webcam. It may be in use or not available."

    return _analyze_image(image_bytes, prompt)


def get_screen_image_bytes() -> Optional[bytes]:
    """Utility: get raw screen capture bytes (for other modules/UI)."""
    return _capture_screen()


def get_webcam_image_bytes() -> Optional[bytes]:
    """Utility: get raw webcam frame bytes (for other modules/UI)."""
    return _capture_webcam()
