# Changelog

Sound Blaster Command for Linux: the UI for the Creative Sound Blaster AE-9
driver ([SbAe9-Drv](https://github.com/3xHelix/SbAe9-Drv)).

## Unreleased

- **Second colour palette, "Helix"**: blue-black and violet with coral-orange
  and amber accents and a mint EQ curve. Switch between it and the original
  "Command" palette under Settings → Appearance; the choice is remembered.
- **Third palette, "Albino"**: a light theme in off-white, cream, blush and
  peach with a coral accent.
- **Fourth palette, "Wololo"**: a monk's royal-blue robe and white cloth with
  sun-gold controls, a grass-green EQ curve and a staff-brown touch.
- `--palette NAME` starts the app in a palette for one launch; `--version`.

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
