# 12 — Hardware & Platforms

> **Scope:** Which MCUs QMK runs on and the tradeoffs between them; the ARM/ChibiOS platform-development guides (Proton C, WeAct Blackpill F4x1, Raspberry Pi RP2040) and the early-init hooks; hand-wiring a keyboard matrix; replacing or augmenting the default matrix scanner (`CUSTOM_MATRIX` / `custom_lite`); porting an existing keyboard (TMK or other) into QMK via `qmk new-keyboard`; the hardware-driver overview; the `CONVERT_TO` mechanism for swapping a drop-in controller (Pro Micro → Proton C / RP2040 / Blackpill); why proprietary/binary vendor libraries (Nordic SoftDevice, ST BT, WCH CH582, WB32 ISP) **cannot** ship in QMK; and the "Easy Maker" direct-pin scaffolding for one-off builds.
>
> **Cross-refs:** `03-config-and-info-json.md` (matrix pin config, `diode_direction`, `matrix_pins.direct`, LAYOUT macros, per-platform **pin-naming conventions** §10 — read it), `02-getting-started-build.md` (`qmk new-keyboard`/`new-keymap`/`import-kbfirmware`), `13-drivers-lowlevel.md` (GPIO, ADC, I²C/SPI/UART, eeprom, ws2812, LED drivers), `15-flashing-debugging.md` (bootloaders, DFU/UF2, ISP flashing, ARM debugging), `10-connectivity.md` (split serial driver selection which is platform-specific).

---

## 1. Compatible microcontrollers — overview

QMK runs on **any USB-capable AVR or ARM MCU with enough flash**. Practical floors:

| Architecture | Minimum flash (rough) | Notes |
|---|---|---|
| AVR | **32 kB** usable; can *squeeze* into 16 kB with heavy feature disabling | LUFA stack for native-USB AVRs; V-USB for non-USB AVRs |
| ARM | **64 kB**+ | via ChibiOS HAL; most ARM chips have far more |

> **Capability caveat:** "QMK runs on it" ≠ "every QMK feature works on it." Some features are AVR-only or ARM-only (see `15-flashing-debugging.md` and per-feature notes across the reference set).

### 1.1 Atmel AVR (LUFA / V-USB)

**Native USB (LUFA stack):**

| MCU | Common boards |
|---|---|
| ATmega16U2 / 32U2 | — |
| ATmega16U4 / **32U4** | **SparkFun Pro Micro** (and clones), PJRC **Teensy 2.0**, Adafruit Feather 32U4, Elite-C (32U4 + USB-C) |
| AT90USB64 / 128 | PJRC **Teensy++ 2.0** |
| AT90USB162 | — |

**No native USB → V-USB (bit-banged USB):** ATmega32A, ATmega328P, ATmega328. These work but V-USB is electrically fragile and slower; avoid for new designs.

### 1.2 ARM (ChibiOS)

Any ARM chip with USB that **ChibiOS** supports. STM32 has the best base-MCU *and* peripheral support. ChibiOS-Contrib adds Kinetis and a few others but with weaker peripheral coverage and less testing.

**STM32 (preferred):** F0x2, **F103** (Bluepill), **F303** (QMK Proton C), **F401** & **F411** (WeAct Blackpill), F405, F407, F446, G431, G474, H723, H733, L412/L422/L432/L433/L442/L443.

**WestBerryTech (WB32):** WB32F3G71xx, WB32FQ95xx — uses a **closed-source ISP flashing tool** (see §9 proprietary libs).

**Artery (AT32):** AT32F415.

**NXP Kinetis:** MKL26Z64 (Teensy LC), MK20DX128, MK20DX256 (Teensy 3.2), MK64FX512 (Teensy 3.5), MK66FX1M0 (Teensy 3.6).

**Raspberry Pi:** **RP2040** — see §4.

**RISC-V (GigaDevice):** GD32VF103 (SiPeed Longan Nano) via ChibiOS-Contrib; largely pin/feature compatible with STM32F103/F303. Experimental.

### 1.3 Capability / footprint / USB / peripheral tradeoffs (quick chooser)

| Need | Pick | Why |
|---|---|---|
| Cheapest drop-in, established ecosystem | ATmega32U4 (Pro Micro clone) | 32 kB flash, 2.5 kB SRAM, 20 I/O, LUFA, well-understood. **Tight on features** — RGB matrix + audio + lots of layers will overflow flash. |
| More flash/RAM, still AVR, more pins | AT90USB1286 (Teensy++ 2.0) | 128 kB flash, 46 I/O |
| Modern ARM, cheap, handwire-friendly | **RP2040** (Pico / Pro Micro RP2040 / RP2040-CE boards) | Dual-core M0+, 264 kB SRAM, 2 MB external flash, **flexible pin muxing**, USB-C, ~$1-6, dual-tap-reset bootloader |
| Powerful ARM, lots of pins/flash, handwire | WeAct **Blackpill F401/F411** | M4, 512 kB / 1 MB flash, USB-C, ~$6 |
| Official QMK reference ARM | QMK **Proton C** (STM32F303) | Drop-in Pro Micro replacement, 23× 3.3 V I/O, 256 kB flash |
| Highest-end ARM | STM32H723/H733, F7-class | M7, big flash/RAM — rarely needed for keyboards |
| Bluetooth/wireless | **See `10-connectivity.md`** | ZMK is the usual recommendation; QMK's wireless story is constrained by the proprietary-libs policy (§9) |

**General ARM advantages over AVR:** far more flash & RAM (enables RGB matrix, audio, OLED, large keymaps simultaneously), hardware USB, faster CPU, DMA. **Tradeoffs:** 3.3 V I/O (not 5 V tolerant — matters for WS2812 power and for 5 V sensors), different bootloaders (DFU/UF2, not Caterina), GPLv3-only binaries (ChibiOS), and pin-naming differences (§1.4).

### 1.4 Pin-naming conventions (AVR vs ARM) — summary

QMK writes pin names as **strings in `info.json`** (`"cols": ["B0","A0"]`) and **bare tokens in `config.h`/C** (`#define MATRIX_ROW_PINS { B0 }`). The token form differs by family:

| Family | Form | Examples | Port width |
|---|---|---|---|
| AVR (ATmega) | **port letter + pin #**, but ports are ≤ 8 bits wide | `B0`, `D7`, `F6` | numbers **0-7 only** — `B12` is **impossible** on AVR |
| STM32 / ChibiOS PAL | **port letter + pin #**, supports ≥ 8 | `A0`, `B12`, `C13`, `F0` | 0-15 typical |
| RP2040 | **`GPx`** (GPIO number from the RP2040 datasheet, *not* the silkscreen pin number) | `GP0`, `GP8`, `GP17` | — |

**Critical cross-ref:** the authoritative per-platform pin-naming rules, the `PB0`/`PA0` "doubled prefix" trap (datasheets write `PB0`, QMK uses `B0` — **never** `PB0` in QMK config), the `A0` ambiguity on ARM (STM32 GPIO vs an ADC-channel label), and `qmk info -kb <keyboard>` to resolve the effective pinout, live in **`03-config-and-info-json.md` §10 (Pin-naming conventions)**. Read it before assigning pins. The Pro Micro→Proton C and Pro Micro→RP2040 pin *remapping* tables are in §3 and §4 below and in §7 (converters).

