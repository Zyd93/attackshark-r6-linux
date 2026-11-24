"""Hardware constants, protocol enums, and USB HID keycode tables for ATTACK SHARK R6."""

from __future__ import annotations

from enum import IntEnum, IntFlag
from typing import Dict, List, Optional, Tuple

VENDOR_ID = 0x373E
WIRED_PID = 0x0021
WIRELESS_PID = 0x0022

SUPPORTED_PIDS: Dict[int, str] = {
    WIRED_PID: "Wired",
    WIRELESS_PID: "Wireless 2.4G",
}

REPORT_SIZE = 65
WIRE_REPORT_SIZE = 64

CONTROL_USAGE_PAGE = 0xFFFF
NOTIFY_USAGE_PAGE = 0xFFA0
NOTIFY_REPORT_ID = 0x04

STATUS_OK = 0xA1

TARGET_DONGLE = 0x00
TARGET_DONGLE_CTRL = 0x01
TARGET_MOUSE = 0x02

PROFILE_MIN = 1
PROFILE_MAX = 3

DPI_MIN = 50
DPI_MAX = 42000
DPI_STEP = 50
DPI_MAX_STAGES = 6

DEFAULT_DPI_COLORS: List[Tuple[int, int, int]] = [
    (0xFF, 0x00, 0x00),  # Red
    (0x00, 0x00, 0xFF),  # Blue
    (0x00, 0xFF, 0x00),  # Green
    (0xFF, 0x00, 0xFF),  # Magenta
    (0xFF, 0xFF, 0x00),  # Yellow
    (0xFF, 0xFF, 0xFF),  # White
]

SLEEP_MIN_SEC = 15
SLEEP_MAX_SEC = 1800
SLEEP_DISABLED = 0xFFFF
DEFAULT_SLEEP_SEC = 900

DEBOUNCE_MIN_MS = 0
DEBOUNCE_MAX_MS = 15

MACRO_MIN_ID = 1
MACRO_MAX_ID = 29
MACRO_CHUNK_SIZE = 51  # 0x33 bytes per packet


class ButtonID(IntEnum):
    NA1 = 0
    LEFT = 1
    RIGHT = 2
    MIDDLE = 3
    BACKWARD = 4
    FORWARD = 5
    BUTTON6 = 6
    BUTTON7 = 7
    BUTTON8 = 8
    NA2 = 9
    SCROLL_UP = 16
    SCROLL_DOWN = 17
    DPI_UP = 18
    DPI_DOWN = 19
    DPI_LOOP_UP = 20
    DPI_LOOP_DOWN = 21


BUTTON_LABELS: Dict[ButtonID, str] = {
    ButtonID.LEFT: "Left Button",
    ButtonID.RIGHT: "Right Button",
    ButtonID.MIDDLE: "Middle Button",
    ButtonID.BACKWARD: "Backward",
    ButtonID.FORWARD: "Forward",
    ButtonID.SCROLL_UP: "Scroll Up",
    ButtonID.SCROLL_DOWN: "Scroll Down",
    ButtonID.DPI_LOOP_UP: "DPI Button",
}

CONFIGURABLE_BUTTONS: List[ButtonID] = [
    ButtonID.LEFT,
    ButtonID.RIGHT,
    ButtonID.MIDDLE,
    ButtonID.BACKWARD,
    ButtonID.FORWARD,
    ButtonID.SCROLL_UP,
    ButtonID.SCROLL_DOWN,
]

