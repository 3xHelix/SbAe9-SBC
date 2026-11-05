# Changelog

Sound Blaster Command for Linux: the UI for the Creative Sound Blaster AE-9
driver ([SbAe9-Drv](https://github.com/3xHelix/SbAe9-Drv)).

## 0.5.0 (2026-11-05)

Catching up with [SbAe9-Drv v0.7.0](https://github.com/3xHelix/SbAe9-Drv/releases/tag/v0.7.0),
which slayed the dragons: 5.1 at 96 kHz plays clean now, so the app treats
it like any other rate. Plus a few comfort things: shrink the whole app
down, lose the window frame, and decide whether your last rate comes back
when the app starts. Older drivers still work, same as before.

### Added

- **UI scale** (Settings → Appearance): a slider from 70% to 150% that
  shrinks or grows the whole app, dials, text and all, so it sits nicely in
  a smaller window. Hit Apply and the window pops back up at the new size
  in about a second. `--scale 80` tries a size for one launch without
  saving it.
- **No more window frame.** The app wears its own title bar now: grab the
  AE-9 header to move it, double-click it to maximize, drag any edge to
  resize, and there's a little minimize and close up in the corner (close
  goes red, so you know). Like the frame back? Settings → Appearance, one
  checkbox.
- **"Reload the last sample rate when the app starts"** (Settings → App).
  On (as before): your last pick comes back at launch. Off: the app opens,
  shows whatever PipeWire is running and touches nothing until you pick a
  rate. Your last pick is still remembered for when you turn it back on.
- A test suite (`python3 -m unittest discover -s tests`): ~70 tests, a few
  seconds, no card needed. It runs against a fake AE-9 and a fake PipeWire,
  so it never touches your card, your PipeWire or your settings.
- `tools/screenshots.py` regenerates the README screenshots in any palette.

### Changed

- **5.1 at 96 kHz, for real** (driver v0.7.0 or newer, with its
  `surround_96k` option on, which is the default): the picker offers a plain
  "96 kHz" on a 5.1 stream, it comes back at start like any other pick, and
  a higher pick (192 / 384 kHz) lands on 96 kHz in 5.1 instead of dropping
  to 48. DSP mode still runs at 48 kHz. On older drivers it stays the
  "here be dragons" option it was.
- README screenshots redone in the Helix palette, on a 5.1 setup.

### Fixed

- Playback: a long speaker description (5.1) could push the bit-depth box
  off the edge of the window. It wraps now.
- Recording: the Listen switch had no gap before its text.

## 0.4.1 (2026-11-04)

The driver caught up. [SbAe9-Drv v0.6.8](https://github.com/3xHelix/SbAe9-Drv/releases/tag/v0.6.8)
is out, and it's the one 0.4.0 was waiting for: 48–384 kHz out of the box,
the "PCM Bit Depth" control (so the 24 / 32-bit picker finally does
something), 5.1 locked to a sane 48 kHz with the `surround_96k` dragons
behind a door, and the EQ presets in a sensible order. Get v0.6.8 or newer
for all of that; older drivers still work, just with less to pick from.

### Changed

- "Applying changes…" gives the card one more second per change: 5 s after
  Direct Mode or a stereo / 5.1 switch, 4 s after speakers, rate or bit
  depth (11 s at most). The card asked nicely.
- EQ presets: the list follows the driver, so with v0.6.8 it's music A-Z
  with the game presets (Project CARS, Racing, Rocket League, RPG) under
  their own "Games" heading at the bottom, like on Windows. Older drivers
  keep their old order. Presets are kept by name, so nothing gets mixed up
  when the order changes.
- README: which features need v0.6.8 (rate picker in full, bit depth,
  preset order).
- README: Helvum gets a mention as a handy companion for seeing where your
  audio actually goes.

## 0.4.0 (2026-11-04)

The "slow down, cowboy" release. Sample rate and bit depth get a proper
picker, and the app now gives the card a moment to breathe between big
changes, because tonight's testing showed it really, really wants one.

Works with [SbAe9-Drv v0.6.7](https://github.com/3xHelix/SbAe9-Drv/releases/tag/v0.6.7).
The bit-depth picker and the experimental 5.1 at 96 kHz light up with the
next driver release (it adds the "PCM Bit Depth" control and the
`surround_96k` option); until then the depth shows greyed out.

### Added

- **Sample rate + bit depth picker** (Playback → Audio Quality): Automatic,
  48, 96, 192 or 384 kHz, and 24- or 32-bit. Picking a depth reopens the card
  so it kicks in right away. On older drivers the depth shows what the
  driver's `pcm_bits` option is set to, greyed out.
- **"Applying changes…"**, like Creative's own app. Direct Mode, speaker
  layout, stereo / 5.1 stream, sample rate and bit depth now go one at a
  time, each with a few seconds to settle (3-4 s, done early once the card
  is back, never more than 10 s), behind a notice that keeps you from
  clicking the next one too soon. Several at once (say 5.1 plus the rate it
  needs) go in a row inside one notice. Turns out this card doesn't do a 180
  on a dime: fast bursts of changes were behind every stuck-DSP and
  stuttering-stream moment in testing. Effects, sliders and the EQ aren't
  slowed down.
- Shows what the card is actually running right now, e.g. "384 kHz · 32-bit ·
  stereo".

### Changed

- Rates the card can't take right now are greyed out, with the reason:
  DSP mode runs at 48 kHz, and so does 5.1. Switch Direct Mode
  off while forced to 384 kHz and the app drops PipeWire to 48 kHz; switch it
  back on and your 384 kHz comes back. Same for leaving 5.1.
- 5.1 at 96 kHz is in there, but you have to go looking for it: with the
  driver's `surround_96k` option set to 1, the picker offers "96 kHz
  (experimental: here be dragons)" on a 5.1 stream. It stutters more and
  more as it plays, so the app never picks or restores it on its own. Leave
  5.1 or restart the app and you're back at a sensible 48 kHz.
- The app only touches PipeWire's rate when you pick one in it. Set a rate
  or quantum by hand (`pw-metadata`) and it stays put; the picker just shows
  "PipeWire is set to … outside the app". On Automatic the app leaves
  PipeWire completely alone.
- The PipeWire drop-in (`90-sbae9-sbc-rates.conf`) always lists all four
  rates. Caps like DSP mode's 48 kHz only go into the live forced rate, so
  PipeWire never gets stuck opening the card at 48 kHz and resampling.
- 192 and 384 kHz get a bigger PipeWire buffer (quantum 1024 / 2048), so 384
  kHz stops crackling. 48/96 kHz and Automatic leave PipeWire's own buffer
  alone.

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
