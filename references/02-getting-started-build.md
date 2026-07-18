# 02 — Getting Started & Build Workflow

> The agent's map of **environment setup**, the **build/flash loop**, the **QMK CLI** (full command catalog), **make-based** building, **External Userspace** + GitHub Actions, the **Configurator** path, **Docker**, and the **Git workflow** for contributing. This is the onboarding reference: it tells you how to turn source into a `.hex`/`.bin`/`.uf2` and get it onto a board.
>
> Sources synthesized: `newbs.md`, `newbs_getting_started.md`, `newbs_building_firmware.md`, `newbs_building_firmware_configurator.md`, `newbs_building_firmware_workflow.md`, `newbs_flashing.md`, `newbs_external_userspace.md`, `newbs_git_best_practices.md`, `newbs_git_resolving_merge_conflicts.md`, `newbs_git_resynchronize_a_branch.md`, `newbs_git_using_your_master_branch.md`, `newbs_learn_more_resources.md`, `newbs_testing_debugging.md`, `cli.md`, `cli_commands.md`, `cli_configuration.md`, `cli_tab_complete.md`, `getting_started_docker.md`, `getting_started_github.md`, `getting_started_introduction.md`, `getting_started_make_guide.md`.

---

## 0. TL;DR — The 60-Second Path From Zero To Flashed

```sh
# 1. Install QMK CLI (Windows: use QMK MSYS bundle instead)
curl -fsSL https://install.qmk.fm | sh

# 2. Set up the firmware tree (clones qmk_firmware, installs deps). Answer y to prompts.
qmk setup

# 3. (Optional) set your default keyboard/keymap so you can omit them later
qmk config user.keyboard=clueboard/66/rev4 user.keymap=<your_github_username>

# 4. Create a personal keymap (copies the keyboard's default keymap)
qmk new-keymap        # or:  qmk new-keymap -kb <keyboard>

# 5. Edit the generated keymap, then build
qmk compile           # or:  qmk compile -kb <keyboard> -km <keymap>

# 6. Put the board in bootloader mode, then flash + reboot
qmk flash             # or:  qmk flash -kb <keyboard> -km <keymap>
```

**Three big rules that prevent most pain:**

1. **Never commit to your fork's `master`** — update it often, do all work on feature branches (see §11). This is the single most repeated piece of advice in the QMK docs.
2. **`qmk doctor` is your friend** — if a build or flash is misbehaving, run it; it detects missing tools, udev rules, and CLI/bootloader issues and can fix many of them.
3. **The `-kb`/`-km` you pass is a path, not a name** — `clueboard/66/rev4` is the path under `keyboards/`. `qmk list-keyboards` / `qmk list-keymaps -kb <kb>` resolve ambiguity.

The build artifacts land in the **root of `qmk_firmware`** (or your External Userspace dir) named `<keyboard>_<keymap>.{hex|bin|uf2}`, *and* a copy stays in `.build/`.

---

## 1. Repository Layout (what's where)

QMK is a fork of Jun Wako's `tmk_keyboard`. Key folders inside `qmk_firmware/`:

| Folder | Contents |
|---|---|
| `quantum/` | QMK's additions on top of TMK (features, keycodes, RGB, etc.) |
| `tmk_core/` | Original TMK code (protocol, common) |
| `keyboards/` | One directory per keyboard project, incl. `handwired/` and vendor dirs |
| `keyboards/<kb>/keymaps/<name>/` | A keymap (see below) |
| `layouts/<layout>/<name>/` | Community/shared keymaps by layout name (e.g. `60_ansi`) |
| `users/<name>/` | Per-user **userspace** code shared across keyboards |
| `lib/` | Submodules: `chibios`, `chibios-contrib`, `lufa`, `googletest`, `...` |
| `util/` | Helper scripts (`docker_build.sh`, `qmk_tab_complete.sh`, installers) |

### Keyboard project structure (`keyboards/<kb>/`)

- `keymaps/` — different keymaps that can be built
- `rules.mk` — default make options. **Do not edit directly**; override in a keymap-specific `rules.mk`.
- `config.h` — default compile-time options. **Do not edit directly**; override in a keymap-specific `config.h`.
- `info.json` — data-driven config (layouts, features, matrix, bootloader). See `03-config-and-info-json.md`.
- `<keyboard>.h` — layout macros defined against the switch matrix
- `<keyboard>.c` — custom keyboard code
- `readme.md` — overview

### Keymap structure (`keyboards/<kb>/keymaps/<name>/`)

Only `keymap.c` (or `keymap.json`) is required; missing files fall back to defaults.

| File | Purpose |
|---|---|
| `keymap.c` | All of your keymap code (**required** if not using JSON) |
| `keymap.json` | Data-driven keymap (Configurator export); alternative to `keymap.c` |
| `config.h` | Keymap-level config overrides |
| `rules.mk` | Keymap-level feature overrides |
| `readme.md` | Description of the keymap |

### `config.h` lookup order (build system picks all three in this order)

1. keyboard: `/keyboards/<keyboard>/config.h`
2. userspace: `/users/<user>/config.h`
3. keymap: `/keyboards/<keyboard>/keymaps/<keymap>/config.h`

To override a setting from an earlier file, you must first `#undef` then `#define` again under a `#pragma once`:

```c
#pragma once
#undef MY_SETTING
#define MY_SETTING 4
```

> Cross-ref: the data-driven `info.json` schema, `rules.mk` semantics, EEPROM, and debounce config are all covered in **`03-config-and-info-json.md`**. Keymap authoring (layers, keycodes, mod_tap, etc.) is in **`04-keymaps-and-keycodes.md`**.

---

## 2. Setting Up Your Environment

### 2.1 Install the QMK CLI

The recommended, universal installer (do **not** use distro packages — they are "almost certainly out of date"):

```sh
curl -fsSL https://install.qmk.fm | sh
```

