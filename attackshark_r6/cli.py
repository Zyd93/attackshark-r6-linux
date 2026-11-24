"""Command-line interface for ATTACK SHARK R6 mouse on Linux."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import List, Optional, Tuple

from .constants import (
    BUTTON_ALIASES,
    BUTTON_LABELS,
    CONFIGURABLE_BUTTONS,
    CONSUMER_KEY_LABELS,
    DPI_MAX_STAGES,
    LOD_CODE_TO_NAME,
    LOD_NAME_TO_CODE,
    MACRO_MAX_ID,
    MACRO_MIN_ID,
    POWER_KEY_LABELS,
    PROFILE_MAX,
    PROFILE_MIN,
    SLEEP_DISABLED,
    WIRED_POLLING_RATES,
    WIRELESS_POLLING_RATES,
    ButtonID,
    ConsumerKey,
    DPIAction,
    PowerKey,
    ProfileAction,
    parse_hid_key,
    parse_modifiers,
)
from .hid_transport import (
    HidrawTransport,
    NotificationListener,
    R6DeviceInfo,
    discover_devices,
)
from .protocol import (
    TARGET_MOUSE,
    ButtonBinding,
    DPIStage,
    R6Protocol,
    build_packet,
)


def _select_device(device_path: Optional[str]) -> R6DeviceInfo:
    devices = discover_devices()
    if device_path:
        for d in devices:
            if d.control_path == device_path:
                if not d.has_permission:
                    sys.exit(
                        f"Permission denied on {d.control_path}. "
                        "Install 60-attackshark-r6.rules (run ./install.sh) and reconnect or re-login."
                    )
                return d
        sys.exit(f"Device not found at {device_path}")

    if not devices:
        sys.exit("No ATTACK SHARK R6 mouse found (expected USB VID 373E, PID 0021/0022).")

    for d in devices:
        if d.has_permission:
            return d

    d0 = devices[0]
    sys.exit(
        f"Found {d0.name} ({d0.mode_label}) at {d0.control_path}, "
        "but lacks read/write permissions.\n"
        "Run ./install.sh to install udev rules (60-attackshark-r6.rules)."
    )


def _open_proto(
    device_path: Optional[str], debug: bool = False
) -> Tuple[R6DeviceInfo, HidrawTransport, R6Protocol]:
    info = _select_device(device_path)
    transport = HidrawTransport(info.control_path, debug=debug)
    transport.open()
    return info, transport, R6Protocol(transport)


def _parse_bool(val: str) -> bool:
    v = val.strip().lower()
    if v in ("1", "on", "true", "yes", "enable", "enabled"):
        return True
    if v in ("0", "off", "false", "no", "disable", "disabled"):
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {val!r}")


def _parse_hex_color(spec: str) -> Tuple[int, int, int]:
    s = spec.strip().lstrip("#")
    if len(s) == 8:  # allow AARRGGBB
        s = s[2:]
    if len(s) != 6:
        raise ValueError(f"Invalid RGB hex color: {spec!r}")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _parse_dpi_stage(spec: str) -> DPIStage:
    s = spec.strip().lower()
    if "x" in s:
        px, py = s.split("x", 1)
        return DPIStage(x=int(px), y=int(py)).normalized()
    v = int(s)
    return DPIStage(x=v, y=v).normalized()


def _parse_button_id(spec: str) -> ButtonID:
    key = spec.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    if key in BUTTON_ALIASES:
        return BUTTON_ALIASES[key]
    raise ValueError(
        f"Unknown button {spec!r}. Valid: {', '.join(b.name.lower() for b in CONFIGURABLE_BUTTONS)}"
    )


def _parse_binding(action: str, extra: List[str]) -> ButtonBinding:
    act = action.strip().lower().replace("_", "-")
    if act in ("off", "disable", "disabled"):
        return ButtonBinding.off()
    if act in ("mouse", "button"):
        if not extra:
            raise ValueError("mouse binding requires target button (left/right/middle/backward/forward/scrollup/scrolldown)")
        return ButtonBinding.mouse_button(_parse_button_id(extra[0]))
    if act in ("double-click", "doubleclick", "ldoubleclick"):
        return ButtonBinding.double_click()
    if act == "xclick":
        btn = _parse_button_id(extra[0]) if len(extra) >= 1 else ButtonID.LEFT
        cnt = int(extra[1]) if len(extra) >= 2 else 2
        interval = int(extra[2]) if len(extra) >= 3 else 100
        return ButtonBinding.double_click(btn=btn, clicks=cnt, interval_ms=interval)
    if act in ("key", "keyboard"):
        if not extra:
            raise ValueError("key binding requires key combo like 'A' or 'LCtrl+C'")
        raw = "+".join(extra)
        tokens = [t.strip() for t in raw.split("+") if t.strip()]
        if len(tokens) == 1:
            return ButtonBinding.keyboard(0, parse_hid_key(tokens[0]))
        mods = parse_modifiers(tokens[:-1])
        key = parse_hid_key(tokens[-1])
        return ButtonBinding.keyboard(mods, key)
    if act in ("media", "consumer"):
        if not extra:
            raise ValueError("media binding requires action name or hex usage")
        key = " ".join(extra).strip().lower()
        for usage, label in CONSUMER_KEY_LABELS.items():
            if key in (label.lower(), label.lower().replace(" ", "-"), label.lower().replace("/", "-")):
                return ButtonBinding.consumer(int(usage))
        for ck in ConsumerKey:
            if key == ck.name.lower() or key == ck.name.lower().replace("_", "-"):
                return ButtonBinding.consumer(int(ck))
        if key.startswith("0x"):
            return ButtonBinding.consumer(int(key, 16))
        raise ValueError(f"Unknown media key: {extra!r}")
    if act == "power":
        if not extra:
            raise ValueError("power binding requires power|sleep|wake")
        k = extra[0].lower()
        if k in ("power", "system-power"):
            return ButtonBinding.power(PowerKey.SYSTEM_POWER)
        if k in ("sleep", "system-sleep"):
            return ButtonBinding.power(PowerKey.SYSTEM_SLEEP)
        if k in ("wake", "system-wake"):
            return ButtonBinding.power(PowerKey.SYSTEM_WAKE)
        raise ValueError(f"Unknown power key: {extra[0]!r}")
    if act == "dpi-up":
        return ButtonBinding.dpi_action(DPIAction.STAGE_UP)
    if act == "dpi-down":
        return ButtonBinding.dpi_action(DPIAction.STAGE_DOWN)
    if act in ("dpi-cycle-up", "dpi+"):
        return ButtonBinding.dpi_action(DPIAction.CYCLE_UP)
    if act in ("dpi-cycle-down", "dpi-"):
        return ButtonBinding.dpi_action(DPIAction.CYCLE_DOWN)
    if act == "dpi-lock":
        dpi_val = int(extra[0]) if extra else 800
        return ButtonBinding.dpi_action(DPIAction.STAGE_LOCK, lock_dpi=dpi_val)
    if act == "profile-up":
        return ButtonBinding.profile_action(ProfileAction.PROFILE_UP)
    if act == "profile-down":
        return ButtonBinding.profile_action(ProfileAction.PROFILE_DOWN)
    if act == "profile-loop-up":
        return ButtonBinding.profile_action(ProfileAction.LOOP_UP)
    if act == "profile-loop-down":
        return ButtonBinding.profile_action(ProfileAction.LOOP_DOWN)
    if act in ("battery", "bat"):
        return ButtonBinding.battery_indicator()
    if act in ("macro1", "macro-repeat"):
        if not extra:
            raise ValueError("macro1 requires <macro_id> [repeat_count]")
        mid = int(extra[0])
        rep = int(extra[1]) if len(extra) >= 2 else 1
        return ButtonBinding.macro_repeat(mid, rep)
    if act in ("macro2", "macro-hold"):
        if not extra:
            raise ValueError("macro2 requires <macro_id>")
        return ButtonBinding.macro_hold(int(extra[0]))
    if act in ("macro3", "macro-toggle"):
        if not extra:
            raise ValueError("macro3 requires <macro_id>")
        return ButtonBinding.macro_toggle(int(extra[0]))
    raise ValueError(f"Unknown button action: {action!r}")


def cmd_devices(args: argparse.Namespace) -> int:
    devs = discover_devices()
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "vid": f"0x{d.vid:04X}",
                        "pid": f"0x{d.pid:04X}",
                        "name": d.name,
                        "mode": d.mode_label,
                        "serial": d.serial,
                        "control_path": d.control_path,
                        "notify_path": d.notify_path,
                        "boot_mouse_path": d.boot_mouse_path,
                        "control_rw": d.control_rw,
                        "notify_ro": d.notify_ro,
                    }
                    for d in devs
                ],
                indent=2,
            )
        )
        return 0
    if not devs:
        print("No ATTACK SHARK R6 devices connected.")
        return 1
    for d in devs:
        perm = "OK (rw)" if d.has_permission else "NO PERMISSION (install udev rule)"
        print(
            f"{d.name} [{d.vid:04X}:{d.pid:04X} {d.mode_label}] serial={d.serial or '-'}\n"
            f"  Control: {d.control_path} ({perm})\n"
            f"  Notify : {d.notify_path or '-'} ({'OK (ro)' if d.notify_ro else 'no permission'})\n"
            f"  Mouse  : {d.boot_mouse_path or '-'}"
        )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    info, tr, proto = _open_proto(args.device, debug=args.debug)
    try:
        state = proto.read_full_state(profile_id=args.profile)
        if args.json:
            payload = state.to_export_dict()
            payload["connection_mode"] = info.mode_label
            payload["device_fw"] = state.device_fw
            payload["dongle_fw"] = state.dongle_fw
            payload["battery_percent"] = state.battery_percent
            payload["battery_charging"] = state.battery_charging
            print(json.dumps(payload, indent=2))
            return 0

        chg = " (Charging)" if state.battery_charging else ""
        sleep_str = "Never" if state.sleep_sec == SLEEP_DISABLED else f"{state.sleep_sec}s"
        lod_str = LOD_CODE_TO_NAME.get(state.lod_code, f"0x{state.lod_code:02X}")
        print(f"Device        : {info.name} [{info.mode_label}] ({info.control_path})")
        print(f"Mouse FW      : {state.device_fw}   Dongle FW: {state.dongle_fw}   PID: 0x{state.device_pid:04X}")
        print(f"Battery       : {state.battery_percent}%{chg}")
        print(f"Profile       : {state.profile_id}")
        print(f"Polling Rate  : {state.polling_rate_hz} Hz")
        print(f"LOD           : {lod_str}")
        print(f"Debounce      : {state.debounce_ms} ms")
        print(f"Sleep Timeout : {sleep_str}")
        print(
            f"Sensor Tuning : MotionSync={'ON' if state.motion_sync else 'OFF'}, "
            f"Ripple={'ON' if state.ripple_control else 'OFF'}, "
            f"AngleSnap={'ON' if state.angle_snap else 'OFF'}"
        )
        print(f"DPI Stages    : ({len(state.dpi_stages)} active, current=#{state.active_dpi_stage})")
        for idx, st in enumerate(state.dpi_stages, 1):
            r, g, b = state.dpi_colors[idx - 1]
            mark = "*" if idx == state.active_dpi_stage else " "
            xy = f"{st.x}" if st.x == st.y else f"{st.x}x{st.y}"
            print(f"  {mark} Stage {idx}: {xy:>11s} DPI   Color: #{r:02X}{g:02X}{b:02X}")
        print("Buttons:")
        for bid in CONFIGURABLE_BUTTONS:
            binding = state.buttons[int(bid)]
            print(f"  {BUTTON_LABELS[bid]:15s}: {binding.describe()}")
        return 0
    finally:
        tr.close()


def cmd_probe(args: argparse.Namespace) -> int:
    info, tr, proto = _open_proto(args.device, debug=True)
    try:
        print(f"Probing {info.name} on {info.control_path}")
        for label, pkt in [
            ("GetBattery", build_packet(TARGET_MOUSE, 0x02, 0x00, 0x83)),
            ("GetDeviceFW", build_packet(TARGET_MOUSE, 0x10, 0x00, 0x81)),
            ("GetProfileID", build_packet(TARGET_MOUSE, 0x01, 0x00, 0x85)),
        ]:
            print(f"\n--- {label} ---")
            tr.set_feature(pkt)
            time.sleep(0.03)
            ret, raw = tr.get_feature_raw()
            print(f"HIDIOCGFEATURE ret={ret}, raw[0:16]={bytes(raw[:16]).hex(' ')}")
        print("\nParsed:")
        print("  FW:", proto.get_device_fw_version())
        print("  Battery:", proto.get_battery())
        print("  Profile:", proto.get_profile_id())
        return 0
    finally:
        tr.close()


def cmd_monitor(args: argparse.Namespace) -> int:
    info = _select_device(args.device)
    if not info.notify_path:
        sys.exit("Notification interface (MI01) not found.")
    if not info.notify_ro:
        sys.exit(f"No read permission on {info.notify_path}.")
    print(f"Listening for live mouse notifications on {info.notify_path} (Ctrl+C to stop)...")

    def on_evt(kind: str, data: bytes) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {kind}: {data.hex(' ')}", flush=True)

    listener = NotificationListener(info.notify_path, on_evt)
    listener.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        listener.stop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="attackshark-r6-cli",
        description="Native Linux configurator CLI for ATTACK SHARK R6 mouse.",
    )
    p.add_argument("-d", "--device", help="Explicit hidraw control path (e.g. /dev/hidraw4)")
    p.add_argument("--debug", action="store_true", help="Print raw HID feature frames")

    sub = p.add_subparsers(dest="command", required=True)

    s_dev = sub.add_parser("devices", help="List detected ATTACK SHARK R6 devices")
    s_dev.add_argument("--json", action="store_true")
    s_dev.set_defaults(func=cmd_devices)

    s_stat = sub.add_parser("status", help="Read full mouse configuration")
    s_stat.add_argument("--profile", type=int, choices=range(PROFILE_MIN, PROFILE_MAX + 1))
    s_stat.add_argument("--json", action="store_true")
    s_stat.set_defaults(func=cmd_status)

    s_probe = sub.add_parser("probe", help="Inspect raw hidraw feature responses")
    s_probe.set_defaults(func=cmd_probe)

    s_mon = sub.add_parser("monitor", help="Stream live hardware notifications (DPI/wake/sleep)")
    s_mon.set_defaults(func=cmd_monitor)

    s_prof = sub.add_parser("set-profile", help="Switch active onboard profile (1..3)")
    s_prof.add_argument("profile_id", type=int, choices=range(PROFILE_MIN, PROFILE_MAX + 1))

    s_dpi = sub.add_parser("set-dpi", help="Set 1..6 DPI stages (e.g. 400 800 1600 3200)")
    s_dpi.add_argument("stages", nargs="+", help="DPI values or XxY pairs (50..42000)")
    s_dpi.add_argument("--profile", type=int, choices=range(PROFILE_MIN, PROFILE_MAX + 1))

    s_adpi = sub.add_parser("set-active-dpi", help="Select active DPI stage (1..6)")
    s_adpi.add_argument("stage", type=int, choices=range(1, DPI_MAX_STAGES + 1))
    s_adpi.add_argument("--profile", type=int, choices=range(PROFILE_MIN, PROFILE_MAX + 1))

    s_dcol = sub.add_parser("set-dpi-colors", help="Set up to 6 DPI stage RGB hex colors")
    s_dcol.add_argument("colors", nargs="+", help="Hex colors like #FF0000")
    s_dcol.add_argument("--profile", type=int, choices=range(PROFILE_MIN, PROFILE_MAX + 1))

    s_poll = sub.add_parser("set-polling", help="Set polling rate in Hz")
    s_poll.add_argument("hz", type=int, choices=WIRELESS_POLLING_RATES)
    s_poll.add_argument("--profile", type=int, choices=range(PROFILE_MIN, PROFILE_MAX + 1))

    s_lod = sub.add_parser("set-lod", help="Set lift-off distance (0.7mm, 1mm, 2mm)")
    s_lod.add_argument("lod", choices=["0.7mm", "1mm", "2mm", "0.7", "1", "2"])
    s_lod.add_argument("--profile", type=int, choices=range(PROFILE_MIN, PROFILE_MAX + 1))

    s_deb = sub.add_parser("set-debounce", help="Set button debounce time (0..15 ms)")
    s_deb.add_argument("ms", type=int)
    s_deb.add_argument("--profile", type=int, choices=range(PROFILE_MIN, PROFILE_MAX + 1))

    s_slp = sub.add_parser("set-sleep", help="Set wireless sleep timeout (15..1800s or 'off')")
    s_slp.add_argument("seconds", help="Seconds (15..1800) or 'off'")
    s_slp.add_argument("--profile", type=int, choices=range(PROFILE_MIN, PROFILE_MAX + 1))

    s_sen = sub.add_parser("set-sensor", help="Toggle MotionSync, Ripple Control, Angle Snap")
    s_sen.add_argument("--motion-sync", type=_parse_bool, default=None)
    s_sen.add_argument("--ripple", type=_parse_bool, default=None)
    s_sen.add_argument("--angle-snap", type=_parse_bool, default=None)
    s_sen.add_argument("--profile", type=int, choices=range(PROFILE_MIN, PROFILE_MAX + 1))

    s_btns = sub.add_parser("buttons", help="Show button assignments")
    s_btns.add_argument("--profile", type=int, choices=range(PROFILE_MIN, PROFILE_MAX + 1))

    s_sbtn = sub.add_parser("set-button", help="Assign a function to a button")
    s_sbtn.add_argument("button", help="left|right|middle|backward|forward|scrollup|scrolldown|dpi")
    s_sbtn.add_argument(
        "action",
        help="off|mouse|double-click|xclick|key|media|power|dpi-up|dpi-down|dpi-cycle-up|dpi-cycle-down|dpi-lock|profile-up|profile-down|battery|macro1|macro2|macro3",
    )
    s_sbtn.add_argument("extra", nargs="*", help="Action arguments")
    s_sbtn.add_argument("--profile", type=int, choices=range(PROFILE_MIN, PROFILE_MAX + 1))

    s_mac = sub.add_parser("macros", help="Manage onboard macros (1..29)")
    mac_sub = s_mac.add_subparsers(dest="macro_cmd", required=True)
    mac_sub.add_parser("list", help="List stored onboard macros")
    mg = mac_sub.add_parser("get", help="Print decoded macro steps")
    mg.add_argument("macro_id", type=int)
    md = mac_sub.add_parser("delete", help="Delete an onboard macro")
    md.add_argument("macro_id", type=int)

    s_pair = sub.add_parser("pair", help="Start 2.4G receiver pairing")
    s_pair.add_argument("--timeout", type=int, default=20)

    s_rst = sub.add_parser("reset", help="Reset current profile or factory reset")
    s_rst.add_argument("--factory", action="store_true")
    s_rst.add_argument("--profile", type=int, choices=range(PROFILE_MIN, PROFILE_MAX + 1))

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return int(args.func(args))

    info, tr, proto = _open_proto(args.device, debug=args.debug)
    try:
        prof = getattr(args, "profile", None)
        if prof is None and args.command not in ("set-profile", "macros", "pair"):
            prof = proto.get_profile_id()

        if args.command == "set-profile":
            ok = proto.set_profile_id(args.profile_id)
            print(f"Profile -> {args.profile_id}: {'OK' if ok else 'Failed'}")
            return 0 if ok else 1

        if args.command == "set-dpi":
            stages = [_parse_dpi_stage(s) for s in args.stages[:DPI_MAX_STAGES]]
            ok = proto.set_dpi_stages(prof, stages)
            print(f"DPI stages updated ({len(stages)} stages): {'OK' if ok else 'Failed'}")
            return 0 if ok else 1

        if args.command == "set-active-dpi":
            ok = proto.set_active_dpi(prof, args.stage)
            print(f"Active DPI stage -> {args.stage}: {'OK' if ok else 'Failed'}")
            return 0 if ok else 1

        if args.command == "set-dpi-colors":
            colors = proto.get_dpi_colors(prof)
            for idx, hex_c in enumerate(args.colors[:DPI_MAX_STAGES]):
                colors[idx] = _parse_hex_color(hex_c)
            ok = proto.set_dpi_colors(prof, colors)
            print(f"DPI colors updated: {'OK' if ok else 'Failed'}")
            return 0 if ok else 1

        if args.command == "set-polling":
            allowed = WIRELESS_POLLING_RATES if info.is_wireless else WIRED_POLLING_RATES
            if args.hz not in allowed:
                sys.exit(f"Polling rate {args.hz}Hz is not supported in {info.mode_label} mode (allowed: {allowed})")
            ok = proto.set_polling_rate(prof, args.hz)
            print(f"Polling rate -> {args.hz} Hz: {'OK' if ok else 'Failed'}")
            return 0 if ok else 1

        if args.command == "set-lod":
            code = LOD_NAME_TO_CODE[args.lod]
            ok = proto.set_lod(prof, code)
            print(f"LOD -> {LOD_CODE_TO_NAME[code]}: {'OK' if ok else 'Failed'}")
            return 0 if ok else 1

        if args.command == "set-debounce":
            ok = proto.set_debounce_time(prof, args.ms)
            print(f"Debounce -> {args.ms} ms: {'OK' if ok else 'Failed'}")
            return 0 if ok else 1

        if args.command == "set-sleep":
            sec = SLEEP_DISABLED if args.seconds.lower() in ("off", "never", "disable") else int(args.seconds)
            ok = proto.set_sleep_time(prof, sec)
            print(f"Sleep timeout updated: {'OK' if ok else 'Failed'}")
            return 0 if ok else 1

        if args.command == "set-sensor":
            if args.motion_sync is None and args.ripple is None and args.angle_snap is None:
                sys.exit("Specify at least one of --motion-sync, --ripple, or --angle-snap")
            if args.motion_sync is not None:
                proto.set_motion_sync(prof, args.motion_sync)
            if args.ripple is not None:
                proto.set_ripple_control(prof, args.ripple)
            if args.angle_snap is not None:
                proto.set_angle_snap(prof, args.angle_snap)
            print("Sensor tuning updated.")
            return 0

        if args.command == "buttons":
            for bid in CONFIGURABLE_BUTTONS:
                b = proto.get_button(prof, bid)
                print(f"{BUTTON_LABELS[bid]:15s}: {b.describe()}")
            return 0

        if args.command == "set-button":
            bid = _parse_button_id(args.button)
            binding = _parse_binding(args.action, args.extra)
            ok = proto.set_button(prof, bid, binding)
            print(f"{BUTTON_LABELS.get(bid, bid.name)} -> {binding.describe()}: {'OK' if ok else 'Failed'}")
            return 0 if ok else 1

        if args.command == "macros":
            if args.macro_cmd == "list":
                found = proto.list_macros()
                if not found:
                    print("No onboard macros stored.")
                for mid, sz in sorted(found.items()):
                    print(f"Macro #{mid:2d}: {sz} bytes")
                return 0
            if args.macro_cmd == "get":
                if not (MACRO_MIN_ID <= args.macro_id <= MACRO_MAX_ID):
                    sys.exit(f"Macro ID must be {MACRO_MIN_ID}..{MACRO_MAX_ID}")
                steps = proto.get_macro(args.macro_id)
                if not steps:
                    print(f"Macro #{args.macro_id} is empty.")
                    return 0
                for idx, st in enumerate(steps, 1):
                    print(f"  {idx:3d}. {st.describe()}")
                return 0
            if args.macro_cmd == "delete":
                ok = proto.delete_macro(args.macro_id)
                print(f"Delete macro #{args.macro_id}: {'OK' if ok else 'Failed'}")
                return 0 if ok else 1

        if args.command == "pair":
            print("Hold Left + Middle + Right mouse buttons for 3 seconds until LED flashes fast.")
            proto.set_pair_status(True)
            deadline = time.monotonic() + args.timeout
            try:
                while time.monotonic() < deadline:
                    st = proto.get_pair_status()
                    if st == 2:
                        proto.set_pair_status(False)
                        print("Paired successfully!")
                        return 0
                    time.sleep(0.5)
            finally:
                proto.set_pair_status(False)
            print("Pairing timed out.")
            return 1

        if args.command == "reset":
            if args.factory:
                ok = proto.factory_reset(prof or 1)
                print(f"Factory reset: {'OK' if ok else 'Failed'}")
                return 0 if ok else 1
            ok = proto.reset_profile(prof)
            print(f"Reset profile {prof}: {'OK' if ok else 'Failed'}")
            return 0 if ok else 1

    finally:
        tr.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
