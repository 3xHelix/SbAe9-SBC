# SPDX-License-Identifier: GPL-2.0-only
"""The AE-9 as a Qt object: named hardware features on top of the ALSA controls.

Every change made anywhere (this app, alsamixer, the head-unit knob, the
desktop volume slider) arrives as an ALSA event and is re-emitted as
`changed(name)`, so the UI never has to poll the card.
"""

import errno
import math
import os
import re
import subprocess

from PySide6.QtCore import QObject, QSocketNotifier, QTimer, Signal

from sbae9kit import ae9
from . import alsa

# Control names (from the snd-hda-codec-creative-ae9 driver)
OUTPUT = "Head Unit Output"            # Speakers / Headphones
MASTER = "Master Playback Volume"      # 0..254, 0.5 dB steps, -127..0 dB
MASTER_SW = "Master Playback Switch"
MIC = "Capture Volume"                 # 0..99, -90 + v dB, 0 = mute
MIC_GAIN = "Mic Gain Capture Volume"   # 0/1/2 = 0/+10/+20 dB, head unit XLR/TRS + 3.5 mm mic jack
DAC_FILTER = "DAC Filter"              # 7 ES9038Q2M filters, Creative's names (driver 0.11.0; older: Default/Fast/Slow)
DIRECT = "Direct Mode Switch"
SBX = "SBX Switch"
HU_AUTO = "Head Unit Auto Switch"              # newer drivers: the 3.5 mm headphone plug switches outputs
HU_PHONES = "Head Unit 3.5mm Phones Plugged"   # read-only: head unit's 3.5 mm headphone jack
HU_MIC = "Head Unit 3.5mm Mic Plugged"         # read-only: head unit's 3.5 mm mic jack
HU_PHANTOM = "Head Unit Phantom Power"         # 48 V on the XLR/TRS jack; writable on newer drivers
# Older names of renamed controls: released drivers' (kept for good) and some
# test builds' (until every build in use has the new ones).
ALIASES = {
    MIC_GAIN: ("XLR Gain Capture Volume",),     # its name in drivers up to 0.9.2
    HU_PHONES: ("Head Unit Phones Plugged",),
    HU_MIC: ("Head Unit Line In Plugged",),
}
OPTICAL_OUT = "Optical Out Playback Switch"   # newer drivers: optical plays what the main output plays
# Driver 0.12.0: optical out is also its own playback device (hw:AE9,4). Its
# channel status; AES0 bit 1 = non-audio (AC-3 / DTS passthrough), set by
# ae9-optical-passthrough while it plays a file. Left on, PCM is noise.
OPTICAL_IEC958 = "IEC958 Playback Default"
# Driver 0.12.1: mirror the main output to optical while nothing plays to
# hw:AE9,4 (default off: optical plays only its own stream). Older drivers
# always mirror.
OPTICAL_MIRROR = "Optical Out Mirror Switch"
IEC958_NONAUDIO = 0x02
OPTICAL_OUT_PCM = 4
BIT_DEPTH = "PCM Bit Depth"
CAP_BIT_DEPTH = "Capture Bit Depth"       # 24-bit / 32-bit recording (newer drivers), next open             # 24-bit / 32-bit (newer drivers), next stream open
SPEAKER_CFG = "Speaker Config"         # 2.0 / 2.1
SV_MODE = "FX Smart Volume Mode"       # Normal / Loud / Night
EQ_ON = "EQ Switch"
EQ_PRESET = "EQ Preset"
SCOUT = "Scout Mode Switch"

EFFECTS = ["Surround", "Crystalizer", "Bass", "Smart Volume", "Dialog Plus"]
EFFECT_LABELS = {"Surround": "Surround", "Crystalizer": "Crystalizer", "Bass": "Bass",
                 "Smart Volume": "Smart Vol", "Dialog Plus": "Dialog +"}
EQ_BANDS = ["31Hz", "62Hz", "125Hz", "250Hz", "500Hz", "1kHz", "2kHz", "4kHz", "8kHz", "16kHz"]
EQ_BAND_LABELS = ["31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"]
EQ_PREGAIN = "EQ Pre-gain Volume"

