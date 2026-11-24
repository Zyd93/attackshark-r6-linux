<p align="center">
  <img src="assets/icon.png" alt="ATTACK SHARK R6 — Linux Control Center" width="140" />
</p>

<h1 align="center">ATTACK SHARK R6 — Linux Control Center</h1>

<p align="center">
  <strong>Native open-source Linux USB HID driver, PyQt5 desktop configurator, and CLI for the ATTACK SHARK R6 mouse (Wired &amp; 2.4G Wireless 8K).</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="License: GPLv3" /></a>
  <img src="https://img.shields.io/badge/Platform-Linux%20(hidraw)-informational" alt="Platform: Linux" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-green" alt="Python 3.10+" />
  <a href="https://github.com/Zyd93/attackshark-r6-linux/releases"><img src="https://img.shields.io/github/v/release/Zyd93/attackshark-r6-linux" alt="Latest Release" /></a>
</p>

> [!NOTE]
> **Pure Linux `hidraw` implementation:** Communicates directly with the mouse hardware via `/dev/hidraw*` without Wine, Mono, VirtualBox, or Windows drivers.
> **Built with Agentic AI:** Created with the help of **Antigravity** (Google DeepMind).
> *Unofficial community software — not affiliated with or endorsed by ATTACK SHARK.*

---

## Table of Contents

