"""Persistent user settings for the ATTACK SHARK R6 Linux Control Center."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


def default_settings_path() -> Path:
    """Return the XDG-compliant JSON path for persisted GUI settings."""
    xdg_cfg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_cfg) if xdg_cfg else (Path.home() / ".config")
    return base / "attackshark-r6" / "settings.json"


@dataclass
class AppSettings:
    """User-configurable GUI lifecycle preferences."""

    close_to_tray: bool = True
    start_minimized: bool = False


def load_settings(path: Optional[Path] = None) -> AppSettings:
    """Load settings from JSON, falling back cleanly to defaults on any error."""
    target = path if path is not None else default_settings_path()
    defaults = AppSettings()
    try:
        raw = target.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError, TypeError):
        return defaults
    if not isinstance(data, dict):
        return defaults
    return AppSettings(
        close_to_tray=bool(data.get("close_to_tray", defaults.close_to_tray)),
        start_minimized=bool(data.get("start_minimized", defaults.start_minimized)),
    )


def save_settings(settings: AppSettings, path: Optional[Path] = None) -> None:
    """Atomically write settings JSON to disk."""
    target = path if path is not None else default_settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(settings), indent=2) + "\n"
    fd, tmp_path = tempfile.mkstemp(
        prefix=".settings-", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
