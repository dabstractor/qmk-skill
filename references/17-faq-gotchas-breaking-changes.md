# 17 — FAQ, Gotchas, Breaking Changes & Changelog Highlights

> **Purpose:** This is the **trap-detection layer** — the catch-all that flags
> deprecated patterns, version-specific gotchas, and the breaking-change rhythm
> so the agent never suggests an obsolete API, an old keycode name, or a config
> style that has been removed. When you are about to write a `#define`, a
> keycode, a `rules.mk` line, a GPIO call, or a callback signature, **check here
> first.**
>
> **Audience:** AI agent + humans. Density is intentional. Tables and bullets
> are scannable. Everything is current to the **0.33.0 (2026-05-31)** breaking
> change. When a pattern is marked ❌ it has been **removed**; when marked ⚠️ it
> is **deprecated and slated for removal**.

This reference cross-cuts every other reference. Concretely, it ties into:
`03-config-and-info-json.md` (the config.h → info.json migration is the single
biggest recurring breaking change), `04-keymaps-and-keycodes.md` (keycode
renames), `07-led-rgb-backlight.md` (RGB/LED driver + keycode renames),
`13-drivers-lowlevel.md` (GPIO/I2C/SPI API renames), `15-flashing-debugging.md`
(flashing/EEPROM-clear gotchas), `16-userspace-development.md` (PR/breaking
change process).

---

## 1. The Breaking-Change Process (the "Develop" cycle)

### 1.1 Cadence & branches

QMK merges breaking changes from the **`develop`** branch into **`master`** on a
**~3-month cadence** (Feb / May / Aug / Nov, historically the last weekend).
A "breaking change" = any change that modifies QMK behavior in an incompatible
or dangerous way, **including any keyboard moves/renames within the repo**.
Between merges, `master` only gets non-breaking PRs; each push to `master` is
auto-merged forward into `develop` by GitHub Actions.

**Version history (newest first)** — see §6 for per-cycle detail:

| Date | Version | Date | Version |
|------|---------|------|---------|
| 2026-05-31 | 0.33.0 | 2023-11-26 | 0.23.0 |
| 2026-02-22 | 0.32.0 | 2023-08-27 | 0.22.0 |
| 2025-11-30 | 0.31.0 | 2023-05-28 | 0.21.0 |
| 2025-08-31 | 0.30.0 | 2023-02-26 | 0.20.0 |
| 2025-05-25 | 0.29.0 | 2022-11-26 | 0.19.0 |
| 2025-02-23 | 0.28.0 | 2022-08-27 | 0.18.0 |
| 2024-11-24 | 0.27.0 | 2022-05-28 | 0.17.0 |
| 2024-08-25 | 0.26.0 | 2022-02-26 | 0.16.0 |
| 2024-05-26 | 0.25.0 | 2021-11-27 | 0.15.0 |
| 2024-02-25 | 0.24.0 | 2021-08-28 | 0.14.0 |
| | | 2021-05-29 | 0.13.0 |
| | | 2021-02-27 | 0.12.0 |
| | | 2020-11-28 | 0.11.0 |
| | | 2020-08-29 | 0.10.0 |
| | | 2020-05-30 | 0.9.0 |
| | | 2020-02-29 | 0.8.0 |
| | | 2019-08-30 | 0.7.0 |

The **next** planned breaking change at time of writing is **2026-08-30**.

### 1.2 The merge timeline (what "develop window" means)

Around each merge date, the repo moves through a fixed sequence of freeze
stages. A PR must be **accepted into `develop`** before `develop` closes:

| When (relative to merge) | State |
|--------------------------|-------|
| ~5 weeks before | last window to **raise** new functional PRs against `develop` |
| ~4 weeks before | `develop` **closed to new PRs**; call for testers posted |
| ~2 weeks before | `develop` **closed to existing PR merges** — bugfixes only |
| ~1 week before | `develop` **locked** — critical bugfixes only |
| 2 days before | **`master` locked** — no PRs merged at all |
| Day of merge | `develop` → `master` (`git merge --no-ff develop`), version tag cut, `master` unlocked |
| Immediately after | `master` merged back into `develop`, new `develop` rebranched & tagged `breakpoint_YYYY_MM_DD` |

### 1.3 Labels

* **`core`** — auto-applied to any PR touching core areas. *Having the label
  does not guarantee inclusion.*
* **`breaking_change_YYYYqN`** — applied by collaborators to mark a PR as a
  strong candidate for the *N*th-quarter cycle; prioritized for review.

### 1.4 Handling breaking changes in **your fork** (rebase strategy)

QMK officially recommends you **do not** maintain a long-lived divergent fork of
firmware. The supported workflows are, in order of preference:

1. **External Userspace** (best). Keep your keymaps in your own
   `qmk_userspace` repo and build against stock `qmk_firmware` (or a
   fork+ref). See `16-userspace-development.md`. Historical keyboard names stay
   valid under External Userspace, so renames don't break your build.
2. If you do fork firmware, **rebase, don't merge**, on `master` after each
   breaking-change merge. Merges accumulate conflict debt across cycles.
3. After a breaking-change merge, expect to: rebuild, **clear EEPROM** (see
   §3.2), and re-test. ARM boards especially may need an EEPROM reset because
   EEPROM layout can shift.

> **Gotcha:** when you submit a PR flagged as breaking, the maintainers will ask
> you to (a) consider splitting it so old keymaps still build, (b) write a
> ChangeLog file `docs/ChangeLog/<YYYYMMDD>/PR<number>.md`, and (c) be
> responsive. Large unreviewed PRs are far more likely to hit conflicts before
> `develop` closes.

---

## 2. Deprecation & Removal Policy (support tiers)

### 2.1 The policy

