# SPDX-License-Identifier: GPL-2.0-only
"""The active palette and the Qt style sheet.

Every colour the app draws comes from the active palette. `apply(name)`
switches palettes; widgets read the module attributes (T.ACCENT, ...) when
they paint, and `stylesheet()` builds the QSS from them.
"""

from sbae9kit import desktop as _desktop
from sbae9kit import glass as _glass
from sbae9kit import palettes as _palettes

# The palettes are shared with SbAe9-AudioMon (sbae9kit.palettes).
PALETTES = _palettes.PALETTES

CURRENT = "command"

# UI scale in percent. Qt scales the whole window (fonts, dials, spacing,
# minimum size) from QT_SCALE_FACTOR, which it only reads at start-up, so a
# new scale means reopening the window.
SCALES = _desktop.SCALES
SCALE = 100          # what this launch runs at
clamp_scale = _desktop.clamp_scale


rgba = _palettes.rgba


# Glass: the window's backgrounds (title and bottom bars, sidebar, pages, the
# EQ graph) become see-through, on top of whichever palette is active; text
# and controls stay solid. KDE blurs what's behind when the app runs through
# XWayland (see __main__.use_xwayland and MainWindow.showEvent).
GLASS = False
GLASS_OPACITY = _glass.DEFAULT / 100   # how solid the glass is (0.3 - 0.95)
GLASS_RANGE = _glass.RANGE             # percent, for the Settings slider
clamp_glass = _glass.clamp


def surface(hex_color, depth=1.0):
    """A window background colour: as is, or see-through with Glass on.
    depth < 1 makes that surface a little clearer than the others."""
    return _glass.surface(hex_color, GLASS, GLASS_OPACITY, depth)


def surface_q(hex_color, depth=1.0):
    """surface() as a QColor, for widgets that paint their own background."""
    return _glass.surface_q(hex_color, GLASS, GLASS_OPACITY, depth)


# Warnings use one red in every palette, so they always look the same.
DANGER = _palettes.DANGER


def apply(name):
    """Make `name` the active palette (unknown names fall back to Command)."""
    global CURRENT
    CURRENT = name if name in PALETTES else "command"
    for k, v in PALETTES[CURRENT].items():
        if k.isupper():
            globals()[k] = v


apply("command")


