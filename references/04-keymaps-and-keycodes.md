# 04 — Keymaps & Keycodes Reference

> **Role:** This is the agent's *primary* reference for writing `keymap.c` and for choosing/combining keycodes. It covers keymap anatomy, the layers model, the full basic-keycode tables, mod-tap, one-shot keys, tap-hold configuration, quantum/mod-combo keycodes, magic keycodes, US-ANSI-shifted caveats, and the language (international layout) keymap-extras mechanism.
>
> **Cross-links:** For the internal key-processing pipeline (where `process_record_user` sits, scan → keycode decode → action → send), see `01-architecture.md`. For `info.json` schema, `rules.mk`/`config.h` data-driven migration, and EEPROM/debounce, see `03-config-and-info-json.md`. For text-input features that consume keycodes (macros/send_string, combos, key_overrides, tap_dance, tri_layer, layer_lock, grave_esc, auto_shift), see `05-text-input-and-combos.md`. For breaking changes / deprecation history, see `17-faq-gotchas-breaking-changes.md`.

---

## 1. Keymap Anatomy

### Summary

A QMK keymap is a C source file (`keymap.c`) whose core data structure is an array of layer arrays:

```c
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = { ... };
```

Each entry is a **16-bit action code** (often loosely called a "keycode"). For a trivial key the high byte is `0x00` and the low byte is the USB HID usage ID. Quantum/advanced keycodes pack function bits into the high byte. (This is why QMK can encode layers, mods, mod-taps, etc. into one `uint16_t` — and also why there are hard limits described below.)

