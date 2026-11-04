# SPDX-License-Identifier: GPL-2.0-only
"""PipeWire side of the card: its sink/source nodes, default device, sample
rate, per-node volume, a test tone, mic monitoring and an input level meter.

Uses the stock command-line tools (pw-dump, wpctl, pw-metadata, pw-play,
pw-loopback, pw-record), so there is nothing extra to install.
"""

import json
import math
import os
import re
import shutil
import struct
import subprocess
import wave

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from . import config

RATES = [48000, 96000, 192000, 384000]  # what the AE-9 driver plays (pcm_rates=1)
RATES_CONF = os.path.expanduser("~/.config/pipewire/pipewire.conf.d/90-sbae9-sbc-rates.conf")


def _run(*args, timeout=3):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def available():
    return shutil.which("pw-dump") is not None and shutil.which("wpctl") is not None


def dump():
    out = _run("pw-dump", timeout=5)
    try:
        return json.loads(out) if out else []
    except json.JSONDecodeError:
        return []


def _is_ae9(props):
    text = " ".join(str(props.get(k, "")) for k in
                    ("alsa.id", "api.alsa.card.name", "alsa.card_name", "alsa.driver_name"))
    return "AE9" in text or "AE-9" in text or "creative_ae9" in text


class Nodes:
    """Snapshot of the AE-9's PipeWire nodes and the current defaults."""

    def __init__(self, objs=None):
        objs = dump() if objs is None else objs
        self.sink = self.source = self.device = None
        self.default_sink = self.default_source = None
        for o in objs:
            info = o.get("info") or {}
            props = info.get("props") or {}
            mc = props.get("media.class")
            meta_name = (o.get("props") or {}).get("metadata.name") or props.get("metadata.name")
            if o.get("type", "").endswith("Metadata") and meta_name == "default":
                for m in o.get("metadata", []):
                    val = m.get("value")
                    name = val.get("name") if isinstance(val, dict) else None
                    if m.get("key") == "default.audio.sink":
                        self.default_sink = name
                    elif m.get("key") == "default.audio.source":
                        self.default_source = name
            if not _is_ae9(props):
                continue
            node = {"id": o["id"], "name": props.get("node.name"),
                    "description": props.get("node.description"), "props": props,
                    "params": info.get("params") or {}}
            if mc == "Audio/Sink" and not self.sink:
                self.sink = node
            elif mc == "Audio/Source" and not self.source:
                self.source = node
            elif mc == "Audio/Device":
                self.device = node

    @property
    def sink_is_default(self):
        return bool(self.sink and self.sink["name"] == self.default_sink)

    @property
    def source_is_default(self):
        return bool(self.source and self.source["name"] == self.default_source)

    def sink_format(self):
        """(rate, format) the sink is running at, or None when idle."""
        if not self.sink:
            return None
        for f in self.sink["params"].get("Format") or []:
            return f.get("rate"), f.get("format")
        return None

    def sink_channel_volumes(self):
        if not self.sink:
            return None
        for p in self.sink["params"].get("Props") or []:
            if "channelVolumes" in p:
                return p["channelVolumes"]
        return None


def set_default(node_id):
    return _run("wpctl", "set-default", str(node_id)) is not None


def get_volume(node_id):
    """(volume 0..1.5, muted) on the desktop slider scale."""
    out = _run("wpctl", "get-volume", str(node_id))
    if not out:
        return None, False
    m = re.search(r"Volume:\s*([\d.]+)", out)
    return (float(m.group(1)) if m else None), "MUTED" in out


def set_volume(node_id, vol):
    _run("wpctl", "set-volume", str(node_id), f"{max(0.0, vol):.3f}")


def set_mute(node_id, muted):
    _run("wpctl", "set-mute", str(node_id), "1" if muted else "0")


