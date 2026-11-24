"""Native PyQt5 Linux desktop application for the ATTACK SHARK R6 mouse."""

from __future__ import annotations

import argparse
import ctypes
import gc
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from PyQt5.QtCore import (
    QObject,
    QSize,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QFont,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPixmap,
    QWheelEvent,
)
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QShortcut,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .constants import (
    BUTTON_LABELS,
    CONFIGURABLE_BUTTONS,
    CONSUMER_KEY_LABELS,
    DEBOUNCE_MAX_MS,
    DEBOUNCE_MIN_MS,
    DEFAULT_DPI_COLORS,
    DPI_ACTION_LABELS,
    DPI_MAX,
    DPI_MAX_STAGES,
    DPI_MIN,
    DPI_STEP,
    HID_KEY_TO_NAME,
    LOD_CODE_TO_NAME,
    MACRO_CHUNK_SIZE,
    MACRO_MAX_ID,
    MACRO_MIN_ID,
    MODIFIER_NAMES,
    POWER_KEY_LABELS,
    PROFILE_ACTION_LABELS,
    PROFILE_MAX,
    PROFILE_MIN,
    SLEEP_DISABLED,
    SLEEP_MAX_SEC,
    SLEEP_MIN_SEC,
    WIRED_POLLING_RATES,
    WIRELESS_POLLING_RATES,
    ButtonID,
    DPIAction,
    FunctionID,
    Modifier,
    ProfileAction,
    hid_key_name,
    qt_event_to_hid,
)
from . import __version__
from .hid_transport import (
    HidrawTransport,
    NotificationListener,
    R6DeviceInfo,
    discover_devices,
)
from .macros import MacroStep, decode_macro, encode_macro
from .protocol import ButtonBinding, DPIStage, MouseState, R6Protocol
from .settings import AppSettings, default_settings_path, load_settings, save_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
UDEV_RULE_SOURCE = PROJECT_ROOT / "60-attackshark-r6.rules"
UDEV_RULE_TARGET = Path("/etc/udev/rules.d/60-attackshark-r6.rules")

STYLESHEET = """
QMainWindow, QDialog {
    background-color: #161d20;
    color: #e6eff2;
    font-family: "Noto Sans", "Segoe UI", sans-serif;
    font-size: 10pt;
}
QWidget {
    color: #e6eff2;
}
QFrame#HeaderBar {
    background-color: #1e282c;
    border-bottom: 1px solid #2e3e44;
}
QFrame#PermBanner {
    background-color: #3a2a14;
    border: 1px solid #c98627;
    border-radius: 6px;
}
QFrame#Card, QGroupBox {
    background-color: #1e282c;
    border: 1px solid #2e3e44;
    border-radius: 8px;
}
QGroupBox {
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #5cd4ef;
}
QTabWidget::pane {
    border: 1px solid #2e3e44;
    background-color: #161d20;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: #1e282c;
    color: #9cb2ba;
    padding: 9px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #2e3e44;
    border-bottom: none;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #253235;
    color: #5cd4ef;
    border-color: #3d555e;
}
QTabBar::tab:hover:!selected {
    background-color: #222e33;
    color: #d6e4e8;
}
QPushButton {
    background-color: #253235;
    border: 1px solid #394d54;
    border-radius: 5px;
    padding: 6px 12px;
    color: #e6eff2;
}
QPushButton:hover {
    background-color: #2f4045;
    border-color: #5cd4ef;
}
QPushButton:pressed {
    background-color: #1c2629;
}
QPushButton:checked {
    background-color: #0b6980;
    border-color: #5cd4ef;
    color: #ffffff;
    font-weight: bold;
}
QPushButton:disabled {
    background-color: #1a2225;
    color: #63767d;
    border-color: #263236;
}
QPushButton#PrimaryBtn {
    background-color: #0d7c96;
    border-color: #2cb4d4;
    font-weight: bold;
}
QPushButton#PrimaryBtn:hover {
    background-color: #1094b3;
}
QPushButton#DangerBtn {
    background-color: #6b2323;
    border-color: #a83c3c;
}
QPushButton#DangerBtn:hover {
    background-color: #872e2e;
}
QComboBox, QSpinBox, QListWidget, QPlainTextEdit {
    background-color: #13191b;
    border: 1px solid #34474d;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e6eff2;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #1e282c;
    color: #e6eff2;
    selection-background-color: #0d7c96;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #2c3b40;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #5cd4ef;
    border: 1px solid #0b6980;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}
QSlider::sub-page:horizontal {
    background: #0d7c96;
    border-radius: 3px;
}
QProgressBar {
    background-color: #13191b;
    border: 1px solid #34474d;
    border-radius: 4px;
    text-align: center;
    height: 18px;
}
QProgressBar::chunk {
    background-color: #0d7c96;
}
QLabel#StatusPill {
    padding: 4px 10px;
    border-radius: 10px;
    font-weight: bold;
    font-size: 9pt;
}
"""


def _asset_pixmap(filename: str) -> QPixmap:
    path = ASSETS_DIR / filename
    if path.exists():
        return QPixmap(str(path))
    return QPixmap()


def _app_icon() -> QIcon:
    for name in ("icon.png", "icon.svg"):
        path = ASSETS_DIR / name
        if path.exists():
            return QIcon(str(path))
    return QIcon()


def _trim_process_memory() -> None:
    """Collect Python garbage and ask glibc to release free heap pages."""
    gc.collect()
    try:
        libc = ctypes.CDLL("libc.so.6")
        if hasattr(libc, "malloc_trim"):
            libc.malloc_trim(0)
    except Exception:
        pass


