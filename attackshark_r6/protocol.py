"""ATTACK SHARK R6 USB HID protocol implementation (NewProtocol=1)."""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .constants import (
    BUTTON_LABELS,
    CONSUMER_KEY_LABELS,
    DEBOUNCE_MAX_MS,
    DEBOUNCE_MIN_MS,
    DEFAULT_DPI_COLORS,
    DPI_ACTION_LABELS,
    DPI_MAX,
    DPI_MAX_STAGES,
    DPI_MIN,
    DPI_STEP,
    LOD_CODE_TO_NAME,
    MACRO_CHUNK_SIZE,
    MACRO_MAX_ID,
    MACRO_MIN_ID,
    POLLING_CODE_TO_HZ,
    POLLING_HZ_TO_CODE,
    POWER_KEY_LABELS,
    PROFILE_ACTION_LABELS,
    PROFILE_MAX,
    PROFILE_MIN,
    REPORT_SIZE,
    SLEEP_DISABLED,
    SLEEP_MAX_SEC,
    SLEEP_MIN_SEC,
    STATUS_OK,
    TARGET_DONGLE,
    TARGET_DONGLE_CTRL,
    TARGET_MOUSE,
    WIRED_POLLING_RATES,
    ButtonID,
    DPIAction,
    FunctionID,
    ProfileAction,
    format_modifiers,
    hid_key_name,
)
from .hid_transport import HidrawTransport
from .macros import MacroStep, decode_macro, encode_macro


class ProtocolError(RuntimeError):
    """Raised when the mouse firmware fails to acknowledge or returns invalid data."""


@dataclass
class DPIStage:
    x: int
    y: int

    def normalized(self) -> "DPIStage":
        def clamp(v: int) -> int:
            v = max(DPI_MIN, min(DPI_MAX, int(v)))
            return max(DPI_MIN, round(v / DPI_STEP) * DPI_STEP)

        return DPIStage(x=clamp(self.x), y=clamp(self.y))


@dataclass
class ButtonBinding:
    """Represents the programmable function assigned to a mouse button."""

    function_id: FunctionID
    data: bytes = b""

    def describe(self) -> str:
        fid = self.function_id
        d = self.data
        if fid == FunctionID.OFF:
            return "Disabled"
        if fid == FunctionID.BUTTON_CODE and len(d) >= 1:
            try:
                bid = ButtonID(d[0])
                return BUTTON_LABELS.get(bid, bid.name.replace("_", " ").title())
            except ValueError:
                return f"Mouse Button {d[0]}"
        if fid == FunctionID.X_CLICK and len(d) >= 2:
            btn = d[1]
            cnt = d[2] if len(d) >= 3 else 2
            interval = ((d[3] << 8) | d[4]) if len(d) >= 5 else 100
            try:
                blabel = BUTTON_LABELS.get(ButtonID(btn), f"Button {btn}")
            except ValueError:
                blabel = f"Button {btn}"
            if btn == ButtonID.LEFT and cnt == 2:
                return "Left Double Click"
            return f"{blabel} {cnt}x Click ({interval}ms)"
        if fid == FunctionID.KEYBOARD_CODE and len(d) >= 2:
            mod_str = format_modifiers(d[0])
            key_str = hid_key_name(d[1]) if d[1] else ""
            if mod_str and key_str:
                return f"{mod_str} + {key_str}"
            return mod_str or key_str or "Key (None)"
        if fid == FunctionID.CONSUMER_KEYS and len(d) >= 2:
            usage = (d[0] << 8) | d[1]
            return CONSUMER_KEY_LABELS.get(usage, f"Media 0x{usage:04X}")
        if fid == FunctionID.POWER_KEYS and len(d) >= 1:
            return POWER_KEY_LABELS.get(d[0], f"Power 0x{d[0]:02X}")
        if fid == FunctionID.DPI and len(d) >= 1:
            act = d[0]
            if act == DPIAction.STAGE_LOCK and len(d) >= 3:
                dpi_val = (d[1] << 8) | d[2]
                return f"DPI Lock ({dpi_val})"
            return DPI_ACTION_LABELS.get(act, f"DPI Action {act}")
        if fid == FunctionID.PROFILE and len(d) >= 1:
            return PROFILE_ACTION_LABELS.get(d[0], f"Profile Action {d[0]}")
        if fid == FunctionID.BAT_BUTTON:
            return "Battery Indicator"
        if fid == FunctionID.MACRO_I and len(d) >= 3:
            mid = (d[0] << 8) | d[1]
            rep = d[2]
            return f"Macro #{mid} (x{rep})"
        if fid == FunctionID.MACRO_II and len(d) >= 2:
            mid = (d[0] << 8) | d[1]
            return f"Macro #{mid} (Hold)"
        if fid == FunctionID.MACRO_III and len(d) >= 2:
            mid = (d[0] << 8) | d[1]
            return f"Macro #{mid} (Toggle)"
        return f"Func 0x{int(fid):02X} [{d.hex(' ')}]"

    def to_dict(self) -> Dict[str, object]:
        return {
            "function_id": int(self.function_id),
            "data_hex": self.data.hex(),
            "description": self.describe(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, object]) -> "ButtonBinding":
        return cls(
            function_id=FunctionID(int(raw["function_id"])),
            data=bytes.fromhex(str(raw.get("data_hex", ""))),
        )

    @classmethod
    def off(cls) -> "ButtonBinding":
        return cls(FunctionID.OFF, b"")

    @classmethod
    def mouse_button(cls, btn: ButtonID) -> "ButtonBinding":
        return cls(FunctionID.BUTTON_CODE, bytes([int(btn)]))

    @classmethod
    def double_click(
        cls,
        btn: ButtonID = ButtonID.LEFT,
        clicks: int = 2,
        interval_ms: int = 100,
    ) -> "ButtonBinding":
        return cls(
            FunctionID.X_CLICK,
            bytes(
                [
                    1,
                    int(btn),
                    max(1, min(255, clicks)),
                    (interval_ms >> 8) & 0xFF,
                    interval_ms & 0xFF,
                ]
            ),
        )

    @classmethod
    def keyboard(cls, modifiers: int, hid_key: int) -> "ButtonBinding":
        return cls(FunctionID.KEYBOARD_CODE, bytes([modifiers & 0xFF, hid_key & 0xFF]))

    @classmethod
    def consumer(cls, usage: int) -> "ButtonBinding":
        return cls(FunctionID.CONSUMER_KEYS, bytes([(usage >> 8) & 0xFF, usage & 0xFF]))

    @classmethod
    def power(cls, key: int) -> "ButtonBinding":
        return cls(FunctionID.POWER_KEYS, bytes([key & 0xFF]))

    @classmethod
    def dpi_action(cls, action: DPIAction, lock_dpi: int = 800) -> "ButtonBinding":
        if action == DPIAction.STAGE_LOCK:
            d = max(DPI_MIN, min(DPI_MAX, int(lock_dpi)))
            hi, lo = (d >> 8) & 0xFF, d & 0xFF
            return cls(FunctionID.DPI, bytes([int(action), hi, lo, hi, lo]))
        return cls(FunctionID.DPI, bytes([int(action)]))

    @classmethod
    def profile_action(cls, action: ProfileAction) -> "ButtonBinding":
        return cls(FunctionID.PROFILE, bytes([int(action)]))

    @classmethod
    def battery_indicator(cls) -> "ButtonBinding":
        return cls(FunctionID.BAT_BUTTON, b"\x01")

    @classmethod
    def macro_repeat(cls, macro_id: int, count: int = 1) -> "ButtonBinding":
        return cls(
            FunctionID.MACRO_I,
            bytes([(macro_id >> 8) & 0xFF, macro_id & 0xFF, max(1, min(255, count))]),
        )

    @classmethod
    def macro_hold(cls, macro_id: int) -> "ButtonBinding":
        return cls(FunctionID.MACRO_II, bytes([(macro_id >> 8) & 0xFF, macro_id & 0xFF]))

    @classmethod
    def macro_toggle(cls, macro_id: int) -> "ButtonBinding":
        return cls(FunctionID.MACRO_III, bytes([(macro_id >> 8) & 0xFF, macro_id & 0xFF]))


