"""
EVA Metric Bar — Cyberpunk HUD-style system metrics.
Neon gradient bars with animated glow, HUD labels, warning pulse,
segmented fill, and glitch highlights.
"""

import math
import random

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QColor, QPen, QLinearGradient, QFont, QBrush
from PyQt6.QtCore import Qt, QRectF, QTimer, QPointF

from ui.styles import theme


class SingleMetric(QWidget):
    """A single cyberpunk metric bar with animated glow and segmentation."""

    def __init__(self, label: str, color: QColor, icon: str = "▪", parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self._label = label
        self._icon = icon
        self._color = color
        self._value: float = 0.0
        self._target: float = 0.0
        self._warning = False
        self._pulse_phase: float = random.uniform(0, math.pi * 2)
        self._glow_intensity: float = 0.0

    def set_value(self, value: float) -> None:
        self._target = max(0, min(100, value))
        self._warning = self._target > 85

    def _tick(self) -> None:
        self._value += (self._target - self._value) * 0.10
        self._pulse_phase += 0.12
        self._glow_intensity = 0.5 + 0.5 * math.sin(self._pulse_phase * 0.7)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        bar_height = 8
        bar_y = h - bar_height - 4
        bar_x = 8
        bar_width = w - 16
        fill_width = (self._value / 100.0) * bar_width

        # ── Label: "CPU // 43%" ──────────────────────────────
        painter.setFont(theme.font_hud(9))

        # Label with icon
        painter.setPen(QPen(self._color, 1))
        painter.drawText(QRectF(bar_x, 2, bar_width * 0.5, 20),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        f"{self._label}")

        # Value with glow
        value_color = self._color if not self._warning else theme.error
        if self._warning:
            pulse = int(abs(math.sin(self._pulse_phase)) * 100)
            value_color = QColor(255, 40 + pulse, 80)

        painter.setPen(QPen(value_color, 1))
        painter.drawText(QRectF(bar_width * 0.5, 2, bar_width * 0.5 + 8, 20),
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        f"// {self._value:.0f}%")

        # ── Bar background with subtle gradient ──────────────
        bg_grad = QLinearGradient(bar_x, 0, bar_x + bar_width, 0)
        bg_grad.setColorAt(0.0, QColor(theme.bg_input))
        bg_grad.setColorAt(1.0, QColor(theme.bg_input.red() + 5,
                                        theme.bg_input.green() + 5,
                                        theme.bg_input.blue() + 8))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(QRectF(bar_x, bar_y, bar_width, bar_height), bg_grad)

        # ── Bar fill with glow layers ────────────────────────
        if fill_width > 1:
            # Deep glow
            glow_alpha = int(20 * self._glow_intensity)
            glow_color = QColor(self._color.red(), self._color.green(),
                               self._color.blue(), glow_alpha)
            painter.fillRect(QRectF(bar_x, bar_y - 4, fill_width, bar_height + 8),
                           glow_color)

            # Main fill gradient
            grad = QLinearGradient(bar_x, 0, bar_x + fill_width, 0)
            grad.setColorAt(0.0, QColor(self._color.red(), self._color.green(),
                                        self._color.blue(), 160))
            grad.setColorAt(0.7, self._color)
            grad.setColorAt(1.0, QColor(min(255, self._color.red() + 40),
                                         min(255, self._color.green() + 40),
                                         min(255, self._color.blue() + 40)))
            painter.fillRect(QRectF(bar_x, bar_y, fill_width, bar_height), grad)

            # Segment markers
            segment_width = bar_width / 20
            seg_pen = QPen(QColor(0, 0, 0, 40))
            seg_pen.setWidthF(1)
            painter.setPen(seg_pen)
            for s in range(1, 20):
                sx = bar_x + s * segment_width
                if sx < bar_x + fill_width:
                    painter.drawLine(QPointF(sx, bar_y),
                                   QPointF(sx, bar_y + bar_height))

            # Bright tip with pulse
            tip_width = min(6, fill_width)
            tip_alpha = int(180 + 75 * math.sin(self._pulse_phase * 2))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.fillRect(
                QRectF(bar_x + fill_width - tip_width, bar_y,
                       tip_width, bar_height),
                QColor(255, 255, 255, min(255, tip_alpha))
            )

            # Animated shimmer (a bright spot that moves)
            shimmer_x = bar_x + (self._pulse_phase * 30) % fill_width
            shimmer_grad = QLinearGradient(shimmer_x - 15, 0, shimmer_x + 15, 0)
            shimmer_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
            shimmer_grad.setColorAt(0.5, QColor(255, 255, 255, 25))
            shimmer_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.fillRect(QRectF(bar_x, bar_y, fill_width, bar_height),
                           shimmer_grad)

        # ── Border line ──────────────────────────────────────
        pen = QPen(QColor(self._color.red(), self._color.green(),
                          self._color.blue(), 40))
        pen.setWidthF(0.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(bar_x, bar_y, bar_width, bar_height), 2, 2)

        painter.end()


class MetricBar(QWidget):
    """Four-metric cyberpunk HUD panel with animated borders."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(180)
        self._pulse_phase: float = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Header
        header = QLabel("  ◈ SYSTEM STATUS")
        header.setFont(theme.font_hud(9))
        header.setFixedHeight(22)
        header.setStyleSheet(f"""
            color: {theme.accent_dim.name()};
            letter-spacing: 2px;
        """)
        layout.addWidget(header)

        # Create metrics
        self._cpu = SingleMetric("CPU", theme.cpu_color, "◆")
        self._ram = SingleMetric("RAM", theme.ram_color, "◆")
        self._gpu = SingleMetric("GPU", theme.gpu_color, "◆")
        self._temp = SingleMetric("TEMP", theme.temp_color, "◆")

        for m in [self._cpu, self._ram, self._gpu, self._temp]:
            layout.addWidget(m)

        # Animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # ~30 FPS

    def update_metrics(self, cpu: float, ram: float,
                       gpu: float, temp: float) -> None:
        self._cpu.set_value(cpu)
        self._ram.set_value(ram)
        self._gpu.set_value(gpu)
        self._temp.set_value(temp)

    def _tick(self) -> None:
        self._pulse_phase += 0.05
        for m in [self._cpu, self._ram, self._gpu, self._temp]:
            m._tick()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(0, 0, -1, -1)

        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.bg_secondary))
        painter.drawRoundedRect(rect, 4, 4)

        # Animated border glow
        pulse = 0.5 + 0.5 * math.sin(self._pulse_phase)
        border_alpha = int(30 + 20 * pulse)
        pen = QPen(QColor(theme.accent.red(), theme.accent.green(),
                          theme.accent.blue(), border_alpha))
        pen.setWidthF(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 4, 4)

        painter.end()
        super().paintEvent(event)
