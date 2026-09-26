"""
EVA Main Window — Cyberpunk-styled composition of all UI widgets.
Neon header with glowing divider, animated input bar, HUD-style layout,
and reactive state indicators.
"""

import math
import threading

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QApplication, QFrame,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtGui import (
    QIcon, QColor, QPainter, QPen, QLinearGradient,
    QBrush, QRadialGradient,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QRectF, QPointF

from ui.styles import theme
from ui.hud_canvas import HudCanvas
from ui.metric_bar import MetricBar
from ui.log_widget import LogWidget
from ui.file_drop_zone import FileDropZone
from ui.camera_preview import CameraPreview
from ui.setup_overlay import SetupOverlay
from ui.customize_overlay import SettingsPanel
from ui.clipboard_panel import ClipboardPanel
from ui.remote_key_overlay import RemoteKeyOverlay
from memory.config_manager import config


class NeonDivider(QWidget):
    """Animated neon horizontal line divider."""

    def __init__(self, color: QColor = None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(2)
        self._color = color or theme.accent
        self._phase = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def _tick(self):
        self._phase += 0.08
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        w = self.width()

        # Animated gradient sweep
        sweep_pos = (math.sin(self._phase) + 1) / 2  # 0 to 1
        grad = QLinearGradient(0, 0, w, 0)

        c = self._color
        dim = QColor(c.red(), c.green(), c.blue(), 30)
        bright = QColor(c.red(), c.green(), c.blue(), 200)

        grad.setColorAt(0.0, dim)
        grad.setColorAt(max(0, sweep_pos - 0.15), dim)
        grad.setColorAt(sweep_pos, bright)
        grad.setColorAt(min(1, sweep_pos + 0.15), dim)
        grad.setColorAt(1.0, dim)

        painter.fillRect(0, 0, w, 2, grad)
        painter.end()


class PulseButton(QPushButton):
    """Button with subtle pulse glow animation on hover."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._pulse_phase = 0.0
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event):
        self._hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        super().leaveEvent(event)


class MainWindow(QMainWindow):
    """Cyberpunk-styled main application window."""

    # Signals for thread-safe UI updates
    update_amplitude_signal = pyqtSignal(str, float)
    update_state_signal = pyqtSignal(str)
    add_log_signal = pyqtSignal(str, str)
    update_metrics_signal = pyqtSignal(float, float, float, float)

    # Signals to communicate with the core engine
    text_command_signal = pyqtSignal(str)
    interrupt_signal = pyqtSignal()
    file_process_signal = pyqtSignal(str)
    clipboard_action_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            f"{config.get('assistant_name', 'EVA')} — Enhanced Virtual Assistant"
        )
        self.setMinimumSize(500, 750)
        self.resize(520, 880)

        # Apply base stylesheet
        self.setStyleSheet(theme.stylesheet_base())

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Neon Top Bar ────────────────────────────────────
        top_bar = QWidget()
        top_bar.setFixedHeight(56)
        top_bar.setStyleSheet(f"""
            background-color: {theme.bg_secondary.name()};
        """)
        header = QHBoxLayout(top_bar)
        header.setContentsMargins(16, 0, 16, 0)

        # Title with glow effect
        self._title_label = QLabel(config.get("assistant_name", "EVA"))
        self._title_label.setFont(theme.font_title())
        self._title_label.setStyleSheet(f"""
            color: {theme.accent.name()};
            letter-spacing: 4px;
        """)
        header.addWidget(self._title_label)

        # Status indicator (animated)
        self._status_dot = QLabel("●")
        self._status_dot.setFont(theme.font(8))
        self._status_dot.setStyleSheet(f"color: {theme.success.name()};")
        header.addWidget(self._status_dot)

        header.addStretch()

        # Settings button
        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setFixedSize(40, 40)
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                font-size: 22px; color: {theme.text_dim.name()};
                border-radius: 20px;
            }}
            QPushButton:hover {{
                color: {theme.accent.name()};
                background: rgba({theme.accent.red()}, {theme.accent.green()}, {theme.accent.blue()}, 20);
            }}
        """)
        self._settings_btn.clicked.connect(self._show_settings)
        header.addWidget(self._settings_btn)

        # Remote button
        self._remote_btn = QPushButton("📱")
        self._remote_btn.setFixedSize(40, 40)
        self._remote_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remote_btn.setStyleSheet(self._settings_btn.styleSheet())
        self._remote_btn.clicked.connect(self._show_remote)
        header.addWidget(self._remote_btn)

        main_layout.addWidget(top_bar)

        # ── Animated neon divider ───────────────────────────
        self._top_divider = NeonDivider()
        main_layout.addWidget(self._top_divider)

        # ── Content area ────────────────────────────────────
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 8, 12, 8)
        content_layout.setSpacing(8)

        # ── HUD Canvas (the orb) ────────────────────────────
        self.hud = HudCanvas()
        content_layout.addWidget(self.hud, stretch=3)

        # ── Camera Preview ──────────────────────────────────
        self.camera_preview = CameraPreview()
        content_layout.addWidget(
            self.camera_preview, 0, Qt.AlignmentFlag.AlignCenter
        )

        # ── Metric Bars ─────────────────────────────────────
        self.metrics = MetricBar()
        content_layout.addWidget(self.metrics)

        # ── Activity Log ────────────────────────────────────
        self.log = LogWidget()
        content_layout.addWidget(self.log, stretch=2)

        # ── File Drop Zone ──────────────────────────────────
        self.file_drop = FileDropZone()
        self.file_drop.file_dropped.connect(self._on_file_dropped)
        content_layout.addWidget(self.file_drop)

        main_layout.addWidget(content, stretch=1)

        # ── Bottom divider ──────────────────────────────────
        self._bottom_divider = NeonDivider()
        main_layout.addWidget(self._bottom_divider)

        # ── Input Bar ───────────────────────────────────────
        input_container = QWidget()
        input_container.setFixedHeight(60)
        input_container.setStyleSheet(f"""
            background-color: {theme.bg_secondary.name()};
        """)
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(14, 10, 14, 10)
        input_layout.setSpacing(10)

        # Prompt symbol (animated via state)
        self._prompt_label = QLabel("›")
        self._prompt_label.setFont(theme.font(size=20, bold=True))
        self._prompt_label.setStyleSheet(f"color: {theme.accent.name()};")
        self._prompt_label.setFixedWidth(18)
        input_layout.addWidget(self._prompt_label)

        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("Enter command...")
        self._text_input.setFixedHeight(38)
        self._text_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: rgba({theme.bg_input.red()}, {theme.bg_input.green()}, {theme.bg_input.blue()}, 180);
                color: {theme.accent_bright.name()};
                border: 1px solid {theme.border_color.name()};
                border-radius: 6px;
                padding: 8px 14px;
                font-family: "{theme.font_mono}";
                font-size: 12px;
                selection-background-color: {theme.accent_dim.name()};
            }}
            QLineEdit:focus {{
                border-color: {theme.accent.name()};
                background-color: rgba(15, 12, 38, 220);
            }}
        """)
        self._text_input.returnPressed.connect(self._on_text_submit)
        input_layout.addWidget(self._text_input)

        # Interrupt / Stop button
        self._interrupt_btn = QPushButton("■")
        self._interrupt_btn.setFixedSize(38, 38)
        self._interrupt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._interrupt_btn.setToolTip("Interrupt (stop speaking)")
        self._interrupt_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {theme.error.name()};
                border: 1px solid {theme.error.name()};
                border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 40, 80, 40);
                color: white;
                border-color: #ff4060;
            }}
            QPushButton:pressed {{
                background-color: rgba(255, 40, 80, 80);
            }}
        """)
        self._interrupt_btn.clicked.connect(self.interrupt_signal.emit)
        input_layout.addWidget(self._interrupt_btn)

        main_layout.addWidget(input_container)

        # ── Overlays ────────────────────────────────────────
        self._setup_overlay = None
        self._settings_panel = None
        self._remote_overlay = None
        self._clipboard_panel = ClipboardPanel(self)
        self._clipboard_panel.action_triggered.connect(
            self._on_clipboard_action
        )

        # ── Signal connections ──────────────────────────────
        self.update_amplitude_signal.connect(self._on_amplitude_update)
        self.update_state_signal.connect(self._on_state_update)
        self.add_log_signal.connect(self._on_add_log)
        self.update_metrics_signal.connect(self._on_metrics_update)

        # ── System metrics polling ──────────────────────────
        self._metrics_timer = QTimer(self)
        self._metrics_timer.timeout.connect(self._poll_metrics)
        self._metrics_timer.start(
            config.get("system_monitor_interval", 30) * 1000
        )
        QTimer.singleShot(1000, self._poll_metrics)

        # ── Prompt blink timer ──────────────────────────────
        self._prompt_phase = 0.0
        self._prompt_timer = QTimer(self)
        self._prompt_timer.timeout.connect(self._animate_prompt)
        self._prompt_timer.start(500)

    # ── Public methods for external thread-safe updates ─────

    def show_setup_overlay(self) -> SetupOverlay:
        """Show the first-run setup overlay."""
        self._setup_overlay = SetupOverlay(self)
        self._setup_overlay.setGeometry(self.rect())
        self._setup_overlay.show()
        self._setup_overlay.raise_()
        return self._setup_overlay

    def update_title(self, name: str) -> None:
        self._title_label.setText(name)
        self.setWindowTitle(f"{name} — Enhanced Virtual Assistant")

    # ── Slots ───────────────────────────────────────────────

    @pyqtSlot(str, float)
    def _on_amplitude_update(self, source: str, amplitude: float) -> None:
        if source == "input":
            self.hud.set_amplitude(amplitude)
        elif source == "output":
            self.hud.set_amplitude(amplitude * 1.5)

    @pyqtSlot(str)
    def _on_state_update(self, state: str) -> None:
        self.hud.set_state(state)
        # Update status dot
        color_map = {
            "idle": theme.text_dim,
            "listening": theme.success,
            "speaking": theme.accent_bright,
            "thinking": theme.neon_yellow,
        }
        c = color_map.get(state, theme.text_dim)
        self._status_dot.setStyleSheet(f"color: {c.name()};")

        # Update prompt symbol based on state
        prompt_map = {
            "idle": "›",
            "listening": "◉",
            "speaking": "◈",
            "thinking": "⟳",
        }
        self._prompt_label.setText(prompt_map.get(state, "›"))

    @pyqtSlot(str, str)
    def _on_add_log(self, text: str, source: str) -> None:
        color_map = {
            "user": theme.neon_cyan,
            "assistant": theme.accent_bright,
            "system": theme.text_dim,
            "tool": theme.neon_yellow,
            "error": theme.error,
        }
        self.log.add_entry(text, source, color_map.get(source))

    @pyqtSlot(float, float, float, float)
    def _on_metrics_update(self, cpu: float, ram: float,
                           gpu: float, temp: float) -> None:
        self.metrics.update_metrics(cpu, ram, gpu, temp)

    def _on_text_submit(self) -> None:
        text = self._text_input.text().strip()
        if text:
            self._text_input.clear()
            self.log.add_user_message(text)
            self.text_command_signal.emit(text)

    def _on_file_dropped(self, path: str) -> None:
        self.log.add_system_message(f"File dropped: {path}")
        self.file_process_signal.emit(path)

    def _on_clipboard_action(self, action: str, text: str) -> None:
        self.log.add_user_message(f"[Clipboard: {action}]")
        self.clipboard_action_signal.emit(action, text)

    def _show_settings(self) -> None:
        if not self._settings_panel:
            self._settings_panel = SettingsPanel(self)
            self._settings_panel.settings_changed.connect(self._apply_theme)
        self._settings_panel.load_current_settings()
        self._settings_panel.setGeometry(self.rect())
        self._settings_panel.show()
        self._settings_panel.raise_()

    def _show_remote(self) -> None:
        if not self._remote_overlay:
            self._remote_overlay = RemoteKeyOverlay(self)
        self._remote_overlay.setGeometry(self.rect())
        self._remote_overlay.show()
        self._remote_overlay.raise_()

    def get_remote_overlay(self) -> RemoteKeyOverlay:
        if not self._remote_overlay:
            self._remote_overlay = RemoteKeyOverlay(self)
        return self._remote_overlay

    def _apply_theme(self) -> None:
        """Re-apply theme after settings change."""
        self.setStyleSheet(theme.stylesheet_base())
        self._title_label.setText(config.get("assistant_name", "EVA"))
        self._title_label.setStyleSheet(f"""
            color: {theme.accent.name()};
            letter-spacing: 4px;
        """)
        self.update()

    def _animate_prompt(self) -> None:
        """Blink the prompt symbol."""
        self._prompt_phase += 1
        alpha = 255 if int(self._prompt_phase) % 2 == 0 else 140
        self._prompt_label.setStyleSheet(
            f"color: rgba({theme.accent.red()}, {theme.accent.green()}, "
            f"{theme.accent.blue()}, {alpha});"
        )

    def _poll_metrics(self) -> None:
        """Poll system metrics in a background thread."""
        def _poll():
            try:
                from actions.system_monitor import get_metrics_dict
                m = get_metrics_dict()
                self.update_metrics_signal.emit(
                    m.get("cpu", 0), m.get("ram", 0),
                    m.get("gpu", 0), m.get("temp", 0)
                )
            except Exception:
                pass

        thread = threading.Thread(target=_poll, daemon=True)
        thread.start()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        for overlay in [self._setup_overlay, self._settings_panel,
                        self._remote_overlay]:
            if overlay and overlay.isVisible():
                overlay.setGeometry(self.rect())
