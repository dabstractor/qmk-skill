# 15 — Flashing, Debugging, Testing & Size Optimization

> Coverage: how firmware leaves a build and lands on a chip, how to watch what the running firmware does, how to test it on the host, how to single-step it under a hardware debugger, and how to shrink it when AVR flash runs out.
>
> **Cross-refs:** the build that produces these files is in `02-getting-started-build.md` (§4 `qmk compile`/`qmk flash`). The `BOOTLOADER` / `firmware_format` / `bootloader` info.json keys and the MCU/ARCH/fuse defaults are documented in `03-config-and-info-json.md` (§3 `rules.mk`, §4 info.json schema). Per-MCU platform specifics (ChibiOS/ARM, RP2040, hand-wire, converters) live in `12-hardware-platforms.md`. Feature cost/disabling knobs (`CONSOLE_ENABLE`, `LTO_ENABLE`, `MAGIC_ENABLE`, RGB effects) are duplicated in `03` and §5 below.

---

## 1. Flashing Overview

Almost every QMK keyboard reflashes over USB through a small resident program called a **bootloader**, which lives in a protected region of flash. The bootloader cannot overwrite itself, so changing or restoring the bootloader requires a separate **ISP flash** step (see §4). Most STM32/APM32/GD32V/RP2040 MCUs ship with a **factory bootloader in ROM** that cannot be modified or deleted; only a few (notably STM32F103, and bare AVRs) need a bootloader flashed first.

The general sequence for any bootloader is:

1. **Enter bootloader mode** (see §2 for the many ways).
2. **Wait for the OS to enumerate the bootloader device.**
3. **Flash the appropriate file format** (`.hex` for AVR, `.bin` for STM32/APM32/Kiibohd/WB32, `.uf2` for RP2040/tinyuf2/uf2boot).
4. **Reset into application mode** (often automatic).

### 1.1 The `BOOTLOADER` key (data-driven preferred)

The bootloader is declared in `info.json`, with a `rules.mk` fallback:

```jsonc
// info.json (preferred)
{
  "bootloader": "atmel-dfu",            // required if development_board not set
  "bootloader_instructions": "Hold Esc while plugging in", // human hint
  "build": { "firmware_format": "hex" } // bin | hex | uf2
}
```

```make
# rules.mk (legacy equivalent)
BOOTLOADER = atmel-dfu
```

`bootloader` is **required** for any keyboard that doesn't set `development_board`. QMK uses this single value to (a) compute whether a built `.hex` fits the AVR's flash, (b) pick the right flasher tool and make target, and (c) report the file format. If `bootloader` is unset or unsupported you'll see:

```
WARNING: This board's bootloader is not specified or is not supported by the ":flash" target at this time.
```

### 1.2 File formats by family

| Family | Output file | Why |
|---|---|---|
| AVR (atmel-dfu, lufa/qmk-dfu, qmk-hid, halfkay, caterina, bootloadhid, usbasploader) | `.hex` (Intel HEX) | AVR toolchain emits HEX; bootloader row sizes vary |
| STM32 / APM32 / AT32 / GD32V (dfu) | `.bin` | DFU on these flashes raw binary at a fixed address |
| Kiibohd DFU | `.bin` | NXP Kinetis, dfu-util |
| WB32 DFU | `.bin` | WestBridge MCUs (GMMK/Akko/MonsGeek/Inland) |
| STM32duino | `.bin` | dfu-util to alt interface 2 |
| RP2040 / tinyuf2 / uf2boot | `.uf2` | USB-Mass-Storage drag-and-drop |

You rarely pick this manually — `build.firmware_format` (or `BOOTLOADER`) selects it. See `03-config-and-info-json.md` §4 for the full info.json `build` block.

### 1.3 `qmk flash` and the `:flash` make target

The modern entry point:

```sh
qmk flash -kb <keyboard> -km <keymap>
# or, in a configured keymap dir:
qmk flash
```

`qmk flash` is `qmk compile` plus an upload step. It reads `bootloader` and invokes the correct flasher; you do **not** need to know which tool your board uses. To override the auto-detected bootloader:

```sh
qmk flash -kb <kb> -km <km> -bl dfu        # explicit bootloader
```

The raw make equivalent is `:<bootloader>` (the per-bootloader make targets are listed in §3). The generic `:flash` target picks the right one from `BOOTLOADER`; if `BOOTLOADER` is unknown it errors with the warning above.

If a device isn't detected, run `qmk doctor` for suggestions (missing `dfu-util`, `udev` rules, etc.).

> AVR-only note: QMK also auto-checks that the `.hex` fits the bootloader-reserved flash region and prints `bytes used / max` (the max shrinks as the bootloader region grows, e.g. 4 KB on ATmega32U4 DFU).

### 1.4 OS-specific flashing notes

| OS | Notes |
|---|---|
| **Windows** | DFU-class bootloaders (atmel-dfu, stm32-dfu, kiibohd, apm32-dfu, at32-dfu, gd32v-dfu) need a **libusb/WinUSB driver** assigned via **Zadig** — see §5. Caterina (Pro Micro) shows as a COM port (`usbser`, built-in — no Zadig). HalfKay/bootloadHID/qmk-hid show as generic HID (`HidUsb`, built-in — no Zadig). WB32 needs the `wb32-dfu-updater_cli` (bundled with QMK MSYS and Glorious Toolbox). Use **MSYS2 / QMK MSYS**, not `cmd.exe`, for any flash/ISP work. |
| **Linux** | Needs `udev` rules for the device to be user-accessible (else run with `sudo`). QMK installs rules under `/etc/udev/rules.d/`; re-plug after installing. `dfu-util`, `avrdude`, `st-flash`, `openocd` come from your distro. |
| **macOS** | Driver-free for almost everything. Use Homebrew for `dfu-util`, `avrdude`, `stlink`, `openocd`. |

---

## 2. Entering Bootloader / Reset Mode

There is no universal key — try these in order (from `newbs_flashing`). Methods depend on what firmware is currently running:

| Method | How | When it works |
|---|---|---|
| **`QK_BOOT` keycode** | Press a key bound to `QK_BOOTLOADER` (alias `QK_BOOT`, formerly `RESET`) — often on a layer | Firmware running & responsive |
| **Magic + Pause** | Hold both Shifts, tap `Pause` | Command/Magic enabled (default) |
| **Magic + B** | Hold both Shifts, tap `B` | Command enabled (default Left Shift+Right Shift) |
| **Bootmagic Space+B** | Unplug, hold **Space+B**, plug in, release after ~1s | Bootmagic enabled (default). *Note: the zadig doc phrases this as "Space+`B`"; `newbs_flashing` and Bootmagic docs use Space+B.* |
| **Bootmagic lite** | Unplug, hold the top-left key (default Esc, may be remapped to e.g. LCtrl), plug in | Bootmagic lite enabled |
| **Physical `RESET` button** | Press the tactile button on the PCB underside | Board has one |
| **`RESET`+`GND` header** | Short the `RESET`/`GND` pins while plugging in | PCB exposes the header |
| **Short RST→GND** | Briefly bridge RST to GND | Bare MCU / no button |

