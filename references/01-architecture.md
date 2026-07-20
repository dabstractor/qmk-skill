# 01 — QMK Architecture & Internals

> The agent's map of how QMK works internally. This is the most cross-linked reference: other references point here for the **process_record dispatch chain order**, the **keypress lifecycle**, **matrix scanning**, the **layer stack**, and the **complete list of overrideable hooks**.
>
> Sources synthesized: `understanding_qmk.md`, `how_keyboards_work.md`, `how_a_matrix_works.md`, `ref_functions.md`, `custom_quantum_functions.md`.

---

## 0. TL;DR — The Keypress Lifecycle (end to end)

```
User finger ──> physical switch ──> MATRIX SCAN (polling, MCU-paced)
                                       │  compares prev scan vs current scan
                                       ▼
                              state-change detected (press or release)
                                       │  matrix[row][col] -> keycode via LAYOUT() + active layer
                                       ▼
                            action_exec(event)
                                       │
            ┌──────────────────────────┴───────────────────────────┐
            ▼                                                      ▼
  pre_process_record_quantum(record)            process_record(record)
   ├─ pre_process_record_kb                         ├─ process_record_quantum(record)
   │    └─ pre_process_record_user                  │     (see FULL ORDER below)
   └─ process_combo                                 └─ ... process_record_kb ─> process_record_user ...
                                       │
                                       ▼
                              (any handler may return false → HALT)
                                       │
                                       ▼
                            post_process_record(record)
                               ├─ post_process_record_quantum
                               │    ├─ post_process_record_kb
                               │    │    └─ post_process_record_user
                               │    └─ post_process_clicky
                                       │
                                       ▼
                        housekeeping_task_*  (end of this loop iteration)
                                       │
                                       ▼
                      next main-loop iteration (protocol_task ─> keyboard_task)
```

- A key event is a **change** between two scans, not the current state. The host wants deltas.
- Returning `false` anywhere in the `process_record_*` chain **halts all further processing** of that event — including normal keycode handling.
- `post_process_record_*` runs **after** the normal chain regardless (it is for cleanup/observation), but it is reached via its own dispatch after `process_record`.

---

## 1. Startup & The Main Loop

QMK is a normal C program whose `main()` never returns. Entry point: `quantum/main.c` → `main()`.

**Startup sequence (high level):**

1. `main()` calls `platform_setup()` (e.g. `platforms/avr/platform.c`) and `protocol_setup()` (e.g. `tmk_core/protocol/lufa/lufa.c` for the `lufa` platform on AVR `atmega32u4`; `chibios`, `vusb` for other platforms).
2. Hardware + USB are initialized. Most optional code is compiled out by `#define`s when the feature isn't enabled, so "looks huge" ≠ "huge at runtime".
3. The three keyboard-init hooks fire in order (see §6): `keyboard_pre_init_*` → `matrix_init_*` → `keyboard_post_init_*`.

**The main loop** is `while (true)` in `main()`. Each iteration:

1. `protocol_task()` — handles the USB/transport layer.
2. `protocol_task()` → `keyboard_task()` (`quantum/keyboard.c`). This is where keyboard-specific work happens:
   - **Matrix scanning** (detect switch changes) — see §2.
   - Mouse handling.
   - Keyboard status LEDs (Caps Lock / Num Lock / Scroll Lock) — see `07-led-rgb-backlight.md`.
3. At the **end** of all QMK processing, `housekeeping_task_*()` runs (layer states settled, USB reports sent, LEDs updated, displays drawn), then the loop repeats.

> Cross-link: build/environment details live in `02-getting-started-build.md`; platform-specific `main`/protocol details in `12-hardware-platforms.md` and `10-connectivity.md`.

---

## 2. Matrix Scanning

### 2.1 What it is

Matrix scanning is **the** core function of keyboard firmware: detecting which keys are pressed. It runs repeatedly — the docs state ~99% of CPU time is spent here, and the rate is "at least 10 times per second to avoid perceptible lag" (in practice far faster; see §4 for the real numbers).

The controller drives one **column** HIGH at a time and reads all **rows**, then moves to the next column (or the reverse for `ROW2COL`). For a 5×4 numpad the firmware's view of the matrix is:

```
{
    {0,0,0,0},
    {0,0,0,0},
    {0,0,0,0},
    {0,0,0,0},
    {0,0,0,0}
}
```

A `1` at `[row][col]` = that switch is closed (pressed).

### 2.2 Ghosting & diodes

With more than 2–3 simultaneous keys, a passive matrix can report **phantom** presses ("ghosting") because current can flow back through unintended paths. The fix is a **diode** per switch (one-way current), oriented so the black bar faces the row (mnemonic `>|`). With diodes, only genuinely-closed switches register. This is why QMK assumes diodes and why `DIRECT_PINS` / `COL2ROW` / `ROW2COL` exist.