> **TMK history note:** TMK (QMK's predecessor) used `const uint8_t PROGMEM keymaps[]...` with 8-bit keycodes. QMK widened this to 16-bit. Some docs still say "keycode" when they mean the full action code.

### Standard `keymap.c` layout

```c
#include QMK_KEYBOARD_H

// Layer index enum (names are for readability; underscores are cosmetic)
enum layer_names {
    _QWERTY = 0,
    _LOWER,
    _RAISE,
    _ADJUST,
};

// Custom keycodes start at SAFE_RANGE / QK_USER to avoid collisions
enum custom_keycodes {
    KC_CYCLE_LAYERS = SAFE_RANGE,   // legacy form
    // or: KC_CYCLE_LAYERS = QK_USER,  (preferred modern form)
};

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [_QWERTY] = LAYOUT(
        KC_ESC,  KC_1,    KC_2,    KC_3, /* ... */   KC_BSPC,
        KC_TAB,  KC_Q,    KC_W,    KC_E, /* ... */   KC_BSLS,
        KC_LCTL, KC_A,    KC_S,    KC_D, /* ... */   MO(_LOWER),
        KC_LSFT, KC_Z,    KC_X,    KC_C, /* ... */   MO(_RAISE),
        /* ... */
    ),
    [_LOWER] = LAYOUT(
        KC_GRV,  KC_F1,   KC_F2,   KC_F3, /* ... */  KC_DEL,
        _______, _______, _______, _______, /* ... */ _______,
        /* ... KC_TRNS / _______ falls through to lower layers ... */
    ),
    /* ... */
};
```

### Anatomy details

- **`#include QMK_KEYBOARD_H`** — always first. Pulls in all keycode definitions, the keyboard's `LAYOUT` macro (from its `.h` / `info.json`), and the QMK API.
- **Layer enum** — gives names to layer indices 0–31. Optional; you can use raw numbers, but names are strongly preferred for readability.
- **`_______` and `XXXXXXX`** — these aliases for `KC_TRNS` and `KC_NO` are **defined by default**; you do *not* need to `#define` them in modern QMK. (Older keymaps still have the `#define`s — they're harmless but redundant.)
- **`LAYOUT(...)`** — a macro defined per-keyboard (in its header, generated from `info.json`). It maps a flat list of keycodes onto the physical matrix (`MATRIX_ROWS` × `MATRIX_COLS`), hiding the scan-matrix wiring. Whitespace/newlines inside the call are cosmetic only — used to visualize physical layout.
- **`PROGMEM`** — stores the keymap in flash (program memory) on AVR, saving RAM. On ARM it's effectively a no-op but still required by convention.
- **Naming convention:** plain HID scancodes are prefixed `KC_`; "special"/quantum keycodes (`MO`, `LT`, `MT`, `OSM`, `QK_*`, custom) are *not*.

### Custom keycodes & safe range

Define custom keycodes that begin past QMK's reserved range, then handle them in `process_record_user`:

```c
enum custom_keycodes {
    MY_CUSTOM = SAFE_RANGE,   // legacy: must avoid overlapping QMK's own
    // Modern/preferred:
    // MY_CUSTOM = QK_USER,
};

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case MY_CUSTOM:
            if (record->event.pressed) {
                SEND_STRING("Hello");
            }
            return false;   // false = stop further processing
        default:
            return true;    // true = normal processing
    }
}
```

- **`SAFE_RANGE`** — older mechanism; the value tracks QMK's internal keycode ceiling. Works but is fragile if you also use feature keycodes dynamically.
- **`QK_USER`** — modern preferred start for user keycodes (dedicated user keycode range, `QK_USER` … `QK_USER_MAX`). See `quantum_keycodes.md`. **Prefer `QK_USER`.**

> See `01-architecture.md` for the full `process_record` chain ordering (where `_user` sits relative to `_kb` and feature handlers).

---

## 2. The Layers Model

### Summary

QMK supports up to **32 layers** (indices 0–31). Layers stack: when resolving a keypress, QMK scans from the **highest active layer downward** and uses the first non-transparent (`KC_TRNS`) keycode it finds. Higher layers therefore have **precedence** over lower ones.

### Layer state: two 32-bit values

| State | Meaning |
|-------|---------|
| **`default_layer_state`** | Bitmask of the *base* layer(s). Always active; the foundation other layers stack on. Typically bit 0 set (layer 0). Change this to *permanently* switch base layout (e.g. QWERTY ↔ Colemak). |
| **`layer_state`** | Bitmask of *currently active overlay layers* (on/off per bit). This is what `MO`/`TG`/`LT`/etc. mutate. |

Both are bitmasks: bit *N* set ⇒ layer *N* active. The effective keycode lookup considers `default_layer_state | layer_state`, scanning from the highest set bit down.

### Transparency & precedence

- **`KC_TRANSPARENT` / `KC_TRNS` / `_______`** — "fall through": at this position, keep descending to lower active layers until a non-transparent keycode is found.
- **`KC_NO` / `XXXXXXX`** — "block": nothing is sent; lookup stops here (does *not* fall through).
- Lookup **stops at the first non-`KC_TRNS` entry**, even if that entry is `KC_NO`. Lower layers are never consulted for that key.

```
   ____________
  /           /  <--- Higher active layer (e.g. layer 2)
 /  KC_TRNS  //
/___________//   <--- Lower active layer (KC_A)  → result: KC_A
/___________/
```

### Gotchas (layers)

- **You can't overlay a lower layer *on top of* a higher one.** If a higher active layer has a non-`KC_TRNS` key at a position, activating a *lower* layer will not change what that key does. This is the #1 cause of "my layer switch doesn't work."
- **Momentary keys need a transparent destination.** `MO(n)`, `LM(n, ...)`, `LT(n, kc)`, `TT(n)` all *activate* layer `n`; if layer `n` has a non-transparent key at the *same physical position* as the momentary switch key, you can lose access to the layer (and on some setups, lock yourself in). Leave the switch position (and usually most of the layer) `KC_TRNS`.
- **It is possible to lock yourself into a layer** with no key to escape (especially with `TG`/`TO`/`DF`/`PDF`). Always keep an escape path; `EE_CLR` (clear EEPROM) is a last resort.
- **Beginner rule:** layer 0 is base; arrange layers as a tree rooted at 0; only reference *higher-numbered* layers from a given layer.
- `TO(n)` is special: it replaces the *entire* active layer stack (except default), so it's the only way to "go down" reliably.

---

## 3. Layer-Switch Keycodes (exact semantics)

> Source: `feature_layers.md` + `keycodes.md`. These are the authoritative behaviors; the differences are subtle and matter.

| Keycode | Persistence | Behavior |
|---------|-------------|----------|
| `DF(layer)` | Until power loss | Sets the **default (base) layer**. Temporary — resets on reboot. Use to switch base layout (QWERTY→Dvorak). |
| `PDF(layer)` | EEPROM (survives reboot) | Like `DF` but **persists** to EEPROM. |
| `MO(layer)` | While held | Momentary: layer on while key held, off on release. Needs `KC_TRNS` on destination. |
| `LM(layer, mod)` | While held | Momentary layer **plus** modifiers `mod` active. Layer & mod limited to 0–15 / 5-bit (see caveats). `mod` uses `MOD_*` prefix. |
| `LT(layer, kc)` | Tap vs hold | Tap → send `kc`; hold → momentary layer `layer`. Layer 0–15, `kc` must be a Basic Keycode (≤`0xFF`). |
| `OSL(layer)` | One keypress | Momentary layer for **exactly one** subsequent keypress. See §6 one-shot. |
| `TG(layer)` | Toggle (sticky) | Toggles layer on/off (like a caps-lock for a layer). |
| `TO(layer)` | Replaces stack | Activates `layer` and **deactivates all other layers except default**. Fires on keydown. Uniquely lets you replace higher layers with a lower one. |
| `TT(layer)` | Hold or tap-toggle | Hold = `MO`; tap repeatedly = `TG`. Default 5 taps to toggle (`TAPPING_TOGGLE`). **Tap-toggle requires Quick Tap enabled** (`QUICK_TAP_TERM != 0`). |

### `LM` / `LT` caveats (16-bit keycode packing)

Because keycodes are 16 bits and QMK reserves bits for the function id + layer/mod, there are hard limits:

- **`LT(layer, kc)`:** `layer` ∈ 0–15; `kc` must be a **Basic Keycode** (≤ `0xFF`). You **cannot** use `LCTL(...)`, `KC_TILD`/`KC_DQUO` (US-ANSI-shifted aliases — see §10), mod-taps, or anything `> 0xFF`. (4 bits function id, 4 bits layer, 8 bits keycode.)
- **`LM(layer, mod)`:** `layer` ∈ 0–15; `mod` must fit in 5 bits. You **cannot mix left & right modifiers** — specifying any right-hand mod converts *all* listed mods to their right-hand counterpart. (E.g. `MOD_RALT|MOD_LSFT` sends RAlt+RShift.) Always use the `MOD_xxx` constants.
- **Correct `LM` forms** (the `mod` arg): `LM(_RAISE, MOD_LCTL | MOD_LALT)` ✅. Wrong: `LM(1, KC_LSFT)`, `LM(1, MOD_MASK_SHIFT)`, `LM(1, MOD_BIT(KC_LSFT))` ❌ — use `LM(1, MOD_LSFT)`.
- Workaround for needing modifiers on a *tapped* `LT`/`MT` key: **Tap Dance** (see `05-text-input-and-combos.md`), or intercept in `process_record_user` (see §5 "Intercepting Mod-Taps").

### Layer C API (functions & callbacks)

Callable from `keymap.c` (macros/code) — from `feature_layers.md`:

| Function | Purpose |
|----------|---------|
| `layer_state_set(layer_mask)` | Directly set layer state (avoid unless you know what you're doing). |
| `layer_clear()` | Turn all layers off. |
| `layer_move(layer)` | Turn `layer` on, all others off (≈ `TO`). |
| `layer_on(layer)` / `layer_off(layer)` | Toggle one layer, leave others. |
| `layer_invert(layer)` | Toggle state of `layer`. |
| `layer_or(layer_mask)` / `layer_and(layer_mask)` / `layer_xor(layer_mask)` | Bitwise-merge masks into state. |
| `layer_debug(layer_mask)` | Print bitmask + highest layer to debug console. |
| `default_layer_set(layer_mask)` | Directly set default layer state (avoid). |
| `default_layer_or/and/xor(layer_mask)` | Bitwise default-layer ops. |
| `default_layer_debug(layer_mask)` | Debug-print default-layer state. |
| `set_single_default_layer(layer)` | Set default layer (NOT written to EEPROM). |
| `set_single_persistent_default_layer(layer)` | Set default layer **and** write to EEPROM (≈ `PDF`). |
| `update_tri_layer(x, y, z)` | If `x` and `y` both on → `z` on; else `z` off. (See tri_layer in `05`.) |
| `update_tri_layer_state(state, x, y, z)` | Same, but callable from `layer_state_set_*`. |

Query macros:

| Function / Macro | Aliases | Purpose |
|------------------|---------|---------|
| `layer_state_is(layer)` | `IS_LAYER_ON(layer)`, `IS_LAYER_OFF(layer)` | Global layer on/off check (use outside callbacks). |
| `layer_state_cmp(state, layer)` | `IS_LAYER_ON_STATE(state, layer)`, `IS_LAYER_OFF_STATE(state, layer)` | Check a *passed-in* state (use inside `layer_state_set_*`). |
| `get_highest_layer(state)` | — | Highest active layer index in `state`. |

Callbacks (called on layer change):

| Callback | Scope |
|----------|-------|
| `layer_state_set_kb(layer_state_t state)` | Keyboard-level. |
| `layer_state_set_user(layer_state_t state)` | Keymap-level (you). **Must `return state;`** (possibly modified). |
| `default_layer_state_set_kb(layer_state_t state)` | Keyboard, called on init. |
| `default_layer_state_set_user(layer_state_t state)` | Keymap, called on init. |

```c
// Example: set RGB underglow by active layer
layer_state_t layer_state_set_user(layer_state_t state) {
    switch (get_highest_layer(state)) {
        case _RAISE:  rgblight_setrgb(0x00, 0x00, 0xFF); break;
        case _LOWER:  rgblight_setrgb(0xFF, 0x00, 0x00); break;
        default:      rgblight_setrgb(0x00, 0xFF, 0xFF); break;
    }
    return state;
}
```

> For **Layer Lock** (`QK_LAYER_LOCK` / `QK_LLCK`) — locks the highest active layer until pressed again — see `05-text-input-and-combos.md`.

---

## 4. Basic Keycodes (full tables)

> Source: `keycodes_basic.md`. These map directly to the USB HID Keyboard/Keypad Usage Page (0x07), with `KC_NO`, `KC_TRNS`, and the `0xA5–0xDF` range reserved for internal use. These are the *only* keycodes usable as the `kc` arg of `MT()` / `LT()` / `LM()` tap portion.

### Special keys

| Key | Aliases | Description |
|-----|---------|-------------|
| `KC_NO` | `XXXXXXX` | Ignore this key (NOOP); blocks fall-through. |
| `KC_TRANSPARENT` | `KC_TRNS`, `_______` | Fall through to next lower active layer. |

### Letters and numbers

| Key | Description | Key | Description |
|-----|-------------|-----|-------------|
| `KC_A` … `KC_Z` | `a`/`A` … `z`/`Z` | `KC_1` | `1` and `!` |
| | | `KC_2` | `2` and `@` |
| | | `KC_3` | `3` and `#` |
| | | `KC_4` | `4` and `$` |
| | | `KC_5` | `5` and `%` |
| | | `KC_6` | `6` and `^` |
| | | `KC_7` | `7` and `&` |
| | | `KC_8` | `8` and `*` |
| | | `KC_9` | `9` and `(` |
| | | `KC_0` | `0` and `)` |

### F keys

`KC_F1` … `KC_F24` (F1–F24).

### Punctuation / whitespace

| Key | Aliases | Description |
|-----|---------|-------------|
| `KC_ENTER` | `KC_ENT` | Return (Enter) |
| `KC_ESCAPE` | `KC_ESC` | Escape |
| `KC_BACKSPACE` | `KC_BSPC` | Delete (Backspace) |
| `KC_TAB` | | Tab |
| `KC_SPACE` | `KC_SPC` | Spacebar |
| `KC_MINUS` | `KC_MINS` | `-` and `_` |
| `KC_EQUAL` | `KC_EQL` | `=` and `+` |
| `KC_LEFT_BRACKET` | `KC_LBRC` | `[` and `{` |
| `KC_RIGHT_BRACKET` | `KC_RBRC` | `]` and `}` |
| `KC_BACKSLASH` | `KC_BSLS` | `\` and `\|` |
| `KC_NONUS_HASH` | `KC_NUHS` | Non-US `#` and `~` |
| `KC_SEMICOLON` | `KC_SCLN` | `;` and `:` |
| `KC_QUOTE` | `KC_QUOT` | `'` and `"` |
| `KC_GRAVE` | `KC_GRV` | `` ` `` and `~` |
| `KC_COMMA` | `KC_COMM` | `,` and `<` |
| `KC_DOT` | | `.` and `>` |
| `KC_SLASH` | `KC_SLSH` | `/` and `?` |
| `KC_NONUS_BACKSLASH` | `KC_NUBS` | Non-US `\` and `\|` |

### Lock keys

| Key | Aliases | Description |
|-----|---------|-------------|
| `KC_CAPS_LOCK` | `KC_CAPS` | Caps Lock |
| `KC_SCROLL_LOCK` | `KC_SCRL`, `KC_BRMD` | Scroll Lock; Brightness Down (macOS) |
| `KC_NUM_LOCK` | `KC_NUM` | Keypad Num Lock and Clear |
| `KC_LOCKING_CAPS_LOCK` | `KC_LCAP` | Locking Caps Lock |
| `KC_LOCKING_NUM_LOCK` | `KC_LNUM` | Locking Num Lock |
| `KC_LOCKING_SCROLL_LOCK` | `KC_LSCR` | Locking Scroll Lock |

### Modifiers

| Key | Aliases | Description |
|-----|---------|-------------|
| `KC_LEFT_CTRL` | `KC_LCTL` | Left Control |
| `KC_LEFT_SHIFT` | `KC_LSFT` | Left Shift |
| `KC_LEFT_ALT` | `KC_LALT`, `KC_LOPT` | Left Alt (Option) |
| `KC_LEFT_GUI` | `KC_LGUI`, `KC_LCMD`, `KC_LWIN` | Left GUI (Windows/Command/Super) |
| `KC_RIGHT_CTRL` | `KC_RCTL` | Right Control |
| `KC_RIGHT_SHIFT` | `KC_RSFT` | Right Shift |
| `KC_RIGHT_ALT` | `KC_RALT`, `KC_ROPT`, `KC_ALGR` | Right Alt (Option/AltGr) |
| `KC_RIGHT_GUI` | `KC_RGUI`, `KC_RCMD`, `KC_RWIN` | Right GUI (Windows/Command/Super) |

### Commands / navigation

| Key | Aliases | Description |
|-----|---------|-------------|
| `KC_PRINT_SCREEN` | `KC_PSCR` | Print Screen |
| `KC_PAUSE` | `KC_PAUS`, `KC_BRK`, `KC_BRMU` | Pause; Brightness Up (macOS) |
| `KC_INSERT` | `KC_INS` | Insert |
| `KC_HOME` | | Home |
| `KC_PAGE_UP` | `KC_PGUP` | Page Up |
| `KC_DELETE` | `KC_DEL` | Forward Delete |
| `KC_END` | | End |
| `KC_PAGE_DOWN` | `KC_PGDN` | Page Down |
| `KC_RIGHT` | `KC_RGHT` | Right Arrow |
| `KC_LEFT` | | Left Arrow |
| `KC_DOWN` | | Down Arrow |
| `KC_UP` | | Up Arrow |
| `KC_APPLICATION` | `KC_APP` | Application (Windows Context Menu) |
| `KC_KB_POWER` | | System Power |
| `KC_EXECUTE` | `KC_EXEC` | Execute |
| `KC_HELP` | | Help |
| `KC_MENU` | | Menu |
| `KC_SELECT` | `KC_SLCT` | Select |
| `KC_STOP` | | Stop |
| `KC_AGAIN` | `KC_AGIN` | Again |
| `KC_UNDO` | | Undo |
| `KC_CUT` | | Cut |
| `KC_COPY` | | Copy |
| `KC_PASTE` | `KC_PSTE` | Paste |
| `KC_FIND` | | Find |
| `KC_KB_MUTE` / `KC_KB_VOLUME_UP` / `KC_KB_VOLUME_DOWN` | | Mute / Vol Up / Vol Down (system) |
| `KC_ALTERNATE_ERASE` … `KC_EXSEL` | `KC_ERAS`,`KC_SYRQ`,`KC_CNCL`,`KC_CLR`,`KC_PRIR`,`KC_RETN`,`KC_SEPR`,`KC_CLAG`,`KC_CRSL`,`KC_EXSL` | Rare HID commands (Alternate Erase, SysReq, Cancel, Clear, Prior, Return, Separator, Clear/Again, CrSel, ExSel). |

### Media / system / consumer (HID Consumer + Generic Desktop pages)

| Key | Aliases | Description |
|-----|---------|-------------|
| `KC_SYSTEM_POWER` | `KC_PWR` | System Power Down |
| `KC_SYSTEM_SLEEP` | `KC_SLEP` | System Sleep |
| `KC_SYSTEM_WAKE` | `KC_WAKE` | System Wake |
| `KC_AUDIO_MUTE` | `KC_MUTE` | Mute |
| `KC_AUDIO_VOL_UP` | `KC_VOLU` | Volume Up |
| `KC_AUDIO_VOL_DOWN` | `KC_VOLD` | Volume Down |
| `KC_MEDIA_NEXT_TRACK` | `KC_MNXT` | Next Track |
| `KC_MEDIA_PREV_TRACK` | `KC_MPRV` | Previous Track |
| `KC_MEDIA_STOP` | `KC_MSTP` | Stop Track |
| `KC_MEDIA_PLAY_PAUSE` | `KC_MPLY` | Play/Pause |
| `KC_MEDIA_SELECT` | `KC_MSEL` | Launch Media Player |
| `KC_MEDIA_EJECT` | `KC_EJCT` | Eject |
| `KC_MAIL` | | Launch Mail |
| `KC_CALCULATOR` | `KC_CALC` | Launch Calculator |
| `KC_MY_COMPUTER` | `KC_MYCM` | Launch My Computer |
| `KC_WWW_SEARCH` | `KC_WSCH` | Browser Search |
| `KC_WWW_HOME` | `KC_WHOM` | Browser Home |
| `KC_WWW_BACK` | `KC_WBAK` | Browser Back |
| `KC_WWW_FORWARD` | `KC_WFWD` | Browser Forward |
| `KC_WWW_STOP` | `KC_WSTP` | Browser Stop |
| `KC_WWW_REFRESH` | `KC_WREF` | Browser Refresh |
| `KC_WWW_FAVORITES` | `KC_WFAV` | Browser Favorites |
| `KC_MEDIA_FAST_FORWARD` | `KC_MFFD` | Fast Forward |
| `KC_MEDIA_REWIND` | `KC_MRWD` | Rewind |
| `KC_BRIGHTNESS_UP` | `KC_BRIU` | Brightness Up |
| `KC_BRIGHTNESS_DOWN` | `KC_BRID` | Brightness Down |
| `KC_CONTROL_PANEL` | `KC_CPNL` | Open Control Panel |
| `KC_ASSISTANT` | `KC_ASST` | Launch Assistant |
| `KC_MISSION_CONTROL` | `KC_MCTL` | Open Mission Control (macOS) |
| `KC_LAUNCHPAD` | `KC_LPAD` | Open Launchpad (macOS) |

> **OS quirks:** On macOS, `KC_PSCR`/`KC_SCRL`/`KC_PAUS` are treated as F13–F15. `KC_PWR`/`KC_SLEP`/`KC_WAKE` must be held ~3s and prompt first. `KC_VOLU`/`KC_VOLD` allow finer control with Shift+Option. `KC_MFFD`/`KC_MRWD`/`KC_MNXT`/`KC_MPRV` skip *within* a track when held, skip the whole track when tapped, in iTunes. Linux HID driver recognizes nearly all codes; default bindings depend on DE/WM.

### Number pad (keypad)

| Key | Aliases | Description |
|-----|---------|-------------|
| `KC_KP_SLASH` | `KC_PSLS` | Keypad `/` |
| `KC_KP_ASTERISK` | `KC_PAST` | Keypad `*` |
| `KC_KP_MINUS` | `KC_PMNS` | Keypad `-` |
| `KC_KP_PLUS` | `KC_PPLS` | Keypad `+` |
| `KC_KP_ENTER` | `KC_PENT` | Keypad Enter |
| `KC_KP_1` | `KC_P1` | Keypad `1` and End |
| `KC_KP_2` | `KC_P2` | Keypad `2` and Down |
| `KC_KP_3` | `KC_P3` | Keypad `3` and Page Down |
| `KC_KP_4` | `KC_P4` | Keypad `4` and Left |
| `KC_KP_5` | `KC_P5` | Keypad `5` |
| `KC_KP_6` | `KC_P6` | Keypad `6` and Right |
| `KC_KP_7` | `KC_P7` | Keypad `7` and Home |
| `KC_KP_8` | `KC_P8` | Keypad `8` and Up |
| `KC_KP_9` | `KC_P9` | Keypad `9` and Page Up |
| `KC_KP_0` | `KC_P0` | Keypad `0` and Insert |
| `KC_KP_DOT` | `KC_PDOT` | Keypad `.` and Delete |
| `KC_KP_EQUAL` | `KC_PEQL` | Keypad `=` |
| `KC_KP_COMMA` | `KC_PCMM` | Keypad `,` |
| `KC_KP_EQUAL_AS400` | | Keypad `=` on AS/400 keyboards |

### International & language (HID International/Language pages)

| Key | Aliases | Description |
|-----|---------|-------------|
| `KC_INTERNATIONAL_1` | `KC_INT1` | JIS `\` and `_` |
| `KC_INTERNATIONAL_2` | `KC_INT2` | JIS Katakana/Hiragana |
| `KC_INTERNATIONAL_3` | `KC_INT3` | JIS `¥` and `\|` |
| `KC_INTERNATIONAL_4` | `KC_INT4` | JIS Henkan |
| `KC_INTERNATIONAL_5` | `KC_INT5` | JIS Muhenkan |
| `KC_INTERNATIONAL_6` | `KC_INT6` | JIS Numpad `,` |
| `KC_INTERNATIONAL_7/8/9` | `KC_INT7/8/9` | International 7/8/9 |
| `KC_LANGUAGE_1` | `KC_LNG1` | Hangul/English |
| `KC_LANGUAGE_2` | `KC_LNG2` | Hanja |
| `KC_LANGUAGE_3` | `KC_LNG3` | JIS Katakana |
| `KC_LANGUAGE_4` | `KC_LNG4` | JIS Hiragana |
| `KC_LANGUAGE_5` | `KC_LNG5` | JIS Zenkaku/Hankaku |
| `KC_LANGUAGE_6/7/8/9` | `KC_LNG6/7/8/9` | Language 6–9 |

---

## 5. Mod-Tap (`MT`) and Modifier Combos

### Summary

`MT(mod, kc)` is a **dual-role key**: acts as modifier `mod` when *held*, sends `kc` when *tapped*. The canonical use is home-row mods (e.g. `LGUI_T(KC_A)` = A on tap, GUI on hold).

### Mod-Tap mod constants (`MOD_*` prefix, NOT `KC_*`)

| Mod | Description |
|-----|-------------|
| `MOD_LCTL` | Left Control |
| `MOD_LSFT` | Left Shift |
| `MOD_LALT` | Left Alt |
| `MOD_LGUI` | Left GUI |
| `MOD_RCTL` | Right Control |
| `MOD_RSFT` | Right Shift |
| `MOD_RALT` | Right Alt (AltGr) |
| `MOD_RGUI` | Right GUI |
| `MOD_HYPR` | Hyper = LCTL+LSFT+LALT+LGUI |
| `MOD_MEH` | Meh = LCTL+LSFT+LALT |

Combine by ORing: `MT(MOD_LCTL | MOD_LSFT, KC_ESC)`.

### Mod-Tap shortcut macros

| Key | Aliases | Held mods | 
|-----|---------|-----------|
| `LCTL_T(kc)` | `CTL_T(kc)` | LCTL |
| `LSFT_T(kc)` | `SFT_T(kc)` | LSFT |
| `LALT_T(kc)` | `ALT_T(kc)`, `LOPT_T(kc)`, `OPT_T(kc)` | LALT |
| `LGUI_T(kc)` | `GUI_T(kc)`, `LCMD_T(kc)`, `LWIN_T(kc)`, `CMD_T(kc)`, `WIN_T(kc)` | LGUI |
| `LCS_T(kc)` | | LCTL+LSFT |
| `LCA_T(kc)` | | LCTL+LALT |
| `LCG_T(kc)` | | LCTL+LGUI |
| `LSA_T(kc)` | | LSFT+LALT |
| `LSG_T(kc)` | | LSFT+LGUI |
| `LAG_T(kc)` | | LALT+LGUI |
| `LCSG_T(kc)` | | LCTL+LSFT+LGUI |
| `LCAG_T(kc)` | | LCTL+LALT+LGUI |
| `LSAG_T(kc)` | | LSFT+LALT+LGUI |
| `RCTL_T(kc)` | | RCTL |
| `RSFT_T(kc)` | | RSFT |
| `RALT_T(kc)` | `ROPT_T(kc)`, `ALGR_T(kc)` | RALT |
| `RGUI_T(kc)` | `RCMD_T(kc)`, `RWIN_T(kc)` | RGUI |
| `RCS_T(kc)`, `RCA_T(kc)`, `RCG_T(kc)`, `RSA_T(kc)`, `RSG_T(kc)`, `RAG_T(kc)`, `RCSG_T(kc)`, `RCAG_T(kc)`, `RSAG_T(kc)` | | Right-side combos (mirrors of the `L*` set) |
| `MEH_T(kc)` | | LCTL+LSFT+LALT |
| `HYPR_T(kc)` | | LCTL+LSFT+LALT+LGUI |

### Mod-Tap caveats (16-bit packing, same root cause as `LT`/`LM`)

- **`kc` arg limited to Basic Keycodes** (≤ `0xFF`). **Cannot** use `LCTL(...)`, `KC_TILD`/`KC_DQUO` (US-ANSI-shifted aliases), other mod-taps, or anything `> 0xFF`. (3 bits function id, 1 bit L/R, 4 bits mods, 8 bits keycode.)
- **Cannot mix left & right mods:** any right-hand mod in the combo converts *all* mods to right-hand. (`MOD_LCTL | MOD_RSFT` → RCTL+RSFT.)
- **Remote Desktop (Windows) issue:** mod-taps send events faster than a human; RDC may drop them. Fix: RDC → Show Options → Local Resources → keyboard → "On this Computer". Can also be mitigated by raising `TAP_CODE_DELAY` (see `03-config-and-info-json.md`).

### Intercepting Mod-Taps / Layer-Taps in `process_record_user`

When you need a tap/hold keycode outside the Basic set, intercept it. Key tool: `record->tap.count` (nonzero ⇒ it's being treated as a tap).

```c
// Work around KC_DQUO limitation on a mod-tap (tap → send KC_DQUO manually)
bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case LCTL_T(KC_DQUO):
            if (record->tap.count && record->event.pressed) {
                tap_code16(KC_DQUO);   // send on tap
                return false;          // stop further processing
            }
            break;                     // fall through → normal hold (LCTL) behavior
    }
    return true;
}
```

```c
// Use LT(0, kc) (layer 0 always active, so the "layer" is useless) to add hold-actions:
bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case LT(0, KC_X):
            if (!record->tap.count && record->event.pressed) {
                tap_code16(C(KC_X));   // hold → Ctrl-X
                return false;
            }
            return true;               // tap → normal KC_X
        case LT(0, KC_C): /* ... C(KC_C) ... */ return true;
        case LT(0, KC_V): /* ... C(KC_V) ... */ return true;
    }
    return true;
}
```

### Modifier combos (one-shot-with-key, not dual-role)

These hold a modifier *for the duration of the keypress* (modifier down → `kc` down → `kc` up → modifier up). Distinct from `MT` (dual-role tap/hold). Source: `feature_advanced_keycodes.md`.

| Key | Aliases | Mods held |
|-----|---------|-----------|
| `LCTL(kc)` | `C(kc)` | LCTL |
| `LSFT(kc)` | `S(kc)` | LSFT |
| `LALT(kc)` | `A(kc)`, `LOPT(kc)` | LALT |
| `LGUI(kc)` | `G(kc)`, `LCMD(kc)`, `LWIN(kc)` | LGUI |
| `LCS(kc)` | | LCTL+LSFT |
| `LCA(kc)` | | LCTL+LALT |
| `LCG(kc)` | | LCTL+LGUI |
| `LSA(kc)` | | LSFT+LALT |
| `LSG(kc)` | | LSFT+LGUI |
| `LAG(kc)` | | LALT+LGUI |
| `LCSG(kc)` | | LCTL+LSFT+LGUI |
| `LCAG(kc)` | | LCTL+LALT+LGUI |
| `LSAG(kc)` | | LSFT+LALT+LGUI |
| `RCTL(kc)`, `RSFT(kc)`, `RALT(kc)` (`ROPT`/`ALGR`), `RGUI(kc)` (`RCMD`/`RWIN`) | | right-side singles |
| `RCA/RCS/RCG/RSA/RSG/RAG/RCSG/RCAG/RSAG(kc)` | | right-side combos |
| `MEH(kc)` | | LCTL+LSFT+LALT |
| `HYPR(kc)` | | LCTL+LSFT+LALT+LGUI |

Chainable: `LCTL(LALT(KC_DEL))`, `C(A(KC_DEL))`, and `LCA(KC_DEL)` all send Ctrl+Alt+Del.

> **These mod-combo keycodes (e.g. `C_S_T`, `C(KC_X)` style) cannot be used as the `kc` of `MT`/`LT`** because they exceed the Basic keycode range — see §10 and the intercepting pattern above.

### Checking & manipulating modifier state

Modifier byte layout: `(GASC)_R (GASC)_L` — e.g. `01000010` = LShift+RAlt.

| Function | Purpose |
|----------|---------|
| `get_mods()` | Current normal+modtap mods (uint8). |
| `get_oneshot_mods()` | Current one-shot mods (unless held → acts like normal). |
| `add_mods(m)` / `register_mods(m)` | Enable `m` (latter sends report immediately). |
| `del_mods(m)` / `unregister_mods(m)` | Disable `m` (latter sends report immediately). |
| `set_mods(m)` | Overwrite mod state. |
| `clear_mods()` | Clear all mods. |
| `add_oneshot_mods(m)` / `del_oneshot_mods(m)` / `set_oneshot_mods(m)` / `clear_oneshot_mods()` | One-shot mod equivalents. |

**Mod masks** (use `MOD_MASK_*` to match both sides; `MOD_BIT(KC_xxx)` to match one specific side):

`MOD_MASK_CTRL`, `MOD_MASK_SHIFT`, `MOD_MASK_ALT`, `MOD_MASK_GUI`, `MOD_MASK_CS`, `MOD_MASK_CA`, `MOD_MASK_CG`, `MOD_MASK_SA`, `MOD_MASK_SG`, `MOD_MASK_AG`, `MOD_MASK_CSA`, `MOD_MASK_CSG`, `MOD_MASK_CAG`, `MOD_MASK_SAG`, `MOD_MASK_CSAG`.

- Match either side: `get_mods() & MOD_MASK_SHIFT`.
- Match one side: `get_mods() & MOD_BIT(KC_LSFT)`.
- Match *exactly* a set: `get_mods() == (MOD_BIT(KC_LCTL) | MOD_BIT(KC_LSFT))`.

```c
// Shift+Backspace → Delete (cancel shift while sending KC_DEL, restore after)
uint8_t mod_state;
bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    mod_state = get_mods();
    switch (keycode) {
        case KC_BSPC: {
            static bool delkey_registered;
            if (record->event.pressed) {
                if (mod_state & MOD_MASK_SHIFT) {
                    del_mods(MOD_MASK_SHIFT);
                    register_code(KC_DEL);
                    delkey_registered = true;
                    set_mods(mod_state);
                    return false;
                }
            } else if (delkey_registered) {
                unregister_code(KC_DEL);
                delkey_registered = false;
                return false;
            }
            return true;
        }
    }
    return true;
}
```

> This Shift+BSPC→DEL can also be done declaratively via **Key Overrides** — see `05-text-input-and-combos.md`.

---

## 6. One-Shot Keys (`OSM` / `OSL`)

### Summary

One-shot keys ("sticky keys") stay active until the **next keypress**, then release. Lets you type combos one key at a time: tap `OSM(MOD_LSFT)`, release, then tap `KC_A` → sends `A` (shift applied only to that one key). They also work as normal modifiers if *held* — releasing the held one-shot immediately ends it.

### Enable / config

No feature flag needed beyond defaults; behavior tuned via `config.h`:

| Define | Type | Default | Meaning |
|--------|------|---------|---------|
| `ONESHOT_TAP_TOGGLE` | int (count) | 5 | Tapping a one-shot key this many times **locks** it on (until tapped again). Applies to both `OSM` and `OSL`. |
| `ONESHOT_TIMEOUT` | ms | 5000 | Time before an un-consumed one-shot auto-releases. |

### Keycodes

| Key | Aliases | Description |
|-----|---------|-------------|
| `OSM(mod)` | | Hold `mod` for one keypress. `mod` uses `MOD_*` prefix (e.g. `OSM(MOD_LCTL \| MOD_LSFT)`). |
| `OSL(layer)` | | Switch to `layer` for one keypress. |
| `OS_LCTL`, `OS_LSFT`, `OS_LALT`, `OS_LGUI` | | One-shot single left mods. |
| `OS_LCS`, `OS_LCA`, `OS_LCG`, `OS_LSA`, `OS_LSG`, `OS_LAG`, `OS_LCSG`, `OS_LCAG`, `OS_LSAG` | | One-shot left-mod combos. |
| `OS_RCTL`, `OS_RSFT`, `OS_RALT`, `OS_RGUI` | | One-shot single right mods. |
| `OS_RCS`, `OS_RCA`, `OS_RCG`, `OS_RSA`, `OS_RSG`, `OS_RAG`, `OS_RCSG`, `OS_RCAG`, `OS_RSAG` | | One-shot right-mod combos. |
| `OS_MEH` | | One-shot LCTL+LSFT+LALT. |
| `OS_HYPR` | | One-shot LCTL+LSFT+LALT+LGUI. |
| `QK_ONE_SHOT_TOGGLE` | `OS_TOGG` | Toggle one-shot keys on/off globally. |
| `QK_ONE_SHOT_ON` | `OS_ON` | Turn one-shot keys on. |
| `QK_ONE_SHOT_OFF` | `OS_OFF` | Turn one-shot keys off. |

> When one-shot keys are turned off (`OS_OFF`), `OSM()` behaves like a normal modifier and `OSL()` behaves like `MO()`.

### C API for one-shot (macros / tap dance)

| Function | Purpose |
|----------|---------|
| `set_oneshot_mods(MOD_BIT(KC_*))` | Activate a one-shot mod programmatically. |
| `clear_oneshot_mods()` | Cancel current one-shot mod. |
| `set_oneshot_layer(LAYER, ONESHOT_START)` | Activate one-shot layer (call on key-down). |
| `clear_oneshot_layer_state(ONESHOT_PRESSED)` | Mark layer consumed (call on key-up). |
| `reset_oneshot_layer()` | Cancel the one-shot layer. |

### Callbacks

| Callback | Fires when |
|----------|------------|
| `oneshot_mods_changed_user(uint8_t mods)` / `_kb` | Any one-shot mod toggles on or off. `mods` = post-change state. |
| `oneshot_locked_mods_changed_user(uint8_t mods)` / `_kb` | A one-shot mod is locked via tap-toggle. |
| `oneshot_layer_changed_user(uint8_t layer)` / `_kb` | One-shot layer changes. `layer == 0` ⇒ all one-shot layers off. (For *any* layer change, prefer `layer_state_set_user`.) |

### Gotchas (one-shot)

- **`OSM()` arg must use `MOD_*` prefix**, not `KC_*`.
- **Remote Desktop (Windows):** OSM may not translate over RDC. Same Local Resources → "On this Computer" fix as mod-taps.
- One-shot layer is **only ever one layer deep** at a time (tapping another `OSL` while one is pending replaces it).
- Tap-toggle (locking) requires `ONESHOT_TAP_TOGGLE` defined and is governed by `QUICK_TAP_TERM` timing (see §7).

---

## 7. Tap-Hold Configuration

> Source: `tap_hold.md`. These options apply to **Mod-Tap `MT`**, **Layer-Tap `LT`**, layer tap-toggle **`TT`**, one-shot **`OSM`/`OSL`**, and Swap Hands **`SH_T`/`SH_TT`**. They do **NOT** apply to Tap Dance (which has its own simpler decision logic and ignores permissive/chordal/etc.).

### Tapping term (the core knob)

| Define / key | Type | Default | Meaning |
|--------------|------|---------|---------|
| `TAPPING_TERM` | ms | **200** | Global threshold: hold longer than this ⇒ hold action. Below ⇒ tap decision is still possible. |
| `TAPPING_TERM_PER_KEY` | flag | off | Enable per-key tapping term via `get_tapping_term()`. |

Per-key:

```c
#define TAPPING_TERM_PER_KEY
uint16_t get_tapping_term(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case SFT_T(KC_SPC): return TAPPING_TERM + 1250;
        case LT(1, KC_GRV): return 130;
        default:            return TAPPING_TERM;
    }
}
```

Filter helpers: compare against ranges `QK_MOD_TAP ... QK_MOD_TAP_MAX` and `QK_LAYER_TAP ... QK_LAYER_TAP_MAX`; use `QK_MOD_TAP_GET_MODS`, `QK_LAYER_MOD_GET_MODS`, `QK_ONE_SHOT_MOD_GET_MODS` to filter by mods.

### Dynamic tapping term (runtime tuning)

Enable in `rules.mk`: `DYNAMIC_TAPPING_TERM_ENABLE = yes`.

| Key | Aliases | Description |
|-----|---------|-------------|
| `QK_DYNAMIC_TAPPING_TERM_PRINT` | `DT_PRNT` | Types current tapping term (ms). |
| `QK_DYNAMIC_TAPPING_TERM_UP` | `DT_UP` | +`DYNAMIC_TAPPING_TERM_INCREMENT` (default 5ms). |
| `QK_DYNAMIC_TAPPING_TERM_DOWN` | `DT_DOWN` | −`DYNAMIC_TAPPING_TERM_INCREMENT`. |

> Adjustments are **not persistent** — once you find a value, copy it into `#define TAPPING_TERM`. If using per-key terms with dynamic tuning, replace `TAPPING_TERM` with the runtime variable `g_tapping_term` inside `get_tapping_term()`, or changes won't take effect. Use `GET_TAPPING_TERM(keycode, record)` macro to access from elsewhere.

