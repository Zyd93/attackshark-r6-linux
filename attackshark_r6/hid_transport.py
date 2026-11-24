"""Linux hidraw transport, sysfs device discovery, and notification listener."""

from __future__ import annotations

import fcntl
import glob
import os
import select
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .constants import (
    REPORT_SIZE,
    SUPPORTED_PIDS,
    VENDOR_ID,
    WIRELESS_PID,
)

# Linux <linux/hidraw.h> ioctl constants:
# _IOWR('H', 0x06, len) and _IOWR('H', 0x07, len)
_IOC_WRITE = 1
_IOC_READ = 2
_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS


def _ioc(direction: int, ioc_type: str, nr: int, size: int) -> int:
    return (
        (direction << _IOC_DIRSHIFT)
        | (ord(ioc_type) << _IOC_TYPESHIFT)
        | (nr << _IOC_NRSHIFT)
        | (size << _IOC_SIZESHIFT)
    )


def hidiocsfeature(length: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, "H", 0x06, length)


def hidiocgfeature(length: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, "H", 0x07, length)


def normalize_feature_response(ret: int, buf: bytearray) -> bytearray:
    """Normalize HIDIOCGFEATURE response to a 65-byte buffer [0x00, wire_0..63].

    For unnumbered feature reports (Report ID 0), Linux hidraw may return 64 bytes
    starting at buf[0], or 65 bytes with Report ID 0x00 at buf[0].
    """
    if ret == REPORT_SIZE - 1:
        out = bytearray(REPORT_SIZE)
        out[0] = 0x00
        out[1:REPORT_SIZE] = buf[: REPORT_SIZE - 1]
        return out
    if ret >= REPORT_SIZE and buf[0] != 0x00:
        out = bytearray(REPORT_SIZE)
        out[0] = 0x00
        out[1:REPORT_SIZE] = buf[: REPORT_SIZE - 1]
        return out
    out = bytearray(REPORT_SIZE)
    take = min(len(buf), REPORT_SIZE)
    out[:take] = buf[:take]
    return out


