# 03 — Configuration: config.h, rules.mk, and the info.json Data-Driven Schema

> **Scope:** This is the **configuration reference**. It covers the `config.h` option categories, the `rules.mk` build/feature switches, the migration from `config.h`/`rules.mk` → `info.json` (the modern "data-driven" path), the **full `info.json` schema organized by feature block**, the LAYOUT-macro generation from layouts JSON, `matrix_pins`/`diode_direction`/`debounce`, EEPROM backends, the debounce algorithms (`sym_defer_pk`, `sym_eager_pk`, …) with their tradeoffs, community layouts, and keyboard submission guidelines. It ends with the **pin-naming conventions per platform** and an explicit list of options that are **NOT yet data-driven**.

This reference is heavily cross-linked. The config layer is the foundation every other feature builds on; keymap/keycode behavior is in `04-keymaps-and-keycodes.md`, the internal main loop / process_record chain in `01-architecture.md`, build/CLI workflow in `02-getting-started-build.md`, hardware platforms in `12-hardware-platforms.md`, and the breaking-change history of the data-driven migration in `17-faq-gotchas-breaking-changes.md`.

---

## 1. Summary

QMK is configured through three file types that are combined at build time into one final configuration:

| File | Role | Modern status |
|------|------|---------------|
| `info.json` / `keyboard.json` | **Data-driven** metadata + schema-validated config; single source of truth. | **Preferred.** QMK generates `config.h`/`rules.mk` values from it. |
| `config.h` | C preprocessor `#define` directives. | Legacy but still required for options not yet migrated. |
| `rules.mk` | GNU make variables (features, MCU, sources). | Legacy; feature enables now also expressible in `info.json`. |

All three file types exist at a **priority stack**: QMK Default → Keyboard → Folder (up to 5 deep) → Keymap. Higher-priority files override lower ones. `#undef <VAR>` can undefine a lower-level declaration in a keymap before redefining it.

---

## 2. The Data-Driven Migration (why `info.json` is the modern path)

Historically QMK was configured only through `rules.mk` + `config.h`. With ~4000 keyboards that became ~6000 freeform config files under `keyboards/` alone — unmaintainable. QMK introduced `info.json` as a single source of truth that:

- Is validated by a JSON Schema (`data/schemas/keyboard.jsonschema`).
- Is consumed by the **QMK API** and **QMK Configurator** to render the keyboard and its layouts.
- Is compiled into generated `config.h`/`rules.mk` at build time (written to `.build/obj_<keyboard>_<keymap>/src/info_config.h` and `.../rules.mk`).

### 2.1 What this means for editing keyboards

- **Prefer `info.json`/`keyboard.json`** for any option that has a schema key (see §5).
- Both `info.json` and `keyboard.json` are valid for the same content. A `keyboard.json` in a folder marks that folder as a **buildable keyboard**; an `info.json` at a parent level holds shared metadata.
- `config.h`/`rules.mk` are still required for anything **not yet data-driven** (see §8).

### 2.2 How a new option becomes data-driven (QMK internals — for contributors)

1. Add the option to the schema in `data/schemas/keyboard.jsonschema`.
2. Add a mapping in `data/mappings/info_config.hjson` (→ `config.h`) or `data/mappings/info_rules.hjson` (→ `rules.mk`). Each mapping is keyed by the `config.h`/`rules.mk` variable name and has:
   - `info_key` (required) — JSON dot-notation path, e.g. `rgblight.split_count`.
   - `value_type` (optional, default `raw`) — one of `array`, `array.int`, `int`, `hex`, `list`, `mapping`, `str`.
   - `to_json` / `to_c` (optional booleans, default `true`) — whether to extract to JSON / emit to C.
   - `warn_duplicate` (optional, default `true`).
3. (Optional, discouraged) Add extraction code to `lib/python/qmk/info.py` (`_extract_<feature>()` called from `_extract_config_h()`/`_extract_rules_mk()`) and generation code to `lib/python/qmk/cli/generate/config_h.py` or `.../rules_mk.py`.

On the C side nothing changes: new `#define`s still get a doc entry in `docs/config_options.md`, a default in the relevant core file, and `#ifdef` guards.

### 2.3 Gotchas — migration
- **Duplicate warnings:** if a value exists in both `info.json` and `config.h`/`rules.mk`, QMK warns (unless the mapping sets `warn_duplicate: false`). Pick one home for each value.
- **`keyboard.json` vs `info.json` are interchangeable content-wise**, but only the presence of `keyboard.json` makes a folder a build target.
- The generated `info_config.h` is read **between** the keyboard's deepest `config.h` and the keymap `config.h` (see §9.1 reading order) — so keymap `config.h` still wins.

---

## 3. The `config.h` file — option categories (legacy reference)

A C header included early and persistent across the build. Should **not** `#include` other `config.h` files. Categories below map to `info.json` keys in §5; only items without a data-driven equivalent **must** live here.

### 3.1 Hardware options

| `#define` | Type/Unit | Default | Meaning |
|-----------|-----------|---------|---------|
| `VENDOR_ID` | hex | — | USB VID (any value for DIY) |
| `PRODUCT_ID` | hex | — | USB PID |
| `DEVICE_VER` | hex | — | Device version (often hardware revision) |
| `MANUFACTURER` | string | — | USB manufacturer string |
| `PRODUCT` | string | — | USB product string / keyboard name |
| `MATRIX_ROWS` | int | — | Number of matrix rows |
| `MATRIX_COLS` | int | — | Number of matrix columns |
| `MATRIX_ROW_PINS` | `{ pins }` | — | Row pins, top→bottom. Omit only with custom matrix. |
| `MATRIX_COL_PINS` | `{ pins }` | — | Column pins, left→right. Omit only with custom matrix. |
| `MATRIX_IO_DELAY` | µs | `30` | Delay between setting a matrix pin and reading it |
| `MATRIX_HAS_GHOST` | flag | off | Matrix has ghosting (rare) |
| `MATRIX_UNSELECT_DRIVE_HIGH` | flag | off | On unselect, drive pins output-high instead of input-high |
| `DIODE_DIRECTION` | `COL2ROW`/`ROW2COL` | — | Diode orientation. COL2ROW = diode mark faces rows, between switch and row. |
| `DIRECT_PINS` | 2D `{ pins }` | — | Each switch on its own pin + ground (no diode matrix) |
| `DEBOUNCE` | ms | `5` | Debounce time |
| `LOCKING_SUPPORT_ENABLE` | flag | off | Mechanical locking switch support (use `KC_LCAP`/`KC_LNUM`/`KC_LSCR`) |
| `LOCKING_RESYNC_ENABLE` | flag | off | Keep switch state consistent with host LED state |
| `IS_COMMAND()` | macro | shift-only | Magic/Command key combo for debugging |
| `USB_MAX_POWER_CONSUMPTION` | mA | `500` | Max USB current declared to host (does not limit real draw) |
| `USB_POLLING_INTERVAL_MS` | ms | `10` | USB polling interval (keyboard/mouse/shared) |
| `USB_SUSPEND_WAKEUP_DELAY` | ms | `0` | Pause after sending USB wakeup packet (try ~200 if wake fails) |
| `F_SCL` | Hz | `400000` (serial-split: `100000`) | I²C clock rate |

