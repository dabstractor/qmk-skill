# 18 — Community Modules

> Sources synthesized: `features/community_modules.md` (+ the "Compatible APIs" list), plus direct reading of real-world modules from [`qmk/awesome-qmk`](https://github.com/qmk/awesome-qmk) (see §7).

**Community Modules are the modern, recommended way to ship a redistributable QMK plugin** (released 2025). They are newer than most model training data — **prefer this reference over memory**, and when a concrete question exceeds it, read a real module's source (§7) or the user's local `quantum/` tree.

A module is a self-contained directory (`qmk_module.json` + `rules.mk` + `<module>.c` + optional `config.h`) that hooks into the same lifecycle/key-processing APIs as built-in features, declares its own keycodes and feature dependencies, and is discovered via `keymap.json`. They have first-class support for **External Userspace** — strongly cross-reference `16-userspace-development.md`.

> **Relationship to userspace:** Community Modules are the **packaged, redistributable** counterpart to hand-rolled userspace code (`16`'s `custom_quantum_functions`). Where userspace lets *you* add `_kb`/`_user` hooks for *your* keyboards, modules let *authors* ship those hooks for *anyone's* build, including declaring new keycodes and feature deps.
>
> **Decision rule:** *per-keymap* throwaway logic → `process_record_user` (`04`). *Share across your own keyboards* → a userspace (`16`). *Distribute to other people* → a **community module** (this file).

Canonical reference: <https://docs.qmk.fm/features/community_modules> — especially the **"Compatible APIs"** list (reproduced with min-versions in §5 below).

---

## 1. Adding a module to a build

Modules live in either:
- `<QMK_USERSPACE>/modules/`  (preferred — use External Userspace), or
- `<QMK_FIRMWARE>/modules/`.

In your keymap directory, create/edit `keymap.json` and list modules by their path relative to the `modules/` dir:

```json
{
    "modules": [
        "qmk/hello_world"
    ]
}
```

> ⚠️ **Community Modules are NOT supported by QMK Configurator** (`14-configurator-api-via.md`). You must build your own firmware.

QMK ships a built-in example module `qmk/hello_world` that prints to the HID console after 10 s and adds keycode `COMMUNITY_MODULE_HELLO` (alias `CM_HELO`) which types "Hello there."

## 2. Importing a module repo into External Userspace

```sh
cd /path/to/your/external/userspace
mkdir -p modules
git submodule add https://github.com/{user}/{repo}.git modules/{user}
git submodule update --init --recursive
```

```json
{
    "modules": [
        "qmk/hello_world",
        "{user}/{module_name}"
    ]
}
```

The `keymap.json` entry is the **relative path under `modules/`** — as long as the module exists somewhere under `modules/`, the path can point to it.

## 3. Writing a module

A module is denoted by `qmk_module.json`:

```json
{
    "module_name": "Hello World",
    "maintainer": "QMK Maintainers",
    "license": "GPL-2.0-or-later",
    "features": {
        "deferred_exec": true
    },
    "keycodes": [
        { "key": "COMMUNITY_MODULE_HELLO", "aliases": ["CM_HELO"] }
    ]
}
```

Required fields: `module_name`, `maintainer`. `license` (use an [SPDX identifier](https://spdx.org/licenses/)) and `url` are encouraged. `features` mirrors the `info.json` features block and lets the module pull in build dependencies (e.g. `deferred_exec`, `pointing_device`, `mouse`). `keycodes` declares new keycodes + aliases the module contributes to keymaps — see §7.1 for how real modules shape these.

### 3.1 Module files

| File | Auto-added? | Purpose |
|---|---|---|
| `qmk_module.json` | (manifest) | Required manifest: name, maintainer, license, features, keycodes. |
| `config.h` | yes | Treated as if present in the keyboard/keymap. |
| `rules.mk` / `post_rules.mk` | yes | Standard Makefile customization (also `SRC += extra.c` for additional files). |
| `<module>.c` | yes, **only if filename matches the directory name** | Main module source (e.g. `hello_world.c` in `qmk/hello_world/`). Other `.c` files must be added via `SRC +=` in `rules.mk`. |
| `introspection.c` / `introspection.h` | yes (advanced) | Hook into keymap introspection: header is prepended before the user keymap; source appended after. Advanced — see §7.5. |
| `led_matrix_module.inc` | yes | Custom LED matrix effects (like `led_matrix_kb.inc`); effect names prefixed `LED_MATRIX_COMMUNITY_MODULE_`. See `07-led-rgb-backlight.md`. |
| `rgb_matrix_module.inc` | yes | Custom RGB matrix effects; names prefixed `RGB_MATRIX_COMMUNITY_MODULE_`. See `07-led-rgb-backlight.md`. |
| Custom split sync IDs | (define) | `SPLIT_TRANSACTION_IDS_MODULE_<MODULE>` — see `10-connectivity.md` custom data sync. |

In `<module>.c`, assert a minimum API version so the module fails loudly on incompatible QMK:

```c
ASSERT_COMMUNITY_MODULES_MIN_API_VERSION(1, 0, 0);   // note: commas, not dots
```

## 4. Minimal example

`modules/myorg/greet/qmk_module.json`:
```json
{
    "module_name": "Greet",
    "maintainer": "me",
    "license": "GPL-2.0-or-later",
    "keycodes": [
        { "key": "COMMUNITY_MODULE_GREET", "aliases": ["CM_GRRT"] }
    ]
}
```

`modules/myorg/greet/greet.c`:
```c
#include "quantum.h"

ASSERT_COMMUNITY_MODULES_MIN_API_VERSION(1, 1, 0);

bool process_record_greet(uint16_t keycode, keyrecord_t *record) {
    if (!record->event.pressed) return true;
    switch (keycode) {
        case COMMUNITY_MODULE_GREET:
            SEND_STRING("Hello from a module!");
            return false;  // handled, stop further processing
    }
    return true;
}
```

`keymap.json`:
```json
{ "modules": [ "myorg/greet" ] }
```
Then bind `CM_GRRT` in your keymap.

## 5. Compatible APIs (the hook surface)

A module may provide a specialization for any of these base APIs by suffixing with `_<module>` (e.g. `process_record_hello_world`). Each also has equivalent `_<module>_kb()` and `_<module>_user()` hooks, matching QMK's `_quantum`/`_kb`/`_user` convention (`16-userspace-development.md`). Unspecified APIs are simply ignored.

| Base API | Module function format | Example | Min API |
|---|---|---|---|
| `keyboard_pre_init` | `keyboard_pre_init_<module>` | `keyboard_pre_init_hello_world` | `0.1.0` |
| `keyboard_post_init` | `keyboard_post_init_<module>` | `keyboard_post_init_hello_world` | `0.1.0` |
| `pre_process_record` | `pre_process_record_<module>` | `pre_process_record_hello_world` | `0.1.0` |
| `process_record` | `process_record_<module>` | `process_record_hello_world` | `0.1.0` |
| `post_process_record` | `post_process_record_<module>` | `post_process_record_hello_world` | `0.1.0` |
| `housekeeping_task` | `housekeeping_task_<module>` | `housekeeping_task_hello_world` | `1.0.0` |
| `suspend_power_down` | `suspend_power_down_<module>` | `suspend_power_down_hello_world` | `1.0.0` |
| `suspend_wakeup_init` | `suspend_wakeup_init_<module>` | `suspend_wakeup_init_hello_world` | `1.0.0` |
| `shutdown` | `shutdown_<module>` | `shutdown_hello_world` | `1.0.0` |
| `process_detected_host_os` | `process_detected_host_os_<module>` | `process_detected_host_os_hello_world` | `1.0.0` |
| `default_layer_state_set` | `default_layer_state_set_<module>` | `default_layer_state_set_hello_world` | `1.1.0` |
| `layer_state_set` | `layer_state_set_<module>` | `layer_state_set_hello_world` | `1.1.0` |
| `led_matrix_indicators` | `led_matrix_indicators_<module>` | `led_matrix_indicators_hello_world` | `1.1.0` |
| `led_matrix_indicators_advanced` | `led_matrix_indicators_advanced_<module>` | `led_matrix_indicators_advanced_hello_world` | `1.1.0` |
| `rgb_matrix_indicators` | `rgb_matrix_indicators_<module>` | `rgb_matrix_indicators_hello_world` | `1.1.0` |
| `rgb_matrix_indicators_advanced` | `rgb_matrix_indicators_advanced_<module>` | `rgb_matrix_indicators_advanced_hello_world` | `1.1.0` |
| `pointing_device_init` | `pointing_device_init_<module>` | `pointing_device_init_hello_world` | `1.1.0` |
| `pointing_device_task` | `pointing_device_task_<module>` | `pointing_device_task_hello_world` | `1.1.0` |

> Where these hooks sit in the processing order (e.g. `pre_process_record` runs earliest in the `process_record` chain; `housekeeping_task` runs every main-loop iteration after the matrix scan) — see `01-architecture.md`.

## 6. Gotchas

- **Not supported by QMK Configurator** — module users must build firmware themselves (CLI/make/Docker; `02-getting-started-build.md`).
- The main C file is auto-compiled **only if its name matches the directory name** (`hello_world.c` for `qmk/hello_world/`). Any other `.c` file must be added with `SRC += file.c` in `rules.mk`.
- Always call `ASSERT_COMMUNITY_MODULES_MIN_API_VERSION(maj, min, patch)` (commas, not dots) so the module refuses to build against an incompatible QMK.
- The `_<module>` hook naming is **string-based** — the function name must match the module's directory name exactly, or it won't be discovered.
- Each module API has `_kb` and `_user` sibling hooks too; module code plays the same `_kb`-calls-`_user` game as built-in features (`16-userspace-development.md`).
- `introspection.c/.h` is powerful but **advanced and easy to get wrong** — follow existing module patterns (§7.5); ask on Discord/issues if unsure.
- `features` in `qmk_module.json` is the same schema as keyboard `info.json` features, so a module can pull in `deferred_exec`, `pointing_device`, RGB matrix, split sync, etc. — but each adds firmware size.
- Effect-name prefixes for custom LED/RGB matrix effects are fixed (`LED_MATRIX_COMMUNITY_MODULE_*` / `RGB_MATRIX_COMMUNITY_MODULE_*`); custom split sync IDs must follow `SPLIT_TRANSACTION_IDS_MODULE_<MODULE>` (`10-connectivity.md`).
- Host via git submodules under `modules/` for clean versioning; the `keymap.json` path is relative to the `modules/` directory.

---

## 7. Examples in the wild

The curated list at **<https://github.com/qmk/awesome-qmk>** links the standout module and userspace repos. Because there are relatively few real modules (the mechanism shipped in 2025), reading a few of them is the fastest way to internalize the patterns. The annotated excerpts below are drawn directly from those repos; read the full sources for anything non-trivial.

Notable module collections:
- **getreuer/qmk-modules** — `achordion`, `select_word`, `sentence_case`, `socd_cleaner`, `custom_shift_keys`, `orbital_mouse`, `speculative_hold`, `tap_flow`, … (text-input & pointing behavior; Apache-2.0).
- **drashna/qmk_modules** — `rtc`, `unicode_typing`, `console_keylogging`, `drag_scroll`, `mouse_jiggler`, `i2c_scanner`, `display_menu`, `signalrgb`, … (utilities & drivers; GPL-2.0-or-later).
- **yeroca/qmk_concurrent_macros** — looping/concurrent macros for gaming.

### 7.1 Declaring keycodes (manifest shapes)

Two common shapes. **With aliases** (getreuer `select_word`):
```json
"keycodes": [
    { "key": "SELECT_WORD",       "aliases": ["SELWORD"] },
    { "key": "SELECT_WORD_BACK",  "aliases": ["SELWBAK"] },
    { "key": "SELECT_LINE",       "aliases": ["SELLINE"] }
]
```
**Many keycodes, no aliases** — fine too (getreuer `orbital_mouse`, 18 keys, also shows `"mousekey": false` to *disable* a feature the `mouse` feature would otherwise pull in):
```json
"features": { "mouse": true, "mousekey": false },
"keycodes": [
    {"key": "OM_CS_U"}, {"key": "OM_CS_D"}, {"key": "OM_FAST"}, {"key": "OM_SLOW"},
    {"key": "OM_SEL1"}, {"key": "OM_SEL2"}   /* …18 total */
]
```

### 7.2 Feature dependency + deferred exec (timing without a busy-loop)

drashna `mouse_jiggler` declares the dependency in the manifest, then uses the deferred-exec subsystem to schedule movement without blocking the main loop:
```json
"features": { "deferred_exec": true, "pointing_device": true }
```
```c
/* A deferred callback: return 0 = don't reschedule, return N = run again in N ms. */
uint32_t jiggler_introtimer(uint32_t trigger_time, void *cb_arg) {
    jiggler_intro_end();
    return 0;
}
/* Scheduling primitives available once "deferred_exec": true is declared. */
deferred_token t = defer_exec(delay_ms, my_callback, NULL);  /* fire once after delay_ms */
extend_deferred_exec(t, new_delay_ms);                      /* push out an in-flight timer */
cancel_deferred_exec(t);                                    /* stop it */
```
`housekeeping_task_<module>` is the right hook for "check state every loop and maybe schedule work."

### 7.3 Pointing-device hook (return the transformed report, call `_kb`)

drashna `drag_scroll` shows the canonical pointing-device pattern — transform the `report_mouse_t`, then hand off to `_kb` so keymaps can still override:
```c
report_mouse_t pointing_device_task_drag_scroll(report_mouse_t mouse_report) {
    if (set_scrolling) {
        mouse_report.h = (mouse_report.x + scroll_remainder_h) / scroll_divisor_h;
        mouse_report.v = (mouse_report.y + scroll_remainder_v) / scroll_divisor_v;
        mouse_report.x = 0;
        mouse_report.y = 0;
    }
    return pointing_device_task_drag_scroll_kb(mouse_report);   /* ← call _kb! */
}

bool process_record_drag_scroll(uint16_t keycode, keyrecord_t *record) {
    if (!process_record_drag_scroll_kb(keycode, record)) return true;  /* ← _kb gate */
    switch (keycode) {
        case DRAG_SCROLL_TOGGLE:    /* press toggles */
            if (record->event.pressed) set_drag_scroll_scrolling(!get_drag_scroll_scrolling());
            break;
        case DRAG_SCROLL_MOMENTARY: /* hold = on */
            set_drag_scroll_scrolling(record->event.pressed);
            break;
    }
    return true;
}
```

### 7.4 process_record + housekeeping + OS detection

getreuer `select_word` combines a `process_record_<module>` switch with a `housekeeping_task_<module>` timeout, and adapts Mac vs Win/Linux hotkeys via OS Detection when available:
```c
void housekeeping_task_select_word(void) { /* idle-timeout the selection state */ }

bool process_record_select_word(uint16_t keycode, keyrecord_t *record) {
    const uint8_t saved_mods = get_mods();
    /* … */
    switch (keycode) {
        case SELECT_WORD: /* emulate Ctrl+Shift+Left (Win/Linux) or Cmd+Shift+Left (Mac) */ break;
        /* … */
    }
    return true;
}
```
```c
#if defined(SELECT_WORD_OS_DYNAMIC) || defined(OS_DETECTION_ENABLE)
__attribute__((weak)) bool select_word_host_is_mac(void) {
#  ifdef OS_DETECTION_ENABLE
    switch (detected_host_os()) {        /* OS Detection integration */
        case OS_MACOS: case OS_IOS: return true;
        default: return false;
    }
#  endif
}
#endif
```

### 7.5 introspection.c — the advanced, rare pattern

Most modules never need `introspection.c/.h`. When a module exposes its own arrays/tables to the keymap-introspection system (so keymaps can read or override them), follow the **weak `_raw` + overridable wrapper** idiom. getreuer `custom_shift_keys`:
```c
#ifdef COMMUNITY_MODULE_CUSTOM_SHIFT_KEYS_ENABLE

uint16_t custom_shift_keys_count_raw(void) {
    return ARRAY_SIZE(custom_shift_keys);
}
__attribute__((weak)) uint16_t custom_shift_keys_count(void) {
    return custom_shift_keys_count_raw();          /* keymap may override this */
}

const custom_shift_key_t *custom_shift_keys_get_raw(uint16_t index) {
    if (index >= custom_shift_keys_count_raw()) return NULL;
    return &custom_shift_keys[index];
}
__attribute__((weak)) const custom_shift_key_t *custom_shift_keys_get(uint16_t index) {
    return custom_shift_keys_get_raw(index);       /* keymap may override this */
}

#endif
```
The `_raw` function is the ground truth; the non-raw function is `__attribute__((weak))` so a keymap can replace it. This is the pattern to copy whenever your module needs introspection.

---

## Cross-cutting cheat sheet

| What | Where |
|---|---|
| Hook surface / lifecycle order | `01-architecture.md` §9 |
| `_kb`-calls-`_user` convention | `16-userspace-development.md` |
| Split data sync from a module | `10-connectivity.md` (custom `SPLIT_TRANSACTION_IDS_MODULE_*`) |
| Built-in feature enabling (the `features` schema) | `03-config-and-info-json.md` |
| Not buildable via Configurator/API | `14-configurator-api-via.md` |