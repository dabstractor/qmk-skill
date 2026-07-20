# 11 — Other Features: Bootmagic, DIP Switches, Unicode, Stenography, WPM

A grab-bag of standalone QMK features that don't fit cleanly into the other reference clusters. Each section is self-contained: enable it, keycodes, config knobs, C API/callbacks, examples, and gotchas.

Cross-references:
- **`01-architecture.md`** — main loop, `process_record` chain order, matrix scan, EEPROM.
- **`03-config-and-info-json.md`** — `config.h` / `info.json` data-driven config, EEPROM, debounce.
- **`04-keymaps-and-keycodes.md`** — full keycode tables, **Magic keycodes** (the live-at-runtime replacement for the deprecated full Bootmagic), NKRO keycodes (`NK_ON`/`NK_OFF`/`NK_TOGG`), basic keycodes.
- **`10-connectivity.md`** — split keyboard sync, handedness (`SPLIT_HAND_PIN`, `EE_HANDS`), `os_detection`.
- **`16-userspace-development.md`** — external userspace, `custom_quantum_functions` (`_quantum`/`_kb`/`_user`), coding conventions. Community Modules build directly on this.

---

## Bootmagic

### Summary

Bootmagic lets you enter the bootloader (for flashing) by holding a specific key while plugging the keyboard in — essential for boards with no physical reset button. **The current QMK Bootmagic is "Bootmagic Lite"**: it does *only* the bootloader jump (plus an EEPROM reset, see gotchas). The older "full Bootmagic" — which configured runtime settings like NKRO, layer default, and key swaps at boot — is **deprecated**; those runtime behaviors now live in **Magic Keycodes** (see `04-keymaps-and-keycodes.md`) and the **Command** feature (`10-connectivity.md`).

> ⚠️ Despite the "Lite" name, the docs and `BOOTMAGIC_ENABLE` flag still just call the feature "Bootmagic." The "lite vs full" distinction is mostly historical: what shipped in QMK today is the lite behavior.

### Enable it

```make
# rules.mk
BOOTMAGIC_ENABLE = yes
```

Data-driven (`info.json`) equivalent:

```json
{
    "features": {
        "bootmagic": true
    }
}
```

`BOOTMAGIC_ENABLE` accepts the values `yes` / `no` / `lite` / `full`. **`full` is deprecated** and emits a warning; use `yes` (== modern lite behavior) or `lite`. On some keyboards Bootmagic is disabled by default and must be explicitly enabled.

### The trigger key position

Bootmagic checks a single physical matrix position (row, column) at boot. Configure it in `config.h`:

```c
#define BOOTMAGIC_ROW    0
#define BOOTMAGIC_COLUMN 0
// defaults: 0 and 0 (usually the "ESC" key on most keyboards)
```

Hold that key while plugging in to jump to the bootloader. **Just the single key.**

### Split keyboards

For split keyboards with predetermined handedness (`SPLIT_HAND_PIN` or `EE_HANDS`; see `10-connectivity.md`), each half has its own matrix and you may need a different trigger key for the right half. The right-half row/column is **not set by default** — define it explicitly:

```c
// Right-half trigger position (read from the keyboard's <keyboard>.h LAYOUT matrix)
#define BOOTMAGIC_ROW_RIGHT    4
#define BOOTMAGIC_COLUMN_RIGHT 4
```

To find the right values, inspect the key matrix in `<keyboard>.h` and pick the physical key, then map it to its row/column index in the C matrix array.

### Bootmagic Lite config

Beyond the basic trigger key, Bootmagic Lite honors a few `config.h` knobs:

| Define | Default | Meaning |
|---|---|---|
| `BOOTMAGIC_ROW` / `BOOTMAGIC_COLUMN` | `0` / `0` | Left-half trigger key position. |
| `BOOTMAGIC_ROW_RIGHT` / `BOOTMAGIC_COLUMN_RIGHT` | *(unset)* | Right-half trigger key position (split keyboards). |
| `BOOTMAGIC_LITE_EEPROM` | *(unset; EEPROM reset happens by default)* | Control EEPROM reset behavior. |
| `BOOTMAGIC_LITE_SKIP_EEPROM` / `BOOTMAGIC_NO_EEPROM` | *(unset)* | If set, **do not** reset EEPROM on the bootmagic key press (only jump to bootloader). Define this if you want to keep saved settings. |

> ⚠️ **Default behavior wipes EEPROM.** The standard warning from the docs: "Using Bootmagic will **always reset** the EEPROM, so you will lose any settings that have been saved." To preserve EEPROM while still jumping to the bootloader, define `BOOTMAGIC_NO_EEPROM` (or the equivalent skip flag for your build).

### C API / advanced override

`bootmagic_scan()` is a **weak** function — override it entirely in your code (e.g. `<keyboard>.c`) for custom logic:

```c
void bootmagic_scan(void) {
    matrix_scan();
    wait_ms(DEBOUNCE * 2);
    matrix_scan();

    if (matrix_get_row(BOOTMAGIC_ROW) & (1 << BOOTMAGIC_COLUMN)) {
        bootloader_jump();   // jump to bootloader
    }
}
```

You can add logic here (e.g. require multiple keys, conditional EEPROM reset). Note `bootmagic_scan()` runs **before most features initialize**, so most QMK APIs are not yet available inside it.

`bootloader_jump()` is the underlying call that enters the bootloader; you can also call it yourself from a custom keycode (often bound to `QK_BOOT`).

