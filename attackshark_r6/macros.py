"""Macro step data model, bytecode encoder, and decoder for ATTACK SHARK R6."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple

from .constants import (
    BUTTON_LABELS,
    MODIFIER_BIT_TO_HID,
    MODIFIER_HID_TO_BIT,
    ButtonID,
    Modifier,
    hid_key_name,
)

MacroKind = Literal[
    "key_down",
    "key_up",
    "mouse_down",
    "mouse_up",
    "mouse_move",
    "wheel",
    "delay",
]


def _encode_signed16(val: int) -> Tuple[int, int]:
    """Encode signed integer (-32768..32767) matching DriverCore.exe macro encoder."""
    v = max(-32768, min(32767, int(val)))
    u = v & 0xFFFF
    return (u >> 8) & 0xFF, u & 0xFF


def _decode_signed16(hi: int, lo: int) -> int:
    raw = ((hi & 0xFF) << 8) | (lo & 0xFF)
    return raw - 0x10000 if raw >= 0x8000 else raw


@dataclass
class MacroStep:
    """Single step in an ATTACK SHARK R6 onboard hardware macro."""

    kind: MacroKind
    code: int = 0          # HID key usage (for key_*), ButtonID (for mouse_*), or +1/-1 (wheel)
    delay_ms: int = 0      # milliseconds (for kind == "delay")
    dx: int = 0            # relative X (for kind == "mouse_move")
    dy: int = 0            # relative Y (for kind == "mouse_move")

    def describe(self) -> str:
        if self.kind == "key_down":
            return f"Key Down: {hid_key_name(self.code)}"
        if self.kind == "key_up":
            return f"Key Up: {hid_key_name(self.code)}"
        if self.kind == "mouse_down":
            try:
                label = BUTTON_LABELS.get(ButtonID(self.code), f"Button {self.code}")
            except ValueError:
                label = f"Button {self.code}"
            return f"Mouse Down: {label}"
        if self.kind == "mouse_up":
            if self.code == 0:
                return "Mouse Up"
            try:
                label = BUTTON_LABELS.get(ButtonID(self.code), f"Button {self.code}")
            except ValueError:
                label = f"Button {self.code}"
            return f"Mouse Up: {label}"
        if self.kind == "mouse_move":
            return f"Mouse Move: X={self.dx}, Y={self.dy}"
        if self.kind == "wheel":
            direction = "Up" if self.code == 1 else "Down"
            return f"Wheel {direction}"
        if self.kind == "delay":
            return f"Delay: {self.delay_ms} ms ({self.delay_ms / 1000.0:.3f} s)"
        return f"Unknown({self.kind})"

    def to_dict(self) -> Dict[str, object]:
        return {
            "kind": self.kind,
            "code": self.code,
            "delay_ms": self.delay_ms,
            "dx": self.dx,
            "dy": self.dy,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> "MacroStep":
        return cls(
            kind=str(d["kind"]),  # type: ignore[arg-type]
            code=int(d.get("code", 0)),
            delay_ms=int(d.get("delay_ms", 0)),
            dx=int(d.get("dx", 0)),
            dy=int(d.get("dy", 0)),
        )


def encode_macro(steps: List[MacroStep]) -> bytes:
    """Serialize a list of MacroStep objects into firmware bytecode."""
    out = bytearray()
    for step in steps:
        if step.kind == "key_down":
            if step.code in MODIFIER_HID_TO_BIT:
                out.append(0x09)
                out.append(int(MODIFIER_HID_TO_BIT[step.code]))
            else:
                out.append(0x02)
                out.append(step.code & 0xFF)
        elif step.kind == "key_up":
            if step.code in MODIFIER_HID_TO_BIT:
                out.append(0x0A)
                out.append(int(MODIFIER_HID_TO_BIT[step.code]))
            else:
                out.append(0x03)
                out.append(step.code & 0xFF)
        elif step.kind == "mouse_down":
            out.append(0x01)
            out.append(step.code & 0xFF)
        elif step.kind == "mouse_up":
            # In firmware bytecode, mouse release is opcode 0x01, operand 0x00
            out.append(0x01)
            out.append(0x00)
        elif step.kind == "mouse_move":
            xhi, xlo = _encode_signed16(step.dx)
            yhi, ylo = _encode_signed16(step.dy)
            out.extend((0x08, xhi, xlo, yhi, ylo))
        elif step.kind == "wheel":
            out.append(0x10)
            out.append(0x01 if step.code >= 0 else 0xFF)
        elif step.kind == "delay":
            ms = max(0, int(step.delay_ms))
            if ms <= 0xFF:
                out.extend((0x20, ms))
            elif ms <= 0xFFFF:
                out.extend((0x21, (ms >> 8) & 0xFF, ms & 0xFF))
            elif ms <= 0xFFFFFF:
                out.extend((0x22, (ms >> 16) & 0xFF, (ms >> 8) & 0xFF, ms & 0xFF))
            else:
                ms = min(ms, 0xFFFFFFFF)
                out.extend(
                    (
                        0x23,
                        (ms >> 24) & 0xFF,
                        (ms >> 16) & 0xFF,
                        (ms >> 8) & 0xFF,
                        ms & 0xFF,
                    )
                )
        else:
            raise ValueError(f"Unsupported macro step kind: {step.kind!r}")
    return bytes(out)


def decode_macro(data: bytes) -> List[MacroStep]:
    """Decode firmware macro bytecode into a list of MacroStep objects."""
    steps: List[MacroStep] = []
    i = 0
    n = len(data)
    last_btn = 0

    while i < n:
        op = data[i]
        if op == 0x01 and i + 1 < n:
            btn = data[i + 1]
            if btn > 0:
                last_btn = btn
                steps.append(MacroStep(kind="mouse_down", code=btn))
            else:
                steps.append(MacroStep(kind="mouse_up", code=last_btn))
            i += 2
        elif op == 0x02 and i + 1 < n:
            steps.append(MacroStep(kind="key_down", code=data[i + 1]))
            i += 2
        elif op == 0x03 and i + 1 < n:
            steps.append(MacroStep(kind="key_up", code=data[i + 1]))
            i += 2
        elif op == 0x09 and i + 1 < n:
            bit = Modifier(data[i + 1])
            hid_code = MODIFIER_BIT_TO_HID.get(bit, 0xE0)
            steps.append(MacroStep(kind="key_down", code=hid_code))
            i += 2
        elif op == 0x0A and i + 1 < n:
            bit = Modifier(data[i + 1])
            hid_code = MODIFIER_BIT_TO_HID.get(bit, 0xE0)
            steps.append(MacroStep(kind="key_up", code=hid_code))
            i += 2
        elif op == 0x08 and i + 4 < n:
            dx = _decode_signed16(data[i + 1], data[i + 2])
            dy = _decode_signed16(data[i + 3], data[i + 4])
            steps.append(MacroStep(kind="mouse_move", dx=dx, dy=dy))
            i += 5
        elif op == 0x10 and i + 1 < n:
            w = 1 if data[i + 1] == 1 else -1
            steps.append(MacroStep(kind="wheel", code=w))
            i += 2
        elif op == 0x20 and i + 1 < n:
            steps.append(MacroStep(kind="delay", delay_ms=data[i + 1]))
            i += 2
        elif op == 0x21 and i + 2 < n:
            ms = (data[i + 1] << 8) | data[i + 2]
            steps.append(MacroStep(kind="delay", delay_ms=ms))
            i += 3
        elif op in (0x13, 0x22) and i + 3 < n:
            ms = (data[i + 1] << 16) | (data[i + 2] << 8) | data[i + 3]
            steps.append(MacroStep(kind="delay", delay_ms=ms))
            i += 4
        elif op in (0x14, 0x23) and i + 4 < n:
            ms = (
                (data[i + 1] << 24)
                | (data[i + 2] << 16)
                | (data[i + 3] << 8)
                | data[i + 4]
            )
            steps.append(MacroStep(kind="delay", delay_ms=ms))
            i += 5
        else:
            # Stop on unknown/trailing padding
            break

    return steps
