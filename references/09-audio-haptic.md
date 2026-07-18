# 09 — Audio, MIDI, Sequencer & Haptic Feedback

This reference covers four QMK features that produce non-visual output: **Audio** (piezo/speaker beeps, songs, music mode, clicky), **MIDI** (USB-MIDI device with notes/CC), **Sequencer** (experimental step sequencer built on MIDI), and **Haptic Feedback** (drv2605l / solenoid motors).

Each feature is self-contained but they share infrastructure: Audio and Haptic both hook the key-processing chain; MIDI and Sequencer both present USB descriptors; Audio/MIDI/Haptic all participate in the process_record pipeline (see `01-architecture.md`). Cross-references at the end of each section.

---

## 1. Audio

### Summary
Drive one or more piezo/speakers from a spare GPIO pin (or DAC channel) to make the keyboard beep: layer-change chimes, boot/startup songs, a "click" per keypress, or a chromatic-scale "music mode" you play across the matrix. Audio is the foundation for **music mode**, **audio clicky**, the **song/note macros**, and can also generate MIDI notes.

### Enable it

**Data-driven (preferred for ARM/new boards):** in `info.json` enable the feature and pick a driver:
```json
{
  "features": { "audio": true },
  "audio": {
    "driver": "dac_additive",
    "pins": ["A5"]
  }
}
```

**Legacy (still required for AVR and many knobs):** in `rules.mk`:
```make
AUDIO_ENABLE = yes
# ARM only — pick the driver. AVR is always pwm_hardware (auto-selected).
AUDIO_DRIVER = dac_additive   # or dac_basic | pwm_software | pwm_hardware
```

The `AUDIO_DRIVER` setting is **ARM-only**. On AVR (ATmega32U4) the driver is always `pwm_hardware` and is auto-configured — you do **not** set `AUDIO_DRIVER` on AVR.

### Keycodes

| Keycode | Alias | Description |
|---|---|---|
| `QK_AUDIO_ON` | `AU_ON` | Turn the whole Audio feature on |
| `QK_AUDIO_OFF` | `AU_OFF` | Turn the whole Audio feature off |
| `QK_AUDIO_TOGGLE` | `AU_TOGG` | Toggle Audio on/off |
| `QK_AUDIO_VOICE_NEXT` | `AU_NEXT` | Cycle through audio "voice"/effect presets |
| `QK_AUDIO_VOICE_PREVIOUS` | `AU_PREV` | Cycle audio voices in reverse |
| `QK_AUDIO_CLICKY_TOGGLE` | `CK_TOGG` | Toggle audio-clicky mode |
| `QK_AUDIO_CLICKY_ON` | `CK_ON` | Turn audio-clicky on |
| `QK_AUDIO_CLICKY_OFF` | `CK_OFF` | Turn audio-clicky off |
| `QK_AUDIO_CLICKY_UP` | `CK_UP` | Increase click frequency (× minor-third default) |
| `QK_AUDIO_CLICKY_DOWN` | `CK_DOWN` | Decrease click frequency |
| `QK_AUDIO_CLICKY_RESET` | `CK_RST` | Reset click frequency to default |
| `QK_MUSIC_ON` | `MU_ON` | Turn Music Mode on |
| `QK_MUSIC_OFF` | `MU_OFF` | Turn Music Mode off |
| `QK_MUSIC_TOGGLE` | `MU_TOGG` | Toggle Music Mode |
| `QK_MUSIC_MODE_NEXT` | `MU_NEXT` | Cycle music modes (chromatic/guitar/violin/major) |

> ⚠️ `AU_OFF` disables **everything** audio: feedback, clicky, music mode, songs — completely.

### Audio drivers (ARM) — the matrix you must get right

There are four ARM drivers; availability is MCU/peripheral-dependent. This is the central footgun of the Audio feature — see `13-drivers-lowlevel.md` ("Audio driver") for the canonical hardware-routing table and ChibiOS `halconf.h`/`mcuconf.h` changes each driver needs.

| Driver | `AUDIO_DRIVER` | Output | Simultaneous tones | When to use |
|---|---|---|---|---|
| `dac_basic` | `dac_basic` | Square wave on DAC pin (A4 and/or A5) | **1 per channel** (2 if both channels wired to 2 speakers) | Default ARM driver; simple, square-wave only |
| `dac_additive` | `dac_additive` | Additive waveform synthesis (sine/triangle/trapezoid/square or custom) | **Multiple** (the only driver that does true polyphony) | Best quality / chords in Music Mode; needs only TIM6 |
| `pwm_software` | `pwm_software` | PWM via software pin-toggling in a timer callback | 1 | No usable DAC (e.g. STM32F1xx), only one speaker |
| `pwm_hardware` | `pwm_hardware` | PWM driven directly by hardware timer/alt-function pin | 1 | STM32F1xx (hardware PWM but no DAC); also the **forced AVR** driver |

**Pin config (`config.h`):**
```c
// Primary speaker (one of these, mandatory)
#define AUDIO_PIN C6        // AVR: C4/C5/C6 (Timer3) or B5/B6/B7 (Timer1)
// Optional second speaker or second lead of one speaker
#define AUDIO_PIN_ALT B7
// Drive ONE piezo from TWO pins (red=AUDIO_PIN, black=AUDIO_PIN_ALT)
#define AUDIO_PIN_ALT_AS_NEGATIVE
```
- **AVR:** primary on C4/C5/C6 (Timer3) **or** B5/B6/B7 (Timer1). Second speaker (`AUDIO_PIN_ALT`) must be on the *other* timer's pin (B5/B6/B7). Up to 2 simultaneous tones on AVR.
- **ARM dac_basic/dac_additive:** A4 (DAC1/TIM6) and/or A5 (DAC2/TIM7). dac_additive supports one piezo across A4+A5 with `AUDIO_PIN_ALT_AS_NEGATIVE` (Proton-C default: A5 + A4-as-negative).
- **ARM pwm_software:** `AUDIO_PIN` can be any pin; toggled in software from a timer callback.
- **ARM pwm_hardware:** `AUDIO_PIN A8`, `AUDIO_PWM_DRIVER PWMD1`, `AUDIO_PWM_CHANNEL 1` (TIM1_CH1=PA8 on F103). On STM32F2+ also set `AUDIO_PWM_PAL_MODE 42` to the correct alt-function number, and optionally `AUDIO_PWM_COMPLEMENTARY_OUTPUT` for TIMx_CHyN.

