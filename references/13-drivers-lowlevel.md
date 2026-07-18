# 13 — Low-Level Drivers (Buses, GPIO, Storage, Peripherals, LED/RGB ICs)

> The authoritative reference for QMK's hardware drivers: communication buses (I2C/SPI/UART/serial), GPIO & ADC, storage (EEPROM/flash/wear-leveling), peripherals (WS2812/APA102/audio/battery), and the consolidated LED/RGB matrix driver-IC table.
>
> **What this file is authoritative for:** the driver-string → IC mapping, I²C/SPI/bus C APIs, EEPROM/flash backends and wear-leveling sizes, and the full per-IC LED-driver table that `07-led-rgb-backlight.md` cross-references.
>
> **Relationships:** RGB/LED matrix *usage* (animations, effects, the `rgb_matrix`/`led_matrix` user APIs) lives in `07-led-rgb-backlight.md` — it points here for the chip-level driver config. Data-driven `info.json` driver keys (`rgb_matrix.driver`, `led_matrix.driver`, `ws2812.driver`, `eeprom.driver`, etc.) are documented in `03-config-and-info-json.md`. The **serial** driver here is the *split-transport* wire protocol — the split feature itself (sync, halves, transport selection) is in `10-connectivity.md`. Pin naming / alternate-function conventions and per-MCU platform details are in `12-hardware-platforms.md`.

---

## Table of contents