### Tap-or-hold decision modes (three, increasing hold preference)

Until the decision completes, key events are **delayed** (not sent to host immediately). Default mode gives the most delay.

| Mode | Define | Selects hold when… |
|------|--------|--------------------|
| **Default** | (none) | Held longer than `TAPPING_TERM`. Other keys pressed meanwhile do **not** influence the decision. Most delay. |
| **Permissive Hold** | `PERMISSIVE_HOLD` (+ `PERMISSIVE_HOLD_PER_KEY` / `get_permissive_hold()`) | Default behavior **plus**: another key is *tapped* (pressed AND released) while the dual-role key is held, even before `TAPPING_TERM`. Converts **nested** sequences (ABBA) but **not** rolls (ABAB). |
| **Hold On Other Key Press** | `HOLD_ON_OTHER_KEY_PRESS` (+ `_PER_KEY` / `get_hold_on_other_key_press()`) | Default behavior **plus**: another key is *pressed* while held (release not required). Converts **both** nested and rolling sequences. Takes precedence over Permissive Hold. |

**Decision-mode comparison** (`LSFT_T(KC_A)` + `KC_B`, `TAPPING_TERM=200`):

- **Distinct taps (AABB), A released at 199ms:** all three modes → `a` then `ab`.
- **Nested (ABBA), B pressed 110 / released 120, A released 199:** Default → `ab`; Permissive → `B`; HoldOnOtherKey → `B` (on B-down at 110).
- **Rolling (ABAB), B pressed 110, A released 130, B released 140:** Default → `ab`; Permissive → `ab` (still a roll, not nested); HoldOnOtherKey → `B`.