BUTTON_ALIASES: Dict[str, ButtonID] = {
    "left": ButtonID.LEFT,
    "leftbutton": ButtonID.LEFT,
    "lmb": ButtonID.LEFT,
    "1": ButtonID.LEFT,
    "right": ButtonID.RIGHT,
    "rightbutton": ButtonID.RIGHT,
    "rmb": ButtonID.RIGHT,
    "2": ButtonID.RIGHT,
    "middle": ButtonID.MIDDLE,
    "middlebutton": ButtonID.MIDDLE,
    "mmb": ButtonID.MIDDLE,
    "3": ButtonID.MIDDLE,
    "backward": ButtonID.BACKWARD,
    "back": ButtonID.BACKWARD,
    "4": ButtonID.BACKWARD,
    "forward": ButtonID.FORWARD,
    "5": ButtonID.FORWARD,
    "scrollup": ButtonID.SCROLL_UP,
    "wheelup": ButtonID.SCROLL_UP,
    "16": ButtonID.SCROLL_UP,
    "scrolldown": ButtonID.SCROLL_DOWN,
    "wheeldown": ButtonID.SCROLL_DOWN,
    "17": ButtonID.SCROLL_DOWN,
    "dpi": ButtonID.DPI_LOOP_UP,
    "dpibutton": ButtonID.DPI_LOOP_UP,
    "dpiloopup": ButtonID.DPI_LOOP_UP,
    "20": ButtonID.DPI_LOOP_UP,
    "dpiloopdown": ButtonID.DPI_LOOP_DOWN,
    "21": ButtonID.DPI_LOOP_DOWN,
}


class FunctionID(IntEnum):
    OFF = 0x00
    BUTTON_CODE = 0x01
    X_CLICK = 0x02
    KEYBOARD_CODE = 0x04
    CONSUMER_KEYS = 0x05
    POWER_KEYS = 0x06
    DPI = 0x07
    PROFILE = 0x08
    BAT_BUTTON = 0x0C
    MACRO_I = 0x10
    MACRO_II = 0x11
    MACRO_III = 0x12


class Modifier(IntFlag):
    NONE = 0x00
    L_CTRL = 0x01
    L_SHIFT = 0x02
    L_ALT = 0x04
    L_WIN = 0x08
    R_CTRL = 0x10
    R_SHIFT = 0x20
    R_ALT = 0x40
    R_WIN = 0x80


MODIFIER_NAMES: List[Tuple[Modifier, str]] = [
    (Modifier.L_CTRL, "LCtrl"),
    (Modifier.L_SHIFT, "LShift"),
    (Modifier.L_ALT, "LAlt"),
    (Modifier.L_WIN, "LWin"),
    (Modifier.R_CTRL, "RCtrl"),
    (Modifier.R_SHIFT, "RShift"),
    (Modifier.R_ALT, "RAlt"),
    (Modifier.R_WIN, "RWin"),
]

MODIFIER_STR_TO_BIT: Dict[str, Modifier] = {
    name.lower(): bit for bit, name in MODIFIER_NAMES
}
MODIFIER_STR_TO_BIT.update(
    {
        "l_ctrl": Modifier.L_CTRL,
        "ctrl": Modifier.L_CTRL,
        "l_shift": Modifier.L_SHIFT,
        "shift": Modifier.L_SHIFT,
        "l_alt": Modifier.L_ALT,
        "alt": Modifier.L_ALT,
        "l_win": Modifier.L_WIN,
        "l_gui": Modifier.L_WIN,
        "win": Modifier.L_WIN,
        "super": Modifier.L_WIN,
        "meta": Modifier.L_WIN,
        "r_ctrl": Modifier.R_CTRL,
        "r_shift": Modifier.R_SHIFT,
        "r_alt": Modifier.R_ALT,
        "r_win": Modifier.R_WIN,
        "r_gui": Modifier.R_WIN,
    }
)


class ConsumerKey(IntEnum):
    LIGHTING_UP = 0x006F
    LIGHTING_DOWN = 0x0070
    NEXT_TRACK = 0x00B5
    PREVIOUS_TRACK = 0x00B6
    MEDIA_STOP = 0x00B7
    MEDIA_EJECT = 0x00B8
    MEDIA_PLAY_PAUSE = 0x00CD
    MUTE_SOUND = 0x00E2
    VOLUME_UP = 0x00E9
    VOLUME_DOWN = 0x00EA
    MEDIA_SELECT = 0x0183
    MY_MAIL = 0x018A
    CALC = 0x0192
    MY_COMPUTER = 0x0194
    MY_EXPLORER = 0x0196
    SELECT_APP = 0x01A3
    MY_COPY = 0x021B
    MY_CUT = 0x021C
    MY_PASTE = 0x021D
    WWW_HOME = 0x0223
    WWW_REFRESH = 0x0227