def _qss():
    # thin light edges where glass panes meet, like light catching an edge
    edge = rgba(OVERLAY, 0.14)
    GLASS_EDGE_BOTTOM = f" border-bottom: 1px solid {edge};" if GLASS else ""
    GLASS_EDGE_TOP = f" border-top: 1px solid {edge};" if GLASS else ""
    GLASS_EDGE_RIGHT = f" border-right: 1px solid {edge};" if GLASS else ""
    return f"""
* {{
    font-family: "Roboto Condensed", "Barlow Semi Condensed", "Noto Sans", "DejaVu Sans Condensed", sans-serif;
    color: {TEXT};
    font-size: 14px;
}}
QMainWindow, #root {{ background: {"transparent" if GLASS else MAIN_TOP}; }}
#titleBar {{ background: {surface(TITLE_BG)};{GLASS_EDGE_BOTTOM} }}
#winButton, #winClose {{ background: transparent; border: none; border-radius: 3px; }}
#winButton:hover {{ background: {rgba(OVERLAY, 0.10)}; }}
#winClose:hover {{ background: {DANGER}; }}
#appTitle {{ font-size: 16px; color: {TEXT}; }}
#deviceName {{ font-size: 17px; font-weight: 700; color: {ACCENT}; }}
#sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {surface(SIDEBAR_TOP)},
                                stop:1 {surface(SIDEBAR_BOTTOM)});{GLASS_EDGE_RIGHT}
}}
#sideCaption {{ color: {MUTED}; font-size: 13px; padding-left: 18px; }}
#sideSep {{ background: {rgba(OVERLAY, 0.13)}; max-height: 1px; min-height: 1px; margin: 4px 10px; }}
#content {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {surface(MAIN_TOP, 0.85)},
                                stop:1 {surface(MAIN_BOTTOM, 0.85)});
}}
#bottomBar {{ background: {surface(BOTTOM_BG)};{GLASS_EDGE_TOP} }}
#pageTitle {{ font-size: 23px; font-weight: 700; }}
#sectionTitle {{ font-size: 15px; font-weight: 700; }}
#subTitle {{ font-size: 16px; font-weight: 700; }}
#tabBar {{ border-bottom: 1px solid {rgba(OVERLAY, 0.10)}; }}
#pageTab {{
    background: transparent; border: none; border-bottom: 2px solid transparent; border-radius: 0;
    padding: 4px 0 6px 0; font-size: 16px; font-weight: 700; color: {MUTED};
}}
#pageTab:hover {{ color: {TEXT}; }}
#pageTab:checked {{ color: {ACCENT}; border-bottom: 2px solid {ACCENT}; }}
#muted, .muted {{ color: {MUTED}; font-size: 13px; }}
#hint {{ color: {MUTED}; font-size: 13px; }}
#bigValue {{ font-size: 15px; font-weight: 700; }}
#profileLabel {{ font-size: 20px; font-weight: 600; }}
#sbxLogo {{ font-size: 26px; font-weight: 900; font-style: italic; color: {TEXT}; letter-spacing: 1px; }}
#banner {{
    background: {rgba(ACCENT, 0.16)}; border: 1px solid {rgba(ACCENT, 0.55)};
    border-radius: 4px;
}}
#banner QLabel {{ font-size: 13px; }}
#warnBanner {{
    background: {rgba(DANGER, 0.24)}; border: 1px solid {DANGER}; border-radius: 4px;
}}
#warnBanner QLabel {{ font-size: 13px; }}
#warnBanner QPushButton, #warnBanner QPushButton#accentButton {{
    background: {DANGER}; color: #ffffff; border: none; font-weight: 600;
}}
#warnBanner QPushButton#accentButton:hover {{ background: #ec6a74; }}
#warnBanner QPushButton#accentButton:pressed {{ background: #c63e4a; }}
#card {{ background: {rgba(SHADE, 0.10)}; border-radius: 6px; }}

QToolTip {{ background: {TOOLTIP}; color: {TEXT}; border: 1px solid {POPUP_BORDER}; padding: 4px; }}

QPushButton {{
    background: {PANEL}; border: none; padding: 7px 18px; border-radius: 2px; font-size: 14px;
}}
QPushButton:hover {{ background: {PANEL_HI}; }}
QPushButton:pressed {{ background: {PANEL_LO}; }}
QPushButton:disabled {{ color: {DIM}; background: {PANEL_LO}; }}
QPushButton#accentButton {{ background: {ACCENT}; color: {ACCENT_TEXT}; }}
QPushButton#accentButton:hover {{ background: {ACCENT_HI}; }}
QToolButton {{ background: transparent; border: none; padding: 4px; border-radius: 3px; }}
QToolButton:hover {{ background: {rgba(OVERLAY, 0.08)}; }}
QToolButton::menu-indicator {{ image: none; }}

QComboBox {{
    background: {PANEL}; border: none; padding: 7px 12px; border-radius: 2px; min-height: 22px;
    font-size: 15px; font-weight: 600;
}}
QComboBox:hover {{ background: {PANEL_HI}; }}
QComboBox:disabled {{ color: {DIM}; }}
QComboBox::drop-down {{ border: none; width: 34px; }}
QComboBox::down-arrow {{ image: url(__CHEVRON__); width: 16px; height: 16px; }}
QComboBox QAbstractItemView {{
    background: {LIST_BG}; border: 1px solid {POPUP_BORDER}; selection-background-color: {ACCENT};
    selection-color: {ACCENT_TEXT};
    outline: none; padding: 4px;
}}

QMenu {{ background: {POPUP}; border: 1px solid {POPUP_BORDER}; padding: 6px 0; }}
QMenu::item {{ padding: 8px 34px 8px 20px; }}
QMenu::item:selected {{ background: {rgba(ACCENT, 0.35)}; }}
QMenu::item:disabled {{ color: {DIM}; }}
QMenu::separator {{ height: 1px; background: {POPUP_BORDER}; margin: 4px 8px; }}

QRadioButton {{ spacing: 10px; font-size: 15px; }}
QRadioButton::indicator {{
    width: 16px; height: 16px; border-radius: 10px; border: 2px solid {TEXT}; background: transparent;
}}
QRadioButton::indicator:checked {{
    border: 2px solid {ACCENT}; background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {ACCENT}, stop:0.55 {ACCENT}, stop:0.6 transparent);
}}
QRadioButton:disabled {{ color: {DIM}; }}
QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 2px solid {TEXT}; border-radius: 2px; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: url(__CHECK__); }}

QSlider::groove:horizontal {{ height: 5px; background: {TRACK}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::sub-page:horizontal:disabled {{ background: {DIM}; }}
QSlider::handle:horizontal {{
    background: {HANDLE}; border: 1px solid {HANDLE_BORDER};
    width: 14px; height: 14px; margin: -6px 0; border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{ background: {HANDLE_HOVER}; }}

QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {rgba(OVERLAY, 0.18)}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QTableWidget {{
    background: {rgba(SHADE, 0.10)}; border: none; gridline-color: {rgba(OVERLAY, 0.08)};
    font-size: 13px;
}}
QHeaderView {{ background: transparent; }}
QTableCornerButton::section {{ background: transparent; border: none; }}
QSpinBox {{
    background: {PANEL}; border: none; padding: 4px 6px; color: {TEXT}; selection-background-color: {ACCENT};
}}
QHeaderView::section {{
    background: {rgba(SHADE, 0.18)}; color: {MUTED}; border: none; padding: 5px; font-size: 12px;
}}
QLineEdit {{ background: {PANEL}; border: none; padding: 6px 8px; selection-background-color: {ACCENT}; }}
QInputDialog, QMessageBox, QDialog {{ background: {DIALOG}; }}
"""


def stylesheet():
    """QSS with icon URLs resolved to cached PNG files."""
    import os
    from . import config, icons

    out = _qss()
    for key, name, color in (("__CHEVRON__", "chevron-down", TEXT), ("__CHECK__", "check", ACCENT_TEXT)):
        path = os.path.join(config.cache_dir(), f"qss-{name}-{color.lstrip('#')}.png")
        if not os.path.exists(path):
            icons.pixmap(name, color, 16, 2.0).save(path)
        out = out.replace(key, path)
    return out