> Enabling both `PERMISSIVE_HOLD` and `HOLD_ON_OTHER_KEY_PRESS` is redundant — the latter dominates.

### Quick Tap Term (auto-repeat control)

| Define / key | Type | Default | Meaning |
|--------------|------|---------|---------|
| `QUICK_TAP_TERM` | ms | `TAPPING_TERM` (max allowed) | Window after a tap within which a re-press auto-repeats the *tap* action (not hold). Set `0` to **disable auto-repeat** (second press always = hold). |
| `QUICK_TAP_TERM_PER_KEY` | flag | off | Per-key via `get_quick_tap_term()`. |

```c
#define QUICK_TAP_TERM 120
#define QUICK_TAP_TERM_PER_KEY
uint16_t get_quick_tap_term(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case SFT_T(KC_SPC): return QUICK_TAP_TERM - 20;
        default:            return QUICK_TAP_TERM;
    }
}
```

> **`QUICK_TAP_TERM` also governs tap-toggle behavior** of `TT(layer)` and one-shot tap-toggle. `TT`'s toggling **requires** Quick Tap enabled (`QUICK_TAP_TERM != 0`, or per-key `get_quick_tap_term()` returning non-zero for the `TT` key). If `QUICK_TAP_TERM > TAPPING_TERM`, it's clamped to `TAPPING_TERM`.

