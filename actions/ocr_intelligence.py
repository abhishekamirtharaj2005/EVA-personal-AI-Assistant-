"""
EVA OCR Intelligence — Extract text from screen, images, and documents.
Uses Gemini vision for intelligent OCR with context understanding.
Can also fill forms and read error messages.
"""

import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool
from utils.platform_utils import IS_WINDOWS

logger = logging.getLogger("eva.actions.ocr_intelligence")


def _capture_screen_region(x: int = 0, y: int = 0, w: int = 0, h: int = 0) -> Optional[bytes]:
    """Capture a screen region or full screen as PNG bytes."""
    try:
        import mss
        with mss.mss() as sct:
            if w > 0 and h > 0:
                monitor = {"left": x, "top": y, "width": w, "height": h}
            else:
                monitor = sct.monitors[1]  # Primary monitor

            img = sct.grab(monitor)

            from PIL import Image
            import io
            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG", optimize=True)
            return buf.getvalue()
    except Exception as e:
        logger.error(f"Screen capture failed: {e}")
        return None


def _ocr_with_tesseract(image_bytes: bytes) -> str:
    """OCR using Tesseract (fallback if available)."""
    try:
        import pytesseract
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(img)
        return text.strip()
    except ImportError:
        return ""
    except Exception as e:
        logger.error(f"Tesseract OCR failed: {e}")
        return ""


def _ocr_with_gemini(image_bytes: bytes, prompt: str = "Extract all text from this image.") -> str:
    """OCR using Gemini vision API."""
    try:
        import base64
        from google import genai

        from memory.config_manager import config
        api_key = config.get("gemini_api_key", "") or config.get("api_key", "")
        if not api_key:
            return ""

        client = genai.Client(api_key=api_key)
        b64 = base64.b64encode(image_bytes).decode("ascii")

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {"inline_data": {"mime_type": "image/png", "data": b64}},
                {"text": prompt},
            ],
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini OCR failed: {e}")
        return ""


@register_tool(
    name="ocr_extract",
    description="Extract text from screen, images, or specific screen regions using AI vision. "
                "Can read error messages, extract tracking numbers, read documents, "
                "and understand context of on-screen content.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: screen (full screen OCR), region (specific area), "
                               "file (from image file), smart (contextual extraction with a question)",
            },
            "question": {
                "type": "STRING",
                "description": "Specific question about the image content. "
                               "E.g., 'What is the error message?', 'Extract the tracking number'",
            },
            "file_path": {
                "type": "STRING",
                "description": "Path to image file (for file action)",
            },
            "x": {"type": "INTEGER", "description": "Left coordinate for region capture"},
            "y": {"type": "INTEGER", "description": "Top coordinate for region capture"},
            "width": {"type": "INTEGER", "description": "Width for region capture"},
            "height": {"type": "INTEGER", "description": "Height for region capture"},
        },
        "required": ["action"],
    },
    category="vision",
    cooldown_seconds=3.0,
)
def ocr_extract(
    action: str,
    question: str = "Extract all visible text from this image accurately.",
    file_path: str = "",
    x: int = 0, y: int = 0, width: int = 0, height: int = 0,
) -> str:
    """Extract text from screen or images."""
    action = action.lower().strip()

    if action in ("screen", "smart"):
        img_bytes = _capture_screen_region()
        if not img_bytes:
            return "Failed to capture screen."

        prompt = question if action == "smart" else "Extract all text from this screenshot accurately. Preserve formatting."
        result = _ocr_with_gemini(img_bytes, prompt)
        if not result:
            result = _ocr_with_tesseract(img_bytes)
        if not result:
            return "Could not extract text from the screen."
        return f"📸 Extracted text:\n{result}"

    elif action == "region":
        if width <= 0 or height <= 0:
            return "I need region coordinates: x, y, width, height."
        img_bytes = _capture_screen_region(x, y, width, height)
        if not img_bytes:
            return "Failed to capture screen region."
        result = _ocr_with_gemini(img_bytes, question)
        return f"📸 Region text:\n{result}" if result else "No text found in region."

    elif action == "file":
        if not file_path:
            return "Which image file should I read? Give me the file path."
        p = Path(file_path)
        if not p.exists():
            return f"File not found: {file_path}"
        img_bytes = p.read_bytes()
        result = _ocr_with_gemini(img_bytes, question)
        return f"📸 Text from {p.name}:\n{result}" if result else "No text found."

    return f"Unknown OCR action '{action}'. Use: screen, region, file, or smart."
