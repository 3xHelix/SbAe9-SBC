# SPDX-License-Identifier: GPL-2.0-only
"""Line icons drawn as inline SVG and tinted on demand."""

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import theme as T

_S = 'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"'

PATHS = {
    "home": f'<path {_S} d="M3 11 12 3.5 21 11"/><path {_S} d="M5.5 9v11.5h4.5v-6h4v6h4.5V9"/>',
    "equalizer": f'<path {_S} d="M5 3v18M12 3v18M19 3v18"/><rect {_S} x="3" y="13" width="4" height="3" rx="1"/>'
                 f'<rect {_S} x="10" y="6" width="4" height="3" rx="1"/><rect {_S} x="17" y="15" width="4" height="3" rx="1"/>',
    "playback": f'<path {_S} d="M3 9h4l5-4v14l-5-4H3z"/><path {_S} d="M16 9.5a4 4 0 0 1 0 5M18.5 7a7.5 7.5 0 0 1 0 10"/>',
    "recording": f'<rect {_S} x="9" y="3" width="6" height="11" rx="3"/><path {_S} d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M9 21h6"/>',
    "scout": f'<circle {_S} cx="12" cy="12" r="8"/><circle {_S} cx="12" cy="12" r="3"/>'
             f'<path {_S} d="M12 1.5v5M12 17.5v5M1.5 12h5M17.5 12h5"/>',
    "mixer": f'<path {_S} d="M3 6h18M3 12h18M3 18h18"/><circle {_S} cx="15" cy="12" r="2"/><circle {_S} cx="10" cy="18" r="2"/><circle {_S} cx="8" cy="6" r="2"/>',
    "settings": f'<circle {_S} cx="12" cy="12" r="3"/><path {_S} d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "headphones": f'<path {_S} d="M3.5 18v-6a8.5 8.5 0 0 1 17 0v6"/><rect {_S} x="3" y="14" width="4.5" height="7" rx="1.5"/><rect {_S} x="16.5" y="14" width="4.5" height="7" rx="1.5"/>',
    "speaker": f'<rect {_S} x="5" y="2.5" width="14" height="19" rx="2"/><circle {_S} cx="12" cy="15" r="3.5"/><circle {_S} cx="12" cy="7" r="1.3"/>',
    "volume": f'<path {_S} d="M3 9h4l5-4v14l-5-4H3z"/><path {_S} d="M16 9.5a4 4 0 0 1 0 5M18.5 7a7.5 7.5 0 0 1 0 10"/>',
    "mute": f'<path {_S} d="M3 9h4l5-4v14l-5-4H3z"/><path {_S} d="M16 9l5 6M21 9l-5 6"/>',
    "mic": f'<rect {_S} x="9" y="3" width="6" height="11" rx="3"/><path {_S} d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
    "mic-off": f'<rect {_S} x="9" y="3" width="6" height="11" rx="3"/><path {_S} d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/><path stroke="#e2505c" stroke-width="1.9" stroke-linecap="round" d="M4 3l16 18"/>',
    "info": f'<circle {_S} cx="12" cy="12" r="9.5"/><path {_S} d="M12 11v6"/><circle cx="12" cy="7.5" r="1.2" fill="currentColor"/>',
    "plus": f'<path {_S} d="M12 4v16M4 12h16"/>',
    "dots": '<circle cx="5" cy="12" r="1.9" fill="currentColor"/><circle cx="12" cy="12" r="1.9" fill="currentColor"/><circle cx="19" cy="12" r="1.9" fill="currentColor"/>',
    "chevron-left": f'<path {_S} d="M15 4 7 12l8 8"/>',
    "chevron-right": f'<path {_S} d="M9 4l8 8-8 8"/>',
    "chevron-down": f'<path {_S} d="M5 9l7 7 7-7"/>',
    "check": f'<path {_S} d="M5 12.5l4.5 4.5L19 7.5"/>',
    "film": f'<rect {_S} x="3" y="4" width="18" height="16" rx="2"/><path {_S} d="M7 4v16M17 4v16M3 8h4M3 12h4M3 16h4M17 8h4M17 12h4M17 16h4"/>',
    "gamepad": f'<path {_S} d="M7 7h10a5 5 0 0 1 4.9 6l-.8 4a2.5 2.5 0 0 1-4.3 1.2L14.5 16h-5l-2.3 2.2A2.5 2.5 0 0 1 2.9 17l-.8-4A5 5 0 0 1 7 7z"/><path {_S} d="M7 10.5v3M5.5 12h3"/><circle cx="15.5" cy="11" r="1" fill="currentColor"/><circle cx="17.5" cy="13" r="1" fill="currentColor"/>',
    "music": f'<path {_S} d="M9 18V5l11-2v13"/><circle {_S} cx="6" cy="18" r="3"/><circle {_S} cx="17" cy="16" r="3"/>',
    "moon": f'<path {_S} d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5z"/>',
    "star": f'<path {_S} d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    "wave": f'<path {_S} d="M2 12h2l2-6 3 12 3-15 3 15 3-12 2 6h2"/>',
    "refresh": f'<path {_S} d="M20 11a8 8 0 1 0-2.3 5.7"/><path {_S} d="M20 4v7h-7"/>',
    "chip": f'<rect {_S} x="6" y="6" width="12" height="12" rx="2"/><path {_S} d="M9 2.5V6M15 2.5V6M9 18v3.5M15 18v3.5M2.5 9H6M2.5 15H6M18 9h3.5M18 15h3.5"/>',
    "save": f'<path {_S} d="M5 3h11l4 4v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a1 1 0 0 1 1-1z"/><path {_S} d="M8 3v5h7V3M8 21v-7h8v7"/>',
    "power": f'<path {_S} d="M12 3v8"/><path {_S} d="M6.3 6.8a8 8 0 1 0 11.4 0"/>',
}


def svg(name, color):
    body = PATHS[name].replace("currentColor", color)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{body}</svg>'


def pixmap(name, color=None, size=22, ratio=2.0):
    return _pixmap(name, color or T.TEXT, size, ratio)


@lru_cache(maxsize=512)
def _pixmap(name, color, size, ratio):
    r = QSvgRenderer(QByteArray(svg(name, color).encode()))
    px = QPixmap(int(size * ratio), int(size * ratio))
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p, QRectF(0, 0, px.width(), px.height()))
    p.end()
    px.setDevicePixelRatio(ratio)
    return px


def icon(name, color=None, active=None, disabled=None, size=22):
    color = color or T.TEXT
    disabled = disabled or T.DIM
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, size), QIcon.Normal, QIcon.Off)
    ic.addPixmap(pixmap(name, active or color, size), QIcon.Normal, QIcon.On)
    ic.addPixmap(pixmap(name, active or color, size), QIcon.Active, QIcon.Off)
    ic.addPixmap(pixmap(name, disabled, size), QIcon.Disabled, QIcon.Off)
    return ic


def paint(painter, name, rect, color):
    r = QSvgRenderer(QByteArray(svg(name, color).encode()))
    r.render(painter, QRectF(rect))