### Relationship to Magic keycodes & Command (important)

- **Full Bootmagic is deprecated.** Its old boot-time settings (NKRO default, default layer, Caps-as-Ctrl, Alt/GUI swap, etc.) are now controlled at runtime by **Magic Keycodes** (`MAGIC_*` / aliases like `NK_ON`, `AG_SWAP`, `CL_SWAP`, `CG_SWAP`, `GU_OFF` — full table in `04-keymaps-and-keycodes.md`). Magic keycodes persist their state to EEPROM.
- The **Command** feature (formerly also called "Magic") is a magic+debug command console over the debug console / `MAGIC` key combo; see `10-connectivity.md`. It overlaps Magic keycodes but adds console output (version info, etc.).

### Example

Minimal `rules.mk` + `config.h` to make the top-left key (ESC) the bootloader trigger, preserving EEPROM:

```make
# rules.mk
BOOTMAGIC_ENABLE = yes
```
```c
// config.h
#define BOOTMAGIC_ROW    0
#define BOOTMAGIC_COLUMN 0
#define BOOTMAGIC_NO_EEPROM   // jump to bootloader WITHOUT wiping EEPROM
```

### Gotchas

- **EEPROM is wiped by default** on a Bootmagic trigger unless you opt out (`BOOTMAGIC_NO_EEPROM`). Lost settings include Magic keycode state (key swaps, NKRO), Unicode input mode, default layer, and any EEPROM-backed config.
- `BOOTMAGIC_ENABLE = full` is **deprecated** — use `yes` (lite) and configure runtime behaviors via Magic keycodes instead.
- The trigger key is a **physical matrix position** (row/column), not a keycode. For unusual matrices or split halves you must compute the correct indices from the keyboard's `LAYOUT` macro.
- On split keyboards the **right-half trigger defaults to undefined** — if you only set the left pair, the right half may not enter the bootloader via a key. Set `BOOTMAGIC_ROW_RIGHT`/`BOOTMAGIC_COLUMN_RIGHT`.
- `bootmagic_scan()` runs **very early**, before most feature init — don't rely on other QMK subsystems being ready inside your override.
- Bootmagic and a physical reset button are alternatives; some boards disable Bootmagic by default for safety.

---

## DIP Switches

### Summary

Support hardware DIP switches (or slide switches) as additional inputs beyond the key matrix. Useful for persistent hardware toggles (layer select, layout swap, Plover mode). Switches can be wired to dedicated GPIO pins **or** to unused row/column intersections in the existing key matrix.

### Enable it

```make
# rules.mk
DIP_SWITCH_ENABLE = yes
```

Data-driven (`info.json`) equivalent:

```json
{
    "features": {
        "dip_switch": true
    }
}
```

### Wiring modes (mutually exclusive)

**Mode A — dedicated GPIO pins** (one pin per switch):

```c
// config.h
#define DIP_SWITCH_PINS { B14, A15, A10, B9 }
// For split keyboards, separately define the right-side pins:
#define DIP_SWITCH_PINS_RIGHT { ... }
```

**Mode B — unused key-matrix intersections** (diode + switch tying a ROW line to a COL line):

```c
// config.h — list of {row, col} pairs
#define DIP_SWITCH_MATRIX_GRID { {0,6}, {1,6}, {2,6} }
```

