"""
EVA Wake Word Detection — "Hey EVA" activation.
Uses a lightweight keyword spotter running on a background thread.
When detected, unmutes the mic so EVA starts listening.

Two modes:
1. Simple mode (no dependencies): Monitors Gemini's input transcription for "hey eva"
2. Advanced mode (requires openwakeword): Local neural net keyword detection

Falls back to simple mode if openwakeword is not installed.
"""

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger("eva.wakeword")


class WakeWordDetector:
    """
    Background wake word detector.
    
    Simple mode: Watches transcription text for the wake phrase.
    This is zero-dependency and works with the existing Gemini session.
    """

    WAKE_PHRASES = [
        "hey eva", "hay eva", "hey ava", "a eva", "hello eva",
        "okay eva", "ok eva", "hi eva", "eva listen", "wake up eva",
        "hey eva,", "hey, eva",
    ]

    def __init__(self):
        self._enabled: bool = False
        self._on_wake: Optional[Callable] = None
        self._cooldown: float = 3.0  # seconds between wake triggers
        self._last_triggered: float = 0.0
        self._advanced_available: bool = False
        self._advanced_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Check for openwakeword
        try:
            import openwakeword
            self._advanced_available = True
            logger.info("openwakeword available — advanced mode ready")
        except ImportError:
            logger.info("openwakeword not found — using simple transcript mode")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self, on_wake: Callable) -> None:
        """Enable wake word detection with a callback."""
        self._on_wake = on_wake
        self._enabled = True
        logger.info("Wake word detection enabled")

        if self._advanced_available:
            self._start_advanced()

    def disable(self) -> None:
        """Disable wake word detection."""
        self._enabled = False
        self._stop_event.set()
        logger.info("Wake word detection disabled")

    def check_transcript(self, text: str) -> bool:
        """
        Check if a transcript contains the wake phrase.
        Called from the Gemini input transcription handler.
        Returns True if wake word detected.
        """
        if not self._enabled or not text:
            return False

        text_lower = text.lower().strip()

        for phrase in self.WAKE_PHRASES:
            if phrase in text_lower:
                now = time.monotonic()
                if (now - self._last_triggered) > self._cooldown:
                    self._last_triggered = now
                    logger.info(f"Wake word detected: '{phrase}' in '{text_lower}'")
                    if self._on_wake:
                        self._on_wake()
                    return True
        return False

    def _start_advanced(self) -> None:
        """Start the advanced openwakeword detector in a background thread."""
        if not self._advanced_available:
            return

        self._stop_event.clear()
        self._advanced_thread = threading.Thread(
            target=self._advanced_loop, daemon=True, name="wake-word"
        )
        self._advanced_thread.start()

    def _advanced_loop(self) -> None:
        """Background loop using openwakeword for local detection."""
        try:
            import numpy as np
            import sounddevice as sd
            from openwakeword.model import Model

            model = Model(
                wakeword_models=["hey_jarvis"],  # closest available model
                inference_framework="onnx",
            )

            CHUNK = 1280  # ~80ms at 16kHz
            THRESHOLD = 0.5

            def audio_callback(indata, frames, time_info, status):
                if not self._enabled:
                    return
                audio = np.squeeze(indata)
                prediction = model.predict(audio)

                for mdl_name, score in prediction.items():
                    if score > THRESHOLD:
                        now = time.monotonic()
                        if (now - self._last_triggered) > self._cooldown:
                            self._last_triggered = now
                            logger.info(f"Wake word (neural): score={score:.2f}")
                            if self._on_wake:
                                self._on_wake()

            with sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="int16",
                blocksize=CHUNK,
                callback=audio_callback,
            ):
                logger.info("Advanced wake word listener active")
                while not self._stop_event.is_set():
                    self._stop_event.wait(timeout=0.5)

        except Exception as e:
            logger.error(f"Advanced wake word failed: {e}")
            logger.info("Falling back to simple transcript mode")
            self._advanced_available = False


# Module singleton
wake_detector = WakeWordDetector()