### Retro Tapping

| Define | Type | Default | Meaning |
|--------|------|---------|---------|
| `RETRO_TAPPING` | flag | off | If you hold & release a dual-role key **without** pressing any other key, send the *tap* keycode anyway (even past `TAPPING_TERM`). Normally nothing is sent. |
| `RETRO_TAPPING_PER_KEY` | flag | off | Per-key via `get_retro_tapping()`. |

```c
#define RETRO_TAPPING_PER_KEY
bool get_retro_tapping(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case LT(2, KC_SPC): return true;
        default: return false;
    }
}
```

**`DUMMY_MOD_NEUTRALIZER_KEYCODE`** — some OSes bind actions to a lone mod tap (e.g. tap GUI → Start menu). Retro-tapping can falsely fire these. Define a "neutralizer" (a basic unmodified HID keycode like `KC_RIGHT_CTRL` or `KC_F18`; **not** `KC_NO`/`KC_TRNS`/`KC_PIPE`) sent between the mod's register/unregister to suppress the false trigger. `MODS_TO_NEUTRALIZE` (a brace-list of 8-bit mod masks, e.g. `MOD_BIT(KC_LEFT_ALT)`) selects which mods to neutralize (default: LAlt + LGUI). **Do not** use `MOD_LSFT`-style 5-bit constants here — use `MOD_BIT()` or `MOD_MASK_*`.

