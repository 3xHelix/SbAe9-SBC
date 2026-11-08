# SPDX-License-Identifier: GPL-2.0-only
"""The optical encoder: surround over one optical cable, as Creative's
Windows app does it.

The AE-9 can't encode by itself: on Windows, Creative's software encodes on
the PC. Here the same loop runs in user space:

  What U Hear (the card's own mix, hw:AE9,2)  ->  pw-record
  -> the user's ffmpeg: AC-3 640 kbps or DTS (experimental), IEC 61937 framing
  -> aplay to the separate optical output (hw:AE9,4, driver 0.12.0) with the
     S/PDIF non-audio bit set, so the receiver decodes it.

It runs as the user service sbae9-sbc-encoder (install.sh installs it), so it
keeps going with the app closed and comes back at login. The app never ships
an encoder: it uses the ffmpeg already installed, and says when it's missing.
"""

import os
import shutil
import signal
import subprocess
import time

from sbae9kit import ae9

from . import alsa, config, pipewire
from . import card as C

UNIT = "sbae9-sbc-encoder.service"
UNIT_PATH = os.path.expanduser(f"~/.config/systemd/user/{UNIT}")

# mode -> (name in the app, ffmpeg encoder, its options)
ENCODERS = {
    "ac3": ("AC-3", "ac3", ["-c:a", "ac3", "-b:a", "640k"]),
    "dts": ("DTS", "dca", ["-c:a", "dca", "-strict", "experimental"]),
}
RATE = 48000
OPTICAL_PCM = f"hw:{ae9.CARD_ID},{C.OPTICAL_OUT_PCM}"


def _run(*args, timeout=5):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""


# --- what's there ----------------------------------------------------------------
_encoders_cache = None


def ffmpeg_encoders():
    """The audio encoders the installed ffmpeg has (empty without ffmpeg)."""
    global _encoders_cache
    if _encoders_cache is None:
        _encoders_cache = set()
        if shutil.which("ffmpeg"):
            rc, out = _run("ffmpeg", "-hide_banner", "-encoders")
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0].startswith("A"):
                    _encoders_cache.add(parts[1])
    return _encoders_cache


def missing(mode, nodes=None):
    """Why `mode` can't run here, or "" when it can."""
    if not shutil.which("ffmpeg"):
        return "Needs ffmpeg (Fedora: sudo dnf install ffmpeg-free)."
    if ENCODERS[mode][1] not in ffmpeg_encoders():
        return f"Your ffmpeg has no {ENCODERS[mode][0]} encoder."
    for tool in ("pw-record", "aplay", "systemctl"):
        if not shutil.which(tool):
            return f"Needs {tool}."
    nodes = nodes if nodes is not None else pipewire.Nodes()
    if not (nodes.optical_out or C.has_playback_pcm(C.OPTICAL_OUT_PCM)):
        return "Needs driver 0.12.0 or newer (optical as its own output)."
    if not nodes.what_u_hear:
        return "Needs the What U Hear input in PipeWire (Recording > Other Input)."
    if not os.path.exists(UNIT_PATH):
        return "Run install.sh once: it installs the encoder's background service."
    return ""


# --- the service (the app and `ctl encoder` drive it) -------------------------------
def active():
    return _run("systemctl", "--user", "is-active", "--quiet", UNIT)[0] == 0


def set_mode(mode):
    """Pick the encoder: "off", "ac3" or "dts". Saved, and the service is
    (re)started and enabled for login, or stopped and disabled. Returns
    (ok, message)."""
    if mode != "off" and mode not in ENCODERS:
        return False, f"encoder: off, {', '.join(ENCODERS)}"
    if mode != "off":
        why = missing(mode)
        if why:
            return False, why
    settings = config.Settings()
    settings["encoder"] = mode
    if mode == "off":
        _run("systemctl", "--user", "disable", "--now", UNIT, timeout=15)
        return True, ""
    _run("systemctl", "--user", "enable", UNIT)
    rc, _ = _run("systemctl", "--user", "restart", UNIT, timeout=15)
    return (rc == 0), ("" if rc == 0 else "The encoder service didn't start; "
                       "see journalctl --user -u " + UNIT)


# --- inside the service --------------------------------------------------------
def _channels(node):
    try:
        return max(1, min(6, int(node["props"].get("audio.channels") or 2)))
    except (TypeError, ValueError):
        return 2


