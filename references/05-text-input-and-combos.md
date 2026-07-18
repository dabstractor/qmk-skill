# 05 — Text Input, Macros, and Chords

This reference covers features that **generate, transform, or chord keyboard input**: typing strings, recording/playing macros, autocorrecting typos, Caps Word, Repeat/Alt-Repeat Key, Combos, Leader Key, Key Overrides, Key Lock, Layer Lock, Space Cadet, Tap Dance, Tri Layer, Grave Escape, and Auto Shift.

> **Process-record ordering matters here.** Several of these features hook the key-processing pipeline at specific stages. Combos run in `pre_process_record_quantum` (the *earliest* stage, before `process_record_user`). Key Lock, Dynamic Macro, and Repeat Key run near the top of `process_record_quantum`, *before* `process_record_user`. Autocorrect, Caps Word, Key Overrides, and Leader run *during/after* `process_record_user`. See **`01-architecture.md`** (the full `process_record` chain) and **`08-displays.md`** (where OLED/encoder hooks sit relative to these). Cross-ref the keycode tables in **`04-keymaps-and-keycodes.md`**.

The verified `process_record_quantum` ordering (from `quantum/quantum.c`), top of the chain:

1. `pre_process_record_quantum` → **Combos** (`process_combo`)
2. (Secure preprocess)
3. **Tap Dance** preprocess (`preprocess_tap_dance`)
4. `process_record_quantum` main, in order: **Key Lock** → **Dynamic Macro** → **Repeat/Alt-Repeat Key** (`process_last_key` + `process_repeat_key`) → … → `process_record_kb` → **`process_record_user`** (your keymap) → … → Autocorrect / Caps Word / Key Overrides / Leader / Grave Esc / Space Cadet / Auto Shift / Tri Layer modules → `post_process_record_*`.

---

## 1. Send String

**Summary.** Part of QMK's macro system. Types a sequence of ASCII keystrokes automatically. Supports the full ASCII character set and all keycodes in the Basic Keycode range. This is the building block under `SEND_STRING()` macros (see §2).

### Enable it

Enabled **by default**. To explicitly enable (or re-enable after disabling):

```make
# rules.mk
SEND_STRING_ENABLE = yes
```

No `info.json` feature toggle is documented; use `rules.mk`.

### Configuration

| `config.h` define | Default | Meaning |
|---|---|---|
| `SENDSTRING_BELL` | *not defined* | If Audio is enabled, the `\a` (ASCII `BEL`) char beeps the speaker. |
| `BELL_SOUND` | `TERMINAL_SOUND` | Song played on `\a` (default: eighth note of C5). |

### SS_* injection macros and X_* keycodes

Send String accepts a C string literal. Inject keycodes with `SS_*` macros. Inside those macros, use the **`X_` prefix** (not `KC_`) for keycodes — e.g. `X_HOME`, `X_LEFT`. Only the Basic Keycode range (`KC_A`…`KC_EXSEL`-ish) is valid because only those reach the host.

| Macro | Description |
|---|---|
| `SS_TAP(x)` | Keydown then keyup for the given Send String keycode (`x` uses `X_` prefix). |
| `SS_DOWN(x)` | Keydown only. |
| `SS_UP(x)` | Keyup only. |
| `SS_DELAY(ms)` | Wait `ms` milliseconds. |

Convenience character mappings inside the string:

| Char | Hex | ASCII | Keycode |
|---|---|---|---|
| `\b` | `\x08` | BS | `KC_BACKSPACE` |
| `\e` | `\x09` | ESC | `KC_ESCAPE` |
| `\n` | `\x0A` | LF | `KC_ENTER` |
| `\t` | `\x1B` | TAB | `KC_TAB` |
| *(0x7F)* | `\x7F` | DEL | `KC_DELETE` |

**Modifier-shortcut macros** (take a *string*, not an `X_` keycode; press mod, send string, release mod):

`SS_LCTL(s)`, `SS_LSFT(s)`, `SS_LALT(s)` / `SS_LOPT(s)`, `SS_LGUI(s)` / `SS_LCMD(s)` / `SS_LWIN(s)`, and the right-side equivalents `SS_RCTL`, `SS_RSFT`, `SS_RALT`/`SS_ROPT`/`SS_ALGR`, `SS_RGUI`/`SS_RCMD`/`SS_RWIN`.

Example: `SEND_STRING(SS_LCTL("ac"))` sends Ctrl+A then Ctrl+C without releasing Ctrl.

### API

| Function / Macro | Purpose |
|---|---|
| `void send_string(const char *string)` | Type an ASCII string. Calls `send_string_with_delay(string, 0)`. |
| `void send_string_with_delay(const char *string, uint8_t interval)` | Type ASCII string, `interval` ms between each char. |
| `void send_string_P(const char *string)` | Type a **PROGMEM** ASCII string. (Alias for `send_string_with_delay` on ARM.) |
| `void send_string_with_delay_P(const char *string, uint8_t interval)` | PROGMEM string with delay. (Alias on ARM.) |
| `void send_char(char ascii_code)` | Type a single ASCII char. |
| `void send_dword(uint32_t number)` | Type 8 hex digits (`00000000`–`ffffffff`). |
| `void send_word(uint16_t number)` | Type 4 hex digits. |
| `void send_byte(uint8_t number)` | Type 2 hex digits. |
| `void send_nibble(uint8_t number)` | Type 1 hex digit. |
| `void tap_random_base64(void)` | Type a pseudorandom char from `A-Za-z0-9+/`. |
| `SEND_STRING(string)` | Macro → `send_string_with_delay_P(PSTR(string), 0)`. (ARM: `send_string_with_delay(string, 0)`.) |
| `SEND_STRING_DELAY(string, interval)` | Macro → `send_string_with_delay_P(PSTR(string), interval)`. |

### Behavior & internationalization

- Assumes **US ANSI** layout by default. To use another OS layout (Colemak, Dvorak, Workman, language layouts), include the relevant `sendstring_*.h` header (see keymap extras / `04-keymaps-and-keycodes.md`). This overrides the ASCII→keycode lookup tables.
- `SEND_STRING(...)` is a **C preprocessor macro** (wraps the string in `PSTR()` for PROGMEM). The runtime functions `send_string()` / `send_string_with_delay()` take a normal `char*` — the `SS_*` injection macros work only inside `SEND_STRING()`/`send_string_*`, not arbitrary string variables, because they expand to inline code.

### Example

```c
bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case SS_HELLO:
            if (record->event.pressed) {
                SEND_STRING("Hello, world!\n");
            }
            return false;
    }
    return true;
}
```

Type `{}` then move cursor between them: `SEND_STRING("{}" SS_TAP(X_LEFT));`

### Gotchas
- **Unicode is NOT supported** by Send String — use the Unicode feature (`11-other-features.md`) instead. Only ASCII + Basic keycodes are emitted.
- `SS_*` injection macros only work inside `SEND_STRING()` / `send_string_*()` calls, not inside plain `char[]` buffers passed elsewhere.
- Use the **`X_`** prefix (not `KC_`) inside `SS_TAP`/`SS_DOWN`/`SS_UP`. `SS_LCTL(...)` etc. take *strings* (`"a"`), not `X_` keycodes.
- On AVR, literal strings go to PROGMEM via `PSTR()`; on ARM they stay in RAM. `send_string_P`/`SEND_STRING` are portable.
- macOS: tapping `KC_CAPS` via `tap_code` uses `TAP_HOLD_CAPS_DELAY` (default 80 ms) because macOS resists accidental Caps Lock.
- `\e`/`\t` hex values in the docs look swapped vs. their ASCII names; rely on the keycode mapping, not the hex, when in doubt.

---

## 2. Macros (static / JSON macros)

**Summary.** Define up to 32 macros in `keymap.json` (data-driven), or implement custom macros in C with `SEND_STRING()` + `process_record_user()`. "QMK macros" (the `QK_MACRO_n` JSON system) are distinct from C preprocessor macros like `SEND_STRING`.

### JSON macros (data-driven, preferred for new keymaps)

Define a `macros` array in `keymap.json`; reference them with `QK_MACRO_0` … `QK_MACRO_31`. Each macro is an array of strings and objects. Strings are typed; objects have an `action` key.

| Action | Example | Meaning |
|---|---|---|
| `beep` | `{"action":"beep"}` | Play bell if Audio enabled. |
| `delay` | `{"action":"delay","duration":500}` | Pause `duration` ms. |
| `down` | `{"action":"down","keycodes":["LSFT"]}` | Key-down for one or more keycodes. |
| `tap` | `{"action":"tap","keycodes":["LCTL","LALT","DEL"]}` | Chord: down-each then up-each. |
| `up` | `{"action":"up","keycodes":["LSFT"]}` | Key-up. |

- Only **basic** keycodes are supported (the `KC_` prefix is **omitted**: write `LSFT`, `LCTL`, `DEL`, `F1`).
- Non-QWERTY host layouts: use [language-specific keycodes](reference_keymap_extras) / Send String headers (§1).

```json
{
  "macros": [
    [ {"action":"down","keycodes":["LSFT"]}, "hello world1", {"action":"up","keycodes":["LSFT"]} ],
    [ {"action":"tap","keycodes":["LCTL","LALT","DEL"]} ]
  ],
  "layers": [ ["QK_MACRO_0", "QK_MACRO_1"] ]
}
```

### C macros (`SEND_STRING` + `process_record_user`)

```c
enum custom_keycodes { QMKBEST = SAFE_RANGE, QMKURL };

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case QMKBEST:
            if (record->event.pressed) SEND_STRING("QMK is the best thing ever!");
            break;
        case QMKURL:
            if (record->event.pressed) SEND_STRING("https://qmk.fm/\n");
            break;
    }
    return true;
}
```

