# 00 — Cross-Cutting Gotchas, Conflicts & Dead APIs

**Read this before you write or edit keymap.c, config.h, info.json, or any custom C.** This file aggregates the highest-value traps that span multiple features. Each item names the deeper reference. The job of this file is **trap detection**: stop the agent from suggesting obsolete APIs and from hitting silent interactions.

> Terminology note: "data-driven" = the `info.json` / `rules.mk` schema path (modern). "Legacy" = hand-written `config.h` `#define`s. QMK is mid-migration; show the data-driven key first, give the `#define` equivalent, and flag anything not yet data-driven. See `03-config-and-info-json.md`.

---

## A. The keypress pipeline (get this wrong and everything breaks)

Detailed chain in `01-architecture.md §7`. Compressed order:

```
pre_process_record_quantum          ← COMBOS run here (earliest), before your code
  → process_record_quantum
    → ...feature pre-handlers...
    → process_record_kb  ──► process_record_user   ← YOUR hook, runs BEFORE most features
    → process_combo? no. feature handlers run AFTER user:
       key_override, tap_dance, caps_word, unicode, auto_shift, magic,
       grave_esc, rgb, mouse/joystick/programmable_button, then quantum keycodes
  → post_process_record_quantum  ──► post_process_record_kb ──► _user
```

- **`return false` in `process_record_user` halts the ENTIRE downstream chain** — including the final handler that turns `MO`/`LT`/`OSL`/`TG` into layer actions. Returning false on a layer keycode *without reproducing its effect* silently disables the layer. `process_record_user` runs **before** most feature handlers, not after. (`01 §7.4`)
- **`_kb` callbacks MUST call `_user`** (and `_<module>_kb` → `_<module>_user`) or the downstream hook never fires. Easy to break when copying a keyboard `.c`. (`01 §9`)
- **`matrix_scan_user` / `housekeeping_task_user` run once per matrix scan** (often hundreds of times/sec). Heavy work there directly raises key latency. Never sleep/poll there. (`01 §9.2`)
- **`KC_NO`/`XXXXXXX` (block) vs `KC_TRNS`/`_______` (fall-through)** — the #1 keymap bug. "I want to disable this key on a layer" + `_______` = it just inherits the base-layer binding. (`01 §6`, `04`)
- **Combos run in `pre_process_record`**, *before* `process_record_user`. They transparently intercept keys but add a small input delay; Key Overrides run later (mod-shortcut style) and add none. Don't confuse the two. (`05`, `01 §7.1`)

## B. Keycodes & keymaps (`04`, `05`)

- **16-bit keycode packing limits everything fancy:** `MT`/`LT`'s tap keycode is restricted to **Basic keycodes only** (≤ `0xFF`); `LM`/`MT` **cannot mix left & right modifiers** (any right-hand mod silently makes *all* mods right-handed); `LT`/`LM` layer arg is capped `0–15`. Workarounds: `process_record_user` interception via `record->tap.count`, or Tap Dance. (`04`)
- **US-ANSI-shifted aliases (`KC_TILD`, `KC_LCBR`, `KC_DQUO`, `KC_RPRN`…) are NOT real keycodes** — they expand to `LSFT(kc)`. They break inside `MT`/`LT` (modifier masked out), produce wrong characters on non-US host layouts, and are dropped by Windows Remote Desktop. Use the genuinely-basic `KC_1`→`1`/`!` pairs in `MT`/`LT` instead. (`04`)
- **Layer precedence:** you cannot overlay a *lower* layer on top of a *higher* one. Lookup descends from the highest active layer and stops at the first non-`KC_TRNS` entry — **even if that entry is `KC_NO`**. Momentary keys (`MO`/`LM`/`LT`/`TT`) need a `KC_TRNS` escape path on their own destination layer or you lock yourself in. (`04`)
- **`TT(n)` tap-toggle does nothing if `QUICK_TAP_TERM == 0`** (or the per-key `get_quick_tap_term()` returns 0). `QUICK_TAP_TERM` also governs one-shot lock + auto-repeat and is clamped to `TAPPING_TERM`. (`04`)
- **Magic keycodes persist to EEPROM** (runtime successor to deprecated Bootmagic Full). `EE_CLR` clears EEPROM — the escape hatch when Magic swaps/Bootmagic bricked your layout. (`04`, `11`)

