# LED / Lighting Reference — backlight, indicators, rgblight, rgb_matrix, led_matrix

> **Scope:** All QMK LED/lighting subsystems in one file. Five distinct features with overlapping keycodes but **mutually exclusive hardware targets**. Read the "Which feature do I use?" matrix first — picking the wrong subsystem is the #1 lighting mistake.

Cross-references: driver silicon config (is31fl*/snled27351/aw20216s/ws2812/apa102) → `13-drivers-lowlevel.md`; info.json feature/layout keys → `03-config-and-info-json.md`; split sync (`SPLIT_LED_STATE_ENABLE`, `SPLIT_LAYER_STATE_ENABLE`, `SPLIT_TRANSPORT_MIRROR`) → `10-connectivity.md`; EEPROM persistence model → `03-config-and-info-json.md`; main loop / callback ordering → `01-architecture.md`.

---

## 0. Which feature do I use? (read first)

QMK has **five** lighting features. They target different hardware and **do not coexist arbitrarily**:

| Feature | Hardware | Granularity | Color | Keycodes prefix | `rules.mk` enable | Distinct from |
|---|---|---|---|---|---|---|
| **Backlight** | Single-color LEDs on a PWM/transistor pin (or pins) | Whole-board brightness only | Single fixed color (per installed LED) | `BL_*` | `BACKLIGHT_ENABLE = yes` | one brightness for all keys |
| **LED Indicators** | Up to 5 dedicated GPIO pins for lock LEDs | Per-pin on/off | Single fixed | (no keycodes — host-driven) | (none; `config.h` pins) | just mirrors host lock state |
| **RGBLIGHT** ("underglow") | Addressable strip (WS2812/SK6812/APA102) on 1 data pin | Per-LED, but treated as a strip | Full RGB (HSV) | `UG_*` (legacy `RGB_M_*`) | `RGBLIGHT_ENABLE = yes` | zones/animations, no per-key physical map |
| **RGB_MATRIX** | Per-key RGB LEDs driven by an LED driver IC (is31fl*/snled27351/aw20216s) or addressable strip wired per-key | Per-key, with physical `{x,y}` map | Full RGB (HSV) | `RM_*` | `RGB_MATRIX_DRIVER = ...` (auto-enables) | per-key effects + indicators |
| **LED_MATRIX** | Per-key single-color LEDs driven by same driver ICs | Per-key, with physical `{x,y}` map | Monochrome (value only) | `LM_*` | `LED_MATRIX_DRIVER = ...` (auto-enables) | monochrome twin of RGB_MATRIX |

### Critical coexistence rules (these bite people)

- **RGBLIGHT vs RGB_MATRIX: these CONFLICT.** Both redefine the same legacy `RGB_*` keycodes and the shared "RGB" codepath. RGB_MATRIX is documented as hooking "into the RGBLIGHT system" to reuse keycodes. Enabling both is not a supported configuration — pick one. Modern guidance: use `RM_*` keycodes for RGB_MATRIX, and define `RGB_MATRIX_DISABLE_SHARED_KEYCODES` to stop the `UG_*`/`RGB_M_*` keycodes from also driving RGB_MATRIX.
- **RGB_MATRIX vs LED_MATRIX: mutually exclusive.** They **share the same EEPROM region** (see "EEPROM storage" below) precisely because QMK assumes only one is used at a time. Same driver-IC family, monochrome vs color — choose based on whether your LEDs are RGB.
- **Backlight** is independent of all the above — a board can have backlight + RGBLIGHT (very common on prebuilt boards: single-color key backlight + RGB underglow strip).
- **LED Indicators** is independent of everything; it just reads host lock LED state. It can coexist with any lighting feature (and `BACKLIGHT_CAPS_LOCK` even reuses the backlight pin as a caps indicator).

### "Underglow" vs "per-key RGB" decision
- Strip of addressable LEDs glued to the case, no per-key wiring, no physical-position map needed → **RGBLIGHT**.
- LEDs individually mounted under each switch, driven by an is31fl*/snled27351/aw20216s IC (or a per-key WS2812 chain you want effects + indicators on) → **RGB_MATRIX**.

---

## 1. Backlight

### Summary
Brightness control of single-color backlight LEDs via PWM duty-cycle. Whole-board only; one brightness level for every backlit key. Also exposes a breathing animation and (via `BACKLIGHT_CAPS_LOCK`) can repurpose the backlight as a Caps Lock indicator.

### Enable it
**rules.mk** (primary — backlight is not yet fully data-driven):
```make
BACKLIGHT_ENABLE = yes
BACKLIGHT_DRIVER = pwm        # default. also: timer | software | custom
```
Driver is selected in `rules.mk`, not info.json. There is no info.json `BACKLIGHT_DRIVER` equivalent widely used; pin config still lives in `config.h`.

### Keycodes
| Key | Alias | Description |
|---|---|---|
| `QK_BACKLIGHT_TOGGLE` | `BL_TOGG` | Turn backlight on/off |
| `QK_BACKLIGHT_STEP` | `BL_STEP` | Cycle through levels |
| `QK_BACKLIGHT_ON` | `BL_ON` | Set to max brightness |
| `QK_BACKLIGHT_OFF` | `BL_OFF` | Turn off |
| `QK_BACKLIGHT_UP` | `BL_UP` | Increase level |
| `QK_BACKLIGHT_DOWN` | `BL_DOWN` | Decrease level |
| `QK_BACKLIGHT_TOGGLE_BREATHING` | `BL_BRTG` | Toggle breathing |

### Configuration (config.h)
| Define | Default | Meaning |
|---|---|---|
| `BACKLIGHT_PIN` | *undef* | Pin controlling the LEDs |
| `BACKLIGHT_PINS` | *undef* | **Alternative to `BACKLIGHT_PIN`** — multiple pins switched together (`timer`/`software` drivers only), e.g. `{ F5, B2 }` |
| `BACKLIGHT_LEVELS` | `3` | Number of brightness levels (max **31** excluding off) |
| `BACKLIGHT_CAPS_LOCK` | *undef* | Use backlight as Caps Lock indicator (no dedicated LED) |
| `BACKLIGHT_BREATHING` | *undef* | Enable breathing **if the driver supports it** |
| `BREATHING_PERIOD` | `6` | Seconds per breath |
| `BACKLIGHT_ON_STATE` | `1` | Pin state when "on" — `1`=high (N-channel/NPN), `0`=low (P-channel/PNP) |
| `BACKLIGHT_LIMIT_VAL` | `255` | Max duty cycle (255 = full). Lower reduces max brightness |
| `BACKLIGHT_DEFAULT_ON` | `true` | On after EEPROM clear |
| `BACKLIGHT_DEFAULT_BREATHING` | `false` | Breathing on after EEPROM clear |
| `BACKLIGHT_DEFAULT_LEVEL` | `BACKLIGHT_LEVELS` | Default level after EEPROM clear |

### Drivers (`BACKLIGHT_DRIVER` in rules.mk)
- **`pwm`** (default) — hardware PWM. Most efficient. Pin must be a hardware-PWM-capable pin.
- **`timer`** — interrupt-driven GPIO toggling. Any GPIO pin. `BACKLIGHT_PWM_TIMER` (default `1`) selects the timer. **Timer choice may conflict with the Audio feature.**
- **`software`** — PWM emulated in the main loop. Max hardware compat, **but no breathing support and flickers when keyboard is busy.**
- **`custom`** — implement your own: `void backlight_init_ports(void)`, `void backlight_set(uint8_t level)`, `void backlight_task(void)` (runs in main loop — keep it short).