> **Deprecated in favor of `info.json`:** `VENDOR_ID`→`usb.vid`, `PRODUCT_ID`→`usb.pid`, `DEVICE_VER`→`usb.device_version`, `MANUFACTURER`→`manufacturer`, `PRODUCT`→`keyboard_name`, matrix pins→`matrix_pins`, `DEBOUNCE`→`debounce`, `DIODE_DIRECTION`→`diode_direction`, `USB_*`→`usb.*`. See §5.

### 3.2 Features that can be DISABLED (saves code size)

| `#define` | Effect |
|-----------|--------|
| `NO_DEBUG` | Disable debugging |
| `NO_PRINT` | Disable printing/`hid_listen` |
| `NO_ACTION_LAYER` | Disable layers |
| `NO_ACTION_TAPPING` | Disable tap dance / tapping features |
| `NO_ACTION_ONESHOT` | Disable one-shot modifiers |

### 3.3 Features that can be ENABLED

| `#define` | Effect |
|-----------|--------|
| `ENABLE_COMPILE_KEYCODE` | Enables the `QK_MAKE` keycode |
| `STRICT_LAYER_RELEASE` | Evaluate key release against the *current* layer stack rather than the layer the key came from (advanced) |

### 3.4 Behavior knobs (tapping / combos / leader / oneshot / mouse)

The **modern** home for these is the `info.json` `tapping` block (see §5.4) plus per-feature blocks (`combo`, `leader_key`, `oneshot`, `mouse_key`). Legacy `config.h` equivalents:

| `#define` | Unit | Default | Meaning |
|-----------|------|---------|---------|
| `TAPPING_TERM` | ms | `200` | Time before a press becomes a hold |
| `TAPPING_TERM_PER_KEY` | flag | off | Enable per-key `TAPPING_TERM` |
| `RETRO_TAPPING` / `RETRO_TAPPING_PER_KEY` | flag | off | Tap anyway after `TAPPING_TERM` if uninterrupted |
| `TAPPING_TOGGLE` | count | `5` (dd) | Taps before toggle |
| `PERMISSIVE_HOLD` / `..._PER_KEY` | flag | off | Hold triggers if another key pressed before release |
| `QUICK_TAP_TERM` | ms | `= TAPPING_TERM` | Tap-then-hold repeats dual-role key; also retunes `TT`/OS-tap-toggle |
| `QUICK_TAP_TERM_PER_KEY` | flag | off | Per-key `QUICK_TAP_TERM` |
| `HOLD_ON_OTHER_KEY_PRESS` / `..._PER_KEY` | flag | off | Pick hold action as soon as another key interrupts the tap |
| `LEADER_TIMEOUT` | ms | `300` | Leader sequence timeout |
| `LEADER_PER_KEY_TIMING` | flag | off | Reset timeout per keypress |
| `LEADER_KEY_STRICT_KEY_PROCESSING` | flag | off | Don't unwrap Mod-Tap/Layer-Tap into tap keycodes |
| `MOUSE_EXTENDED_REPORT` | flag | off | Extended reports (-32767..32767 vs -127..127) for pointing/mousekeys |
| `ONESHOT_TIMEOUT` | ms | `300` | One-shot timeout |
| `ONESHOT_TAP_TOGGLE` | count | — | Taps to toggle one-shot |
| `COMBO_TERM` | ms | `= TAPPING_TERM` | Combo detection window (dd default `50`) |
| `COMBO_MUST_HOLD_MODS` | flag | off | Extend timeout for mod-containing combos |
| `COMBO_MOD_TERM` | ms | `200` | Extend `COMBO_TERM` for mods mid-combo |
| `COMBO_MUST_HOLD_PER_COMBO` | flag | off | Per-combo `get_combo_must_hold()` |
| `COMBO_TERM_PER_COMBO` | flag | off | Per-combo `get_combo_term()` |
| `COMBO_STRICT_TIMER` | flag | off | Start combo timer only on first keypress |
| `COMBO_NO_TIMER` | flag | off | Disable combo timer (relaxed combos) |
| `TAP_CODE_DELAY` | ms | `0` | Delay between `register_code`/`unregister_code` (fixes V-USB) |
| `TAP_HOLD_CAPS_DELAY` | ms | `80` | Extra delay for `LT`/`MT` taps of `KC_CAPS_LOCK` (macOS quirk; try ~200) |
| `KEY_OVERRIDE_REPEAT_DELAY` | ms | `500` | Key-override repeat interval |
| `LEGACY_MAGIC_HANDLING` | flag | off | Magic handling for advanced keycodes (Mod Tap/Layer Tap) |

### 3.5 RGB light (`config.h`) → see `07-led-rgb-backlight.md`

`WS2812_DI_PIN`, `RGBLIGHT_LAYERS`, `RGBLIGHT_MAX_LAYERS` (default 8, ≤32), `RGBLIGHT_LAYER_BLINK`, `RGBLIGHT_LAYERS_OVERRIDE_RGB_OFF`, `RGBLIGHT_LED_COUNT`, `RGBLIGHT_SPLIT`, `RGBLED_SPLIT`, `RGBLIGHT_HUE_STEP`, `RGBLIGHT_SAT_STEP`, `RGBLIGHT_VAL_STEP`, `WS2812_RGBW`, `BACKLIGHT_PIN`, `BACKLIGHT_LEVELS` (≤31), `BACKLIGHT_BREATHING`, `BREATHING_PERIOD` (s). **Data-driven equivalents:** `rgblight.*`, `ws2812.*`, `backlight.*` (§5).

### 3.6 Mouse keys (`config.h`)

`MOUSEKEY_INTERVAL 20`, `MOUSEKEY_DELAY 0`, `MOUSEKEY_TIME_TO_MAX 60`, `MOUSEKEY_MAX_SPEED 7`, `MOUSEKEY_WHEEL_DELAY 0` → `mouse_key.*` (§5).

### 3.7 Split keyboard (`config.h`) — see `10-connectivity.md`

Requires `SPLIT_KEYBOARD = yes`. Handedness (in precedence order): `SPLIT_HAND_PIN` → `EE_HANDS` (flash `eeprom-lefthand.eep`/`righthand.eep`; or `:dfu-split-left/right`, `:avrdude-split-left/right`, `:dfu-util-split-left/right`) → `MASTER_RIGHT` → default (USB side = master = left). Other: `USE_I2C` (AVR-only; default serial, ARM-supported), `SOFT_SERIAL_PIN`, `MATRIX_ROW_PINS_RIGHT`/`MATRIX_COL_PINS_RIGHT`/`DIRECT_PINS_RIGHT`, `SELECT_SOFT_SERIAL_SPEED` (0=189kbps … 5=20kbps, default 1), `SPLIT_USB_DETECT`/`SPLIT_USB_TIMEOUT` (2000)/`SPLIT_USB_TIMEOUT_POLL` (10), `SPLIT_WATCHDOG_ENABLE`/`SPLIT_WATCHDOG_TIMEOUT` (3000), `FORCED_SYNC_THROTTLE_MS` (100), `SPLIT_TRANSPORT_MIRROR`, `SPLIT_LAYER_STATE_ENABLE`, `SPLIT_LED_STATE_ENABLE`, `SPLIT_MODS_ENABLE`, `SPLIT_WPM_ENABLE`, `SPLIT_OLED_ENABLE`, `SPLIT_ST7565_ENABLE`, `SPLIT_TRANSACTION_IDS_KB`/`_USER`. **Data-driven:** `split.*` (§5.11).