* **Large features / whole subsystems:** deprecation is communicated on
  `develop` **at least one breaking-change cycle (≥3 months)** before removal,
  often longer for high-impact items. Notices appear in the cycle's ChangeLog,
  and **compile-time warnings** are emitted where possible while the deprecated
  path still works.
* **Small features:** may be removed within a single cycle, generally based on
  in-repo usage. Minimal-use features can be pulled at any time on `develop`.
* **Third-party libs:** QMK forks them to mitigate upstream disappearance; if
  upstream vanishes, the feature is replaced when practical or removed per this
  policy.

So the lifecycle a feature follows is: **works → deprecation warning on
`develop` → still works but warned → alias/compat removed (compile breaks) →
gone.** A typical deprecation-to-removal window is **1–2 cycles (3–6 months)**.

### 2.2 Why things get removed

Better alternative exists · lacks standards adherence · poor owner/upstream
support · poor design · hardware constraints (AVR flash/RAM) · minimal in-repo
use · copyright disputes · bit-rot. The most common trigger is the ATmega32U4
flash ceiling — see `15-flashing-debugging.md` "Squeezing AVR".

### 2.3 License enforcement (relevant when suggesting vendor boards)

QMK is GPL and **requires full source disclosure** for any QMK-derived
firmware, including wireless-capable boards (a wired-only "crippled" source
drop for a tri-mode board is a violation). Vendors who don't comply get PRs put
on hold, boards removed, and are listed as offending vendors. Practical
implication for support: **don't assume a vendor board's QMK exists upstream**;
many `via.json`-only boards have no source. Reusing one `VID`/`PID` across
variants (wired vs wireless) is itself rejected because it bricks customers.

---

## 3. Top Operational Gotchas (FAQ fixes, distilled)

These are the recurring "my keyboard does X, why" answers, with the **actual
fix**. Grouped by symptom.

### 3.1 Build / flash failures

| Symptom | Fix |
|---------|-----|
| **Linux: can't flash / permission denied on the bootloader device** | Install udev rules: `util/install_udev.sh` (from `qmk_udev`). Avoid `sudo make ... :flash`. If using old ModemManager (<1.12) set `--filter-policy=default`. Pro Micro (ACM) needs kernel `CONFIG_USB_ACM=y`. |
| **Windows: "Unknown Device" in DFU / wrong driver** | Re-run QMK install or reinstall QMK Toolbox, or use Zadig to install the right driver (see `15-flashing-debugging.md`). Since QMK Toolbox 0.3.0 (2024-02-25 cycle) Atmel DFU uses **WinUSB, not libusb** — if you upgraded Toolbox/MSYS and DFU broke, replace libusb with WinUSB via Zadig. |
| **`make` with `sudo`** | Don't. It's a footgun. Use the per-command `sudo dfu-programmer ...` form only as a last resort. |
| **Keyboard unusable after flashing, especially ARM (Planck rev6, Preonic rev3, etc.)** | **EEPROM contents are stale/invalid on ARM after a layout shift.** Clear EEPROM: hold the Bootmagic key (usually top-left/Esc) while plugging in, or press `QK_CLEAR_EEPROM`/`EE_CLR`, or use the bootloader's "Clear EEPROM". |
| **USB 3 flakiness / dropouts** | Move to a USB 2.0 port. |
| **Keyboard dead in BIOS/UEFI, or after sleep/wake/power-cycle** | Disable `CONSOLE_ENABLE`, `NKRO_ENABLE`, `SLEEP_LED_ENABLE`. NKRO often breaks BIOS; toggle to 6KRO with Magic **N** (`LShift+RShift+N`). |

### 3.2 EEPROM / "my changes don't stick"

* **VIA keymaps override flash.** On first boot VIA copies the keymap from
  flash into EEPROM and thereafter reads EEPROM — so edits to `keymap.c` are
  ignored. **Fix: clear the EEPROM** (same methods as above).
* **Magic/Command settings persist in EEPROM** and can leave Ctrl/Caps swapped,
  GUI disabled, Alt/GUI swapped, etc. Clearing EEPROM returns these to default.
  See `04-keymaps-and-keycodes.md` (Magic keycodes) and `10-connectivity.md`
  (Command).
* **EEPROM write-cycle limit ≈ 100,000.** Don't write firmware/state in a tight
  loop; you'll wear it out.

### 3.3 Keymap behavior surprises

| Symptom | Cause / Fix |
|---------|-------------|
| **Modifier or layer "stuck"** | You must put `KC_TRNS` in the **same position on the destination layer** to unregister the mod / return from the layer on release. Missing `KC_TRNS` = stuck. |
| **The "Menu" key doesn't work** | That key is `KC_APP`, not "Menu" (Microsoft named it Application; there's already a Menu in HID). |
| **Power/Sleep/Wake keys ignored** | Use the **Consumer** page codes `KC_SYSTEM_POWER`/`KC_PWR`, `KC_SLEP`, `KC_WAKE` — they work on all three OSes. The Keyboard-page `KC_KB_POWER` is macOS-only. On macOS you must *hold* them until the dialog appears; on Windows they fire instantly. |
| **JIS keys (Muhenkan/Henkan/Hiragana) ignored on macOS** | macOS doesn't recognize them; use Seil/Karabiner to remap. |
| **Apple Fn key** | Not reproducible without spoofing a real Apple VID/PID and reshaping the report — QMK won't support it (legal). |
| **Eject on macOS** | `KC_EJCT` works on macOS; Win10 ignores it; Linux sees it unmapped. |
| **Esc + `` ` `` on one key** | Use the Grave Escape feature (`QK_GESC`), see `05-text-input-and-combos.md`. |
| **Real vs Weak modifiers** | "Real" = physical mod state; "weak" = temporary virtual mod state. They are **ORed** in the report, so releasing a weak mod while the real mod is still held changes *nothing*. Code that toggles weak mods expecting them to take over will look broken. |
| **TrackPoint (PS/2) inconsistent** | Needs a proper reset circuit on the TrackPoint; without it init is unreliable. |
| **Column beyond 16 reads wrong** | On AVR `1<<16` is `int` (16-bit) ⇒ `0`. Use `1UL<<16` in custom `read_cols()`. |
| **System/audio/extra keys do nothing** | `EXTRAKEY_ENABLE = yes` is required in `rules.mk`/info.json `features`. |
| **Won't wake from sleep (Windows)** | Enable "Allow this device to wake the computer" in Device Manager → Power Management; check BIOS. |
| **Arduino pin names** | Arduino `D0` ≠ chip `PD0`. Arduino Leonardo/Micro use ATmega32U4 and work, but the Arduino bootloader can be a problem. |
| **Want JTAG kept enabled** | QMK disables JTAG on startup by default (it steals matrix/LED pins). Add `#define NO_JTAG_DISABLE` to `config.h`. |

