---
name: qmk-skill
description: >-
  QMK Firmware expert companion. Use when the user is editing, building,
  flashing, wiring, porting, or designing anything for a QMK keyboard:
  writing or refactoring keymap.c, choosing/combining keycodes, configuring
  layers/mod-tap/one-shot/tap-dance/combos/RGB/OLED/encoders/split/wireless,
  editing info.json/rules.mk/config.h (data-driven config), working with
  keymap.json / the QMK Configurator / the QMK compile API, hooking a board
  up to VIA or Vial, adding features or custom C (process_record_user,
  community modules, userspace), designing novel per-key behavior, sizing a
  hand-wired matrix, selecting a microcontroller/bootloader, debugging
  (hid_listen, SWD, unit tests), or recovering from a broken flash. Covers
  every feature and driver in the QMK docs, plus standing issues, gotchas,
  breaking changes, and dead/renamed APIs so obsolete code is never produced.
---

# QMK Firmware Companion

You are helping a user with **QMK Firmware** (the open-source keyboard firmware). This skill is a compressed, navigable synthesis of the **entire QMK documentation set** (≈207 docs) plus a synthesized VIA/Vial layer and an aggregated gotchas index. It is organized so you can pull in **only the area you need** instead of loading everything.

**Golden rules — always:**
1. **Read `references/00-cross-cutting-gotchas.md` before you write or edit** keymap.c, config.h, info.json, or any custom C. It is the trap-detection layer (process_record return semantics, RGB subsystem conflicts, pin naming, EEPROM staleness, dead/renamed APIs). Ignoring it is the most common source of bad advice.
2. **Prefer the data-driven path** (`info.json` feature blocks + `rules.mk` `XXX_ENABLE = yes`) over hand-written `config.h` `#define`s. Show the `info.json` key first, the `#define` equivalent second, and flag anything not yet data-driven. Details: `references/03-config-and-info-json.md`.
3. **Never suggest removed APIs.** The QMK tree has churned hard: `setPinOutput`→`gpio_set_pin_output`, `RGB_*`→`UG_*`/`RM_*`, `RESET`→`QK_BOOT`, lowercase driver strings (`ws2812`, `snled27351`), callbacks now return `bool`, etc. The full list is `references/00 §H` and `references/17-faq-gotchas-breaking-changes.md`.
4. **Verify the user's MCU/platform and bootloader** before recommending features or flash commands — many features are ARM-only or AVR-only, and pin naming differs (`references/12-hardware-platforms.md`).

## How this skill is organized

```
qmk-skill/
├── SKILL.md                     ← you are here (navigation + playbooks + gotchas index)
├── references/
│   ├── 00-cross-cutting-gotchas.md      ← READ FIRST before editing
│   ├── 01-architecture.md               ← main loop, process_record chain, hooks, layers
│   ├── 02-getting-started-build.md      ← setup, CLI, building, git, docker
│   ├── 03-config-and-info-json.md       ← config.h, data-driven config, info.json schema
│   ├── 04-keymaps-and-keycodes.md       ← keymap.c, layers, full keycode tables, mod/one-shot/tap-hold
│   ├── 05-text-input-and-combos.md      ← macros, send_string, combos, tap-dance, autocorrect, caps_word…
│   ├── 06-pointing-and-hid-devices.md   ← mouse_keys, pointing_device, joystick, digitizer…
│   ├── 07-led-rgb-backlight.md          ← backlight, rgblight, rgb_matrix, led_matrix, indicators
│   ├── 08-displays.md                   ← OLED, Quantum Painter, HD44780, ST7565, encoders
│   ├── 09-audio-haptic.md               ← audio, MIDI, sequencer, haptic
│   ├── 10-connectivity.md               ← split, wireless/BT, command, secure, os_detection, rawhid, battery
│   ├── 11-other-features.md             ← bootmagic, dip_switch, unicode, steno, wpm, community modules
│   ├── 12-hardware-platforms.md         ← MCUs, ARM platforms, hand-wire, custom matrix, converters
│   ├── 13-drivers-lowlevel.md           ← i2c/spi/uart/serial/gpio/adc, eeprom/flash, ws2812, LED-driver table
│   ├── 14-configurator-api-via.md       ← Configurator, QMK API, keymap.json, VIA & Vial
│   ├── 15-flashing-debugging.md         ← flash/bootloader, ISP, Zadig, debug, SWD, unit tests, size
│   ├── 16-userspace-development.md      ← userspace, coding conventions, contributing, glossary
│   └── 17-faq-gotchas-breaking-changes.md ← FAQs, breaking-change cycle, changelog, deprecated APIs
└── assets/
    ├── keymap-template.c                ← idiomatic starter keymap (layer enum, SAFE_RANGE, hooks)
    └── info-json-template.json          ← starter keyboard definition with schema notes
```