> The detailed electrical picture (column-by-column bit reads like `col0: 0b01`) is in the source `how_a_matrix_works.md`; treat the scan as a black box unless you're hand-wiring or overriding it (see `12-hardware-platforms.md` → custom_matrix / hand_wire).

### 2.3 Matrix orientation (config knobs)

| key (info.json / config.h) | type | meaning |
|---|---|---|
| `matrix.rows`, `matrix.cols` (info.json) | int | Number of rows / columns. Equivalent `MATRIX_ROWS` / `MATRIX_COLS` in `config.h`. |
| `matrix.pins.rows` / `matrix.pins.cols` (info.json) | array[str] | GPIO pin per row / column. Legacy `MATRIX_ROW_PINS` / `MATRIX_COL_PINS` in `config.h`. |
| `matrix.layout` / `DIODE_DIRECTION` | enum | `COL2ROW` (default), `ROW2COL`, or `DIRECT_PINS` (no matrix — one pin per switch). |
| `matrix.custom` (info.json) | bool | `true` = skip built-in scan, use your own (legacy `CUSTOM_MATRIX = yes` in `rules.mk`). |

> Cross-link: full debounce + scan-rate knobs in `03-config-and-info-json.md`; custom/hand-wired matrix overrides in `12-hardware-platforms.md`.

### 2.4 State-change detection → dispatch

The scan only gives the **current** state. QMK keeps the previous scan and diffs them. Only **changes** (new press or new release) become key events; held keys that don't change produce no event. Each changed `[row][col]` is mapped through `LAYOUT()` + the active layer to a keycode (§3, §5) and dispatched into `action_exec()` → the process_record chain (§7).

---

## 3. The LAYOUT() Macro — Matrix ↔ Physical Mapping

QMK separates **physical layout** from **keycode assignment** using a C macro (conventionally `LAYOUT(...)`) generated by QMK from the keyboard's `info.json` `layouts` block. The macro has two halves:

1. **Argument list** = physical positions, in reading order (the way a human fills out the keymap).
2. **Body** = a 2-D `[row][col]` array that places each argument at its true matrix position.

Any matrix position with **no physical switch** is pre-filled with `KC_NO`, so the keymap author never has to write it. Example for a 17-key numpad (3 empty matrix slots):

```c
#define LAYOUT( \
    k00, k01, k02, k03, \
    k10, k11, k12, k13, \
    k20, k21, k22, \
    k30, k31, k32, k33, \
    k40,      k42 \
) { \
    { k00, k01,   k02, k03   }, \
    { k10, k11,   k12, k13   }, \
    { k20, k21,   k22, KC_NO }, \
    { k30, k31,   k32, k33   }, \
    { k40, KC_NO, k42, KC_NO } \
}
```

A keymap then assigns keycodes to the **physical** slots — these line up 1:1 with the macro's argument list:

```c
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT(
        KC_NUM,  KC_PSLS, KC_PAST, KC_PMNS,
        KC_P7,   KC_P8,   KC_P9,   KC_PPLS,
        KC_P4,   KC_P5,   KC_P6,
        KC_P1,   KC_P2,   KC_P3,   KC_PENT,
        KC_P0,            KC_PDOT
    )
};
```

This macro can encode any unusual matrix topology (e.g. Alice). **A keyboard can define multiple `LAYOUT_*()` macros** (community layouts) to support alternate physical arrangements over the same matrix.

> The data-driven source of these macros (`info.json` → `layouts.LAYOUT_*` → `layout` array of `{"x","y","r","rx","ry"}` + the physical-to-matrix mapping) is documented in `03-config-and-info-json.md` and `14-configurator-api-via.md`.

---

## 4. Scan Rate, Debounce, and USB Polling

Three distinct timing domains affect latency and behavior. They are **independent** but compound:

| Concept | What it governs | Set by |
|---|---|---|
| **Matrix scan rate** | How often the firmware re-reads the matrix (loop iterations/sec). MCU-paced — "as often as the MCU can handle." Bounded by how much work is in the loop. | Implicit; lower it by doing heavy work in `matrix_scan_*`/`housekeeping_task_*`. |
| **Debounce** | How long a switch must read consistently before a press/release is accepted (filters contact bounce). Adds latency to **every** key event. | `DEBOUNCE` (`config.h`, ms, default **5**) or info.json `debounce`. Algorithm via `DEBOUNCE_TYPE`. |
| **USB polling rate** | How often the host asks the keyboard for a new HID report. USB-level, **not** firmware-controlled. | Fixed by USB: Full-Speed = **1000 Hz** (1 ms), Low-Speed = 125 Hz (8 ms, common on cheap AVR). |

**Relationship:**