**Validated MCU × driver matrix (from `docs/drivers/audio.md`):**

| MCU | dac_basic | dac_additive | pwm_hardware | pwm_software |
|---|:--:|:--:|:--:|:--:|
| ATmega32U4 | n/a | n/a | ✓ (forced) | n/a |
| RP2040 | ✗ | ✗ | ✓ | ? |
| STM32F103C8 (bluepill) | ✗ | ✗ | ✓ | ✓ |
| STM32F303CCT6 (proton-c) | ✓ | ✓ | ? | ✓ |
| STM32F405VG | ✓ | ✓ | ✓ | ✓ |
| STM32L0xx | ✗ (no TIM8) | ? | ? | ? |

`✓` tested/works · `n/a` does not apply · `✗` MCU lacks the peripheral · `?` untested.

**DAC quality presets (dac drivers)** — define exactly one (default `AUDIO_DAC_QUALITY_SANE_MINIMUM`). Each trades sample rate / polyphony / buffer size:

| Define | Sample Rate | Simultaneous tones | Buffer size |
|---|---|---|---|
| `AUDIO_DAC_QUALITY_VERY_LOW` | 11025 Hz | 8 | 64 |
| `AUDIO_DAC_QUALITY_LOW` | 22050 Hz | 4 | 128 |
| `AUDIO_DAC_QUALITY_HIGH` | 44100 Hz | 2 | 256 |
| `AUDIO_DAC_QUALITY_VERY_HIGH` | 88200 Hz | 1 | 256 |
| `AUDIO_DAC_QUALITY_SANE_MINIMUM` *(default)* | 16384 Hz | 8 | 64 |

### Configuration knobs (config.h)

| Define / key | Type | Default | Meaning |
|---|---|---|---|
| `AUDIO_PIN` | pin | *undefined* | Speaker output pin (primary) |
| `AUDIO_PIN_ALT` | pin | *undefined* | Second speaker, or second lead of one speaker |
| `AUDIO_PIN_ALT_AS_NEGATIVE` | flag | *undef* | Treat `AUDIO_PIN_ALT` as the negative lead of a single piezo |
| `AUDIO_INIT_DELAY` | flag | *undef* | Delay startup song for USB-enumeration timing issues |
| `AUDIO_ENABLE_TONE_MULTIPLEXING` | flag | *undef* | Time-slice multiple active tones through limited speakers (for non-DAC hardware doing chords) |
| `AUDIO_TONE_MULTIPLEXING_RATE_DEFAULT` | int | `0` (off; try `4`) | Multiplex cycling rate — lower = higher CPU load |
| `AUDIO_POWER_CONTROL_PIN` | pin | *undef* | Pin to enable/cut speaker power (e.g. PAM8302 amp) |
| `AUDIO_POWER_CONTROL_PIN_ON_STATE` | 0/1 | `1` | State of power-control pin when audio is "on" |
| `AUDIO_STATE_TIMER` | GPTD* | `GPTD8` (basic) / `GPTD8` (sw) | Override the audio state timer |
| `AUDIO_DAC_SAMPLE_MAX` | uint16 | `4095U` (12-bit) | Max DAC sample value → volume. **Only affects non-precomputed samples** (i.e. `WAVEFORM_SQUARE`) |
| `AUDIO_DAC_OFF_VALUE` | uint16 | `SAMPLE_MAX/2` | DAC idle value (set to 0 or `SAMPLE_MAX` for some setups) |
| `AUDIO_DAC_SAMPLE_RATE` / `_MAX_SIMULTANEOUS_TONES` / `_BUFFER_SIZE` | uint | preset-derived | Override individual DAC quality params |
| `AUDIO_DAC_SAMPLE_WAVEFORM_SINE` | flag | *(sine is default)* | dac_additive waveform select (pick one) |
| `AUDIO_DAC_SAMPLE_WAVEFORM_TRIANGLE` | flag | — | dac_additive waveform |
| `AUDIO_DAC_SAMPLE_WAVEFORM_TRAPEZOID` | flag | — | dac_additive waveform |
| `AUDIO_DAC_SAMPLE_WAVEFORM_SQUARE` | flag | — | dac_additive waveform |
| `AUDIO_VOICES` | flag | *undef* | Enable "voices"/effects (timbre presets) |
| `AUDIO_VOICE_DEFAULT` | int | — | Select default voice (see `quantum/audio/voices.h`) |
| `TEMPO_DEFAULT` | uint8 (bpm) | `120` | Initial song playback tempo |
| `PITCH_STANDARD_A` | float (Hz) | `440.0f` | Reference pitch for note-frequency math (music mode) |
| `NO_MUSIC_MODE` | flag | *undef* | Compile out Music Mode to save flash |
| `MUSIC_MASK` | expr | `keycode < 0xFF` | Which keycodes become notes in music mode (⚠️ `keycode != KC_NO` traps you in music mode!) |

### Songs / notes / rests — the SONG macro system

Predefined songs play automatically on events. Override any in `config.h`:

| Song define | Default sound | Triggered by |
|---|---|---|
| `STARTUP_SONG` | `STARTUP_SOUND` | Keyboard boot (`audio.c`) |
| `GOODBYE_SONG` | `GOODBYE_SOUND` | `QK_BOOT` pressed (`quantum.c`) |
| `AG_NORM_SONG` | `AG_NORM_SOUND` | `AG_NORM` (`process_magic.c`) |
| `AG_SWAP_SONG` | `AG_SWAP_SOUND` | `AG_SWAP` (`process_magic.c`) |
| `CG_NORM_SONG` | `AG_NORM_SOUND` | `CG_NORM` (`process_magic.c`) |
| `CG_SWAP_SONG` | `AG_SWAP_SOUND` | `CG_SWAP` (`process_magic.c`) |
| `MUSIC_ON_SONG` / `MUSIC_OFF_SONG` | `MUSIC_ON/OFF_SOUND` | Music mode on/off (`process_music.c`) |
| `MIDI_ON_SONG` / `MIDI_OFF_SONG` | `MUSIC_ON/OFF_SOUND` | MIDI mode on/off (`process_music.c`) |
| `CHROMATIC/GUITAR/VIOLIN/MAJOR_SONG` | matching `_SOUND` | Music mode selection |
| `DEFAULT_LAYER_SONGS` | *undef* | Song array played on `set_single_persistent_default_layer()` |
| `SENDSTRING_BELL` | *undef* | Chime when `"\a"` (bell) char is sent via send_string |