# Speaker setup (newer drivers): bass redirect and per-speaker calibration,
# done by the DSP, so inactive in Direct Mode. Raw values are the units.
BASS_REDIRECT = "Bass Redirect Switch"
BASS_XOVER = "Bass Redirect Crossover"            # Hz, 50..200 in 10s
BASS_SUB_BOOST = "Bass Redirect Sub Boost Switch"  # on/off (driver 0.10.1+)
# Driver 0.10.0 had the boost as a -12..+12 dB int by mistake (Creative's
# BassManagement_SubwooferBoost is a bool): 0 = off, SUB_BOOST_OLD_ON = on.
BASS_SUB_GAIN_OLD = "Bass Redirect Sub Gain Volume"
SUB_BOOST_OLD_ON = 6
SPEAKER_CHANNELS = ["Front L", "Front R", "Center", "Sub", "Rear L", "Rear R"]
SPEAKER_TYPES = {"Tower": 80, "Desktop": 120}     # Windows sets the crossover from these
CM_DELAY_MS = 0.0293867                           # the driver's delay per cm (sound at 340.29 m/s)


HP_PROFILE = "Headphone Profile"   # Off + SB Command's headphone models (newer drivers)
HP_VIRT = "Headphone Virtualization Switch"     # Virtual 7.1 on headphones (0.12.2)
LINE_VIRT = "Line Out Virtualization Switch"    # the headphone mix on the RCA out (0.12.2)
MIC_MONITOR = "Mic Monitor Playback Switch"     # the mic mixed in the DSP, no delay (0.12.2)
# read-only (0.12.3): the monitor was on since the DSP loaded. After that, a Voice
# Clarity recording made with the monitor off comes out broken until a power cycle.
MIC_MONITOR_USED = "Mic Monitor Used Since Power-up"
# Voice Clarity (Recording, 0.12.2): the master and its effects
VC = "Voice Clarity Capture Switch"
VC_AEC = "Acoustic Echo Cancellation Capture Switch"
VC_NR = "Noise Reduction Capture Switch"
VC_SVM = "Mic Smart Volume Capture Switch"
VC_MICEQ = "Mic EQ Capture Enum"
VC_MORPH = "Voice Morphing Capture Enum"


def vc_needs_listen(card, change=None):
    """Voice Clarity is in use on a driver before 0.12.7, where switching the
    card's mic monitor off breaks Voice Clarity recordings until a power-off:
    the Monitor uses the software Listen then. 0.12.7 fixed it in the driver."""
    return vc_in_use(card, change) and not driver_at_least(0, 12, 7)


def vc_in_use(card, change=None):
    """Voice Clarity is in use: the master, an effect, Mic EQ or a voice is on.
    `change` ({name: value}) asks what it would be after that write."""
    if not card.has(VC):
        return False
    change = change or {}
    return any(bool(change.get(n, card.get(n, 0))) for n in (VC, VC_AEC, VC_NR, VC_SVM, VC_MICEQ, VC_MORPH))
# where ae9-get-firmware puts Creative's headphone curves (it checks the same);
# firmware/updates/ first, as the kernel does (Arch installs there: AE-5/AE-7 clash)
HP_DIRS = ("/etc/firmware", "/lib/firmware/updates", "/usr/lib/firmware/updates",
           "/lib/firmware", "/usr/lib/firmware")


# Headphone Profile items -> the file each loads (driver's hp_profiles[]):
# Creative's models by name; the last four are custom slots, named by the
# driver's hp_custom parameter (0.12.2), "Custom N" (custom<N>.bin) when empty.
HP_KEYS = {
    "AKG M220": "AKGM220", "Apple Earphone": "IP3EP", "Apple Earpod": "IP5EP",
    "audio-technica ATH-M50": "ATHM50", "CORSAIR HS50": "HS50",
    "Creative Aurvana Air": "CTAVNA", "Creative Aurvana Gold": "CTAVNG",
    "Creative Aurvana Live!": "CTAVNL", "Creative Aurvana Live!2": "CTAVNL2",
    "Creative EP-3NC": "CTEP3NC", "Creative Fatal1ty Gaming Headset": "CTFATGHS",
    "Creative Flex": "CTFlex", "Creative Outlier": "OUTLIER",
    "Creative Outlier Black": "OUTLIERB", "Creative SB Inferno Headset": "CTSBINF",
    "Creative SXFI AIR": "SXFIAIR", "Creative SXFI AIR C": "SXFIAIRC",
    "E-MU Teak": "EMUTEAK", "E-MU Walnut": "WALNUT", "HYPERX HX-HSCF": "HXHSCF",
    "Mr Speakers ETHER C": "ETHERC", "Philips Fidelio X2HR": "PFX2HR",
    "Samsung Galaxy Headset": "GS3EP", "SENNHEISER HD 201": "HD201",
    "SENNHEISER HD 280 Pro": "HD280Pro", "SENNHEISER HD 457": "HD457",
    "SONY MDR-1R": "MDR1R", "Sound Blaster Blaze": "SBBLAZE",
    "Sound BlasterX H3": "H3", "Sound BlasterX H5 TE": "H5",
    "Sound BlasterX H7 TE": "H7", "Sound BlasterX P5": "P5",
}
HP_CUSTOM_SLOTS = 4
HP_CUSTOM_PARAM = "hp_custom"


