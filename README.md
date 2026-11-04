# Sound Blaster Command for Linux (AE-9)

![Sound Blaster Command for Linux: the SBX Profile page](docs/screenshot.png)

A desktop control panel for the Creative Sound Blaster AE-9, styled after
Creative's *Sound Blaster Command*. This is the UI half of
[SbAe9-Drv](https://github.com/3xHelix/SbAe9-Drv): it drives the card through that
driver (`snd-hda-codec-creative-ae9`, 0.6.x) and
works with the normal Linux audio stack: apps play to the AE-9 through
PipeWire as usual. The effects run on the card's own DSP, and this app
switches and adjusts them.

## What it controls

| Page | What it does | How |
|---|---|---|
| **SBX Profile** | SBX on/off; Surround, Crystalizer, Bass, Smart Volume (Night/Normal/Loud), Dialog+; built-in and personal profiles | card DSP (ALSA `SBX Switch`, `FX …`) |
| **Equalizer** | 10-band EQ + pre-gain, Creative's 20 presets, your own saved curves | card DSP (`EQ …`) |
| **Playback** | Speakers / headphones, speaker config (2.0/2.1), Direct Mode, DAC filter, sample rate, default device, left/right test tone | ALSA + PipeWire |
| **Recording** | XLR mic level, XLR gain (0/+10/+20 dB), live input meter, mute, "listen to mic", default device | ALSA + PipeWire |
| **Scout Mode** | Creative's Scout Mode (footstep EQ + Smart Volume) | card DSP |
| **Mixer** | Output volume (same as the head-unit knob), mute, per-channel levels (Front Left / Right, …), mic level | ALSA + PipeWire |
| **Settings** | Colour palette (Command, Helix, Albino or Wololo), driver/device info, every ALSA control (including inactive ones), reset | ALSA |

## Screenshots

<table>
  <tr>
    <td><img src="docs/equalizer.png" alt="Equalizer page"><br><sub>Equalizer</sub></td>
    <td><img src="docs/playback.png" alt="Playback page"><br><sub>Playback</sub></td>
  </tr>
  <tr>
    <td><img src="docs/recording.png" alt="Recording page"><br><sub>Recording</sub></td>
    <td><img src="docs/mixer.png" alt="Mixer page"><br><sub>Mixer</sub></td>
  </tr>
</table>

Volume, mute and output changes made with the head-unit knob, `alsamixer` or the
desktop slider show up in the app immediately (it listens to ALSA control events).

**Direct Mode on** = audio goes straight to the DAC at the source's rate (up
to 384 kHz) with no effects. **Direct Mode off** = audio goes through the DSP
at 96 kHz, and SBX, the EQ and Scout Mode are heard. The app keeps your
effect settings either way.

Not available on Linux (yet): Super X-Fi, Dolby Digital Live / DTS encoding,
S/PDIF, surround (5.1/7.1) outputs, and 44.1 kHz-family playback. The driver
doesn't support these yet.

## Requirements

- The AE-9 driver loaded ([SbAe9-Drv](https://github.com/3xHelix/SbAe9-Drv)), with the "Stereo Output + Stereo
  Input" PipeWire profile.
- Python 3, PySide6 (`sudo dnf install python3-pyside6`), PipeWire tools
  (`pw-dump`, `wpctl`, `pw-metadata`, `pw-play`, `pw-record`, `pw-loopback`),
  and `libasound`. All of these come with Fedora's standard desktop install.

## Run / install

```sh
./sbae9-sbc            # run from this folder
./install.sh           # adds a menu entry + ~/.local/bin/sbae9-sbc
./sbae9-sbc --palette helix   # one launch in the Helix palette (saved choice unchanged)
```

## Files it writes

- `~/.config/sbae9-sbc/settings.json` — your profiles, EQ presets, last page.
- `~/.config/pipewire/pipewire.conf.d/90-sbae9-sbc-rates.conf` — only if you
  pick an *Audio Quality* setting (PipeWire's allowed/forced sample rate).
  Delete it to go back to PipeWire's defaults.

## Layout

```
sbcommand/
  alsa.py       ctypes binding to alsa-lib's control API (incl. events)
  card.py       the AE-9 as a Qt object: named controls, volume curves, profiles
  pipewire.py   nodes, default device, rates, test tone, mic monitor, level meter
  profiles.py   built-in SBX profiles and the driver's EQ preset tables
  pages.py      one class per page
  widgets.py    dial, toggle switch, EQ graph, profile carousel, meters
  window.py     sidebar, page stack, bottom bar
  theme.py      colors + Qt style sheet
```

## License

GPL-2.0-only, same as the driver. See [LICENSE](LICENSE).

## Disclaimer

Not affiliated with Creative. "Sound Blaster", "SBX" and related names are
Creative Technology's trademarks; the look is a nod to their app, with no
Creative code or artwork included.
