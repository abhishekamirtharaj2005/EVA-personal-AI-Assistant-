"""
EVA Camera Preview — Live webcam thumbnail that activates during vision calls.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QImage, QColor, QPen
from PyQt6.QtCore import Qt, QTimer, QRectF

from ui.styles import theme


class CameraPreview(QWidget):
    """Live webcam preview widget, only active during vision calls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 120)
        self._active = False
        self._frame: bytes = b""
        self._image = None
        self.setVisible(False)

    def activate(self) -> None:
        """Show the preview and start capturing."""
        self._active = True
        self.setVisible(True)
        self._start_capture()

    def deactivate(self) -> None:
        """Hide the preview."""
        self._active = False
        self.setVisible(False)
        self._image = None

    def set_frame(self, frame_bytes: bytes) -> None:
        """Update the preview with a new JPEG frame."""
        try:
            self._image = QImage()
            self._image.loadFromData(frame_bytes, "JPEG")
            self.update()
        except Exception:
            pass

    def _start_capture(self) -> None:
        """Start periodic webcam capture."""
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    _, buf = cv2.imencode(".jpg", frame,
                                           [cv2.IMWRITE_JPEG_QUALITY, 50])
                    self.set_frame(buf.tobytes())
                cap.release()
        except Exception:
            pass

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        rect = QRectF(0, 0, w, h)

        # Border
        painter.setPen(QPen(theme.accent, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)

        if self._image and not self._image.isNull():
            # Scale and draw the image
            scaled = self._image.scaled(
                w - 4, h - 4,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            x = (w - scaled.width()) // 2
            y = (h - scaled.height()) // 2
            painter.drawImage(x, y, scaled)
        else:
            # Placeholder
            painter.fillRect(rect.adjusted(2, 2, -2, -2), theme.bg_tertiary)
            painter.setPen(theme.text_dim)
            painter.setFont(theme.font(size=9))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "📷 Camera")

        # "LIVE" indicator
        if self._active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 50, 50))
            painter.drawEllipse(w - 16, 6, 8, 8)
            painter.setFont(theme.font(size=7, bold=True))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(w - 38, 14, "LIVE")

        painter.end()
