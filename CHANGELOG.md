# Changelog

Sound Blaster Command for Linux: the UI for the Creative Sound Blaster AE-9
driver ([SbAe9-Drv](https://github.com/3xHelix/SbAe9-Drv)).

## 0.2.1 (2026-11-04)

Mixer round: independent Left/Right volume, like the desktop's own mixer.
Same driver as before (0.6.x).

### Changed

- **Mixer**: the Left/Right balance slider is replaced by one slider per
  channel (Front Left, Front Right, and more on surround outputs), on the same
  percent scale as the desktop's volume control. **Link channels** moves them
  together; **Equalise** sets them all to the loudest.
- Channel levels are set on the card's output route, the way the desktop
  mixer does it: the card's hardware Master follows the loudest channel and
  only the quieter ones are trimmed in software, so one side can be quiet
  without pulling the whole output down.

## 0.2.0 (2026-11-04)

Colour round: three new palettes to go with the original, and a flag to
pick one from the command line. Same driver as before (0.6.x).

### Added

- **Palettes**, switched under Settings → Appearance (remembered between
  launches):
  - **Helix**: blue-black and violet with coral-orange and amber accents and
    a mint EQ curve.
  - **Albino**: a light theme in off-white, cream, blush and peach with a
    coral accent.
  - **Wololo**: a monk's royal-blue robe and white cloth, sun-gold controls,
    a grass-green EQ curve and a staff-brown touch.
- `--palette NAME` starts the app in a palette for one launch without
  changing the saved one; `--version` and `--help`.

### Changed

- The built-in SBX profiles are labelled "Built-in" instead of
  "The Sound Blaster Team"; they're this app's presets, not Creative's.
- README: screenshots of the main pages.

## 0.1.0 (2026-11-04)

First release. Needs driver 0.6.x (the one with SBX on the card's DSP).

- **SBX Profile:** SBX switch, Surround / Crystalizer / Bass / Smart Volume
  (Night, Normal, Loud) / Dialog+ dials, built-in profiles (Default, Gaming,
  Movie, Music, Night) and your own.
- **Equalizer:** 10 bands + pre-gain on the card's DSP, Creative's 20 presets,
  saved custom curves.
- **Playback:** speakers / headphones, 2.0 / 2.1, Direct Mode, DAC filter,
  sample rate (48-384 kHz via PipeWire), default device, L/R test tone.
- **Recording:** XLR mic level and gain, live input meter, mute, listen to mic.
- **Scout Mode**, **Mixer** (volume, mute, balance) and **Settings** (driver
  info, every ALSA control including inactive ones).
- Follows the head-unit knob, alsamixer and the desktop slider live (ALSA
  control events).