**MCU-specific physical entry:**

- **STM32 DFU** — if a reset circuit is present, tap `RESET`; otherwise bridge **`BOOT0`→VCC**, pulse `RESET` low, then release `BOOT0`. Some boards have a BOOT0 toggle switch. `QK_BOOT` may not work on STM32F042.
- **AT32 DFU / APM32 DFU / STM32duino** — same `BOOT0`/`RESET` dance.
- **USBasploader** — hold `BOOT`, tap `RESET`; or hold `BOOT` while plugging in.
- **bootloadHID** (PS2AVRGB) — hold the "salt key" while plugging in (often MCU pins A0+B0; see board README).
- **RP2040** — hold **`BOOTSEL`** while plugging in, **or** double-tap `RESET` (the latter only works if the running firmware defined `RP2040_BOOTLOADER_DOUBLE_TAP_RESET`).
- **tinyuf2 / uf2boot** — double-tap the `nRST`/`RESET` button.

**Time-limited bootloaders:** Caterina and HalfKay typically expose the bootloader for only **~7 seconds**; some Caterina variants (SparkFun) require two `RESET` taps within **750 ms** to stay longer. Plan your flash command accordingly.

### 2.1 `QK_BOOT` keycode

| Name | Alias | Description |
|---|---|---|
| `QK_BOOTLOADER` | `QK_BOOT`, legacy `RESET` | Jump to the bootloader for flashing |

In code you can also call `reset_keyboard()` (see `ref_functions`). On ChibiOS, the early-init path can be configured to honor a `QK_BOOT` press at boot.

---

## 3. Bootloader Catalog (flash methods per bootloader/MCU)

Each subsection gives: the `BOOTLOADER` value, compatible flashers (recommended CLI first), the make target, and entry-specific gotchas. **Caterina, HalfKay, bootloadHID need no driver on Windows**; everything DFU-class does (§5).

### 3.1 `atmel-dfu` — Atmel / LUFA DFU (AVR)

USB-AVR default bootloader (ATmega16U4/32U4, AT90USB64/128). LUFA's DFU or QMK's fork are alternatives (`lufa-dfu`, `qmk-dfu`). USB ID `03EB:2FFx`.

```make
BOOTLOADER = atmel-dfu     # or lufa-dfu, qmk-dfu
```

- **CLI:** `dfu-programmer` / make target `:dfu`
  ```sh
  dfu-programmer <mcu> erase --force
  dfu-programmer <mcu> flash --force <file.hex>
  dfu-programmer <mcu> reset
  ```
- **GUI:** QMK Toolbox.
- **Make targets:** `:dfu` (polls every 5 s for a DFU device); `:dfu-split-left` / `:dfu-split-right` (also write handedness to EEPROM — use for Elite-C splits).

#### `qmk-dfu` extras (LUFA DFU fork)

QMK's DFU fork adds a matrix scan to exit the bootloader and an LED/speaker tick. Configure in `config.h` (the info.json equivalent is the `qmk_lufa_bootloader` block, see `03`):

```c
#define QMK_ESC_OUTPUT F1   // COL pin if COL2ROW
#define QMK_ESC_INPUT  D5   // ROW pin if COL2ROW
// optional:
//#define QMK_LED E6
//#define QMK_SPEAKER C6
```

- Build the bootloader alone with `make <kb>:<km>:bootloader`.
- Build a combined production `.hex` with `make <kb>:<km>:production`.
- Manufacturer/product strings are auto-pulled from `config.h` with " Bootloader" appended.

### 3.2 `caterina` — Arduino-style (AVR109, virtual serial)

Pro Micro, Arduino Leonardo/Micro, Pololu A-Star, Adafruit Feather/ItsyBitsy, LilyPadUSB. Uses AVR109 over a virtual COM port. **No Zadig needed** (Windows `usbser` is built in). Many VID/PID variants (see §5 table).

```make
BOOTLOADER = caterina
```

- **CLI:** `avrdude` (programmer `avr109`) / make target `:avrdude`
  ```sh
  avrdude -p <mcu> -c avr109 -P <serialport> -U flash:w:<file.hex>:i
  ```
- **GUI:** QMK Toolbox, AVRDUDESS.
- **Make targets:** `:avrdude` (polls 5 s for a new COM port); `:avrdude-loop` (reflashes repeatedly — bulk flashing, Ctrl+C to stop); `:avrdude-split-left` / `:avrdude-split-right` (Pro Micro splits).

### 3.3 `halfkay` — PJRC Teensy (HID)

Ships on all Teensys (e.g. Teensy 2.0, ATmega32U4). Closed-source; **once overwritten (e.g. by ISP-flashing another bootloader) it cannot be restored.** No driver needed (generic HID).

```make
BOOTLOADER = halfkay
```

- **CLI:** `teensy_loader_cli` / make target `:teensy`
  ```sh
  teensy_loader_cli -v -mmcu=<mcu> <file.hex>
  ```
- **GUI:** QMK Toolbox, Teensy Loader.
- 7-second bootloader window.

### 3.4 `stm32-dfu` / `apm32-dfu` — STM32 / APM32 factory DFU

All USB-capable STM32/APM32 except STM32F103 (see §3.7) and a few others have an undeletable ROM DFU bootloader. STM32 USB ID `0483:DF11`; APM32 `314B:0106`.

```make
BOOTLOADER = stm32-dfu      # or apm32-dfu
```

- **CLI:** `dfu-util` / make target `:dfu-util`
  ```sh
  # STM32
  dfu-util -a 0 -d 0483:DF11 -s 0x8000000:leave -D <file.bin>
  ```
