"""
EVA Remote Key Overlay — QR pairing display for the remote dashboard.
"""

import io

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtGui import QPainter, QColor, QPixmap, QImage
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from ui.styles import theme


class RemoteKeyOverlay(QWidget):
    """QR code pairing display with manual URL/key fallback."""

    pairing_started = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._pairing_key = ""
        self._connect_url = ""
        self._qr_pixmap = None
        self._connected = False

        self._build_ui()

        # Poll connection state
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._check_connection)
        self._poll_timer.start(2000)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title
        title = QLabel("📱 Remote Connect")
        title.setFont(theme.font(size=18, bold=True))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {theme.text_primary.name()};")
        layout.addWidget(title)

        subtitle = QLabel("Scan the QR code with your phone to connect")
        subtitle.setFont(theme.font(size=10))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"color: {theme.text_secondary.name()};")
        layout.addWidget(subtitle)

        layout.addSpacing(10)

        # QR code display
        self.qr_label = QLabel()
        self.qr_label.setFixedSize(200, 200)
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setStyleSheet(
            f"background-color: white; border-radius: 12px; padding: 10px;"
        )
        layout.addWidget(self.qr_label, 0, Qt.AlignmentFlag.AlignCenter)

        # Manual fallback
        self.url_label = QLabel("")
        self.url_label.setFont(theme.font(size=9, mono=True))
        self.url_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.url_label.setStyleSheet(f"color: {theme.accent.name()};")
        self.url_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.url_label)

        self.key_label = QLabel("")
        self.key_label.setFont(theme.font(size=14, bold=True, mono=True))
        self.key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.key_label.setStyleSheet(f"color: {theme.accent_bright.name()};")
        self.key_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.key_label)

        # Status
        self.status_label = QLabel("Waiting for connection...")
        self.status_label.setFont(theme.font(size=10))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"color: {theme.text_dim.name()};")
        layout.addWidget(self.status_label)

        layout.addSpacing(10)

        # New key / Close buttons
        btn_style = f"""
            QPushButton {{
                background-color: {theme.bg_tertiary.name()};
                color: {theme.text_primary.name()};
                border: 1px solid {theme.border_color.name()};
                border-radius: 8px; padding: 8px 16px; font-size: 11px;
            }}
            QPushButton:hover {{
                border-color: {theme.accent.name()};
            }}
        """

        self.new_key_btn = QPushButton("🔄 New Key")
        self.new_key_btn.setStyleSheet(btn_style)
        self.new_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_key_btn.clicked.connect(self._generate_new_key)
        layout.addWidget(self.new_key_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet(btn_style)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.hide)
        layout.addWidget(self.close_btn)

    def show_pairing(self, key: str, url: str) -> None:
        """Display pairing info with QR code."""
        self._pairing_key = key
        self._connect_url = url
        self._connected = False

        # Generate QR code
        try:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=5, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")  # type: ignore[arg-type]
            buffer.seek(0)

            qimage = QImage()
            qimage.loadFromData(buffer.read())
            self._qr_pixmap = QPixmap.fromImage(qimage)
            self.qr_label.setPixmap(
                self._qr_pixmap.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio)
            )
        except ImportError:
            self.qr_label.setText("QR generation\nnot available")

        self.url_label.setText(url)
        self.key_label.setText(f"Key: {key}")
        self.status_label.setText("Waiting for connection...")
        self.status_label.setStyleSheet(f"color: {theme.text_dim.name()};")
        self.show()

    def set_connected(self) -> None:
        """Update UI to show connected state."""
        self._connected = True
        self.status_label.setText("✅ Device connected!")
        self.status_label.setStyleSheet(f"color: {theme.success.name()};")

    def _generate_new_key(self) -> None:
        """Request a new pairing key from the dashboard server."""
        self.pairing_started.emit()

    def _check_connection(self) -> None:
        """Periodically check if a device has connected."""
        pass  # Will be connected to the dashboard server

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(10, 10, 18, 235))
        painter.end()
