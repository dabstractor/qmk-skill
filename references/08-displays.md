# Displays & Rotary Encoders Reference — oled_driver, Quantum Painter (+lvgl/qff/qgf/rle), HD44780, ST7565, encoders

> **Scope:** Every QMK display subsystem plus rotary encoders, in one file. There are **four distinct display stacks** and **two encoder stacks** — they do not all coexist, and several only work on specific platforms. Read the "Which stack do I use?" matrix first; picking the wrong API is the most common display mistake.

Cross-references: I2C / SPI / GPIO driver setup (every display rides on these) → `13-drivers-lowlevel.md`; split sync of OLED/layer state, `is_keyboard_master()` / `is_keyboard_left()`, transport mirror → `10-connectivity.md`; main-loop task ordering and `housekeeping_task` / `matrix_scan` / `process_record` callback chains → `01-architecture.md`; info.json feature keys & EEPROM model → `03-config-and-info-json.md`; RGB matrix sharing HSV color model (note: QP colors are *not* subject to the RGB CIE curve) → `07-led-rgb-backlight.md`.

---

## 0. Which display stack do I use? (read first)

QMK has **four** display subsystems. They target different hardware and run on different platforms:

| Stack | Hardware | Transport | Platform | `rules.mk` enable | Notes |
|---|---|---|---|---|---|
| **OLED driver** (`oled_driver`) | SSD1306 / SH1106 / SH1107 monochrome OLED panels | I2C *or* SPI | AVR + ARM | `OLED_ENABLE = yes` | Most common on custom/split boards; PROGMEM `glcdfont.c` font; software 90° rotation; scrolling on SSD1306 only |
| **Quantum Painter** (`qp`) | Modern color TFTs (GC9A01/ILI9xxx/ST77xx/SSD1351), RGB OLED, and also mono OLEDs (SH1106/SSD1306/LD7032) | SPI *or* I2C | **ARM only** (no AVR) | `QUANTUM_PAINTER_ENABLE = yes` + `QUANTUM_PAINTER_DRIVERS += ...` | Standardised drawing API, QGF images + QFF fonts, RLE, optional LVGL. Heavy Flash/RAM cost |
| **HD44780** | Character LCD modules (1602A etc.), HD44780U IC | 4-bit parallel GPIO | AVR + ARM | `HD44780_ENABLE = yes` | Classic 16×2 text LCD; up to 8 custom glyphs in CGRAM |
| **ST7565** | ST7565 monochrome GLCD (e.g. Ergodox Infinity NHD-C12832A1Z) | SPI | AVR + ARM | `ST7565_ENABLE = yes` | API mirrors `oled_driver` but with `st7565_*` names and only 0°/180° rotation |

### Critical coexistence / platform rules (these bite people)

- **Quantum Painter is ARM-only.** "Due to the complexity, there is no support for Quantum Painter on AVR-based boards." On an ATmega32U4 board you must use the OLED driver (or HD44780/ST7565), not QP.
- **OLED driver vs Quantum Painter both target the same SH1106/SSD1306 silicon.** They are *alternative APIs* for the same panel — pick one. The OLED driver is the lightweight PROGMEM-font approach; Quantum Painter is the modern draw/image/font API. The QP SH1106/SSD1306 driver is even configured with `QUANTUM_PAINTER_DRIVERS += sh1106_*`.
- **Quantum Painter is NOT integrated with system suspend.** You must manually call `qp_power(display, false)` in `suspend_power_down_user` and `qp_power(display, true)` in `suspend_wakeup_init_user`. (See code under QP "Display Power".)
- **Quantum Painter image/font conversion is a build-time CLI step**, not runtime. You run `qmk painter-convert-graphics` / `qmk painter-make-font-image` + `qmk painter-convert-font-image` to emit `*.qgf.c/.h` and `*.qff.c/.h` files that are then `#include`d and added to `SRC`.
- **Encoders** (`ENCODER_ENABLE`) are independent of all display stacks; they can coexist with any of them. Encoder events normally go through `encoder_update_user`/`_kb`, *unless* `ENCODER_MAP_ENABLE = yes`, in which case they are routed through the standard keycode pipeline.

---

## 1. OLED Driver (`oled_driver`)

### Summary
Lightweight monochrome OLED driver for SSD1306, SH1106, and SH1107 ICs over I2C or SPI. Renders into a RAM framebuffer using a 6×8 PROGMEM font (`glcdfont.c`), with dirty-block rendering, optional scrolling (SSD1306 only), software 90° rotation, timeout, and fade-out. The standard display solution for most custom/split keyboards.

### Enable it
**`rules.mk`** (the canonical way — OLED is configured via `rules.mk` + `config.h`, not a rich info.json block):
```make
OLED_ENABLE = yes
OLED_DRIVER    = ssd1306     # default; same driver serves SSD1306, SH1106, SH1107
OLED_TRANSPORT = i2c         # default; or spi
```
The IC type is *not* selected by `OLED_DRIVER` (always `ssd1306`) — instead set `OLED_IC` in `config.h` for SH1106/SH1107 (see table below).

### Keycodes
None. The OLED driver has no keycodes; all interaction is via `oled_task_user()` and the `oled_*` C API.

### Basic configuration (`config.h`)
| Define | Default | Meaning |
|---|---|---|
| `OLED_BRIGHTNESS` | `255` | Default brightness, 0–255 |
| `OLED_IC` | `OLED_IC_SSD1306` | Set to `OLED_IC_SH1106` or `OLED_IC_SH1107` for those controllers |
| `OLED_COLUMN_OFFSET` | `0` | Shift output right by N pixels (e.g. center a 128-wide panel on a 132-wide SH1106) |
| `OLED_DISPLAY_CLOCK` | `0x80` | Display clock divide ratio / oscillator frequency |
| `OLED_FONT_H` | `"glcdfont.c"` | Font source file (override for custom fonts) |
| `OLED_FONT_START` | `0` | Starting glyph index |
| `OLED_FONT_END` | `223` | Ending glyph index |
| `OLED_FONT_WIDTH` | `6` | Font width in px |
| `OLED_FONT_HEIGHT` | `8` | Font height in px (untested) |
| `OLED_TIMEOUT` | `60000` | Blank the screen after this many ms of *update* inactivity (burn-in mitigation); `0` disables |
| `OLED_FADE_OUT` | *undef* | Enable fade-out animation; pair with `OLED_TIMEOUT` |
| `OLED_FADE_OUT_INTERVAL` | `0` | Fade speed 0–15 (larger = slower) |
| `OLED_SCROLL_TIMEOUT` | `0` | Auto-scroll after this many ms of OLED inactivity (burn-in); `0` disables |
| `OLED_SCROLL_TIMEOUT_RIGHT` | *undef* | If defined, scroll direction is right; left if undefined |
| `OLED_UPDATE_INTERVAL` | `0` (`50` on splits) | ms between display updates; raising helps the matrix scan rate |
| `OLED_UPDATE_PROCESS_LIMIT` | `1` | Dirty blocks rendered per loop; raising may hurt performance |

#### I2C config
| Define | Default | Meaning |
|---|---|---|
| `OLED_DISPLAY_ADDRESS` | `0x3C` | I2C 7-bit address |

#### SPI config (requires `OLED_TRANSPORT = spi`)
| Define | Default | Meaning |
|---|---|---|
| `OLED_DC_PIN` | *required* | D/C pin |
| `OLED_CS_PIN` | *required* | CS pin |
| `OLED_RST_PIN` | *undef* | RST pin (may be omitted if RST is tied) |
| `OLED_SPI_MODE` | `3` | SPI mode (rarely changed) |
| `OLED_SPI_DIVISOR` | `2` | SPI clock multiplier |