def hp_custom_slots():
    """[(key, name) or None] * 4: the driver's custom headphone slots (0.12.2)."""
    raw = module_param(HP_CUSTOM_PARAM) or ""
    slots = [None] * HP_CUSTOM_SLOTS
    for n, ent in enumerate(raw.split(";")[:HP_CUSTOM_SLOTS]):
        if "=" in ent:
            k, v = ent.split("=", 1)
            if k.strip():
                slots[n] = (k.strip(), v.strip())
    return slots


def hp_file(key):
    """Where the driver would find hp/<key>.bin, or None."""
    for d in HP_DIRS:
        f = os.path.join(d, "creative-ae9", "hp", f"{key}.bin")
        if os.path.exists(f):
            return f
    return None


def hp_item_files(items):
    """For each Headphone Profile item: (key, installed). Off is (None, True);
    an item SBC doesn't know is (None, True) too (shown as is)."""
    out = []
    # Off + Creative's models + the custom slots (driver 0.12.2)
    custom0 = 1 + len(HP_KEYS) if len(items) == 1 + len(HP_KEYS) + HP_CUSTOM_SLOTS else None
    slots = hp_custom_slots() if custom0 is not None else []
    for i, name in enumerate(items):
        if custom0 is not None and i >= custom0:
            n = i - custom0
            key = slots[n][0] if slots[n] else f"custom{n + 1}"
        else:
            key = HP_KEYS.get(name)
        out.append((key, True if key is None else hp_file(key) is not None))
    return out


# a DSP-mode stream bind (the format code follows the stream's rate, bits and channels)
DSP_PATH_LOG = (r"switching the running stream to DSP mode"
                r"|router chip stream format (0x[0-9a-f]{2} ok|now 0x)")
# what undoes it: a DSP (re)load (driver reload, wake) or Direct Mode on
DSP_PATH_RESET_LOG = r"DSP firmware downloaded and running|Direct Mode on"


