# SPDX-License-Identifier: GPL-2.0-only
"""The optical encoder: surround over one optical cable, as Creative's
Windows app does it.

The AE-9 can't encode by itself: on Windows, Creative's software encodes on
the PC. Here the same loop runs in user space:

  What U Hear (the card's own mix, hw:AE9,2)  ->  pw-record: 5.1 from the
     6-channel source of the 5.1 duplex card profile (driver 0.12.1), else 2.0
  -> the user's ffmpeg: AC-3 640 kbps or DTS (experimental), IEC 61937 framing
  -> aplay to the separate optical output (hw:AE9,4, driver 0.12.0) with the
     S/PDIF non-audio bit set, so the receiver decodes it.

It runs as the user service sbae9-sbc-encoder (install.sh installs it), so it
keeps going with the app closed and comes back at login. The app never ships
an encoder: it uses the ffmpeg already installed, and says when it's missing.
"""

import os
import select
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
# "Main output with effects": What U Hear looped to the optical output on the
# PC, as Windows' "Play Stereo Mix to Digital Output" does. Same service.
FX = "fx"
MODES = (FX,) + tuple(ENCODERS)
FX_NAME = "ae9-optical-fx"
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
    if mode == FX:
        for tool in ("pw-loopback", "systemctl"):
            if not shutil.which(tool):
                return f"Needs {tool}."
        nodes = nodes if nodes is not None else pipewire.Nodes()
        if not nodes.optical_out:
            return "Needs AE-9 Optical Out in PipeWire (driver 0.12.0 and its card profile)."
        if not nodes.what_u_hear:
            return "Needs the What U Hear input in PipeWire (Recording > Other Input)."
        if not os.path.exists(UNIT_PATH):
            return "Run install.sh once: it installs the optical out's background service."
        return ""
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
    """Pick what the service runs: "off", "fx" (the effects loop), "ac3" or
    "dts". Saved, and the service is (re)started and enabled for login, or
    stopped and disabled. Returns (ok, message)."""
    if mode != "off" and mode not in MODES:
        return False, f"encoder: off, {', '.join(MODES)}"
    if mode != "off":
        why = missing(mode)
        if why:
            return False, why
    settings = config.Settings()
    settings["encoder"] = mode
    if mode in ENCODERS:
        settings["encoder_last"] = mode
    if mode == "off":
        _run("systemctl", "--user", "disable", "--now", UNIT, timeout=15)
        return True, ""
    _run("systemctl", "--user", "enable", UNIT)
    rc, _ = _run("systemctl", "--user", "restart", UNIT, timeout=15)
    return (rc == 0), ("" if rc == 0 else "The encoder service didn't start; "
                       "see journalctl --user -u " + UNIT)


def source(nodes):
    """(What U Hear node, channels) to encode from: the 6-channel source of the
    5.1 duplex profile, else the stereo one as 2.0 (never 6 ch from the stereo
    source: its channels 3-6 are only the DSP's upmix). (None, 2) if neither."""
    if nodes.what_u_hear_51:
        return nodes.what_u_hear_51, 6
    return nodes.what_u_hear, 2


def surround_profile(nodes):
    """The card profile that gives 5.1 What U Hear, when the card is on another
    one that could switch to it; else None."""
    cur = nodes.card_profile() or ""
    if nodes.what_u_hear_51 or cur == pipewire.SURROUND_DUPLEX:
        return None
    if cur in ("off", "pro-audio") or cur.startswith("pro-audio"):
        return None
    return pipewire.SURROUND_DUPLEX if pipewire.SURROUND_DUPLEX in nodes.card_profiles() else None


# --- Playback > Digital's "Optical out plays" ------------------------------------
CHOICES = ("own", "mirror", FX, "ac3", "dts")


def set_mirror(on):
    """The driver's Optical Out Mirror Switch (0.12.1); False without it."""
    try:
        m = _mixer()
    except OSError:
        return False
    if not m:
        return False
    try:
        if not m.has(C.OPTICAL_MIRROR):
            return False
        m.set(C.OPTICAL_MIRROR, bool(on))
        return True
    except OSError:
        return False
    finally:
        m.close()


