"""Custom widgets: toggle switch, effect dial, EQ graph, profile carousel..."""

import math

from PySide6.QtCore import (Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt,
                            QTimer, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)
from PySide6.QtWidgets import (QAbstractButton, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QSlider, QToolButton, QVBoxLayout, QWidget)

from . import icons
from . import theme as T


def label(text="", name=None, wrap=False):
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    if wrap:
        lb.setWordWrap(True)
    return lb


class Throttle:
    """Coalesce rapid calls (slider drags) into one call every `ms`."""

    def __init__(self, fn, ms=50):
        self.fn = fn
        self.args = None
        self.timer = QTimer(singleShot=True, interval=ms)
        self.timer.timeout.connect(self._fire)

    def __call__(self, *args):
        self.args = args
        if not self.timer.isActive():
            self._fire()
            self.timer.start()

    def _fire(self):
        if self.args is not None:
            args, self.args = self.args, None
            self.fn(*args)


# --------------------------------------------------------------------------------
class ToggleSwitch(QAbstractButton):
    """Pill switch like the Creative app's (teal when on)."""

    def __init__(self, parent=None, size=(38, 20)):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._w, self._h = size
        self.setFixedSize(*size)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def setCheckedSilently(self, on):
        if on == self.isChecked():
            return
        self.blockSignals(True)
        self.setChecked(on)
        self.blockSignals(False)
        self._pos = 1.0 if on else 0.0
        self.update()

    def _get(self):
        return self._pos

    def _set(self, v):
        self._pos = v
        self.update()

    knob = Property(float, _get, _set)

    def sizeHint(self):
        return QSize(self._w, self._h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self._w - 2, self._h - 2)
        off, on = QColor("#5a5c6c"), QColor(T.ACCENT)
        if not self.isEnabled():
            on = QColor(T.DIM)
        c = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos))
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * self._pos
        p.setBrush(QColor("#f4f4f8") if self.isEnabled() else QColor("#9a9cab"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))


# --------------------------------------------------------------------------------
class Dial(QWidget):
    """Arc dial 0..100 with the value in the middle (SBX 'Acoustic Engine')."""
    valueChanged = Signal(int)

    def __init__(self, parent=None, diameter=104):
        super().__init__(parent)
        self._value = 0
        self._active = True
        self._dragging = False
        self._d = diameter
        self.setFixedSize(diameter + 8, diameter + 8)
        self.setCursor(Qt.SizeVerCursor)
        self.setFocusPolicy(Qt.WheelFocus)
        self.setToolTip("Drag up/down, scroll or use the arrow keys")

    def value(self):
        return self._value

    def setValue(self, v, emit=False):
        v = max(0, min(100, int(round(v))))
        if v != self._value:
            self._value = v
            self.update()
            if emit:
                self.valueChanged.emit(v)

    def setActive(self, active):
        self._active = active
        self.update()

    def _from_pos(self, pos):
        c = QPointF(self.width() / 2, self.height() / 2)
        ang = math.degrees(math.atan2(c.y() - pos.y(), pos.x() - c.x()))  # 0 = east, ccw
        # Arc starts at 225 deg (lower left) and runs clockwise 270 deg to -45.
        sweep = (225 - ang) % 360
        if sweep > 270:
            sweep = 0 if sweep > 315 else 270
        return sweep / 270 * 100

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragging = True
            self.setValue(self._from_pos(e.position()), emit=True)

    def mouseMoveEvent(self, e):
        if self._dragging:
            self.setValue(self._from_pos(e.position()), emit=True)

    def mouseReleaseEvent(self, e):
        self._dragging = False

    def wheelEvent(self, e):
        step = 5 if e.modifiers() & Qt.ShiftModifier else 1
        self.setValue(self._value + (step if e.angleDelta().y() > 0 else -step), emit=True)

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key_Up, Qt.Key_Right):
            self.setValue(self._value + 1, emit=True)
        elif k in (Qt.Key_Down, Qt.Key_Left):
            self.setValue(self._value - 1, emit=True)
        elif k == Qt.Key_PageUp:
            self.setValue(self._value + 10, emit=True)
        elif k == Qt.Key_PageDown:
            self.setValue(self._value - 10, emit=True)
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = 11
        r = QRectF(4 + w / 2, 4 + w / 2, self._d - w, self._d - w)
        pen = QPen(QColor("#4a4b58"), w, Qt.SolidLine, Qt.FlatCap)
        p.setPen(pen)
        p.drawArc(r, 225 * 16, -270 * 16)
        if self._value > 0:
            pen.setColor(QColor(T.ACCENT if self._active else "#7d8296"))
            p.setPen(pen)
            p.drawArc(r, 225 * 16, int(-270 * 16 * self._value / 100))
        if self.hasFocus():
            p.setPen(QPen(QColor(255, 255, 255, 40), 1))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(r.adjusted(w, w, -w, -w))
        f = QFont("DejaVu Sans Mono")
        f.setPixelSize(int(self._d * 0.27))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(T.TEXT if self._active else T.MUTED))
        p.drawText(r, Qt.AlignCenter, str(self._value))