---

## 4. The `rules.mk` file

A GNU make file included by the top-level `Makefile`; configures the MCU and feature on/off. Many settings now also expressible in `info.json`.

### 4.1 Build options

| Variable | Meaning |
|----------|---------|
| `FIRMWARE_FORMAT` | Output format: `bin` / `hex` (dd adds `uf2`) |
| `SRC` | Files added to compile/link |
| `LIB_SRC` | Library files, linked **after** `SRC` |
| `LAYOUTS` | Community layouts this keyboard supports |
| `LTO_ENABLE` | Link-Time Optimization (smaller binary, slower build) |

### 4.2 AVR MCU options

`MCU = atmega32u4`, `F_CPU = 16000000`, `ARCH = AVR8`, `F_USB = $(F_CPU)`, `OPT_DEFS += -DINTERRUPT_CONTROL_ENDPOINT`, `BOOTLOADER =` one of `atmel-dfu` | `lufa-dfu` | `qmk-dfu` | `qmk-hid` | `halfkay` | `caterina` | `bootloadhid` | `usbasploader`.

### 4.3 Feature on/off switches {#feature-options-rulesmk}

> Each `XXX_ENABLE` here is also expressible as `features.<xxx>` in `info.json` (§5.2).

| Variable | Feature |
|----------|---------|
| `MAGIC_ENABLE` | Magic actions (BOOTMAGIC without the boot) |
| `BOOTMAGIC_ENABLE` | Bootmagic |
| `MOUSEKEY_ENABLE` | Mouse keys |
| `EXTRAKEY_ENABLE` | Audio + System control |
| `CONSOLE_ENABLE` | Debug console |
| `COMMAND_ENABLE` | Debug/config commands |
| `COMBO_ENABLE` | Key combos |
| `NKRO_ENABLE` | USB N-Key Rollover |
| `AUDIO_ENABLE` | Audio subsystem |
| `KEY_OVERRIDE_ENABLE` | Key overrides |
| `RGBLIGHT_ENABLE` | Underglow |
| `LEADER_ENABLE` | Leader key |
| `MIDI_ENABLE` | MIDI |
| `UNICODE_ENABLE` | Unicode |
| `BLUETOOTH_ENABLE` | Bluetooth (bluefruit_le, rn42) |
| `SPLIT_KEYBOARD` | Split keyboard (dual MCU; pulls in `quantum/split_common`) |
| `CUSTOM_MATRIX` | Custom matrix scan |
| `DEBOUNCE_TYPE` | Alternative debounce algorithm (§6.2) |
| `USB_WAIT_FOR_ENUMERATION` | Wait for USB enumeration before startup |
| `NO_USB_STARTUP_CHECK` | Disable post-startup USB suspend check (useful for split) |
| `DEFERRED_EXEC_ENABLE` | Deferred executor (timed callbacks) |
| `DYNAMIC_TAPPING_TERM_ENABLE` | Configure global tapping term at runtime |

### 4.4 USB endpoint budget

USB endpoints are a **finite per-MCU resource**; exceeding them is a build error. Features that can each need an endpoint: `MOUSEKEY_ENABLE`, `EXTRAKEY_ENABLE`, `CONSOLE_ENABLE`, `NKRO_ENABLE`, `MIDI_ENABLE`, `RAW_ENABLE`, `VIRTSER_ENABLE`.

By default `MOUSEKEY` + `EXTRAKEY` + `NKRO` share one endpoint. `KEYBOARD_SHARED_EP = yes` folds the base keyboard in too (frees one endpoint, but breaks Boot Keyboard in some BIOSes). `MOUSE_SHARED_EP = no` uncombines the mouse (breaks Boot Mouse compat).

---

## 5. The `info.json` schema — full reference by feature block

The schema lives in `data/schemas/keyboard.jsonschema`. `info.json` files at every level under `keyboards/<keyboard>/` are merged (more-specific overrides less-specific). Types in `<Badge>`: `String`, `Number`, `Boolean`, `Pin`, `Matrix` (`[row, col]`), `KeyUnit`, `Array: <T>`, `Object: <T>`.

### 5.1 General metadata (required)

| Key | Type | Notes |
|-----|------|-------|
| `keyboard_name` | String (**required**) | USB product string; Unicode via `\u03A8` (Ψ) |
| `maintainer` | String (**required**) | GitHub username, or `qmk` for community-maintained |
| `manufacturer` | String (**required**) | USB manufacturer string |
| `url` | String (**required**) | Product/browse page |
| `bootloader_instructions` | String | How to enter flash mode |
| `tags` | Array<String> | e.g. `["ortho","split","rgb"]` |

### 5.2 Hardware + firmware configuration

| Key | Type | Notes |
|-----|------|-------|
| `board` | String | Override ChibiOS board name (ARM only) |
| `bootloader` | String | Bootloader (required if no `development_board`) |
| `development_board` | String | e.g. `"promicro"` (required if no `processor`) |
| `pin_compatible` | String | Form factor: `elite_c` | `promicro` |
| `processor` | String | MCU (required if no `development_board`) |
| `build.debounce_type` | String | `asym_eager_defer_pk` | `custom` | `sym_defer_g` | `sym_defer_pk` | `sym_defer_pr` | `sym_eager_pk` | `sym_eager_pr` |
| `build.firmware_format` | String | `bin` | `hex` | `uf2` |
| `build.lto` | Boolean (default `false`) | Link-Time Optimization |
| `features` | Object<Boolean> | Feature on/off, e.g. `{"rgb_matrix": true, "rgblight": false}` |

#### 5.2.1 `qmk` block

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `qmk.locking.enabled` | Boolean | `false` | Locking-switch support |
| `qmk.locking.resync` | Boolean | `false` | Keep switch state consistent with host LEDs |
| `qmk.tap_capslock_delay` | Number (ms) | `80` | Delay for Caps Lock tap events |
| `qmk.tap_keycode_delay` | Number (ms) | `0` | Delay for generic tap events |

### 5.3 Tapping block (replaces `TAPPING_*` defines) {#tapping-block}

| Key | Type | Default |
|-----|------|---------|
| `tapping.chordal_hold` | Boolean | `false` |
| `tapping.hold_on_other_key_press` | Boolean | `false` |
| `tapping.hold_on_other_key_press_per_key` | Boolean | `false` |
| `tapping.permissive_hold` | Boolean | `false` |
| `tapping.permissive_hold_per_key` | Boolean | `false` |
| `tapping.retro` | Boolean | `false` |
| `tapping.retro_per_key` | Boolean | `false` |
| `tapping.term` | Number (ms) | `200` |
| `tapping.term_per_key` | Boolean | `false` |
| `tapping.toggle` | Number | `5` |

### 5.4 LED/lighting drivers (see `07-led-rgb-backlight.md`, `13-drivers-lowlevel.md`)