- End-to-end press latency ≈ scan period + debounce delay + (up to one) USB poll interval + OS processing.
- Scan rate is the *firmware* knob the user actually influences: anything you put in `matrix_scan_kb/user` or `housekeeping_task_kb/user` runs **once per scan**, so heavy work there directly slows scanning and raises latency. The docs explicitly warn: "Be extremely careful with the performance of code in these functions, as it will be called at least 10 times per second."
- Debounce is **mandatory** latency on top of scanning — lowering `DEBOUNCE` too aggressively causes double-presses from physical bounce.
- USB polling is a floor on report delivery cadence; a 1000 Hz keyboard cannot deliver reports faster than 1 ms apart regardless of scan rate, and an 8 Hz Low-Speed device is the real bottleneck on some boards.
- Wireless/split adds transport latency on top of all three — see `10-connectivity.md`.

> Cross-link: full debounce options (`DEBOUNCE_TYPE`: `sym_defer_g`/`sym_eager_pk`/`sym_eager_pr`/`sym_eager_g`/`asym_eager_defer_g`, `DEBOUNCE` range, per-key vs global) live in `03-config-and-info-json.md`.

---

## 5. Layers — Stack, Precedence, default_layer_state vs layer_state

QMK layers form a **stack**. A keycode lookup consults the stack from the **highest-numbered active layer downward**, returning the first non-transparent keycode it finds at `[row][col]`.

### 5.1 The two state variables

| Variable | Type | Meaning |
|---|---|---|
| `default_layer_state` | `layer_state_t` (bitmap) | The **base** layer(s) always on at boot. Persistent default layer is written to EEPROM. Set persistently via `set_single_persistent_default_layer(layer)` (survives unplug) or `set_single_default_layer(layer)` (runtime only). |
| `layer_state` | `layer_state_t` (bitmap) | The **current** active-layer mask (default-layer bits + any momentary/toggle layers currently on). This is what `layer_state_set_*` receives and returns. |

- **`default_layer_state`** = "what's always on". The keymap array index `[0]` is the conventional default.
- **`layer_state`** = "what's on right now" = default ∪ momentary/toggled layers.
- `layer_state_set_user(state)` is the hook for reacting to layer changes; return the (possibly modified) state.

### 5.2 Precedence rule

Higher layer numbers win. When resolving `[row][col]`:

1. Start at the highest active layer.
2. If the keycode there is **transparent** (`KC_TRNS`), drop to the next lower active layer.
3. Repeat until a non-`KC_TRNS` keycode (including `KC_NO`) is found, or you hit the default layer.

> Cross-link: the full keycode table for momentary/toggle/one-shot/tap-dance/layer-tap layer keys (`MO`, `TG`, `TO`, `TT`, `OSL`, `LM`, `LT`, `DF`) and tri_layer is in `04-keymaps-and-keycodes.md` and `05-text-input-and-combos.md`.

### 5.3 Tri-layer helper functions (from `ref_functions`)

| Function | Signature | Purpose |
|---|---|---|
| `update_tri_layer` | `void update_tri_layer(uint8_t x, uint8_t y, uint8_t z)` | If layers `x` **and** `y` are both on → turn on `z`; else turn off `z`. Call manually from `process_record_user` (e.g. on your LOWER/RAISE keys). |
| `update_tri_layer_state` | `layer_state_t update_tri_layer_state(layer_state_t state, uint8_t x, uint8_t y, uint8_t z)` | Meant to be **returned** from `layer_state_set_user`. Auto-triggers on any layer change (including `LT`/`TG`), not just your own keycodes. |

**`update_tri_layer_state` caveats:**
1. You **cannot** turn on `z` alone — activating `z` reruns the check and immediately turns `z` back off. You can only reach `z` via `x`+`y`.
2. `z` **must be a higher layer number** than `x` and `y`, or it may be unreachable / get clobbered (precedence rule).

```c
// Manual style (only fires on your own LOWER/RAISE keycodes):
bool process_record_user(uint16_t keycode, keyrecord_t *record) {
  switch (keycode) {
    case LOWER:
      if (record->event.pressed) { layer_on(_LOWER);  update_tri_layer(_LOWER,_RAISE,_ADJUST); }
      else                       { layer_off(_LOWER); update_tri_layer(_LOWER,_RAISE,_ADJUST); }
      return false;
    /* ... RAISE symmetric ... */
  }
  return true;
}

// Declarative style (fires on ANY layer change):
layer_state_t layer_state_set_user(layer_state_t state) {
  return update_tri_layer_state(state, _LOWER, _RAISE, _ADJUST);
  // or stack multiple:
  // state = update_tri_layer_state(state, _LOWER, _RAISE, _ADJUST);
  // state = update_tri_layer_state(state, _RAISE, _SYMB, _SPECIAL);
  // return state;
}
```

---

## 6. Special-Position Keycodes in the Matrix: KC_TRNS / KC_NO / _______ / XXXXXXX