## C. Config & data-driven (`03`)

- **`info.json` files combine top-down** — a deeper folder's `info.json` overrides a shallower one's keys. But **the generated `info_config.h` sits *below* the keymap `config.h`**, so keymap `config.h` always wins over data-driven values. (`03`)
- **`keyboard.json` vs `info.json` is a build-system signal**, not just a name. Identical content; only `keyboard.json`'s presence makes a folder a *buildable* keyboard. (`03`)
- **Pin naming is platform-specific and silently matters.** AVR uses single-letter `B0`/`D7` (ports cap at 8 bits — `B12` is **impossible** on AVR). STM32/ChibiOS uses `A0`/`B12`. RP2040 uses `GPx`. QMK uses the **single-letter form everywhere — never `PB0`/`PA0`** even though datasheets do. On ARM, `A0` is a GPIO pin, not an ADC channel label. (`03 §10`, `12`)
- **Debounce `0` disables debouncing** (not "minimal"). Eager algorithms (`sym_eager_*`, `asym_eager_defer_pk` key-down) **are not noise-resistant** — on a ghosting/noisy matrix they pass noise straight through as phantom keypresses. (`03`, `12`)
- **EEPROM has finite write endurance** — writing per-scan can brick the MCU. Basic (DWORD) and datablock APIs are **mutually exclusive**. Wear-leveling `backing_size` must be a **multiple** of `logical_size`, and SPI-flash logical EEPROM is hard-capped at 64 kB. (`03`, `13`)
- **Strict LAYOUT naming for upstream PRs:** a lone `LAYOUT_all` is invalid; a plain `LAYOUT` when multiple layouts exist is invalid; macro names lowercase except the `LAYOUT` prefix. `qmk lint` enforces this. (`03`)

## D. Resources, conflicts & licensing (`07`, `03`, `09`, `10`, `13`)

- **USB endpoint budget is finite per MCU.** `MOUSEKEY`+`EXTRAKEY`+`NKRO` share one endpoint by default; adding `CONSOLE`/`MIDI`/`RAW`/`VIRTSER` can exhaust endpoints → build error. `KEYBOARD_SHARED_EP=yes` frees one but breaks Boot Keyboard in some BIOSes. Each of mouse/pointing/joystick/digitizer/programmable_button can consume an endpoint too. (`03`, `06`)
- **RGBLIGHT vs RGB_MATRIX vs LED_MATRIX:** RGB_MATRIX "hooks into the RGBLIGHT system" so legacy `UG_*`/`RGB_M_*` keycodes silently drive **both**. Mitigate with `RGB_MATRIX_DISABLE_SHARED_KEYCODES` + use `RM_*`. RGB_MATRIX and LED_MATRIX are **mutually exclusive** (shared EEPROM region). Use exactly one lighting subsystem; they do not coexist cleanly. (`07`)
- **Audio on AVR hard-uses Timer 1 and Timer 3** (`pwm_hardware`, auto-selected — you do NOT set `AUDIO_DRIVER` on AVR). Backlight `pwm` driver also wants those timers. **Audio + backlight on AVR = a classic timer collision.** `AUDIO_DRIVER` is ARM-only. (`09`, `07`, `13`)
- **ARM binaries are GPLv3-only** (ChibiOS license); AVR may be GPLv2 or v3. Proprietary vendor libs (Nordic SoftDevice, ST BT, WCH CH582, WB32 ISP) are **categorically excluded** — this is the root cause of QMK's limited wireless story (ZMK is the usual recommendation for wireless). (`12`, `10`)
- **I²C split transport is AVR-only** (ARM I²C slave unsupported); ARM splits need serial or custom transport. **bitbang serial + bitbang WS2812 conflict on ARM** — use hardware USART + hardware WS2812. (`10`, `13`)
- **`LTO_ENABLE = yes` removes deprecated Action Functions/Action Macros** (biggest AVR size win has a hidden functional cost) and **defeats GDB debugging**. For debugging builds: `LTO_ENABLE = no`, `OPT = g`, `DEBUG_ENABLE = yes`. (`15`, `02`)

## E. Split & connectivity (`10`)