**`apa102`** — `clock_pin` (req), `data_pin` (req), `default_brightness` (0–31, default 31).
**`backlight`** — `as_caps_lock`, `breathing`, `breathing_period` (s, default 6), `default.{on,breathing,brightness}`, `driver` (`custom`|`pwm`|`software`|`timer`, default `pwm`), `levels` (1–31, default 3), `max_brightness` (0–255, default 255), `on_state` (0|1, default 1), `pin`, `pins`.
**`rgblight`** — `led_count` (req), `animations`, `brightness_steps` (default 17), `default.{animation,on,hue,sat,val,speed}`, `driver` (`apa102`|`custom`|`ws2812`, default `ws2812`), `hue_steps` (8), `layers.{blink,enabled,max (1–32, default 8)}`, `led_map`, `max_brightness` (255), `saturation_steps` (17), `sleep`, `split` (default false), `split_count`.
**`led_matrix`** / **`rgb_matrix`** — `driver` (req), `layout` (req; array of `{flags,x(0–224),y(0–64),matrix?}`), `animations`, `center_point` (default `[112,32]`), `flag_steps`, `default.{animation,on,hue?(rgb only),sat?(rgb only),val,speed,flags}`, `hue_steps`(rgb 8)/`sat_steps`(rgb 16), `led_flush_limit` (16), `led_process_limit` (`(led_count+4)/5`), `max_brightness` (255), `react_on_keyup` (false), `sleep` (false), `speed_steps` (16), `split_count`, `timeout` (ms, default 0), `val_steps` (8 led / 16 rgb).
  - `led_matrix.driver`: `custom`|`is31fl3218`|`is31fl3731`|`is31fl3733`|`is31fl3736`|`is31fl3737`|`is31fl3741`|`is31fl3742a`|`is31fl3743a`|`is31fl3745`|`is31fl3746a`|`snled27351`.
  - `rgb_matrix.driver`: adds `aw20216s`, `is31fl3236`, `is31fl3729`, `ws2812`.
**`ws2812`** — `driver` (`bitbang`|`custom`|`i2c`|`pwm`|`spi`|`vendor`, default `bitbang`), `pin` (req for bitbang/pwm/spi/vendor), `i2c_address` (default `"0xB0"`), `i2c_timeout` (ms, default 100), `rgbw` (false).
**`indicators`** — `caps_lock`/`compose`/`kana`/`num_lock`/`scroll_lock` (Pins), `on_state` (0|1, default 1).

### 5.5 Matrix configuration {#matrix-block}

```
"matrix_pins": {
  "rows": ["B0","B1","B2"],
  "cols": ["A0","A1","A2"],
  "direct": [["A0","A1"],["B0","B1"]],
  "custom": false,
  "custom_lite": false,
  "ghost": false,
  "input_pressed_state": 0,
  "io_delay": 30,
  "masked": false
},
"diode_direction": "COL2ROW",
"debounce": 5
```

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `matrix_pins.cols` | Array<Pin> | — | Column pins, left→right |
| `matrix_pins.rows` | Array<Pin> | — | Row pins, top→bottom |
| `matrix_pins.direct` | 2D Array<Pin> | — | Direct-pin matrix (no diodes); `diode_direction` unused |
| `matrix_pins.custom` | Boolean | `false` | Full custom matrix scan |
| `matrix_pins.custom_lite` | Boolean | `false` | "Lite" custom scan |
| `matrix_pins.ghost` | Boolean | `false` | No anti-ghosting diodes |
| `matrix_pins.input_pressed_state` | 0\|1 | `0` | GPIO state of input pins when pressed |
| `matrix_pins.io_delay` | Number (µs) | `30` | Wait between select and read |
| `matrix_pins.masked` | Boolean | `false` | Ignore unconfigured intersections |
| `diode_direction` | `COL2ROW`/`ROW2COL` | — | Diode orientation (unused for `direct`) |
| `debounce` | Number (ms) | `5` | Debounce time; `0` disables |

### 5.6 Layouts (the LAYOUT macro source) {#layouts-block}

This is the **data-driven source of the C `LAYOUT(...)` macros**. The build generates the matrix-aware `LAYOUT_<name>(...)` macro from the `matrix` field of each key entry, so a keyboard no longer needs to hand-write `#define LAYOUT_60_ansi(...)` in its `.h`.

| Key | Type | Notes |
|-----|------|-------|
| `community_layouts` | Array<String> | e.g. `["60_ansi","60_iso"]` |
| `layout_aliases` | Object<String> | Map alias → real layout, e.g. `{"LAYOUT_ansi":"LAYOUT_60_ansi"}` |
| `layouts` | Object | Dict of `LAYOUT_<name>` → `{ layout: [ ...keys ] }` |

Each key object: `matrix` `[row,col]` (**required**, ties the key to the matrix), `x` (KeyUnit, req), `y` (KeyUnit, req), `w` (default 1), `h` (default 1), `label` (human/Configurator label — **not** a keymap assignment), `r`/`rx`/`ry` (rotation — **not implemented**), `hand` (`"L"`/`"R"`/`"*"` for Chordal Hold), `encoder` (encoder index this key is linked to).

Example:
```json
"LAYOUT_all": {
  "layout": [
    {"label":"Esc","matrix":[0,0],"x":0,"y":0},
    {"label":"Shift","matrix":[4,0],"x":0,"y":4.25,"w":2.25},
    {"label":"Enter","matrix":[2,6],"x":0,"y":2,"w":1.25,"h":2}
  ]
}
```

- The ISO enter is represented as a **1.25u×2uh** key.
- Coordinates are absolute from the keyboard's top-left, in key units.
- See §7 for community layouts + submission naming.

### 5.7 USB

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `usb.vid` | String (hex) (**required**) | — | e.g. `"0xC1ED"` |
| `usb.pid` | String (hex) (**required**) | — | e.g. `"0x23B0"` |
| `usb.device_version` | String (**required**) | — | BCD `MM.m.r` (≤`99.9.9`) |
| `usb.max_power` | Number (mA) | `500` | Declared max current (does not limit real draw) |
| `usb.no_startup_check` | Boolean | `false` | Disable post-startup suspend check |
| `usb.polling_interval` | Number (ms) | `1` (1000 Hz) | Host polling rate |
| `usb.shared_endpoint.keyboard` | Boolean | `false` | Keyboard reports via shared endpoint |
| `usb.shared_endpoint.mouse` | Boolean | `true` | Mouse reports via shared endpoint |
| `usb.suspend_wakeup_delay` | Number (ms) | `0` | Pause after wakeup packet |
| `usb.wait_for_enumeration` | Boolean | `false` | Wait for enumeration before startup |

### 5.8 EEPROM backend {#eeprom-block}

```json
"eeprom": {
  "driver": "wear_leveling",
  "wear_leveling": {
    "driver": "embedded_flash",
    "backing_size": 16384,
    "logical_size": 4096
  }
}
```

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `eeprom.driver` | String | `"vendor"` | `custom` \| `i2c` \| `legacy_stm32_flash` \| `spi` \| `transient` \| `vendor` \| `wear_leveling` |
| `eeprom.wear_leveling.driver` | String | — | `embedded_flash` \| `legacy` \| `rp2040_flash` \| `spi_flash` \| `custom` |
| `eeprom.wear_leveling.backing_size` | Number | — | Bytes for backing store; must be a **multiple of `logical_size`** |
| `eeprom.wear_leveling.logical_size` | Number | — | Usable EEPROM bytes exposed to QMK |