@dataclass
class MouseState:
    """Full configuration snapshot read from the mouse."""

    profile_id: int
    device_fw: str
    dongle_fw: str
    device_pid: int
    battery_percent: int
    battery_charging: bool
    polling_rate_hz: Optional[int]
    active_dpi_stage: int
    dpi_stages: List[DPIStage]
    dpi_colors: List[Tuple[int, int, int]]
    lod_code: int
    debounce_ms: int
    sleep_sec: int
    angle_snap: bool
    motion_sync: bool
    ripple_control: bool
    buttons: Dict[int, ButtonBinding] = field(default_factory=dict)

    def to_export_dict(self) -> Dict[str, object]:
        return {
            "model": "ATTACK SHARK R6",
            "profile_id": self.profile_id,
            "polling_rate_hz": self.polling_rate_hz,
            "active_dpi_stage": self.active_dpi_stage,
            "dpi_stages": [{"x": s.x, "y": s.y} for s in self.dpi_stages],
            "dpi_colors": [list(c) for c in self.dpi_colors],
            "lod": LOD_CODE_TO_NAME.get(self.lod_code, str(self.lod_code)),
            "lod_code": self.lod_code,
            "debounce_ms": self.debounce_ms,
            "sleep_sec": self.sleep_sec,
            "angle_snap": self.angle_snap,
            "motion_sync": self.motion_sync,
            "ripple_control": self.ripple_control,
            "buttons": {str(k): v.to_dict() for k, v in self.buttons.items()},
        }


def build_packet(
    target: int = TARGET_MOUSE,
    length: int = 0,
    group: int = 0,
    cmd: int = 0,
    payload: bytes | bytearray = b"",
) -> bytearray:
    """Build a 65-byte HID Feature packet matching DriverCore.exe layout."""
    buf = bytearray(REPORT_SIZE)
    buf[0] = 0x00
    buf[3] = target & 0xFF
    buf[4] = length & 0xFF
    buf[5] = group & 0xFF
    buf[6] = cmd & 0xFF
    if payload:
        end = min(REPORT_SIZE, 7 + len(payload))
        buf[7:end] = payload[: end - 7]
    return buf