#### Custom / preset panel sizes (default is 128×32)
| Define | Default | Meaning |
|---|---|---|
| `OLED_DISPLAY_128X64` | undef | Preset for 128×64 |
| `OLED_DISPLAY_64X32` | undef | Preset for 64×32 |
| `OLED_DISPLAY_64X48` | undef | Preset for 64×48 |
| `OLED_DISPLAY_64X128` | undef | Preset for 64×128 (defaults IC to SH1107) |
| `OLED_DISPLAY_128X128` | undef | Preset for 128×128 (defaults IC to SH1107) |
| `OLED_DISPLAY_CUSTOM` | undef | Manual; requires you to define the low-level knobs below |
| `OLED_DISPLAY_WIDTH` | `128` | Panel width |
| `OLED_DISPLAY_HEIGHT` | `32` | Panel height |
| `OLED_MATRIX_SIZE` | `512` | Buffer bytes = `HEIGHT/8 * WIDTH` |
| `OLED_BLOCK_TYPE` | `uint16_t` | Unsigned int type for dirty tracking |
| `OLED_BLOCK_COUNT` | `16` | Dirty-block count = `sizeof(BLOCK_TYPE)*8` |
| `OLED_BLOCK_SIZE` | `32` | Bytes per dirty block = `MATRIX_SIZE/BLOCK_COUNT` |
| `OLED_COM_PINS` | `COM_PINS_SEQ` | SSD1306 COM-pin mapping; one of `COM_PINS_SEQ`, `COM_PINS_ALT`, `COM_PINS_SEQ_LR`, `COM_PINS_ALT_LR` |
| `OLED_COM_PIN_COUNT` | (from IC) | Number of COM pins; defaults to value for the selected `OLED_IC` |
| `OLED_COM_PIN_OFFSET` | `0` | First COM pin used |
| `OLED_SOURCE_MAP` | `{0,...N}` | Precalc source array for 90° render |
| `OLED_TARGET_MAP` | `{24,...N}` | Precalc target array for 90° render |

> **Note on 64×128 / 128×128:** these heights are *only* supported by SH1107 — defining those presets forces the SH1107 IC type.

### Supported hardware matrix
| IC | Size | Platform | Notes |
|---|---|---|---|
| SSD1306 | 128×32 | AVR | Primary support |
| SSD1306 | 128×64 | AVR | Verified |
| SSD1306 | 128×32 | ARM | |
| SSD1306 | 128×64 | ARM | Verified |
| SH1106 | 128×64 | AVR | **No scrolling** |
| SH1107 | 64×128 | AVR | **No scrolling** |
| SH1107 | 64×128 | ARM | **No scrolling** |
| SH1107 | 128×128 | ARM | **No scrolling** |

### C API / callbacks
```c
typedef enum {
    OLED_ROTATION_0   = 0,
    OLED_ROTATION_90  = 1,
    OLED_ROTATION_180 = 2,
    OLED_ROTATION_270 = 3, // = 90 | 180
} oled_rotation_t;
```

**Lifecycle / callbacks:**
| Signature | Purpose |
|---|---|
| `bool oled_init(oled_rotation_t rotation);` | Initialise the display with a rotation |
| `oled_rotation_t oled_init_kb(oled_rotation_t rotation);` | Weak; called at start of `oled_init` to override rotation (keyboard level) |
| `oled_rotation_t oled_init_user(oled_rotation_t rotation);` | Weak; keymap-level rotation override |
| `void oled_task(void);` | Internal: render + timeout + call `oled_task_user` |
| `bool oled_task_kb(void);` | Weak; called at start of `oled_task` (keyboard) |
| `bool oled_task_user(void);` | Weak; **the main hook you implement** — draw your UI here. Return `false` to prevent the default rendering pass (see Gotchas). |

**Sending raw commands/data:**
| Signature | Purpose |
|---|---|
| `bool oled_send_cmd(const uint8_t *data, uint16_t size);` | Send a command sequence |
| `bool oled_send_cmd_P(const uint8_t *data, uint16_t size);` | PROGMEM command sequence |
| `bool oled_send_data(const uint8_t *data, uint16_t size);` | Send raw pixel data |

**Buffer / cursor / text:**
| Signature | Purpose |
|---|---|
| `void oled_clear(void);` | Clear buffer, reset cursor, mark dirty |
| `#define oled_render() oled_render_dirty(false)` | Legacy alias — render dirty blocks |
| `void oled_render_dirty(bool all);` | Render dirty blocks (`all=true` → all blocks). Use `oled_render_dirty(true)` to force-flush. |
| `void oled_set_cursor(uint8_t col, uint8_t line);` | Move cursor (wraps) |
| `void oled_advance_page(bool clearPageRemainder);` | Next page; optionally fill remainder with spaces |
| `void oled_advance_char(void);` | Advance one char (advances page if no room) |
| `void oled_write_char(const char data, bool invert);` | Write one glyph |
| `void oled_write(const char *data, bool invert);` | Write a C string |
| `void oled_write_ln(const char *data, bool invert);` | Write a string + newline (pads remainder) |
| `void oled_pan(bool left);` | Pan buffer contents (true = left) |
| `oled_buffer_reader_t oled_read_raw(uint16_t start_index);` | Read buffer; returns `{current_element, remaining_element_count}` |
| `void oled_write_raw(const char *data, uint16_t size);` | Write raw bytes at cursor |
| `void oled_write_raw_byte(const char data, uint16_t index);` | Write one byte at an index |
| `void oled_write_pixel(uint8_t x, uint8_t y, bool on);` | Set/clear a pixel (origin top-left) |

**PROGMEM variants (AVR only; on ARM they `#define`-remap to the plain versions):**
```c
#if defined(__AVR__)
void oled_write_P(const char *data, bool invert);
void oled_write_ln_P(const char *data, bool invert);
void oled_write_raw_P(const char *data, uint16_t size);
#else
# define oled_write_P(data, invert)      oled_write(data, invert)
# define oled_write_ln_P(data, invert)   oled_write_ln(data, invert)
# define oled_write_raw_P(data, size)    oled_write_raw(data, size)
#endif
```

**Power / brightness / scroll / invert / geometry:**
| Signature | Purpose |
|---|---|
| `bool oled_on(void);` / `bool oled_off(void);` | Manual on/off; returns resulting state |
| `bool is_oled_on(void);` | Current power state |
| `uint8_t oled_set_brightness(uint8_t level);` / `uint8_t oled_get_brightness(void);` | Brightness get/set (0–255) |
| `void oled_scroll_set_area(uint8_t start_line, uint8_t end_line);` | 0–7 row range to scroll (whole screen by default; rows 4–7 unused on 128×32) |
| `void oled_scroll_set_speed(uint8_t speed);` | 0–7, fastest→slowest. Delays: `0=2,1=3,2=4,3=5,4=25,5=64,6=128,7=256` |
| `bool oled_scroll_right(void);` / `bool oled_scroll_left(void);` | Start scrolling whole display. **Contents cannot change while scrolling.** |
| `bool oled_scroll_off(void);` | Stop scrolling |
| `bool is_oled_scrolling(void);` | Scroll state |
| `bool oled_invert(bool invert);` | Invert display |
| `uint8_t oled_max_chars(void);` / `uint8_t oled_max_lines(void);` | Geometry helpers |

### Behavior & ordering
- `oled_task()` runs from the main loop on the `OLED_UPDATE_INTERVAL` cadence. It calls `oled_task_user()` first; what you return matters: returning `false` from `_user` is the conventional way to say "I handled all rendering, don't do anything else." The task also manages `OLED_TIMEOUT` (blanking) and `OLED_SCROLL_TIMEOUT`.
- Rendering is **dirty-block based**: only changed blocks are flushed. `OLED_UPDATE_PROCESS_LIMIT` (default `1`) bounds blocks-per-loop to protect the matrix scan rate; raising it speeds up a full redraw but can starve scanning.
- On split keyboards, default `OLED_UPDATE_INTERVAL` is `50` ms (vs `0` on non-split) — this is deliberate to keep the split transport responsive. Split sync of OLED-relevant state (layers, LEDs) is covered in `10-connectivity.md`; the common idiom is to branch on `is_keyboard_master()` / `is_keyboard_left()` (from `split_util.h`) inside `oled_task_user`.

