# Changelog

Sound Blaster Command for Linux: the UI for the Creative Sound Blaster AE-9
driver ([SbAe9-Drv](https://github.com/3xHelix/SbAe9-Drv)).

## 0.3.0 (2026-11-04)

5.1 has entered the building. Goes hand in hand with
[SbAe9-Drv v0.6.7](https://github.com/3xHelix/SbAe9-Drv/releases/tag/v0.6.7),
which taught the card to do surround. You need that driver with its PipeWire
profile set installed
([setup step 4](https://github.com/3xHelix/SbAe9-Drv#4-pipewire-profiles-stereo-and-51))
for the 5.1 bits; on an older driver the app carries on in stereo like
nothing happened.

### Added

- **5.1 stream switching.** Pick 4.0, 4.1 or 5.1 speakers and the app flips
  PipeWire over to the 5.1 profile; pick 2.0 or 2.1 and it goes back to
  stereo. Your mic input comes along for the ride. A new **Stereo stream /
  5.1 stream** box shows which one you're on, keeps up when you change it in
  KDE's sound settings, and still works in Direct Mode. The app only
  switches when *you* pick something, so it and the driver don't argue. It
  stays hidden without the driver's profile set, and keeps its hands off
  "pro-audio" or "off" if you picked those yourself.
- **Speaker test that talks.** Test now says "Front Left", "Front Center",
  "Rear Right"… out of each speaker in turn, using the voice files from
  alsa-utils (not bundled here). The sub gets a burst of noise, because subs
  don't talk. Click a speaker in the diagram to test just that one. No
  alsa-utils? You get a tone instead.
- The speaker diagram draws 4.0, 4.1 and 5.1 layouts, and the Mixer grows a
  slider for each of the six channels on a 5.1 stream.

### Changed

- "This won't be heard because Direct Mode / SBX / Scout Mode…" notices,
  and the "card not found" bar, are now warning red with a red button. Same
  red in every palette, so a warning always looks like a warning.
- The bottom bar says "SBX | Off" instead of "SBX | SBX off". We heard you
  the first time.

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