def commands(mode, source, channels):
    """The three processes of the loop: capture, encode, play to optical."""
    layout = {1: "mono", 2: "stereo", 6: "5.1"}.get(channels, "stereo")
    rec = ["pw-record", "--target", source, "--rate", str(RATE), "--channels", str(channels),
           "--format", "s16", "-P", '{ node.description="AE-9 encoder" node.dont-reconnect=true }']
    if channels == 6:
        # PipeWire's RL/RR are ffmpeg's 5.1 back pair: the order both expect
        rec += ["--channel-map", "FL,FR,FC,LFE,RL,RR"]
    rec.append("-")
    enc = (["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-fflags", "nobuffer", "-probesize", "32", "-analyzeduration", "0",
            "-f", "s16le", "-ar", str(RATE), "-ac", str(channels), "-ch_layout", layout, "-i", "-"]
           + ENCODERS[mode][2] + ["-flush_packets", "1", "-f", "spdif", "-"])
    out = ["aplay", "-q", "-D", OPTICAL_PCM, "-f", "S16_LE", "-r", str(RATE), "-c", "2",
           "-t", "raw", "--buffer-time=100000", "-"]
    return rec, enc, out


def _mixer():
    idx = alsa.find_card("AE9", "Sound Blaster AE-9", "AE-9")
    return alsa.Mixer(idx) if idx >= 0 else None


def set_nonaudio(on):
    """The S/PDIF non-audio bit on the optical output (AES0 bit 1)."""
    try:
        m = _mixer()
    except OSError:
        return False
    if not m:
        return False
    try:
        if not m.has(C.OPTICAL_IEC958):
            return False
        st = m.get_iec958(C.OPTICAL_IEC958)
        new = (st[0] | C.IEC958_NONAUDIO) if on else (st[0] & ~C.IEC958_NONAUDIO)
        if new != st[0]:
            m.set_iec958(C.OPTICAL_IEC958, bytes([new]) + st[1:])
        return True
    except OSError:
        return False
    finally:
        m.close()


def _suspend_optical_sink(on):
    """PipeWire lets go of hw:AE9,4 (or takes it back)."""
    if not shutil.which("pactl"):
        return
    n = pipewire.Nodes()
    if n.optical_out:
        _run("pactl", "suspend-sink", n.optical_out["name"], "1" if on else "0")


def cleanup():
    """After the loop (ExecStopPost): PCM audio again, the sink back to PipeWire."""
    set_nonaudio(False)
    _suspend_optical_sink(False)
    return 0


def run():
    """The service: run the loop for the saved encoder until stopped. A
    non-zero exit makes systemd try again (e.g. PipeWire not up yet)."""
    mode = config.Settings()["encoder"]
    if mode not in ENCODERS:
        return 0
    n = None
    for _ in range(30):                 # at login, PipeWire may still be starting
        n = pipewire.Nodes()
        if n.what_u_hear and (n.optical_out or C.has_playback_pcm(C.OPTICAL_OUT_PCM)):
            break
        time.sleep(1)
    why = missing(mode, n)
    if why:
        print(why, flush=True)
        return 1
    rec_cmd, enc_cmd, out_cmd = commands(mode, n.what_u_hear["name"], _channels(n.what_u_hear))
    _suspend_optical_sink(True)
    procs = []
    stopping = []

    def stop(*_):
        stopping.append(True)
        for p in procs:
            if p.poll() is None:
                p.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        rec = subprocess.Popen(rec_cmd, stdout=subprocess.PIPE)
        procs.append(rec)
        enc = subprocess.Popen(enc_cmd, stdin=rec.stdout, stdout=subprocess.PIPE)
        procs.append(enc)
        rec.stdout.close()
        set_nonaudio(True)
        out = subprocess.Popen(out_cmd, stdin=enc.stdout)
        procs.append(out)
        enc.stdout.close()
        print(f"{ENCODERS[mode][0]} encoder: {n.what_u_hear['name']} "
              f"({_channels(n.what_u_hear)} ch) -> {OPTICAL_PCM}", flush=True)
        while not stopping and all(p.poll() is None for p in procs):
            time.sleep(0.5)
    finally:
        stop()
        for p in procs:
            try:
                p.wait(3)
            except subprocess.TimeoutExpired:
                p.kill()
        cleanup()
    return 0 if stopping else 1