| Symbol | Value | Meaning when placed in keymap `[row][col]` |
|---|---|---|
| `KC_NO` | (no-op keycode) | This key does **nothing** — the lookup **stops here**. Lower layers are **not** consulted. Used to "block" a key on a higher layer, and to pre-fill empty matrix slots inside `LAYOUT()`. |
| `KC_TRNS` | transparent | "Look at the next lower active layer for this position." The lookup **falls through** downward. |
| `_______` | alias for `KC_TRNS` | Readability alias. Mnemonic: "blank, inherit from below." |
| `XXXXXXX` | alias for `KC_NO` | Readability alias. Mnemonic: "hard block." |

**The precedence interaction (critical):** because `KC_NO` stops the lookup, putting `KC_NO` on a higher layer **shadows** whatever is below it for that key. Putting `KC_TRNS` lets a lower layer's binding show through. Misusing one for the other is a classic keymap bug (e.g. wanting to "disable" a key on a layer and using `_______` — which just inherits the base-layer binding instead of disabling it).

> `KC_NO` and `_______`/`XXXXXXX` aliases also appear in the full keycode tables in `04-keymaps-and-keycodes.md`.

---

## 7. The process_record Dispatch Chain (ORDER MATTERS)

This is the single most-referenced section. **Order is fixed.** A function compiled in only if its feature is enabled (`rules.mk`/`info.json`). Any handler may **`return false` to halt all further processing** of that event.

> Anchor: the chain begins in `action_exec(keyevent_t event)` (`quantum/action.c`).

### 7.1 Pre-processing phase

```
action_exec(event)
└─ pre_process_record_quantum(record)          // quantum/quantum.c
   ├─ pre_process_record_kb(keycode, record)   // _kb override (keyboard)
   │   └─ pre_process_record_user(keycode, record)   // _user override (keymap)
   └─ process_combo(keycode, record)           // combos — must see keys BEFORE normal handling
```

`pre_process_record_*` exists so features (notably **combos**) can intercept keys before the main chain. `_kb` must call `_user` or the keymap hook is never invoked.

### 7.2 Main processing phase — process_record_quantum

```
process_record(record)                         // quantum/action.c
└─ process_record_quantum(record)              // quantum/quantum.c
   ├─ (map record → keycode)
   ├─ velocikey_accelerate()
   ├─ update_wpm(keycode)
   ├─ preprocess_tap_dance(keycode, record)
   ├─ process_key_lock(keycode, record)
   ├─ process_dynamic_macro(keycode, record)
   ├─ process_clicky(keycode, record)
   ├─ process_haptic(keycode, record)
   ├─ process_record_via(keycode, record)
   ├─ process_record_kb(keycode, record)       // KEYBOARD hook
   │   └─ process_record_user(keycode, record) // KEYMAP hook  <-- most user code goes here
   ├─ process_secure(keycode, record)
   ├─ process_sequencer(keycode, record)
   ├─ process_midi(keycode, record)
   ├─ process_audio(keycode, record)
   ├─ process_backlight(keycode, record)
   ├─ process_steno(keycode, record)
   ├─ process_music(keycode, record)
   ├─ process_key_override(keycode, record)
   ├─ process_tap_dance(keycode, record)
   ├─ process_caps_word(keycode, record)
   ├─ process_unicode_common(keycode, record)
   │   ├─ process_unicode(...)
   │   ├─ process_unicodemap(...)
   │   └─ process_ucis(...)
   ├─ process_leader(keycode, record)
   ├─ process_auto_shift(keycode, record)
   ├─ process_dynamic_tapping_term(keycode, record)
   ├─ process_space_cadet(keycode, record)
   ├─ process_magic(keycode, record)
   ├─ process_grave_esc(keycode, record)
   ├─ process_rgb(keycode, record)
   ├─ process_joystick(keycode, record)
   ├─ process_programmable_button(keycode, record)
   └─ (identify + process Quantum-specific keycodes)   // quantum.c
```

**Ordering facts to remember:**

- **Combos** run in the **pre** phase, before everything else.
- `process_record_kb` runs **before** `process_record_user`, and `process_record_user` runs **before** most feature handlers (secure, audio, key_override, tap_dance, caps_word, unicode, leader, auto_shift, magic, grave_esc, rgb, …) and before the final Quantum-keycode dispatch.
- This means: if your `process_record_user` returns `false`, **none of the later feature handlers see the event** — including the final Quantum-keycode handler that turns `MO(1)`/`LT`/etc. into layer actions. Returning `false` on a layer/quantum keycode without reproducing its side effects will silently break it.
- Returning `true` from `process_record_user` lets normal handling continue (extending rather than replacing behavior).

