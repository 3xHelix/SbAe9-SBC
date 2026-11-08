# SPDX-License-Identifier: GPL-2.0-only
"""`sbae9-sbc ctl`: the AE-9's basics from the command line, no window.

The panel widget (plasmoid/) runs this. Changes follow the app's rules
(the same rate cap, quantum floor, bit-depth reopen and settings), and
the app, if it's open, sees them as changes made elsewhere.

  sbae9-sbc ctl status                 JSON: the state the widget shows
  sbae9-sbc ctl direct 0|1             Direct Mode off (DSP) / on
  sbae9-sbc ctl sbx 0|1
  sbae9-sbc ctl output speakers|headphones
  sbae9-sbc ctl rate 0|<Hz>            0 = automatic
  sbae9-sbc ctl depth <index>          an item of "PCM Bit Depth"
  sbae9-sbc ctl quantum 0|<frames>     8 to 8192; 0 = PipeWire decides
  sbae9-sbc ctl phantom 0|1            48 V; the caller asks the user first
  sbae9-sbc ctl preset <Hz> <frames>   rate and quantum at once
  sbae9-sbc ctl encoder off|ac3|dts    the optical encoder (driver 0.12.0+, ffmpeg)

  direct, sbx and output also take "toggle" (the keyboard shortcuts use it).
  --notify shows the result as a desktop notification too.

Every command prints one JSON object; changes print {"ok": ..., "error": ...}.
"""

import errno
import json
import shutil
import subprocess
import sys

from . import alsa, config, pipewire
from . import card as C

ERRORS = {
    errno.EBUSY: "Phantom power can't be switched on yet (card just started); try again in a few seconds.",
    errno.EAGAIN: "The head unit hasn't reported in yet; try again in a moment.",
}


class Card:
    """The AE-9's mixer, opened once for one command."""

    def __init__(self):
        self.mixer = None
        idx = alsa.find_card("AE9", "Sound Blaster AE-9", "AE-9")
        if idx >= 0:
            try:
                self.mixer = alsa.Mixer(idx)
            except OSError:
                self.mixer = None

    @property
    def present(self):
        return self.mixer is not None

    def _name(self, name):
        if self.mixer and not self.mixer.has(name):
            for old in C.ALIASES.get(name, ()):
                if self.mixer.has(old):
                    return old
        return name

    def has(self, name):
        return bool(self.mixer and self.mixer.has(self._name(name)))

    def control(self, name):
        return self.mixer.controls.get(self._name(name)) if self.mixer else None

    def get(self, name, default=None):
        if not self.has(name):
            return default
        try:
            return self.mixer.get(self._name(name))
        except OSError:
            return default

    def items(self, name):
        c = self.control(name)
        return list(c.items) if c else []

    def inactive(self, name):
        c = self.control(name)
        return bool(c and c.inactive)

    def write(self, name, value):
        """0, or the error number."""
        if not self.has(name):
            return errno.ENOENT
        try:
            self.mixer.set(self._name(name), value)
            return 0
        except OSError as e:
            return e.errno or errno.EIO

    def close(self):
        if self.mixer:
            self.mixer.close()
            self.mixer = None


def rate_set(card, nodes, direct=None):
    """The rates the card plays now (as the app's Context.rate_set)."""
    if direct is None:
        direct = bool(card.get(C.DIRECT, True)) if card.present else True
    surround = nodes.stream_layout() == "surround"
    return pipewire.playable_rates(direct, surround, C.module_param("pcm_rates") or "1",
                                   C.surround_max(), C.dsp_96k(), C.plays_176k4())


def apply_rate(settings, card, nodes, direct=None):
    """Write the saved rate pick, capped to what the card plays (nothing
    for automatic, unless PipeWire still forces a rate)."""
    mode = settings["rate_mode"] or 0
    if not mode and not pipewire.current_force_rate():
        return
    eff = pipewire.effective_rate(mode, rate_set(card, nodes, direct))
    pipewire.set_rate_mode(eff, pipewire.allowed_rates(C.module_param("pcm_rates"), C.plays_176k4()),
                           settings["quantum"] or 0)