**Note / rest / song macros** (see `quantum/audio/musical_notes.h` and `quantum/audio/song_list.h`):
- Notes: `NOTE(_note, _duration)` where `_note` is e.g. `C4`, `CSharp4`/`Db4`, `Rest`/`MUTE` and `_duration` is a note-length macro like `M_64TH` (1/64), `M_16TH` … `WHOLE`. Pitch math uses `PITCH_STANDARD_A`.
- Build a melody: `float my_song[][2] = SONG(NOTE_C4, EIGHTH_NOTE, NOTE_E4, QUARTER_NOTE);` — `SONG(...)` wraps a list of `(frequency, duration)` pairs.
- Play once: `PLAY_SONG(my_song);`  ·  Loop: `PLAY_LOOP(my_song);`  ·  Stop: `stop_all_notes();` (= `audio_stop_all()`).
- Define your own sounds in `user_song_list.h` in your keymap/userspace folder — auto-included, useful for copyrighted melodies.
- `PLAY_NOTE` / single tone: `play_note(frequency, v)` (legacy macro → `audio_play_tone`).

> Always wrap audio code in `#ifdef AUDIO_ENABLE ... #endif` so the build still works when audio is off.

### Tempo
Song speed is beats-per-minute; note lengths are relative to it. Default `120` bpm (`TEMPO_DEFAULT`). Runtime API:
```c
void audio_set_tempo(uint8_t tempo);
void audio_increase_tempo(uint8_t tempo_change);
void audio_decrease_tempo(uint8_t tempo_change);
```

### C API / callbacks (`quantum/audio/audio.h`)

| Signature | Purpose |
|---|---|
| `void PLAY_SONG(arr)` (macro) | Play a melody once → `audio_play_melody(&arr, len, false)` |
| `void PLAY_LOOP(arr)` (macro) | Play a melody looping → `audio_play_melody(&arr, len, true)` |
| `bool audio_is_playing_melody(void);` | Is a SONG currently playing? |
| `bool audio_is_playing_note(void);` | Is a single tone playing? |
| `void audio_stop_all(void);` | Stop everything (`stop_all_notes()`) |
| `void audio_play_tone(float freq);` | Play one tone (`play_note(f, v)`) |
| `void audio_stop_tone(float freq);` | Stop a tone (`stop_note(f)`) |
| `uint8_t audio_get_number_of_active_tones(void);` | Count active tones |
| `float audio_get_frequency(uint8_t idx);` | Raw frequency of tone `idx` (0=newest) |
| `float audio_get_processed_frequency(uint8_t idx);` | Post-effects frequency |
| `void audio_set_tempo(uint8_t tempo);` | Set bpm |
| `void audio_increase_tempo(uint8_t)/decrease_tempo(uint8_t);` | nudge bpm |
| `uint16_t audio_duration_to_ms(uint16_t)/audio_ms_to_duration(uint16_t);` | 64-parts-per-beat ↔ ms |
| `void audio_set_tone_multiplexing_rate(uint16_t rate);` | (needs `AUDIO_ENABLE_TONE_MULTIPLEXING`) |
| `void audio_enable_tone_multiplexing(void)/disable_…/increase_…/decrease_…(uint16_t);` | multiplex control |
| `void audio_startup(void)/audio_shutdown(void);` | Called by core on boot/`QK_BOOT` |
| `void audio_on_user(void)/audio_off_user(void);` | **Weak keymap hooks** — implement to react to AU_ON/AU_OFF |

Legacy aliases still defined: `is_audio_on`, `is_playing_notes`, `is_playing_note`, `stop_all_notes`, `stop_note`, `play_note`, `set_tempo`, `increase_tempo`, `decrease_tempo`, `set_timbre`.

### Music mode
Maps matrix columns→chromatic scale, rows→octaves. Best on ortholinear. Keycodes `< 0xFF` become notes and don't type (see `MUSIC_MASK`). Recording is **experimental** and memory-fragile; replug to recover.