For installer options: `curl -fsSL https://install.qmk.fm | sh -s -- --help`.

**Per-OS specifics:**

| OS | Notes |
|---|---|
| **Windows** | Use the **QMK MSYS** bundle (MSYS2 + CLI + toolchain + udev deps). Advanced users can install plain MSYS2 then run the curl installer in a **MinGW 64-bit** terminal — *not* the default MSYS terminal (prompt must say `MINGW64`). |
| **macOS** | Install Homebrew (`https://brew.sh`), then run the curl installer. |
| **Linux/WSL** | Run the curl installer. Best on Debian/Ubuntu/Mint, CentOS/Fedora/Rocky, Arch/Manjaro/CachyOS. **The standard environment does NOT support `musl`-based distros** (e.g. Alpine). WSL: keep the repo **inside the WSL filesystem**, not under `/mnt/...` (Windows-FS access is extremely slow). |
| **FreeBSD** | `pkg install -g "py*-qmk"` — best-effort, community-supported. Follow the post-install instructions (`pkg info -Dg "py*-qmk"` to re-show). |

### 2.2 The `qmk setup` step

```sh
qmk setup            # answer y to the prompts
```

This clones `qmk_firmware` (with submodules) into your QMK home and installs the toolchain/flasher deps. Useful variants:

| Variant | Effect |
|---|---|
| `qmk setup -H <path>` | Put `qmk_firmware` at `<path>` instead of the default |
| `qmk setup <github_username>/qmk_firmware` | Clone your **personal fork** instead of `qmk/qmk_firmware` (recommended if you'll PR; see §11) |
| `qmk setup --help` | All options |

QMK home is later changeable via `qmk config user.qmk_home=<path>`.

### 2.3 The Debian/Ubuntu PATH bug (important)

On Debian/Ubuntu and derivatives, `bash` may not have `$HOME/.local/bin` on `PATH`, so you'll get `qmk: command not found`. Fix:

```sh
echo 'PATH="$HOME/.local/bin:$PATH"' >> $HOME/.bashrc && source $HOME/.bashrc
```

### 2.4 Validate: build a known-good firmware

```sh
qmk compile -kb clueboard/66/rev3 -km default
```

A healthy run ends like:

```
Linking: .build/clueboard_66_rev3_default.elf                                  [OK]
Creating load file for flashing: .build/clueboard_66_rev3_default.hex          [OK]
Copying clueboard_66_rev3_default.hex to qmk_firmware folder                   [OK]
Checking file size of clueboard_66_rev3_default.hex                            [OK]
 * The firmware size is fine - 26356/28672 (2316 bytes free)
```

### Gotchas

- **Distro `qmk` packages are stale** — always use the curl installer (or QMK MSYS on Windows).
- **`musl`-based Linux is unsupported** by the standard environment (use Docker or switch libc).
- **WSL:** clone into the Linux FS, never `/mnt/c/...`.
- **Windows MinGW:** the post-install MSYS terminal (purple) is *not* what you want — open the blue **MinGW 64-bit** terminal so the prompt reads `MINGW64`.
- **Optional GUI flasher:** [QMK Toolbox](https://github.com/qmk/qmk_toolbox) is Windows/macOS only. (See §10 for why RP2040 boards don't need it.)

---

## 3. QMK CLI Configuration (`qmk config`)

`qmk config` is a key/value store. Each key is `<subcommand|general|user|default>.<key>`, mirroring the CLI argument name with a period. Stored in `qmk.ini` (e.g. `~/Library/Application Support/qmk/qmk.ini` on macOS, `~/.config/qmk/qmk.ini` on Linux).

### Token grammar

```
<subcommand|general|default>[.<key>][=<value>]
```

- `qmk config` — show **entire** configuration
- `qmk config compile` — show a whole **section**
- `qmk config compile.keyboard` — show a **single key**
- `qmk config user compile.keyboard compile.keymap` — show **multiple** keys
- `qmk config user.keyboard=clueboard/66/rev4` — **set** (must be full `<section>.<key>`)
- `qmk config default.keymap=None` — **delete** (set to literal string `None`)
- Multiple read/write tokens in one command run left-to-right.

### The two most useful defaults

```sh
qmk config user.keyboard=clueboard/66/rev4 user.keymap=<your_github_username>
```

Setting `user.*` means **every** subcommand that takes `--keyboard`/`--keymap` picks these up — so `qmk compile`, `qmk flash`, `qmk new-keymap`, `qmk lint`, etc. all Just Work with no args.

> Note: the per-command `compile.keyboard`/`compile.keymap` keys exist too, but `user.*` is broader — it applies to all commands, not just `compile`.

### Full config-option table

| Key | Default | Description |
|---|---|---|
| `user.keyboard` | `None` | Default keyboard path (e.g. `clueboard/66/rev4`) |
| `user.keymap` | `None` | Default keymap name |
| `user.name` | `None` | GitHub username (used by `new-keyboard`, `new-keymap` defaults) |
| `compile.keyboard` | `None` | Default keyboard for `qmk compile` only |
| `compile.keymap` | `None` | Default keymap for `qmk compile` only |
| `new_keyboard.keyboard` | `None` | Default for `qmk new-keyboard` |
| `new_keyboard.keymap` | `None` | Default for `qmk new-keymap` |
| `hello.name` | `None` | Name greeted by `qmk hello` |
| `default.keymap` | `None` | Fallback default keymap name |

### Gotchas

- `None` is a literal string token for deletion — don't quote it.
- `compile.*` only affects `qmk compile`; set `user.*` if you want flash/new-keymap to also inherit defaults.
- The exact `qmk.ini` path varies by OS; the CLI prints where it wrote on every save.

---

## 4. The Build Workflow (CLI)

### 4.1 Create a keymap

```sh
qmk new-keymap                       # uses user.keyboard / user.keymap defaults
qmk new-keymap -kb <keyboard>        # explicit keyboard
```

This **copies the keyboard's `default` keymap** to `keyboards/<keyboard>/keymaps/<your_name>/` (path is printed). The default keymap may be `.c` or `.json`; convert a `.json` to `.c` with `qmk json2c` (§5.4).

The `keymap.c` structure: defines/enums at top, then

```c
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    // one LAYOUT(...) block per layer
};
```

> **Watch the commas.** Adding/removing a stray comma in a `LAYOUT(...)` block breaks the build in ways that are hard to locate. Make small changes when learning.

### 4.2 `qmk compile`

Directory-aware: run it inside a keyboard dir, keymap dir, or layout dir and it auto-fills `KEYBOARD`/`KEYMAP`.

| Usage | When |
|---|---|
| `qmk compile` | In a keyboard dir (needs a `default` keymap or `compile.keymap`), in a keymap dir, or with `user.*`/`compile.*` defaults set |
| `qmk compile -kb <keyboard> -km <keymap>` | Explicit |
| `qmk compile -kb all -km <keymap>` | Build **every keyboard** that supports that keymap |
| `qmk compile <configuratorExport.json>` | Build a Configurator JSON export (see §9) |
| `qmk compile -c ...` | Clean first (`-c` = clean) |
| `qmk compile -e <var>=<value>` | Pass a make variable (repeatable) |
| `qmk compile -j <n>` | Parallel jobs; `-j 0` = unlimited |
| `qmk compile --compiledb` | Also emit `compile_commands.json` (for IDE language servers — kills red squiggles on `#include QMK_KEYBOARD_H`) |
| `qmk compile -km <name>` (in keyboard dir) | One specific keymap of the current keyboard |

In a `layouts/<layout>/<name>/` folder, supply `-kb <keyboard>` to bind the community keymap to a target.

### 4.3 `qmk flash`

Same options as `compile`, plus bootloader targeting:

```sh
qmk flash                                  # uses defaults; bootloader = :flash
qmk flash -kb <keyboard> -km <keymap>
qmk flash -bl <bootloader>                 # override bootloader
qmk flash -b                               # LIST available bootloaders
qmk flash <file.hex|file.bin>              # flash a pre-compiled binary
qmk flash -m <mcu> <file.hex>              # for HalfKay / QMK HID / USBaspLoader, or ISP flashers (USBasp, USBtinyISP)
```

`qmk flash` **auto-detects the bootloader** from the keyboard's config — you usually don't need to know it. If the bootloader isn't configured/supported:

```
WARNING: This board's bootloader is not specified or is not supported by the ":flash" target at this time.
```

In that case specify `-bl <bootloader>` explicitly (see `15-flashing-debugging.md` for the full bootloader catalog and ISP flashing).

If a flash fails to detect the board, run **`qmk doctor`** — it spots missing udev rules / drivers / toolchain issues.

### Gotchas

- `-bl` defaults to `:flash`; mass-storage bootloaders (some STM32, RP2040 UF2) are **not** supported by the `flash` target — copy the file manually for those.
- For HalfKay/QMK HID/USBaspLoader **and** for ISP flashers (USBasp, USBtinyISP), you must pass `-m <microcontroller>`.
- `qmk flash` requires the bootloader be set in the keyboard's config (`info.json` `bootloader` or legacy `rules.mk` `BOOTLOADER`); see `03-config-and-info-json.md`.
- On Linux you may need `udev` rules or `sudo` for the flasher to see the device (see `15-flashing-debugging.md`).

---

## 5. The Full QMK CLI Command Catalog

> Authoritative reference for `cli_commands.md`. Grouped as **User**, **External Userspace**, and **Developer** commands. "Directory-aware" commands auto-detect `KEYBOARD`/`KEYMAP` from your cwd.

### 5.1 User commands

| Command | Purpose | Key usage |
|---|---|---|
| `qmk compile` | Build firmware | `qmk compile [-c] [-e v=val] [-j n] [--compiledb] [-kb K] [-km M] [file.json]` — directory-aware |
| `qmk flash` | Build + flash to a bootloader | `qmk flash [-bl B] [-b] [-c] [-e v=val] [-j n] [-m mcu] [-kb K] [-km M] [file]` — directory-aware |
| `qmk config` | Read/write CLI config | `qmk config [-ro] [token ...]` (see §3) |
| `qmk cd` | Open a shell in `QMK_HOME` | `qmk cd` (no-op if already inside `QMK_HOME`) |
| `qmk find` | Search keyboards/keymaps by `info.json` data | `qmk find [-km M] [-p PRINT] [-f FILTER]` (filters repeatable) |
| `qmk console` | Live `dprint`/`print`/`uprint` console from a keyboard | `qmk console [-d pid:vid[:idx]] [-l] [-n] [-t] [-w s] [--no-bootloaders]` (needs `CONSOLE_ENABLE=yes`) |
| `qmk doctor` | Diagnose + fix build/flash environment | `qmk doctor [-y|-n]` (`-y` = auto-fix, `-n` = report only) |
| `qmk format-json` | Pretty-print an `info.json`/`keymap.json` | `qmk format-json [-f FORMAT] <file>` (auto-detects format) |
| `qmk info` | Show keyboard/keymap info, layouts, matrix | `qmk info [-f FORMAT] [-m] [-l] [-km M] [-kb K]` — directory-aware |
| `qmk json2c` | Configurator JSON → `keymap.c` | `qmk json2c [-o OUTPUT] <file>` |
| `qmk c2json` | `keymap.c` → Configurator JSON | `qmk c2json -km M -kb K [-q] [--no-cpp] [-o OUT] [file]` (parsing C is fragile) |
| `qmk lint` | Check keyboard/keymap for errors/anti-patterns | `qmk lint [-km M] [-kb K] [--strict]` — directory-aware |
| `qmk list-keyboards` | List all keyboards | `qmk list-keyboards` |
| `qmk list-keymaps` | List keymaps for a keyboard | `qmk list-keymaps -kb K` — directory-aware |
| `qmk migrate` | Move legacy `rules.mk`/`config.h` → `info.json` | `qmk migrate -kb K [-f FILTER]` |
| `qmk new-keyboard` | Scaffold a new keyboard from templates | `qmk new-keyboard [-kb K] [-t MCU] [-l LAYOUT] -u USER` (prompts for blanks) |
| `qmk new-keymap` | Copy default keymap to a new name | `qmk new-keymap [-kb K] [-km M]` — directory-aware |
| `qmk clean` | Remove `.build/` (and, with `-a`, root `.hex`/`.bin`) | `qmk clean [-a]` |
| `qmk via2json` | VIA backup JSON → QMK `keymap.json` (layers + macros) | `qmk via2json -kb K [-l LAYOUT] [-km M] [-o OUT] <file>` |
| `qmk import-keyboard` | Import a data-driven `info.json` keyboard into the repo | `qmk import-keyboard <file>` |
| `qmk import-keymap` | Import a data-driven `keymap.json` into the repo | `qmk import-keymap <file>` |
| `qmk import-kbfirmware` | Import a kbfirmware.com export as a new keyboard | `qmk import-kbfirmware <file>` (basic — prefer `new-keyboard`) |

#### `qmk find` filter grammar

Filters repeat; **all** must match. Values may include `*`/`?` wildcards.

| Expression | Meaning |
|---|---|
| `key == value` | equality (wildcards allowed) |
| `key != value` | inequality (wildcards allowed) |
| `key < value`, `>`, `<=`, `>=` | numeric comparison |
| `exists(key)` / `absent(key)` | key present / absent |
| `contains(key, value)` | key contains value (strings, arrays, object keys) |
| `length(key, value)` | length of key equals value |

```sh
qmk find -f 'processor==STM32F411' -f 'features.rgb_matrix==true'
qmk find -f 'processor==STM32F411' -p 'keyboard_name' -p 'features.rgb_matrix'
```

### 5.2 External Userspace commands

| Command | Purpose | Key usage |
|---|---|---|
| `qmk userspace-add` | Add a keyboard/keymap (or loose JSON) to External Userspace build targets | `qmk userspace-add [-km M] [-kb K] [builds ...]` |
| `qmk userspace-remove` | Remove a build target | `qmk userspace-remove [-km M] [-kb K] [builds ...]` |
| `qmk userspace-list` | List External Userspace build targets | `qmk userspace-list [-e]` (`-e` expands `all`) |
| `qmk userspace-compile` | Build **all** External Userspace targets | `qmk userspace-compile [-e v=val] [-p] [-n] [-c] [-j N] [-t]` |
| `qmk userspace-doctor` | Diagnose External Userspace setup | `qmk userspace-doctor` |

These update/read `qmk.json` in your External Userspace root. See §7.

### 5.3 Developer commands

| Command | Purpose | Key usage |
|---|---|---|
| `qmk format-text` | Enforce Unix (LF) line endings on all text files | `qmk format-text` (Windows devs: required for PR merge) |
| `qmk format-c` | clang-format C code | `qmk format-c [-a] [-b branch] [files...]` (no args = changed vs `origin/master`) |
| `qmk format-python` | Format python in `qmk_firmware` | `qmk format-python` |
| `qmk pytest` | Run the python test suite | `qmk pytest [-t TEST]` |
| `qmk test-c` | Run the C unit test suite | `qmk test-c [-t TEST] [-l] [-c] [-e ENV] [-j N]` (`-l` lists, globs supported) |
| `qmk docs` | Live-reload local docs server (port 8936) | `qmk docs [-b] [-p PORT]` (needs `node`+`yarn`) |
| `qmk generate-docs` | Build docs for production | `qmk generate-docs [-s]` (needs `node`+`yarn`, symlink support) |
| `qmk generate-rgb-breathe-table` | RGB breathing LUT header | `qmk generate-rgb-breathe-table [-q] [-o OUT] [-m MAX] [-c CENTER]` |
| `qmk kle2json` | KLE raw data → QMK Configurator JSON (`info.json`) | `qmk kle2json [-f] <file>` (`-f` overwrite) |
| `qmk painter-convert-graphics` | Image → QGF (Quantum Painter) | see Quantum Painter docs |
| `qmk painter-make-font-image` | TTF → intermediate font image | see Quantum Painter docs |
| `qmk painter-convert-font-image` | Intermediate font image → QFF | see Quantum Painter docs |
| `qmk generate-compilation-database` | **DEPRECATED** — use `qmk compile --compiledb` instead | (ignored converters/env vars) |

> Cross-ref for testing/debugging depth: **`15-flashing-debugging.md`** (flashing, ISP, zadig, AVR/ARM debugging, unit testing, VS Code/Eclipse, squeezing AVR size, tab-complete) and **`16-userspace-development.md`** (CLI/API development, coding conventions, contributing, PR checklist). Note: `newbs_testing_debugging.md` itself is now just a redirect to `faq_misc#testing` and `faq_debug#debugging` (those live in `15`/`17`).

### 5.4 The JSON round-trip: `json2c` / `c2json` / `via2json` / `format-json` / `kle2json`

These are the conversion utilities that tie the Configurator world to the source world:

```sh
qmk json2c -o keymap.c keymap.json        # Configurator JSON -> keymap.c
qmk c2json -km mymap -kb handwired/foo keymap.c -o keymap.json
qmk via2json -kb ai03/polaris -o polaris_keymap.json polaris_via_backup.json
qmk format-json keymap.json               # normalize/pretty-print
qmk kle2json -f kle.txt                   # KLE -> info.json (use -f to overwrite)
```

#### Gotchas

- **`c2json` is fragile** — parsing C source is hard. If it fails, try `--no-cpp` (skip the C preprocessor).
- **`generate-compilation-database` is deprecated** — it can't see converters or env vars; use `qmk compile --compiledb` instead.
- **`import-kbfirmware` is "basic"** — QMK explicitly suggests `qmk new-keyboard` instead.
- **`kle2json` won't overwrite** an existing `info.json` without `-f`.

---

## 6. Make-Based Building (legacy / advanced)

Under the hood, `qmk compile`/`qmk flash` invoke `make`. You can call `make` directly for full control or legacy workflows.

### 6.1 Full syntax

```
make <keyboard>:<keymap>:<target>
```

- `<keyboard>` — path under `keyboards/` (e.g. `planck`, `planck/rev4`). `all` = every keyboard. If the keyboard has no revision folders, omit; the default folder is used when omitted.
- `<keymap>` — keymap name. `all` = every keymap.
- `<target>` — see below.

### 6.2 Targets

| Target | Effect |
|---|---|
| *(none)* / `all` | Compile the specified keyboard/keymap(s). `make planck/rev4:default` → one hex; `make planck/rev4:all` → one per keymap. |
| `flash`, `dfu`, `teensy`, `avrdude`, `dfu-util`, `bootloadhid` | Compile **and upload**. Programmer depends on the board: most = `dfu`; ChibiOS/ARM = `dfu-util`; classic Teensy = `teensy`. If compile fails, nothing is uploaded. |
| `clean` | Wipe build output for a from-scratch rebuild (run before normal builds when things act weird). |
| `distclean` | Also remove `.hex`/`.bin` files. |

**Developer targets:** `show_path`, `dump_vars`, `objs-size`, `show_build_options`, `check-md5`.

### 6.3 Useful make flags

| Flag | Effect |
|---|---|
| `COLOR=false` | Disable color output |
| `SILENT=true` | Only errors/warnings |
| `VERBOSE=true` | All gcc output (debug only) |
| `VERBOSE_LD_CMD=yes` / `VERBOSE_AS_CMD=yes` | Run linker/assembler with `-v` |
| `VERBOSE_C_CMD=<file.c>` | Add `-v` when compiling `<file.c>` |
| `DUMP_C_MACROS=<file.c> [> logfile]` | Dump preprocessor macros for `<file.c>` |
| `VERBOSE_C_INCLUDE=<file.c> [2> logfile]` | Dump included file list for `<file.c>` |
| `-j<n>` (on `make` itself) | Parallel jobs across `n` CPUs |

```sh
make planck/rev4:default:flash COLOR=false
sudo make planck/rev4:default:flash   # if udev rules aren't set up
```

### 6.4 `rules.mk` (build-feature toggles)

These are the **legacy** per-feature toggles (set to `yes`/`no`). The modern, preferred path is the data-driven `info.json` `features` block — see **`03-config-and-info-json.md`**. Documented here because you'll still see them everywhere.

| Variable | What it enables |
|---|---|
| `BOOTMAGIC_ENABLE` | Hold a key (default Escape) to reset EEPROM + ready for new firmware |
| `MOUSEKEY_ENABLE` | Cursor/click via keycodes |
| `EXTRAKEY_ENABLE` | System + audio control keycodes |
| `CONSOLE_ENABLE` | `hid_listen` debug printing (`dprint`/`print`/`xprintf`/`uprint`) — **eats significant flash** |
| `COMMAND_ENABLE` | Magic commands (default `LSHIFT+RSHIFT+KEY`); e.g. `MAGIC+D` debug, `MAGIC+N` toggle NKRO |
| `SLEEP_LED_ENABLE` | LED breathing while host sleeps (largely untested, needs work) |
| `NKRO_ENABLE` | Advertise up to 248 simultaneous keys (default 6). Off by default even when set; toggle with `NK_TOGG`. |
| `BACKLIGHT_ENABLE` | In-switch LED backlighting (`#define BACKLIGHT_PIN B7` in `config.h`) |
| `MIDI_ENABLE` | MIDI send/receive (`MI_ON`/`MI_OFF`) — largely untested |
| `UNICODE_ENABLE` | `UC(<codepoint>)`, code points up to `0x7FFF` |
| `UNICODEMAP_ENABLE` | `UM(<index>)` via a map table; up to `0x10FFFF` |
| `UCIS_ENABLE` | Mnemonic → unicode; up to `0x10FFFF` |
| `AUDIO_ENABLE` | Audio output on pin C6 |
| `VARIABLE_TRACE` | Debug variable-value changes (see unit testing) |
| `KEY_LOCK_ENABLE` | Key lock feature |
| `SPLIT_KEYBOARD` | Dual-MCU split support (includes `quantum/split_common`) |
| `SPLIT_TRANSPORT` | `= custom` for ARM splits (standard transport is AVR-specific) |
| `CUSTOM_MATRIX` | Replace default matrix scan with your own |
| `DEBOUNCE_TYPE` | `= custom` for a custom debounce implementation |
| `DEFERRED_EXEC_ENABLE` | Deferred executor (timed callback delays) |

### Console / debug-print interactions (the `CONSOLE_ENABLE` rabbit hole)

`CONSOLE_ENABLE=yes` enables `dprint`, `print`/`xprintf`, and `uprint` over `hid_listen` — but **all** are on by default, which can blow the `.hex` past the flash limit. Trim with `config.h`:

| `config.h` define | Effect |
|---|---|
| `NO_DEBUG` | Disable `dprint` only |
| `NO_PRINT` | Disable `print`/`xprintf` **and** `uprint` |
| `USER_PRINT` | Disable `print`/`xprintf` but **keep** `uprint` (do **not** also set `NO_PRINT`) |

> **Never put `uprint` calls in anything other than your own keymap code.** Bloating the core framework bloats everyone else's `.hex`.

### 6.5 Per-keymap `rules.mk` override

A `rules.mk` in your keymap directory **overrides** the keyboard-level one for that keymap. E.g. if the keyboard has `BACKLIGHT_ENABLE = yes` and you put `BACKLIGHT_ENABLE = no` in your keymap's `rules.mk`, your build has no backlight.

### Gotchas

- **`make` flashers often need root on Linux** if udev rules aren't installed — `sudo make ...:flash` or set up the udev rules (`qmk doctor` can help).
- **`CONSOLE_ENABLE` + full printing** is a frequent cause of "firmware too big" on AVR.
- **ARM splits** need `SPLIT_TRANSPORT = custom` (the stock transport is AVR-only).
- Prefer `qmk compile` over raw `make` for everyday work; it sets up the right environment variables and converters automatically.

---

## 7. External Userspace (build keymaps outside the firmware repo)

External Userspace lets you keep **your keymaps in your own repo**, decoupled from the QMK Firmware tree. You no longer fork-and-maintain `qmk_firmware`. The External Userspace dir **mirrors the firmware layout** — it can hold `keyboards/<kb>/keymaps/<name>/`, `layouts/<layout>/<name>/`, and `users/<name>/`.

> Cross-ref: the **userspace feature itself** (shared C across keyboards, `process_record_user` in a shared place, etc.) is detailed in **`16-userspace-development.md`**. This section covers the *repo layout + build/CI* mechanics.

### 7.1 Set up

Clone the skeleton and point the CLI at it:

```sh
cd $HOME
git clone https://github.com/qmk/qmk_userspace.git     # or your fork
qmk config user.overlay_dir="$(realpath qmk_userspace)"
```

> You still need a local copy of `qmk_firmware` to run the External Userspace CLI commands — the overlay is *additional*.

### 7.2 Add a keymap + build target

```sh
qmk new-keymap                 # creates the keymap (in the overlay dir)
# ...or manually: keyboards/<kb>/keymaps/<name>/  or  layouts/<layout>/<name>/keymap.*

qmk userspace-add -kb <keyboard> -km <keymap>          # add to build targets (writes qmk.json)
qmk userspace-add <relative/path/to/keymap.json>       # ...or a loose JSON keymap

qmk userspace-list                                       # see what's configured
qmk userspace-compile                                    # build ALL targets at once
```

`userspace-compile` drops the resulting `.hex`/`.bin`/`.uf2` files in the **root of your External Userspace directory**.

### 7.3 GitHub Actions (CI builds)

With build targets in `qmk.json` and workflows enabled in repo settings, every **push** triggers a build of all configured targets and publishes a **GitHub Release** with the firmware files (downloadable from the Releases page).

> **Local builds have much shorter turnaround than waiting on Actions.**

### Gotchas

- **`user.overlay_dir` must be set** (the `qmk config` line above) or `qmk compile` won't see your external keymaps.
- **External Userspace CLI commands still need a copy of `qmk_firmware`** locally — they're not standalone.
- **It's flagged as new/possibly buggy** in the upstream docs ("Tighter integration with the `qmk` command will occur over time").
- The older "GitHub userspace keymap.json + Actions" workflow (`newbs_building_firmware_workflow.md`) still works but is **superseded** by External Userspace.

---

## 8. The "GitHub Userspace" Workflow (legacy JSON + Actions path)

> Older alternative to External Userspace. Kept here because it still functions and you'll see it referenced. Prefer §7 for new setups.

This builds a **Configurator JSON keymap** in a personal repo (`qmk_keymap`) using GitHub Actions, with no local toolchain. Requires Git familiarity.

### Layout

```
qmk_keymap/
├── .github/workflows/build.yml   # the Actions workflow
├── rules.mk                      # e.g. SRC += source.c
├── config.h
├── source.c                      # #include QMK_KEYBOARD_H + user callbacks (process_record_user, etc.)
└── username.json                 # Configurator keymap export (Keymap Name = your GitHub username)
```

### Workflow skeleton (`.github/workflows/build.yml`)

```yml
name: Build QMK firmware
on: [push, workflow_dispatch]

jobs:
  build:
    runs-on: ubuntu-latest
    container: ghcr.io/qmk/qmk_cli
    strategy:
      fail-fast: false
      matrix:
        file:
        - username.json      # one entry per keymap JSON; add more to build multiple
    steps:
    - name: Disable git safe directory checks
      run: git config --global --add safe.directory '*'
    - name: Checkout QMK
      uses: actions/checkout@v3
      with:
        repository: qmk/qmk_firmware
        submodules: recursive
    - name: Checkout userspace
      uses: actions/checkout@v3
      with:
        path: users/${{ github.actor }}
    - name: Build firmware
      run: qmk compile "users/${{ github.actor }}/${{ matrix.file }}"
    - name: Archive firmware
      uses: actions/upload-artifact@v3
      continue-on-error: true
      with:
        name: ${{ matrix.file }}_${{ github.actor }}
        path: |
          *.hex
          *.bin
          *.uf2
```

The build clones your repo into `users/<actor>/` inside the firmware checkout, then compiles the listed JSON(s). Successful artifacts appear under the run's **Artifacts**.

### Constraints

- Keymap files **must stay JSON** — don't convert to `keymap.c` in this flow.
- User callbacks (`process_record_user`, etc.) go in `source.c`.
- The **Keymap Name** in Configurator **must be your exact GitHub username** — otherwise the build can't find your files.
- Indentation in `build.yml` is load-bearing; wrong spacing = workflow syntax errors.
- Every change needs a `git commit` + `push` to trigger a build.

### Gotchas

- This predates External Userspace (§7); the External Userspace repo + `qmk userspace-*` commands are the modern equivalent.
- Wrong GitHub username in the Configurator export = silent build failure (files not found).

---

## 9. The QMK Configurator Path

[QMK Configurator](https://config.qmk.fm) is a web GUI that generates `.hex`/`.bin` (and exports a `keymap.json`). Best in **Chrome or Firefox**.

### When to use it

- You want a no-code way to design a keymap.
- You want a `keymap.json` to feed into `qmk compile`/`qmk json2c` or the GitHub Actions flows (§7, §8).

### When it can't help

- **Converted controllers** — e.g. an RP2040 on a board designed for a Pro Micro. The Configurator can't produce that firmware; use the CLI [converters](feature_converters#supported-converters) (`-e CONVERT_TO=...`) instead. See `12-hardware-platforms.md`.
- **Not compatible with KLE or kbfirmware exports** — those are different tools. Don't load/import them.

### From Configurator to source

```sh
qmk compile keymap.json         # build directly from the export
qmk json2c -o keymap.c keymap.json   # ...or turn it into editable C
```

> Cross-ref: Configurator internals, QMK API, and VIA/Vial integration are in **`14-configurator-api-via.md`**.

---

## 10. Docker Build

Build in a container for a reproducible, OS-agnostic environment identical to QMK's CI. Requires `docker` or `podman`.

### Build only

```sh
git clone --recurse-submodules https://github.com/qmk/qmk_firmware.git
cd qmk_firmware

util/docker_build.sh <keyboard>:<keymap>            # e.g. planck/rev6:default
util/docker_build.sh <keyboard>                      # omit :keymap -> all keymaps
util/docker_build.sh                                 # interactive: prompts for params
```

### Build + flash

```sh
util/docker_build.sh <keyboard>:<keymap>:target     # e.g. planck/rev6:default:flash
```

> **Mass-storage bootloaders are NOT supported** by the `flash` target — copy the file manually for those.

### Runtime / flashing control

```sh
RUNTIME="podman" util/docker_build.sh <kb>:<km>:flash       # force podman over docker
SKIP_FLASHING_SUPPORT=1 util/docker_build.sh <kb>:<km>      # unprivileged container, no USB passthrough
```

### Gotchas

- **Flash-from-Docker on Windows/macOS needs Docker Machine with USB support** — tedious; use QMK Toolbox instead. Docker for Windows also needs **Hyper-V** (so it fails on Win7/8 and **Win10 Home**).
- **`docker` is preferred over `podman`** by default; override with `RUNTIME`.
- The parameter format matches `make` (`keyboard:keymap:target`), **not** `qmk compile` flags.

---

## 11. Git Workflow for Contributing to QMK

The overarching rule, repeated across four docs: **update your fork's `master` often, commit to it never.** Do all work on branches, PR from branches.

### 11.1 Fork + clone (with submodules!)

On [github.com/qmk/qmk_firmware](https://github.com/qmk/qmk_firmware), click **Fork** → copy the HTTPS URL of *your* fork →:

```sh
git clone --recurse-submodules https://github.com/<you>/qmk_firmware.git
```

(If you forgot `--recurse-submodules`, submodules like `lib/chibios`, `lib/lufa`, `lib/googletest` won't populate. Or just run `qmk setup <you>/qmk_firmware`.)

> Cross-ref for contributing/PR-checklist depth: **`16-userspace-development.md`**.

### 11.2 Keep `master` in sync ("Update Often, Commit Never")

Add the QMK repo as `upstream`, then sync `master` from it:

```sh
git remote add upstream https://github.com/qmk/qmk_firmware.git   # once
git remote -v                                                      # verify origin=your fork, upstream=qmk

git checkout master
git fetch upstream
git pull upstream master
git push origin master
```

### 11.3 Work on a branch ("Making Changes")

```sh
git checkout -b dev_branch                 # or:  git checkout -b dev_branch master
git push --set-upstream origin dev_branch  # (= git push -u ...)
```

Make **many small commits** (easier to bisect/revert):

```sh
git add path/to/file            # or: git add -- f1 f2 ...
git commit -m "descriptive message"
git push                        # publishes to your fork
```

### 11.4 Open a PR

On your fork's GitHub page → **New Pull Request** → review the diff → **Create Pull Request**.

### 11.5 Resolving merge conflicts (rebase onto `upstream/master`)

```sh
git fetch upstream
git rev-list --left-right --count HEAD...upstream/master
#   ^ first number  = commits on your branch since it split
#     second number = commits on upstream/master your branch doesn't have
git rebase upstream/master
```

On conflict, Git marks the file:

```
<<<<<<< HEAD
<upstream/master version>
=======
<your branch version>
>>>>>>> Commit #1
```

Edit to resolve, then:

```sh
git add <conflicted_file>
git rebase --continue        # (or --skip / --abort)
```

### 11.6 Resyncing a dirty `master` (if you committed to it by mistake)

If you committed to `master` and now GitHub says your fork is N commits ahead of `qmk:master`:

```sh
# (optional) back up your dirty master
git branch old_master master

# ensure remotes are right
git remote -v
git remote add upstream https://github.com/qmk/qmk_firmware.git   # if missing
git remote set-url origin https://github.com/<you>/qmk_firmware.git

# reset local master to exactly match upstream
git fetch --recurse-submodules upstream
git reset --recurse-submodules --hard upstream/master

# force-push your fork to match (overrides remote changes)
git push --recurse-submodules=on-demand --force-with-lease
```

> **`--force-with-lease` will erase other users' commits** on that fork — never do this on a shared fork.

### Gotchas

- **Always `--recurse-submodules`** when cloning — QMK depends on `lib/chibios`, `lib/lufa`, etc.
- **`origin` should point at your fork, `upstream` at `qmk/qmk_firmware`** — a common mistake is having `origin` point at QMK and losing push rights.
- **Never commit to `master`** — it makes PRs messy and forces the §11.6 resync dance.
- **`--force-with-lease` is destructive** on shared forks; prefer rebases + normal pushes on feature branches.
- Use **small, descriptive commits** so a broken change is easy to revert.

---

## 12. Tab Completion

For Bash ≥4.2, Zsh, or Fish, enable QMK CLI tab completion (flags, keyboards, files, options).

```sh
# Per-user (add to ~/.bashrc or ~/.profile)
source ~/qmk_firmware/util/qmk_tab_complete.sh

# Zsh users also need, in ~/.zshrc:
autoload -Uz bashcompinit && bashcompinit

# System-wide symlink:
ln -s ~/qmk_firmware/util/qmk_tab_complete.sh /etc/profile.d/qmk_tab_complete.sh
```

If a symlink won't work (e.g. restricted `/etc/profile.d`), copy the file — but re-copy it periodically since the script is updated.

> More in **`15-flashing-debugging.md`** (which also lists tab completion under tooling).

---

## 13. Testing & Debugging (onboarding pointers)

The standalone `newbs_testing_debugging.md` is now a **redirect**: testing → `faq_misc#testing`, debugging → `faq_debug#debugging`. For the agent, the substantive material lives in:

- **`15-flashing-debugging.md`** — flashing (all bootloaders), ISP flashing, Zadig (Windows driver), debugging AVR vs ARM (GDB, `hid_listen`/`qmk console`, `dprint`/`print`/`uprint`), unit testing (`qmk test-c` / `qmk pytest`), VS Code & Eclipse setup, squeezing AVR flash size, tab-complete.
- **`17-faq-gotchas-breaking-changes.md`** — FAQ misc + the canonical debugging FAQ.

### Quick debugging knobs (set via `config.h`; see §6.4 for full rules)

| Define | Effect |
|---|---|
| `CONSOLE_ENABLE = yes` (rules.mk/info.json) | Enable console output |
| `#define NO_DEBUG` | Disable `dprint` |
| `#define NO_PRINT` | Disable `print`/`xprintf` **and** `uprint` |
| `#define USER_PRINT` | Disable `print`/`xprintf` but **keep** `uprint` |

Read the console with `qmk console` (§5.1) or `hid_listen`.

### Gotchas

- **`uprint` is keymap-only** — never in core/framework code.
- **`CONSOLE_ENABLE` with all printing on** frequently overflows AVR flash — trim with `NO_DEBUG`/`NO_PRINT`/`USER_PRINT`.
- **`qmk console` needs `CONSOLE_ENABLE=yes`** at build time or you'll see nothing.

---

## 14. Cross-Reference Index

| This ref covers | For depth, see |
|---|---|
| Build/flash/CLI/install | `02` (this file) |
| `info.json` schema, `config.h`/`rules.mk` options, EEPROM, debounce, layout macros | **`03-config-and-info-json.md`** |
| Keymap authoring, layers, full keycode tables, mod_tap/tap_hold/one_shot | **`04-keymaps-and-keycodes.md`** |
| All bootloaders, ISP flashing, Zadig, AVR/ARM debugging, unit tests, IDE setup, size optimization, tab-complete | **`15-flashing-debugging.md`** |
| Userspace feature (shared C), CLI/API development, coding conventions, contributing, PR checklist, glossary, deprecation | **`16-userspace-development.md`** |
| Configurator internals, QMK API, VIA/Vial | **`14-configurator-api-via.md`** |
| Microcontrollers, ARM platform guides, hand-wire, custom matrix, porting, converters | **`12-hardware-platforms.md`** |
| FAQs, breaking changes, ChibiOS upgrades | **`17-faq-gotchas-breaking-changes.md`** |

---

## 15. Master Gotchas (build/install path)

- **Never commit to fork `master`; update it often; work on branches.** The #1 repeated QMK advice.
- **Distro `qmk` packages are stale** — always use the curl installer or QMK MSYS.
- **`qmk doctor`** detects and often fixes missing toolchain/udev/bootloader problems — run it first when a build or flash is broken.
- **The `-kb`/`-km` value is a path** under `keyboards/` (e.g. `clueboard/66/rev4`), not a bare name.
- **Build artifacts land in the repo root** as `<keyboard>_<keymap>.{hex|bin|uf2}`; a copy also stays in `.build/`.
- **Mass-storage bootloaders** (some STM32, RP2040 UF2) are **not** supported by `qmk flash`'s `:flash` target — copy the file manually.
- **HalfKay / QMK HID / USBaspLoader** (and ISP flashers USBasp/USBtinyISP) need `-m <mcu>` on `qmk flash`.
- **`CONSOLE_ENABLE` with full printing** is the classic AVR "firmware too big" culprit — trim with `NO_DEBUG`/`NO_PRINT`/`USER_PRINT`. `uprint` is keymap-only.
- **ARM splits need `SPLIT_TRANSPORT = custom`** — the stock transport is AVR-only.
- **External Userspace needs `user.overlay_dir` set** and a local `qmk_firmware` to run its CLI commands; it's still flagged "new/possibly buggy".
- **Configurator can't build converted-controller boards** (e.g. RP2040 on a Pro Micro PCB) — use CLI converters.
- **Configurator ≠ KLE ≠ kbfirmware** — don't import KLE/kbfirmware files into it.
- **WSL**: keep the repo inside the Linux FS (not `/mnt/c`); the Windows-FS path is extremely slow.
- **Docker flash on Windows/macOS** needs Docker Machine + USB support (tedious) — use QMK Toolbox instead; Docker on Windows also needs Hyper-V (fails on Win10 Home).
- **`git clone --recurse-submodules`** is mandatory — QMK depends on `lib/chibios`, `lib/lufa`, `lib/googletest`, etc.
- **`origin` = your fork, `upstream` = `qmk/qmk_firmware`** — a flipped config loses push rights.
- **`--force-with-lease` is destructive** on shared forks; it erases others' commits.
- **`c2json` is fragile** (C parsing is hard) — try `--no-cpp` if it fails.
- **`generate-compilation-database` is deprecated** — use `qmk compile --compiledb`.
- **In the GitHub-userspace JSON workflow, the Configurator Keymap Name must equal your exact GitHub username**, or the build silently can't find your files.
- **Ubuntu/Debian `qmk: command not found`** after install — `$HOME/.local/bin` isn't on `PATH` (a known bash bug); add it to `~/.bashrc`.