#### AVR PWM driver pin support (only marked cells do hardware PWM; else use `timer`)
| Pin | AT90USB64/128 | AT90USB162 | ATmega16/32U4 | ATmega16/32U2 | ATmega32A | ATmega328/P |
|---|---|---|---|---|---|---|
| `B1`,`B2` | | | | | | Timer 1 |
| `B5`,`B6` | Timer 1 | | Timer 1 | | | |
| `B7` | Timer 1 | Timer 1 | Timer 1 | Timer 1 | | |
| `C4` | Timer 3 | | | | | |
| `C5` | Timer 3 | Timer 1 | | Timer 1 | | |
| `C6` | Timer 3 | Timer 1 | Timer 3 | Timer 1 | | |
| `D4`,`D5` | | | | | Timer 1 | |

#### ChibiOS/ARM (`pwm` driver) — also requires `halconf.h` `HAL_USE_PWM TRUE` + `mcuconf.h` `STM32_PWM_USE_TIMx TRUE`
| Define | Default | Meaning |
|---|---|---|
| `BACKLIGHT_PWM_DRIVER` | `PWMD4` | PWM driver |
| `BACKLIGHT_PWM_CHANNEL` | `3` | PWM channel |
| `BACKLIGHT_PAL_MODE` | `2` | Pin alternate function |
| `BACKLIGHT_PWM_PERIOD` | *undef* | PWM period in counter ticks (platform-dependent default) |

#### ChibiOS/ARM (`timer` driver) — requires `HAL_USE_GPT TRUE` + `STM32_GPT_USE_TIMx TRUE`
| Define | Default | Meaning |
|---|---|---|
| `BACKLIGHT_GPT_DRIVER` | `GPTD15` | GPT timer |

### C API
| Function | Purpose |
|---|---|
| `void backlight_toggle(void)` | Toggle on/off |
| `void backlight_enable(void)` / `void backlight_disable(void)` | Force on/off |
| `void backlight_step(void)` | Cycle levels |
| `void backlight_increase(void)` / `void backlight_decrease(void)` | Bump level |
| `void backlight_level(uint8_t level)` | Set level 0..`BACKLIGHT_LEVELS` |
| `uint8_t get_backlight_level(void)` | Current level |
| `bool is_backlight_enabled(void)` | On? |
| `void backlight_toggle_breathing(void)` / `..._enable_breathing` / `..._disable_breathing` | Breathing control |
| `bool is_backlight_breathing(void)` | Breathing on? |

> Note: backlight has **no `_noeeprom` variants** and **no `_user`/`_kb` callbacks** — it's controlled purely via keycodes and the above API. Unlike RGB_MATRIX/LED_MATRIX it does not persist complex state.

### Gotchas — backlight
- **`BACKLIGHT_LEVELS` max is 31** (excluding off). Higher values silently misbehave.
- **`software` driver cannot breathe** and flickers under load.
- **`timer` driver timer conflicts with Audio** — both want the same AVR timer.
- **`BACKLIGHT_ON_STATE`** depends on your transistor: N-channel/NPN gate → `1` (default); P-channel/PNP → `0`. Wrong value = LEDs always-on or always-off.
- AVR hardware-PWM is **pin-restricted** (table above). Wrong pin → silent failure; fall back to `timer` driver.
- `BACKLIGHT_PINS` (plural) only works with `timer`/`software`, not `pwm`.
- ChibiOS requires both `halconf.h` (`HAL_USE_PWM`/`HAL_USE_GPT`) **and** `mcuconf.h` timer enables at the keyboard level — forgetting one is a common silent-no-backlight bug.
- `BACKLIGHT_CAPS_LOCK` repurposes the whole backlight, not a single key.

---

## 2. LED Indicators (host lock LEDs)

### Summary
Reads the 5 USB-HID lock LEDs (Num/Caps/Scroll Lock, Compose, Kana) and drives up to 5 GPIO pins, and/or exposes them to user code via `led_update_*` callbacks. This is the *host-driven* indicator layer — independent of RGB.

### Enable it
No `rules.mk` flag. Configure pins in `config.h`:
| Define | Default | Meaning |
|---|---|---|
| `LED_NUM_LOCK_PIN` | *undef* | Num Lock LED pin |
| `LED_CAPS_LOCK_PIN` | *undef* | Caps Lock LED pin |
| `LED_SCROLL_LOCK_PIN` | *undef* | Scroll Lock LED pin |
| `LED_COMPOSE_PIN` | *undef* | Compose LED pin |
| `LED_KANA_PIN` | *undef* | Kana LED pin |
| `LED_PIN_ON_STATE` | `1` | Pin state when "on" (`1`=high, `0`=low) |

### C API / callbacks
| Signature | Purpose |
|---|---|
| `bool led_update_kb(led_t led_state)` | Keyboard-level callback when any of the 5 LEDs change. Return `false` to **override** QMK's default pin driving. |
| `bool led_update_user(led_t led_state)` | Keymap-level. Return `true` to let `led_update_kb` proceed; `false` to suppress (depends on kb impl). |
| `led_t host_keyboard_led_state(void)` | Current state as a struct (`.num_lock`, `.caps_lock`, `.scroll_lock`, `.compose`, `.kana`). Use outside callbacks. |
| `void led_update_ports(void)` | Writes the configured pin states to hardware. Call manually inside `led_update_*` if you want to combine custom logic with default pin behavior. |
| `uint8_t host_keyboard_leds(void)` | **Deprecated.** Returns raw `uint8_t` bitmask. Use `host_keyboard_led_state()`. |

#### `led_t` fields
`.num_lock`, `.caps_lock`, `.scroll_lock`, `.compose`, `.kana` — all `bool`.

### Behavior & ordering
- `led_update_kb` runs the default pin-writing, then (or around) calls `led_update_user`. Convention: kb calls user first, branches on its return. See example.
- **Timing warning:** `host_keyboard_led_state()` may reflect updated state *before* `led_update_user()` fires — don't rely on callback ordering to dedupe; track previous state yourself.
- On **split keyboards**, indicator state must be synced to the slave with `#define SPLIT_LED_STATE_ENABLE` (see `10-connectivity.md`).

### Examples
Keyboard-level pin driving (inverted LEDs — common when LED is between pin and VCC):
```c
bool led_update_kb(led_t led_state) {
    bool res = led_update_user(led_state);
    if (res) {
        gpio_write_pin(B0, !led_state.num_lock);
        gpio_write_pin(B1, !led_state.caps_lock);
        gpio_write_pin(B2, !led_state.scroll_lock);
        gpio_write_pin(B3, !led_state.compose);
        gpio_write_pin(B4, !led_state.kana);
    }
    return res;
}
```
Sound on Caps Lock toggle (user-level, returns `true` so kb still drives pins):
```c
bool led_update_user(led_t led_state) {
    static uint8_t caps_state = 0;
    if (caps_state != led_state.caps_lock) {
        led_state.caps_lock ? PLAY_SONG(caps_on) : PLAY_SONG(caps_off);
        caps_state = led_state.caps_lock;
    }
    return true;
}
```