Hardware notes:
- GPIO mode: one side of the switch to the MCU pin, the other to ground (polarity doesn't matter).
- Matrix mode: wire like a normal keyswitch (diode + switch between a ROW and COL line).

### Configuration knobs

| Define | Default | Meaning |
|---|---|---|
| `DIP_SWITCH_PINS` | *(none)* | GPIO pins for each DIP switch (left/only half). |
| `DIP_SWITCH_PINS_RIGHT` | *(none)* | GPIO pins for the right half of a split keyboard. |
| `DIP_SWITCH_MATRIX_GRID` | *(none)* | `{row,col}` pairs for matrix-wired switches. Mutually exclusive with `DIP_SWITCH_PINS`. |
| `NUM_DIP_SWITCHES` | *(derived from pins/grid)* | Count of switches; needed if you also enable `DIP_SWITCH_MAP_ENABLE`. |
| `NUM_DIP_STATES` | `2` | States per switch (OFF / ON). |

> Polling/debounce for DIP switches is handled internally; there is no per-switch `DEBOUNCE` knob specific to DIP switches — the general debounce setting applies (see `03-config-and-info-json.md`).

### DIP Switch map (keycode-style mapping)

For simple OFF→keycode / ON→keycode behavior, you can build a PROGMEM map (mirrors how a keymap works) instead of writing callbacks. Enable at the **keymap level only**:

```make
# keymap's rules.mk
DIP_SWITCH_MAP_ENABLE = yes
```

```c
// keymap.c
#if defined(DIP_SWITCH_MAP_ENABLE)
const uint16_t PROGMEM dip_switch_map[NUM_DIP_SWITCHES][NUM_DIP_STATES] = {
    DIP_SWITCH_OFF_ON(DF(0), DF(1)),       // switch 0: default layer 0 vs 1
    DIP_SWITCH_OFF_ON(EC_NORM, EC_SWAP)    // switch 1: normal vs swapped Esc/Caps
};
#endif
```

`DIP_SWITCH_OFF_ON(off_key, on_key)` is the helper macro for the two-state row. This is the simplest path when each switch just emits a keycode per state.

### Callbacks (per-switch and bitmask)

There are two flavors, each with `_kb` (`<keyboard>.c`) and `_user` (`keymap.c`) variants.

**Per-switch (index, active):**

```c
// <keyboard>.c
bool dip_switch_update_kb(uint8_t index, bool active) {
    if (!dip_switch_update_user(index, active)) { return false; }
    return true;
}

// keymap.c
bool dip_switch_update_user(uint8_t index, bool active) {
    switch (index) {
        case 0: (active) ? audio_on() : audio_off();   break;
        case 1: (active) ? clicky_on() : clicky_off(); break;
        case 3:
            if (active) { layer_on(_PLOVER);  }
            else        { layer_off(_PLOVER); }
            break;
    }
    return true;
}
```

**Bitmask (full switch state as a `uint32_t`):** for logic that depends on combinations of switches:

```c
// <keyboard>.c
bool dip_switch_update_mask_kb(uint32_t state) {
    if (!dip_switch_update_mask_user(state)) { return false; }
    return true;
}

// keymap.c
bool dip_switch_update_mask_user(uint32_t state) {
    if ((state & (1UL<<0)) && (state & (1UL<<1))) { layer_on(_ADJUST);  }
    else                                          { layer_off(_ADJUST); }
    return true;
}
```

Bit `N` of `state` corresponds to DIP switch `N`. Use the mask callbacks when a single action depends on multiple switches at once.

### Split handling

- For GPIO mode, define `DIP_SWITCH_PINS_RIGHT` for the right half; the master reads the slave's state over the split link. See `10-connectivity.md` for the underlying split transport.
- For matrix mode, the switch positions are part of each half's matrix and ride the normal matrix scan.
- The `_kb` callback is expected to call `_user` and propagate `false` to short-circuit.

### Example

A 4-switch GPIO DIP, switch 3 toggles a Plover layer:

```make
# rules.mk
DIP_SWITCH_ENABLE = yes
```
```c
// config.h
#define DIP_SWITCH_PINS { B14, A15, A10, B9 }
```
```c
// keymap.c
bool dip_switch_update_user(uint8_t index, bool active) {
    if (index == 3) { active ? layer_on(_PLOVER) : layer_off(_PLOVER); }
    return true;
}
```

### Gotchas

- `DIP_SWITCH_MAP_ENABLE` should be enabled **only at the keymap level**, never the keyboard level.
- `DIP_SWITCH_PINS` and `DIP_SWITCH_MATRIX_GRID` are **mutually exclusive** wiring modes — pick one.
- On splits, forgetting `DIP_SWITCH_PINS_RIGHT` means the right-half switches are never read.
- The callback convention is: `_kb` calls `_user`; if `_user` returns `false`, `_kb` should return `false` to stop further processing.
- `index` is zero-based and follows the order of the `PINS`/`MATRIX_GRID` arrays.
- Bitmask (`*_mask_*`) callbacks give you the whole state at once — handy for "two switches both ON" logic that per-switch callbacks make awkward.

---

## Unicode

### Summary

Input Unicode characters (any code point up to `U+10FFFF`) by having the firmware drive the host OS's Unicode input method. Because there is **no cross-OS standard** for Unicode input, each host requires its own setup (and sometimes third-party software), and the keyboard's behavior is **OS-specific** — Unicode will not "just work" when you move the keyboard to another machine. Three subsystems build on the core API: **Basic** (`UC(c)`), **Unicode Map** (`UM(i)` / `UP(i,j)`), and **UCIS** (mnemonic replacement).

> **Why this is hard (from `how_keyboards_work.md`):** USB HID only has a limited keycode space, so you can't have a keycode per Unicode character. Instead the firmware sends *sequences of normal keystrokes* that invoke the host OS's hex-input method. Consequences: tied to one OS at a time (may need recompile when you switch OS), doesn't work in all host software, and some hosts only cover a subset of Unicode.

### Enable it

The Unicode code is shared; pick one (or more) subsystem per build.

```make
# rules.mk — required base for all unicode subsystems
UNICODE_COMMON = yes

# Then enable exactly the subsystem(s) you want:
UNICODE_ENABLE     = yes   # Basic: UC(c), code points up to U+7FFF
UNICODEMAP_ENABLE  = yes   # Unicode Map: UM(i) / UP(i,j), all code points
UCIS_ENABLE        = yes   # UCIS mnemonic replacement, all code points
```

> Multiple subsystems can coexist (e.g. `UNICODEMAP_ENABLE` + `UCIS_ENABLE`). `UNICODE_COMMON` is the shared core.

### Input modes (the host-OS dependency)

Set which input modes are enabled (and cyclable) via `UNICODE_SELECTED_MODES`:

```c
// config.h
#define UNICODE_SELECTED_MODES UNICODE_MODE_LINUX
// or cycle through several:
#define UNICODE_SELECTED_MODES UNICODE_MODE_MACOS, UNICODE_MODE_WINCOMPOSE
```

If EEPROM works, the last-used mode is remembered across reboots (disable with `UNICODE_CYCLE_PERSIST = false`). You can also switch to any mode directly via its keycode, even modes not in `UNICODE_SELECTED_MODES`.

| Mode name | Host | Setup | Code-point range | Notes |
|---|---|---|---|---|
| `UNICODE_MODE_MACOS` | macOS | System Settings → Keyboard → Input Sources → add **Unicode Hex Input** (under Other); activate from menu bar. | all (surrogate pairs above `U+FFFF`) | May disable some Option-based shortcuts (Option+Left/Right). |
| `UNICODE_MODE_LINUX` | Linux (IBus) | Enabled by default on IBus distros; works almost everywhere. Without IBus, only GTK apps. | all | Non-GTK apps without IBus may need a custom keyboard layout. |
| `UNICODE_MODE_WINCOMPOSE` | Windows | Install [WinCompose](https://github.com/samhocevar/wincompose); auto-runs on startup. | all | **Recommended Windows mode.** |
| `UNICODE_MODE_WINDOWS` | Windows (HexNumpad) | Admin registry edit + reboot: `reg add "HKCU\Control Panel\Input Method" -v EnableHexNumpad -t REG_SZ -d 1` | up to `U+FFFF` only | **NOT "Alt codes"** (those use Windows-1252, not Unicode). Not recommended — reliability/compat issues. |
| `UNICODE_MODE_EMACS` | Emacs | Built-in `insert-char` (`C-x 8 RET`). | all | |
| `UNICODE_MODE_BSD` | BSD | *(not implemented)* | n/a | Stub; contributions welcome. |

### Basic Configuration

| Define | Default | Description |
|---|---|---|
| `UNICODE_KEY_MAC` | `KC_LEFT_ALT` | Key held to begin a macOS Unicode sequence. |
| `UNICODE_KEY_LNX` | `LCTL(LSFT(KC_U))` | Key tapped to begin a Linux (IBus) Unicode sequence. |
| `UNICODE_KEY_WINC` | `KC_RIGHT_ALT` | Key held to begin a WinCompose Unicode sequence. |
| `UNICODE_SELECTED_MODES` | *(n/a)* | Comma-separated list of modes for cycling (`UC_NEXT`/`UC_PREV`). |
| `UNICODE_CYCLE_PERSIST` | `true` | Whether the current mode is persisted to EEPROM. |
| `UNICODE_TYPE_DELAY` | `10` (ms) | Delay between Unicode sequence keystrokes. |

Most users only need to set `UNICODE_SELECTED_MODES`. If you switch modes manually (via the `UC_*` keycodes) and never cycle, you can omit it.

### Audio feedback (optional)

If **Audio** is enabled (`09-audio-haptic.md`), you can play a song when each mode is selected:

| Define | Default | Description |
|---|---|---|
| `UNICODE_SONG_MAC` | *(n/a)* | Song for macOS mode. |
| `UNICODE_SONG_LNX` | *(n/a)* | Song for Linux mode. |
| `UNICODE_SONG_BSD` | *(n/a)* | Song for BSD mode. |
| `UNICODE_SONG_WIN` | *(n/a)* | Song for Windows (HexNumpad) mode. |
| `UNICODE_SONG_WINC` | *(n/a)* | Song for WinCompose mode. |

### Keycodes

| Key | Aliases | Description |
|---|---|---|
| `UC(c)` | | Send Unicode code point `c`, up to `0x7FFF` (Basic only). Hex without `U+`. |
| `UM(i)` | | Send code point at index `i` in `unicode_map[]` (Unicode Map). |
| `UP(i, j)` | | Send index `i`, or `j` if Shift/Caps is on (Unicode Map pairs). |
| `QK_UNICODE_MODE_NEXT` | `UC_NEXT` | Cycle forward through `UNICODE_SELECTED_MODES`. |
| `QK_UNICODE_MODE_PREVIOUS` | `UC_PREV` | Cycle backward through selected modes. |
| `QK_UNICODE_MODE_MACOS` | `UC_MAC` | Switch to macOS input. |
| `QK_UNICODE_MODE_LINUX` | `UC_LINX` | Switch to Linux input. |
| `QK_UNICODE_MODE_WINDOWS` | `UC_WIN` | Switch to Windows (HexNumpad) input. |
| `QK_UNICODE_MODE_BSD` | `UC_BSD` | Switch to BSD input (not implemented). |
| `QK_UNICODE_MODE_WINCOMPOSE` | `UC_WINC` | Switch to Windows WinCompose input. |
| `QK_UNICODE_MODE_EMACS` | `UC_EMAC` | Switch to Emacs input (`C-x 8 RET`). |

> Note the alias spellings: `UC_LINX` (no "U"), `UC_EMAC` (no "S").

### Input subsystems in detail

**Basic** — easiest, limited to `U+7FFF` (most modern-language chars + many symbols, **no emoji**). Use `UC(0x40B)` → `Ћ`, `UC(0x30C4)` → `ツ`.

**Unicode Map** — supports all code points (`U+10FFFF`); code points live in a separate PROGMEM table (max **16,384** entries):

```c
enum unicode_names { BANG, IRONY, SNEK };

const uint32_t PROGMEM unicode_map[] = {
    [BANG]  = 0x203D,  // ‽
    [IRONY] = 0x2E2E,  // ⸮
    [SNEK]  = 0x1F40D, // 🐍
};
// keymap: UM(BANG), UM(SNEK)
```

Lower/upper-case pairs via `UP(i, j)` (Shift/Caps selects uppercase). **Constraint:** `i` and `j` must each be ≤ 127 (first 128 entries) due to keycode size limits.

**UCIS** — all code points, mnemonic replacement. Type a mnemonic, hit Space/Enter, the mnemonic is backspaced and the emoji inserted. Requires a `ucis_symbol_table`:

```c
const ucis_symbol_t ucis_symbol_table[] = UCIS_TABLE(
    UCIS_SYM("poop", 0x1F4A9),               // 💩
    UCIS_SYM("rofl", 0x1F923),               // 🤣
    UCIS_SYM("ukr",  0x1F1FA, 0x1F1E6),      // 🇺🇦
    UCIS_SYM("look", 0x0CA0, 0x005F, 0x0CA0) // ಠ_ಠ
);
```

```c
// config.h — raise the per-entry code-point limit (default 3)
#define UCIS_MAX_CODE_POINTS 4
```

UCIS must be started with `ucis_start()` (typically from a custom keycode), then type the mnemonic and press Space/Enter.

### C API / callbacks

**Input mode:**

```c
uint8_t get_unicode_input_mode(void);            // current mode
void    set_unicode_input_mode(uint8_t mode);    // set mode
void    unicode_input_mode_step(void);           // next selected mode
void    unicode_input_mode_step_reverse(void);   // previous selected mode

// Callbacks (mode change):
void unicode_input_mode_set_user(uint8_t input_mode);  // keymap.c
void unicode_input_mode_set_kb(uint8_t input_mode);    // <keyboard>.c
```

**Sequence primitives** (all weakly defined — override to customize per-mode behavior):

```c
void unicode_input_start(void);   // begin sequence (mode-dependent)
void unicode_input_finish(void);  // complete sequence
void unicode_input_cancel(void);  // abort sequence
```

Per-mode `start`/`finish`/`cancel` behavior:
- **macOS:** start=hold `UNICODE_KEY_MAC`; finish=release; cancel=release.
- **Linux:** start=tap `UNICODE_KEY_LNX`; finish=tap Space; cancel=tap Escape.
- **WinCompose:** start=tap `UNICODE_KEY_WINC`, then `U`; finish=tap Enter; cancel=tap Escape.
- **HexNumpad:** start=hold Left Alt, tap Numpad +; finish=release Left Alt; cancel=release Left Alt.
- **Emacs:** start=Ctrl+X, 8, Enter; finish=tap Enter; cancel=Ctrl+G.

**Sending characters:**

```c
void register_unicode(uint32_t code_point);      // send one char (surrogate pair if needed)
void send_unicode_string(const char *str);        // send a UTF-8/Unicode string
```

**Unicode Map helpers:**

```c
uint8_t  unicodemap_index(uint16_t keycode);       // map keycode → unicode_map index (respects Shift for pairs)
uint32_t unicodemap_get_code_point(uint8_t index); // index → code point
void     register_unicodemap(uint8_t index);       // send code point at index
```

**UCIS helpers:**

```c
void  ucis_start(void);                  // begin input sequence
bool  ucis_active(void);                 // is UCIS active?
uint8_t ucis_count(void);                // chars currently in buffer
bool  ucis_add(uint16_t keycode);        // add KC_A–KC_Z or KC_1–KC_0; true if added
bool  ucis_remove_last(void);            // backspace one char; true if buffer was non-empty
void  ucis_finish(void);                 // mark complete & match
void  ucis_cancel(void);                 // abort
void  register_ucis(uint8_t index);      // send code point(s) for table index
```

### Example

Unicode Map with a pair, plus a mode-cycle key:

```make
# rules.mk
UNICODE_COMMON    = yes
UNICODEMAP_ENABLE = yes
```
```c
// config.h
#define UNICODE_SELECTED_MODES UNICODE_MODE_MACOS, UNICODE_MODE_WINCOMPOSE
```
```c
// keymap.c
enum unicode_names { AE_LOWER, AE_UPPER, SNEK };
const uint32_t PROGMEM unicode_map[] = {
    [AE_LOWER] = 0x00E6,  // æ
    [AE_UPPER] = 0x00C6,  // Æ
    [SNEK]     = 0x1F40D, // 🐍
};

// keymap entries: UP(AE_LOWER, AE_UPPER), UM(SNEK), UC_NEXT
```

### Gotchas

- **Host-OS dependent** — each host needs its own setup (macOS Unicode Hex Input, WinCompose, IBus, Emacs). The keyboard will not work on a host that isn't configured for the active mode. This is the #1 surprise. (Root cause per `how_keyboards_work.md`: the firmware types keystroke sequences that invoke the host's hex-input method.)
- **Basic `UC(c)` only goes to `U+7FFF`** — no emoji. Use Unicode Map (`UM`) or UCIS for `U+1F300+`.
- `UP(i,j)` pair indices are **limited to 0–127** each (keycode bit-budget).
- `UNICODE_MODE_WINDOWS` (HexNumpad) is **not** "Alt codes" and is capped at `U+FFFF`; prefer `UNICODE_MODE_WINCOMPOSE` on Windows.
- The mode is **persisted to EEPROM** by default; switching hosts requires either cycling modes (`UC_NEXT`) or setting `UNICODE_CYCLE_PERSIST = false`.
- Alias spelling traps: `UC_LINX` (not `UC_LINUX`), `UC_EMAC` (not `UC_EMACS`).
- `UNICODE_TYPE_DELAY` (default 10 ms) matters on slower hosts — raise it if sequences get dropped.
- `UNICODE_COMMON = yes` is required by all subsystems; forgetting it (or only setting `UNICODE_ENABLE`) is a common build failure on newer QMK.
- BSD mode is a stub (not implemented).

---

## Stenography

### Summary

Support [stenography](https://en.wikipedia.org/wiki/Stenotype) / the [Open Steno Project](https://www.openstenoproject.org/)'s **Plover** real-time translator. QMK can act as a plain QWERTY keyboard for Plover, or speak a real steno-machine protocol (**TX Bolt** or **GeminiPR**) over a virtual serial port so Plover treats the keyboard as a stenotype machine. Professional steno reaches 200–300 WPM.

Three integration levels (least → most configuration):
1. **Plover with Arpeggiation** — no firmware changes; works on any QWERTY keyboard.
2. **Plover with NKRO** — enable NKRO in QMK; Plover sees all chorded keys at once.
3. **Steno machine protocols** (TX Bolt / GeminiPR) — QMK presents a virtual serial port and speaks the steno protocol. Most config, but lets you toggle between normal typing and steno without re-activating Plover.

### Enable it

For protocol mode:

```make
# rules.mk
STENO_ENABLE  = yes
STENO_PROTOCOL = all        # or: txbolt | geminipr | all
```

`STENO_PROTOCOL` values: `txbolt`, `geminipr`, `all` (default). `all` compiles both protocols and lets you switch on the fly via keycodes (at the cost of firmware size); a single protocol is usually sufficient.

### Protocols

**TX Bolt** — 24 keys over variable-length (1–4 byte) packets. Each byte's top 2 bits are a group ID; remaining bits are key-press flags:
```
00HWPKTS 01UE*OAR 10GLBPRF 110#ZDST
```
A new packet starts when the current byte's group ID ≤ the previous byte's group ID. Examples: `EUBG` = `01110000 10101000`; `WAZ` = `00010000 01000010 11001000`.

**GeminiPR** — 42 keys in a fixed 6-byte packet. Byte 0 has MSB=1 (packet start); bytes 1–5 have MSB=0. More capable than TX Bolt: distinguishes top/bottom `S-`, supports non-English theories:
```
1 Fn  #1  #2 #3 #4 #5   #6
0 S1- S2- T- K- P- W-   H-
0 R-  A-  O- *1 *2 res1 res2
0 pwr *3  *4 -E -U -F   -R
0 -P  -B  -L -G -T -S   -D
0 #7  #8  #9 #A #B #C   -Z
```

### Switching protocols on the fly

With `STENO_PROTOCOL = all`, two keycodes switch the active protocol at runtime; the choice is saved to (emulated) EEPROM and remembered across reboots. Default protocol is **GeminiPR**.

| Key | Description |
|---|---|
| `QK_STENO_BOLT` | Switch to TX Bolt. |
| `QK_STENO_GEMINI` | Switch to GeminiPR. |

> Do **not** use `tap_code(QK_STENO_*)` to switch programmatically — `tap_code` only handles basic keycodes. Use `steno_set_mode(STENO_MODE_BOLT)` or `steno_set_mode(STENO_MODE_GEMINI)` instead.

### Configuring the build (USB endpoint conflicts)

Steno protocol mode opens a virtual serial port, which consumes **3 USB endpoints**. Some MCUs have a limited endpoint count, so you may need to disable conflicting features:

```make
# rules.mk — often needed together with STENO_ENABLE
NKRO_ENABLE    = no   # conflicts with serial steno
MOUSEKEY_ENABLE = no
EXTRAKEY_ENABLE = no
```

⚠️ If you have **explicitly** set `VIRTSER_ENABLE = no`, none of the serial steno protocols will work — leave it `yes` or remove the line. (Typo'd `VIRSTER_ENABLE` in the source docs; the real flag is `VIRTSER_ENABLE`.)

Plover-side serial settings: baud 9600 (up to 115200 works), 8 data bits, 1 stop bit, no parity, no flow control. Test with Plover's Tools → Paper Tape / Layout Display.

### Steno keycodes

TX Bolt doesn't support the full key set; QMK maps GeminiPR keys to the nearest TX Bolt key so one keymap works for both. Define `STENO_COMBINEDMAP` in `config.h` to enable the combined (two-keys-one-finger) keycodes.

| GeminiPR | TX Bolt | Steno key |
|---|---|---|
| `STN_N1`–`STN_NC` | `STN_NUM` | Number bar #1–#A,#B,#C |
| `STN_S1` | `STN_SL` | `S-` upper |
| `STN_S2` | `STN_SL` | `S-` lower |
| `STN_TL` / `STN_KL` / `STN_PL` / `STN_WL` / `STN_HL` / `STN_RL` | same | `T-` `K-` `P-` `W-` `H-` `R-` |
| `STN_A` / `STN_O` | same | `A` / `O` vowels |
| `STN_ST1`–`STN_ST4` | `STN_STR` | `*` upper/lower-left/right |
| `STN_E` / `STN_U` | same | `E` / `U` vowels |
| `STN_FR` `STN_RR` `STN_PR` `STN_BR` `STN_LR` `STN_GR` `STN_TR` `STN_SR` `STN_DR` `STN_ZR` | same | `-F -R -P -B -L -G -T -S -D -Z` |
| `STN_FN` | — | Function (GeminiPR only) |
| `STN_RES1` / `STN_RES2` | — | Reset 1 / Reset 2 (GeminiPR only) |
| `STN_PWR` | — | Power (GeminiPR only) |

Combined keycodes (need `#define STENO_COMBINEDMAP`):

| Combined | = Key1 + Key2 |
|---|---|
| `STN_S3` | `STN_S1` + `STN_S2` |
| `STN_TKL` | `STN_TL` + `STN_KL` |
| `STN_PWL` | `STN_PL` + `STN_WL` |
| `STN_HRL` | `STN_HL` + `STN_RL` |
| `STN_FRR` | `STN_FR` + `STN_RR` |
| `STN_PBR` | `STN_PR` + `STN_BR` |
| `STN_LGR` | `STN_LR` + `STN_GR` |
| `STN_TSR` | `STN_TR` + `STN_SR` |
| `STN_DZR` | `STN_DR` + `STN_ZR` |
| `STN_AO` | `STN_A` + `STN_O` |
| `STN_EU` | `STN_E` + `STN_U` |

### C API / hooks

Three interceptable hooks (return `true` to continue normal processing, `false` to signal you handled it):

```c
// Called when a chord is about to be sent. mode is STENO_MODE_BOLT or STENO_MODE_GEMINI.
// You can MODIFY chord[] in place. Return true to let normal sending proceed.
bool send_steno_chord_user(steno_mode_t mode, uint8_t chord[MAX_STROKE_SIZE]);

// Called on each keypress BEFORE processing. keycode is QK_STENO_BOLT,
// QK_STENO_GEMINI, or one of the STN_* values.
bool process_steno_user(uint16_t keycode, keyrecord_t *record);

// Called AFTER a key is processed, before the send-a-chord decision.
// Ideal for live chord/key displays.
bool post_process_steno_user(uint16_t keycode, keyrecord_t *record,
                             steno_mode_t mode, uint8_t chord[MAX_STROKE_SIZE],
                             int8_t n_pressed_keys);
```

Runtime mode switch:

```c
void steno_set_mode(steno_mode_t mode);  // STENO_MODE_BOLT or STENO_MODE_GEMINI
```

Notes on `post_process_steno_user`:
- When `record->event.pressed` is false **and** `n_pressed_keys` is 0 or 1, the chord is about to be sent (but hasn't been yet) — this relieves you from tracking packet boundaries yourself.
- `chord` is the **protocol packet**, not a list of `STN_*` keycodes. See the protocol byte layouts above.
- `n_pressed_keys` is the count of **physical** keys held, which can differ from the Hamming weight of `chord` (e.g. press 4, release 3, press 1 more → 5 bits set but `n_pressed_keys == 2`).

### Example

GeminiPR steno with a Plover layer:

```make
# rules.mk
STENO_ENABLE  = yes
STENO_PROTOCOL = geminipr
NKRO_ENABLE   = no
```
```c
// keymap.c — a STN_* keycode per steno key in your Plover layer
// e.g. STN_S1, STN_TK, STN_A, STN_O, ..., plus a key to toggle the layer
```

### Gotchas

- **Serial steno protocols are NOT supported on V-USB (AVR) keyboards** — TX Bolt / GeminiPR need a real USB stack with a virtual serial port.
- **USB endpoint exhaustion:** steno's virtual serial port uses 3 endpoints; you often must disable NKRO, mouse keys, and/or extrakeys to compile.
- `VIRTSER_ENABLE = no` (if set explicitly) **breaks serial steno** — leave it `yes`/unset.
- `tap_code(QK_STENO_*)` does **not** switch protocols — use `steno_set_mode()` for programmatic switching (these are not basic keycodes).
- Default protocol is **GeminiPR**; last-used protocol is saved to EEPROM.
- TX Bolt has fewer keys (24) than GeminiPR (42); QMK maps GeminiPR→TX Bolt so one keymap works for both, but you lose top/bottom `S-` distinction and `STN_FN`/`STN_RES*`/`STN_PWR` on TX Bolt.
- `chord` in the hooks is the **raw protocol packet**, not an array of `STN_*` keys.
- The source doc contains a typo (`VIRSTER_ENABLE`); the real flag is `VIRTSER_ENABLE`.
- Example reference keymaps: `planck/keymaps/default` (QWERTY+Plover), `splitography/keymaps/default` (protocol steno).

---

## WPM (Words Per Minute)

### Summary

Computes a rolling-average words-per-minute value from inter-keystroke timing and exposes it via `get_current_wpm()`. Common use: display WPM on an OLED (`08-displays.md`) or RGB indicator (`07-led-rgb-backlight.md`). On split keyboards using soft serial, the computed WPM is available on **both** halves.

### Enable it

```make
# rules.mk
WPM_ENABLE = yes
```

Data-driven (`info.json`):

```json
{
    "features": {
        "wpm": true
    }
}
```

### Configuration

| Define | Default | Description |
|---|---|---|
| `WPM_ESTIMATED_WORD_SIZE` | `5` | Average word size (chars) used for the calculation. |
| `WPM_ALLOW_COUNT_REGRESSION` | *(undefined)* | If defined, WPM can **decrease** when Delete/Backspace is pressed (via `wpm_regress_count`). |
| `WPM_UNFILTERED` | *(undefined)* | If undefined (default), WPM is smoothed to avoid sudden jumps. Define for unsmoothed (lower-latency, smaller code) values. |
| `WPM_SAMPLE_SECONDS` | `5` (s) | How many seconds of typing to average. Higher = smoother but more latency. |
| `WPM_SAMPLE_PERIODS` | `25` | Number of sampling periods. Higher = smoother decay when typing stops, at ~1 byte/period firmware cost. |
| `WPM_LAUNCH_CONTROL` | *(undefined)* | If defined, after WPM hits 0 the next typing burst is computed from only the time since it started → reaches accurate WPM faster (helps when filtering + large `WPM_SAMPLE_SECONDS`). |

Tuning guidance:
- Increase `WPM_SAMPLE_SECONDS` → smoother, slightly more latency.
- Increase `WPM_SAMPLE_PERIODS` → smoother decay after you stop typing, ~1 byte each.
- `WPM_LAUNCH_CONTROL` dramatically cuts time-to-accurate-WPM after idle, even with filtering on.

### Public functions

| Function | Description |
|---|---|
| `uint8_t get_current_wpm(void)` | Current WPM (0–255). |
| `void set_current_wpm(uint8_t x)` | Force the current WPM to `x` (0–255). |

### Callbacks

By default the WPM score counts **letters, numbers, space, and some punctuation**. To change which keycodes count, implement `wpm_keycode_user`:

```c
// keymap.c — the default behavior, reproduced for customization:
bool wpm_keycode_user(uint16_t keycode) {
    // Unwrap mod-tap / layer-tap / modded keycodes to their basic keycode
    if ((keycode >= QK_MOD_TAP && keycode <= QK_MOD_TAP_MAX) ||
        (keycode >= QK_LAYER_TAP && keycode <= QK_LAYER_TAP_MAX) ||
        (keycode >= QK_MODS && keycode <= QK_MODS_MAX)) {
        keycode = keycode & 0xFF;
    } else if (keycode > 0xFF) {
        keycode = 0;
    }
    if ((keycode >= KC_A && keycode <= KC_0) ||
        (keycode >= KC_TAB && keycode <= KC_SLSH)) {
        return true;
    }
    return false;
}
```

If `WPM_ALLOW_COUNT_REGRESSION` is defined, you can also penalize keycodes (decrement the count) via:

```c
__attribute__((weak)) uint8_t wpm_regress_count(uint16_t keycode) {
    // Return number of chars to subtract; e.g. backspace = 1,
    // Ctrl+Backspace (word delete) = WPM_ESTIMATED_WORD_SIZE
    // (apply the same keycode-unwrapping as wpm_keycode_user first)
}
```

### Example

Show WPM on an OLED each frame:

```make
# rules.mk
WPM_ENABLE = yes
```
```c
// keymap.c
#include <stdio.h>
char wpm_str[8];

void render_wpm(void) {  // call from your oled_task_user()
    snprintf(wpm_str, sizeof(wpm_str), "WPM:%3d", get_current_wpm());
    oled_write(wpm_str, false);
}
```

### Gotchas

- WPM is a `uint8_t` capped at **255** — it saturates; very fast bursts won't read above 255.
- By default WPM **only counts A–Z, 0–9, space, and a punctuation range**; mouse keys, layer switches, and most non-typing keys are ignored. Override `wpm_keycode_user` to change this.
- **Regression (decreasing WPM) is opt-in** via `WPM_ALLOW_COUNT_REGRESSION`; without it, Backspace/Delete don't reduce WPM.
- Filtering is **on by default** (`WPM_UNFILTERED` undefined) — values jump less but lag more. Define `WPM_UNFILTERED` for raw values (smaller code, lower latency).
- `WPM_LAUNCH_CONTROL` is the fix for "WPM takes forever to climb after I pause" — recommended with large `WPM_SAMPLE_SECONDS`.
- On split keyboards the value syncs to both halves via the split transport (`10-connectivity.md`); no extra work needed.
- When customizing `wpm_keycode_user`, remember to **unwrap mod-tap/layer-tap/mods keycodes** (`keycode & 0xFF`) before range-checking, or you'll miss modded typing.

---

## Community Modules

QMK's modern third-party **plugin** mechanism now has its own reference: **`18-community-modules.md`**. A module is a self-contained `modules/<name>/` directory (`qmk_module.json` + `<name>.c`) that hooks `process_record_<module>` / `keyboard_pre_init_<module>` / `housekeeping_task_<module>` / pointing-device / RGB-matrix / split-sync APIs, declares its own keycodes and feature deps, and is discovered via `keymap.json`. It is the recommended way to **distribute** reusable behavior (vs. a personal userspace, `16`). Not supported by the QMK Configurator (`14`).

---

## Cross-cutting cheat sheet

| Feature | `rules.mk` enable | Key API / hook | Cross-ref |
|---|---|---|---|
| Bootmagic | `BOOTMAGIC_ENABLE = yes` | `bootmagic_scan()` (weak) | Magic keycodes → `04`; Command → `10` |
| DIP switch | `DIP_SWITCH_ENABLE = yes` (+ optional `DIP_SWITCH_MAP_ENABLE = yes`) | `dip_switch_update_user(index, active)`, `*_mask_*` | Split → `10` |
| Unicode | `UNICODE_COMMON = yes` + `UNICODE_ENABLE`/`UNICODEMAP_ENABLE`/`UCIS_ENABLE` | `get/set_unicode_input_mode`, `register_unicode`, `send_unicode_string`, `unicode_input_mode_set_user` | host-OS setup; how_keyboards_work |
| Stenography | `STENO_ENABLE = yes` (+ `STENO_PROTOCOL`) | `process_steno_user`, `send_steno_chord_user`, `post_process_steno_user`, `steno_set_mode` | NKRO → `04`; split → `10` |
| WPM | `WPM_ENABLE = yes` | `get_current_wpm`, `set_current_wpm`, `wpm_keycode_user`, `wpm_regress_count` | OLED/RGB display → `07`/`08`; split sync → `10` |
| Community Modules | (none; declared in `keymap.json`) | `process_record_<module>`, `keyboard_pre_init_<module>`, … | **`18`**; userspace → `16`; split sync → `10` |
