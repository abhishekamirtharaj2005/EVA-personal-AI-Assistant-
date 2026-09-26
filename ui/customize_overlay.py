"""
EVA Settings Panel — Tabbed cyberpunk settings overlay.
Tabs: API Keys, Voice & Model, Appearance, System.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSlider, QTabWidget, QComboBox, QCheckBox,
    QSpacerItem, QSizePolicy, QFrame,
)
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, pyqtSignal

from ui.styles import theme
from memory.config_manager import config


class SettingsPanel(QWidget):
    """Full cyberpunk settings panel with tabbed sections."""

    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("⚙ SETTINGS")
        title.setFont(theme.font_title())
        title.setStyleSheet(f"""
            color: {theme.accent.name()};
            letter-spacing: 4px;
        """)
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {theme.text_dim.name()}; font-size: 16px;
            }}
            QPushButton:hover {{ color: {theme.error.name()}; }}
        """)
        close_btn.clicked.connect(self._save_and_close)
        header.addWidget(close_btn)
        root.addLayout(header)
        root.addSpacing(10)

        # ── Neon separator ──────────────────────────────────
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {theme.accent_dim.name()};")
        root.addWidget(sep)
        root.addSpacing(10)

        # ── Tab widget ──────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_api_tab(), "API KEYS")
        self._tabs.addTab(self._build_voice_tab(), "VOICE & MODEL")
        self._tabs.addTab(self._build_appearance_tab(), "APPEARANCE")
        self._tabs.addTab(self._build_integrations_tab(), "INTEGRATIONS")
        self._tabs.addTab(self._build_system_tab(), "SYSTEM")
        root.addWidget(self._tabs)

        root.addSpacing(10)

        # ── Bottom buttons ──────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        reset_btn = QPushButton("RESET DEFAULTS")
        reset_btn.setStyleSheet(theme.neon_button_style(theme.warning))
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)

        save_btn = QPushButton("SAVE & CLOSE")
        save_btn.setStyleSheet(theme.neon_button_style(theme.neon_cyan))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(save_btn)

        root.addLayout(btn_row)

    # ── Tab Builders ────────────────────────────────────────────

    def _build_api_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(self._section_label("GEMINI (PRIMARY)"))
        self._gemini_key = self._api_key_field("Gemini API Key")
        layout.addWidget(self._gemini_key)

        layout.addSpacing(8)
        layout.addWidget(self._section_label("OPENAI"))
        self._openai_key = self._api_key_field("OpenAI API Key")
        layout.addWidget(self._openai_key)

        layout.addSpacing(8)
        layout.addWidget(self._section_label("ANTHROPIC"))
        self._anthropic_key = self._api_key_field("Anthropic API Key")
        layout.addWidget(self._anthropic_key)

        # ── Ollama (Local LLM) ──────────────────────────────
        layout.addSpacing(16)
        layout.addWidget(self._section_label("OLLAMA (LOCAL LLM)"))

        self._ollama_check = QCheckBox("Enable Ollama fallback")
        self._ollama_check.setFont(theme.font_hud(10))
        self._ollama_check.setStyleSheet(f"color: {theme.text_primary.name()};")
        layout.addWidget(self._ollama_check)

        self._ollama_url = QLineEdit()
        self._ollama_url.setPlaceholderText("http://localhost:11434")
        self._ollama_url.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,0.05);
                border: 1px solid {theme.accent_dim.name()};
                color: {theme.text_primary.name()};
                padding: 6px 10px;
                font-family: \"{theme.font_mono}\";
                font-size: 11px;
            }}
        """)
        self._ollama_url.setFixedHeight(36)
        layout.addWidget(self._ollama_url)

        self._ollama_model = QLineEdit()
        self._ollama_model.setPlaceholderText("Model name (blank = auto-detect)")
        self._ollama_model.setStyleSheet(self._ollama_url.styleSheet())
        self._ollama_model.setFixedHeight(36)
        layout.addWidget(self._ollama_model)

        # Status indicator
        self._ollama_status = QLabel("// Status: checking...")
        self._ollama_status.setFont(theme.font_hud(9))
        self._ollama_status.setStyleSheet(f"color: {theme.text_dim.name()};")
        layout.addWidget(self._ollama_status)

        layout.addStretch()

        note = QLabel("// Keys are stored locally in config/settings.json")
        note.setFont(theme.font_hud(9))
        note.setStyleSheet(f"color: {theme.text_dim.name()};")
        layout.addWidget(note)

        return tab

    def _build_voice_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Model selector
        layout.addWidget(self._section_label("LIVE MODEL"))
        self._model_combo = QComboBox()
        self._model_combo.addItems([
            "gemini-3.8-live",
            "gemini-3.8-live-extended-thinking",
            "gemini-3.1-flash-live-preview",
            "gemini-2.5-flash-native-audio-latest",
        ])
        layout.addWidget(self._model_combo)

        layout.addSpacing(6)

        # Voice selector
        layout.addWidget(self._section_label("VOICE"))
        self._voice_combo = QComboBox()
        self._voice_combo.addItems(["Aoede", "Charon", "Fenrir", "Kore", "Puck"])
        layout.addWidget(self._voice_combo)

        layout.addSpacing(6)

        # Toggles
        self._briefing_check = QCheckBox("Morning briefing on startup")
        layout.addWidget(self._briefing_check)

        self._proactive_check = QCheckBox("Proactive mode (idle engagement)")
        layout.addWidget(self._proactive_check)

        layout.addSpacing(6)

        # Proactive idle slider
        layout.addWidget(self._section_label("PROACTIVE IDLE THRESHOLD"))
        self._idle_slider = self._labeled_slider(60, 600, "sec")
        layout.addLayout(self._idle_slider["layout"])

        layout.addStretch()
        return tab

    def _build_appearance_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Accent hue
        layout.addWidget(self._section_label("ACCENT HUE"))
        self._hue_slider = self._labeled_slider(0, 359, "°")
        layout.addLayout(self._hue_slider["layout"])

        # Color preview
        self._color_preview = QLabel("  ████████  ")
        self._color_preview.setFixedHeight(24)
        self._color_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._color_preview)

        self._hue_slider["slider"].valueChanged.connect(self._on_hue_changed)

        layout.addSpacing(10)

        # Names
        layout.addWidget(self._section_label("ASSISTANT NAME"))
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("EVA")
        layout.addWidget(self._name_input)

        layout.addSpacing(6)
        layout.addWidget(self._section_label("YOUR NAME"))
        self._user_input = QLineEdit()
        self._user_input.setPlaceholderText("User")
        layout.addWidget(self._user_input)

        layout.addStretch()
        return tab

    def _build_integrations_tab(self) -> QWidget:
        """Tab for Email, Telegram, Smart Home credentials."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Email ────────────────────────────────────────────
        layout.addWidget(self._section_label("EMAIL (GMAIL / OUTLOOK)"))

        self._email_address = QLineEdit()
        self._email_address.setPlaceholderText("Email address (e.g. you@gmail.com)")
        self._email_address.setFixedHeight(36)
        self._email_address.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,0.05);
                border: 1px solid {theme.accent_dim.name()};
                color: {theme.text_primary.name()};
                padding: 6px 10px;
                font-family: \"{theme.font_mono}\";
                font-size: 11px;
            }}
        """)
        layout.addWidget(self._email_address)

        self._email_password = self._api_key_field(
            "App Password (Gmail: myaccount.google.com/apppasswords)")
        layout.addWidget(self._email_password)

        email_hint = QLabel(
            "// Gmail: Use App Password, NOT your normal password. "
            "Enable 2FA first.")
        email_hint.setFont(theme.font_hud(8))
        email_hint.setStyleSheet(f"color: {theme.text_dim.name()};")
        email_hint.setWordWrap(True)
        layout.addWidget(email_hint)

        # ── Telegram ─────────────────────────────────────────
        layout.addSpacing(12)
        layout.addWidget(self._section_label("TELEGRAM BOT"))

        self._telegram_token = self._api_key_field(
            "Bot Token (from @BotFather on Telegram)")
        layout.addWidget(self._telegram_token)

        tg_hint = QLabel(
            "// Open Telegram → @BotFather → /newbot → copy token")
        tg_hint.setFont(theme.font_hud(8))
        tg_hint.setStyleSheet(f"color: {theme.text_dim.name()};")
        layout.addWidget(tg_hint)

        # ── Smart Home (Home Assistant) ──────────────────────
        layout.addSpacing(12)
        layout.addWidget(self._section_label("HOME ASSISTANT (SMART HOME)"))

        self._ha_url = QLineEdit()
        self._ha_url.setPlaceholderText("HA URL (e.g. http://192.168.1.100:8123)")
        self._ha_url.setFixedHeight(36)
        self._ha_url.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,0.05);
                border: 1px solid {theme.accent_dim.name()};
                color: {theme.text_primary.name()};
                padding: 6px 10px;
                font-family: \"{theme.font_mono}\";
                font-size: 11px;
            }}
        """)
        layout.addWidget(self._ha_url)

        self._ha_token = self._api_key_field(
            "Long-Lived Access Token (HA → Profile → Tokens)")
        layout.addWidget(self._ha_token)

        ha_hint = QLabel(
            "// For TP-Link Kasa devices: pip install python-kasa "
            "(auto-discovers, no config needed)")
        ha_hint.setFont(theme.font_hud(8))
        ha_hint.setStyleSheet(f"color: {theme.text_dim.name()};")
        ha_hint.setWordWrap(True)
        layout.addWidget(ha_hint)

        layout.addStretch()

        note = QLabel("// All credentials stored locally in config/settings.json")
        note.setFont(theme.font_hud(9))
        note.setStyleSheet(f"color: {theme.text_dim.name()};")
        layout.addWidget(note)

        return tab

    def _build_system_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Monitor interval
        layout.addWidget(self._section_label("MONITOR INTERVAL"))
        self._monitor_slider = self._labeled_slider(10, 120, "sec")
        layout.addLayout(self._monitor_slider["layout"])

        # Alert thresholds
        layout.addWidget(self._section_label("CPU ALERT THRESHOLD"))
        self._cpu_thresh = self._labeled_slider(50, 100, "%")
        layout.addLayout(self._cpu_thresh["layout"])

        layout.addWidget(self._section_label("RAM ALERT THRESHOLD"))
        self._ram_thresh = self._labeled_slider(50, 100, "%")
        layout.addLayout(self._ram_thresh["layout"])

        layout.addWidget(self._section_label("TEMP ALERT THRESHOLD"))
        self._temp_thresh = self._labeled_slider(50, 100, "°C")
        layout.addLayout(self._temp_thresh["layout"])

        layout.addSpacing(6)

        # City
        layout.addWidget(self._section_label("CITY (FOR WEATHER)"))
        self._city_input = QLineEdit()
        self._city_input.setPlaceholderText("e.g. Tokyo, London, NYC")
        layout.addWidget(self._city_input)

        layout.addStretch()
        return tab

    # ── Widget Helpers ──────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(f"◈ {text}")
        label.setFont(theme.font_hud(9))
        label.setStyleSheet(f"""
            color: {theme.accent_dim.name()};
            letter-spacing: 2px;
        """)
        return label

    def _api_key_field(self, placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setFixedHeight(36)
        return field

    def _labeled_slider(self, min_val: int, max_val: int,
                        unit: str) -> dict:
        layout = QHBoxLayout()
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        value_label = QLabel(f"{min_val}{unit}")
        value_label.setFont(theme.font_hud(10))
        value_label.setFixedWidth(60)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        value_label.setStyleSheet(f"color: {theme.accent_bright.name()};")

        slider.valueChanged.connect(
            lambda v: value_label.setText(f"{v}{unit}")
        )
        layout.addWidget(slider)
        layout.addWidget(value_label)
        return {"layout": layout, "slider": slider, "label": value_label}

    # ── Load / Save ─────────────────────────────────────────────

    def load_current_settings(self) -> None:
        """Populate fields from config."""
        self._gemini_key.setText(config.get("api_key", ""))
        self._openai_key.setText(config.get("openai_api_key", ""))
        self._anthropic_key.setText(config.get("anthropic_api_key", ""))

        model = config.get("preferred_model", "gemini-3.1-flash-live-preview")
        idx = self._model_combo.findText(model)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)

        voice = config.get("voice_name", "Aoede")
        idx = self._voice_combo.findText(voice)
        if idx >= 0:
            self._voice_combo.setCurrentIndex(idx)

        self._briefing_check.setChecked(config.get("morning_briefing", True))
        self._proactive_check.setChecked(config.get("proactive_mode", True))
        self._idle_slider["slider"].setValue(
            config.get("proactive_idle_seconds", 300))

        self._hue_slider["slider"].setValue(config.get("accent_hue", 180))
        self._on_hue_changed(config.get("accent_hue", 180))

        self._name_input.setText(config.get("assistant_name", "EVA"))
        self._user_input.setText(config.get("user_name", "User"))

        self._monitor_slider["slider"].setValue(
            config.get("system_monitor_interval", 30))
        self._cpu_thresh["slider"].setValue(
            config.get("cpu_alert_threshold", 90))
        self._ram_thresh["slider"].setValue(
            config.get("ram_alert_threshold", 90))
        self._temp_thresh["slider"].setValue(
            config.get("temp_alert_threshold", 85))
        self._city_input.setText(config.get("city", ""))

        # Ollama settings
        self._ollama_check.setChecked(config.get("ollama_enabled", True))
        self._ollama_url.setText(
            config.get("ollama_url", "http://localhost:11434"))
        self._ollama_model.setText(config.get("ollama_model", ""))
        self._refresh_ollama_status()

        # Integrations
        self._email_address.setText(config.get("email_address", ""))
        self._email_password.setText(config.get("email_app_password", ""))
        self._telegram_token.setText(config.get("telegram_bot_token", ""))
        self._ha_url.setText(config.get("home_assistant_url", ""))
        self._ha_token.setText(config.get("home_assistant_token", ""))


    def _save_and_close(self) -> None:
        """Save all settings and close."""
        config.update(
            api_key=self._gemini_key.text().strip(),
            openai_api_key=self._openai_key.text().strip(),
            anthropic_api_key=self._anthropic_key.text().strip(),
            preferred_model=self._model_combo.currentText(),
            voice_name=self._voice_combo.currentText(),
            morning_briefing=self._briefing_check.isChecked(),
            proactive_mode=self._proactive_check.isChecked(),
            proactive_idle_seconds=self._idle_slider["slider"].value(),
            accent_hue=self._hue_slider["slider"].value(),
            assistant_name=self._name_input.text().strip() or "EVA",
            user_name=self._user_input.text().strip() or "User",
            system_monitor_interval=self._monitor_slider["slider"].value(),
            cpu_alert_threshold=self._cpu_thresh["slider"].value(),
            ram_alert_threshold=self._ram_thresh["slider"].value(),
            temp_alert_threshold=self._temp_thresh["slider"].value(),
            city=self._city_input.text().strip(),
            ollama_enabled=self._ollama_check.isChecked(),
            ollama_url=self._ollama_url.text().strip() or "http://localhost:11434",
            ollama_model=self._ollama_model.text().strip(),
            # Integrations
            email_address=self._email_address.text().strip(),
            email_app_password=self._email_password.text().strip(),
            telegram_bot_token=self._telegram_token.text().strip(),
            home_assistant_url=self._ha_url.text().strip(),
            home_assistant_token=self._ha_token.text().strip(),
        )

        # Apply accent color live
        theme.accent_hue = self._hue_slider["slider"].value()
        self.settings_changed.emit()
        self.hide()

    def _reset_defaults(self) -> None:
        """Reset all fields to defaults."""
        self._hue_slider["slider"].setValue(180)
        self._name_input.setText("EVA")
        self._user_input.setText("User")
        self._briefing_check.setChecked(True)
        self._proactive_check.setChecked(True)
        self._idle_slider["slider"].setValue(300)
        self._monitor_slider["slider"].setValue(30)
        self._cpu_thresh["slider"].setValue(90)
        self._ram_thresh["slider"].setValue(90)
        self._temp_thresh["slider"].setValue(85)
        self._model_combo.setCurrentIndex(0)
        self._voice_combo.setCurrentIndex(0)
        self._city_input.clear()
        self._ollama_check.setChecked(True)
        self._ollama_url.setText("http://localhost:11434")
        self._ollama_model.clear()
        # Integrations
        self._email_address.clear()
        self._email_password.clear()
        self._telegram_token.clear()
        self._ha_url.clear()
        self._ha_token.clear()

    def _refresh_ollama_status(self) -> None:
        """Check Ollama server status and update the label."""
        import threading

        def _check():
            try:
                from core.ollama_client import ollama
                status = ollama.get_status()
                if status["available"]:
                    models = status["models"]
                    text_m = status.get("text_model", "?")
                    vision_m = status.get("vision_model", "none")
                    label = (
                        f"// Status: ✓ Connected ({len(models)} models) | "
                        f"Text: {text_m} | Vision: {vision_m}"
                    )
                    color = "#00ff88"
                else:
                    label = "// Status: ✗ Not running — start with 'ollama serve'"
                    color = "#ff4444"
            except Exception:
                label = "// Status: ✗ Could not check"
                color = "#ff4444"

            # Update UI from main thread
            try:
                self._ollama_status.setText(label)
                self._ollama_status.setStyleSheet(f"color: {color};")
            except RuntimeError:
                pass  # Widget may have been deleted

        threading.Thread(target=_check, daemon=True).start()

    def _on_hue_changed(self, hue: int) -> None:
        color = QColor.fromHsl(hue, 255, 160)
        self._color_preview.setStyleSheet(f"""
            background-color: {color.name()};
            border: 1px solid {color.name()};
            border-radius: 4px;
            color: black;
            font-family: "{theme.font_mono}";
            font-size: 10px;
            letter-spacing: 2px;
        """)
        self._color_preview.setText(f"  {color.name().upper()}  ")

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        # Dark overlay background
        painter.fillRect(self.rect(), QColor(2, 0, 12, 240))
        # Neon border
        pen = QPen(theme.accent_dim, 1)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(15, 15, -16, -16))
        painter.end()


# Keep backward compatibility with the old name
CustomizeOverlay = SettingsPanel