### 3.4 Lock switches (mechanical, notCaps/Num/Scroll)

For *vintage mechanical lock switches* (Alps-style), enable in `config.h`:
```c
#define LOCKING_SUPPORT_ENABLE
#define LOCKING_RESYNC_ENABLE
```
and use `KC_LCAP` / `KC_LNUM` / `KC_LSCR`. **Modern keyboards do not need this** —
just use `KC_CAPS` / `KC_NUM` / `KC_SCRL`.

### 3.5 VID/PID

* Use any VID/PID; `0xFEED` is the de-facto QMK vendor ID. Pick a unique PID by
  scanning existing keyboards. Collisions are vanishingly rare for personal use.
* Officially-unique VID:PID can be purchased but is unnecessary for personal
  builds. (Note: spoofing Apple's VID/PID is how the Apple-Fn hack would have to
  work — and it's not done.)

---

## 4. The Great Renames — "Never Suggest the Old Name"

These are the high-frequency traps. **Always use the right-hand column.**

### 4.1 Bootloader / reset keycode

| ❌ Removed / deprecated | ✅ Use |
|------------------------|--------|
| `RESET` | `QK_BOOT` (renamed 2022-05 & 2022-08; old alias later removed) |

### 4.2 Grave Escape

| ❌ | ✅ |
|----|----|
| `KC_GESC` | `QK_GESC` (renamed 2022-11, #19018) |

### 4.3 RGB / LED / Mouse keycodes (the 2024 overhaul)

The 2024-05 → 2024-11 cycle **split** the old `RGB_xxx` keycodes into
per-subsystem namespaces so rgblight and rgb_matrix can coexist:

| Subsystem | Prefix | Status |
|-----------|--------|--------|
| Underglow (rgblight) | `UG_xxx` | current |
| RGB Matrix | `RM_xxx` | current |
| LED Matrix | `LM_xxx` (added 2024-05) | current |
| Backlight | `BL_xxx` | current |
| `RGB_xxx` | ⚠️ acts as `UG_xxx` during transition, **scheduled for removal** | deprecated |
| Old `RGB_` / Mouse keycodes | ❌ backward-compat **removed 2025-08-31** (#25444) | removed |

If a board has both rgblight and rgb_matrix, you **must** use `UG_` vs `RM_`
explicitly. See `07-led-rgb-backlight.md` for the full keycode tables.

### 4.4 Misc keycode renames (2022-11 "keycode overhaul" + later)

| ❌ old | ✅ new |
|--------|--------|
| `KC_LEAD` | `QK_LEAD` |
| `KC_LOCK` | `QK_LOCK` |
| `CAPS_WORD` / `CAPSWRD` | `CW_TOGG` |
| `VLK_TOGG` (variable keycode lock) | `VK_TOGG` |
| `X(i)` (unicodemap) | `UM(i)` |
| `XP(i,j)` | `UP(i,j)` |
| Legacy EEPROM-clear keycodes | removed (use `QK_CLEAR_EEPROM` / `EE_CLR`) |
| Legacy fauxclicky keycodes | ❌ removed (feature gone, §5.4) |
| Legacy international keycodes | ❌ removed |
| `KC_DELT` | `KC_DEL` (removed 2019-08) |

> **2024-05 also removed a batch of "deprecated quantum keycodes."** If a build
> fails on a missing keycode, consult
> `quantum/quantum_keycodes_legacy.h` in the firmware tree — it maps old → new.

### 4.5 GPIO API (Arduino-style → `gpio_` prefix)

**Removed final backward-compat in 2026-02-22 (#26028).** Started 2024-02-25.
The bare names are **gone**; always use the `gpio_` form:

| ❌ removed | ✅ |
|-----------|---|
| `setPinInput(pin)` | `gpio_set_pin_input(pin)` |
| `setPinInputHigh(pin)` | `gpio_set_pin_input_high(pin)` |
| `setPinInputLow(pin)` | `gpio_set_pin_input_low(pin)` |
| `setPinOutput(pin)` | `gpio_set_pin_output(pin)` |
| `setPinOutputPushPull(pin)` | `gpio_set_pin_output_push_pull(pin)` |
| `setPinOutputOpenDrain(pin)` | `gpio_set_pin_output_open_drain(pin)` |
| `writePinHigh(pin)` | `gpio_write_pin_high(pin)` |
| `writePinLow(pin)` | `gpio_write_pin_low(pin)` |
| `writePin(pin, lvl)` | `gpio_write_pin(pin, lvl)` |
| `readPin(pin)` | `gpio_read_pin(pin)` |
| `togglePin(pin)` | `gpio_toggle_pin(pin)` |

Pin *naming* is QMK-native (e.g. `B5`), **not** Arduino (`D0`). See
`13-drivers-lowlevel.md`.

### 4.6 I2C API

| ❌ removed (2025-02 #24832) | ✅ |
|----------------------------|---|
| `i2c_readReg()` | `i2c_read_register()` |
| `i2c_readReg16()` | `i2c_read_register16()` |
| `i2c_writeReg()` | `i2c_write_register()` |
| `i2c_writeReg16()` | `i2c_write_register16()` |

### 4.7 Config-key renames (still commonly mistyped)

| ❌ old | ✅ current |
|--------|-----------|
| `RGB_DI_PIN` | info.json `"ws2812": { "pin": ... }` (config.h define **errors at build** since 2023-05) |
| `RGBLED_NUM` | `RGBLIGHT_LED_COUNT` (then info.json `rgblight.led_count`) |
| `DRIVER_LED_COUNT` (RGB) | `RGB_MATRIX_LED_COUNT` (then info.json) |
| `RGB_DISABLE_TIMEOUT` | `RGB_MATRIX_TIMEOUT` |
| `RGB_DISABLE_WHEN_USB_SUSPENDED` | `RGB_MATRIX_SLEEP` |
| `LED_DISABLE_WHEN_USB_SUSPENDED` | `LED_MATRIX_SLEEP` |
| `RGB_MATRIX_STARTUP_*` | `RGB_MATRIX_DEFAULT_*` (HUE/SAT/VAL/SPD/MODE) |
| `LED_MATRIX_STARTUP_*` | `LED_MATRIX_DEFAULT_*` |
| `RGBW` | `WS2812_RGBW` |
| `RGB_DISABLE_AFTER_TIMEOUT` (ticks) | `RGB_MATRIX_TIMEOUT` (ms) |
| `JOYSTICK_AXES_COUNT` | `JOYSTICK_AXIS_COUNT` |

### 4.8 Driver-name casing (all lowercase now)

Driver selectors are **lowercase** (renamed 2023-08, compat later removed):

* RGBLight `RGBLIGHT_DRIVER`: `ws2812`, `apa102` (was `WS2812`/`APA102`)
* RGB/LED Matrix `*_MATRIX_DRIVER`: `is31fl3731`, `is31fl3733`, `is31fl3736`,
  `is31fl3737`, `is31fl3741`, `is31fl3742a`, `is31fl3743a`, `is31fl3745`,
  `is31fl3746a`, `aw20216`, `snled27351` (was `CKLED2001`), `ws2812`
* OLED `OLED_DRIVER`: `ssd1306` (old `ssd1306.c`/`SSD1306OLED` driver **removed**)
* Haptic `HAPTIC_DRIVER`: `drv2605l`, `solenoid`
* Bluetooth `BLUETOOTH_DRIVER` / `bluetooth.driver`: `bluefruit_le`, `rn42`
* I2C address defines renamed `DRIVER_ADDR_n` → driver-prefixed form (2023-11)

### 4.9 USB IDs (must be data-driven)

❌ `#define VENDOR_ID / PRODUCT_ID / DEVICE_VER / MANUFACTURER / PRODUCT` in
`config.h` — **removed** (warned 2022-08, failed 2022-11).
✅ `info.json` (and now `keyboard.json`):
```json
{
  "keyboard_name": "MyKeyboard",
  "manufacturer": "Me",
  "usb": { "vid": "0x1234", "pid": "0x5678", "device_version": "0.0.1" }
}
```

---

## 5. Removed Features & Subsystems (do not suggest)

| Feature | Status | Removed |
|---------|--------|---------|
| **FAUXCLICKY** (speaker "click" emulation) | ❌ removed | deprecated 2021-02 (#11829), keycodes removed 2022-11 (#18800). Use the `audio`/clicky feature instead. |
| **`MACRO()` / `action_get_macro`** (legacy macro/action_function) | ❌ removed | 2022-02 (#16025). Use core Macros / `SEND_STRING`. |
| **`LAYOUT_kc` macros** | ❌ removed | 2021-05 (#12160). Use plain `LAYOUT`. |
| **deprecated `KEYMAP` alias** | ❌ removed | 2021-11 (#15037). Use `LAYOUT`. |
| **Bootmagic "Full"** | ❌ removed | phased out 2021-05→2021-11. `BOOTMAGIC_ENABLE` is now `yes`/`no` only; "Lite" terminology itself dropped 2024-02 (#22970). |
| **`qmk json-keymap`** | ❌ removed | 2021-02 (#11823). |
| **`SERIAL_LINK`** | ❌ removed | 2021-11 (#14727). |
| **`SERIAL_MOUSE`** | ❌ removed | 2021-11 (#14969). |
| **QWIIC drivers** | ❌ removed | 2021-11 (#14174). Use the normal OLED driver. |
| **MIDI sysex API** | ❌ removed | 2021-11 (#14723). |
| **`arm_atsam` platform** (Massdrop CTRL/ALT) | ❌ removed | 2024-11 (#24337). No replacement yet; users must stay on 0.26.x. |
| **`led_set_user`** | ❌ removed | 2024-08 (#23979). Use `led_update_user`. |
| **`process_action_kb`** callback | ❌ removed | 2025-08 (#25331). |
| **`CTPC` / `CONVERT_TO_PROTON_C`** | ❌ removed | 2025-05 (#25111). Use `CONVERT_TO=proton_c`. |
| **`DEFAULT_FOLDER`** | ❌ removed | 2025-08 (#23281); deprecated 2025-02. Use `keyboard.json` / keyboard aliases. |
| **`FORCE_NKRO` / `usb.force_nkro`** | ❌ removed | 2026-05 (#25262/#26206). Use `host.default.nkro` / `NKRO_DEFAULT_ON`. |
| **`isLeftHand`** | ❌ removed | 2026-05 (#25897). Use `is_keyboard_left()` from `split_util.h`. |
| **`master_left` / `MASTER_LEFT`** | ❌ removed | 2024-08 (#24163). Use split handedness config. |
| **`RING_BUFFERED_6KRO_REPORT_ENABLE`** | ❌ removed | 2024-11 (#24433). |
| **ADNS9800 / PMW33xx SROM firmware blobs** | ❌ removed | 2024-11 (#24428); opt-in 2024-08 (#24001). Sensors work from on-chip firmware. Re-supplying a blob makes your firmware **non-distributable** (GPL clash). |
| **`STM32_PWM_USE_ADVANCED`** | ❌ removed | 2024-11 (#24432). |
| **`OLED_DISPLAY_128X32`** config | ❌ removed | 2026-05 (#26190). |
| **`config_common.h`** | ❌ removed | 2023-05 (#20312). Don't include it. |
| **`USB_LED_*` macros** (`USB_LED_CAPS_LOCK`, `_NUM_LOCK`, `_SCROLL_LOCK`, `_COMPOSE`, `_KANA`) | ❌ removed | 2023-08 (#21366/#21405/#21424/#21436). Use `host_keyboard_leds()` bit helpers. |
| **`keymap.h` / `quantum/keymap.h`** direct includes | ❌ removed | 2023-08 (#21086). |
| **`IS_LED_ON/OFF()`** macros | ❌ removed | 2023-11 (#21878). |
| **`promicro_rp2040` converter** | renamed → `sparkfun_rp2040` | 2024-08 (#24192). |
| **`via` keymaps in `qmk_firmware`** | ❌ removed | migrated to VIA team's External Userspace 2024-05→2024-08 (#24322). PR `via` keymaps to `the-via/qmk_userspace_via`. |
| **`user_keymaps` in `qmk_firmware`** | ❌ removed | 2023-08+ (move to External Userspace). |
| **nix support** | ❌ removed | 2025-05 (#25280, bit-rot). |

### 5.1 Deprecated now (⚠️ slated for removal — prefer the new form)

* **`encoder_update_kb` / `encoder_update_user`** — end-of-life; migrate to
  **Encoder Map** (`ENCODER_MAP_ENABLE`). `ENCODER_MAP_ENABLE` will become
  default-on, then the flag removed entirely. (Deprecated 2025-05.)
* **`RGB_xxx` keycodes** — use `UG_`/`RM_` (§4.3).
* **Keyboard-level overriding of `QK_{LED,RGB}_MATRIX_TOGGLE`** — removed to
  unify on the generic flag-cycling keycodes (2025-11 #25672).
* **`eeconfig_init_kb` C implementations** — migrating to data-driven config.
* **`g_led_config` C arrays** — migrating to data-driven (2025-11 wave).
* **Some nonstandard mod & mod-tap keycode aliases** — deprecated 2025-08 (#25437).

---

## 6. Changelog Highlights (newest first)

One-line-per-notable-item style. ❌ = removal/break, ✨ = notable feature,
🔧 = refactor/migration requiring attention, ⚠️ = deprecation notice.
Keyboard renames happen *every* cycle and are not all listed — assume any build
target may have moved; use External Userspace for portability.

### 0.33.0 — 2026-05-31
* ❌ Removed deprecated `FORCE_NKRO` / `usb.force_nkro` → `host.default.nkro` / `NKRO_DEFAULT_ON`
* ❌ Removed deprecated `isLeftHand` → `is_keyboard_left()` (`split_util.h`)
* ❌ Removed deprecated GPIO defines (final compat) — §4.5
* ❌ Removed `OLED_DISPLAY_128X32` config; removed override of `QK_{LED,RGB}_MATRIX_TOGGLE`; removed deprecated audio pin defines
* ✨ VIA v13; PixArt PMW-3325 sensor driver; Speculative Hold constraints (`SPECULATIVE_HOLD_ONE_KEY`, `SPECULATIVE_HOLD_FLOW_TERM`)
* 🔧 Migrate `SPLIT_OLED_ENABLE`; always generate `.map` files; API version assertion for split_data_sync module
* 🔧 ChibiOS/ChibiOS-Contrib updates (merged, reverted, re-merged)

### 0.32.0 — 2026-02-22
* ❌ Removed deprecated GPIO defines (the big GPIO rename completes — §4.5)
* ⚠️ `isLeftHand` deprecation (removed next cycle)
* 🔧 `config_h_features` removed from generated `info.json`; `ROW_SHIFTER` → core `MATRIX_ROW_SHIFTER`; lint now checks all keymaps; `qmk doctor` reports permission issues

### 0.31.0 — 2025-11-30
* ✨ **Speculative Hold** for mod-taps — applies modifier instantly on keydown (great for Shift+click / Ctrl+scroll)
* ❌ Tap dance state moved out of the action struct — custom tap-dance code must use `tap_dance_get_state(idx)` and `->` notation (not `action->state`)
* 🔧 Massive `g_led_config` → data-driven migration wave; debounce refactored to static allocation; `debounce()` `num_rows` param deprecated; `flowtap` timer made public
* ✨ PixArt PAW-3222 sensor; DIP-switch map in `keymap.json`; STM32F446 default HSE → 8 MHz

### 0.30.0 — 2025-08-31
* ❌ Removed `DEFAULT_FOLDER` handling (use `keyboard.json`/aliases)
* ❌ Removed deprecated `RGB_` and Mouse keycodes (final compat, §4.3)
* 🔒 **VIA matrix-test keylogger mitigation** — QMK unilaterally blocks VIA key-press reporting (VIA team non-responsive to 2022 security report)
* ❌ Removed `process_action_kb` callback
* 🔧 Converter now requires explicit pin-compatibility declaration (`development_board` / `PIN_COMPATIBLE`)
* 🔧 Many bastardkb/helix/tweetydabird/novelkeys folder+rev consolidations; `usb.force_nkro` → `host.default.nkro` migration

### 0.29.0 — 2025-05-25
* ✨ **Flow Tap** core tap-hold option (aka Global Quick Tap / Require Prior Idle) — disables HRM holds during fast typing
* ✨ **Community Modules 1.1.1** — module-defined RGB/LED matrix effects + indicator/pointing/layer callbacks
* ❌ Removed `CTPC` / `CONVERT_TO_PROTON_C` → `CONVERT_TO=proton_c`
* ⚠️ Deprecated `encoder_update_{kb,user}` (migrate to Encoder Map) (§5.1)
* ⚠️ Deprecated `qmk generate-compilation-database` → use `qmk compile --compiledb`
* ⚠️ Deprecated `usb.force_nkro` / `FORCE_NKRO`
* 🔧 Battery-level interface; high-res scrolling; connection keycodes (BT/2.4 GHz); allow disabling EEPROM subsystem entirely; `split.soft_serial_pin` → `split.serial.pin` migration completed

### 0.28.0 — 2025-02-23
* ✨ **Community Modules** (third-party code importable into builds; first-class External Userspace support)
* ✨ **Chordal Hold** tap-hold option ("opposite-hands rule," Achordion-like)
* ❌ Removed deprecated `i2c_master` functions (§4.6), LED-driver deprecated defines
* ⚠️ `DEFAULT_FOLDER` formally deprecated
* 🔧 Unified I2C/UART/SPI headers; `process_record_via` now invoked after `_user`/`_kb`; ChibiOS `stable_21.11.x`

### 0.27.0 — 2024-11-24
* ❌ **Removed `arm_atsam` platform** (Massdrop CTRL/ALT) — no replacement; stay on 0.26.x
* ⚠️ **RGB keycode overhaul**: `RGB_xxx` → `UG_xxx` (underglow) / `RM_xxx` (rgb matrix); `RGB_` acts as `UG_` during transition
* ❌ Removed ADNS9800/PMW33xx SROM blobs (§5)
* ✨ Layer Lock feature; `PDF(layer)` keycode to persist default layer in EEPROM; AT32F415 MCU support
* 🔧 Renamed RGB/HSV structs; extended wheel reports; OS detect `OS_DETECTION_SINGLE_REPORT`

### 0.26.0 — 2024-08-25
* ❌ **All `via`-enabled keymaps removed from `qmk_firmware`** → VIA team's External Userspace
* ❌ Removed deprecated `led_set_user` → `led_update_user`
* ⚠️ ADNS9800/PMW33xx SROM upload now opt-in (`ADNS9800_UPLOAD_SROM` / `PMW33XX_UPLOAD_SROM`)
* 🔧 **Key Override signature change**: drop the cast and the `NULL` terminator — `const key_override_t *key_overrides[] = { ... };`
* 🔧 `promicro_rp2040` converter → `sparkfun_rp2040`; `split.soft_serial_pin` → `split.serial.pin` migration begins; normalise mouse keycodes; rename encoder pin defines

### 0.25.0 — 2024-05-26
* ✨ **`keyboard.json` introduced** — single data file for keyboard-level config; `info.json` becomes shared fragments; `rules.mk` now optional. Old system still works but slated for removal.
* 🔧 **ChibiOS USB endpoints → fully async** — fixes ARM suspend/resume + BIOS/UEFI "stuck keys"/lockups
* ❌ Removed deprecated quantum keycodes (check `quantum_keycodes_legacy.h`)
* ✨ New LED Matrix keycodes; new RGB Matrix keycodes; split `process_{led,rgb}_matrix()`; `RGBW` → `WS2812_RGBW`
* 🔧 Huge data-driven keyboard-conversion wave; `LOCKING_*_ENABLE`, `RGBLIGHT_SPLIT`, `SPLIT_KEYBOARD` → data-driven

### 0.24.0 — 2024-02-25
* 🔧 **Windows DFU driver: libusb → WinUSB** (QMK Toolbox 0.3.0) — re-Zadig if DFU flashing broke
* 🔧 **GPIO rename** begins (§4.5); **I2C API rename** (§4.6)
* 🔧 "Bootmagic Lite" → just "Bootmagic" (terminology)
* ✨ DIP Switch Mapping (`DIP_SWITCH_MAP_ENABLE`); `AUTO_MOUSE_THRESHOLD` configurable; Quantum Painter: ILI9486, SSD1306, native font palettes
* 🔧 LED-driver split-out (IS31FL3742A/3743A/3745/3746A from IS31COMMON); `CKLED2001` → `SNLED27351`; `RGBLED_NUM` → `RGBLIGHT_LED_COUNT`; LED/RGB Matrix config → info.json wave

### 0.23.0 — 2023-11-26
* ✨ **External Userspace** (store/build keymaps outside `qmk_firmware`) — beta
* ✨ Switch-statement keycode **range helpers** (`BASIC_KEYCODE_RANGE`, `MODIFIER_KEYCODE_RANGE`, …) — use these instead of raw `case KC_A ... KC_EXSEL`
* ✨ Quantum Painter SH1106 (128×64) OLED support; `shutdown_kb` callback added; `oled_render_dirty(bool)` for deterministic OLED flush
* 🔧 Peripheral subsystems: `ANALOG_DRIVER_REQUIRED = yes` etc. replace `SRC += analog.c`
* ✨ NKRO on V-USB boards (ATmega32A/328P); macOS Globe key (`AC Next Keyboard Layout Select`)
* 🔧 Massive RGB/LED driver naming/cleanup wave; `CKLED2001`→`SNLED27351`

### 0.22.0 — 2023-08-27
* ❌ `qmk_firmware` **no longer accepts user keymap PRs** (manufacturer keymaps only) → External Userspace
* ❌ Removed old OLED API (`ssd1306.c`/`SSD1306OLED`) → standard OLED driver
* ❌ Unicodemap rename `X(i)`→`UM(i)`, `XP(i,j)`→`UP(i,j)`
* ❌ Removed `USB_LED_*` macros (Caps/Num/Scroll/Compose/Kana lock)
* 🔧 Driver names → **lowercase** (§4.8)
* 🔧 Removed encoder-in-matrix workaround → use Encoder Map
* ✨ RGB Matrix skip-transmit optimization; audio `double`→`float` (ARM perf+size)

### 0.21.0 — 2023-05-28
* ✨ **Repeat Key / Alt Repeat Key** (`QK_REP` / `QK_AREP`)
* ✨ `pre_process_record_kb` / `pre_process_record_user` (runs before `process_combo`)
* ❌ **`IGNORE_MOD_TAP_INTERRUPT` removed** — its behavior is now **default**; use `HOLD_ON_OTHER_KEY_PRESS` to get the old behavior
* ❌ **`config_common.h` removed**; **`RGB_DI_PIN` errors at build** → `ws2812.pin`
* 🔧 Layout/matrix definitions in `info.json` now **mandatory** for merge; `LAYOUT` macros in `.h` no longer accepted; drop `"w":1`/`"h":1`; `encoder_map[][NUM_ENCODERS][2]` → `[NUM_DIRECTIONS]`
* ✨ OLED SH1107 + SPI OLED support; encoder fallback behavior

### 0.20.0 — 2023-02-26
* ❌ `IGNORE_MOD_TAP_INTERRUPT_PER_KEY` removed → `get_hold_on_other_key_press` (note inverted logic + broader keycode arg)
* ❌ `TAPPING_FORCE_HOLD` → `QUICK_TAP_TERM` (ms; 0 disables auto-repeat); `_PER_KEY` → `get_quick_tap_term`
* ✨ Leader Key **rework** — `leader_end_user()` + `leader_sequence_*()` helpers; `LEADER_EXTERNS()`/`LEADER_DICTIONARY()` gone

### 0.19.0 — 2022-11-26
* ✨ **Autocorrect** feature
* 🔧 **Keycode overhaul** — strong keycode versioning for host-tool interop; many renames (§4.4); `KC_GESC`→`QK_GESC`; `DRIVER_LED_COUNT`→`*_MATRIX_LED_COUNT`; `*_STARTUP_*`→`*_DEFAULT_*`
* ❌ Removed legacy fauxclicky/unicode/EEPROM-clear/international/grave-esc keycodes
* ❌ USB IDs in `config.h` now **fail to compile** (use info.json)

### 0.18.0 — 2022-08-27
* ✨ **RP2040 support** (Pi Pico, SparkFun Pro Micro RP2040, KB2040) — near-complete subsystem coverage
* ✨ Board **converters** generalized (`CONVERT_TO=...`, 1→7 boards); `qmk flash <binary>`; generic wear-leveling EEPROM emulation (RP2040 XIP flash, SPI NOR)
* ❌ **`RESET` → `QK_BOOT`** (keymap sweep)
* 🔧 Default layers 32 → **16** (`LAYER_STATE_16BIT`); AVR users gain free flash
* ⚠️ USB IDs in `config.h` start warning (fail next cycle)
* ✨ Pointing-device improvements (Cirque circular/inertial, large mouse reports, PMW33xx overhaul)

### 0.17.0 — 2022-05-28
* ✨ **Caps Word**, **Quantum Painter** (ARM/RISC-V only, not AVR), **Encoder Mapping** (`ENCODER_MAP_ENABLE`)
* ❌ **`RESET` → `QK_BOOT`** begins (still aliased)
* ⚠️ `SEND_STRING` keycode overhaul (deprecated old names — check `send_string_keycodes.h`)
* 🔧 Quantum Painter adds **Pillow** CLI dependency (install via pacman/brew/pip)

### 0.16.0 — 2022-02-26
* ❌ **Legacy `MACRO()` / `action_get_macro` removed** → core Macros
* ✨ `bootloader` configurable in `info.json`; pointing-device config expansions

### 0.15.0 — 2021-11-27
* ❌ **Bootmagic Full removed** — `BOOTMAGIC_ENABLE` is `yes`/`no` only ("lite" now fails)
* ❌ Removed deprecated `KEYMAP` alias; QWIIC drivers; `SERIAL_LINK`; `SERIAL_MOUSE`; MIDI sysex API
* ✨ Dynamic tapping term keycodes; macros in `keymap.json` (up to 32); OLED `bool` callback refactor (`oled_task_user` returns bool, keyboard defers to keymap); "Squeezing AVR" docs; compilation-database command

### 0.14.0 — 2021-08-28
* ❌ Bootmagic Full deprecation step (`=full` fails; `=lite`/`=yes`/`=no` ok)
* ✨ **Extensible split data sync** (per-side custom shared data); large `info.json` expansion (backlight, bluetooth, build.lto, tapping.* , etc.); keyboard `tags`
* 🔧 Data-driven push continues; `BOOTMAGIC_ENABLE = yes` now means Lite

### 0.13.0 — 2021-05-29
* ✨ RGB Matrix for split_common; Teensy 3.6; `qmk console`; LED Matrix improvements
* ❌ **`LAYOUT_kc` removed**; encoder callbacks → `bool`; Bootmagic deprecation begins (`=yes` ⇒ Lite)

### 0.12.0 — 2021-02-27
* ❌ Removed **FAUXCLICKY**; removed `qmk json-keymap`; audio system overhaul; "USB and BT" output option removed

### 0.11.0 — 2020-11-28 / 0.10.0 — 2020-08-29
* Maintenance cycles; relocated keyboards; core fixes; ChibiOS/ARM stability

### 0.9.0 — 2020-05-30
* 🔧 V-USB driver → submodule; per-key tap-hold functions now take `keyrecord_t*`
* 🔧 `RGB_DISABLE_AFTER_TIMEOUT` (ticks) → `RGB_DISABLE_TIMEOUT` (ms; multiply old value by 1200)

### 0.8.0 — 2020-02-29
* 🔧 ChibiOS/ChibiOS-Contrib/uGFX submodule updates; ChibiOS 16-bit SysTick timer overflow fix; `BACKLIGHT_ON_STATE` for HW PWM backlight; `ACTION_LAYER_TAP_KEY()` in `fn_actions` → `LT()`; backlight keycode handling → `process_keycode/`

### 0.7.0 — 2019-08-30
* 🔧 `clang-format` code formatting; LUFA → submodule; `ACTION_LAYER_MOMENTARY()` → `MO()`; `ACTION_BACKLIGHT_*()` → `BL_` keycodes; ❌ `KC_DELT` → `KC_DEL`

---

## 7. ChibiOS Upgrade Procedure (maintainer-side; rarely user-facing)

ChibiOS and ChibiOS-Contrib **must be updated in tandem** — Contrib has a branch
tied to the ChibiOS version and must not be mixed across versions. This is done
by QMK maintainers, not end users, but it explains why a ChibiOS bump can land
as a breaking change (and why suspend/resume/USB behavior can shift).

High-level flow (full commands in `docs/chibios_upgrade_instructions.md`):

1. **ChibiOS** is mirrored from upstream SVN via `git svn` into `qmk/ChibiOS`,
   tagged `ver<XX.x.x>` and `develop_YYYY_qN`.
2. **ChibiOS-Contrib** is cloned, the matching `chibios-<XX.x>.x` branch pushed
   to `qmk/ChibiOS-Contrib`, tagged `develop_YYYY_qN`.
3. In firmware: `git checkout -b chibios-version-bump`, update both submodules
   to `develop_YYYY_qN`, run `./util/chibios_conf_updater.sh`, then
   `qmk mass-compile -j 4` to verify everything builds.
4. On PR merge, reset the `qmk-master`/`qmk-develop` branches of both submodule
   forks to the tagged SHA (so Configurator keeps working).

**User-facing gotcha:** after a ChibiOS bump, ARM boards may need an EEPROM
clear (§3.1/§3.2), and USB suspend/resume/BIOS behavior can change (notably the
2024-05 async-endpoints refactor fixed many ARM "stuck key" issues).

---

## 8. Cross-Reference Index

| If you're touching… | Also see |
|---------------------|----------|
| `config.h` defines, `info.json`/`keyboard.json` schema, layouts | `03-config-and-info-json.md` |
| Keycodes, mod-tap/layer-tap options, Magic, layers | `04-keymaps-and-keycodes.md` |
| Macros, send_string, combos, tap-dance, leader, grave-esc | `05-text-input-and-combos.md` |
| Pointing device, mouse keys, joystick | `06-pointing-and-hid-devices.md` |
| RGB/LED/backlight drivers & keycodes (`UG_`/`RM_`/`LM_`/`BL_`) | `07-led-rgb-backlight.md` |
| OLED driver, Quantum Painter, encoders (map vs callback) | `08-displays.md` |
| GPIO/I2C/SPI/UART/WS2812 driver APIs | `13-drivers-lowlevel.md` |
| Flashing, Zadig, ISP, EEPROM clear, squeezing AVR | `15-flashing-debugging.md` |
| External Userspace, custom quantum functions, PR checklist | `16-userspace-development.md` |
| Split keyboard (`is_keyboard_left`, split sync, handedness) | `10-connectivity.md` |

---

### Quick pre-flight checklist before writing QMK code

Before emitting any of these, verify against this file:
- [ ] Keycode isn't a removed/renamed one (`RESET`, `KC_GESC`, `RGB_*`, `X()`/`XP()`, `CAPS_WORD`, `KC_LEAD`, `KC_LOCK`, `VLK_TOGG`, `USB_LED_*`).
- [ ] GPIO call uses `gpio_*` prefix (not bare `setPinOutput` etc.).
- [ ] I2C calls use `i2c_*_register[_16]()`.
- [ ] Driver selector is **lowercase** (`ws2812`, `is31fl3731`, `snled27351`, `ssd1306`, …).
- [ ] Config is **data-driven** where a migration exists (USB IDs, `RGB_DI_PIN`, `RGBLED_NUM`, matrix/layout, `FORCE_NKRO`, `LOCKING_*`, split serial pin).
- [ ] Not suggesting a removed feature (FAUXCLICKY, `MACRO()`/`action_get_macro`, `LAYOUT_kc`, `KEYMAP`, Bootmagic Full, `arm_atsam`, `led_set_user`, `process_action_kb`, `isLeftHand`, `CTPC`).
- [ ] Callback returns `bool` where the modern signature requires it (OLED, LED/RGB indicators, key overrides, pre_process_record).
- [ ] Encoder logic uses **Encoder Map**, not `encoder_update_user`.
- [ ] NKRO default via `host.default.nkro` / `NKRO_DEFAULT_ON`, not `FORCE_NKRO`.
- [ ] Split-side left check uses `is_keyboard_left()`.