### Examples
Layer + LED status:
```c
#ifdef OLED_ENABLE
bool oled_task_user(void) {
    oled_write_P(PSTR("Layer: "), false);
    switch (get_highest_layer(layer_state)) {
        case _QWERTY: oled_write_P(PSTR("Default\n"), false); break;
        case _FN:     oled_write_P(PSTR("FN\n"), false);     break;
        case _ADJ:    oled_write_P(PSTR("ADJ\n"), false);    break;
        default:      oled_write_ln_P(PSTR("Undefined"), false);
    }
    led_t s = host_keyboard_led_state();
    oled_write_P(s.num_lock   ? PSTR("NUM ") : PSTR("    "), false);
    oled_write_P(s.caps_lock  ? PSTR("CAP ") : PSTR("    "), false);
    oled_write_P(s.scroll_lock? PSTR("SCR ") : PSTR("    "), false);
    return false;
}
#endif
```
Split: flip the off-hand display 180° and render different content per half:
```c
#ifdef OLED_ENABLE
oled_rotation_t oled_init_user(oled_rotation_t rotation) {
    if (!is_keyboard_master()) return OLED_ROTATION_180;
    return rotation;
}
bool oled_task_user(void) {
    if (is_keyboard_master()) render_status();
    else { render_logo(); oled_scroll_left(); }
    return false;
}
#endif
```
Render a message on shutdown/bootloader entry (forces a flush with `oled_render_dirty(true)`):
```c
void oled_render_boot(bool bootloader) {
    oled_clear();
    for (int i = 0; i < 16; i++) {
        oled_set_cursor(0, i);
        oled_write_P(bootloader ? PSTR("Awaiting New Firmware ")
                                : PSTR("Rebooting "), false);
    }
    oled_render_dirty(true);
}
bool shutdown_user(bool jump_to_bootloader) {
    oled_render_boot(jump_to_bootloader);
}
```
Reading the framebuffer (random fade-out effect) uses `oled_read_raw(0)` → `oled_buffer_reader_t{ current_element, remaining_element_count }` and `oled_write_raw_byte(...)`.

