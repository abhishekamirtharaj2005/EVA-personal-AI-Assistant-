"""
EVA File Drop Zone — Drag-and-drop target wired to file processing.
"""

from pathlib import Path

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QDragEnterEvent, QDropEvent
from PyQt6.QtCore import Qt, QRectF, pyqtSignal

from ui.styles import theme


class FileDropZone(QWidget):
    """Drag-and-drop file target that emits file paths for processing."""

    file_dropped = pyqtSignal(str)  # Emitted with the dropped file path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(80)
        self._hovering = False

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
        rect = QRectF(4, 4, w - 8, h - 8)

        # Background
        bg = theme.accent_bg if self._hovering else theme.bg_tertiary
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(rect, 12, 12)

        # Dashed border
        border_color = theme.accent if self._hovering else theme.border_color
        pen = QPen(border_color, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 12, 12)

        # Icon and text
        painter.setFont(theme.font(size=20))
        painter.setPen(theme.accent if self._hovering else theme.text_dim)
        icon_rect = QRectF(0, 8, w, 35)
        painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, "📁")

        painter.setFont(theme.font(size=9))
        text = "Drop files here to analyze" if not self._hovering else "Release to process..."
        text_rect = QRectF(0, 40, w, 25)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.end()