### Gotchas — LED indicators
- **Split keyboards need `SPLIT_LED_STATE_ENABLE`** or the slave half's lock LEDs won't update.
- `host_keyboard_leds()` is deprecated; use `host_keyboard_led_state()`.
- `host_keyboard_led_state()` can race ahead of `led_update_user()` — track prior state manually if you need edge detection.
- `LED_PIN_ON_STATE` polarity depends on whether the LED sits between pin-and-VCC (active low) or pin-and-GND (active high).
- Repurposing a lock LED as a layer indicator: do it in `led_update_user`/`layer_state_set_user` and call `led_update_ports()` for the ones you still want default behavior on.
- Ergodox boards have bespoke APIs (`ergodox_right_led_1_on/off()`, `ergodox_right_led_set(led, n)`, `ergodox_led_all_set(n)`, `LED_BRIGHTNESS_LO`/`_HI`) — board-specific, not generic.

---

## 3. RGBLIGHT ("underglow" / addressable strip)

### Summary
Controls an addressable LED strip (WS2811/WS2812/WS2812B/WS2812C, SK6812/SK6812MINI/SK6805, APA102) on a single data pin. Uses HSV color. Treats LEDs as a linear strip with zones/animations — **no per-key physical map**, no per-key indicators (use Lighting Layers instead).

### Enable it
**rules.mk:**
```make
RGBLIGHT_ENABLE = yes
RGBLIGHT_DRIVER = ws2812   # default; or apa102
```
**config.h** (minimum):
| Define | Default | Meaning |
|---|---|---|
| `WS2812_DI_PIN` | *undef* | WS2812 data pin |
| `APA102_DI_PIN` / `APA102_CI_PIN` | *undef* | APA102 data / clock pin (both required) |
| `RGBLIGHT_LED_COUNT` | *undef* | Number of LEDs |
| `RGBLED_SPLIT` | *undef* | (Split) LEDs per half, e.g. `{ 10, 10 }` |

> ARM boards: the default WS2812 bitbang driver works but dedicated PWM/SPI drivers are faster — see `13-drivers-lowlevel.md` (ws2812).

### Color model — HSV
QMK uses **Hue/Saturation/Value**, not RGB, for user-facing color. Hue cycles 0–255 around the wheel; Saturation 0 (white) – 255 (pure); Value 0 (off) – 255 (max, clamped by `RGBLIGHT_LIMIT_VAL`). Named colors (`HSV_RED`, `HSV_CYAN`, …) defined in `quantum/color.h` (see Colors table below).

### Keycodes
| Key | Alias | Description |
|---|---|---|
| `QK_UNDERGLOW_TOGGLE` | `UG_TOGG` | Toggle on/off |
| `QK_UNDERGLOW_MODE_NEXT` | `UG_NEXT` | Next mode (Shift = reverse) |
| `QK_UNDERGLOW_MODE_PREVIOUS` | `UG_PREV` | Prev mode (Shift = forward) |
| `QK_UNDERGLOW_HUE_UP` | `UG_HUEU` | Hue up (Shift = down) |
| `QK_UNDERGLOW_HUE_DOWN` | `UG_HUED` | Hue down (Shift = up) |
| `QK_UNDERGLOW_SATURATION_UP` | `UG_SATU` | Sat up (Shift = down) |
| `QK_UNDERGLOW_SATURATION_DOWN` | `UG_SATD` | Sat down (Shift = up) |
| `QK_UNDERGLOW_VALUE_UP` | `UG_VALU` | Brightness up (Shift = down) |
| `QK_UNDERGLOW_VALUE_DOWN` | `UG_VALD` | Brightness down (Shift = up) |
| `QK_UNDERGLOW_SPEED_UP` | `UG_SPDU` | Speed up (Shift = down) |
| `QK_UNDERGLOW_SPEED_DOWN` | `UG_SPDD` | Speed down (Shift = up) |
| `RGB_MODE_PLAIN` | `RGB_M_P` | Static (**deprecated**) |
| `RGB_MODE_BREATHE` | `RGB_M_B` | Breathing (**deprecated**) |
| `RGB_MODE_RAINBOW` | `RGB_M_R` | Rainbow (**deprecated**) |
| `RGB_MODE_SWIRL` | `RGB_M_SW` | Swirl (**deprecated**) |
| `RGB_MODE_SNAKE` | `RGB_M_SN` | Snake (**deprecated**) |
| `RGB_MODE_KNIGHT` | `RGB_M_K` | Knight (**deprecated**) |
| `RGB_MODE_XMAS` | `RGB_M_X` | Christmas (**deprecated**) |
| `RGB_MODE_GRADIENT` | `RGB_M_G` | Gradient (**deprecated**) |
| `RGB_MODE_RGBTEST` | `RGB_M_T` | RGB test (**deprecated**) |
| `RGB_MODE_TWINKLE` | `RGB_M_TW` | Twinkle (**deprecated**) |

> **Shared-keycode trap:** `UG_*` / `RGB_M_*` keycodes **also drive RGB_MATRIX** if it is enabled (legacy behavior being deprecated). If you run RGB_MATRIX, add `#define RGB_MATRIX_DISABLE_SHARED_KEYCODES` and use the `RM_*` keycodes instead.

### Configuration (config.h)
| Define | Default | Meaning |
|---|---|---|
| `RGBLIGHT_HUE_STEP` | `8` | Hue increment per adjustment |
| `RGBLIGHT_SAT_STEP` | `17` | Saturation increment per adjustment |
| `RGBLIGHT_VAL_STEP` | `17` | Brightness increment per adjustment |
| `RGBLIGHT_LIMIT_VAL` | `255` | Max brightness |
| `RGBLIGHT_SLEEP` | *undef* | Turn RGB off when host sleeps |
| `RGBLIGHT_SPLIT` | *undef* | Enable split sync (use with `RGBLED_SPLIT`) |
| `RGBLIGHT_DEFAULT_MODE` | `RGBLIGHT_MODE_STATIC_LIGHT` | Default mode after EEPROM clear |
| `RGBLIGHT_DEFAULT_HUE` | `0` (red) | Default hue |
| `RGBLIGHT_DEFAULT_SAT` | `255` | Default saturation |
| `RGBLIGHT_DEFAULT_VAL` | `RGBLIGHT_LIMIT_VAL` | Default brightness |
| `RGBLIGHT_DEFAULT_SPD` | `0` | Default speed |
| `RGBLIGHT_DEFAULT_ON` | `true` | On after EEPROM clear |

### Effects & animations
Static light is **always enabled**. Others opt-in via `RGBLIGHT_EFFECT_*`:
| Mode symbol | Sub-variants | Enable define |
|---|---|---|
| `RGBLIGHT_MODE_STATIC_LIGHT` | — | always on |
| `RGBLIGHT_MODE_BREATHING` | 0,1,2,3 | `RGBLIGHT_EFFECT_BREATHING` |
| `RGBLIGHT_MODE_RAINBOW_MOOD` | 0,1,2 | `RGBLIGHT_EFFECT_RAINBOW_MOOD` |
| `RGBLIGHT_MODE_RAINBOW_SWIRL` | 0–5 | `RGBLIGHT_EFFECT_RAINBOW_SWIRL` |
| `RGBLIGHT_MODE_SNAKE` | 0–5 | `RGBLIGHT_EFFECT_SNAKE` |
| `RGBLIGHT_MODE_KNIGHT` | 0,1,2 | `RGBLIGHT_EFFECT_KNIGHT` |
| `RGBLIGHT_MODE_CHRISTMAS` | — | `RGBLIGHT_EFFECT_CHRISTMAS` |
| `RGBLIGHT_MODE_STATIC_GRADIENT` | 0–9 | `RGBLIGHT_EFFECT_STATIC_GRADIENT` |
| `RGBLIGHT_MODE_RGB_TEST` | — | `RGBLIGHT_EFFECT_RGB_TEST` |
| `RGBLIGHT_MODE_ALTERNATING` | — | `RGBLIGHT_EFFECT_ALTERNATING` |
| `RGBLIGHT_MODE_TWINKLE` | 0–5 | `RGBLIGHT_EFFECT_TWINKLE` |