class EffectControl(QWidget):
    """Dial + on/off switch + caption, one per SBX effect."""
    levelChanged = Signal(int)
    toggled = Signal(bool)

    def __init__(self, caption, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.dial = Dial()
        self.switch = ToggleSwitch(size=(36, 18))
        self.caption = label(caption, "subTitle")
        self.caption.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.dial, 0, Qt.AlignHCenter)
        self.extra = QHBoxLayout()
        self.extra.setSpacing(8)
        self.extra.addStretch()
        self.extra.addWidget(self.switch)
        self.extra.addStretch()
        lay.addLayout(self.extra)
        lay.addSpacing(6)
        lay.addWidget(self.caption)
        self.dial.valueChanged.connect(self.levelChanged)
        self.switch.toggled.connect(self._on_toggle)
        self.switch.toggled.connect(self.toggled)

    def _on_toggle(self, on):
        self.dial.setActive(on)

    def set_state(self, on, level):
        self.switch.setCheckedSilently(on)
        self.dial.setActive(on)
        if not self.dial._dragging:
            self.dial.setValue(level)


class Segmented(QWidget):
    """Small exclusive button row (e.g. Night / Normal / Loud)."""
    selected = Signal(str)

    def __init__(self, options, parent=None, labels=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.buttons = {}
        for i, opt in enumerate(options):
            b = QPushButton((labels or {}).get(opt, opt))
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            first, last = i == 0, i == len(options) - 1
            b.setStyleSheet(
                "QPushButton{background:#3d3e4c;padding:4px 10px;font-size:12px;border-radius:0;"
                f"border-top-left-radius:{9 if first else 0}px;border-bottom-left-radius:{9 if first else 0}px;"
                f"border-top-right-radius:{9 if last else 0}px;border-bottom-right-radius:{9 if last else 0}px;}}"
                "QPushButton:hover{background:#4c4e5e;}"
                f"QPushButton:checked{{background:{T.ACCENT};color:white;}}")
            b.clicked.connect(lambda _=False, o=opt: self._click(o))
            lay.addWidget(b)
            self.buttons[opt] = b

    def _click(self, opt):
        self.set_value(opt)
        self.selected.emit(opt)

    def set_value(self, opt):
        for k, b in self.buttons.items():
            b.setChecked(k == opt)


# --------------------------------------------------------------------------------
class EqGraph(QWidget):
    """Pre-gain column + 10-band curve with draggable points (whole dB)."""
    bandChanged = Signal(int, float)  # 0 = pre-gain, 1..10 = bands
    editFinished = Signal()

    def __init__(self, labels, parent=None):
        super().__init__(parent)
        self.labels = labels
        self.values = [0.0] * (len(labels) + 1)
        self._drag = None
        self._hover = None
        self._active = True
        self.setMinimumSize(560, 250)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_values(self, vals):
        if self._drag is None:
            self.values = [float(v) for v in vals]
            self.update()

    def setActive(self, on):
        self._active = on
        self.update()

    # geometry
    def _pre_rect(self):
        return QRectF(0, 0, 72, self.height())

    def _main_rect(self):
        return QRectF(106, 0, self.width() - 106, self.height())

    def _plot(self, rect):
        return QRectF(rect.left() + 18, rect.top() + 22, rect.width() - 36, rect.height() - 62)

    def _y(self, plot, db):
        return plot.top() + (12 - db) / 24 * plot.height()

    def _db(self, plot, y):
        return max(-12, min(12, round(12 - (y - plot.top()) / plot.height() * 24)))

    def _points(self):
        pre = self._plot(self._pre_rect())
        main = self._plot(self._main_rect())
        pts = [QPointF(pre.center().x(), self._y(pre, self.values[0]))]
        n = len(self.labels)
        for i in range(n):
            x = main.left() + main.width() * i / (n - 1)
            pts.append(QPointF(x, self._y(main, self.values[i + 1])))
        return pts, pre, main

    def _hit(self, pos):
        pts, _, _ = self._points()
        best, bd = None, 18
        for i, pt in enumerate(pts):
            d = abs(pt.x() - pos.x())
            if d < bd:
                best, bd = i, d
        return best

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        self._drag = self._hit(e.position())
        if self._drag is not None:
            self._move(e.position())

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self._move(e.position())
        else:
            h = self._hit(e.position())
            if h != self._hover:
                self._hover = h
                self.setCursor(Qt.SizeVerCursor if h is not None else Qt.ArrowCursor)
                self.update()

    def mouseReleaseEvent(self, e):
        if self._drag is not None:
            self._drag = None
            self.editFinished.emit()

    def leaveEvent(self, e):
        self._hover = None
        self.update()

    def wheelEvent(self, e):
        i = self._hit(e.position())
        if i is None:
            return
        v = max(-12, min(12, round(self.values[i]) + (1 if e.angleDelta().y() > 0 else -1)))
        if v != self.values[i]:
            self.values[i] = v
            self.update()
            self.bandChanged.emit(i, v)
            self.editFinished.emit()

    def _move(self, pos):
        _, pre, main = self._points()
        plot = pre if self._drag == 0 else main
        v = self._db(plot, pos.y())
        if v != self.values[self._drag]:
            self.values[self._drag] = v
            self.update()
            self.bandChanged.emit(self._drag, float(v))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pts, pre, main = self._points()
        line = QColor("#7f9cf5" if self._active else "#8a8da0")
        for rect, plot, grid in ((self._pre_rect(), pre, False), (self._main_rect(), main, True)):
            p.fillRect(rect, QColor("#45454f"))
            f = p.font()
            f.setPixelSize(13)
            p.setFont(f)
            for db in (12, 0, -12):
                y = self._y(plot, db)
                p.setPen(QColor("#d5d6de"))
                p.drawText(QRectF(rect.left() + 2, y - 9, 22, 18), Qt.AlignCenter, str(db))
            if grid:
                n = len(self.labels)
                for i, lb in enumerate(self.labels):
                    x = plot.left() + plot.width() * i / (n - 1)
                    p.setPen(QPen(QColor(255, 255, 255, 26), 1))
                    p.drawLine(QPointF(x, plot.top() - 10), QPointF(x, plot.bottom() + 6))
                    p.setPen(QColor("#d5d6de"))
                    p.drawText(QRectF(x - 24, plot.bottom() + 14, 48, 20), Qt.AlignCenter, lb)
            else:
                p.setPen(QPen(QColor(255, 255, 255, 26), 1))
                p.drawLine(QPointF(plot.center().x(), plot.top() - 10), QPointF(plot.center().x(), plot.bottom() + 6))
                p.setPen(QColor("#d5d6de"))
                p.drawText(QRectF(rect.left(), plot.bottom() + 14, rect.width(), 20), Qt.AlignCenter, "Pre")
            p.setPen(QPen(QColor(255, 255, 255, 40), 1, Qt.DashLine))
            p.drawLine(QPointF(plot.left() - 4, self._y(plot, 0)), QPointF(plot.right() + 4, self._y(plot, 0)))

        # smooth curve through the band points (Catmull-Rom)
        bands = pts[1:]
        path = QPainterPath()
        ext = [QPointF(main.left() - 18, bands[0].y())] + bands + [QPointF(main.right() + 18, bands[-1].y())]
        path.moveTo(ext[0])
        for i in range(len(ext) - 1):
            p0 = ext[max(0, i - 1)]
            p1, p2 = ext[i], ext[i + 1]
            p3 = ext[min(len(ext) - 1, i + 2)]
            c1 = p1 + (p2 - p0) / 6
            c2 = p2 - (p3 - p1) / 6
            path.cubicTo(c1, c2, p2)
        fill = QPainterPath(path)
        fill.lineTo(ext[-1].x(), self._y(main, 0))
        fill.lineTo(ext[0].x(), self._y(main, 0))
        fill.closeSubpath()
        p.save()
        p.setClipRect(self._main_rect())
        col = QColor(line)
        col.setAlpha(40)
        p.fillPath(fill, col)
        p.setPen(QPen(line, 2.2))
        p.drawPath(path)
        p.restore()

        for i, pt in enumerate(pts):
            hot = i == self._drag or i == self._hover
            p.setPen(QPen(QColor("#ffffff"), 2.6))
            p.setBrush(line)
            rad = 8.5 if hot else 7
            p.drawEllipse(pt, rad, rad)
            if hot:
                v = self.values[i]
                txt = f"{v:+.0f} dB" if v else "0 dB"
                p.setPen(QColor(T.TEXT))
                p.drawText(QRectF(pt.x() - 30, pt.y() - 34, 60, 18), Qt.AlignCenter, txt)


# --------------------------------------------------------------------------------
ART = {
    "default": (("#1b3a6b", "#2f8fb3", "#7ee0e8"), "wave"),
    "gaming": (("#22351f", "#5c7a3a", "#c9d68a"), "gamepad"),
    "movie": (("#3a1218", "#8e2330", "#e6a15c"), "film"),
    "music": (("#3d1f5c", "#b14d9a", "#ffd0a6"), "music"),
    "night": (("#0b1030", "#2a2f7a", "#8fa0ff"), "moon"),
    "custom": (("#251a55", "#7a3fd1", "#e6a8ff"), "star"),
}


class ProfileCard(QWidget):
    clicked = Signal(str)

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(160, 184)

    def set_selected(self, sel):
        self.selected = sel
        self.setFixedSize(*((200, 228) if sel else (160, 184)))
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.profile["name"])

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        (c1, c2, c3), ic = ART.get(self.profile.get("art"), ART["custom"])
        art = QRectF(r.left(), r.top(), r.width(), r.height() - (56 if self.selected else 48))
        g = QLinearGradient(art.topLeft(), art.bottomRight())
        g.setColorAt(0, QColor(c1))
        g.setColorAt(0.65, QColor(c2))
        g.setColorAt(1, QColor(c3))
        p.fillRect(art, g)
        glow = QRadialGradient(art.center() + QPointF(art.width() * 0.2, -art.height() * 0.2), art.width() * 0.7)
        glow.setColorAt(0, QColor(255, 255, 255, 70))
        glow.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(art, glow)
        s = art.height() * 0.48
        p.setOpacity(0.85)
        icons.paint(p, ic, QRectF(art.center().x() - s / 2, art.center().y() - s / 2, s, s), "#ffffff")
        p.setOpacity(1.0)
        cap = QRectF(r.left(), art.bottom(), r.width(), r.bottom() - art.bottom())
        p.fillRect(cap, QColor("#3f3f4a"))
        f = p.font()
        f.setPixelSize(17 if self.selected else 15)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(T.TEXT))
        p.drawText(cap.adjusted(4, 4, -4, -cap.height() / 2), Qt.AlignCenter, self.profile["name"])
        f.setBold(False)
        f.setPixelSize(13 if self.selected else 12)
        p.setFont(f)
        p.setPen(QColor(T.MUTED))
        p.drawText(cap.adjusted(4, cap.height() / 2, -4, -4), Qt.AlignCenter, self.profile.get("author", ""))
        if self.selected:
            p.setPen(QPen(QColor(T.ACCENT), 4))
            p.setBrush(Qt.NoBrush)
            p.drawRect(r)