- [Supported Hardware](#supported-hardware)
- [Features](#features)
- [Zero-Resource System Tray Idle Mode](#zero-resource-system-tray-idle-mode)
- [Installation](#installation)
  - [Dependencies by Distribution](#dependencies-by-distribution)
  - [Install from Release or Git](#install-from-release-or-git)
  - [Uninstall](#uninstall)
- [Desktop GUI Overview](#desktop-gui-overview)
- [CLI Reference](#cli-reference)
- [Architecture & USB HID Protocol Overview](#architecture--usb-hid-protocol-overview)
- [Troubleshooting](#troubleshooting)
- [Development & Testing](#development--testing)
- [Contributors](#contributors)
- [License](#license)

---

## Supported Hardware

| Connection Mode | USB VID:PID | Control Interface | Live Notifications | Polling Rates |
| :--- | :---: | :--- | :--- | :--- |
| **Wired USB-C** | `373e:0021` | `hidraw` (`HIDIOCSFEATURE` / `HIDIOCGFEATURE`) | `MI01` interrupt reports | `125`, `250`, `500`, `1000 Hz` |
| **Wireless 2.4G 8K Dongle** | `373e:0022` | `hidraw` (`HIDIOCSFEATURE` / `HIDIOCGFEATURE`) | `MI01` interrupt reports | `125`, `250`, `500`, `1000`, `2000`, `4000`, `8000 Hz` |

---

## Features

- **Automatic Hotplug & Live Telemetry**: Detects Wired and 2.4G Wireless connections, reads Mouse & Dongle firmware versions (`00.00.03.01` / `00.00.03.00`), battery percentage & charging state, and streams `MI01` hardware events (DPI changes, wake/sleep, LOD, polling rate switches).
- **Profiles 1–3**: Read, switch active onboard profile, export/import full JSON backups, reset current profile, or factory reset mouse & dongle.
- **Full Button Remapping**: Configure Left, Right, Middle, Backward, Forward, Scroll Up, and Scroll Down (plus `DPI` alias in CLI) to:
  - Standard mouse clicks, Double-Click, or X-Click (burst count & interval)
  - Any USB HID keyboard key + modifier chord (`Ctrl`, `Shift`, `Alt`, `Meta`/`Super`)
  - Multimedia / Consumer keys & System Power actions
  - DPI actions (Up, Down, Cycle Up/Down, **DPI Lock / Sniper DPI**)
  - Profile switching & Wireless Battery LED check
  - Onboard Macros (Run N times / Repeat, Hold-to-repeat, Toggle) or Disable (`Off`)
- **Sensor & Performance Tuning**:
  - Up to **6 DPI stages** (`50–42,000 DPI`, step `50`), optional independent X/Y DPI, active stage switching, and per-stage RGB hex colors
  - Polling rate (`125–1000 Hz` wired; `125–8000 Hz` 2.4G wireless)
  - Lift-Off Distance (**LOD**): `0.7 mm`, `1.0 mm`, `2.0 mm`
  - Button debounce time: `0–15 ms`
  - Wireless sleep timeout: `15 s – 1800 s` (`30 min`), or `Never` (`0xFFFF`)
  - Hardware sensor toggles: **Motion Sync**, **Ripple Control**, **Angle Snapping**
- **Wayland-Safe Onboard Macro Editor (Slots 1–29)**:
  - Live keyboard/mouse capture inside the Qt pad or manual insertion of Key Down/Up, Mouse Down/Up, Wheel, Relative Move, and Delay steps
  - Chunked onboard flash read, write, allocation, and deletion
- **2.4 GHz Receiver Pairing Wizard**: Pair a mouse and 8K wireless receiver natively on Linux.
- **Zero-Resource Tray Idle Mode**: Minimizing to the system tray tears down polling, workers, and `/dev/hidraw*` file descriptors until reopened.

---

## Zero-Resource System Tray Idle Mode

Because all configuration settings, DPI stages, button bindings, and macros live inside the mouse's onboard flash memory, the desktop configurator does **not** need to poll USB HID devices while sitting in the background.

When **Minimize to system tray when pressing X** is enabled in the **Settings** tab (enabled by default):

1. Pressing the window close button (**X**) hides the main window to your desktop taskbar / system tray instead of exiting.
2. **`enter_tray_idle()` immediately shuts down all active background work**:
   - Stops `hotplug_timer`, `battery_timer`, and any active pairing timer (`0` periodic timer wakeups/sec, ~`0%` CPU).
   - Stops the `MI01` `NotificationListener` background thread.
   - Signals cancellation (`cancel_check`) to any long macro scan and waits cleanly for active `TaskWorker` threads.
   - Closes open `/dev/hidraw*` file descriptors and clears live `transport` / `proto` / `state` objects.
   - Runs `gc.collect()` and best-effort `malloc_trim(0)` via `libc.so.6` to return freed heap pages back to the kernel.
3. **Instant Single-Instance Wakeup**: Left-clicking (or double-clicking) the tray icon — or launching `attackshark-r6` again from your app menu/terminal — signals the sleeping instance over a UID-scoped `QLocalServer` socket (`attackshark-r6-linux-<uid>`), reopens the window, re-attaches `/dev/hidraw*`, and syncs live mouse state immediately.
4. **Full Exit**: Right-click the tray icon → **Quit**, click **Quit Application (Ctrl+Q)** in the Settings tab, or press `Ctrl+Q`. You can also start directly into tray idle mode with `attackshark-r6 --minimized` (or enable **Start minimized to system tray** in Settings).

---

## Installation

### Dependencies by Distribution

- **Python**: 3.10+ (standard library is sufficient for the CLI and tests)
- **GUI toolkit**: `PyQt5` (with `PyQt5.QtSvg` only needed if regenerating PNGs from SVGs)
- **Privilege helper (GUI installer button only)**: `polkit` (`pkexec`) or `sudo`

<details>
<summary>Install packages on Arch / CachyOS, Ubuntu / Debian, or Fedora</summary>

- **Arch / CachyOS**:
  ```bash
  sudo pacman -S python python-pyqt5 polkit
  ```
- **Ubuntu / Debian**:
  ```bash
  sudo apt install python3 python3-pyqt5 python3-pyqt5.qtsvg policykit-1
  ```
- **Fedora**:
  ```bash
  sudo dnf install python3 python3-qt5 polkit
  ```

</details>

### Install from Release or Git

**Option A — Release tarball** (from [GitHub Releases](https://github.com/Zyd93/attackshark-r6-linux/releases)):
```bash
tar -xzf attackshark-r6-linux.tar.gz
cd attackshark-r6-linux
./install.sh
```

**Option B — Clone from Git**:
```bash
git clone https://github.com/Zyd93/attackshark-r6-linux.git
cd attackshark-r6-linux
./install.sh
```

What `./install.sh` sets up:
1. Symlinks `attackshark-r6` and `attackshark-r6-cli` into `~/.local/bin/`.
2. Copies [`assets/icon.png`](assets/icon.png) to `~/.local/share/icons/hicolor/256x256/apps/attackshark-r6.png` and creates `~/.local/share/applications/attackshark-r6.desktop`.
3. Installs [`60-attackshark-r6.rules`](60-attackshark-r6.rules) to `/etc/udev/rules.d/60-attackshark-r6.rules` (using `sudo` or `pkexec`) and reloads `udevadm` so your desktop user gets read/write access to `/dev/hidraw*` without unplugging or running the GUI as root.

> [!TIP]
> Alternatively, you can run `./attackshark-r6` directly before installing udev rules and click **"Install USB Permissions (pkexec)"** on the warning banner or inside the **Settings** tab.

### Uninstall

```bash
./uninstall.sh
```

Pass `--remove-udev` to also remove `/etc/udev/rules.d/60-attackshark-r6.rules`:
```bash
./uninstall.sh --remove-udev
```

---

## Desktop GUI Overview

Launch from your application menu (**ATTACK SHARK R6**) or run:
```bash
attackshark-r6            # Normal startup
attackshark-r6 --minimized  # Start directly in 0-resource tray idle mode
```

The GUI features 5 tabs:

1. **Key Binding**: Interactive mouse diagram with callout markers (`1–7`) alongside remap buttons for all 7 hardware controls (`Left`, `Right`, `Middle`, `Backward`, `Forward`, `Scroll Up`, `Scroll Down`) and modal binding dialog supporting mouse clicks, double/X-clicks, keyboard captures + modifiers, multimedia/power keys, DPI actions (including DPI Lock), profiles, battery check, macros, and Disable.
2. **Performance**: Up to 6 DPI stages (`50–42,000 DPI`), per-stage X/Y link toggle, active stage radio button, RGB color picker, Polling Rate selector, LOD radio buttons, Debounce slider/spinbox, Wireless Sleep Timeout slider + `Never`, and Motion Sync / Ripple Control / Angle Snapping checkboxes.
3. **Macro Editor**: List/load/delete onboard macros (`1–29`), live keyboard/mouse recorder pad (works natively on Wayland and X11), manual event & delay step editor, reorder/delete steps, and chunked flash uploader with progress bar.
4. **Device & Pairing**: Connected USB metadata (`VID:PID`, serial, `/dev/hidraw*` control & notify paths), 2.4G wireless receiver pairing wizard, JSON profile Export/Import, Reset Current Profile, Factory Reset, and live `MI01` event log.
5. **Settings**: Always enabled (even when the mouse is disconnected). Configure **Minimize to system tray when pressing X**, **Start minimized to system tray**, trigger **Minimize to Tray Now**, **Quit Application (`Ctrl+Q`)**, view config file path, or reinstall `udev` rules.

---

## CLI Reference

Every hardware setting can also be scripted headless via `attackshark-r6-cli` (`~/.local/bin/attackshark-r6-cli`).

Global options (placed before the subcommand):
- `-d PATH`, `--device PATH`: Target a specific control device (e.g., `/dev/hidraw4`)
- `--debug`: Print raw TX/RX 65-byte HID feature frames

| Command | Description & Examples |
| :--- | :--- |
| `devices [--json]` | List detected ATTACK SHARK R6 devices and `/dev/hidraw*` permission status.<br>`attackshark-r6-cli devices` |
| `status [--profile N] [--json]` | Read complete onboard state (FW versions, battery, DPI stages, colors, polling, LOD, debounce, sleep, sensor tuning, all 7 buttons).<br>`attackshark-r6-cli status` |
| `probe` | Send diagnostic feature reads (`GetBattery`, `GetDeviceFW`, `GetProfileID`) and print raw kernel `HIDIOCGFEATURE` lengths/hex frames. |
| `monitor` | Stream live `MI01` interrupt notifications (`dpi_changed`, `wake`, `sleep`, `lod_changed`, `polling_changed`). |
| `set-profile <1\|2\|3>` | Switch the active onboard profile.<br>`attackshark-r6-cli set-profile 2` |
| `set-dpi <STAGES...> [--profile N]` | Set 1–6 DPI stages (`50..42000`, symmetric or `XxY`).<br>`attackshark-r6-cli set-dpi 800 1600 3200x2800` |
| `set-active-dpi <1..6> [--profile N]` | Select the active DPI stage.<br>`attackshark-r6-cli set-active-dpi 2` |
| `set-dpi-colors <HEX...> [--profile N]` | Set up to 6 DPI stage RGB hex colors.<br>`attackshark-r6-cli set-dpi-colors #FF0000 #00FF88 #0088FF` |
| `set-polling <HZ> [--profile N]` | Set polling rate (`125`, `250`, `500`, `1000`, and `2000`/`4000`/`8000` in 2.4G mode).<br>`attackshark-r6-cli set-polling 4000` |
| `set-lod <0.7mm\|1mm\|2mm> [--profile N]` | Set Lift-Off Distance (`0.7mm`, `1mm`, `2mm`, or `0.7`/`1`/`2`).<br>`attackshark-r6-cli set-lod 0.7mm` |
| `set-debounce <MS> [--profile N]` | Set debounce time (`0..15` ms).<br>`attackshark-r6-cli set-debounce 2` |
| `set-sleep <SEC\|off> [--profile N]` | Set wireless sleep timeout (`15..1800` seconds, or `off`/`never`/`disable`).<br>`attackshark-r6-cli set-sleep 180` |
| `set-sensor [...] [--profile N]` | Toggle `--motion-sync`, `--ripple`, and/or `--angle-snap` (`on`/`off`).<br>`attackshark-r6-cli set-sensor --motion-sync on --ripple off --angle-snap off` |
| `buttons [--profile N]` | Print all 7 configurable button assignments. |
| `set-button <BTN> <ACTION> [EXTRA...] [--profile N]` | Remap a button (`left`, `right`, `middle`, `backward`, `forward`, `scrollup`, `scrolldown`, `dpi`) to an action (`off`, `mouse`, `double-click`, `xclick`, `key`, `media`, `power`, `dpi-up`, `dpi-down`, `dpi-cycle-up`, `dpi-cycle-down`, `dpi-lock`, `profile-up`, `profile-down`, `battery`, `macro1`, `macro2`, `macro3`).<br>`attackshark-r6-cli set-button forward key LCtrl+C`<br>`attackshark-r6-cli set-button backward dpi-lock 800`<br>`attackshark-r6-cli set-button middle macro1 5 1` |
| `macros list` | Scan onboard macro slots `1..29` and show byte sizes. |
| `macros get <ID>` | Decode and print macro step sequence for slot `ID`. |
| `macros delete <ID>` | Erase onboard macro slot `ID`. |
| `pair [--timeout SEC]` | Put the 2.4G receiver into pairing mode (default timeout: `20`s). |
| `reset [--profile N] [--factory]` | Reset a profile (`--profile`) or full factory reset (`--factory`). |

---

## Architecture & USB HID Protocol Overview

```text
attackshark-r6-linux/
├── attackshark_r6/
│   ├── constants.py       # USB VID/PIDs, NewProtocol=1 enums, HID usages, 7-button map
│   ├── hid_transport.py   # /sys/class/hidraw discovery, HIDIOCSFEATURE/HIDIOCGFEATURE, MI01 listener
│   ├── protocol.py        # R6Protocol packet codec, RLock transaction serialization, MouseState
│   ├── macros.py          # Onboard macro binary encoder/decoder (keys, mouse, wheel, XY, delays)
│   ├── settings.py        # XDG atomic JSON settings persistence (~/.config/attackshark-r6/settings.json)
│   ├── cli.py             # Argparse CLI frontend
│   └── gui.py             # PyQt5 Control Center + zero-resource system tray idle mode
├── assets/                # Original GPL-3.0 matte-white studio PNG renders & pairing icon
├── tests/
│   ├── test_protocol.py   # Protocol frame, macro codec, hidraw normalization, RLock & settings tests
│   └── test_gui_tray.py   # Offscreen PyQt5 Settings & tray suspend/resume tests
├── 60-attackshark-r6.rules
├── install.sh / uninstall.sh
└── .github/workflows/ci-release.yml
```

Key Linux protocol notes implemented from reverse-engineering the stock `DriverCore.exe` (`NewProtocol=1`) protocol:
- **65-byte Feature Reports & Linux `hidraw` Normalization**: Commands are 65-byte zero-report-ID frames (`buf[3]=target` (`0x00` Dongle, `0x01` Dongle Ctrl, `0x02` Mouse), `buf[4]=length`, `buf[5]=group`, `buf[6]=cmd`, `buf[7:]=payload`). Because Linux `HIDIOCGFEATURE(65)` can return either 64-byte unnumbered payloads or 65-byte `[0x00, A1, ...]` buffers depending on driver/kernel behavior, `normalize_feature_response()` aligns both into canonical 65-byte frames.
- **`0xA1` Status & Retry Loop + Thread Serialization**: Firmware responds with `resp[1] == 0xA1` (`STATUS_OK`) or busy `< 0xA1` requiring retry reads. All full transactions (`set_feature` → `wait_sec` → `get_feature` + retries) are serialized under `R6Protocol._tx_lock` (`threading.RLock`) so background polling never interleaves between another command's write and read.
- **Polling Rate `0x10` Alias**: Reads of `get_polling_rate()` map both `0x08` and firmware `0x10` cleanly to `1000 Hz`.
- **`60-attackshark-r6.rules` Priority**: Ordered at priority **`60`**, strictly before systemd's `/usr/lib/udev/rules.d/73-seat-late.rules` which processes `TAG+="uaccess"` ACL grants at **`73`** (`99-*` rules run too late for `uaccess`).

---

## Troubleshooting

- **"Your user lacks /dev/hidraw read/write permission" banner**:
  Run `./install.sh` (or click **Install USB Permissions (pkexec)** in the GUI) to install `/etc/udev/rules.d/60-attackshark-r6.rules`. Verify your user ACL with:
  ```bash
  getfacl /dev/hidraw*
  ```
- **Missing system tray icon / pressing X exits instead of minimizing**:
  Ensure your desktop session provides a StatusNotifier / System Tray widget (standard in KDE Plasma, GNOME + AppIndicator extension, XFCE, etc.). In the **Settings** tab, **System tray status** tells you whether Qt detected an active tray.
- **Dongle connected (`373e:0022`) while wireless mouse is asleep**:
  Wake the mouse by moving or clicking it, then click **Refresh** in the top bar (or wake events over `MI01` will automatically trigger a sync).
- **Inspecting raw USB frames**:
  ```bash
  attackshark-r6-cli --debug status
  attackshark-r6-cli probe
  ```

---

## Development & Testing

Run syntax checks and all unit/GUI tests locally (works headless via `QT_QPA_PLATFORM=offscreen`):

```bash
python3 -m py_compile attackshark_r6/*.py tests/*.py
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
bash -n install.sh uninstall.sh
```

Note: GUI tray lifecycle tests in [`tests/test_gui_tray.py`](tests/test_gui_tray.py) mock device discovery and use a temporary `settings.json`, so running the test suite **never** alters your live mouse settings or `~/.config/attackshark-r6/settings.json`.

---

## Contributors

- **[@Zyd93](https://github.com/Zyd93)** — Project Creator & Maintainer
- **Antigravity (Google DeepMind)** — Agentic AI Contributor

---

## License

Licensed under the **GNU General Public License v3.0** ([LICENSE](LICENSE)).

*ATTACK SHARK is a trademark of its respective owner. This project is an independent open-source Linux community implementation and contains zero proprietary binaries or vendor artwork.*
