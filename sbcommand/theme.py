# SPDX-License-Identifier: GPL-2.0-only
"""Colour palettes and the Qt style sheet.

Every colour the app draws comes from the active palette. `apply(name)`
switches palettes; widgets read the module attributes (T.ACCENT, ...) when
they paint, and `stylesheet()` builds the QSS from them.
"""

PALETTES = {
    # Navy and purple with teal, like Creative's app.
    "command": {
        "label": "Command",
        "ACCENT": "#1fa6b8", "ACCENT_HI": "#35c3d6", "ACCENT_TEXT": "#ffffff",
        "TEXT": "#e8eaf3", "MUTED": "#a4a8bf", "DIM": "#6b6f86",
        "TRACK": "#4a4b5c", "PANEL": "#4b4c58", "PANEL_HI": "#585a68", "PANEL_LO": "#3d3e4b",
        "TITLE_BG": "#1b2034", "BOTTOM_BG": "#191d30",
        "SIDEBAR_TOP": "#272c5c", "SIDEBAR_BOTTOM": "#2d2a63",
        "MAIN_TOP": "#2b2b55", "MAIN_BOTTOM": "#33294f",
        "POPUP": "#1e2238", "POPUP_BORDER": "#343957", "LIST_BG": "#2d2f45",
        "DIALOG": "#24284a", "TOOLTIP": "#303247",
        "SWITCH_OFF": "#5a5c6c", "DIAL_TRACK": "#4a4b58", "IDLE": "#7d8296",
        "GRAPH_BG": "#45454f", "GRAPH_TEXT": "#d5d6de", "EQ_LINE": "#7f9cf5",
        "SEG": "#3d3e4c", "SEG_HOVER": "#4c4e5e", "CARD_CAP": "#3f3f4a", "SPEAKER_BOX": "#33355a",
        "OK": "#33d14f", "WARN": "#e9c64a",
        "METER": ["#1fa6b8", "#7fd16a", "#e9c64a", "#e2505c"],
        "OVERLAY": "#ffffff", "SHADE": "#000000", "DOT_IDLE": "#f2f2f2",
        "HANDLE": "#f2f2f6", "HANDLE_BORDER": "#f2f2f6", "HANDLE_HOVER": "#ffffff",
    },
    # From the 3xHelix avatar: blue-black, violet, coral-orange to amber, mint.
    "helix": {
        "label": "Helix",
        "ACCENT": "#f57a45", "ACCENT_HI": "#ffb63a", "ACCENT_TEXT": "#1b1230",
        "TEXT": "#f2edff", "MUTED": "#ab9fcb", "DIM": "#6d6190",
        "TRACK": "#3a2f5a", "PANEL": "#3b2e5e", "PANEL_HI": "#4b3b74", "PANEL_LO": "#2e2449",
        "TITLE_BG": "#120f21", "BOTTOM_BG": "#110e1f",
        "SIDEBAR_TOP": "#2a1850", "SIDEBAR_BOTTOM": "#3a1452",
        "MAIN_TOP": "#1d1832", "MAIN_BOTTOM": "#26183f",
        "POPUP": "#16122a", "POPUP_BORDER": "#3b2f5c", "LIST_BG": "#211b38",
        "DIALOG": "#1d1832", "TOOLTIP": "#2a2145",
        "SWITCH_OFF": "#4a3d6e", "DIAL_TRACK": "#3a2f5a", "IDLE": "#7a6c9e",
        "GRAPH_BG": "#241d3d", "GRAPH_TEXT": "#d9d0f0", "EQ_LINE": "#5dcaa8",
        "SEG": "#2e2449", "SEG_HOVER": "#3b2e5e", "CARD_CAP": "#2a2145", "SPEAKER_BOX": "#3b2e5e",
        "OK": "#5dcaa8", "WARN": "#ffb63a",
        "METER": ["#5dcaa8", "#5dcaa8", "#ffb63a", "#e31b49"],
        "OVERLAY": "#ffffff", "SHADE": "#000000", "DOT_IDLE": "#f2f2f2",
        "HANDLE": "#f2f2f6", "HANDLE_BORDER": "#f2f2f6", "HANDLE_HOVER": "#ffffff",
    },
    # Light: off-white and cream with blush and peach, coral accent.
    "albino": {
        "label": "Albino",
        "ACCENT": "#cf7166", "ACCENT_HI": "#b4554b", "ACCENT_TEXT": "#ffffff",
        "TEXT": "#4a3a38", "MUTED": "#8c7a76", "DIM": "#b9aaa5",
        "TRACK": "#e6d9d2", "PANEL": "#efe6df", "PANEL_HI": "#e8d9d1", "PANEL_LO": "#e2d4cc",
        "TITLE_BG": "#f7faf3", "BOTTOM_BG": "#f3efe6",
        "SIDEBAR_TOP": "#f4e7e3", "SIDEBAR_BOTTOM": "#eed3d2",
        "MAIN_TOP": "#f8f7f1", "MAIN_BOTTOM": "#eeecdf",
        "POPUP": "#fbfaf6", "POPUP_BORDER": "#e2d4cc", "LIST_BG": "#fbfaf6",
        "DIALOG": "#f8f7f1", "TOOLTIP": "#fbfaf6",
        "SWITCH_OFF": "#dccdc6", "DIAL_TRACK": "#ebe0d9", "IDLE": "#c9b8b2",
        "GRAPH_BG": "#fbfaf6", "GRAPH_TEXT": "#7a6864", "EQ_LINE": "#d0838c",
        "SEG": "#ebe1da", "SEG_HOVER": "#e3d4cc", "CARD_CAP": "#f5eee8", "SPEAKER_BOX": "#efe3dd",
        "OK": "#7fae8c", "WARN": "#d9a441",
        "METER": ["#dda394", "#db8176", "#cf6a5e", "#b8433a"],
        "OVERLAY": "#5a3a36", "SHADE": "#8a5a50", "DOT_IDLE": "#b9aaa5",
        "HANDLE": "#ffffff", "HANDLE_BORDER": "#cf7166", "HANDLE_HOVER": "#fff4f1",
    },
    # Wololo: the monk's royal-blue robe and white cloth, sun gold, grass
    # green, sky blue, and his staff's brown.
    "wololo": {
        "label": "Wololo",
        "ACCENT": "#f0d050", "ACCENT_HI": "#fdf2a0", "ACCENT_TEXT": "#1a2350",
        "TEXT": "#eef3e6", "MUTED": "#a9c6d6", "DIM": "#6a7eaa",
        "TRACK": "#33448a", "PANEL": "#2e3f86", "PANEL_HI": "#3a4d9c", "PANEL_LO": "#26356f",
        "TITLE_BG": "#121a3f", "BOTTOM_BG": "#101735",
        "SIDEBAR_TOP": "#2a3d9a", "SIDEBAR_BOTTOM": "#1f2f7a",
        "MAIN_TOP": "#1a2558", "MAIN_BOTTOM": "#1b2f52",
        "POPUP": "#141d48", "POPUP_BORDER": "#33458f", "LIST_BG": "#1a2558",
        "DIALOG": "#1a2558", "TOOLTIP": "#22306a",
        "SWITCH_OFF": "#44558f", "DIAL_TRACK": "#2e3f80", "IDLE": "#7183b3",
        "GRAPH_BG": "#17214f", "GRAPH_TEXT": "#c9dbe3", "EQ_LINE": "#8fce6f",
        "SEG": "#26356f", "SEG_HOVER": "#33458f", "CARD_CAP": "#3d3527", "SPEAKER_BOX": "#2e3f86",
        "OK": "#8fce6f", "WARN": "#f0d050",
        "METER": ["#6fb660", "#94ce7b", "#f0d050", "#e05a4f"],
        "OVERLAY": "#ffffff", "SHADE": "#000000", "DOT_IDLE": "#eef3e6",
        "HANDLE": "#eef3e6", "HANDLE_BORDER": "#eef3e6", "HANDLE_HOVER": "#ffffff",
    },
}

