# 16 — Userspace, Coding Conventions, CLI/API Development, Contributing & Glossary

This reference synthesizes everything about *extending QMK beyond a single keymap*: the **userspace** feature (sharing C across keyboards), the **C and Python coding conventions** QMK enforces, how to **develop `qmk` CLI subcommands** and self-host the **QMK Compile API**, the **contribution workflow and PR checklist**, **documentation** writing rules (vuepress/Markdown), the **glossary** of QMK terms, and the **learning syllabus**.

> Sources synthesized: `feature_userspace.md`, `coding_conventions_c.md`, `coding_conventions_python.md`, `cli_development.md`, `api_development_overview.md`, `api_development_environment.md`, `contributing.md`, `pr_checklist.md`, `documentation_best_practices.md`, `documentation_templates.md`, `support.md`, `reference_glossary.md`, `syllabus.md`.
>
> Companion references: **`01-architecture.md`** (the `process_record` dispatch chain §7 and the full overrideable-hook catalog §9 — do **not** duplicate here), **`02-getting-started-build.md`** (External Userspace *repo* setup + `qmk userspace-*` commands §7), **`18-community-modules.md`** (community modules — an alternative code-sharing mechanism), **`17-faq-gotchas-breaking-changes.md`** (deprecation policy & breaking-changes history).

---

## Table of Contents