def _parse_uevent(path: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    data[k] = v
    except OSError:
        pass
    return data


def _read_bytes(path: str) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return b""


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return ""


def _parse_hid_id(hid_id: str) -> Optional[Tuple[int, int]]:
    # Format: 0003:0000373E:00000022
    parts = hid_id.split(":")
    if len(parts) != 3:
        return None
    try:
        return int(parts[1], 16), int(parts[2], 16)
    except ValueError:
        return None


def _is_control_descriptor(rdesc: bytes) -> bool:
    # Vendor Usage Page 0xFFFF (06 ff ff) + Feature item (b1 ...) + 64 byte count (95 40)
    return b"\x06\xff\xff" in rdesc and b"\x95\x40" in rdesc


def _is_notify_descriptor(rdesc: bytes) -> bool:
    # Vendor Usage Page 0xFFA0 (06 a0 ff) + Report ID 4 (85 04)
    return b"\x06\xa0\xff" in rdesc and b"\x85\x04" in rdesc


@dataclass
class R6DeviceInfo:
    """Discovered ATTACK SHARK R6 USB device / receiver."""

    vid: int
    pid: int
    name: str
    serial: str
    phys_base: str
    control_path: str
    notify_path: Optional[str] = None
    boot_mouse_path: Optional[str] = None
    control_rw: bool = False
    notify_ro: bool = False

    @property
    def is_wireless(self) -> bool:
        return self.pid == WIRELESS_PID

    @property
    def mode_label(self) -> str:
        return SUPPORTED_PIDS.get(self.pid, f"PID 0x{self.pid:04X}")

    @property
    def has_permission(self) -> bool:
        return bool(self.control_path and self.control_rw)


def discover_devices(sysfs_root: str = "/sys/class/hidraw") -> List[R6DeviceInfo]:
    """Scan Linux hidraw sysfs entries for connected ATTACK SHARK R6 devices."""
    grouped: Dict[str, Dict[str, object]] = {}

    for entry in sorted(glob.glob(os.path.join(sysfs_root, "hidraw*"))):
        node_name = os.path.basename(entry)
        dev_node = os.path.join("/dev", node_name)
        dev_dir = os.path.join(entry, "device")
        uevent = _parse_uevent(os.path.join(dev_dir, "uevent"))
        vid_pid = _parse_hid_id(uevent.get("HID_ID", ""))
        if not vid_pid:
            continue
        vid, pid = vid_pid
        if vid != VENDOR_ID or pid not in SUPPORTED_PIDS:
            continue

        phys = uevent.get("HID_PHYS", "")
        phys_base = phys.rsplit("/input", 1)[0] if "/input" in phys else phys
        if not phys_base:
            phys_base = os.path.realpath(os.path.join(dev_dir, "..", ".."))

        iface_num = _read_text(os.path.join(dev_dir, "..", "bInterfaceNumber"))
        rdesc = _read_bytes(os.path.join(dev_dir, "report_descriptor"))

        bucket = grouped.setdefault(
            phys_base,
            {
                "vid": vid,
                "pid": pid,
                "name": uevent.get("HID_NAME", "ATTACK SHARK R6").strip(),
                "serial": uevent.get("HID_UNIQ", "").strip(),
                "phys_base": phys_base,
                "control_path": "",
                "notify_path": None,
                "boot_mouse_path": None,
            },
        )

        if _is_control_descriptor(rdesc) or iface_num == "02" or phys.endswith("/input2"):
            bucket["control_path"] = dev_node
        elif _is_notify_descriptor(rdesc) or iface_num == "01" or phys.endswith("/input1"):
            bucket["notify_path"] = dev_node
        elif iface_num == "00" or phys.endswith("/input0"):
            bucket["boot_mouse_path"] = dev_node

    results: List[R6DeviceInfo] = []
    for bucket in grouped.values():
        ctrl = str(bucket["control_path"])
        if not ctrl:
            continue
        ntf = bucket["notify_path"]
        ntf_str = str(ntf) if ntf else None
        boot = bucket["boot_mouse_path"]
        boot_str = str(boot) if boot else None
        results.append(
            R6DeviceInfo(
                vid=int(bucket["vid"]),  # type: ignore[arg-type]
                pid=int(bucket["pid"]),  # type: ignore[arg-type]
                name=str(bucket["name"]),
                serial=str(bucket["serial"]),
                phys_base=str(bucket["phys_base"]),
                control_path=ctrl,
                notify_path=ntf_str,
                boot_mouse_path=boot_str,
                control_rw=os.access(ctrl, os.R_OK | os.W_OK),
                notify_ro=bool(ntf_str and os.access(ntf_str, os.R_OK)),
            )
        )

    return results


class HidrawError(OSError):
    """Raised when a hidraw operation fails."""


class HidrawTransport:
    """Thread-safe Linux hidraw transport for 65-byte HID Feature reports."""

    def __init__(self, device_path: str, debug: bool = False) -> None:
        self.device_path = device_path
        self.debug = debug
        self._lock = threading.RLock()
        self._fd: Optional[int] = None

    def open(self) -> None:
        with self._lock:
            if self._fd is None:
                self._fd = os.open(self.device_path, os.O_RDWR)

    def close(self) -> None:
        with self._lock:
            if self._fd is not None:
                try:
                    os.close(self._fd)
                finally:
                    self._fd = None

    def __enter__(self) -> "HidrawTransport":
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def set_feature(self, report: bytes | bytearray) -> None:
        if len(report) != REPORT_SIZE:
            raise ValueError(f"Expected {REPORT_SIZE}-byte feature report, got {len(report)}")
        buf = bytearray(report)
        with self._lock:
            opened_here = self._fd is None
            if opened_here:
                self.open()
            try:
                assert self._fd is not None
                if self.debug:
                    print(f"[TX] {bytes(buf).hex(' ')}")
                fcntl.ioctl(self._fd, hidiocsfeature(len(buf)), buf, True)
            except OSError as exc:
                raise HidrawError(f"HIDIOCSFEATURE failed on {self.device_path}: {exc}") from exc
            finally:
                if opened_here:
                    self.close()

    def get_feature_raw(self, report_id: int = 0) -> Tuple[int, bytearray]:
        """Execute raw HIDIOCGFEATURE(65) and return (ioctl_ret, raw_buffer)."""
        buf = bytearray(REPORT_SIZE)
        buf[0] = report_id & 0xFF
        with self._lock:
            opened_here = self._fd is None
            if opened_here:
                self.open()
            try:
                assert self._fd is not None
                ret = fcntl.ioctl(self._fd, hidiocgfeature(len(buf)), buf, True)
                if self.debug:
                    print(f"[RX raw ret={ret}] {bytes(buf).hex(' ')}")
                return int(ret), buf
            except OSError as exc:
                raise HidrawError(f"HIDIOCGFEATURE failed on {self.device_path}: {exc}") from exc
            finally:
                if opened_here:
                    self.close()

    def get_feature(self, report_id: int = 0) -> bytearray:
        ret, buf = self.get_feature_raw(report_id)
        norm = normalize_feature_response(ret, buf)
        if self.debug:
            print(f"[RX norm] {bytes(norm).hex(' ')}")
        return norm


class NotificationListener:
    """Background reader for live MI01 vendor notifications (Report ID 0x04)."""

    def __init__(
        self,
        notify_path: str,
        on_event: Callable[[str, bytes], None],
    ) -> None:
        self.notify_path = notify_path
        self.on_event = on_event
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="r6-notify-listener",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run(self) -> None:
        fd: Optional[int] = None
        try:
            fd = os.open(self.notify_path, os.O_RDONLY | os.O_NONBLOCK)
            while not self._stop.is_set():
                rlist, _, _ = select.select([fd], [], [], 0.2)
                if not rlist:
                    continue
                try:
                    data = os.read(fd, 64)
                except BlockingIOError:
                    continue
                except OSError:
                    break
                if not data:
                    time.sleep(0.05)
                    continue
                # Report ID 0x04 vendor notifications
                if data[0] == 0x04 and len(data) >= 3:
                    code = data[1]
                    if code == 0x01:
                        self.on_event("dpi_changed", data)
                    elif code == 0x06:
                        kind = "wake" if data[2] == 0x01 else "sleep"
                        self.on_event(kind, data)
                    elif code == 0x07:
                        self.on_event("lod_changed", data)
                    elif code == 0x08:
                        self.on_event("polling_changed", data)
                    else:
                        self.on_event("vendor_other", data)
        except OSError:
            pass
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