class ProfileCarousel(QWidget):
    picked = Signal(str)

    VISIBLE = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.profiles = []
        self.cards = []
        self.offset = 0
        self.current = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 14, 6, 14)
        self.prev = QToolButton()
        self.prev.setIcon(icons.icon("chevron-left", size=34))
        self.prev.setIconSize(QSize(34, 34))
        self.next = QToolButton()
        self.next.setIcon(icons.icon("chevron-right", size=34))
        self.next.setIconSize(QSize(34, 34))
        self.prev.clicked.connect(lambda: self._scroll(-1))
        self.next.clicked.connect(lambda: self._scroll(1))
        self.row = QHBoxLayout()
        self.row.setSpacing(20)
        lay.addWidget(self.prev)
        lay.addStretch()
        lay.addLayout(self.row)
        lay.addStretch()
        lay.addWidget(self.next)
        self.setMinimumHeight(262)

    def set_profiles(self, profiles, current):
        self.profiles = profiles
        self.current = current
        self._ensure_visible()
        self._rebuild()

    def set_current(self, name):
        self.current = name
        self._ensure_visible()
        self._rebuild()

    def _ensure_visible(self):
        names = [p["name"] for p in self.profiles]
        if self.current in names:
            i = names.index(self.current)
            if i < self.offset:
                self.offset = i
            elif i >= self.offset + self.VISIBLE:
                self.offset = i - self.VISIBLE + 1
        self.offset = max(0, min(self.offset, max(0, len(self.profiles) - self.VISIBLE)))

    def _scroll(self, d):
        self.offset = max(0, min(self.offset + d, max(0, len(self.profiles) - self.VISIBLE)))
        self._rebuild()

    def _rebuild(self):
        for c in self.cards:
            c.setParent(None)
            c.deleteLater()
        self.cards = []
        for prof in self.profiles[self.offset:self.offset + self.VISIBLE]:
            c = ProfileCard(prof)
            c.set_selected(prof["name"] == self.current)
            c.clicked.connect(self.picked)
            self.row.addWidget(c, 0, Qt.AlignVCenter)
            self.cards.append(c)
        self.prev.setEnabled(self.offset > 0)
        self.next.setEnabled(self.offset + self.VISIBLE < len(self.profiles))

    def paintEvent(self, _):
        p = QPainter(self)
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0, QColor(0, 0, 0, 70))
        g.setColorAt(1, QColor(255, 255, 255, 10))
        p.fillRect(self.rect(), g)


