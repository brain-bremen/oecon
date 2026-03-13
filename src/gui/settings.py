from pathlib import Path

from PySide6.QtCore import QSettings


def _q() -> QSettings:
    return QSettings("brain-bremen", "OEcon")


def get_last_session_dir() -> str | None:
    v = _q().value("last_session_dir")
    return str(v) if v and Path(str(v)).is_dir() else None


def set_last_session_dir(path: Path) -> None:
    _q().setValue("last_session_dir", str(path.parent))


def get_last_config_path() -> str | None:
    v = _q().value("last_config_path")
    return str(v) if v and Path(str(v)).is_file() else None


def set_last_config_path(path: str) -> None:
    _q().setValue("last_config_path", path)
