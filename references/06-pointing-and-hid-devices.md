# 06 — Pointing Devices & HID Device Emulation

This reference covers features that make the keyboard present itself as **another HID device class** besides a keyboard: a **mouse** (`mouse_keys`, `pointing_device`, `ps2_mouse`), a **joystick/gamepad** (`joystick`), a **digitizer/touch/stylus** (`digitizer`), and a **Consumer/Telephony programmable-button** device (`programmable_button`). Together these let a QMK board drive a cursor, scroll, move a gamepad, emulate absolute pen input, and emit OS-transparent macro buttons.

> **Three things bite people in this cluster, in order of frequency:**
> 1. **USB endpoint budget** — each HID class here can consume an endpoint. `mouse_keys` + `pointing_device` share the **mouse** endpoint; `joystick`, `digitizer`, and `programmable_button` each add their own. On AVR you will hit `ENDPOINT_TOTAL` build errors before you run out of flash. See **`03-config-and-info-json.md` §4.4 (USB endpoint budget)**.
> 2. **The shared `report_mouse_t`** — `mouse_keys`, `pointing_device`, and `ps2_mouse` **all write the same mouse report and the same button bits**. They cooperate, but that also means a button pressed by `mouse_keys` is visible in `pointing_device_task_user`, and vice versa.
> 3. **Sign range / HID spec** — `report_mouse_t.x/y/h/v` are **-127…+127** (8-bit) by default, **not** -128. Extended reports (`MOUSE_EXTENDED_REPORT`/`WHEEL_EXTENDED_REPORT`) widen to int16 **-32767…+32767** but cost a larger descriptor.

### Where this sits in the firmware loop (cross-refs)

- **`process_record` chain:** `process_joystick(keycode, record)` and `process_programmable_button(keycode, record)` run **late** in `process_record_quantum`, after `process_record_user` and after most feature modules (leader/auto_shift/magic/grave_esc/rgb). See **`01-architecture.md` §7.2**. Mouse-key keycodes (`MS_*`) are handled inside the quantum keycode dispatcher in the same late phase. If your `process_record_user` returns `false` on a `JS_*`/`PB_*`/`MS_*` keycode, the feature never sees it.
- **Main loop / scan:** the `pointing_device` driver is **polled** every scan (throttled by `POINTING_DEVICE_TASK_THROTTLE_MS`), not on a key event. This is the same scan loop described in **`01-architecture.md`** — heavy work in the driver's `get_report` directly raises key latency. Prefer `housekeeping_task_*` for unrelated heavy work (see **`01-architecture.md` §9.2**).
- **Split / wireless pointers** are covered in **`10-connectivity.md`** (split data sync, `SPLIT_POINTING_ENABLE`, transport). Sensor/driver bus specifics (SPI/I2C/ADC/serial) are in **`13-drivers-lowlevel.md`**.
- **`info.json` / config schema:** see **`03-config-and-info-json.md`**. Most options below are still `config.h` `#define`s; `rules.mk` features (`*_ENABLE = yes`) and `info.json` `features`/`ps2` blocks are noted where they exist.

---

## 1. Mouse Keys (`MOUSEKEY_ENABLE`)

### Summary
Emulates a mouse **using the keyboard matrix** — no hardware sensor needed. Move the pointer, scroll in 8 directions, and click up to 8 buttons. Five selectable acceleration models. This is the simplest way to get cursor control; it coexists with `pointing_device` and `ps2_mouse` because all three share `report_mouse_t`.

### Enable it
```make
# rules.mk
MOUSEKEY_ENABLE = yes
```
This is a `rules.mk` toggle. The mouse HID interface is enabled/disabled at the **USB descriptor** level via `usb.shared_endpoint.mouse` in `info.json` (default `true`, sharing one endpoint with extrakey/nkro). See **`03-config-and-info-json.md` §5.7**.

### Keycodes
| Keycode | Alias | Description |
|---|---|---|
| `QK_MOUSE_CURSOR_UP` | `MS_UP` | Move cursor up |
| `QK_MOUSE_CURSOR_DOWN` | `MS_DOWN` | Move cursor down |
| `QK_MOUSE_CURSOR_LEFT` | `MS_LEFT` | Move cursor left |
| `QK_MOUSE_CURSOR_RIGHT` | `MS_RGHT` | Move cursor right |
| `QK_MOUSE_BUTTON_1` … `_8` | `MS_BTN1` … `MS_BTN8` | Mouse buttons 1–8 |
| `QK_MOUSE_WHEEL_UP` | `MS_WHLU` | Wheel up |
| `QK_MOUSE_WHEEL_DOWN` | `MS_WHLD` | Wheel down |
| `QK_MOUSE_WHEEL_LEFT` | `MS_WHLL` | Wheel left |
| `QK_MOUSE_WHEEL_RIGHT` | `MS_WHLR` | Wheel right |
| `QK_MOUSE_ACCELERATION_0` | `MS_ACL0` | Set acceleration/speed tier 0 (slowest) |
| `QK_MOUSE_ACCELERATION_1` | `MS_ACL1` | Set acceleration/speed tier 1 |
| `QK_MOUSE_ACCELERATION_2` | `MS_ACL2` | Set acceleration/speed tier 2 (max) |

### Acceleration models (config.h `#define`s)

Mouse keys has **five** cursor-motion models, selected by defines. Times are in **ms**; scroll speed is in multiples of the OS's default scroll step.

**Accelerated (default).** Same algorithm as X11 MouseKeysAccel. Keys held accelerate until `MAX_SPEED`.
| Define | Default | Meaning |
|---|---|---|
| `MOUSEKEY_DELAY` | `10` | Delay between pressing a move key and first cursor move (ms) |
| `MOUSEKEY_INTERVAL` | `20` | Time between cursor moves (ms); lower = smoother/faster |
| `MOUSEKEY_MOVE_DELTA` | `8` | Step size (px) |
| `MOUSEKEY_MAX_SPEED` | `10` | Max cursor speed where acceleration stops |
| `MOUSEKEY_TIME_TO_MAX` | `30` | Time until max speed reached; **`0` disables accel** (constant) |
| `MOUSEKEY_WHEEL_DELAY` | `10` | Delay before first wheel move (ms) |
| `MOUSEKEY_WHEEL_INTERVAL` | `80` | Time between wheel moves (ms) |
| `MOUSEKEY_WHEEL_DELTA` | `1` | Wheel step size |
| `MOUSEKEY_WHEEL_MAX_SPEED` | `8` | Max scroll steps per action |
| `MOUSEKEY_WHEEL_TIME_TO_MAX` | `40` | Time until max scroll speed; **`0` disables scroll accel** |