> Cross-links for each feature handler: combos/caps_word/key_override/tap_dance/leader/space_cadet/auto_shift/tri_layer in `05-text-input-and-combos.md`; audio/haptic in `09-audio-haptic.md`; rgb/backlight in `07-led-rgb-backlight.md`; secure/command/os_detection in `10-connectivity.md`; unicode/steno/wpm in `11-other-features.md`; midi/sequencer in `09-audio-haptic.md`; VIA in `14-configurator-api-via.md`.

### 7.3 post_process_record (cleanup / observation, runs after the chain)

```
post_process_record(record)
└─ post_process_record_quantum(record)
   ├─ (map record → keycode)
   ├─ post_process_clicky(keycode, record)
   ├─ post_process_record_kb(keycode, record)   // KEYBOARD
   │   └─ post_process_record_user(keycode, record)   // KEYMAP
```

`post_process_record_*` is for **after-the-fact** work — e.g. activity timers, logging, RGB wake-on-press. Use it when you want to react to a key regardless of whether some earlier handler returned `false`.

> `post_process_record_user` is used in the canonical RGB-timeout example in `custom_quantum_functions.md` (refresh an activity timer on every press). See `07-led-rgb-backlight.md` for the LED side.

### 7.4 `return false` — the halt semantics

- **Pre / main chain:** any `process_*` (or `pre_process_record_*`) returning `false` **stops the chain cold** for that event. Downstream feature handlers, `_kb`/`_user`, and the final Quantum-keycode handler are all skipped. You own any HID/layer side effects the keycode would have had.
- **`_user` vs `_kb` precedence for the `shutdown_*` hook only:** returning `false` from `shutdown_user` **disables** the `_kb` level (opposite intuition — see §10).
- When you replace a keycode's behavior, you usually also need to handle **release** (`record->event.pressed == false`), or you'll leak a "stuck" key.

### 7.5 The `keyrecord_t` you receive

```c
keyrecord_t record {
  keyevent_t event {
    keypos_t key {
      uint8_t col;
      uint8_t row;
    };
    bool     pressed;   // true = key-down, false = key-up
    uint16_t time;      // timer ticks at press/release (see §11 software timers)
  };
};
```

- `keycode` is the **separate first argument** (`uint16_t`), already resolved through the layer stack to the value in your keymap (e.g. `MO(1)`, `KC_L`, your custom `FOO`).
- `record->event.pressed` distinguishes press vs release.
- `record->event.key.row/col` is the **matrix** position (not the physical-layout index) — useful for position-aware logic.

---

## 8. Custom Keycodes & SAFE_RANGE

To add a keycode, enumerate starting at `SAFE_RANGE` (guarantees a unique number above all built-in keycodes):

```c
enum my_keycodes {
  FOO = SAFE_RANGE,
  BAR
};
```

Then implement behavior in `process_record_user`. Two idioms:

- **Replace:** handle your keycode, `return false` (QMK does nothing else for it).
- **Augment:** handle (or fall through) and `return true` so QMK still does the normal thing (e.g. play a tone on `KC_ENTER` but still send Enter).

```c
bool process_record_user(uint16_t keycode, keyrecord_t *record) {
  switch (keycode) {
    case FOO:
      if (record->event.pressed) { /* down */ } else { /* up */ }
      return false;            // skip all further processing
    case KC_ENTER:
      if (record->event.pressed) { PLAY_SONG(tone_qwerty); }
      return true;             // still send Enter
    default:
      return true;             // everything else: normal handling
  }
}
```

> Always include a `default: return true;` — forgetting it silently swallows every unhandled keycode.

---

## 9. Complete Overrideable Hook Catalog

The hierarchy is **Core → Community Module (`_<module>`) → Keyboard/Revision (`_kb`) → Keymap (`_user`)**. A `_kb` implementation **must** call its `_user` counterpart at an appropriate point, or the keymap hook never fires. Likewise `_<module>_kb` must call `_<module>_user`. The full community-module pattern is documented in `18-community-modules.md`.

### 9.1 Initialization (called in this order)

| Stage | Keyboard (`_kb`) | Keymap (`_user`) | When |
|---|---|---|---|
| Pre-init (very early; before USB) | `void keyboard_pre_init_kb(void)` | `void keyboard_pre_init_user(void)` | Before almost anything. Hardware/LED-pin setup. |
| Matrix init (mid-startup) | `void matrix_init_kb(void)` | `void matrix_init_user(void)` | After some hardware, before most features. |
| Post-init (last thing) | `void keyboard_post_init_kb(void)` | `void keyboard_post_init_user(void)` | End of startup. **Preferred for most customization** (e.g. set up RGB underglow). |

> Tip from docs: most users want `keyboard_post_init_user`. Use `keyboard_pre_init_*` only for early hardware init (e.g. `gpio_set_pin_output(...)` for LED pins).

### 9.2 Per-scan / housekeeping