- **`SPLIT_USB_DETECT` auto-enables on ARM/ChibiOS and breaks battery-pack demos** — without a USB cable neither half can do VBUS-based master delegation. (`10`)
- **`EE_HANDS` handedness survives `eeconfig_init()` but NOT external EEPROM wipes** (QMK Toolbox "Reset EEPROM", avrdude EEPROM files). Blackpill/DFU boards may **lose the flag on every flash** — re-flash the split bootloader target each time. (`10`)
- **`RGBLED_SPLIT` forcibly implies/enables `RGBLIGHT_SPLIT`** even if you didn't set it. (`10`, `07`)
- **Split sync is asymmetric:** nearly all `SPLIT_*` flags push master→slave; `SPLIT_POINTING_ENABLE` is the exception (pulls slave→master). Each flag adds per-scan overhead. (`10`)
- **Lighting on splits needs explicit sync flags or "lights work on one side":** `SPLIT_LED_STATE_ENABLE` (lock LEDs), `SPLIT_LAYER_STATE_ENABLE` (layer/host indicators), `RGBLIGHT_SPLIT`+`RGBLED_SPLIT` (underglow), `RGB_MATRIX_SPLIT`/`LED_MATRIX_SPLIT` (matrices). (`07`, `10`)
- **Raw HID reports are always exactly 32 bytes both ways** (`RAW_EPSIZE`); `0xFF60`/`0xFF61` are the **VIA defaults** — your own host tool on that endpoint collides with VIA/Vial. (`10`, `14`)

## F. Flashing & EEPROM staleness (`15`, `17`)

- **EEPROM staleness after ANY breaking-change merge, especially on ARM.** VIA copies flash→EEPROM on first boot and thereafter **ignores `keymap.c`**; ARM EEPROM layout shifts can brick the board. "My keymap changes don't take effect" and "ARM board dead after flashing" are almost always solved by **clearing EEPROM** (Bootmagic key / `EE_CLR` / bootloader clear). (`17`, `14`)
- **Wrong AVR fuse clock bits = bricked MCU** (only high-voltage programming recovers). The `efuse` readback mismatch warning is usually benign if the low nibble matches. (`15`)
- **HalfKay (Teensy) is closed-source and unrestorable.** ISP-flashing any other bootloader over a Teensy permanently destroys it. ISP RESET wiring (programmer pin → target RESET) is the #1 physical mistake. (`15`)
- **DFU bootloaders need Zadig/WinUSB on Windows; Caterina/HalfKay/bootloadHID/qmk-hid do NOT.** Installing a driver while the keyboard is NOT in bootloader mode silently breaks typing. (`15`)
- **STM32duino vs stm32-dfu differ:** stm32duino uses `dfu-util -a 2` (no `:leave`); stm32-dfu uses `dfu-util -a 0 -s 0x8000000:leave`. (`15`)
- **RP2040 double-tap-RESET entry only works if running firmware defined `RP2040_BOOTLOADER_DOUBLE_TAP_RESET`** — otherwise it's BOOTSEL-on-plug only. (`15`, `12`)

## G. VIA / Vial (`14`)