`MS_ACL0/1/2` (in accelerated mode) set speed to ¼ / ½ / max respectively.

**Kinetic mode** — `#define MK_KINETIC_SPEED`. Quadratic speed curve: precise at start, fast over distance.
| Define | Default | Meaning |
|---|---|---|
| `MOUSEKEY_DELAY` | `5` | Delay before first move (ms) |
| `MOUSEKEY_INTERVAL` | `10` | Time between moves (ms); shorter = smoother |
| `MOUSEKEY_MOVE_DELTA` | `16` | Step size accelerating initial→base speed |
| `MOUSEKEY_INITIAL_SPEED` | `100` | Initial cursor speed (px/s) |
| `MOUSEKEY_BASE_SPEED` | `5000` | Max cursor speed (px/s) |
| `MOUSEKEY_DECELERATED_SPEED` | `400` | Decelerated cursor speed (px/s) |
| `MOUSEKEY_ACCELERATED_SPEED` | `3000` | Accelerated cursor speed (px/s) |
| `MOUSEKEY_WHEEL_INITIAL_MOVEMENTS` | `16` | Initial wheel movements |
| `MOUSEKEY_WHEEL_BASE_MOVEMENTS` | `32` | Max wheel movements where accel stops |
| `MOUSEKEY_WHEEL_ACCELERATED_MOVEMENTS` | `48` | Accelerated wheel movements |
| `MOUSEKEY_WHEEL_DECELERATED_MOVEMENTS` | `8` | Decelerated wheel movements |

Wheel always operates at step size 1; you tune *movements per second*, not pixels.

**Constant mode** — `#define MK_3_SPEED` (add `#define MK_MOMENTARY_ACCEL` for momentary vs tap-to-select). No acceleration; `MS_ACL0/1/2` pick from 3 fixed speeds.
| Define | Default | Meaning |
|---|---|---|
| `MK_3_SPEED` | *undef* | Enable constant cursor speeds |
| `MK_MOMENTARY_ACCEL` | *undef* | Speed tier active only while held (else tap-to-select) |
| `MK_C_OFFSET_UNMOD` / `MK_C_INTERVAL_UNMOD` | `16` / `16` | Unmodified cursor offset / interval |
| `MK_C_OFFSET_0` / `MK_C_INTERVAL_0` | `1` / `32` | `MS_ACL0` cursor offset / interval |
| `MK_C_OFFSET_1` / `MK_C_INTERVAL_1` | `4` / `16` | `MS_ACL1` cursor offset / interval |
| `MK_C_OFFSET_2` / `MK_C_INTERVAL_2` | `32` / `16` | `MS_ACL2` cursor offset / interval |
| `MK_W_OFFSET_UNMOD` / `MK_W_INTERVAL_UNMOD` | `1` / `40` | Unmodified scroll steps / interval |
| `MK_W_OFFSET_0` / `MK_W_INTERVAL_0` | `1` / `360` | `MS_ACL0` scroll |
| `MK_W_OFFSET_1` / `MK_W_INTERVAL_1` | `1` / `120` | `MS_ACL1` scroll |
| `MK_W_OFFSET_2` / `MK_W_INTERVAL_2` | `1` / `20` | `MS_ACL2` scroll |

**Combined mode** — `#define MK_COMBINED`. Accelerated normally; holding `MS_ACL0/1/2` momentarily forces slowest / half-max / max constant speed. Uses the Accelerated-mode settings otherwise.

**Inertia mode** — `#define MOUSEKEY_INERTIA`. Cursor accelerates on a quadratic curve while held and **glides to a stop** after release (ice-like); X/Y tracked independently for curves. Applies to **cursor only, not wheel**. Mutually exclusive with Kinetic/Constant/Combined.
| Define | Default | Meaning |
|---|---|---|
| `MOUSEKEY_DELAY` | `150` | Delay before first move (ms) — match host key-repeat delay (100–300) |
| `MOUSEKEY_INTERVAL` | `16` | ms between moves (16 = 60fps; `1000/FPS`) |
| `MOUSEKEY_MAX_SPEED` | `32` | Max px/frame (~screen_width / FPS) |
| `MOUSEKEY_TIME_TO_MAX` | `32` | Frames to reach max speed (~FPS/2) |
| `MOUSEKEY_FRICTION` | `24` | How fast cursor stops after release (1–255; 8–40 typical) |
| `MOUSEKEY_MOVE_DELTA` | `1` | First-frame move (keep at 1) |

### Overlapping mouse key control
| Define | Default | Meaning |
|---|---|---|
| `MOUSEKEY_OVERLAP_RESET` | *undef* | Reset acceleration when a new overlapping key is pressed |
| `MOUSEKEY_OVERLAP_MOVE_DELTA` | `MOUSEKEY_MOVE_DELTA` | Step size of reset move accel |
| `MOUSEKEY_OVERLAP_WHEEL_DELTA` | `MOUSEKEY_WHEEL_DELTA` | Step size of reset wheel accel |
| `MOUSEKEY_OVERLAP_INTERVAL` | `MOUSEKEY_INTERVAL` | Reset interval (Kinetic only) |

Does **not** apply in Inertia mode.