## Quick triage — which reference do I load?

| The user wants to… | Primary reference(s) | Also read |
|---|---|---|
| Understand how a keypress flows through QMK | `01` | `00` |
| Write / edit / restructure a keymap | `04`, `05` | `00`, `01` |
| Pick or combine keycodes (layers, mod-tap, one-shot, tap-hold) | `04` | `05`, `01` |
| Add a feature (combos, tap-dance, autocorrect, RGB…) | `05`/`07`/`08`/… | `03`, `00` |
| Configure the keyboard (info.json/rules.mk/config.h) | `03` | `00`, the feature ref |
| Create / define a key **matrix** | `03` §Matrix, `12` (hand-wire/custom matrix) | `01` |
| Choose / wire a microcontroller; pick a bootloader | `12` | `15`, `13` |
| **Build & flash** firmware | `02` (workflow), `15` (deep) | `12` |
| Use the **QMK Configurator** or `keymap.json` | `14` | `03`, `02` (json2c/c2json) |
| Hook up **VIA / Vial** | `14` | `10` (rawhid), `00 §G` |
| Add **plugins / custom C / modules** | `16` (userspace/modules), `01` (hooks), `05` | `00` |
| Design **advanced / unique keymap behavior** | `04`, `05`, `01` | `00` |
| **Wireless / split** keyboard | `10` | `12`, `13`, `07`/`08` (sync) |
| Add **RGB / backlight / per-key LEDs** | `07` | `13` (drivers), `03` |
| Add a **display** (OLED / Quantum Painter) | `08` | `13` (i2c/spi) |
| Add **audio / haptic / MIDI** | `09` | `13`, `07` (AVR timer clash) |
| Add **mouse / pointing / joystick** | `06` | `10` (split pointing), `03` (endpoints) |
| **Debug** a misbehaving keyboard | `15`, `17` | `00` |
| Recover from a **broken flash / bricked board** | `15`, `00 §F` | `12` |
| Contribute a keyboard/PR upstream | `16`, `03` (lint/guidelines) | `17` |
| Know if an API is **deprecated/removed** | `00 §H`, `17` | — |

## The 5-line mental model (read `references/01` for depth)

1. **Matrix scan** runs continuously (often hundreds of times/sec); each key is a `[row][col]` bit.
2. **State-change detection** turns raw scans into press/release events → dispatched through the **`process_record` chain** (`01 §7`).
3. The chain has a strict **order**: combos (pre-process) → feature handlers → `process_record_kb`/`_user` → more features → quantum keycodes → `post_process_record`. **`return false` halts everything downstream.**
4. A **layer stack** (up to 32) maps matrix positions → 16-bit **keycodes**; higher layers win, `KC_TRNS` falls through, `KC_NO` blocks (`04`).
5. Keycodes become **USB HID reports** (scancodes + modifiers); the **host OS** maps scancodes → characters via its layout. You can only send what the host layout knows (`01`, `11` for Unicode).

## Workflow playbooks