### Logo / font system
- The default font is `drivers/oled/glcdfont.c`; override the path with `OLED_FONT_H`. Glyph ranges: `OLED_FONT_START`(0) … `OLED_FONT_END`(223), width 6 px, height 8 px.
- The default font reserves glyph ranges `0x80–0x94`, `0xA0–0xB4`, `0xC0–0xD4` (plus terminator `0x00`) for a built-in QMK logo — write that byte sequence with `oled_write_P` to render the logo.
- External editors: [Helix Font Editor](https://helixfonteditor.netlify.app/) and [Logo Editor](https://joric.github.io/qle/).

### SSD1306.h → oled_driver migration
| Old API | New API |
|---|---|
| `iota_gfx_init` | `oled_init` |
| `iota_gfx_on` / `iota_gfx_off` | `oled_on` / `oled_off` |
| `iota_gfx_flush` | `oled_render` |
| `iota_gfx_task` / `iota_gfx_task_user` | `oled_task` / `oled_task_user` |
| `iota_gfx_write_char` / `_write` / `_write_P` | `oled_write_char` / `oled_write` / `oled_write_P` |
| `matrix_write_char` / `matrix_write` / `matrix_write_ln` / `_P` | `oled_write_char` / `oled_write` / `oled_write_ln` / `_P` |
| `iota_gfx_clear_screen` / `matrix_clear` | `oled_clear` / (removed) |
| `struct CharacterMatrix` | (removed — delete all references) |

### Gotchas — OLED driver
- **Scrolling is unsupported on SH1106 and SH1107.** SSD1306 only.
- **Scrolling breaks on SSD1306 if display width < 128.**
- **You cannot change display contents while scrolling is active** (`oled_scroll_left/right`). Stop with `oled_scroll_off()` first.
- **90°/270° rotation is software, not free.** SSD1306/SH1106/SH1107 only support 0°/180° in hardware. Software rotation adds CPU time per refresh (ATmega32U4 example: 2 ms → 5 ms; keycodes started dropping at ~15 ms). Rotation on SH1106/SH1107 is markedly worse than SSD1306 because they lack "horizontal addressing mode"; SH1107 refresh is ~45% slower than an equivalent SSD1306 on STM32 (~20% slower on AVR). If cycles are tight, avoid 90° rotation.
- **64×128 and 128×128 presets force the SH1107 IC** (those heights aren't supported by other ICs).
- **`OLED_DRIVER` is always `ssd1306`.** Selecting the actual IC is done via `OLED_IC` (`OLED_IC_SH1106` / `OLED_IC_SH1107`), *not* via `OLED_DRIVER`.
- **`oled_write_P` and friends only exist on AVR.** On ARM they are `#define` macros that call the plain version. Code written with `_P` is portable, but do not assume PROGMEM semantics on ARM.
- **`oled_task_user` return value**: the conventional pattern returns `false`; treat returning `true` cautiously (it allows further default processing). Be deliberate.
- **Brightness default is `255`, not 128** — common surprise on battery-powered boards.

---

## 2. Quantum Painter (`qp`) — the modern display API

### Summary
Standardised graphics API for TFT/OLED panels with drawing primitives, custom images (QGF), fonts (QFF), animations, optional RLE compression, and optional LVGL integration. **ARM-only.** Selected per-panel via `QUANTUM_PAINTER_DRIVERS += <driver>`.

### Enable it
**`rules.mk`:**
```make
QUANTUM_PAINTER_ENABLE = yes
QUANTUM_PAINTER_DRIVERS += st7789_spi   # one per physical panel
```
Driver options and their transports/sizes:

| Panel | Type | Size | Comms | Driver add |
|---|---|---|---|---|
| GC9A01 | RGB LCD (circular) | 240×240 | SPI+DC+RST | `gc9a01_spi` |
| ILI9163 | RGB LCD | 128×128 | SPI+DC+RST | `ili9163_spi` |
| ILI9341 | RGB LCD | 240×320 | SPI+DC+RST | `ili9341_spi` |
| ILI9486 | RGB LCD | 320×480 | SPI+DC+RST | `ili9486_spi` |
| ILI9488 | RGB LCD | 320×480 | SPI+DC+RST | `ili9488_spi` |
| LD7032 | mono OLED | 128×40 | SPI+DC+RST *or* I2C | `ld7032_spi` / `ld7032_i2c` |
| SSD1351 | RGB OLED | 128×128 | SPI+DC+RST | `ssd1351_spi` |
| ST7735 | RGB LCD | 132×162, 80×160 | SPI+DC+RST | `st7735_spi` |
| ST7789 | RGB LCD | 240×320, 240×240 | SPI+DC+RST | `st7789_spi` |
| SH1106 | mono OLED | 128×64 | SPI+DC+RST *or* I2C | `sh1106_spi` / `sh1106_i2c` |
| SSD1306 | mono OLED | 128×64 (SPI) / 128×32 (I2C) | SPI+DC+RST *or* I2C | **uses `sh1106_spi`/`sh1106_i2c`** |
| Surface | virtual | user-defined | none (RAM buffer) | `surface` |

> **SSD1306 in Quantum Painter:** SSD1306 and SH1106 are "almost entirely identical, to the point of being indistinguishable by Quantum Painter." Enable SH1106 support and create SH1106 devices for SSD1306 panels.

### Keycodes
None. QP is a drawing API; interaction is via `qp_*` functions called from `keyboard_post_init_*` / `housekeeping_task_*` / suspend hooks.

### Configuration (`config.h`)
| Define | Default | Meaning |
|---|---|---|
| `QUANTUM_PAINTER_DISPLAY_TIMEOUT` | `30000` | ms all displays stay on after last input; `0` = always on |
| `QUANTUM_PAINTER_TASK_THROTTLE` | `1` | ms the internal task waits between executions (affects animations, timeout, LVGL timing) |
| `QUANTUM_PAINTER_NUM_IMAGES` | `8` | Max loaded images/animations at once |
| `QUANTUM_PAINTER_NUM_FONTS` | `4` | Max loaded fonts at once |
| `QUANTUM_PAINTER_CONCURRENT_ANIMATIONS` | `4` | Max simultaneous animations |
| `QUANTUM_PAINTER_LOAD_FONTS_TO_RAM` | `FALSE` | Load fonts to RAM (relevant for off-chip flash-stored fonts) |
| `QUANTUM_PAINTER_PIXDATA_BUFFER_SIZE` | `1024` | Max pixel bytes per transaction; higher = more RAM |
| `QUANTUM_PAINTER_SUPPORTS_256_PALETTE` | `FALSE` | Enable 256-color palettes; **large RAM cost** |
| `QUANTUM_PAINTER_SUPPORTS_NATIVE_COLORS` | `FALSE` | Enable `rgb888`/`rgb565` formats; **large RAM cost** |
| `QUANTUM_PAINTER_DEBUG` | unset | Verbose console debug; severe perf hit |
| `QUANTUM_PAINTER_DEBUG_ENABLE_FLUSH_TASK_OUTPUT` | unset | Keep debug output during flush (clogs console) |

Per-driver max-device overrides (default `1` each): `GC9A01_NUM_DEVICES`, `ILI9163_NUM_DEVICES`, `ILI9341_NUM_DEVICES`, `ILI9486_NUM_DEVICES`, `ILI9488_NUM_DEVICES`, `ST7735_NUM_DEVICES`, `ST7789_NUM_DEVICES`, `SSD1351_NUM_DEVICES`, `SH1106_NUM_SPI_DEVICES`/`SH1106_NUM_I2C_DEVICES`, `LD7032_NUM_SPI_DEVICES`/`LD7032_NUM_I2C_DEVICES`, `SURFACE_NUM_DEVICES`.

### Native color format → format flag mapping
Each panel reports a "native" format; image/font conversion must target a compatible format:
- GC9A01 / ILI9163 / ILI9341 / ST7735 / ST7789 / SSD1351 → **rgb565**
- ILI9486 → **rgb888** (Waveshare variant: **rgb565**)
- ILI9488 → **rgb888**
- SH1106 / SSD1306 / LD7032 → **mono2**

### Device construction APIs
SPI panels (5-pin: SCK, MOSI, CS, D/C, RST) — `spi_master` must already be configured:
```c
painter_device_t qp_<panel>_make_spi_device(uint16_t panel_width, uint16_t panel_height,
                                            pin_t chip_select_pin, pin_t dc_pin, pin_t reset_pin,
                                            uint16_t spi_divisor, int spi_mode);
```
Panels with this SPI signature: `gc9a01`, `ili9163`, `ili9341`, `ili9486`, `ili9488`, `st7735`, `st7789`, `ssd1351`, `sh1106`, `ld7032`. (ILI9486 also has `qp_ili9486_make_spi_waveshare_device(...)` for the Waveshare SPI→parallel module.)
I2C panels (SH1106, LD7032) — `i2c_master` must already be configured:
```c
painter_device_t qp_sh1106_make_i2c_device(uint16_t w, uint16_t h, uint8_t i2c_address);
painter_device_t qp_ld7032_make_i2c_device(uint16_t w, uint16_t h, uint8_t i2c_address);
```

### Drawing API (`#include <qp.h>`)
All functions take a `painter_device_t` as the first arg. **Coordinate convention:** most functions take `left, top, right, bottom` (inclusive), *not* x/y/width/height — this is required because some internal datatypes max out at 255 (a width of 256 would wrap to 0). Colors are QMK HSV triplets `0..255` each (H→0..360°, S→0..100%, V→0..100%). **QP colors are NOT subject to the RGB lighting CIE curve** even if that's enabled elsewhere.

**Device control:**
| Signature | Purpose |
|---|---|
| `bool qp_init(painter_device_t device, painter_rotation_t rotation);` | Init with `QP_ROTATION_0/90/180/270` |
| `bool qp_power(painter_device_t device, bool power_on);` | Power on/off the panel (does NOT control separate backlight — handle that manually) |
| `bool qp_clear(painter_device_t device);` | Clear screen |
| `bool qp_flush(painter_device_t device);` | Push queued draws to the panel — call at end of every draw sequence |

**Primitives:**
| Signature | Purpose |
|---|---|
| `bool qp_setpixel(painter_device_t device, uint16_t x, uint16_t y, uint8_t h, uint8_t s, uint8_t v);` | Set one pixel (inefficient for bulk) |
| `bool qp_line(painter_device_t device, uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1, ...);` | Line |
| `bool qp_rect(painter_device_t device, uint16_t left, uint16_t top, uint16_t right, uint16_t bottom, uint8_t h, uint8_t s, uint8_t v, bool filled);` | Rectangle (unfilled leaves interior as-is) |
| `bool qp_circle(painter_device_t device, uint16_t x, uint16_t y, uint16_t radius, ..., bool filled);` | Circle |
| `bool qp_ellipse(painter_device_t device, uint16_t x, uint16_t y, uint16_t sizex, uint16_t sizey, ..., bool filled);` | Ellipse |

**Image (QGF) functions:**
| Signature | Purpose |
|---|---|
| `painter_image_handle_t qp_load_image_mem(const void *buffer);` | Load a compiled-in QGF; returns handle or NULL |
| `bool qp_close_image(painter_image_handle_t image);` | Unload |
| `bool qp_drawimage(painter_device_t device, uint16_t x, uint16_t y, painter_image_handle_t image);` | Draw image |
| `bool qp_drawimage_recolor(painter_device_t device, uint16_t x, uint16_t y, painter_image_handle_t image, uint8_t h_fg, uint8_t s_fg, uint8_t v_fg, uint8_t h_bg, uint8_t s_bg, uint8_t v_bg);` | Draw mono image recolored (fg/bg) |
| `deferred_token qp_animate(painter_device_t device, uint16_t x, uint16_t y, painter_image_handle_t image);` | Start animating; returns token; loops until stopped |
| `deferred_token qp_animate_recolor(...);` | Recolor variant of animate |
| `void qp_stop_animation(deferred_token anim_token);` | Stop a running animation |

Image handle fields: `image->width`, `image->height`, `image->frame_count`.

**Font (QFF) functions:**
| Signature | Purpose |
|---|---|
| `painter_font_handle_t qp_load_font_mem(const void *buffer);` | Load compiled-in QFF |
| `bool qp_close_font(painter_font_handle_t font);` | Unload |
| `int16_t qp_textwidth(painter_font_handle_t font, const char *str);` | Pixel width of string |
| `int16_t qp_drawtext(painter_device_t device, uint16_t x, uint16_t y, painter_font_handle_t font, const char *str);` | Draw text; returns width |
| `int16_t qp_drawtext_recolor(...);` | Recolor variant |

Font handle field: `font->line_height`.

**Advanced / geometry / raw:**
| Signature | Purpose |
|---|---|
| `uint16_t qp_get_width(painter_device_t device);` / `qp_get_height` | Dimensions |
| `painter_rotation_t qp_get_rotation(painter_device_t device);` | Current rotation |
| `uint16_t qp_get_offset_x/y(painter_device_t device);` | Viewport offsets |
| `void qp_get_geometry(painter_device_t device, uint16_t *w, uint16_t *h, painter_rotation_t *r, uint16_t *ox, uint16_t *oy);` | All at once (pass NULL for any you don't want) |
| `void qp_set_viewport_offsets(painter_device_t device, uint16_t offset_x, uint16_t offset_y);` | Compensate for panels smaller than the controller (e.g. ST7735 80×160, ST7789 240×240) |
| `bool qp_viewport(painter_device_t device, uint16_t left, uint16_t top, uint16_t right, uint16_t bottom);` | Set raw pixel write region |
| `bool qp_pixdata(painter_device_t device, const void *pixel_data, uint32_t native_pixel_count);` | Stream raw pixels in the panel's native format (count is *pixels*, not bytes) |

### Behavior & ordering
- Typical init in `keyboard_post_init_kb`: create device → `qp_init(device, QP_ROTATION_0)` → optionally `qp_lvgl_attach`. Drawing then happens from `housekeeping_task_user` (throttle to e.g. 30 fps with `timer_elapsed32`) or event hooks.
- **Suspend is manual.** Implement `suspend_power_down_user` (call `qp_power(display, false)` + handle backlight/RGB) and `suspend_wakeup_init_user` (`qp_power(display, true)`).
- `qp_flush` must be the last call in a draw sequence. Some panels appear to work without it because their driver can't queue, but flush is required for correctness/portability.
- The internal QP task runs every `QUANTUM_PAINTER_TASK_THROTTLE` ms (default 1) and handles animations, the display timeout, and LVGL ticks (if attached).
- `QUANTUM_PAINTER_NUM_IMAGES` / `_NUM_FONTS` cap how many handles can be live at once — raise in `config.h` if you need more.

### Image/font conversion (build-time CLI)
Images and fonts are converted **offline** to C source (`*.qgf.c/.h`, `*.qff.c/.h`), then `#include`d and added to `SRC`:
```make
SRC += my_image.qgf.c noto11.qff.c
```
```c
#include "my_image.qgf.h"
#include "noto11.qff.h"
```

**`qmk painter-convert-graphics`** — image/GIF → QGF:
```
qmk painter-convert-graphics [-w] [-d] [-r] -f FORMAT [-o OUTPUT] -i INPUT [-v]
  -w, --raw       emit raw QGF instead of c/h
  -d, --no-deltas disable delta frames (animations)
  -r, --no-rle    disable RLE
  -f FORMAT       rgb888|rgb565|pal256|pal16|pal4|pal2|mono256|mono16|mono4|mono2
```
Format support notes: `rgb888`/`rgb565` need `QUANTUM_PAINTER_SUPPORTS_NATIVE_COLORS`; `pal256`/`mono256` need `QUANTUM_PAINTER_SUPPORTS_256_PALETTE`. `INPUT` is anything Pillow can load (PNG, animated GIF). `OUTPUT` is a directory (defaults to input's dir).

**`qmk painter-make-font-image`** — TTF → intermediate PNG (for manual editing):
```
qmk painter-make-font-image [-a] [-u UNICODE_GLYPHS] [-n] [-s SIZE] -o OUTPUT -f FONT
  -a, --no-aa            disable anti-aliasing
  -u, --unicode-glyphs   extra unicode glyphs (string)
  -n, --no-ascii         skip full ASCII 0x20..0x7E
  -s, --size SIZE        font size (default 12)
```
The output PNG uses the top-left pixel (0,0) as the glyph "delimiter" color; each glyph begins where that color appears on the first row; the first row is discarded on conversion. Glyph order = ASCII (if present) then unicode glyphs.

**`qmk painter-convert-font-image`** — intermediate PNG → QFF:
```
qmk painter-convert-font-image [-w] [-r] -f FORMAT [-u UNICODE_GLYPHS] [-n] [-o OUTPUT] [-i INPUT]
```
Must pass the **same** `--no-ascii` / `--unicode-glyphs` as the make step. Formats: `rgb565|pal256|pal16|pal4|pal2|mono256|mono16|mono4|mono2`.

### Examples
Init + draw an image bottom-right on a 240×320 panel:
```c
static painter_device_t display;
static painter_image_handle_t my_image;
void keyboard_post_init_kb(void) {
    display = qp_st7789_make_spi_device(240, 320, MY_CS, MY_DC, MY_RST, 2, 3);
    qp_init(display, QP_ROTATION_0);
    my_image = qp_load_image_mem(gfx_my_image);
    if (my_image) qp_drawimage(display, 240 - my_image->width, 320 - my_image->height, my_image);
}
```
Animate + stop:
```c
static deferred_token my_anim;
my_anim = qp_animate(display, x, y, my_image);
// later:
qp_stop_animation(my_anim);
```
Throttled housekeeping draw (30 fps):
```c
void housekeeping_task_user(void) {
    static uint32_t last_draw = 0;
    if (timer_elapsed32(last_draw) > 33) {
        last_draw = timer_read32();
        qp_rect(display, 0, 7, 0, 239, rgb_matrix_get_hue(), 255, 255, true);
        qp_flush(display);
    }
}
```

### LVGL integration
Enable:
```make
QUANTUM_PAINTER_ENABLE = yes
QUANTUM_PAINTER_DRIVERS = ......
QUANTUM_PAINTER_LVGL_INTEGRATION = yes
```
API:
```c
bool qp_lvgl_attach(painter_device_t device);  // LVGL now "owns" this display
void qp_lvgl_detach(void);                      // stop LVGL ticks, release resources
```
LVGL features are tuned via your own `lv_conf.h`.

LVGL task period — `config.h`:
```c
#define QP_LVGL_TASK_PERIOD 40   // ms; default 5
```

### Gotchas — Quantum Painter
- **ARM-only. No AVR support** (complexity). Pick the OLED driver on ATmega32U4 boards.
- **Big Flash cost; LVGL especially.** "Recommended to use a supported MCU with >256 kB of flash." LVGL integration is the heaviest.
- **`rgb888`/`rgb565`/`pal256`/`mono256` formats need RAM-expensive config flags** (`QUANTUM_PAINTER_SUPPORTS_NATIVE_COLORS` / `..._256_PALETTE`); default off.
- **No suspend integration.** You MUST manually `qp_power(false/true)` in the suspend hooks (and handle backlight separately — `qp_power` does not touch the backlight pin).
- **Coordinate system is inclusive `left/top/right/bottom`, not x/y/width/height.** A horizontal line 8 px wide starting at x=4 uses `left=4, right=11`. Getting this wrong produces off-by-one or wrapped geometry (256 wraps to 0 in some internal types).
- **`qp_flush` is required** at the end of a draw batch, even if a panel seems to update without it.
- **Once `qp_lvgl_attach` is called, LVGL "owns" the display** — calling standard QP draw ops afterward will likely produce artifacts. Use `qp_lvgl_detach` first.
- **LVGL default 5 ms task period can drop keystrokes/encoder rotations** during dynamic animation, because LVGL competes with QMK's matrix scan. Raise `QP_LVGL_TASK_PERIOD` (e.g. 40 ms) if you rely on QMK for input.
- **SSD1306 in QP uses the SH1106 driver** — enable `sh1106_spi`/`sh1106_i2c` and construct SH1106 devices.
- **ST7735 / ST7789 panel offsets.** Some modules are physically smaller than the controller's internal framebuffer (e.g. 80×160 on a 132×162 ST7735; 240×240 on a 240×320 ST7789) — use `qp_set_viewport_offsets` to correct rendering.
- **CLI is build-time only.** Converted `.qgf.c`/`.qff.c` must be added to `SRC` and their `.h` `#include`d. There's no runtime image loading from SD/flash unless you wire up external storage yourself.
- **`qp_pixdata` count is in *pixels*, not bytes** (e.g. 10 RGB565 pixels = 20 bytes transferred).

---

## 2a. Quantum Painter file formats — QGF (graphics), QFF (fonts), and RLE

These are the on-disk/compiled-in binary formats emitted by the `qmk painter-convert-*` CLI. You rarely hand-edit them, but knowing the structure helps debug conversion / size issues.

### Common conventions
- All integers little-endian.
- Files are sequences of **blocks**: each block = 5-byte **header** + optional **blob**.
- Block header (`qgf_block_header_v1_t`, 5 bytes): `type_id` (u8), `neg_type_id` (u8, negated for parse-error detection), `length` (u24, blob length, max ~16 MB).
- `total_file_size` + `neg_total_file_size` are stored in the descriptor for integrity checks.

### QGF (Quantum Graphics Format) — images & animations
Block layout:
1. **Graphics descriptor** (`type_id=0x00`, len 18) — magic `0x464751` ("QGF"), `qgf_version=0x01`, `total_file_size`, `neg_total_file_size`, `image_width`, `image_height`, `frame_count` (≥1).
2. **Frame offsets** (`type_id=0x01`, variable) — array of u32 file offsets, one per frame (duplicates allowed to repeat a frame in an animation).
3. Per frame:
   - **Frame descriptor** (`type_id=0x02`, len 5): `format`, `flags`, `compression_scheme`, `transparency_index`, `delay` (u16, ms — animation frame delay).
   - **Frame palette** (`type_id=0x03`, optional) — array of HSV888 entries (only for palette formats).
   - **Frame delta** (`type_id=0x04`, len 8, optional) — `left/top/right/bottom` sub-image location (only if delta flag set).
   - **Frame data** (`type_id=0x05`, variable) — raw or RLE pixel bytes.

Frame `format` byte: `0x00`=1bpp gray, `0x01`=2bpp gray, `0x02`=4bpp gray, `0x03`=8bpp gray, `0x04`=1bpp indexed, `0x05`=2bpp indexed, `0x06`=4bpp indexed, `0x07`=8bpp indexed. Grayscale: 0=black, max=white, LSb-first pixel. Indexed: LSb-first.
Frame `flags` (bitmask): bit0 = Transparency (use `transparency_index`), bit1 = Delta (this is a delta frame → expect a frame delta block). Bits 2–7 reserved.
`compression_scheme`: `0x00` = none, `0x01` = QMK RLE.
> **Note:** the descriptor's `length` is documented as 5 but the struct (header+6 payload) totals 11 bytes — i.e. 6 payload bytes (format, flags, compression_scheme, transparency_index, u16 delay).

### QFF (Quantum Font Format) — fonts
Block layout:
1. **Font descriptor** (`type_id=0x00`, len 20) — magic `0x464651` ("QFF"), `qff_version=0x01`, `total_file_size`, `neg_total_file_size`, `line_height`, `has_ascii_table`, `num_unicode_glyphs`, `format`, `flags`, `compression_scheme`, `transparency_index`. (`format/flags/compression/transparency` mirror QGF; `delta` flag is ignored for QFF.)
2. **ASCII glyph table** (`type_id=0x01`, len 290) — 95 entries for `0x20..0x7E`. Each u24 packs 6 bits width (`QFF_GLYPH_WIDTH_MASK`) + 18 bits offset (`QFF_GLYPH_OFFSET_MASK`).
3. **Unicode glyph table** (`type_id=0x02`, variable, optional) — N × { u24 `code_point`, u24 `glyph` }.
4. **Font palette** (`type_id=0x03`, optional) — identical to QGF frame palette (only for palette fonts).
5. **Font data** (`type_id=0x04`, variable) — last block; identical to QGF frame data (different type_id).

### RLE schema (shared by QGF & QFF)
Marker-octet based, runs up to 128:
- **marker ≥ 128** → non-repeating run: `length = marker - 128`; then `length` literal octets follow.
- **marker < 128** → repeating run: `length = marker`; one octet follows, repeated `length` times.

Decoder pseudocode:
```
while !EOF:
    marker = READ_OCTET()
    if marker >= 128:
        for i in 0 .. (marker - 128) - 1: WRITE(READ_OCTET())
    else:
        c = READ_OCTET()
        for i in 0 .. marker - 1: WRITE(c)
```
Disable with `-r`/`--no-rle` on both convert commands.

### Gotchas — file formats
- **`transparency_index` is "not yet implemented"** in both QGF and QFF despite being in the descriptors — don't rely on per-frame transparency yet.
- **QFF ignores the `delta` flag** (fonts don't animate).
- **Glyph encoding in QFF ASCII table is bit-packed** (6-bit width + 18-bit offset into one u24). Don't try to parse by eye.
- **RLE max run length is 128** — long identical runs split into multiple markers.

---

## 3. HD44780 Character LCD

### Summary
Driver for classic character LCD modules using the HD44780U IC (or equivalent), communicating in **4-bit parallel** mode (D4–D7 + RS/RW/E). Primary tested module is the 1602A (16×2). Supports up to 8 user-defined custom glyphs (CGRAM, non-persistent).

### Enable it
**`rules.mk`:**
```make
HD44780_ENABLE = yes
```

### Configuration (`config.h`) — all pin defines are required
| Define | Default | Meaning |
|---|---|---|
| `HD44780_DATA_PINS` | *required* | Array of 4 GPIOs for D4–D7, e.g. `{ B1, B3, B2, B6 }` |
| `HD44780_RS_PIN` | *required* | RS pin |
| `HD44780_RW_PIN` | *required* | RW pin |
| `HD44780_E_PIN` | *required* | E (enable) pin |
| `HD44780_DISPLAY_COLS` | `16` | Visible chars per line |
| `HD44780_DISPLAY_LINES` | `2` | Visible lines |
| `HD44780_WRAP_LINES` | *undef* | If defined, input wraps to the next line |

> 2004A (20×4) is listed but **untested / not currently supported**. To run modules at 3.3 V you need a MAX660 charge-pump IC + two 10 µF caps.

### C API
| Signature | Purpose |
|---|---|
| `void hd44780_init(bool cursor, bool blink);` | Initialise once; `cursor`=show cursor, `blink`=blink if shown |
| `void hd44780_clear(void);` | Clear (called on init) |
| `void hd44780_home(void);` | Cursor home (called on init) |
| `void hd44780_on(bool cursor, bool blink);` | Display on + cursor props |
| `void hd44780_off(void);` | Display off |
| `void hd44780_set_cursor(uint8_t col, uint8_t line);` | Move cursor (col 0–15, line 0/1 on 16×2) |
| `void hd44780_putc(char c);` | Print a char; `\n` → start of next line. Glyph set depends on the module's ROM code |
| `void hd44780_puts(const char *s);` | Print a string |
| `void hd44780_puts_P(const char *s);` | PROGMEM string (alias of `hd44780_puts` on ARM) |
| `void hd44780_define_char(uint8_t index, uint8_t *data);` | Define custom glyph (index 0–7; `data` = 8 bytes of 5-bit rows) |
| `void hd44780_define_char_P(uint8_t index, const uint8_t *data);` | PROGMEM variant (alias on ARM) |
| `bool hd44780_busy(void);` | True if the display is still processing |
| `void hd44780_write(uint8_t data, bool isData);` | Raw byte write |
| `uint8_t hd44780_read(bool isData);` | Read byte (`isData=true` → char at cursor; else DDRAM address + busy flag) |
| `void hd44780_command(uint8_t command);` | Send a command byte (waits for busy clear). See datasheet / `hd44780.h` for defines |
| `void hd44780_data(uint8_t data);` | Send a data byte (waits for busy clear) |
| `void hd44780_set_cgram_address(uint8_t address);` | CGRAM addr 0x00–0x3F (custom glyph definition) |
| `void hd44780_set_ddram_address(uint8_t address);` | DDRAM addr 0x00–0x7F (text/cursor) |

> **Custom glyph layout:** 8 bytes, first byte = topmost row, LSB of each byte = rightmost column (5-bit wide glyphs). The first 16 character positions are reserved for the 8 custom glyphs (duplicated). Defining a char advances the cursor — call `hd44780_home()` afterward. CGRAM is **not persistent** across power cycles.

### Behavior & ordering
- There is **no periodic task callback** like `oled_task_user`. You typically call `hd44780_init(...)` once in `keyboard_post_init_user` and then write text from event hooks.
- `hd44780_command`/`hd44780_data` block on the busy flag; `hd44780_write` does not.

### Example
```c
void keyboard_post_init_user(void) {
    hd44780_init(true, true);                  // blinking cursor
    hd44780_puts_P(PSTR("Hello, world!\n"));
}
```
Custom character (QMK Psi):
```c
const uint8_t PROGMEM psi[8] = { 0x15, 0x15, 0x15, 0x0E, 0x04, 0x04, 0x04, 0x00 };
void keyboard_post_init_user(void) {
    hd44780_init(false, false);
    hd44780_define_char_P(0, psi);
    hd44780_home();                            // cursor was advanced by define_char
    hd44780_puts_P(PSTR("\x08 QMK Firmware")); // 0x08 to skip the null terminator
}
```

### Gotchas — HD44780
- **4-bit mode only** — all 8 data lines are not supported; you wire D4–D7.
- **No `hd44780_task_user` hook** — unlike the OLED/ST7565 drivers, there's no periodic draw callback. Drive it imperatively.
- **2004A (20×4) is untested / unsupported** despite being a common module.
- **3.3 V operation needs extra hardware** (MAX660 + caps); most modules are 5 V.
- **Custom glyphs are volatile** (CGRAM clears on power loss) and must be redefined each boot.
- **Defining a custom glyph advances the cursor** — always `hd44780_home()` after.
- **`puts_P`/`define_char_P` are PROGMEM-only on AVR**; on ARM they alias the non-P versions.

---

## 4. ST7565 GLCD

### Summary
Monochrome GLCD driver for the ST7565 IC over SPI. API mirrors the OLED driver but with `st7565_*` names and a smaller feature set (only 0°/180° rotation, no 90° software rotation, no scrolling). Primary consumer is the Ergodox Infinity (Newhaven NHD-C12832A1Z, 128×32).

### Enable it
**`rules.mk`:**
```make
ST7565_ENABLE = yes
```

### Configuration (`config.h`)
| Define | Default | Meaning |
|---|---|---|
| `ST7565_A0_PIN` | *required* | A0 (data/command) pin |
| `ST7565_RST_PIN` | *required* | Reset pin |
| `ST7565_SS_PIN` | *required* | SPI slave-select pin |
| `ST7565_SPI_CLK_DIVISOR` | `4` | SPI clock divisor |
| `ST7565_FONT_H` | `"glcdfont.c"` | Font source (override for custom fonts) |
| `ST7565_FONT_START` | `0` | Starting glyph index |
| `ST7565_FONT_END` | `223` | Ending glyph index |
| `ST7565_FONT_WIDTH` | `6` | Font width px |
| `ST7565_FONT_HEIGHT` | `8` | Font height px (untested) |
| `ST7565_TIMEOUT` | `60000` | ms of keyboard inactivity before blanking (burn-in); `0` disables |
| `ST7565_COLUMN_OFFSET` | `0` | Shift output right N pixels |
| `ST7565_CONTRAST` | `32` | Contrast 0–255 |
| `ST7565_UPDATE_INTERVAL` | `0` | ms between updates (raise to help scan rate) |
| `ST7565_DISPLAY_WIDTH` | `128` | Panel width |
| `ST7565_DISPLAY_HEIGHT` | `32` | Panel height |
| `ST7565_MATRIX_SIZE` | `512` | Buffer bytes = `HEIGHT/8 * WIDTH` |
| `ST7565_BLOCK_TYPE` | `uint16_t` | Dirty-tracking int type |
| `ST7565_BLOCK_COUNT` | `16` | Dirty-block count |
| `ST7565_BLOCK_SIZE` | `32` | Bytes per dirty block |

### C API / callbacks
```c
typedef enum { DISPLAY_ROTATION_0, DISPLAY_ROTATION_180 } display_rotation_t;
```
| Signature | Purpose |
|---|---|
| `bool st7565_init(display_rotation_t rotation);` | Init |
| `display_rotation_t st7565_init_user(display_rotation_t rotation);` | Weak; override rotation |
| `void st7565_task(void);` | Internal: render + timeout + call `st7565_task_user` |
| `void st7565_task_user(void);` | Weak; **main hook** (note: returns void, not bool) |
| `void st7565_clear(void);` | Clear buffer, reset cursor, mark dirty |
| `void st7565_render(void);` | Render dirty chunks |
| `void st7565_set_cursor(uint8_t col, uint8_t line);` | Move cursor (wraps) |
| `void st7565_advance_page(bool clearPageRemainder);` | Next page |
| `void st7565_advance_char(void);` | Advance one char |
| `void st7565_write_char(const char data, bool invert);` | One glyph |
| `void st7565_write(const char *data, bool invert);` | String |
| `void st7565_write_ln(const char *data, bool invert);` | String + newline (pads) |
| `void st7565_pan(bool left);` | Pan buffer |
| `display_buffer_reader_t st7565_read_raw(uint16_t start_index);` | Read buffer (returns `{current_element, remaining_element_count}`) |
| `void st7565_write_raw(const char *data, uint16_t size);` | Raw bytes at cursor |
| `void st7565_write_raw_byte(const char data, uint16_t index);` | One byte at index |
| `void st7565_write_pixel(uint8_t x, uint8_t y, bool on);` | Set pixel (origin top-left) |
| `void st7565_write_P/st7565_write_ln_P/st7565_write_raw_P(...)` | PROGMEM variants (alias to non-P on ARM) |
| `bool st7565_on(void);` / `bool st7565_off(void);` | Manual on/off (returns resulting state) |
| `void st7565_on_user(void);` / `void st7565_off_user(void);` | Weak; called only when state actually changes |
| `bool st7565_is_on(void);` | Power state |
| `bool st7565_invert(bool invert);` | Invert display |
| `uint8_t st7565_max_chars(void);` / `uint8_t st7565_max_lines(void);` | Geometry helpers |

### Behavior & ordering
- `st7565_task()` runs periodically (cadence `ST7565_UPDATE_INTERVAL`), manages `ST7565_TIMEOUT`, and calls `st7565_task_user()`.
- Mirrors the OLED driver's dirty-block rendering and PROGMEM font (`glcdfont.c`).
- Split idiom: branch on `is_keyboard_master()`/`is_keyboard_left()` in `st7565_init_user` (rotation) and `st7565_task_user` (content).

### Example
```c
#ifdef ST7565_ENABLE
void st7565_task_user(void) {
    st7565_write_P(PSTR("Layer: "), false);
    switch (get_highest_layer(layer_state)) {
        case _QWERTY: st7565_write_P(PSTR("Default\n"), false); break;
        case _FN:     st7565_write_P(PSTR("FN\n"), false);     break;
        case _ADJ:    st7565_write_P(PSTR("ADJ\n"), false);    break;
        default:      st7565_write_ln_P(PSTR("Undefined"), false);
    }
}
#endif
```

### Gotchas — ST7565
- **Only 0° and 180° rotation** (`DISPLAY_ROTATION_0`/`_180`) — no 90° software rotation like the OLED driver.
- **`st7565_task_user` returns `void`, not `bool`** — different from `oled_task_user`. Don't copy an OLED callback verbatim.
- **No scrolling support** (unlike SSD1306).
- **Contrast default is `32`** (0–255) — the ZLE12864B specifically requires contrast adjustment.
- **ST7565_A0_PIN / RST_PIN / SS_PIN are all required** (SPI-only transport).
- SPI must already be configured for the platform (see `13-drivers-lowlevel.md`).

---

## 5. Rotary Encoders

### Summary
Support for EC11-compatible quadrature rotary encoders. Each encoder is two GPIO pins (A/B) polled in the main loop; detents generate `encoder_update_user`/`_kb` callbacks. Optionally, `ENCODER_MAP_ENABLE` routes encoder events through the normal per-layer keycode pipeline like key switches.

### Enable it
**`rules.mk`:**
```make
ENCODER_ENABLE = yes
# Optional, keymap-level only:
ENCODER_MAP_ENABLE = yes
```
**`config.h`** pin arrays (one entry per encoder):
```c
#define ENCODER_A_PINS { B12 }
#define ENCODER_B_PINS { B13 }
```

### Keycodes
No dedicated keycodes in the basic mode. With `ENCODER_MAP_ENABLE`, you populate `encoder_map[][][]` using the `ENCODER_CCW_CW(ccw, cw)` macro with any standard keycodes (e.g. `MS_WHLU/MS_WHLD`, `KC_VOLD/KC_VOLU`, `UG_HUED/UG_HUEU`).

### Configuration (`config.h`)
| Define | Default | Meaning |
|---|---|---|
| `ENCODER_A_PINS` | *required* | Array of A-pad pins, one per encoder |
| `ENCODER_B_PINS` | *required* | Array of B-pad pins, one per encoder |
| `ENCODER_DIRECTION_FLIP` | *undef* | Flip CW/CCW (or just swap A/B pins) |
| `ENCODER_RESOLUTION` | `4` | Pulses registered per detent |
| `ENCODER_RESOLUTIONS` | (single value) | Per-encoder resolutions, e.g. `{ 4, 2 }` |
| `ENCODER_DEFAULT_POS` | *undef* | Default pin state for 4× encoders that skip pulses on direction change (e.g. `0x3` if both pins idle high) |
| `ENCODER_A_PINS_RIGHT` / `ENCODER_B_PINS_RIGHT` | (mirror left) | Right-half pinout on splits with different wiring |
| `ENCODER_RESOLUTIONS_RIGHT` | (mirror left) | Right-half resolutions |
| `ENCODER_MAP_KEY_DELAY` | = `TAP_CODE_DELAY` | ms between the synthesized keyup/keydown when using encoder map |

### Default behavior
With no callback and no encoder map: **every installed encoder acts as Volume Up (CW) / Volume Down (CCW)**. No further config needed if that's what you want.

### Callbacks
```c
bool encoder_update_kb(uint8_t index, bool clockwise);   // keyboard/<keyboard>.c
bool encoder_update_user(uint8_t index, bool clockwise); // keymap.c
```
- `index` = encoder number (0-based), `clockwise` = direction.
- `_kb` runs first and should call `encoder_update_user`; if `_user` returns `false`, stop. If `_user` returns `true`, the keyboard/core code runs on top.
- **Returning `false` from `_user` is the safe default** — it overrides the keyboard-level handler and avoids the default volume behavior. Returning `true` lets both run.

Example (`keymap.c`):
```c
bool encoder_update_user(uint8_t index, bool clockwise) {
    if (index == 0) {
        if (clockwise) tap_code(KC_PGDN); else tap_code(KC_PGUP);
    } else if (index == 1) {
        if (clockwise) rgb_matrix_increase_hue(); else rgb_matrix_decrease_hue();
    }
    return false;
}
```

### Encoder map (per-layer, keycode pipeline)
```c
#if defined(ENCODER_MAP_ENABLE)
const uint16_t PROGMEM encoder_map[][NUM_ENCODERS][NUM_DIRECTIONS] = {
    [0] = { ENCODER_CCW_CW(MS_WHLU, MS_WHLD),  ENCODER_CCW_CW(KC_VOLD, KC_VOLU) },
    [1] = { ENCODER_CCW_CW(UG_HUED, UG_HUEU),  ENCODER_CCW_CW(UG_SATD, UG_SATU) },
    [2] = { ENCODER_CCW_CW(UG_VALD, UG_VALU),  ENCODER_CCW_CW(UG_SPDD, UG_SPDU) },
    [3] = { ENCODER_CCW_CW(UG_PREV, UG_NEXT),  ENCODER_CCW_CW(KC_RIGHT, KC_LEFT) },
};
#endif
```
- **Enable only at the keymap level.**
- When the map is enabled, `encoder_update_user`/`_kb` are **not** the primary path — events are pushed through `process_record_*()` as a keydown/keyup pair. `ENCODER_MAP_KEY_DELAY` controls the gap (defaults to `TAP_CODE_DELAY`).

### Split keyboards
- Define `ENCODER_A_PINS_RIGHT` / `ENCODER_B_PINS_RIGHT` / `ENCODER_RESOLUTIONS_RIGHT` only when the right half differs. If omitted, the left-side definitions apply to both halves.
- A side with no encoders uses empty arrays: `{ }`.
- Right-half-only example:
```c
#define ENCODER_A_PINS        { }
#define ENCODER_B_PINS        { }
#define ENCODER_RESOLUTIONS   { }
#define ENCODER_A_PINS_RIGHT      { B12 }
#define ENCODER_B_PINS_RIGHT      { B13 }
#define ENCODER_RESOLUTIONS_RIGHT { 4 }
```

### Hardware wiring
- A and B lines go directly to MCU GPIOs; C/common line goes to ground.

### Multiple encoders sharing pins (advanced)
Detent encoders can share pins under these conditions:
- using detent encoders;
- pads are high at the detent "default position";
- no more than two encoders sharing a pin are turned simultaneously.

Two encoders on 3 pins: `A_PINS {B1,B1}`, `B_PINS {B2,B3}`. Three encoders on 3 pins (`A{B1,B1,B2}`, `B{B2,B3,B3}`) works but turning two sharing-pin encoders at once can produce wrong output depending on timing.

### Behavior & ordering
- Encoder polling happens in the main loop (matrix-scan-adjacent). Events then either hit `encoder_update_kb`→`_user` (basic mode) or the keycode pipeline (map mode).
- In map mode the synthesized key event flows through the full `process_record` chain (see `01-architecture.md`), so layer state, mods, and other handlers all apply.

### Gotchas — encoders
- **`ENCODER_MAP_ENABLE` should be keymap-level only.**
- **Default behavior is Volume Up/Down for *every* encoder** — if you implement `encoder_update_user`, return `false` to suppress that or you'll get double events.
- **Changing resolution requires reflashing the half that has the affected encoder.** This is easy to forget on splits.
- **CW/CCW direction can be wrong** — fix by swapping the A/B pin definitions or defining `ENCODER_DIRECTION_FLIP`.
- **`ENCODER_RESOLUTION` default is 4** (4 pulses/detent). Per-encoder override via `ENCODER_RESOLUTIONS { ... }`.
- **4× encoders that skip pulses on direction change** may need `ENCODER_DEFAULT_POS` (e.g. `0x3` for both-idle-high).
- **`encoder_update_user` returning `true` lets keyboard-level code also run** — usually surprising. Default to `false`.
- **Pin-sharing configurations can misdecode** when two sharing encoders are turned at once.
- **Split OLED/encoder state sync** — encoder events on the slave half are transported to the master; see `10-connectivity.md` for the split transport model.

---

## Cross-cutting relationships
- **Transport dependency:** every display rides on I2C, SPI, or parallel GPIO — configure those first (`13-drivers-lowlevel.md`). OLED driver SPI needs `OLED_DC_PIN`/`OLED_CS_PIN`/`OLED_RST_PIN`; QP SPI panels need `spi_master` configured; QP I2C panels and the OLED driver I2C path need `i2c_master` configured; ST7565/HD44780 need their GPIOs.
- **Split displays:** the OLED/ST7565 idiom branches on `is_keyboard_master()`/`is_keyboard_left()` (from `split_util.h`) for per-half content/rotation. Split transport of layer/LED state that those renderers consume is covered in `10-connectivity.md`. Encoder events on the off-hand are also transported across the split.
- **Main-loop ordering:** `oled_task`/`st7565_task`/QP internal task and `housekeeping_task` all live in the main loop alongside matrix scan and `process_record` — see `01-architecture.md`. Heavier draw loops (90° OLED rotation, LVGL animations) directly compete with scan latency.
- **Color model:** QP uses QMK HSV `0..255` but is explicitly **not** subject to the RGB lighting CIE curve (`07-led-rgb-backlight.md`); don't expect a QP color to match an RGB_MATRIX color byte-for-byte when CIE is on.
- **Data-driven status:** OLED/ST7565/HD44780/encoders are still primarily `rules.mk` + `config.h` configured (not rich info.json feature blocks). QP drivers are selected in `rules.mk` via `QUANTUM_PAINTER_DRIVERS`. See `03-config-and-info-json.md` for the migration status.