- Declare the `enum custom_keycodes` **before** `keymaps[]`, `process_record_user`, and anything using it.
- Start custom keycodes at `SAFE_RANGE` (see `16-userspace-development.md`).

### Useful functions inside macros

| Function | Purpose |
|---|---|
| `record->event.pressed` | Bool: keydown vs keyup. |
| `register_code(kc)` / `unregister_code(kc)` | Send basic keycode down/up. |
| `tap_code(kc)` | register then unregister. Honors `TAP_CODE_DELAY` (default 0); `KC_CAPS` uses `TAP_HOLD_CAPS_DELAY` (default 80). |
| `tap_code_delay(kc, delay)` | tap with explicit delay. |
| `register_code16(kc)` / `unregister_code16(kc)` / `tap_code16(kc)` / `tap_code16_delay(kc, delay)` | 16-bit variants — accept **modded** keycodes like `S(KC_5)` or `C(KC_A)`. |
| `clear_keyboard()` | Clear all mods and keys. |
| `clear_mods()` | Clear mods only. |
| `clear_keyboard_but_mods()` | Clear keys but keep mods. |
| `post_process_record_user(kc, record)` | Runs *after* `process_record` — useful to wrap a key with before/after behavior. |

See also `ref_functions` (e.g. `reset_keyboard()`, `timer_read()`/`timer_elapsed()` for macro timers) and modifier-state helpers (`get_mods() & MOD_MASK_SHIFT`) — cross-ref `01-architecture.md`.

### Example: Super ALT↯TAB (timer-driven)

Uses `process_record_user` + `matrix_scan_user` + a timer to cycle windows.

```c
bool is_alt_tab_active = false;
uint16_t alt_tab_timer = 0;
enum custom_keycodes { ALT_TAB = SAFE_RANGE };

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case ALT_TAB:
            if (record->event.pressed) {
                if (!is_alt_tab_active) { is_alt_tab_active = true; register_code(KC_LALT); }
                alt_tab_timer = timer_read();
                register_code(KC_TAB);
            } else {
                unregister_code(KC_TAB);
            }
            break;
    }
    return true;
}

void matrix_scan_user(void) {
    if (is_alt_tab_active && timer_elapsed(alt_tab_timer) > 1000) {
        unregister_code(KC_LALT);
        is_alt_tab_active = false;
    }
}
```

### Gotchas
- **Security:** never store passwords/credit cards in macros — anyone with the keyboard can dump them.
- JSON macros: omit the `KC_` prefix and only use basic keycodes; quantum/modified keycodes are rejected.
- `tap_code` waits `TAP_CODE_DELAY` (default 0) before unregister; some hosts need a small delay for fast taps to register reliably.
- `post_process_record_user` is the place to inject a held key *around* a normal key (e.g. press F22 before, release after).

---

## 3. Dynamic Macros

**Summary.** Record and replay macros **at runtime** from the keyboard. Up to two macros share a single buffer (default 128 keypresses). Macros are lost on reboot (not persistent).

### Enable it

```make
# rules.mk
DYNAMIC_MACRO_ENABLE = yes
```

### Keycodes

| Key | Alias | Description |
|---|---|---|
| `QK_DYNAMIC_MACRO_RECORD_START_1` | `DM_REC1` | Start recording Macro 1. |
| `QK_DYNAMIC_MACRO_RECORD_START_2` | `DM_REC2` | Start recording Macro 2. |
| `QK_DYNAMIC_MACRO_PLAY_1` | `DM_PLY1` | Replay Macro 1. |
| `QK_DYNAMIC_MACRO_PLAY_2` | `DM_PLY2` | Replay Macro 2. |
| `QK_DYNAMIC_MACRO_RECORD_STOP` | `DM_RSTP` | Finish the currently recording macro. |

Operation: `DM_REC1`/`DM_REC2` starts recording; `DM_RSTP` (or pressing the same `DM_RECn` again) stops; `DM_PLY1`/`DM_PLY2` replays.

### Configuration

| `config.h` define | Default | Meaning |
|---|---|---|
| `DYNAMIC_MACRO_SIZE` | `128` | Buffer size in keypresses. Both macros share it. RAM-limited. |
| `DYNAMIC_MACRO_USER_CALL` | *not defined* | Route macro handling through your `keymap.c` `process_record_user` (legacy stop-via-layer-key behavior). |
| `DYNAMIC_MACRO_NO_NESTING` | *not defined* | Disable calling a macro from within another macro. |
| `DYNAMIC_MACRO_DELAY` | *not defined* | Per-key delay (ms) when replaying. |
| `DYNAMIC_MACRO_KEEP_ORIGINAL_LAYER_STATE` | *not defined* | Keep layer state when starting to record (instead of switching to the macro layer). |

### Hooks (C API)

All take/return `direction`: `1` = Macro 1, `-1` = Macro 2, `0` = none.

| Callback | When called |
|---|---|
| `dynamic_macro_record_start_user(int8_t direction)` | Recording starts. |
| `dynamic_macro_play_user(int8_t direction)` | Playback starts. |
| `dynamic_macro_record_key_user(int8_t direction, keyrecord_t *record)` | Each keypress while recording. |
| `dynamic_macro_record_end_user(int8_t direction)` | Recording stops. |

Helper: `dynamic_macro_led_blink()` flashes backlights (if enabled) — also used internally to signal **buffer full** (LEDs blink on each keypress when out of space).

`DYNAMIC_MACRO_USER_CALL` legacy snippet (call at the top of `process_record_user`):

```c
uint16_t macro_kc = (keycode == MO(_DYN) ? DM_RSTP : keycode);
if (!process_record_dynamic_macro(macro_kc, record)) return false;
```

### Behavior & ordering

Dynamic Macro runs **very early** in `process_record_quantum` (right after Key Lock) so every keypress gets recorded. When `DYNAMIC_MACRO_USER_CALL` is **not** defined, `process_dynamic_macro()` is called by the core automatically and you do not invoke it yourself.

### Gotchas
- **Buffer overflow:** LEDs blink on each keypress when the buffer is full. Make the *other* macro shorter, or raise `DYNAMIC_MACRO_SIZE` (costs RAM).
- **Two macros, one buffer:** Macro 1 and Macro 2 share the `DYNAMIC_MACRO_SIZE` budget.
- **No recursion:** never record a macro that plays itself (e.g. Macro 1 replaying Macro 1) — the keyboard will hang; unplug to recover. Cross-replaying (Macro 2 inside Macro 1) is fine. Define `DYNAMIC_MACRO_NO_NESTING` to forbid nesting entirely.
- Not persistent across reboots/unplugs (unlike static/JSON macros).
- Default direction sign convention is `1` / `-1` / `0`, not `1` / `2`.

---

## 4. Autocorrect

**Summary.** Maintains a small buffer of recent keypresses; on each press checks whether the buffer ends in a recognized typo and, if so, sends backspaces + the correction. Typos are stored as a compact **trie** (PROGMEM), queried in reverse from the last letter.

### Enable it

```make
# rules.mk
AUTOCORRECT_ENABLE = yes
```

A small sample dictionary is included by default; provide your own via the generator (below). Autocorrect ships **disabled at runtime** — toggle it on with `AC_TOGG` (state is persisted to EEPROM).

### Dictionary format & generation

Text file, one entry per line: `typo  ->  correction`.

```text
:thier        -> their
fitler        -> filter
lenght        -> length
```

Rules:
- Syntax is `typo -> correction`. Case-insensitive; surrounding whitespace ignored.
- **Typo** may contain only letters `a–z` and the special word-break char `:`. **Correction** may have any non-unicode characters.
- Leading/trailing `:` constrains matching (word break). `:` matches space, period, comma, underscore, digits, and most non-alpha characters.

| Pattern | whole-word `thier` | `thiers` | `wealthier` |
|---|:---:|:---:|:---:|
| `thier` | ✓ | ✓ | ✓ |
| `:thier` | ✓ | ✓ | ✗ |
| `thier:` | ✓ | ✗ | ✓ |
| `:thier:` | ✓ | ✗ | ✗ |

Generate the trie header:

```sh
qmk generate-autocorrect-data autocorrect_dictionary.txt
# optionally: -kb <keyboard> -km <keymap>
```

Produces `autocorrect_data.h` (defines `AUTOCORRECT_MIN_LENGTH`, `AUTOCORRECT_MAX_LENGTH`, `DICTIONARY_SIZE`, and the PROGMEM byte array). Place it in your keymap/userspace folder and it is picked up automatically. The generator can flag false-trigger substrings using the `english_words` Python package (`python3 -m pip install english_words`); limited to English.

### Keycodes

| Keycode | Alias | Description |
|---|---|---|
| `QK_AUTOCORRECT_ON` | `AC_ON` | Turn Autocorrect on. |
| `QK_AUTOCORRECT_OFF` | `AC_OFF` | Turn Autocorrect off. |
| `QK_AUTOCORRECT_TOGGLE` | `AC_TOGG` | Toggle Autocorrect. |

Status API: `autocorrect_enable()`, `autocorrect_disable()`, `autocorrect_toggle()`, `autocorrect_is_enabled()`.

### How it hooks typing (callbacks)

Autocorrect only matches **8-bit basic keycodes**. Because quantum keycodes (Mod-Tap, Layer-Tap, swap hands, etc.) are 16-bit, you must sanitize them. Override the **weak** default callback:

```c
bool process_autocorrect_user(uint16_t *keycode, keyrecord_t *record,
                              uint8_t *typo_buffer_size, uint8_t *mods);
```