### PB-1 — Build & flash a keymap (the #1 task)
1. Confirm environment: `qmk doctor` (`references/02`). Config: `qmk config user.keyboard=... user.keymap=...`.
2. Edit `keyboards/<kb>/keymaps/<name>/keymap.c` (or your **external userspace** repo — `02`).
3. Build: `qmk compile -kb <kb> -km <name>` (artifact: `<kb>_<name>.{hex|bin|uf2}` in repo root).
4. Flash: `qmk flash -kb <kb> -km <name>` (or the `:flash` make target). Enter bootloader first.
5. **Gotchas:** mass-storage bootloaders (RP2040 UF2, some STM32) aren't supported by `:flash` — copy the `.uf2`. `-kb`/`-km` are **paths** (`clueboard/66/rev4`). `CONSOLE_ENABLE` + printing is the classic AVR-too-big cause. See `02`, `15`.

### PB-2 — Edit / create a keymap
- Start from `assets/keymap-template.c`. Use the keyboard's `LAYOUT()` macro (generated from `info.json` `layouts`).
- Read `references/04` for the full keycode tables, layer model (`MO`/`LM`/`LT`/`TG`/`TO`/`TT`/`OSL`/`DF`), mod-tap, one-shot, tap-hold decision modes.
- Read `references/05` for macros/combos/tap-dance/caps-word/etc.
- **Must-know traps:** `00 §A` (process_record return semantics), `00 §B` (16-bit keycode limits — `MT`/`LT` tap-keycode is Basic-only; `LM`/`MT` can't mix L/R mods; `LT`/`LM` layer ≤15), layer precedence (`KC_NO` still blocks fall-through), and US-ANSI-shifted aliases break inside `MT`/`LT`.

### PB-3 — Configure the keyboard (info.json / rules.mk / config.h)
- Read `references/03` for the full `info.json` schema by feature block and the `#define`↔`info.json` mapping.
- Use `assets/info-json-template.json` as a skeleton. Validate with `qmk info -kb <kb>` and `qmk lint`.
- **Must-know traps:** `00 §C` — pin naming per platform, `keyboard.json` vs `info.json`, keymap `config.h` overrides data-driven values, debounce `0` disables.

### PB-4 — Create / define a key matrix
- Standard matrix: set `matrix_pins.cols`/`rows` + `diode_direction` in `info.json` (`03 §Matrix`, `12`). Direct-pin: use `matrix_pins.direct` (a 2D pin array; ignores `cols`/`rows`/`diode_direction`).
- **Hand-wiring:** read `references/12` (matrix sizing, rows/cols, diodes, direct pin) + `references/01 §2` (ghosting & diodes, scan rate). Diode direction: black stripe faces the row on COL2ROW boards.
- **Custom scanner:** `CUSTOM_MATRIX = lite` + `matrix_init_custom()`/`matrix_scan_custom()` (only 2 functions). Full replacement MUST also call `matrix_init_kb`/`matrix_scan_kb` + `debounce(...)` or keymaps silently break (`12`, `00 §I`).

### PB-5 — Choose a microcontroller / platform / bootloader
- Read `references/12`: AVR (atmega32u4/328p/32a) vs ARM (STM32F1/F4/F7/H7, RP2040) capability & footprint tradeoffs, ARM platform guides (proton_c, blackpill, rp2040), converters (CONVERT_TO to swap MCU), proprietary-libs limits.
- Read `references/15` for bootloader/flash per MCU and `references/13` for peripheral/driver availability.
- **Must-know traps:** `00 §D` (ARM GPLv3, I²C split AVR-only, endpoint budget), `00 §I` (voltage domains, Blackpill/RP2040 pin landmines), `00 §C` (pin naming).

### PB-6 — Add a feature / plugin
1. Enable it: the feature's `info.json` block **and/or** `rules.mk` `XXX_ENABLE = yes` (each feature reference in `05`–`11` shows both).
2. Configure knobs (defaults documented in each reference).
3. Wire any callbacks (`process_record_user`, indicator functions, etc.) — read `01 §9` for the full hook catalog and `00 §A` for return semantics.
4. For **advanced/custom plugins** with no built-in feature: write it in `process_record_user` (keymap-level) or a **userspace** (`16`) or a **community module** (`11`). See PB-7.

### PB-7 — Add extensive / advanced custom code (plugins, modules, userspace)
- **Per-keymap custom logic:** implement `process_record_user` + custom keycodes (`SAFE_RANGE`/`QK_USER`). Pattern in `assets/keymap-template.c`.
- **Share code across keyboards:** a **userspace** (`references/16`) — `users/<name>/` with `rules.mk` + `config.h` + `<name>.h` + `<name>.c`. `USER_NAME` overrides the name=keymap-name default. **`config.h`** = build-time defines; **`<name>.h`** = enums/settings (including them the wrong way is the #1 build break).
- **Distributable, self-contained extension:** a **community module** (`references/11`) — `modules/<name>/` with its own `rules.mk` + `<name>.c`; hooks discovered by name matching the directory; API version-gated. (Not supported by the Configurator.)
- **Deep customization hooks** (the full catalog, `01 §9`): `keyboard_pre_init`, `keyboard_post_init`, `matrix_init/scan`, `housekeeping_task`, `process_record`, `post_process_record`, `layer_state_set`, `led_update`, `suspend_*`, `encoder_update`, `oled_task`, RGB/LED indicator callbacks, etc. Most have `_kb` (call `_user`!) and `_user` variants.

### PB-8 — Design advanced / unique keymap behavior
This is where QMK shines. Combine these (read `04` + `05`):
- **Layer gymnastics:** `MO`/`LM`/`LT`/`TO`/`TT`/`OSL`/`DF`, tri-layer (`update_tri_layer_state`), layer_lock, per-key layer toggles in `process_record_user`.
- **Chording:** combos (`05`) run *before* your `process_record_user`; key overrides (`05`) emulate shifted/modified keys; tap-dance (`05`) for multi-tap state machines.
- **Timing:** mod-tap per-key `get_tapping_term`, permissive/hold-on-other-key/chordal-hold/flow-tap, retro-tap, auto-shift, one-shot timeouts.
- **State in callbacks:** use `get_mods()`/`get_oneshot_mods()`, `layer_state`, `record->tap.count`, `timer_read()`. Remember weak mods vs strong mods (`get_mods`/`add_mods` vs `set_mods`).
- **Text generation:** `SEND_STRING`/`send_string`/macros/dynamic macros (`05`); `send_string_P` for PROGMEM.
- **Novel behavior:** intercept in `process_record_user`, return `false` to fully handle, reproduce any suppressed effect. Compose caps_word + repeat_key + autocorrect + combos for sophisticated text flows (`05`).
- **Always check interactions:** `00 §A/B` (process_record order + 16-bit keycode limits mean some combos are impossible without `process_record_user` interception).

### PB-9 — QMK Configurator & keymap.json
- Read `references/14`. The Configurator builds via the **QMK API** from `info.json` metadata; it can only build keymaps expressible in JSON (no custom C — if a keyboard enables a custom-C feature at keyboard level, Configurator **cannot** build it at all).
- `keymap.json` ↔ `keymap.c` round-trip: `qmk json2c` (JSON→C) and `qmk c2json` (C→JSON). Layers use **numeric indices** (`MO(2)`), never `MO(_FN)` — C symbols don't survive the round-trip.
- **Troubleshooting:** keyboard not listed = missing from API/`info.json` metadata; layout mismatch = `LAYOUT` macro param order must equal `info.json` layout array order (positional); `.hex` vs `.bin` depends on bootloader.

### PB-10 — Hook up VIA / Vial
- Read `references/14` (the VIA/Vial section is **synthesized** — QMK docs don't cover it).
- **VIA:** set `VIA_ENABLE = yes` in `rules.mk` (force-enables RAW/DYNAMIC_KEYMAP/BOOTMAGIC/TRI_LAYER). The `LAYOUT` macro must exist; the keyboard must be in the `the-via/keyboards` definitions or side-loaded via the VIA app's Design tab. Edit layers + lighting at runtime; the app talks HID raw on the `0xFF60`/`0xFF61` endpoints.
- **Vial:** requires the **`vial-kb/vial-qmk` fork** (lags upstream) + `VIAL_ENABLE = yes` + `vial.json` + a unique keyboard ID. Adds runtime editing of tap-dance/combos/key-overrides/macros and per-key RGB on supported boards. **Upstream QMK rejects `VIAL_ENABLE` as an `_invalid` key** — building Vial on upstream fails; that error means you're on the wrong tree.
- **Critical gotcha (`00 §G`):** VIA protocol version in firmware must match the VIA app; and **VIA copies flash→EEPROM on first boot, then ignores `keymap.c`** — so firmware keymap changes don't appear until EEPROM is cleared (`EE_CLR`/Bootmagic reset).

### PB-11 — Split / wireless
- Read `references/10`. Split transport: serial (bitbang/usart/vendor) or custom — **I²C split is AVR-only**. On ARM, **bitbang serial + bitbang WS2812 conflict** — use hardware for both.
- Handedness: `SPLIT_HAND_PIN`, `SPLIT_HAND_MATRIX_GRID`, `EE_HANDS` (survives `eeconfig` but not external EEPROM wipes; Blackpill may lose it each flash), VBUS/`SPLIT_USB_DETECT` (auto on ARM, breaks battery-pack demos).
- Sync is mostly master→slave; `SPLIT_POINTING_ENABLE` is slave→master. Each `SPLIT_*` sync flag (LED state, layer, modifiers, OLED, WPM, haptic…) adds overhead. Lighting on splits needs explicit flags or "lights work on one side" (`07`, `00 §E`).
- Wireless: BT drivers (`rn42`, `bluefruit_le`) are AVR-only and need `NKRO_ENABLE = no`; most `BT_*`/`OU_*` keycodes are **not yet implemented**. Proprietary BT stacks are excluded from QMK (ZMK is the usual wireless recommendation) (`12`, `10`).

### PB-12 — Debugging
- Read `references/15` + `references/17`. Enable `CONSOLE_ENABLE = yes` + `DEBUG_ENABLE`; use `print`/`uprint`/`dprintf` (keymap-only) and **QMK Toolbox / `hid_listen`** (output needs trailing `\n`).
- Matrix/scan-rate debug: `DEBUG_MATRIX_SCAN_RATE`. ARM SWD: ST-Link/Black Magic Probe + OpenOCD + GDB (set `LTO_ENABLE = no`, `OPT = g` or stepping breaks).
- Unit tests: the `unit_tests` build target + pytest framework (`15`).
- "Changes don't take effect" / "ARM board dead after flash" → **clear EEPROM** (`00 §F`).

## Cross-cutting feature relationships (follow the trail)

These are the non-obvious links an agent should chase:

- **`process_record` order is load-bearing** (`01 §7` → every feature in `05`). Combos run *before* your hook; key overrides, tap-dance, caps-word, unicode, RGB run *after*. Returning `false` in the wrong place silently breaks layers (`00 §A`).
- **Lighting is ONE subsystem** (`07`). RGBLIGHT/RGB_MATRIX/LED_MATRIX share keycodes/EEPROM; pick one. LED/RGB indicator callbacks (`rgb_matrix_indicators_user`) are the integration point for layer/caps/lock lighting. Drivers live in `13`; info.json keys in `03`.
- **AVR timer scarcity couples Audio + Backlight** (`07`↔`09`, `00 §D`). Audio grabs Timer 1/3; backlight `pwm` wants them too. Move backlight to `software`/`timer`, or drop audio.
- **Split sync threads through every peripheral** (`10`↔`07`/`08`/`06`/`11`). Adding RGB/OLED/pointing/WPM to a split needs the matching `SPLIT_*` sync flag or it only works on the master half.
- **16-bit keycodes cap everything** (`04`→`05`→`01`). `MT`/`LT` tap-keycodes are Basic-only; US-ANSI-shifted aliases break there; `process_record_user` + Tap Dance are the escape hatches for "impossible" combos.
- **VIA sits on rawhid + EEPROM** (`14`↔`10`↔`03`). Raw HID endpoints `0xFF60/1` are VIA's; VIA caches keymap to EEPROM and then ignores C; protocol version + keyboard definitions must match.
- **Driver string casing + GPIO/I²C renames** (`13`↔`17`↔`00 §H`). All driver strings lowercase; `setPinOutput` etc. are gone; check before writing any driver or custom-matrix code.
- **Data-driven config vs `config.h`** (`03`↔every feature ref). Feature references show the `info.json` block first; if a knob isn't data-driven yet, fall back to the `#define`.
- **EEPROM persistence couples settings across reboots & breaking changes** (`03`↔`11`↔`17`↔`00 §F`). Magic/Unicode/default-layer/RGB/VIA state live in EEPROM; clear it whenever behavior is stale or after a breaking-change merge.

## API hygiene — quick do/don't (full list: `references/00 §H`, `references/17`)

| Don't suggest | Suggest instead |
|---|---|
| `setPinOutput`, `writePinHigh`, `readPin` | `gpio_set_pin_output`, `gpio_write_pin_high`, `gpio_read_pin` |
| `i2c_readReg` / `i2c_writeReg` | `i2c_read_register` / `i2c_write_register` (and `_16` variants) |
| `RGB_*` (underglow) / `RGB_*` (matrix) | `UG_*` / `RM_*` |
| `RESET`, `KC_GESC` | `QK_BOOT`, `QK_GESC` |
| `KEYMAP`, `action_get_macro`, `MACRO()` | `LAYOUT`, `SEND_STRING` / `process_record_user` |
| `led_set_user`, `USB_LED_*` | `led_update_user`/`_kb`, `led_t led_state` fields |
| `TAPPING_FORCE_HOLD` | `QUICK_TAP_TERM` (ms; 0 = disable) |
| `IGNORE_MOD_TAP_INTERRUPT` | (removed; old behavior is now default; invert with `HOLD_ON_OTHER_KEY_PRESS`) |
| `Bootmagic Full` | Bootmagic Lite + Magic keycodes |
| Uppercase driver strings (`WS2812`, `IS31FL3731`, `CKLED2001`) | lowercase (`ws2812`, `is31fl3731`, `snled27351`) |
| `void`-returning callbacks (`oled_task_user`, indicators, `encoder_update_*`, `pre_process_record_*`) | `bool` returns (`return false;` = handled) |

**For upstream PRs:** target `develop` (not `master`); new `_kb`/`_user` callbacks return `bool`; first custom keycode is `QK_USER`; wrap `LAYOUT(...)` in `// clang-format off`/`on`. (`16`)

## Assets

- `assets/keymap-template.c` — idiomatic starter keymap: layer enum, `SAFE_RANGE`/`QK_USER`, `process_record_user` with correct return semantics, common callbacks (encoder/OLED/layer/LED). Use as a base and trim.
- `assets/info-json-template.json` — starter `info.json`/`keyboard.json` with schema notes and the platform pin-naming rules inline. Use as a base; validate with `qmk info` / `qmk lint`.

## Final operating guidance

- **Confirm the MCU/platform/bootloader** before recommending features or flash commands (AVR vs ARM vs RP2040 differ a lot).
- **When the user's request could touch multiple subsystems**, read the relevant references in parallel rather than guessing — they were written to be independently loadable.
- **Surface gotchas proactively.** If you enable a feature, mention its traps (the relevant reference's `### Gotchas` + `00`). Users almost never know about endpoint budgets, EEPROM staleness, or AVR timer conflicts until they're bitten.
- **When in doubt, keep it in / verify against the tree.** This skill is a synthesis; the authoritative source is the QMK firmware repo. For exact symbol names/signatures, grep the source (e.g. `quantum/quantum.c`, `quantum/via.h`) rather than trusting memory.