**`RGBLIGHT_ANIMATIONS` (enable-all) is deprecated** — explicitly define each effect you want. Disabling unused effects saves ~flash (e.g. `#undef RGBLIGHT_EFFECT_STATIC_GRADIENT` + `#undef RGBLIGHT_EFFECT_RAINBOW_SWIRL` ≈ 4 KiB).

#### Effect tuning defines
| Define | Default | Meaning |
|---|---|---|
| `RGBLIGHT_EFFECT_BREATHE_CENTER` | *undef* | Breathing curve, 1.0–2.7 |
| `RGBLIGHT_EFFECT_BREATHE_MAX` | `255` | Breathing max brightness, 1–255 |
| `RGBLIGHT_EFFECT_CHRISTMAS_INTERVAL` | `40` | ms between christmas steps |
| `RGBLIGHT_EFFECT_CHRISTMAS_STEP` | `2` | LEDs per red/green group |
| `RGBLIGHT_EFFECT_KNIGHT_LED_NUM` | `RGBLIGHT_LED_COUNT` | LEDs the knight travels |
| `RGBLIGHT_EFFECT_KNIGHT_LENGTH` | `3` | LEDs lit for knight |
| `RGBLIGHT_EFFECT_KNIGHT_OFFSET` | `0` | Knight start offset |
| `RGBLIGHT_RAINBOW_SWIRL_RANGE` | `255` | Swirl hue range |
| `RGBLIGHT_EFFECT_SNAKE_LENGTH` | `4` | LEDs lit for snake |
| `RGBLIGHT_EFFECT_TWINKLE_LIFE` | `200` | Twinkle brighten/dim speed (steps) |
| `RGBLIGHT_EFFECT_TWINKLE_PROBABILITY` | `1/127` | Per-LED twinkle chance per step |

#### Animation speed arrays (ms between steps) — override in keymap
`RGBLED_BREATHING_INTERVALS[] {30,20,10,5}`, `RGBLED_RAINBOW_MOOD_INTERVALS[] {120,60,30}`, `RGBLED_RAINBOW_SWIRL_INTERVALS[] {100,50,20}`, `RGBLED_SNAKE_INTERVALS[] {100,50,20}`, `RGBLED_KNIGHT_INTERVALS[] {127,63,31}`, `RGBLED_TWINKLE_INTERVALS[] {50,25,10}`, `RGBLED_GRADIENT_RANGES[] {255,170,127,85,64}` (hue ranges for gradient modes). All `PROGMEM`.

### Lighting Layers (status indicators via the strip)
Enable with `#define RGBLIGHT_LAYERS`. Overlay colored LED segments without disrupting animations — used for layer/caps-lock indication.
- Default **8 layers**, expandable to **32** via `RGBLIGHT_MAX_LAYERS` (more = bigger firmware + slower split sync).
- Define segments with `RGBLIGHT_LAYER_SEGMENTS({start, count, HSV_COLOR}, ...)`, combine via `RGBLIGHT_LAYERS_LIST(...)`, assign in `keyboard_post_init_user`: `rgblight_layers = my_rgb_layers;`
- **Later layers in the list take precedence** (override earlier).
- Toggle at runtime: `rgblight_set_layer_state(index, bool)`.
- **Split:** flash **both halves** when changing `rgblight_layers`; sync needs `SPLIT_LAYER_STATE_ENABLE`.
- `RGBLIGHT_LAYER_BLINK` → `rgblight_blink_layer(index, ms)` / `rgblight_blink_layer_repeat(index, ms, count)`; blinking **accumulates** across layers — use `rgblight_unblink_layer(i)` / `rgblight_unblink_all_but_layer(i)` to isolate.
- `RGBLIGHT_LAYERS_OVERRIDE_RGB_OFF` → layers show even when RGB is toggled off.
- `RGBLIGHT_LAYERS_RETAIN_VAL` → layers use current brightness instead of their configured value.
- **Lighting Layers is RGBLIGHT-only** — for RGB_MATRIX use `rgb_matrix_indicators_*` instead.

### C API (selection — full list in `quantum/rgblight/rgblight.h`)
Most setters have `_noeeprom` variants that skip EEPROM writes — use these inside callbacks/macros to avoid wear/race.
- **Flush/range:** `rgblight_set()`, `rgblight_set_clipping_range(pos, num)`, `rgblight_set_effect_range(pos, num)`
- **Per-LED direct (RAM only, not EEPROM):** `rgblight_setrgb_at(r,g,b,index)`, `rgblight_sethsv_at(h,s,v,index)`, `rgblight_setrgb_range(...)`, `rgblight_sethsv_range(...)`, `rgblight_setrgb(r,g,b)`, `rgblight_setrgb_master/slave(...)`, `rgblight_sethsv_master/slave(...)`
- **Mode:** `rgblight_mode(x)` / `_noeeprom`, `rgblight_step()` / `_noeeprom`, `rgblight_step_reverse()` / `_noeeprom`, `rgblight_reload_from_eeprom()`
- **On/off:** `rgblight_toggle/enable/disable` (+`_noeeprom`)
- **HSV:** `rgblight_increase/decrease_hue/sat/val` (+`_noeeprom`), `rgblight_sethsv(h,s,v)` / `_noeeprom`
- **Speed:** `rgblight_increase/decrease_speed` (+`_noeeprom`), `rgblight_set_speed(x)` / `_noeeprom` (0–255)
- **Layers:** `rgblight_get_layer_state(i)`, `rgblight_set_layer_state(i, is_on)`, `rgblight_blink_layer(i, ms)`, `rgblight_blink_layer_repeat(i, ms, n)`, `rgblight_unblink_layer(i)`, `rgblight_unblink_all_but_layer(i)`
- **Query:** `rgblight_is_enabled()`, `rgblight_get_mode()`, `rgblight_get_hue/sat/val/speed()`

### LED remapping & clipping
- `RGBLIGHT_LED_MAP { 3, 2, 1, 0 }` (size = `RGBLIGHT_LED_COUNT`) — remaps logical→physical LED order.
- `rgblight_set_clipping_range(pos, num)` — output a sub-range of a larger buffer (useful to treat split halves as contiguous). Combinable with `RGBLIGHT_LED_MAP`.

### Colors (in `quantum/color.h`)
`RGB_*` for `setrgb*`, `HSV_*` for `sethsv*`: `AZURE, BLACK/OFF, BLUE, CHARTREUSE, CORAL, CYAN, GOLD, GOLDENROD, GREEN, MAGENTA, ORANGE, PINK, PURPLE, RED, SPRINGGREEN, TEAL, TURQUOISE, WHITE, YELLOW`.

### Velocikey (typing-speed → effect speed)
`VELOCIKEY_ENABLE = yes` in rules.mk + `VK_TOGG` keycode. Controls speed of Breathing / Rainbow Mood / Rainbow Swirl / Snake / Knight. No config knobs — edit `velocikey.c` to tune.