See §6.3 for the EEPROM feature API and write-endurance caveat.

### 5.9 Other feature blocks (summary; see cross-linked references)

| Block | Notable keys |
|-------|--------------|
| `audio` | `driver` (`dac_additive`/`dac_basic`/`pwm_software`/`pwm_hardware`), `pins` (req), `default.{on,clicky}`, `macro_beep`, `power_control.{pin,on_state}`, `voices` — see `09-audio-haptic.md` |
| `battery` | `driver` (`adc`/`custom`/`vendor`), `adc.{pin(req),reference_voltage(3300),divider_r1(100),divider_r2(100),resolution(10)}`, `sample_interval`(30000 ms) — see `13-drivers-lowlevel.md` |
| `bluetooth` | `driver` (`custom`/`bluefruit_le`/`rn42`) — see `10-connectivity.md` |
| `bootmagic` | `enabled`, `matrix` (default `[0,0]`) — see `11-other-features.md` |
| `caps_word` | `enabled`, `both_shifts_turns_on`, `double_tap_shift_turns_on`, `idle_timeout`(5000 ms), `invert_on_shift` — see `05-text-input-and-combos.md` |
| `combo` | `term` (default 50 ms) — see `05-text-input-and-combos.md` |
| `dip_switch` | `enabled`, `pins`, `matrix_grid` — see `11-other-features.md` |
| `encoder` | `rotary: [{pin_a(req),pin_b(req),resolution(4)}]` — see `08-displays.md` |
| `host` | `default.nkro` (false) |
| `keycodes` | Array of `{key(req),label,aliases[]}` — custom keycodes |
| `leader_key` | `timing`, `strict_processing`, `timeout`(300 ms) — see `05-text-input-and-combos.md` |
| `mouse_key` | `enabled`, `delay`, `interval`, `max_speed`, `time_to_max`, `wheel_delay` — see `06-pointing-and-hid-devices.md` |
| `oneshot` | `tap_toggle`, `timeout` — see `04-keymaps-and-keycodes.md` |
| `ps2` | `clock_pin`, `data_pin`, `driver` (`busywait`/`interrupt`/`usart`/`vendor`, default `busywait`), `enabled`, `mouse_enabled` — see `06-pointing-and-hid-devices.md` |
| `qmk_lufa_bootloader` | `esc_input`(req), `esc_output`(req), `led`, `speaker` |
| `secure` | `enabled`, `idle_timeout`(60000 ms), `unlock_sequence` (≤5 matrices), `unlock_timeout`(5000 ms) — see `10-connectivity.md` |
| `stenography` | `enabled`, `protocol` (`all`/`geminipr`/`txbolt`, default `all`) — see `11-other-features.md` |

### 5.10 Layout JSON / KLE conversion

