"""
EVA HUD Canvas — Cyberpunk orb with hex grid, neon rings, scanlines,
energy field, orbiting particles, and reactive audio visualization.
"""

import math
import random
import time

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient,
    QLinearGradient, QPainterPath, QFont, QConicalGradient,
)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF

from ui.styles import theme


class HudCanvas(QWidget):
    """Cyberpunk-styled animated orb with hex grid, neon rings, particles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(280)

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
        self._status_text: str = "STANDBY"
        self._energy_phase: float = 0.0
        self._orbit_phase: float = 0.0
        self._breath_phase: float = 0.0
        self._data_streams: list = []
        self._glitch_active: bool = False
        self._glitch_end: float = 0.0
        self._state_transition: float = 1.0
        self._prev_state: str = "idle"

        # Animation timer (60 FPS)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        # Spawn particles
        for _ in range(30):
            self._particles.append(self._new_particle())

        # Spawn data streams (vertical lines that flow)
        for _ in range(8):
            self._data_streams.append(self._new_data_stream())

    def set_state(self, state: str) -> None:
        if state != self._state:
            self._prev_state = self._state
            self._state_transition = 0.0
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
        self._energy_phase += 0.05
        self._orbit_phase += 0.02
        self._breath_phase += 0.015

        # State transition smoothing
        if self._state_transition < 1.0:
            self._state_transition = min(1.0, self._state_transition + 0.04)

        # Random glitch effect
        now = time.time()
        if random.random() < 0.003 and not self._glitch_active:
            self._glitch_active = True
            self._glitch_end = now + random.uniform(0.05, 0.15)
        if self._glitch_active and now > self._glitch_end:
            self._glitch_active = False

        # Update particles
        for p in self._particles:
            p["y"] -= p["speed"]
            p["alpha"] -= 0.003
            p["x"] += math.sin(p["y"] * 0.02 + p["phase"]) * 0.3
            if p["alpha"] <= 0 or p["y"] < -20:
                p.update(self._new_particle())

        # Update data streams
        for ds in self._data_streams:
            ds["y"] += ds["speed"]
            if ds["y"] > self.height() + 20:
                ds.update(self._new_data_stream())

        self.update()

    def _new_particle(self) -> dict:
        w = max(self.width(), 200)
        h = max(self.height(), 200)
        return {
            "x": random.uniform(0, w),
            "y": random.uniform(h * 0.3, h),
            "speed": random.uniform(0.3, 1.5),
            "size": random.uniform(1, 4),
            "alpha": random.uniform(0.3, 0.9),
            "phase": random.uniform(0, math.pi * 2),
            "trail": random.random() > 0.6,  # Some particles have trails
        }

    def _new_data_stream(self) -> dict:
        w = max(self.width(), 200)
        return {
            "x": random.uniform(0, w),
            "y": random.uniform(-100, 0),
            "speed": random.uniform(1.0, 3.0),
            "length": random.randint(20, 80),
            "alpha": random.uniform(0.05, 0.15),
        }

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2 - 10

        # ── Background ──────────────────────────────────────
        painter.fillRect(self.rect(), theme.bg_primary)

        # ── Data streams (matrix-style) ─────────────────────
        self._draw_data_streams(painter, w, h)

        # ── Hex grid background ─────────────────────────────
        self._draw_hex_grid(painter, w, h)

        # ── Floating particles ──────────────────────────────
        for p in self._particles:
            alpha = int(p["alpha"] * 100)
            if alpha <= 0:
                continue
            color = QColor(theme.accent.red(), theme.accent.green(),
                          theme.accent.blue(), alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(p["x"], p["y"]),
                              p["size"], p["size"])

            # Particle trails
            if p.get("trail") and p["size"] > 2:
                trail_color = QColor(theme.accent.red(), theme.accent.green(),
                                    theme.accent.blue(), alpha // 3)
                painter.setBrush(QBrush(trail_color))
                for t in range(1, 4):
                    painter.drawEllipse(
                        QPointF(p["x"] - math.sin(p["y"] * 0.02 + p["phase"]) * 0.3 * t,
                                p["y"] + p["speed"] * t * 3),
                        p["size"] * (1 - t * 0.2), p["size"] * (1 - t * 0.2)
                    )

        # ── Outer energy field ─────────────────────────────
        orb_radius = min(w, h) * 0.25
        self._draw_energy_field(painter, cx, cy, orb_radius + 40)

        # ── Outer neon ring ─────────────────────────────────
        breath = math.sin(self._breath_phase) * 0.3 + 0.7
        ring_radius = orb_radius + 22 + math.sin(self._ring_pulse) * 5

        # Glow ring (doubled for depth)
        for glow_offset, glow_alpha in [(12, 15), (6, 30), (0, 50)]:
            ring_pen = QPen(QColor(theme.accent.red(), theme.accent.green(),
                                   theme.accent.blue(), glow_alpha))
            ring_pen.setWidthF(8 - glow_offset * 0.5)
            painter.setPen(ring_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy),
                              ring_radius + glow_offset, ring_radius + glow_offset)

        # Main ring
        ring_pen = QPen(QColor(theme.accent.red(), theme.accent.green(),
                                theme.accent.blue(), int(120 * breath)))
        ring_pen.setWidthF(1.5)
        painter.setPen(ring_pen)
        painter.drawEllipse(QPointF(cx, cy), ring_radius, ring_radius)

        # ── Orbiting dots ───────────────────────────────────
        self._draw_orbiting_dots(painter, cx, cy, ring_radius)

        # ── Waveform ring ───────────────────────────────────
        if self._amplitude > 0.01:
            self._draw_waveform_ring(painter, cx, cy, ring_radius - 8)

        # ── Core orb ────────────────────────────────────────
        orb_grad = theme.orb_gradient(cx, cy, orb_radius, self._state)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(orb_grad))
        painter.drawEllipse(QPointF(cx, cy), orb_radius, orb_radius)

        # Inner bright core with pulsing
        core_pulse = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(self._breath_phase * 2))
        core_radius = orb_radius * (0.25 + self._amplitude * 0.15)
        core_alpha = int((60 + self._amplitude * 100) * core_pulse)
        core_color = QColor(255, 255, 255, min(255, core_alpha))
        core_grad = QRadialGradient(cx, cy, core_radius)
        core_grad.setColorAt(0.0, core_color)
        core_grad.setColorAt(0.5, QColor(theme.accent_bright.red(),
                                          theme.accent_bright.green(),
                                          theme.accent_bright.blue(), 40))
        core_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QPointF(cx, cy), core_radius, core_radius)

        # ── Secondary inner ring ────────────────────────────
        inner_ring_r = orb_radius * 0.7
        inner_pen = QPen(QColor(theme.accent.red(), theme.accent.green(),
                                theme.accent.blue(), 35))
        inner_pen.setWidthF(0.8)
        painter.setPen(inner_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), inner_ring_r, inner_ring_r)

        # ── Glitch effect ───────────────────────────────────
        if self._glitch_active:
            self._draw_glitch(painter, w, h)

        # ── Status text with typing effect ──────────────────
        status_y = cy + ring_radius + 38
        painter.setFont(theme.font_hud(10))

        # Blinking cursor
        cursor = "█" if int(self._phase * 4) % 2 == 0 else " "
        status_str = f"// {self._status_text} {cursor}"

        # Text glow
        glow_pen = QPen(QColor(theme.accent.red(), theme.accent.green(),
                               theme.accent.blue(), 60))
        painter.setPen(glow_pen)
        painter.drawText(QRectF(1, status_y + 1, w, 20),
                        Qt.AlignmentFlag.AlignCenter, status_str)

        painter.setPen(QPen(theme.accent, 1))
        painter.drawText(QRectF(0, status_y, w, 20),
                        Qt.AlignmentFlag.AlignCenter, status_str)

        # ── Corner HUD decorations ──────────────────────────
        self._draw_hud_corners(painter, w, h)

        # ── Scanline overlay ────────────────────────────────
        self._draw_scanlines(painter, w, h)

        painter.end()

    def _draw_hex_grid(self, painter: QPainter, w: int, h: int) -> None:
        """Draw a subtle hex grid background with pulse."""
        hex_size = 30
        pulse = 8 + int(math.sin(self._hex_phase) * 5)
        color = QColor(theme.grid_color.red(), theme.grid_color.green(),
                       theme.grid_color.blue(), pulse)
        pen = QPen(color)
        pen.setWidthF(0.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for row in range(-1, int(h / (hex_size * 1.5)) + 2):
            for col in range(-1, int(w / (hex_size * 1.73)) + 2):
                x = col * hex_size * 1.73 + (row % 2) * hex_size * 0.866
                y = row * hex_size * 1.5

                # Proximity-based brightness near center
                dist = math.sqrt((x - w/2)**2 + (y - h/2)**2)
                if dist < 120:
                    bright_color = QColor(theme.accent.red(), theme.accent.green(),
                                         theme.accent.blue(),
                                         int((1 - dist/120) * 15))
                    painter.setPen(QPen(bright_color, 0.8))
                else:
                    painter.setPen(QPen(color, 0.5))

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

    def _draw_energy_field(self, painter: QPainter, cx: float, cy: float,
                           radius: float) -> None:
        """Draw rotating energy arcs around the orb."""
        segments = 3
        arc_length = 60  # degrees

        for i in range(segments):
            base_angle = (360 / segments) * i + self._energy_phase * 57.3
            alpha = int(25 + self._amplitude * 30)
            color = QColor(theme.accent.red(), theme.accent.green(),
                          theme.accent.blue(), alpha)
            pen = QPen(color)
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
            painter.drawArc(rect, int(base_angle * 16), int(arc_length * 16))

        # Counter-rotating arcs
        for i in range(2):
            base_angle = (180 * i) - self._energy_phase * 57.3 * 1.5
            alpha = int(15 + self._amplitude * 20)
            color = QColor(theme.accent_bright.red(), theme.accent_bright.green(),
                          theme.accent_bright.blue(), alpha)
            pen = QPen(color)
            pen.setWidthF(1.0)
            painter.setPen(pen)

            rect = QRectF(cx - radius - 10, cy - radius - 10,
                         (radius + 10) * 2, (radius + 10) * 2)
            painter.drawArc(rect, int(base_angle * 16), int(45 * 16))

    def _draw_orbiting_dots(self, painter: QPainter, cx: float, cy: float,
                            radius: float) -> None:
        """Draw small dots orbiting the ring."""
        num_dots = 5
        for i in range(num_dots):
            angle = self._orbit_phase + (2 * math.pi / num_dots) * i
            speed_mult = 1.0 + (i % 2) * 0.5
            r = radius + math.sin(self._phase * 2 + i) * 3
            x = cx + r * math.cos(angle * speed_mult)
            y = cy + r * math.sin(angle * speed_mult)

            # Dot with glow
            dot_size = 2.5 + math.sin(self._phase + i * 1.5) * 1
            glow = QRadialGradient(x, y, dot_size * 4)
            glow.setColorAt(0.0, QColor(theme.accent_bright.red(),
                                         theme.accent_bright.green(),
                                         theme.accent_bright.blue(), 120))
            glow.setColorAt(1.0, QColor(theme.accent.red(),
                                         theme.accent.green(),
                                         theme.accent.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(QPointF(x, y), dot_size * 4, dot_size * 4)

            # Core dot
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            painter.drawEllipse(QPointF(x, y), dot_size, dot_size)

    def _draw_data_streams(self, painter: QPainter, w: int, h: int) -> None:
        """Draw matrix-like data streams in the background."""
        for ds in self._data_streams:
            grad = QLinearGradient(ds["x"], ds["y"], ds["x"], ds["y"] + ds["length"])
            alpha = int(ds["alpha"] * 255)
            grad.setColorAt(0.0, QColor(theme.accent.red(), theme.accent.green(),
                                        theme.accent.blue(), 0))
            grad.setColorAt(0.5, QColor(theme.accent.red(), theme.accent.green(),
                                        theme.accent.blue(), alpha))
            grad.setColorAt(1.0, QColor(theme.accent.red(), theme.accent.green(),
                                        theme.accent.blue(), 0))
            painter.setPen(QPen(QBrush(grad), 1.0))
            painter.drawLine(QPointF(ds["x"], ds["y"]),
                           QPointF(ds["x"], ds["y"] + ds["length"]))

    def _draw_waveform_ring(self, painter: QPainter, cx: float, cy: float,
                            radius: float) -> None:
        """Draw audio waveform around the orb with glow."""
        segments = 72
        amp = self._amplitude

        # Outer glow
        glow_color = QColor(theme.accent_bright.red(), theme.accent_bright.green(),
                           theme.accent_bright.blue(), 40)
        glow_pen = QPen(glow_color)
        glow_pen.setWidthF(4.0)
        painter.setPen(glow_pen)

        path = QPainterPath()
        for i in range(segments + 1):
            angle = (i / segments) * math.pi * 2
            wave = math.sin(angle * 8 + self._phase * 3) * amp * 18
            wave += math.sin(angle * 12 + self._phase * 5) * amp * 10
            wave += math.sin(angle * 4 + self._phase * 1.5) * amp * 6
            r = radius + wave

            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)

            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)

        painter.drawPath(path)

        # Sharp line
        color = QColor(theme.accent_bright.red(), theme.accent_bright.green(),
                       theme.accent_bright.blue(), 180)
        pen = QPen(color)
        pen.setWidthF(1.5)
        painter.setPen(pen)
        painter.drawPath(path)

    def _draw_glitch(self, painter: QPainter, w: int, h: int) -> None:
        """Draw random glitch bars across the canvas."""
        for _ in range(random.randint(2, 5)):
            y = random.randint(0, h)
            bar_h = random.randint(1, 4)
            offset = random.randint(-8, 8)
            color = QColor(theme.accent_bright.red(), theme.accent_bright.green(),
                          theme.accent_bright.blue(), random.randint(30, 80))
            painter.fillRect(QRectF(offset, y, w, bar_h), color)

    def _draw_hud_corners(self, painter: QPainter, w: int, h: int) -> None:
        """Draw cyberpunk corner brackets with animation."""
        corner_len = 30
        pulse = 0.6 + 0.4 * math.sin(self._breath_phase)
        pen = QPen(QColor(theme.accent_dim.red(), theme.accent_dim.green(),
                          theme.accent_dim.blue(), int(255 * pulse)), 1.5)
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

        # Corner accent dots
        dot_color = QColor(theme.accent.red(), theme.accent.green(),
                          theme.accent.blue(), int(180 * pulse))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(dot_color))
        dot_size = 2
        for dx, dy in [(margin, margin), (w - margin, margin),
                       (margin, h - margin), (w - margin, h - margin)]:
            painter.drawEllipse(QPointF(dx, dy), dot_size, dot_size)

    def _draw_scanlines(self, painter: QPainter, w: int, h: int) -> None:
        """Subtle CRT scanline overlay."""
        color = QColor(0, 0, 0, theme.scanline_alpha)
        offset = int(self._scanline_offset)
        for y in range(offset, h, 4):
            painter.fillRect(0, y, w, 1, color)