> **Retro Shift** is Auto Shift's analogue of retro tapping — see `05-text-input-and-combos.md` (auto_shift).

### Flow Tap (disable holds during fast typing)

| Define / key | Type | Default | Meaning |
|--------------|------|---------|---------|
| `FLOW_TAP_TERM` | ms | off (undefined) | When a tap-hold key is pressed within this many ms of the *previous* keypress, force the **tap** action (disables accidental holds while fast-typing). Recommended start: 150. |

Default Flow Tap active when: tap-hold key pressed within `FLOW_TAP_TERM` of prev key, AND both keys' tap keycodes are in `KC_A`…`KC_Z`, `KC_COMM`, `KC_DOT`, `KC_SCLN`, `KC_SLSH`, or `KC_SPC`. Temporarily disabled while a tap-hold key is undecided (so you can still chord mods).

Callbacks:

```c
bool is_flow_tap_key(uint16_t keycode);   // default restricts to alphas+space+., ;/
uint16_t get_flow_tap_term(uint16_t keycode, keyrecord_t* record, uint16_t prev_keycode);  // return 0 to disable
```

If you define both, `get_flow_tap_term()` takes precedence.

### Chordal Hold (opposite-hands rule)

| Define | Type | Default | Meaning |
|--------|------|---------|---------|
| `CHORDAL_HOLD` | flag | off | If a tap-hold key and the next key are on the **same hand**, settle as **tapped** immediately. Intended to be combined with Permissive Hold or Hold On Other Key Press for the opposite-hand case. |

