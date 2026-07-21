"""
EVA Clipboard Panel — Clipboard-change triggered quick-action panel.
Fires on copies ≥10 chars, shows 4 action buttons, auto-dismiss timer.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QApplication, QGraphicsOpacityEffect,
)
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve

from ui.styles import theme


class ClipboardPanel(QWidget):
    """Floating action bar triggered by clipboard changes ≥N chars."""

    action_triggered = pyqtSignal(str, str)  # (action_type, clipboard_text)

    def __init__(self, parent=None, min_chars: int = 10):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 65)

        self._min_chars = min_chars
        self._clipboard_text = ""
        self._auto_dismiss_timer = QTimer(self)
        self._auto_dismiss_timer.setSingleShot(True)
        self._auto_dismiss_timer.timeout.connect(self._dismiss)
        self._dismiss_seconds = 8

        self._build_ui()
        self._setup_clipboard_monitor()
        self.hide()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Label
        self._label = QLabel("📋 Clipboard detected:")
        self._label.setFont(theme.font(size=9))
        self._label.setStyleSheet(f"color: {theme.text_secondary.name()};")
        layout.addWidget(self._label)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        actions = [
            ("Summarize", "summarize", "📝"),
            ("Explain", "explain", "💡"),
            ("Translate", "translate", "🌐"),
            ("Analyze", "analyze", "🔍"),
        ]

        btn_style = f"""
            QPushButton {{
                background-color: {theme.bg_tertiary.name()};
                color: {theme.text_primary.name()};
                border: 1px solid {theme.border_color.name()};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: {theme.accent_bg.name()};
                border-color: {theme.accent.name()};
            }}
        """

        for label, action_type, icon in actions:
            btn = QPushButton(f"{icon} {label}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda checked, a=action_type: self._on_action(a))
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)

    def _setup_clipboard_monitor(self) -> None:
        """Monitor the system clipboard for changes."""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.dataChanged.connect(self._on_clipboard_change)

    def _on_clipboard_change(self) -> None:
        """Handle clipboard content changes."""
        clipboard = QApplication.clipboard()
        if not clipboard:
            return

        text = clipboard.text()
        if text and len(text) >= self._min_chars:
            self._clipboard_text = text
            preview = text[:50] + "..." if len(text) > 50 else text
            self._label.setText(f"📋 Copied: {preview}")
            self._show_panel()

    def _show_panel(self) -> None:
        """Show the panel and start auto-dismiss timer."""
        # Position at bottom-center of parent
        if self.parent():
            parent = self.parent()
            x = (parent.width() - self.width()) // 2
            y = parent.height() - self.height() - 20
            self.move(x, y)

        self.show()
        self.raise_()
        self._auto_dismiss_timer.start(self._dismiss_seconds * 1000)

    def _dismiss(self) -> None:
        """Hide the panel."""
        self.hide()

    def _on_action(self, action_type: str) -> None:
        """Handle an action button click."""
        self.action_triggered.emit(action_type, self._clipboard_text)
        self._dismiss()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(18, 18, 30, 220))
        painter.drawRoundedRect(self.rect(), 12, 12)
        painter.end()