CURRENT = "command"


def rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


# Warnings use one red in every palette, so they always look the same.
DANGER = "#e2505c"


def apply(name):
    """Make `name` the active palette (unknown names fall back to Command)."""
    global CURRENT
    CURRENT = name if name in PALETTES else "command"
    for k, v in PALETTES[CURRENT].items():
        if k.isupper():
            globals()[k] = v


apply("command")


def _qss():
    return f"""
* {{
    font-family: "Roboto Condensed", "Barlow Semi Condensed", "Noto Sans", "DejaVu Sans Condensed", sans-serif;
    color: {TEXT};
    font-size: 14px;
}}
QMainWindow, #root {{ background: {MAIN_TOP}; }}
#titleBar {{ background: {TITLE_BG}; }}
#appTitle {{ font-size: 16px; color: {TEXT}; }}
#deviceName {{ font-size: 17px; font-weight: 700; color: {ACCENT}; }}
#sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {SIDEBAR_TOP}, stop:1 {SIDEBAR_BOTTOM});
}}
#sideCaption {{ color: {MUTED}; font-size: 13px; padding-left: 18px; }}
#sideSep {{ background: {rgba(OVERLAY, 0.13)}; max-height: 1px; min-height: 1px; margin: 4px 10px; }}
#content {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {MAIN_TOP}, stop:1 {MAIN_BOTTOM});
}}
#bottomBar {{ background: {BOTTOM_BG}; }}
#pageTitle {{ font-size: 23px; font-weight: 700; }}
#sectionTitle {{ font-size: 15px; font-weight: 700; }}
#subTitle {{ font-size: 16px; font-weight: 700; }}
#tabActive {{ font-size: 16px; font-weight: 700; color: {ACCENT}; }}
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
