from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QAbstractItemView, QFileDialog, QListView, QTreeView, QWidget


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


def pick_session_dirs(parent: QWidget, title: str = "Select Open Ephys session folder(s)", initial: str = "") -> list[Path]:
    """Open a folder-picker dialog that supports selecting multiple directories."""
    dialog = QFileDialog(parent, title, initial)
    dialog.setFileMode(QFileDialog.FileMode.Directory)
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)

    for view in (dialog.findChild(QListView, "listView"), dialog.findChild(QTreeView)):
        if view:
            view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    if not dialog.exec():
        return []
    return [Path(p) for p in dialog.selectedFiles()]