def set_optical(choice, mirror=set_mirror):
    """What optical out plays, one of CHOICES: its own output, the mirror of
    the main output, the main output with effects (the loop), or an encoder.
    Each turns the others off. `mirror` sets the driver's mirror switch (the
    app passes its own). Returns (ok, message)."""
    if choice not in CHOICES:
        return False, f"optical: {', '.join(CHOICES)}"
    service = choice if choice in MODES else "off"
    if choice != "mirror":
        mirror(False)           # first: a stopping loop mustn't hand over to the mirror
    ok, msg = set_mode(service)
    if ok and choice == "mirror":
        mirror(True)
    return ok, msg


def pause():
    """Stop the running encoder for a card profile switch (it holds hw:AE9,4:
    a profile built meanwhile would come up without the optical output).
    True if it was running; resume() starts it again."""
    if not active():
        return False
    _run("systemctl", "--user", "stop", UNIT, timeout=15)
    return True


def resume():
    if config.Settings()["encoder"] in ENCODERS:
        _run("systemctl", "--user", "start", UNIT, timeout=15)


# --- inside the service --------------------------------------------------------
def commands(mode, source, channels):
    """The three processes of the loop: capture, encode, play to optical."""
    layout = "5.1" if channels == 6 else "stereo"
    rec = ["pw-record"] + pipewire.raw_flag() + [
           "--target", source, "--rate", str(RATE), "--channels", str(channels),
           "--format", "s32", "-P", '{ node.description="AE-9 encoder" node.dont-reconnect=true }']
    if channels == 6:
        # the source's order (front-left, front-right, front-center, lfe,
        # rear-left, rear-right) is ffmpeg's 5.1 and AC-3's input order
        rec += ["--channel-map", "FL,FR,FC,LFE,RL,RR"]
    rec.append("-")
    enc = (["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-fflags", "nobuffer", "-probesize", "32", "-analyzeduration", "0",
            # raw samples on any PipeWire: --raw on 1.4+ (without it "-" gets a
            # Sun AU header); 1.0-1.2 have no --raw and write raw samples anyway
            "-f", "s32le", "-ar", str(RATE), "-ch_layout", layout, "-i", "-"]
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


def _source_changed(name):
    n = pipewire.Nodes()
    src, _ = source(n)
    return bool(src) and src["name"] != name


def run():
    """The service: run the loop for the saved encoder until stopped. A
    non-zero exit makes systemd try again (e.g. PipeWire not up yet)."""
    mode = config.Settings()["encoder"]
    if mode == FX:
        return run_fx()
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
    src, channels = source(n)
    rec_cmd, enc_cmd, out_cmd = commands(mode, src["name"], channels)
    _suspend_optical_sink(True)
    procs = []
    stopping = []

    def end():
        for p in procs:
            if p.poll() is None:
                p.terminate()

    def stop(*_):                       # SIGTERM / SIGINT: asked to stop
        stopping.append(True)
        end()

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
        print(f"{ENCODERS[mode][0]} encoder: {src['name']} ({channels} ch) -> {OPTICAL_PCM}",
              flush=True)
        ticks = 0
        while not stopping and all(p.poll() is None for p in procs):
            time.sleep(0.5)
            ticks += 1
            if ticks % 6 == 0 and _source_changed(src["name"]):
                # a card profile switch: exit non-zero, systemd starts it
                # again on the new source (5.1 <-> 2.0)
                print("What U Hear changed; restarting on the new source", flush=True)
                break
    finally:
        end()
        for p in procs:
            try:
                p.wait(3)
            except subprocess.TimeoutExpired:
                p.kill()
        cleanup()
    return 0 if stopping else 1


# --- the effects loop --------------------------------------------------------------
def _spa(props):
    """SPA JSON for pw-loopback's stream properties (double quotes only)."""
    def val(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, list):
            return "[ " + " ".join(v) + " ]"
        return f'"{v}"'
    return "{ " + " ".join(f"{k}={val(v)}" for k, v in props.items()) + " }"


def fx_command(source, channels, sink):
    """pw-loopback: What U Hear -> AE-9 Optical Out, stereo. Both streams keep
    node.dont-fallback (a missing target must not fall back to the mic, or to
    the analog output: a feedback howl) and node.linger (WirePlumber would
    otherwise remove such a stream when its target goes, e.g. on a profile
    switch). WirePlumber 0.4 ignores node.dont-fallback, so there they also
    get node.dont-reconnect; the service ends the loop once a target is gone.
    The 6-channel What U Hear is downmixed to stereo by PipeWire."""
    cap = {"node.description": "AE-9 Effects to Optical (What U Hear)",
           "target.object": source, "node.dont-fallback": True, "node.linger": True,
           "audio.position": ["FL", "FR"]}
    if channels == 2:
        cap["stream.dont-remix"] = True
    play = {"node.description": "AE-9 Effects to Optical",
            "target.object": sink, "node.dont-fallback": True, "node.linger": True,
            "stream.dont-remix": True, "audio.position": ["FL", "FR"]}
    if pipewire.wireplumber_04():
        cap["node.dont-reconnect"] = play["node.dont-reconnect"] = True
    return ["pw-loopback", "-n", FX_NAME, "--capture-props", _spa(cap),
            "--playback-props", _spa(play)]


def fx_wanted(nodes):
    """(source, channels, sink) while the loop should run, else None. It runs
    only while the main output plays: the driver loads a picked headphone
    profile only once every stream has stopped, so an always-on loop would
    hold it back. It stops when the main output suspends (idle for a few s)."""
    src, ch = source(nodes)
    sink = nodes.sink
    if not (src and nodes.optical_out and sink):
        return None
    if sink.get("state") == "running":
        return src["name"], ch, nodes.optical_out["name"]
    return False if sink.get("state") == "idle" else None


def run_fx():
    """The effects loop, gated on the main output. Follows PipeWire's events
    (pactl subscribe), and looks again every 2 s."""
    why = ""
    for _ in range(30):                 # at login, PipeWire may still be starting
        why = missing(FX)
        if not why:
            break
        time.sleep(1)
    if why:
        print(why, flush=True)
        return 1
    stopping = []
    loop = [None, None]                 # the pw-loopback process, what it runs

    def end_loop():
        p = loop[0]
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(3)
            except subprocess.TimeoutExpired:
                p.kill()
        loop[:] = [None, None]

    def stop(*_):
        stopping.append(True)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    sub = None
    if shutil.which("pactl"):
        try:
            sub = subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL)
        except OSError:
            sub = None
    print("Effects to optical: waiting for the main output to play", flush=True)
    try:
        while not stopping:
            want = fx_wanted(pipewire.Nodes())
            if loop[0] and loop[0].poll() is not None:
                print("pw-loopback ended; starting it again", flush=True)
                loop[:] = [None, None]
            if want is False:
                pass                    # idle between tracks: keep what runs
            elif want != loop[1]:
                if loop[0]:
                    end_loop()
                    print("Effects to optical: off", flush=True)
                if want:
                    loop[:] = [subprocess.Popen(fx_command(*want)), want]
                    print(f"Effects to optical: {want[0]} ({want[1]} ch) -> {want[2]}", flush=True)
            # wait for a PipeWire event, or 2 s
            fds = [sub.stdout] if sub and sub.poll() is None else []
            try:
                ready = select.select(fds, [], [], 2.0)[0] if fds else (time.sleep(2) or [])
            except InterruptedError:
                ready = []
            if ready:
                if not os.read(sub.stdout.fileno(), 65536):
                    sub = None
                time.sleep(0.2)         # let a burst of events pass
    finally:
        end_loop()
        if sub and sub.poll() is None:
            sub.terminate()
    return 0 if stopping else 1