CONSUMER_KEY_LABELS: Dict[int, str] = {
    ConsumerKey.MEDIA_SELECT: "Media Player",
    ConsumerKey.MEDIA_PLAY_PAUSE: "Play/Pause",
    ConsumerKey.NEXT_TRACK: "Next Track",
    ConsumerKey.PREVIOUS_TRACK: "Previous Track",
    ConsumerKey.MEDIA_STOP: "Stop",
    ConsumerKey.MEDIA_EJECT: "Eject",
    ConsumerKey.VOLUME_UP: "Volume Up",
    ConsumerKey.VOLUME_DOWN: "Volume Down",
    ConsumerKey.MUTE_SOUND: "Mute",
    ConsumerKey.CALC: "Calculator",
    ConsumerKey.MY_COMPUTER: "File Manager / PC",
    ConsumerKey.WWW_HOME: "Browser Home",
    ConsumerKey.WWW_REFRESH: "Refresh",
    ConsumerKey.MY_EXPLORER: "Web Browser",
    ConsumerKey.MY_MAIL: "Email",
    ConsumerKey.LIGHTING_UP: "Brightness Up",
    ConsumerKey.LIGHTING_DOWN: "Brightness Down",
    ConsumerKey.SELECT_APP: "Switch Apps",
    ConsumerKey.MY_COPY: "Copy",
    ConsumerKey.MY_CUT: "Cut",
    ConsumerKey.MY_PASTE: "Paste",
}


class PowerKey(IntEnum):
    SYSTEM_POWER = 0x81
    SYSTEM_SLEEP = 0x82
    SYSTEM_WAKE = 0x83


POWER_KEY_LABELS: Dict[int, str] = {
    PowerKey.SYSTEM_POWER: "System Power",
    PowerKey.SYSTEM_SLEEP: "System Sleep",
    PowerKey.SYSTEM_WAKE: "System Wake",
}


class DPIAction(IntEnum):
    STAGE_UP = 1
    STAGE_DOWN = 2
    STAGE_LOCK = 5
    CYCLE_UP = 6
    CYCLE_DOWN = 7


DPI_ACTION_LABELS: Dict[int, str] = {
    DPIAction.STAGE_UP: "DPI Stage Up",
    DPIAction.STAGE_DOWN: "DPI Stage Down",
    DPIAction.STAGE_LOCK: "DPI Lock",
    DPIAction.CYCLE_UP: "DPI+ (Cycle Up)",
    DPIAction.CYCLE_DOWN: "DPI- (Cycle Down)",
}


class ProfileAction(IntEnum):
    PROFILE_UP = 1
    PROFILE_DOWN = 2
    LOOP_UP = 3
    LOOP_DOWN = 4


PROFILE_ACTION_LABELS: Dict[int, str] = {
    ProfileAction.PROFILE_UP: "Profile Up",
    ProfileAction.PROFILE_DOWN: "Profile Down",
    ProfileAction.LOOP_UP: "Profile Cycle Up",
    ProfileAction.LOOP_DOWN: "Profile Cycle Down",
}

POLLING_CODE_TO_HZ: Dict[int, int] = {
    0x08: 125,
    0x04: 250,
    0x02: 500,
    0x01: 1000,
    0x20: 2000,
    0x40: 4000,
    0x80: 8000,
}
POLLING_HZ_TO_CODE: Dict[int, int] = {hz: code for code, hz in POLLING_CODE_TO_HZ.items()}

WIRED_POLLING_RATES: List[int] = [125, 250, 500, 1000]
WIRELESS_POLLING_RATES: List[int] = [125, 250, 500, 1000, 2000, 4000, 8000]