### Gotchas — RGBLIGHT
- **`RGBLIGHT_ANIMATIONS` is deprecated.** Define each `RGBLIGHT_EFFECT_*` explicitly.
- `UG_*`/`RGB_M_*` keycodes **also drive RGB_MATRIX** (being deprecated). Define `RGB_MATRIX_DISABLE_SHARED_KEYCODES` if both subsystems' code is present.
- These keycodes are **not USB HID keycodes** — `tap_code16()` won't work; call the `rgblight_*` functions directly from `process_record_user`/`encoder_update_user`.
- Split RGB needs `RGBLIGHT_SPLIT` **and** `RGBLED_SPLIT`; flash both halves after editing `rgblight_layers` or changing `RGBLIGHT_MAX_LAYERS`.
- Lighting Layers ≠ RGB Matrix indicators — different APIs entirely.
- `RGBLIGHT_LIMIT_VAL` clamps `RGBLIGHT_DEFAULT_VAL` and per-LED `v`.

---

## 4. RGB_MATRIX (per-key RGB)

### Summary
Per-key RGB LEDs driven by an external driver IC (is31fl*/snled27351/aw20216s) or a per-key addressable chain, with a physical `{x,y}` map (`g_led_config`), 50+ effects, and per-key indicator callbacks. The right choice when you have individually-addressable RGB under each switch.

### Enable it
**rules.mk** (driver auto-enables the feature):
```make
RGB_MATRIX_DRIVER = is31fl3733   # or is31fl3741, snled27351, aw20216s, ws2812, apa102, ...
```
Driver silicon config (I²C address, count, pins, `RGB_MATRIX_LED_COUNT`) → `13-drivers-lowlevel.md`. Layout/`g_led_config` and feature flags can also be expressed in info.json → `03-config-and-info-json.md`.

### Supported drivers & max LEDs
| Driver | Max LEDs | Driver | Max LEDs |
|---|---|---|---|
| APA102 | ? | IS31FL3736 | 32 |
| AW20216S | 72 | IS31FL3737 | 48 |
| IS31FL3218 | 6 | IS31FL3741 | 117 |
| IS31FL3236 | 12 | IS31FL3742A | 60 |
| IS31FL3729 | 45 | IS31FL3743A | 66 |
| IS31FL3731 | 48 | IS31FL3745 | 48 |
| IS31FL3733 | 64 | IS31FL3746A | 24 |
| SNLED27351 | 64 | WS2812 | ? |

> **Driver doc inconsistency:** per-IC max-LED numbers differ between the LED_MATRIX table (which lists full matrix capacity) and the RGB_MATRIX table (which lists a typical per-board subset). Always confirm against the driver page in `13-drivers-lowlevel.md`.

### `g_led_config` (the heart of per-key)
```c
led_config_t g_led_config = { {
  // 1) Key Matrix (row,col) -> LED index    (NO_LED where none)
  {   5, NO_LED, NO_LED,   0 },
  { NO_LED, NO_LED, NO_LED, NO_LED },
  {   4, NO_LED, NO_LED,   1 },
  {   3, NO_LED, NO_LED,   2 }
}, {
  // 2) LED index -> physical {x,y}; range {0..224, 0..64}, center {112,32}
  { 188, 16 }, { 187, 48 }, { 149, 64 }, { 112, 64 }, { 37, 48 }, { 38, 16 }
}, {
  // 3) LED index -> flag bitmask (see Flags)
  1, 4, 4, 4, 4, 1
} };
```
Position formula (physical layout, not electrical):
```c
x = 224 / (NUMBER_OF_COLS - 1) * COL_POSITION;
y =  64 / (NUMBER_OF_ROWS - 1) * ROW_POSITION;
```
Override center with `#define RGB_MATRIX_CENTER { 112, 32 }`. Max x/y = 255, **recommended max 224** (animation runoff room). Reverse lookup available as `g_led_config.matrix_co[row][col]` (→ LED index or `NO_LED`).

### LED Flags (bitmask — set per LED in `g_led_config.flags[]`)
| Define | Value | Meaning |
|---|---|---|
| `LED_FLAG_NONE` | `0x00` | No flags |
| `LED_FLAG_ALL` | `0xFF` | All flags |
| `LED_FLAG_MODIFIER` | `0x01` | Modifier key LED |
| `LED_FLAG_UNDERGLOW` | `0x02` | Underglow LED (**RGB_MATRIX only** — absent from LED_MATRIX) |
| `LED_FLAG_KEYLIGHT` | `0x04` | Key backlight LED |
| `LED_FLAG_INDICATOR` | `0x08` | State-indicator LED |
| `HAS_FLAGS(bits, flags)` | — | true if `bits` has **all** `flags` |
| `HAS_ANY_FLAGS(bits, flags)` | — | true if `bits` has **any** `flags` |

> **RGB_MATRIX vs LED_MATRIX flag difference:** `LED_FLAG_UNDERGLOW` (`0x02`) exists only in RGB_MATRIX. The default `RGB_MATRIX_FLAG_STEPS` cycles through `{ALL, KEYLIGHT|MODIFIER, UNDERGLOW, NONE}`; LED_MATRIX's default is `{ALL, KEYLIGHT|MODIFIER, NONE}`. Recommend each LED carry exactly one flag type.

### Keycodes
| Key | Alias | Description |
|---|---|---|
| `QK_RGB_MATRIX_ON` / `QK_RGB_MATRIX_OFF` | `RM_ON` / `RM_OFF` | On / off |
| `QK_RGB_MATRIX_TOGGLE` | `RM_TOGG` | Toggle |
| `QK_RGB_MATRIX_MODE_NEXT` / `_PREVIOUS` | `RM_NEXT` / `RM_PREV` | Cycle effects |
| `QK_RGB_MATRIX_HUE_UP` / `_DOWN` | `RM_HUEU` / `RM_HUED` | Hue |
| `QK_RGB_MATRIX_SATURATION_UP` / `_DOWN` | `RM_SATU` / `RM_SATD` | Saturation |
| `QK_RGB_MATRIX_VALUE_UP` / `_DOWN` | `RM_VALU` / `RM_VALD` | Brightness |
| `QK_RGB_MATRIX_SPEED_UP` / `_DOWN` | `RM_SPDU` / `RM_SPDD` | Speed |
| `QK_RGB_MATRIX_FLAG_NEXT` / `_PREVIOUS` | `RM_FLGN` / `RM_FLGP` | Cycle flag steps |

