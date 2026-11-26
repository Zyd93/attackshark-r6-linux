"""Unit tests for ATTACK SHARK R6 protocol, macro codec, and hidraw normalization."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Callable, List
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from attackshark_r6.constants import (
    DEFAULT_DPI_COLORS,
    SLEEP_DISABLED,
    STATUS_OK,
    ButtonID,
    ConsumerKey,
    DPIAction,
    FunctionID,
    Modifier,
    PowerKey,
    ProfileAction,
)
from attackshark_r6.hid_transport import normalize_feature_response
from attackshark_r6.macros import MacroStep, decode_macro, encode_macro
from attackshark_r6.protocol import ButtonBinding, DPIStage, ProtocolError, R6Protocol
from attackshark_r6.settings import (
    AppSettings,
    default_settings_path,
    load_settings,
    save_settings,
)


class FakeTransport:
    """In-memory mock HidrawTransport capturing sent packets and serving scripted responses."""

    def __init__(self, handler: Callable[[bytearray, int], bytearray]) -> None:
        self.handler = handler
        self.sent: List[bytearray] = []
        self._last_cmd: bytearray = bytearray(65)
        self._get_count = 0

    def set_feature(self, report: bytes | bytearray) -> None:
        pkt = bytearray(report)
        self.sent.append(pkt)
        self._last_cmd = pkt
        self._get_count = 0

    def get_feature(self, report_id: int = 0) -> bytearray:
        self._get_count += 1
        return self.handler(self._last_cmd, self._get_count)


class TestHidrawNormalization(unittest.TestCase):
    def test_64_byte_unnumbered_response_prepends_zero(self) -> None:
        raw = bytearray(65)
        raw[0] = STATUS_OK
        raw[1] = 0x00
        raw[2] = 0x02
        raw[6] = 0x01
        raw[7] = 0x55
        norm = normalize_feature_response(64, raw)
        self.assertEqual(len(norm), 65)
        self.assertEqual(norm[0], 0x00)
        self.assertEqual(norm[1], STATUS_OK)
        self.assertEqual(norm[3], 0x02)
        self.assertEqual(norm[7], 0x01)
        self.assertEqual(norm[8], 0x55)

    def test_65_byte_response_with_report_id_zero_preserved(self) -> None:
        raw = bytearray(65)
        raw[0] = 0x00
        raw[1] = STATUS_OK
        raw[7] = 1
        raw[8] = 85
        norm = normalize_feature_response(65, raw)
        self.assertEqual(norm[0], 0x00)
        self.assertEqual(norm[1], STATUS_OK)
        self.assertEqual(norm[7], 1)
        self.assertEqual(norm[8], 85)

    def test_65_byte_response_without_leading_zero_shifted(self) -> None:
        raw = bytearray(65)
        raw[0] = STATUS_OK
        raw[6] = 0x42
        norm = normalize_feature_response(65, raw)
        self.assertEqual(norm[0], 0x00)
        self.assertEqual(norm[1], STATUS_OK)
        self.assertEqual(norm[7], 0x42)


class TestMacroCodec(unittest.TestCase):
    def test_roundtrip_all_step_types(self) -> None:
        steps = [
            MacroStep(kind="key_down", code=0xE0),  # LCtrl -> 0x09 0x01
            MacroStep(kind="key_down", code=0x06),  # C -> 0x02 0x06
            MacroStep(kind="delay", delay_ms=45),  # 0x20 0x2D
            MacroStep(kind="key_up", code=0x06),    # 0x03 0x06
            MacroStep(kind="key_up", code=0xE0),    # 0x0A 0x01
            MacroStep(kind="mouse_down", code=ButtonID.LEFT),
            MacroStep(kind="delay", delay_ms=500),  # 0x21 0x01 0xF4
            MacroStep(kind="mouse_move", dx=-120, dy=340),
            MacroStep(kind="wheel", code=1),
            MacroStep(kind="wheel", code=-1),
            MacroStep(kind="mouse_up", code=ButtonID.LEFT),
            MacroStep(kind="delay", delay_ms=70000),     # 0x22
            MacroStep(kind="delay", delay_ms=20000000),  # 0x23
        ]
        blob = encode_macro(steps)
        decoded = decode_macro(blob)
        self.assertEqual(decoded, steps)

    def test_legacy_delay_opcodes_decode(self) -> None:
        blob = bytes([0x13, 0x01, 0x00, 0x00, 0x14, 0x01, 0x00, 0x00, 0x01])
        decoded = decode_macro(blob)
        self.assertEqual(
            decoded,
            [
                MacroStep(kind="delay", delay_ms=0x010000),
                MacroStep(kind="delay", delay_ms=0x01000001),
            ],
        )


class TestProtocolCommands(unittest.TestCase):
    def _ok_resp(self, cmd: bytearray) -> bytearray:
        r = bytearray(cmd)
        r[0] = 0x00
        r[1] = STATUS_OK
        return r

    def test_fw_pid_battery(self) -> None:
        def handler(cmd: bytearray, _n: int) -> bytearray:
            r = self._ok_resp(cmd)
            if cmd[3] == 2 and cmd[5] == 0 and cmd[6] == 0x81:
                r[7:11] = bytes([1, 2, 3, 4])
            elif cmd[3] == 0 and cmd[5] == 0 and cmd[6] == 0x81:
                r[7:11] = bytes([2, 0, 1, 9])
            elif cmd[3] == 1 and cmd[5] == 0 and cmd[6] == 0x8B:
                r[11:13] = bytes([0x00, 0x22])
            elif cmd[3] == 2 and cmd[5] == 0 and cmd[6] == 0x83:
                r[7], r[8] = 1, 87
            return r

        tr = FakeTransport(handler)
        proto = R6Protocol(tr, wait_sec=0.0, macro_retry_sec=0.0)

        self.assertEqual(proto.get_device_fw_version(), "01.02.03.04")
        self.assertEqual(tr.sent[-1][3:7], bytearray([2, 0x10, 0x00, 0x81]))

        self.assertEqual(proto.get_dongle_fw_version(), "02.00.01.09")
        self.assertEqual(tr.sent[-1][3:7], bytearray([0, 0x10, 0x00, 0x81]))

        self.assertEqual(proto.get_device_pid(), 0x0022)
        self.assertEqual(tr.sent[-1][3:8], bytearray([1, 0x06, 0x00, 0x8B, 0x02]))

        self.assertEqual(proto.get_battery(), (True, 87))
        self.assertEqual(tr.sent[-1][3:7], bytearray([2, 0x02, 0x00, 0x83]))

    def test_profile_and_polling_including_0x10_fallback_and_a1_retry(self) -> None:
        def handler(cmd: bytearray, n: int) -> bytearray:
            r = self._ok_resp(cmd)
            if cmd[5] == 0 and cmd[6] == 0x85:
                if n == 1:
                    r[1] = 0x50  # busy (< A1) on first read
                else:
                    r[7] = 2
            elif cmd[5] == 1 and cmd[6] == 0x80:
                r[8] = 0x10  # special firmware alias for 1000Hz
            return r

        tr = FakeTransport(handler)
        proto = R6Protocol(tr, wait_sec=0.0, macro_retry_sec=0.0)

        self.assertEqual(proto.get_profile_id(), 2)
        self.assertTrue(proto.set_profile_id(3))
        self.assertEqual(tr.sent[-1][3:8], bytearray([2, 1, 0, 5, 3]))

        self.assertEqual(proto.get_polling_rate(2), 1000)
        self.assertEqual(tr.sent[-1][3:8], bytearray([2, 2, 1, 0x80, 2]))

        self.assertTrue(proto.set_polling_rate(2, 8000))
        self.assertEqual(tr.sent[-1][3:9], bytearray([2, 2, 1, 0, 2, 0x80]))

    def test_dpi_stages_active_and_colors(self) -> None:
        def handler(cmd: bytearray, _n: int) -> bytearray:
            r = self._ok_resp(cmd)
            if cmd[5] == 1 and cmd[6] == 0x81:
                r[8] = 2
                # Stage 1: 800x800 (0x0320), Stage 2: 1600x1200 (0x0640, 0x04B0)
                r[9:17] = bytes([0x03, 0x20, 0x03, 0x20, 0x06, 0x40, 0x04, 0xB0])
            elif cmd[5] == 1 and cmd[6] == 0x82:
                r[8] = 2
            elif cmd[5] == 2 and cmd[6] == 0x81:
                r[8:26] = bytes([255, 0, 0, 0, 255, 0] + [0] * 12)
            return r

        tr = FakeTransport(handler)
        proto = R6Protocol(tr, wait_sec=0.0, macro_retry_sec=0.0)

        stages, active = proto.get_dpi_stages(1)
        self.assertEqual(active, 2)
        self.assertEqual(stages, [DPIStage(800, 800), DPIStage(1600, 1200)])

        self.assertTrue(proto.set_active_dpi(1, 2))
        self.assertEqual(tr.sent[-1][3:9], bytearray([2, 2, 1, 2, 1, 2]))

        self.assertTrue(proto.set_dpi_stages(1, [DPIStage(400, 400), DPIStage(3200, 3200)]))
        pkt = tr.sent[-1]
        self.assertEqual(pkt[3:9], bytearray([2, 10, 1, 1, 1, 2]))
        self.assertEqual(pkt[9:17], bytearray([0x01, 0x90, 0x01, 0x90, 0x0C, 0x80, 0x0C, 0x80]))

        cols = proto.get_dpi_colors(1)
        self.assertEqual(cols[0], (255, 0, 0))
        self.assertEqual(cols[1], (0, 255, 0))

        self.assertTrue(proto.set_dpi_colors(1, DEFAULT_DPI_COLORS))
        cpkt = tr.sent[-1]
        self.assertEqual(cpkt[3:8], bytearray([2, 0x13, 2, 1, 1]))
        self.assertEqual(list(cpkt[8:14]), [255, 0, 0, 0, 0, 255])

    def test_sleep_debounce_lod_and_sensors(self) -> None:
        def handler(cmd: bytearray, _n: int) -> bytearray:
            r = self._ok_resp(cmd)
            if cmd[5] == 0 and cmd[6] == 0x87:
                r[8:10] = bytes([0xFF, 0xFF])
            elif cmd[5] == 0 and cmd[6] == 0x88:
                r[8] = 6
            elif cmd[5] == 1 and cmd[6] == 0x88:
                r[8] = 0x87
            elif cmd[5] == 1 and cmd[6] in (0x84, 0x89, 0x8A):
                r[8] = 1
            return r

        tr = FakeTransport(handler)
        proto = R6Protocol(tr, wait_sec=0.0, macro_retry_sec=0.0)

        self.assertEqual(proto.get_sleep_time(1), SLEEP_DISABLED)
        self.assertTrue(proto.set_sleep_time(1, 300))
        self.assertEqual(tr.sent[-1][3:10], bytearray([2, 3, 0, 7, 1, 0x01, 0x2C]))

        self.assertEqual(proto.get_debounce_time(1), 6)
        self.assertTrue(proto.set_debounce_time(1, 4))
        self.assertEqual(tr.sent[-1][3:9], bytearray([2, 2, 0, 8, 1, 4]))

        self.assertEqual(proto.get_lod(1), 0x87)
        self.assertTrue(proto.set_lod(1, 0x87))
        self.assertEqual(tr.sent[-1][3:9], bytearray([2, 2, 1, 8, 1, 0x87]))

        self.assertTrue(proto.get_angle_snap(1))
        self.assertTrue(proto.set_angle_snap(1, False))
        self.assertEqual(tr.sent[-1][3:9], bytearray([2, 2, 1, 4, 1, 0]))

        self.assertTrue(proto.get_motion_sync(1))
        self.assertTrue(proto.set_motion_sync(1, True))
        self.assertEqual(tr.sent[-1][3:9], bytearray([2, 2, 1, 9, 1, 1]))

        self.assertTrue(proto.get_ripple_control(1))
        self.assertTrue(proto.set_ripple_control(1, True))
        self.assertEqual(tr.sent[-1][3:9], bytearray([2, 2, 1, 10, 1, 1]))

    def test_all_button_bindings_encode_and_decode(self) -> None:
        stored = {}

        def handler(cmd: bytearray, _n: int) -> bytearray:
            r = self._ok_resp(cmd)
            if cmd[5] == 3 and cmd[6] == 0x00:
                bid = cmd[8]
                stored[bid] = bytes(cmd[10 : 12 + cmd[11]])
            elif cmd[5] == 3 and cmd[6] == 0x80:
                bid = cmd[8]
                blob = stored[bid]
                r[10 : 10 + len(blob)] = blob
            return r

        tr = FakeTransport(handler)
        proto = R6Protocol(tr, wait_sec=0.0, macro_retry_sec=0.0)

        bindings = [
            ButtonBinding.off(),
            ButtonBinding.mouse_button(ButtonID.FORWARD),
            ButtonBinding.double_click(ButtonID.LEFT, 2, 100),
            ButtonBinding.keyboard(int(Modifier.L_CTRL | Modifier.L_SHIFT), 0x06),
            ButtonBinding.consumer(ConsumerKey.MEDIA_PLAY_PAUSE),
            ButtonBinding.power(PowerKey.SYSTEM_SLEEP),
            ButtonBinding.dpi_action(DPIAction.CYCLE_UP),
            ButtonBinding.dpi_action(DPIAction.STAGE_LOCK, lock_dpi=1600),
            ButtonBinding.profile_action(ProfileAction.LOOP_UP),
            ButtonBinding.battery_indicator(),
            ButtonBinding.macro_repeat(5, 3),
            ButtonBinding.macro_hold(7),
            ButtonBinding.macro_toggle(9),
        ]

        for b in bindings:
            self.assertTrue(proto.set_button(1, ButtonID.FORWARD, b))
            got = proto.get_button(1, ButtonID.FORWARD)
            self.assertEqual(
                tr.sent[-1][3:12],
                bytearray([2, 15, 3, 0x80, 1, int(ButtonID.FORWARD), 0, 0xFF, 10]),
            )
            self.assertEqual(got.function_id, b.function_id)
            self.assertEqual(got.data, b.data)
            self.assertTrue(len(got.describe()) > 0)

        # Unmapped button response (r[10] == 0xFF) should decode cleanly as OFF with empty data
        stored[int(ButtonID.DPI_LOOP_UP)] = bytes([0xFF, 10, 0, 0])
        unmapped = proto.get_button(1, ButtonID.DPI_LOOP_UP)
        self.assertEqual(unmapped.function_id, FunctionID.OFF)
        self.assertEqual(unmapped.data, b"")

    def test_macro_chunked_write_and_read(self) -> None:
        mem = bytearray()
        alloc_size = 0

        def handler(cmd: bytearray, _n: int) -> bytearray:
            nonlocal mem, alloc_size
            r = self._ok_resp(cmd)
            if cmd[5] == 4 and cmd[6] == 0x01:  # Allocate
                alloc_size = (cmd[9] << 24) | (cmd[10] << 16) | (cmd[11] << 8) | cmd[12]
                mem = bytearray(alloc_size)
            elif cmd[5] == 4 and cmd[6] == 0x03:  # Set chunk
                off = (cmd[9] << 24) | (cmd[10] << 16) | (cmd[11] << 8) | cmd[12]
                ln = cmd[13]
                mem[off : off + ln] = cmd[14 : 14 + ln]
            elif cmd[5] == 4 and cmd[6] == 0x81:  # Get size
                r[9:13] = alloc_size.to_bytes(4, "big")
            elif cmd[5] == 4 and cmd[6] == 0x83:  # Get chunk
                off = (cmd[9] << 24) | (cmd[10] << 16) | (cmd[11] << 8) | cmd[12]
                ln = cmd[13]
                r[9:13] = cmd[9:13]
                r[14 : 14 + ln] = mem[off : off + ln]
            elif cmd[5] == 4 and cmd[6] == 0x02:  # Delete
                alloc_size = 0
                mem = bytearray()
            return r

        tr = FakeTransport(handler)
        proto = R6Protocol(tr, wait_sec=0.0, macro_retry_sec=0.0)

        steps = [MacroStep(kind="key_down", code=0x04), MacroStep(kind="delay", delay_ms=10), MacroStep(kind="key_up", code=0x04)] * 25
        expected = encode_macro(steps)
        self.assertGreater(len(expected), 51)  # spans multiple 51-byte chunks

        proto.set_macro(3, steps)
        self.assertEqual(proto.get_macro_size(3), len(expected))
        self.assertEqual(proto.get_macro_bytes(3), expected)
        self.assertEqual(proto.get_macro(3), steps)
        self.assertTrue(proto.delete_macro(3))
        self.assertEqual(proto.get_macro_size(3), 0)

    def test_pairing_and_resets(self) -> None:
        def handler(cmd: bytearray, _n: int) -> bytearray:
            r = self._ok_resp(cmd)
            if cmd[3] == 1 and cmd[5] == 0 and cmd[6] == 0x8C:
                r[7] = 2
            return r

        tr = FakeTransport(handler)
        proto = R6Protocol(tr, wait_sec=0.0, macro_retry_sec=0.0)

        self.assertTrue(proto.set_pair_status(True))
        self.assertEqual(tr.sent[-1][3:8], bytearray([1, 1, 0, 0x0C, 1]))
        self.assertEqual(proto.get_pair_status(), 2)
        self.assertEqual(tr.sent[-1][3:7], bytearray([1, 0, 0, 0x8C]))
        self.assertTrue(proto.reset_profile(2))
        self.assertEqual(tr.sent[-1][3:8], bytearray([2, 1, 0, 0x0D, 2]))

    def test_list_macros_cancel_check(self) -> None:
        scanned: List[int] = []

        def handler(cmd: bytearray, _n: int) -> bytearray:
            r = self._ok_resp(cmd)
            if cmd[5] == 4 and cmd[6] == 0x81:
                mid = (cmd[7] << 8) | cmd[8]
                scanned.append(mid)
                if mid in (1, 5):
                    r[9:13] = (12).to_bytes(4, "big")
            return r

        tr = FakeTransport(handler)
        proto = R6Protocol(tr, wait_sec=0.0, macro_retry_sec=0.0)
        found = proto.list_macros(cancel_check=lambda: len(scanned) >= 3)
        self.assertEqual(scanned, [1, 2, 3])
        self.assertEqual(found, {1: 12})

    def test_tx_lock_serializes_concurrent_transactions(self) -> None:
        lock = threading.Lock()
        in_flight = False
        overlap_detected = False
        last_target = 0

        class SerialCheckTransport:
            def set_feature(self, report: bytes | bytearray) -> None:
                nonlocal in_flight, overlap_detected, last_target
                with lock:
                    if in_flight:
                        overlap_detected = True
                    in_flight = True
                    last_target = report[3]

            def get_feature(self, report_id: int = 0) -> bytearray:
                nonlocal in_flight
                with lock:
                    target = last_target
                    in_flight = False
                r = bytearray(65)
                r[1] = STATUS_OK
                r[3] = target
                if target == 2:
                    r[7:11] = bytes([0, 0, 3, 1])
                else:
                    r[7:11] = bytes([0, 0, 3, 0])
                return r

        proto = R6Protocol(SerialCheckTransport(), wait_sec=0.005, macro_retry_sec=0.0)
        errors: List[Exception] = []

        def worker(fn: Callable[[], str], expected: str) -> None:
            try:
                for _ in range(12):
                    if fn() != expected:
                        raise AssertionError(f"Mismatched interleaved response != {expected}")
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=worker, args=(proto.get_device_fw_version, "00.00.03.01"))
        t2 = threading.Thread(target=worker, args=(proto.get_dongle_fw_version, "00.00.03.00"))
        t1.start()
        t2.start()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        self.assertFalse(overlap_detected)
        self.assertEqual(errors, [])


class TestSettingsStorage(unittest.TestCase):
    def test_defaults_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_settings(Path(tmp) / "missing.json")
            self.assertEqual(cfg, AppSettings(close_to_tray=True, start_minimized=False))

    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "settings.json"
            want = AppSettings(close_to_tray=False, start_minimized=True)
            save_settings(want, path)
            self.assertEqual(load_settings(path), want)

    def test_corrupt_or_non_dict_json_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not-valid-json", encoding="utf-8")
            self.assertEqual(load_settings(bad), AppSettings())

            arr = Path(tmp) / "arr.json"
            arr.write_text("[1, 2, 3]", encoding="utf-8")
            self.assertEqual(load_settings(arr), AppSettings())

    def test_default_settings_path_uses_xdg_config_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}):
                self.assertEqual(
                    default_settings_path(),
                    Path(tmp) / "attackshark-r6" / "settings.json",
                )


class TestSetterFailuresAndValidation(unittest.TestCase):
    def _proto(self, status: int = STATUS_OK, polling_code: int = 0x01, is_wireless=None):
        def handler(cmd: bytearray, _n: int) -> bytearray:
            r = bytearray(cmd)
            r[0] = 0x00
            r[1] = status
            if cmd[5] == 1 and cmd[6] == 0x80:
                r[8] = polling_code
            return r

        tr = FakeTransport(handler)
        return tr, R6Protocol(tr, wait_sec=0.0, macro_retry_sec=0.0, is_wireless=is_wireless)

    def test_failed_setters_raise_protocol_error(self) -> None:
        _tr, proto = self._proto(status=0x50)
        calls = [
            lambda: proto.set_profile_id(1),
            lambda: proto.set_polling_rate(1, 1000),
            lambda: proto.set_active_dpi(1, 1),
            lambda: proto.set_dpi_colors(1, DEFAULT_DPI_COLORS),
            lambda: proto.set_sleep_time(1, 300),
            lambda: proto.set_debounce_time(1, 4),
            lambda: proto.set_lod(1, 0x87),
            lambda: proto.set_angle_snap(1, True),
            lambda: proto.set_motion_sync(1, True),
            lambda: proto.set_ripple_control(1, True),
            lambda: proto.set_button(1, ButtonID.FORWARD, ButtonBinding.off()),
            lambda: proto.set_pair_status(True),
            lambda: proto.delete_macro(3),
        ]
        for call in calls:
            with self.assertRaises(ProtocolError):
                call()

    def test_unknown_polling_code_returns_none_and_0x10_alias_kept(self) -> None:
        _tr, proto = self._proto(polling_code=0x33)
        self.assertIsNone(proto.get_polling_rate(1))
        _tr, proto = self._proto(polling_code=0x10)
        self.assertEqual(proto.get_polling_rate(1), 1000)

    def test_wired_polling_cap_enforced(self) -> None:
        tr, proto = self._proto(is_wireless=False)
        with self.assertRaises(ValueError):
            proto.set_polling_rate(1, 8000)
        self.assertEqual(tr.sent, [])
        self.assertTrue(proto.set_polling_rate(1, 1000))
        _tr, wireless = self._proto(is_wireless=True)
        self.assertTrue(wireless.set_polling_rate(1, 8000))

    def test_apply_export_dict_validates_before_any_write(self) -> None:
        good = {"dpi_stages": [{"x": 800, "y": 800}], "polling_rate_hz": 1000}
        bad_cases = [
            {**good, "debounce_ms": 99},
            {**good, "dpi_stages": [{"x": 800}, {"x": 825}]},
            {**good, "dpi_stages": [{"x": 20}]},
            {**good, "dpi_stages": [{"x": 50000}]},
            {**good, "dpi_stages": "nope"},
            {**good, "dpi_colors": [[1, 2]]},
            {**good, "dpi_colors": [[1, 2, 300]]},
            {**good, "polling_rate_hz": 333},
            {**good, "polling_rate_hz": "1000"},
            {**good, "lod_code": 0x55},
            {**good, "active_dpi_stage": 5},
            {**good, "angle_snap": "yes"},
            {**good, "sleep_sec": 5},
            {**good, "buttons": {"999": {"function_id": 0}}},
            {**good, "buttons": {"1": {"function_id": 0x7F}}},
            {**good, "buttons": {"1": {"function_id": 0, "data_hex": "zz"}}},
            {**good, "buttons": [1]},
        ]
        for data in bad_cases:
            tr, proto = self._proto(is_wireless=True)
            with self.assertRaises(ProtocolError, msg=repr(data)):
                proto.apply_export_dict(1, data)
            self.assertEqual(tr.sent, [], msg=f"wrote to mouse for {data!r}")

        tr, proto = self._proto(is_wireless=False)
        with self.assertRaises(ProtocolError):
            proto.apply_export_dict(1, {"polling_rate_hz": 4000})
        self.assertEqual(tr.sent, [])
        with self.assertRaises(ProtocolError):
            proto.apply_export_dict(1, [1, 2])  # type: ignore[arg-type]

    def test_apply_export_dict_valid_writes(self) -> None:
        tr, proto = self._proto(is_wireless=True)
        proto.apply_export_dict(
            1,
            {
                "dpi_stages": [{"x": 800, "y": 800}, {"x": 1600}],
                "active_dpi_stage": 2,
                "polling_rate_hz": 2000,
                "lod_code": 0x87,
                "debounce_ms": 4,
                "buttons": {"1": {"function_id": 1, "data_hex": "01"}},
            },
        )
        self.assertGreaterEqual(len(tr.sent), 6)


if __name__ == "__main__":
    unittest.main()
