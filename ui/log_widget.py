"""
EVA Log Widget — Cyberpunk terminal-style scrolling log.
Monospace font, neon color coding, HUD-style prefixes,
fade-in animation, and glow highlights.
"""

import time
import math

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QFrame,
)
from PyQt6.QtGui import QColor, QPainter, QPen, QFont, QLinearGradient
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve

from ui.styles import theme


class LogEntry(QLabel):
    """Single log entry with cyberpunk styling and source glow."""

    def __init__(self, text: str, source: str, color: QColor = None, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setFont(theme.font_hud(10))

        # Source prefix mapping
        prefix_map = {
            "user": "[USR]",
            "assistant": "[EVA]",
            "system": "[SYS]",
            "tool": "[MOD]",
            "error": "[ERR]",
        }
        icon_map = {
            "user": "▸",
            "assistant": "◈",
            "system": "●",
            "tool": "⚙",
            "error": "✖",
        }
        prefix = prefix_map.get(source, "[---]")
        icon = icon_map.get(source, "·")
        timestamp = time.strftime("%H:%M:%S")

        # Color mapping
        color_map = {
            "user": theme.neon_cyan,
            "assistant": theme.accent_bright,
            "system": theme.text_dim,
            "tool": theme.neon_yellow,
            "error": theme.error,
        }
        c = color or color_map.get(source, theme.text_secondary)

        self.setText(f"{timestamp} {prefix} {icon} {text}")

        # Glow border on left side based on source type
        glow_alpha = 100 if source in ("error", "user", "assistant") else 50
        self.setStyleSheet(f"""
            QLabel {{
                color: {c.name()};
                background: rgba({c.red()}, {c.green()}, {c.blue()}, 8);
                padding: 4px 10px;
                border-left: 3px solid rgba({c.red()}, {c.green()}, {c.blue()}, {glow_alpha});
                border-radius: 2px;
                margin: 1px 4px;
            }}
        """)
        self.setContentsMargins(0, 1, 0, 1)


class LogWidget(QWidget):
    """Scrolling cyberpunk terminal log with glow header."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_entries = 200
        self._pulse_phase = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QLabel("  ◈ ACTIVITY LOG")
        header.setFont(theme.font_hud(9))
        header.setFixedHeight(26)
        header.setStyleSheet(f"""
            QLabel {{
                color: {theme.accent_dim.name()};
                background-color: {theme.bg_secondary.name()};
                border-bottom: 1px solid {theme.border_color.name()};
                padding-left: 8px;
                letter-spacing: 2px;
            }}
        """)
        layout.addWidget(header)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: rgba(3, 2, 10, 220);
                border: 1px solid {theme.border_color.name()};
                border-radius: 6px;
            }}
        """)

        # Container for entries
        self._container = QWidget()
        self._entries_layout = QVBoxLayout(self._container)
        self._entries_layout.setContentsMargins(4, 6, 4, 6)
        self._entries_layout.setSpacing(2)
        self._entries_layout.addStretch()

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

        self._entry_count = 0

    def add_entry(self, text: str, source: str = "system",
                  color: QColor = None) -> None:
        """Add a log entry with auto-scroll."""
        entry = LogEntry(text, source, color, self._container)

        # Insert before the stretch
        self._entries_layout.insertWidget(
            self._entries_layout.count() - 1, entry
        )
        self._entry_count += 1

        # Trim old entries
        if self._entry_count > self._max_entries:
            item = self._entries_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
            self._entry_count -= 1

        # Auto-scroll to bottom
        QTimer.singleShot(50, self._scroll_to_bottom)

    def add_user_message(self, text: str) -> None:
        self.add_entry(text, "user")

    def add_system_message(self, text: str) -> None:
        self.add_entry(text, "system")

    def _scroll_to_bottom(self) -> None:
        scrollbar = self._scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def paintEvent(self, event) -> None:
        # Draw subtle scanline effect over the log
        painter = QPainter(self)
        for y in range(0, self.height(), 3):
            painter.fillRect(0, y, self.width(), 1, QColor(0, 0, 0, 6))
        painter.end()
        super().paintEvent(event)