def status(card, settings):
    nodes = pipewire.Nodes()
    out = {"present": card.present, "pipewire": nodes.sink is not None}
    if not card.present:
        return out
    clock = pipewire.clock_settings()

    def num(key):
        try:
            return int(clock.get(key, "0"))
        except ValueError:
            return 0
    direct = bool(card.get(C.DIRECT, True))
    live = pipewire.card_stream()
    offered = pipewire.card_rates(C.module_param("pcm_rates") or "1", C.plays_176k4())
    depths = card.items(C.BIT_DEPTH)
    out.update({
        "direct": direct,
        "sbx": bool(card.get(C.SBX, False)),
        "sbx_enabled": not direct and not card.inactive(C.SBX),
        "output": "headphones" if card.get(C.OUTPUT) == 1 else "speakers",
        "rate_pick": settings["rate_mode"] or 0,
        "rate_forced": num("clock.force-rate"),
        "rates": offered,
        "playable": rate_set(card, nodes, direct),
        "depths": depths,
        "depth": card.get(C.BIT_DEPTH, 0) if depths else None,
        "depth_fixed": None if depths else f"{C.module_param('pcm_bits') or '24'}-bit",
        "quantum_pick": settings["quantum"] or 0,
        "quantum_forced": num("clock.force-quantum"),
        "quantum_default": num("clock.quantum"),
        "quantum_max": num("clock.max-quantum"),
        "quanta": list(pipewire.QUANTA),
        "quantum_floor": pipewire.QUANTUM,
        "live": {"rate": live[0], "channels": live[1]} if live else None,
        "phantom": None,
    })
    if card.has(C.HU_PHANTOM):
        c = card.control(C.HU_PHANTOM)
        out["phantom"] = {"on": bool(card.get(C.HU_PHANTOM)), "writable": bool(c and c.writable)}
    return out


def change(card, settings, cmd, arg, extra=()):
    """Run one change; (ok, error message)."""
    if not card.present:
        return False, "The AE-9 isn't there."
    try:
        n = int(arg) if cmd not in ("output",) else None
    except (TypeError, ValueError):
        return False, f"{cmd}: expected a number, got {arg!r}"
    if cmd == "direct":
        on = bool(n)
        err = card.write(C.DIRECT, on)
        if not err:
            apply_rate(settings, card, pipewire.Nodes(), direct=on)
    elif cmd == "sbx":
        # two stages, as in the app: Direct Mode off (DSP) first, then SBX
        if card.get(C.DIRECT, True) or card.inactive(C.SBX):
            return False, "SBX works with Direct Mode off: switch to DSP first."
        err = card.write(C.SBX, bool(n))
    elif cmd == "output":
        if arg not in ("speakers", "headphones"):
            return False, "output: speakers or headphones"
        err = card.write(C.OUTPUT, 1 if arg == "headphones" else 0)
    elif cmd == "rate":
        if n and n not in pipewire.ALL_RATES:
            return False, f"rate: the AE-9 doesn't play {n} Hz"
        settings["rate_mode"] = n
        nodes = pipewire.Nodes()
        eff = pipewire.effective_rate(n, rate_set(card, nodes)) if n else 0
        pipewire.set_rate_mode(eff, pipewire.allowed_rates(C.module_param("pcm_rates"), C.plays_176k4()),
                               settings["quantum"] or 0)
        return True, ""
    elif cmd == "depth":
        items = card.items(C.BIT_DEPTH)
        if not 0 <= n < len(items):
            return False, "depth: this driver sets the bit depth with its pcm_bits option"
        err = card.write(C.BIT_DEPTH, n)
        if not err:
            pipewire.reopen_sink(pipewire.Nodes())    # taken when the card opens
    elif cmd == "preset":
        # rate and quantum at once (the widget's quick preset): "preset <Hz> <frames>"
        try:
            q = int(extra[0]) if extra else 0
        except ValueError:
            return False, "preset: <rate> <quantum>"
        if q and not pipewire.QUANTUM_MIN <= q <= pipewire.QUANTUM_MAX:
            return False, f"quantum: {pipewire.QUANTUM_MIN} to {pipewire.QUANTUM_MAX}, or 0"
        settings["quantum"] = q
        return change(card, settings, "rate", str(n))
    elif cmd == "quantum":
        if n and not pipewire.QUANTUM_MIN <= n <= pipewire.QUANTUM_MAX:
            return False, f"quantum: {pipewire.QUANTUM_MIN} to {pipewire.QUANTUM_MAX}, or 0"
        settings["quantum"] = n
        pipewire.set_quantum(pipewire.quantum_for(pipewire.current_force_rate(), n))
        return True, ""
    elif cmd == "phantom":
        if not card.has(C.HU_PHANTOM):
            return False, "This driver has no phantom power control."
        err = card.write(C.HU_PHANTOM, bool(n))
        if err in ERRORS:
            return False, ERRORS[err]
    else:
        return False, f"unknown command {cmd!r}"
    return (True, "") if not err else (False, f"{cmd}: {errno.errorcode.get(err, err)}")


