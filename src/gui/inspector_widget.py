from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QTextEdit

from oecon.inspect import SessionInfo, format_session_info, inspect_session


class _InspectWorker(QThread):
    result: Signal = Signal(object)   # SessionInfo
    error: Signal = Signal(str)

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self) -> None:
        try:
            self.result.emit(inspect_session(self._path))
        except Exception as exc:
            self.error.emit(str(exc))


class SessionInspectorWidget(QGroupBox):
    """Read-only panel that summarises the content of an Open Ephys session."""

    def __init__(self, parent=None):
        super().__init__("Session Inspector", parent)
        self._worker: _InspectWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFixedHeight(130)
        mono = QFont("Courier New" if sys.platform == "win32" else "Monospace")
        mono.setPointSize(9)
        self._text.setFont(mono)
        self._text.setPlaceholderText("Select a session folder to see its contents.")
        layout.addWidget(self._text)

    def load(self, session_path: Path) -> None:
        """Start (or restart) inspection of *session_path* in a background thread."""
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()

        self._text.setPlainText("Inspecting…")
        self._worker = _InspectWorker(session_path, parent=self)
        self._worker.result.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def clear(self) -> None:
        self._text.clear()

    def _on_result(self, info: SessionInfo) -> None:
        self._text.setPlainText(format_session_info(info))

    def _on_error(self, msg: str) -> None:
        self._text.setPlainText(f"Could not inspect session:\n{msg}")
