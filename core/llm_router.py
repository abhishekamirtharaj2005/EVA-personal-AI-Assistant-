"""
EVA LLM Router — Smart routing between Gemini and Ollama.
Tries Gemini first for text/vision tasks; on 429 or failure,
automatically falls back to local Ollama.
"""

import base64
import logging
from typing import Optional

logger = logging.getLogger("eva.core.llm_router")


def smart_generate(prompt: str,
                   image_bytes: Optional[bytes] = None) -> str:
    """
    Generate text (or vision analysis) using the best available provider.
    Priority: Gemini → Ollama → error message.

    Args:
        prompt: The text prompt.
        image_bytes: Optional JPEG bytes for vision analysis.

    Returns:
        Generated text, or an error message string.
    """
    # ── Try Gemini first ────────────────────────────────────
    gemini_result = _try_gemini(prompt, image_bytes)
    if gemini_result:
        return gemini_result

    # ── Fallback to Ollama ──────────────────────────────────
    ollama_result = _try_ollama(prompt, image_bytes)
    if ollama_result:
        return ollama_result

    return "Both cloud and local LLM are unavailable. Please check your API key or start Ollama."


def get_provider_status() -> dict:
    """Return availability of all providers."""
    status = {"gemini": False, "ollama": False}

    try:
        from memory.config_manager import config
        status["gemini"] = bool(config.get("api_key", ""))
    except Exception:
        pass

    try:
        from core.ollama_client import ollama
        status["ollama"] = ollama.is_available()
    except Exception:
        pass

    return status


# ── Internal Providers ──────────────────────────────────────────

def _try_gemini(prompt: str,
                image_bytes: Optional[bytes]) -> Optional[str]:
    """Try Gemini for generation. Returns None on failure/429."""
    try:
        import google.generativeai as genai
        from memory.config_manager import config

        api_key = config.get("api_key", "")
        if not api_key:
            return None

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        if image_bytes:
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            response = model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": image_b64},
            ])
        else:
            response = model.generate_content(prompt)

        if response and response.text:
            logger.info(f"Gemini generate OK ({len(response.text)} chars)")
            return response.text

    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "quota" in error_str.lower():
            logger.info("Gemini rate limited (429), falling back to Ollama")
        else:
            logger.warning(f"Gemini generate failed: {e}")

    return None


def _try_ollama(prompt: str,
                image_bytes: Optional[bytes]) -> Optional[str]:
    """Try Ollama for generation. Returns None on failure."""
    try:
        from core.ollama_client import ollama

        if not ollama.is_available():
            logger.debug("Ollama not available for fallback")
            return None

        if image_bytes:
            result = ollama.generate_vision(prompt, image_bytes)
        else:
            result = ollama.generate(prompt)

        if result:
            logger.info(f"Ollama fallback OK ({len(result)} chars)")
            return result

    except Exception as e:
        logger.warning(f"Ollama fallback failed: {e}")

    return None