TOGGLES = ("direct", "sbx", "output")


def toggled_arg(card, cmd):
    """The argument that flips `cmd` from its state now."""
    if cmd == "direct":
        return "0" if card.get(C.DIRECT, True) else "1"
    if cmd == "sbx":
        return "0" if card.get(C.SBX, False) else "1"
    return "speakers" if card.get(C.OUTPUT) == 1 else "headphones"


def state_text(card, cmd):
    """How a toggle left things, for the notification."""
    if cmd == "direct":
        return "Direct Mode on" if card.get(C.DIRECT, True) else "DSP on (Direct Mode off)"
    if cmd == "sbx":
        return "SBX on" if card.get(C.SBX, False) else "SBX off"
    if cmd == "output":
        return "Headphones" if card.get(C.OUTPUT) == 1 else "Speakers"
    return "Done"


def notify(text, error=False):
    """A short desktop notification (the shortcuts have no window)."""
    if not shutil.which("notify-send"):
        return
    try:
        subprocess.run(["notify-send", "-a", "Sound Blaster AE-9", "-i", "audio-card",
                        "-u", "normal" if error else "low", "-t", "4000" if error else "1500",
                        "-e", "-h", "string:x-canonical-private-synchronous:sbae9-sbc",
                        "Sound Blaster AE-9", text], timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def main(argv):
    show = "--notify" in argv
    argv = [a for a in argv if a != "--notify"]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    settings = config.Settings()
    card = Card()
    try:
        if argv[0] == "status":
            print(json.dumps(status(card, settings)))
            return 0
        if argv[0] in ("encoder", "encoder-run", "encoder-cleanup"):
            card.close()          # the encoder opens the mixer itself
            from . import encoder
            if argv[0] == "encoder-run":
                return encoder.run()
            if argv[0] == "encoder-cleanup":
                return encoder.cleanup()
            ok, msg = encoder.set_mode(argv[1] if len(argv) > 1 else "")
            print(json.dumps({"ok": ok, "error": msg}))
            return 0 if ok else 1
        cmd, arg = argv[0], argv[1] if len(argv) > 1 else None
        if arg == "toggle" and cmd in TOGGLES and card.present:
            arg = toggled_arg(card, cmd)
        ok, msg = change(card, settings, cmd, arg, argv[2:])
        print(json.dumps({"ok": ok, "error": msg}))
        if show:
            notify(state_text(card, cmd) if ok else msg, error=not ok)
            return 0      # a shortcut: the notification said what happened
        return 0 if ok else 1
    finally:
        card.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