def dsp_path_ready():
    """True if the DSP's output path is set up: a playback stream ran in DSP
    mode since the DSP last loaded and since Direct Mode was last switched
    on. The driver's mic monitor is silent until then. From the kernel log;
    None when it can't be read."""
    try:
        r = subprocess.run(["journalctl", "-k", "-b", "-q", "--no-pager", "-o", "cat",
                            "-g", f"{DSP_PATH_LOG}|{DSP_PATH_RESET_LOG}"],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode not in (0, 1):
        return None
    return dsp_path_from_log(r.stdout)


def dsp_path_from_log(text):
    """The latest of those kernel log lines says whether the path is up."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return bool(lines) and re.search(DSP_PATH_LOG, lines[-1]) is not None


def headphone_curves():
    """How many headphone curves are installed (0: the profiles stay off)."""
    for d in HP_DIRS:
        try:
            n = sum(1 for f in os.listdir(os.path.join(d, "creative-ae9", "hp")) if f.endswith(".bin"))
        except OSError:
            continue
        if n:
            return n
    return 0


def speaker_level(ch):
    return f"Speaker Level {ch} Volume"           # dB, -12..+12


def speaker_distance(ch):
    return f"Speaker Distance {ch}"               # cm, 0..500: delays that speaker


def fx_switch(effect):
    return f"FX {effect} Switch"


def fx_level(effect):
    return f"FX {effect} Volume"


def eq_band(band):
    return f"EQ {band} Volume"


EQ_CONTROLS = [EQ_PREGAIN] + [eq_band(b) for b in EQ_BANDS]

MODULE_PARAMS = ae9.MODULE_PARAMS


# --- volume curves ------------------------------------------------------------
# The desktop (PipeWire) maps its slider cubically: amplitude = pct^3. Using the
# same curve keeps our slider at the same spot as the KDE/GNOME one.
def master_raw_to_pct(raw):
    if raw <= 0:
        return 0.0
    db = (raw - 254) / 2.0
    return min(1.0, 10 ** (db / 60.0))


def master_pct_to_raw(pct):
    if pct <= 0.0005:
        return 0
    db = 60.0 * math.log10(pct)
    return max(0, min(254, int(round(254 + db * 2))))


def master_raw_to_db(raw):
    return (raw - 254) / 2.0


def mic_raw_to_db(raw):
    return raw - 90  # 99 -> +9 dB


class AE9(QObject):
    changed = Signal(str)         # control name whose value changed
    info_changed = Signal(str)    # control name whose active state changed
    connection_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mixer = None
        self.card_index = -1
        self.longname = ""
        self._notifier = None
        self._retry = QTimer(self, interval=3000)
        self._retry.timeout.connect(self._try_open)
        self._try_open()

    # --- connection ---------------------------------------------------------
    @property
    def present(self):
        return self.mixer is not None

    def _try_open(self):
        idx = alsa.find_card("AE9", "Sound Blaster AE-9", "AE-9")
        if idx < 0:
            self._retry.start()
            return
        try:
            self.mixer = alsa.Mixer(idx)
        except OSError:
            self._retry.start()
            return
        self._retry.stop()
        self.card_index = idx
        self.longname = alsa.card_longname(idx)
        fd = self.mixer.subscribe()
        self._notifier = QSocketNotifier(fd, QSocketNotifier.Read, self)
        self._notifier.activated.connect(self._on_events)
        self.connection_changed.emit(True)

    def _lost(self):
        if self._notifier:
            self._notifier.setEnabled(False)
            self._notifier.deleteLater()
            self._notifier = None
        if self.mixer:
            self.mixer.close()
        self.mixer = None
        self.connection_changed.emit(False)
        self._retry.start()

    def _on_events(self, *_):
        if not self.mixer:
            return
        try:
            events = self.mixer.read_events()
        except OSError:
            self._lost()
            return
        if not events:
            # readable but nothing to read: card went away
            try:
                self.mixer.get(MASTER)
            except (OSError, KeyError):
                self._lost()
            return
        for numid, mask in events:
            if mask == alsa.EVENT_MASK_REMOVE:
                self._lost()
                return
            if mask & alsa.EVENT_MASK_ADD:
                self.mixer.rescan()
            c = self.mixer.by_numid.get(numid)
            if not c:
                continue
            if mask & alsa.EVENT_MASK_INFO:
                self.mixer.refresh_info(numid)
                self.info_changed.emit(c.name)
            if mask & alsa.EVENT_MASK_VALUE:
                self.changed.emit(c.name)

    # --- generic access ----------------------------------------------------------
    def _name(self, name):
        """The control's name on this driver: `name`, or an older name for it."""
        if self.mixer and not self.mixer.has(name):
            for old in ALIASES.get(name, ()):
                if self.mixer.has(old):
                    return old
        return name

    def has(self, name):
        return bool(self.mixer and self.mixer.has(self._name(name)))

    def get(self, name, default=None):
        name = self._name(name)
        if not self.has(name):
            return default
        try:
            return self.mixer.get(name)
        except OSError:
            return default

    def set(self, name, value, force=False):
        name = self._name(name)
        if not self.has(name):
            return False
        try:
            if isinstance(value, str):
                value = self.mixer.controls[name].items.index(value)
            if not force and self.mixer.get(name) == value:
                return True
            self.mixer.set(name, value)
            return True
        except OSError:
            return False

    def write(self, name, value):
        """Write a control and say why it failed: 0, or the error number
        (e.g. EBUSY: phantom power right after the card started)."""
        name = self._name(name)
        if not self.has(name):
            return errno.ENOENT
        try:
            self.mixer.set(name, value)
            return 0
        except OSError as e:
            return e.errno or errno.EIO

    def iec958(self, name):
        """An IEC958 control's 24 channel-status bytes, or None."""
        name = self._name(name)
        if not self.has(name):
            return None
        try:
            return self.mixer.get_iec958(name)
        except OSError:
            return None

    def passthrough(self):
        """Optical out sends non-audio (AC-3 / DTS): None without the control."""
        st = self.iec958(OPTICAL_IEC958)
        return None if st is None else bool(st[0] & IEC958_NONAUDIO)

    def clear_passthrough(self):
        """Back to PCM audio on optical out (a stuck passthrough)."""
        st = self.iec958(OPTICAL_IEC958)
        if st is None or not st[0] & IEC958_NONAUDIO:
            return True
        try:
            self.mixer.set_iec958(OPTICAL_IEC958, bytes([st[0] & ~IEC958_NONAUDIO]) + st[1:])
            return True
        except OSError:
            return False

    def writable(self, name):
        c = self.control(name)
        return bool(c and c.writable)

    def control(self, name):
        return self.mixer.controls.get(self._name(name)) if self.mixer else None

    def items(self, name):
        c = self.control(name)
        return list(c.items) if c else []

    def get_item(self, name):
        c = self.control(name)
        v = self.get(name)
        if c is None or v is None or v >= len(c.items):
            return None
        return c.items[v]

    def inactive(self, name):
        c = self.control(name)
        return bool(c and c.inactive)

    def all_controls(self):
        return list(self.mixer.controls.values()) if self.mixer else []

    # --- feature helpers --------------------------------------------------------
    @property
    def dsp_active(self):
        """True when audio runs through the DSP with SBX on (effects audible)."""
        return self.present and not self.get(DIRECT, True) and bool(self.get(SBX, False))

    def eq_db(self):
        """[pre-gain, 31Hz .. 16kHz] in dB."""
        return [(self.get(n, 12) or 0) - 12 for n in EQ_CONTROLS]

    def set_eq_db(self, values):
        for name, db in zip(EQ_CONTROLS, values):
            self.set(name, int(round(db)) + 12)

    def snapshot(self):
        """Everything an SBX profile stores."""
        return {
            "fx": {e: [bool(self.get(fx_switch(e), False)), int(self.get(fx_level(e), 50))] for e in EFFECTS},
            "sv_mode": self.get_item(SV_MODE) or "Normal",
            "eq_on": bool(self.get(EQ_ON, False)),
            "eq_preset": self.get_item(EQ_PRESET),
            "eq": self.eq_db(),
        }

    def apply(self, profile, include_eq=True):
        for e, (on, lvl) in profile.get("fx", {}).items():
            self.set(fx_level(e), int(lvl))
            self.set(fx_switch(e), bool(on))
        if profile.get("sv_mode") in self.items(SV_MODE):
            self.set(SV_MODE, profile["sv_mode"])
        if include_eq and "eq" in profile:
            preset = profile.get("eq_preset")
            if preset in self.items(EQ_PRESET):
                # The preset carries 0.1 dB values the band controls can't; only
                # write bands when the profile edited them.
                self.set(EQ_PRESET, preset, force=True)
            if any(abs(a - b) > 0.55 for a, b in zip(self.eq_db(), profile["eq"])):
                self.set_eq_db(profile["eq"])
            self.set(EQ_ON, bool(profile.get("eq_on", True)))


def module_param(name):
    return ae9.module_param(name)


def has_playback_pcm(device, card_id="AE9"):
    """The driver offers playback device `device` (4 = the separate optical out)."""
    return os.path.exists(f"/proc/asound/{card_id}/pcm{device}p")


def has_capture_pcm(device, card_id="AE9"):
    """The driver offers capture device `device` (1 = optical in, 2 = What U Hear,
    3 = head unit rear RCA)."""
    return ae9.has_capture_pcm(device, card_id)


def module_version():
    return ae9.module_version()


def driver_at_least(*want):
    """True if the loaded driver's version is want (e.g. 0, 7, 0) or newer."""
    return ae9.driver_at_least(*want, version=module_version() or "")


def surround_96k_stable():
    """Driver 0.7.0 fixed 5.1 at 96 kHz and turned it on by default
    (surround_96k=1). Before that the option was an unstable experiment."""
    return driver_at_least(0, 7, 0) and module_param("surround_96k") == "1"


def surround_max():
    """The highest rate 5.1 plays at: 192 kHz with the driver's surround_192k
    option on (0.9.4+), 96 kHz with a stable surround_96k (0.7.0+), else 48."""
    if not surround_96k_stable():
        return 48000
    return 192000 if module_param("surround_192k") == "1" else 96000


def dsp_96k():
    """DSP mode (Direct Mode off) takes 96 kHz as well as 48 (driver 0.9.4+,
    its dsp_96k option, on by default)."""
    return module_param("dsp_96k") in ("Y", "1")


def wuh_96k():
    """What U Hear can record at 96 kHz as well as 48 (driver 0.9.5+, its
    wuh_96k option, on by default)."""
    return module_param("wuh_96k") in ("Y", "1")


def plays_176k4():
    """The driver plays 176.4 kHz (0.9.7+, its pcm_176k4 option)."""
    return module_param("pcm_176k4") in ("Y", "1")


def plays_cd_rates():
    """The driver can play 44.1 and 88.2 kHz (0.9.4+, its dac_441 option)."""
    return module_param("dac_441") is not None


def restarts_stream_on_direct():
    """Drivers with surround_192k (0.9.4+) restart a playing stream when
    Direct Mode turns on, so no pause and play is needed."""
    return module_param("surround_192k") is not None