| Hook | Keyboard | Keymap | Notes |
|---|---|---|---|
| Matrix scan | `void matrix_scan_kb(void)` | `void matrix_scan_user(void)` | Called every scan (≥10×/sec, realistically far more). **Performance-critical.** For custom matrix code or status output when not typing. |
| Housekeeping | `void housekeeping_task_kb(void)` | `void housekeeping_task_user(void)` | End of all QMK processing each loop. By this point: layer states updated, USB reports sent, LEDs updated, displays drawn. Still MCU-paced — keep it light, throttle if needed. |

**Prefer `process_record_*` / `housekeeping_task_*` over `matrix_scan_*`** to avoid hurting scan performance. The docs deliberately omit a `matrix_scan_*` example and warn you not to add to it lightly.

### 9.3 Key-event hooks (see §7 for full chain)

| Hook | Keyboard | Keymap | Returns |
|---|---|---|---|
| Pre-process | `bool pre_process_record_kb(uint16_t keycode, keyrecord_t *record)` | `bool pre_process_record_user(uint16_t keycode, keyrecord_t *record)` | `false` halts |
| Process | `bool process_record_kb(uint16_t keycode, keyrecord_t *record)` | `bool process_record_user(uint16_t keycode, keyrecord_t *record)` | `false` halts |
| Post-process | `void post_process_record_kb(uint16_t keycode, keyrecord_t *record)` | `void post_process_record_user(uint16_t keycode, keyrecord_t *record)` | `void` |

### 9.4 Layer-change hook

| Hook | Keyboard | Keymap |
|---|---|---|
| Layer state | `layer_state_t layer_state_set_kb(layer_state_t state)` | `layer_state_t layer_state_set_user(layer_state_t state)` |

Return the (possibly modified) `state`. Pair with `update_tri_layer_state` (§5.3). Default-layer changes have their own persistent setters (`set_single_persistent_default_layer`).

### 9.5 Status-LED / indicator hooks

> Cross-link: full LED-indicator semantics in `07-led-rgb-backlight.md` (led_indicators).

| Hook | Keyboard | Keymap |
|---|---|---|
| LED update | `bool led_update_kb(led_t led_state)` | `bool led_update_user(led_t led_state)` |

Return `false` to stop the `_kb`/core from acting on the indicator (same halt convention as `process_record_*`). `led_t` carries the host's Caps/Num/Scroll/etc. lock bits.

### 9.6 Encoder hooks

> Cross-link: encoders in `08-displays.md`.

| Hook | Keyboard | Keymap |
|---|---|---|
| Encoder tick | `bool encoder_update_kb(uint8_t index, bool clockwise)` | `bool encoder_update_user(uint8_t index, bool clockwise)` |
| Encoder post-process | `bool encoder_update_kb`... (post variant) | `void post_encoder_update_user(uint8_t index, bool clockwise)` |

(`post_encoder_update_*` is used in the RGB-timeout example to treat encoder activity as "user activity.")

### 9.7 Suspend / wake (idle)

| Hook | Keyboard | Keymap |
|---|---|---|
| Power-down | `void suspend_power_down_kb(void)` | `void suspend_power_down_user(void)` |
| Wake | `void suspend_wakeup_init_kb(void)` | `void suspend_wakeup_init_user(void)` |

