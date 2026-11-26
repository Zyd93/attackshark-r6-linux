# Security Policy

## Scope & Design Principles

**ATTACK SHARK R6 — Linux Control Center** is an open-source, user-space USB HID configuration utility for the ATTACK SHARK R6 mouse (`373e:0021` Wired and `373e:0022` Wireless 2.4G).

Key security boundaries:
- **User-space `/dev/hidraw*` access only:** The desktop GUI and CLI never run as `root` and never load kernel modules. Hardware communication uses standard Linux `HIDIOCSFEATURE` / `HIDIOCGFEATURE` ioctls and non-blocking `read()` calls on the vendor-defined `hidraw` interfaces.
- **Scoped `uaccess` udev rule (`60-attackshark-r6.rules`):** Only matches USB VID/PID `373e:0021` and `373e:0022` on `hidraw*` nodes (no raw `usb` device access is granted) and grants local desktop session access via systemd `TAG+="uaccess"` (`MODE="0660"`), processed before systemd's `73-seat-late.rules` without making device nodes world-writable.
- **Least-privilege permission setup:** Only the one-time installation of `/etc/udev/rules.d/60-attackshark-r6.rules` uses `sudo` or `pkexec`.
- **Zero network activity or telemetry:** The application makes zero outbound network connections and sends no analytics.
- **Local single-instance IPC:** Single-instance window activation uses a Qt `QLocalServer` / `QLocalSocket` named socket scoped to the current user's numeric UID (`attackshark-r6-linux-<uid>`).

## Reporting a Vulnerability

If you discover a security issue (such as unsafe privilege elevation, command injection, or malformed HID buffer handling):
1. Please use GitHub **Security Advisories** (*Security* tab → *Report a vulnerability*) or open an issue at [GitHub Issues](https://github.com/Zyd93/attackshark-r6-linux/issues) if advisories are unavailable.
2. Include your Linux distribution/desktop environment, reproduction steps, and the relevant module (`attackshark_r6/hid_transport.py`, `attackshark_r6/protocol.py`, `attackshark_r6/gui.py`, `install.sh`, etc.).
