"""
EVA File Drop Zone — Drag-and-drop target with animated dashed border,
glow-on-hover, and neon pulse effect.
"""

import math
from pathlib import Path

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QDragEnterEvent, QDropEvent,
    QLinearGradient,
)
from PyQt6.QtCore import Qt, QRectF, QTimer, pyqtSignal

from ui.styles import theme


class FileDropZone(QWidget):
    """Drag-and-drop file target with animated neon border."""

    file_dropped = pyqtSignal(str)  # Emitted with the dropped file path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(75)
        self._hovering = False
        self._dash_offset = 0.0
        self._pulse_phase = 0.0

        # Animate the dashed border
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def _tick(self):
        self._dash_offset += 0.8
        self._pulse_phase += 0.1
        if self._hovering:
            self.update()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._hovering = True
            self.update()

    def dragLeaveEvent(self, event) -> None:
        self._hovering = False
        self.update()

    def dropEvent(self, event: QDropEvent) -> None:
        self._hovering = False
        urls = event.mimeData().urls()
        for url in urls:
            file_path = url.toLocalFile()
            if file_path and Path(file_path).exists():
                self.file_dropped.emit(file_path)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        rect = QRectF(6, 4, w - 12, h - 8)

        # Background with hover glow
        if self._hovering:
            pulse = 0.5 + 0.5 * math.sin(self._pulse_phase * 2)
            glow_alpha = int(15 + 15 * pulse)
            bg = QColor(theme.accent.red(), theme.accent.green(),
                       theme.accent.blue(), glow_alpha)
        else:
            bg = theme.bg_tertiary
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(rect, 10, 10)

        # Animated dashed border
        border_color = theme.accent if self._hovering else theme.border_color
        if self._hovering:
            alpha = int(150 + 105 * math.sin(self._pulse_phase * 2))
            border_color = QColor(theme.accent.red(), theme.accent.green(),
                                 theme.accent.blue(), alpha)

        pen = QPen(border_color, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(self._dash_offset)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 10, 10)

        # Icon and text
        text_color = theme.accent if self._hovering else theme.text_dim
        painter.setPen(text_color)

        painter.setFont(theme.font(size=18))
        icon_rect = QRectF(0, 6, w, 30)
        icon = "⬇" if self._hovering else "📁"
        painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, icon)

        painter.setFont(theme.font_hud(9))
        text = ("Release to process..." if self._hovering
                else "Drop files here to analyze")
        text_rect = QRectF(0, 38, w, 22)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.end()