`suspend_power_down_*` may be called **multiple times** while suspended. Used to idle RGB/backlight to save power. (Note: the docs' Function Documentation table repeats `suspend_wakeup_init_user`/`_kb` inconsistently — treat the wake signature as `void` as shown above.)

### 9.8 Shutdown / reboot

| Hook | Keyboard | Keymap |
|---|---|---|
| Shutdown | `bool shutdown_kb(bool jump_to_bootloader)` | `bool shutdown_user(bool jump_to_bootloader)` |

- Fires on **both** soft reset (`QK_REBOOT`/`QK_CLEAR_EEPROM`) and bootloader jump (`QK_BOOT`). `jump_to_bootloader == true` ⇒ entering bootloader; `false` ⇒ soft reset reloading firmware.
- During shutdown QMK clears the keyboard, stops music/midi, plays a shutdown chime (if audio), stops haptic.
- **`shutdown_user` returning `false` disables the `_kb` level** (inverse of `process_record_*` intuition) — this is how a keymap fully takes over shutdown visuals.
- **Bootmagic does NOT trigger `shutdown_*()`** (it runs before most init).

```c
bool shutdown_user(bool jump_to_bootloader) {
    rgb_matrix_set_color_all(jump_to_bootloader ? RGB_RED : RGB_OFF);
    rgb_matrix_update_pwm_buffers();   // force flush — normal flush won't happen before reset
    return false;                       // don't also run _kb
}
```

### 9.9 Low-level matrix overrides (keyboard-designer level)

| Hook | Signature | When |
|---|---|---|
| Pin init | `void matrix_init_pins(void)` | Initialize all row/col GPIO per `MATRIX_ROW_PINS`/`MATRIX_COL_PINS` and direction (`COL2ROW`/`ROW2COL`/`DIRECT_PINS`). Overriding **disables** QMK's built-in pin init. |
| `COL2ROW` row read | `void matrix_read_cols_on_row(matrix_row_t current_matrix[], uint8_t current_row)` | Per-row column read for `COL2ROW`. |
| `ROW2COL` col read | `void matrix_read_rows_on_col(matrix_row_t current_matrix[], uint8_t current_col, matrix_row_t row_shifter)` | Per-column row read for `ROW2COL`. |
| `DIRECT_PINS` read | `void matrix_read_cols_on_row(matrix_row_t current_matrix[], uint8_t current_row)` | Direct-pin read. |

Implement **only one** of the three read functions. Overriding any of them makes QMK skip its own GPIO manipulation for that scan. (Full custom-matrix wiring: `CUSTOM_MATRIX = yes` / info.json `matrix.custom: true` — see `12-hardware-platforms.md`.)

### 9.10 Community module hooks (`_<module>`)

For keyboards/keymaps to override or augment a community module's processing, implement e.g. `process_record_<module>_kb` / `_user`. Same `_kb`-calls-`_user` discipline. See `18-community-modules.md`.

---

## 10. Useful Core Utility Functions (from `ref_functions`)

| Function | Signature | Purpose |
|---|---|---|
| `update_tri_layer` | `void update_tri_layer(uint8_t x, uint8_t y, uint8_t z)` | Manual tri-layer (§5.3). |
| `update_tri_layer_state` | `layer_state_t update_tri_layer_state(layer_state_t state, uint8_t x, uint8_t y, uint8_t z)` | Declarative tri-layer for `layer_state_set_*` (§5.3). |
| `set_single_persistent_default_layer` | `void set_single_persistent_default_layer(uint8_t layer)` | Set default layer + write to EEPROM + play default-layer song if audio. |
| `set_single_default_layer` | `void set_single_default_layer(uint8_t layer)` | Set default layer **runtime only** (not persisted). |
| `soft_reset_keyboard` | `void soft_reset_keyboard(void)` | Soft reset (reboot into firmware) — for use inside a macro. |
| `reset_keyboard` | `void reset_keyboard(void)` | Jump to bootloader. (Keycode equivalents: `QK_BOOTLOADER` / `QK_BOOT`.) |
| `eeconfig_init` | `void eeconfig_init(void)` | Wipe EEPROM, resetting most settings to default. (Keycode: `EE_CLR`.) |
| `tap_random_base64` | `void tap_random_base64(void)` | Send a pseudorandom Base64 char (0–25 A–Z, 26–51 a–z, 52–61 0–9, 62 `+`, 63 `/`). **Not** cryptographically secure. |
| Software timers | `uint16_t timer_read(void)` / `uint16_t timer_elapsed(uint16_t start)` | 16-bit ms timers. Use `timer_read32()` / `timer_elapsed32()` for 32-bit when you need long idle windows. |

**Default-layer songs** (`config.h`):
```c
#define DEFAULT_LAYER_SONGS { SONG(QWERTY_SOUND), \
                              SONG(COLEMAK_SOUND), \
                              SONG(DVORAK_SOUND) }
```

**Software-timer idiom:**
```c
static uint16_t key_timer = timer_read();
if (timer_elapsed(key_timer) < 100) { /* < 100 ms */ }
else                                 { /* >= 100 ms */ }
```

---

## 11. Deferred Execution (timer-based callbacks)

> Enable: `DEFERRED_EXEC_ENABLE = yes` in `rules.mk` (no data-driven equivalent shown).

A deferred executor lets you schedule a callback after N ms instead of hand-rolling a timer in `matrix_scan_*`.

**Callback signature** (return value = ms until next repeat, `0` = unregister):
```c
uint32_t my_callback(uint32_t trigger_time, void *cb_arg) {
    bool repeat = my_deferred_functionality();
    return repeat ? 500 : 0;
}
```

| API | Signature | Notes |
|---|---|---|
| Schedule | `deferred_token defer_exec(uint32_t delay_ms, uint32_t (*cb)(uint32_t, void*), void *cb_arg)` | `delay_ms` from now; returns `INVALID_DEFERRED_TOKEN` on failure (delay 0, null cb, or too many in-flight). |
| Extend | `void extend_deferred_exec(deferred_token token, uint32_t delay_ms)` | Re-delay a pending exec. |
| Cancel | `void cancel_deferred_exec(deferred_token token)` | Cancel before invocation. Token is then invalid; do not reuse. |

- `trigger_time` is the **intended** execution time (allows catch-up / skip). The returned delay is applied to `trigger_time`, **not** invocation time → consistent cadence despite late runs.
- `cb_arg` must outlive the callback (no pointers to stack locals).
- Cap on in-flight executors: `MAX_DEFERRED_EXECUTORS` (default **8**) in `config.h`:
  ```c
  #define MAX_DEFERRED_EXECUTORS 16
  ```

---

## 12. Gotchas (architecture-level)

### Gotchas

- **`return false` is a sledgehammer.** In `process_record_*` it halts the **entire** downstream chain — including Quantum-keycode handling that turns `MO`/`LT`/`OSL`/`TG` into layer actions. Returning `false` on a layer keycode without reproducing its effect silently breaks the layer. For "augment, don't replace," `return true`.
- **`process_record_user` runs *before* most feature handlers**, not after. If you `return false`, later handlers (key_override, tap_dance, caps_word, unicode, auto_shift, magic, grave_esc, rgb, …) never see the key. Order is fixed (§7.2).
- **`shutdown_user` returning `false` does the *opposite*** of `process_record_*`: it **disables** the `_kb` level (lets the keymap take over shutdown visuals). Don't apply the usual halt intuition here.
- **`KC_NO` vs `KC_TRNS` mix-up** is the #1 keymap bug: `KC_NO`/`XXXXXXX` **blocks** (lookup stops), `KC_TRNS`/`_______` **falls through** to lower layers. Wanting to "disable a key on this layer" and using `_______` just inherits the base-layer binding.
- **`update_tri_layer_state` traps:** (1) you can't activate layer `z` alone — turning `z` on reruns the rule and turns it off; (2) `z` must be a **higher** layer number than `x`/`y` or precedence can shadow/unreach it.
- **`matrix_scan_*` and `housekeeping_task_*` are scan-rate killers.** They run once per scan (≥10×/sec, often far more). Heavy work there directly raises key latency. Prefer `process_record_*` or deferred executors. The docs intentionally omit a `matrix_scan_*` example.
- **Debounce is *mandatory* latency** layered on every key event (default 5 ms). Lowering `DEBOUNCE` too far reintroduces contact bounce as phantom double-events.
- **USB polling is a floor, not firmware-controlled.** A 1000 Hz Full-Speed board still can't report faster than 1 ms; Low-Speed USB (some AVR) is 8 ms / 125 Hz — the real ceiling on those boards.
- **A replaced keycode needs its release handled too.** If you swallow the press (`return false`), QMK never sees the release either; if you synthesised a press you must also synthesise the release or you leak a stuck key.
- **Forgetting `default: return true;`** in `process_record_user` silently eats every keycode not in your `switch`.
- **`_kb` must call `_user`** (and `_<module>_kb` must call `_<module>_user`) or the downstream hook never runs. Easy to break when copying a keyboard-level `.c`.
- **`pre_process_record_*` is where combos live** — anything that must intercept a key *before* the main chain belongs here, not in `process_record_user`.
- **Bootmagic bypasses `shutdown_*()`** because it runs before init — don't expect shutdown cleanup to fire on a Bootmagic reset.
- **`suspend_power_down_*` fires repeatedly** while suspended; code there must be idempotent.
- **`post_process_record_*` is for observation/cleanup** (e.g. activity timers), reached via its own dispatch after the main chain — use it when you want to react regardless of an earlier `return false`.

---

## 13. Cross-reference Index

- **`02-getting-started-build.md`** — build system, `main()`/platform wiring from the toolchain side.
- **`03-config-and-info-json.md`** — `info.json` schema for matrix/layout/debounce; `config.h` matrix + debounce defines; `LAYOUT` generation.
- **`04-keymaps-and-keycodes.md`** — keymap.c structure, full keycode tables (incl. `KC_TRNS`/`KC_NO`, layer keycodes, mod_tap, quantum keycodes).
- **`05-text-input-and-combos.md`** — combos (pre-process), key_override, tap_dance, caps_word, leader, auto_shift, space_cadet, tri_layer.
- **`07-led-rgb-backlight.md`** — `led_update_*` indicators, RGB timeout patterns, `process_rgb`/`process_backlight`.
- **`08-displays.md`** — `encoder_update_*` / `post_encoder_update_*`.
- **`09-audio-haptic.md`** — `process_audio`/`process_haptic`/`process_midi`/`process_sequencer`/`process_clicky`.
- **`10-connectivity.md`** — split sync over the main loop, wireless transport latency, `process_secure`/command/os_detection.
- **`11-other-features.md`** — unicode/steno/wpm handlers. **`18-community-modules.md`** — community module `_<module>` hook pattern, keycodes, examples.
- **`12-hardware-platforms.md`** — `matrix_init_pins` / `matrix_read_*` custom-matrix overrides, hand-wire, porting.
- **`14-configurator-api-via.md`** — `LAYOUT_*` macro generation for Configurator/VIA, `process_record_via`.
- **`16-userspace-development.md`** — `_kb`/`_user` coding conventions for keyboards/userspace.
- **`17-faq-gotchas-breaking-changes.md`** — historical changes to the hook set and process_record ordering.