def set_balance(node_id, balance, channel_volumes):
    """balance -1 (left) .. +1 (right); keeps the louder channel's level."""
    if not channel_volumes or len(channel_volumes) < 2:
        return
    level = max(channel_volumes[:2]) or 1.0
    left = level * (1.0 - max(0.0, balance))
    right = level * (1.0 + min(0.0, balance))
    _run("pw-cli", "set-param", str(node_id), "Props",
         f"{{ channelVolumes = [ {left:.6f} {right:.6f} ] }}")


def balance_of(channel_volumes):
    if not channel_volumes or len(channel_volumes) < 2:
        return 0.0
    left, right = channel_volumes[:2]
    top = max(left, right)
    if top <= 0:
        return 0.0
    return (1.0 - left / top) if left < right else -(1.0 - right / top)


# --- sample rate ----------------------------------------------------------------
def clock_settings():
    out = _run("pw-metadata", "-n", "settings", "0") or ""
    s = {}
    for m in re.finditer(r"key:'([^']+)' value:'([^']*)'", out):
        s[m.group(1)] = m.group(2)
    return s


def set_rate_mode(mode):
    """mode 0 = follow the source (any card rate), else force that rate.

    Applied live through the settings metadata and written to a PipeWire
    drop-in so it survives restarts.
    """
    rates = RATES if mode == 0 else [mode]
    _run("pw-metadata", "-n", "settings", "0", "clock.allowed-rates",
         "[ " + " ".join(map(str, rates)) + " ]")
    _run("pw-metadata", "-n", "settings", "0", "clock.force-rate", str(mode))
    os.makedirs(os.path.dirname(RATES_CONF), exist_ok=True)
    with open(RATES_CONF, "w") as f:
        f.write("# Written by Sound Blaster Command for Linux (sbae9-sbc).\n"
                "# The AE-9 plays 48/96/192/384 kHz; 44.1 kHz material is resampled.\n"
                "context.properties = {\n"
                f"    default.clock.rate          = {rates[0]}\n"
                f"    default.clock.allowed-rates = [ {' '.join(map(str, rates))} ]\n"
                "}\n")


def current_rate_mode():
    s = clock_settings()
    try:
        force = int(s.get("clock.force-rate", "0"))
    except ValueError:
        force = 0
    if force:
        return force
    allowed = s.get("clock.allowed-rates", "")
    nums = [int(x) for x in re.findall(r"\d+", allowed)]
    if len(nums) == 1:
        return nums[0]
    return 0


# --- test tone ----------------------------------------------------------------
def _tone_file(channel):
    path = os.path.join(config.cache_dir(), f"test-{channel}.wav")
    if os.path.exists(path):
        return path
    rate, secs, freq = 48000, 1.2, 440.0
    n = int(rate * secs)
    frames = bytearray()
    for i in range(n):
        env = min(1.0, i / 2400, (n - i) / 2400)  # 50 ms fades, no clicks
        # pink-ish chirp: 440 Hz with a little 880 so small speakers show it too
        s = 0.25 * env * (math.sin(2 * math.pi * freq * i / rate) +
                          0.3 * math.sin(4 * math.pi * freq * i / rate))
        v = int(max(-1.0, min(1.0, s)) * 32767)
        l, r = (v, 0) if channel == "left" else (0, v) if channel == "right" else (v, v)
        frames += struct.pack("<hh", l, r)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return path


class TestTone(QObject):
    """Plays a tone on the left speaker, then the right."""
    step = Signal(str)   # "left", "right" or "" when done

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue = []
        self._proc = None
        self._target = None

    @property
    def running(self):
        return self._proc is not None

    def start(self, target_name, channels=("left", "right")):
        self.stop()
        self._target = target_name
        self._queue = list(channels)
        self._next()

    def stop(self):
        self._queue = []
        if self._proc:
            p, self._proc = self._proc, None
            p.finished.disconnect()
            p.kill()
            p.waitForFinished(500)
        self.step.emit("")

    def _next(self, *_):
        if not self._queue:
            self._proc = None
            self.step.emit("")
            return
        ch = self._queue.pop(0)
        args = [_tone_file(ch)]
        if self._target:
            args = ["--target", self._target] + args
        self._proc = QProcess(self)
        self._proc.finished.connect(self._next)
        self._proc.start("pw-play", args)
        self.step.emit(ch)


