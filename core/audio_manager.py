"""
EVA Audio Manager
Mic capture → PCM queue, speaker playback with barge-in interrupt,
and amplitude tracking for the UI visualization.
"""

import asyncio
import collections
import logging
import threading
from typing import Optional, Callable

import numpy as np
import sounddevice as sd

logger = logging.getLogger("eva.audio")

# Audio format constants (Gemini Live expects 16-bit PCM)
INPUT_SAMPLE_RATE = 16000   # Gemini Live input
OUTPUT_SAMPLE_RATE = 24000  # Gemini Live output
CHANNELS = 1
DTYPE = "int16"
INPUT_BLOCK_SIZE = 1600     # 100ms chunks at 16kHz
OUTPUT_BLOCK_SIZE = 2400    # 100ms chunks at 24kHz


class AudioManager:
    """
    Manages mic capture and speaker playback as async-compatible queues.
    Thread-safe, designed to feed an asyncio event loop from callback threads.
    """

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self._loop = loop

        # Async queues bridging audio threads ↔ event loop
        # Created lazily when start_input/start_output are called
        self._input_queue: Optional[asyncio.Queue] = None
        self._output_queue: Optional[asyncio.Queue] = None

        # Streams
        self._input_stream: Optional[sd.RawInputStream] = None
        self._output_stream: Optional[sd.RawOutputStream] = None

        # State
        self._is_speaking = False
        self._is_listening = False
        self._interrupted = False

        # Amplitude tracking for UI visualization
        self._input_amplitude: float = 0.0
        self._output_amplitude: float = 0.0
        self._amplitude_callbacks: list[Callable] = []

        # Rolling buffer for waveform display
        self._waveform_buffer = collections.deque(maxlen=200)

    # ── Lifecycle ───────────────────────────────────────────────

    def start_input(self) -> None:
        """Start microphone capture with smart device selection."""
        if self._input_stream is not None:
            return

        # Create queue inside the running loop context
        if self._input_queue is None:
            self._input_queue = asyncio.Queue(maxsize=100)

        self._is_listening = True

        # Smart mic selection: config override → real hardware mic → default
        device = self._select_input_device()

        self._input_stream = sd.RawInputStream(
            samplerate=INPUT_SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=INPUT_BLOCK_SIZE,
            callback=self._input_callback,
            device=device,
        )
        self._input_stream.start()

        device_name = sd.query_devices(device)['name'] if device is not None else 'system default'
        logger.info(f"Mic capture started (16kHz mono PCM) — device: {device_name}")

    @staticmethod
    def _select_input_device():
        """
        Select the best input device.
        Priority:
          1. config 'mic_device' (index or name substring)
          2. First real hardware microphone (skip virtual cables)
          3. System default
        """
        from memory.config_manager import config as cfg

        # 1. Manual override from config
        mic_pref = cfg.get("mic_device", "")
        if mic_pref:
            # If it's a number, use as device index
            try:
                idx = int(mic_pref)
                dev = sd.query_devices(idx)
                if dev['max_input_channels'] > 0:
                    logger.info(f"Using configured mic device [{idx}]: {dev['name']}")
                    return idx
            except (ValueError, sd.PortAudioError):
                pass
            # If it's a string, search by name
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if mic_pref.lower() in d['name'].lower() and d['max_input_channels'] > 0:
                    logger.info(f"Using configured mic device [{i}]: {d['name']}")
                    return i

        # 2. Auto-detect: find first real hardware microphone
        #    Skip virtual cables, stereo mix, sound mappers, and loopback devices
        skip_keywords = [
            'virtual', 'cable', 'stereo mix', 'loopback', 'what u hear',
            'sound mapper', 'primary sound',
        ]
        prefer_keywords = ['microphone', 'mic']

        devices = sd.query_devices()
        candidates = []
        for i, d in enumerate(devices):
            if d['max_input_channels'] <= 0:
                continue
            name_lower = d['name'].lower()
            if any(kw in name_lower for kw in skip_keywords):
                continue
            # Prioritize devices with "microphone" or "mic" in the name
            priority = 0 if any(kw in name_lower for kw in prefer_keywords) else 1
            candidates.append((priority, i, d['name']))

        if candidates:
            candidates.sort()  # Lower priority number = better
            best_idx = candidates[0][1]
            best_name = candidates[0][2]
            logger.info(f"Auto-selected mic [{best_idx}]: {best_name}")
            return best_idx

        # 3. Fall back to system default
        default_idx = sd.default.device[0]
        if default_idx is not None and default_idx >= 0:
            dev = sd.query_devices(default_idx)
            logger.info(f"Using default mic [{default_idx}]: {dev['name']}")
            return default_idx

        return None

    def start_output(self) -> None:
        """Start speaker playback stream."""
        if self._output_stream is not None:
            return

        # Create queue inside the running loop context
        if self._output_queue is None:
            self._output_queue = asyncio.Queue(maxsize=200)

        self._output_stream = sd.RawOutputStream(
            samplerate=OUTPUT_SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=OUTPUT_BLOCK_SIZE,
        )
        self._output_stream.start()
        logger.info("Speaker playback started (24kHz mono PCM)")

    def stop(self) -> None:
        """Stop all audio streams."""
        self._is_listening = False
        self._is_speaking = False

        if self._input_stream:
            self._input_stream.stop()
            self._input_stream.close()
            self._input_stream = None

        if self._output_stream:
            self._output_stream.stop()
            self._output_stream.close()
            self._output_stream = None

        logger.info("Audio streams stopped")

    # ── Mic capture ─────────────────────────────────────────────

    def _input_callback(self, indata: bytes, frames: int,
                        time_info: dict, status: sd.CallbackFlags) -> None:
        """Called by sounddevice on the audio thread for each mic chunk."""
        if status:
            logger.warning(f"Input status: {status}")

        if not self._is_listening:
            return

        # Compute amplitude for visualization
        try:
            samples = np.frombuffer(indata, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(samples ** 2))) / 32768.0
            self._input_amplitude = rms
            self._waveform_buffer.append(rms)
            self._notify_amplitude("input", rms)
        except Exception:
            pass

        # Enqueue for the async send task
        if self._loop and self._input_queue and not self._input_queue.full():
            self._loop.call_soon_threadsafe(
                self._input_queue.put_nowait, bytes(indata)
            )

    async def get_input_chunk(self) -> bytes:
        """Async: get the next mic PCM chunk."""
        return await self._input_queue.get()

    # ── Speaker playback ────────────────────────────────────────

    async def play_chunk(self, data: bytes) -> None:
        """Async: write a PCM chunk to speakers."""
        if self._interrupted or self._output_stream is None:
            return

        self._is_speaking = True

        # Compute output amplitude
        try:
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(samples ** 2))) / 32768.0
            self._output_amplitude = rms
            self._notify_amplitude("output", rms)
        except Exception:
            pass

        # Write to speaker (blocking call, run in thread pool)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, self._output_stream.write, data
        )

    async def drain_output_queue(self) -> None:
        """Async: continuously drain the output queue to speakers."""
        while True:
            data = await self._output_queue.get()
            if self._interrupted:
                # Flush remaining items
                while not self._output_queue.empty():
                    try:
                        self._output_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                self._interrupted = False
                self._is_speaking = False
                continue

            await self.play_chunk(data)

            if self._output_queue.empty():
                self._is_speaking = False
                self._output_amplitude = 0.0
                self._notify_amplitude("output", 0.0)

    def enqueue_output(self, data: bytes) -> None:
        """Thread-safe: add audio data to the output queue."""
        if self._loop and self._output_queue and not self._output_queue.full():
            self._loop.call_soon_threadsafe(
                self._output_queue.put_nowait, data
            )

    # ── Barge-in / Interrupt ────────────────────────────────────

    def interrupt(self) -> None:
        """
        Flush the output queue and signal that the assistant was interrupted.
        Called when the user talks over the assistant (barge-in).
        """
        self._interrupted = True
        self._is_speaking = False
        self._output_amplitude = 0.0

        # Drain the queue (guard against None if audio not started yet)
        if self._output_queue is not None:
            while not self._output_queue.empty():
                try:
                    self._output_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

        self._notify_amplitude("output", 0.0)
        logger.info("Audio interrupted (barge-in)")

    def clear_interrupt(self) -> None:
        """Reset interrupt flag for next assistant turn."""
        self._interrupted = False

    # ── State queries ───────────────────────────────────────────

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def is_listening(self) -> bool:
        return self._is_listening

    @property
    def input_amplitude(self) -> float:
        return self._input_amplitude

    @property
    def output_amplitude(self) -> float:
        return self._output_amplitude

    @property
    def waveform_data(self) -> list[float]:
        return list(self._waveform_buffer)

    # ── Amplitude callbacks for UI ──────────────────────────────

    def on_amplitude(self, callback: Callable) -> None:
        """Register a callback: callback(source: str, amplitude: float)."""
        self._amplitude_callbacks.append(callback)

    def _notify_amplitude(self, source: str, amplitude: float) -> None:
        for cb in self._amplitude_callbacks:
            try:
                cb(source, amplitude)
            except Exception:
                pass
