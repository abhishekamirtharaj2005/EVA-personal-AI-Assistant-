"""
EVA AI Image Generation — Generate images by voice description.
Uses Gemini Imagen API or DALL-E API for image generation.
Can auto-set generated images as wallpaper.
"""

import base64
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.image_gen")

_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "config" / "generated_images"
_IST = timezone(timedelta(hours=5, minutes=30))


def _generate_with_gemini(prompt: str, api_key: str) -> Optional[Path]:
    """Generate image using Gemini's image generation."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(_IST).strftime("%Y%m%d_%H%M%S")

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                ext = part.inline_data.mime_type.split("/")[-1]
                if ext == "jpeg":
                    ext = "jpg"
                filename = f"eva_gen_{timestamp}.{ext}"
                filepath = _OUTPUT_DIR / filename
                filepath.write_bytes(part.inline_data.data)
                logger.info(f"Image generated: {filepath}")
                return filepath

        return None
    except Exception as e:
        logger.error(f"Gemini image gen failed: {e}")
        return None


def _generate_with_openai(prompt: str, api_key: str) -> Optional[Path]:
    """Generate image using OpenAI DALL-E 3."""
    try:
        import requests

        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024",
                "response_format": "b64_json",
            },
            timeout=60,
        )

        if response.status_code != 200:
            logger.error(f"DALL-E error: {response.text[:200]}")
            return None

        data = response.json()
        img_b64 = data["data"][0]["b64_json"]
        img_bytes = base64.b64decode(img_b64)

        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(_IST).strftime("%Y%m%d_%H%M%S")
        filepath = _OUTPUT_DIR / f"eva_gen_{timestamp}.png"
        filepath.write_bytes(img_bytes)
        logger.info(f"Image generated: {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"DALL-E gen failed: {e}")
        return None


def _set_wallpaper(image_path: Path) -> bool:
    """Set image as desktop wallpaper on Windows."""
    try:
        import ctypes
        ctypes.windll.user32.SystemParametersInfoW(
            20, 0, str(image_path.resolve()), 3
        )
        return True
    except Exception as e:
        logger.error(f"Set wallpaper failed: {e}")
        return False


@register_tool(
    name="generate_image",
    description="Generate AI images from text descriptions. "
                "Can create art, wallpapers, logos, illustrations. "
                "Optionally set the generated image as desktop wallpaper.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "Description of the image to generate. Be detailed. "
                               "E.g., 'A cyberpunk city at night with neon lights and rain'",
            },
            "set_wallpaper": {
                "type": "BOOLEAN",
                "description": "If true, set the generated image as desktop wallpaper",
            },
            "style": {
                "type": "STRING",
                "description": "Art style: realistic | anime | digital_art | "
                               "watercolor | oil_painting | pixel_art | minimalist",
            },
        },
        "required": ["prompt"],
    },
    category="creative",
)
def generate_image(
    prompt: str,
    set_wallpaper: bool = False,
    style: str = "",
) -> str:
    """Generate an AI image from a text description."""
    from memory.config_manager import config

    # Enhance prompt with style
    full_prompt = prompt
    if style:
        style_map = {
            "realistic": "photorealistic, highly detailed, 8K resolution",
            "anime": "anime art style, vibrant colors, Studio Ghibli quality",
            "digital_art": "digital art, trending on ArtStation, highly detailed",
            "watercolor": "watercolor painting, soft colors, artistic brush strokes",
            "oil_painting": "oil painting, rich textures, classical art style",
            "pixel_art": "pixel art, retro game aesthetic, 16-bit style",
            "minimalist": "minimalist design, clean lines, simple shapes",
        }
        style_desc = style_map.get(style.lower(), style)
        full_prompt = f"{prompt}, {style_desc}"

    if set_wallpaper:
        full_prompt += ", desktop wallpaper, 16:9 aspect ratio, high resolution"

    # Try Gemini first, then OpenAI
    gemini_key = config.get("gemini_api_key", "") or config.get("api_key", "")
    openai_key = config.get("openai_api_key", "")

    filepath = None

    if gemini_key:
        filepath = _generate_with_gemini(full_prompt, gemini_key)

    if not filepath and openai_key:
        filepath = _generate_with_openai(full_prompt, openai_key)

    if not filepath:
        return (
            "Failed to generate image. Make sure your API key supports image generation. "
            "Gemini Imagen or OpenAI DALL-E is required."
        )

    result = f"🖼️ Image generated: {filepath}\n"

    if set_wallpaper:
        if _set_wallpaper(filepath):
            result += "🖥️ Set as desktop wallpaper!"
        else:
            result += "⚠️ Generated but couldn't set as wallpaper."

    # Open the image
    try:
        import os
        os.startfile(str(filepath))
        result += "\n📂 Opened in default viewer."
    except Exception:
        pass

    return result