LOD_CODE_TO_NAME: Dict[int, str] = {
    0x87: "0.7mm",
    1: "1mm",
    2: "2mm",
}
LOD_NAME_TO_CODE: Dict[str, int] = {
    "0.7mm": 0x87,
    "0.7": 0x87,
    "135": 0x87,
    "1mm": 1,
    "1": 1,
    "2mm": 2,
    "2": 2,
}

# USB HID Usage Page 0x07 Keyboard/Keypad codes -> Canonical label matching DriverCore.exe
HID_KEY_TO_NAME: Dict[int, str] = {
    0x04: "A",
    0x05: "B",
    0x06: "C",
    0x07: "D",
    0x08: "E",
    0x09: "F",
    0x0A: "G",
    0x0B: "H",
    0x0C: "I",
    0x0D: "J",
    0x0E: "K",
    0x0F: "L",
    0x10: "M",
    0x11: "N",
    0x12: "O",
    0x13: "P",
    0x14: "Q",
    0x15: "R",
    0x16: "S",
    0x17: "T",
    0x18: "U",
    0x19: "V",
    0x1A: "W",
    0x1B: "X",
    0x1C: "Y",
    0x1D: "Z",
    0x1E: "1",
    0x1F: "2",
    0x20: "3",
    0x21: "4",
    0x22: "5",
    0x23: "6",
    0x24: "7",
    0x25: "8",
    0x26: "9",
    0x27: "0",
    0x28: "Enter",
    0x29: "Esc",
    0x2A: "BackSpace",
    0x2B: "Tab",
    0x2C: "Space",
    0x2D: "-",
    0x2E: "=",
    0x2F: "[",
    0x30: "]",
    0x31: "\\",
    0x33: ";",
    0x34: "'",
    0x35: "`",
    0x36: ",",
    0x37: ".",
    0x38: "/",
    0x39: "Caps",
    0x3A: "F1",
    0x3B: "F2",
    0x3C: "F3",
    0x3D: "F4",
    0x3E: "F5",
    0x3F: "F6",
    0x40: "F7",
    0x41: "F8",
    0x42: "F9",
    0x43: "F10",
    0x44: "F11",
    0x45: "F12",
    0x46: "Print",
    0x47: "Scroll",
    0x48: "Pause",
    0x49: "Insert",
    0x4A: "Home",
    0x4B: "Page Up",
    0x4C: "Delete",
    0x4D: "End",
    0x4E: "Page Down",
    0x4F: "Right",
    0x50: "Left",
    0x51: "Down",
    0x52: "Up",
    0x53: "Num Lock",
    0x54: "Pad /",
    0x55: "Pad *",
    0x56: "Pad -",
    0x57: "Pad +",
    0x58: "Pad Enter",
    0x59: "Pad 1",
    0x5A: "Pad 2",
    0x5B: "Pad 3",
    0x5C: "Pad 4",
    0x5D: "Pad 5",
    0x5E: "Pad 6",
    0x5F: "Pad 7",
    0x60: "Pad 8",
    0x61: "Pad 9",
    0x62: "Pad 0",
    0x63: "Pad .",
    0x65: "Menu",
    0xE0: "LCtrl",
    0xE1: "LShift",
    0xE2: "LAlt",
    0xE3: "LWin",
    0xE4: "RCtrl",
    0xE5: "RShift",
    0xE6: "RAlt",
    0xE7: "RWin",
}

NAME_TO_HID_KEY: Dict[str, int] = {name.lower(): code for code, name in HID_KEY_TO_NAME.items()}
NAME_TO_HID_KEY.update(
    {
        "return": 0x28,
        "escape": 0x29,
        "backspace": 0x2A,
        "spacebar": 0x2C,
        "minus": 0x2D,
        "equal": 0x2E,
        "equals": 0x2E,
        "backslash": 0x31,
        "semicolon": 0x33,
        "apostrophe": 0x34,
        "quote": 0x34,
        "grave": 0x35,
        "tilde": 0x35,
        "comma": 0x36,
        "period": 0x37,
        "dot": 0x37,
        "slash": 0x38,
        "capslock": 0x39,
        "caps_lock": 0x39,
        "printscreen": 0x46,
        "prtsc": 0x46,
        "scrolllock": 0x47,
        "ins": 0x49,
        "pgup": 0x4B,
        "pageup": 0x4B,
        "del": 0x4C,
        "pgdn": 0x4E,
        "pagedown": 0x4E,
        "numlock": 0x53,
        "super_l": 0xE3,
        "super_r": 0xE7,
    }
)