### Effects (enum `rgb_matrix_effects`) — enable individually via `ENABLE_RGB_MATRIX_<NAME>`
All honor current Hue/Sat/Val/Speed unless noted.
- **Static:** `SOLID_COLOR` (=1, no speed), `ALPHAS_MODS`, `GRADIENT_UP_DOWN`, `GRADIENT_LEFT_RIGHT`
- **Band/fade:** `BREATHING`, `BAND_SAT`, `BAND_VAL`, `BAND_PINWHEEL_SAT`, `BAND_PINWHEEL_VAL`, `BAND_SPIRAL_SAT`, `BAND_SPIRAL_VAL`
- **Cycle/rainbow:** `CYCLE_ALL`, `CYCLE_LEFT_RIGHT`, `CYCLE_UP_DOWN`, `CYCLE_OUT_IN`, `CYCLE_OUT_IN_DUAL`, `RAINBOW_MOVING_CHEVRON`, `CYCLE_PINWHEEL`, `CYCLE_SPIRAL`, `DUAL_BEACON`, `RAINBOW_BEACON`, `RAINBOW_PINWHEELS`, `FLOWER_BLOOMING`
- **Random:** `RAINDROPS`, `JELLYBEAN_RAINDROPS`, `HUE_BREATHING`, `HUE_PENDULUM`, `HUE_WAVE`
- **Pixel/framebuffer:** `PIXEL_FRACTAL`, `PIXEL_FLOW`, `PIXEL_RAIN`, `TYPING_HEATMAP` *(framebuffer)*, `DIGITAL_RAIN` *(framebuffer)*
- **Reactive (keypress):** `SOLID_REACTIVE_SIMPLE`, `SOLID_REACTIVE`, `SOLID_REACTIVE_WIDE`, `SOLID_REACTIVE_MULTIWIDE`, `SOLID_REACTIVE_CROSS`, `SOLID_REACTIVE_MULTICROSS`, `SOLID_REACTIVE_NEXUS`, `SOLID_REACTIVE_MULTINEXUS`, `SPLASH`, `MULTISPLASH`, `SOLID_SPLASH`, `SOLID_MULTISPLASH`
- **Starlight/river:** `STARLIGHT`, `STARLIGHT_SMOOTH`, `STARLIGHT_DUAL_HUE`, `STARLIGHT_DUAL_SAT`, `RIVERFLOW`

> Reactive + framebuffer effects add logic and **increase firmware size** — enable selectively. `RGB_MATRIX_NONE = 0`, `RGB_MATRIX_SOLID_COLOR = 1`.

#### Typing Heatmap tuning
| Define | Default | Meaning |
|---|---|---|
| `RGB_MATRIX_TYPING_HEATMAP_DECREASE_DELAY_MS` | `25` | ms between temperature decreases |
| `RGB_MATRIX_TYPING_HEATMAP_SPREAD` | `40` | Distance effect spreads to neighbors |
| `RGB_MATRIX_TYPING_HEATMAP_AREA_LIMIT` | `16` | How hot neighbors get per press |
| `RGB_MATRIX_TYPING_HEATMAP_SLIM` | *undef* | Disable spread entirely |
| `RGB_MATRIX_TYPING_HEATMAP_INCREASE_STEP` | `32` | HSV shades gained per press (lower = more presses to heat up) |

#### Solid Reactive gradient mode
`#define RGB_MATRIX_SOLID_REACTIVE_GRADIENT_MODE` — auto-cycle reactive hue over time; duration set by `RM_SPDU`/`RM_SPDD`.

### Custom effects
`RGB_MATRIX_CUSTOM_USER = yes` (keymap/userspace) or `RGB_MATRIX_CUSTOM_KB = yes` (keyboard). Create `rgb_matrix_user.inc` / `rgb_matrix_kb.inc`:
```c
// NO #pragma once
RGB_MATRIX_EFFECT(my_effect)         // declare (no semicolon)
#ifdef RGB_MATRIX_CUSTOM_EFFECT_IMPLS
static bool my_effect(effect_params_t* params) {
    RGB_MATRIX_USE_LIMITS(led_min, led_max);
    for (uint8_t i = led_min; i < led_max; i++) rgb_matrix_set_color(i, 0xff, 0xff, 0x00);
    return rgb_matrix_check_finished_leds(led_max);
}
#endif
```
Switch via `rgb_matrix_mode(RGB_MATRIX_CUSTOM_my_effect);`. Built-ins live in `quantum/rgb_matrix/animations/`.