- `return false` → skip this keycode for autocorrect. Also set `*typo_buffer_size = 0` to reset the buffer.
- Mask shifted keys: for `QK_LSFT…QK_LSFT+255` set `*mods |= MOD_LSFT` and `*keycode &= 0xFF` (get the basic keycode).
- Exclude tap-hold *holds* (`!record->tap.count` → return false) but pass through taps (`*keycode &= 0xFF`).
- The default implementation already handles most QMK keycodes and disables autocorrect when a non-Shift modifier is held.

The correction application hook:

```c
bool apply_autocorrect(uint8_t backspaces, const char *str, char *typo, char *correct);
```

- `backspaces` = how many backspaces to send; `str` = replacement (PROGMEM pointer); `typo`/`correct` = best-effort complete words (may be imprecise, e.g. `wordtpyo` vs `wordtypo`).
- `return true` → let core do the correction. `return false` → you handle it (must tap backspaces + `send_string_P(str)` yourself).
- **`str` is PROGMEM** — use `send_string_P`, **not** `send_string`/`SEND_STRING`.

### Example (audio on correct + manual application)

```c
#ifdef AUDIO_ENABLE
float autocorrect_song[][2] = SONG(TERMINAL_SOUND);
#endif

bool apply_autocorrect(uint8_t backspaces, const char *str, char *typo, char *correct) {
#ifdef AUDIO_ENABLE
    PLAY_SONG(autocorrect_song);
#endif
    for (uint8_t i = 0; i < backspaces; ++i) tap_code(KC_BSPC);
    send_string_P(str);
    return false;
}
```

### Overriding autocorrect

To intentionally type a typo: type the typo, but before the last letter press+release **Ctrl or Alt** (any non-Shift modifier). Autocorrect resets whenever a non-Shift modifier is held. Or just use `AC_TOGG`.

### Gotchas
- `str` in `apply_autocorrect` is **PROGMEM** — `send_string_P` only.
- Only 8-bit basic keycodes are matched; sanitize 16-bit quantum keycodes in `process_autocorrect_user` or typos silently fail to detect.
- Buffer min/max lengths are derived from the dictionary at generation time (`AUTOCORRECT_MIN_LENGTH`/`AUTOCORRECT_MAX_LENGTH`).
- The `typo`/`correct` strings passed to `apply_autocorrect` are heuristic and can include surrounding letters — don't rely on them for exact matching.
- The trie is stored reversed (queried from the last letter backwards).
- False-trigger detection in the generator is English-only.

---

## 5. Caps Word

**Summary.** A modern alternative to Caps Lock: while active, letters are capitalized and `-` becomes `_`. Auto-disables at the end of the "word" (a word-breaking key) or after an idle timeout.

### Enable it

```make
# rules.mk
CAPS_WORD_ENABLE = yes
```

### Activation

- **Key:** `QK_CAPS_WORD_TOGGLE` (alias `CW_TOGG`).
- **Both shifts:** `#define BOTH_SHIFTS_TURNS_ON_CAPS_WORD` in `config.h`. (Conflicts with Command — disable Command or remap `IS_COMMAND()`.)
- **Double-tap Left Shift:** `#define DOUBLE_TAP_SHIFT_TURNS_ON_CAPS_WORD`. Max time between taps is `TAPPING_TERM` (or `get_tapping_term()`). Works with `KC_LSFT` or `OSM(MOD_LSFT)`.
- **From code:** call `caps_word_on()` (e.g. from a combo or tap dance).

### Configuration

| `config.h` define | Default | Meaning |
|---|---|---|
| `BOTH_SHIFTS_TURNS_ON_CAPS_WORD` | *not defined* | Activate by pressing both shifts. |
| `DOUBLE_TAP_SHIFT_TURNS_ON_CAPS_WORD` | *not defined* | Activate by double-tapping Left Shift. |
| `CAPS_WORD_IDLE_TIMEOUT` | `5000` (ms) | Auto-disable after this idle time. `0` = never time out. |
| `CAPS_WORD_INVERT_ON_SHIFT` | *not defined* | Pressing Shift while Caps Word is on continues it and inverts shift (e.g. `DBaaS`, `PDFs`). One-shot shifts behave like normal shifts while on. |

### Keycodes / functions

| Function | Description |
|---|---|
| `QK_CAPS_WORD_TOGGLE` / `CW_TOGG` | Toggle Caps Word. |
| `caps_word_on()` / `caps_word_off()` / `caps_word_toggle()` | Control Caps Word from code. |
| `is_caps_word_on()` | True if currently active. |
| `caps_word_set_user(bool active)` | Callback when Caps Word turns on/off (for LEDs/sound). |
| `caps_word_press_user(uint16_t keycode)` | Called on each keypress while active. Return `true` to continue the word, `false` to break (deactivate). Call `add_weak_mods(MOD_BIT(KC_LSFT))` to shift the key. |

### Continuation rules (default `caps_word_press_user`)

While Caps Word is on, these keys **continue** the word:
- **Shifted:** `KC_A`…`KC_Z`, `KC_MINS` (→ `_`).
- **Unshifted:** `KC_1`…`KC_0`, `KC_BSPC`, `KC_DEL`, `KC_UNDS`.

Everything else **breaks** the word and deactivates Caps Word.

```c
bool caps_word_press_user(uint16_t keycode) {
    switch (keycode) {
        case KC_A ... KC_Z:
        case KC_MINS:
            add_weak_mods(MOD_BIT(KC_LSFT));
            return true;
        case KC_1 ... KC_0:
        case KC_BSPC:
        case KC_DEL:
        case KC_UNDS:
            return true;
        default:
            return false;
    }
}
```

> **API note:** the per-key callback in this firmware revision is `caps_word_press_user(uint16_t keycode)` (takes a keycode, returns bool). There is **no** `get_caps_word_pressing` getter in this revision — drive behavior through the callback's return value and `is_caps_word_on()`.

### Gotchas
- **Does not use `KC_CAPS`** — works even if you remap Caps Lock at the OS level (great for Emacs/Vim users). But this also means it does **not** follow OS Caps Lock semantics; on non-US/UK layouts some keys behave unexpectedly (e.g. Dvorak `,` / `KC_W` gets shifted; Spanish `Ñ` / `KC_SCLN` does not get capitalized). Override `caps_word_press_user` to fix.
- `BOTH_SHIFTS_TURNS_ON_CAPS_WORD` conflicts with **Command** (both use LSFT+RSFT). Disable Command (`COMMAND_ENABLE = no`) or remap `IS_COMMAND()`.
- With mod-tap shifts + both-shifts activation: hold both until tapping term, then release.
- `CAPS_WORD_INVERT_ON_SHIFT`: one-shot shifts behave like regular (held) shifts while Caps Word is on.

---

## 6. Repeat Key & Alternate Repeat Key

**Summary.** Repeat Key re-performs the last pressed key (with its mods). Alternate Repeat Key performs a defined "alternate" (default: reverse-direction for navigation keys). Caps Word and Repeat Key compose (see gotchas).

### Enable it

```make
# rules.mk
REPEAT_KEY_ENABLE = yes
```

Alternate Repeat is enabled by default alongside Repeat Key; disable it to save space with `#define NO_ALT_REPEAT_KEY` in `config.h`.

### Keycodes

| Keycode | Alias | Description |
|---|---|---|
| `QK_REPEAT_KEY` | `QK_REP` | Repeat the last pressed key. |
| `QK_ALT_REPEAT_KEY` | `QK_AREP` | Perform the alternate of the last key. |

### Default alternate definitions

Where it makes sense, these include mod combinations (Ctrl/Alt/GUI + key).

- **Navigation:** `KC_LEFT`↔`KC_RGHT`, `KC_UP`↔`KC_DOWN`, `KC_HOME`↔`KC_END`, `KC_PGUP`↔`KC_PGDN`, and mouse `MS_LEFT`↔`MS_RGHT`, `MS_UP`↔`MS_DOWN`, `MS_WHLL`↔`MS_WHLR`, `MS_WHLU`↔`MS_WHLD`.
- **Misc:** `KC_BSPC`↔`KC_DEL`, `KC_LBRC`↔`KC_RBRC`, `KC_LCBR`↔`KC_RCBR`.
- **Media:** `KC_WBAK`↔`KC_WFWD`, `KC_MNXT`↔`KC_MPRV`, `KC_MFFD`↔`KC_MRWD`, `KC_VOLU`↔`KC_VOLD`, `KC_BRIU`↔`KC_BRID`.
- **Vim/Emacs-style (mod = Ctrl/Alt/GUI):** mod+`F`↔mod+`B`, mod+`D`↔mod+`U`, mod+`N`↔mod+`P`, mod+`A`↔mod+`E`, mod+`O`↔mod+`I`, `KC_J`↔`KC_K`, `KC_H`↔`KC_L`, `KC_W`↔`KC_B`.

### Callbacks / functions

| Function | Purpose |
|---|---|
| `uint16_t get_alt_repeat_key_keycode_user(uint16_t keycode, uint8_t mods)` | Define/override alternates. Return `KC_NO` (do nothing), `KC_TRNS` (use default), or a keycode. |
| `bool remember_last_key_user(uint16_t keycode, keyrecord_t *record, uint8_t *remembered_mods)` | Control which keys/mods are eligible for repeating. Return `false` to ignore a key; mutate `*remembered_mods` to forget mods. |
| `get_last_keycode()` / `get_last_mods()` | Inspect the remembered key. |
| `set_last_keycode(kc)` / `set_last_mods(mods)` | Set what will be repeated (e.g. from a macro). |
| `get_repeat_key_count()` | Signed count: 0 normal press, +1/+2… on repeats, −1/−2… on alternate repeats. Use inside `process_record_user` to vary macro behavior. |
| `get_alt_repeat_key_keycode()` | The keycode that will be used for alternate repeating. |