MODIFIER_HID_TO_BIT: Dict[int, Modifier] = {
    0xE0: Modifier.L_CTRL,
    0xE1: Modifier.L_SHIFT,
    0xE2: Modifier.L_ALT,
    0xE3: Modifier.L_WIN,
    0xE4: Modifier.R_CTRL,
    0xE5: Modifier.R_SHIFT,
    0xE6: Modifier.R_ALT,
    0xE7: Modifier.R_WIN,
}
MODIFIER_BIT_TO_HID: Dict[Modifier, int] = {bit: hid for hid, bit in MODIFIER_HID_TO_BIT.items()}


def hid_key_name(code: int) -> str:
    """Return human-readable label for a USB HID keyboard usage code."""
    return HID_KEY_TO_NAME.get(code, f"0x{code:02X}")


def parse_hid_key(spec: str) -> int:
    """Parse a key name or hex literal ('A', 'Enter', '0x04') into a USB HID usage code."""
    cleaned = spec.strip()
    if not cleaned:
        raise ValueError("Empty key specification")
    low = cleaned.lower()
    if low in NAME_TO_HID_KEY:
        return NAME_TO_HID_KEY[low]
    if low.startswith("0x"):
        val = int(low, 16)
        if 0 <= val <= 0xFF:
            return val
    if cleaned.isdigit():
        val = int(cleaned, 10)
        if 0 <= val <= 0xFF:
            return val
    raise ValueError(f"Unknown key name or code: {spec!r}")


def format_modifiers(mask: int) -> str:
    """Format a Modifier bitmask as e.g. 'LCtrl + LShift'."""
    parts = [label for bit, label in MODIFIER_NAMES if mask & bit]
    return " + ".join(parts)


def parse_modifiers(parts: List[str]) -> int:
    """Parse a list of modifier names into a Modifier bitmask."""
    mask = 0
    for item in parts:
        for token in item.replace("+", " ").replace(",", " ").split():
            key = token.strip().lower()
            if not key:
                continue
            if key not in MODIFIER_STR_TO_BIT:
                raise ValueError(f"Unknown modifier: {token!r}")
            mask |= int(MODIFIER_STR_TO_BIT[key])
    return mask


# Linux evdev / X11 native scan / Qt.Key -> USB HID usage helper for PyQt5 GUI
_QT_KEY_TO_HID: Optional[Dict[int, int]] = None