The `layouts` block (§5.6) uses [Keyboard Layout Editor](https://keyboard-layout-editor.com) concepts (x/y/w/h, rotation) but **each key is stateless** — nothing is inherited from the previous key. To generate a starting `info.json` layout from a KLE raw-data blob, use:

```
qmk new-keyboard        # interactive; imports KLE
# or the Configurator's "Import KLE" / qmk tooling
```

### 5.11 Split block (see `10-connectivity.md`)

```json
"split": {
  "enabled": true,
  "handedness": { "pin": "D0" },                 // or "matrix_grid": ["A1","B5"]
  "matrix_pins": { "right": { /* like matrix_pins */ } },
  "serial": { "driver":"bitbang", "pin":"D0", "speed":1 },
  "transport": {
    "protocol": "serial",
    "sync": { "layer_state":true, "modifiers":true, "matrix_state":true, /* ... */ },
    "watchdog": false,
    "watchdog_timeout": 3000
  },
  "usb_detect": { "enabled":true, "polling_interval":10, "timeout":2000 },
  "encoder": { "right": { "rotary": [ /* encoder objects */ ] } },
  "dip_switch": { "right": { "pins": [] } },
  "bootmagic": { "matrix": [0,0] }
}
```

`serial.driver` ∈ `bitbang`|`usart`|`vendor` (default `bitbang`). `transport.protocol` ∈ `custom`|`i2c`|`serial`. `transport.sync.*` booleans (all default `false`): `activity`, `detected_os`, `haptic`, `layer_state`, `indicators`, `matrix_state`, `modifiers`, `oled`, `st7565`, `wpm`. `serial.speed` 0–5 (fastest→slowest, default 1).

---

## 6. Matrix, debounce, and EEPROM internals

### 6.1 Matrix reading order

The matrix is scanned each `matrix_scan` (see `01-architecture.md` for where it sits in the main loop). For a diode matrix: strobe one row/col, wait `matrix.io_delay` µs, read the other axis, advance. `input_pressed_state` flips the read polarity; `ghost`/`masked` handle no-diode and partial matrices. Split keyboards: the slave's matrix is transported to the master (see `10-connectivity.md`).

### 6.2 Debounce algorithms {#debounce-algorithms}

Mechanical switches bounce; software debouncing reports a clean transition. Select with **`build.debounce_type`** in `info.json` or **`DEBOUNCE_TYPE =`** in `rules.mk`. Default `sym_defer_g` when unset.

**Debounce time:** set via `debounce` (info.json) or `#define DEBOUNCE 10` (config.h, default 5 ms). **`DEBOUNCE 0` disables debouncing.**

#### Algorithm dimensions

1. **Time unit:** all built-ins are **timestamp (ms)** based, not cycle based. (Cycle-based would couple settling time to scan rate — avoided.)
2. **Symmetric vs asymmetric:** same algo for up/down (`sym_*`) vs different (`asym_*`).
3. **Eager vs defer:** *Eager* reports immediately then ignores changes for DEBOUNCE ms (**not noise-resistant**). *Defer* waits for DEBOUNCE ms of no change before reporting (**noise-resistant**).
4. **Scope:** Global (`_g`, one timer), Per-row (`_pr`), Per-key (`_pk`).

#### Built-in algorithms

| Algorithm | Scope | Up/Down | Noise-resistant? | Tradeoff |
|-----------|-------|---------|------------------|----------|
| `sym_defer_g` *(default)* | global | defer/defer | ✅ | Highest perf, lowest RAM; whole-board latency |
| `sym_defer_pr` | per-row | defer/defer | ✅ | More responsive than `_g`, less noise-prone than per-key |
| `sym_defer_pk` | per-key | defer/defer | ✅ | Per-key responsiveness; more RAM/CPU |
| `sym_eager_pr` | per-row | eager/eager | ❌ | Immediate; good for slow/rotated matrices (e.g. ErgoDox) |
| `sym_eager_pk` | per-key | eager/eager | ❌ | Immediate per-key; not noise-resistant |
| `asym_eager_defer_pk` | per-key | down=eager / up=defer | down no, up yes | Snappy key-down, clean key-up |

**Choosing:** want lowest latency and your switches/matrix are clean → `sym_eager_pk`. Want robustness on a noisy build → `sym_defer_g`/`_pk`. Want snappy presses but clean releases → `asym_eager_defer_pk`. ErgoDox-style rotated/slow matrices → `sym_eager_pr`.

**Custom debounce:** `DEBOUNCE_TYPE = custom` + `SRC += debounce.c` implementing `debounce.c` (see `quantum/debounce`). Debouncing runs after every raw matrix scan; use `num_rows` (not `MATRIX_ROWS`) to support splits correctly.

#### Gotchas — debounce
- Only timestamp-based algorithms exist; there is **no cycle-based** built-in yet.
- Eager algorithms **will pass through noise** as spurious keypresses — never use them on a noisy/ghosting matrix.
- `DEBOUNCE 0` **disables** debouncing entirely (not "minimal").

### 6.3 EEPROM — persistent config + backends

EEPROM holds persistent settings (RGB defaults, layer indication toggles, etc.) across power loss. Two **mutually exclusive** APIs:

#### Basic API — one DWORD (4 bytes) per side

| Function | Layer | Purpose |
|----------|-------|---------|
| `void eeconfig_init_kb(void)` / `_user(void)` | kb/user | Set defaults on EEPROM reset (force with `EE_CLR` or Bootmagic) |
| `uint32_t eeconfig_read_kb(void)` / `_user(void)` | kb/user | Read the 32-bit value |
| `void eeconfig_update_kb(uint32_t val)` / `_user(void)` | kb/user | Write the 32-bit value |

Idiom — pack settings into a `union { uint32_t raw; struct { bool flag:1; uint8_t x:8; ... }; }`, read in `keyboard_post_init_user`, write on change, re-derive in `eeconfig_init_user`.

#### Datablock API — larger blobs

> ⚠️ When datablock is in use, the basic DWORD API is **unavailable**.

In `config.h`: `EECONFIG_KB_DATA_SIZE` (default 0) and optional `EECONFIG_KB_DATA_VERSION` (invalidates stored data on bump); equivalent `_USER_` defines.

```c
bool     eeconfig_is_kb_datablock_valid(void);                          // kb / _user
uint32_t eeconfig_read_kb_datablock(void *data, uint32_t off, uint32_t len);
uint32_t eeconfig_update_kb_datablock(const void *data, uint32_t off, uint32_t len);
void     eeconfig_init_kb_datablock(void);
// field helpers:
eeconfig_read_kb_datablock_field(obj, field);
eeconfig_update_kb_datablock_field(obj, field);
```

#### Backends (set via `eeprom.driver` in info.json — §5.8)

| Driver | Use |
|--------|-----|
| `vendor` *(default)* | MCU's native EEPROM (AVR EEPROM, etc.) |
| `transient` | RAM-only; lost on power-off (testing) |
| `i2c` | External I²C EEPROM chip |
| `spi` | External SPI flash/EEPROM |
| `legacy_stm32_flash` | Legacy STM32 flash emulation |
| `wear_leveling` | Flash-backed with wear-leveling (modern ARM/RP2040) — sub-driver `wear_leveling.driver`: `embedded_flash` | `legacy` | `rp2040_flash` | `spi_flash` | `custom` |
| `custom` | Hand-rolled |

`backing_size` must be a **multiple** of `logical_size`.

#### Gotchas — EEPROM
- **Limited write endurance.** EEPROM/flash cells die after too many writes. Batch writes; avoid writing every scan. Writing too often can brick the MCU's persistent storage.
- Basic and datablock APIs are **mutually exclusive** — pick one per side.
- The basic API gives only **32 bits** per side — bit-pack with a `union`.
- Forcing a reset: `EE_CLR` keycode or Bootmagic. Re-bump `EECONFIG_*_DATA_VERSION` to invalidate datablocks after a struct layout change.
- Wear-leveling `backing_size` ≠ `logical_size`: you allocate more flash than the usable EEPROM.

---

## 7. Community layouts & LAYOUT macro generation

### 7.1 The layouts/ tree

```
layouts/
├── default/<layout>/        # one reference keymap named default_<layout>
└── community/<layout>/      # community keymaps
```

Each layout folder is lowercase `[a-z0-9_]+`, named for the physical layout generically (e.g. `60_ansi`, `ortho_4x12`), and contains a `readme.md` naming the layout (`# 60_ansi\n\n   LAYOUT_60_ansi`). Existing standard names (dozens: `60_ansi`, `60_iso`, `60_jis`, `64_ansi`, `65_ansi_blocker_tsangan_split_bs`, `tkl_ansi`, …) should be reused; new names go through PR/Issue discussion.

### 7.2 Supporting a community layout on your keyboard

Data-driven: add to `info.json`:
```json
"community_layouts": ["60_ansi", "60_iso"]
```
and define matching `LAYOUT_60_ansi`/`LAYOUT_60_iso` entries in the `layouts` block (§5.6). Legacy `rules.mk`: `LAYOUTS = 60_ansi`.

Build any of them: `make <keyboard>:<layout>`. If the keyboard supports multiple layouts and a keymap exists for several, force one with `FORCE_LAYOUT=ortho_4x4`.

### 7.3 Keyboard-agnostic keymaps

- Include the current keyboard's header with `#include QMK_KEYBOARD_H` (never `#include "planck.h"` in a layout keymap).
- Use the `LAYOUT_<layout>` macro (e.g. `LAYOUT_ortho_4x12`), not a board-specific macro, so the same keymap builds for a Let's Split and a Planck.
- Conditionalize board-specific code with `#ifdef KEYBOARD_<folder1>_<folder2>` (lowercase, matches folder names exactly): `KEYBOARD_planck`, `KEYBOARD_planck_rev4`.

---

## 8. Options NOT yet data-driven

These still require `config.h` and/or `rules.mk` even when you use `info.json`:

- **All `config.h` behavior knobs in §3.4 that have no `info.json` key** — notably the per-key/per-combo *enable flags* (`TAPPING_TERM_PER_KEY`, `PERMISSIVE_HOLD_PER_KEY`, `HOLD_ON_OTHER_KEY_PRESS_PER_KEY`, `RETRO_TAPPING_PER_KEY`, `QUICK_TAP_TERM_PER_KEY`, `COMBO_MUST_HOLD_PER_COMBO`, `COMBO_TERM_PER_COMBO`, `COMBO_STRICT_TIMER`, `COMBO_NO_TIMER`, `COMBO_MOD_TERM`, `COMBO_MUST_HOLD_MODS`), `MOUSE_EXTENDED_REPORT`, `LEGACY_MAGIC_HANDLING`, `KEY_OVERRIDE_REPEAT_DELAY`, `STRICT_LAYER_RELEASE`, `LEADER_KEY_STRICT_KEY_PROCESSING` (legacy form).
- Disable flags: `NO_DEBUG`, `NO_PRINT`, `NO_ACTION_LAYER`, `NO_ACTION_TAPPING`, `NO_ACTION_ONESHOT`.
- `MATRIX_HAS_GHOST`, `MATRIX_UNSELECT_DRIVE_HIGH`, `IS_COMMAND()`, `AUDIO_VOICES`, `F_SCL` (I²C speed).
- The datablock defines `EECONFIG_KB_DATA_SIZE`/`_VERSION` and `EECONFIG_USER_*`.
- `SRC` / `LIB_SRC` / `OPT_DEFS` / extra `rules.mk` source includes and hardware-driver wiring (pointing device driver, etc.).
- AVR MCU tuning (`F_CPU`, `F_USB`, `ARCH`, `INTERRUPT_CONTROL_ENDPOINT`).
- Endpoint sharing knobs `KEYBOARD_SHARED_EP` / `MOUSE_SHARED_EP` and the legacy `*_ENABLE` for `RAW_ENABLE`, `VIRTSER_ENABLE`, `MIDI_ENABLE` where not modeled in `features.*`.
- `post_config.h` / `post_rules.mk` conditional post-processing (see §9.2) — inherently a build-time C/make mechanism.

> When in doubt: if it's not in §5's schema, put it in `config.h`/`rules.mk`.

---

## 9. Build-time file reading order & post hooks

### 9.1 `config.h` include order (lowest → highest priority)

```
keyboards/top_folder/config.h
  → sub_1/config.h
    → sub_2/config.h
      → sub_3/config.h
        → sub_4/config.h
          → .build/obj_<kb>_<keymap>/src/info_config.h   ← generated from info.json
          → users/<user>/config.h
          → keyboards/.../keymaps/<keymap>/config.h
        → sub_4/post_config.h
      → sub_3/post_config.h
    → sub_2/post_config.h
  → sub_1/post_config.h
→ keyboards/top_folder/post_config.h
```

`rules.mk` mirrors this (with `post_rules.mk` read before `common_features.mk`, which interprets feature flags). **Implication:** keymap `config.h` always wins over `info.json`; the generated `info_config.h` sits below the keymap but above the keyboard's deepest folder.

### 9.2 `post_config.h` / `post_rules.mk` — conditional defaults

`post_config.h` runs *after* all upstream `config.h` but the layout above means a keymap-level `#define IOS_DEVICE_ENABLE` can gate keyboard-level defaults. Example: keymap sets `IOS_DEVICE_ENABLE`; `post_config.h` then clamps `USB_MAX_POWER_CONSUMPTION` to 100 mA and lowers RGB brightness for iOS power adapters. **Do not** also define the gated option in keyboard/user `config.h` when using this pattern. `post_rules.mk` similarly lets a keyboard interpret a user-facing option (`RGBLED_OPTION_TYPE = backlight|underglow|none`) into `RGBLIGHT_ENABLE`/defines before `common_features.mk` runs.

---

## 10. Pin-naming conventions per platform

Pin names are **strings in `info.json`** and **bare tokens in `config.h`/C**. The naming depends on the MCU family:

### 10.1 AVR (atmega32u4, at90usb1286, …)

- Form: **single port letter + pin number**, e.g. `B0`, `B7`, `D0`, `D7`, `F4`, `C7`.
- These map directly to AVR `PORTB`/`PINB` etc. via `avr/io.h`.
- A pin like `B12` **does not exist** on most AVR keyboards — AVR ports top out at 8 bits (`B0`–`B7`). So `B12` is an **ARM** (STM32) pin, not AVR.
- In `config.h`: `#define MATRIX_ROW_PINS { D0, D5, B5, B6 }` (bare tokens).
- In `info.json`: `"rows": ["D0","D5","B5","B6"]` (quoted strings).

### 10.2 ARM — STM32 (Proton C, Blackpill F4x1, etc.)

- Form: **port letter + pin number**, supporting numbers ≥8, e.g. `A0`, `B0`, `B12`, `C8`, `F0`. This is ChibiOS PAL naming (bank `A`/`B`/`C`/… + index).
- `B12` here is STM32 port B pin 12 — **valid**, unlike on AVR.
- Mapped through ChibiOS PAL driver.
- In `info.json`: `"cols": ["A0","A1","A2"]`, `"rows": ["B0","B1","B2"]`.

### 10.3 PB0 / PA0 alternate notation

- Some docs/datasheets write AVR/STM pins as **`PB0`, `PA0`, `PB12`** (port prefix doubled). QMK's own configuration uses the **single-letter** form (`B0`, `A0`, `B12`) — **do not** write `PB0` in `info.json`/`config.h` for QMK; use `B0`. (`PB0` appears in AVR libc datasheets, not QMK config.)
- On ARM, `A0` is STM32 port A pin 0 (a real GPIO), **not** an analog-channel label — ADC pins are configured separately (see `13-drivers-lowlevel.md`).

### 10.4 RP2040 / others

RP2040 uses the same `GP0`/`GP1` style historically, but QMK abstracts to the `gpio_set_pin_*` macros (see `13-drivers-lowlevel.md` GPIO), so the pin token you write follows the platform's QMK pin map. When unsure, `qmk info -kb <keyboard>` resolves and prints the effective pinout.

### 10.5 Direct pins

`DIRECT_PINS` (config.h) / `matrix_pins.direct` (info.json) is a **2D** array of pins — one pin per switch, no shared rows/cols; each switch shorts its pin to ground. `diode_direction` is **ignored** for direct pins.

---

## 11. Keyboard submission guidelines

Run **`qmk lint -kb <keyboard>`** frequently (and before any PR). Passing example prints `Lint check passed!`; failures list missing files / schema violations.

### 11.1 Naming

- Lowercase, `[a-z0-9_]` only; **may not begin with `_`**; `/` separates sub-folders.
- Reserved (cannot be a keyboard/subfolder name): `test`, `keyboard`, `all`.
- Valid: `412_64`, `chimera_ortho`, `clueboard/66/rev3`, `planck`, `v60_type_r`.

### 11.2 Folder structure (≤4 levels deep)

`qmk_firmware/keyboards/top_folder/sub_1/sub_2/sub_3/sub_4`. A folder with a `keyboard.json` is **buildable** (appears in Configurator, built by `make all`). Organizational parent folders must **not** have `keyboard.json`. Multi-revision pattern: `info.json` at the keyboard level for shared config, `keyboard.json` per revision for revision-specific config.

### 11.3 Required/expected files

| File | Required? | Notes |
|------|-----------|-------|
| `readme.md` | **Yes** | What/who/where; follow the published template; link to external images (no binaries in-repo) |
| `keyboard.json` (or `info.json`) | **Yes** (makes it buildable) | All config; also feeds the API + Configurator |
| `config.h` | Optional | Only for non-data-driven options (§8) |
| `rules.mk` | Optional | Hardware drivers, extra sources |
| `<keyboard>.c` | Optional | Hardware init, OLED, etc.; auto-included. Typical functions: `matrix_init_kb`, `matrix_scan_kb`, `process_record_kb`, `led_update_kb`. **Only keyboard-essential code**, not user-tunable behavior. |
| `<keyboard>.h` | Optional | Prototypes / shared header for `<keyboard>.c` |

### 11.4 Layout naming rules (strict)

- **Single layout** → name it `LAYOUT`.
- **Multiple layouts** → must have a base `LAYOUT_all` supporting every switch position in the matrix (even if physically unbuildable); use it in the `default` keymap. Add `default_<layout>` keymaps per extra layout. Example:

  | Layout | Keymap | Description |
  |--------|--------|-------------|
  | `LAYOUT_all` | `default` | Supports both ISO + ANSI |
  | `LAYOUT_ansi` | `default_ansi` | ANSI |
  | `LAYOUT_iso` | `default_iso` | ISO |

- **`LAYOUT_all` alone is invalid**, and providing a plain `LAYOUT` when multiple layouts exist is invalid.
- Macro names are lowercase except the `LAYOUT` prefix.

### 11.5 Keyboard defaults & features

- **Minimal feature set.** Enable only what the hardware needs; users add more in their keymaps.
- **Magic Keycodes / Command:** think hard before enabling; if the keyboard lacks two shift keys, provide a working `IS_COMMAND` default even when `COMMAND_ENABLE = no`.
- **Custom functions:** if you implement e.g. `process_record_kb`, **call the `_user()` variant** and only run your code when it returns `true`.
- **Handwired/non-production** → goes in `keyboards/handwired/`; promoted to `keyboards/` if it becomes a product.
- **Warnings are errors** during keyboard builds — fix all warnings.
- **Copyright headers** — update to your name/year when adapting; keep original authors when changes are trivial; append years for multi-year work (`Copyright 2015-2017 …`).
- **License:** core is GPL. AVR binaries may be GPLv2 **or** GPLv3; **ARM binaries must be GPLv3** (ChibiOS is GPLv3).

### 11.6 Image/hardware files

No binary files in-repo (with rare exceptions). Host images (imgur) and hardware files (plates/cases/PCBs in a personal repo) and link them from `readme.md`.

---

## 12. Minimal worked example

A complete data-driven `info.json` for a small ARM split (illustrative):

```json
{
  "keyboard_name": "Example Split",
  "maintainer": "you",
  "manufacturer": "You",
  "url": "https://example.com",
  "tags": ["split", "ortho"],
  "processor": "STM32F411",
  "bootloader": "stm32-dfu",
  "usb": { "vid": "0xC1ED", "pid": "0x0001", "device_version": "1.0.0" },
  "build": { "debounce_type": "sym_eager_pk", "lto": true },
  "features": { "split_keyboard": true, "rgblight": true, "oled": true },
  "matrix_pins": { "rows": ["B0","B1","B2","B3"], "cols": ["A0","A1","A2","A3","A4","A5"] },
  "diode_direction": "COL2ROW",
  "debounce": 5,
  "rgblight": { "led_count": 12, "driver": "ws2812", "split_count": [6,6] },
  "ws2812": { "pin": "A10", "driver": "pwm" },
  "split": {
    "enabled": true,
    "handedness": { "pin": "B10" },
    "serial": { "driver": "usart", "pin": "A2" },
    "transport": { "protocol": "serial", "sync": { "layer_state": true, "matrix_state": true } }
  },
  "community_layouts": ["ortho_4x6"],
  "layouts": {
    "LAYOUT_ortho_4x6": { "layout": [ /* {matrix,x,y} per key, 24 entries */ ] }
  }
}
```

Non-data-driven bits land in `config.h`:

```c
#pragma once
#define TAPPING_TERM 180
#define PERMISSIVE_HOLD
#define QUICK_TAP_TERM 120
#define RGBLIGHT_LIMIT_VAL 200
```

---

## 13. Gotchas (cross-cutting)

- **`keyboard.json` makes a folder buildable; `info.json` does not (it's just config).** They hold identical content — the filename is the signal to the build system.
- **Generated `info_config.h` priority is *below* the keymap `config.h`** but above the keyboard's deepest folder — so a keymap can still override data-driven values via plain `#define`.
- **Duplicate-in-both-places warnings:** if a value is in both `info.json` and `config.h`/`rules.mk`, you get a warning (per-mapping `warn_duplicate`). One home per value.
- **`LAYOUT_all` alone is invalid; a plain `LAYOUT` with multiple layouts is invalid.** Submission lint will fail.
- **Pin naming differs by platform and silently matters:** AVR uses `B0`/`D7` (ports ≤7 bits, so `B12` is impossible on AVR); STM32 uses `A0`/`B12` (ChibiOS PAL). QMK uses the **single-letter** form everywhere — **never** `PB0`/`PA0` in QMK config even though datasheets use that.
- **Debounce `0` disables debouncing** (it is not "minimal"). Eager algorithms are **not noise-resistant** — never use them on ghosting/noisy matrices.
- **EEPROM has finite write endurance** — batch writes, never write per-scan; misuse can shorten MCU life. Basic DWORD API and datablock API are **mutually exclusive**.
- **`backing_size` must be a multiple of `logical_size`** for wear-leveling EEPROM, or you silently get a misconfigured store.
- **Endpoint budget is finite per MCU** — combining `MOUSEKEY`+`EXTRAKEY`+`NKRO` is default; enabling `CONSOLE`/`MIDI`/`RAW`/`VIRTSER` can exhaust endpoints → build error. `KEYBOARD_SHARED_EP=yes` frees one but breaks Boot Keyboard in some BIOSes.
- **ARM binaries are GPLv3-only** (ChibiOS); AVR may be GPLv2 or v3. Matters for distribution.
- **`post_config.h` / `post_rules.mk`** are the only way to make keyboard defaults react to a keymap-level option — but never also define the gated option at keyboard/user level when using this pattern.
- **`IS_COMMAND()` should be defined even with `COMMAND_ENABLE = no`** if the keyboard lacks two shift keys — gives users a sane default if they later enable Command.
- **LAYOUT macro `r`/`rx`/`ry` rotation fields exist in the schema but are "currently not implemented"** — don't rely on them for rendering.
- **Chordal Hold `hand` field** (`"L"`/`"R"`/`"*"`) in layout keys feeds `tapping.chordal_hold`; leaving it out means `"*"` (exempted).
- **I²C for split is AVR-only** (serial works on ARM). ARM splits currently need `SPLIT_TRANSPORT = custom` (legacy) or the data-driven `transport.protocol: "serial"`.

---

## 14. Cross-links

- **`01-architecture.md`** — where matrix scan / debounce / process_record sit in the main loop; why debounce timing is in ms not cycles.
- **`02-getting-started-build.md`** — `qmk lint`, `qmk info`, `make`, the build pipeline that consumes `info.json` → `info_config.h`.
- **`04-keymaps-and-keycodes.md`** — `LAYOUT_*` macros from a keymap's perspective; tapping/oneshot behavior referenced by `tapping.*`.
- **`07-led-rgb-backlight.md`** — `backlight`/`rgblight`/`*_matrix`/`indicators`/`ws2812`/`apa102` blocks.
- **`10-connectivity.md`** — `split.*` transport/sync, handedness, watchdog; split EEPROM considerations.
- **`12-hardware-platforms.md`** — `processor`/`board`/`development_board`/`pin_compatible`; custom/hand-wired matrix; converters.
- **`13-drivers-lowlevel.md`** — GPIO pin abstraction, ADC (vs `A0` ambiguity), I²C/SPI/UART drivers behind `eeprom`/`ws2812`/etc.
- **`14-configurator-api-via.md`** — how the API + Configurator consume `info.json` layouts/`community_layouts`.
- **`17-faq-gotchas-breaking-changes.md`** — the historical `config.h`/`rules.mk` → `info.json` migration timeline and breaking changes.