# --------------------------------------------------------------------------------
class VolumeRow(QWidget):
    """[icon mute button] [slider] [value text] — used in the mixer and bottom bar."""
    valueChanged = Signal(float)   # 0..1
    muteToggled = Signal(bool)

    def __init__(self, icon_on="volume", icon_off="mute", width=None, parent=None, show_value=True):
        super().__init__(parent)
        self.icon_on, self.icon_off = icon_on, icon_off
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.btn = QToolButton()
        self.btn.setIconSize(QSize(22, 22))
        self.btn.setCheckable(True)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setCursor(Qt.PointingHandCursor)
        if width:
            self.slider.setFixedWidth(width)
        self.value_label = QLabel()
        self.value_label.setObjectName("muted")
        self.value_label.setMinimumWidth(66)
        self.value_label.setVisible(show_value)
        lay.addWidget(self.btn)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.value_label)
        self.slider.valueChanged.connect(lambda v: self.valueChanged.emit(v / 1000))
        self.btn.toggled.connect(self._mute)
        self._set_icon(False)

    def _set_icon(self, muted):
        self.btn.setIcon(icons.icon(self.icon_off if muted else self.icon_on))

    def _mute(self, muted):
        self._set_icon(muted)
        self.muteToggled.emit(muted)

    def set_state(self, value, muted=False, text=None):
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(int(round(value * 1000)))
            self.slider.blockSignals(False)
        self.btn.blockSignals(True)
        self.btn.setChecked(muted)
        self.btn.blockSignals(False)
        self._set_icon(muted)
        if text is not None:
            self.value_label.setText(text)