class MicMonitor(QObject):
    """'Listen to this device': loops the AE-9 input to the default output."""
    state = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None

    @property
    def running(self):
        return self._proc is not None

    def start(self, source_name):
        self.stop()
        self._proc = QProcess(self)
        self._proc.finished.connect(self._done)
        self._proc.start("pw-loopback", [
            "-n", "sbae9-mic-monitor", "-l", "20",
            "-C", source_name,
            "--capture-props", "node.description='AE-9 mic monitor' node.dont-reconnect=true",
            "--playback-props", "media.role=Communication node.description='AE-9 mic monitor'",
        ])
        self.state.emit(True)

    def stop(self):
        if self._proc:
            p, self._proc = self._proc, None
            p.finished.disconnect()
            p.terminate()
            if not p.waitForFinished(800):
                p.kill()
        self.state.emit(False)

    def _done(self, *_):
        self._proc = None
        self.state.emit(False)


class LevelMeter(QObject):
    """Peak level of a source in dBFS per channel, from raw pw-record output."""
    levels = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._buf = b""
        self._peak = [-90.0, -90.0]
        self._timer = QTimer(self, interval=50)
        self._timer.timeout.connect(self._emit)

    def start(self, source_name):
        self.stop()
        self._proc = QProcess(self)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.start("pw-record", ["--raw", "--target", source_name, "--rate", "48000",
                                       "--channels", "2", "--format", "s16",
                                       "-P", "node.description='AE-9 level meter' node.dont-reconnect=true",
                                       "-"])
        self._timer.start()

    def stop(self):
        self._timer.stop()
        if self._proc:
            p, self._proc = self._proc, None
            p.readyReadStandardOutput.disconnect()
            p.terminate()
            if not p.waitForFinished(500):
                p.kill()
        self._peak = [-90.0, -90.0]
        self.levels.emit(-90.0, -90.0)

    def _read(self):
        if not self._proc:
            return
        data = self._buf + bytes(self._proc.readAllStandardOutput())
        usable = len(data) - len(data) % 4
        self._buf = data[usable:]
        if not usable:
            return
        samples = struct.unpack(f"<{usable // 2}h", data[:usable])
        for ch in (0, 1):
            pk = max((abs(x) for x in samples[ch::2]), default=0)
            db = 20 * math.log10(pk / 32768) if pk else -90.0
            self._peak[ch] = max(self._peak[ch], db)

    def _emit(self):
        self.levels.emit(*self._peak)
        # simple peak hold with fall-off
        self._peak = [max(-90.0, p - 3.0) for p in self._peak]


class Watcher(QObject):
    """Refreshes the PipeWire snapshot in the background (pw-dump via QProcess)."""
    updated = Signal(object)  # Nodes

    def __init__(self, parent=None, interval=2500):
        super().__init__(parent)
        self.nodes = Nodes([])
        self._proc = None
        self._timer = QTimer(self, interval=interval)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        QTimer.singleShot(0, self.refresh)

    def refresh(self):
        if self._proc is not None or not available():
            return
        self._proc = QProcess(self)
        self._proc.finished.connect(self._done)
        self._proc.start("pw-dump", [])

    def _done(self, *_):
        p, self._proc = self._proc, None
        try:
            objs = json.loads(bytes(p.readAllStandardOutput()).decode() or "[]")
        except (json.JSONDecodeError, UnicodeDecodeError):
            objs = []
        p.deleteLater()
        self.nodes = Nodes(objs)
        self.updated.emit(self.nodes)