1. [Userspace feature](#1-userspace-feature)
2. [C coding conventions](#2-c-coding-conventions)
3. [Python coding conventions](#3-python-coding-conventions)
4. [QMK CLI development](#4-qmk-cli-development)
5. [QMK Compile API development](#5-qmk-compile-api-development)
6. [Contributing workflow](#6-contributing-workflow)
7. [PR checklist](#7-pr-checklist)
8. [Documentation best practices & templates](#8-documentation-best-practices--templates)
9. [Support & community](#9-support--community)
10. [Glossary](#10-glossary)
11. [Learning syllabus](#11-learning-syllabus)

---

## 1. Userspace feature

**Summary.** The userspace feature lets you put shared C code, keycodes, layer enums, `config.h` options, and `rules.mk` logic in a single `users/<name>/` directory that is **automatically included** when you build any keymap *named* `<name>`. It is the canonical way to keep one set of custom behavior (macros, custom keycodes, per-board features) consistent across many different keyboards.

> ::: warning (from upstream)
> **Userspace submissions to the upstream `qmk/qmk_firmware` repository are no longer accepted.** The feature itself is fully functional and remains supported for local use. Likewise, personal **keymap** and **user-keymap** contributions are no longer accepted into `qmk_firmware` — see §7. This applies only to the in-tree `users/` directory; the modern **External Userspace** repo (see `02-getting-started-build.md` §7) is the supported sharing mechanism.
> :::

### 1.1 When is a userspace directory pulled in?

All of the userspace machinery triggers **only when the keymap being built is named `<name>`**:

```
make planck:<name>      # e.g.  make planck:jack   →  includes /users/jack/
```

The directory `/users/<name>/` is added to the build path automatically, and `rules.mk` + `config.h` inside it are included automatically.

The name can be **overridden** (see §1.4) when the keymap name must differ from the userspace folder name.

### 1.2 Directory layout

```
/users/<name>/
├── readme.md            (optional, recommended — authorship + GPL-compatible license)
├── rules.mk             (included automatically)
├── config.h             (included automatically)
├── <name>.h             (optional — layer/keycode enums, user/keyboard-specific settings)
├── <name>.c             (optional — recommended default source file)
├── cool_rgb_stuff.c     (optional — extra source modules)
└── cool_rgb_stuff.h     (optional)
```

| File | Auto-included? | Purpose |
|------|:-:|---------|
| `rules.mk` | ✅ | Adds `SRC +=` files; conditional feature gating |
| `config.h` | ✅ | `#define` build-time options (e.g. `TAPPING_TERM`) |
| `<name>.h` | ❌ (you `#include` it) | Enums for layers/custom keycodes; keymap-specific settings |
| `<name>.c` | via `rules.mk` `SRC += <name>.c` | Shared functions / hooks (`process_record_user`, etc.) |

### 1.3 `rules.mk` — adding sources & feature gating

`/users/<name>/rules.mk` is included **after** the keymap's own `rules.mk`, so it can gate on QMK feature flags that may or may not be present on a given board:

```make
# Recommended: one default source file
SRC += <name>.c

# Conditionally pull in extra sources only when a feature is enabled
ifeq ($(strip $(RGBLIGHT_ENABLE)), yes)
  SRC += cool_rgb_stuff.c
endif
```

Alternatively define your own gate variable in the keymap's `rules.mk` and test it in userspace:

```make
# keymap rules.mk:
RGB_ENABLE = yes
```
```make
# userspace rules.mk:
ifdef RGB_ENABLE
  SRC += cool_rgb_stuff.c
endif
```

### 1.4 Overriding the default userspace (`USER_NAME`)

By default the userspace folder = keymap name. When that's undesirable (e.g. the `layout` feature forces distinct keymap names like `mylayout-ansi` and `mylayout-iso`), set in the keymap's `rules.mk`:

```make
USER_NAME := mylayout
```

Also useful when different keyboards have different physical hardware (RGB vs Audio, different LED counts, different pins) but share logic.

### 1.5 `config.h` vs `<name>.h` — don't mix them up

> **Use `config.h` for [configuration options] (`#define TAPPING_TERM 100`, etc.), and `<name>.h` for user/keymap-specific settings (layer enums, custom-keycode enums).** `<name>.h` is NOT included early enough to feed build-time `#define`s, and `#include`-ing `<name>.h` *inside* any `config.h` causes compile errors.

See `03-config-and-info-json.md` for the data-driven equivalents of these options.

### 1.6 The "customized functions" / weak-keymap pattern (THE central idiom)

QMK exposes `_quantum` / `_kb` / `_user` variants of most hooks (full catalog in **`01-architecture.md` §9**). If you implement `*_user` in your **userspace**, the keymap can no longer provide its own. The solution is a **weak `_keymap` stub** that the keymap may override.

```c
// <name>.c

/* Weak default — keymap.c may provide its own. */
__attribute__ ((weak))
layer_state_t layer_state_set_keymap(layer_state_t state) {
    return state;
}

/* The real _user hook lives in userspace, then delegates to _keymap. */
layer_state_t layer_state_set_user(layer_state_t state) {
    state = update_tri_layer_state(state, 2, 3, 5);   // shared tri-layer on ALL boards
    return layer_state_set_keymap(state);             // keymap can add more
}
```

- `__attribute__ ((weak))` = "placeholder the linker may replace." If `keymap.c` defines `layer_state_set_keymap`, that wins; otherwise the no-op stub is used. No link conflict.
- The suffix **must not** be `_quantum` / `_kb` / `_user` (those are taken). Common choices: `_keymap`, `_mine`, `_fn`. `_keymap` is the community convention (matches `users/drashna/template.c`).
- This works for **any** `_user` hook: `process_record_user`, `matrix_scan_user`, `keyboard_pre_init_user`, `suspend_*_user`, etc. (see `01-architecture.md` §9 for the full list).

#### Consolidated process_record_user + shared keycodes

The most common userspace pattern: own `process_record_user` in userspace, delegate per-board handling to a weak `process_record_keymap`, and declare a shared custom-keycode enum in `<name>.h`.

`<name>.h`:
```c
#pragma once

#include "quantum.h"
#include "action.h"
#include "version.h"

enum custom_keycodes {
    KC_MAKE = SAFE_RANGE,   // global custom keycodes live here
    NEW_SAFE_RANGE          // keymap-specific keycodes start from THIS, not SAFE_RANGE
};
```

`<name>.c`:
```c
#include "<name>.h"

__attribute__ ((weak))
bool process_record_keymap(uint16_t keycode, keyrecord_t *record) {
    return true;
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case KC_MAKE:
            if (!record->event.pressed) {
                uint8_t temp_mod = get_mods();
                uint8_t temp_osm = get_oneshot_mods();
                clear_mods(); clear_oneshot_mods();
                SEND_STRING("make " QMK_KEYBOARD ":" QMK_KEYMAP);
#ifndef FLASH_BOOTLOADER
                if ((temp_mod | temp_osm) & MOD_MASK_SHIFT)
#endif
                {
                    SEND_STRING(":flash");   // Shift held (or FLASH_BOOTLOADER) → add :flash
                }
                if ((temp_mod | temp_osm) & MOD_MASK_CTRL) {
                    SEND_STRING(" -j8 --output-sync");   // Ctrl → parallel build
                }
                tap_code(KC_ENT);
                set_mods(temp_mod);
            }
            break;
    }
    return process_record_keymap(keycode, record);   // ALWAYS delegate at the end
}
```

Then in each `keymap.c`:
- `#include "<name>.h"`
- replace any `process_record_user` with `process_record_keymap`
- replace `SAFE_RANGE` with `NEW_SAFE_RANGE` for board-local keycodes

> **Where this sits in the dispatch chain:** `process_record_user` is the KEYMAP hook near the *end* of the main `process_record_quantum` chain; returning `false` halts the rest of the chain (no later feature sees the key). Full ordering and halt semantics: **`01-architecture.md` §7 and §9.3**. Do not re-derive the chain here.

### 1.7 Custom features gated per-board (`OPT_DEFS += -D...`)

Hide optional code behind a preprocessor flag you enable per-keymap:

```make
# userspace rules.mk:
ifeq ($(strip $(MACROS_ENABLED)), yes)
    OPT_DEFS += -DMACROS_ENABLED     # note the -D  →  #define MACROS_ENABLED
endif
```
```make
# a keymap's rules.mk that wants macros:
MACROS_ENABLED = yes
```
```c
bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
#ifdef MACROS_ENABLED
        case MACRO1:
            if (!record->event.pressed) SEND_STRING("This is macro 1!");
            break;
        case MACRO2:
            if (!record->event.pressed) SEND_STRING("This is macro 2!");
            break;
#endif
    }
    return true;
}
```

`FLASH_BOOTLOADER = yes` works the same way (forces `:flash` on boards without a Shift key — e.g. macro pads).

### 1.8 Build all keyboards for one userspace

Verify every keymap that uses your userspace compiles in one shot:

```
make all:<name>          # e.g. make all:jack
```

### 1.9 `readme.md` template (authorship + license)

```
Copyright <year> <name> <email> @<github_username>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
```

### 1.10 Examples to crib from

- Minimal: `users/_example/` in the qmk_firmware repo.
- Full-featured: `users/drashna/` — see its `template.c` for the complete set of weak `_keymap` stubs.
- Community collection: the `awesome-qmk` GitHub list.

### 1.11 Gotchas — Userspace

- **In-tree `users/` submissions are closed.** Do not PR a `users/<name>/` to `qmk_firmware`; use the External Userspace repo (`02-getting-started-build.md` §7) for sharing.
- **Keymap name must equal the folder name** unless you set `USER_NAME`. A typo here silently means your userspace is never compiled in.
- **`config.h` vs `<name>.h` confusion** is the #1 build break: build-time `#define`s must be in `config.h`; enums go in `<name>.h`. Never `#include "<name>.h"` from a `config.h`.
- **`rules.mk` ordering:** userspace `rules.mk` runs *after* the keymap's, so it can read feature flags set by the keymap — but the reverse is not true.
- **Always `return process_record_keymap(...)` at the end** of the shared `process_record_user`; forgetting it silently eats every per-board keycode.
- **Replace `SAFE_RANGE` with `NEW_SAFE_RANGE`** in every keymap, or board-local keycodes collide with the shared ones.
- **`KC_MAKE`-style auto-flash (`:flash`) does not work on WSL** (AVRDUDE limitation).
- **Alternative sharing mechanisms:** the External Userspace repo (`02` §7) for the *build/CI* side, and **community modules** (`18-community-modules.md`) for an opt-in module system that doesn't require a matching keymap name.

---

## 2. C coding conventions

QMK firmware is mostly C (with some C++), targeting AVR (LUFA) and ARM (ChibiOS). **Primary rule: match the style of the code surrounding your change.** Fall back to these rules only when that code is inconsistent or unclear.

| Rule | QMK convention |
|------|----------------|
| Indentation | **4 spaces** (soft tabs), never hard tabs |
| Brace style | Modified **One True Brace Style** (1TBS / K&R): opening brace at end of opening line; closing brace lined up with the statement; `} else {` on one line |
| Optional braces | **Always include them** — `if (x) { return 1; }` ✅ ; `if (x) return 1;` ❌ |
| Comments | C-style `/* */`; write the *why*, not the obvious; when unsure, include |
| Line wrapping | Generally don't; if you do, **≤ 76 columns** |
| Header guards | **`#pragma once`** at top of headers (not `#ifndef`/`#define`/`#endif`) |
| Preprocessor ifs | Both `#ifdef X` and `#if defined(X)` accepted; prefer `#if defined(X)` if unsure; **do not** churn existing code between styles |
| Indented preprocessor | Keep `#` at column 0; if indenting, 4 spaces *between* `#` and `if`; follow surrounding file's style |

Reference snippet:

```c
/* Enums for foo */
enum foo_state {
    FOO_BAR,
    FOO_BAZ,
};

/* Returns a value */
int foo(void) {
    if (some_condition) {
        return FOO_BAR;
    } else {
        return -1;
    }
}
```

### 2.1 Auto-format with clang-format

QMK ships a `.clang-format` config in the repo root that enforces most of the above (whitespace/newlines only — **you still add optional braces yourself**).

- Install: full LLVM installer (Windows) or `sudo apt install clang-format` (Ubuntu).
- Run: `clang-format -style=file <file>` (auto-finds the config).
- VS Code: built-in C/C++ extension supports it, or the LLVM Clang-Format extension.
- **Clang-format destroys `LAYOUT(...)` macros.** Either skip those files or wrap sensitive regions in `// clang-format off` … `// clang-format on`.

### 2.2 Quantum internal API rules (from pr_checklist "best practices")

These are hard requirements for PRs touching core/keyboard C:

- **`#pragma once`** instead of `#ifndef` include guards.
- **No "old-school" / low-level GPIO, I2C, SPI calls** — use QMK abstractions (see `13-drivers-lowlevel.md`). Laziness is not justification.
- **Timing abstractions too:** `wait_ms()` (not `_delay_ms()`; drop `#include <util/delay.h>`); `timer_read()` / `timer_read32()` (see `platforms/timer.h`).
- New callbacks **must return `bool`** when adding `_kb`/`_user` variants (so users can override keyboard-level callbacks).
- Custom matrix should use `CUSTOM_MATRIX = lite` unless full custom is justified.
- Prefer LED-indicator *config options* to hand-rolled `led_update_*()`.

### 2.3 Gotchas — C conventions

- **clang-format on `LAYOUT` macros** silently breaks the keymap matrix — always wrap or skip.
- **Braces are mandatory even for one-liners**; reviewers will reject bare `if (x) foo();`.
- **Don't restyle unrelated code** in a feature PR — match surrounding style, raise style-only refactors separately.
- **GPL license header is mandatory** on every `*.c`/`*.h` (see §7.5). Pure assignment-only `rules.mk` files may omit it.

---

## 3. Python coding conventions

For QMK CLI / scripts (`lib/python/qmk/`). Follows **PEP 8 with local relaxations**.

| Rule | QMK convention |
|------|----------------|
| Target | **Python 3.9** |
| Indent | 4 spaces |
| Comments | Liberal, tell the *why*, skip the obvious |
| Docstrings | **Required for every function** (see §3.5 format) |
| Line wrap | Generally don't; if you do, ≤ 76 cols |
| Auto-format | **YAPF** (config in `setup.cfg` `[yapf]`) |
| Type annotations | **None** — keep code unannotated for now |
| Imports | Specific names preferred (`from qmk.keymap import compile_firmware`); one import per line; group system / 3rd-party / local; never `from foo import *` |
| Filenames | `module_name.py`, `.py` extension, **never dashes** |

### 3.1 Naming

`module_name`, `package_name`, `ClassName`, `method_name`, `ExceptionName`, `function_name`, `GLOBAL_CONSTANT_NAME`, `global_var_name`, `instance_var_name`, `function_parameter_name`, `local_var_name`. **Descriptive; no abbreviations.**

Avoid: single-char names (except loop counters / iterators, and `e` in `except`), dashes in module names, `__dunder__` names (reserved by Python).

### 3.2 Statements & comprehensions

- One statement per line — never `if foo: bar` on one line.
- Comprehensions/generators encouraged but kept simple; fall back to a `for` loop when complex.
- Lambdas OK but prefer comprehensions; avoid them as function args.
- Conditional expressions (`x = 1 if c else 2`) OK in assignment, **avoid** elsewhere (too easy to miss).

### 3.3 Defaults, properties, truthiness

- **Default args must be immutable.** Never `def f(x={})`; use `def f(x=None)` + `if not x: x = {}`.
- **Use `@property`** instead of getter/setter functions.
- **Implicit truthiness:** `if foo:` not `if foo == True:`; `if not bar:` not `if bar == False:`.

### 3.4 Tuples / lists / dicts / parens / format strings

- One-item tuples always get a trailing comma.
- YAPF: trailing comma ⇒ one item per line; no comma ⇒ single line. Break to multi-line early for readability.
- Avoid excess parens; never parenthesize a `return` unless returning a tuple or a math expression.
- **Prefer printf-style** format strings (`'Hello, %s!' % (name,)`) — matches the logging module and is C-coder-friendly. Never use `%` directly with `cli.log`/`cli.echo`; pass values as args.

### 3.5 Docstrings (required for every function)

- Markdown formatting; triple-double-quote with a newline: `"""\n"""`.
- First line: short (< 70 char) description; blank line before more detail.
- `Args:` / `Returns:` / `Raises:` (each preceded by a blank line) come last, in that order.

```python
def my_awesome_function(start=None, offset=0):
    """Return the number of seconds since 1970 Jan 1 00:00 UTC.

    This function always returns an integer number of seconds.


    Args:
        start
            The time to start at instead of 1970 Jan 1 00:00 UTC

        offset
            Return an answer that has this number of seconds subtracted first

    Returns:
        An integer describing a number of seconds.

    Raises:
        ValueError
            When `start` or `offset` are not positive numbers
    """
```

### 3.6 Exceptions, threading, "power features"

- Exceptions are for **exceptional** situations, **not flow control** (deliberate break from Python's "ask forgiveness"). Keep `try` blocks short.
- Catch-all `except` must `cli.log` the exception + stacktrace.
- **Avoid threading/multiprocessing** unless you make a strong case.
- **No metaclasses, bytecode hacks, dynamic inheritance, reflection, import hacks, etc.** Readability > cleverness > performance. (Using stdlib modules that internally do this is fine.)

### 3.7 Function length, FIXMEs, testing

- Prefer small focused functions; ~40 lines is the "think about splitting" threshold.
- FIXMEs are OK, formatted `FIXME(username): ...`.
- **Tests live in `lib/python/qmk/tests/`** — integration tests in `test_cli_commands.py` (run real CLI via `subprocess`, check output + returncode); unit tests in `test_<module_under_dots>.py`. Run with `qmk pytest`. No mocking yet.

### 3.8 Gotchas — Python conventions

- **No type annotations** anywhere in QMK Python (deliberate).
- **Mutable default args** are a classic bug — always `None`-guard.
- **printf-style only** — f-strings/`.format` are not the house style for logging/cli output.
- `from foo import *` is forbidden.
- Don't be clever: reviewers value readability over compactness.

---

## 4. QMK CLI development

**Summary.** The `qmk` CLI uses the **git subcommand pattern**: the main script sets up the environment and dispatches; each subcommand is a self-contained module under `lib/python/qmk/cli/` exposing a function decorated with `@cli.subcommand()` that returns a shell returncode (or `None`).

### 4.1 Developer mode

```
qmk config user.developer=True
```

Reveals *all* subcommands (some are hidden until enabled). The bootstrapper install (`curl -fsSL https://install.qmk.fm | sh`) already pulls in dev requirements.

### 4.2 The MILC framework

[MILC](https://github.com/clueboard/milc) handles argument parsing, configuration (`qmk.ini`), logging, color, and more. You import its singleton:

```python
"""QMK Python Hello World

This is an example QMK CLI script.
"""
from milc import cli


@cli.argument('-n', '--name', default='World', help='Name to greet.')
@cli.subcommand('QMK Hello World.')
def hello(cli):
    """Log a friendly greeting.
    """
    cli.log.info('Hello, %s!', cli.config.hello.name)
```

- `@cli.argument('-n', '--name', ...)` registers `--name` **and** auto-creates a config var `hello.name` (and `user.name`).
- `@cli.subcommand('...')` marks the function as a subcommand. **The function name becomes the subcommand name.**
- Inside the function: `cli.log` is a stdlib `Logger`; `cli.config.hello.name` resolves in priority order: CLI arg → `qmk.ini` → decorator default.

### 4.3 Subcommand file location & registration

Local subcommands live in `qmk_firmware/lib/python/qmk/cli/`. A file `lib/python/qmk/cli/<name>.py` with a `@cli.subcommand()`-decorated function named `<name>` is auto-discovered (sub-folders create namespaced subcommands). **Developer mode** (`user.developer=True`) must be on to see the full set.

### 4.4 Output: `cli.log` vs `cli.echo`

Prefer **`cli.log.info()`** for general output. Both support printf-style tokens and color tokens; **never use the `%` operator directly** — pass values as args.

`cli.log` levels and their emoji:

| Function | Emoji |
|----------|-------|
| `cli.log.critical` | `{bg_red}{fg_white}¬_¬{style_reset_all}` |
| `cli.log.error` | `{fg_red}☒{style_reset_all}` |
| `cli.log.warning` | `{fg_yellow}⚠{style_reset_all}` |
| `cli.log.info` | `{fg_blue}Ψ{style_reset_all}` |
| `cli.log.debug` | `{fg_cyan}☐{style_reset_all}` |
| `cli.log.notset` | `{style_reset_all}¯\_(o_o)_/¯` |

Default level is `INFO`; `qmk -v <subcommand>` sets `DEBUG`. Use `cli.echo()` only for fixed data that should never be logged.

### 4.5 Colorizing text

Embed color tokens in strings. **Use color to highlight, not to convey info** (users can disable color and the command must still work). Generally avoid background colors.

| Color | Foreground | Background | Extended FG | Extended BG |
|-------|-----------|-----------|-------------|-------------|
| Black | `{fg_black}` | `{bg_black}` | `{fg_lightblack_ex}` | `{bg_lightblack_ex}` |
| Blue | `{fg_blue}` | `{bg_blue}` | `{fg_lightblue_ex}` | `{bg_lightblue_ex}` |
| Cyan | `{fg_cyan}` | `{bg_cyan}` | `{fg_lightcyan_ex}` | `{bg_lightcyan_ex}` |
| Green | `{fg_green}` | `{bg_green}` | `{fg_lightgreen_ex}` | `{bg_lightgreen_ex}` |
| Magenta | `{fg_magenta}` | `{bg_magenta}` | `{fg_lightmagenta_ex}` | `{bg_lightmagenta_ex}` |
| Red | `{fg_red}` | `{bg_red}` | `{fg_lightred_ex}` | `{bg_lightred_ex}` |
| White | `{fg_white}` | `{bg_white}` | `{fg_lightwhite_ex}` | `{bg_lightwhite_ex}` |
| Yellow | `{fg_yellow}` | `{bg_yellow}` | `{fg_lightyellow_ex}` | `{bg_lightyellow_ex}` |

Control sequences: `{style_bright}`, `{style_dim}`, `{style_normal}`, `{style_reset_all}` (auto-appended to every string), `{bg_reset}`, `{fg_reset}`.

### 4.6 Arguments & configuration

Arguments auto-propagate into `cli.config` keyed by subcommand name + long arg name (e.g. `--keyboard` in `qmk compile` ⇒ `cli.config.compile.keyboard`). Access by attribute (`cli.config.compile.keyboard`) or dict (`cli.config['compile']['keyboard']`). Underlying storage is ConfigParser.

- **Read:** iterate `for section in cli.config: for key in cli.config[section]: ...`.
- **Set:** `cli.config.<section>.<key> = v` (or dict form).
- **Delete:** `del(cli.config.<section>.<key>)` (or dict form).
- **Persist:** `cli.save_config()` — but prefer letting the user run `qmk config` deliberately; most commands never write config.
- **Exclude an arg from config:** pass `arg_only=True` to `@cli.argument(...)`. Such args are reachable **only** via `cli.args.<name>` (not `cli.config`).

```python
@cli.argument('-o', '--output', arg_only=True, help='File to write to')
@cli.argument('filename', arg_only=True, help='Configurator JSON file')
@cli.subcommand('Create a keymap.c from a QMK Configurator export.')
def json_keymap(cli):
    cli.log.info('Reading from %s and writing to %s', cli.args.filename, cli.args.output)
```

### 4.7 Test / lint / format

| Command | Does |
|---------|------|
| `qmk pytest` | Runs **nose2** tests + **flake8** lint (`lib/python/qmk/tests/`) |
| `qmk format-python` | Runs **YAPF** (`setup.cfg` `[yapf]`) |

Favor integration tests if you can't write both. Mark gaps with `# TODO(unassigned/<user>): Write <unit|integration> tests`. Code must pass flake8 before opening a PR (CI enforces it).

### 4.8 Gotchas — CLI development

- **The function name IS the subcommand name** — renaming the function renames the command.
- **`arg_only=True` args are invisible to `cli.config`** — read them via `cli.args`; a common gotcha when porting an older subcommand.
- **Don't use `%` yourself** — pass values as trailing args to `cli.log.*` / `cli.echo`.
- **Don't write the config file** from a normal command; let `qmk config` do it.
- **flake8 must pass** or CI fails the PR.

---

## 5. QMK Compile API development

**Summary.** The QMK Compile API is a self-hostable service that compiles arbitrary keymaps in the cloud/browser. It has three parts: a **Flask API service** (clients talk only to this), **Redis Queue (RQ)** (job broker), and **workers** (build the firmware), with **S3-compatible storage** for results.

> The full stack (API + Redis + workers + S3 + web frontend) is provided by the **`qmk_web_stack`** repo: https://github.com/qmk/qmk_web_stack — start there to self-host.

### 5.1 Architecture

```
API Client ──HTTP──▶ API Service (Flask)
                         │  enqueue job
                         ▼
                     Redis Queue (RQ) ◀── fetch jobs ── Worker(s)
                                                      │  checkout qmk_firmware,
                                                      │  build keymap.c,
                                                      │  build firmware,
                                                      │  zip source,
                                                      │  upload to S3,
                                                      │  report status to RQ
                         │  poll RQ + S3
                         ▼
                    API Service ──results──▶ API Client
```

### 5.2 Worker job lifecycle

When a worker pulls a job from RQ it:

1. Makes a **fresh `qmk_firmware` checkout**.
2. Builds a `keymap.c` from the supplied layers + keyboard metadata.
3. **Builds the firmware.**
4. **Zips a copy of the source.**
5. **Uploads firmware + source zip + a metadata file to S3.**
6. Reports job status back to **RQ**.

### 5.3 API Service endpoints (Flask)

| Route | Method | Purpose |
|-------|--------|---------|
| `/v1/compile` | `POST` | Main entrypoint. Client POSTs JSON describing the keyboard; API does basic validation then enqueues the compile job. |
| `/v1/compile/<job_id>` | `GET` | Most-called endpoint. Pulls job details from Redis if available, else cached details on S3. |
| `/v1/compile/<job_id>/download` | `GET` | Download the compiled firmware binary. |
| `/v1/compile/<job_id>/source` | `GET` | Download the firmware source zip. |

### 5.4 Gotchas — API

- This is the **self-hosted compiler API**, distinct from the public **QMK API** docs reference and from **VIA** — see `14-configurator-api-via.md` for the Configurator/VIA side.
- All real depth is in the `qmk_api` / `qmk_web_stack` source; the overview doc is intentionally high-level.
- Results persist on **S3** even after Redis evicts job details — that's why the status endpoint falls back to S3.

---

## 6. Contributing workflow

### 6.1 Project shape

QMK is mostly C (with some C++), targeting **AVR (LUFA)** and **ARM (ChibiOS)**. Arduino experience maps well; it's not required. Code of Conduct: treat everyone with respect (https://qmk.fm/coc/).

### 6.2 The standard contribution flow

1. Sign up for GitHub.
2. Find an issue or feature (or open one to discuss a new feature **before** building it).
3. **Fork** `qmk/qmk_firmware`.
4. Clone your fork locally.
5. For new features, **open an issue first** to align on approach.
6. **Create a non-`master` branch:** `git checkout -b branch-name`.
7. Make changes.
8. `git add <files>` → `git commit -m "..."`.
9. `git push origin branch-name`.
10. Open a PR against `qmk/qmk_firmware` (target `master`, or `develop` for core/keyboard moves — see §7).
11. Title: short description + issue/bug number (e.g. "Added more log outputting to resolve #4352").
12. In the description: explain changes, known issues, questions for the maintainer.
13. Address reviewer feedback; iterate.
14. Celebrate when merged.

### 6.3 General guidelines (all PRs)

- **Keep your fork up to date** with upstream `qmk_firmware` to avoid CI surprises.
- **Separate PRs into logical units** — one feature per PR; never two features in one PR.
- `git diff --check` to catch stray whitespace before committing.
- **It must compile:** keymaps (`make keyboard:keymap`), keyboards (`make keyboard:all`), core (`make all`).
- **user-keymap and userspace contributions are no longer accepted** (in-tree).
- **Commit messages:** ≤ 70-char subject line, blank second line, then detail. Should stand alone.

### 6.4 Documentation contributions

Easiest way to start. Docs live in `qmk_firmware/docs/` (or use the "Edit this page" link on https://docs.qmk.fm/). **Use the canonical enum names** in examples:

```c
enum my_layers {
    _FIRST_LAYER,
    _SECOND_LAYER
};

enum my_keycodes {
    FIRST_LAYER = SAFE_RANGE,
    SECOND_LAYER
};
```

Preview locally before a PR:

```
qmk docs -b     # serves http://localhost:8936/ and opens a browser
```

See §8 for the full Markdown/vuepress rules.

### 6.5 Keyboard PR guidelines

- Write `readme.md` from the template (§8.4).
- Include a clean **`default`** keymap as a starting slate.
- **Don't bundle core features with a new keyboard** — feature first, keyboard second (separate PRs).
- Name `.c`/`.h` after the immediate parent folder, e.g. `/keyboards/<kb1>/<kb2>/<kb2>.[ch]`.
- **No `Makefile`s** in keyboard folders (no longer used).
- Update copyright headers (replace `%YOUR_NAME%`).

### 6.6 Core / Quantum feature guidelines

**Discuss before implementing** significant changes (Discord or an issue) — QMK is mid-refactor and unplanned PRs may need heavy rework.

- **Disabled by default:** memory is scarce; features must be opt-**in**, not opt-out.
- **Compile locally** before submitting.
- **Cross-platform where possible:** support ARM **and** AVR, or auto-disable on unsupported platforms.
- **Document it** in `docs/` or nobody benefits.
- Keep commit count reasonable or expect a squash.
- Don't mix keyboards/keymaps into a core PR.
- Write **unit tests** for your feature.
- Follow surrounding file style, else the coding conventions (§2/§3).

### 6.7 Refactoring

Planned centrally — open an issue to propose a refactor rather than a surprise PR.

### 6.8 Gotchas — Contributing

- **Personal keymaps and in-tree userspaces are closed** to upstream PRs.
- **Core/keyboard PRs target `develop`, not `master`** (breaking-changes timeline) — see §7.
- **Discuss features before coding** or expect rework.
- **"Disabled by default"** is mandatory for new core features.
- Reviewers are volunteers; ~200 PRs open + merge per month means patience is required.

---

## 7. PR checklist

Non-exhaustive list of what QMK collaborators verify. Inconsistencies → open an issue or ask on Discord.

### 7.1 All PRs

- **Source branch must not be your own `master`** (target `master`/`develop` as appropriate — but work on a branch). Using your `master` triggers a "how to git" pointer post-merge.
  - Don't over-merge upstream into your branch; only rebase to resolve conflicts or pull relevant changes.
- **Smallest viable diff:** one logical change per PR. Smaller ⇒ faster review, faster merge, fewer conflicts. **Multiple keyboards in one PR is not acceptable.**
- **New directories/files must be lowercase** (relaxed only for upstream sources like LUFA/ChibiOS, or with justification; a designer's uppercase board name is *not* justification).
- **Valid license headers on all `*.c`/`*.h`** (GPL2/GPL3 recommended; must be GPL-compatible + redistributable; missing headers **block merge**). Assignment-only `rules.mk` may omit; `.mk` with logic may need one.
- **Best practices:** `#pragma once`; no low-level GPIO/I2C/SPI/timing (use QMK abstractions — `wait_ms()` not `_delay_ms()`); prototype new abstractions in a board first, then refactor into core as a separate PR.
- **Resolve all merge conflicts** before opening the PR.

### 7.2 Keymap PRs (vendor only)

::: warning
**Personal keymap submissions are no longer accepted.** This section applies to **manufacturer-supported** keymaps only (see qmk_firmware#22724).
:::

- Vendor keymaps named `default_${vendor}` (e.g. `default_clueboard`); may be richer than stock `default`.
- `#include QMK_KEYBOARD_H` (not specific board headers).
- Prefer layer **enums** to `#define`s.
- **Custom-keycode enum's first entry must be `QK_USER`.**
- Align on commas / first char of keycodes; **spaces over tabs**.
- **Keymaps must not enable VIA** — VIA keymaps go to the [VIA QMK Userspace](https://github.com/the-via/qmk_userspace_via) repo.

### 7.3 Keyboard PRs

- **Keyboard moves and data-driven refactors target `develop`** (reduces `master`→`develop` conflicts). Update `data/mappings/keyboard_aliases.hjson` on moves so existing Configurator `keymap.json` files still resolve.
- **No `kbfirmware` exports** unless converted — try `qmk import-kbfirmware`.
- **`info.json`** — use the [schema](https://github.com/qmk/qmk_firmware/blob/master/data/schemas/keyboard.jsonschema) maximally. **Mandatory:** valid URL, valid maintainer, valid USB VID/PID + device version, displays in Configurator (Ctrl+Shift+I preview, fast-input to verify ordering), `layout` defs include **matrix positions** (so `LAYOUT` macros generate at build), MCU + bootloader, diode direction (unless direct pins).
  - **Layout naming:** single electrical layout → `LAYOUT` (or a community layout name if it fits). Multiple → include `LAYOUT_all` (every matrix position) + per-layout names preferring community names (`LAYOUT_tkl_ansi`, `LAYOUT_ortho_4x4`).
  - **Must be in `info.json` if applicable:** direct pins, backlight, split, encoders, bootmagic, LED indicators, RGB Light, RGB Matrix.
  - **Run `qmk format-json -i`** before submitting.
- **`readme.md`** — follow `data/templates/keyboard/readme.md`; flash command with `:flash`; valid hardware-availability link (handwired exempt; private groupbuys OK; one-off prototypes questioned; open-source ⇒ link to files); explicit bootloader-entry instructions; **keyboard + PCB pictures hosted externally** (imgur etc.), linked **directly to the image** not a preview page (e.g. `https://i.imgur.com/vqgE7Ok.jpg`). No images in-repo.
- **`rules.mk`** — remove `MIDI_ENABLE`, `FAUXCLICKY_ENABLE`, `HD44780_ENABLE`; fix the Bluetooth comment to just `# Enable Bluetooth`; no `(-/+size)` comments; drop unused alternate-bootloader list; don't redefine MCU defaults that match `builddefs/mcu_selection.mk`; no keymap-only features (`COMBO_ENABLE`, `ENCODER_MAP_ENABLE`).
- **keyboard `config.h`** — no `#define DESCRIPTION`; no Magic/MIDI/HD44780 config; no user-preference `#define`s at keyboard level; don't redefine defaults (`DEBOUNCE`, RGB settings…); no copy-pasted feature-comment blocks or commented-out defines; no `#include "config_common.h"`; no `#define MATRIX_ROWS/COLS` unless custom matrix; bare-minimum boot code only; **no Vial files**.
- **`<keyboard>.c`** — remove empty/commented weak `_kb`/`_user` stubs; migrate `matrix_init_board()` → `keyboard_pre_init_kb()`; custom matrix uses `CUSTOM_MATRIX = lite` (justify full custom); prefer LED-indicator config options over `led_update_*()`; init on-board OLEDs/encoders here.
- **`<keyboard>.h`** — `#include "quantum.h"` at top; **no `LAYOUT` macros** (move to `info.json`).
- **keymap `config.h`** — no duplication of keyboard `rules.mk`/`config.h`.
- **`keymaps/default/keymap.c`** — remove `QMKBEST`/`QMKURL` examples; use **Tri Layer** (`features/tri_layer`) instead of manual `layer_on/off` + `update_tri_layer` in `process_record_user` when `MO(1)`+`MO(2)` reach a third layer.
- **Default keymaps must be pristine:** no custom keycodes, no advanced features (tap-dance/macros); basic mod-taps/home-row-mods OK where necessary; prefer standard layouts; use **encoder map** not `encoder_update_user()`; **no VIA**.
- You may add an example/`default_<vendor>` keymap in the same PR.
- **No VIA `.json`, no KLE `.json`, no source files copied from another keyboard/vendor folder** in the PR. (Core files like `drivers/sensors/pmw3360.c` are fine for any board.) Multi-board code ⇒ candidate for core.

**Wireless-capable boards:** QMK rejects vendor PRs for wireless/BT keyboards that ship **without** wireless/bt sources (historical bad-faith VIA-compat abuse; GPL2+ requires full source disclosure for distributed binaries). Such PRs are held unmergeable until bindings arrive; if a wireless board is discovered post-merge, **all** that vendor's PRs go on hold until resolved.

**ChibiOS-specific:**
- Strong preference for **existing ChibiOS board definitions** (e.g. an STM32L082KZ can use `BOARD = ST_NUCLEO64_L073RZ`).
- New board definitions **must not be embedded in a keyboard PR** — see §7.4.
- If unavoidable: `board.c` needs standard `__early_init()` + empty `boardInit()`; migrate `__early_init()` → `early_hardware_init_pre()`/`early_hardware_init_post()`, `boardInit()` → `board_init()`.

### 7.4 Core PRs

- **Target `develop`** (merged to `master` on the breaking-changes schedule).
- **Smallest set of changes** — multi-area PRs get split. Keyboard/keymap changes only if they affect base/default-like builds; everything else as a follow-up PR after merge. Large refactors/renames always separate.
- **New hardware needs a test board** under `keyboards/handwired/onekey` — a child keyboard targeting the new MCU (new MCU), or a keymap exercising the new peripheral (display panel, matrix impl, etc.). Exception: an existing keymap already covers it (e.g. `rgb` for a new RGB driver chip) — confirm on Discord.
- **New `_kb`/`_user` callbacks must return `bool`.**
- **Unit tests strongly recommended** for critical paths; the **keycode-handling pipeline** almost certainly requires them. Don't be surprised if a collaborator demands them.
- Other requirements at collaborators' discretion (core is subjective).

### 7.5 Example license header (GPL2+)

```c
/* Copyright 2024 Your Name (@yourgithub)
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */
```

SPDX shorthand is also accepted:

```c
// Copyright 2024 Your Name (@yourgithub)
// SPDX-License-Identifier: GPL-2.0-or-later
```

### 7.6 Review process

- Want **2+ meaningful (code-inspected) approvals** before merge. Community reviews count (just no green checkmark). Reviewers are unpaid volunteers; ~200 PRs/month each way — be patient.

### 7.7 Gotchas — PR checklist

- **Core + keyboard PRs go to `develop`, not `master`** — a frequent first-PR mistake.
- **First custom-keycode enum entry must be `QK_USER`** (keymap PRs) — `SAFE_RANGE` is the older pattern but checklist calls for `QK_USER`.
- **Missing license headers block merge** — even one file.
- **Wireless-without-sources** PRs are hard-held for all of a vendor's future PRs.
- **VIAL/KLE/VIA JSON files are PR-rejects** — they don't belong in `qmk_firmware`.
- **Default keymap must stay pristine** — no tap-dance, no macros, no custom keycodes.

---

## 8. Documentation best practices & templates

### 8.1 Page structure

- Start with an **H1 heading**, then a **1-paragraph** description. (The H1 + paragraph sit next to the Table of Contents, so keep the heading short and avoid long no-whitespace strings.)
- **Multiple H1 headings are fine** — but only **H1 and H2** appear in the ToC. Plan them; avoid wide H1/H2 strings.
- **Paragraphs:** one raw-Markdown line each (no hard line breaks within a paragraph — they're a no-op anyway; use editor line-wrapping).

### 8.2 Styled hint blocks (vuepress containers)

| Block | Syntax | Use |
|-------|--------|-----|
| Warning | `::: warning` … `:::` | Important / must-read |
| Tip | `::: tip` … `:::` | Helpful suggestion |
| Info | `::: info` … `:::` | General note |

```markdown
::: warning
This is important
:::

::: tip
This is a helpful tip.
:::
```

### 8.3 Documenting a new feature

Create `docs/features/<my_cool_feature>.md`, add it to `docs/_sidebar.json`, and (if it adds keycodes) list them in `docs/keycodes.md` linking back. Minimal template:

```markdown
# My Cool Feature

This page describes my cool feature. You can use my cool feature to ...

## My Cool Feature Keycodes

|Long Name|Short Name|Description|
|---------|----------|-----------|
|KC_COFFEE||Make Coffee|
|KC_CREAM||Order Cream|
|KC_SUGAR||Order Sugar|
```

### 8.4 Templates

**Keymap `readme.md`:** an image (KLE → hosted on imgur, **not** in-repo) + a short description.

```markdown
![Clueboard Layout Image](https://i.imgur.com/7Capi8W.png)

# Default Clueboard Layout

This is the default layout that comes flashed on every Clueboard. ...
```

**Keyboard `readme.md`** (`data/templates/keyboard/readme.md`):

```markdown
# Planck

![Planck](https://i.imgur.com/q2M3uEU.jpg)

A compact 40% (12x4) ortholinear keyboard kit made and sold by OLKB and Massdrop.
[More info on qmk.fm](https://qmk.fm/planck/)

* Keyboard Maintainer: [Jack Humbert](https://github.com/jackhumbert)
* Hardware Supported: Planck PCB rev1, rev2, rev3, rev4, Teensy 2.0
* Hardware Availability: [OLKB.com](https://olkb.com), [Massdrop](https://www.massdrop.com/...)

Make example for this keyboard (after setting up your build environment):

    make planck/rev4:default

Flashing example for this keyboard:

    make planck/rev4:default:flash

See the [build environment setup](getting_started_build_tools) and the
[make instructions](getting_started_make_guide) for more information. Brand new
to QMK? Start with our [Complete Newbs Guide](newbs).

## Bootloader

Enter the bootloader in 3 ways:

* **Bootmagic reset**: Hold down the key at (0,0) in the matrix (usually the top
  left key or Escape) and plug in the keyboard
* **Physical reset button**: Briefly press the button on the back of the PCB -
  some may have pads you must short instead
* **Keycode in layout**: Press the key mapped to `QK_BOOT` if it is available
```

> The three bootloader-entry methods above (Bootmagic reset, physical reset, `QK_BOOT` keycode) are the convention every keyboard `readme.md` should document — flashing mechanics are covered in `15-flashing-debugging.md`.

### 8.5 Gotchas — Documentation

- **Only H1/H2 enter the ToC** — H3+ headings won't, so structure accordingly.
- **Images go external** (imgur etc.), linked **directly** to the image file, never a preview page, never in-repo.
- **Use the canonical enum names** (`my_layers`, `my_keycodes`) in examples for consistency.
- **Preview with `qmk docs -b`** (port 8936) before opening a PR.

---

## 9. Support & community

Read the [Code of Conduct](https://qmk.fm/coc/) before participating.

| Channel | Best for |
|---------|----------|
| [Discord](https://discord.gg/qmk) | Realtime help — usually someone online |
| [/r/olkb](https://reddit.com/r/olkb) (Reddit) | The official QMK forum |
| [GitHub Issues](https://github.com/qmk/qmk_firmware/issues) | Long-term discussion / debugging |

When asking: be patient (responses can take hours), remember everyone's a volunteer, and frame the question to be easy to answer.

---

## 10. Glossary

Definitions of the key QMK terms an agent/helper will encounter.

| Term | Definition |
|------|-----------|
| **ARM** | Line of 32-bit MCUs (Atmel, Cypress, Kinetis, NXP, ST, TI). |
| **AVR** | Line of 8-bit MCUs by Atmel/Microchip — the original TMK platform. |
| **Backlight** | Generic term for keyboard lighting; typically an LED array shining through keycaps/switches. |
| **Bluetooth** | Short-range peer-to-peer wireless; most common keyboard wireless protocol. |
| **Bootloader** | Special program in a protected MCU area that lets the MCU upgrade its own firmware (usually over USB). |
| **Bootmagic** | Feature for on-the-fly behavior changes (swap/disable keys, etc.). |
| **C** | Low-level systems language; most QMK code is C. |
| **Compile** | Turning human-readable code into MCU machine code. |
| **Dynamic Macro** | A macro recorded on the keyboard; lost on unplug/reboot. |
| **Firmware** | The software that controls the MCU. |
| **Flash** | (Verb) writing firmware to the MCU; (noun) the result. |
| **git** | Command-line version-control software. |
| **GitHub** | Hosts most of QMK; provides git integration, issue tracking. |
| **hid_listen** | Interface for receiving keyboard debug messages (via QMK Flasher or PJRC's hid_listen). |
| **info.json** | Data-driven keyboard config file (schema: `data/schemas/keyboard.jsonschema`); modern replacement for many `rules.mk`/`config.h` options. See `03-config-and-info-json.md`. |
| **ISP** | In-system programming — flashing an AVR via external hardware + JTAG pins. |
| **Keycode** | A **2-byte** number representing a key. `0x00`–`0xFF` = Basic Keycodes; `0x100`–`0xFFFF` = Quantum Keycodes. |
| **Key Down / Key Up / Tap** | Key-press event / key-release event / press-then-release. "Tap" = both at once. |
| **Keymap** | An array of keycodes mapped to a physical layout, processed on press/release. |
| **Layer** | Abstraction letting one key serve multiple purposes; **highest active layer wins**. |
| **Leader Key** | Tap leader then a 1–3 key sequence to fire an action. |
| **LED** | Light-Emitting Diode; most common indicator device. |
| **Make** | Build system that compiles all sources into firmware. |
| **Macro** | Feature sending multiple keypress events from one key. |
| **Matrix** | Wiring pattern of columns × rows letting an MCU detect presses with fewer pins; usually uses diodes for NKRO. |
| **MCU** | Microcontroller Unit — the processor powering the keyboard. |
| **Modifier** | A held key that changes another key's action (Ctrl, Alt, Shift, GUI). |
| **Mousekeys** | Feature controlling the mouse cursor + clicks from the keyboard. |
| **NKRO (N-Key Rollover)** | Keyboard can report any number of simultaneous presses. Variants: 2KRO, 6KRO, NKRO. |
| **Oneshot Modifier** | Modifier that behaves held until the next key is released (a.k.a. Sticky / Dead key). |
| **ProMicro** | Low-cost AVR dev board; cheap clones common but flashing can be finicky. |
| **Pull Request (PR)** | Request to submit code to QMK; encouraged for bugfixes and features. |
| **QMK_USERSPACE** | Build define/path set when a userspace is being compiled in. (See `02-getting-started-build.md` for the External Userspace variant.) |
| **Rollover** | Pressing a key while another is held. |
| **Scancode** | A **1-byte** number sent in a HID report representing one key (per USB-IF HID Usage Tables). |
| **Space Cadet Shift** | Shift keys that type braces when tapped N times. |
| **Tap Dance** | Multiple keycodes on one key based on press count. |
| **Teensy** | Low-cost AVR dev board for hand-wired builds; popular for its Halfkay bootloader. |
| **Underlight** | LEDs lighting the underside of the board (shine toward the resting surface). |
| **Unicode** | OS schemes to send unicode codepoints instead of scancodes. |
| **Unit Testing** | Automated test framework for QMK. |
| **USB** | Universal Serial Bus — most common wired keyboard interface. |
| **USB Host** | Your computer / whatever the keyboard is plugged into. |
| **AZERTY / QWERTY / QWERTZ / Colemak / Dvorak** | Standard/alternative keyboard layouts (named for their first row of keys). |
| **Eclipse** | C-friendly IDE (QMK has setup docs). |

> Couldn't find a term? Open an issue (or PR the definition) against `docs/reference_glossary.md`.

---

## 11. Learning syllabus

The QMK docs organize learning into three tiers. (Original page: `docs/syllabus.md`.)

### 11.1 Beginning topics (read these first)

After the **Tutorial** you should be able to create, compile, and flash a basic keymap.

- **QMK Tools:** [Tutorial] → [CLI] → [git best practices]
- **Keymaps:** [Layers] → [Keycodes] (full list; some need Intermediate/Advanced knowledge)
- **(Optional) IDE setup:** Eclipse, VS Code

### 11.2 Intermediate topics

- **Configuring features:** Audio; Lighting (Backlight, LED Matrix, RGB Lighting, RGB Matrix); Tap-Hold config; Squeezing AVR space
- **More about keymaps:** Keymaps; Custom Functions & Keycodes; Macros (Dynamic + Compiled); Tap Dance; Combos; **Userspace**; Key Overrides

### 11.3 Advanced topics

*(Requires familiarity with `config.h` and `rules.mk`.)*

- **Maintaining keyboards in QMK:** Handwiring; Keyboard Guidelines; `info.json` reference; Debounce API
- **Advanced features:** Unicode; API; Bootmagic
- **Hardware:** How Keyboards Work; How a Matrix Works; Split Keyboards; Stenography; Pointing Devices
- **Core development:** C Coding Conventions; Compatible Microcontrollers; Custom Matrix; Understanding QMK
- **CLI development:** Python Coding Conventions; CLI Development Overview

### 11.4 Mapping the syllabus onto these references

| Syllabus area | Reference |
|---------------|-----------|
| Tutorial / CLI / git / build / flash | `02-getting-started-build.md` |
| Layers / keycodes / keymap.c | `04-keymaps-and-keycodes.md` |
| `config.h` / `info.json` / debounce / keyboard guidelines | `03-config-and-info-json.md` |
| Lighting (backlight/LED/RGB/RGB-matrix) | `07-led-rgb-backlight.md` |
| Tap-hold / combos / macros / tap-dance / key overrides | `05-text-input-and-combos.md` |
| **Userspace** | **this file (§1)** + `02` §7 |
| Unicode / bootmagic / pointing / stenography | `11-other-features.md`, `06-pointing-and-hid-devices.md` |
| Hand-wire / matrix / split / MCU / custom matrix | `12-hardware-platforms.md` |
| Coding conventions (C + Python), CLI/API dev, contributing, PRs | **this file (§2–§8)** |
| Flashing / ISP / unit testing / IDEs / squeezing AVR | `15-flashing-debugging.md` |
| API / Configurator / VIA | `14-configurator-api-via.md` |

---

### End-note: cross-references at a glance

- **`01-architecture.md`** §7 (process_record dispatch chain, halt semantics) & §9 (full overrideable-hook catalog) — the userspace usually implements `process_record_user` / `matrix_scan_user` / `layer_state_set_user` etc.; consult 01 for ordering and signatures, not this file.
- **`02-getting-started-build.md`** §7 — the **External Userspace** repo + `qmk userspace-add/remove/list/compile/doctor` commands; the modern, upstream-supported sharing mechanism (vs. the in-tree `users/` feature here).
- **`03-config-and-info-json.md`** — data-driven equivalents of `config.h` `#define`s; `QMK_USERSPACE` build define.
- **`18-community-modules.md`** — **community modules**, an alternative opt-in code-sharing system that doesn't require a matching keymap name.
- **`14-configurator-api-via.md`** — the public QMK API / Configurator / VIA side (distinct from the self-hosted Compile API in §5).
- **`15-flashing-debugging.md`** — flashing mechanics, `QK_BOOT`, unit testing, IDE setup.
- **`17-faq-gotchas-breaking-changes.md`** — deprecation policy and breaking-changes history (why in-tree userspace/keymap PRs closed).