### C API
Mouse keys has no user-facing C callbacks of its own (it's driven entirely by keycodes). It cooperates with `pointing_device` by writing button bits into the shared `report_mouse_t.buttons` — so `MOUSE_BTN1`…`MOUSE_BTN8` masks (defined in `report.h`) are reusable when you set buttons manually via `pointing_device_set_report()` (see §2).

### Behavior & ordering
- Mouse-key keycodes are dispatched in the **late quantum keycode** phase (after `process_record_user`). Returning `false` in `process_record_user` for an `MS_*` keycode prevents the move/click.
- **Button bits are shared** with `pointing_device` and `ps2_mouse`, so mouse-key clicks can be used for click-and-drag while a sensor moves the pointer (and vice versa).
- Movement deltas are written to `report_mouse_t.x/y`; wheel to `h/v`. After send, the motion fields are zeroed but **buttons persist** (see §2 report flow).

### Example
```c
// keymap.c — a mouse layer
[_MOUSE] = LAYOUT(
    MS_BTN1, MS_UP,    MS_BTN2,
    MS_LEFT, MS_DOWN,  MS_RGHT,
             MS_WHLU
),
```

### Gotchas
- **Endpoint cost:** enabling `MOUSEKEY_ENABLE` adds the mouse HID interface. By default it shares an endpoint with extrakey/nkro; if you've forced `MOUSE_SHARED_EP = no` (or `usb.shared_endpoint.mouse = false`) you consume an extra endpoint. On small AVRs you can run out (`ENDPOINT_TOTAL` error). See **`03-config-and-info-json.md` §4.4**.
- **`-127…+127`, not -128.** Mouse delta fields are 8-bit signed by HID spec; max magnitude per report is 127.
- **`MOUSEKEY_DELAY` too low → unresponsive; too high → small moves hard.** `MOUSEKEY_INTERVAL` too low → too fast.
- Setting `MOUSEKEY_TIME_TO_MAX` or `MOUSEKEY_WHEEL_TIME_TO_MAX` to `0` **disables** acceleration for that axis (a way to mix constant + accelerated in one mode).
- Inertia mode ignores wheel options (wheel uses accelerated-mode defaults) and ignores `MOUSEKEY_OVERLAP_RESET`.
- Kinetic/Constant/Combined/Inertia are **mutually exclusive** modes — define exactly one.
- The `MOUSE_BTN1..8` masks live in `report.h`, not a mouse_keys header.

---

## 2. Pointing Device (`POINTING_DEVICE_ENABLE`)

### Summary
The **hardware-sensor-driven** mouse feature. Polls a physical sensor (optical mouse sensor, trackpad, trackball, analog joystick) each scan and feeds its motion into `report_mouse_t`. Designed to be the central plumbing for any pointer: you (or a driver) produce a `report_mouse_t` and QMK handles rotation, inversion, gestures, split sync, and USB send. Mouse keys and PS/2 mouse both coexist by sharing this same report.

### Enable it
```make
# rules.mk
POINTING_DEVICE_ENABLE = yes
POINTING_DEVICE_DRIVER = <driver>   # one driver at a time (see below)
```
`POINTING_DEVICE_DRIVER` is **required** — pick one. To drive more than one sensor, use `custom` and merge reports yourself.

### Sensor drivers (`POINTING_DEVICE_DRIVER =`)
Only **one** driver compiles per build. Defaults shown are CPI / pin defaults.

| Driver value | Device | Bus | CPI range / default | Notes |
|---|---|---|---|---|
| `adns5050` | ADNS-5050 optical | serial (SCLK/SDIO) + extra light | 125–1375 step 125, default 500 | pins: `ADNS5050_SCLK/SDIO/CS_PIN` (→ `POINTING_DEVICE_*_PIN`) |
| `adns9800` | ADNS-9800 laser | SPI | 800–8200 step 200, default 1800 | `ADNS9800_CLOCK_SPEED` `2000000`, `SPI_MODE` `3`, `SPI_DIVISOR` varies |
| `analog_joystick` | Analog thumbstick | ADC | n/a | `ANALOG_JOYSTICK_X/Y_AXIS_PIN` (required); see ADC driver **`13-drivers-lowlevel.md`** |
| `azoteq_iqs5xx` | Azoteq IQS525/550/572 trackpad (TPS43/TPS65) | I2C addr `0xE8` | per device | profiles `AZOTEQ_IQS5XX_TPS43`/`_TPS65`; rich gesture config |
| `cirque_pinnacle_i2c` / `cirque_pinnacle_spi` | Cirque Pinnacle 1CA027 (TM040040/035035/023023) | I2C `0x2A` / SPI | scaling 1024, CPI from diameter | absolute & relative modes; throttle defaults to 10ms |
| `paw3204` | PAW-3204 optical | serial + light | 400–1600 (set values), default 1000 | `PAW3204_SCLK/SDIO_PIN` |
| `paw3222` | PAW-3222 | SPI | up to 4000, default 1000 | `PAW3222_CS_PIN`, `PAW3222_SPI_DIVISOR` (required) |
| `pimoroni_trackball` | Pimoroni Trackball | I2C `0x0A` | n/a | RGB trackball; `SCALE` `5`, debounce `20` |
| `pmw3320` | PMW-3320 optical | serial + light | 500–3500 step 250, default 1000 | `PMW3320_SCLK/SDIO/CS_PIN` |
| `pmw3325` | PMW-3325 | SPI | 100–5000 step 100, default 2000 | `PMW3325_CS_PIN`, `PMW3325_SPI_DIVISOR` |
| `pmw3360` | PMW-3360 IR | SPI | 100–12000 step 100, default 1600 | supports **multiple sensors per controller** |
| `pmw3389` | PMW-3389 IR | SPI | 50–16000 step 50, default 2000 | supports multiple sensors per controller |
| `custom` | your own | — | — | implement the 5 `pointing_device_driver_*` functions |

**Shared default pins** (each sensor falls back to these): `POINTING_DEVICE_CS_PIN`, `POINTING_DEVICE_SDIO_PIN`, `POINTING_DEVICE_SCLK_PIN`.

**Multi-sensor PMW33xx (split):** set `PMW33XX_CS_PINS { B5, B6 }` instead of `PMW33XX_CS_PIN`; for per-half wiring add `PMW33XX_CS_PIN_RIGHT` / `PMW33XX_CS_PINS_RIGHT` (default to the left values). Per-sensor CPI/liftoff/rotation/X-Y flip is **not** supported — you merge reads in `pointing_device_task_kb`. Example:

```c
// keyboard.c
#ifdef POINTING_DEVICE_ENABLE
void pointing_device_init_kb(void) {
    pmw33xx_init(1);            // 2nd device
    pmw33xx_set_cpi(0, 800);
    pmw33xx_set_cpi(1, 800);
    pointing_device_init_user();
}
report_mouse_t pointing_device_task_kb(report_mouse_t mouse_report) {
    pmw33xx_report_t report = pmw33xx_read_burst(1);
    if (!report.motion.b.is_lifted && report.motion.b.is_motion) {
        // constrain to HID -127..127 (from quantum/pointing_device_drivers.c)
        #define constrain_hid(amt) ((amt) < -127 ? -127 : ((amt) > 127 ? 127 : (amt)))
        mouse_report.x = constrain_hid(mouse_report.x + report.delta_x);
        mouse_report.y = constrain_hid(mouse_report.y + report.delta_y);
    }
    return pointing_device_task_user(mouse_report);
}
#endif
```

**Custom driver contract** (`POINTING_DEVICE_DRIVER = custom`):
```c
bool           pointing_device_driver_init(void);
report_mouse_t pointing_device_driver_get_report(report_mouse_t mouse_report);
uint16_t       pointing_device_driver_get_cpi(void);
void           pointing_device_driver_set_cpi(uint16_t cpi);
```
New sensor hardware ideally belongs in `drivers/sensors/` + `quantum/pointing_device_drivers.c`; `custom` is the escape hatch. See **`13-drivers-lowlevel.md`** for the SPI/I2C/ADC/serial APIs these drivers build on.

### Common configuration (all drivers)
| Define | Default | Meaning |
|---|---|---|
| `MOUSE_EXTENDED_REPORT` | undef | Widen x/y to int16 -32767…32767 (bigger descriptor) |
| `WHEEL_EXTENDED_REPORT` | undef | Widen h/v to int16 -32767…32767 |
| `POINTING_DEVICE_ROTATION_90` / `_180` / `_270` | undef | Rotate X/Y by that many degrees |
| `POINTING_DEVICE_INVERT_X` / `_Y` | undef | Invert X / Y axis |
| `POINTING_DEVICE_MOTION_PIN` | undef | Only read sensor when pin active (skip polling when idle) |
| `POINTING_DEVICE_MOTION_PIN_ACTIVE_LOW` | varies | Motion pin is active-low |
| `POINTING_DEVICE_TASK_THROTTLE_MS` | undef (10 for Cirque, 1 for split) | Min ms between sensor polls |
| `POINTING_DEVICE_GESTURES_CURSOR_GLIDE_ENABLE` | undef | Inertial cursor after flick (kinetic friction) |
| `POINTING_DEVICE_GESTURES_SCROLL_ENABLE` | undef | Enable scroll gesture (device-dependent trigger) |
| `POINTING_DEVICE_CS_PIN` / `_SDIO_PIN` / `_SCLK_PIN` | undef | Shared default pins sensors fall back to |

### High-resolution scrolling
| Define | Default | Meaning |
|---|---|---|
| `POINTING_DEVICE_HIRES_SCROLL_ENABLE` | undef | Add a wheel resolution multiplier to the HID descriptor (smooth scroll for trackballs/high-end encoders) |
| `POINTING_DEVICE_HIRES_SCROLL_MULTIPLIER` | `120` | 1..127; resolution = `1 / (MULT × 10^EXP)` → default `1/120` |
| `POINTING_DEVICE_HIRES_SCROLL_EXPONENT` | `0` | 0..127; `1` gives `1/1200` |

Getter: `uint16_t pointing_device_get_hires_scroll_resolution(void)`.

### Split keyboard (`SPLIT_POINTING_ENABLE` — see **`10-connectivity.md`**)
Pick **one**: `POINTING_DEVICE_LEFT`, `POINTING_DEVICE_RIGHT`, or `POINTING_DEVICE_COMBINED`. The `*_RIGHT` rotation/invert options apply **only** under `POINTING_DEVICE_COMBINED`. Set up handedness (`EE_HANDS` recommended) for correct left/right detection.

| Define | Default | Meaning |
|---|---|---|
| `POINTING_DEVICE_LEFT` / `_RIGHT` / `_COMBINED` | undef | Side(s) with a sensor (pick one) |
| `POINTING_DEVICE_ROTATION_90_RIGHT` / `_180_RIGHT` / `_270_RIGHT` | undef | Rotate right-side data (combined only) |
| `POINTING_DEVICE_INVERT_X_RIGHT` / `_Y_RIGHT` | undef | Invert right-side axes (combined only) |

### Report flow & the shared `report_mouse_t`

`report_mouse_t` fields (default 8-bit signed unless extended):
- **`.x`** — signed, -127…127, +right / -left (extended: int16)
- **`.y`** — signed, -127…127, +up / -down (extended: int16)
- **`.v`** — vertical scroll, -127…127, +up / -down (extended: int16)
- **`.h`** — horizontal scroll, -127…127, +right / -left (extended: int16)
- **`.buttons`** — `uint8_t`, all 8 bits used: bit 0 = button 1 … bit 7 = button 8

**Per-scan pipeline (when no sensor motion):**
```
pointing_device_driver_get_report()          // driver reads sensor → fills report
  → pointing_device_adjust_by_defines()      // apply rotation/invert defines
  → pointing_device_task_kb(report)          // keyboard hook
      → pointing_device_task_user(report)    // YOUR hook (return modified report)
  → has_mouse_report_changed()? → pointing_device_send()
```
`pointing_device_send()`:
- sends the report to the host **only if it changed** (avoids keeping the host awake),
- then **zeros x/y/h/v but keeps `buttons`** — so movement is one-shot, button state persists.

You can override `pointing_device_send()` entirely to change either behavior.

### Callbacks & functions
| Function | Level | Purpose |
|---|---|---|
| `void pointing_device_init_kb(void)` / `_user(void)` | kb / user | Init hook for extra hardware sensors |
| `report_mouse_t pointing_device_task_kb(report_mouse_t)` / `_user(...)` | kb / user | Intercept/modify the report before send; **return** the report |
| `uint8_t pointing_device_handle_buttons(uint8_t buttons, bool pressed, uint8_t button)` | — | Handle hw button presses; returns new buttons byte |
| `uint16_t pointing_device_get_cpi(void)` | — | Current CPI/DPI if supported |
| `void pointing_device_set_cpi(uint16_t)` | — | Set CPI/DPI if supported |
| `report_mouse_t pointing_device_get_report(void)` | — | Current report being sent |
| `void pointing_device_set_report(report_mouse_t)` | — | Override/save the report |
| `void pointing_device_send(void)` | — | Send + zero motion (overridable) |
| `bool has_mouse_report_changed(new, old)` | — | True if reports differ |
| `report_mouse_t pointing_device_adjust_by_defines(report_mouse_t)` | — | Apply rotation/invert defines to a raw report |
| `pointing_device_status_t pointing_device_get_status(void)` | — | `POINTING_DEVICE_STATUS_SUCCESS` is healthy |
| `void pointing_device_set_status(pointing_device_status_t)` | — | Non-success disables reports from the device |

**Split-only (under `POINTING_DEVICE_COMBINED`):** `pointing_device_set_shared_report(r)`, `pointing_device_set_cpi_on_side(bool left, uint16_t cpi)`, `pointing_device_combine_reports(left, right)`, `pointing_device_task_combined_kb/_user(left, right)`, `pointing_device_adjust_by_defines_right(r)`.

### Examples

**Drag-scroll (toggle)** — redirect sensor motion to scroll:
```c
enum { DRAG_SCROLL = SAFE_RANGE };
bool set_scrolling = false;

report_mouse_t pointing_device_task_user(report_mouse_t m) {
    if (set_scrolling) { m.h = m.x; m.v = m.y; m.x = 0; m.y = 0; }
    return m;
}
bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    if (keycode == DRAG_SCROLL && record->event.pressed) set_scrolling = !set_scrolling;
    return true;
}
```

**Custom mouse keycode** (click + scroll 127/127, reverse on release):
```c
case MS_SPECIAL:
    if (record->event.pressed) {
        report_mouse_t r = pointing_device_get_report();
        r.v = 127; r.h = 127; r.buttons |= MOUSE_BTN1;
        pointing_device_set_report(r);
    } else {
        report_mouse_t r = pointing_device_get_report();
        r.v = -127; r.h = -127; r.buttons &= ~MOUSE_BTN1;
        pointing_device_set_report(r);
    }
    pointing_device_send();
    break;
```
(Motion fires once per send because `pointing_device_send` zeros it.)

**Combined pointing devices** (left = scroll-only, right = mouse): requires `POINTING_DEVICE_COMBINED`.
```c
void keyboard_post_init_user(void) {
    pointing_device_set_cpi_on_side(true, 1000);   // left: slow scroll
    pointing_device_set_cpi_on_side(false, 8000);  // right: mousing
}
report_mouse_t pointing_device_task_combined_user(report_mouse_t l, report_mouse_t r) {
    l.h = l.x; l.v = l.y; l.x = 0; l.y = 0;
    return pointing_device_combine_reports(l, r);
}
```

### Automatic Mouse Layer (`POINTING_DEVICE_AUTO_MOUSE_ENABLE`)
Automatically activates a target layer when the pointing device is active (motion, button press) and deactivates it after `AUTO_MOUSE_TIME`. Mouse keys + relevant layer keys are treated as mouse keys; mod/mod-tap/one-shot-mod keys are ignored so typing doesn't trigger it. Requires explicit runtime enable.

```c
// config.h
#define POINTING_DEVICE_AUTO_MOUSE_ENABLE
#define AUTO_MOUSE_DEFAULT_LAYER 1   // optional; else set in code
// keymap.c
void pointing_device_init_user(void) {
    set_auto_mouse_layer(1);   // only if AUTO_MOUSE_DEFAULT_LAYER not set
    set_auto_mouse_enable(true); // ALWAYS REQUIRED — starts disabled
}
```

| Define | Range | Units | Default | Meaning |
|---|---|---|---|---|
| `AUTO_MOUSE_DEFAULT_LAYER` | 0–`LAYER_MAX` | `uint8_t` | `1` | Target layer index |
| `AUTO_MOUSE_TIME` | 250–1000 ideal | ms | `650` | Layer stays active after activation |
| `AUTO_MOUSE_DELAY` | 100–1000 ideal | ms | `TAPPING_TERM` or `200` | Lockout after a non-mouse key |
| `AUTO_MOUSE_DEBOUNCE` | 10–100 ideal | ms | `25` | Delay from activation to next update |
| `AUTO_MOUSE_THRESHOLD` | 0– | units | `10` | Mouse movement required to trigger |

Layer-key handling for the target layer: `MO`/`LM` treated as mouse key; `LT` tapped = non-mouse, held = mouse; `TG`/`TO` pin the layer until re-pressed; `TT` flips between mouse-key and `TG` at `TAPPING_TOGGLE`; `DF`/`OSL` skip (but `OSL` pins if it's the target).

**Callbacks to add custom mouse keys:** `bool is_mouse_record_kb/_user(uint16_t keycode, keyrecord_t *record)` — return `true` to treat a keycode as a mouse key.

**Runtime control functions:** `set_auto_mouse_enable(bool)`, `get_auto_mouse_enable()` (`AUTO_MOUSE_ENABLED`), `set_auto_mouse_layer(uint8_t)`, `get_auto_mouse_layer()` (`AUTO_MOUSE_TARGET_LAYER`), `remove_auto_mouse_layer(state, bool force)`, `auto_mouse_layer_off()`, `auto_mouse_toggle()`, `get_auto_mouse_toggle()`, `set/get_auto_mouse_timeout(uint16_t)`, `set/get_auto_mouse_debounce(...)`, `is_auto_mouse_active()`, `get/set_auto_mouse_key_tracker(int8_t)`.

**Custom activation:** override `bool auto_mouse_activation(report_mouse_t mouse_report)` (default: true if any of x/y/h/v nonzero or any button set; Cirque overrides to also activate on touchdown, master-side only).

> ⚠️ Do **not** call `auto_mouse_trigger_reset` or `auto_mouse_layer_off` inside `layer_state_set_*` — indefinite loops. Use `remove_auto_mouse_layer` there and `auto_mouse_layer_off` elsewhere. Call one of them **before** `set_auto_mouse_enable(false)` or `set_auto_mouse_layer(...)` to avoid a stuck layer.

### Debug
`#define POINTING_DEVICE_DEBUG` in `config.h` prints driver internals to `CONSOLE`. See **`15-flashing-debugging.md`**.

### Gotchas
- **`POINTING_DEVICE_MOTION_PIN` is unsupported with `SPLIT_POINTING_ENABLE`**, and `POINTING_DEVICE_TASK_THROTTLE_MS` defaults to `1` on split (raising it improves transport throughput at the cost of pointer responsiveness). See **`10-connectivity.md`**.
- **Cursor-glide gesture requires continuous polling** — do **not** combine `POINTING_DEVICE_GESTURES_CURSOR_GLIDE_ENABLE` with `POINTING_DEVICE_MOTION_PIN`.
- **Hi-res scroll can overflow the host input buffer** — define `WHEEL_EXTENDED_REPORT` and throttle report rate; many programs jitter when receiving simultaneous v+h wheel input (snap to one axis).
- **Default report range is -127…+127.** Sensor deltas larger than 127 per scan get clamped unless you enable `MOUSE_EXTENDED_REPORT`. The PMW33xx example clamps manually with `constrain_hid`.
- **Only one driver compiles.** Multiple sensors → `custom` + manual merge, or PMW33xx's `CS_PINS` array.
- **`pointing_device_send` zeros motion but keeps buttons** — if you call it yourself expecting movement to repeat, it won't.
- **`pointing_device_send` only sends on change** by default — continuous reports that keep a host awake require overriding it.
- **Endpoint budget:** like mouse_keys, the mouse interface defaults to the shared endpoint; forcing it private costs an endpoint. See **`03-config-and-info-json.md` §4.4**.
- **Auto-mouse starts disabled** — forgetting `set_auto_mouse_enable(true)` is the #1 "it does nothing" bug.
- **`pointing_device_task_auto_mouse(report)` + `process_auto_mouse(keycode, record)` must both be wired in** if you override `pointing_device_task` or `process_record`.

---

## 3. PS/2 Mouse (`PS2_MOUSE_ENABLE`)

### Summary
Drive a real **PS/2 mouse, Trackpoint, or touchpad** wired to GPIO. The keyboard reads the PS/2 device and feeds it into the same `report_mouse_t` pipeline as pointing_device/mouse_keys (shared buttons). Three host-driver implementations (`busywait`/`interrupt`/`usart`) plus an RP2040 PIO (`vendor`) driver trade off ease vs. responsiveness.

### Enable it
```make
# rules.mk
PS2_MOUSE_ENABLE = yes
PS2_ENABLE = yes
PS2_DRIVER = busywait   # or interrupt | usart | vendor
```
Data-driven equivalent in `info.json`:
```json
"ps2": {
    "clock_pin": "GP1",
    "data_pin": "GP0",
    "driver": "vendor",
    "enabled": true,
    "mouse_enabled": true
}
```
`ps2.driver` valid values: `busywait` (default), `interrupt`, `usart`, `vendor`.

### Wiring
A 4.7kΩ pull-up resistor is needed on **both** DATA and CLK lines to +5V:
```
        DATA ----+---- PIN
                 |
                4.7k
                 |
MODULE 5+ ---+--+---- PWR   CONTROLLER
             |
            4.7k
             |
        CLK -+------- PIN
```

### Driver details (pin assignments live in `config.h` under `#ifdef PS2_DRIVER_*`)

**`busywait`** (default, **not recommended** — jerky movement / dropped inputs):
```c
#ifdef PS2_DRIVER_BUSYWAIT
# define PS2_CLOCK_PIN  D1
# define PS2_DATA_PIN   D2
#endif
```

**`interrupt`** (AVR ATmega32u4 — any INT/PCINT pin for clock, any pin for data; example uses D2 clock / D5 data on INT2):
```c
#ifdef PS2_DRIVER_INTERRUPT
#define PS2_CLOCK_PIN  D2
#define PS2_DATA_PIN   D5
#define PS2_INT_INIT()  do { EICRA |= ((1<<ISC21)|(0<<ISC20)); } while (0)
#define PS2_INT_ON()    do { EIMSK |= (1<<INT2); } while (0)
#define PS2_INT_OFF()   do { EIMSK &= ~(1<<INT2); } while (0)
#define PS2_INT_VECT    INT2_vect
#endif
```
ARM (ChibiOS): any two pins (e.g. `A8` clock / `A9` data); requires `#define PAL_USE_CALLBACKS TRUE` in `halconf.h` before `#include_next <halconf.h>`.

**`usart`** (best on ATmega32u4 — **fixed pins**: PD5 clock / PD2 data; if either is taken, fall back to interrupt):
```c
#ifdef PS2_DRIVER_USART
#define PS2_CLOCK_PIN  D5
#define PS2_DATA_PIN   D2
#define PS2_USART_INIT()      do { /* synchronous, odd parity, 1 stop, 8 data, falling-edge sample */ \
    PS2_CLOCK_DDR &= ~(1<<PS2_CLOCK_BIT); PS2_DATA_DDR &= ~(1<<PS2_DATA_BIT); \
    UCSR1C = ((1<<UMSEL10)|(3<<UPM10)|(0<<USBS1)|(3<<UCSZ10)|(0<<UCPOL1)); \
    UCSR1A = 0; UBRR1H = 0; UBRR1L = 0; } while (0)
#define PS2_USART_RX_INT_ON()  do { UCSR1B = ((1<<RXCIE1)|(1<<RXEN1)); } while (0)
#define PS2_USART_RX_POLL_ON() do { UCSR1B = (1<<RXEN1); } while (0)
#define PS2_USART_OFF()        do { UCSR1C = 0; UCSR1B &= ~((1<<RXEN1)|(1<<TXEN1)); } while (0)
#define PS2_USART_RX_READY     (UCSR1A & (1<<RXC1))
#define PS2_USART_RX_DATA      UDR1
#define PS2_USART_ERROR        (UCSR1A & ((1<<FE1)|(1<<DOR1)|(1<<UPE1)))
#define PS2_USART_RX_VECT      USART1_RX_vect
#endif
```

**`vendor`** (RP2040 PIO only): any two GPIOs but **clock GPIO must be directly after data GPIO** (e.g. data GP0, clock GP1). Optionally `#define PS2_PIO_USE_PIO1` to use PIO1 instead of default PIO0. Configure via the `info.json` `ps2` block above.

### PS/2 protocol features (config.h)
| Define | Default | Meaning |
|---|---|---|
| `PS2_MOUSE_USE_REMOTE_MODE` | undef | Remote mode instead of default stream mode |
| `PS2_MOUSE_ENABLE_SCROLLING` | undef | Enable scrollwheel/scroll gesture |
| `PS2_MOUSE_SCROLL_MASK` | `0xFF` | Scroll mask (some mice need `0x0F`) |
| `PS2_MOUSE_USE_2_1_SCALING` | undef | Apply 2:1 movement scaling |
| `PS2_MOUSE_INIT_DELAY` | `1000` | ms to wait after PS/2 host init |

**Fine control (multipliers):**
```c
#define PS2_MOUSE_X_MULTIPLIER 3
#define PS2_MOUSE_Y_MULTIPLIER 3
#define PS2_MOUSE_V_MULTIPLIER 1
```

**Scroll button (Trackpoint scroll):**
```c
#define PS2_MOUSE_SCROLL_BTN_MASK (1<<PS2_MOUSE_BTN_MIDDLE)  // default; 0 disables
#define PS2_MOUSE_SCROLL_BTN_SEND 300   // ms: release-before-this sends click, after scrolls; 0 = never send
#define PS2_MOUSE_SCROLL_DIVISOR_H 2
#define PS2_MOUSE_SCROLL_DIVISOR_V 2
```
Button indices: `PS2_MOUSE_BTN_LEFT 0`, `PS2_MOUSE_BTN_RIGHT 1`, `PS2_MOUSE_BTN_MIDDLE 2` (combine with `|`).

**Invert / rotate:**
```c
#define PS2_MOUSE_INVERT_BUTTONS   // swap left/right
#define PS2_MOUSE_INVERT_X / _Y    // invert movement axes
#define PS2_MOUSE_INVERT_H / _V    // reverse scroll axes
#define PS2_MOUSE_ROTATE 90        // or 180 / 270 (clockwise)
```

**Debug:** `debug_mouse = true` (or bootmagic), or `#define PS2_MOUSE_DEBUG_HID` / `PS2_MOUSE_DEBUG_RAW`.

### C API (from `ps2_mouse.h`)
```c
void ps2_mouse_disable_data_reporting(void);
void ps2_mouse_enable_data_reporting(void);
void ps2_mouse_set_remote_mode(void);
void ps2_mouse_set_stream_mode(void);
void ps2_mouse_set_scaling_2_1(void);
void ps2_mouse_set_scaling_1_1(void);
void ps2_mouse_set_resolution(ps2_mouse_resolution_t resolution);
void ps2_mouse_set_sample_rate(ps2_mouse_sample_rate_t sample_rate);

// Movement hook (define in keymap to filter/accelerate/auto-layer):
void ps2_mouse_moved_user(report_mouse_t *mouse_report);
```

### Behavior & ordering
- PS/2 mouse reads are injected into the **same `report_mouse_t`** as pointing_device and mouse_keys — buttons are shared, so a PS/2 click works with mouse-key drags.
- `ps2_mouse_moved_user` runs **before** the report is sent to the host — ideal for noise filtering, acceleration, or auto-activating a layer.

### Gotchas
- **`busywait` is genuinely bad** — jerky movement and dropped inputs. Prefer `usart` (best) or `interrupt` (better).
- **`usart` on ATmega32u4 has fixed pins** (PD5 clock, PD2 data). If either is unavailable you **must** use `interrupt`.
- **Required pull-ups:** missing the 4.7kΩ resistors on DATA and CLK is the most common "doesn't work" cause.
- **Pin ordering constraint on RP2040 PIO:** clock GPIO must be exactly data+1.
- `ps2_mouse_set_resolution` is **not supported on most touchpads**.
- Shares the mouse endpoint / report with mouse_keys and pointing_device (endpoint budget — **`03-config-and-info-json.md` §4.4**).

---

## 4. Joystick (`JOYSTICK_ENABLE`)

### Summary
Presents the keyboard as a **game controller / joystick** HID device: up to **6 axes** (X, Y, Z, Rx, Ry, Rz), **32 buttons**, and an **8-way hat** switch. Axes are read from ADC pins (analog joystick/potentiometer) or driven virtually from code.

### Enable it
```make
# rules.mk
JOYSTICK_ENABLE = yes
JOYSTICK_DRIVER = analog    # default; or digital
```
When using `analog` on **ARM you must power the stick at 3.3V** — the ADC driver does not support 5V even on boards with a 5V pin (e.g. Helios). See ADC driver in **`13-drivers-lowlevel.md`**.

### Keycodes
| Keycode | Alias | Description |
|---|---|---|
| `QK_JOYSTICK_BUTTON_0` … `_31` | `JS_0` … `JS_31` | Joystick buttons 0–31 |

(32 keycodes total. `JS_*` is the short alias.)

### Configuration (config.h)
```c
#define JOYSTICK_BUTTON_COUNT   16   // min 0, max 32
#define JOYSTICK_AXIS_COUNT     3    // min 0, max 6: X, Y, Z, Rx, Ry, Rz
#define JOYSTICK_AXIS_RESOLUTION 10  // min 8, max 16 bits
```
Defaults: **2 axes, 8 buttons, 8-bit resolution (-127…+127).** ADC max is 10-bit on AVR, 12-bit on most STM32. **You must define at least one button or axis.**

**Hat switch:** `#define JOYSTICK_HAS_HAT` enables the 8-way hat. Set with `joystick_set_hat(value)`; clockwise from north, center = `-1`.

| Define | Value | Angle |
|---|---|---|
| `JOYSTICK_HAT_CENTER` | `-1` | — |
| `JOYSTICK_HAT_NORTH` | `0` | 0° |
| `JOYSTICK_HAT_NORTHEAST` | `1` | 45° |
| `JOYSTICK_HAT_EAST` | `2` | 90° |
| `JOYSTICK_HAT_SOUTHEAST` | `3` | 135° |
| `JOYSTICK_HAT_SOUTH` | `4` | 180° |
| `JOYSTICK_HAT_SOUTHWEST` | `5` | 225° |
| `JOYSTICK_HAT_WEST` | `6` | 270° |
| `JOYSTICK_HAT_NORTHWEST` | `7` | 315° |

### Axes definition
Define an array (usually in `keymap.c`):
```c
joystick_config_t joystick_axes[JOYSTICK_AXIS_COUNT] = {
    JOYSTICK_AXIS_IN(A4, 900, 575, 285),   // pin, low, rest, high
    JOYSTICK_AXIS_VIRTUAL                   // value provided in code
};
```
- `JOYSTICK_AXIS_IN(input_pin, low, rest, high)` — ADC samples `input_pin`; `low`/`high`/`rest` are the min/max/centering analog readings. **Swap low/high to invert the axis.**
- `JOYSTICK_AXIS_VIRTUAL` — no ADC; set value via `joystick_set_axis()`.

With default 8-bit resolution, the example maps analog 900→575 to -127→0 and 575→285 to 0→+127.

### C API
| Function | Purpose |
|---|---|
| `void joystick_flush(void)` | Send the report if marked dirty |
| `void register_joystick_button(uint8_t button)` | Press button 0–31, flush |
| `void unregister_joystick_button(uint8_t button)` | Release button 0–31, flush |
| `int16_t joystick_read_axis(uint8_t axis)` | Sample/process an axis; 0 = rest |
| `void joystick_set_axis(uint8_t axis, int16_t value)` | Set an axis value (for virtual axes) |
| `void joystick_set_hat(int8_t value)` | Set hat position (`-1`…`7`) |

**Structs:** `joystick_t` (state) — `uint8_t buttons[]` (size `(JOYSTICK_BUTTON_COUNT-1)/8 + 1`), `int16_t axes[]`, `int8_t hat`, `bool dirty`. `joystick_config_t` — `pin_t input_pin` (`JS_VIRTUAL_AXIS` if virtual), `uint16_t min_digit`/`mid_digit`/`max_digit`.

### Behavior & ordering
- `JS_*` keycodes are dispatched by `process_joystick()` **late** in `process_record_quantum` (after `process_record_user`). Returning `false` in your `process_record_user` for a `JS_*` keycode prevents the button press. See **`01-architecture.md` §7.2**.
- ADC axes are sampled each scan by `joystick_read_axis`; reports are flushed only when `dirty`.

### Example (virtual axes driven by keypad, `KC_P0` = precision)
```c
joystick_config_t joystick_axes[JOYSTICK_AXIS_COUNT] = {
    JOYSTICK_AXIS_VIRTUAL, JOYSTICK_AXIS_VIRTUAL
};
static bool precision = false;
static uint16_t precision_mod = 64;
static uint16_t axis_val = 127;

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    int16_t v = axis_val;
    if (precision) v -= precision_mod;
    switch (keycode) {
        case KC_P8: joystick_set_axis(1, record->event.pressed ? -v : 0); return false;
        case KC_P2: joystick_set_axis(1, record->event.pressed ?  v : 0); return false;
        case KC_P4: joystick_set_axis(0, record->event.pressed ? -v : 0); return false;
        case KC_P6: joystick_set_axis(0, record->event.pressed ?  v : 0); return false;
        case KC_P0: precision = record->event.pressed; return false;
    }
    return true;
}
```

### Gotchas
- **ARM analog joysticks need 3.3V, not 5V** — the ADC driver rejects 5V even on 5V-pinned boards.
- **At least one button or axis is mandatory** or the descriptor is invalid.
- ADC resolution ceilings: **10-bit AVR, 12-bit most STM32** — `JOYSTICK_AXIS_RESOLUTION` above these won't add precision.
- **Endpoint cost:** joystick gets its own HID interface/endpoint. Combined with digitizer/programmable_button/console/midi you can exhaust AVR endpoints. See **`03-config-and-info-json.md` §4.4**.
- Swap `low`/`high` in `JOYSTICK_AXIS_IN` to invert — there's no separate invert define.

---

## 5. Digitizer (`DIGITIZER_ENABLE`)

### Summary
Presents the keyboard as a **digitizer / absolute-pointing stylus** device. Unlike pointing_device (relative deltas), the digitizer places the cursor at **absolute normalized coordinates** (0…1). Implements a stylus with a **tip switch** and **barrel switch** (≈ primary/secondary mouse buttons). **Tip pressure is not implemented.**

### Enable it
```make
# rules.mk
DIGITIZER_ENABLE = yes
```

### Positioning
X and Y are **normalized 0…1**: X `0` = left, `1` = right; Y `0` = top, `1` = bottom. With no display attached, the OS typically maps these to the **virtual desktop** — relevant with multiple monitors.

### C API
| Function | Purpose |
|---|---|
| `void digitizer_flush(void)` | Send report if dirty |
| `void digitizer_in_range_on(void)` / `_off(void)` | Assert/deassert "in range" + flush |
| `void digitizer_tip_switch_on(void)` / `_off(void)` | Assert/deassert tip switch + flush |
| `void digitizer_barrel_switch_on(void)` / `_off(void)` | Assert/deassert barrel switch + flush |
| `void digitizer_set_position(float x, float y)` | Set absolute X/Y (0…1) + flush |

**State struct** `digitizer_t` (`digitizer_state` is the global): `bool in_range`, `bool tip`, `bool barrel`, `float x`, `float y`, `bool dirty`.

### Behavior & ordering
- Digitizer is driven entirely from **C API calls** (no keycodes). Call it from `process_record_user` (on a custom keycode) or `pointing_device_task_user` / `housekeeping_task_*`.
- **`in_range` must be on** for a coordinate change to register. Turn it off to end an interaction (not strictly required).
- Each convenience function **flushes immediately**; to change multiple fields in one report, edit `digitizer_state` directly and call `digitizer_flush()`.

### Examples
```c
// Place cursor mid-screen
digitizer_in_range_on();
digitizer_set_position(0.5, 0.5);
```
```c
// Multi-field single report
digitizer_state.in_range = true;
digitizer_state.dirty    = true;
digitizer_flush();
```

### Gotchas
- **`in_range` gating:** forgetting `digitizer_in_range_on()` before `set_position` is the #1 "nothing happens" bug.
- **No tip pressure** — only binary tip/barrel switches.
- **Coordinates map to the virtual desktop**, not a single monitor — multi-monitor setups can be surprising.
- **Endpoint cost:** own HID interface/endpoint (see **`03-config-and-info-json.md` §4.4**).

---

## 6. Programmable Button (`PROGRAMMABLE_BUTTON_ENABLE`)

### Summary
Emits **32 "programmable button" keycodes** with no OS-defined meaning, on the **HID Telephony Device page (`0x0B`), Programmable Button usage (`0x09`)**. The host-side companion software interprets them. On **Linux > 5.14** they auto-map to `KEY_MACRO1`…`KEY_MACRO30`. (Contrast with raw HID in **`10-connectivity.md`**, which is a fully custom interface — this is a standardized usage page.)

> **No known support in Windows or macOS.** A custom HID driver could receive these usages, but that's out of scope for QMK docs.

### Enable it
```make
# rules.mk
PROGRAMMABLE_BUTTON_ENABLE = yes
```

### Keycodes
| Keycode | Alias | Description |
|---|---|---|
| `QK_PROGRAMMABLE_BUTTON_1` … `_32` | `PB_1` … `PB_32` | Programmable buttons 1–32 |

(32 keycodes total.)

### C API
| Function | Purpose |
|---|---|
| `void programmable_button_clear(void)` | Clear the report |
| `void programmable_button_add(uint8_t index)` | Press button index 0–31 (no flush) |
| `void programmable_button_remove(uint8_t index)` | Release button index 0–31 (no flush) |
| `void programmable_button_register(uint8_t index)` | Press button index 0–31 **+ flush** |
| `void programmable_button_unregister(uint8_t index)` | Release button index 0–31 **+ flush** |
| `bool programmable_button_is_on(uint8_t index)` | True if button index currently pressed |
| `void programmable_button_flush(void)` | Send the report |
| `uint32_t programmable_button_get_report(void)` | Current button bitmask |
| `void programmable_button_set_report(uint32_t report)` | Set the bitmask |

**Note:** the C API uses **0-based** indices (`0`–`31`); the keycodes `PB_1`…`PB_32` are **1-based**.

### Behavior & ordering
- `PB_*` keycodes are dispatched by `process_programmable_button()` **late** in `process_record_quantum` (after `process_record_user`). Returning `false` there for a `PB_*` keycode prevents the press. See **`01-architecture.md` §7.2**.
- `_add`/`_remove` mutate state but **don't flush** — pair with `programmable_button_flush()`, or use `_register`/`_unregister` which flush automatically.

### Gotchas
- **Off-by-one:** C API indices are 0-based; keycodes/aliases are 1-based (`PB_1`).
- **Platform support is Linux-only (>5.14, → `KEY_MACRO#`)** — Windows/macOS need a custom host driver.
- `_add`/`_remove` don't flush — forgetting `programmable_button_flush()` (or using `_register`/`_unregister`) is the common "key does nothing" bug.
- **Endpoint cost:** own HID interface/endpoint (see **`03-config-and-info-json.md` §4.4**).

---

## Cross-reference summary

| Topic | Where |
|---|---|
| `process_record` chain order (where `MS_*`/`JS_*`/`PB_*` dispatch) | **`01-architecture.md` §7.2** |
| Main loop, scan rate, `housekeeping_task_*` (polling cost) | **`01-architecture.md`** |
| USB endpoint budget, `usb.shared_endpoint.mouse`, polling interval | **`03-config-and-info-json.md` §4.4 / §5.7** |
| Split keyboard, `SPLIT_POINTING_ENABLE`, transport sync, wireless pointers | **`10-connectivity.md`** |
| SPI / I2C / ADC / serial driver APIs (sensor buses) | **`13-drivers-lowlevel.md`** |
| Flashing / `CONSOLE` debugging / `debug_mouse` | **`15-flashing-debugging.md`** |