def qt_event_to_hid(qt_key: int, native_scan_code: int = 0) -> Optional[int]:
    """Map a PyQt5 Qt.Key (and optional Linux evdev keycode) to a USB HID usage code.

    On Linux Wayland/X11, XKB adds +8 to evdev keycodes for X11/Wayland scan codes,
    which helps distinguish left vs. right modifiers or keypad keys when available.
    """
    global _QT_KEY_TO_HID
    if _QT_KEY_TO_HID is None:
        from PyQt5.QtCore import Qt

        tbl: Dict[int, int] = {
            Qt.Key_Return: 0x28,
            Qt.Key_Enter: 0x58,
            Qt.Key_Escape: 0x29,
            Qt.Key_Backspace: 0x2A,
            Qt.Key_Tab: 0x2B,
            Qt.Key_Space: 0x2C,
            Qt.Key_Minus: 0x2D,
            Qt.Key_Underscore: 0x2D,
            Qt.Key_Equal: 0x2E,
            Qt.Key_Plus: 0x2E,
            Qt.Key_BracketLeft: 0x2F,
            Qt.Key_BraceLeft: 0x2F,
            Qt.Key_BracketRight: 0x30,
            Qt.Key_BraceRight: 0x30,
            Qt.Key_Backslash: 0x31,
            Qt.Key_Bar: 0x31,
            Qt.Key_Semicolon: 0x33,
            Qt.Key_Colon: 0x33,
            Qt.Key_Apostrophe: 0x34,
            Qt.Key_QuoteDbl: 0x34,
            Qt.Key_QuoteLeft: 0x35,
            Qt.Key_AsciiTilde: 0x35,
            Qt.Key_Comma: 0x36,
            Qt.Key_Less: 0x36,
            Qt.Key_Period: 0x37,
            Qt.Key_Greater: 0x37,
            Qt.Key_Slash: 0x38,
            Qt.Key_Question: 0x38,
            Qt.Key_CapsLock: 0x39,
            Qt.Key_Print: 0x46,
            Qt.Key_SysReq: 0x46,
            Qt.Key_ScrollLock: 0x47,
            Qt.Key_Pause: 0x48,
            Qt.Key_Insert: 0x49,
            Qt.Key_Home: 0x4A,
            Qt.Key_PageUp: 0x4B,
            Qt.Key_Delete: 0x4C,
            Qt.Key_End: 0x4D,
            Qt.Key_PageDown: 0x4E,
            Qt.Key_Right: 0x4F,
            Qt.Key_Left: 0x50,
            Qt.Key_Down: 0x51,
            Qt.Key_Up: 0x52,
            Qt.Key_NumLock: 0x53,
            Qt.Key_Menu: 0x65,
            Qt.Key_Control: 0xE0,
            Qt.Key_Shift: 0xE1,
            Qt.Key_Alt: 0xE2,
            Qt.Key_AltGr: 0xE6,
            Qt.Key_Super_L: 0xE3,
            Qt.Key_Super_R: 0xE7,
            Qt.Key_Meta: 0xE3,
        }
        for i in range(26):
            tbl[int(Qt.Key_A) + i] = 0x04 + i
        # Top-row 1..9, 0
        for i in range(9):
            tbl[int(Qt.Key_1) + i] = 0x1E + i
        tbl[int(Qt.Key_0)] = 0x27
        for i in range(12):
            tbl[int(Qt.Key_F1) + i] = 0x3A + i
        _QT_KEY_TO_HID = tbl

    # Disambiguate left/right modifiers via Linux XKB scan code (evdev + 8)
    # evdev: L_CTRL=29(37), R_CTRL=97(105), L_SHIFT=42(50), R_SHIFT=54(62),
    #        L_ALT=56(64), R_ALT=100(108), L_META=125(133), R_META=126(134)
    from PyQt5.QtCore import Qt

    if qt_key == Qt.Key_Control and native_scan_code == 105:
        return 0xE4
    if qt_key == Qt.Key_Shift and native_scan_code == 62:
        return 0xE5
    if qt_key == Qt.Key_Alt and native_scan_code == 108:
        return 0xE6
    if qt_key in (Qt.Key_Meta, Qt.Key_Super_L, Qt.Key_Super_R) and native_scan_code == 134:
        return 0xE7

    # Also handle shifted symbols on top row when Shift is held
    shifted_digits = {
        int(Qt.Key_Exclam): 0x1E,
        int(Qt.Key_At): 0x1F,
        int(Qt.Key_NumberSign): 0x20,
        int(Qt.Key_Dollar): 0x21,
        int(Qt.Key_Percent): 0x22,
        int(Qt.Key_AsciiCircum): 0x23,
        int(Qt.Key_Ampersand): 0x24,
        int(Qt.Key_Asterisk): 0x25,
        int(Qt.Key_ParenLeft): 0x26,
        int(Qt.Key_ParenRight): 0x27,
    }
    if qt_key in shifted_digits:
        return shifted_digits[qt_key]

    return _QT_KEY_TO_HID.get(qt_key)