class LevelBar(QWidget):
    """Horizontal peak meter, -60..0 dBFS."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = -90.0
        self.setFixedHeight(8)
        self.setMinimumWidth(160)

    def set_db(self, db):
        self.db = db
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.TRACK))
        p.drawRoundedRect(r, 3, 3)
        frac = max(0.0, min(1.0, (self.db + 60) / 60))
        if frac > 0:
            g = QLinearGradient(r.topLeft(), r.topRight())
            g.setColorAt(0, QColor(T.ACCENT))
            g.setColorAt(0.75, QColor("#7fd16a"))
            g.setColorAt(0.92, QColor("#e9c64a"))
            g.setColorAt(1, QColor(T.DANGER))
            p.setBrush(QBrush(g))
            p.setClipRect(QRectF(r.left(), r.top(), r.width() * frac, r.height()))
            p.drawRoundedRect(r, 3, 3)


class SpeakerDiagram(QWidget):
    """Listener with stereo speakers (and sub for 2.1) or headphones; lights the one playing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = "speakers"
        self.config = "2.1"
        self.playing = ""
        self.setFixedSize(220, 200)

    def set_state(self, mode=None, config=None, playing=None):
        if mode is not None:
            self.mode = mode
        if config is not None:
            self.config = config
        if playing is not None:
            self.playing = playing
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        rad = 72
        p.setPen(QPen(QColor(255, 255, 255, 70), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, rad, rad)

        def spk(name, pt, size=24):
            col = T.ACCENT_HI if self.playing == name else T.TEXT
            box = QRectF(pt.x() - size / 2, pt.y() - size / 2, size, size)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(T.ACCENT if self.playing == name else "#33355a"))
            p.drawRoundedRect(box.adjusted(-3, -3, 3, 3), 4, 4)
            icons.paint(p, "speaker", box, col)

        if self.mode == "headphones":
            s = 64
            icons.paint(p, "headphones", QRectF(c.x() - s / 2, c.y() - s / 2, s, s), T.TEXT)
            for name, dx in (("left", -1), ("right", 1)):
                if self.playing == name:
                    p.setPen(QPen(QColor(T.ACCENT_HI), 3))
                    p.drawArc(QRectF(c.x() + dx * 44 - 14, c.y() - 14, 28, 28),
                              (90 if dx < 0 else -90) * 16, 180 * 16)
            return
        icons.paint(p, "headphones", QRectF(c.x() - 13, c.y() - 13, 26, 26), T.MUTED)
        a = math.radians(50)
        spk("left", QPointF(c.x() - rad * math.sin(a), c.y() - rad * math.cos(a)))
        spk("right", QPointF(c.x() + rad * math.sin(a), c.y() - rad * math.cos(a)))
        if self.config == "2.1":
            spk("sub", QPointF(c.x(), c.y() + rad), 22)