- **VIA protocol-version mismatch:** `VIA_PROTOCOL_VERSION` compiled into firmware must be supported by the VIA app version; **plus** the keyboard must be in the `the-via/keyboards` definitions or side-loaded via the Design tab — otherwise the app connects but won't edit, or doesn't recognize the board. (`14`)
- **`VIA_ENABLE = yes` silently force-enables `RAW_ENABLE`, `DYNAMIC_KEYMAP_ENABLE`, `BOOTMAGIC_ENABLE`, and `TRI_LAYER_ENABLE`.** Setting these explicitly can produce surprising interactions. (`14`)
- **Vial requires the `vial-kb/vial-qmk` FORK** (lags upstream). Upstream QMK **explicitly rejects** `VIAL_ENABLE`/`VIAL_KEYBOARD_UID`/`VIAL_UNLOCK_COMBO_*` as `_invalid` keys — so a Vial build on upstream QMK fails with an `_invalid` key error. That error is the diagnostic signature of being on the wrong tree. (`14`)
- **Vial force-enables a large feature bundle** (verified from the fork's `builddefs/build_vial.mk`): `VIAL_ENABLE = yes` turns on tap-dance, caps-word, combo, key-override, layer-lock, repeat-key, auto-shift, plus a live "QMK Settings" tab (per-key `TAPPING_TERM`/permissive/hold-on-other/chordal/flow/retro). Two consequences: (1) you **cannot** meaningfully disable those per-keymap in a Vial build; (2) the build is large — `LTO_ENABLE = yes` is near-mandatory and flash-tight AVR may not fit. (`14 §7.5.2`)
- **The fork's `docs/` folder is NOT Vial documentation** — it's just a stale copy of upstream QMK docs. Vial's real prose docs live in the separate `vial-kb/docs` repo / get.vial.today. The actual Vial build mechanics live in the fork's *code* (`builddefs/build_vial.mk`, `quantum/vial.c`, per-board `vial.json`). (`14 §7.5`)
- **Per-board `VIAL_KEYBOARD_UID` must be unique** — `quantum/vial.c:95` reads it; never copy another keyboard's 8-byte UID. The unlock combo (`VIAL_UNLOCK_COMBO_ROWS`/`_COLS`) must be held to edit secure state; `VIAL_INSECURE = yes` bypasses (note: `VIAL_` not `VIA_`). (`14 §7.5.3`)
- **`keymap.json` layers use numeric indices** (`MO(2)`), never `MO(_FN)` — no C symbols survive the json2c round-trip. (`14`)

## H. Dead / renamed APIs — NEVER suggest these (trap detection) (`17`)

> This is the curated high-frequency list. For the exhaustive per-release keycode-change catalog (version-to-version migrations), see `references/19-keycodes-changelog.md` — it is an index into `references/keycodes-changelog/<version>.md` (one file per release). To dump every release in a migration window `(from, to]` as one document, run `scripts/keycodes_migration.py --from <from> [--to <to|latest>]`.

**Removed with zero backward-compat (will not compile):**
- GPIO: `setPinOutput`/`writePinHigh`/`readPin`/`setPinInput` → use `gpio_set_pin_output`/`gpio_write_pin_high`/`gpio_read_pin`/`gpio_set_pin_input`. (`13`, `17`)
- I²C: `i2c_readReg`/`i2c_writeReg` → use `i2c_read_register`/`i2c_write_register` (and the `_16` variants). (`13`, `17`)
- `RGB_*` keycode namespace (underglow) → **`UG_*`**; matrix → **`RM_*`**. `RGB_*` fully removed 2025-08. (`07`, `17`)
- `RESET` → `QK_BOOT`; `KC_GESC` → `QK_GESC`; grave-esc feature keycode → `QK_GRAVE_ESCAPE`. (`04`, `17`)
- `RGB_DI_PIN`, `config_common.h`, `KEYMAP` (use `LAYOUT`), `led_set_user` (use `led_update_kb`/`_user`), `process_action_kb`, `isLeftHand`, `FAUXCLICKY`, `action_get_macro`/`MACRO()` (use `SEND_STRING`/`process_record_user`), `FORCE_NKRO`, `CTPC`, the `USB_LED_*` macros, `arm_atsam` (Massdrop CTRL/ALT must stay on 0.26.x). (`17`)

**Renamed/inverted (will silently change behavior):**
- `IGNORE_MOD_TAP_INTERRUPT` was **removed** — its old behavior is now the **default**; invert with `HOLD_ON_OTHER_KEY_PRESS` (and the per-key fn takes *any* dual-role keycode, not just mod-taps). (`04`, `17`)
- `TAPPING_FORCE_HOLD` → `QUICK_TAP_TERM` (now in **ms**; `0` disables auto-repeat). (`04`, `17`)
- `CKLED2001` → `snled27351`; **all driver strings are now lowercase**: `ws2812`, `is31fl3731`, `ssd1306`, `apa102`, `pwm_software`, etc. (`13`, `17`)
- `Bootmagic Full` (`BOOTMAGIC_ENABLE = full`) deprecated → use Magic keycodes / Bootmagic Lite. (`11`, `17`)

**Callback signatures flipped to `bool` over time** — returning `void` or forgetting the `return false;` (handled) is a recurring bug: `oled_task_user`, `oled_task_kb`, RGB/LED matrix indicator callbacks, key override handlers, `encoder_update_user/_kb`, `pre_process_record_*`, `dip_switch_update_*`, `matrix_scan_*`-style hooks. Always check the current signature in the relevant reference. (`08`, `07`, `01`)

**Contributing:** core/keyboard PRs target **`develop`**, not `master` (breaking-changes window). `clang-format` destroys `LAYOUT(...)` macros — wrap them in `// clang-format off`/`on`. (`16`)

## I. Hardware & platform (`12`, `11`)

- **Voltage domains:** RP2040 GPIO is **not 5 V tolerant**; Blackpill `A0`/`B5` aren't either. Proton C VCC/RAW shorted on Gherkin-style Pro Micro PCBs can **damage the MCU** — leave RAW disconnected. (`12`)
- **Blackpill pin landmines:** `C13`/`C14`/`C15` are input-current-limited (bad as COL2ROW row pins — rows sink current); `A11`/`A12` (USB), `B2` (BOOT1), `VBAT`, `NRST` unusable; `A9`/`A10` break DFU/USB. (`12`)
- **Custom matrix full-replacement has mandatory calls** (`matrix_init_kb`/`matrix_scan_kb` + `debounce(...)`/`debounce_init()`) — omitting them silently breaks keymaps. Prefer `CUSTOM_MATRIX = lite` (just 2 functions). (`12`)
- **Quantum Painter is ARM-only** (no AVR). OLED `90°/270°` rotation is software and costly (drops keycodes at ~15 ms on AVR). ST7565 `st7565_task_user` returns `void` (not `bool` like OLED). (`08`)
- **Bootmagic Lite wipes EEPROM by default** unless `BOOTMAGIC_NO_EEPROM`. (`11`)
- **Community Modules aren't supported by the Configurator** (build your own firmware); the main `.c` is auto-compiled only if its name matches the directory; API versions gated by `ASSERT_COMMUNITY_MODULES_MIN_API_VERSION` (commas, not dots). (`18`, `16`)

## J. Unicode & text (`11`, `05`)

- **Unicode is host-OS dependent and will not "just work."** Each host needs setup (macOS Unicode Hex Input, WinCompose, IBus, Emacs). `UC(c)` Basic tops at `U+7FFF` (no emoji); pair indices in `UP(i,j)` cap at 127; `UNICODE_MODE_WINDOWS` caps at `U+FFFF` and is **not** Alt codes. Aliases: `UC_LINX`, `UC_EMAC`. (`11`, `01` for the why)
- **`apply_autocorrect`'s `str` arg is PROGMEM** — must use `send_string_P`, never `send_string`/`SEND_STRING`; only 8-bit basic keycodes match. (`05`)
- **Caps Word uses `KC_LSFT` weak mods, not `KC_CAPS`** — works with OS-remapped Caps Lock, but mis-shifts on non-US layouts. The real API is `caps_word_press_user` + `is_caps_word_on()` (NOT a `get_caps_word_pressing`). (`05`)
- **Dynamic Macros: one shared 128-keypress buffer, not persistent, recursive macros hang the keyboard.** (`05`)

---

## Quick "which subsystem does X?" conflict cheatsheet

| If the user wants… | Use | Do NOT also use |
|---|---|---|
| Per-key RGB animation | `RGB_MATRIX` (`07`) | `RGBLIGHT`/`LED_MATRIX` at the same time |
| Underglow strip / single zone | `RGBLIGHT` (`07`) | `RGB_MATRIX` (keycodes collide unless `RGB_MATRIX_DISABLE_SHARED_KEYCODES`) |
| Per-key single-color brightness | `LED_MATRIX` (`07`) | `RGB_MATRIX` (shared EEPROM) |
| Audio beep on AVR + backlight | move backlight to `software`/`timer` or drop Audio | `BACKLIGHT_DRIVER=pwm` + Audio (`09`,`07`) |
| Wireless split | serial or custom transport (ARM) | I²C split on ARM (`10`) |
| Custom host comms + VIA | different endpoint / coordinate with VIA | raw HID on `0xFF60`/`0xFF61` (`10`,`14`) |
| More endpoints on AVR | `KEYBOARD_SHARED_EP=yes` (carefully) | expect Boot Keyboard to work in all BIOSes (`03`) |
| Bigger firmware (AVR) | `LTO_ENABLE=yes`, cut RGB/audio/console | expect Action Functions/Macros or GDB debug (`15`) |
