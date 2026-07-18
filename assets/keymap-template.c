/*
 * keymap.c — QMK keymap template
 * ------------------------------------------------------------------
 * Drop this into keyboards/<keyboard>/keymaps/<name>/keymap.c (or your
 * userspace).  It demonstrates the idiomatic patterns the agent should
 * follow: layer enum, the keymaps[] array via the keyboard's LAYOUT()
 * macro, custom keycodes with SAFE_RANGE / QK_USER, process_record_user
 * (with correct return semantics), and a few common callbacks.
 *
 * Read references/04-keymaps-and-keycodes.md and references/01-architecture.md
 * before editing.  Read references/00-cross-cutting-gotchas.md for traps.
 *
 * Enable features in rules.mk (or info.json `features`), e.g.:
 *   TAP_DANCE_ENABLE = yes
 *   COMBO_ENABLE = yes
 *   RGBLIGHT_ENABLE = yes
 */
#include QMK_KEYBOARD_H

// ---- Layers ----------------------------------------------------------------
// Name your layers for readability. Layer 0 is the default/base layer.
enum layer_names {
    _BASE,
    _LOWER,
    _RAISE,
    _ADJUST,
};

// ---- Custom keycodes -------------------------------------------------------
// For NEW keymaps/PRs targeting upstream QMK, the FIRST entry MUST be QK_USER.
// For personal/userspace keymaps, SAFE_RANGE as the first entry still works.
enum custom_keycodes {
    QK_USER,            // <- required anchor for upstream PRs (keep first)
    MY_CUSTOM_1 = SAFE_RANGE,
    MY_CUSTOM_2,
};

// Shortcuts for transparent / noop (provided by default, shown for clarity)
// #define _______ KC_TRNS
// #define XXXXXXX KC_NO

// ---- Keymap ----------------------------------------------------------------
// Use the keyboard's LAYOUT() macro (generated from info.json `layouts`).
// Higher layers override lower; KC_TRNS falls through, KC_NO blocks.
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [_BASE] = LAYOUT(
        KC_Q,    KC_W,    KC_E,    KC_R,    KC_T,        KC_Y,    KC_U,    KC_I,    KC_O,    KC_P,
        KC_A,    KC_S,    KC_D,    KC_F,    KC_G,        KC_H,    KC_J,    KC_K,    KC_L,    KC_SCLN,
        KC_Z,    KC_X,    KC_C,    KC_V,    KC_B,        KC_N,    KC_M,    KC_COMM, KC_DOT,  KC_SLSH,
        KC_LCTL, KC_LGUI, KC_LALT, MO(_LOWER), KC_SPC,   KC_ENT,  MO(_RAISE), KC_RALT, KC_RGUI, KC_RCTL
    ),
    [_LOWER] = LAYOUT(
        KC_1,    KC_2,    KC_3,    KC_4,    KC_5,        KC_6,    KC_7,    KC_8,    KC_9,    KC_0,
        _______, _______, _______, _______, _______,     _______, _______, _______, _______, _______,
        _______, _______, _______, _______, _______,     _______, _______, _______, _______, _______,
        _______, _______, _______, _______, _______,     _______, _______, _______, _______, _______
    ),
    [_RAISE] = LAYOUT(
        KC_F1,   KC_F2,   KC_F3,   KC_F4,   KC_F5,       KC_F6,   KC_F7,   KC_F8,   KC_F9,   KC_F10,
        _______, _______, _______, _______, _______,     _______, _______, _______, _______, _______,
        _______, _______, _______, _______, _______,     _______, _______, _______, _______, _______,
        _______, _______, _______, _______, _______,     _______, _______, _______, MO(_ADJUST), _______
    ),
    [_ADJUST] = LAYOUT(
        QK_BOOT, _______, _______, _______, _______,     _______, _______, _______, _______, _______,
        _______, _______, _______, _______, _______,     _______, _______, _______, _______, _______,
        _______, _______, _______, _______, _______,     _______, _______, _______, _______, _______,
        _______, _______, _______, _______, _______,     _______, _______, _______, _______, _______
    ),
};

// ---- process_record_user ---------------------------------------------------
// Runs DURING the key-processing chain, BEFORE most feature handlers.
// RETURN SEMANTICS (critical, see references/00 §A):
//   return true  -> let QMK keep processing (default).
//   return false -> HALT the entire downstream chain (including layer keycodes
//                   like MO/LT!). Only return false when you have fully handled
//                   the key, and reproduce any behaviour you are suppressing.
bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case MY_CUSTOM_1:
            if (record->event.pressed) {
                SEND_STRING("Hello!");
            }
            return false;  // handled — stop further processing
        case MY_CUSTOM_2:
            if (record->event.pressed) {
                // example: toggle a layer on tap, do nothing on hold
                tap_code(KC_ESC);
            }
            return false;
    }
    return true;  // let everything else through
}

// ---- Per-scan hook (runs hundreds of times/sec — keep it cheap!) -----------
void matrix_scan_user(void) {
    // read a sensor, update state machines, etc.  No sleeping/polling.
}

// ---- Layer change hook -----------------------------------------------------
layer_state_t layer_state_set_user(layer_state_t state) {
    // Example tri-layer: ADJUST = LOWER + RAISE both active (see references/05).
    //   return update_tri_layer_state(state, _LOWER, _RAISE, _ADJUST);
    return state;
}

// ---- Status LED / indicator hook (see references/07) -----------------------
bool led_update_user(led_t led_state) {
    return true;  // return false to stop the keyboard-level handler from running
}

// ---- Encoder (if ENCODER_ENABLE; see references/08) ------------------------
#ifdef ENCODER_ENABLE
bool encoder_update_user(uint8_t index, bool clockwise) {
    if (index == 0) {
        tap_code(clockwise ? KC_VOLU : KC_VOLD);
    }
    return false;  // return false to suppress default volume behavior
}
#endif

// ---- OLED (if OLED_ENABLE; see references/08) ------------------------------
#ifdef OLED_ENABLE
bool oled_task_user(void) {
    oled_write_P(PSTR("Layer: "), false);
    switch (get_highest_layer(layer_state)) {
        case _BASE:   oled_write_ln_P(PSTR("Base"),   false); break;
        case _LOWER:  oled_write_ln_P(PSTR("Lower"),  false); break;
        case _RAISE:  oled_write_ln_P(PSTR("Raise"),  false); break;
        case _ADJUST: oled_write_ln_P(PSTR("Adjust"), false); break;
        default:      oled_write_ln_P(PSTR("?"),      false); break;
    }
    return false;  // returning false lets the keyboard-level oled handler run too
}
#endif
