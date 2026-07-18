# Connectivity & Communications Reference — split_keyboard, wireless/BT, command, secure, os_detection, rawhid, battery

> **Scope:** Everything that moves data between two halves, between keyboard and host, or between keyboard and another radio. Seven distinct features, all communication-oriented: **Split Keyboard** (inter-half transport + state sync), **Wireless/Bluetooth** (radio output), **Command** (the on-keyboard "Magic" debug console), **Secure** (lock/unlock gating), **OS Detection** (fingerprint the host OS from USB descriptors), **Raw HID** (the bidirectional host-comms channel that VIA and custom host tools are built on), and **Battery** (ADC sampling of cell voltage).
>
> Read the "0. Decision map" first — these features intersect (e.g. wireless splits need `SPLIT_USB_DETECT`; raw HID is the foundation for VIA; battery only matters for wireless builds).

Cross-references: main loop / process_record chain / `housekeeping_task` ordering → `01-architecture.md`; info.json feature & split-transport layout keys → `03-config-and-info-json.md`; magic keycodes that overlap Command → `04-keymaps-and-keycodes.md`; split pointing device details → `06-pointing-and-hid-devices.md`; split LED/RGB sync (`RGBLIGHT_SPLIT`, `RGBLED_SPLIT`) → `07-led-rgb-backlight.md`; split OLED/ST7565 sync → `08-displays.md`; serial/i2c/adc/eeprom driver silicon config → `13-drivers-lowlevel.md`; raw HID → VIA/Vial → `14-configurator-api-via.md`; EEPROM handedness files & reset semantics → `03-config-and-info-json.md`; flashing split bootloader targets & ISP → `15-flashing-debugging.md`.

---

## 0. Decision map (read first)

| You want to... | Use | Enable line |
|---|---|---|
| Talk between two controller halves over a cable | **Split Keyboard** (§1) | `SPLIT_KEYBOARD = yes` |
| Send keyboard output over Bluetooth instead of (or alongside) USB | **Wireless/BT** (§2) | `BLUETOOTH_ENABLE = yes` + `BLUETOOTH_DRIVER = rn42\|bluefruit_le` |
| A hidden on-keyboard debug console (toggle NKRO, jump to bootloader, dump EEPROM) | **Command** (§3) | `COMMAND_ENABLE = yes` |
| Lock the keyboard until a secret key sequence is entered | **Secure** (§4) | `SECURE_ENABLE = yes` |
| Make keymap behavior differ per host OS (macOS vs Windows vs Linux) | **OS Detection** (§5) | `OS_DETECTION_ENABLE = yes` |
| Bidirectional custom comms with a host program (VIA, macros, metrics) | **Raw HID** (§6) | `RAW_ENABLE = yes` |
| Report battery % on a wireless build | **Battery** (§7) | `BATTERY_ENABLE = yes` |

**Feature intersections that bite:**
- **Wireless split:** without a USB cable always attached, neither half can use VBUS detection to pick master/slave. You must enable `SPLIT_USB_DETECT` (it is auto-enabled on ARM/ChibiOS). Note the warning: `SPLIT_USB_DETECT` *breaks* battery-pack demos.
- **Split + Bluetooth:** supported BT chips (RN-42, Bluefruit LE SPI Friend) are **AVR-only** and do **not** support NKRO — `rules.mk` must have `NKRO_ENABLE = no`. Mixing AVR (wireless) and ARM (split) halves is impossible.
- **Raw HID + VIA:** VIA rides on top of Raw HID (usage page `0xFF60`, usage `0x61`). If you write your own host tool on the same endpoint, you will collide with VIA. See §6 and `14-configurator-api-via.md`.
- **Split + Command / Secure / OS Detection:** these are host-facing and run on the master side; the slave sees mirrored state only if you enable the corresponding `SPLIT_*` sync flag (§1.4).

---

## 1. Split Keyboard