- Same hand → tapped (immediately, on the other key's press).
- Opposite hands → defer to `HOLD_ON_OTHER_KEY_PRESS` (held on press) or `PERMISSIVE_HOLD` (held on nested release).
- No effect after `TAPPING_TERM`.
- **Combos are exempt** (handedness ill-defined).
- **Exception:** multiple same-side modifiers can combine within tapping term (enables e.g. Ctrl+Shift+V where J,K right and V left).

Handedness sources (later ones take precedence): auto-guessed from geometry → `chordal_hold_layout[MATRIX_ROWS][MATRIX_COLS]` (`'L'`/`'R'`/`'*'`-exempt, using the keyboard's `LAYOUT` macro) → `keyboard.json` `"hand"` field (`"L"`/`"R"`/`"*"`, first layout only) → `chordal_hold_handedness(keypos_t key)` function.

Per-chord override:

```c
bool get_chordal_hold(uint16_t tap_hold_keycode, keyrecord_t* tap_hold_record,
                      uint16_t other_keycode, keyrecord_t* other_record) {
    switch (tap_hold_keycode) {
        case LCTL_T(KC_Z):
            if (other_keycode == KC_C || other_keycode == KC_V) return true;
            break;
    }
    return get_chordal_hold_default(tap_hold_record, other_record);  // default opposite-hands rule
}
```

### Speculative Hold (responsive mod-taps, e.g. Shift+Click)

| Define | Type | Default | Meaning |
|--------|------|---------|---------|
| `SPECULATIVE_HOLD` | flag | off | Apply the modifier **instantly on keydown**, before the tap/hold decision. If later tapped, cancel the speculative mod just before sending the tap keycode. Eliminates lag for Shift+Click etc. Compatible with all other tap-hold options. |

By default applies to mod-taps with Shift, Ctrl, or Shift+Ctrl. Override with `get_speculative_hold()`:

```c
bool get_speculative_hold(uint16_t keycode, keyrecord_t* record) {
    switch (keycode) {
        case LCTL_T(KC_ESC):
        case LSFT_T(KC_Z):
        case RSFT_T(KC_SLSH): return true;
    }
    return false;
}
```

**"Flashing mods" mitigation** (Speculative Hold can falsely fire lone-mod actions like tap-GUI → Start menu):

- `DUMMY_MOD_NEUTRALIZER_KEYCODE` (+ `MODS_TO_NEUTRALIZE`) — same as Retro Tapping.
- `SPECULATIVE_HOLD_ONE_KEY` — don't speculate when any mod is already active.
- `SPECULATIVE_HOLD_FLOW_TERM <ms>` — don't speculate within N ms of the previous keypress (like Flow Tap, but only gates speculation).
- Or use Flow Tap itself (settles immediately during fast typing → no speculation).

### Why no `_kb`/`_user` variants for tap-hold callbacks?

Unlike most QMK hooks, the per-key tap-hold functions (`get_tapping_term`, `get_permissive_hold`, `get_hold_on_other_key_press`, `get_quick_tap_term`, `get_retro_tapping`, `get_chordal_hold`, `get_speculative_hold`, `is_flow_tap_key`, `get_flow_tap_term`) are **user-level only** — there's no keyboard-level variant, so no `_kb`/`_user` suffix distinction.

### Home row mods (HRM) recommended starting config

```c
#define TAPPING_TERM 250
#define PERMISSIVE_HOLD     // tap another key while holding → mod triggers
#define CHORDAL_HOLD        // holds only on opposite-hand combos
// #define FLOW_TAP_TERM 150 // disables holds during fast typing
```

Plus consider `SPECULATIVE_HOLD` for lag-free Shift+Click. There is no universal best config — it depends on typing speed/habits.

---

## 8. Quantum Keycodes

> Source: `quantum_keycodes.md` + `keycodes.md`. Quantum keycodes occupy `0x0100`–`0xFFFF` (the range above basic keycodes `0x0000`–`0x00FF`). User custom keycodes also live here (start at `QK_USER`, or legacy `SAFE_RANGE`).

| Key | Aliases | Description |
|-----|---------|-------------|
| `QK_BOOTLOADER` | `QK_BOOT` | Put keyboard into bootloader mode for flashing. |
| `QK_DEBUG_TOGGLE` | `DB_TOGG` | Toggle debug mode. |
| `QK_CLEAR_EEPROM` | `EE_CLR` | Reinitialize EEPROM (persistent memory). Last-resort escape from bad config. |
| `QK_MAKE` | — | Sends `qmk compile -kb (kb) -km (km)`; `qmk flash` if Shift held; bootloader if Shift+Ctrl held. **Requires `#define ENABLE_COMPILE_KEYCODE` in `config.h`.** |
| `QK_REBOOT` | `QK_RBT` | Reset keyboard (does NOT load bootloader). |

> See `keycodes.md` (the master index) for the full per-feature keycode tables — most feature keycodes (audio, backlight, RGB/LED matrix, bluetooth, dynamic macros, grave esc, joystick, layer lock, leader, magic, MIDI, mouse keys, etc.) are documented in their own reference files: `05-text-input-and-combos.md`, `06-pointing-and-hid-devices.md`, `07-led-rgb-backlight.md`, `09-audio-haptic.md`, `10-connectivity.md`, `11-other-features.md`. The **Magic** and **layer-switch** keycode sets are reproduced in full below because they are keymap-core.

---

## 9. Magic Keycodes (runtime Bootmagic-equivalent)

> Source: `keycodes_magic.md`. Prefixed `QK_MAGIC_` (legacy `MAGIC_`). These expose the deprecated **Bootmagic** feature's functionality *after* keyboard init, by assigning keycodes in the keymap. They modify persistent (EEPROM) state for things like key swaps and NKRO.

| Key | Aliases | Description |
|-----|---------|-------------|
| `QK_MAGIC_SWAP_CONTROL_CAPS_LOCK` | `CL_SWAP` | Swap Caps Lock and Left Control |
| `QK_MAGIC_UNSWAP_CONTROL_CAPS_LOCK` | `CL_NORM` | Unswap CapsLock/LCtrl |
| `QK_MAGIC_TOGGLE_CONTROL_CAPS_LOCK` | `CL_TOGG` | Toggle that swap |
| `QK_MAGIC_CAPS_LOCK_AS_CONTROL_ON` | `CL_CTRL` | Treat Caps Lock as Control |
| `QK_MAGIC_CAPS_LOCK_AS_CONTROL_OFF` | `CL_CAPS` | Stop treating Caps Lock as Control |
| `QK_MAGIC_SWAP_ESCAPE_CAPS_LOCK` | `EC_SWAP` | Swap Caps Lock and Escape |
| `QK_MAGIC_UNSWAP_ESCAPE_CAPS_LOCK` | `EC_NORM` | Unswap Caps/Escape |
| `QK_MAGIC_TOGGLE_ESCAPE_CAPS_LOCK` | `EC_TOGG` | Toggle Caps/Escape swap |
| `QK_MAGIC_SWAP_LCTL_LGUI` | `CG_LSWP` | Swap Left Control and GUI |
| `QK_MAGIC_UNSWAP_LCTL_LGUI` | `CG_LNRM` | Unswap LCTL/LGUI |
| `QK_MAGIC_SWAP_RCTL_RGUI` | `CG_RSWP` | Swap Right Control and GUI |
| `QK_MAGIC_UNSWAP_RCTL_RGUI` | `CG_RNRM` | Unswap RCTL/RGUI |
| `QK_MAGIC_SWAP_CTL_GUI` | `CG_SWAP` | Swap Control and GUI (both sides) |
| `QK_MAGIC_UNSWAP_CTL_GUI` | `CG_NORM` | Unswap Control/GUI (both sides) |
| `QK_MAGIC_TOGGLE_CTL_GUI` | `CG_TOGG` | Toggle Control/GUI swap |
| `QK_MAGIC_SWAP_LALT_LGUI` | `AG_LSWP` | Swap Left Alt and GUI |
| `QK_MAGIC_UNSWAP_LALT_LGUI` | `AG_LNRM` | Unswap LALT/LGUI |
| `QK_MAGIC_SWAP_RALT_RGUI` | `AG_RSWP` | Swap Right Alt and GUI |
| `QK_MAGIC_UNSWAP_RALT_RGUI` | `AG_RNRM` | Unswap RALT/RGUI |
| `QK_MAGIC_SWAP_ALT_GUI` | `AG_SWAP` | Swap Alt and GUI (both sides) — "Apple/Cmd" swap |
| `QK_MAGIC_UNSWAP_ALT_GUI` | `AG_NORM` | Unswap Alt/GUI (both sides) |
| `QK_MAGIC_TOGGLE_ALT_GUI` | `AG_TOGG` | Toggle Alt/GUI swap |
| `QK_MAGIC_GUI_OFF` | `GU_OFF` | Disable GUI keys (gaming) |
| `QK_MAGIC_GUI_ON` | `GU_ON` | Enable GUI keys |
| `QK_MAGIC_TOGGLE_GUI` | `GU_TOGG` | Toggle GUI keys |
| `QK_MAGIC_SWAP_GRAVE_ESC` | `GE_SWAP` | Swap `` ` `` and Escape |
| `QK_MAGIC_UNSWAP_GRAVE_ESC` | `GE_NORM` | Unswap `` ` ``/Escape |
| `QK_MAGIC_SWAP_BACKSLASH_BACKSPACE` | `BS_SWAP` | Swap `\` and Backspace |
| `QK_MAGIC_UNSWAP_BACKSLASH_BACKSPACE` | `BS_NORM` | Unswap `\`/Backspace |
| `QK_MAGIC_TOGGLE_BACKSLASH_BACKSPACE` | `BS_TOGG` | Toggle `\`/Backspace swap |
| `QK_MAGIC_NKRO_ON` | `NK_ON` | Enable N-key rollover |
| `QK_MAGIC_NKRO_OFF` | `NK_OFF` | Disable N-key rollover |
| `QK_MAGIC_TOGGLE_NKRO` | `NK_TOGG` | Toggle NKRO |
| `QK_MAGIC_EE_HANDS_LEFT` | `EH_LEFT` | Set split master half = left (for `EE_HANDS`) |
| `QK_MAGIC_EE_HANDS_RIGHT` | `EH_RGHT` | Set split master half = right (for `EE_HANDS`) |

> **Magic vs Bootmagic:** Bootmagic is the *deprecated* init-time feature (hold keys during boot to configure). Magic keycodes are the supported runtime equivalent. See `11-other-features.md` for Bootmagic details and `17-faq-gotchas-breaking-changes.md` for deprecation status. `EE_HANDS` is a split-keyboard setting — see `10-connectivity.md`.

---

## 10. US-ANSI-Shifted Symbols (critical caveats)

> Source: `keycodes_us_ansi_shifted.md`. These keycodes are **NOT real keycodes** — they are aliases for `LSFT(kc)`. They send Left Shift + the unshifted keycode, **not** the symbol directly. The OS interprets the shift+base combination according to the active *host* layout.

| Key | Aliases | Symbol |
|-----|---------|--------|
| `KC_TILDE` | `KC_TILD` | `~` |
| `KC_EXCLAIM` | `KC_EXLM` | `!` |
| `KC_AT` | | `@` |
| `KC_HASH` | | `#` |
| `KC_DOLLAR` | `KC_DLR` | `$` |
| `KC_PERCENT` | `KC_PERC` | `%` |
| `KC_CIRCUMFLEX` | `KC_CIRC` | `^` |
| `KC_AMPERSAND` | `KC_AMPR` | `&` |
| `KC_ASTERISK` | `KC_ASTR` | `*` |
| `KC_LEFT_PAREN` | `KC_LPRN` | `(` |
| `KC_RIGHT_PAREN` | `KC_RPRN` | `)` |
| `KC_UNDERSCORE` | `KC_UNDS` | `_` |
| `KC_PLUS` | | `+` |
| `KC_LEFT_CURLY_BRACE` | `KC_LCBR` | `{` |
| `KC_RIGHT_CURLY_BRACE` | `KC_RCBR` | `}` |
| `KC_PIPE` | | `\|` |
| `KC_COLON` | `KC_COLN` | `:` |
| `KC_DOUBLE_QUOTE` | `KC_DQUO`, `KC_DQT` | `"` |
| `KC_LEFT_ANGLE_BRACKET` | `KC_LABK`, `KC_LT` | `<` |
| `KC_RIGHT_ANGLE_BRACKET` | `KC_RABK`, `KC_GT` | `>` |
| `KC_QUESTION` | `KC_QUES` | `?` |

### Gotchas (US-ANSI-shifted)

- **Cannot be used in Mod-Taps (`MT`) or Layer-Taps (`LT`).** They are 16-bit `LSFT(kc)` values; the modifier bits get masked/ignored by `MT`/`LT`'s 8-bit `kc` field. Work around via `process_record_user` interception (§5) or Tap Dance.
- **Layout-dependent:** on a non-US host layout they may produce the wrong character (since they're really "Shift + base key").
- **Remote Desktop (Windows):** they send shift very fast; RDC may drop them. Fix: RDC → Local Resources → keyboard → "On this Computer".
- Contrast with the **basic** shifted pairs (e.g. `KC_1` sends `1` unshifted and `!` when Shift is *actually* held) — those ARE plain HID keycodes and work fine inside `MT`/`LT`. The trap is specifically the `KC_TILD`-style aliases.

---

## 11. Language Keymap Extras (International Layouts)

> Source: `reference_keymap_extras.md`. **Mechanism:** the keyboard sends numerical HID codes; the **OS** maps them to characters based on the host's configured layout (US ANSI by default). QMK provides *language-specific keycode aliases* so your keymap reads like the keycaps (e.g. `SE_ARNG` for Swedish `å`, which actually sends `KC_LBRC`). They are labels, not magic — **you must still set the matching layout in the OS.**

### Selecting a host layout

In `keymap.c`, include the keycodes header:

```c
#include QMK_KEYBOARD_H
#include "keymap_japanese.h"   // gives you JP_* aliases
```

Or, in `keymap.json`, set `host_language` (data-driven):

```json
{
    "keyboard": "handwired/my_macropad",
    "keymap": "my_keymap",
    "host_language": "swedish",
    "layout": "LAYOUT_all",
    "layers": [ ["SE_ARNG"] ]
}
```

Available `host_language` values are those layouts with a _Sendstring LUT Header_ in the table below.

### Sendstring support

`SEND_STRING()` assumes US ANSI by default. To use a different layout's ASCII→keycode lookup table, include the corresponding `sendstring_*.h` (this implicitly includes the `keymap_*.h` too — don't include both).

- `SEND_STRING()` operates on **ASCII only** — no Unicode/ accented characters.
- Many layouts make Grave/Tilde **dead keys**; add a space after them in the string to prevent combining with the next char.
- Non-Latin layouts (Greek, Russian, etc.) have no Sendstring header (can't input most ASCII).

### Header files (in `quantum/keymap_extras/`)

| Layout | Keycodes Header | Sendstring LUT Header |
|--------|-----------------|----------------------|
| Canadian Multilingual (CSA) | `keymap_canadian_multilingual.h` | `sendstring_canadian_multilingual.h` |
| Croatian | `keymap_croatian.h` | `sendstring_croatian.h` |
| Czech | `keymap_czech.h` | `sendstring_czech.h` |
| Czech (macOS ANSI) | `keymap_czech_mac_ansi.h` | `sendstring_czech_mac_ansi.h` |
| Czech (macOS ISO) | `keymap_czech_mac_iso.h` | `sendstring_czech_mac_iso.h` |
| Danish | `keymap_danish.h` | `sendstring_danish.h` |
| Dutch (Belgium) / French (Belgium) | `keymap_belgian.h` | `sendstring_belgian.h` |
| English (Ireland) | `keymap_irish.h` | |
| English (UK) | `keymap_uk.h` | `sendstring_uk.h` |
| English (US Extended) | `keymap_us_extended.h` | |
| English (US International) | `keymap_us_international.h` | `sendstring_us_international.h` |
| English (US International, Linux) | `keymap_us_international_linux.h` | |
| Estonian | `keymap_estonian.h` | `sendstring_estonian.h` |
| EurKEY | `keymap_eurkey.h` | |
| Farsi | `keymap_farsi.h` | |
| Finnish | `keymap_finnish.h` | `sendstring_finnish.h` |
| French | `keymap_french.h` | `sendstring_french.h` |
| French (AFNOR) | `keymap_french_afnor.h` | `sendstring_french_afnor.h` |
| French (BÉPO) | `keymap_bepo.h` | `sendstring_bepo.h` |
| French (Canada) | `keymap_canadian_french.h` | `sendstring_canadian_french.h` |
| French (Switzerland) | `keymap_swiss_fr.h` | `sendstring_swiss_fr.h` |
| French (macOS ISO) | `keymap_french_mac_iso.h` | `sendstring_french_mac_iso.h` |
| German | `keymap_german.h` | `sendstring_german.h` |
| German (Switzerland) | `keymap_swiss_de.h` | `sendstring_swiss_de.h` |
| German (macOS) | `keymap_german_mac_iso.h` | `sendstring_german_mac_iso.h` |
| German (Neo2) | `keymap_neo2.h` | |
| Greek | `keymap_greek.h` | |
| Hebrew | `keymap_hebrew.h` | |
| Hungarian | `keymap_hungarian.h` | `sendstring_hungarian.h` |
| Icelandic | `keymap_icelandic.h` | `sendstring_icelandic.h` |
| Italian | `keymap_italian.h` | `sendstring_italian.h` |
| Italian (macOS ANSI) | `keymap_italian_mac_ansi.h` | `sendstring_italian_mac_ansi.h` |
| Italian (macOS ISO) | `keymap_italian_mac_iso.h` | `sendstring_italian_mac_iso.h` |
| Japanese | `keymap_japanese.h` | `sendstring_japanese.h` |
| Korean | `keymap_korean.h` | |
| Latvian | `keymap_latvian.h` | `sendstring_latvian.h` |
| Lithuanian (ĄŽERTY) | `keymap_lithuanian_azerty.h` | `sendstring_lithuanian_azerty.h` |
| Lithuanian (QWERTY) | `keymap_lithuanian_qwerty.h` | `sendstring_lithuanian_qwerty.h` |
| Norwegian | `keymap_norwegian.h` | `sendstring_norwegian.h` |
| Polish | `keymap_polish.h` | |
| Portuguese | `keymap_portuguese.h` | `sendstring_portuguese.h` |
| Portuguese (macOS ISO) | `keymap_portuguese_mac_iso.h` | `sendstring_portuguese_mac_iso.h` |
| Portuguese (Brazil) | `keymap_brazilian_abnt2.h` | `sendstring_brazilian_abnt2.h` |
| Romanian | `keymap_romanian.h` | `sendstring_romanian.h` |
| Russian | `keymap_russian.h` | |
| Serbian | `keymap_serbian.h` | |
| Serbian (Latin) | `keymap_serbian_latin.h` | `sendstring_serbian_latin.h` |
| Slovak | `keymap_slovak.h` | `sendstring_slovak.h` |
| Slovenian | `keymap_slovenian.h` | `sendstring_slovenian.h` |
| Spanish | `keymap_spanish.h` | `sendstring_spanish.h` |
| Spanish (Dvorak) | `keymap_spanish_dvorak.h` | `sendstring_spanish_dvorak.h` |
| Spanish (Latin America) | `keymap_spanish_latin_america.h` | `sendstring_spanish_latin_america.h` |
| Swedish | `keymap_swedish.h` | `sendstring_swedish.h` |
| Swedish (macOS ANSI / ISO) | `keymap_swedish_mac_ansi.h` / `keymap_swedish_mac_iso.h` | |
| Swedish Pro (macOS ANSI / ISO) | `keymap_swedish_pro_mac_ansi.h` / `keymap_swedish_pro_mac_iso.h` | |
| Turkish (F) / Turkish (Q) | `keymap_turkish_f.h` / `keymap_turkish_q.h` | `sendstring_turkish_f.h` / `sendstring_turkish_q.h` |
| Ukrainian | `keymap_ukrainian.h` | |

Non-language layout helpers (alternative key layouts — useful when not on QWERTY):

| Layout | Keycodes Header | Sendstring LUT Header |
|--------|-----------------|----------------------|
| Colemak | `keymap_colemak.h` | `sendstring_colemak.h` |
| Dvorak | `keymap_dvorak.h` | `sendstring_dvorak.h` |
| Dvorak (French) | `keymap_dvorak_fr.h` | `sendstring_dvorak_fr.h` |
| Dvorak (Programmer) | `keymap_dvorak_programmer.h` | `sendstring_dvorak_programmer.h` |
| Norman | `keymap_norman.h` | `sendstring_norman.h` |
| Plover / Plover (Dvorak) | `keymap_plover.h` / `keymap_plover_dvorak.h` | |
| Workman / Workman (ZXCVM) | `keymap_workman.h` / `keymap_workman_zxcvm.h` | `sendstring_workman.h` / `sendstring_workman_zxcvm.h` |

### Gotchas (keymap extras)

- **Aliases are labels, not behavior.** `SE_ARNG` literally sends `KC_LBRC`; the OS does the `å` mapping. If the OS layout is wrong, you get `[`.
- **Include only the `sendstring_*.h` OR the `keymap_*.h`, not both** when you want sendstring support (sendstring implies keymap).
- Dead keys in sendstrings need a trailing space.

---

## Appendix: Quick Decision Guide

**"I want a key that…"**

- …is a normal key: use a `KC_*` basic keycode (§4).
- …holds a modifier while pressed (one-shot combo like Ctrl+C on one key): `C(KC_C)` etc. (§5 modifier combos).
- …is a modifier when held, letter when tapped (home-row mod): `LCTL_T(KC_A)` etc. (§5 mod-tap).
- …switches layer while held: `MO(n)`. With a modifier too: `LM(n, MOD_LALT)`. Tap=key, hold=layer: `LT(n, kc)`.
- …toggles a layer: `TG(n)`. Replaces whole stack: `TO(n)`. One-shot layer: `OSL(n)`. Tap-toggle: `TT(n)`.
- …permanently changes base layout: `PDF(n)` (EEPROM) or `DF(n)` (until reboot).
- …is a shifted symbol like `{`: prefer holding real Shift + `KC_LBRC`; only use `KC_LCBR` if you understand it's `LSFT(...)` and **never inside `MT`/`LT`** (§10).
- …needs a non-basic keycode on a mod-tap/layer-tap tap: intercept in `process_record_user` via `record->tap.count` (§5).
- …is fully custom: `QK_USER` + handle in `process_record_user` (§1, §8).
