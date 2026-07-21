"""
EVA HUD Canvas — Cyberpunk orb with hex grid, neon rings, scanlines.
"""

import math
import random
import time

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient,
    QLinearGradient, QPainterPath, QFont,
)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF

from ui.styles import theme


class HudCanvas(QWidget):
    """Cyberpunk-styled animated orb with hex grid, neon rings, particles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(250)

        # State
        self._state: str = "idle"
        self._amplitude: float = 0.0
        self._target_amplitude: float = 0.0
        self._phase: float = 0.0
        self._particles: list = []
        self._scanline_offset: float = 0.0
        self._glitch_timer: float = 0.0
        self._ring_pulse: float = 0.0
        self._hex_phase: float = 0.0
        self._status_text: str = "IDLE"

        # Animation timer (60 FPS)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        # Spawn particles
        for _ in range(20):
            self._particles.append(self._new_particle())

    def set_state(self, state: str) -> None:
        self._state = state
        state_labels = {
            "idle": "STANDBY",
            "listening": "LISTENING",
            "speaking": "SPEAKING",
            "thinking": "PROCESSING",
        }
        self._status_text = state_labels.get(state, state.upper())

    def set_amplitude(self, amplitude: float) -> None:
        self._target_amplitude = min(1.0, amplitude * 3.0)

    def _tick(self) -> None:
        self._phase += 0.04
        self._amplitude += (self._target_amplitude - self._amplitude) * 0.15
        self._target_amplitude *= 0.95
        self._scanline_offset = (self._scanline_offset + 0.5) % 4.0
        self._ring_pulse += 0.03
        self._hex_phase += 0.01

        # Update particles
        for p in self._particles:
            p["y"] -= p["speed"]
            p["alpha"] -= 0.003
            p["x"] += math.sin(p["y"] * 0.02 + p["phase"]) * 0.3
            if p["alpha"] <= 0 or p["y"] < -20:
                p.update(self._new_particle())

        self.update()

    def _new_particle(self) -> dict:
        w = max(self.width(), 200)
        h = max(self.height(), 200)
        return {
            "x": random.uniform(0, w),
            "y": random.uniform(h * 0.3, h),
            "speed": random.uniform(0.3, 1.2),
            "size": random.uniform(1, 3),
            "alpha": random.uniform(0.3, 0.8),
            "phase": random.uniform(0, math.pi * 2),
        }

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        # ── Background ──────────────────────────────────────
        painter.fillRect(self.rect(), theme.bg_primary)

        # ── Hex grid background ─────────────────────────────
        self._draw_hex_grid(painter, w, h)

        # ── Floating particles ──────────────────────────────
        for p in self._particles:
            alpha = int(p["alpha"] * 80)
            if alpha <= 0:
                continue
            color = QColor(theme.accent.red(), theme.accent.green(),
                          theme.accent.blue(), alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(p["x"], p["y"]),
                              p["size"], p["size"])

        # ── Outer neon ring ─────────────────────────────────
        orb_radius = min(w, h) * 0.25
        ring_radius = orb_radius + 20 + math.sin(self._ring_pulse) * 5

        # Glow ring
        ring_pen = QPen(QColor(theme.accent.red(), theme.accent.green(),
                               theme.accent.blue(), 40))
        ring_pen.setWidthF(8)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), ring_radius + 6, ring_radius + 6)

        # Main ring
        ring_pen.setColor(QColor(theme.accent.red(), theme.accent.green(),
                                  theme.accent.blue(), 120))
        ring_pen.setWidthF(1.5)
        painter.setPen(ring_pen)
        painter.drawEllipse(QPointF(cx, cy), ring_radius, ring_radius)

        # ── Waveform ring ───────────────────────────────────
        if self._amplitude > 0.01:
            self._draw_waveform_ring(painter, cx, cy, ring_radius - 8)

        # ── Core orb ────────────────────────────────────────
        orb_grad = theme.orb_gradient(cx, cy, orb_radius, self._state)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(orb_grad))
        painter.drawEllipse(QPointF(cx, cy), orb_radius, orb_radius)

        # Inner bright core
        core_radius = orb_radius * 0.3
        core_color = QColor(255, 255, 255, 60 + int(self._amplitude * 80))
        core_grad = QRadialGradient(cx, cy, core_radius)
        core_grad.setColorAt(0.0, core_color)
        core_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QPointF(cx, cy), core_radius, core_radius)

        # ── Status text ─────────────────────────────────────
        status_y = cy + ring_radius + 35
        painter.setFont(theme.font_hud(10))
        painter.setPen(QPen(theme.accent, 1))
        painter.drawText(QRectF(0, status_y, w, 20),
                        Qt.AlignmentFlag.AlignCenter, f"// {self._status_text}")

        # ── Corner HUD decorations ──────────────────────────
        self._draw_hud_corners(painter, w, h)

        # ── Scanline overlay ────────────────────────────────
        self._draw_scanlines(painter, w, h)

        painter.end()

    def _draw_hex_grid(self, painter: QPainter, w: int, h: int) -> None:
        """Draw a subtle hex grid background."""
        hex_size = 30
        color = QColor(theme.grid_color.red(), theme.grid_color.green(),
                       theme.grid_color.blue(),
                       20 + int(math.sin(self._hex_phase) * 8))
        pen = QPen(color)
        pen.setWidthF(0.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for row in range(-1, int(h / (hex_size * 1.5)) + 2):
            for col in range(-1, int(w / (hex_size * 1.73)) + 2):
                x = col * hex_size * 1.73 + (row % 2) * hex_size * 0.866
                y = row * hex_size * 1.5
                self._draw_hexagon(painter, x, y, hex_size * 0.9)

    def _draw_hexagon(self, painter: QPainter, cx: float, cy: float,
                      size: float) -> None:
        path = QPainterPath()
        for i in range(6):
            angle = math.pi / 3 * i - math.pi / 6
            px = cx + size * math.cos(angle)
            py = cy + size * math.sin(angle)
            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)
        path.closeSubpath()
        painter.drawPath(path)

    def _draw_waveform_ring(self, painter: QPainter, cx: float, cy: float,
                            radius: float) -> None:
        """Draw audio waveform around the orb."""
        segments = 72
        amp = self._amplitude

        color = QColor(theme.accent_bright.red(), theme.accent_bright.green(),
                       theme.accent_bright.blue(), 160)
        pen = QPen(color)
        pen.setWidthF(1.5)
        painter.setPen(pen)

        path = QPainterPath()
        for i in range(segments + 1):
            angle = (i / segments) * math.pi * 2
            wave = math.sin(angle * 8 + self._phase * 3) * amp * 15
            wave += math.sin(angle * 12 + self._phase * 5) * amp * 8
            r = radius + wave

            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)

            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)

        painter.drawPath(path)

    def _draw_hud_corners(self, painter: QPainter, w: int, h: int) -> None:
        """Draw cyberpunk corner brackets."""
        corner_len = 25
        pen = QPen(theme.accent_dim, 1)
        painter.setPen(pen)
        margin = 8

        # Top-left
        painter.drawLine(margin, margin, margin + corner_len, margin)
        painter.drawLine(margin, margin, margin, margin + corner_len)
        # Top-right
        painter.drawLine(w - margin, margin, w - margin - corner_len, margin)
        painter.drawLine(w - margin, margin, w - margin, margin + corner_len)
        # Bottom-left
        painter.drawLine(margin, h - margin, margin + corner_len, h - margin)
        painter.drawLine(margin, h - margin, margin, h - margin - corner_len)
        # Bottom-right
        painter.drawLine(w - margin, h - margin, w - margin - corner_len, h - margin)
        painter.drawLine(w - margin, h - margin, w - margin, h - margin - corner_len)

    def _draw_scanlines(self, painter: QPainter, w: int, h: int) -> None:
        """Subtle CRT scanline overlay."""
        color = QColor(0, 0, 0, theme.scanline_alpha)
        offset = int(self._scanline_offset)
        for y in range(offset, h, 4):
            painter.fillRect(0, y, w, 1, color)
