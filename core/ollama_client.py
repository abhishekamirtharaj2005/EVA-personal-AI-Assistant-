"""
EVA Ollama Client — Local LLM connectivity via Ollama REST API.
Handles text generation, vision analysis, model auto-detection,
and availability checks.
"""

import base64
import logging
import requests
from typing import Optional

from memory.config_manager import config

logger = logging.getLogger("eva.core.ollama")

# Model preference order for auto-selection
_TEXT_MODEL_PREFS = [
    "llama3.1", "llama3", "llama3.2", "mistral", "qwen2.5",
    "qwen2", "gemma2", "phi3", "deepseek-coder",
]
_VISION_MODEL_PREFS = [
    "llava", "llama3.2-vision", "moondream", "bakllava",
    "llava-llama3", "llava-phi3",
]

_DEFAULT_URL = "http://localhost:11434"
_TIMEOUT = 60  # seconds


class OllamaClient:
    """Thread-safe Ollama REST API client."""

    def __init__(self):
        self._cached_models: Optional[list[str]] = None
        self._available: Optional[bool] = None

    @property
    def base_url(self) -> str:
        return config.get("ollama_url", _DEFAULT_URL).rstrip("/")

    @property
    def enabled(self) -> bool:
        return config.get("ollama_enabled", True)

    def is_available(self) -> bool:
        """Check if Ollama server is running."""
        if not self.enabled:
            return False
        try:
            resp = requests.get(
                f"{self.base_url}/api/tags", timeout=3
            )
            self._available = resp.status_code == 200
            if self._available:
                data = resp.json()
                self._cached_models = [
                    m.get("name", "").split(":")[0]
                    for m in data.get("models", [])
                ]
            return self._available
        except Exception:
            self._available = False
            self._cached_models = None
            return False

    def list_models(self) -> list[str]:
        """List installed model names."""
        if self._cached_models is None:
            self.is_available()
        return self._cached_models or []

    def _pick_model(self, preferences: list[str],
                    config_key: str) -> Optional[str]:
        """Auto-select best model from installed ones."""
        # User override from config
        user_model = config.get(config_key, "").strip()
        if user_model:
            return user_model

        installed = self.list_models()
        if not installed:
            return None

        # Match by preference order
        for pref in preferences:
            for model in installed:
                if model.startswith(pref):
                    return model

        # Fallback: first installed model
        return installed[0] if installed else None

    @property
    def text_model(self) -> Optional[str]:
        return self._pick_model(_TEXT_MODEL_PREFS, "ollama_model")

    @property
    def vision_model(self) -> Optional[str]:
        return self._pick_model(_VISION_MODEL_PREFS, "ollama_vision_model")

    def generate(self, prompt: str,
                 model: Optional[str] = None) -> Optional[str]:
        """
        Generate text using Ollama.
        Returns the response text, or None on failure.
        """
        if not self.enabled:
            return None

        model = model or self.text_model
        if not model:
            logger.warning("No Ollama text model available")
            return None

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 1024,
                    },
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            result = data.get("response", "").strip()
            if result:
                logger.info(f"Ollama generate OK ({model}, "
                            f"{len(result)} chars)")
            return result or None

        except requests.Timeout:
            logger.warning(f"Ollama generate timed out ({model})")
            return None
        except Exception as e:
            logger.warning(f"Ollama generate failed ({model}): {e}")
            return None

    def generate_vision(self, prompt: str, image_bytes: bytes,
                        model: Optional[str] = None) -> Optional[str]:
        """
        Generate text from an image using Ollama vision model.
        Returns the response text, or None on failure.
        """
        if not self.enabled:
            return None

        model = model or self.vision_model
        if not model:
            logger.warning("No Ollama vision model available")
            return None

        try:
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 1024,
                    },
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            result = data.get("response", "").strip()
            if result:
                logger.info(f"Ollama vision OK ({model}, "
                            f"{len(result)} chars)")
            return result or None

        except requests.Timeout:
            logger.warning(f"Ollama vision timed out ({model})")
            return None
        except Exception as e:
            logger.warning(f"Ollama vision failed ({model}): {e}")
            return None

    def get_status(self) -> dict:
        """Return connection status for UI display."""
        available = self.is_available()
        models = self.list_models()
        text_m = self.text_model
        vision_m = self.vision_model
        return {
            "available": available,
            "models": models,
            "text_model": text_m,
            "vision_model": vision_m,
            "url": self.base_url,
        }


# Module-level singleton
ollama = OllamaClient()
