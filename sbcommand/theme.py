"""Colors and the Qt style sheet, modelled on Sound Blaster Command."""

ACCENT = "#1fa6b8"
ACCENT_HI = "#35c3d6"
TEXT = "#e8eaf3"
MUTED = "#a4a8bf"
DIM = "#6b6f86"
TRACK = "#4a4b5c"
PANEL = "#4b4c58"
PANEL_HI = "#585a68"
TITLE_BG = "#1b2034"
BOTTOM_BG = "#191d30"
SIDEBAR_TOP = "#272c5c"
SIDEBAR_BOTTOM = "#2d2a63"
MAIN_TOP = "#2b2b55"
MAIN_BOTTOM = "#33294f"
DANGER = "#e2505c"
OK = "#33d14f"

QSS = f"""
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
#sideSep {{ background: rgba(255,255,255,0.13); max-height: 1px; min-height: 1px; margin: 4px 10px; }}
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
    background: rgba(31,166,184,0.16); border: 1px solid rgba(31,166,184,0.55);
    border-radius: 4px;
}}
#banner QLabel {{ font-size: 13px; }}
#warnBanner {{
    background: rgba(226,80,92,0.15); border: 1px solid rgba(226,80,92,0.6); border-radius: 4px;
}}
#card {{ background: rgba(0,0,0,0.16); border-radius: 6px; }}

QToolTip {{ background: #303247; color: {TEXT}; border: 1px solid #555; padding: 4px; }}

QPushButton {{
    background: {PANEL}; border: none; padding: 7px 18px; border-radius: 2px; font-size: 14px;
}}
QPushButton:hover {{ background: {PANEL_HI}; }}
QPushButton:pressed {{ background: #3e3f4b; }}
QPushButton:disabled {{ color: {DIM}; background: #3d3e4b; }}
QPushButton#accentButton {{ background: {ACCENT}; color: white; }}
QPushButton#accentButton:hover {{ background: {ACCENT_HI}; }}
QToolButton {{ background: transparent; border: none; padding: 4px; border-radius: 3px; }}
QToolButton:hover {{ background: rgba(255,255,255,0.08); }}
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
    background: #2d2f45; border: 1px solid #3f4260; selection-background-color: {ACCENT};
    outline: none; padding: 4px;
}}

QMenu {{ background: #1e2238; border: 1px solid #343957; padding: 6px 0; }}
QMenu::item {{ padding: 8px 34px 8px 20px; }}
QMenu::item:selected {{ background: rgba(31,166,184,0.35); }}
QMenu::item:disabled {{ color: {DIM}; }}
QMenu::separator {{ height: 1px; background: #343957; margin: 4px 8px; }}

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
    background: #f2f2f6; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{ background: white; }}

QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.18); border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QTableWidget {{
    background: rgba(0,0,0,0.18); border: none; gridline-color: rgba(255,255,255,0.06);
    font-size: 13px;
}}
QHeaderView {{ background: transparent; }}
QTableCornerButton::section {{ background: transparent; border: none; }}
QSpinBox {{
    background: {PANEL}; border: none; padding: 4px 6px; color: {TEXT}; selection-background-color: {ACCENT};
}}
QHeaderView::section {{
    background: rgba(0,0,0,0.3); color: {MUTED}; border: none; padding: 5px; font-size: 12px;
}}
QLineEdit {{ background: {PANEL}; border: none; padding: 6px 8px; selection-background-color: {ACCENT}; }}
QInputDialog, QMessageBox, QDialog {{ background: #24284a; }}
"""


def stylesheet():
    """QSS with icon URLs resolved to cached PNG files."""
    import os
    from . import config, icons

    out = QSS
    for key, name, color in (("__CHEVRON__", "chevron-down", TEXT), ("__CHECK__", "check", "#ffffff")):
        path = os.path.join(config.cache_dir(), f"qss-{name}.png")
        if not os.path.exists(path):
            icons.pixmap(name, color, 16, 2.0).save(path)
        out = out.replace(key, path)
    return out
