"""Offscreen PyQt5 lifecycle tests for Settings tab & zero-resource tray idle mode."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication

    from attackshark_r6 import gui
    from attackshark_r6.settings import AppSettings, load_settings

    HAS_PYQT5 = True
except Exception:
    HAS_PYQT5 = False


@unittest.skipUnless(HAS_PYQT5, "PyQt5 not installed")
class TestGuiTrayIdleLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_settings_persistence_and_tray_idle_suspend_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "settings.json"
            with mock.patch.object(gui, "discover_devices", return_value=[]):
                win = gui.MainWindow(settings_path=cfg_path, start_minimized=False)
                win.show()
                self._app.processEvents()

                # Settings tab must remain enabled even when no mouse is connected
                self.assertEqual(win.tabs.count(), 5)
                self.assertTrue(win.settings_tab.isEnabled())
                self.assertTrue(win.close_to_tray_chk.isChecked())
                self.assertFalse(win.start_minimized_chk.isChecked())

                # Toggle settings and verify atomic persistence on disk
                win.close_to_tray_chk.setChecked(False)
                win.start_minimized_chk.setChecked(True)
                self._app.processEvents()
                self.assertEqual(
                    load_settings(cfg_path),
                    AppSettings(close_to_tray=False, start_minimized=True),
                )

                # Enter zero-resource tray idle mode
                self.assertTrue(win.hotplug_timer.isActive())
                self.assertTrue(win.battery_timer.isActive())
                win.enter_tray_idle()
                self._app.processEvents()

                self.assertTrue(win._suspended)
                self.assertFalse(win.hotplug_timer.isActive())
                self.assertFalse(win.battery_timer.isActive())
                self.assertIsNone(win.transport)
                self.assertIsNone(win.proto)
                self.assertIsNone(win.dev_info)
                self.assertIsNone(win.state)
                self.assertFalse(win.isVisible())

                # Wake from tray restores visibility and restarts timers
                win.wake_from_tray()
                self._app.processEvents()
                self.assertFalse(win._suspended)
                self.assertTrue(win.hotplug_timer.isActive())
                self.assertTrue(win.battery_timer.isActive())
                self.assertTrue(win.isVisible())

                win.quit_application()
                self._app.processEvents()
                self.assertTrue(win._closing)


if __name__ == "__main__":
    unittest.main()