### Examples

Define Ctrl+Y ↔ Ctrl+Z:

```c
uint16_t get_alt_repeat_key_keycode_user(uint16_t keycode, uint8_t mods) {
    if ((mods & MOD_MASK_CTRL)) {
        switch (keycode) {
            case KC_Y: return C(KC_Z);
            case KC_Z: return C(KC_Y);
        }
    }
    return KC_TRNS;
}
```

Ignore Backspace from being remembered; forget Shift on letters (so "Aaron" doesn't become "AAron"):

```c
bool remember_last_key_user(uint16_t keycode, keyrecord_t* record, uint8_t* remembered_mods) {
    switch (keycode) {
        case KC_BSPC: return false;
        case KC_A ... KC_Z:
            if ((*remembered_mods & ~(MOD_MASK_SHIFT | MOD_BIT(KC_RALT))) == 0)
                *remembered_mods &= ~MOD_MASK_SHIFT;
            break;
    }
    return true;
}
```

Macro as alternate repeat (Alt Repeat presses a macro keycode):

```c
uint16_t get_alt_repeat_key_keycode_user(uint16_t keycode, uint8_t mods) {
    switch (keycode) {
        case KC_K:   return M_KEYBOARD;   // k + AltRep => "keyboard"
        case KC_DOT: return M_UPDIR;      // . + AltRep => "../"
    }
    return KC_TRNS;
}
```

### Behavior & ordering

Repeat Key runs **early** in `process_record_quantum` (`process_last_key` then `process_repeat_key`), before `process_record_user`. Modifiers and layer-switch keys are **always ignored** when tracking "the last key," so you can change mods/layers between a key and its repeat.

### Gotchas
- **Caps Word + Repeat Key interaction:** Repeat Key tracks the last key independently of Caps Word. If you repeat a letter while Caps Word is on, Caps Word's `caps_word_press_user` still applies its own shift — so a repeated letter stays capitalized as expected. Because Repeat Key replays the *remembered mods* (which may include the Caps Word shift), test shifted-letter repeats; use `remember_last_key_user` to forget Shift on letters if you get doubled capitals ("AAron").
- `KC_TRNS` vs `KC_NO` return semantics from `get_alt_repeat_key_keycode_user` are easy to mix up: `KC_NO` disables any alternate; `KC_TRNS` defers to the default table.
- Any keycode (including custom macro keycodes) may be returned as an alternate.
- `get_repeat_key_count()` is the way to make a *macro* keycode behave differently when repeated vs alternate-repeated vs pressed normally.
- Defining `NO_ALT_REPEAT_KEY` saves firmware size.

---

## 7. Combos

**Summary.** Chording: press multiple keys at once within a "combo term" to emit a different keycode or run a custom action (e.g. `A`+`B` → `ESC`). Runs **very early** in the pipeline (in `pre_process_record_quantum`), before `process_record_user`.

### Enable it

```make
# rules.mk
COMBO_ENABLE = yes
```

Define combos in `keymap.c`:

```c
const uint16_t PROGMEM test_combo1[] = {KC_A, KC_B, COMBO_END};   // MUST end with COMBO_END
combo_t key_combos[] = {
    COMBO(test_combo1, KC_ESC),
    COMBO(test_combo2, LCTL(KC_Z)),   // keycodes with mods are allowed
};
```

- Advanced keycodes (Mod-Tap, Layer-Tap, Tap Dance) are supported in the chord — put the full keycode in the array.
- Overlapping combos: the **longest** matching chord wins (3-key combo beats its 2-key subset when all three are pressed).
- `COMBO_ACTION(arr)` = `COMBO(arr, KC_NO)`; handle it in `process_combo_event(uint16_t combo_index, bool pressed)`. (Newer style: just use a custom keycode and handle it in `process_record_user`.)

### Keycodes

| Keycode | Alias | Description |
|---|---|---|
| `QK_COMBO_ON` | `CM_ON` | Turn Combos on. |
| `QK_COMBO_OFF` | `CM_OFF` | Turn Combos off (clears combo buffer). |
| `QK_COMBO_TOGGLE` | `CM_TOGG` | Toggle Combos. |

Functions: `combo_enable()`, `combo_disable()`, `combo_toggle()`, `is_combo_enabled()`.

### Configuration (combo term & buffers)

| `config.h` define | Default | Meaning |
|---|---|---|
| `COMBO_TERM` | `50` (ms) | Window for the chord to be recognized. |
| `COMBO_HOLD_TERM` | `TAPPING_TERM` | Window for **modifier** combos (only with `COMBO_MUST_HOLD_MODS`). |
| `COMBO_MUST_HOLD_MODS` | *not defined* | Extend the window for combos resolving to a modifier; can no longer be tapped (less misfire-prone). |
| `COMBO_MUST_PRESS_IN_ORDER` | *not defined* | Combos only fire if keys are pressed in the defined order. |
| `EXTRA_SHORT_COMBOS` | *not defined* | Max **6** keys/combo (packs state into 1 byte). |
| *(default)* | — | Max **8** keys/combo. |
| `EXTRA_LONG_COMBOS` | *not defined* | Max **16** keys/combo. |
| `EXTRA_EXTRA_LONG_COMBOS` | *not defined* | Max **32** keys/combo. |
| `COMBO_KEY_BUFFER_LENGTH` | `8` | Key-press buffer size. |
| `COMBO_BUFFER_LENGTH` | `4` | Active-combo buffer size. |
| `COMBO_STRICT_TIMER` | *not defined* | Timer starts only on first key; full chord must land within `COMBO_TERM`. |
| `COMBO_NO_TIMER` | *not defined* | No timer; combos activate on first key release (disables must-hold). |
| `COMBO_ONLY_FROM_LAYER` | *(not defined)* | If set to a layer index, combo keys are always read from that layer (e.g. `0` for layout-independent combos). |

### Per-combo & advanced hooks

Each requires its `config.h` flag and the matching function:

| Flag | Function | Default | Purpose |
|---|---|---|---|
| `COMBO_TERM_PER_COMBO` | `uint16_t get_combo_term(uint16_t index, combo_t *combo)` | `COMBO_TERM` | Per-combo term. |
| `COMBO_MUST_HOLD_PER_COMBO` | `bool get_combo_must_hold(uint16_t index, combo_t *combo)` | `false` | Must hold vs tap-fire. |
| `COMBO_MUST_TAP_PER_COMBO` | `bool get_combo_must_tap(uint16_t index, combo_t *combo)` | `false` | Fire only if tapped within `COMBO_HOLD_TERM`. |
| `COMBO_MUST_PRESS_IN_ORDER_PER_COMBO` | `bool get_combo_must_press_in_order(uint16_t index, combo_t *combo)` | `true` | Per-combo order enforcement. |
| `COMBO_SHOULD_TRIGGER` | `bool combo_should_trigger(uint16_t index, combo_t *combo, uint16_t keycode, keyrecord_t *record)` | — | Generic allow/deny (e.g. disable on a layer). |
| `COMBO_PROCESS_KEY_RELEASE` | `bool process_combo_key_release(uint16_t index, combo_t *combo, uint8_t key_index, uint16_t keycode)` | — | Custom code on each key release after a combo activates; `return true` to release the combo early. |
| `COMBO_PROCESS_KEY_REPRESS` | `bool process_combo_key_repress(uint16_t index, combo_t *combo, uint8_t key_index, uint16_t keycode)` | — | Custom code on repress of a just-released combo key. |

Per-combo reference layer: `COMBO_REF_LAYER(layer, ref_layer)` / `DEFAULT_REF_LAYER(layer)` macros (or implement `uint8_t combo_ref_from_layer(uint8_t layer)`).

### Dictionary management (gboards)

Add `VPATH += keyboards/gboards` to `rules.mk`, `#include "g/keymap_combo.h"` in `keymap.c`, then write `combos.def` with `COMB(name, result, keys…)`, `SUBS(name, "string", keys…)`, and `COMBO_REF_LAYER`/`DEFAULT_REF_LAYER` entries. **Note:** this consumes `process_combo_event`, so put your `case`s in `inject.h` instead. Ready-made dictionaries: http://combos.gboards.ca/

### Example (custom action)

```c
enum combo_events { EM_EMAIL, BSPC_LSFT_CLEAR };
const uint16_t PROGMEM email_combo[]      = {KC_E, KC_M, COMBO_END};
const uint16_t PROGMEM clear_line_combo[] = {KC_BSPC, KC_LSFT, COMBO_END};

combo_t key_combos[] = {
    [EM_EMAIL]         = COMBO_ACTION(email_combo),
    [BSPC_LSFT_CLEAR]  = COMBO_ACTION(clear_line_combo),
};

void process_combo_event(uint16_t combo_index, bool pressed) {
    switch (combo_index) {
        case EM_EMAIL:
            if (pressed) SEND_STRING("john.doe@example.com");
            break;
        case BSPC_LSFT_CLEAR:
            if (pressed) { tap_code16(KC_END); tap_code16(S(KC_HOME)); tap_code16(KC_BSPC); }
            break;
    }
}
```

### Gotchas
- **Combos run in `pre_process_record_quantum` — the earliest stage**, before `process_record_user`. This is why combos can transparently intercept keys; it also means combo processing can delay regular key input slightly (unlike Key Overrides, which don't).
- Chord arrays **must** be `PROGMEM` and **must** end with `COMBO_END`.
- Long combos / many overlapping combos can overflow `COMBO_KEY_BUFFER_LENGTH` / `COMBO_BUFFER_LENGTH`; raise them (costs RAM).
- `EXTRA_SHORT_COMBOS` caps you at 6 keys/combo — don't combine with longer combos.
- Combos resolving to modifiers can misfire; use `COMBO_MUST_HOLD_MODS` + `COMBO_HOLD_TERM`.
- Default `get_combo_must_press_in_order` per-combo is **true** (different from the global `COMBO_MUST_PRESS_IN_ORDER` default of off) — mind the asymmetry.
- `COMBO_NO_TIMER` disables must-hold entirely.
- gboards dictionary mode hijacks `process_combo_event` — use `inject.h` for your cases.

---

## 8. Leader Key

**Summary.** Press `QK_LEAD`, then type a **sequence** of up to 5 keys; when the sequence ends (timeout/match), `leader_end_user()` runs and you match it against the buffer. Unlike Combos (simultaneous), Leader is sequential.

### Enable it

```make
# rules.mk
LEADER_ENABLE = yes
```

Add `QK_LEAD` (alias `QK_LEADER`) to your keymap.

### Keycodes / configuration

| Keycode | Alias | Description |
|---|---|---|
| `QK_LEADER` | `QK_LEAD` | Begin the leader sequence. |

| `config.h` define | Default | Meaning |
|---|---|---|
| `LEADER_TIMEOUT` | `300` (ms) | Time to complete the sequence after the leader key. |
| `LEADER_PER_KEY_TIMING` | *not defined* | Reset the timer on each key (good for long sequences; then lower `LEADER_TIMEOUT`, e.g. 250). |
| `LEADER_NO_TIMEOUT` | *not defined* | No timeout for the *first* key after the leader (lets you reposition your hand). |
| `LEADER_KEY_STRICT_KEY_PROCESSING` | *not defined* | Add the full Mod-Tap/Layer-Tap keycode to the buffer instead of just the tap keycode. |

### Callbacks & API

| Function | Purpose |
|---|---|
| `void leader_start_user(void)` | Called when the sequence begins. |
| `void leader_end_user(void)` | Called when the sequence ends — match the buffer here. |
| `bool leader_add_user(uint16_t keycode)` | Called when a keycode is added; return `true` to finish the sequence. |
| `void leader_start(void)` / `void leader_end(void)` | Begin/end the sequence from code. |
| `bool leader_sequence_active(void)` | Whether a sequence is in progress. |
| `bool leader_sequence_add(uint16_t keycode)` | Add a keycode to the buffer. |
| `bool leader_sequence_timed_out(void)` | Whether the timeout was reached. |
| `bool leader_reset_timer(void)` | Reset the sequence timer. |
| `bool leader_sequence_one_key(kc)` … `leader_sequence_five_keys(kc1…kc5)` | Match helpers (max **5** keys). |

By default only the **tap keycode** of Mod-Tap/Layer-Tap keys is buffered (e.g. `LT(3, KC_A)` adds `KC_A`). Enable `LEADER_KEY_STRICT_KEY_PROCESSING` to buffer the full keycode.

### Example

```c
void leader_end_user(void) {
    if (leader_sequence_one_key(KC_F)) {
        SEND_STRING("QMK is awesome.");
    } else if (leader_sequence_two_keys(KC_D, KC_D)) {
        SEND_STRING(SS_LCTL("a") SS_LCTL("c"));
    } else if (leader_sequence_three_keys(KC_D, KC_D, KC_S)) {
        SEND_STRING("https://start.duckduckgo.com\n");
    }
}
```

### Gotchas
- Max sequence length is **5** keys (`leader_sequence_five_keys` is the longest matcher).
- Default behavior buffers only the tap keycode of tap-hold keys; use `LEADER_KEY_STRICT_KEY_PROCESSING` if you need the full keycode.
- Without `LEADER_PER_KEY_TIMING`, you have one `LEADER_TIMEOUT` for the *whole* sequence — long sequences need a high timeout or per-key timing.
- `LEADER_NO_TIMEOUT` applies only to the gap between the leader key and the first sequence key.

---

## 9. Key Overrides

**Summary.** Override modifier+key combinations to send a different combination or run custom code. Unlike Combos (simultaneous non-modifier keys), Key Overrides work like OS shortcuts: **multiple modifiers + one non-modifier key**, with careful emulation of OS key-repeat/ordering semantics.

### Enable it

```make
# rules.mk
KEY_OVERRIDE_ENABLE = yes
```

Define `const key_override_t *key_overrides[]` in `keymap.c`.

### Initializers

| Helper | Description |
|---|---|
| `ko_make_basic(mods, key, replacement)` | Send `replacement` when `key` + `mods` are all down (activates even with extra mods). |
| `ko_make_with_layers(mods, key, replacement, layers)` | Add a layer bitmask. |
| `ko_make_with_layers_and_negmods(mods, key, replacement, layers, negative_mods)` | Add modifiers that must NOT be down. |
| `ko_make_with_layers_negmods_and_options(mods, key, replacement, layers, negative_mods, options)` | Add `ko_option_t` flags. |

### Keycodes

| Keycode | Alias | Description |
|---|---|---|
| `QK_KEY_OVERRIDE_TOGGLE` | `KO_TOGG` | Toggle key overrides. |
| `QK_KEY_OVERRIDE_ON` | `KO_ON` | Turn on. |
| `QK_KEY_OVERRIDE_OFF` | `KO_OFF` | Turn off. |

### Example

Shift+Backspace → Delete:

```c
const key_override_t delete_key_override = ko_make_basic(MOD_MASK_SHIFT, KC_BSPC, KC_DEL);
const key_override_t *key_overrides[] = { &delete_key_override };
```

macOS-friendly grave-escape replacement (no Grave Esc bugs):

```c
const key_override_t tilde_esc = ko_make_basic(MOD_MASK_SHIFT, KC_ESC, S(KC_GRV));
const key_override_t grave_esc = ko_make_basic(MOD_MASK_GUI,  KC_ESC, KC_GRV);
const key_override_t *key_overrides[] = { &tilde_esc, &grave_esc };
```

### `key_override_t` reference (advanced)

| Member | Description |
|---|---|
| `uint16_t trigger` | Non-modifier keycode that triggers the override (`KC_NO` = mods-only). |
| `uint8_t trigger_mods` | Mods required (use `MOD_MASK_*` / `MOD_BIT()`). Both sides of a mod → only one required. |
| `layer_state_t layers` | **Bitmask**: bit `i` set → active on layer `i`. |
| `uint8_t negative_mod_mask` | Mods that must NOT be down (`(active & neg) == 0` required). |
| `uint8_t suppressed_mods` | Mods hidden from the OS while the override is active. |
| `uint16_t replacement` | Keycode/mod-combo sent on activation (`KC_NO` = nothing). |
| `ko_option_t options` | Behavior flags (see below). |
| `bool (*custom_action)(bool activated, void *context)` | Custom handler; return `false` to suppress replacement register/unregister. |
| `void *context` | Passed to `custom_action`. |
| `bool *enabled` | Points to false → disabled; `NULL` = always enabled. |

### `ko_option_t` flags

`ko_option_activation_trigger_down`, `ko_option_activation_required_mod_down`, `ko_option_activation_negative_mod_up` (the three activation triggers; all on by default), `ko_option_one_mod` (OR vs AND of `trigger_mods`), `ko_option_no_unregister_on_other_key_down`, `ko_option_no_reregister_trigger`, `ko_options_default`.

### Behavior & ordering

Activation can happen on (1) trigger key down with mods already down, (2) required mod down with trigger already down, (3) negative mod released. The override only activates if `trigger` is the **last non-modifier key** pressed (emulating OS behavior). Deactivation: any trigger key lifted, another non-mod pressed, or a negative mod pressed. A **key repeat delay** (`KEY_OVERRIDE_REPEAT_DELAY`, default `500` ms) defers the replacement to mimic OS repeat behavior.

| `config.h` define | Default | Meaning |
|---|---|---|
| `KEY_OVERRIDE_REPEAT_DELAY` | `500` (ms) | Delay before the replacement is sent (mimics OS key-repeat delay). |
| `DUMMY_MOD_NEUTRALIZER_KEYCODE` | *not defined* | Basic HID keycode sent between register/unregister of a suppressed mod, to avoid false lone-mod taps (e.g. `KC_RIGHT_CTRL`, `KC_F18`). Must be basic/unmodified. |
| `MODS_TO_NEUTRALIZE` | `{MOD_BIT(KC_LEFT_ALT), MOD_BIT(KC_LEFT_GUI)}` | List of 8-bit mod masks to neutralize. **Use `MOD_BIT()`/`MOD_MASK_*`, not `MOD_LSFT` etc.** |

### Gotchas
- **Key Overrides ≠ Combos.** Overrides are modifier-shortcut style (mods + one non-mod key) and don't delay regular input; Combos are simultaneous non-mod chords and *do* introduce a small delay.
- `layers` is a **bitmask**, not a layer index — set `(1 << i)`.
- The override only fires if `trigger` is the *last* non-modifier key down (OS emulation). Plan ordering accordingly.
- Default key-repeat delay (`KEY_OVERRIDE_REPEAT_DELAY` = 500 ms) can make overrides feel sluggish; tune it.
- On macOS etc., suppressed mods can false-trigger menu-bar/app actions; set `DUMMY_MOD_NEUTRALIZER_KEYCODE`.
- In `MODS_TO_NEUTRALIZE` use `MOD_BIT(kc)`/`MOD_MASK_*` (8-bit), **never** `MOD_LSFT`/`MOD_RALT` (5-bit packed) — wrong width.
- Precedence: overrides are modifier-composition based and layer-aware via the bitmask; they do **not** participate in the layer stack the way `MO`/`LT` do (see `04-keymaps-and-keycodes.md`).

---

## 10. Key Lock

**Summary.** Press `QK_LOCK`, then the **next** key you press is held down until you press it again.

### Enable it

```make
# rules.mk
KEY_LOCK_ENABLE = yes
```

### Keycode

| Keycode | Description |
|---|---|
| `QK_LOCK` | Hold down the next key pressed until it is pressed again. |

### Behavior & ordering

Key Lock runs **first** in `process_record_quantum` (so it can mask key-up events). `cancel_key_lock()` cancels the lock from code.

### Gotchas
- Only holds **standard action keys** and **One-Shot Modifier** keys (e.g. `OSM(MOD_LSFT)`). No other QMK special functions, and no pre-shifted keys like `KC_LPRN`. If it's in the Basic Keycodes list, it can be held.
- Switching layers does **not** cancel the lock.

---

## 11. Layer Lock

**Summary.** "Locks" the current layer on (for layers reached via `MO`/`LT`/`OSL`/`TT`/`LM`), so you can release the momentary key and stay on the layer. Tap Layer Lock again (or a layer-off key like `TO(other)`) to unlock.

### Enable it

```make
# rules.mk
LAYER_LOCK_ENABLE = yes
```

### Keycode / configuration

| Keycode | Alias | Description |
|---|---|---|
| `QK_LAYER_LOCK` | `QK_LLCK` | Lock/unlock the highest active layer. |

| `config.h` define | Default | Meaning |
|---|---|---|
| `LAYER_LOCK_IDLE_TIMEOUT` | *not defined* | If set (ms), unlock after this idle time. |

### Functions

| Function | Description |
|---|---|
| `is_layer_locked(layer)` | Is `layer` locked? |
| `layer_lock_on(layer)` / `layer_lock_off(layer)` | Lock+on / unlock+off. |
| `layer_lock_invert(layer)` | Toggle lock. |
| `bool layer_lock_set_user(layer_state_t locked_layers)` | Callback on lock change; `locked_layers` is a bitfield (bit k = layer k locked). Return `true`. |

### Gotchas
- Locking the **base layer has no effect** — put the key on layers above base.
- `QK_LLCK` locks the **highest active layer**, regardless of which layer the key itself sits on (handy if other layers are transparent at that position).
- `QK_LLCK` is **not a basic keycode**, so `MT(mod, QK_LLCK)` is invalid. To make a mod-tap Layer Lock, use the "change tap function" pattern (intercept tap in `process_record_user` and call `layer_lock_invert(get_highest_layer(layer_state))`); same idea for layer-tap `LT`.

---

## 12. Space Cadet

**Summary.** Tap a Shift/Ctrl/Alt key alone → emit `(` or `)` (or Enter); hold it → normal modifier.

### Enable it

Enabled by default for the Shift parens variant; configure in `config.h`. No `rules.mk` toggle required for basic use.

### Keycodes

| Keycode | Alias | Description |
|---|---|---|
| `QK_SPACE_CADET_LEFT_CTRL_PARENTHESIS_OPEN` | `SC_LCPO` | LCtrl held, `(` tapped. |
| `QK_SPACE_CADET_RIGHT_CTRL_PARENTHESIS_CLOSE` | `SC_RCPC` | RCtrl held, `)` tapped. |
| `QK_SPACE_CADET_LEFT_SHIFT_PARENTHESIS_OPEN` | `SC_LSPO` | LShift held, `(` tapped. |
| `QK_SPACE_CADET_RIGHT_SHIFT_PARENTHESIS_CLOSE` | `SC_RSPC` | RShift held, `)` tapped. |
| `QK_SPACE_CADET_LEFT_ALT_PARENTHESIS_OPEN` | `SC_LAPO` | LAlt held, `(` tapped. |
| `QK_SPACE_CADET_RIGHT_ALT_PARENTHESIS_CLOSE` | `SC_RAPC` | RAlt held, `)` tapped. |
| `QK_SPACE_CADET_RIGHT_SHIFT_ENTER` | `SC_SENT` | RShift held, Enter tapped. |

### Configuration (modern bundled defines)

Each `*_KEYS` define is a triple: `Modifier (held)`, `Tap Modifier`, `Keycode (tapped)`. `KC_TRNS` as Tap Modifier = no modifier on tap.

| Define | Default | Description |
|---|---|---|
| `LSPO_KEYS` | `KC_LSFT, LSPO_MOD, LSPO_KEY` | LShift held; mod+key on tap. |
| `RSPC_KEYS` | `KC_RSFT, RSPC_MOD, RSPC_KEY` | RShift held; mod+key on tap. |
| `LCPO_KEYS` | `KC_LCTL, KC_LSFT, KC_9` | LCtrl held; Shift+`9` (`(`) on tap. |
| `RCPC_KEYS` | `KC_RCTL, KC_RSFT, KC_0` | RCtrl held; Shift+`0` (`)`) on tap. |
| `LAPO_KEYS` | `KC_LALT, KC_LSFT, KC_9` | LAlt held; Shift+`9` on tap. |
| `RAPC_KEYS` | `KC_RALT, KC_RSFT, KC_0` | RAlt held; Shift+`0` on tap. |
| `SFTENT_KEYS` | `KC_RSFT, KC_TRNS, SFTENT_KEY` | RShift held; no mod, key on tap. |
| `SPACE_CADET_MODIFIER_CARRYOVER` | *not defined* | Remember mods active before the hold mod and apply them to the tap mod/keycode. |

Legacy (back-compat) defines: `LSPO_KEY`=`KC_9`, `RSPC_KEY`=`KC_0`, `LSPO_MOD`=`KC_LSFT`, `RSPC_MOD`=`KC_RSFT`, `SFTENT_KEY`=`KC_ENT`, `DISABLE_SPACE_CADET_MODIFIER` (suppress tap modifier — superseded by `*_KEYS` with `KC_TRNS`).

### Gotchas
- Conflicts with **Command** when both Shift keys are held; disable Command (`COMMAND_ENABLE = no`) or remap `IS_COMMAND()`.
- Assumes **US ANSI** layout by default — redefine `*_KEYS` for other paren positions.
- Mods from other keys still apply to the tapped keycode (e.g. holding `KC_RSFT` while tapping `SC_LSPO` with `KC_TRNS` tap-mod).
- `SPACE_CADET_MODIFIER_CARRYOVER` is for users who release a modifier just before triggering Space Cadet.

---

## 13. Tap Dance

**Summary.** A single key behaves differently based on tap count (and hold/interruption). State machine: `on_each_tap` → `on_dance_finished` → `on_dance_reset`.

### Enable it

```make
# rules.mk
TAP_DANCE_ENABLE = yes
```

Adds ~1k to firmware. Optionally tune `TAPPING_TERM` (affects tap-dance *and* all tap-hold keys) and `TAPPING_TERM_PER_KEY` + `get_tapping_term()`.

| `config.h` define | Default | Meaning |
|---|---|---|
| `TAP_DANCE_MAX_SIMULTANEOUS` | `3` | Max concurrently active tap-dance keys; extras are ignored — raise it if you hold many at once. |

### Action macros

| Macro | Behavior |
|---|---|
| `ACTION_TAP_DANCE_DOUBLE(kc1, kc2)` | kc1 on single tap, kc2 otherwise; hold → appropriate keycode. |
| `ACTION_TAP_DANCE_LAYER_MOVE(kc, layer)` | kc on tap, `TO(layer)` otherwise. |
| `ACTION_TAP_DANCE_LAYER_TOGGLE(kc, layer)` | kc on tap, `TG(layer)` otherwise. |
| `ACTION_TAP_DANCE_FN(fn)` | Call `fn(state, user_data)` with final tap count. |
| `ACTION_TAP_DANCE_FN_ADVANCED(on_each_tap, on_dance_finished, on_dance_reset)` | Per-tap, finish, reset callbacks. |
| `ACTION_TAP_DANCE_FN_ADVANCED_WITH_RELEASE(on_each_tap, on_each_release, on_dance_finished, on_dance_reset)` | Adds an `on_each_release` called on every release (even after the dance finishes / on long hold). |

- Use `TD(index)` in the keymap; index into `tap_dance_action_t tap_dance_actions[]`.
- Only **basic keycodes** in the built-in macros. For custom/modified keycodes use `ACTION_TAP_DANCE_FN_ADVANCED` and `register_code16`/`unregister_code16`.
- End a dance immediately (skip `on_dance_finished`, not `on_dance_reset`) with `reset_tap_dance(state)`.

### State machine & ordering

Three entry points (cross-ref `01-architecture.md`):
- `preprocess_tap_dance()` — runs early in `process_record_quantum`; handles interruptions and enqueues keys.
- `process_tap_dance()` — runs *after* `process_record_kb`/`process_record_user`; calls `on_each_tap` and `on_dance_reset`.
- `tap_dance_task()` — periodic; finishes a dance when `TAPPING_TERM` elapsed since the last tap.

`tap_dance_state_t` fields used in custom dances: `count`, `pressed`, `interrupted`, `finished`. The timer resets on each tap, so you have `TAPPING_TERM` *between* taps (not for the whole sequence).

### Examples

Simple (Esc / Caps Lock):

```c
enum { TD_ESC_CAPS };
tap_dance_action_t tap_dance_actions[] = {
    [TD_ESC_CAPS] = ACTION_TAP_DANCE_DOUBLE(KC_ESC, KC_CAPS),
};
// in keymap: TD(TD_ESC_CAPS)
```

Per-key tapping term for tap dances:

```c
uint16_t get_tapping_term(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case QK_TAP_DANCE ... QK_TAP_DANCE_MAX: return 275;
        default: return TAPPING_TERM;
    }
}
```

Quad-function state decode (`cur_dance`) is the standard pattern for tap/hold/double-tap/double-hold/etc. — see source examples 4–6. Key state values: `TD_NONE`, `TD_UNKNOWN`, `TD_SINGLE_TAP`, `TD_SINGLE_HOLD`, `TD_DOUBLE_TAP`, `TD_DOUBLE_HOLD`, `TD_DOUBLE_SINGLE_TAP` (for fast typing like "pepper"), `TD_TRIPLE_TAP`, `TD_TRIPLE_HOLD`.

### Gotchas
- Only **basic keycodes** in the simple macros; use `FN_ADVANCED` + `register_code16` for modded/custom keycodes.
- `TAPPING_TERM` is **global** — changing it affects mod-tap/layer-tap too. Use `TAPPING_TERM_PER_KEY` + `get_tapping_term()` to scope a longer term to tap-dance keys only.
- "Hold" fires **after** the tap-dance timeout by default; for instant hold, drop the `state->interrupted` checks.
- Default `TAP_DANCE_MAX_SIMULTANUS` = 3 — holding more than 3 tap-dance keys at once silently drops the rest.
- Advanced tap dances on frequently-typed letters (e.g. `A`, `p`) are painful (e.g. "pepper"); prefer non-letter keys (z,q,x,j,k,v,b, F-keys, home/end, comma, semicolon).
- Tap Dance can't fully mimic `PERMISSIVE_HOLD`.
- For simple "non-basic keycode on tap + mod/layer on hold," a Mod-Tap/Layer-Tap with an intercepted tap function is often simpler and gets tap-hold options for free.

---

## 14. Tri Layer

**Summary.** OLKB-style Tri Layer: `TL_LOWR` and `TL_UPPR` are momentary like `MO`, but pressing **both** activates a third "adjust" layer.

### Enable it

```make
# rules.mk
TRI_LAYER_ENABLE = yes
```

### Keycodes / configuration

| Keycode | Alias | Description |
|---|---|---|
| `QK_TRI_LAYER_LOWER` | `TL_LOWR` | Momentary lower; enables adjust if upper also on. |
| `QK_TRI_LAYER_UPPER` | `TL_UPPR` | Momentary upper; enables adjust if lower also on. |

| `config.h` define | Default | Description |
|---|---|---|
| `TRI_LAYER_LOWER_LAYER` | `1` | The "lower" layer index. |
| `TRI_LAYER_UPPER_LAYER` | `2` | The "upper" layer index. |
| `TRI_LAYER_ADJUST_LAYER` | `3` | The "adjust" layer index. |

### Functions

| Function | Description |
|---|---|
| `set_tri_layer_lower_layer(layer)` / `set_tri_layer_upper_layer(layer)` / `set_tri_layer_adjust_layer(layer)` | Change a layer at runtime. |
| `set_tri_layer_layers(lower, upper, adjust)` | Set all three. |
| `get_tri_layer_lower_layer()` / `get_tri_layer_upper_layer()` / `get_tri_layer_adjust_layer()` | Get current values. |

### Behavior

"Upper"/"lower"/"adjust" are just labels. Layers process highest→lowest numeric value; values need not be consecutive. The runtime setters are **not persistent** — reset to defaults on power loss/cycle.

### Gotchas
- The runtime `set_tri_layer_*` settings are **volatile** — they reset on reboot. Persist them yourself if needed.
- Layer indices need not be consecutive, but higher layers mask lower ones (see `04-keymaps-and-keycodes.md` for the layer stack).
- `TRI_LAYER_*_LAYER` defaults are 1/2/3 — if your keymap uses different layer numbers, set them in `config.h`.

> **Note on `LAYER_STATE_8BIT`:** the Tri Layer doc itself does not reference `LAYER_STATE_8BIT`. Layer-state width is a separate, global config concern (see `03-config-and-info-json.md` / `01-architecture.md`): on AVR, `layer_state_t` is 8-bit by default (limiting you to layers 0–7) unless widened; ARM uses a wider type. If you assign Tri Layer layers ≥ 8 on AVR without widening layer state, they will not behave correctly.

---

## 15. Grave Escape

**Summary.** Share the grave/tilde key with Escape: `QK_GESC` sends `ESC` normally, `` ` `` when GUI held, `~` when Shift held.

### Enable it

Built-in; no `rules.mk` toggle. Put `QK_GESC` in your keymap (typically replacing `KC_GRV`).

### Keycode / configuration

| Keycode | Alias | Description |
|---|---|---|
| `QK_GRAVE_ESCAPE` | `QK_GESC` | ESC when pressed; `` ` `` when Shift or GUI held. |

| `config.h` define | Meaning |
|---|---|
| `GRAVE_ESC_ALT_OVERRIDE` | Always send ESC if Alt pressed. |
| `GRAVE_ESC_CTRL_OVERRIDE` | Always send ESC if Ctrl pressed. |
| `GRAVE_ESC_GUI_OVERRIDE` | Always send ESC if GUI pressed. |
| `GRAVE_ESC_SHIFT_OVERRIDE` | Always send ESC if Shift pressed. |

### Gotchas
- **macOS:** Cmd+`` ` `` is mapped to "Move focus to next window" by default, so it will **not** output a backtick. Terminal always intercepts it to cycle windows even if remapped.
- Breaks **Ctrl+Shift+Esc** (Windows Task Manager) and **Cmd+Opt+Esc** (macOS force-quit). Use the `*_OVERRIDE` defines to restore ESC for those combos.
- For more flexibility and to avoid the macOS bugs, prefer **Key Overrides** (§9) over Grave Escape.

---

## 16. Auto Shift

**Summary.** Tap a key → its character; hold it slightly longer → its shifted state. No Shift key needed. Times out via `AUTO_SHIFT_TIMEOUT`.

### Enable it

```make
# rules.mk
AUTO_SHIFT_ENABLE = yes
```

### Keycodes (setup helpers)

| Keycode | Alias | Description |
|---|---|---|
| `QK_AUTO_SHIFT_DOWN` | `AS_DOWN` | Lower the timeout. |
| `QK_AUTO_SHIFT_UP` | `AS_UP` | Raise the timeout. |
| `QK_AUTO_SHIFT_REPORT` | `AS_RPT` | Type the current timeout value. |
| `QK_AUTO_SHIFT_ON` | `AS_ON` | Turn Auto Shift on. |
| `QK_AUTO_SHIFT_OFF` | `AS_OFF` | Turn Auto Shift off. |
| `QK_AUTO_SHIFT_TOGGLE` | `AS_TOGG` | Toggle Auto Shift. |

### Configuration (timing & scope)

| `config.h` define | Default | Meaning |
|---|---|---|
| `AUTO_SHIFT_TIMEOUT` | `175` (ms) | Hold longer than this → shifted. Start high, work down (~135–150 typical). |
| `AUTO_SHIFT_TIMEOUT_PER_KEY` | *not defined* | Enable per-key timeout via `get_autoshift_timeout()`. |
| `AUTO_SHIFT_MODIFIERS` | *not defined* | Apply Auto Shift even when modifiers are held (default: disabled with mods). |
| `AUTO_SHIFT_REPEAT` | *not defined* | Enable keyrepeat of the shifted key on long hold. |
| `AUTO_SHIFT_NO_AUTO_REPEAT` | *not defined* | Disable automatic keyrepeat. |
| `AUTO_SHIFT_REPEAT_PER_KEY` / `AUTO_SHIFT_NO_AUTO_REPEAT_PER_KEY` | *not defined* | Per-key control via `get_auto_shift_repeat()` / `get_auto_shift_no_auto_repeat()`. |
| `NO_AUTO_SHIFT_SPECIAL` | *not defined* | Don't auto-shift special keys (symbols + `KC_TAB`). |
| `NO_AUTO_SHIFT_TAB` | *not defined* | Don't auto-shift `KC_TAB` (keep other specials). |
| `NO_AUTO_SHIFT_SYMBOLS` | *not defined* | Don't auto-shift symbol keys (`-_ =+ [{ ]} ;: '" ,< .> /?`). |
| `NO_AUTO_SHIFT_NUMERIC` | *not defined* | Don't auto-shift 0–9. |
| `NO_AUTO_SHIFT_ALPHA` | *not defined* | Don't auto-shift A–Z. |
| `AUTO_SHIFT_ENTER` | *not defined* | Auto-shift `KC_ENT`. |
| `RETRO_SHIFT` | *not defined* | Holding+releasing a tap-hold key with no interrupt produces the shifted tap keycode. If set to a value (ms), holds longer than that trigger the hold action instead. |
| `AUTO_SHIFT_NO_SETUP` | *not defined* | Disable the AS_UP/AS_DOWN/AS_RPT setup keys (after you've tuned the timeout). |

Predefined key groups: `AUTO_SHIFT_ALPHA` (A–Z), `AUTO_SHIFT_NUMERIC` (1–0), `AUTO_SHIFT_SYMBOLS` (the symbol set above), `AUTO_SHIFT_SPECIAL` (symbols + `KC_TAB`).

### Per-key callbacks

| Function | Purpose |
|---|---|
| `uint16_t get_autoshift_timeout(uint16_t keycode, keyrecord_t *record)` | Per-key timeout (needs `AUTO_SHIFT_TIMEOUT_PER_KEY`). Use `get_generic_autoshift_timeout()` for the base value. |
| `bool get_auto_shifted_key(uint16_t keycode, keyrecord_t *record)` | Default decider (group-based); override fully to change scope. |
| `bool get_custom_auto_shifted_key(uint16_t keycode, keyrecord_t *record)` | Add extra keys (e.g. `KC_DOT`) on top of defaults. Enabled by default. |
| `void autoshift_press_user(uint16_t keycode, bool shifted, keyrecord_t *record)` | Register the correct (possibly custom) shifted value. Use **weak mods** (`add_weak_mods`). |
| `void autoshift_release_user(uint16_t keycode, bool shifted, keyrecord_t *record)` | Unregister counterpart. |
| `get_auto_shift_repeat()` / `get_auto_shift_no_auto_repeat()` | Per-key repeat control (needs the matching `_PER_KEY` define). |

### Custom shifted values (example: `.` → `!`)

```c
bool get_custom_auto_shifted_key(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) { case KC_DOT: return true; default: return false; }
}

void autoshift_press_user(uint16_t keycode, bool shifted, keyrecord_t *record) {
    switch (keycode) {
        case KC_DOT: register_code16((!shifted) ? KC_DOT : KC_EXLM); break;
        default:
            if (shifted) add_weak_mods(MOD_BIT(KC_LSFT));
            register_code16((IS_RETRO(keycode)) ? keycode & 0xFF : keycode);
    }
}
```

### Retro Shift (tap-hold integration)

`#define RETRO_SHIFT` (optionally a ms value). Hold+release of a tap-hold key with no interrupting key → shifted tap keycode. If set to a value, holds longer than that value trigger the hold action (good for mod+mouse-click combos). The value must exceed your `TAPPING_TERM`; use per-key tapping terms as a workaround. `RETRO_SHIFT` implies `PERMISSIVE_HOLD`-like behavior on applicable mod-taps. Tap-hold keys must be added to Auto Shift (via `get_custom_auto_shifted_key`); `IS_RETRO` helps identify them. `RETRO_TAPPING_PER_KEY` is checked before retro shift applies.

### Caps/curly modes

"Auto Shift special keys" includes the curly/symbol set (`[{ ]}`), so Auto Shift applies to them by default — disable with `NO_AUTO_SHIFT_SPECIAL` (all symbols + Tab) or `NO_AUTO_SHIFT_SYMBOLS` (symbols only, keep Tab). There is no separate "curly mode"; it's part of `AUTO_SHIFT_SYMBOLS`.

### Gotchas
- **Auto Shift does not apply to tap-hold keys** by default — use Retro Shift (and add the tap-hold key via `get_custom_auto_shifted_key`) for that.
- With keyrepeat, the shift state always "belongs" to the last key pressed — repeating a capital then tapping a lowercase key can leave the capital's key held but shift not.
- Default `AUTO_SHIFT_TIMEOUT` is 175 ms; start there and decrease. Use `AS_UP`/`AS_DOWN`/`AS_RPT` to tune live, then bake the value into `config.h` and add `AUTO_SHIFT_NO_SETUP`.
- In `autoshift_press_user`, use **weak mods** (`add_weak_mods`), not real mods, or subsequent keys get shifted too. Auto Shift clears mods itself.
- `IS_RETRO(keycode) ? keycode & 0xFF : keycode` is required when using Retro Shift with tap-holds (gets the tap keycode).
- You cannot override individual keys inside a group case (`AUTO_SHIFT_ALPHA`) in the same switch — use a separate earlier switch for individual keys.
- `RETRO_SHIFT` (if set to a value) must be greater than `TAPPING_TERM`.

---

## 17. Swap-Hands Action (one-handed mirroring)

Swap-Hands mirrors your layout left↔right for **one-handed typing without a separate layer**. While active, each key is looked up at a mirrored matrix position defined by a config table, so the *same* keymap serves both normal and mirrored typing. `SWAP_HANDS_ENABLE = yes` in `rules.mk`. (Not exposed as an `info.json` feature block — `rules.mk` only.)

### Keycodes

| Key | Alias | Description |
|---|---|---|
| `SH_T(kc)` | | Momentary swap when held, `kc` when tapped |
| `QK_SWAP_HANDS_ON` | `SH_ON` | Turn swap on (latched) |
| `QK_SWAP_HANDS_OFF` | `SH_OFF` | Turn swap off |
| `QK_SWAP_HANDS_MOMENTARY_ON` | `SH_MON` | Swap on while held |
| `QK_SWAP_HANDS_MOMENTARY_OFF` | `SH_MOFF` | Swap off while held |
| `QK_SWAP_HANDS_TOGGLE` | `SH_TOGG` | Toggle swap |
| `QK_SWAP_HANDS_TAP_TOGGLE` | `SH_TT` | Momentary when held, toggle when tapped (5 taps = toggle, via `TAPPING_TOGGLE`) |
| `QK_SWAP_HANDS_ONE_SHOT` | `SH_OS` | Swap on while held or until next key press |

### Configuration — the `hand_swap_config` table

Swap-Hands mirrors by **matrix position**, not keycode. You define a 2-D table mapping every `[row][col]` to its mirrored `{col, row}`. Values are `keypos_t` which is **`{col, row}` (column first!)** and zero-based — the reversed order vs. C's `[row][col]` indexing is the classic source of confusion. Example (Planck 12×4):

```c
const keypos_t PROGMEM hand_swap_config[MATRIX_ROWS][MATRIX_COLS] = {
  {{11, 0}, {10, 0}, {9, 0}, {8, 0}, {7, 0}, {6, 0}, {5, 0}, {4, 0}, {3, 0}, {2, 0}, {1, 0}, {0, 0}},
  {{11, 1}, {10, 1}, {9, 1}, {8, 1}, {7, 1}, {6, 1}, {5, 1}, {4, 1}, {3, 1}, {2, 1}, {1, 1}, {0, 1}},
  {{11, 2}, {10, 2}, {9, 2}, {8, 2}, {7, 2}, {6, 2}, {5, 2}, {4, 2}, {3, 2}, {2, 2}, {1, 2}, {0, 2}},
  {{11, 3}, {10, 3}, {9, 3}, {8, 3}, {7, 3}, {6, 3}, {5, 3}, {4, 3}, {3, 3}, {2, 3}, {1, 3}, {0, 3}},
};
```

`hand_swap_config[2][4]` (3rd row, 5th col) → `{7, 2}` (3rd row, 8th col). PROGMEM is correct (it's read-only).

### C API / callbacks

| Function | Description |
|---|---|
| `swap_hands_on()` | Turn swap on. |
| `swap_hands_off()` | Turn swap off. |
| `swap_hands_toggle()` | Toggle swap. |
| `is_swap_hands_on()` | `true` if swap currently active. |

### Encoder swapping (with encoder map)

If you use `ENCODER_MAP_ENABLE`, encoders can also swap between sides. Indices are left-to-right and the array length must equal `NUM_ENCODERS`. For a split with one encoder per half:

```c
#if defined(SWAP_HANDS_ENABLE) && defined(ENCODER_MAP_ENABLE)
const uint8_t PROGMEM encoder_hand_swap_config[NUM_ENCODERS] = { 1, 0 };
#endif
```

### Behavior & ordering

- The tap-hold decision options (`TAPPING_TERM`, permissive/hold-on-other-key, etc.) **do apply** to `SH_T` and `SH_TT` (see `04-keymaps-and-keycodes.md` tap-hold section), unlike Tap Dance.
- `SH_TT` tap-toggle works like layer `TT`: tapping `TAPPING_TOGGLE` times (default 5) toggles swap on/off.
- Swap is orthogonal to layers — it remaps the *physical matrix position* before keycode lookup, so it works across all active layers.

### Gotchas

- **`keypos_t` is `{col, row}`** while the array is indexed `[row][col]` — the reversal is the #1 mistake; mirror tables built the wrong way silently mis-remap keys.
- The table must cover your full `MATRIX_ROWS`×`MATRIX_COLS` or the mirror is incomplete; unsymmetric layouts (column-stagger, split) need a hand-tuned table per board.
- Swap-Hands is **`rules.mk`-only** (no `info.json` feature block) — don't look for a `swap_hands`/`features.swap_hands` key.
- `SH_T`/`SH_TT` participate in the tap-hold pipeline, so quick-roll behavior depends on your global tap-hold settings (`04`).

---

## Cross-cutting interactions (quick map)

- **`process_record` order** (`01-architecture.md`): `pre_process_record_quantum` (Combos) → Tap Dance preprocess → `process_record_quantum` (Key Lock → Dynamic Macro → Repeat Key → … → `process_record_user` → Autocorrect/Caps Word/Key Overrides/Leader/Grave Esc/Space Cadet/Auto Shift/Tri Layer) → `post_process_record_*`.
- **Key generation primitives** (`register_code`/`tap_code`/`SEND_STRING`/`send_string_P`) are shared by macros, dynamic macros, autocorrect, combos, leader, and key overrides — see §1/§2.
- **Layer interactions** (`04-keymaps-and-keycodes.md`): Key Overrides use a layer *bitmask*; Combos can pin a reference layer (`COMBO_ONLY_FROM_LAYER`/`COMBO_REF_LAYER`); Layer Lock/Tri Layer mutate layer state; Tap Dance can `layer_on`/`layer_off`.
- **macOS pitfalls:** `QK_GESC` (Cmd+`` ` ``), `tap_code(KC_CAPS)` (needs `TAP_HOLD_CAPS_DELAY`), and suppressed-mod Key Overrides all have macOS quirks — see respective Gotchas.
- **Output devices:** if you also drive an OLED/encoder, those hooks live in `08-displays.md` and run on different cadences than these input features.
