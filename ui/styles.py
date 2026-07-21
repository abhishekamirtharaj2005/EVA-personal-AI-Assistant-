"""
EVA UI Styles — CYBERPUNK theme system.
Neon glows, scanline effects, dark chrome palette.
Supports live accent color changes without restart.
"""

from PyQt6.QtGui import QColor, QFont, QLinearGradient, QRadialGradient, QFontDatabase
from PyQt6.QtCore import Qt


class EvaTheme:
    """Cyberpunk-themed visual system with neon glows and dark chrome."""

    def __init__(self):
        # ── Accent color (HSL-based, live-changeable) ─────────
        self._accent_hue: int = 180  # Neon cyan default

        # ── Cyberpunk base palette ────────────────────────────
        self.bg_primary = QColor(5, 2, 18)            # Ultra-dark chrome
        self.bg_secondary = QColor(10, 8, 28)          # Card background
        self.bg_tertiary = QColor(18, 14, 40)          # Elevated surface
        self.bg_overlay = QColor(2, 0, 12, 230)        # Heavy overlay
        self.bg_input = QColor(12, 10, 32)             # Input field bg

        self.text_primary = QColor(220, 240, 255)      # Cool white
        self.text_secondary = QColor(140, 160, 190)    # Steel blue
        self.text_dim = QColor(70, 85, 110)            # Faded

        self.border_color = QColor(30, 25, 60)         # Purple-tinted border
        self.border_active = QColor(50, 40, 90)        # Active border

        # ── Neon status colors ────────────────────────────────
        self.success = QColor(0, 255, 136)             # Matrix green
        self.warning = QColor(255, 200, 0)             # Amber
        self.error = QColor(255, 40, 80)               # Hot pink
        self.info = QColor(0, 180, 255)                # Electric blue

        # ── Metric neon colors ────────────────────────────────
        self.cpu_color = QColor(0, 255, 255)           # Cyan
        self.ram_color = QColor(190, 0, 255)           # Purple
        self.gpu_color = QColor(0, 255, 100)           # Neon green
        self.temp_color = QColor(255, 80, 20)          # Hot orange

        # ── Typography ────────────────────────────────────────
        self.font_family = "Consolas"
        self.font_mono = "Consolas"
        self.font_display = "Segoe UI"  # Fallback for display text

        # ── Cyberpunk extras ──────────────────────────────────
        self.scanline_alpha = 12            # Subtle scanline overlay
        self.glow_radius = 15               # Neon glow spread
        self.neon_pink = QColor(255, 0, 110)
        self.neon_cyan = QColor(0, 255, 213)
        self.neon_yellow = QColor(255, 240, 0)
        self.neon_purple = QColor(160, 0, 255)
        self.grid_color = QColor(20, 18, 45)

        # ── Derived accent colors ─────────────────────────────
        self._update_accent_colors()

    def _update_accent_colors(self) -> None:
        """Recalculate accent-derived colors from current hue."""
        h = self._accent_hue
        self.accent = QColor.fromHsl(h, 255, 160)
        self.accent_bright = QColor.fromHsl(h, 255, 200)
        self.accent_dim = QColor.fromHsl(h, 200, 80)
        self.accent_glow = QColor.fromHsl(h, 255, 160, 80)
        self.accent_bg = QColor.fromHsl(h, 150, 15)

        # Orb colors — cyberpunk neon transitions
        self.orb_idle = QColor.fromHsl(h, 220, 120)
        self.orb_listening = QColor.fromHsl((h + 40) % 360, 255, 170)
        self.orb_speaking = QColor.fromHsl((h + 80) % 360, 255, 190)
        self.orb_thinking = QColor.fromHsl((h + 160) % 360, 240, 150)

    @property
    def accent_hue(self) -> int:
        return self._accent_hue

    @accent_hue.setter
    def accent_hue(self, hue: int) -> None:
        self._accent_hue = hue % 360
        self._update_accent_colors()

    def set_accent_hex(self, hex_color: str) -> None:
        """Set accent from a hex color string."""
        color = QColor(hex_color)
        self._accent_hue = color.hslHue()
        if self._accent_hue < 0:
            self._accent_hue = 180
        self._update_accent_colors()

    # ── Font helpers ──────────────────────────────────────────

    def font(self, size: int = 11, bold: bool = False,
             mono: bool = False) -> QFont:
        family = self.font_mono if mono else self.font_family
        f = QFont(family, size)
        if bold:
            f.setBold(True)
        return f

    def font_title(self) -> QFont:
        f = QFont(self.font_display, 20)
        f.setBold(True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3.0)
        return f

    def font_subtitle(self) -> QFont:
        f = QFont(self.font_family, 12)
        f.setBold(True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        return f

    def font_body(self) -> QFont:
        return self.font(size=11)

    def font_small(self) -> QFont:
        return self.font(size=9)

    def font_code(self) -> QFont:
        return self.font(size=10, mono=True)

    def font_hud(self, size: int = 10) -> QFont:
        """HUD-style monospace font for meters and readouts."""
        f = QFont(self.font_mono, size)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        return f

    # ── Gradient helpers ──────────────────────────────────────

    def accent_gradient(self, x1: float, y1: float,
                        x2: float, y2: float) -> QLinearGradient:
        grad = QLinearGradient(x1, y1, x2, y2)
        grad.setColorAt(0.0, self.accent)
        grad.setColorAt(1.0, self.accent_bright)
        return grad

    def neon_gradient(self, x1: float, y1: float,
                      x2: float, y2: float) -> QLinearGradient:
        """Cyberpunk neon gradient: cyan → magenta."""
        grad = QLinearGradient(x1, y1, x2, y2)
        grad.setColorAt(0.0, self.neon_cyan)
        grad.setColorAt(0.5, self.accent)
        grad.setColorAt(1.0, self.neon_pink)
        return grad

    def orb_gradient(self, cx: float, cy: float,
                     radius: float, state: str = "idle") -> QRadialGradient:
        grad = QRadialGradient(cx, cy, radius)

        color_map = {
            "idle": (self.orb_idle, self.accent_dim),
            "listening": (self.orb_listening, self.accent),
            "speaking": (self.orb_speaking, self.accent_bright),
            "thinking": (self.orb_thinking, self.accent),
        }

        inner, outer = color_map.get(state, color_map["idle"])
        grad.setColorAt(0.0, inner)
        grad.setColorAt(0.4, QColor(inner.red(), inner.green(),
                                     inner.blue(), 140))
        grad.setColorAt(0.7, QColor(outer.red(), outer.green(),
                                     outer.blue(), 50))
        grad.setColorAt(1.0, QColor(outer.red(), outer.green(),
                                     outer.blue(), 0))
        return grad

    # ── Stylesheet snippets ───────────────────────────────────

    def stylesheet_base(self) -> str:
        """Cyberpunk base stylesheet."""
        return f"""
            QWidget {{
                background-color: {self.bg_primary.name()};
                color: {self.text_primary.name()};
                font-family: "{self.font_family}";
                font-size: 11px;
            }}
            QLineEdit {{
                background-color: {self.bg_input.name()};
                color: {self.accent_bright.name()};
                border: 1px solid {self.border_color.name()};
                border-radius: 4px;
                padding: 8px 12px;
                font-family: "{self.font_mono}";
                font-size: 12px;
                selection-background-color: {self.accent_dim.name()};
            }}
            QLineEdit:focus {{
                border-color: {self.accent.name()};
                background-color: {QColor(15, 12, 38).name()};
            }}
            QPushButton {{
                background-color: {self.bg_tertiary.name()};
                color: {self.text_primary.name()};
                border: 1px solid {self.border_color.name()};
                border-radius: 3px;
                padding: 8px 16px;
                font-family: "{self.font_mono}";
                font-size: 11px;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background-color: {self.accent_bg.name()};
                border-color: {self.accent.name()};
                color: {self.accent_bright.name()};
            }}
            QPushButton:pressed {{
                background-color: {self.accent_dim.name()};
            }}
            QScrollBar:vertical {{
                background: {self.bg_secondary.name()};
                width: 6px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {self.accent_dim.name()};
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {self.accent.name()};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QComboBox {{
                background-color: {self.bg_input.name()};
                color: {self.accent_bright.name()};
                border: 1px solid {self.border_color.name()};
                border-radius: 4px;
                padding: 6px 10px;
                font-family: "{self.font_mono}";
                font-size: 11px;
            }}
            QComboBox:hover {{
                border-color: {self.accent.name()};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {self.bg_tertiary.name()};
                color: {self.text_primary.name()};
                border: 1px solid {self.accent_dim.name()};
                selection-background-color: {self.accent_bg.name()};
                selection-color: {self.accent_bright.name()};
            }}
            QSlider::groove:horizontal {{
                background: {self.bg_input.name()};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {self.accent.name()};
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {self.accent_bright.name()};
            }}
            QCheckBox {{
                color: {self.text_primary.name()};
                font-family: "{self.font_mono}";
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 1px solid {self.border_color.name()};
                border-radius: 3px;
                background: {self.bg_input.name()};
            }}
            QCheckBox::indicator:checked {{
                background: {self.accent.name()};
                border-color: {self.accent.name()};
            }}
            QTabWidget::pane {{
                border: 1px solid {self.border_color.name()};
                background: {self.bg_secondary.name()};
                border-radius: 4px;
            }}
            QTabBar::tab {{
                background: {self.bg_tertiary.name()};
                color: {self.text_dim.name()};
                border: 1px solid {self.border_color.name()};
                padding: 8px 16px;
                font-family: "{self.font_mono}";
                font-size: 10px;
                letter-spacing: 1px;
                text-transform: uppercase;
            }}
            QTabBar::tab:selected {{
                background: {self.accent_bg.name()};
                color: {self.accent_bright.name()};
                border-bottom: 2px solid {self.accent.name()};
            }}
            QTabBar::tab:hover {{
                color: {self.accent.name()};
            }}
        """

    def neon_button_style(self, color: QColor = None) -> str:
        """Glowing neon button stylesheet."""
        c = color or self.accent
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {c.name()};
                border: 1px solid {c.name()};
                border-radius: 3px;
                padding: 10px 20px;
                font-family: "{self.font_mono}";
                font-size: 11px;
                letter-spacing: 2px;
            }}
            QPushButton:hover {{
                background-color: rgba({c.red()}, {c.green()}, {c.blue()}, 30);
                color: white;
            }}
            QPushButton:pressed {{
                background-color: rgba({c.red()}, {c.green()}, {c.blue()}, 60);
            }}
        """


# Global theme singleton
theme = EvaTheme()