### Gotchas — MCU selection
- **`B12` on AVR is a red flag** — AVR ports are ≤ 7; that token only exists on ARM. A config mixing them across a converter swap is the most common pin error.
- **AVR flash is genuinely tight.** A 32U4 with RGB matrix + audio + a big keymap can overflow; ARM removes that ceiling.
- **ARM I/O is 3.3 V.** RP2040 GPIO is **not 5 V tolerant**; Blackpill `A0`/`B5` aren't either. Power WS2812 from 5 V but level-shift/accept the data line accordingly (Proton C provides a dedicated 5 V output for WS2812 chains).
- **ARM binaries are GPLv3-only** (ChibiOS); AVR may be GPLv2 or v3. Matters for redistribution.
- **Non-STM32 ChibiOS support is often stale** and "only supports ancient MCUs" — not recommended for new designs (§2).
- Some MCU BSPs carry **licensing/redistribution restrictions** (e.g. nRF5 binaries can't go through QMK Configurator) — see §9.

---

## 2. Selecting / adding an ARM MCU (ChibiOS)

QMK does **not** maintain MCU support packages itself — all MCU families must live in upstream **ChibiOS** (STM32) or **ChibiOS-Contrib** (Kinetis, GD32V, …). QMK reserves the right to **deprecate/remove keyboards** whose support packages fall behind upstream ChibiOS.

### 2.1 Is my STM32 supported? (verification recipe)

1. Browse `os/hal/ports/STM32/<family>/` in [QMK's ChibiOS fork](https://github.com/qmk/ChibiOS/tree/master/os/hal/ports/STM32); each family has a `stm32_registry.h`.
2. Look for a guard like `#if defined(STM32F303xC)` — confirms the MCU variant is known to ChibiOS.
3. Inside that guard, confirm USB is exposed: `STM32_HAS_USB TRUE`, or `STM32_HAS_OTG1 TRUE` / `STM32_HAS_OTG2 TRUE`. At least one `TRUE` = high confidence QMK can run it; the rest is configuration.

### 2.2 Adding a new MCU

| Situation | Path |
|---|---|
| New MCU, **same family**, only RAM/flash differs (or an unused crypto peripheral like L082 vs L072) | "Masquerade" as the sibling MCU; or upstream a `stm32_registry.h` patch to ChibiOS |
| New MCU in an **existing STM32 family** | Modify `stm32_registry.h` for that family; ideally upstream to ChibiOS |
| **New STM32 family** | Must go through upstream ChibiOS *before* QMK accepts boards |
| **New MCU family (non-STM32)** | Must go through ChibiOS-Contrib first |

> **Policy:** QMK will not take over maintenance of a bespoke/commercial MCU support package without agreement from all parties.

### Gotchas — ARM MCU selection
- Don't assume a listed MCU = full feature support — "USB works" is the floor, not the ceiling; check each subsystem (I²C/SPI/ADC/audio/WS2812) on `13-drivers-lowlevel.md`.
- **Non-STM32 paths are out of date** upstream; relying on them risks future removal.
- Adding a family is **not** a QMK-side task — approach ChibiOS/ChibiOS-Contrib, not QMK.

---

## 3. Proton C (STM32F303) platform guide

The **QMK Proton C** is an **STM32F303CCT6** (Cortex-M4, 72 MHz) drop-in replacement for the Pro Micro.

**Specs:** USB-C (through-hole); 256 kB flash; 40 kB RAM; I²C/SPI/PWM/DMA/DAC/USART/I²S; **23× 3.3 V I/O**; one **5 V output for WS2812 chains**; AST1109MLTRQ speaker footprint; reset button; one onboard LED on `C13`.

### 3.1 ⚠️ VCC/RAW short warning

> Some Pro-Micro-compatible PCBs (notably **Gherkin**) short **VCC (3.3 V)** and **RAW (5 V)** together. On a Proton C this shorts USB 5 V into the MCU's regulated 3.3 V rail and **can damage the MCU**. **Workaround:** don't connect the `RAW` pin at all on affected PCBs.

### 3.2 Native use (no converter)

In `rules.mk`:
```make
MCU = STM32F303
BOARD = QMK_PROTON_C
```
Remove `BOOTLOADER` and `EXTRA_FLAGS` if present, then remap pins per the table below. (Using `CONVERT_TO=proton_c` instead avoids the manual remap — see §7.)

### 3.3 Pro Micro → Proton C pin map

| Pro Micro L | Proton C L | | Proton C R | Pro Micro R |
|---|---|---|---|---|
| `D3` | `A9` | | 5 V | RAW (5 V) |
| `D2` | `A10` | | GND | GND |
| GND | GND | | FLASH | RESET |
| GND | GND | | 3.3 V | VCC ¹ |
| `D1` | `B7` | | `A2` | `F4` |
| `D0` | `B6` | | `A1` | `F5` |
| `D4` | `B5` | | `A0` | `F6` |
| `C6` | `B4` | | `B8` | `F7` |
| `D7` | `B3` | | `B13` | `B1` |
| `E6` | `B2` | | `B14` | `B3` |
| `B4` | `B1` | | `B15` | `B2` |
| `B5` | `B0` | | `B9` | `B6` |
| `B0` (RX LED) | `C13` ² | | `C13` ² | `D5` (TX LED) |

**Extended Proton C pins** (not on Pro Micro footprint):

| Left | Right |
|---|---|
| `A4` ³ | `B10` |
| `A5` ³ | `B11` |
| `A6` | `B12` |
| `A7` | `A14` ⁴ (SWCLK) |
| `A8` | `A13` ⁴ (SWDIO) |
| `A15` | RESET ⁵ |

**Footnotes:**
1. On a Pro Micro `VCC` may be 3.3 V **or** 5 V; on Proton C it's 3.3 V.
2. Proton C has **one** onboard LED (`C13`); Pro Micro has two (RX `D5`, TX `B0`).
3. `A4`/`A5` are **shared with the speaker**.
4. `A13`/`A14` are **SWD debug** lines (SWDIO/SWCLK); usable as GPIO but use them **last**.
5. Short `RESET` to 3.3 V (pull high) to reboot the MCU — this **resets**, it does **not** enter bootloader like a Pro Micro.

### Gotchas — Proton C
- Proton C has **one LED, not two**. By default the Pro Micro **TXLED (D5)** maps to `C13`; add `#define CONVERT_TO_PROTON_C_RXLED` to map **RXLED (B0)** instead (converter path).
- Speaker (`A4`/`A5`) conflicts — don't reuse those for matrix/RGB if audio is on.
- `RESET` ≠ bootloader entry on Proton C (unlike Pro Micro). Use `QK_BOOT` (bootmagic/keycode) or DFU entry.
- Voltage domain is 3.3 V; the dedicated 5 V output is **only** for WS2812 power.

---

## 4. WeAct Blackpill (STM32F401 / F411)

Popular for handwired boards: powerful M4, USB-C, lots of pins, large flash, ~$6. *(Official WeAct F411 stock has been intermittent.)*

### 4.1 Pin usage limitations — READ BEFORE ASSIGNING

| Category | Pin(s) | Rule |
|---|---|---|
| **Unusable** | `A11`, `A12` | USB D-/D+ — reserved. "Using" them can kill USB outright. |
| **Unusable** | `B2` | Tied to `BOOT1`. |
| **Unusable** | `VBAT`, `NRST` | Not GPIO. |
| **Avoid** | `A9` | VBUS sense; internal pull-down causes issues. Pull-up (~5.1 k) works but avoid. |
| **Avoid** | `A10` | Any connection can block DFU bootloader entry; needs ~22 k pull-up if used. |
| **Shared** | `A0` | Shared with the User button. Usable. |
| **Shared** | `C13` | Onboard LED (tied to +3.3 V); usable but LED may blink with pin activity. |
| **Shared (SPI flash footprint)** | `A4` (CS — **not shareable**), `A5`/`A6`/`A7` (SCK/MISO/MOSI — shareable with other SPI devices) | SOIC-8 footprint on the back for SPI flash or EEPROM. |
| **Limited output current** | `C13`, `C14`, `C15` | **Input only** — do NOT use as row pins in COL2ROW (rows sink current); OK as column pins (columns are pulled up, sensing is independent of source limit). |
| **Not 5 V tolerant** | `A0`, `B5` | 3.3 V only. |

### 4.2 Bootloader / flashing

- **25 MHz crystal** can cause bootloader-entry issues; heating the chip can help.
- If `A10` is wired to *anything*, add a **~22 k pull-up** or DFU won't engage.
- Supports **tinyuf2** (mass-storage UF2): set `BOOTLOADER = tinyuf2` so flashing firmware won't overwrite the bootloader. Build: <https://github.com/adafruit/tinyuf2>.

### Gotchas — Blackpill
- `C13/C14/C15` as **rows in COL2ROW** = silent failures (current limit). Use them as columns, or invert the matrix to ROW2COL and use them as rows (input side).
- `A10` and `A9` look free but break DFU/USB — avoid for matrix.
- `A4` SPI CS is dedicated — don't try to share it.
- 5 V on `A0`/`B5` damages the chip.
- Crystal/bootloader flakiness is real; tinyuf2 is the more robust path.

---

## 5. Raspberry Pi RP2040 platform guide

Dual-core Cortex-M0+, 264 kB SRAM, **external SPI flash** (2 MB on the Pico), flexible per-pin function muxing (any pin → nearly any peripheral), USB-C. QMK support builds on ChibiOS.

> **⚠️ RP2040 GPIO is NOT 5 V tolerant.**

### 5.1 Peripheral/driver support status

| System | Status |
|---|---|
| ADC | ✅ |
| Audio (PWM hardware) | ✅ |
| Backlight | ✅ |
| I²C | ✅ |
| SPI | ✅ |
| WS2812 | ✅ via **`PIO`** driver |
| External EEPROM | ✅ via I²C or SPI driver |
| EEPROM emulation (wear leveling) | ✅ |
| serial (split) | ✅ via **SIO** or **PIO** driver |
| UART | ✅ via SIO driver |

### 5.2 GPIO & pin naming

- QMK refers to RP2040 pins as **`GPx`** where `x` = the RP2040 GPIO number from the datasheet. **This is not the silkscreen pin number.** E.g. Pico silkscreen "pin 11" = **`GP8`**.
- Flexible muxing: nearly every pin can be I²C/SPI/UART/PWM. Consult the [RP2040 datasheet §1.4.3 GPIO functions](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf#page=14).

### 5.3 Selecting hardware peripherals (ChibiOS convention)

| Peripheral | `mcuconf.h` value | Driver token |
|---|---|---|
| I²C0 / I²C1 | `RP_I2C_USE_I2C0` / `RP_I2C_USE_I2C1` | `I2CD0` / `I2CD1` |
| SPI0 / SPI1 | `RP_SPI_USE_SPI0` / `RP_SPI_USE_SPI1` | `SPID0` / `SPID1` |
| UART0 / UART1 | `RP_SIO_USE_UART0` / `RP_SIO_USE_UART1` | `SIOD0` / `SIOD1` |

(See `13-drivers-lowlevel.md` for the full driver config; the table here is the RP2040-specific key mapping.)

### 5.4 Double-tap reset → UF2 bootloader

RP2040's onboard bootloader is a **mass-storage UF2**. QMK can enter it via a **fast double-tap of RESET on startup** (Pro-Micro-like). **On by default for the Pro Micro RP2040 board**; for others add to `config.h`:

```c
#define RP2040_BOOTLOADER_DOUBLE_TAP_RESET              // enable double-tap behavior
#define RP2040_BOOTLOADER_DOUBLE_TAP_RESET_TIMEOUT 200U // ms window for the double tap
#define RP2040_BOOTLOADER_DOUBLE_TAP_RESET_LED GP17     // optional status LED that blinks on entry
```

### 5.5 Pre-defined RP2040 boards

**a) Generic Pro Micro RP2040** (default unless another RP2040 board is selected). Mirrors the Sparkfun Pro Micro RP2040 I²C/SPI/serial pinout; all overridable in `config.h`. Double-tap reset **on by default**.

| Driver | Defaults |
|---|---|
| I²C | `I2C_DRIVER=I2CD1`, `I2C1_SDA_PIN=GP2`, `I2C1_SCL_PIN=GP3` |
| SPI | `SPI_DRIVER=SPID0`, `SPI_SCK_PIN=GP18`, `SPI_MISO_PIN=GP20`, `SPI_MOSI_PIN=GP19` |
| serial (SIO) | `SERIAL_USART_DRIVER=SIOD0`, `SOFT_SERIAL_PIN` undefined (use `SERIAL_USART_TX_PIN=GP0`), `SERIAL_USART_RX_PIN=GP1` |
| UART | `UART_DRIVER=SIOD0`, `UART_TX_PIN=GP0`, `UART_RX_PIN=GP1` |

> **Tip:** Adafruit **KB2040** and Boardsource **Blok** pinouts **deviate** from the Sparkfun Pro Micro RP2040 — look up the pinout and adjust pin defines.

**b) Generic RP2040 board** — no preconfigured pins/drivers; you define everything. Select in `rules.mk`:
```make
BOARD = GENERIC_RP_RP2040
```

### 5.6 Split keyboard support

Full split support via the serial driver, half- and full-duplex. Two subsystems:

| Feature | SIO driver | PIO driver |
|---|---|---|
| Half-duplex | — | ✅ |
| Full-duplex | ✅ | ✅ |
| TX/RX pin swap | — | ✅ |
| Any GPIO as TX/RX | Only UART-capable pins | ✅ |
| Simple config | — | ✅ |

The **PIO** driver is more flexible; the only cost is consuming a PIO block (normally a non-issue). See `10-connectivity.md` for split wiring and `13-drivers-lowlevel.md` for the serial driver.

### 5.7 Second-stage bootloader (external flash) selection

RP2040 has **no internal flash**; it boots from external SPI flash via a **second-stage bootloader** matched to the flash chip. Default assumes `W25Q080`. Override in `config.h`:

| Flash chip | Define |
|---|---|
| W25Q080 | *(default)* |
| AT25SF128A | `#define RP2040_FLASH_AT25SF128A` |
| GD25Q64CS | `#define RP2040_FLASH_GD25Q64CS` |
| W25X10CL | `#define RP2040_FLASH_W25X10CL` |
| IS25LP080 | `#define RP2040_FLASH_IS25LP080` |
| Generic 03H flash | `#define RP2040_FLASH_GENERIC_03H` |

### 5.8 RP2040 Community Edition pinout

A pinout standard defined on the BastardKB Discord for **drop-in replacements of ATmega32U4 Pro Micros** (e.g. as an Elite-C upgrade). Compatible controllers: **0xB2 Splinky, Elite-Pi, Sea-Picro EXT, 0xCB Helios, Frood, Liatris**. (These are the `rp2040_ce` family of converter targets — §7.)

### Gotchas — RP2040
- **`GPx` ≠ silkscreen number.** Always cross-reference the datasheet GPIO number.
- GPIO is **not 5 V tolerant** — relevant for WS2812 power rails and level shifting.
- **External flash matters:** a wrong/unmatched second-stage bootloader = no boot. Pick the `RP2040_FLASH_*` define to match your chip.
- Double-tap reset is **only default-on for the Pro Micro RP2040 board**; configure it explicitly elsewhere or you can't enter UF2 without a PC connection.
- KB2040/Blok pinouts differ from Sparkfun's — don't assume the generic defaults.
- PIO serial is more flexible than SIO; pick PIO if you need half-duplex or arbitrary pins.

---

## 6. ARM/ChibiOS early initialization hooks

QMK abstracts the ChibiOS low-level board definition into three overridable hooks, so you **no longer need to duplicate board definitions** into your keyboard dir. (Official ChibiOS board defs: `<qmk_firmware>/lib/chibios/os/hal/boards`.)

### 6.1 `early_hardware_init_pre(void)` — earliest possible

Equivalent to the **start** of ChibiOS's `__early_init`. **Runs before RAM is cleared and before clocks/GPIOs are configured** — ChibiOS delays likely don't work; variables you set may be zeroed afterward. Limit to **raw register writes**.

Default behavior can be made to jump to bootloader when `QK_BOOT` was pressed, via `config.h`:

| `config.h` define | Meaning | Default |
|---|---|---|
| `EARLY_INIT_PERFORM_BOOTLOADER_JUMP` | Jump to bootloader during early init if `QK_BOOT` pressed | `FALSE` |
| `STM32_BOOTLOADER_DUAL_BANK` | (Dual-bank STM32) toggle a GPIO to enter bootloader | `FALSE` |
| `STM32_BOOTLOADER_DUAL_BANK_GPIO` | (Dual-bank) pin to toggle, e.g. `B8` | `<none>` |
| `STM32_BOOTLOADER_DUAL_BANK_POLARITY` | (Dual-bank) value to set the pin to (charges an RC circuit) | `0` |
| `STM32_BOOTLOADER_DUAL_BANK_DELAY` | (Dual-bank) arbitrary delay-before-reset magnitude | `100` |

Kinetis: no configurable options.

Override:
```c
void early_hardware_init_pre(void) {
    // raw register writes only; RAM not yet valid, no delays
}
```

### 6.2 `early_hardware_init_post(void)` — after RAM/clock/GPIO init

Equivalent to the **end** of `__early_init`. RAM is cleared and clocks/GPIO configured, but **ChibiOS itself is not yet initialized** — same delay/timing restrictions. Limit to register writes, variable init, and GPIO toggling. Default: no-op.

```c
void early_hardware_init_post(void) {
    // register writes, variable init, GPIO toggling; no ChibiOS calls yet
}
```

### 6.3 `board_init(void)` — after ChibiOS init

Equivalent to ChibiOS's `boardInit`. **All normal low-level functionality (timers, delays) is available**, except **USB is not yet connected**. Default: no-op.

```c
void board_init(void) {
    // anything needing ChibiOS (timers, etc.); USB still down
}
```

### Behavior & ordering
`early_hardware_init_pre` → (RAM clear, clocks, GPIO) → `early_hardware_init_post` → (ChibiOS init) → `board_init` → (USB connect) → `matrix_init`/keyboard init. These run **before** the QMK main loop and before any `matrix_init_*`/`keyboard_pre_init_*` hooks (see `01-architecture.md`).

### Gotchas — early init
- **`_pre` writes to C variables are unreliable** — RAM may be zeroed after your function returns. Use registers only.
- **No delays/timing in `_pre` or `_post`** — ChibiOS isn't running. Only `board_init` can sleep.
- These hooks are **ARM/ChibiOS only** — AVR has a different startup path.
- Dual-bank STM32 bootloader entry needs the GPIO/polarity/delay trio set *together*.

---

## 7. Converters — swapping a drop-in controller

The `CONVERT_TO` mechanism rebuilds a keyboard's firmware for a **pin-compatible replacement controller** without editing the keyboard itself. Designed for Pro Micro / Elite-C footprints.

### 7.1 Usage

Append `-e CONVERT_TO=<target>` to compile/flash, **or** set it in the keymap:

```sh
qmk flash -c -kb keebio/bdn9/rev1 -km default -e CONVERT_TO=proton_c
```

**`keymap.json`:**
```json
{
    "version": 1,
    "keyboard": "keebio/bdn9/rev1",
    "keymap": "keebio_bdn9_rev1_layout_2025-05-20",
    "converter": "proton_c",
    "layout": "LAYOUT"
}
```
**`rules.mk`:**
```make
CONVERT_TO = proton_c
```

> If you get build errors, the keyboard code must be made **converter-compatible** (§7.4) or you must supply keymap-level config (§7.5).

### 7.2 Supported targets (by source footprint)

| From | To |
|---|---|
| `promicro` | `proton_c`, `kb2040`, `sparkfun_pm2040`, `blok`, `bit_c_pro`, `stemcell`, `bonsai_c4`, `rp2040_ce`, `elite_pi`, `helios`, `liatris`, `imera`, `michi`, `svlinky` |
| `elite_c` | `stemcell`, `rp2040_ce`, `elite_pi`, `helios`, `liatris` |

**Pro Micro targets** (each exposes a `CONVERT_TO_<TARGET_UPPERCASE>` `#ifdef` flag, e.g. `CONVERT_TO_PROTON_C`, `CONVERT_TO_KB2040`, `CONVERT_TO_RP2040_CE`, `CONVERT_TO_STEMCELL`, `CONVERT_TO_BONSAI_C4`, `CONVERT_TO_HELIOS`, `CONVERT_TO_LIATRIS`, `CONVERT_TO_SVLINKY`, …):

| Target | Device | Notable defaults/notes |
|---|---|---|
| `proton_c` | QMK Proton C (STM32F303) | Audio enabled; RGB disabled; backlight forced to task-driven PWM; **USB-USB host unsupported** (AVR-specific); split partial. Single LED `C13`; default maps **TXLED D5**; `#define CONVERT_TO_PROTON_C_RXLED` for RXLED `B0`. |
| `kb2040` | Adafruit KB2040 (RP2040) | RGB via **PIO** driver; backlight task-PWM; no USB host; split partial via PIO. |
| `sparkfun_pm2040` / `blok` / `bit_c_pro` / `michi` | Sparkfun Pro Micro RP2040, Boardsource Blok, Bit-C PRO, Michi | Feature set identical to `kb2040`. |
| `stemcell` | STeMCell | Identical to Proton C. **Pinout versions v1.0.0 vs v2.0.0** (v1.0.1/v1.0.2 pre-release); default firmware supports **v2.0.0 only**. Can swap UART/I²C for single-wire UART: split on `D3`→`-e STMC_US=yes`, `D1`→`-e STMC_IS=yes`; `D2`/`D0` need nothing. |
| `bonsai_c4` | customMK Bonsai C4 | Single LED `B2`; both TXLED `D5` & RXLED `B0` mapped to it by default. To map only one: `#undef B0` then e.g. `#define B0 PAL_LINE(GPIOA, 9)` (reuses VBUS-detect pin). |
| `rp2040_ce` | RP2040 Community Edition (Splinky/Elite-Pi/Sea-Picro/Helios/Frood/Liatris family) | As `kb2040`; **VBUS detection enabled by default** for better split support. |
| `elite_pi` / `helios` / `liatris` | Specific RP2040-CE boards | As `rp2040_ce`. |
| `imera` / `michi` / `svlinky` | Imera / Michi / Svlinky (RP2040) | Svlinky = RP2040-CE equivalent but **two analog GPIO replaced with digital-only**, moved to an FPC connector for the [VIK spec](https://github.com/sadekbaroudi/vik) — analog on all 4 pins is **not** available. |

**Elite-C targets:** `stemcell` (Elite-C variant = Pro Micro STeMCell + extra bottom-row pins), `rp2040_ce` (Elite-C variant = Pro Micro RP2040-CE + bottom row), `elite_pi`, `helios`, `liatris`.

### 7.3 Conditional code

```c
#ifdef CONVERT_TO_PROTON_C
    // Proton C code
#else
    // Pro Micro code
#endif
```

### 7.4 Making a keyboard converter-compatible

Declare a **development board** (which implies pin compatibility) in `keyboard.json`:
```json
{
    "maintainer": "QMK",
    "development_board": "promicro",
    "diode_direction": "COL2ROW"
}
```
**Additional requirements:** the keyboard must use QMK's **platform-agnostic abstractions**, especially the [GPIO Controls](drivers/gpio) (`gpio_set_pin_output`/`gpio_read_pin`/…), not raw AVR/ARM register access. (See `13-drivers-lowlevel.md` §GPIO.)

### 7.5 Additional keymap-level config

Sometimes a converter needs platform-specific driver enabling or feature disabling. **Enable** via a keymap-level `mcuconf.h`:
```c
#pragma once
#include_next <mcuconf.h>
#undef RP_SIO_USE_UART0
#define RP_SIO_USE_UART0 TRUE
```
**Disable** an incompatible feature in `keymap.json`:
```json
{
    "converter": "proton_c",
    "config": { "features": { "audio": false } }
}
```
(or `AUDIO_ENABLE = no` in keymap `rules.mk`).

### 7.6 Pin compatibility (the validation framework)

For keyboards not using a `development_board` preset, declare pin compatibility explicitly:
```json
{
    "development_board": "elite_c",
    "pin_compatible": "elite_c",
    "diode_direction": "COL2ROW"
}
```
This declares the **base interface** for conversions and validates that only compatible targets are attempted. The framework maps pins from `<PIN_COMPATIBLE>` → converter `<target>`.

> **Warning:** Mapped pins must adhere **strictly** to the defined interface; extra pins on the hardware should be ignored.

**Available pin-compatible interfaces:** `promicro` (includes LEDs B0/D5, which may map to unused pins when absent), `elite_c` (adds the bottom-row pins B7/D5/C7/F1/F0; no LEDs).

### Gotchas — converters
- **USB-USB (host) converters don't work on ARM targets** — the USB-host code is AVR-specific. Proton C / RP2040 targets can't be a USB-USB converter.
- **Backlight forces task-driven (software) PWM** on ARM converters until ARM auto-config exists.
- **Split support is "partial" and feature-dependent** on every converter — verify your split features actually transport.
- **STeMCell has two pinout versions**; default firmware = v2.0.0 only. Single-wire UART needs `STMC_US`/`STMC_IS` flags depending on the split pin.
- **Svlinky loses 2 analog GPIO** vs RP2040-CE (moved to FPC for VIK) — analog on all 4 CE pins is not available.
- Declaring `development_board`/`pin_compatible` is **required** for converter validation; ad-hoc keyboards without it will fail or silently mis-map pins.
- Mapped pins must stay within the declared interface — don't rely on "extra" hardware pins through the converter.

---

## 8. Hand-wiring a keyboard

Building a keyboard matrix from discrete switches + diodes + wire on a plate (no PCB).

### 8.1 Bill of materials (per *x* keys)
- QMK-compatible MCU board (Teensy, Pro Micro, Proton C, …)
- *x* keyswitches (MX/Gateron/Matias/…)
- *x* through-hole diodes (1N4148 typical)
- Plate + plate-mount stabilizers; wire; rosin-core solder; iron; wire cutters; ventilation
- Optional: wire strippers/knife, tweezers/needle-nose, helping hands
- Plate generators: [ai03 Plate Generator](https://kbplate.ai03.me/), [Swillkb Plate & Case Builder](http://builder.swillkb.com/)

### 8.2 Matrix sizing — the cardinal rule

> **(rows + columns) ≤ available digital I/O pins.**

A full-size ISO matrix needs more pins than a Pro Micro/Teensy offer; use a Proton C (36 I/O) or Teensy++ 2.0 (46 I/O). Plan matrices with [Keyboard Firmware Builder](https://kbfirmware.com/) (import from [Keyboard Layout Editor](https://www.keyboard-layout-editor.com/)).

| Board | Controller | # I/O |
|---|---|---|
| Pro Micro* | ATmega32U4 | 20 |
| Teensy 2.0 | ATmega32U4 | 25 |
| QMK Proton C | STM32F303xC | 36 |
| Teensy++ 2.0 | AT90USB1286 | 46 |

*Elite-C ≈ Pro Micro with USB-C. Handwire-specific boards (Postage board, Postage board mini, Swiss helper) mount to a few switches and break out the rest.

### 8.3 Rows, columns, and diodes

- One switch leg → its row neighbors; the other leg → its column neighbors.
- A **diode** goes on one leg (conventionally the row leg), oriented so current flows one way. The wire furthest from the diode's black bar connects to the switch.
- **Diode direction** in firmware (`diode_direction`: `COL2ROW` or `ROW2COL`) **must match the physical diode orientation** — see `03-config-and-info-json.md` §matrix. Mismatch = no keys register (or all keys ghost).
- Diodes must be in **parallel** (outputs don't feed inputs).
- **Why diodes at all:** without them, multi-key "ghost" paths form in the matrix. (Background: `how_a_matrix_works`.)

### 8.4 Soldering notes (condensed)
- Iron temp ~315 °C / 600 °F; tin the iron, wipe on wet sponge/brass.
- Heat both surfaces ~1 s, *then* apply solder; don't linger (flux burns off → cold/peaked joints; heat damages switch housings).
- Diodes vertical, black bar toward you; solder the input lead to the switch's left contact, bend output right onto the next switch. Trim excess per row.
- Column wires: insulate them (the diode row wiring isn't insulated). Options: stripped single-core, magnet/enamel wire (burn off insulation with the iron), rigid brass "hardline", bare wire + kapton, copper tape.
- **Split keyboards:** each half needs its own controller + inter-half link (TRRS or hardwired). See `10-connectivity.md`.

### 8.5 Wiring to the controller
- Avoid `GND`, `VCC`, `AREF`, `RST`. On Teensy 2.0 also avoid `D6` (onboard LED) and dedicated UART/SPI/I²C/PWM pins unless you're using them.
- Solder **after the diode** on a row — soldering before the diode (switch side) breaks that row.
- Record the row/col→pin mapping; that drives `matrix_pins` in `keyboard.json`.

### 8.6 Firmware from a handwire
- Quick path: [Keyboard Firmware Builder](https://kbfirmware.com/) → export JSON → `qmk import-kbfirmware /path.json` (note: KFB is based on **early-2017 QMK**; "basic" support — **prefer `qmk new-keyboard`**, see §11).
- Modern path: `qmk new-keyboard`, then fill in `matrix_pins`/`diode_direction`/layouts in `keyboard.json` (see `02-getting-started-build.md`, `03-config-and-info-json.md`).

### 8.7 Direct pin wiring (no diode matrix)
Each switch on its own pin, other leg to ground; the MCU's **internal pull-ups** do the sensing — **no diodes, no rows/cols**. Configured via `matrix_pins.direct` (2D array of pins, `null` for blanks) in `keyboard.json`; `diode_direction` is **ignored** for direct pins (see `03-config-and-info-json.md` §matrix and the Easy Maker §12).

### 8.8 Testing non-working keys (troubleshooting order)
1. Short the switch contacts with a wire (rules out a bad switch).
2. Inspect switch solder joints (plump & whole).
3. Diode joints (loose diode → partial row).
4. Column wiring (loose → partial/full column dead).
5. Both ends of MCU wires.
6. `<project>.h`/layouts JSON: misplaced `KC_NO` / wrong `k*xy`.
7. Did you actually compile & flash?
8. Multimeter: does the switch close when actuated?

> Multiple faults can stack — re-test by shorting after each fix.

### Gotchas — hand-wiring
- **rows + cols ≤ I/O pins** is the hard constraint; full-size boards need a big-pin controller.
- **Diode direction mismatch** = silent total failure or ghosting; set `diode_direction` to match physical orientation.
- Soldering **before** the diode on a row disconnects that row.
- KFB export is **stale** (2017 QMK); `qmk new-keyboard` is the supported path.
- Column wires shorting to uninsulated diode rows is the #1 build fault — insulate columns.
- Direct-pin mode **ignores** `diode_direction` and `cols`/`rows`; don't set them together with `matrix_pins.direct`.

---

## 9. Custom matrix scanning

Replace or augment QMK's default matrix scanner. Use cases: I/O multiplexers / line decoders between switches and MCU, irregular matrices (simultaneous `COL2ROW` + `ROW2COL`), or exotic switch hardware.

### 9.1 Setup
Create `keyboards/<keyboard>/matrix.c` and compile it:
```make
# rules.mk
SRC += matrix.c
```

### 9.2 Two modes — the contract differs

**`CUSTOM_MATRIX = lite`** (recommended — less boilerplate). Implement **two** functions in `matrix.c`:

```c
void matrix_init_custom(void) {
    // initialize hardware
}

bool matrix_scan_custom(matrix_row_t current_matrix[]) {
    bool matrix_has_changed = false;
    // scanning routine: write into current_matrix[], set changed=true if any bit flipped
    return matrix_has_changed;
}
```
QMK supplies init/scan wrappers, debouncing, and the `_kb`/`_user` callback chain. `current_matrix[]` is `MATRIX_ROWS` entries of `matrix_row_t` (a bitmask of columns).

**`CUSTOM_MATRIX = yes`** (full replacement — more control, more responsibility). You own the whole scan and must call the QMK machinery yourself:

```c
matrix_row_t matrix_get_row(uint8_t row) {
    // return the requested row's bitmask
}

void matrix_print(void) {
    // print() the matrix state to console
}

void matrix_init(void) {
    // init hardware + global matrix state
    debounce_init();                 // unless hardware debouncing
    matrix_init_kb();                // MUST be called
}

uint8_t matrix_scan(void) {
    bool changed = false;
    // scanning routine
    changed = debounce(raw_matrix, matrix, changed); // unless HW debouncing
    matrix_scan_kb();                // MUST be called
    return changed;
}
```
You must also provide (weak) defaults for the callback chain:
```c
__attribute__((weak)) void matrix_init_kb(void)  { matrix_init_user(); }
__attribute__((weak)) void matrix_scan_kb(void)  { matrix_scan_user(); }
__attribute__((weak)) void matrix_init_user(void) {}
__attribute__((weak)) void matrix_scan_user(void) {}
```

### 9.3 Data-driven equivalents
In `info.json`, `matrix_pins.custom` (full) and `matrix_pins.custom_lite` (lite) are the booleans (see `03-config-and-info-json.md` §matrix). `CUSTOM_MATRIX` in `rules.mk` is the legacy equivalent.

### Behavior & ordering
Custom scan output feeds the same debounce + QMK matrix state as the default scanner, so `process_record` / layers / `matrix_scan_user` downstream are unaffected. In full-replacement mode, **forgetting `matrix_init_kb()`/`matrix_scan_kb()`** or `debounce(...)` breaks the keyboard — they're mandatory, not optional. See `01-architecture.md` for where matrix scan sits in the main loop.

### Gotchas — custom matrix
- **lite vs full**: lite = 2 functions (`matrix_init_custom` + `matrix_scan_custom`); full = 4+ functions and you own debouncing + the `_kb` chain. Default to lite.
- In full mode, **`matrix_init_kb()` and `matrix_scan_kb()` are mandatory** — omitting them silently breaks keymaps (no `_user` callbacks fire).
- In full mode you must call `debounce_init()`/`debounce(raw_matrix, matrix, changed)` yourself **unless** you do hardware debouncing.
- `matrix_row_t` width limits columns per row (architecture-dependent) — verify for wide matrices.
- The `current_matrix[]`/`raw_matrix[]` arrays are indexed by row; mask bits are columns.

---

## 10. Porting a keyboard into QMK

For bringing an existing keyboard (from TMK, another firmware, or a fresh design) into QMK.

### 10.1 Scaffolding: `qmk new-keyboard`

`qmk new-keyboard` generates the full directory and defaults. Interactive prompts:

- **Keyboard Name** (follow naming guidelines).
- **Attribution** (GitHub username; real name) — used for `maintainer`/copyright.
- **Default Layout** (pick a common base layout, e.g. `60_abnt2` … or `none of the above`).
- **Development board?** y/n — is the MCU a separate dev board (Pro Micro, …) or integrated on the PCB?
- **Development Board** (if y): `promicro`, `bit_c_pro`, …, `svlinky`, …

Output: `keyboards/<name>/` with `keyboard.json`, `readme.md`, keymap, etc. Build: `qmk compile -kb <name> -km default`. Then "update the config files to match the hardware."

See `02-getting-started-build.md` for CLI details and `qmk import-kbfirmware` (basic; prefer `new-keyboard`).

### 10.2 `readme.md`
Describe the keyboard; follow the Keyboard Readme Template; host images externally (Imgur).

### 10.3 `keyboard.json` (hardware + features)
**USB identity** (how the board appears to the OS):
```json
{
    "keyboard_name": "my_awesome_keyboard",
    "maintainer": "You",
    "usb": {
        "vid": "0xFEED",
        "pid": "0x0000",
        "device_version": "1.0.0"
    }
}
```
- Leave `usb.vid` as `0xFEED` unless you have reason to change.
- Pick an unused `usb.pid`.
- Set `manufacturer`/`keyboard_name` accurately.
- Windows/macOS show `manufacturer`/`keyboard_name`; Linux `lsusb` prefers the [USB ID Repository](http://www.linux-usb.org/usb-ids.html) list and only falls back to device values if the VID/PID isn't listed (`sudo lsusb -v` and kernel logs always show device values).

**Matrix** (full details in `03-config-and-info-json.md` §matrix):

*Diode matrix:*
```json
"matrix_pins": {
    "cols": ["C1","C2","C3","C4"],
    "rows": ["D1","D2","D3","D4"]
},
"diode_direction": "ROW2COL"
```
Matrix dims are **inferred** from `cols`/`rows` array lengths (legacy: `MATRIX_ROWS`/`MATRIX_COLS` in `config.h`).

*Direct pin matrix:*
```json
"matrix_pins": {
    "direct": [
        ["F1","E6","B0","B2","B3"],
        ["F5","F0","B1","B7","D2"],
        ["F6","F7","C7","D5","D3"],
        ["B5","C6","B6", null, null]
    ]
}
```
Dims inferred from the 2D array; each row needs the same column count; use `null` for blanks (minimize them). `diode_direction`/`cols`/`rows` are **ignored** — don't mix.

**Layout macros** — define physical key positions and their matrix `[row, col]`:
```json
"layouts": {
    "LAYOUT_ortho_4x4": {
        "layout": [
            {"matrix": [0,0], "x": 0, "y": 0},
            {"matrix": [0,1], "x": 1, "y": 0}
            // … one entry per physical key
        ]
    }
}
```
- `LAYOUT_<name>` must follow layout-naming guidelines.
- `{"matrix":[r,c]}` ties a physical key to its matrix position (physical layout may differ from the wiring matrix).
- See also: Split Keyboard Layout Macro (`10-connectivity.md`) and Matrix-to-Physical-Layout (`01-architecture.md`).

### 10.4 Additional (non-data-driven) config
Some options still need `config.h` (Config Options) or `rules.mk` (Feature Options) — see `03-config-and-info-json.md` for the migration status and the "NOT yet data-driven" list.

### 10.5 From TMK specifically
QMK forked from TMK; most TMK keymaps port with moderate changes (different build system, data-driven config, QMK-specific keycodes/features). Scaffold with `qmk new-keyboard`, then port the keymap layer definitions and matrix wiring into `keyboard.json` + the keymap. Don't try to build raw TMK source inside QMK.

### Gotchas — porting
- **`matrix_pins` dims are inferred from array length** — mismatched `MATRIX_ROWS`/`MATRIX_COLS` legacy defines vs the JSON arrays cause confusion; prefer JSON.
- **Don't mix `matrix_pins.direct` with `cols`/`rows`/`diode_direction`** — direct mode overrides and ignores them.
- `usb.vid` `0xFEED` is the convention; don't claim a PID already in use.
- Linux `lsusb` may show a *different* name than what you set (USB ID Repository wins) — not a bug.
- `qmk import-kbfirmware` is "basic"/stale; `qmk new-keyboard` is the supported path.
- Layout name must follow the naming guidelines or PRs will be rejected.

---

## 11. Hardware drivers — overview

QMK ships built-in support for common MCUs and matrix configurations; additional drivers add support for **pointing devices, I/O expanders (split keyboards), Bluetooth modules, and LCD/OLED/TFT displays**. (The driver list below is the high-level index; **per-driver configuration lives in `13-drivers-lowlevel.md`** and the relevant feature pages.)

| Driver | What it does | Where |
|---|---|---|
| **ProMicro (AVR only)** | Address Pro Micro pins by Arduino name instead of AVR name | lightly documented; read the code or open an issue |
| **SSD1306 OLED** | SSD1306-based OLED displays | `08-displays.md` (oled_driver) |
| **WS2812** | WS2811/WS2812{a,b,c} LEDs | `07-led-rgb-backlight.md` (rgblight) |
| **IS31FL3731** | Up to 2 drivers; 2 charlieplex matrices each via I²C; ≤144 same-color or 32 RGB LEDs | `07-led-rgb-backlight.md` (rgb_matrix) |
| **IS31FL3733** | Up to 1 driver (expandable); 192 LEDs or 64 RGB | `07-led-rgb-backlight.md` (rgb_matrix) |
| **24xx external I²C EEPROM** | External I²C EEPROM instead of on-chip | `13-drivers-lowlevel.md` (eeprom) |

> The full LED-driver family (IS31FL3731/3733/3736/3737/3741/3742A/3743A/3745/3746A, SNLED27351, AW20216S, etc.), WS2812/APA102, ADC/I²C/SPI/UART/serial, GPIO, EEPROM/flash, audio driver, and battery driver are all detailed in **`13-drivers-lowlevel.md`**. This page is only the high-level index from the legacy `hardware_drivers` doc.

### Gotchas — hardware drivers
- The legacy `hardware_drivers.md` is **sparse** (the upstream doc even carries a `FIXME` about documenting how drivers integrate and how to add your own). Treat it as an index, not a reference — go to `13-drivers-lowlevel.md` and the feature pages for real config.
- **ProMicro Arduino-name driver is AVR-only** and thinly documented.
- IS31FL* drivers are I²C-based; on ARM you must enable the right I²C peripheral (see RP2040/STM32 driver tables above and `13-drivers-lowlevel.md`).

---

## 12. Proprietary vendor libraries — why they're banned

**QMK (GPL) cannot include any proprietary vendor library** — binary-only blobs, hardware-locked libs, or code with redistribution limits. This is the single biggest constraint on QMK's wireless/hardware story.

### 12.1 Why firmware is special (architecture constraints)
- **Monolithic binary**: all code compiles into one image.
- **No OS isolation**: no process/memory separation.
- **Shared resources**: one memory space, shared peripherals/execution context.
- **Static linking**: everything links at compile time.

→ Any proprietary code becomes **inseparable** from GPL code = immediate license violation.

### 12.2 Typical incompatible restrictions
- **Hardware lock-in** (chip-only clauses; e.g. Nordic, ST).
- **No source** — binary-only libs (.a/.lib), no fix/modify ability (e.g. WCH CH582 precompiled BLE, Nordic SoftDevice).
- **Redistribution limits** (who can distribute, commercial-use caps, fees/permissions).
- **Extra legal terms** (patent assertions, indemnification, jurisdiction, explicit anti-GPL clauses).

### 12.3 Bluetooth-stack exemplars
- **Nordic SoftDevice** (Nordic 5-clause): binary-only BT/radio, hardware-locked, no source, SVC interface. **Still not GPL-compatible** (functional integration, not linking method, is what GPL examines).
- **ST Bluetooth** (SLA0044): **explicitly forbids** "Open Source Terms" and **calls out GPL incompatibility**; ST-chips only.
- **WCH CH582**: precompiled BT libraries.

### 12.4 Why the "System Library" exception fails
The GPL system-library exception covers only libs that (1) ship with a Major Component (OS kernel/compiler), (2) aren't distributed with the app, (3) aren't part of the app. Firmware vendor libs fail **all** of these: no OS exists, drivers aren't kernels/compilers, the code is distributed *inside* the firmware binary, and peripheral drivers are application code. (The exception is for things like Windows DLLs / Linux glibc.)

### 12.5 Workarounds that DON'T work
- **SVC interfaces** (Nordic SoftDevice): GPL looks at *functional integration*, not linking method — a board that *needs* the proprietary blob to function is one work.
- **Binary-only distributions**: classic static linking of proprietary into GPL; can't modify = GPL violation.
- **Loader-based separation** (GPL bootloader loads proprietary BT from external storage): functional interdependence + co-distribution ⇒ treated as one work; looks like GPL circumvention.

### 12.6 Practical consequences for hardware choices
- **No Nordic SoftDevice / ST BT / WCH CH582 BT** in QMK → **QMK's Bluetooth story is limited**; for wireless keyboards, **ZMK** is the common recommendation (see `10-connectivity.md`).
- **WB32 ISP flashing** uses a closed-source vendor tool — you can flash WB32 boards but the tooling isn't in QMK.
- **nRF5 binaries can't be redistributed via QMK Configurator** (BSP licensing).
- **ST HAL/LL** source is *visible* but SLA0044-restricted (this is navigable for ChibiOS HAL use, but it's why pure proprietary stacks are off-limits).

### 12.7 Evaluation criteria (for any library under consideration)
Complete source available **and** GPL-compatible license (GPL/LGPL/MIT/BSD/Apache) **and** no hardware restrictions **and** no redistribution limits **and** no extra legal terms **and** no anti-GPL clauses.

> **Policy:** No proprietary libraries, no binary blobs, no platform restrictions, no additional terms — only GPL.

### Gotchas — proprietary libs
- **"Just put the BT stack in a separate partition/SVC" is not a legal escape** — GPL tests functional integration.
- **This is why QMK wireless is constrained** and ZMK is often recommended — set expectations with users accordingly.
- WB32/nRF5 tooling/redistribution limits are licensing, not technical.
- ST HAL being "source visible" ≠ freely redistributable — SLA0044 still applies.

---

## 13. Easy Maker — one-off direct-pin scaffolding

[Easy Maker](https://config.qmk.fm/#/?filter=ez_maker/direct) builds firmware for one-off projects (macropads, single controls) in minutes via QMK Configurator, **without `qmk new-keyboard`**.

**Styles:**
- **Direct Pin** — one switch per pin (available now).
- Direct Pin + Backlight / + Numlock / + Capslock / + Encoder — *(Coming Soon)* per the upstream doc.

### 13.1 Direct Pin
- **One switch per pin**; the switch's other side → **ground (VSS/GND)**.
- **No diodes, no resistors needed** — the MCU's **internal pull-ups** sense the switch.
- Wire your switches, then pick your **MCU** from the Keyboard dropdown at <https://config.qmk.fm/#/?filter=ez_maker/direct>, assign a keycode per pin, and build.

> Equivalent in code: `matrix_pins.direct` in `keyboard.json` (see `03-config-and-info-json.md` §matrix and §8.7 above). Easy Maker is the Configurator UI for the same direct-pin model.

### Gotchas — Easy Maker
- Only **Direct Pin** is currently live; the backlight/LED/encoder variants are still "Coming Soon."
- Easy Maker targets **one-off** builds — for a real keyboard, use `qmk new-keyboard` (§10) instead.
- Pin names follow the platform conventions (§1.4) — pick the matching MCU in the dropdown or pins won't resolve.

---

## 14. Cross-cutting relationships (where to go next)

- **`03-config-and-info-json.md`** — §matrix (`matrix_pins`, `diode_direction`, `matrix_pins.direct`, `matrix_pins.custom`/`custom_lite`, `input_pressed_state`, `io_delay`), LAYOUT macros, and §10 **pin-naming conventions** (the authoritative AVR-`B0` vs ARM-`A0` vs RP2040-`GPx` rules).
- **`02-getting-started-build.md`** — `qmk new-keyboard`/`new-keymap`/`import-kbfirmware`, build flags including `-e CONVERT_TO=…`.
- **`13-drivers-lowlevel.md`** — GPIO abstraction (required for converter compatibility), ADC (and the `A0` ambiguity), I²C/SPI/UART/serial driver config (incl. RP2040 `mcuconf.h` keys), eeprom/flash, ws2812/apa102, all IS31FL*/SNLED27351/AW20216S LED drivers, battery driver.
- **`15-flashing-debugging.md`** — DFU/UF2/Caterina/STM32duino/tinyuf2 bootloaders, ISP flashing, AVR & ARM debugging (SWD on Proton C `A13`/`A14`), squeezing AVR size.
- **`10-connectivity.md`** — split serial driver selection (SIO vs PIO on RP2040), VBUS detection, wireless constraints.
- **`01-architecture.md`** — where matrix scan / `matrix_scan_*` / debounce sit in the main loop; `process_record` chain (unaffected by custom matrix).

---

### Top gotchas found (for the master index)
- **Pin-naming is platform-specific and silently breaks across swaps:** AVR `B0`/`D7` (ports ≤ 7 bits — `B12` impossible), STM32 `A0`/`B12`/`C13`, RP2040 `GPx` (datasheet GPIO #, **not** silkscreen #). QMK uses **single-letter** form everywhere — **never** `PB0`/`PA0`. See `03-config-and-info-json.md` §10. **This is the #1 trap when converting Pro Micro → Proton C / RP2040.**
- **Proton C / Blackpill / RP2040 are 3.3 V** (RP2040 explicitly *not* 5 V tolerant); Proton C's VCC/RAW short on Gherkin-style PCBs can **damage the MCU** — leave RAW disconnected.
- **Blackpill `C13`/`C14`/`C15` are input-current-limited** → don't use as COL2ROW row pins (rows sink current); `A11`/`A12`/`B2`/`VBAT`/`NRST` unusable; `A9`/`A10` break DFU/USB.
- **Custom matrix full-replacement mode has mandatory calls** — `matrix_init_kb()`/`matrix_scan_kb()` (and `debounce(...)`/`debounce_init()` unless HW debouncing). Omitting them silently breaks keymaps. Prefer `CUSTOM_MATRIX = lite` (2 functions).
- **Converters can't do USB-USB host on ARM**, force software-PWM backlight, and give only "partial" split support; STeMCell has two pinout versions (default = v2.0.0 only); Svlinky loses 2 analog GPIO to the VIK FPC.
- **Proprietary vendor libs are categorically unbannable-into-QMK** — Nordic SoftDevice, ST BT, WCH CH582, WB32 ISP — *despite* SVC/loader/binary workarounds, because GPL tests functional integration in a monolithic bare-metal binary. This is why QMK's wireless story is limited (ZMK is the usual recommendation).
- **RP2040 external flash needs a matched second-stage bootloader** (default W25Q080; `RP2040_FLASH_*` defines) or it won't boot; double-tap-reset-to-UF2 is default **only** for the Pro Micro RP2040 board.
- **`qmk import-kbfirmware` / Keyboard Firmware Builder are stale** (early-2017 QMK) — `qmk new-keyboard` is the supported scaffolding path; Easy Maker (direct pin) is for one-offs only.
- **`matrix_pins` dimensions are inferred from array lengths**, and `matrix_pins.direct` **overrides + ignores** `cols`/`rows`/`diode_direction` — don't set them together.