- [A. Communication buses](#a-communication-buses)
  - [A.1 I2C master](#a1-i2c-master)
  - [A.2 SPI master](#a2-spi-master)
  - [A.3 UART](#a3-uart)
  - [A.4 Serial — the split-transport driver](#a4-serial--the-split-transport-driver)
- [B. GPIO & ADC](#b-gpio--adc)
  - [B.1 GPIO control](#b1-gpio-control)
  - [B.2 ADC (analog)](#b2-adc-analog)
- [C. Storage (EEPROM & Flash)](#c-storage-eeprom--flash)
  - [C.1 EEPROM driver backends](#c1-eeprom-driver-backends)
  - [C.2 Wear-leveling (logical/backing sizes)](#c2-wear-leveling-logicalbacking-sizes)
  - [C.3 FLASH driver (SPI NOR)](#c3-flash-driver-spi-nor)
- [D. Peripherals](#d-peripherals)
  - [D.1 WS2812](#d1-ws2812)
  - [D.2 APA102](#d2-apa102)
  - [D.3 Audio driver](#d3-audio-driver)
  - [D.4 Battery driver](#d4-battery-driver)
- [E. LED/RGB matrix driver ICs (consolidated table + per-IC detail)](#e-ledrgb-matrix-driver-ics)

---

## A. Communication buses

I2C, SPI, and UART in QMK are **per-bus configured** hardware-master drivers (one peripheral instance per build by default). They are most often pulled in automatically by a feature that needs them (OLED, an LED-matrix IC, EEPROM, etc.). The **serial** driver is a *different thing*: it is QMK's split-keyboard inter-half transport (see `10-connectivity.md`), not the UART/USART API.

Common standalone-enable pattern (only needed when no feature pulls the bus in for you):

```make
I2C_DRIVER_REQUIRED = yes      # pulls in i2c_master
SPI_DRIVER_REQUIRED = yes      # pulls in spi_master
UART_DRIVER_REQUIRED = yes     # pulls in uart
```

Then `#include "i2c_master.h"` / `"spi_master.h"` / `"uart.h"`.

### A.1 I2C master

**Summary.** MCU-agnostic I²C master used by OLED, LED-matrix ICs, I²C EEPROMs, etc. Pin/instance config differs by platform; the C API is portable.

**AVR.** No special setup; connect SDA/SCL. Only `F_SCL` (default `400000` Hz) is configurable.

| MCU | SCL | SDA |
|---|---|---|
| ATmega16/32U4, AT90USB64/128 | D0 | D1 |
| ATmega32A | C0 | C1 |
| ATmega328/P | C5 | C4 |

**ARM (ChibiOS).** Enable I²C in `halconf.h` (`HAL_USE_I2C TRUE`) and the chosen peripheral in `mcuconf.h` (e.g. `STM32_I2C_USE_I2C2 TRUE`). Defaults match Proton-C / STM32F303.

| `config.h` override | Default | Meaning |
|---|---|---|
| `I2C_DRIVER` | `I2CD1` | I²C peripheral: I2C1→`I2CD1`, I2C2→`I2CD2`, … |
| `I2C1_SCL_PIN` / `I2C1_SDA_PIN` | `B6` / `B7` | SCL/SDA pins |
| `I2C1_SCL_PAL_MODE` / `I2C1_SDA_PAL_MODE` | `4` | Alternate-function mode |

> Only a single I²C peripheral is supported; the `I2C1_*` defines configure it regardless of which `I2C_DRIVER` is selected.

`mcuconf.h` knobs: `STM32_I2C_BUSY_TIMEOUT` (ms, default `50`), `STM32_I2C_USE_DMA` (default `TRUE`), plus expert IRQ/DMA priority settings.

**I2C LLD variants** (clock/timing registers, dictated by MCU family):

- **I2Cv1** — STM32F1xx, F2xx, F4xx, L0xx, L1xx. Knobs: `I2C1_OPMODE`=`OPMODE_I2C`, `I2C1_CLOCK_SPEED`=`100000`, `I2C1_DUTY_CYCLE`=`STD_DUTY_CYCLE`.
- **I2Cv2** — STM32F0xx, F3xx, F7xx, L4xx. Knobs: `I2C1_TIMINGR_PRESC`=`0U`, `_SCLDEL`=`7U`, `_SDADEL`=`0U`, `_SCLH`=`38U`, `_SCLL`=`129U`.

**I²C addressing (critical).** All API `address` parameters expect the 7-bit address **shifted into the upper 7 bits**; the driver sets the R/W bit. Datasheet addresses are 7-bit. Always shift left by 1:

```c
#define MY_I2C_ADDRESS (0x18 << 1)
```

**C API** (`i2c_master.h`). All return `i2c_status_t`: `I2C_STATUS_SUCCESS`, `I2C_STATUS_TIMEOUT`, `I2C_STATUS_ERROR`. `timeout` is in ms.

| Function | Purpose |
|---|---|
| `void i2c_init(void)` | Initialize once, weakly defined (override to set up pins/AF manually). |
| `i2c_status_t i2c_transmit(uint8_t address, const uint8_t* data, uint16_t length, uint16_t timeout)` | Send `length` bytes. |
| `i2c_status_t i2c_transmit_P(...)` | PROGMEM transmit (AVR); alias of `i2c_transmit` on ARM. |
| `i2c_status_t i2c_receive(uint8_t address, uint8_t* data, uint16_t length, uint16_t timeout)` | Receive `length` bytes. |
| `i2c_status_t i2c_transmit_and_receive(uint8_t address, const uint8_t* tx, uint16_t tx_len, uint8_t* rx, uint16_t rx_len, uint16_t timeout)` | Send then receive. |
| `i2c_status_t i2c_write_register(uint8_t devaddr, uint8_t regaddr, const uint8_t* data, uint16_t length, uint16_t timeout)` | Write 8-bit-addressed register. |
| `i2c_status_t i2c_write_register16(uint8_t devaddr, uint16_t regaddr, const uint8_t* data, uint16_t length, uint16_t timeout)` | Write 16-bit-**big-endian**-addressed register. |
| `i2c_status_t i2c_read_register(uint8_t devaddr, uint8_t regaddr, uint8_t* data, uint16_t length, uint16_t timeout)` | Read 8-bit-addressed register. |
| `i2c_status_t i2c_read_register16(uint8_t devaddr, uint16_t regaddr, uint8_t* data, uint16_t length, uint16_t timeout)` | Read 16-bit-big-endian-addressed register. |
| `i2c_status_t i2c_ping_address(uint8_t address, uint16_t timeout)` | Ping address; weakly defined. |

#### Gotchas (I2C)
- **Address must be pre-shifted `<< 1`.** Forgetting this is the #1 silent failure. I²C EEPROMs' datasheet `0b01010000` must become `0b10100000` for `EXTERNAL_EEPROM_I2C_BASE_ADDRESS`.
- ATmega16/32U2 has **no I²C** — cannot use this driver.
- Only **one** I²C peripheral instance is supported at a time; config keys are always `I2C1_*` even when `I2C_DRIVER`=`I2CD2`.
- `i2c_ping_address` on ChibiOS does a "best effort" register-0 read — devices that don't answer a register-0 read produce **false negatives**.
- I2Cv1 vs I2Cv2 timing knobs are different sets; pick by MCU family.

### A.2 SPI master

**Summary.** MCU-agnostic SPI master for OLED (SPI), SPI EEPROMs/flash, AW20216S, WS2812-over-SPI, etc.

**AVR.** No setup; connect SS/SCK/MOSI/MISO. You may use any GPIO as an additional slave-select; `SPI_SS_PIN` is a convenient alias.

| MCU | SS | SCK | MOSI | MISO |
|---|---|---|---|---|
| ATmega16/32U2/4, AT90USB64/128/162 | B0 | B1 | B2 | B3 |
| ATmega32A | B4 | B7 | B5 | B6 |
| ATmega328/P | B2 | B5 | B3 | B4 |

**ARM (ChibiOS).** Enable SPI in `halconf.h` (`HAL_USE_SPI TRUE`) + peripheral in `mcuconf.h` (`STM32_SPI_USE_SPI2 TRUE`). Defaults match Proton-C.

| `config.h` override | Default | Meaning |
|---|---|---|
| `SPI_DRIVER` | `SPID2` | SPI1→`SPID1`, SPI2→`SPID2`, … |
| `SPI_SCK_PIN` / `SPI_SCK_PAL_MODE` | `B13` / `5` | SCK pin + AF |
| `SPI_MOSI_PIN` / `SPI_MOSI_PAL_MODE` | `B15` / `5` | MOSI pin + AF |
| `SPI_MISO_PIN` / `SPI_MISO_PAL_MODE` | `B14` / `5` | MISO pin + AF |

Disable unused pins: `#define SPI_MISO_PIN NO_PIN`, `#define SPI_MOSI_PIN NO_PIN`, and in `mcuconf.h` `#define SPI_SELECT_MODE SPI_SELECT_MODE_NONE` (then `spi_start()`'s `slavePin` may be `NO_PIN`).

**C API** (`spi_master.h`). `spi_status_t`: `SPI_STATUS_SUCCESS`, `SPI_STATUS_TIMEOUT`, `SPI_STATUS_ERROR`.

| Function | Purpose |
|---|---|
| `void spi_init(void)` | Initialize once. |
| `bool spi_start(pin_t slavePin, bool lsbFirst, uint8_t mode, uint16_t divisor)` | Start transaction; asserts SS. |
| `spi_status_t spi_write(uint8_t data)` | Write one byte. |
| `spi_status_t spi_read(void)` | Read one byte (returns the byte, or `SPI_STATUS_TIMEOUT`). |
| `spi_status_t spi_transmit(const uint8_t *data, uint16_t length)` | Send buffer. |
| `spi_status_t spi_receive(uint8_t *data, uint16_t length)` | Receive buffer. |
| `void spi_stop(void)` | End transaction; deasserts SS, resets mode/divisor. |

`spi_start()` **mode** (CPOL/CPHA): `0` rising/sample-leading, `1` rising/sample-trailing, `2` falling/sample-leading, `3` falling/sample-trailing. **divisor** is rounded up to a power of two = `MCU_clock / desired_SPI_clock`.

#### Gotchas (SPI)
- `divisor` is rounded **up to the nearest power of two** — you can't hit arbitrary SPI clocks.
- You can share the bus across multiple SS pins, but only one transaction at a time (`spi_start`→…→`spi_stop`).
- WS2812-over-SPI and the SPI AW20216S each have their own `*_SPI_DRIVER`/divisor overrides that **bypass** the generic `SPI_*` config (see §D.1 / §E).

### A.3 UART

**Summary.** MCU-agnostic UART driver. **No hardware flow control** (RTS/CTS) is currently supported. Most often used for host-side comms / modules; the split transport uses the separate *serial* driver (§A.4).

**AVR.** No setup. Connect device RX↔MCU TX and device TX↔MCU RX.

| MCU | TX | RX | CTS | RTS |
|---|---|---|---|---|
| ATmega16/32U2 | D3 | D2 | D7 | D6 |
| ATmega16/32U4 | D3 | D2 | D5 | B7 |
| AT90USB64/128 | D3 | D2 | — | — |
| ATmega32A / 328P | D1 | D0 | — | — |

**ARM (ChibiOS).** Enable USART in `mcuconf.h` (e.g. `STM32_SERIAL_USE_USART2 TRUE`). Defaults match Proton-C.

| `config.h` override | Default | Meaning |
|---|---|---|
| `UART_DRIVER` | `SD1` | USART1→`SD1`, USART2→`SD2`, … |
| `UART_TX_PIN` / `_PAL_MODE` | `A9` / `7` | TX + AF |
| `UART_RX_PIN` / `_PAL_MODE` | `A10` / `7` | RX + AF |
| `UART_CTS_PIN` / `_PAL_MODE` | `A11` / `7` | CTS + AF (not currently used) |
| `UART_RTS_PIN` / `_PAL_MODE` | `A12` / `7` | RTS + AF (not currently used) |

**C API** (`uart.h`):

| Function | Purpose |
|---|---|
| `void uart_init(uint32_t baud)` | Initialize once. |
| `void uart_write(uint8_t data)` | Send one byte. |
| `uint8_t uart_read(void)` | Receive one byte — **blocks** if buffer empty. |
| `void uart_transmit(const uint8_t *data, uint16_t length)` | Send buffer. |
| `void uart_receive(char *data, uint16_t length)` | Receive buffer. |
| `bool uart_available(void)` | `true` if RX buffer has data. |

#### Gotchas (UART)
- No flow control. RTS/CTS pins are documented but the driver doesn't drive them.
- `uart_read()` **blocks** when no data is available — always check `uart_available()` first in non-blocking code.
- "UART" here is the host/module API. The split-half "serial" wire (§A.4) is a *separate* driver even though both reuse USART hardware.

### A.4 Serial — the split-transport driver

**Summary.** The **serial** driver powers the split-keyboard feature — bit-by-bit comms between two halves over a TRS/TRRS cable. It is **not** the UART API and **not** more than two halves. Full split config (transport selection, sync, halves) is in `10-connectivity.md`; this section covers the driver-internal options.

> "Serial" here means *sending one bit at a time*, not UART/USART/RS232/RS485 standards.

| Driver | AVR | ARM | Wiring |
|---|:---:|:---:|---|
| **Bitbang** (default) | ✅ | ✅ | Single wire, RX+TX shared. |
| **USART Half-duplex** | — | ✅ | Single wire via USART; needs external pull-up (1.5k–8.2kΩ) except RP2040. |
| **USART Full-duplex** | — | ✅ | Two wires (TX/RX crossed); most efficient; needs TRRS. |

Select via `rules.mk`: `SERIAL_DRIVER = bitbang` | `usart` | `vendor` (`vendor` = RP2040 PIO).

- **Bitbang:** `#define SOFT_SERIAL_PIN D0` (D0/D1/D2/D3/E6 on AVR). On ARM also set `#define PAL_USE_CALLBACKS TRUE` in `halconf.h`.
- **Half-duplex (usart):** `#define SERIAL_USART_TX_PIN B6`; STM32 `SERIAL_USART_TX_PAL_MODE` (default 7) and optional `USART1_REMAP`.
- **Full-duplex (usart):** `#define SERIAL_USART_FULL_DUPLEX`, `SERIAL_USART_TX_PIN`, `SERIAL_USART_RX_PIN`; optional `SERIAL_USART_PIN_SWAP` (some MCUs only), `USART1_REMAP`.
- **RP2040 PIO (`vendor`):** any GPIO can be TX/RX; built-in pull-ups mean **no external pull-up needed**; optionally `#define SERIAL_PIO_USE_PIO1`. Uses 2 state machines, 13 instructions, full IRQ handler of one PIO.

**Subsystem choice (ARM `usart`/`vendor`):** ChibiOS `SERIAL` (most MCUs, `SDn`, `HAL_USE_SERIAL`), `SIO` (newer MCUs only, `SIODn`, `HAL_USE_SIO`), or RP2040 `PIO`. Override with `#define SERIAL_USART_DRIVER SD3` (or `SIOD3`).

**Advanced (`config.h`):**

| Define | Effect |
|---|---|
| `SELECT_SOFT_SERIAL_SPEED n` | Baudrate preset. Bitbang: `0`=189000¹, `1`=137000 (default), `2`=75000, `3`=39000, `4`=26000, `5`=20000. Half/Full-duplex: `0`=460800, `1`=230400 (default), `2`=115200, `3`=57600, `4`=38400, `5`=19200. |
| `SERIAL_USART_SPEED` | Specify baudrate directly (alternative). |
| `SERIAL_USART_TIMEOUT` | Driver timeout ms (default `20`). |
| `SERIAL_DEBUG` | Print debug to `CONSOLE` when transactions fail. |

#### Gotchas (serial)
- **Max two halves.** No driver supports 3+ halves.
- On ARM, **bitbang serial + bitbang WS2812 together cause connection issues** — prefer non-bitbang for both.
- Half-duplex needs an **external pull-up (1.5k–8.2kΩ)** to keep the line high, *unless* it's RP2040 PIO.
- Full-duplex TX↔RX crossover usually must be done outside the MCU (cable/PCB); a few MCUs (STM32F303) can swap internally.
- STM32F103 needs **no AF config** (already set); only `USARTn_REMAP` defines matter.

---

## B. GPIO & ADC

### B.1 GPIO control

**Summary.** MCU-agnostic GPIO macros in `platforms/<platform>/gpio.h`. Pin naming/AF conventions are in `12-hardware-platforms.md`.

| Macro | Description |
|---|---|
| `gpio_set_pin_input(pin)` | Input, high-Z. |
| `gpio_set_pin_input_high(pin)` | Input + internal pull-up. |
| `gpio_set_pin_input_low(pin)` | Input + internal pull-down (**unavailable on AVR**). |
| `gpio_set_pin_output(pin)` | Output, push-pull (alias of `_push_pull`). |
| `gpio_set_pin_output_push_pull(pin)` | Output push-pull. |
| `gpio_set_pin_output_open_drain(pin)` | Output open-drain (**unavailable on AVR**). |
| `gpio_write_pin_high(pin)` / `gpio_write_pin_low(pin)` / `gpio_write_pin(pin, level)` | Drive output. |
| `gpio_read_pin(pin)` | Return pin level. |
| `gpio_toggle_pin(pin)` | Invert output level. |

For advanced/architecture-specific access (AVR `avr/io.h`; STM32 ChibiOS PAL — `palReadLine`, `palSetPadMode`, `PAL_MODE_ALTERNATE(n)`, etc.) consult the MCU datasheet/PAL docs directly; the abstraction does not block those calls.

**Atomicity.** GPIO macros are **not guaranteed atomic**. Wrap multi-step critical sections:

```c
ATOMIC_BLOCK_FORCEON {
    // interrupts disabled here; re-enabled after block
}
```

(`ATOMIC_BLOCK_FORCEON` forces interrupts off before the block and re-enables them after — only safe if it's OK to leave interrupts enabled on exit.)

#### Gotchas (GPIO)
- `gpio_set_pin_input_low` and `gpio_set_pin_output_open_drain` do **not exist on AVR**.
- Not atomic by default — use `ATOMIC_BLOCK_FORCEON` for read-modify-write sequences shared with ISRs.

### B.2 ADC (analog)

**Summary.** Reads voltages on ADC-capable pins (battery level, potentiometers, etc.). 10-bit results (0–1023) by default, mapped 0V→VCC (5V or 3.3V on AVR; 3.3V on ARM). ARM has extra precision/behavior knobs. Enable: `rules.mk` `ANALOG_DRIVER_REQUIRED = yes`, then `#include "analog.h"`.

**Channel maps.** AVR:

| Ch | AT90USB64/128 | ATmega16/32U4 | ATmega32A | ATmega328/P |
|---|---|---|---|---|
| 0–7 | F0–F7 | F0–F7 | A0–A7 | C0–C5 (C6/C7 not on DIP) |
| 8–13 | — | D4,D6,D7,B4,B5,B6 | — | — |

ARM (STM32) — abbreviated (consult datasheet; pins double up across ADCs):

| ADC.Ch | F0xx | F1xx | F3xx | F4xx |
|---|---|---|---|---|
| 1.0–1.7 | A0–A7 / B0,B1,C0,C1 | A0–A7,B0,B1,C0,C1 | A0–A3,F4,C0,C1,C2,C3 | A0–A7,B0,B1,C0–C5 |
| 2.x | — | (ADC2 unsupported¹) | A4–A7,C0–C5,B2 | A0–A7² |
| 3.x | — | (ADC3 unsupported¹) | B1,E9,E13,B13,E8,D10–D14,B0,E7,E10–E12 | A1–A3,F3,F4–F10² |
| 4.x | — | — | E14,E15,B12,B14,B15,E8,D8–D14 | — |

¹ As of ChibiOS 20.3.4, STM32F1xx ADC driver supports **only ADC1** — ADC2/3 and pins F6–F10 are unusable.
² Not all STM32F4xx have ADC2/3; pins F4–F10 need ADC3 which may be absent — check datasheet.

**RP2040:** single ADC (`ADCD1`, index 0): channels 0–3 = GP26–GP29; channel 4 = internal temperature sensor (disabled by default; enable via `adcRPEnableTS(&ADCD1)` after ADC init).

**API:**

| Function | AVR | ARM |
|---|---|---|
| `analogReference(mode)` | ✅ `ADC_REF_EXTERNAL`/`_POWER`/`_INTERNAL` | — |
| `analogReadPin(pin)` | ✅ | ✅ (picks lower-numbered ADC if pin usable by several) |
| `analogReadPinAdc(pin, adc)` | — | ✅ ADCs are **0-indexed** here |
| `pinToMux(pin)` | ✅ | ✅ |
| `adc_read(mux)` | ✅ | ✅ |

**ARM-only config (`config.h`):**

| Define | Default | Meaning |
|---|---|---|
| `ADC_CIRCULAR_BUFFER` | `false` | Use circular buffer. |
| `ADC_NUM_CHANNELS` | `1` | Channels per scan (only `1` supported). |
| `ADC_BUFFER_DEPTH` | `2` | Bytes per result. |
| `ADC_SAMPLING_RATE` | `ADC_SMPR_SMP_1P5` | Fastest by default. |
| `ADC_RESOLUTION` | `ADC_CFGR1_RES_10BIT` / `ADC_CFGR_RES_10BITS` | 12/10/8/6-bit; name varies by MCU. |

#### Gotchas (ADC)
- STM32F1xx: only **ADC1** works (ChibiOS driver limitation).
- STM32F4xx: pins F4–F10 need ADC3, which is missing on many parts.
- `analogReadPinAdc`'s `adc` arg is **0-indexed**; the channel tables above use 1-indexed ADCs for STM32F3.
- RP2040 temp sensor needs explicit enable + a prior (dummy) conversion to ensure ADC init.

---

## C. Storage (EEPROM & Flash)

EEPROM holds persistent keyboard state (layers, rgblight, etc.). The backend is swappable in `rules.mk` via `EEPROM_DRIVER` (data-driven: `eeprom.driver`, see `03-config-and-info-json.md`).

### C.1 EEPROM driver backends

| `EEPROM_DRIVER` | Description |
|---|---|
| `vendor` (default) | On-chip. AVR = avr-libc. ARM: STM32F3xx/F1xx/F072xB = flash-emulated; STM32L0xx/L1xx = true on-chip EEPROM; everything else behaves like `transient`. |
| `i2c` | External 24xx-series I²C EEPROM. Needs working I²C config. |
| `spi` | External 25xx-series SPI EEPROM/FRAM. Needs working SPI config. |
| `transient` | RAM-only, lost on power loss. |
| `wear_leveling` | Frontend over the wear-leveling system (in-MCU or external SPI NOR flash). |

**Vendor — STM32L0/L1:** `STM32_ONBOARD_EEPROM_SIZE` (default: min for eeconfig, or `1024` if VIA). ⚠️ Reset takes up to **1 second per kB** of internal EEPROM.

**I²C (24xx)** — `config.h` overrides (defaults shown):

| Override | Default | Meaning |
|---|---|---|
| `EXTERNAL_EEPROM_I2C_BASE_ADDRESS` | `0b10100000` | Base addr, **shifted <<1** per i2c_master. |
| `EXTERNAL_EEPROM_I2C_ADDRESS(addr)` | base | Per-address calc. |
| `EXTERNAL_EEPROM_BYTE_COUNT` | `8192` | Total bytes. |
| `EXTERNAL_EEPROM_PAGE_SIZE` | `32` | Page size (datasheet). |
| `EXTERNAL_EEPROM_ADDRESS_SIZE` | `2` | Mem-addr bytes. |
| `EXTERNAL_EEPROM_WRITE_TIME` | `5` | Write-cycle time (ms). |
| `EXTERNAL_EEPROM_WP_PIN` | — | If set, toggled on write (use external pull-up). |

Pre-defined modules: `EEPROM_I2C_CAT24C512`, `EEPROM_I2C_RM24C512C`, `EEPROM_I2C_24LC32A`, `EEPROM_I2C_24LC64`, `EEPROM_I2C_24LC128`, `EEPROM_I2C_24LC256`, `EEPROM_I2C_MB85RC256V` (FRAM).

**SPI (25xx)** — `config.h` overrides: `EXTERNAL_EEPROM_SPI_SLAVE_SELECT_PIN` (none), `EXTERNAL_EEPROM_SPI_CLOCK_DIVISOR` (`64`), `EXTERNAL_EEPROM_BYTE_COUNT` (`8192`), `EXTERNAL_EEPROM_PAGE_SIZE` (`32`), `EXTERNAL_EEPROM_ADDRESS_SIZE` (`2`). Pre-defined: `EEPROM_SPI_MB85RS64V` (FRAM). ⚠️ **No way to detect a missing SPI EEPROM** — reads silently return zeros.

**Transient:** only `TRANSIENT_EEPROM_SIZE` (default `64`).

#### Gotchas (EEPROM backends)
- I²C EEPROM address must be **pre-shifted `<<1`** (e.g. datasheet `0b01010000` → define `0b10100000`). Most common I²C EEPROM bug.
- SPI EEPROM: a missing/non-responding chip reads as **all zeros** with no error.
- STM32L0/L1 EEPROM reset is **slow** (~1 s/kB).
- Some vendors recommend **against** hardcoding WP to ground (brown-out protection); if WP is configured, add an external pull-up.

### C.2 Wear-leveling (logical/backing sizes)

**Summary.** `EEPROM_DRIVER = wear_leveling` is a frontend; the actual store is one of these **backing drivers** selected by `WEAR_LEVELING_DRIVER` in `rules.mk`:

| `WEAR_LEVELING_DRIVER` | Backing store |
|---|---|
| `embedded_flash` | In-MCU flash (last sectors). |
| `spi_flash` | External SPI NOR flash (needs FLASH driver, §C.3). |
| `rp2040_flash` | RP2040 code flash. |
| `legacy` | Historical emulated EEPROM; STM32F0xx/F4x1 only; **slated for deprecation**. |

⚠️ **Every wear-leveling driver requires RAM equal to the logical EEPROM size** — 32 kB logical needs 32 kB RAM, which many MCUs lack.

**Critical sizing model:** `WEAR_LEVELING_LOGICAL_SIZE` is the usable EEPROM exposed to QMK; `WEAR_LEVELING_BACKING_SIZE` is the raw flash consumed (must be a multiple of logical size). Default logical = backing/2.

**embedded_flash (`config.h`):**

| Override | Default | Meaning |
|---|---|---|
| `WEAR_LEVELING_EFL_FIRST_SECTOR` | unset (auto) | First flash sector to use. |
| `WEAR_LEVELING_EFL_FLASH_SIZE` | unset (auto) | Override available flash. **Too large → MCU won't boot.** |
| `WEAR_LEVELING_EFL_OMIT_LAST_SECTOR_COUNT` | `0` | Sectors to reserve at end (bootloader flag). |
| `WEAR_LEVELING_LOGICAL_SIZE` | `backing/2` | Usable EEPROM bytes. |
| `WEAR_LEVELING_BACKING_SIZE` | `2048` | Raw flash bytes (multiple of logical). |
| `BACKING_STORE_WRITE_SIZE` | auto | Write width; set manually if auto-detect fails. |

**spi_flash (`config.h`):**

| Override | Default | Meaning |
|---|---|---|
| `WEAR_LEVELING_EXTERNAL_FLASH_BLOCK_COUNT` | `1` | Blocks used. |
| `WEAR_LEVELING_EXTERNAL_FLASH_BLOCK_OFFSET` | `0` | First block index. |
| `WEAR_LEVELING_LOGICAL_SIZE` | `(block_count*block_size)/2` | Usable EEPROM (≤ 64 kB). |
| `WEAR_LEVELING_BACKING_SIZE` | `block_count*block_size` | Raw flash. |
| `BACKING_STORE_WRITE_SIZE` | `8` | Write width. |

**rp2040_flash (`config.h`):**

| Override | Default | Meaning |
|---|---|---|
| `WEAR_LEVELING_RP2040_FLASH_SIZE` | `PICO_FLASH_SIZE_BYTES` | Total flash. |
| `WEAR_LEVELING_RP2040_FLASH_BASE` | `flash_size-sector_size` | Backing location. |
| `WEAR_LEVELING_LOGICAL_SIZE` | `backing/2` | Usable EEPROM. |
| `WEAR_LEVELING_BACKING_SIZE` | `8192` | Raw flash (multiple of logical **and** sector size). |
| `BACKING_STORE_WRITE_SIZE` | `2` | Write width. |

**legacy (STM32F0xx/F4x1):** default `1024` bytes logical / varies flash — see table:

| MCU | EEPROM | Flash used |
|---|---|---|
| STM32F042/F070/F072 | 1024 B | 2048 B |
| STM32F401/F411 | 1024 B | 16384 B |

#### Gotchas (wear-leveling)
- **RAM cost = logical size.** Don't crank `WEAR_LEVELING_LOGICAL_SIZE` without checking RAM.
- SPI-flash logical size **hard-capped at 64 kB** (QMK EEPROM subsystem limit).
- EFL: if MCU won't boot after switching, flash size was misdetected (usually as a larger part) — override `WEAR_LEVELING_EFL_FLASH_SIZE`.
- `legacy` is deprecated; use `embedded_flash` once your MCU family is supported.

### C.3 FLASH driver (SPI NOR)

**Summary.** External SPI NOR flash backend (used by `WEAR_LEVELING_DRIVER = spi_flash`). Only one driver today: `FLASH_DRIVER = spi` in `rules.mk`.

**`config.h` overrides** (defaults based on MX25L4006E):

| Override | Default | Meaning |
|---|---|---|
| `EXTERNAL_FLASH_SPI_SLAVE_SELECT_PIN` | — | SS pin. |
| `EXTERNAL_FLASH_SPI_CLOCK_DIVISOR` | `8` | SPI clock divisor. |
| `EXTERNAL_FLASH_PAGE_SIZE` | `256` | Page bytes. |
| `EXTERNAL_FLASH_SECTOR_SIZE` | `4*1024` | Sector bytes. |
| `EXTERNAL_FLASH_BLOCK_SIZE` | `64*1024` | Block bytes. |
| `EXTERNAL_FLASH_SIZE` | `512*1024` | Total bytes. |
| `EXTERNAL_FLASH_ADDRESS_SIZE` | `3` | Address bytes. |

⚠️ These defaults are specific to MX25L4006E — override all relevant ones for a different chip.

---

## D. Peripherals

### D.1 WS2812

**Summary.** WorldSemi-style addressable RGB(W) LEDs (WS2811/2812/2812B/2812C, SK6812, SK6805). Usually driven via RGBLight/RGB Matrix; standalone: `rules.mk` `WS2812_DRIVER_REQUIRED = yes`, `#include "ws2812.h"`. Driver-string lives in `rules.mk` `WS2812_DRIVER` or info.json `ws2812.driver`.

**Driver variants** (`WS2812_DRIVER`):

| Variant | Platforms | Notes |
|---|---|---|
| `bitbang` (default) | AVR, ARM | GPIO toggling. Only realistic AVR option; long chains/heavy CPU → visible lag on AVR. |
| `i2c` | — (PS2AVRGB) | ATtiny85 on board handles LEDs. `WS2812_I2C_ADDRESS`=`0xB0`, `WS2812_I2C_TIMEOUT`=`100` ms. **No RGBW.** |
| `spi` | ARM only | DI **must** connect to MOSI; leave other SPI pins unused. Clock-dependent. |
| `pwm` | ARM only | Uses PWM+DMA. |
| `vendor` | RP2040 only | PIO+DMA; 50 ns resolution. |
| `custom` | any | User-supplied. |

**Basic config (`config.h`):**

| Define | Default | Meaning |
|---|---|---|
| `WS2812_DI_PIN` | — | Data-in pin of first LED. |
| `WS2812_LED_COUNT` | — | LED count (auto-set by RGBLight/RGB Matrix). |
| `WS2812_TIMING` | `1250` ns | Total bit length (TH+TL). |
| `WS2812_T1H` / `WS2812_T0H` | `900` / `350` ns | "1"/"0" high-phase lengths. |
| `WS2812_TRST_US` | `280` µs | Reset (latch) phase. |
| `WS2812_BYTE_ORDER` | `WS2812_BYTE_ORDER_GRB` | `GRB` (most), `RGB` (WS2812B-2020), `BGR` (TM1812). |
| `WS2812_RGBW` | — | Enable RGBW conversion (not on `i2c` driver). |
| `WS2812_T1L` / `WS2812_T0L` | `TIMING-T1H` / `TIMING-T0H` | Low-phase lengths (bitbang/PIO only). |

**5V logic levels** (WS2812 usually runs at 5V; many ARM MCUs are 3.3V):
1. **Open drain** — `#define WS2812_EXTERNAL_PULLUP` + ~10kΩ pull-up to 5V. ⚠️ DI pin is pulled to **5V**, so it **must be 5V-tolerant**.
2. **Level shifter** (e.g. SN74LV1T34) — no firmware change, no 5V-tolerant pin needed.

**SPI-driver-specific:** `WS2812_SPI_DRIVER`=`SPID1`, `WS2812_SPI_MOSI_PAL_MODE`=`5`, `WS2812_SPI_SCK_PIN`/`_PAL_MODE` (required for F072+), `WS2812_SPI_DIVISOR`=`16` (only 2/4/8/16/32/64/128/256 on STM32), `WS2812_SPI_USE_CIRCULAR_BUFFER` (anti-flicker).

**PWM-driver-specific:** enable PWM in halconf/mcuconf (`STM32_PWM_USE_TIM2`). `WS2812_PWM_DRIVER`=`PWMD2`, `WS2812_PWM_CHANNEL`=`2`, `WS2812_PWM_PAL_MODE`=`2`, `WS2812_PWM_DMA_STREAM`=`STM32_DMA1_STREAM2`, `WS2812_PWM_DMA_CHANNEL`=`2`, `WS2812_PWM_DMAMUX_ID` (DMAMUX MCUs only), `WS2812_PWM_COMPLEMENTARY_OUTPUT` (`TIMx_CHyN`, advanced timers 1/8/20 only).

**PIO-driver-specific:** `WS2812_PIO_USE_PIO1` (force PIO1 over PIO0).

**RGBW conversion:** `w = min(r,g,b); r-=w; g-=w; b-=w;` so `255,255,255` → `0,0,0,255`.

**C API** (`ws2812.h`): `void ws2812_init(void)`, `void ws2812_set_color(int index, uint8_t r, uint8_t g, uint8_t b)`, `void ws2812_set_color_all(uint8_t r, uint8_t g, uint8_t b)`, `void ws2812_flush(void)` (set_color is buffered; flush to push).

#### Gotchas (WS2812)
- 3.3V MCU → 5V LEDs is unreliable; use open-drain+pullup (on a **5V-tolerant** pin) or a level shifter.
- Byte order varies by LED variant — wrong colors usually mean wrong `WS2812_BYTE_ORDER`.
- `i2c` WS2812 driver (PS2AVRGB) does **not** support RGBW.
- AVR bitbang lags on long chains; on ARM, bitbang serial + bitbang WS2812 together break (see §A.4).
- SPI divisor is power-of-two constrained on STM32.

### D.2 APA102

**Summary.** APA102 addressable RGB LEDs — like WS2812 but higher data/refresh rates; uses a 2-wire (data + clock) protocol. Standalone: `rules.mk` `APA102_DRIVER_REQUIRED = yes`, `#include "apa102.h"`.

**Config (`config.h`):**

| Define | Default | Meaning |
|---|---|---|
| `APA102_DI_PIN` | — | Data-in pin. |
| `APA102_CI_PIN` | — | Clock-in pin. |
| `APA102_DEFAULT_BRIGHTNESS` | `31` | Global brightness 0–31. |

**C API** (`apa102.h`): `void apa102_init(void)`, `void apa102_set_color(uint16_t index, uint8_t r, uint8_t g, uint8_t b)`, `void apa102_set_color_all(uint8_t r, uint8_t g, uint8_t b)`, `void apa102_flush(void)`, `void apa102_set_brightness(uint8_t brightness)` (0–31).

### D.3 Audio driver

**Summary.** The hardware backend for the audio feature (songs/notes). The audio *core* handles playback; the driver handles the hardware specifics. Driver selected via `rules.mk` `AUDIO_DRIVER`. The audio *feature*/keycodes live in `09-audio-haptic.md`.

**AVR:** only `pwm_hardware` (default). Two PWM pin groups via Timer3 (C4/C5/C6) and Timer1 (B4/B5/B7); one or two speakers.

**ARM drivers** (`AUDIO_DRIVER`):

| Driver | Timers/pins (1 = primary speaker, 2 = secondary) |
|---|---|
| `dac_basic` (default ARM) | DAC1=A4 (TIM6) + DAC2=A5 (TIM7); state timer TIM8 (`AUDIO_STATE_TIMER`, e.g. `GPTD9`). One or two piezos. |
| `dac_additive` | Single timer (TIM6) triggers DAC; state updates in DAC callback. A4/A5 piezo. |
| `pwm_software` | PWMD1/TIM1_CH1 callback toggles `AUDIO_PIN` (and `AUDIO_PIN_ALT` inversely if `AUDIO_PIN_ALT_AS_NEGATIVE`). |
| `pwm_hardware` | Hardware square wave on `AUDIO_PIN` (e.g. A8 = TIM1_CH1 on F103). Configure `AUDIO_PWM_DRIVER`, `AUDIO_PWM_CHANNEL`, `AUDIO_PWM_PAL_MODE` (GPIOv2/v3), optional `AUDIO_PWM_COMPLEMENTARY_OUTPUT`. |

Enable the HAL bits in `halconf.h`/`mcuconf.h` accordingly: `HAL_USE_DAC`+`HAL_USE_GPT` (DAC drivers) or `HAL_USE_PWM`+`HAL_USE_PAL` (PWM drivers), plus the relevant `STM32_DAC_USE_DAC1_CHn`, `STM32_GPT_USE_TIMx`, `STM32_PWM_USE_TIMx`.

**DAC config (`config.h`):**

| Define | Default | Meaning |
|---|---|---|
| `AUDIO_DAC_SAMPLE_MAX` | `4095U` | 12-bit ceiling; lower = quieter. |
| `AUDIO_DAC_OFF_VALUE` | `SAMPLE_MAX/2` | DAC idle value. |
| `AUDIO_MAX_SIMULTANEOUS_TONES` | see presets | Tones playable at once; too high → freeze/glitch. |
| `AUDIO_DAC_SAMPLE_RATE` | see presets | Effective DAC bitrate (Hz). |
| `AUDIO_DAC_BUFFER_SIZE` | see presets | Samples per refill. |

Quality presets: `AUDIO_DAC_QUALITY_VERY_LOW` (11025 Hz / 8 tones / 64), `_LOW` (22050/4/128), `_HIGH` (44100/2/256), `_VERY_HIGH` (88200/1/256), `_SANE_MINIMUM` (16384/8/64, default).

**Validation matrix (partial):**

| Board | dac_basic | dac_additive | pwm_hw | pwm_sw |
|---|:--:|:--:|:--:|:--:|
| Atmega32U4 | n/a | n/a | ✅ | n/a |
| RP2040 | ✗ | ✗ | ✅ | ? |
| STM32F103C8 | ✗ | ✗ | ✅ | ✅ |
| STM32F303 (Proton-C) | ✅ | ✅ | ? | ✅ |
| STM32F405 | ✅ | ✅ | ✅ | ✅ |
| L0xx | ✗ (no TIM8) | ? | ? | ? |

#### Gotchas (audio)
- Driver availability is highly MCU/config dependent — the matrix is only "partially validated."
- Buffer-size trade-off: too small → CPU thrash; too large → RAM/flash exhaustion or matrix-scan pauses that drop key events (esp. additive driver).
- DAC sample rate ↑ means fewer simultaneous tones.

### D.4 Battery driver

**Summary.** Samples battery level for the battery feature (see `10-connectivity.md`). `rules.mk` `BATTERY_DRIVER_REQUIRED = yes`, driver via `BATTERY_DRIVER`.

| Driver | Notes |
|---|---|
| `adc` (default) | Battery on an ADC pin through a voltage divider. |
| `vendor` | Vendor-provided. |
| `custom` | Implement `void battery_driver_init(void)` and `uint8_t battery_driver_sample_percent(void)`. |

**`adc` driver config (`config.h`):**

| Define | Default | Meaning |
|---|---|---|
| `BATTERY_ADC_PIN` | — | Voltage-divider pin. |
| `BATTERY_ADC_REF_VOLTAGE_MV` | `3300` | ADC reference (mV). |
| `BATTERY_ADC_VOLTAGE_DIVIDER_R1` | `100` | kΩ; `0` disables. |
| `BATTERY_ADC_VOLTAGE_DIVIDER_R2` | `100` | kΩ; `0` disables. |
| `BATTERY_ADC_RESOLUTION` | `10` | Matches the ADC driver resolution. |

---

## E. LED/RGB matrix driver ICs

These are the chip-level drivers behind `rgb_matrix` and `led_matrix` (usage/effects in `07-led-rgb-backlight.md`). The **driver string** goes in info.json `rgb_matrix.driver` / `led_matrix.driver` (schema-validated; see `03-config-and-info-json.md`), or equivalently `RGB_MATRIX_DRIVER`/`LED_MATRIX_DRIVER` in `rules.mk`. Almost all are I²C; **`aw20216s` is the only SPI one**. Each supports a **maximum of 4 drivers** (driver index 0–3) and a **single-color (`-mono.c`) or RGB (`.c`)** build.

### E.1 Consolidated authoritative table

> This table is the authoritative driver-IC reference that `07-led-rgb-backlight.md` points to. All sizes are per-driver (×4 max drivers). All I²C addresses are **7-bit** (the API still wants them `<<1`).

| IC | driver string | Bus | Matrix | Max single-color | Max RGB | 7-bit I²C addresses (AD/ADDR pin(s)) | PWM res / freq | Notable flags/quirks |
|---|---|---|---|---|---|---|---|---|
| **AW20216S** | `aw20216s` | **SPI** | 18×12 | 216 | 72 | n/a (CS per driver) | 8-bit PWM + scaling | `AW20216S_CS_PIN_1/2`, shared `EN_PIN`, `SPI_MODE`=`0`, `SPI_DIVISOR`=`4`, `SCALING_MAX`=`150`, `GLOBAL_CURRENT_MAX`=`150`. RGB-matrix only (not in led_matrix enum). |
| **IS31FL3218** | `is31fl3218` | I²C | (18 outputs) | 18 | 6 | Fixed `0x54` (`IS31FL3218_I2C_ADDRESS`); no AD pin. | 8-bit | Single driver only (no `_ADDRESS_n`). `SDB_PIN`, `I2C_TIMEOUT`=`100`, `I2C_PERSISTENCE`=`0`. |
| **IS31FL3236** | `is31fl3236` | I²C | 12×3 | 36 | 12 | AD pin → `0x3C`/`0x3D`/`0x3E`/`0x3F` (GND/SCL/SDA/VCC). | 8-bit | `SDB_PIN`, timeout/persistence. No PWM-freq/sync/pull resistors. |
| **IS31FL3729** | `is31fl3729` | I²C | 16×8 (135 usable) | 135 | 45 | AD pin → `0x34`/`0x35`/`0x36`/`0x37`. | 8-bit | `PWM_FREQUENCY` (default 32 kHz; 80k/55k/32k/4k/2k/1k/500/250), `SW_PULLDOWN`, `CS_PULLUP` (de-ghosting), `GLOBAL_CURRENT`=`0x40`. **Scaling** registers. |
| **IS31FL3731** | `is31fl3731` | I²C | 16×9 (charlieplex) | 144 | 48 | AD pin → `0x74`/`0x75`/`0x76`/`0x77`. | 8-bit | `DEGHOST` flag (ghost prevention). Older "control register" scheme. Has `select_page`. |
| **IS31FL3733** | `is31fl3733` | I²C | 12×16 | 192 | 64 | ADDR1/ADDR2 → 16 addrs `0x50`–`0x5F`. | 8-bit / 8.4 kHz (B-only) | `SYNC_1..4` (master/slave/none), `PWM_FREQUENCY` (B-only: 8.4k/4.2k/26.7k/2.1k/1.05k), `SW_PULLUP`/`CS_PULLDOWN`, `GLOBAL_CURRENT`=`0xFF`. Control-register scheme. |
| **IS31FL3736** | `is31fl3736` | I²C | 12×8 | 96 | 32 | ADDR1/ADDR2 → 16 addrs `0x50`–`0x5F`. | 8-bit / 8.4 kHz (B-only) | `PWM_FREQUENCY` (B-only), `SW_PULLUP`/`CS_PULLDOWN`, `GLOBAL_CURRENT`=`0xFF`. Control-register scheme. |
| **IS31FL3737** | `is31fl3737` | I²C | 12×12 | 144 | 48 | AD pin → `0x50`/`0x55`/`0x5A`/`0x5F` (GND/SCL/SDA/VCC). | 8-bit / 8.4 kHz (B-only) | `PWM_FREQUENCY` (B-only), `SW_PULLUP`/`CS_PULLDOWN`, `GLOBAL_CURRENT`=`0xFF`. Control-register scheme. |
| **IS31FL3741** | `is31fl3741` | I²C | 39×9 | 351 | 117 | AD pin → `0x30`/`0x31`/`0x32`/`0x33`. | 8-bit / 29 kHz (A only) | `CONFIGURATION`=`1`, `PWM_FREQUENCY` (A-only: 29k/3.6k/1.8k/900), `SW_PULLUP`/`CS_PULLDOWN` (default 32kΩ), `GLOBAL_CURRENT`=`0xFF`. `driver`/regs are `uint32_t`. Control-register scheme. |
| **IS31FL3742A** | `is31fl3742a` | I²C | 30×6 | 180 | 60 | AD pin → `0x30`/`0x31`/`0x32`/`0x33`. | 8-bit / 29 kHz | `CONFIGURATION`=`0x31`, `PWM_FREQUENCY` (29k/3.6k/1.8k/900), `SW_PULLDOWN`/`CS_PULLUP` (default 8kΩ), `GLOBAL_CURRENT`=`0xFF`. **Scaling** registers. |
| **IS31FL3743A** | `is31fl3743a` | I²C | 18×11 | 198 | 66 | ADDR1/ADDR2 → 16 addrs `0x20`–`0x2F`. | 8-bit | `SYNC_1..4`, `CONFIGURATION`=`0x01`, `SW_PULLDOWN`/`CS_PULLUP` (default 2kΩ-off), `GLOBAL_CURRENT`=`0xFF`. **Scaling** registers. |
| **IS31FL3745** | `is31fl3745` | I²C | 18×8 | 144 | 48 | ADDR1/ADDR2 → 16 addrs `0x20`–`0x2F`. | 8-bit | `SYNC_1..4`, `CONFIGURATION`=`0x31`, `SW_PULLDOWN`/`CS_PULLUP` (default 2kΩ-off), `GLOBAL_CURRENT`=`0xFF`. **Scaling** registers. |
| **IS31FL3746A** | `is31fl3746a` | I²C | 18×4 | 72 | 24 | ADDR1/ADDR2 → 16 addrs `0x60`–`0x6F`. | 8-bit / 29 kHz | `CONFIGURATION`=`0x01`, `PWM_FREQUENCY` (29k/14.5k/7.25k/3.63k/1.81k/906/453), `SW_PULLDOWN`/`CS_PULLUP` (default 2kΩ-off), `GLOBAL_CURRENT`=`0xFF`. **Scaling** registers. `init(index, sync)`. |
| **SNLED27351** | `snled27351` | I²C | 16×12 | 192 | 64 | AD pin → `0x74`/`0x75`/`0x76`/`0x77` (GND/SCL/SDA/**VDDIO**). | 8-bit | Sonix IC; a modified variant is **"CKLED2001"** (old driver string, renamed to `snled27351`). `SDB_PIN`, timeout/persistence. No PWM-freq/pull/sync. Control-register scheme. |

**Two register schemes across these ICs (important for the API):**
- **Control-register ICs** (`is31fl3218`, `is31fl3236`, `is31fl3731`, `is31fl3733`, `is31fl3736`, `is31fl3737`, `is31fl3741`, `snled27351`): expose `set_led_control_register(...)` + `update_led_control_registers()`.
- **Scaling-register ICs** (`is31fl3729`, `is31fl3742a`, `is31fl3743a`, `is31fl3745`, `is31fl3746a`): expose `set_scaling_register(...)` + `update_scaling_registers()` instead.

### E.2 Common config across all I²C LED ICs

For every I²C IC above (driver string `xxx`):

| Define | Default | Meaning |
|---|---|---|
| `XXX_SDB_PIN` | — | GPIO on the drivers' shutdown pin (shared across all 4). |
| `XXX_I2C_TIMEOUT` | `100` | I²C timeout (ms). |
| `XXX_I2C_PERSISTENCE` | `0` | Retry count for I²C transactions. |
| `XXX_I2C_ADDRESS_1..4` | — | One of the `XXX_I2C_ADDRESS_*` constants per driver index (except IS31FL3218, which is a single fixed address). |
| `XXX_GLOBAL_CURRENT` | `0xFF` (or `0x40` on 3729) | 0–255 global current. |

You must also enable/configure I²C at the keyboard level on ChibiOS (`halconf.h` `HAL_USE_I2C TRUE` + `mcuconf.h` peripheral) — see §A.1.

### E.3 Common LED-mapping + C-API shape

Every IC requires a `g_<driver>_leds[]` table in `<keyboard>.c` mapping each LED index to its matrix coordinates. The struct and per-channel macros differ per IC (see each datasheet page noted in §E.1). Generic shape (RGB):

```c
const is31fl3733_led_t PROGMEM g_is31fl3733_leds[IS31FL3733_LED_COUNT] = {
/* Driver |   R        G        B   */
    {0,    SW1_CS1,  SW1_CS2,  SW1_CS3},
    // ...
};
```

Single-color (`-mono.c`) build uses one channel (`v`) instead of `r/g/b`:

```c
const is31fl3733_led_t PROGMEM g_is31fl3733_leds[IS31FL3733_LED_COUNT] = {
/* Driver |  V    */
    {0,    SW1_CS1},
    // ...
};
```

**Common API surface** (all ICs, single-color vs RGB variants noted):

| Function | Purpose |
|---|---|
| `void xxx_init(uint8_t index)` | Init driver `index` (0–3). `aw20216s_init(pin_t cs_pin)` instead; `is31fl3746a_init(uint8_t index, uint8_t sync)` takes sync. `is31fl3218_init(void)` (single IC). |
| `void xxx_write_register(uint8_t index, uint8_t reg, uint8_t data)` | Raw register write (`aw20216s`/`is31fl3218` omit `index`). |
| `void xxx_select_page(uint8_t index, uint8_t page)` | Page switch (paged ICs only: 3731/3733/3736/3737/3741/3742a/3743a/3745/3746a/snled27351). |
| `void xxx_set_color(int index, uint8_t r, uint8_t g, uint8_t b)` | Buffered color set (RGB build). |
| `void xxx_set_color_all(uint8_t r, uint8_t g, uint8_t b)` | Set all LEDs (RGB). |
| `void xxx_set_value(int index, uint8_t value)` | Buffered brightness set (single-color build). |
| `void xxx_set_value_all(uint8_t value)` | Set all (single-color). |
| `void xxx_set_led_control_register(uint8_t index, bool r, bool g, bool b)` / `(index, bool value)` | Control-register ICs only. |
| `void xxx_set_scaling_register(uint8_t index, uint8_t r, uint8_t g, uint8_t b)` / `(index, uint8_t value)` | Scaling-register ICs only. |
| `void xxx_update_pwm_buffers(uint8_t index)` | Flush PWM to driver. (`aw20216s_update_pwm_buffers(pin_t cs_pin, uint8_t index)`.) |
| `void xxx_update_led_control_registers(uint8_t index)` | Flush control regs (control-register ICs). |
| `void xxx_update_scaling_registers(uint8_t index)` | Flush scaling regs (scaling-register ICs). |

Standalone build (not via RGB/LED matrix) needs in `rules.mk`:

```make
COMMON_VPATH += $(DRIVER_PATH)/led/issi   # or $(DRIVER_PATH)/led for aw20216s / snled27351
SRC += is31fl3733.c        # RGB
# SRC += is31fl3733-mono.c # single-color
I2C_DRIVER_REQUIRED = yes  # SPI_DRIVER_REQUIRED = yes for aw20216s
```

### E.4 Per-IC quick config notes

- **AW20216S** (SPI): needs `AW20216S_CS_PIN_1` (+ `_2` for 2nd), shared `AW20216S_EN_PIN`. 18×12, 8-bit PWM + per-channel scaling. `SPI_MODE`=`0`, `SPI_DIVISOR`=`4`, `SCALING_MAX`=`150`, `GLOBAL_CURRENT_MAX`=`150`. Enable SPI at keyboard level.
- **IS31FL3731**: charlieplexed 16×9; `DEGHOST` flag; addresses `0x74`–`0x77`.
- **IS31FL3733/3736/3737/3741**: PWM-frequency knob applies **only to the `-B` variant** (3733/3736/3737) or `-A` variant (3741). `GLOBAL_CURRENT` default `0xFF`.
- **IS31FL3741** uniquely uses **`uint32_t`** for `driver`/`r`/`g`/`b`/`v` (39×9 matrix → registers exceed 8-bit).
- **IS31FL3746A** `init` takes an extra `sync` argument.
- **SNLED27351**: was **`ckled2001`** (renamed); the 4th address pin maps to **VDDIO** (not VCC). Addresses `0x74`–`0x77`.

### E.5 Gotchas (LED/RGB matrix ICs)
- **All I²C addresses in the docs are 7-bit** but the `i2c_master` API wants them `<<1`; QMK's per-IC `XXX_I2C_ADDRESS_*` constants are already the 7-bit values the driver shifts internally — set `XXX_I2C_ADDRESS_n` to one of those constants, do **not** pre-shift.
- IS31FL3218 is **single-driver only** (fixed `0x54`, no `_ADDRESS_n`, no `index` arg on most functions).
- `aw20216s` is **SPI** and appears only in the `rgb_matrix` driver enum (not `led_matrix`).
- `ws2812` is a valid `rgb_matrix.driver` but it's a chainable LED, not a matrix IC — no `led_matrix` equivalent and configured via §D.1.
- Don't confuse control-register vs scaling-register APIs — calling `update_led_control_registers()` on a scaling-register IC (e.g. 3742A/3743A/3745/3746A/3729) won't compile/exist.
- ICs 3733/3736/3737: PWM-frequency setting is **`-B` variant only**; 3741 is **`-A` only**. Setting it on the wrong variant is a no-op.
- 3733/3743A/3745 have `SYNC_n` (master/slave) multi-driver sync; wire SYNC pins together and designate exactly one master.
- `SNLED27351` is the current name for the chip previously called `CKLED2001`.
- Most ICs use `SWx`/`CSx` matrix coords; IS31FL3731 uses charlieplexed `C1_1`-style coords; SNLED27351 uses `CBx_CAy`.

---

## Cross-references

- **`07-led-rgb-backlight.md`** — RGB matrix / LED matrix *usage*: animations, effects, `rgb_matrix_*`/`led_matrix_*` user APIs, `RGB_*`/`LM_*` keycodes. Points **here** for the chip-level driver table (§E) and WS2812/APA102 config (§D).
- **`03-config-and-info-json.md`** — data-driven `info.json` schema: `rgb_matrix.driver`, `led_matrix.driver`, `ws2812.driver`, `eeprom.driver`, `*.driver` keys, and their `rules.mk` equivalents.
- **`10-connectivity.md`** — split-keyboard feature (transport selection, sync between halves). The *serial* driver in §A.4 is the wire protocol this feature uses.
- **`12-hardware-platforms.md`** — MCU families, ARM platform guides, pin naming / alternate-function conventions, porting.
- **`09-audio-haptic.md`** — audio *feature* (songs, notes, keycodes) that the audio *driver* in §D.3 backs.