- **GUI:** QMK Toolbox.
- **Make targets:** `:dfu-util`; `:dfu-util-split-left` / `:dfu-util-split-right` (Proton-C splits); `:st-link-cli` (flash via ST-Link CLI — needs dongle); `:st-flash` (flash via `st-flash` from [stlink tools](https://github.com/stlink-org/stlink)).
- Entry via `BOOT0`+`RESET`; `QK_BOOT` may not work on STM32F042.

### 3.5 `kiibohd` — Input Club (NXP Kinetis, dfu-util)

Input Club keyboards (Whitefox, Kira, etc.). Rarely set at keymap/user level.

```make
BOOTLOADER = kiibohd
```

- **CLI:** `dfu-util -a 0 -d 1C11:B007 -D <file.bin>` (USB ID `1C11:B007`).
- **GUI:** QMK Toolbox.

### 3.6 `bootloadhid` / `qmk-hid` — HID bootloaders

`bootloadhid`: PS2AVRGB boards (ATmega32A), no driver needed (HID). USB ID `16C0:05DF`. **Not recommended for new designs.**

```make
BOOTLOADER = bootloadhid
```

- **CLI:** `bootloadHID -r <file.hex>` / make target `:bootloadhid`. GUI: QMK Toolbox / HIDBootFlash.
- Entry: tap `QK_BOOT`, or hold the "salt key" while plugging in.

`qmk-hid`: QMK's LUFA HID fork (USB ID `03EB:2067`), behaves like HalfKay with the same matrix-scan/LED/speaker extras as `qmk-dfu` (same `QMK_ESC_*` / `QMK_LED` / `QMK_SPEAKER` config.h defines).

```make
BOOTLOADER = qmk-hid
```

- **CLI:** `hid_bootloader_cli` / make target `:qmk-hid` (polls 5 s). GUI: QMK Toolbox.

### 3.7 `stm32duino` — STM32F103 (Bluepill)

STM32F103 has no USB DFU in ROM, so the community [STM32duino bootloader](https://github.com/rogerclarkmelbourne/STM32duino-bootloader) (a Maple descendant, dfu-util-compatible) is flashed via ST-Link first — see §4.4. USB ID `1EAF:0003`.

```make
BOOTLOADER = stm32duino
```

- **CLI:** `dfu-util -a 2 -d 1EAF:0003 -D <file.bin>` (note **alt 2**, no `:leave`). GUI: QMK Toolbox.

### 3.8 `at32-dfu` / `gd32v-dfu` — AT32 / GD32V

AT32 (undeletable ROM DFU, USB ID `2E3C:DF11`); GD32V RISC-V (`28E9:0189`).

```make
BOOTLOADER = at32-dfu      # GD32V: BOOTLOADER = gd32v-dfu
```

- **CLI (AT32):** `dfu-util -a 0 -d 2E3C:DF11 -s 0x8000000:leave -D <file.bin>`.
- **Make targets (AT32):** `:dfu-util`; `:dfu-util-split-left/right`.

### 3.9 `wb32-dfu` — WestBridge (GMMK / Akko / MonsGeek / Inland)

```make
BOOTLOADER = wb32-dfu      # info.json key
```

- **CLI:** `wb32-dfu-updater_cli -t -s 0x8000000 -D <file.bin>` / `:flash`. On non-Windows you may need to build the [CLI from source](https://github.com/WestberryTech/wb32-dfu-updater).
- **GUI:** Glorious's QMK Toolbox build (the standard Toolbox does **not** support WB32).

### 3.10 `rp2040` / `tinyuf2` / `uf2boot` — UF2 mass-storage

These expose the board as a USB drive; you copy a `.uf2` to it. **No flasher tool, no driver, no Toolbox needed** (RP2040 specifically doesn't need QMK Toolbox).

```make
BOOTLOADER = rp2040        # tinyuf2 (F303/F401/F411), uf2boot (F103)
```

- **Any file copy** (Finder/Explorer), or `qmk flash ...` (CLI handles the copy).
- Entry: RP2040 — `QK_BOOT`, or hold `BOOTSEL` while plugging in, or double-tap `RESET` (needs `RP2040_BOOTLOADER_DOUBLE_TAP_RESET`). tinyuf2/uf2boot — double-tap `nRST`.
- **Make targets:** `:uf2-split-left` / `:uf2-split-right` (generate side-specific firmware + handedness EEPROM).

### 3.11 `usbasploader` — V-USB (ATmega32A, ATmega328P)

For non-USB AVRs running V-USB; emulates a USBasp programmer. USB ID `16C0:05DC`.

```make
BOOTLOADER = usbasploader
```

- **CLI:** `avrdude -p <mcu> -c usbasp -U flash:w:<file.hex>:i` / make target `:usbasp`. GUI: QMK Toolbox / AVRDUDESS.
- Entry: hold `BOOT`, tap `RESET` (or hold `BOOT` while plugging in).

---

## 4. ISP Flashing (writing a bootloader onto a bare AVR)

ISP (In-System Programming) writes through the SPI pins (`RESET`/`SCLK`/`MOSI`/`MISO`) and can reach the whole flash — including the bootloader region and **fuse bytes**. Use it to: restore a corrupted bootloader, switch bootloaders (e.g. Caterina → DFU on a Pro Micro), or flash a bare chip. **Most STM32 already have a USB bootloader in ROM and don't need ISP** — STM32F103 is the exception (§4.4).

### 4.1 ISP programmers

| Programmer | `avrdude -c` | `-P` | Limitation |
|---|---|---|---|
| Pro Micro (loaded with [ISP firmware](https://github.com/qmk/qmk_firmware/blob/master/util/pro_micro_ISP_B6_10.hex)) | `avrisp` | serial | — |
| Arduino Uno / Micro ([ArduinoISP sketch](https://docs.arduino.cc/built-in-examples/arduino-isp/ArduinoISP)) | `stk500v1` | serial | — |
| Teensy 2.0 ([ISP firmware](https://github.com/qmk/qmk_firmware/blob/master/util/teensy_2.0_ISP_B6_10.hex)) | `avrisp` | serial | — |
| SparkFun PocketAVR / Adafruit USBtinyISP | `usbtiny` | `usb` | **No support for >64 KiB flash** (e.g. AT90USB128) — verification errors |
| [USBasp](https://www.fischl.de/usbasp/) | `usbasp` | `usb` | — |
| [Bus Pirate](https://www.adafruit.com/product/237) | `buspirate` | serial | Use the **10-pin** header (opposite USB), not the 5-pin ICSP (that's for the BP's own PIC) |

> **Wiring gotcha (critical):** connect the programmer's designated RESET-driving pin (e.g. Pro Micro pin `10`/`B6`, Uno pin `10`/`B2`, Teensy `B0`) to the **target's `RESET`**. **Do NOT** wire programmer-RESET to target-RESET. Like-to-like wiring for `VCC`, `GND`, `SCLK`, `MOSI`, `MISO`. If the target lacks an ISP header, temporarily solder to switch pins or directly to the MCU.

### 4.2 The `avrdude` ISP command

```sh
avrdude -c <programmer> -P <port> -p <mcu> -U flash:w:<bootloader.hex>:i
```

- `<programmer>`: from the table above (e.g. `avrisp`, `usbasp`).
- `<port>`: serial port or `usb`. Windows `COMx`; Linux `/dev/ttyACMx`; macOS `/dev/tty.usbmodemXXXXXX`. For USB-class programmers you can often omit `-P`.
- `<mcu>`: lowercase AVR name (e.g. `atmega32u4`).
- `<filename>`: the bootloader `.hex` (see §4.3).

QMK Toolbox can do the ISP write but **cannot set AVR fuses** — use `avrdude` directly for that.

### 4.3 AVR fuses (lfuse / hfuse / efuse)

Fuses set clock source/speed, JTAG enable, bootloader size, etc. **Wrong clock bits can brick the MCU** (recoverable only via high-voltage programming). [Engbedded fuse calculator](https://www.engbedded.com/conffuse/). To set fuses, append to the `avrdude` command:

```sh
-U lfuse:w:0xXX:m -U hfuse:w:0xXX:m -U efuse:w:0xXX:m
```

> **`efuse` readback warning:** `avrdude` may warn the read-back extended fuse differs. If the **second** hex digit matches, ignore it — the top nibble doesn't physically exist on many AVRs and reads back as garbage.

#### Atmel DFU defaults

| MCU | lfuse | hfuse | efuse | USB ID |
|---|---|---|---|---|
| ATmega16U4 | `0x5E` | `0x99` / `0xD9` (JTAG disabled) | `0xF3` | `03EB:2FF3` |
| **ATmega32U4** | `0x5E` | `0x99` / `0xD9` (JTAG disabled) | `0xF3` | `03EB:2FF4` |
| AT90USB64 | `0x5E` | `0x9B` / `0xDB` (JTAG disabled) | `0xF3` | `03EB:2FF9` |
| AT90USB128 | `0x5E` | `0x99` / `0xD9` (JTAG disabled) | `0xF3` | `03EB:2FFB` |

> AT90USB64/128 bootloaders are [slightly modified](https://github.com/qmk/qmk_firmware/pull/14064) to enumerate on Windows 8+. The two hfuse values differ by the JTAG-disable bit.

#### Caterina defaults (ATmega32U4 only; many vendor variants)

| Board | lfuse | hfuse | efuse | USB ID |
|---|---|---|---|---|
| SparkFun Pro Micro 3V3/8MHz | `0xFF` | `0xD8` | `0xFE` | `1B4F:9203` |
| SparkFun Pro Micro 5V/16MHz | `0xFF` | `0xD8` | `0xFB` | `1B4F:9205` |
| SparkFun LilyPadUSB (some clones) | `0xFF` | `0xD8` | `0xFE` | `1B4F:9207` |
| Pololu A-Star 32U4 | `0xFF` | `0xD0` | `0xF8` | `1FFB:0101` |
| Adafruit Feather 32U4 | `0xFF` | `0xD8` | `0xFB` | `239A:000C` |
| Adafruit ItsyBitsy 32U4 3V3/8MHz | `0xFF` | `0xD8` | `0xFB` | `239A:000D` |
| Adafruit ItsyBitsy 32U4 5V/16MHz | `0xFF` | `0xD8` | `0xFB` | `239A:000E` |
| Arduino Leonardo | `0xFF` | `0xD8` | `0xFB` | `2341:0036` |
| Arduino Micro | `0xFF` | `0xD8` | `0xFB` | `2341:0037` |

> Caterina SparkFun variants need `RESET` grounded twice quickly to stay in bootloader >750 ms. Files marked `*` in the upstream table combine an Arduino sketch that also appears as a serial port — that is **not** the bootloader device.

#### BootloadHID (PS2AVRGB, ATmega32A)

| MCU | lfuse | hfuse | USB ID |
|---|---|---|---|
| ATmega32A | `0x0F` | `0xD0` | `16C0:05DF` |

#### USBaspLoader (ATmega32A, ATmega328P)

| MCU | lfuse | hfuse | efuse | USB ID |
|---|---|---|---|---|
| ATmega32A | `0x1F` | `0xC0` | n/a | `16C0:05DC` |
| ATmega328P | `0xD7` | `0xD0` | `0x04` | `16C0:05DC` |

No precompiled `.hex` — clone [Coseyfannitutti's fork](https://github.com/coseyfannitutti/USBaspLoader) (correct branch), `cd firmware && make` → `main.hex`. Some boards ship a specialized build (linked in their README).

### 4.4 Production / combined firmware

For mass production, concatenate QMK + bootloader into one Intel-HEX file (the format allows this):

1. Open both `.hex` files in a text editor.
2. Delete the last line of the QMK firmware (`:00000001FF`, the EOF marker).
3. Paste the bootloader `.hex` on a new line, no blank line between.
4. Save as `<kb>_<km>_production.hex`, then ISP-flash it (one step instead of two).

The QMK `:production` make target does this for you for qmk-dfu/qmk-hid.

### 4.5 Flashing the STM32duino bootloader onto STM32F103 (Bluepill)

Needs an ST-Link V2 dongle. Software: `brew install stlink openocd` (macOS) / `pacman -S mingw-w64-x86_64-stlink mingw-w64-x86_64-openocd` (MSYS2) / distro `stlink`+`openocd`. Optionally update ST-Link firmware with `STSW-LINK007`. Download [`generic_boot20_pc13.bin`](https://github.com/rogerclarkmelbourne/STM32duino-bootloader/blob/master/bootloader_only_binaries/generic_boot20_pc13.bin).

Wiring (Bluepill both jumpers to 0):

| ST-Link | Bluepill |
|---|---|
| `GND` (6) | `GND` |
| `SWCLK` (2) | `DCLK` |
| `SWDIO` (4) | `DIO` |
| `3.3V` (8) | `3.3` |

Probe with `st-info --probe` — a working connection reports `chipid: 0x0410`; `0x0000` means check wiring / try swapping `SWDIO`↔`SWCLK` (some dongles have wrong pinouts). Then:

```sh
st-flash --reset --format binary write generic_boot20_pc13.bin 0x08000000
```

On `Unknown memory region`, unlock the chip and retry:

```sh
openocd -f interface/stlink.cfg -f target/stm32f1x.cfg \
  -c "init; reset halt; stm32f1x unlock 0; reset halt; exit"
```

Afterward, unplug from ST-Link, connect USB — the board is now dfu-util-flashable.

---

## 5. Windows DFU Driver Install (Zadig)

QMK's normal HID keyboard needs **no** driver. Bootloaders usually do on Windows. **Exceptions needing no Zadig:** Caterina (COM port / `usbser`), HalfKay + bootloadHID + qmk-hid (generic HID / `HidUsb`).

1. Put the keyboard in **bootloader mode** (§2). If you can still type, it's *not* in bootloader mode.
2. Open [Zadig](https://zadig.akeo.ie/). If you set up QMK via MSYS2, the CLI installer already installed the drivers. Otherwise enable **Options → List All Devices** and pick the bootloader device.
3. **If Zadig shows `HidUsb` driver(s) and an orange arrow → STOP.** The keyboard is not in bootloader mode; installing a driver now will break typing.
4. Green arrow → pick the driver from the table below → **Install Driver**.
5. Unplug/replug; restart QMK Toolbox if it doesn't see the new driver.

### 5.1 Known bootloader devices and drivers

| Bootloader | Device name (Zadig) | VID:PID | Driver |
|---|---|---|---|
| `atmel-dfu` | ATmega16u2 DFU | `03EB:2FEF` | WinUSB |
| `atmel-dfu` | ATmega32U2 DFU | `03EB:2FF0` | WinUSB |
| `atmel-dfu` | ATm16U4 DFU V1.0.2 | `03EB:2FF3` | WinUSB |
| `atmel-dfu` | ATm32U4DFU | `03EB:2FF4` | WinUSB |
| `atmel-dfu` | AT90USB64 DFU | `03EB:2FF9` | WinUSB |
| `atmel-dfu` | AT90USB128 DFU | `03EB:2FFB` | WinUSB |
| `qmk-dfu` | (name) Bootloader | as `atmel-dfu` | WinUSB |
| `halfkay` | — | `16C0:0478` | HidUsb |
| `caterina` | Pro Micro 3.3V / 5V / LilyPad / A-Star / Leonardo / Micro / Feather / ItsyBitsy ×2 | `1B4F:9203` `1B4F:9205` `1B4F:9207` `1FFB:0101` `2341:0036/7` `239A:000C/D/E` `2A03:0036/7` | usbser |
| `bootloadhid` | HIDBoot | `16C0:05DF` | HidUsb |
| `usbasploader` | USBasp | `16C0:05DC` | libusbK |
| `apm32-dfu` | APM32 DFU ISP Mode | `314B:0106` | WinUSB |
| `at32-dfu` | AT32 Bootloader DFU | `2E3C:DF11` | WinUSB |
| `stm32-dfu` | STM32 BOOTLOADER | `0483:DF11` | WinUSB |
| `gd32v-dfu` | GD32V BOOTLOADER | `28E9:0189` | WinUSB |
| `kiibohd` | Kiibohd DFU Bootloader | `1C11:B007` | WinUSB |
| `stm32duino` | Maple 003 | `1EAF:0003` | WinUSB |
| `qmk-hid` | (name) Bootloader | `03EB:2067` | HidUsb |

> `usbser` and `HidUsb` are built into Windows and **cannot be assigned via Zadig** — if one of those devices has the wrong driver, fix it through Device Manager.

### 5.2 Recovery (installed driver on the wrong device)

If you replaced the **keyboard's** driver (not the bootloader's), you can't type. In Zadig a healthy keyboard shows `HidUsb` on all interfaces. Fix: Device Manager → **View → Devices by container** → find your keyboard → right-click each entry → **Uninstall device** (tick **Delete the driver software** if shown) → **Action → Scan for hardware changes**. Repeat until Zadig shows `HidUsb` again. A full reboot is sometimes needed.

### 5.3 Uninstalling a bootloader driver

Device Manager → Devices by container → bootloader device (match VID:PID). Details tab → copy `Inf name` (e.g. `oemXX.inf`). Admin `cmd`:

```cmd
pnputil /enum-drivers          :: confirm Published Name matches
pnputil /delete-driver oemXX.inf /uninstall
```

> Be extremely careful — you can uninstall a critical device's driver. When unsure, omit `/uninstall` (just `/delete-driver`) and verify with `/enum-drivers` first. Repeat as needed (multiple drivers can match one device).

---

## 6. Debugging the Running Firmware (console / hid_listen)

Debug output goes over a separate HID **console** endpoint, not the typing keyboard.

### 6.1 Enable the console

```make
# rules.mk
CONSOLE_ENABLE = yes
```

By default the output is sparse. **Turn on debug mode** to expand it — any of:

- Press the **`DB_TOGG`** keycode.
- Use **Command** (`Magic`+`d`).
- Set it at runtime in code:
  ```c
  void keyboard_post_init_user(void) {
      debug_enable   = true;
      debug_matrix   = true;
      //debug_keyboard = true;
      //debug_mouse    = true;
  }
  ```

### 6.2 Viewing tools

| Tool | Notes |
|---|---|
| **QMK Toolbox** | GUI, Windows/macOS (not Linux). Prints console output **per line**. |
| **`qmk console`** | CLI; cross-platform. `qmk console -kb <keyboard>`. |
| **`hid_listen`** ([PJRC](https://www.pjrc.com/teensy/hid_listen.html)) | Stand-alone, prebuilt for Win/Linux/macOS. On Linux may need `sudo` or a `udev` rule. |

**`hid_listen` states:**

```
Waiting for device:.........        # console not ready — is CONSOLE_ENABLE=yes?
Waiting for new device:.....
Listening:                          # success
```

If stuck on "Waiting for device": build with `CONSOLE_ENABLE=yes`; enable debug (`Magic`+`d` or `debug_enable=true`); disconnect other console-capable devices ([tmk #97](https://github.com/tmk/tmk_keyboard/issues/97)); on Linux try `sudo hid_listen` or add a `udev` rule:

```
# /etc/udev/rules.d/70-hid-listen.rules  (lowercase hex VID/PID)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="abcd", ATTRS{idProduct}=="def1", \
  TAG+="uaccess", RUN{builtin}+="uaccess"
```

**Console gotcha:** every string **must end with `\n`** — Toolbox prints line-by-line.

### 6.3 Print API (`print.h`)

```c
#include "print.h"
```

| Function | Purpose |
|---|---|
| `print("str")` | Always-on simple string |
| `uprintf(fmt, ...)` | Always-on formatted (printf-style) |
| `dprint("str")` | String only when debug mode enabled |
| `dprintf(fmt, ...)` | Formatted only when debug mode enabled |

`uprintf`/`dprintf` are the workhorses for custom debug. `uprintf` adds significantly to flash on AVR (see §9).

### 6.4 Matrix-position logging recipe

```c
bool process_record_user(uint16_t keycode, keyrecord_t *record) {
#ifdef CONSOLE_ENABLE
    uprintf("KL: kc: 0x%04X, col: %2u, row: %2u, pressed: %u, "
            "time: %5u, int: %u, count: %u\n",
            keycode, record->event.key.col, record->event.key.row,
            record->event.pressed, record->event.time,
            record->tap.interrupted, record->tap.count);
#endif
    return true;
}
```

Sample:
```
KL: kc: 169, col: 0, row: 0, pressed: 1, time: 15505, int: 0, count: 0
```

### 6.5 Human-readable keycodes (`get_keycode_string`)

Numerical keycodes are hard to read. Enable stringification and use `get_keycode_string`:

```make
# rules.mk
KEYCODE_STRING_ENABLE = yes
```

```c
const char *name = get_keycode_string(keycode);
dprintf("kc: %s\n", name);    // prints "LT(2,KC_D)" instead of "0x4207"
```

> **Gotcha:** `get_keycode_string()` returns a pointer to a **static buffer reused on every call** — use the result immediately, don't store it across calls.

Many common keycodes are recognized (basic, layer-switch, mod-tap, one-shot, tap-dance, Unicode); unknown keycodes fall back to hex. Add your own via:

```c
// keymap.c — adds custom-keycode names
KEYCODE_STRING_NAMES_USER(
    KEYCODE_STRING_NAME(MYMACRO1),
    KEYCODE_STRING_NAME(MYMACRO2),
);
// KEYCODE_STRING_NAMES_KB(...) for keyboard-level names
```

### 6.6 Matrix scan-rate profiling

```c
// config.h
#define DEBUG_MATRIX_SCAN_RATE
```

Periodically prints `> matrix scan frequency: 316` (Hz). Use when diagnosing performance / latency.

---

## 7. ARM Hardware Debugging (SWD)

ARM Cortex-M targets support **SWD** (Single Wire Debug) — `SWCLK` + `SWDIO` + `GND` is enough (RESET optional; SWO adds async printf if you want it). Two main probe families:

| Probe | Transport | Notes |
|---|---|---|
| **ST-Link V2** (dongle) | SWD via OpenOCD/`st-flash` | Cheapest; used in the Bluepill bootloader flash (§4.5) |
| **Black Magic Probe (BMP)** | GDB directly over serial | Acts as a GDB server itself; no OpenOCD needed |

> **Pin conflict gotcha:** make sure `SWCLK`/`SWDIO` aren't also used in your key matrix. If they are, temporarily remap them.

### 7.1 rules.mk for debuggable ARM builds

```makefile
DEBUG_ENABLE = yes      # embed debug info in the .elf
LTO_ENABLE  = no        # LTO breaks clean stepping
OPT         = g         # -Og (debug-friendly optimization)
```

Build and flash normally (`qmk compile`/`qmk flash`). The `.elf` (with symbols) lands in `.build/`.

### 7.2 VS Code + Black Magic Probe (Cortex-Debug)

Install the **Cortex-Debug** extension. Add `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Black Magic Probe (OneKey Proton-C)",
      "type": "cortex-debug",
      "request": "launch",
      "cwd": "${workspaceRoot}",
      "executable": "${workspaceRoot}/.build/handwired_onekey_proton_c_default.elf",
      "servertype": "bmp",
      "BMPGDBSerialPort": "COM4",
      "svdFile": "Q:/svd/STM32F303.svd",
      "device": "STM32F303",
      "v1": false,
      "windows": { "armToolchainPath": "C:\\QMK_MSYS\\mingw64\\bin" }
    }
  ]
}
```

Per-device edits:

- `name` — descriptive (you may have several).
- `cwd` — qmk_firmware root (default above is correct for the repo `.vscode`).
- `executable` — the built `.elf` under `<qmk_firmware>/.build`.
- `BMPGDBSerialPort` — `COMx` (Win) or `/dev/...` (Linux/macOS). BMP exposes **two** serial ports; the debug port is usually the first — try the second if the first fails.
- `svdFile` (optional) — register layout from the [cmsis-svd repo](https://github.com/posborne/cmsis-svd/tree/master/data/STMicro) for peripheral register view.
- `device` — matches the `<name>` tag at the top of the SVD file.
- `armToolchainPath` — Windows only (e.g. `C:\QMK_MSYS\mingw64\bin`). Linux/macOS auto-detects. You may also need to point Cortex-Debug's GDB setting at `C:\QMK_MSYS\mingw64\bin\gdb-multiarch.exe`.

Wiring (BMP): `NRST`, `SWDIO`, `SWCLK`, `GND`. Then Run → Debug view → pick the config → green play.

### 7.3 Eclipse + GNU MCU Eclipse + ST-Link

Install via xPack (`npm`-based): `xpm install --global @xpack-dev-tools/arm-none-eabi-gcc`, `@xpack-dev-tools/openocd` (and `@gnu-mcu-eclipse/windows-build-tools` on Windows); install the GNU MCU Eclipse IDE and Java. Import the QMK repo as **Existing Code as Makefile Project** (ARM Cross GCC toolchain). In Properties → MCU, point ARM Toolchains/OpenOCD/Build Tools at xPack. Install the device pack (Packs perspective → refresh → STMicroelectronics → your series → Install). Set the build target in C/C++ Build → Behavior (replace `all` with e.g. `planck/rev6:default`).

Debug config: **GDB OpenOCD Debugging**, Debugger tab, Config options `-f board/<board>.cfg` (e.g. `stm32f3discovery.cfg`). Some board scripts need editing to drop reset assertion (`reset_config srst_only` → `reset_config none`). Reset the keyboard, hit the bug icon — PC halts at `main`.

### 7.4 OpenOCD direct (flash/unlock via ST-Link)

```sh
openocd -f interface/stlink.cfg -f target/stm32f1x.cfg \
  -c "init; reset halt; stm32f1x unlock 0; reset halt; exit"   # unlock STM32F103
```

OpenOCD + GDB (e.g. `arm-none-eabi-gdb`) gives a CLI debugger; the BMP alternative runs GDB-over-serial directly.

---

## 8. Unit Testing (Google Test / Google Mock, on host)

QMK unit tests run **natively on your host** (compiled with the host compiler), not on a keyboard. Framework: **Google Test** + **Google Mock**. Tests are written in **C++** even though QMK is C — wrap C includes in `extern "C" { ... }`.

### 8.1 The `test:all` / `unit_tests` target

```sh
make test:all                                # all tests
make test:tap_hold_configurations            # substring filter
make test:retro_shift:tap_hold_configurations# colon-narrowed (Retro Shift only)
make test:all DEBUG=1                        # forward debug msgs to stderr
```

Substring filtering works because the make target allows substring matching on test-group names — group names share a common prefix to make this useful. Tests live as host executables in `./build/test` (run them under GDB directly if needed).

> The build target family is referred to as `unit_tests` / `make test:...`. There is no flash step — these run on your development machine.

### 8.2 Adding a test for a feature

Mirror the layout in `quantum/sequencer/tests/`:

1. Add a `tests/` subfolder inside the feature folder.
2. Create `testlist.mk` and `rules.mk` there.
3. `include` them from the **root** `testlist.mk` and `build_test.mk`.
4. Add a test-group name to `testlist.mk` (each group = one executable; this is how you mock different subsystems independently). Use a shared prefix for substring filtering.
5. In `rules.mk` define:
   - `<NAME>_SRC` — source files
   - `<NAME>_DEFS` — extra defines
   - `<NAME>_INC` — extra include dirs
6. Write the test in a `.cpp` in that folder; list it in `_SRC`.

Each test should compile **only the minimum** it needs (mock out the rest). Or add `CONSOLE_ENABLE=yes` to the test's `rules.mk`, or run with `DEBUG=1`, to surface `dprintf` output.

> **No full integration tests yet:** there's no framework to compile the whole firmware + a keymap and emulate input→output. It's planned but not present.

### 8.3 `get_keycode_string` and tracing (shared with §6.5)

`KEYCODE_STRING_ENABLE = yes` (also used at runtime, §6.5) is exercised by tests. The **variable trace** feature is host-testable too:

```sh
make <kb>:<km> VARIABLE_TRACE=1     # number of vars to trace (usually 1)
```

```c
void matrix_init_user(void) {
  ADD_TRACED_VARIABLE("layer", &layer_state, sizeof(layer_state));
}
// ...around suspected mutation sites...
VERIFY_TRACED_VARIABLES();
```

It reports which two `VERIFY_TRACED_VARIABLES` calls bracketed a change (binary-search the callsites). Default max var size is 4 bytes (`MAX_VARIABLE_TRACE_SIZE=x` to raise). Each call stores filename+line in ROM — too many can exhaust flash. **Delete all tracing before submitting a PR.**

---

## 9. Squeezing AVR Flash Size

AVR is severely resource-constrained; QMK is approaching the point where AVR may go legacy. Reductions, biggest first:

### 9.1 `rules.mk` knobs

| Knob | Effect |
|---|---|
| **`LTO_ENABLE = yes`** | Link-Time Optimization — **the biggest single win**; slower link. Also disables the deprecated Action Functions and Action Macros. (info.json `build.lto: true`.) |
| `CONSOLE_ENABLE = no` | Big saving; kills console debug (§6) |
| `COMMAND_ENABLE = no` | Magic/Command keycodes |
| `MOUSEKEY_ENABLE = no` | Mouse keys |
| `EXTRAKEY_ENABLE = no` | Media keys, system volume, etc. |
| `SPACE_CADET_ENABLE = no` | Shift-as-paren features |
| `GRAVE_ESC_ENABLE = no` | Grave/Escape |
| `MAGIC_ENABLE = no` | Magic keycodes (NKRO toggle, GUI/Ctrl-Alt swap) — **one of the largest** |
| `MUSIC_ENABLE = no` (with `#define NO_MUSIC_MODE`) | Audio music mode |
| `AVR_USE_MINIMAL_PRINTF = yes` | ~400 B if you use `sprintf`/`snprintf` — but **not fully featured**: no zero-padding/field-width. If you use `%03d`/`%2d` you still need the standard impl. |

**Biggest consumers to target:** `CONSOLE_ENABLE`, RGB matrix/animations, audio, `MAGIC_ENABLE`. See the RGB effect `#undef` lists in `07-led-rgb-backlight.md`.

### 9.2 `config.h` knobs

```c
#undef LOCKING_SUPPORT_ENABLE      // unless you have a Cherry MX Lock switch
#undef LOCKING_RESYNC_ENABLE
#define NO_ACTION_ONESHOT           // drop one-shot keys
#define NO_ACTION_TAPPING           // drop mod-tap/layer-tap
#define NO_ACTION_LAYER             // drop layers entirely
#define LAYER_STATE_8BIT            // ≤8 layers
#define LAYER_STATE_16BIT           // ≤16 layers
#define NO_MUSIC_MODE               // (pair with MUSIC_ENABLE=no)
```

### 9.3 OLED / WPM sprintf rewrite (~1.5 kB)

`sprintf`/`snprintf` cost ~1.5 kB. Replace:

```c
// OLD (~1.5 kB)
char wpm_str[4] = {0};
sprintf(wpm_str, "WPM: %03d", get_current_wpm());
oled_write(wpm_str, false);
```

with the integer formatter:

```c
// NEW
oled_write_P(PSTR("WPM: "), false);
oled_write(get_u8_str(get_current_wpm(), ' '), false);  // "WPM:   5"
// or '0' for "WPM: 005"
```

### 9.4 RGB animation pruning

Both **RGB Light** and **RGB Matrix** now require explicit per-effect defines; some keyboards enable many by default — `#undef` the ones you don't use in your keymap `config.h`. Full `RGBLIGHT_EFFECT_*` and `ENABLE_RGB_MATRIX_*` lists are in `07-led-rgb-backlight.md`. Disabling animations is one of the larger AVR wins.

### 9.5 When AVR still isn't enough → ARM

Migrate to an ARM Pro-Micro replacement: Bonsai C, STeMCell, Adafruit KB2040, SparkFun Pro Micro RP2040, Blok, Elite-Pi, 0xCB Helios, Liatris, Imera, Michi, Proton C (out of stock). Non-Pro-Micro option: WeAct Blackpill F411 (~$6). See `12-hardware-platforms.md` for converters/platform details.

---

## 10. IDE Integration

### 10.1 VS Code

- Install VS Code + Git for Windows (on Windows). On other OSes nothing special.
- **MSYS2 terminal in VS Code** (Windows): in `settings.json` add a profile pointing at `C:/QMK_MSYS/usr/bin/bash.exe` with `MSYSTEM: MINGW64`, `CHERE_INVOKING: 1`, args `["--login"]`. Lets you Ctrl-click build errors.
- Recommended extensions: **clangd** (IntelliSense), **EditorConfig**, **Git Extension Pack**, GitHub Markdown Preview, Live Share.
- **IntelliSense via `compile_commands.json`:**
  ```sh
  qmk compile -kb <keyboard> -km <keymap> --compiledb
  ```
  then in VS Code: `clangd: Download Language Server` (once), `clangd: Restart Language Server`. clangd now uses the exact includes/defines for your keyboard.
- ARM SWD debugging from VS Code — see §7.2 (Black Magic Probe + Cortex-Debug).

### 10.2 Eclipse

- **For AVR dev:** Eclipse CDT + the **AVR Plugin** (understand AVR C) + **ANSI Escape in Console** (colored makefile output). Java 8+ required. Import as **Makefile Project with Existing Code**, toolchain **AVR-GCC**. Set the default make target to `<kb>:<km>` in Project → Properties → C/C++ Build → Behavior (so Clean/Build are fast). Don't use the `qmk_firmware` dir as the Eclipse workspace — use its parent.
- **For ARM SWD debugging:** GNU MCU Eclipse IDE + xPack-installed ARM toolchain/OpenOCD (+ windows-build-tools on Win) — see §7.3.

### 10.3 QMK Toolbox

GUI flasher/debugger, **Windows + macOS only** (no Linux build). Auto-detects bootloader, supports most flashers above, displays console output per-line. Not needed for RP2040 (UF2) or for any CLI workflow. Glorious's fork adds WB32 support.

---

## 11. Quick-Reference Tables

### 11.1 Bootloader → flash method

| `BOOTLOADER` | MCU family | File | CLI flasher | make target | Win driver |
|---|---|---|---|---|---|
| `atmel-dfu` / `lufa-dfu` / `qmk-dfu` | AVR (16U4/32U4/90USB64/128) | `.hex` | `dfu-programmer` | `:dfu`, `:dfu-split-left/right` | Zadig → WinUSB |
| `caterina` | AVR (Pro Micro etc.) | `.hex` | `avrdude` (avr109) | `:avrdude`, `:avrdude-loop`, `:avrdude-split-left/right` | none (`usbser`) |
| `halfkay` | Teensy (AVR) | `.hex` | `teensy_loader_cli` | `:teensy` | none (`HidUsb`) |
| `usbasploader` | AVR V-USB (32A/328P) | `.hex` | `avrdude` (usbasp) | `:usbasp` | Zadig → libusbK |
| `bootloadhid` | AVR (PS2AVRGB) | `.hex` | `bootloadHID` | `:bootloadhid` | none (`HidUsb`) |
| `qmk-hid` | AVR (LUFA HID fork) | `.hex` | `hid_bootloader_cli` | `:qmk-hid` | none (`HidUsb`) |
| `stm32-dfu` / `apm32-dfu` | STM32/APM32 | `.bin` | `dfu-util` | `:dfu-util`, split, `:st-link-cli`, `:st-flash` | Zadig → WinUSB |
| `stm32duino` | STM32F103 | `.bin` | `dfu-util` (alt 2) | `:dfu-util` | Zadig → WinUSB |
| `kiibohd` | NXP Kinetis | `.bin` | `dfu-util` | `:dfu-util` | Zadig → WinUSB |
| `wb32-dfu` | WestBridge | `.bin` | `wb32-dfu-updater_cli` | `:flash` | (Glorious Toolbox) |
| `at32-dfu` | AT32 | `.bin` | `dfu-util` | `:dfu-util`, split | Zadig → WinUSB |
| `gd32v-dfu` | GD32V (RISC-V) | `.bin` | `dfu-util` | `:dfu-util` | Zadig → WinUSB |
| `rp2040` | RP2040 | `.uf2` | file copy / `qmk flash` | `:uf2-split-left/right` | none |
| `tinyuf2` | STM32 F303/F401/F411 | `.uf2` | file copy / `qmk flash` | `:uf2-split-left/right` | none |
| `uf2boot` | STM32F103 | `.uf2` | file copy / `qmk flash` | `:uf2-split-left/right` | none |

### 11.2 Split-handedness targets

All DFU/avrdude/uf2 families offer `-split-left` / `-split-right` variants that bake the handedness bit into EEPROM (or generate side-specific firmware for UF2). Use for Pro Micro / Elite-C / Proton-C splits — see `10-connectivity.md`.

---

### Gotchas

- **HalfKay is closed-source and unrestorable.** ISP-flashing another bootloader over it permanently loses it — there is no way back.
- **DFU on Windows needs Zadig + WinUSB/libusbK; Caterina/HalfKay/bootloadHID/qmk-hid do not.** Installing a driver while the keyboard is *not* in bootloader mode (Zadig shows `HidUsb` + orange arrow) breaks typing — recover via Device Manager (§5.2).
- **Wrong AVR fuse clock bits can brick the chip** (recoverable only by high-voltage programming). Always double-check before writing fuses; the efuse readback warning is usually benign if the low nibble matches.
- **SparkFun PocketAVR / USBtinyISP can't program >64 KiB AVRs** (e.g. AT90USB128) — they fail verification. Use USBasp/Bus Pirate/Arduino-as-ISP instead.
- **ISP RESET wiring is the #1 mistake.** Programmer's reset-output pin → target RESET. Never programmer-RESET → target-RESET.
- **`QK_BOOT` doesn't work on STM32F042**, and physical entry on STM32/APM32/AT32 needs the BOOT0-bridge-then-RESET dance if there's no reset circuit.
- **Caterina/HalfKay bootloader windows are ~7 s**; SparkFun Caterina needs two RESET taps within 750 ms to stay longer.
- **RP2040 double-tap-RESET entry requires `RP2040_BOOTLOADER_DOUBLE_TAP_RESET`** in the running firmware — otherwise use BOOTSEL-on-plug.
- **`qmk-dfu`/`qmk-hid`: don't make `QMK_ESC` the same key as the Bootmagic key** — holding it loops the MCU in/out of bootloader.
- **Console output needs trailing `\n`** — QMK Toolbox prints per-line; missing newline = missing output. Also disconnect other console-capable devices (tmk #97) and on Linux add a `udev` rule or `sudo`.
- **`get_keycode_string()` reuses a static buffer** — consume the result immediately, never across calls.
- **Debug builds need `LTO_ENABLE = no` + `OPT = g` + `DEBUG_ENABLE = yes`** — LTO breaks clean single-stepping and variable inspection under GDB/Cortex-Debug.
- **`AVR_USE_MINIMAL_PRINTF` is not a drop-in** — it drops zero-padding and field-width; `%03d`/`%2d` still need the full `sprintf`.
- **`LTO_ENABLE = yes` silently removes Action Functions and Action Macros** (both already deprecated) — don't be surprised when they vanish.
- **Unit tests run natively on your host, in C++** — wrap C includes in `extern "C"`. There are no full firmware integration tests yet.
- **`VARIABLE_TRACE` calls cost ROM** (filename + line each); delete all tracing before a PR.
- **STM32duino flashes to dfu-util alt interface 2** (`-a 2`) with no `:leave`, unlike stm32-dfu (`-a 0 -s 0x8000000:leave`).
- **WB32 is not supported by stock QMK Toolbox** — use Glorious's build or the `wb32-dfu-updater_cli` (may need building from source off-Windows).
- **QMK Toolbox is Windows/macOS only**; Linux users use the CLI (`qmk flash`/`qmk console`).
- **The AT90USB64/128 Atmel DFU bootloaders are slightly modified** to enumerate on Windows 8+; use QMK's `.hex` files, not raw Atmel factory images, when ISP-flashing those.

### Possibly stale / sparse source notes

- `isp_flashing_guide.md` mixes `avrisp`/`stk500v1` programmer names across the Arduino-as-ISP variants without a single canonical table — the §4.1 table here consolidates them.
- `other_eclipse.md` is explicitly "tested on Ubuntu 16.04 only" and predates the GNU MCU Eclipse → Eclipse Embedded CDT rebrand; treat the Eclipse AVR instructions as best-effort.
- `arm_debugging.md` (Eclipse) and the VS Code BMP section of `other_vscode.md` are two separate older guides; consolidated in §7 here but the BMP/ST-Link split can drift from upstream extension defaults.
- `flashing.md` does not surface the `wb32-dfu`/`at32-dfu` make targets uniformly (only some families list `:dfu-util-split-*`); the §11.1 table standardizes.
- The zadig "Space+`B`" phrasing vs `newbs_flashing`/Bootmagic "Space+B" — reconciled here to Space+B (the Bootmagic-documented combo).