class R6Protocol:
    """High-level protocol client for ATTACK SHARK R6 (NewProtocol = 1)."""

    def __init__(
        self,
        transport: HidrawTransport,
        wait_sec: float = 0.030,
        macro_retry_sec: float = 0.200,
        is_wireless: Optional[bool] = None,
    ) -> None:
        self.transport = transport
        # None = connection type unknown (no wired polling cap enforced here).
        self.is_wireless = is_wireless
        self.wait_sec = wait_sec
        self.macro_retry_sec = macro_retry_sec
        self._tx_lock = threading.RLock()

    def _sleep(self, sec: Optional[float] = None) -> None:
        time.sleep(self.wait_sec if sec is None else sec)

    def _transact(
        self,
        cmd: bytearray,
        retries: int = 5,
        verify_echo: bool = False,
        require_ok: bool = False,
    ) -> bytearray:
        """Send a feature command, wait, read feature response, and handle A1 retries."""
        with self._tx_lock:
            self.transport.set_feature(cmd)
            self._sleep()
            resp = self.transport.get_feature()

            for _ in range(retries):
                status_ok = resp[1] == STATUS_OK
                echo_ok = (not verify_echo) or (resp[5] == cmd[5] and resp[6] == cmd[6])
                if status_ok and echo_ok:
                    return resp

                if resp[1] < STATUS_OK:
                    for _ in range(3):
                        self._sleep()
                        resp = self.transport.get_feature()
                        if resp[1] == STATUS_OK and (
                            (not verify_echo) or (resp[5] == cmd[5] and resp[6] == cmd[6])
                        ):
                            return resp

                self._sleep()
                self.transport.set_feature(cmd)
                self._sleep()
                resp = self.transport.get_feature()

            if require_ok and resp[1] != STATUS_OK:
                raise ProtocolError(
                    f"Command group=0x{cmd[5]:02X} cmd=0x{cmd[6]:02X} failed with status 0x{resp[1]:02X}"
                )
            return resp

    def _transact_simple(self, cmd: bytearray) -> bytearray:
        """Single SetFeature + wait + GetFeature (for commands without retry loop)."""
        with self._tx_lock:
            self.transport.set_feature(cmd)
            self._sleep()
            return self.transport.get_feature()

    @staticmethod
    def _expect_ok(resp: bytearray, what: str) -> bool:
        """Raise ProtocolError unless the firmware acknowledged a setter with STATUS_OK."""
        if resp[1] != STATUS_OK:
            raise ProtocolError(
                f"{what} was not acknowledged by the mouse (status 0x{resp[1]:02X})"
            )
        return True

    def _check_polling_allowed(self, hz: int) -> None:
        if hz not in POLLING_HZ_TO_CODE:
            raise ValueError(f"Unsupported polling rate: {hz} Hz")
        if self.is_wireless is False and hz not in WIRED_POLLING_RATES:
            raise ValueError(
                f"Polling rate {hz} Hz is not supported in wired mode "
                f"(max {max(WIRED_POLLING_RATES)} Hz)"
            )

    # ------------------------------------------------------------------
    # Device & Dongle Info / Status
    # ------------------------------------------------------------------

    def get_device_fw_version(self) -> str:
        cmd = build_packet(TARGET_MOUSE, 0x10, 0x00, 0x81)
        r = self._transact_simple(cmd)
        return f"{r[7]:02d}.{r[8]:02d}.{r[9]:02d}.{r[10]:02d}"

    def get_dongle_fw_version(self) -> str:
        cmd = build_packet(TARGET_DONGLE, 0x10, 0x00, 0x81)
        r = self._transact_simple(cmd)
        return f"{r[7]:02d}.{r[8]:02d}.{r[9]:02d}.{r[10]:02d}"

    def get_device_pid(self) -> int:
        cmd = build_packet(TARGET_DONGLE_CTRL, 0x06, 0x00, 0x8B, bytes([0x02]))
        r = self._transact_simple(cmd)
        return (r[11] << 8) | r[12]

    def get_battery(self) -> Tuple[bool, int]:
        """Return (is_charging, battery_percent)."""
        cmd = build_packet(TARGET_MOUSE, 0x02, 0x00, 0x83)
        r = self._transact_simple(cmd)
        return bool(r[7]), int(r[8])

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def get_profile_id(self) -> int:
        cmd = build_packet(TARGET_MOUSE, 0x01, 0x00, 0x85)
        r = self._transact(cmd, retries=5)
        pid = int(r[7])
        if PROFILE_MIN <= pid <= PROFILE_MAX:
            return pid
        return PROFILE_MIN

    def set_profile_id(self, profile_id: int) -> bool:
        pid = max(PROFILE_MIN, min(PROFILE_MAX, int(profile_id)))
        cmd = build_packet(TARGET_MOUSE, 0x01, 0x00, 0x05, bytes([pid]))
        r = self._transact_simple(cmd)
        return self._expect_ok(r, "Set profile")

    # ------------------------------------------------------------------
    # Polling Rate (NewProtocol = 1)
    # ------------------------------------------------------------------

    def get_polling_rate(self, profile_id: int) -> Optional[int]:
        """Return polling rate in Hz, or None if the firmware reports an unknown code."""
        cmd = build_packet(TARGET_MOUSE, 0x02, 0x01, 0x80, bytes([profile_id]))
        r = self._transact(cmd, retries=3, verify_echo=True)
        code = int(r[8])
        if code == 0x10:
            code = 0x01
        return POLLING_CODE_TO_HZ.get(code)

    def set_polling_rate(self, profile_id: int, hz: int) -> bool:
        self._check_polling_allowed(hz)
        code = POLLING_HZ_TO_CODE[hz]
        cmd = build_packet(TARGET_MOUSE, 0x02, 0x01, 0x00, bytes([profile_id, code]))
        r = self._transact_simple(cmd)
        return self._expect_ok(r, "Set polling rate")

    # ------------------------------------------------------------------
    # DPI Stages & Colors
    # ------------------------------------------------------------------

    def get_dpi_stages(self, profile_id: int) -> Tuple[List[DPIStage], int]:
        """Return (list_of_DPIStage, active_stage_1based)."""
        cmd_stages = build_packet(
            TARGET_MOUSE, 0x0A, 0x01, 0x81, bytes([profile_id, DPI_MAX_STAGES])
        )
        r = self._transact(cmd_stages, retries=5)
        count = max(1, min(DPI_MAX_STAGES, int(r[8])))
        stages: List[DPIStage] = []
        for i in range(count):
            base = 9 + 4 * i
            x = (r[base] << 8) | r[base + 1]
            y = (r[base + 2] << 8) | r[base + 3]
            if x == 0:
                x = 800
            if y == 0:
                y = x
            stages.append(DPIStage(x=x, y=y))

        active = self.get_active_dpi(profile_id)
        if active < 1 or active > len(stages):
            active = 1
        return stages, active

    def get_active_dpi(self, profile_id: int) -> int:
        cmd = build_packet(TARGET_MOUSE, 0x02, 0x01, 0x82, bytes([profile_id]))
        r = self._transact(cmd, retries=5)
        return int(r[8])

    def set_active_dpi(self, profile_id: int, stage_index: int) -> bool:
        idx = max(1, min(DPI_MAX_STAGES, int(stage_index)))
        cmd = build_packet(TARGET_MOUSE, 0x02, 0x01, 0x02, bytes([profile_id, idx]))
        r = self._transact_simple(cmd)
        return self._expect_ok(r, "Set active DPI stage")

    def set_dpi_stages(self, profile_id: int, stages: List[DPIStage]) -> bool:
        if not stages or len(stages) > DPI_MAX_STAGES:
            raise ValueError(f"DPI stages count must be 1..{DPI_MAX_STAGES}")
        payload = bytearray([profile_id & 0xFF, len(stages) & 0xFF])
        for st in stages:
            norm = st.normalized()
            payload.extend(
                [
                    (norm.x >> 8) & 0xFF,
                    norm.x & 0xFF,
                    (norm.y >> 8) & 0xFF,
                    norm.y & 0xFF,
                ]
            )
        cmd = build_packet(
            TARGET_MOUSE,
            2 + 4 * len(stages),
            0x01,
            0x01,
            payload,
        )
        r = self._transact(cmd, retries=5)
        return self._expect_ok(r, "Set DPI stages")

    def get_dpi_colors(self, profile_id: int) -> List[Tuple[int, int, int]]:
        cmd = build_packet(TARGET_MOUSE, 0x13, 0x02, 0x81, bytes([profile_id]))
        r = self._transact(cmd, retries=5)
        colors: List[Tuple[int, int, int]] = []
        for i in range(DPI_MAX_STAGES):
            off = 8 + i * 3
            colors.append((int(r[off]), int(r[off + 1]), int(r[off + 2])))
        return colors

    def set_dpi_colors(
        self, profile_id: int, colors: List[Tuple[int, int, int]]
    ) -> bool:
        padded = list(colors[:DPI_MAX_STAGES])
        while len(padded) < DPI_MAX_STAGES:
            padded.append((0, 0, 0))
        payload = bytearray([profile_id & 0xFF])
        for r_c, g_c, b_c in padded:
            payload.extend((r_c & 0xFF, g_c & 0xFF, b_c & 0xFF))
        cmd = build_packet(TARGET_MOUSE, 0x13, 0x02, 0x01, payload)
        r = self._transact_simple(cmd)
        return self._expect_ok(r, "Set DPI colors")

    # ------------------------------------------------------------------
    # Sleep, Debounce, LOD & Sensor Options (NewProtocol = 1)
    # ------------------------------------------------------------------

    def get_sleep_time(self, profile_id: int) -> int:
        cmd = build_packet(TARGET_MOUSE, 0x03, 0x00, 0x87, bytes([profile_id]))
        r = self._transact(cmd, retries=5)
        return (r[8] << 8) | r[9]

    def set_sleep_time(self, profile_id: int, seconds: int) -> bool:
        sec = int(seconds)
        if sec != SLEEP_DISABLED:
            sec = max(SLEEP_MIN_SEC, min(SLEEP_MAX_SEC, sec))
        cmd = build_packet(
            TARGET_MOUSE,
            0x03,
            0x00,
            0x07,
            bytes([profile_id, (sec >> 8) & 0xFF, sec & 0xFF]),
        )
        r = self._transact_simple(cmd)
        return self._expect_ok(r, "Set sleep time")

    def get_debounce_time(self, profile_id: int) -> int:
        cmd = build_packet(TARGET_MOUSE, 0x02, 0x00, 0x88, bytes([profile_id]))
        r = self._transact_simple(cmd)
        return int(r[8])

    def set_debounce_time(self, profile_id: int, ms: int) -> bool:
        val = max(DEBOUNCE_MIN_MS, min(DEBOUNCE_MAX_MS, int(ms)))
        cmd = build_packet(TARGET_MOUSE, 0x02, 0x00, 0x08, bytes([profile_id, val]))
        r = self._transact_simple(cmd)
        return self._expect_ok(r, "Set debounce time")

    def get_lod(self, profile_id: int) -> int:
        cmd = build_packet(TARGET_MOUSE, 0x02, 0x01, 0x88, bytes([profile_id]))
        r = self._transact_simple(cmd)
        return int(r[8])

    def set_lod(self, profile_id: int, lod_code: int) -> bool:
        if lod_code not in LOD_CODE_TO_NAME:
            raise ValueError(f"Unsupported LOD code: {lod_code}")
        cmd = build_packet(
            TARGET_MOUSE, 0x02, 0x01, 0x08, bytes([profile_id, lod_code])
        )
        r = self._transact_simple(cmd)
        return self._expect_ok(r, "Set LOD")

    def get_angle_snap(self, profile_id: int) -> bool:
        cmd = build_packet(TARGET_MOUSE, 0x02, 0x01, 0x84, bytes([profile_id]))
        return bool(self._transact_simple(cmd)[8])

    def set_angle_snap(self, profile_id: int, enable: bool) -> bool:
        cmd = build_packet(
            TARGET_MOUSE, 0x02, 0x01, 0x04, bytes([profile_id, 1 if enable else 0])
        )
        return self._expect_ok(self._transact_simple(cmd), "Set angle snap")

    def get_motion_sync(self, profile_id: int) -> bool:
        cmd = build_packet(TARGET_MOUSE, 0x02, 0x01, 0x89, bytes([profile_id]))
        return bool(self._transact_simple(cmd)[8])

    def set_motion_sync(self, profile_id: int, enable: bool) -> bool:
        cmd = build_packet(
            TARGET_MOUSE, 0x02, 0x01, 0x09, bytes([profile_id, 1 if enable else 0])
        )
        return self._expect_ok(self._transact_simple(cmd), "Set motion sync")

    def get_ripple_control(self, profile_id: int) -> bool:
        cmd = build_packet(TARGET_MOUSE, 0x02, 0x01, 0x8A, bytes([profile_id]))
        return bool(self._transact_simple(cmd)[8])

    def set_ripple_control(self, profile_id: int, enable: bool) -> bool:
        cmd = build_packet(
            TARGET_MOUSE, 0x02, 0x01, 0x0A, bytes([profile_id, 1 if enable else 0])
        )
        return self._expect_ok(self._transact_simple(cmd), "Set ripple control")

    # ------------------------------------------------------------------
    # Button Bindings
    # ------------------------------------------------------------------

    def get_button(self, profile_id: int, button_id: ButtonID) -> ButtonBinding:
        payload = bytes([profile_id & 0xFF, int(button_id), 0x00, 0xFF, 10])
        cmd = build_packet(TARGET_MOUSE, 15, 0x03, 0x80, payload)
        r = self._transact(cmd, retries=3)
        if r[10] == 0xFF:
            return ButtonBinding.off()
        try:
            fid = FunctionID(r[10])
        except ValueError:
            return ButtonBinding.off()
        dlen = int(r[11])
        data = bytes(r[12 : 12 + min(dlen, 52)])
        return ButtonBinding(function_id=fid, data=data)

    def set_button(
        self, profile_id: int, button_id: ButtonID, binding: ButtonBinding
    ) -> bool:
        d = binding.data
        payload = bytes(
            [profile_id & 0xFF, int(button_id), 0x00, int(binding.function_id), len(d)]
        ) + d
        cmd = build_packet(TARGET_MOUSE, 5 + len(d), 0x03, 0x00, payload)
        r = self._transact_simple(cmd)
        return self._expect_ok(r, "Set button binding")

    # ------------------------------------------------------------------
    # Onboard Macros (IDs 1..29)
    # ------------------------------------------------------------------

    def get_macro_size(self, macro_id: int) -> int:
        cmd = build_packet(
            TARGET_MOUSE,
            6,
            0x04,
            0x81,
            bytes([(macro_id >> 8) & 0xFF, macro_id & 0xFF]),
        )
        r = self._transact_simple(cmd)
        if r[1] != STATUS_OK:
            return 0
        return (r[9] << 24) | (r[10] << 16) | (r[11] << 8) | r[12]

    def list_macros(
        self, cancel_check: Optional[Callable[[], bool]] = None
    ) -> Dict[int, int]:
        """Scan slots 1..29 and return {macro_id: byte_size} for non-empty slots."""
        existing: Dict[int, int] = {}
        for mid in range(MACRO_MIN_ID, MACRO_MAX_ID + 1):
            if cancel_check is not None and cancel_check():
                break
            sz = self.get_macro_size(mid)
            if sz > 0:
                existing[mid] = sz
        return existing

    def delete_macro(self, macro_id: int) -> bool:
        cmd = build_packet(
            TARGET_MOUSE,
            2,
            0x04,
            0x02,
            bytes([(macro_id >> 8) & 0xFF, macro_id & 0xFF]),
        )
        r = self._transact_simple(cmd)
        return self._expect_ok(r, "Delete macro")

    def allocate_macro_size(self, macro_id: int, total_size: int) -> bool:
        payload = bytes(
            [
                (macro_id >> 8) & 0xFF,
                macro_id & 0xFF,
                (total_size >> 24) & 0xFF,
                (total_size >> 16) & 0xFF,
                (total_size >> 8) & 0xFF,
                total_size & 0xFF,
            ]
        )
        cmd = build_packet(TARGET_MOUSE, 6, 0x04, 0x01, payload)
        r = self._transact(cmd, retries=5)
        return r[1] == STATUS_OK

    def _set_macro_chunk(self, macro_id: int, offset: int, chunk: bytes) -> bool:
        n = len(chunk)
        payload = (
            bytes(
                [
                    (macro_id >> 8) & 0xFF,
                    macro_id & 0xFF,
                    (offset >> 24) & 0xFF,
                    (offset >> 16) & 0xFF,
                    (offset >> 8) & 0xFF,
                    offset & 0xFF,
                    n & 0xFF,
                ]
            )
            + chunk
        )
        cmd = build_packet(TARGET_MOUSE, 7 + n, 0x04, 0x03, payload)
        with self._tx_lock:
            self.transport.set_feature(cmd)
            self._sleep()
            resp = self.transport.get_feature()
            for _ in range(10):
                if resp[1] == STATUS_OK:
                    return True
                if resp[1] < STATUS_OK:
                    for _ in range(10):
                        self._sleep(self.macro_retry_sec)
                        resp = self.transport.get_feature()
                        if resp[1] == STATUS_OK:
                            return True
                self._sleep(self.macro_retry_sec)
                self.transport.set_feature(cmd)
                self._sleep(self.macro_retry_sec)
                resp = self.transport.get_feature()
            return resp[1] == STATUS_OK

    def _get_macro_chunk(self, macro_id: int, offset: int, chunk_len: int) -> bytes:
        off_bytes = bytes(
            [
                (offset >> 24) & 0xFF,
                (offset >> 16) & 0xFF,
                (offset >> 8) & 0xFF,
                offset & 0xFF,
            ]
        )
        payload = bytes([(macro_id >> 8) & 0xFF, macro_id & 0xFF]) + off_bytes + bytes([chunk_len & 0xFF])
        cmd = build_packet(TARGET_MOUSE, 7 + chunk_len, 0x04, 0x83, payload)
        with self._tx_lock:
            self.transport.set_feature(cmd)
            self._sleep()
            resp = self.transport.get_feature()

            for _ in range(20):
                if resp[1] == STATUS_OK and bytes(resp[9:13]) == off_bytes:
                    return bytes(resp[14 : 14 + chunk_len])
                if resp[1] < STATUS_OK:
                    for _ in range(3):
                        self._sleep(self.macro_retry_sec)
                        resp = self.transport.get_feature()
                        if resp[1] == STATUS_OK and bytes(resp[9:13]) == off_bytes:
                            return bytes(resp[14 : 14 + chunk_len])
                self._sleep(self.macro_retry_sec)
                self.transport.set_feature(cmd)
                self._sleep(self.macro_retry_sec)
                resp = self.transport.get_feature()

            if resp[1] == STATUS_OK and bytes(resp[9:13]) == off_bytes:
                return bytes(resp[14 : 14 + chunk_len])
            raise ProtocolError(
                f"Macro #{macro_id} read offset {offset} failed (status=0x{resp[1]:02X})"
            )

    def get_macro_bytes(self, macro_id: int) -> bytes:
        total = self.get_macro_size(macro_id)
        if total <= 0:
            return b""
        out = bytearray()
        offset = 0
        while offset < total:
            chunk_len = min(MACRO_CHUNK_SIZE, total - offset)
            out.extend(self._get_macro_chunk(macro_id, offset, chunk_len))
            offset += chunk_len
        return bytes(out)

    def get_macro(self, macro_id: int) -> List[MacroStep]:
        return decode_macro(self.get_macro_bytes(macro_id))

    def set_macro_bytes(self, macro_id: int, data: bytes) -> None:
        if not (MACRO_MIN_ID <= macro_id <= MACRO_MAX_ID):
            raise ValueError(f"Macro ID must be {MACRO_MIN_ID}..{MACRO_MAX_ID}")
        allocated = False
        for _ in range(3):
            if self.allocate_macro_size(macro_id, len(data)):
                allocated = True
                break
            self._sleep(self.macro_retry_sec)
        if not allocated:
            raise ProtocolError(f"Failed to allocate macro #{macro_id} ({len(data)} bytes)")

        for offset in range(0, len(data), MACRO_CHUNK_SIZE):
            chunk = data[offset : offset + MACRO_CHUNK_SIZE]
            if not self._set_macro_chunk(macro_id, offset, chunk):
                raise ProtocolError(f"Failed writing macro #{macro_id} at offset {offset}")

    def set_macro(self, macro_id: int, steps: List[MacroStep]) -> None:
        self.set_macro_bytes(macro_id, encode_macro(steps))

    # ------------------------------------------------------------------
    # Wireless Pairing & Reset
    # ------------------------------------------------------------------

    def set_pair_status(self, start: bool) -> bool:
        cmd = build_packet(
            TARGET_DONGLE_CTRL, 0x01, 0x00, 0x0C, bytes([1 if start else 0])
        )
        r = self._transact_simple(cmd)
        return self._expect_ok(r, "Set pairing status")

    def get_pair_status(self) -> int:
        """Return pairing status byte (2 == paired)."""
        cmd = build_packet(TARGET_DONGLE_CTRL, 0x00, 0x00, 0x8C)
        r = self._transact_simple(cmd)
        return int(r[7])

    def reset_profile(self, profile_id: int) -> bool:
        with self._tx_lock:
            cmd = build_packet(TARGET_MOUSE, 0x01, 0x00, 0x0D, bytes([profile_id]))
            self.transport.set_feature(cmd)
            return True

    def factory_reset(self, profile_id: int = 1) -> bool:
        with self._tx_lock:
            self.set_dpi_colors(profile_id, DEFAULT_DPI_COLORS)
            cmd_mouse = build_packet(TARGET_MOUSE, 0x02, 0x00, 0x00, bytes([0xC0, 0x01]))
            self.transport.set_feature(cmd_mouse)
            time.sleep(1.0)
            cmd_dongle = build_packet(TARGET_DONGLE, 0x02, 0x00, 0x00, bytes([0xC0]))
            r = self._transact_simple(cmd_dongle)
            return r[1] == STATUS_OK

    # ------------------------------------------------------------------
    # Full Snapshot & Profile Import/Export
    # ------------------------------------------------------------------

    def read_full_state(
        self,
        profile_id: Optional[int] = None,
        buttons: Optional[List[ButtonID]] = None,
    ) -> MouseState:
        from .constants import CONFIGURABLE_BUTTONS

        pid = self.get_profile_id() if profile_id is None else profile_id
        device_fw = self.get_device_fw_version()
        dongle_fw = self.get_dongle_fw_version()
        device_pid = self.get_device_pid()
        charging, batt = self.get_battery()
        polling = self.get_polling_rate(pid)
        stages, active_stage = self.get_dpi_stages(pid)
        colors = self.get_dpi_colors(pid)
        lod = self.get_lod(pid)
        debounce = self.get_debounce_time(pid)
        sleep_sec = self.get_sleep_time(pid)
        angle_snap = self.get_angle_snap(pid)
        motion_sync = self.get_motion_sync(pid)
        ripple = self.get_ripple_control(pid)

        btn_list = CONFIGURABLE_BUTTONS if buttons is None else buttons
        btn_map: Dict[int, ButtonBinding] = {}
        for bid in btn_list:
            btn_map[int(bid)] = self.get_button(pid, bid)

        return MouseState(
            profile_id=pid,
            device_fw=device_fw,
            dongle_fw=dongle_fw,
            device_pid=device_pid,
            battery_percent=batt,
            battery_charging=charging,
            polling_rate_hz=polling,
            active_dpi_stage=active_stage,
            dpi_stages=stages,
            dpi_colors=colors,
            lod_code=lod,
            debounce_ms=debounce,
            sleep_sec=sleep_sec,
            angle_snap=angle_snap,
            motion_sync=motion_sync,
            ripple_control=ripple,
            buttons=btn_map,
        )

    def validate_export_dict(self, data: Dict[str, object]) -> Dict[str, object]:
        """Validate a profile export dict and return normalized values.

        Raises ProtocolError (without touching the mouse) on the first problem.
        """
        from .constants import LOD_CODE_TO_NAME

        if not isinstance(data, dict):
            raise ProtocolError("Profile data must be a JSON object")

        def as_int(value: object, name: str) -> int:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ProtocolError(f"{name} must be an integer, got {value!r}")
            return value

        def as_bool(value: object, name: str) -> bool:
            if not isinstance(value, bool):
                raise ProtocolError(f"{name} must be true or false, got {value!r}")
            return value

        out: Dict[str, object] = {}

        if "dpi_stages" in data:
            raw = data["dpi_stages"]
            if not isinstance(raw, list) or not raw:
                raise ProtocolError("dpi_stages must be a non-empty list")
            if len(raw) > DPI_MAX_STAGES:
                raise ProtocolError(f"dpi_stages has {len(raw)} entries (max {DPI_MAX_STAGES})")
            stages: List[DPIStage] = []
            for n, entry in enumerate(raw, 1):
                if not isinstance(entry, dict) or "x" not in entry:
                    raise ProtocolError(f"dpi_stages[{n}] must be an object with 'x' (and optional 'y')")
                x = as_int(entry["x"], f"dpi_stages[{n}].x")
                y = as_int(entry.get("y", x), f"dpi_stages[{n}].y")
                for axis, v in (("x", x), ("y", y)):
                    if not (DPI_MIN <= v <= DPI_MAX) or v % DPI_STEP != 0:
                        raise ProtocolError(
                            f"dpi_stages[{n}].{axis}={v} is invalid "
                            f"(must be {DPI_MIN}..{DPI_MAX} in steps of {DPI_STEP})"
                        )
                stages.append(DPIStage(x=x, y=y))
            out["dpi_stages"] = stages

        if "dpi_colors" in data:
            raw = data["dpi_colors"]
            if not isinstance(raw, list) or not raw:
                raise ProtocolError("dpi_colors must be a non-empty list")
            if len(raw) > DPI_MAX_STAGES:
                raise ProtocolError(f"dpi_colors has {len(raw)} entries (max {DPI_MAX_STAGES})")
            colors: List[Tuple[int, int, int]] = []
            for n, c in enumerate(raw, 1):
                if not isinstance(c, (list, tuple)) or len(c) != 3:
                    raise ProtocolError(f"dpi_colors[{n}] must be [r, g, b]")
                rgb = tuple(as_int(v, f"dpi_colors[{n}]") for v in c)
                if any(not (0 <= v <= 255) for v in rgb):
                    raise ProtocolError(f"dpi_colors[{n}] components must be 0..255")
                colors.append((rgb[0], rgb[1], rgb[2]))
            out["dpi_colors"] = colors

        if "active_dpi_stage" in data:
            idx = as_int(data["active_dpi_stage"], "active_dpi_stage")
            limit = len(out["dpi_stages"]) if "dpi_stages" in out else DPI_MAX_STAGES  # type: ignore[arg-type]
            if not (1 <= idx <= limit):
                raise ProtocolError(f"active_dpi_stage={idx} must be 1..{limit}")
            out["active_dpi_stage"] = idx

        if "polling_rate_hz" in data:
            hz = as_int(data["polling_rate_hz"], "polling_rate_hz")
            try:
                self._check_polling_allowed(hz)
            except ValueError as exc:
                raise ProtocolError(str(exc)) from None
            out["polling_rate_hz"] = hz

        if "lod_code" in data:
            code = as_int(data["lod_code"], "lod_code")
            if code not in LOD_CODE_TO_NAME:
                raise ProtocolError(f"lod_code={code} is not a supported LOD code")
            out["lod_code"] = code

        if "debounce_ms" in data:
            ms = as_int(data["debounce_ms"], "debounce_ms")
            if not (DEBOUNCE_MIN_MS <= ms <= DEBOUNCE_MAX_MS):
                raise ProtocolError(f"debounce_ms={ms} must be {DEBOUNCE_MIN_MS}..{DEBOUNCE_MAX_MS}")
            out["debounce_ms"] = ms

        if "sleep_sec" in data:
            sec = as_int(data["sleep_sec"], "sleep_sec")
            if sec != SLEEP_DISABLED and not (SLEEP_MIN_SEC <= sec <= SLEEP_MAX_SEC):
                raise ProtocolError(
                    f"sleep_sec={sec} must be {SLEEP_MIN_SEC}..{SLEEP_MAX_SEC} or {SLEEP_DISABLED} (never)"
                )
            out["sleep_sec"] = sec

        for key in ("angle_snap", "motion_sync", "ripple_control"):
            if key in data:
                out[key] = as_bool(data[key], key)

        if "buttons" in data:
            raw_buttons = data["buttons"]
            if not isinstance(raw_buttons, dict):
                raise ProtocolError("buttons must be an object")
            buttons: List[Tuple[ButtonID, ButtonBinding]] = []
            for k, v in raw_buttons.items():
                try:
                    bid = ButtonID(int(k))
                except (ValueError, TypeError):
                    raise ProtocolError(f"buttons: unknown button id {k!r}") from None
                if not isinstance(v, dict):
                    raise ProtocolError(f"buttons[{k}] must be an object")
                try:
                    fid = FunctionID(as_int(v.get("function_id"), f"buttons[{k}].function_id"))
                except ValueError:
                    raise ProtocolError(
                        f"buttons[{k}].function_id={v.get('function_id')!r} is not a valid function"
                    ) from None
                try:
                    raw_hex = v.get("data_hex", "")
                    if not isinstance(raw_hex, str):
                        raise ValueError
                    payload = bytes.fromhex(raw_hex)
                except ValueError:
                    raise ProtocolError(f"buttons[{k}].data_hex must be a hex string") from None
                if len(payload) > 52:
                    raise ProtocolError(f"buttons[{k}].data_hex is too long ({len(payload)} bytes, max 52)")
                buttons.append((bid, ButtonBinding(function_id=fid, data=payload)))
            out["buttons"] = buttons

        return out

    def apply_export_dict(self, profile_id: int, data: Dict[str, object]) -> None:
        """Apply an exported profile. The whole dict is validated before any write."""
        plan = self.validate_export_dict(data)
        if "dpi_stages" in plan:
            self.set_dpi_stages(profile_id, plan["dpi_stages"])  # type: ignore[arg-type]
        if "dpi_colors" in plan:
            self.set_dpi_colors(profile_id, plan["dpi_colors"])  # type: ignore[arg-type]
        if "active_dpi_stage" in plan:
            self.set_active_dpi(profile_id, plan["active_dpi_stage"])  # type: ignore[arg-type]
        if "polling_rate_hz" in plan:
            self.set_polling_rate(profile_id, plan["polling_rate_hz"])  # type: ignore[arg-type]
        if "lod_code" in plan:
            self.set_lod(profile_id, plan["lod_code"])  # type: ignore[arg-type]
        if "debounce_ms" in plan:
            self.set_debounce_time(profile_id, plan["debounce_ms"])  # type: ignore[arg-type]
        if "sleep_sec" in plan:
            self.set_sleep_time(profile_id, plan["sleep_sec"])  # type: ignore[arg-type]
        if "angle_snap" in plan:
            self.set_angle_snap(profile_id, plan["angle_snap"])  # type: ignore[arg-type]
        if "motion_sync" in plan:
            self.set_motion_sync(profile_id, plan["motion_sync"])  # type: ignore[arg-type]
        if "ripple_control" in plan:
            self.set_ripple_control(profile_id, plan["ripple_control"])  # type: ignore[arg-type]
        for bid, binding in plan.get("buttons", []):  # type: ignore[union-attr]
            self.set_button(profile_id, bid, binding)