### config.h options
| Define | Default | Meaning |
|---|---|---|
| `RGB_MATRIX_MODE_NAME_ENABLE` | *undef* | Enable `rgb_matrix_get_mode_name()` (costs flash) |
| `RGB_MATRIX_KEYRELEASES` | *undef* | Reactive effects fire on **release** not press |
| `RGB_MATRIX_TIMEOUT` | `0` | ms of inactivity before RGB turns off (0 = never) |
| `RGB_MATRIX_SLEEP` | *undef* | Turn effects off when suspended |
| `RGB_MATRIX_LED_PROCESS_LIMIT` | `(LED_COUNT+4)/5` | LEDs processed per task run (raise = smoother, lower CPU) |
| `RGB_MATRIX_LED_FLUSH_LIMIT` | `16` | ms min between flushes (16 = ~60fps) |
| `RGB_MATRIX_MAXIMUM_BRIGHTNESS` | `200` | **(note: differs from LED_MATRIX's 255!)** Max brightness cap |
| `RGB_MATRIX_DEFAULT_ON` | `true` | On after EEPROM clear |
| `RGB_MATRIX_DEFAULT_MODE` | `RGB_MATRIX_CYCLE_LEFT_RIGHT` | Default effect |
| `RGB_MATRIX_DEFAULT_HUE` / `_SAT` / `_VAL` / `_SPD` | `0`/`255`/`=MAX_BRIGHTNESS`/`127` | Defaults |
| `RGB_MATRIX_HUE_STEP` / `_SAT_STEP` / `_VAL_STEP` / `_SPD_STEP` | `8`/`16`/`16`/`16` | Adjustment steps |
| `RGB_MATRIX_DEFAULT_FLAGS` | `LED_FLAG_ALL` | Default flag filter |
| `RGB_MATRIX_SPLIT` | *undef* | `{ left, right }` LEDs per half (split) |
| `RGB_TRIGGER_ON_KEYDOWN` | *undef* | Fire reactive on keydown (more responsive; may break on some boards) |
| `RGB_MATRIX_FLAG_STEPS` | `{ALL, KEYLIGHT\|MODIFIER, UNDERGLOW, NONE}` | Flag cycle for `RM_FLGN` |
| `RGB_MATRIX_CENTER` | `{112,32}` | Override keyboard center for position-based effects |
| `RGB_MATRIX_DISABLE_SHARED_KEYCODES` | *undef* | Stop `UG_*`/`RGB_M_*` from also driving RGB_MATRIX |

### Split configuration
- `RGB_MATRIX_SPLIT { X, Y }` — LED count per half (X=left, Y=right).
- Reactive effects on split → also enable `SPLIT_TRANSPORT_MIRROR`.
- Indicators reading layer/host state → `SPLIT_LAYER_STATE_ENABLE` / `SPLIT_LED_STATE_ENABLE` (see `10-connectivity.md`).

### Suspend behavior
`RGB_MATRIX_SLEEP` turns effects off when the keyboard suspends; query state with `bool rgb_matrix_get_suspend_state(void)`.

### EEPROM persistence
RGB Matrix persists (enabled, mode, hue, sat, val, speed) to EEPROM. **The EEPROM region is shared with LED Matrix** — QMK assumes only one of the two is used at a time. `rgb_matrix_reload_from_eeprom()` re-reads saved config. Most setters have `_noeeprom` variants to bypass writes (use inside indicators/callbacks). See `03-config-and-info-json.md` for the EEPROM layout.

### Indicators (per-key callbacks)
| Signature | Level | Purpose |
|---|---|---|
| `bool rgb_matrix_indicators_user(void)` | keymap | Simple per-key indicators. Return `true` to let `_kb` run. |
| `bool rgb_matrix_indicators_kb(void)` | keyboard | Calls user; default impl returns its result. Return currently unused. |
| `bool rgb_matrix_indicators_advanced_user(uint8_t led_min, uint8_t led_max)` | keymap | Bounded variant for heavy layouts — only iterate `[led_min, led_max)`. Return `true` to continue `_kb`. |
| `bool rgb_matrix_indicators_advanced_kb(uint8_t led_min, uint8_t led_max)` | keyboard | Bounded, keyboard-level. |

- Helpers: `rgb_matrix_set_color(index, r, g, b)`, `rgb_matrix_set_color_all(r,g,b)`, macro `RGB_MATRIX_INDICATOR_SET_COLOR(i, r, g, b)` (bounds-checked).
- **Critically:** `rgb_matrix_set_color*` only works **inside an effect or indicator callback** — the running animation overwrites it on the next frame otherwise.
- **Ordering:** indicators run **after** the current animation frame is rendered, **before** it's flushed to the LEDs.
- Caps Lock on all keylight-flagged keys; layer indicator examples; host-LED indicator examples all in source. Use `g_led_config.flags[i]` + `HAS_FLAGS`/`HAS_ANY_FLAGS` to target LED classes.
- **Indicators-only without an effect:** you can't truly disable the effect engine (toggling RGB off kills everything). Workaround: `rgb_matrix_mode_noeeprom(RGB_MATRIX_SOLID_COLOR); rgb_matrix_sethsv_noeeprom(HSV_OFF);` then paint in indicators.

### C API (parallel to LED_MATRIX — most have `_noeeprom`)
On/off: `rgb_matrix_toggle/enable/disable` (+`_noeeprom`), `rgb_matrix_is_enabled()`. Per-LED: `rgb_matrix_set_color(i,r,g,b)`, `rgb_matrix_set_color_all(r,g,b)`. Mode: `rgb_matrix_mode/step/step_reverse` (+`_noeeprom`), `rgb_matrix_get_mode()`. HSV: `rgb_matrix_increase/decrease_hue/sat/val` (+`_noeeprom`), `rgb_matrix_sethsv(h,s,v)`/`_noeeprom`, `rgb_matrix_get_hue/sat/val()`, `rgb_matrix_get_hsv()` (returns `hsv_t`). Speed: `rgb_matrix_increase/decrease_speed` (+`_noeeprom`), `rgb_matrix_set_speed(x)`/`_noeeprom` (0–255), `rgb_matrix_get_speed()`. Flags: `rgb_matrix_set_flags(flags)`/`_noeeprom`, `rgb_matrix_flags_step/_reverse` (+`_noeeprom`), `rgb_matrix_get_flags()`. Misc: `rgb_matrix_reload_from_eeprom()`, `rgb_matrix_get_suspend_state()`, `rgb_matrix_get_mode_name()` (needs `RGB_MATRIX_MODE_NAME_ENABLE`).

### Colors
Same `RGB_*`/`HSV_*` table as RGBLIGHT (`quantum/color.h`).

### Gotchas — RGB_MATRIX
- **`RGB_MATRIX_MAXIMUM_BRIGHTNESS` default is 200**, but LED_MATRIX's is 255 — easy to miss if migrating configs.
- **`rgb_matrix_set_color` outside a callback is a no-op** (animation overwrites next frame).
- **Shared keycodes with RGBLIGHT** (`UG_*`/`RGB_M_*`) silently drive both unless `RGB_MATRIX_DISABLE_SHARED_KEYCODES` is set.
- **EEPROM shared with LED_MATRIX** — don't enable both.
- Reactive on split needs `SPLIT_TRANSPORT_MIRROR`; indicators reading host/layer state need the matching `SPLIT_*_ENABLE`.
- `g_led_config` position range is `{0..224, 0..64}` — effects compute center from this; wrong ranges break centered animations.
- `RGB_TRIGGER_ON_KEYDOWN` improves responsiveness but "may cause RGB to not function properly on some boards."
- Indicators-only mode requires the SOLID_COLOR+HSV_OFF hack; there's no clean "effects off, indicators on."
- Custom effects file must **not** have `#pragma once`.

---

## 5. LED_MATRIX (monochrome per-key)

### Summary
Monochrome twin of RGB_MATRIX: per-key single-color LEDs driven by the same driver-IC family, with the same `g_led_config` physical map and the same architecture — but only **value (brightness)**, no hue/sat. Hooks into the **backlight** keycode system per the source note ("you can use the same keycodes as backlighting"), though it defines its own `LM_*` keycodes.

### Enable it
**rules.mk** (driver auto-enables):
```make
LED_MATRIX_DRIVER = is31fl3733   # any is31fl*/snled27351 driver
```
Silicon config → `13-drivers-lowlevel.md`.

### Supported drivers & max LEDs
| Driver | Max | Driver | Max |
|---|---|---|---|
| IS31FL3218 | 18 | IS31FL3737 | 144 |
| IS31FL3236 | 36 | IS31FL3741 | 351 |
| IS31FL3729 | 135 | IS31FL3742A | 180 |
| IS31FL3731 | 144 | IS31FL3743A | 198 |
| IS31FL3733 | 192 | IS31FL3745 | 144 |
| IS31FL3736 | 96 | IS31FL3746A | 72 |
| SNLED27351 | 192 | | |

> These max-LED numbers (full matrix capacity) differ from the RGB_MATRIX table (per-board subset). Verify against `13-drivers-lowlevel.md`.

### `g_led_config`, position formula, center
Identical structure to RGB_MATRIX (`led_config_t`, `{0..224, 0..64}`, center `{112,32}`, `LED_MATRIX_CENTER`, `g_led_config.matrix_co`). See RGB_MATRIX section.

### LED Flags — **no `LED_FLAG_UNDERGLOW`**
| Define | Value |
|---|---|
| `LED_FLAG_NONE` | `0x00` |
| `LED_FLAG_ALL` | `0xFF` |
| `LED_FLAG_MODIFIER` | `0x01` |
| `LED_FLAG_KEYLIGHT` | `0x04` |
| `LED_FLAG_INDICATOR` | `0x08` |
| `HAS_FLAGS` / `HAS_ANY_FLAGS` | — |

### Keycodes
| Key | Alias | Description |
|---|---|---|
| `QK_LED_MATRIX_ON` / `OFF` | `LM_ON` / `LM_OFF` | On / off |
| `QK_LED_MATRIX_TOGGLE` | `LM_TOGG` | Toggle |
| `QK_LED_MATRIX_MODE_NEXT` / `_PREVIOUS` | `LM_NEXT` / `LM_PREV` | Cycle effects |
| `QK_LED_MATRIX_BRIGHTNESS_UP` / `_DOWN` | `LM_BRIU` / `LM_BRID` | Brightness (no hue/sat) |
| `QK_LED_MATRIX_SPEED_UP` / `_DOWN` | `LM_SPDU` / `LM_SPDD` | Speed |
| `QK_LED_MATRIX_FLAG_NEXT` / `_PREVIOUS` | `LM_FLGN` / `LM_FLGP` | Cycle flags |

### Effects (enum `led_matrix_effects`) — enable via `ENABLE_LED_MATRIX_<NAME>`
`NONE=0`, `SOLID=1` (no speed), `ALPHAS_MODS`, `BREATHING`, `BAND`, `BAND_PINWHEEL`, `BAND_SPIRAL`, `CYCLE_LEFT_RIGHT`, `CYCLE_UP_DOWN`, `CYCLE_OUT_IN`, `DUAL_BEACON`, reactive set (`SOLID_REACTIVE_SIMPLE/WIDE/MULTIWIDE/CROSS/MULTICROSS/NEXUS/MULTINEXUS`, `SOLID_SPLASH`, `SOLID_MULTISPLASH`), `WAVE_LEFT_RIGHT`, `WAVE_UP_DOWN`. No framebuffer/pixel/starlight/riverflow equivalents.

### Custom effects
`LED_MATRIX_CUSTOM_USER = yes` / `LED_MATRIX_CUSTOM_KB = yes`; create `led_matrix_user.inc` / `led_matrix_kb.inc` (no `#pragma once`). Pattern mirrors RGB_MATRIX: `LED_MATRIX_EFFECT(name)`, implement under `#ifdef LED_MATRIX_CUSTOM_EFFECT_IMPLS`, use `LED_MATRIX_USE_LIMITS(led_min, led_max)`, `led_matrix_set_value(i, v)`, `led_matrix_check_finished_leds(led_max)`. Switch via `led_matrix_mode(LED_MATRIX_CUSTOM_my_effect)`.

### config.h options
| Define | Default | Meaning |
|---|---|---|
| `LED_MATRIX_MODE_NAME_ENABLE` | *undef* | Enable `led_matrix_get_mode_name()` |
| `LED_MATRIX_KEYRELEASES` | *undef* | Reactive on release not press |
| `LED_MATRIX_TIMEOUT` | `0` | ms inactivity → off |
| `LED_MATRIX_SLEEP` | *undef* | Off when suspended |
| `LED_MATRIX_LED_PROCESS_LIMIT` | `(LED_COUNT+4)/5` | LEDs per task run |
| `LED_MATRIX_LED_FLUSH_LIMIT` | `16` | ms between flushes |
| `LED_MATRIX_MAXIMUM_BRIGHTNESS` | **`255`** | Max brightness (**differs from RGB_MATRIX's 200**) |
| `LED_MATRIX_DEFAULT_ON` | `true` | On after EEPROM clear |
| `LED_MATRIX_DEFAULT_MODE` | `LED_MATRIX_SOLID` | Default effect |
| `LED_MATRIX_DEFAULT_VAL` | `LED_MATRIX_MAXIMUM_BRIGHTNESS` | Default brightness |
| `LED_MATRIX_DEFAULT_SPD` | `127` | Default speed |
| `LED_MATRIX_VAL_STEP` | `8` | Brightness adjustment step |
| `LED_MATRIX_SPD_STEP` | `16` | Speed adjustment step |
| `LED_MATRIX_DEFAULT_FLAGS` | `LED_FLAG_ALL` | Default flag filter |
| `LED_MATRIX_SPLIT` | *undef* | `{ left, right }` per half (split) |
| `LED_MATRIX_FLAG_STEPS` | `{ALL, KEYLIGHT\|MODIFIER, NONE}` | Flag cycle |

### EEPROM
**Shared with RGB_MATRIX** — only one expected at a time. `led_matrix_reload_from_eeprom()`.

### Indicators
| Signature | Level |
|---|---|
| `bool led_matrix_indicators_user(void)` | keymap — return `true` to let `_kb` run |
| `bool led_matrix_indicators_kb(void)` | keyboard |
| `bool led_matrix_indicators_advanced_user(uint8_t led_min, uint8_t led_max)` | keymap, bounded |
| `bool led_matrix_indicators_advanced_kb(uint8_t led_min, uint8_t led_max)` | keyboard, bounded |

Helpers: `led_matrix_set_value(index, v)`, `led_matrix_set_value_all(v)`, macro `LED_MATRIX_INDICATOR_SET_VALUE(i, v)`. Same "only inside callback" rule as RGB_MATRIX.

### C API
On/off: `led_matrix_toggle/enable/disable` (+`_noeeprom`), `led_matrix_is_enabled()`. Per-LED: `led_matrix_set_value(i,v)`, `led_matrix_set_value_all(v)`. Mode: `led_matrix_mode/step/step_reverse` (+`_noeeprom`), `led_matrix_get_mode()`. Brightness: `led_matrix_increase/decrease_val` (+`_noeeprom`) — **note source typo `val_matrix_increase_val` in one heading; the real symbol is `led_matrix_increase_val`** — `led_matrix_get_val()`. Speed: `led_matrix_increase/decrease_speed` (+`_noeeprom`), `led_matrix_set_speed(x)`/`_noeeprom`, `led_matrix_get_speed()`. Flags: `led_matrix_set_flags`/`_noeeprom`, `led_matrix_flags_step/_reverse` (+`_noeeprom`), `led_matrix_get_flags()`. Misc: `led_matrix_reload_from_eeprom()`, `led_matrix_get_suspend_state()`, `led_matrix_get_mode_name()` (needs `LED_MATRIX_MODE_NAME_ENABLE`).

### Gotchas — LED_MATRIX
- **No `LED_FLAG_UNDERGLOW`** (monochrome boards don't have underglow). Flag-cycle default omits it.
- **`LED_MATRIX_MAXIMUM_BRIGHTNESS` default is 255**, vs RGB_MATRIX's 200.
- **EEPROM shared with RGB_MATRIX** — enabling both corrupts/clobbers saved state.
- Source doc has a typo: `val_matrix_increase_val` heading; correct symbol `led_matrix_increase_val`.
- Source says it "hooks into the backlight system" for keycodes, but defines distinct `LM_*` keycodes — prefer `LM_*`.
- Reactive on split needs `SPLIT_TRANSPORT_MIRROR`.

---

## Cross-cutting notes

- **EEPROM model:** RGBLIGHT, RGB_MATRIX, and LED_MATRIX each persist their config; RGB_MATRIX and LED_MATRIX **share one region**. Backlight persists only on/off + level + breathing. `_noeeprom` variants exist on RGBLIGHT/RGB_MATRIX/LED_MATRIX (not backlight) to avoid EEPROM writes inside callbacks. See `03-config-and-info-json.md`.
- **Split sync (`10-connectivity.md`):** every lighting feature that shows host/layer/indicator state on the slave needs the matching `SPLIT_*_ENABLE` (`SPLIT_LED_STATE_ENABLE` for indicators, `SPLIT_LAYER_STATE_ENABLE` for layer-based indicators/lighting layers, `RGBLIGHT_SPLIT`+`RGBLED_SPLIT` for underglow, `RGB_MATRIX_SPLIT`/`LED_MATRIX_SPLIT` for matrices, `SPLIT_TRANSPORT_MIRROR` for reactive effects on split matrices).
- **Process chain:** lighting keycodes flow through `process_record` (see `01-architecture.md`); RGBLIGHT/RGB_MATRIX/LED_MATRIX/breathing keycodes are **not USB HID** — don't `tap_code16()` them; call the corresponding `*_noeeprom`/setter functions from your own handlers.
- **info.json / data-driven (`03-config-and-info-json.md`):** RGB matrix layouts and `g_led_config` can be generated from info.json `rgb_matrix`/`led_matrix` blocks; feature flags live under `features`. Driver/pin selection is still largely `rules.mk`+`config.h`.
- **Driver silicon (`13-drivers-lowlevel.md`):** all is31fl*/snled27351/aw20216s config (I²C addr, `*_LED_COUNT`, current, scaling) and ws2812/apa102 transport (PWM/SPI/bitbang) live there — this file only covers the feature layer above the driver.
