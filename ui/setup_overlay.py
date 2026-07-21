"""
EVA Setup Overlay — Cyberpunk first-run wizard.
Collects API keys and preferences with neon styling.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame,
)
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, pyqtSignal

from ui.styles import theme


class SetupOverlay(QWidget):
    """Cyberpunk-styled first-run setup overlay."""

    setup_complete = pyqtSignal(str, str, str)  # api_key, user_name, assistant_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()

    def _neon_input(self, placeholder: str, password: bool = False) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        if password:
            field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setFixedHeight(42)
        field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.bg_input.name()};
                color: {theme.accent_bright.name()};
                border: 1px solid {theme.border_color.name()};
                border-radius: 4px;
                padding: 8px 14px;
                font-family: "{theme.font_mono}";
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {theme.accent.name()};
                background-color: {QColor(15, 12, 38).name()};
            }}
        """)
        return field

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(f"◈ {text}")
        label.setFont(theme.font_hud(9))
        label.setStyleSheet(f"""
            color: {theme.accent_dim.name()};
            letter-spacing: 2px;
        """)
        return label

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 50, 40, 40)
        layout.setSpacing(12)

        # ── Title ───────────────────────────────────────────
        title = QLabel("E V A")
        title.setFont(theme.font_title())
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            color: {theme.accent.name()};
            letter-spacing: 8px;
        """)
        layout.addWidget(title)

        subtitle = QLabel("// ENHANCED VIRTUAL ASSISTANT //")
        subtitle.setFont(theme.font_hud(10))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"color: {theme.text_dim.name()};")
        layout.addWidget(subtitle)

        # Neon separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {theme.accent_dim.name()};")
        layout.addWidget(sep)
        layout.addSpacing(16)

        # ── Gemini API Key ──────────────────────────────────
        layout.addWidget(self._section_label("GEMINI API KEY (REQUIRED)"))
        self.api_key_input = self._neon_input(
            "Enter your Gemini API key...", password=True
        )
        layout.addWidget(self.api_key_input)

        # ── OpenAI Key (optional) ───────────────────────────
        layout.addSpacing(4)
        layout.addWidget(self._section_label("OPENAI API KEY (OPTIONAL)"))
        self.openai_key_input = self._neon_input(
            "OpenAI key for fallback...", password=True
        )
        layout.addWidget(self.openai_key_input)

        # ── Anthropic Key (optional) ────────────────────────
        layout.addSpacing(4)
        layout.addWidget(self._section_label("ANTHROPIC API KEY (OPTIONAL)"))
        self.anthropic_key_input = self._neon_input(
            "Anthropic key for fallback...", password=True
        )
        layout.addWidget(self.anthropic_key_input)

        layout.addSpacing(8)

        # ── User name ──────────────────────────────────────
        layout.addWidget(self._section_label("YOUR NAME"))
        self.user_name_input = self._neon_input("What should I call you?")
        layout.addWidget(self.user_name_input)

        # ── Assistant name ──────────────────────────────────
        layout.addWidget(self._section_label("ASSISTANT NAME"))
        self.assistant_name_input = self._neon_input("Default: EVA")
        layout.addWidget(self.assistant_name_input)

        layout.addSpacing(12)

        # ── Error label ─────────────────────────────────────
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setFont(theme.font_hud(10))
        self.error_label.setStyleSheet(f"color: {theme.error.name()};")
        layout.addWidget(self.error_label)

        # ── Start button ────────────────────────────────────
        self.start_btn = QPushButton("▶ INITIALIZE")
        self.start_btn.setFixedHeight(48)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {theme.neon_cyan.name()};
                border: 2px solid {theme.neon_cyan.name()};
                border-radius: 4px;
                font-family: "{theme.font_mono}";
                font-size: 14px;
                font-weight: bold;
                letter-spacing: 4px;
            }}
            QPushButton:hover {{
                background-color: rgba(0, 255, 213, 20);
                color: white;
            }}
            QPushButton:pressed {{
                background-color: rgba(0, 255, 213, 40);
            }}
        """)
        self.start_btn.clicked.connect(self._on_submit)
        layout.addWidget(self.start_btn)

        layout.addStretch()

    def _on_submit(self) -> None:
        api_key = self.api_key_input.text().strip()
        if not api_key:
            self.error_label.setText("[ERR] Gemini API key is required")
            return

        if len(api_key) < 10:
            self.error_label.setText("[ERR] Invalid API key format")
            return

        # Save optional keys
        from memory.config_manager import config
        openai_key = self.openai_key_input.text().strip()
        anthropic_key = self.anthropic_key_input.text().strip()
        if openai_key:
            config.set("openai_api_key", openai_key)
        if anthropic_key:
            config.set("anthropic_api_key", anthropic_key)

        user_name = self.user_name_input.text().strip() or "User"
        assistant_name = self.assistant_name_input.text().strip() or "EVA"

        self.setup_complete.emit(api_key, user_name, assistant_name)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        # Dark overlay
        painter.fillRect(self.rect(), QColor(2, 0, 12, 245))
        # Neon border frame
        pen = QPen(theme.accent_dim, 1)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(30, 40, -31, -31))
        painter.end()