### Summary
Drives a two-controller keyboard where one half (the **master**) is connected to USB and the other (the **slave**) is reached over a serial or I²C link through a TRRS (or equivalent) cable. The master scans both halves' matrices, merges them, and sends the combined HID report. QMK's generic implementation (used by Let's Split, crkbd, etc.) supports arbitrary state sync between halves via `SPLIT_*` flags and a transaction/RPC API.

> **Three halves is NOT supported.** The serial driver explicitly supports only two halves. Don't try to chain.

### 1.1 Enable it

```make
# rules.mk
SPLIT_KEYBOARD = yes
```

For a custom (non-serial, non-I²C) transport:
```make
SPLIT_TRANSPORT = custom
```

Data-driven note: `SPLIT_KEYBOARD` is a `rules.mk` build switch (not an info.json feature). Per-half pin overrides (`MATRIX_ROW_PINS_RIGHT`, `ENCODER_A_PINS_RIGHT`, `DIRECT_PINS_RIGHT`) are still `config.h` defines; info.json equivalents for these are limited — prefer `config.h` for split hardware specifics. See `03-config-and-info-json.md`.

### 1.2 Compatibility & transport matrix (critical)

| Transport | AVR | ARM | Notes |
|---|:---:|:---:|---|
| `serial` — bitbang | ✅ | ✅ | Default. CPU bit-bangs one GPIO (`SOFT_SERIAL_PIN`). Single wire, half-duplex. Less efficient. |
| `serial` — USART half-duplex | ❌ | ✅ | Hardware USART, one wire. Fast, accurate, lower CPU. |
| `serial` — USART full-duplex | ❌ | ✅ | Hardware USART, two wires (separate RX/TX). Most efficient. |
| I²C | ✅ | ❌ | **AVR only.** Needs 4-wire cable + 2× 4.7 kΩ pull-ups. I²C slave on ARM is **unsupported**. |

**Both halves must use the same MCU family** (e.g. two Pro Micro-compatible, or two Blackpills). Mixing AVR + ARM is impossible: different serial methods *and* AVR is 5 V logic vs ARM's 3.3 V. Selected via `SERIAL_DRIVER = bitbang | usart | vendor` in `rules.mk` (see `13-drivers-lowlevel.md`).

> **ARM warning:** ARM split supports most subsystems over `serial`/`serial_usart`. I²C slave is unsupported. On ARM the bitbang serial driver conflicts with the bitbang WS2812 driver — use hardware drivers for both instead (see `07-led-rgb-backlight.md`, `13-drivers-lowlevel.md`).

### 1.3 Hardware / wiring

**Serial (bitbang, 3 wires):** GND, VCC, and one data line = `SOFT_SERIAL_PIN` (typically D0/D1/D2/D3, or E6). A TRS cable (3 conductors) suffices.

**Serial USART full-duplex (4 wires):** GND, VCC, RX, TX.

**I²C (4 wires):** GND, VCC, SCL (PD0/pin 3), SDA (PD1/pin 2). Needs 2× pull-up resistors. Total system pull-up should be 2.2–10 kΩ, ideal ~4.7 kΩ. Pull-ups may be on either half or split (4 resistors, one pair per half) if you want halves usable independently.

> ⚠️ **TRRS carries VCC → NOT hot-pluggable.** Always disconnect USB before (un)plugging the inter-half cable, or you can short/destroy a controller. Do not use USB cables for inter-half links — the connector can be mistaken for real USB and short the board.

### 1.4 Handedness detection (master/slave selection)

By default the firmware does not know which half is which. Methods, **in order of precedence**:

| Method | config.h define | How it works |
|---|---|---|
| **Pin** | `#define SPLIT_HAND_PIN B7` | Reads a GPIO; high = left (default), low = right. Flip with `#define SPLIT_HAND_PIN_LOW_IS_LEFT`. |
| **Matrix grid** | `#define SPLIT_HAND_MATRIX_GRID D0, F1` | Reads an *unused* matrix intersection (out pin, in pin). Diode present = right; add `#define SPLIT_HAND_MATRIX_GRID_LOW_IS_LEFT` to invert. **Gotcha:** without `MATRIX_MASKED` the phantom key looks held → can block host suspend. |
| **EEPROM** | `#define EE_HANDS` | Per-half flag in persistent storage. Must flash each half with a handedness bootloader target (see below). Survives `EE_CLR`/`eeconfig_init()` but NOT external EEPROM wipes. |
| **Compile-time `#define`** | `#define MASTER_RIGHT` / `#define MASTER_LEFT` | Only valid if USB is *always* on the same side. Default when neither set: `MASTER_LEFT`. |

**EEPROM handedness bootloader targets** (`qmk flash -kb <kb> -km <km> -bl <target>`):

| MCU / bootloader | Targets |
|---|---|
| AVR + Caterina (Pro Micro) | `avrdude-split-left`, `avrdude-split-right` |
| AVR + Atmel/DFU (Elite-C) | `dfu-split-left`, `dfu-split-right` |
| ARM + DFU (Proton-C) | `dfu-util-split-left`, `dfu-util-split-right` |
| ARM + UF2 (RP2040) | `uf2-split-left`, `uf2-split-right` |

> **Blackpill/DFU gotcha:** some DFU-bootloader boards do not retain the handedness flag between flashes — re-flash the split target every time.
>
> **VBUS vs USB-activity detection:** by default the master is the half that sees voltage on the USB VBUS pin. Many ARM boards lack VBUS detection, so `SPLIT_USB_DETECT` is auto-defined on ChibiOS/ARM. `SPLIT_USB_DETECT` instead waits for active USB communication to delegate master. **Warning: enabling `SPLIT_USB_DETECT` disables battery-pack demos** (no USB = no master delegation).
>
> Teensy 2.0 / Teensy++ 2.0 lack VBUS detection and require `SPLIT_USB_DETECT` — *or* a Schottky diode hardware mod (cut the 5V-center trace, diode from 5V pad to center pad, e.g. PMEG2005EH).

### 1.5 Communication options (config.h)

| Define | Type | Default | Meaning |
|---|---|---|---|
| `USE_I2C` | flag | unset | Use I²C transport (**AVR only**). |
| `SOFT_SERIAL_PIN` | pin | — | GPIO for serial bitbang. If also using I²C, must NOT be D0/D1 (those are I²C). Valid: D0–D3, E6. |
| `SELECT_SOFT_SERIAL_SPEED` | enum | `1` | Serial baud index. `0`≈189 kbps (experimental), `1`≈137 kbps (default), `2`≈75, `3`≈39, `4`≈26, `5`≈20 kbps. Lower if comms are flaky. |
| `FORCED_SYNC_THROTTLE_MS` | ms | `100` | Max interval between forced master→slave syncs even when data is unchanged (safety net). |
| `SPLIT_MAX_CONNECTION_ERRORS` | count | `10` | Failed attempts (one/scan) before master assumes no slave. `0` disables the disconnect check (lets you run master alone). |
| `SPLIT_CONNECTION_CHECK_TIMEOUT` | ms | `500` | After a disconnect, block reconnection attempts for this long; one retry per interval. `0` disables throttling (saves a few bytes). |
| `SPLIT_USB_DETECT` | flag | set on ARM | Delegate master by detecting active USB comms (vs VBUS voltage). Disables battery-pack demo. |
| `SPLIT_USB_TIMEOUT` | ms | `2000` | Max timeout for `SPLIT_USB_DETECT` master delegation. |
| `SPLIT_USB_TIMEOUT_POLL` | ms | `10` | Poll frequency during `SPLIT_USB_DETECT`. |
| `SPLIT_WATCHDOG_ENABLE` | flag | unset | Slave-side software watchdog; reboots if no master comms within `SPLIT_WATCHDOG_TIMEOUT`. Helps when `SPLIT_USB_DETECT` wrongly makes both halves slave. |
| `SPLIT_WATCHDOG_TIMEOUT` | ms | `3000` | Slave wait before watchdog reboot. |

### 1.6 Data sync (`SPLIT_*`) flags — the state-sync semantics

Each flag adds traffic to the inter-half protocol and **can slow the matrix scan** — enable only what you need. Direction of sync matters:

| Define | Direction | Syncs | Typical use |
|---|---|---|---|
| `SPLIT_TRANSPORT_MIRROR` | master → slave | Master's matrix state | Slave-side features reacting to master keypresses (e.g. reactive RGB on slave). |
| `SPLIT_LAYER_STATE_ENABLE` | master → slave | Active layer state | OLED showing current layer on slave half. |
| `SPLIT_LED_STATE_ENABLE` | master → slave | Host LED state (caps/num/scroll lock) | OLED indicators on slave half. |
| `SPLIT_MODS_ENABLE` | master → slave | Modifier state (normal, weak, oneshot, oneshot-locked) | OLED mod display on slave. |
| `SPLIT_WPM_ENABLE` | master → slave | Current WPM value | OLED WPM display on slave. |
| `SPLIT_OLED_ENABLE` | master → slave | OLED on/off state (state only, not framebuffer) | Keep slave OLED in sync with master. See `08-displays.md`. |
| `SPLIT_ST7565_ENABLE` | master → slave | ST7565 on/off state | Same, for ST7565 displays. |
| `SPLIT_POINTING_ENABLE` | slave → master | Pointing device reports | Use a trackball/trackpad on the slave half. **Requires extra config** — see `06-pointing-and-hid-devices.md`. |
| `SPLIT_HAPTIC_ENABLE` | master → slave | Haptic mode/dwell/buzz | Trigger haptic feedback on slave. See `09-audio-haptic.md`. |
| `SPLIT_ACTIVITY_ENABLE` | both | Activity timestamps | Activity-timeout behavior consistent across halves. |

> **Sync direction is asymmetric.** Most flags push master→slave (so the slave can mirror cosmetic state). `SPLIT_POINTING_ENABLE` is the big exception — it pulls slave→master because the pointing device physically lives on the slave and its report must reach the USB-facing master.

**RGB split** (RGBLIGHT only — see `07-led-rgb-backlight.md`):
```c
#define RGBLIGHT_SPLIT              // sync RGBLIGHT mode between halves
#define RGBLED_SPLIT { 6, 6 }       // LED count {left, right}; IMPLIES RGBLIGHT_SPLIT
```
`RGBLED_SPLIT` forcibly enables `RGBLIGHT_SPLIT` if not already set. This is for RGBLIGHT underglow strips wired directly to each controller — *not* for an "extra data wire" on the TRRS cable.

### 1.7 Custom data sync between halves (RPC transactions)

The split transport exposes arbitrary bidirectional data, modelled as remote procedure calls: the **master** invokes a handler on the **slave**, sends data, and gets data back. Define transaction IDs (comma-separated):

```c
// keyboard level:
#define SPLIT_TRANSACTION_IDS_KB   KEYBOARD_SYNC_A, KEYBOARD_SYNC_B
// user/keymap level:
#define SPLIT_TRANSACTION_IDS_USER USER_SYNC_A, USER_SYNC_B, USER_SYNC_C
```

Register a slave-side handler and call it from the master:

```c
typedef struct { int m2s_data; } master_to_slave_t;
typedef struct { int s2m_data; } slave_to_master_t;

void user_sync_a_slave_handler(uint8_t in_buflen, const void* in_data,
                               uint8_t out_buflen, void* out_data) {
    const master_to_slave_t *m2s = (const master_to_slave_t*)in_data;
    slave_to_master_t       *s2m = (slave_to_master_t*)out_data;
    s2m->s2m_data = m2s->m2s_data + 5;   // echo back +5
}

void keyboard_post_init_user(void) {
    transaction_register_rpc(USER_SYNC_A, user_sync_a_slave_handler);
}

void housekeeping_task_user(void) {
    if (is_keyboard_master()) {
        static uint32_t last_sync = 0;
        if (timer_elapsed32(last_sync) > 500) {           // throttle: 500 ms
            master_to_slave_t m2s = {6};
            slave_to_master_t s2m = {0};
            if (transaction_rpc_exec(USER_SYNC_A, sizeof(m2s), &m2s,
                                     sizeof(s2m), &s2m)) {
                last_sync = timer_read32();
                dprintf("Slave value: %d\n", s2m.s2m_data);  // 11
            } else {
                dprint("Slave sync failed!\n");
            }
        }
    }
}
```

> **Always do custom sync from the master's `housekeeping_task_user()`.** This is the right place for timely retries and keeps the matrix scan fast. See `01-architecture.md` for where `housekeeping_task` sits in the main loop.

**API:**
```c
bool transaction_register_rpc(int8_t transaction_id, rpc_slave_handler_t handler);
bool transaction_rpc_exec (int8_t id, uint8_t i2t_len, const void *i2t,
                           uint8_t t2i_len, void *t2i);   // bidirectional
bool transaction_rpc_send (int8_t id, uint8_t i2t_len, const void *i2t); // master→slave only
bool transaction_rpc_recv (int8_t id, uint8_t t2i_len, void *t2i);       // slave→master only
```

Default buffer cap is **32 bytes each way**; override:
```c
#define RPC_M2S_BUFFER_SIZE 48   // master → slave
#define RPC_S2M_BUFFER_SIZE 48   // slave → master
```

### 1.8 Hardware-config options (asymmetric halves)

```c
#define MATRIX_ROW_PINS_RIGHT { ... }   // right-half row pins (count must match left; pad with NO_PIN)
#define MATRIX_COL_PINS_RIGHT { ... }   // right-half col pins
#define DIRECT_PINS_RIGHT     { { ... }, { ... } }   // right-half direct pins
#define ENCODER_A_PINS_RIGHT  { ... }   // right-half encoder A pins
#define ENCODER_B_PINS_RIGHT  { ... }   // right-half encoder B pins
```
For asymmetric boards (e.g. Keebio Quefrency): pin counts per side must match; pad the smaller side with `NO_PIN` and account for the unused rows/cols in the matrix layout. (See `08-displays.md` for encoder specifics, `03-config-and-info-json.md` for layout macros.)

### 1.9 Layout macro consequence

Split keyboards double the **rows** (not columns) in QMK's view: matrix scan fills the left half's rows first, then the right half's. Your `LAYOUT(...)` macro must list keys in that left-then-right row order. This surprises people who expect doubled columns.

### Gotchas — Split Keyboard
- **I²C split is AVR-only.** ARM I²C slave is unsupported. Modern advice: use `serial` (bitbang on AVR, USART on ARM).
- **No three-half splits.** The serial driver caps at two halves.
- **Mixed MCU families impossible** (AVR↔ARM): incompatible serial *and* voltage levels.
- **TRRS carries VCC → not hot-pluggable.** Disconnect USB before (un)plugging the inter-half cable.
- **`SPLIT_USB_DETECT` disables battery-pack demos** and is auto-enabled on ARM/ChibiOS.
- **`SPLIT_HAND_MATRIX_GRID` without `MATRIX_MASKED`** registers a phantom key → can block host suspend.
- **Blackpill/DFU** may lose EEPROM handedness on every flash — re-flash the split target each time.
- **`EE_HANDS` survives `EE_CLR`/`eeconfig_init()` but NOT external EEPROM wipes** (QMK Toolbox "Reset EEPROM" button, avrdude EEPROM file flashes). Re-flash the split bootloader target after such a wipe.
- **`SPLIT_*` sync flags add scan-cycle overhead** — only enable what you use.
- **`RGBLED_SPLIT` implies `RGBLIGHT_SPLIT`** (forcibly enables it).
- **Custom RPC sync should run in `housekeeping_task_user()` on the master**, throttled, to avoid starving the matrix scan.
- **Bitbang serial + bitbang WS2812 on ARM conflict** — pick hardware drivers for both.
- Default handedness when nothing is configured: `MASTER_LEFT`.

---

## 2. Wireless / Bluetooth

### Summary
Lets the keyboard send its HID report over Bluetooth instead of (or switchable with) USB. QMK's BT support is **AVR-only** and narrow: Bluetooth Classic via the **RN-42** module (UART), or **BLE** via the Adafruit **Bluefruit LE SPI Friend** (nRF51822, SPI). BLE is required to talk to iOS (iOS does not support mouse input over BT).

### 2.1 Enable it

```make
# rules.mk
BLUETOOTH_ENABLE = yes
BLUETOOTH_DRIVER = bluefruit_le   # or rn42
NKRO_ENABLE      = no             # REQUIRED: supported BT chips do not support NKRO
```

> **`NKRO_ENABLE = no` is mandatory.** RN-42 and Bluefruit LE cannot do N-key rollover. Leaving NKRO on breaks the BT report.

### 2.2 Supported hardware

| Board | BT protocol | Bus | `BLUETOOTH_DRIVER` | Chip |
|---|---|---|---|---|
| Roving Networks **RN-42** (Sparkfun BlueSMiRF) | Bluetooth Classic (2.1 + EDR) | UART | `rn42` | RN-42 |
| Adafruit **Bluefruit LE SPI Friend** | BLE | SPI | `bluefruit_le` | nRF51822 |

**Not yet supported** (possible community ports): Bluefruit LE UART Friend, HC-05 flashed with RN-42 firmware (shared CSR BC417), Sparkfun Bluetooth Mate, HM-13 boards.

> **BLE + BREDR coexistence caveat:** the two supported drivers target different radio stacks (Classic vs BLE). QMK does not ship a dual-mode driver; you pick one. iOS needs BLE; Classic (RN-42) won't pair with iOS.

### 2.3 Bluefruit LE SPI Friend wiring (config.h)

The Feather 32u4 Bluefruit LE is supported out of the box (AVR MCU + SPI to the Nordic chip with Adafruit firmware). For custom boards, easiest to copy the Feather pinout; otherwise override:
```c
#define BLUEFRUIT_LE_RST_PIN D4
#define BLUEFRUIT_LE_CS_PIN  B4
#define BLUEFRUIT_LE_IRQ_PIN E6
```
Data goes via Adafruit's **SDEP** protocol over hardware SPI. A Bluefruit **UART** Friend can be converted to SPI but requires reflashing + soldering directly to the MDBT40 chip.

### 2.4 Output-selection keycodes

Used on keyboards that can output over multiple transports (USB + BT). Most are **not yet implemented** — only `OU_AUTO`, `OU_USB`, `OU_BT` currently function.

| Key | Alias | Description |
|---|---|---|
| `QK_OUTPUT_AUTO` | `OU_AUTO` | Auto: USB when plugged in, else wireless |
| `QK_OUTPUT_USB` | `OU_USB` | Output to USB only |
| `QK_OUTPUT_BLUETOOTH` | `OU_BT` | Output to Bluetooth only |
| `QK_OUTPUT_NEXT` | `OU_NEXT` | Cycle forward USB→BT→2.4GHz **(not implemented)** |
| `QK_OUTPUT_PREV` | `OU_PREV` | Cycle backward **(not implemented)** |
| `QK_OUTPUT_NONE` | `OU_NONE` | Disable all output **(not implemented)** |
| `QK_OUTPUT_2P4GHZ` | `OU_2P4G` | 2.4 GHz only **(not implemented)** |
| `QK_BLUETOOTH_PROFILE_NEXT` | `BT_NEXT` | Next BT profile **(not implemented)** |
| `QK_BLUETOOTH_PROFILE_PREV` | `BT_PREV` | Previous BT profile **(not implemented)** |
| `QK_BLUETOOTH_UNPAIR` | `BT_UNPR` | Unpair current profile **(not implemented)** |
| `QK_BLUETOOTH_PROFILE1`..`5` | `BT_PRF1`..`BT_PRF5` | Swap to BT profile #1–5 **(not implemented)** |

### Gotchas — Wireless/BT
- **AVR-only.** No ARM BT support in-tree.
- **`NKRO_ENABLE = no` is required** or BT reports break.
- **Most `BT_*` / `OU_*` keycodes are not yet implemented** — only `OU_AUTO`/`OU_USB`/`OU_BT` work today.
- **iOS needs BLE** (Bluefruit); Classic/RN-42 won't pair. **iOS does not support mouse input** over BT.
- **No dual-mode (Classic + BLE) driver** — pick one `BLUETOOTH_DRIVER`.
- Wireless splits: pair with `SPLIT_USB_DETECT` and the §0 caveats; supported BT chips are AVR-only while ARM splits need ARM halves → can't mix.

---

## 3. Command (formerly "Magic")

### Summary
A hidden, on-keyboard console: hold the **Command combo** (default Left Shift + Right Shift) and tap a key to toggle debug flags, jump to the bootloader, clear EEPROM, switch NKRO, or print the QMK version. Overlaps heavily with the **Magic keycodes**; QMK recommends Magic keycodes where possible. Disabled by default on some keyboards — enable explicitly.

### 3.1 Enable it

```make
# rules.mk
COMMAND_ENABLE = yes
```

### 3.2 Configuration (config.h)

The activation combo and per-command key bindings are all `config.h` `#define`s. **All key assignments omit the `KC_` prefix** (e.g. `BSPACE`, not `KC_BSPACE`).

| Define | Default | Description |
|---|---|---|
| `IS_COMMAND()` | `(get_mods() == MOD_MASK_SHIFT)` | The modifier combo that activates Command (LShift+RShift). |
| `MAGIC_KEY_SWITCH_LAYER_WITH_FKEYS` | `true` | Set default layer via the Function row. |
| `MAGIC_KEY_SWITCH_LAYER_WITH_NKEYS` | `true` | Set default layer via number keys. |
| `MAGIC_KEY_SWITCH_LAYER_WITH_CUSTOM` | `false` | Set default layer via `MAGIC_KEY_LAYER0..9`. |
| `MAGIC_KEY_DEBUG` | `D` | Toggle debug-over-serial. |
| `MAGIC_KEY_DEBUG_MATRIX` | `X` | Toggle key-matrix debug. |
| `MAGIC_KEY_DEBUG_KBD` | `K` | Toggle keyboard debug. |
| `MAGIC_KEY_DEBUG_MOUSE` | `M` | Toggle mouse debug. |
| `MAGIC_KEY_CONSOLE` | `C` | Enable the Command console. |
| `MAGIC_KEY_VERSION` | `V` | Print running QMK version to console. |
| `MAGIC_KEY_STATUS` | `S` | Print current keyboard status. |
| `MAGIC_KEY_HELP` | `H` | Print Command help. |
| `MAGIC_KEY_HELP_ALT` | `SLASH` | Help (alternate key). |
| `MAGIC_KEY_LAYER0` | `0` | Make layer 0 default. |
| `MAGIC_KEY_LAYER0_ALT` | `GRAVE` | Layer 0 default (alternate). |
| `MAGIC_KEY_LAYER1`..`9` | `1`..`9` | Make layer 1–9 default. |
| `MAGIC_KEY_BOOTLOADER` | `B` | Jump to bootloader. |
| `MAGIC_KEY_BOOTLOADER_ALT` | `ESC` | Bootloader (alternate). |
| `MAGIC_KEY_LOCK` | `CAPS` | Lock keyboard (no typing). |
| `MAGIC_KEY_EEPROM` | `E` | Print stored EEPROM config. |
| `MAGIC_KEY_EEPROM_CLEAR` | `BSPACE` | Clear EEPROM. |
| `MAGIC_KEY_NKRO` | `N` | Toggle N-key rollover. |
| `MAGIC_KEY_SLEEP_LED` | `Z` | Toggle sleep LED. |

### 3.3 Behavior & ordering
- Command intercepts keys **after** the modifier combo (`IS_COMMAND()`) is held. It is a host-side debug affordance, not part of the normal `process_record_user` chain the way feature keycodes are.
- Magic keycodes (`04-keymaps-and-keycodes.md`) are the modern, preferred equivalent for the runtime toggles (NKRO, default layer, etc.).
- Needs `CONSOLE_ENABLE = yes` to actually print to `qmk console` / QMK Toolbox for the `V`/`S`/`E`/`H` commands.

### Gotchas — Command
- **Disabled by default on some keyboards** — set `COMMAND_ENABLE = yes` explicitly.
- **Key bindings omit the `KC_` prefix** (`BSPACE`, `GRAVE`, `SLASH`, `CAPS`, `ESC`).
- Overlaps Magic keycodes — prefer Magic keycodes for runtime toggles.
- Debug/console output needs `CONSOLE_ENABLE = yes`.
- Conflicts with keymaps that *use* LShift+RShift as a real chord — redefine `IS_COMMAND()`.

---

## 4. Secure

### Summary
Locks the keyboard so input is ignored until the user performs a configured **unlock sequence** (one or more matrix locations, in order). After unlock, an idle timeout re-locks. Intended as a soft gate against unwanted interaction — **not** encryption or strong security.

> ⚠️ **Secure is NOT a security boundary.** It implements no crypto. Don't use it where real hardware/software security is required.

### 4.1 Enable it

```make
# rules.mk
SECURE_ENABLE = yes
```

### 4.2 Keycodes

| Key | Alias | Description |
|---|---|---|
| `QK_SECURE_LOCK` | `SE_LOCK` | Revert to locked state. |
| `QK_SECURE_UNLOCK` | `SE_UNLK` | Force unlock *without* the unlock sequence. |
| `QK_SECURE_TOGGLE` | `SE_TOGG` | Toggle locked/unlocked without the sequence. |
| `QK_SECURE_REQUEST` | `SE_REQ` | Request the user perform the unlock sequence. |

### 4.3 Configuration (config.h)

| Define | Default | Description |
|---|---|---|
| `SECURE_UNLOCK_TIMEOUT` | `5000` | ms the user has to perform the unlock sequence. `0` disables (no timeout). |
| `SECURE_IDLE_TIMEOUT` | `60000` | ms unlocked before auto re-lock. `0` disables. |
| `SECURE_UNLOCK_SEQUENCE` | `{ { 0, 0 } }` | Array of `{row, col}` matrix locations — the sequential keypress sequence required to unlock. |

### 4.4 Functions / hooks

| Function | Description |
|---|---|
| `secure_is_locked()` | True if currently locked. |
| `secure_is_unlocking()` | True if an unlock sequence is in progress. |
| `secure_is_unlocked()` | True if currently unlocked. |
| `secure_lock()` | Lock the device. |
| `secure_unlock()` | Force unlock (bypasses the user sequence). |
| `secure_request_unlock()` | Begin listening for the unlock sequence. |
| `secure_activity_event()` | Flag user activity → refresh the idle timeout, stay unlocked. Call from any hook (`process_record_user`, `housekeeping_task_user`, etc.). |

### 4.5 Behavior
- **While unlocking, all keyboard input is ignored.**
- An incorrect attempt reverts to the previously locked state.
- `secure_activity_event()` is how you keep the device awake — call it from the hooks in `01-architecture.md` (e.g. on every keypress).

### Gotchas — Secure
- **Not cryptographic.** A soft gate only.
- Default unlock sequence `{ { 0, 0 } }` is a single key — set `SECURE_UNLOCK_SEQUENCE` to something real.
- Unlock sequence entries are **matrix `{row,col}` locations**, not keycodes.
- All input is dropped during an unlock attempt.

---

## 5. OS Detection

### Summary
Best-effort guess of the host OS (Linux / Windows / macOS / iOS / unsure) by observing OS-specific behavior during USB descriptor setup. Enables OS-specific keymaps, combos, or lighting. **Not reliable for critical functionality** — treat as a hint. Available on **ChibiOS, LUFA, and V-USB** backends.

### 5.1 Enable it

```make
# rules.mk
OS_DETECTION_ENABLE = yes
```
Auto-includes the needed header. Declares `os_variant_t detected_host_os(void);`.

### 5.2 Return values

```c
enum {
    OS_UNSURE,
    OS_LINUX,
    OS_WINDOWS,
    OS_MACOS,
    OS_IOS,
} os_variant_t;
```

> ⚠️ **Detection is not instant.** It stabilizes over hundreds of ms after boot. The result is **not** ready in early functions like `keyboard_init` / layout setup — query it later (e.g. in `housekeeping_task_user`) or use the callback below.

### 5.3 Callbacks

```c
// keyboard level (keyboard.c):
bool process_detected_host_os_kb(os_variant_t detected_os);
// user level (keymap.c):
bool process_detected_host_os_user(os_variant_t detected_os);
```
The `_kb` variant should call `_user` and bail if it returns `false` (standard QMK chain convention — see `01-architecture.md`). Fires once the debounced result is stable.

```c
bool process_detected_host_os_kb(os_variant_t detected_os) {
    if (!process_detected_host_os_user(detected_os)) return false;
    switch (detected_os) {
        case OS_MACOS: case OS_IOS:  rgb_matrix_set_color_all(RGB_WHITE); break;
        case OS_WINDOWS:             rgb_matrix_set_color_all(RGB_BLUE);  break;
        case OS_LINUX:               rgb_matrix_set_color_all(RGB_ORANGE);break;
        case OS_UNSURE:              rgb_matrix_set_color_all(RGB_RED);   break;
    }
    return true;
}
```

### 5.4 Configuration (config.h)

| Define | Default | Description |
|---|---|---|
| `OS_DETECTION_DEBOUNCE` | `250` | ms the result must be stable before callbacks fire. Raise if your board is noisy. |
| `OS_DETECTION_KEYBOARD_RESET` | unset | Reset the keyboard on USB device reinit. Helps with some KVMs that keep USB powered during switching. |
| `OS_DETECTION_SINGLE_REPORT` | unset | Fire callbacks only once (on first stable result); ignore later changes. Helps when callbacks recur minutes after startup (notably macOS on ARM Macs). |
| `OS_DETECTION_DEBUG_ENABLE` | unset | Log USB setup packets for refining detection. Needs `CONSOLE_ENABLE = yes`. |

### 5.5 Debug (collecting fingerprints for mis-detected OSes)

`config.h`: `#define OS_DETECTION_DEBUG_ENABLE`
`rules.mk`: `COMMAND_ENABLE`/`CONSOLE_ENABLE = yes`
`keymap.c`: `#include "os_detection.h"`, then bind custom keycodes:

```c
enum custom_keycodes { STORE_SETUPS = SAFE_RANGE, PRINT_SETUPS };

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case STORE_SETUPS:
            if (record->event.pressed) store_setups_in_eeprom();
            return false;
        case PRINT_SETUPS:
            if (record->event.pressed) print_stored_setups();
            return false;
        default: return true;
    }
}
```
Press `STORE_SETUPS` on the mis-detecting host, then `PRINT_SETUPS` on a dev machine running `qmk console` and submit the output upstream.

> **EEPROM caveat:** if `STORE_SETUPS` was never run, `PRINT_SETUPS` prints whatever garbage is already in EEPROM — looks like random numbers.

### Gotchas — OS Detection
- **Best-effort, not authoritative** — don't gate critical behavior on it.
- **Not ready at boot** — hundreds of ms delay; not available in `keyboard_init`/layout setup.
- **KVMs break it** — some keep USB powered through switching so no reinit occurs. Fix with `OS_DETECTION_KEYBOARD_RESET`.
- **macOS on ARM Macs can fire callbacks minutes later** — use `OS_DETECTION_SINGLE_REPORT`.
- Original technique from the [FingerprintUSBHost](https://github.com/keyboardio/FingerprintUSBHost) project.

---

## 6. Raw HID

### Summary
Bidirectional, fixed-size HID reports between QMK and a host program — the foundation for **VIA/Vial** and any custom host tooling (live keymap switching, sending CPU/RAM metrics, etc.). You implement `raw_hid_receive()` on the keyboard and write a host-side program (node-hid, hidapi, etc.) to talk to it.

> **This is the substrate VIA uses.** Same usage page `0xFF60` / usage `0x61`. See `14-configurator-api-via.md` for the VIA protocol layered on top.

### 6.1 Enable it

```make
# rules.mk
RAW_ENABLE = yes
```

### 6.2 Configuration (config.h)

| Define | Default | Description |
|---|---|---|
| `RAW_USAGE_PAGE` | `0xFF60` | HID usage page of the Raw HID interface (vendor-defined). |
| `RAW_USAGE_ID` | `0x61` | HID usage ID of the Raw HID interface. |

These defaults (`0xFF60`/`0x61`) are the **VIA convention** — changing them will break VIA/Vial and most existing host tools.

### 6.3 Packet size — the cardinal rule

All reports in **both directions are exactly `RAW_EPSIZE` (32) bytes**, regardless of payload. The HID spec has no variable-length reports. Implement variable-length payloads yourself by framing across multiple 32-byte reports.

> The dedicated Raw HID endpoint vs. the shared-endpoint model: when Raw HID shares an endpoint with other HID interfaces (the default on space-constrained AVR), throughput/latency can suffer; a dedicated endpoint gives clean 32-byte framing. Either way the contract is fixed 32-byte reports.

### 6.4 C API / callbacks

```c
// Invoked when a raw HID report arrives from the host. Implement in keymap.c.
void raw_hid_receive(uint8_t *data, uint8_t length);
//   data   - pointer to the received buffer; length is always RAW_EPSIZE (32)
//   length - always 32

// Send an HID report back to the host. Buffer must be 32 bytes; length must be RAW_EPSIZE.
void raw_hid_send(uint8_t *data, uint8_t length);
```
These are **`_user`-level** callbacks (you implement them in your keymap). There is no `_kb` split for the receive callback in user code; keyboards may also implement them, but for a keymap author the contract is the same.

### 6.5 Example (keyboard side)

Echo: if the first byte is ASCII `'A'`, reply with `'B'`. `memset` clears stale response bytes.

```c
void raw_hid_receive(uint8_t *data, uint8_t length) {
    uint8_t response[length];
    memset(response, 0, length);
    response[0] = 'B';
    if (data[0] == 'A') {
        raw_hid_send(response, length);
    }
}
```

### 6.6 Host side

Find the keyboard's USB VID/PID in its `info.json` under `usb` (or via `lsusb` / Device Manager / System Information). Open by enumerating interfaces and **filtering on usage page + usage ID** so you don't accidentally grab the keyboard/mouse/media interface.

Common libraries: **Node.js** [node-hid](https://github.com/node-hid/node-hid); **C/C++** [hidapi](https://github.com/libusb/hidapi); **Java** [purejavahidapi](https://github.com/nyholku/purejavahidapi) / [hid4java](https://github.com/gary-rowe/hid4java); **Python** [`hid`](https://pypi.org/project/hid/) (install with `pip install hid`, `import hid`) and [pywinusb](https://pypi.org/project/pywinusb/).

> ⚠️ **Python `hid` vs `pyhidapi`:** install `hid` (`pip install hid`). Do **not** install `pyhidapi` from PyPI — different, unmaintained project with a confusingly similar name.

Minimal Python (filter by VID/PID + usage page/ID, send `0x41`, read response):

```python
import sys, hid

vendor_id  = 0x4335
product_id = 0x0002
usage_page = 0xFF60
usage      = 0x61
report_length = 32

def get_raw_hid_interface():
    ifs = hid.enumerate(vendor_id, product_id)
    raw = [i for i in ifs if i['usage_page'] == usage_page and i['usage'] == usage]
    if not raw:
        return None
    return hid.Device(path=raw[0]['path'])

def send_raw_report(data):
    dev = get_raw_hid_interface()
    if dev is None:
        print("No device found"); sys.exit(1)
    try:
        report = bytes([0x00] * (report_length + 1))   # first byte = Report ID
        report = bytearray(report)
        report[1:len(data)+1] = data
        dev.write(report)
        print("Response:", dev.read(report_length, timeout=1000))
    finally:
        dev.close()

if __name__ == '__main__':
    send_raw_report([0x41])
```

### Gotchas — Raw HID
- **Reports are always exactly 32 bytes (`RAW_EPSIZE`)** both ways — pad your payload.
- **`0xFF60`/`0x61` are the VIA defaults** — changing them breaks VIA/Vial and existing host tools.
- **Collides with VIA** if you write your own host tool on the same endpoint. Coordinate or pick a new usage ID (and update VIA config accordingly).
- **Always close the HID device** when done (host-side).
- **Python:** install `hid`, not `pyhidapi`.
- **Filter host enumeration by usage page + usage ID** to avoid opening the keyboard/mouse/media interface.
- Host report buffers typically need a leading Report ID byte (see Python example).

---

## 7. Battery

### Summary
High-level battery-percentage sampling for wireless builds. Periodically samples the cell via a configurable driver (ADC w/ voltage divider by default, vendor, or custom) and exposes the result plus change callbacks. The actual silicon-level driver config lives in `13-drivers-lowlevel.md` (`docs/drivers/battery.md`).

### 7.1 Enable it

```make
# rules.mk
BATTERY_ENABLE = yes
```
This auto-pulls in the battery driver requirement. To select/override the driver:
```make
BATTERY_DRIVER = adc        # default. also: vendor | custom
BATTERY_DRIVER_REQUIRED = yes   # set explicitly if using the driver without the feature
```

### 7.2 Configuration

Feature-level (config.h):

| Define | Default | Description |
|---|---|---|
| `BATTERY_SAMPLE_INTERVAL` | `30000` | ms between battery samples. |

ADC driver (config.h) — assumes the cell feeds an ADC-capable pin through a voltage divider:

| Define | Default | Description |
|---|---|---|
| `BATTERY_ADC_PIN` | *(unset)* | GPIO pin connected to the voltage divider. **Must be set.** |
| `BATTERY_ADC_REF_VOLTAGE_MV` | `3300` | ADC reference voltage, in millivolts. |
| `BATTERY_ADC_VOLTAGE_DIVIDER_R1` | `100` | Divider R1, in kΩ. `0` disables. |
| `BATTERY_ADC_VOLTAGE_DIVIDER_R2` | `100` | Divider R2, in kΩ. `0` disables. |
| `BATTERY_ADC_RESOLUTION` | `10` | ADC resolution (bits) configured for the ADC driver. |

> The ADC driver relies on the underlying ADC peripheral driver — see `13-drivers-lowlevel.md` for ADC channel setup and platform notes.

### 7.3 Custom driver

If `BATTERY_DRIVER = custom`, implement:
```c
void   battery_driver_init(void);          // one-time init
uint8_t battery_driver_sample_percent(void); // return 0–100
```

### 7.4 Functions / callbacks

```c
uint8_t battery_get_percent(void);                  // current battery %, 0–100

void battery_percent_changed_kb(uint8_t level);     // keyboard-level hook
void battery_percent_changed_user(uint8_t level);   // user/keymap hook
//   level - battery percentage 0–100; fired when the sampled value changes
```

### Gotchas — Battery
- Default sampling is **30 s** (`BATTERY_SAMPLE_INTERVAL`) — finer polling costs power.
- ADC driver needs `BATTERY_ADC_PIN` set and a correctly sized voltage divider; default R1=R2=100 kΩ assumes a specific ratio — calibrate to your hardware.
- Only meaningful for wireless builds (§2); wired keyboards have no battery.
- Vendor/custom drivers require their own platform integration (`13-drivers-lowlevel.md`).
- Wireless + battery + `SPLIT_USB_DETECT`: see §0 — `SPLIT_USB_DETECT` breaks battery-pack demos.

---

## Appendix — cross-feature quick map

| If you're building... | Relevant sections |
|---|---|
| Wired split (two Pro Micros, TRRS) | §1 (serial bitbang), `SPLIT_HAND_PIN`/`EE_HANDS` |
| Wired split on ARM | §1 (USART half/full-duplex), auto `SPLIT_USB_DETECT` |
| Wireless split | §1 + §2 + §7; AVR-only BT, `NKRO_ENABLE=no`, `SPLIT_USB_DETECT` caveat |
| VIA-configurable board | §6 (raw HID) + `14-configurator-api-via.md` |
| OS-aware keymap | §5 + layer logic in `04-keymaps-and-keycodes.md` |
| Lockable kiosk keyboard | §4 (Secure) |
| On-keyboard debug | §3 (Command) + `15-flashing-debugging.md` |
