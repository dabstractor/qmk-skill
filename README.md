# qmk-skill

An [Agent Skill](https://agentskills.io/specification) that turns any Agent-Skills-compatible coding agent into a QMK Firmware expert. It is a compressed, navigable synthesis of the **entire QMK documentation set** (~207 Markdown files) plus a verified VIA/Vial layer and an aggregated gotchas/dead-API index, structured so the agent loads only the area it needs.

## What it can help with

- Writing / refactoring `keymap.c`; choosing and combining keycodes
- Layers, mod-tap, one-shot keys, tap-hold, combos, tap-dance, macros, autocorrect, caps-word, repeat-key
- Configuring the keyboard the modern (data-driven) way: `info.json` / `rules.mk` / `config.h`
- Defining a key matrix, hand-wiring, direct-pin, custom matrix scanning
- RGB / RGB Matrix / LED Matrix / backlight / indicators (and why you pick only one)
- OLED, Quantum Painter, HD44780, ST7565, encoders
- Audio, MIDI, sequencer, haptic
- Mouse keys, pointing device, joystick, digitizer, programmable button
- Split keyboards, wireless/BT, OS detection, raw HID
- Choosing a microcontroller / platform / bootloader (AVR, STM32, RP2040, …), converters
- Low-level drivers (I²C, SPI, UART, serial, GPIO, ADC, EEPROM/flash, WS2812, all IS31FL*/SNLED27351/AW20216S LED drivers)
- Building & flashing, ISP flashing, Zadig, debugging (hid_listen, SWD/GDB), unit tests, size optimization
- QMK Configurator, the QMK compile API, `keymap.json` round-trips
- Hooking a board up to **VIA** or **Vial**
- Userspace, community modules, custom C, contributing upstream
- Designing advanced / unique keymap behavior
- Navigating breaking changes and avoiding removed/renamed APIs

## Structure

```
qmk-skill/
├── SKILL.md            # navigation hub, triage table, playbooks, gotchas index
├── references/         # focused, independently-loadable references (00–19)
│   ├── 00-cross-cutting-gotchas.md   # READ FIRST — traps, conflicts, dead APIs
│   ├── 01-architecture.md            …
│   ├── 17-faq-gotchas-breaking-changes.md
│   ├── 18-community-modules.md
│   ├── 19-keycodes-changelog.md      # keycode-migration INDEX (per-version files below)
│   └── keycodes-changelog/           # one file per release; load only your migration window
├── scripts/
│   ├── gen_keycode_catalog.py        # regenerate 19 + keycodes-changelog/ from a qmk_firmware checkout
│   └── keycodes_migration.py         # dump every release changeset in (from, to] as one document
└── assets/
    ├── keymap-template.c          # idiomatic starter keymap
    └── info-json-template.json    # starter keyboard definition (valid JSON)
```

The full file inventory and when-to-read guidance live in `SKILL.md`.

## Installation

This is a standard Agent Skill (a directory with `SKILL.md`), so any compatible client discovers it from the standard skill paths. Clone it, then link (or copy) it in:

```bash
# User-global (available everywhere):
ln -s "$PWD/qmk-skill" ~/.agents/skills/qmk-skill

# …or project-local (available in one repo):
ln -s "$PWD/qmk-skill" /path/to/repo/.agents/skills/qmk-skill
```

(Your client may also offer its own install command; either way it just needs the skill directory on a discovery path.) Once discovered, the skill loads automatically on QMK-related requests via its `description`, or you can invoke it explicitly by name.

## How it was built

The references were synthesized by reading every `docs/**/*.md` in the QMK firmware repo and condensing each topic into a dense, scannable reference with: what it does, how to enable it, its keycodes, configuration knobs (with defaults/units), the C API/callbacks, behavior & ordering, examples, and gotchas. The cross-cutting gotchas index (`references/00`) aggregates the traps that span multiple features so the agent never steps on them.

> Note: QMK's own docs do **not** cover VIA/Vial (separate projects). The VIA section of `references/14-configurator-api-via.md` is verified against QMK's own tree (`quantum/via.{c,h}`, `builddefs/common_features.mk`, the `data/mappings` schema), and the **Vial build mechanics are verified from the `vial-kb/vial-qmk` fork** (`builddefs/build_vial.mk`, `quantum/vial.c`, real `keymaps/vial/` trees). Only the byte-level protocol framing remains best-effort; verify that against the VIA/Vial sources for host-tool work.