- **Modes:** `CHROMATIC_MODE` (row=octave), `GUITAR_MODE` (row=+5 semitones), `VIOLIN_MODE` (row=+7), `MAJOR_MODE`.
- **In music mode these behave specially (don't pass through):** `LCTL`=start recording · `LALT`=stop · `LGUI`=play · `KC_UP`=speed up · `KC_DOWN`=slow down.
- **`music_mask_user(keycode)` / `music_mask_kb(keycode)`** (weak): return `false` to keep a keycode processed normally (not turned into a note).
- **`MUSIC_MAP`:** define in `config.h`, then provide `const uint8_t music_map[MATRIX_ROWS][MATRIX_COLS] = LAYOUT_ortho_4x12(...)` to remap notes per physical key for non-rectangular matrices (splits, Planck Rev6). Number bottom-left→right→up.

### Audio clicky
Per-key click sound, slightly randomized so rapid typing doesn't blur into one note. **Disabled by default** — `#define AUDIO_CLICKY` in `config.h`. Frequencies are floats (Hz).

| Define | Default | Meaning |
|---|---|---|
| `AUDIO_CLICKY_FREQ_DEFAULT` | `440.0f` | Starting click frequency |
| `AUDIO_CLICKY_FREQ_MIN` | `65.0f` | Lowest freq (under 60 is buggy) |
| `AUDIO_CLICKY_FREQ_MAX` | `1500.0f` | Highest freq |
| `AUDIO_CLICKY_FREQ_FACTOR` | `1.18921f` | UP/DOWN step (× = minor third) |
| `AUDIO_CLICKY_FREQ_RANDOMNESS` | `0.05f` | 0 = identical clicks, 1.0 = extreme 90s-typing effect |
| `AUDIO_CLICKY_DELAY_DURATION` | `1` | Note-duration units (1 = 1/16 of tempo). Raise to ~6–12 for loud switches. |

### Example
```c
// config.h
#define AUDIO_PIN C6          // AVR primary
#define AUDIO_PIN_ALT B7      // AVR secondary (other timer)
#define STARTUP_SONG SONG(STARTUP_SOUND)

// keymap.c
#include QMK_KEYBOARD_H
float layer_up_song[][2] = SONG(QWERTY_SOUND);

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case MY_LAYER:
            if (record->event.pressed) { layer_on(2); PLAY_SONG(layer_up_song); }
            return false;
    }
    return true;
}
```

### Behavior & ordering
- Audio keycodes (`AU_*`, `CK_*`, `MU_*`) are handled by their respective `process_*` handlers in the core key-processing chain (see `01-architecture.md`).
- Songs are advanced from a periodic timer/ISR (`audio_update_state`), not the main loop — long ISRs can starve matrix scanning on the additive driver.
- `audio_startup()`/`audio_shutdown()` are invoked by the core; `audio_on_user`/`audio_off_user` are the keymap extension points.

### Gotchas — Audio
- **AVR timer conflicts with backlight:** On ATmega32U4, Audio uses **Timer 1 and Timer 3**. Backlight (`BACKLIGHT_DRIVER = pwm`) also wants Timer 1 (and on some configs Timer 3). Enabling both on AVR is a classic conflict — the backlight timer PWM and audio PWM collide. This is the #1 AVR audio footgun; see `07-led-rgb-backlight.md` (backlight) and `13-drivers-lowlevel.md`. AVR has very few timers.
- **dac_basic only does 1 tone per channel** (square wave). For chords/polyphony use `dac_additive` (the only true-polyphony driver).
- **`AUDIO_DAC_SAMPLE_MAX` (volume) only works with `WAVEFORM_SQUARE`** because other waveforms use a hardcoded/precomputed sample buffer.
- **`AUDIO_DRIVER` is ARM-only.** Setting it on AVR is ignored; AVR is always `pwm_hardware`.
- **`MUSIC_MASK` set to `keycode != KC_NO` traps you in music mode** — you can no longer type `MU_OFF`. Requires replug.
- **Music-mode recording is experimental** and can corrupt state; unplug/replug to fix.
- **`AU_OFF` kills *all* audio** (feedback, clicky, music, songs) — not just beeps.
- dac_additive buffer size is a RAM/quality/CPU tradeoff — too large → matrix-scan pauses that drop fast taps; too small → excessive CPU load or freezes.
- Some pins are **powered during bootloader** and can keep a speaker/solenoid driven through flashing.
- `audio_on_user`/`audio_off_user` are the only sanctioned keymap hooks for on/off events; don't subclass the internal startup functions.

**See also:** `13-drivers-lowlevel.md` (audio driver hardware routing, ChibiOS halconf/mcuconf), `07-led-rgb-backlight.md` (AVR timer conflict with backlight), `01-architecture.md` (process_record chain).

---

## 2. MIDI

### Summary
Expose the keyboard as a **USB-MIDI device** and send Note On/Off, Control Change (CC), pitch bend, modulation, sustain, etc. to a host DAW/synth. Two tiers: **basic** (Note On/Off only) and **advanced** (octave/transpose/velocity/channel/modulation keycodes).

### Enable it

```make
# rules.mk
MIDI_ENABLE = yes
```
Then in `config.h` choose a tier:
```c
#define MIDI_BASIC       // note On/Off only — MI_OCTU/MI_OCTD etc. won't work
// or
#define MIDI_ADVANCED    // octave/transpose/velocity/channel/modulation/pitch-bend
```
(If neither is defined, advanced is the effective behavior for the note keycodes, but the convenience keycodes for octave/transpose/etc. require `MIDI_ADVANCED`.)

> ⚠️ **MIDI requires 2 USB endpoints** and may not work on V-USB (AVR ATmega328P/ATmega32A) controllers.

### Keycodes

**Note keycodes** — `QK_MIDI_NOTE_<NOTE>_<OCTAVE>`, octaves 0–5. Aliases use `MI_<note><octave>`:

| Note (per octave) | Aliases |
|---|---|
| C | `MI_C`, `MI_C1`…`MI_C5` (and `MI_C0`→ octave 0; bare `MI_C` = octave 0) |
| C♯/D♭ | `MI_Cs`/`MI_Db` (+octave suffix) |
| D | `MI_D` (+oct) |
| D♯/E♭ | `MI_Ds`/`MI_Eb` |
| E | `MI_E` |
| F | `MI_F` |
| F♯/G♭ | `MI_Fs`/`MI_Gb` |
| G | `MI_G` |
| G♯/A♭ | `MI_Gs`/`MI_Ab` |
| A | `MI_A` |
| A♯/B♭ | `MI_As`/`MI_Bb` |
| B | `MI_B` |

So the full set spans `MI_C`/`MI_C0` … `MI_B5` (each with sharps/flats), i.e. `QK_MIDI_NOTE_C_0` … `QK_MIDI_NOTE_B_5`.

**Octave** (sets absolute octave; **advanced only**): `MI_OCN2`(-2), `MI_OCN1`(-1), `MI_OC0`(0), `MI_OC1`…`MI_OC7` · `MI_OCTD`/`MI_OCTU` (relative down/up).

**Transpose** (semitones; advanced): `MI_TRN6`…`MI_TRN1` (-6…-1), `MI_TR0` (0), `MI_TR1`…`MI_TR6` (+1…+6) · `MI_TRSD`/`MI_TRSU`.

**Velocity** (advanced): `MI_VL0`…`MI_VL10` mapping to 0,12,25,38,51,64,76,89,102,114,127 · `MI_VELD`/`MI_VELU`.

**Channel** (advanced): `MI_CH1`…`MI_CH16` · `MI_CHND`/`MI_CHNU`.

**Control / performance (advanced):**

| Keycode | Alias | Description |
|---|---|---|
| `QK_MIDI_ON` / `OFF` / `TOGGLE` | `MI_ON`/`MI_OFF`/`MI_TOGG` | Enable/disable MIDI |
| `QK_MIDI_ALL_NOTES_OFF` | `MI_AOFF` | Stop all notes |
| `QK_MIDI_SUSTAIN` | `MI_SUST` | Sustain pedal (CC 64) |
| `QK_MIDI_PORTAMENTO` | `MI_PORT` | Portamento (CC 65) |
| `QK_MIDI_SOSTENUTO` | `MI_SOST` | Sostenuto (CC 66) |
| `QK_MIDI_SOFT` | `MI_SOFT` | Soft pedal (CC 67) |
| `QK_MIDI_LEGATO` | `MI_LEG` | Legato (CC 68) |
| `QK_MIDI_MODULATION` | `MI_MOD` | Modulation |
| `QK_MIDI_MODULATION_SPEED_DOWN`/`UP` | `MI_MODD`/`MI_MODU` | Modulation speed |
| `QK_MIDI_PITCH_BEND_DOWN`/`UP` | `MI_BNDD`/`MI_BNDU` | Pitch bend |

### The `midi_config` struct (not persisted to EEPROM)
```c
typedef struct {
    uint8_t octave;              // default 4 (corresponds to MI_OC2 display-wise; see below)
    int8_t  transpose;           // default 0
    uint8_t velocity;            // default 127
    uint8_t channel;             // default 0  (MIDI channel 1)
    uint8_t modulation_interval; // default 8
} midi_config_t;
```

| Field | Default | Notes |
|---|---|---|
| Octave | `4` | Doc says "corresponds to `MI_OC2`". Note number = `12*octave + (keycode - MIDI_TONE_MIN) + transpose`. With defaults, `MI_C` → MIDI note **48** (C3). **Not saved to EEPROM.** |
| Transposition | `0` | -6…+6 semitones |
| Velocity | `127` | 0–127 |
| Channel | `0` | 0-indexed → MIDI channel 1. CC/Note On sent on `midi_config.channel`. |
| Modulation interval | `8` | How often modulation CC is re-sent |

### Sending CC (and other non-keycode messages)
Not every CC has a keycode (and faders/pots need analog values). Access the device directly:
```c
#include QMK_KEYBOARD_H
extern MidiDevice midi_device;   // declared in quantum/midi/midi_device.h

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    if (keycode == MY_CC80) {                    // custom keycode
        midi_send_cc(&midi_device, midi_config.channel, 80,
                     record->event.pressed ? 127 : 0);  // generic on/off switch CC 80
    }
    return true;
}
```
Other raw senders (see `quantum/midi/midi.h`): `midi_send_noteon(dev, chan, note, vel)`, `midi_send_noteoff(dev, chan, note, vel)`, `midi_send_cc(dev, chan, ctrl, val)`, `midi_send_pitchbend(dev, chan, val)`, `midi_send_programchange(dev, chan, prog)`.

### Example (advanced MIDI keymap)
```c
// rules.mk:  MIDI_ENABLE = yes
// config.h:  #define MIDI_ADVANCED
#include QMK_KEYBOARD_H
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
  [0] = LAYOUT(
    MI_C,   MI_D,   MI_E,   MI_F,
    MI_OCTD, MI_OCTU, MI_VELD, MI_VELU,
    MI_CHND, MI_CHNU, MI_MOD, MI_AOFF
  )
};
```

### Behavior & ordering
- Note keycodes call `process_midi` in the key-processing chain (see `01-architecture.md`). When a note is On, pressing another note key tracks up to `MIDI_TONE_COUNT` simultaneous tones; releasing sends Note Off for the matching tone.
- `midi_config` is RAM-only — **resets on every boot**, never written to EEPROM.
- MIDI and Audio's "MIDI mode" share `MIDI_ON_SONG`/`MIDI_OFF_SONG` (defined under Audio).

### Gotchas — MIDI
- **`midi_config` is NOT persisted** — octave/transpose/velocity/channel reset every power cycle. If you need persistence, you must write your own EEPROM logic.
- **Octave display is confusing:** doc table says default octave `4` "corresponds to `MI_OC2`" and `MI_C` → note **48 (C3)**. The internal math is `12*octave + tone + transpose`, so double-check your DAW's octave numbering (different DAWs disagree on whether 48 is "C3" or "C4").
- **Basic vs Advanced:** with only `MIDI_BASIC`, octave/transpose/velocity/channel/modulation keycodes silently do nothing.
- **V-USB controllers may fail** — MIDI needs 2 USB endpoints.
- The keyboard appears as a USB-MIDI device; the host must route that MIDI port in the DAW/synth.
- For CC beyond the predefined pedal/mod keycodes, you must implement custom keycodes + `midi_send_cc`.

**See also:** `06-pointing-and-hid-devices.md` (other USB device classes), `01-architecture.md` (process_record chain), `10-connectivity.md` (USB descriptor/endpoint constraints).

---

## 3. Sequencer

### Summary
An **experimental** step sequencer (drum-machine style) layered on top of MIDI: up to 8 tracks of note patterns over up to 16 (configurable) steps, driven at a tempo + resolution. Only validated on Planck EZ; scope intentionally limited to drum-machine use cases.

> ⚠️ **Highly experimental** — tested mainly on Planck EZ. Requires `MIDI_ENABLE` (it emits MIDI notes).

### Enable it
```make
# rules.mk
SEQUENCER_ENABLE = yes
```
```c
// config.h (optional)
#define SEQUENCER_STEPS 32     // default 16
// SEQUENCER_TRACKS is fixed at 8 (quantum/sequencer/sequencer.h)
```

`SEQUENCER_STEPS` (default **16**) — number of steps in the pattern. `SEQUENCER_TRACKS` is a compile-time constant (**8**) — you cannot raise it via config.

### Keycodes

| Key | Alias | Description |
|---|---|---|
| `QK_SEQUENCER_ON` | `SQ_ON` | Start playback |
| `QK_SEQUENCER_OFF` | `SQ_OFF` | Stop playback |
| `QK_SEQUENCER_TOGGLE` | `SQ_TOGG` | Toggle playback |
| `QK_SEQUENCER_STEPS_ALL` | `SQ_SALL` | Enable all steps |
| `QK_SEQUENCER_STEPS_CLEAR` | `SQ_SCLR` | Disable all steps |
| `QK_SEQUENCER_TEMPO_DOWN` | `SQ_TMPD` | Decrease tempo |
| `QK_SEQUENCER_TEMPO_UP` | `SQ_TMPU` | Increase tempo |
| `QK_SEQUENCER_RESOLUTION_DOWN` | `SQ_RESD` | Slower resolution |
| `QK_SEQUENCER_RESOLUTION_UP` | `SQ_RESU` | Faster resolution |
| `SQ_S(n)` | — | Toggle step `n` |
| `SQ_R(n)` | — | Set resolution to `n` |
| `SQ_T(n)` | — | Set `n` as the only active track (or deactivate all) |

### Resolutions (`sequencer_resolution_t`)
Tempo = absolute speed; resolution = step granularity.

| Enum | Meaning |
|---|---|
| `SQ_RES_2` | Every other beat |
| `SQ_RES_2T` | Every 1.5 beats |
| `SQ_RES_4` *(default)* | Every beat |
| `SQ_RES_4T` | Three times per 2 beats |
| `SQ_RES_8` | Twice per beat |
| `SQ_RES_8T` | Three times per beat |
| `SQ_RES_16` | Four times per beat |
| `SQ_RES_16T` | Six times per beat |
| `SQ_RES_32` | Eight times per beat |

### Defaults (from `sequencer.c`)
```c
sequencer_config = {
  .enabled     = false,
  .steps       = {false},       // all steps off
  .track_notes = {0},
  .tempo       = 60,            // default tempo
  .resolution  = SQ_RES_4
};
```
Tempo range: **1–255** (`sequencer_set_tempo` clamps). Resolution default `SQ_RES_4`. `sequencer_config` is **not persisted to EEPROM**.

### C API (`quantum/sequencer/sequencer.h`)

| Signature | Purpose |
|---|---|
| `bool is_sequencer_on(void);` | Playing? |
| `void sequencer_on/off/toggle(void);` | Transport control |
| `void sequencer_set_track_notes(const uint16_t track_notes[SEQUENCER_TRACKS]);` | Assign a MIDI note to each of the 8 tracks |
| `bool is_sequencer_track_active(uint8_t track);` | Track active? |
| `void sequencer_set_track_activation(uint8_t track, bool v);` | Activate/deactivate a track |
| `void sequencer_toggle_track_activation(uint8_t track);` | Toggle a track |
| `void sequencer_toggle_single_active_track(uint8_t track);` | Solo a track (or deactivate all) |
| `sequencer_activate_track(t)` / `sequencer_deactivate_track(t)` | macros → set activation true/false |
| `bool is_sequencer_step_on(uint8_t step);` | Step enabled? |
| `bool is_sequencer_step_on_for_track(uint8_t step, uint8_t track);` | Step+track enabled? |
| `void sequencer_set_step(uint8_t step, bool v);` | Enable/disable step |
| `void sequencer_toggle_step(uint8_t step);` | Toggle step |
| `void sequencer_set_all_steps(bool v);` | All steps on/off |
| `sequencer_set_step_on/off(step)`, `sequencer_set_all_steps_on/off()` | macros |
| `uint8_t sequencer_get_tempo(void);` / `void sequencer_set_tempo(uint8_t tempo);` | Tempo (1–255) |
| `void sequencer_increase_tempo(void)/decrease_tempo(void);` | ±tempo |
| `sequencer_resolution_t sequencer_get_resolution(void);` / `void sequencer_set_resolution(sequencer_resolution_t r);` | Resolution |
| `void sequencer_increase_resolution(void)/decrease_resolution(void);` | ±resolution |
| `uint8_t sequencer_get_current_step(void);` | Current step index |
| `uint16_t sequencer_get_beat_duration(void);` | Beat duration (ms-ish, internal units) |
| `uint16_t sequencer_get_step_duration(void);` | Current step duration |
| `uint16_t get_step_duration(uint8_t tempo, sequencer_resolution_t r);` | Compute step duration |
| `void sequencer_task(void);` | Called from the main loop to advance the sequencer |

### Example
```c
// rules.mk: SEQUENCER_ENABLE = yes  (and MIDI_ENABLE = yes)
#include QMK_KEYBOARD_H
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
  [0] = LAYOUT(
    SQ_T(0), SQ_T(1), SQ_T(2), SQ_T(3),   // pick active track(s)
    SQ_S(0), SQ_S(4), SQ_S(8), SQ_S(12),  // toggle steps on the active track
    SQ_TOGG, SQ_TMPU, SQ_TMPD, SQ_RESD
  )
};

void keyboard_post_init_user(void) {
    // Assign MIDI notes (e.g. GM drum map) to the 8 tracks
    uint16_t notes[SEQUENCER_TRACKS] = { 36, 38, 42, 46, 49, 51, 39, 75 };
    sequencer_set_track_notes(notes);
}
```

### Behavior & ordering
- `sequencer_task()` runs from the main loop and emits MIDI Note On/Off for active tracks at enabled steps — so MIDI must be enabled and the host must be listening on the USB-MIDI port.
- Active track selection (`SQ_T(n)` / `sequencer_toggle_single_active_track`) is exclusive: it solos one track, or deactivates all if that track was already the only active one.

### Gotchas — Sequencer
- **Experimental & narrow scope** — built for drum-machine use, only validated on Planck EZ.
- **Requires `MIDI_ENABLE`** — the sequencer emits MIDI notes; without MIDI it does nothing audible.
- **`SEQUENCER_TRACKS` is fixed at 8** (not configurable); only `SEQUENCER_STEPS` is tunable.
- **`sequencer_config` is RAM-only** — patterns/tempo/resolution reset on reboot; no EEPROM persistence.
- Default tempo is **60** (not 120 like Audio songs) — different tempo space, don't confuse the two.

**See also:** MIDI (above), `01-architecture.md` (`sequencer_task` in main loop), `10-connectivity.md` (USB-MIDI endpoint requirements).

---

## 4. Haptic Feedback

### Summary
Drive physical feedback hardware — an **ERM/LRA motor via a DRV2605L** chip (I²C), or a **solenoid/relay** on a GPIO (through a MOSFET) — to buzz/tap on keypress, release, or both. Configurable per-key exclusion, dwell time, waveforms, and continuous mode.

### Enable it

**Data-driven (`info.json`):**
```json
{
  "features": { "haptic": true },
  "haptic": { "driver": "drv2605l" }   // or "solenoid"
}
```

**Legacy (`rules.mk`):**
```make
HAPTIC_ENABLE = yes
HAPTIC_DRIVER = drv2605l   # or solenoid
```

### Drivers

| Driver | `HAPTIC_DRIVER` | Interface | Hardware |
|---|---|---|---|
| **DRV2605L** | `drv2605l` | **I²C** (SDA/SCL) | ERM (eccentric rotating mass) or LRA (linear resonant actuator). 123 built-in waveforms. |
| **Solenoid** | `solenoid` | GPIO pin (via MOSFET) | Solenoid, relay, or similar. Supports multiple solenoids. |

> DRV2605L talks over I²C — you must wire SDA/SCL and enable/configure the I²C peripheral. See `13-drivers-lowlevel.md` (i2c). Known-good motors: **LV061228B-L65-A** (z-axis 2V LRA), **Adafruit Mini Motor Disc** (2–5V ERM).

### Keycodes

> Not all keycodes apply to every driver — buzz/dwell are solenoid-specific, mode/continuous are DRV2605L-specific.

| Key | Alias | Description | Driver |
|---|---|---|---|
| `QK_HAPTIC_ON` | `HF_ON` | Turn haptic on | both |
| `QK_HAPTIC_OFF` | `HF_OFF` | Turn haptic off | both |
| `QK_HAPTIC_TOGGLE` | `HF_TOGG` | Toggle on/off | both |
| `QK_HAPTIC_RESET` | `HF_RST` | Reset config to default | both |
| `QK_HAPTIC_FEEDBACK_TOGGLE` | `HF_FDBK` | Toggle feedback on press / release / both | both |
| `QK_HAPTIC_BUZZ_TOGGLE` | `HF_BUZZ` | Toggle solenoid buzz | solenoid |
| `QK_HAPTIC_MODE_NEXT` | `HF_NEXT` | Next DRV2605L waveform | drv2605l |
| `QK_HAPTIC_MODE_PREVIOUS` | `HF_PREV` | Previous DRV2605L waveform | drv2605l |
| `QK_HAPTIC_CONTINUOUS_TOGGLE` | `HF_CONT` | Toggle continuous haptic | drv2605l |
| `QK_HAPTIC_CONTINUOUS_UP` | `HF_CONU` | Increase continuous strength | drv2605l |
| `QK_HAPTIC_CONTINUOUS_DOWN` | `HF_COND` | Decrease continuous strength | drv2605l |
| `QK_HAPTIC_DWELL_UP` | `HF_DWLU` | Increase solenoid dwell | solenoid |
| `QK_HAPTIC_DWELL_DOWN` | `HF_DWLD` | Decrease solenoid dwell | solenoid |

### Configuration knobs

**All haptic (both drivers):**

| Define | Default | Meaning |
|---|---|---|
| `HAPTIC_ENABLE_PIN` | *undef* | Pin to enable a boost converter (often with solenoid) |
| `HAPTIC_ENABLE_PIN_ACTIVE_LOW` | *undef* | Enable pin is active-low |
| `HAPTIC_ENABLE_STATUS_LED` | *undef* | Pin reflecting haptic on/off status |
| `HAPTIC_ENABLE_STATUS_LED_ACTIVE_LOW` | *undef* | Status LED active-low |
| `HAPTIC_OFF_IN_LOW_POWER` | `0` | `1` = disable haptic before USB configured and while suspended |

**Solenoid-only:**

| Define | Default | Meaning |
|---|---|---|
| `SOLENOID_PIN` | *undef* | Pin driving the solenoid/relay |
| `SOLENOID_PIN_ACTIVE_LOW` | *undef* | Trigger pin active-low |
| `SOLENOID_PINS` | *undef* | Array of pins for multiple solenoids |
| `SOLENOID_PINS_ACTIVE_LOW` | *undef* | Per-pin active-low spec |
| `SOLENOID_RANDOM_FIRE` | *undef* | With multiple solenoids, fire a random one |
| `SOLENOID_DEFAULT_DWELL` | `12` ms | Default dwell (plunger active time) |
| `SOLENOID_MIN_DWELL` | `4` ms | Dwell lower limit |
| `SOLENOID_MAX_DWELL` | `100` ms | Dwell upper limit |
| `SOLENOID_DWELL_STEP_SIZE` | `1` ms | Step per `HF_DWL*` |
| `SOLENOID_DEFAULT_BUZZ` | `0` (off) | On `HF_RST`, buzz set on if this is `1` |
| `SOLENOID_BUZZ_ACTUATED` | `= MIN_DWELL` | Actuated time within a buzz cycle |
| `SOLENOID_BUZZ_NONACTUATED` | `= MIN_DWELL` | Non-actuated time within a buzz cycle |

> Dwell/buzz timing precision is limited by the matrix-scan rate. If scanning is slow, set `SOLENOID_DWELL_STEP_SIZE` slightly smaller than one scan-cycle duration.

**DRV2605L motor setup (`config.h`)** — pick ERM or LRA:

```c
// ERM (eccentric rotating mass)
#define DRV2605L_FB_ERM_LRA 0
#define DRV2605L_FB_BRAKEFACTOR 3   /* 1x:0 2x:1 3x:2 4x:3 6x:4 8x:5 16x:6 DisBrake:7 */
#define DRV2605L_FB_LOOPGAIN 1      /* Low:0 Med:1 High:2 VHigh:3 */
#define DRV2605L_RATED_VOLTAGE 3
#define DRV2605L_V_PEAK 5

// LRA (linear resonant actuator)
#define DRV2605L_FB_ERM_LRA 1
#define DRV2605L_FB_BRAKEFACTOR 3
#define DRV2605L_FB_LOOPGAIN 1
#define DRV2605L_RATED_VOLTAGE 2
#define DRV2605L_V_PEAK 2.1
#define DRV2605L_V_RMS 2.0
#define DRV2605L_F_LRA 205          /* resonance freq — see motor datasheet */
```

Optional DRV2605L defines:
- `#define DRV2605L_GREETING <seq name|num>` — waveform played at startup.
- `#define DRV2605L_DEFAULT_MODE <seq name|num>` — mode `HF_RST` returns to (defaults to `1` = `strong_click`).

**DRV2605L waveform library** — 123 sequences (1–123); call from a macro:
```c
#include "drv2605l.h"
drv2605l_pulse(strong_click);   // or drv2605l_pulse(1);
```
Full list in `docs/features/haptic_feedback.md` (e.g. `strong_click`=1, `sharp_click`=4, `soft_bump`=7, `dbl_click`=10, `buzz`=47, `alert_750ms`=15, `alert_1000ms`=16, … `smooth_hum5_10`=123).

### Per-key exclusion (`NO_HAPTIC_*`) and `get_haptic_enabled_key`
Add to `config.h` to suppress feedback for classes of keys:

| Define | Excluded keys |
|---|---|
| `NO_HAPTIC_MOD` | Mods (Ctrl/Shift/Alt/Gui), `MO()`, `LM()`, `LT()`/*held*, `TT()`/*held*, `MT()`/*held*. (Tap of a mod/layer-tap still buzzes.) |
| `NO_HAPTIC_ALPHA` | `KC_A … KC_Z` |
| `NO_HAPTIC_PUNCTUATION` | Enter, ESC, Backspace, Space, Minus, Equal, `[` `]` `\`, NonUS Hash, `;` `'` `` ` ``, `,` `/` `.`, NonUS Backslash |
| `NO_HAPTIC_LOCKKEYS` | Caps Lock, Scroll Lock, Num Lock |
| `NO_HAPTIC_NAV` | PrtScn, Pause, Insert, Delete, PgDn, PgUp, ← ↑ → ↓, End, Home |
| `NO_HAPTIC_NUMERIC` | `KC_1 … KC_0` |

**Custom exclusion — the hook:**
```c
__attribute__((weak)) bool get_haptic_enabled_key(uint16_t keycode, keyrecord_t *record);
```
Override in `keymap.c` (or keyboard `.c`) to return `false` for any keycode you want to **skip** haptic:
```c
bool get_haptic_enabled_key(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case KC_NO:  return false;   // never buzz on transparent/empty
        default:     return true;
    }
}
```

### C API / hooks (`quantum/haptic.h`, `quantum/process_keycode/process_haptic.c`)

| Signature | Purpose |
|---|---|
| `bool process_haptic(uint16_t keycode, keyrecord_t *record);` | Core handler called in the key-processing chain — fires `haptic_play()` on press/release per feedback mode, gated by `get_haptic_enabled_key`. |
| `bool get_haptic_enabled_key(uint16_t keycode, keyrecord_t *record);` | **Weak** — override to exclude keycodes from feedback. |
| `void haptic_init(void);` | Core init (called once). |
| `void haptic_enable(void);` / `void haptic_disable(void);` | Enable/disable feedback. |
| `void haptic_toggle(void);` | Toggle on/off. |
| `void haptic_reset(void);` | Reset config to defaults. |
| `void haptic_set_feedback(uint8_t feedback);` | 0=press, 1=release, 2=both. |
| `uint8_t haptic_get_feedback(void);` | Current feedback mode. |
| `uint8_t haptic_get_enable(void);` | Is haptic on? |
| `void haptic_mode(uint8_t mode);` / `void haptic_set_mode(uint8_t mode);` / `uint8_t haptic_get_mode(void);` | DRV2605L waveform mode (1–123). |
| `void haptic_mode_increase(void)/haptic_mode_decrease(void);` | Cycle mode. |
| `void haptic_set_dwell(uint8_t dwell);` | Solenoid dwell (ms). |
| `void haptic_dwell_increase(void)/haptic_dwell_decrease(void);` | Adjust dwell. |
| `void haptic_buzz_toggle(void);` | Solenoid buzz on/off. |
| `void haptic_toggle_continuous(void);` | DRV2605L continuous mode on/off. |
| `void haptic_cont_increase(void)/haptic_cont_decrease(void);` | DRV2605L continuous strength. |
| `void haptic_play(void);` | Fire one pulse now (DRV2605L → `drv2605l_pulse`); or fire the solenoid. Used by `process_haptic`. |

### Behavior & ordering
- `process_haptic()` is invoked in the core `process_record` chain (see `01-architecture.md`). On press: if `feedback < 2` (press or both) and key enabled → `haptic_play()`. On release: if `feedback > 0` (release or both) and key enabled → `haptic_play()`.
- Respects `HAPTIC_OFF_IN_LOW_POWER`: if `1`, haptic is silent until the device is USB-configured and during suspend.
- Split keyboards: haptic state syncs via the split transport (`split.haptic`); see `10-connectivity.md` — enable `split.sync.haptic` if needed.

### Example
```c
// info.json:  features.haptic = true,  haptic.driver = "drv2605l"
// config.h:
#define DRV2605L_FB_ERM_LRA 0
#define DRV2605L_RATED_VOLTAGE 3
#define DRV2605L_V_PEAK 5
#define DRV2605L_GREETING strong_click
#define NO_HAPTIC_MOD          // don't buzz on held mods/layers

// keymap.c — custom exclusion + on-demand pulse
#include QMK_KEYBOARD_H
#include "drv2605l.h"

bool get_haptic_enabled_key(uint16_t keycode, keyrecord_t *record) {
    if (keycode == MY_SILENT_KEY) return false;
    return true;
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    if (keycode == ALARM && record->event.pressed) {
        drv2605l_pulse(alert_1000ms);   // fire a specific waveform directly
    }
    return true;
}
```

### Gotchas — Haptic
- **Solenoid pins may be powered during bootloader/DFU** (e.g. **A13 on STM32F303**) → the solenoid stays ON through flashing and can **overheat and damage** the hardware. If you see this, pick a different pin.
- **DRV2605L is I²C** — must wire SDA/SCL and the I²C peripheral must be enabled on the right pins for your MCU (see `13-drivers-lowlevel.md`, i2c).
- **Dwell/buzz timing precision is bounded by the matrix-scan rate** — set `SOLENOID_DWELL_STEP_SIZE` smaller than one scan if scans are slow.
- **Some keycodes are driver-specific** — buzz/dwell do nothing on DRV2605L; mode/continuous do nothing on solenoid.
- **`HAPTIC_OFF_IN_LOW_POWER` default is `0`** — haptic will fire even before USB is configured unless you set it to `1`.
- **`get_haptic_enabled_key` returns `false` to EXCLUDE** — easy to invert by mistake.
- Solenoids need a **MOSFET driver circuit** — MCUs cannot source enough current for the coil directly.
- `LT()`/`TT()`/`MT()` still buzz **on the tap** (only the held-modifier phase is excluded by `NO_HAPTIC_MOD`).
- DRV2605L LRA tuning (`F_LRA`, `V_PEAK`, rated voltage) is motor-specific — copy from the motor datasheet, wrong values give weak or no vibration.

**See also:** `13-drivers-lowlevel.md` (i2c for DRV2605L, GPIO for solenoid), `01-architecture.md` (process_record chain — `process_haptic`), `10-connectivity.md` (split haptic sync), `04-keymaps-and-keycodes.md` (the `MO`/`LT`/`TT`/`MT` keycodes referenced by `NO_HAPTIC_MOD`).

---

## Cross-cutting map

| Concern | Where |
|---|---|
| Process_record chain ordering for `AU_*`/`MI_*`/`SQ_*`/`HF_*` | `01-architecture.md` |
| Audio driver hardware routing, ChibiOS halconf/mcuconf, AVR/ARM peripheral tables | `13-drivers-lowlevel.md` ("Audio driver") |
| I²C setup for DRV2605L | `13-drivers-lowlevel.md` (i2c) |
| AVR Timer1/Timer3 conflict between Audio and backlight | `07-led-rgb-backlight.md` + `13-drivers-lowlevel.md` |
| USB endpoint limits (MIDI needs 2) | `10-connectivity.md` |
| Split sync for haptic | `10-connectivity.md` (`split.sync.haptic`) |
| `info.json` features / driver schema | `03-config-and-info-json.md` |
| `MO`/`LM`/`LT`/`TT`/`MT` keycodes (haptic exclusion) | `04-keymaps-and-keycodes.md` |
| Breaking changes / deprecations | `17-faq-gotchas-breaking-changes.md` |
