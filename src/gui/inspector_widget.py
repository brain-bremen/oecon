from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout

from oecon.inspect import SessionInfo, inspect_session, validate_session_path
from oecon.inspect import _fmt_duration, _fmt_rate, _fmt_size


_PATH_ROLE = 256  # UserRole: stores Path on top-level session items


def _ellipsis_list(names: list[str], max_items: int = 10) -> list[str]:
    if len(names) <= max_items:
        return names
    half = max_items // 2
    omitted = len(names) - max_items
    return names[:half] + [f"… ({omitted} more) …"] + names[half + omitted:]


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
    """Tree panel showing all loaded Open Ephys sessions with their contents."""

    def __init__(self, buttons: list[QPushButton] | None = None, parent=None):
        super().__init__("Sessions", parent)
        self._workers: dict[Path, _InspectWorker] = {}

        outer = QHBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumHeight(180)
        self._tree.setColumnCount(1)
        outer.addWidget(self._tree, stretch=1)

        if buttons:
            btn_layout = QVBoxLayout()
            for btn in buttons:
                btn_layout.addWidget(btn)
            btn_layout.addStretch()
            outer.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, path: Path) -> None:
        """Add a session and start inspecting it in the background."""
        if any(self._tree.topLevelItem(i).data(0, _PATH_ROLE) == path
               for i in range(self._tree.topLevelItemCount())):
            return  # already present

        placeholder = QTreeWidgetItem([f"{path.name}  —  inspecting…"])
        placeholder.setData(0, _PATH_ROLE, path)
        self._tree.addTopLevelItem(placeholder)
        self._tree.setCurrentItem(placeholder)

        worker = _InspectWorker(path, parent=self)
        worker.result.connect(lambda info, p=path: self._on_result(p, info))
        worker.error.connect(lambda msg, p=path: self._on_error(p, msg))
        self._workers[path] = worker
        worker.start()

    def remove_selected(self) -> Path | None:
        """Remove the session that contains the current selection. Returns its path."""
        item = self._tree.currentItem()
        if item is None:
            return None
        # Walk up to the top-level item
        while item.parent() is not None:
            item = item.parent()
        path = item.data(0, _PATH_ROLE)
        index = self._tree.indexOfTopLevelItem(item)
        self._tree.takeTopLevelItem(index)
        if path in self._workers:
            w = self._workers.pop(path)
            if w.isRunning():
                w.terminate()
                w.wait()
        return path

    def session_paths(self) -> list[Path]:
        return [
            self._tree.topLevelItem(i).data(0, _PATH_ROLE)
            for i in range(self._tree.topLevelItemCount())
        ]

    def clear_all(self) -> None:
        for w in self._workers.values():
            if w.isRunning():
                w.terminate()
                w.wait()
        self._workers.clear()
        self._tree.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _top_level_item_for(self, path: Path) -> QTreeWidgetItem | None:
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.data(0, _PATH_ROLE) == path:
                return item
        return None

    def _on_result(self, path: Path, info: SessionInfo) -> None:
        item = self._top_level_item_for(path)
        if item is None:
            return
        item.setText(0, f"{info.path.name}  —  {_fmt_size(info.total_size_bytes)}")

        for rec in info.recordings:
            rec_label = (
                f"Exp {rec.experiment_index + 1} / Rec {rec.recording_index + 1}"
                f"  [{_fmt_duration(rec.duration_s)}]"
            )
            rec_item = QTreeWidgetItem([rec_label])
            item.addChild(rec_item)

            if rec.streams:
                cont_item = QTreeWidgetItem([f"Continuous  ({len(rec.streams)} stream(s))"])
                rec_item.addChild(cont_item)
                for stream in rec.streams:
                    stream_item = QTreeWidgetItem([
                        f"{stream.name}  —  {stream.num_channels} ch, {_fmt_rate(stream.sample_rate)}"
                    ])
                    cont_item.addChild(stream_item)
                    for ch_name in _ellipsis_list(stream.channel_names):
                        stream_item.addChild(QTreeWidgetItem([ch_name]))

            if rec.event_streams:
                ev_item = QTreeWidgetItem([f"Events  ({len(rec.event_streams)})"])
                rec_item.addChild(ev_item)
                for ev in rec.event_streams:
                    label = f"{ev.name}  —  {ev.count} events" if ev.count is not None else ev.name
                    ev_item.addChild(QTreeWidgetItem([label]))

        item.setExpanded(True)
        for i in range(item.childCount()):
            item.child(i).setExpanded(True)

    def _on_error(self, path: Path, msg: str) -> None:
        item = self._top_level_item_for(path)
        if item is None:
            return
        item.setText(0, f"{path.name}  —  error: {msg}")
