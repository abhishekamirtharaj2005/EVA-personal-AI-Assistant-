"""
EVA Metric Bar — Cyberpunk HUD-style system metrics.
Neon gradient bars with glow, HUD labels, warning pulse.
"""

import math

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QColor, QPen, QLinearGradient, QFont
from PyQt6.QtCore import Qt, QRectF, QTimer

from ui.styles import theme


class SingleMetric(QWidget):
    """A single cyberpunk metric bar with label and value."""

    def __init__(self, label: str, color: QColor, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self._label = label
        self._color = color
        self._value: float = 0.0
        self._target: float = 0.0
        self._warning = False
        self._pulse_phase: float = 0.0

    def set_value(self, value: float) -> None:
        self._target = max(0, min(100, value))
        self._warning = self._target > 85

    def _tick(self) -> None:
        self._value += (self._target - self._value) * 0.12
        self._pulse_phase += 0.15
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        bar_height = 6
        bar_y = h - bar_height - 4
        bar_width = w - 8
        fill_width = (self._value / 100.0) * bar_width

        # ── Label: "CPU // 43%" ──────────────────────────────
        painter.setFont(theme.font_hud(9))

        # Label
        painter.setPen(QPen(theme.text_dim, 1))
        painter.drawText(QRectF(4, 2, bar_width * 0.5, 20),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        f"{self._label}")

        # Value
        value_color = self._color if not self._warning else theme.error
        if self._warning:
            pulse = int(abs(math.sin(self._pulse_phase)) * 80)
            value_color = QColor(255, 40 + pulse, 80)

        painter.setPen(QPen(value_color, 1))
        painter.drawText(QRectF(bar_width * 0.5, 2, bar_width * 0.5, 20),
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        f"// {self._value:.0f}%")

        # ── Bar background ───────────────────────────────────
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(QRectF(4, bar_y, bar_width, bar_height),
                        QColor(theme.bg_input))

        # ── Bar fill with glow ───────────────────────────────
        if fill_width > 1:
            # Glow behind
            glow_color = QColor(self._color.red(), self._color.green(),
                               self._color.blue(), 40)
            painter.fillRect(QRectF(4, bar_y - 2, fill_width, bar_height + 4),
                           glow_color)

            # Main fill gradient
            grad = QLinearGradient(4, 0, 4 + fill_width, 0)
            grad.setColorAt(0.0, QColor(self._color.red(), self._color.green(),
                                        self._color.blue(), 200))
            grad.setColorAt(1.0, self._color)
            painter.fillRect(QRectF(4, bar_y, fill_width, bar_height), grad)

            # Bright tip
            tip_width = min(4, fill_width)
            painter.fillRect(
                QRectF(4 + fill_width - tip_width, bar_y, tip_width, bar_height),
                QColor(255, 255, 255, 180)
            )

        # ── Border line ──────────────────────────────────────
        pen = QPen(QColor(self._color.red(), self._color.green(),
                          self._color.blue(), 50))
        pen.setWidthF(0.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(4, bar_y, bar_width, bar_height))

        painter.end()


class MetricBar(QWidget):
    """Four-metric cyberpunk HUD panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(170)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Header
        header = QLabel("  ◈ SYSTEM STATUS")
        header.setFont(theme.font_hud(9))
        header.setFixedHeight(20)
        header.setStyleSheet(f"""
            color: {theme.accent_dim.name()};
            letter-spacing: 2px;
        """)
        layout.addWidget(header)

        # Create metrics
        self._cpu = SingleMetric("CPU", theme.cpu_color)
        self._ram = SingleMetric("RAM", theme.ram_color)
        self._gpu = SingleMetric("GPU", theme.gpu_color)
        self._temp = SingleMetric("TEMP", theme.temp_color)

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
        for m in [self._cpu, self._ram, self._gpu, self._temp]:
            m._tick()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        # Subtle border
        pen = QPen(theme.border_color, 1)
        painter.setPen(pen)
        painter.setBrush(QColor(theme.bg_secondary))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()
        super().paintEvent(event)