class TaskWorker(QThread):
    """Generic background QThread worker for non-blocking HID operations."""

    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(
        self,
        fn: Callable[[Callable[[int], None]], object],
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            res = self._fn(self.progress.emit)
            self.succeeded.emit(res)
        except Exception as exc:
            self.failed.emit(str(exc))


class KeyCaptureButton(QPushButton):
    """Button that captures a single USB HID keyboard key press when toggled."""

    key_captured = pyqtSignal(int)

    def __init__(self, initial_hid: int = 0x04, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.hid_code = initial_hid
        self.setCheckable(True)
        self._update_label()
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        if checked:
            self.setText("Press any key... (Esc to cancel)")
            self.setFocus()
        else:
            self._update_label()

    def _update_label(self) -> None:
        self.setText(f"Captured Key: {hid_key_name(self.hid_code)} (0x{self.hid_code:02X})")

    def set_hid_code(self, code: int) -> None:
        self.hid_code = code
        self.setChecked(False)
        self._update_label()

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:
        if event is None or not self.isChecked():
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key_Escape:
            # Allow Esc binding if double-tapped or fallback via combo; first Esc cancels capture
            self.setChecked(False)
            event.accept()
            return
        hid = qt_event_to_hid(event.key(), event.nativeScanCode())
        if hid is not None:
            self.hid_code = hid
            self.setChecked(False)
            self.key_captured.emit(hid)
        event.accept()


class ButtonBindDialog(QDialog):
    """Modal editor dialog for configuring a single mouse button binding."""

    def __init__(
        self,
        button_id: ButtonID,
        current: ButtonBinding,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.button_id = button_id
        self.setWindowTitle(f"Assign {BUTTON_LABELS.get(button_id, button_id.name)}")
        self.setMinimumWidth(470)

        root = QVBoxLayout(self)
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("Function Type:"))
        self.cat_combo = QComboBox()
        self.categories = [
            "Mouse Button",
            "Double / X-Click",
            "Keyboard Key / Combo",
            "DPI Control",
            "Profile Switch",
            "Multimedia / Shortcuts",
            "System Power / Battery",
            "Macro",
            "Disable",
        ]
        self.cat_combo.addItems(self.categories)
        cat_row.addWidget(self.cat_combo, 1)
        root.addLayout(cat_row)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        # 0: Mouse Button
        w_mouse = QWidget()
        f_mouse = QFormLayout(w_mouse)
        self.mouse_combo = QComboBox()
        for bid in [
            ButtonID.LEFT,
            ButtonID.RIGHT,
            ButtonID.MIDDLE,
            ButtonID.BACKWARD,
            ButtonID.FORWARD,
            ButtonID.SCROLL_UP,
            ButtonID.SCROLL_DOWN,
        ]:
            self.mouse_combo.addItem(BUTTON_LABELS[bid], int(bid))
        f_mouse.addRow("Target Mouse Action:", self.mouse_combo)
        self.stack.addWidget(w_mouse)

        # 1: Double / X-Click
        w_xclick = QWidget()
        f_xclick = QFormLayout(w_xclick)
        self.xclick_btn = QComboBox()
        for bid in [ButtonID.LEFT, ButtonID.RIGHT, ButtonID.MIDDLE, ButtonID.BACKWARD, ButtonID.FORWARD]:
            self.xclick_btn.addItem(BUTTON_LABELS[bid], int(bid))
        self.xclick_count = QSpinBox()
        self.xclick_count.setRange(2, 50)
        self.xclick_count.setValue(2)
        self.xclick_interval = QSpinBox()
        self.xclick_interval.setRange(10, 2000)
        self.xclick_interval.setValue(100)
        self.xclick_interval.setSuffix(" ms")
        f_xclick.addRow("Button:", self.xclick_btn)
        f_xclick.addRow("Repeat Count:", self.xclick_count)
        f_xclick.addRow("Interval:", self.xclick_interval)
        self.stack.addWidget(w_xclick)

        # 2: Keyboard Key / Combo
        w_key = QWidget()
        v_key = QVBoxLayout(w_key)
        self.key_capture = KeyCaptureButton(0x04)
        v_key.addWidget(self.key_capture)
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("Or Select Key:"))
        self.key_combo = QComboBox()
        for code, name in sorted(HID_KEY_TO_NAME.items()):
            if code < 0xE0:
                self.key_combo.addItem(f"{name} (0x{code:02X})", code)
        self.key_combo.currentIndexChanged.connect(self._on_key_combo_changed)
        self.key_capture.key_captured.connect(self._on_key_captured)
        key_row.addWidget(self.key_combo, 1)
        v_key.addLayout(key_row)

        mod_box = QGroupBox("Modifiers")
        mod_grid = QGridLayout(mod_box)
        self.mod_checks: Dict[Modifier, QCheckBox] = {}
        for idx, (bit, label) in enumerate(MODIFIER_NAMES):
            cb = QCheckBox(label)
            self.mod_checks[bit] = cb
            mod_grid.addWidget(cb, idx // 4, idx % 4)
        v_key.addWidget(mod_box)
        self.stack.addWidget(w_key)

        # 3: DPI Control
        w_dpi = QWidget()
        f_dpi = QFormLayout(w_dpi)
        self.dpi_act_combo = QComboBox()
        for act, lbl in DPI_ACTION_LABELS.items():
            self.dpi_act_combo.addItem(lbl, int(act))
        self.dpi_lock_spin = QSpinBox()
        self.dpi_lock_spin.setRange(DPI_MIN, DPI_MAX)
        self.dpi_lock_spin.setSingleStep(DPI_STEP)
        self.dpi_lock_spin.setValue(800)
        self.dpi_act_combo.currentIndexChanged.connect(self._update_dpi_lock_vis)
        f_dpi.addRow("DPI Action:", self.dpi_act_combo)
        f_dpi.addRow("DPI Lock Target:", self.dpi_lock_spin)
        self.stack.addWidget(w_dpi)

        # 4: Profile Switch
        w_prof = QWidget()
        f_prof = QFormLayout(w_prof)
        self.prof_act_combo = QComboBox()
        for act, lbl in PROFILE_ACTION_LABELS.items():
            self.prof_act_combo.addItem(lbl, int(act))
        f_prof.addRow("Profile Action:", self.prof_act_combo)
        self.stack.addWidget(w_prof)

        # 5: Multimedia / Shortcuts
        w_media = QWidget()
        f_media = QFormLayout(w_media)
        self.media_combo = QComboBox()
        for usage, lbl in CONSUMER_KEY_LABELS.items():
            self.media_combo.addItem(lbl, int(usage))
        f_media.addRow("Action:", self.media_combo)
        self.stack.addWidget(w_media)

        # 6: System Power / Battery
        w_pow = QWidget()
        f_pow = QFormLayout(w_pow)
        self.pow_combo = QComboBox()
        self.pow_combo.addItem("Battery Level Indicator", ("bat", 1))
        for pk, lbl in POWER_KEY_LABELS.items():
            self.pow_combo.addItem(lbl, ("power", int(pk)))
        f_pow.addRow("System Action:", self.pow_combo)
        self.stack.addWidget(w_pow)

        # 7: Macro
        w_mac = QWidget()
        f_mac = QFormLayout(w_mac)
        self.macro_id_spin = QSpinBox()
        self.macro_id_spin.setRange(MACRO_MIN_ID, MACRO_MAX_ID)
        self.macro_mode_combo = QComboBox()
        self.macro_mode_combo.addItem("Run N times (Macro I)", int(FunctionID.MACRO_I))
        self.macro_mode_combo.addItem("Repeat while held (Macro II)", int(FunctionID.MACRO_II))
        self.macro_mode_combo.addItem("Toggle repeat on press (Macro III)", int(FunctionID.MACRO_III))
        self.macro_rep_spin = QSpinBox()
        self.macro_rep_spin.setRange(1, 255)
        self.macro_rep_spin.setValue(1)
        self.macro_mode_combo.currentIndexChanged.connect(
            lambda: self.macro_rep_spin.setEnabled(
                self.macro_mode_combo.currentData() == int(FunctionID.MACRO_I)
            )
        )
        f_mac.addRow("Macro ID (1..29):", self.macro_id_spin)
        f_mac.addRow("Execution Mode:", self.macro_mode_combo)
        f_mac.addRow("Repeat Count:", self.macro_rep_spin)
        self.stack.addWidget(w_mac)

        # 8: Disable
        w_off = QWidget()
        v_off = QVBoxLayout(w_off)
        v_off.addWidget(QLabel("This button will emit no action (Disabled)."))
        self.stack.addWidget(w_off)

        self.cat_combo.currentIndexChanged.connect(self.stack.setCurrentIndex)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._load_binding(current)
        self._update_dpi_lock_vis()

    def _update_dpi_lock_vis(self) -> None:
        is_lock = self.dpi_act_combo.currentData() == int(DPIAction.STAGE_LOCK)
        self.dpi_lock_spin.setEnabled(is_lock)

    def _on_key_combo_changed(self) -> None:
        code = self.key_combo.currentData()
        if code is not None:
            self.key_capture.set_hid_code(int(code))

    def _on_key_captured(self, code: int) -> None:
        idx = self.key_combo.findData(code)
        if idx >= 0:
            self.key_combo.blockSignals(True)
            self.key_combo.setCurrentIndex(idx)
            self.key_combo.blockSignals(False)

    def _load_binding(self, b: ButtonBinding) -> None:
        fid = b.function_id
        d = b.data
        if fid == FunctionID.BUTTON_CODE and len(d) >= 1:
            self.cat_combo.setCurrentIndex(0)
            idx = self.mouse_combo.findData(d[0])
            if idx >= 0:
                self.mouse_combo.setCurrentIndex(idx)
        elif fid == FunctionID.X_CLICK and len(d) >= 5:
            self.cat_combo.setCurrentIndex(1)
            idx = self.xclick_btn.findData(d[1])
            if idx >= 0:
                self.xclick_btn.setCurrentIndex(idx)
            self.xclick_count.setValue(max(2, d[2]))
            self.xclick_interval.setValue(max(10, (d[3] << 8) | d[4]))
        elif fid == FunctionID.KEYBOARD_CODE and len(d) >= 2:
            self.cat_combo.setCurrentIndex(2)
            for bit, cb in self.mod_checks.items():
                cb.setChecked(bool(d[0] & bit))
            self.key_capture.set_hid_code(d[1])
            self._on_key_captured(d[1])
        elif fid == FunctionID.DPI and len(d) >= 1:
            self.cat_combo.setCurrentIndex(3)
            idx = self.dpi_act_combo.findData(d[0])
            if idx >= 0:
                self.dpi_act_combo.setCurrentIndex(idx)
            if d[0] == DPIAction.STAGE_LOCK and len(d) >= 3:
                self.dpi_lock_spin.setValue((d[1] << 8) | d[2])
        elif fid == FunctionID.PROFILE and len(d) >= 1:
            self.cat_combo.setCurrentIndex(4)
            idx = self.prof_act_combo.findData(d[0])
            if idx >= 0:
                self.prof_act_combo.setCurrentIndex(idx)
        elif fid == FunctionID.CONSUMER_KEYS and len(d) >= 2:
            self.cat_combo.setCurrentIndex(5)
            idx = self.media_combo.findData((d[0] << 8) | d[1])
            if idx >= 0:
                self.media_combo.setCurrentIndex(idx)
        elif fid == FunctionID.BAT_BUTTON:
            self.cat_combo.setCurrentIndex(6)
            self.pow_combo.setCurrentIndex(0)
        elif fid == FunctionID.POWER_KEYS and len(d) >= 1:
            self.cat_combo.setCurrentIndex(6)
            idx = self.pow_combo.findData(("power", d[0]))
            if idx >= 0:
                self.pow_combo.setCurrentIndex(idx)
        elif fid in (FunctionID.MACRO_I, FunctionID.MACRO_II, FunctionID.MACRO_III) and len(d) >= 2:
            self.cat_combo.setCurrentIndex(7)
            self.macro_id_spin.setValue(max(MACRO_MIN_ID, min(MACRO_MAX_ID, (d[0] << 8) | d[1])))
            idx = self.macro_mode_combo.findData(int(fid))
            if idx >= 0:
                self.macro_mode_combo.setCurrentIndex(idx)
            if fid == FunctionID.MACRO_I and len(d) >= 3:
                self.macro_rep_spin.setValue(max(1, d[2]))
        elif fid == FunctionID.OFF:
            self.cat_combo.setCurrentIndex(8)

    def build_binding(self) -> ButtonBinding:
        cat = self.cat_combo.currentIndex()
        if cat == 0:
            return ButtonBinding.mouse_button(ButtonID(self.mouse_combo.currentData()))
        if cat == 1:
            return ButtonBinding.double_click(
                btn=ButtonID(self.xclick_btn.currentData()),
                clicks=self.xclick_count.value(),
                interval_ms=self.xclick_interval.value(),
            )
        if cat == 2:
            mods = 0
            for bit, cb in self.mod_checks.items():
                if cb.isChecked():
                    mods |= int(bit)
            return ButtonBinding.keyboard(mods, self.key_capture.hid_code)
        if cat == 3:
            act = DPIAction(self.dpi_act_combo.currentData())
            return ButtonBinding.dpi_action(act, lock_dpi=self.dpi_lock_spin.value())
        if cat == 4:
            return ButtonBinding.profile_action(ProfileAction(self.prof_act_combo.currentData()))
        if cat == 5:
            return ButtonBinding.consumer(int(self.media_combo.currentData()))
        if cat == 6:
            kind, val = self.pow_combo.currentData()
            if kind == "bat":
                return ButtonBinding.battery_indicator()
            return ButtonBinding.power(int(val))
        if cat == 7:
            mid = self.macro_id_spin.value()
            mode = FunctionID(self.macro_mode_combo.currentData())
            if mode == FunctionID.MACRO_I:
                return ButtonBinding.macro_repeat(mid, self.macro_rep_spin.value())
            if mode == FunctionID.MACRO_II:
                return ButtonBinding.macro_hold(mid)
            return ButtonBinding.macro_toggle(mid)
        return ButtonBinding.off()


class MacroCapturePad(QFrame):
    """Wayland-safe local capture pad for recording keys, mouse clicks, and wheel events."""

    step_recorded = pyqtSignal(object)  # MacroStep

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumHeight(76)
        self.setFocusPolicy(Qt.StrongFocus)
        self.recording = False
        self.delay_mode = "record"  # record | default | none
        self.default_delay_ms = 50
        self._last_ts: Optional[float] = None
        self._pressed_keys: set[int] = set()

        lay = QVBoxLayout(self)
        self.label = QLabel(
            "Click 'Start Recording' and press keys/mouse inside this pad.\n"
            "(Wayland blocks global hooks safely, so events inside this box are captured.)"
        )
        self.label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.label)
        self._update_style()

    def _update_style(self) -> None:
        if self.recording:
            self.setStyleSheet(
                "MacroCapturePad { background-color: #2b1d1f; border: 2px solid #e05252; border-radius: 6px; }"
            )
            self.label.setText("RECORDING — Type keys, click mouse buttons, or scroll here...")
        else:
            self.setStyleSheet(
                "MacroCapturePad { background-color: #13191b; border: 1px dashed #3d555e; border-radius: 6px; }"
            )
            self.label.setText(
                "Macro Capture Pad (Idle) — Click 'Start Recording' to record keystrokes & mouse events."
            )

    def set_recording(self, active: bool, delay_mode: str, default_delay_ms: int) -> None:
        self.recording = active
        self.delay_mode = delay_mode
        self.default_delay_ms = default_delay_ms
        self._last_ts = time.monotonic() if active else None
        self._pressed_keys.clear()
        self._update_style()
        if active:
            self.setFocus()

    def _emit_delay(self) -> None:
        now = time.monotonic()
        if self.delay_mode == "none":
            self._last_ts = now
            return
        if self.delay_mode == "default":
            if self.default_delay_ms > 0:
                self.step_recorded.emit(MacroStep(kind="delay", delay_ms=self.default_delay_ms))
            self._last_ts = now
            return
        if self._last_ts is not None:
            ms = int(round((now - self._last_ts) * 1000))
            if ms >= 1:
                self.step_recorded.emit(MacroStep(kind="delay", delay_ms=ms))
        self._last_ts = now

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:
        if event is None or not self.recording:
            super().keyPressEvent(event)
            return
        if event.isAutoRepeat():
            event.accept()
            return
        hid = qt_event_to_hid(event.key(), event.nativeScanCode())
        if hid is not None:
            self._pressed_keys.add(hid)
            self._emit_delay()
            self.step_recorded.emit(MacroStep(kind="key_down", code=hid))
        event.accept()

    def keyReleaseEvent(self, event: Optional[QKeyEvent]) -> None:
        if event is None or not self.recording:
            super().keyReleaseEvent(event)
            return
        if event.isAutoRepeat():
            event.accept()
            return
        hid = qt_event_to_hid(event.key(), event.nativeScanCode())
        if hid is not None and hid in self._pressed_keys:
            self._pressed_keys.discard(hid)
            self._emit_delay()
            self.step_recorded.emit(MacroStep(kind="key_up", code=hid))
        event.accept()

    def _qt_btn_to_id(self, btn: int) -> Optional[ButtonID]:
        if btn == Qt.LeftButton:
            return ButtonID.LEFT
        if btn == Qt.RightButton:
            return ButtonID.RIGHT
        if btn == Qt.MiddleButton:
            return ButtonID.MIDDLE
        if btn == Qt.BackButton:
            return ButtonID.BACKWARD
        if btn == Qt.ForwardButton:
            return ButtonID.FORWARD
        return None

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        if event is None or not self.recording:
            super().mousePressEvent(event)
            return
        bid = self._qt_btn_to_id(int(event.button()))
        if bid is not None:
            self._emit_delay()
            self.step_recorded.emit(MacroStep(kind="mouse_down", code=int(bid)))
        event.accept()

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        if event is None or not self.recording:
            super().mouseReleaseEvent(event)
            return
        bid = self._qt_btn_to_id(int(event.button()))
        if bid is not None:
            self._emit_delay()
            self.step_recorded.emit(MacroStep(kind="mouse_up", code=int(bid)))
        event.accept()

    def wheelEvent(self, event: Optional[QWheelEvent]) -> None:
        if event is None or not self.recording:
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        if delta != 0:
            self._emit_delay()
            self.step_recorded.emit(MacroStep(kind="wheel", code=1 if delta > 0 else -1))
        event.accept()


class DpiStageRow(QWidget):
    """Single DPI stage row with enable checkbox, active radio, DPI slider/spin, Y link, color."""

    changed = pyqtSignal()
    activated = pyqtSignal(int)

    def __init__(self, index_1based: int, radio_group: QButtonGroup, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.stage_index = index_1based
        r, g, b = DEFAULT_DPI_COLORS[index_1based - 1]
        self.color: Tuple[int, int, int] = (r, g, b)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)

        self.enable_cb = QCheckBox(f"Stage {index_1based}")
        self.enable_cb.setChecked(True)
        self.enable_cb.toggled.connect(self._on_enable_toggled)
        lay.addWidget(self.enable_cb)

        self.active_radio = QRadioButton("Active")
        radio_group.addButton(self.active_radio, index_1based)
        self.active_radio.clicked.connect(lambda: self.activated.emit(self.stage_index))
        lay.addWidget(self.active_radio)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(DPI_MIN // DPI_STEP, DPI_MAX // DPI_STEP)
        self.slider.setValue(800 // DPI_STEP)
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.slider.sliderReleased.connect(self.changed.emit)
        lay.addWidget(self.slider, 1)

        self.spin_x = QSpinBox()
        self.spin_x.setRange(DPI_MIN, DPI_MAX)
        self.spin_x.setSingleStep(DPI_STEP)
        self.spin_x.setValue(800)
        self.spin_x.setMinimumWidth(82)
        self.spin_x.valueChanged.connect(self._on_spin_x_changed)
        self.spin_x.editingFinished.connect(self.changed.emit)
        lay.addWidget(self.spin_x)

        self.link_cb = QCheckBox("X=Y")
        self.link_cb.setChecked(True)
        self.link_cb.toggled.connect(self._on_link_toggled)
        lay.addWidget(self.link_cb)

        self.spin_y = QSpinBox()
        self.spin_y.setRange(DPI_MIN, DPI_MAX)
        self.spin_y.setSingleStep(DPI_STEP)
        self.spin_y.setValue(800)
        self.spin_y.setMinimumWidth(82)
        self.spin_y.setVisible(False)
        self.spin_y.editingFinished.connect(self.changed.emit)
        lay.addWidget(self.spin_y)

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(30, 26)
        self.color_btn.setToolTip("Stage LED Color")
        self.color_btn.clicked.connect(self._pick_color)
        lay.addWidget(self.color_btn)
        self._apply_color_style()

    def _apply_color_style(self) -> None:
        r, g, b = self.color
        self.color_btn.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); border: 2px solid #496069; border-radius: 4px;"
        )

    def _on_enable_toggled(self, checked: bool) -> None:
        self.active_radio.setEnabled(checked)
        self.slider.setEnabled(checked)
        self.spin_x.setEnabled(checked)
        self.link_cb.setEnabled(checked)
        self.spin_y.setEnabled(checked)
        self.color_btn.setEnabled(checked)
        self.changed.emit()

    def _on_slider_changed(self, step_val: int) -> None:
        dpi = step_val * DPI_STEP
        self.spin_x.blockSignals(True)
        self.spin_x.setValue(dpi)
        self.spin_x.blockSignals(False)
        if self.link_cb.isChecked():
            self.spin_y.blockSignals(True)
            self.spin_y.setValue(dpi)
            self.spin_y.blockSignals(False)

    def _on_spin_x_changed(self, dpi: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(max(1, dpi // DPI_STEP))
        self.slider.blockSignals(False)
        if self.link_cb.isChecked():
            self.spin_y.blockSignals(True)
            self.spin_y.setValue(dpi)
            self.spin_y.blockSignals(False)

    def _on_link_toggled(self, linked: bool) -> None:
        self.spin_y.setVisible(not linked)
        if linked:
            self.spin_y.setValue(self.spin_x.value())
        self.changed.emit()

    def _pick_color(self) -> None:
        r, g, b = self.color
        chosen = QColorDialog.getColor(QColor(r, g, b), self, f"Stage {self.stage_index} Color")
        if chosen.isValid():
            self.color = (chosen.red(), chosen.green(), chosen.blue())
            self._apply_color_style()
            self.changed.emit()

    def set_values(self, enabled: bool, active: bool, stage: DPIStage, color: Tuple[int, int, int]) -> None:
        for w in (self.enable_cb, self.active_radio, self.slider, self.spin_x, self.link_cb, self.spin_y):
            w.blockSignals(True)
        self.enable_cb.setChecked(enabled)
        self.active_radio.setChecked(active)
        self.active_radio.setEnabled(enabled)
        self.slider.setEnabled(enabled)
        self.spin_x.setEnabled(enabled)
        self.link_cb.setEnabled(enabled)
        self.spin_y.setEnabled(enabled)
        self.color_btn.setEnabled(enabled)

        self.spin_x.setValue(stage.x)
        self.spin_y.setValue(stage.y)
        self.slider.setValue(max(1, stage.x // DPI_STEP))
        linked = stage.x == stage.y
        self.link_cb.setChecked(linked)
        self.spin_y.setVisible(not linked)
        self.color = color
        self._apply_color_style()
        for w in (self.enable_cb, self.active_radio, self.slider, self.spin_x, self.link_cb, self.spin_y):
            w.blockSignals(False)

    def get_stage(self) -> DPIStage:
        x = self.spin_x.value()
        y = x if self.link_cb.isChecked() else self.spin_y.value()
        return DPIStage(x=x, y=y).normalized()


class MainWindow(QMainWindow):
    """Main window for ATTACK SHARK R6 Linux configurator."""

    notify_received = pyqtSignal(str, bytes)

    def __init__(
        self,
        settings_path: Optional[Path] = None,
        start_minimized: Optional[bool] = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("ATTACK SHARK R6 — Linux Control Center")
        self.setWindowIcon(_app_icon())
        self.resize(1040, 720)

        self._settings_path = settings_path
        self._settings: AppSettings = load_settings(settings_path)
        self.dev_info: Optional[R6DeviceInfo] = None
        self.transport: Optional[HidrawTransport] = None
        self.proto: Optional[R6Protocol] = None
        self.listener: Optional[NotificationListener] = None
        self.state: Optional[MouseState] = None
        self._workers: List[TaskWorker] = []
        self._closing = False
        self._suspended = False
        self._force_quit = False
        self._syncing_ui = False
        self._macro_steps: List[MacroStep] = []
        self._pair_timer: Optional[QTimer] = None
        self._pair_deadline = 0.0
        self._tray_icon: Optional[QSystemTrayIcon] = None
        self._ipc_server: Optional[QLocalServer] = None

        self.notify_received.connect(self._on_device_notification)

        self._build_ui()
        self._setup_tray()

        quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        quit_shortcut.activated.connect(self.quit_application)

        self.hotplug_timer = QTimer(self)
        self.hotplug_timer.setInterval(1500)
        self.hotplug_timer.timeout.connect(self._poll_hotplug)

        self.battery_timer = QTimer(self)
        self.battery_timer.setInterval(30000)
        self.battery_timer.timeout.connect(self._refresh_battery_only)

        want_min = (
            self._settings.start_minimized
            if start_minimized is None
            else start_minimized
        )
        if (
            want_min
            and self._tray_icon is not None
            and QSystemTrayIcon.isSystemTrayAvailable()
        ):
            self.enter_tray_idle()
        else:
            self.hotplug_timer.start()
            self.battery_timer.start()
            QTimer.singleShot(50, self._poll_hotplug)

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon = None
            return
        tray = QSystemTrayIcon(_app_icon(), self)
        tray.setToolTip("ATTACK SHARK R6 Control Center")
        menu = QMenu(self)
        open_act = QAction("Open ATTACK SHARK R6", menu)
        open_act.triggered.connect(self.wake_from_tray)
        menu.addAction(open_act)
        menu.addSeparator()
        quit_act = QAction("Quit", menu)
        quit_act.triggered.connect(self.quit_application)
        menu.addAction(quit_act)
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        self._tray_icon = tray

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.wake_from_tray()

    def enter_tray_idle(self) -> None:
        """Stop all timers/workers/hidraw handles and trim memory while hidden in tray."""
        self._suspended = True
        self.hotplug_timer.stop()
        self.battery_timer.stop()
        if self._pair_timer is not None:
            self._pair_timer.stop()
            self._pair_timer = None
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
        for w in list(self._workers):
            w.wait(3000)
        self._disconnect_device()
        _trim_process_memory()
        if self._tray_icon is not None:
            self._tray_icon.setToolTip(
                "ATTACK SHARK R6 — Idle (0% CPU) · Click to open"
            )
            self._tray_icon.show()
        self.hide()

    def wake_from_tray(self) -> None:
        """Restore window and resume hardware polling after tray idle."""
        if self._closing:
            return
        was_suspended = self._suspended
        self._suspended = False
        if self._tray_icon is not None:
            self._tray_icon.hide()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if was_suspended or not self.hotplug_timer.isActive():
            self.hotplug_timer.start()
            self.battery_timer.start()
            QTimer.singleShot(0, self._poll_hotplug)

    def quit_application(self) -> None:
        """Exit cleanly even when minimize-to-tray is enabled."""
        self._force_quit = True
        self.close()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if (
            not self._force_quit
            and self._settings.close_to_tray
            and self._tray_icon is not None
            and QSystemTrayIcon.isSystemTrayAvailable()
        ):
            event.ignore()
            self.enter_tray_idle()
            return

        self._closing = True
        self._suspended = True
        self.hotplug_timer.stop()
        self.battery_timer.stop()
        if self._pair_timer is not None:
            self._pair_timer.stop()
            self._pair_timer = None
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
        for w in list(self._workers):
            w.wait(3000)
        self._disconnect_device()
        if self._tray_icon is not None:
            self._tray_icon.hide()
        if self._ipc_server is not None:
            try:
                self._ipc_server.close()
            except Exception:
                pass
            self._ipc_server = None
        super().closeEvent(event)
        app = QApplication.instance()
        if app is not None:
            app.quit()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # Header Bar
        header = QFrame()
        header.setObjectName("HeaderBar")
        header.setFixedHeight(64)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 8, 16, 8)

        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(0, 0, 0, 0)
        logo_row.setSpacing(10)
        icon_lbl = QLabel()
        logo_pm = _asset_pixmap("icon.png")
        if not logo_pm.isNull():
            icon_lbl.setPixmap(
                logo_pm.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            logo_row.addWidget(icon_lbl)
        title_lbl = QLabel("ATTACK SHARK R6")
        title_lbl.setFont(QFont("sans-serif", 13, QFont.Bold))
        logo_row.addWidget(title_lbl)
        h_lay.addLayout(logo_row)

        self.status_pill = QLabel("Disconnected")
        self.status_pill.setObjectName("StatusPill")
        self._set_status_pill("Disconnected", "#5b2525", "#f2b8b8")
        h_lay.addWidget(self.status_pill)

        h_lay.addStretch(1)

        self.fw_label = QLabel("Mouse FW: --   Dongle FW: --")
        self.fw_label.setStyleSheet("color: #9cb2ba;")
        h_lay.addWidget(self.fw_label)

        h_lay.addSpacing(12)

        self.batt_label = QLabel("Battery: --%")
        self.batt_label.setStyleSheet("font-weight: bold; color: #7ee39d;")
        h_lay.addWidget(self.batt_label)

        self.batt_refresh_btn = QPushButton("Refresh")
        self.batt_refresh_btn.clicked.connect(self._refresh_full_state)
        h_lay.addWidget(self.batt_refresh_btn)

        h_lay.addSpacing(12)
        h_lay.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        for p in range(PROFILE_MIN, PROFILE_MAX + 1):
            self.profile_combo.addItem(f"Profile {p}", p)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        h_lay.addWidget(self.profile_combo)

        main_lay.addWidget(header)

        # Body container
        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(14, 12, 14, 12)
        body_lay.setSpacing(10)

        # Permission Helper Banner
        self.perm_banner = QFrame()
        self.perm_banner.setObjectName("PermBanner")
        pb_lay = QHBoxLayout(self.perm_banner)
        self.perm_text = QLabel(
            "ATTACK SHARK R6 detected, but your Linux user lacks /dev/hidraw read/write permission."
        )
        self.perm_text.setWordWrap(True)
        pb_lay.addWidget(self.perm_text, 1)
        self.install_udev_btn = QPushButton("Install USB Permissions (pkexec)")
        self.install_udev_btn.setObjectName("PrimaryBtn")
        self.install_udev_btn.clicked.connect(self._install_udev_rules)
        pb_lay.addWidget(self.install_udev_btn)
        self.perm_banner.setVisible(False)
        body_lay.addWidget(self.perm_banner)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_keybinding_tab(), "Key Binding")
        self.tabs.addTab(self._build_performance_tab(), "Performance")
        self.tabs.addTab(self._build_macro_tab(), "Macro Editor")
        self.tabs.addTab(self._build_device_tab(), "Device && Pairing")
        self.settings_tab = self._build_settings_tab()
        self.tabs.addTab(self.settings_tab, "Settings")
        body_lay.addWidget(self.tabs, 1)

        main_lay.addWidget(body, 1)
        self.statusBar().showMessage("Ready")
        self._set_controls_enabled(False)

    def _set_status_pill(self, text: str, bg: str, fg: str) -> None:
        self.status_pill.setText(text)
        self.status_pill.setStyleSheet(
            f"background-color: {bg}; color: {fg}; padding: 4px 12px; border-radius: 10px; font-weight: bold;"
        )

    def _build_keybinding_tab(self) -> QWidget:
        tab = QWidget()
        lay = QHBoxLayout(tab)
        lay.setSpacing(16)

        # Left column: mouse diagram
        left_card = QFrame()
        left_card.setObjectName("Card")
        left_card.setMinimumWidth(280)
        lc_lay = QVBoxLayout(left_card)
        lc_lay.setAlignment(Qt.AlignCenter)
        img_lbl = QLabel()
        pm = _asset_pixmap("mouse_diagram.png")
        if not pm.isNull():
            img_lbl.setPixmap(pm.scaledToHeight(360, Qt.SmoothTransformation))
        img_lbl.setAlignment(Qt.AlignCenter)
        lc_lay.addWidget(img_lbl)
        hint = QLabel("Click any button on the right to remap it\nto mouse, keyboard, macro, media, or DPI actions.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #9cb2ba;")
        lc_lay.addWidget(hint)
        lay.addWidget(left_card)

        # Right column: button assignment grid
        right_card = QGroupBox("Programmable Buttons")
        grid = QGridLayout(right_card)
        grid.setSpacing(10)
        self.button_assign_btns: Dict[ButtonID, QPushButton] = {}
        for row, bid in enumerate(CONFIGURABLE_BUTTONS):
            lbl = QLabel(BUTTON_LABELS[bid])
            lbl.setStyleSheet("font-weight: bold;")
            btn = QPushButton("—")
            btn.setMinimumHeight(36)
            btn.clicked.connect(lambda _=False, b=bid: self._edit_button_binding(b))
            self.button_assign_btns[bid] = btn
            grid.addWidget(lbl, row, 0)
            grid.addWidget(btn, row, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(len(CONFIGURABLE_BUTTONS), 1)
        lay.addWidget(right_card, 1)
        return tab

    def _build_performance_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setSpacing(12)

        # DPI Stages Box
        dpi_box = QGroupBox("DPI Stages (50 – 42,000 DPI, step 50)")
        dpi_lay = QVBoxLayout(dpi_box)
        self.dpi_radio_group = QButtonGroup(self)
        self.dpi_rows: List[DpiStageRow] = []
        for idx in range(1, DPI_MAX_STAGES + 1):
            row = DpiStageRow(idx, self.dpi_radio_group)
            row.changed.connect(self._apply_dpi_changes)
            row.activated.connect(self._on_active_dpi_selected)
            self.dpi_rows.append(row)
            dpi_lay.addWidget(row)

        dpi_footer = QHBoxLayout()
        dpi_footer.addStretch(1)
        self.apply_dpi_btn = QPushButton("Apply DPI & Colors")
        self.apply_dpi_btn.setObjectName("PrimaryBtn")
        self.apply_dpi_btn.clicked.connect(self._apply_dpi_changes)
        dpi_footer.addWidget(self.apply_dpi_btn)
        dpi_lay.addLayout(dpi_footer)
        lay.addWidget(dpi_box)

        # Bottom split: Polling/LOD/Debounce/Sleep + Sensor Tuning
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        # Hardware Parameters
        hw_box = QGroupBox("Polling Rate, LOD, Debounce & Sleep")
        hw_form = QFormLayout(hw_box)
        hw_form.setSpacing(10)

        self.polling_combo = QComboBox()
        for hz in WIRELESS_POLLING_RATES:
            self.polling_combo.addItem(f"{hz} Hz", hz)
        self.polling_combo.currentIndexChanged.connect(self._on_polling_changed)
        hw_form.addRow("Polling Rate:", self.polling_combo)

        lod_row = QHBoxLayout()
        self.lod_buttons: Dict[int, QPushButton] = {}
        for code, text in [(0x87, "0.7 mm"), (1, "1.0 mm"), (2, "2.0 mm")]:
            b = QPushButton(text)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, c=code: self._on_lod_clicked(c))
            self.lod_buttons[code] = b
            lod_row.addWidget(b)
        hw_form.addRow("Lift-Off Distance:", lod_row)

        deb_row = QHBoxLayout()
        self.debounce_slider = QSlider(Qt.Horizontal)
        self.debounce_slider.setRange(DEBOUNCE_MIN_MS, DEBOUNCE_MAX_MS)
        self.debounce_slider.sliderReleased.connect(self._on_debounce_committed)
        self.debounce_spin = QSpinBox()
        self.debounce_spin.setRange(DEBOUNCE_MIN_MS, DEBOUNCE_MAX_MS)
        self.debounce_spin.setSuffix(" ms")
        self.debounce_slider.valueChanged.connect(self._sync_debounce_from_slider)
        self.debounce_spin.valueChanged.connect(self._sync_debounce_from_spin)
        self.debounce_spin.editingFinished.connect(self._on_debounce_committed)
        deb_row.addWidget(self.debounce_slider, 1)
        deb_row.addWidget(self.debounce_spin)
        hw_form.addRow("Debounce Time:", deb_row)

        slp_row = QHBoxLayout()
        self.sleep_slider = QSlider(Qt.Horizontal)
        self.sleep_slider.setRange(SLEEP_MIN_SEC, SLEEP_MAX_SEC)
        self.sleep_slider.valueChanged.connect(self._on_sleep_slider_moved)
        self.sleep_slider.sliderReleased.connect(self._on_sleep_committed)
        self.sleep_label = QLabel("15 Mins")
        self.sleep_label.setMinimumWidth(68)
        self.sleep_never_cb = QCheckBox("Never (∞)")
        self.sleep_never_cb.toggled.connect(self._on_sleep_never_toggled)
        slp_row.addWidget(self.sleep_slider, 1)
        slp_row.addWidget(self.sleep_label)
        slp_row.addWidget(self.sleep_never_cb)
        hw_form.addRow("Wireless Sleep:", slp_row)

        bottom_row.addWidget(hw_box, 3)

        # Sensor Tuning
        sen_box = QGroupBox("Sensor Tuning (PAW3950)")
        sen_lay = QVBoxLayout(sen_box)
        self.motion_sync_cb = QCheckBox("Motion Sync")
        self.motion_sync_cb.toggled.connect(lambda v: self._on_sensor_toggled("motion_sync", v))
        self.ripple_cb = QCheckBox("Ripple Control")
        self.ripple_cb.toggled.connect(lambda v: self._on_sensor_toggled("ripple", v))
        self.angle_snap_cb = QCheckBox("Angle Snapping")
        self.angle_snap_cb.toggled.connect(lambda v: self._on_sensor_toggled("angle_snap", v))
        sen_lay.addWidget(self.motion_sync_cb)
        sen_lay.addWidget(self.ripple_cb)
        sen_lay.addWidget(self.angle_snap_cb)
        sen_lay.addStretch(1)
        bottom_row.addWidget(sen_box, 2)

        lay.addLayout(bottom_row)
        lay.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    def _build_macro_tab(self) -> QWidget:
        tab = QWidget()
        lay = QHBoxLayout(tab)
        lay.setSpacing(12)

        # Left pane: Stored macros on mouse
        left_box = QGroupBox("Onboard Macros (Slots 1–29)")
        left_lay = QVBoxLayout(left_box)
        self.macro_list = QListWidget()
        self.macro_list.itemDoubleClicked.connect(self._load_selected_macro)
        left_lay.addWidget(self.macro_list, 1)

        lbtn_row1 = QHBoxLayout()
        self.refresh_macros_btn = QPushButton("Refresh")
        self.refresh_macros_btn.clicked.connect(self._refresh_macro_list)
        self.load_macro_btn = QPushButton("Load")
        self.load_macro_btn.clicked.connect(self._load_selected_macro)
        lbtn_row1.addWidget(self.refresh_macros_btn)
        lbtn_row1.addWidget(self.load_macro_btn)
        left_lay.addLayout(lbtn_row1)

        lbtn_row2 = QHBoxLayout()
        self.del_macro_btn = QPushButton("Delete Slot")
        self.del_macro_btn.setObjectName("DangerBtn")
        self.del_macro_btn.clicked.connect(self._delete_selected_macro)
        self.clear_macros_btn = QPushButton("Clear All")
        self.clear_macros_btn.setObjectName("DangerBtn")
        self.clear_macros_btn.clicked.connect(self._clear_all_macros)
        lbtn_row2.addWidget(self.del_macro_btn)
        lbtn_row2.addWidget(self.clear_macros_btn)
        left_lay.addLayout(lbtn_row2)

        lay.addWidget(left_box, 1)

        # Right pane: Editor & Capture Pad
        right_box = QGroupBox("Macro Recorder & Editor")
        r_lay = QVBoxLayout(right_box)

        top_cfg = QHBoxLayout()
        top_cfg.addWidget(QLabel("Target Slot ID:"))
        self.macro_target_spin = QSpinBox()
        self.macro_target_spin.setRange(MACRO_MIN_ID, MACRO_MAX_ID)
        top_cfg.addWidget(self.macro_target_spin)

        top_cfg.addSpacing(12)
        top_cfg.addWidget(QLabel("Delay Mode:"))
        self.macro_delay_mode = QComboBox()
        self.macro_delay_mode.addItem("Record Actual Delay", "record")
        self.macro_delay_mode.addItem("Default Delay", "default")
        self.macro_delay_mode.addItem("No Delay", "none")
        top_cfg.addWidget(self.macro_delay_mode)

        self.macro_default_delay_spin = QSpinBox()
        self.macro_default_delay_spin.setRange(1, 5000)
        self.macro_default_delay_spin.setValue(50)
        self.macro_default_delay_spin.setSuffix(" ms")
        top_cfg.addWidget(self.macro_default_delay_spin)
        top_cfg.addStretch(1)
        r_lay.addLayout(top_cfg)

        self.capture_pad = MacroCapturePad()
        self.capture_pad.step_recorded.connect(self._on_macro_step_recorded)
        r_lay.addWidget(self.capture_pad)

        rec_row = QHBoxLayout()
        self.record_btn = QPushButton("Start Recording")
        self.record_btn.setCheckable(True)
        self.record_btn.setObjectName("PrimaryBtn")
        self.record_btn.toggled.connect(self._on_record_toggled)
        rec_row.addWidget(self.record_btn)

        ins_key_btn = QPushButton("+ Key")
        ins_key_btn.clicked.connect(self._insert_macro_key)
        ins_mouse_btn = QPushButton("+ Mouse Click")
        ins_mouse_btn.clicked.connect(self._insert_macro_mouse)
        ins_delay_btn = QPushButton("+ Delay")
        ins_delay_btn.clicked.connect(self._insert_macro_delay)
        rec_row.addWidget(ins_key_btn)
        rec_row.addWidget(ins_mouse_btn)
        rec_row.addWidget(ins_delay_btn)
        rec_row.addStretch(1)
        r_lay.addLayout(rec_row)

        self.steps_list = QListWidget()
        r_lay.addWidget(self.steps_list, 1)

        step_ops = QHBoxLayout()
        up_btn = QPushButton("Move Up")
        up_btn.clicked.connect(lambda: self._move_macro_step(-1))
        dn_btn = QPushButton("Move Down")
        dn_btn.clicked.connect(lambda: self._move_macro_step(1))
        rm_btn = QPushButton("Remove Step")
        rm_btn.clicked.connect(self._remove_macro_step)
        clr_steps_btn = QPushButton("Clear Steps")
        clr_steps_btn.clicked.connect(self._clear_macro_steps)
        step_ops.addWidget(up_btn)
        step_ops.addWidget(dn_btn)
        step_ops.addWidget(rm_btn)
        step_ops.addWidget(clr_steps_btn)
        step_ops.addStretch(1)
        self.macro_size_lbl = QLabel("0 bytes")
        step_ops.addWidget(self.macro_size_lbl)
        r_lay.addLayout(step_ops)

        up_row = QHBoxLayout()
        self.macro_progress = QProgressBar()
        self.macro_progress.setValue(0)
        self.upload_macro_btn = QPushButton("Upload to Mouse")
        self.upload_macro_btn.setObjectName("PrimaryBtn")
        self.upload_macro_btn.clicked.connect(self._upload_macro)
        up_row.addWidget(self.macro_progress, 1)
        up_row.addWidget(self.upload_macro_btn)
        r_lay.addLayout(up_row)

        lay.addWidget(right_box, 2)
        return tab

    def _build_device_tab(self) -> QWidget:
        tab = QWidget()
        lay = QHBoxLayout(tab)
        lay.setSpacing(14)

        # Left: visual + metadata + actions
        left_col = QVBoxLayout()
        dev_box = QGroupBox("Connected Hardware")
        db_lay = QHBoxLayout(dev_box)
        self.dev_pic_lbl = QLabel()
        pm = _asset_pixmap("device_wireless.png")
        if not pm.isNull():
            self.dev_pic_lbl.setPixmap(pm.scaledToHeight(210, Qt.SmoothTransformation))
        db_lay.addWidget(self.dev_pic_lbl)

        self.dev_info_lbl = QLabel("No device connected.")
        self.dev_info_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.dev_info_lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        db_lay.addWidget(self.dev_info_lbl, 1)
        left_col.addWidget(dev_box)

        pair_box = QGroupBox("2.4 GHz Receiver Pairing")
        pb_lay = QVBoxLayout(pair_box)
        pb_info = QLabel(
            "Put mouse in pairing mode by holding Left + Middle + Right buttons for 3 seconds "
            "until the pairing LED flashes quickly, keep it close to the 2.4G receiver, and click Start Pairing."
        )
        pb_info.setWordWrap(True)
        pb_lay.addWidget(pb_info)
        pair_row = QHBoxLayout()
        pair_icon = QLabel()
        ppm = _asset_pixmap("pair_icon.png")
        if not ppm.isNull():
            pair_icon.setPixmap(ppm.scaledToHeight(32, Qt.SmoothTransformation))
        pair_row.addWidget(pair_icon)
        self.pair_btn = QPushButton("Start 2.4G Pairing")
        self.pair_btn.setObjectName("PrimaryBtn")
        self.pair_btn.clicked.connect(self._start_pairing)
        pair_row.addWidget(self.pair_btn)
        self.pair_status_lbl = QLabel("Idle")
        pair_row.addWidget(self.pair_status_lbl, 1)
        pb_lay.addLayout(pair_row)
        left_col.addWidget(pair_box)

        cfg_box = QGroupBox("Profile Backup & Reset")
        cfg_lay = QGridLayout(cfg_box)
        self.export_btn = QPushButton("Export Profile JSON...")
        self.export_btn.clicked.connect(self._export_profile)
        self.import_btn = QPushButton("Import Profile JSON...")
        self.import_btn.clicked.connect(self._import_profile)
        self.reset_prof_btn = QPushButton("Reset Current Profile")
        self.reset_prof_btn.setObjectName("DangerBtn")
        self.reset_prof_btn.clicked.connect(self._reset_current_profile)
        self.factory_reset_btn = QPushButton("Factory Reset Mouse")
        self.factory_reset_btn.setObjectName("DangerBtn")
        self.factory_reset_btn.clicked.connect(self._factory_reset)
        cfg_lay.addWidget(self.export_btn, 0, 0)
        cfg_lay.addWidget(self.import_btn, 0, 1)
        cfg_lay.addWidget(self.reset_prof_btn, 1, 0)
        cfg_lay.addWidget(self.factory_reset_btn, 1, 1)
        left_col.addWidget(cfg_box)
        left_col.addStretch(1)

        lay.addLayout(left_col, 1)

        # Right: Live Notification Log
        log_box = QGroupBox("Live Hardware Notifications (MI01)")
        log_lay = QVBoxLayout(log_box)
        self.event_log = QPlainTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setPlaceholderText("Live DPI switches, wake/sleep, LOD & polling rate changes appear here...")
        log_lay.addWidget(self.event_log, 1)
        clr_log = QPushButton("Clear Log")
        clr_log.clicked.connect(self.event_log.clear)
        log_lay.addWidget(clr_log, 0, Qt.AlignRight)
        lay.addWidget(log_box, 1)

        return tab

    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setSpacing(14)

        tray_box = QGroupBox("System Tray & Zero-Resource Idle Mode")
        tray_lay = QVBoxLayout(tray_box)
        tray_lay.setSpacing(10)

        self.close_to_tray_chk = QCheckBox(
            "Minimize to system tray when pressing X (0% CPU idle mode)"
        )
        self.close_to_tray_chk.setChecked(self._settings.close_to_tray)
        self.close_to_tray_chk.toggled.connect(self._on_settings_changed)
        tray_lay.addWidget(self.close_to_tray_chk)

        self.start_minimized_chk = QCheckBox("Start minimized to system tray")
        self.start_minimized_chk.setChecked(self._settings.start_minimized)
        self.start_minimized_chk.toggled.connect(self._on_settings_changed)
        tray_lay.addWidget(self.start_minimized_chk)

        desc = QLabel(
            "When minimized to the taskbar system tray, all hotplug/battery polling timers, "
            "background worker threads, and /dev/hidraw* file handles are stopped and closed, "
            "and unused heap memory is trimmed (~0% CPU and 0 wakeups/sec) until you reopen the window "
            "from the tray icon or launcher. Right-click the tray icon → Quit or press Ctrl+Q to exit completely."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #9cb2ba;")
        tray_lay.addWidget(desc)

        tray_ok = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray_avail_lbl = QLabel(
            "System tray status: Available"
            if tray_ok
            else "System tray status: Not detected in this session (pressing X will exit normally)."
        )
        self.tray_avail_lbl.setStyleSheet(
            "color: #7ee39d;" if tray_ok else "color: #f08080;"
        )
        self.tray_avail_lbl.setWordWrap(True)
        tray_lay.addWidget(self.tray_avail_lbl)

        btn_row = QHBoxLayout()
        self.min_tray_now_btn = QPushButton("Minimize to Tray Now")
        self.min_tray_now_btn.setObjectName("PrimaryBtn")
        self.min_tray_now_btn.clicked.connect(self.enter_tray_idle)
        btn_row.addWidget(self.min_tray_now_btn)

        self.quit_app_btn = QPushButton("Quit Application (Ctrl+Q)")
        self.quit_app_btn.setObjectName("DangerBtn")
        self.quit_app_btn.clicked.connect(self.quit_application)
        btn_row.addWidget(self.quit_app_btn)
        btn_row.addStretch(1)
        tray_lay.addLayout(btn_row)
        lay.addWidget(tray_box)

        info_box = QGroupBox("Application Info & USB Permissions")
        info_lay = QVBoxLayout(info_box)
        info_lay.setSpacing(10)
        cfg_path = self._settings_path if self._settings_path is not None else default_settings_path()
        info_lbl = QLabel(
            f"Version: v{__version__}\n"
            f"Settings file: {cfg_path}\n"
            f"udev rule target: {UDEV_RULE_TARGET}"
        )
        info_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info_lbl.setStyleSheet("color: #9cb2ba;")
        info_lay.addWidget(info_lbl)

        udev_btn = QPushButton("Install / Reinstall USB udev Rules (pkexec)")
        udev_btn.clicked.connect(self._install_udev_rules)
        info_lay.addWidget(udev_btn, 0, Qt.AlignLeft)
        lay.addWidget(info_box)

        lay.addStretch(1)
        return tab

    def _on_settings_changed(self) -> None:
        self._settings = AppSettings(
            close_to_tray=self.close_to_tray_chk.isChecked(),
            start_minimized=self.start_minimized_chk.isChecked(),
        )
        try:
            save_settings(self._settings, self._settings_path)
            self.statusBar().showMessage("Settings saved.", 2500)
        except OSError as exc:
            self.statusBar().showMessage(f"Failed to save settings: {exc}", 5000)

    # ------------------------------------------------------------------
    # Device Discovery, Permissions & Connection
    # ------------------------------------------------------------------

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.profile_combo.setEnabled(enabled)
        self.batt_refresh_btn.setEnabled(enabled)
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if w is not None and w is not self.settings_tab:
                w.setEnabled(enabled)

    def _poll_hotplug(self) -> None:
        if self._closing or self._suspended:
            return
        devs = discover_devices()
        if not devs:
            if self.dev_info is not None:
                self._disconnect_device()
            self.perm_banner.setVisible(False)
            self._set_status_pill("Disconnected", "#5b2525", "#f2b8b8")
            self.fw_label.setText("Mouse FW: --   Dongle FW: --")
            self.batt_label.setText("Battery: --%")
            self.dev_info_lbl.setText("No ATTACK SHARK R6 mouse or receiver connected.")
            self._set_controls_enabled(False)
            return

        # Prefer device with rw permission, else first detected
        chosen = next((d for d in devs if d.has_permission), devs[0])
        if not chosen.has_permission:
            if self.dev_info is not None:
                self._disconnect_device()
            self.perm_banner.setVisible(True)
            self.perm_text.setText(
                f"Detected {chosen.name} ({chosen.mode_label}) at {chosen.control_path}, "
                "but your user lacks hidraw read/write permission."
            )
            self._set_status_pill("Permission Required", "#614217", "#ffd899")
            self._update_dev_info_label(chosen)
            self._set_controls_enabled(False)
            return

        self.perm_banner.setVisible(False)
        if (
            self.dev_info is not None
            and self.dev_info.control_path == chosen.control_path
            and self.dev_info.pid == chosen.pid
        ):
            return

        self._connect_device(chosen)

    def _connect_device(self, info: R6DeviceInfo) -> None:
        self._disconnect_device()
        self.dev_info = info
        self.transport = HidrawTransport(info.control_path)
        self.transport.open()
        self.proto = R6Protocol(self.transport)

        mode_txt = "Wireless 8K" if info.is_wireless else "Wired"
        self._set_status_pill(mode_txt, "#164e34", "#9df5c8")
        self._update_dev_info_label(info)
        self._set_controls_enabled(True)

        # Restrict polling rates when wired
        self.polling_combo.blockSignals(True)
        self.polling_combo.clear()
        rates = WIRELESS_POLLING_RATES if info.is_wireless else WIRED_POLLING_RATES
        for hz in rates:
            self.polling_combo.addItem(f"{hz} Hz", hz)
        self.polling_combo.blockSignals(False)

        self.pair_btn.setEnabled(info.is_wireless)

        if info.notify_path and info.notify_ro:
            self.listener = NotificationListener(
                info.notify_path,
                lambda kind, raw: self.notify_received.emit(kind, raw),
            )
            self.listener.start()

        self._refresh_full_state(after_sync=self._refresh_macro_list)

    def _disconnect_device(self) -> None:
        if self._pair_timer is not None:
            self._pair_timer.stop()
            self._pair_timer = None
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
        if self.transport is not None:
            self.transport.close()
            self.transport = None
        self.proto = None
        self.dev_info = None
        self.state = None

    def _update_dev_info_label(self, info: R6DeviceInfo) -> None:
        self.dev_info_lbl.setText(
            f"Name: {info.name}\n"
            f"Mode: {info.mode_label}\n"
            f"USB ID: {info.vid:04X}:{info.pid:04X}\n"
            f"Serial: {info.serial or '-'}\n"
            f"Control: {info.control_path} ({'RW' if info.control_rw else 'No Perm'})\n"
            f"Notify: {info.notify_path or '-'} ({'RO' if info.notify_ro else 'No Perm'})\n"
            f"Boot Mouse: {info.boot_mouse_path or '-'}"
        )

    def _install_udev_rules(self) -> None:
        if not UDEV_RULE_SOURCE.exists():
            QMessageBox.critical(self, "Missing File", f"Rule file not found:\n{UDEV_RULE_SOURCE}")
            return
        pkexec = shutil.which("pkexec")
        if not pkexec:
            QMessageBox.information(
                self,
                "Install udev Rules",
                f"Run in terminal:\n  sudo cp {UDEV_RULE_SOURCE} {UDEV_RULE_TARGET}\n"
                "  sudo udevadm control --reload-rules && sudo udevadm trigger",
            )
            return
        cmd = (
            "rm -f /etc/udev/rules.d/99-attackshark-r6.rules && "
            f"install -m 0644 '{UDEV_RULE_SOURCE}' '{UDEV_RULE_TARGET}' && "
            "udevadm control --reload-rules && "
            "udevadm trigger --subsystem-match=hidraw --subsystem-match=usb && "
            "udevadm settle"
        )
        res = subprocess.run([pkexec, "sh", "-c", cmd], capture_output=True, text=True)
        if res.returncode != 0:
            QMessageBox.warning(
                self,
                "Permission Setup Failed",
                res.stderr.strip() or "Could not install udev rule.",
            )
            return
        self.statusBar().showMessage("USB permissions installed; reconnecting...", 4000)
        QTimer.singleShot(300, self._poll_hotplug)

    # ------------------------------------------------------------------
    # Background Workers & State Sync
    # ------------------------------------------------------------------

    def _run_worker(
        self,
        fn: Callable[[Callable[[int], None]], object],
        on_done: Callable[[object], None],
        on_err: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> None:
        if self._closing or self._suspended:
            return
        worker = TaskWorker(fn, self)
        self._workers.append(worker)

        def _cleanup() -> None:
            if worker in self._workers:
                self._workers.remove(worker)

        def _handle_done(res: object) -> None:
            if not (self._closing or self._suspended):
                on_done(res)

        def _handle_err(msg: str) -> None:
            if not (self._closing or self._suspended):
                if on_err:
                    on_err(msg)
                else:
                    self.statusBar().showMessage(f"Error: {msg}", 6000)

        worker.succeeded.connect(_handle_done)
        worker.failed.connect(_handle_err)
        if on_progress is not None:
            worker.progress.connect(
                lambda val: on_progress(val)
                if not (self._closing or self._suspended)
                else None
            )
        worker.finished.connect(_cleanup)
        worker.start()

    def _refresh_full_state(
        self,
        explicit_profile: Optional[int] = None,
        after_sync: Optional[Callable[[], None]] = None,
    ) -> None:
        if self.proto is None or self._closing or self._suspended:
            return
        proto = self.proto
        self.statusBar().showMessage("Syncing with mouse...")

        def work(_prog: Callable[[int], None]) -> MouseState:
            return proto.read_full_state(profile_id=explicit_profile)

        def done(state_obj: object) -> None:
            self._apply_state_to_ui(state_obj)
            if after_sync is not None and not (self._closing or self._suspended):
                after_sync()

        self._run_worker(work, done, self._on_sync_error)

    def _on_sync_error(self, msg: str) -> None:
        self.statusBar().showMessage(f"HID read failed (mouse may be asleep): {msg}", 5000)

    def _refresh_battery_only(self) -> None:
        if self.proto is None or self._closing or self._suspended:
            return
        proto = self.proto
        self._run_worker(
            lambda _p: proto.get_battery(),
            lambda res: self._update_battery_label(*res),
            lambda _msg: None,
        )

    def _update_battery_label(self, charging: bool, pct: int) -> None:
        suffix = " (Charging)" if charging else ""
        color = "#7ee39d" if pct > 25 else "#f08080"
        self.batt_label.setStyleSheet(f"font-weight: bold; color: {color};")
        self.batt_label.setText(f"Battery: {pct}%{suffix}")

    def _apply_state_to_ui(self, state_obj: object) -> None:
        assert isinstance(state_obj, MouseState)
        self.state = state_obj
        self._syncing_ui = True
        try:
            self.fw_label.setText(
                f"Mouse FW: {state_obj.device_fw}   Dongle FW: {state_obj.dongle_fw}"
            )
            self._update_battery_label(state_obj.battery_charging, state_obj.battery_percent)

            pidx = self.profile_combo.findData(state_obj.profile_id)
            if pidx >= 0:
                self.profile_combo.setCurrentIndex(pidx)

            # Buttons
            for bid, btn in self.button_assign_btns.items():
                b = state_obj.buttons.get(int(bid))
                btn.setText(b.describe() if b else "—")

            # DPI stages & colors
            n_stages = len(state_obj.dpi_stages)
            for i, row in enumerate(self.dpi_rows):
                enabled = i < n_stages
                stage = state_obj.dpi_stages[i] if enabled else DPIStage(800 * (i + 1), 800 * (i + 1))
                color = (
                    state_obj.dpi_colors[i]
                    if i < len(state_obj.dpi_colors)
                    else DEFAULT_DPI_COLORS[i]
                )
                active = enabled and (i + 1 == state_obj.active_dpi_stage)
                row.set_values(enabled, active, stage, color)

            # Polling rate
            poll_idx = self.polling_combo.findData(state_obj.polling_rate_hz)
            if poll_idx >= 0:
                self.polling_combo.setCurrentIndex(poll_idx)

            # LOD
            for code, b in self.lod_buttons.items():
                b.setChecked(code == state_obj.lod_code)

            # Debounce
            self.debounce_slider.setValue(
                max(DEBOUNCE_MIN_MS, min(DEBOUNCE_MAX_MS, state_obj.debounce_ms))
            )
            self.debounce_spin.setValue(
                max(DEBOUNCE_MIN_MS, min(DEBOUNCE_MAX_MS, state_obj.debounce_ms))
            )

            # Sleep
            if state_obj.sleep_sec == SLEEP_DISABLED:
                self.sleep_never_cb.setChecked(True)
                self.sleep_slider.setEnabled(False)
                self.sleep_label.setText("Never")
            else:
                self.sleep_never_cb.setChecked(False)
                self.sleep_slider.setEnabled(True)
                sec = max(SLEEP_MIN_SEC, min(SLEEP_MAX_SEC, state_obj.sleep_sec))
                self.sleep_slider.setValue(sec)
                self._update_sleep_label(sec)

            # Sensors
            self.motion_sync_cb.setChecked(state_obj.motion_sync)
            self.ripple_cb.setChecked(state_obj.ripple_control)
            self.angle_snap_cb.setChecked(state_obj.angle_snap)
        finally:
            self._syncing_ui = False

        self.statusBar().showMessage(
            f"Synced Profile {state_obj.profile_id} ({len(state_obj.dpi_stages)} DPI stages, {state_obj.polling_rate_hz} Hz)",
            3500,
        )

    # ------------------------------------------------------------------
    # Handlers: Profile, Buttons, Performance
    # ------------------------------------------------------------------

    def _current_profile_id(self) -> int:
        val = self.profile_combo.currentData()
        return int(val) if val is not None else 1

    def _on_profile_changed(self) -> None:
        if self._syncing_ui or self.proto is None:
            return
        pid = self._current_profile_id()
        proto = self.proto

        def work(_p: Callable[[int], None]) -> MouseState:
            proto.set_profile_id(pid)
            return proto.read_full_state(profile_id=pid)

        self._run_worker(work, self._apply_state_to_ui, self._on_sync_error)

    def _edit_button_binding(self, bid: ButtonID) -> None:
        if self.proto is None or self.state is None:
            return
        cur = self.state.buttons.get(int(bid), ButtonBinding.mouse_button(bid))
        dlg = ButtonBindDialog(bid, cur, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        new_bind = dlg.build_binding()
        pid = self._current_profile_id()
        proto = self.proto

        def work(_p: Callable[[int], None]) -> bool:
            return proto.set_button(pid, bid, new_bind)

        def done(ok: object) -> None:
            if ok and self.state is not None:
                self.state.buttons[int(bid)] = new_bind
                self.button_assign_btns[bid].setText(new_bind.describe())
                self.statusBar().showMessage(f"{BUTTON_LABELS[bid]} -> {new_bind.describe()}", 3000)

        self._run_worker(work, done)

    def _apply_dpi_changes(self) -> None:
        if self._syncing_ui or self.proto is None:
            return
        enabled_rows = [r for r in self.dpi_rows if r.enable_cb.isChecked()]
        if not enabled_rows:
            self._syncing_ui = True
            self.dpi_rows[0].enable_cb.setChecked(True)
            self._syncing_ui = False
            enabled_rows = [self.dpi_rows[0]]

        stages = [r.get_stage() for r in enabled_rows]
        colors = [r.color for r in enabled_rows]
        while len(colors) < DPI_MAX_STAGES:
            colors.append((0, 0, 0))

        # Active stage (1-based within enabled stages)
        active_idx = 1
        for idx, r in enumerate(enabled_rows, 1):
            if r.active_radio.isChecked():
                active_idx = idx
                break
        if not enabled_rows[active_idx - 1].active_radio.isChecked():
            self._syncing_ui = True
            enabled_rows[0].active_radio.setChecked(True)
            self._syncing_ui = False

        pid = self._current_profile_id()
        proto = self.proto

        def work(_p: Callable[[int], None]) -> bool:
            proto.set_dpi_stages(pid, stages)
            proto.set_dpi_colors(pid, colors)
            proto.set_active_dpi(pid, active_idx)
            return True

        self._run_worker(
            work,
            lambda _ok: self.statusBar().showMessage(
                f"Applied {len(stages)} DPI stage(s), active stage #{active_idx}", 3000
            ),
        )

    def _on_active_dpi_selected(self, row_stage_idx: int) -> None:
        if self._syncing_ui or self.proto is None:
            return
        enabled_rows = [r for r in self.dpi_rows if r.enable_cb.isChecked()]
        target_idx = 1
        for idx, r in enumerate(enabled_rows, 1):
            if r.stage_index == row_stage_idx:
                target_idx = idx
                break
        pid = self._current_profile_id()
        proto = self.proto
        self._run_worker(
            lambda _p: proto.set_active_dpi(pid, target_idx),
            lambda _ok: self.statusBar().showMessage(f"Active DPI stage -> #{target_idx}", 2500),
        )

    def _on_polling_changed(self) -> None:
        if self._syncing_ui or self.proto is None:
            return
        hz = self.polling_combo.currentData()
        if hz is None:
            return
        pid = self._current_profile_id()
        proto = self.proto
        self._run_worker(
            lambda _p: proto.set_polling_rate(pid, int(hz)),
            lambda _ok: self.statusBar().showMessage(f"Polling rate -> {hz} Hz", 2500),
        )

    def _on_lod_clicked(self, lod_code: int) -> None:
        if self._syncing_ui or self.proto is None:
            return
        self._syncing_ui = True
        for c, b in self.lod_buttons.items():
            b.setChecked(c == lod_code)
        self._syncing_ui = False
        pid = self._current_profile_id()
        proto = self.proto
        self._run_worker(
            lambda _p: proto.set_lod(pid, lod_code),
            lambda _ok: self.statusBar().showMessage(
                f"LOD -> {LOD_CODE_TO_NAME.get(lod_code, lod_code)}", 2500
            ),
        )

    def _sync_debounce_from_slider(self, val: int) -> None:
        self.debounce_spin.blockSignals(True)
        self.debounce_spin.setValue(val)
        self.debounce_spin.blockSignals(False)

    def _sync_debounce_from_spin(self, val: int) -> None:
        self.debounce_slider.blockSignals(True)
        self.debounce_slider.setValue(val)
        self.debounce_slider.blockSignals(False)

    def _on_debounce_committed(self) -> None:
        if self._syncing_ui or self.proto is None:
            return
        ms = self.debounce_spin.value()
        pid = self._current_profile_id()
        proto = self.proto
        self._run_worker(
            lambda _p: proto.set_debounce_time(pid, ms),
            lambda _ok: self.statusBar().showMessage(f"Debounce -> {ms} ms", 2500),
        )

    def _update_sleep_label(self, sec: int) -> None:
        if sec >= 60:
            self.sleep_label.setText(f"{sec // 60} Mins")
        else:
            self.sleep_label.setText(f"{sec} s")

    def _on_sleep_slider_moved(self, sec: int) -> None:
        self._update_sleep_label(sec)

    def _on_sleep_committed(self) -> None:
        if self._syncing_ui or self.proto is None or self.sleep_never_cb.isChecked():
            return
        sec = self.sleep_slider.value()
        pid = self._current_profile_id()
        proto = self.proto
        self._run_worker(
            lambda _p: proto.set_sleep_time(pid, sec),
            lambda _ok: self.statusBar().showMessage(f"Sleep timeout -> {sec} s", 2500),
        )

    def _on_sleep_never_toggled(self, never: bool) -> None:
        self.sleep_slider.setEnabled(not never)
        if never:
            self.sleep_label.setText("Never")
        else:
            self._update_sleep_label(self.sleep_slider.value())
        if self._syncing_ui or self.proto is None:
            return
        sec = SLEEP_DISABLED if never else self.sleep_slider.value()
        pid = self._current_profile_id()
        proto = self.proto
        self._run_worker(
            lambda _p: proto.set_sleep_time(pid, sec),
            lambda _ok: self.statusBar().showMessage("Sleep timeout updated", 2500),
        )

    def _on_sensor_toggled(self, kind: str, enabled: bool) -> None:
        if self._syncing_ui or self.proto is None:
            return
        pid = self._current_profile_id()
        proto = self.proto

        def work(_p: Callable[[int], None]) -> bool:
            if kind == "motion_sync":
                return proto.set_motion_sync(pid, enabled)
            if kind == "ripple":
                return proto.set_ripple_control(pid, enabled)
            return proto.set_angle_snap(pid, enabled)

        self._run_worker(
            work,
            lambda _ok: self.statusBar().showMessage(
                f"{kind.replace('_', ' ').title()} -> {'ON' if enabled else 'OFF'}", 2500
            ),
        )

    # ------------------------------------------------------------------
    # Handlers: Macro Editor
    # ------------------------------------------------------------------

    def _refresh_macro_list(self) -> None:
        if self.proto is None or self._closing or self._suspended:
            return
        proto = self.proto
        self._run_worker(
            lambda _p: proto.list_macros(
                cancel_check=lambda: self._closing or self._suspended
            ),
            self._populate_macro_list,
        )

    def _populate_macro_list(self, data: object) -> None:
        assert isinstance(data, dict)
        self.macro_list.clear()
        for mid, sz in sorted(data.items()):
            item = QListWidgetItem(f"Macro #{mid}  ({sz} bytes)")
            item.setData(Qt.UserRole, int(mid))
            self.macro_list.addItem(item)

    def _load_selected_macro(self) -> None:
        if self.proto is None:
            return
        item = self.macro_list.currentItem()
        if item is None:
            return
        mid = int(item.data(Qt.UserRole))
        self.macro_target_spin.setValue(mid)
        proto = self.proto

        def done(steps: object) -> None:
            assert isinstance(steps, list)
            self._macro_steps = steps
            self._refresh_macro_steps_view()
            self.statusBar().showMessage(f"Loaded Macro #{mid} ({len(steps)} steps)", 3000)

        self._run_worker(lambda _p: proto.get_macro(mid), done)

    def _delete_selected_macro(self) -> None:
        if self.proto is None:
            return
        item = self.macro_list.currentItem()
        mid = int(item.data(Qt.UserRole)) if item else self.macro_target_spin.value()
        proto = self.proto
        self._run_worker(
            lambda _p: proto.delete_macro(mid),
            lambda _ok: (
                self.statusBar().showMessage(f"Deleted Macro #{mid}", 3000),
                self._refresh_macro_list(),
            ),
        )

    def _clear_all_macros(self) -> None:
        if self.proto is None:
            return
        if (
            QMessageBox.question(
                self, "Clear All Macros", "Delete all onboard macros (slots 1–29)?"
            )
            != QMessageBox.Yes
        ):
            return
        proto = self.proto

        def work(_p: Callable[[int], None]) -> None:
            existing = proto.list_macros()
            for mid in existing:
                proto.delete_macro(mid)

        self._run_worker(
            work,
            lambda _res: (
                self.statusBar().showMessage("Cleared all onboard macros", 3000),
                self._refresh_macro_list(),
            ),
        )

    def _on_record_toggled(self, active: bool) -> None:
        self.record_btn.setText("Stop Recording" if active else "Start Recording")
        mode = str(self.macro_delay_mode.currentData())
        self.capture_pad.set_recording(active, mode, self.macro_default_delay_spin.value())

    def _on_macro_step_recorded(self, step: MacroStep) -> None:
        self._macro_steps.append(step)
        self._refresh_macro_steps_view()
        self.steps_list.scrollToBottom()

    def _insert_macro_key(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Insert Key Event")
        form = QFormLayout(dlg)
        cap = KeyCaptureButton(0x04, dlg)
        key_cb = QComboBox(dlg)
        for code, name in sorted(HID_KEY_TO_NAME.items()):
            key_cb.addItem(f"{name} (0x{code:02X})", code)
        key_cb.currentIndexChanged.connect(lambda: cap.set_hid_code(int(key_cb.currentData())))
        cap.key_captured.connect(lambda c: key_cb.setCurrentIndex(max(0, key_cb.findData(c))))
        kind_cb = QComboBox(dlg)
        kind_cb.addItem("Press + Release (Down then Up)", "pair")
        kind_cb.addItem("Key Down only", "key_down")
        kind_cb.addItem("Key Up only", "key_up")
        form.addRow("Capture:", cap)
        form.addRow("Key:", key_cb)
        form.addRow("Action:", kind_cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec_() == QDialog.Accepted:
            code = cap.hid_code
            act = kind_cb.currentData()
            if act == "pair":
                self._macro_steps.append(MacroStep(kind="key_down", code=code))
                self._macro_steps.append(MacroStep(kind="delay", delay_ms=20))
                self._macro_steps.append(MacroStep(kind="key_up", code=code))
            else:
                self._macro_steps.append(MacroStep(kind=act, code=code))
            self._refresh_macro_steps_view()

    def _insert_macro_mouse(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Insert Mouse Event")
        form = QFormLayout(dlg)
        btn_cb = QComboBox(dlg)
        for bid in [ButtonID.LEFT, ButtonID.RIGHT, ButtonID.MIDDLE, ButtonID.BACKWARD, ButtonID.FORWARD]:
            btn_cb.addItem(BUTTON_LABELS[bid], int(bid))
        act_cb = QComboBox(dlg)
        act_cb.addItem("Click (Down + Up)", "pair")
        act_cb.addItem("Button Down", "mouse_down")
        act_cb.addItem("Button Up", "mouse_up")
        form.addRow("Button:", btn_cb)
        form.addRow("Action:", act_cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec_() == QDialog.Accepted:
            code = int(btn_cb.currentData())
            act = act_cb.currentData()
            if act == "pair":
                self._macro_steps.append(MacroStep(kind="mouse_down", code=code))
                self._macro_steps.append(MacroStep(kind="delay", delay_ms=20))
                self._macro_steps.append(MacroStep(kind="mouse_up", code=code))
            else:
                self._macro_steps.append(MacroStep(kind=act, code=code))
            self._refresh_macro_steps_view()

    def _insert_macro_delay(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Insert Delay")
        form = QFormLayout(dlg)
        spin = QSpinBox(dlg)
        spin.setRange(1, 60000)
        spin.setValue(50)
        spin.setSuffix(" ms")
        form.addRow("Delay:", spin)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec_() == QDialog.Accepted:
            self._macro_steps.append(MacroStep(kind="delay", delay_ms=spin.value()))
            self._refresh_macro_steps_view()

    def _move_macro_step(self, delta: int) -> None:
        row = self.steps_list.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= len(self._macro_steps):
            return
        self._macro_steps[row], self._macro_steps[target] = (
            self._macro_steps[target],
            self._macro_steps[row],
        )
        self._refresh_macro_steps_view()
        self.steps_list.setCurrentRow(target)

    def _remove_macro_step(self) -> None:
        row = self.steps_list.currentRow()
        if 0 <= row < len(self._macro_steps):
            del self._macro_steps[row]
            self._refresh_macro_steps_view()

    def _clear_macro_steps(self) -> None:
        self._macro_steps.clear()
        self._refresh_macro_steps_view()

    def _refresh_macro_steps_view(self) -> None:
        self.steps_list.clear()
        for idx, st in enumerate(self._macro_steps, 1):
            self.steps_list.addItem(f"{idx:3d}. {st.describe()}")
        raw_len = len(encode_macro(self._macro_steps))
        self.macro_size_lbl.setText(f"{len(self._macro_steps)} steps ({raw_len} bytes)")

    def _upload_macro(self) -> None:
        if self.proto is None:
            return
        if self.record_btn.isChecked():
            self.record_btn.setChecked(False)
        if not self._macro_steps:
            QMessageBox.information(self, "Empty Macro", "Add or record at least one macro step first.")
            return
        mid = self.macro_target_spin.value()
        raw = encode_macro(self._macro_steps)
        proto = self.proto
        self.upload_macro_btn.setEnabled(False)
        self.macro_progress.setValue(0)

        def work(emit_prog: Callable[[int], None]) -> bool:
            for _ in range(3):
                if proto.allocate_macro_size(mid, len(raw)):
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError(f"Failed to allocate macro #{mid}")
            total = len(raw)
            for off in range(0, total, MACRO_CHUNK_SIZE):
                chunk = raw[off : off + MACRO_CHUNK_SIZE]
                if not proto._set_macro_chunk(mid, off, chunk):
                    raise RuntimeError(f"Failed writing macro #{mid} chunk at {off}")
                pct = int(min(100, round(((off + len(chunk)) / total) * 100)))
                emit_prog(pct)
            return True

        def done(_ok: object) -> None:
            self.upload_macro_btn.setEnabled(True)
            self.macro_progress.setValue(100)
            self.statusBar().showMessage(f"Uploaded Macro #{mid} ({len(raw)} bytes)", 3500)
            self._refresh_macro_list()

        def err(msg: str) -> None:
            self.upload_macro_btn.setEnabled(True)
            QMessageBox.critical(self, "Upload Failed", msg)

        self._run_worker(work, done, err, self.macro_progress.setValue)

    # ------------------------------------------------------------------
    # Handlers: Pairing, Backup/Reset & Live Notifications
    # ------------------------------------------------------------------

    def _start_pairing(self) -> None:
        if self.proto is None:
            return
        self.pair_btn.setEnabled(False)
        self.pair_status_lbl.setText("Pairing... Hold L+M+R for 3s")
        self.proto.set_pair_status(True)
        self._pair_deadline = time.monotonic() + 20.0

        if self._pair_timer is not None:
            self._pair_timer.stop()
        self._pair_timer = QTimer(self)
        self._pair_timer.setInterval(500)
        self._pair_timer.timeout.connect(self._poll_pairing)
        self._pair_timer.start()

    def _poll_pairing(self) -> None:
        if self.proto is None:
            return
        if time.monotonic() >= self._pair_deadline:
            assert self._pair_timer is not None
            self._pair_timer.stop()
            self.proto.set_pair_status(False)
            self.pair_status_lbl.setText("Timed out")
            self.pair_btn.setEnabled(True)
            return
        st = self.proto.get_pair_status()
        if st == 2:
            assert self._pair_timer is not None
            self._pair_timer.stop()
            self.proto.set_pair_status(False)
            self.pair_status_lbl.setText("Paired successfully!")
            self.pair_btn.setEnabled(True)
            self._refresh_full_state()

    def _export_profile(self) -> None:
        if self.state is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Profile JSON",
            f"attackshark-r6-profile-{self.state.profile_id}.json",
            "JSON Files (*.json)",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.state.to_export_dict(), f, indent=2)
        self.statusBar().showMessage(f"Exported profile to {path}", 3500)

    def _import_profile(self) -> None:
        if self.proto is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Profile JSON", "", "JSON Files (*.json)"
        )
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pid = self._current_profile_id()
        proto = self.proto

        def work(_p: Callable[[int], None]) -> MouseState:
            proto.apply_export_dict(pid, data)
            return proto.read_full_state(profile_id=pid)

        self._run_worker(work, self._apply_state_to_ui)

    def _reset_current_profile(self) -> None:
        if self.proto is None:
            return
        pid = self._current_profile_id()
        if (
            QMessageBox.question(
                self, "Reset Profile", f"Reset Profile {pid} to defaults?"
            )
            != QMessageBox.Yes
        ):
            return
        proto = self.proto

        def work(_p: Callable[[int], None]) -> MouseState:
            proto.reset_profile(pid)
            time.sleep(0.5)
            return proto.read_full_state(profile_id=pid)

        self._run_worker(work, self._apply_state_to_ui)

    def _factory_reset(self) -> None:
        if self.proto is None:
            return
        if (
            QMessageBox.warning(
                self,
                "Factory Reset",
                "Reset all profiles and device settings to factory defaults?",
                QMessageBox.Yes | QMessageBox.Cancel,
            )
            != QMessageBox.Yes
        ):
            return
        pid = self._current_profile_id()
        proto = self.proto

        def work(_p: Callable[[int], None]) -> MouseState:
            proto.factory_reset(pid)
            time.sleep(0.5)
            return proto.read_full_state(profile_id=1)

        self._run_worker(work, self._apply_state_to_ui)

    def _on_device_notification(self, kind: str, raw: bytes) -> None:
        if self._closing or self._suspended:
            return
        ts = time.strftime("%H:%M:%S")
        self.event_log.appendPlainText(f"[{ts}] {kind}: {raw.hex(' ')}")
        if kind == "wake" and self.dev_info is not None:
            mode_txt = "Wireless 8K" if self.dev_info.is_wireless else "Wired"
            self._set_status_pill(mode_txt, "#164e34", "#9df5c8")
            self._refresh_full_state()
        elif kind == "sleep" and self.dev_info is not None and self.dev_info.is_wireless:
            self._set_status_pill("Wireless (Asleep)", "#4d4319", "#f2dc85")
        elif kind in ("dpi_changed", "lod_changed", "polling_changed"):
            self._refresh_full_state()


def main(argv: Optional[List[str]] = None) -> int:
    raw_args = sys.argv[1:] if argv is None else list(argv)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--minimized", action="store_true", default=False)
    known, remaining = parser.parse_known_args(raw_args)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication([sys.argv[0], *remaining])
    app.setApplicationName("ATTACK SHARK R6")
    app.setDesktopFileName("attackshark-r6")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLESHEET)

    sock_name = f"attackshark-r6-linux-{os.getuid()}"
    probe = QLocalSocket()
    probe.connectToServer(sock_name)
    if probe.waitForConnected(200):
        if not known.minimized:
            probe.write(b"SHOW\n")
            probe.flush()
            probe.waitForBytesWritten(200)
        probe.disconnectFromServer()
        return 0

    QLocalServer.removeServer(sock_name)
    server = QLocalServer()
    win = MainWindow(start_minimized=True if known.minimized else None)
    if server.listen(sock_name):
        win._ipc_server = server

        def _on_ipc_connection() -> None:
            while server.hasPendingConnections():
                conn = server.nextPendingConnection()
                if conn is not None:
                    conn.waitForReadyRead(100)
                    conn.readAll()
                    conn.close()
                    conn.deleteLater()
                    win.wake_from_tray()

        server.newConnection.connect(_on_ipc_connection)

    if not win._suspended:
        win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
