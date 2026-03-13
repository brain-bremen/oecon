import logging
import re
import sys
from pathlib import Path

from pydantic import ValidationError
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QComboBox, QSpinBox, QTabWidget,
    QTextEdit, QVBoxLayout, QWidget, QProgressBar,
)


from oecon.config import (
    ContinuousMuaConfig, DecimationConfig, EventPreprocessingConfig,
    OpenEphysToDhConfig, OutputFormat, RawConfig, SpikeConfig,
    TrialMapConfig, load_config_from_file, save_config_to_file,
)
from oecon import convert_open_ephys_session
from oecon.version import get_version_from_pyproject
from oecon.inspect import validate_session_path

from gui.config_widget import ConfigStepWidget
from gui.inspector_widget import SessionInspectorWidget
from gui.settings import (
    get_last_config_path, get_last_session_dir,
    set_last_config_path, set_last_session_dir, pick_session_dirs,
)

# (tab label, OpenEphysToDhConfig field name, model class, enabled by default)
_TAB_CONFIGS = [
    ("Raw",       "raw_config",            RawConfig,                False),
    ("Events",    "event_config",          EventPreprocessingConfig, True),
    ("Trial Map", "trialmap_config",       TrialMapConfig,           True),
    ("LFP",       "decimation_config",     DecimationConfig,         True),
    ("MUA",       "continuous_mua_config", ContinuousMuaConfig,      True),
    ("Spikes",        "spike_config",          SpikeConfig,             False),
]


def _format_validation_error(exc: ValidationError) -> str:
    model_name = exc.title
    lines = [f"{model_name} has invalid values:"]
    for error in exc.errors():
        field = " → ".join(str(part) for part in error["loc"])
        msg = re.sub(r"^value error,\s*", "", error["msg"], flags=re.IGNORECASE)
        got = error.get("input")
        got_str = f" (got {got!r})" if got is not None else ""
        lines.append(f"  • {field}: {msg}{got_str}")
    return "\n".join(lines)


class _QtLogHandler(logging.Handler):
    def __init__(self, signal: Signal):
        super().__init__()
        self._signal = signal
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._signal.emit(self.format(record))
        except Exception:
            pass


class _ConversionWorker(QThread):
    log_message: Signal = Signal(str)
    step_progress: Signal = Signal(str, int, int)   # step_name, done, total
    session_progress: Signal = Signal(int, int)     # done, total
    finished: Signal = Signal()
    error: Signal = Signal(str)

    def __init__(
        self,
        session_paths: list[Path],
        output_folder: Path | None,
        config: OpenEphysToDhConfig,
        parent=None,
    ):
        super().__init__(parent)
        self._session_paths = session_paths
        self._output_folder = output_folder
        self._config = config

    def run(self) -> None:
        handler = _QtLogHandler(self.log_message)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        n = len(self._session_paths)
        try:
            for i, session_path in enumerate(self._session_paths):
                self.session_progress.emit(i, n)
                convert_open_ephys_session(
                    session_path,
                    output_folder=self._output_folder,
                    config=self._config,
                    on_progress=lambda name, done, total: self.step_progress.emit(name, done, total),
                )
                self.session_progress.emit(i + 1, n)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            root_logger.removeHandler(handler)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"OEcon {get_version_from_pyproject()}")
        self.setMinimumSize(720, 680)
        self._worker: _ConversionWorker | None = None
        self._setup_ui()
        self._restore_settings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)

        add_btn = QPushButton("Add…")
        add_btn.clicked.connect(self._pick_session)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_session)
        self._inspector = SessionInspectorWidget(buttons=[add_btn, remove_btn])
        root.addWidget(self._inspector)

        # Output group: output folder + format + workers
        output_group = QGroupBox("Output")
        output_form = QFormLayout(output_group)
        output_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("Defaults to session parent folder")
        output_btn = QPushButton("Browse")
        output_btn.clicked.connect(self._pick_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self._output_edit)
        output_row.addWidget(output_btn)
        output_form.addRow("Folder:", output_row)

        meta_row = QHBoxLayout()
        self._format_combo = QComboBox()
        self._format_combo.addItem(OutputFormat.DH5.value.upper(), userData=OutputFormat.DH5)
        meta_row.addWidget(self._format_combo)
        meta_row.addSpacing(20)
        meta_row.addWidget(QLabel("Workers (n_jobs):"))
        self._n_jobs_spin = QSpinBox()
        self._n_jobs_spin.setRange(-1, 256)
        self._n_jobs_spin.setValue(1)
        self._n_jobs_spin.setToolTip("Parallelization not yet implemented.")
        self._n_jobs_spin.setEnabled(False)
        meta_row.addWidget(self._n_jobs_spin)
        meta_row.addStretch()
        output_form.addRow("Format:", meta_row)

        root.addWidget(output_group)

        # Step tabs
        self._tabs = QTabWidget()
        self._tab_widgets: dict[str, ConfigStepWidget] = {}
        for tab_name, field_name, model_class, enabled in _TAB_CONFIGS:
            widget = ConfigStepWidget(model_class, enabled_by_default=enabled)
            self._tab_widgets[field_name] = widget
            self._tabs.addTab(widget, tab_name)
        root.addWidget(self._tabs, stretch=1)

        # Progress bars
        self._session_bar = QProgressBar()
        self._session_bar.setTextVisible(True)
        self._session_bar.setRange(0, 1)
        self._session_bar.setValue(0)
        self._session_bar.setFormat("Sessions")
        root.addWidget(self._session_bar)

        self._step_label = QLabel("Step")
        self._step_bar = QProgressBar()
        self._step_bar.setTextVisible(True)
        self._step_bar.setRange(0, 1)
        self._step_bar.setValue(0)
        self._step_bar.setFormat("Ready")
        step_row = QHBoxLayout()
        step_row.addWidget(self._step_label)
        step_row.addWidget(self._step_bar, stretch=1)
        root.addLayout(step_row)

        # Action buttons
        btn_row = QHBoxLayout()
        load_btn = QPushButton("Load Config")
        load_btn.clicked.connect(self._load_config)
        save_btn = QPushButton("Save Config")
        save_btn.clicked.connect(self._save_config)
        self._run_btn = QPushButton("▶  Run")
        self._run_btn.setDefault(True)
        self._run_btn.clicked.connect(self._run)
        btn_row.addWidget(load_btn)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._run_btn)
        root.addLayout(btn_row)

        # Log output
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFixedHeight(160)
        mono = QFont("Courier New" if sys.platform == "win32" else "Monospace")
        mono.setPointSize(9)
        self._log_edit.setFont(mono)
        root.addWidget(self._log_edit)

    # ------------------------------------------------------------------
    # Path pickers
    # ------------------------------------------------------------------

    def _pick_session(self) -> None:
        paths = pick_session_dirs(self, initial=get_last_session_dir() or "")
        for p in paths:
            try:
                validate_session_path(p)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid session", str(exc))
                continue
            set_last_session_dir(p)
            if not self._output_edit.text():
                self._output_edit.setText(str(p.parent))
            self._inspector.add(p)

    def _remove_session(self) -> None:
        self._inspector.remove_selected()

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output folder")
        if path:
            self._output_edit.setText(path)

    # ------------------------------------------------------------------
    # Config build / load / save
    # ------------------------------------------------------------------

    def _build_config(self) -> OpenEphysToDhConfig:
        kwargs: dict = {
            field_name: self._tab_widgets[field_name].get_model()
            for _, field_name, _, _ in _TAB_CONFIGS
        }
        kwargs["output_format"] = self._format_combo.currentData()
        kwargs["n_jobs"] = self._n_jobs_spin.value()
        return OpenEphysToDhConfig(**kwargs)

    def _apply_config(self, config: OpenEphysToDhConfig) -> None:
        for _, field_name, _, _ in _TAB_CONFIGS:
            self._tab_widgets[field_name].set_model(getattr(config, field_name, None))
        for i in range(self._format_combo.count()):
            if self._format_combo.itemData(i) == config.output_format:
                self._format_combo.setCurrentIndex(i)
                break
        self._n_jobs_spin.setValue(config.n_jobs)

    def _restore_settings(self) -> None:
        config_path = get_last_config_path()
        if config_path:
            try:
                self._apply_config(load_config_from_file(config_path))
            except Exception:
                pass  # silently ignore stale/broken config

    def _load_config(self) -> None:
        initial = get_last_config_path() or ""
        path, _ = QFileDialog.getOpenFileName(self, "Load config", initial, filter="JSON (*.json)")
        if not path:
            return
        try:
            self._apply_config(load_config_from_file(path))
            set_last_config_path(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load failed", str(exc))

    def _save_config(self) -> None:
        initial = get_last_config_path() or ""
        path, _ = QFileDialog.getSaveFileName(self, "Save config", initial, filter="JSON (*.json)")
        if not path:
            return
        try:
            save_config_to_file(path, self._build_config())
            set_last_config_path(path)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _run(self) -> None:
        session_paths = self._inspector.session_paths()
        if not session_paths:
            QMessageBox.warning(self, "No session", "Please add at least one session folder.")
            return

        output_str = self._output_edit.text().strip()
        output_folder = Path(output_str) if output_str else None

        try:
            config = self._build_config()
        except ValidationError as exc:
            QMessageBox.critical(self, "Config error", _format_validation_error(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Config error", str(exc))
            return

        self._log_edit.clear()
        self._run_btn.setEnabled(False)

        n = len(session_paths)
        self._step_bar.setRange(0, 1)
        self._step_bar.setValue(0)
        self._step_bar.setFormat("Starting…")
        self._step_label.setText("Step")
        self._session_bar.setRange(0, n)
        self._session_bar.setValue(0)
        self._session_bar.setFormat(f"Session 0 / {n}")

        self._worker = _ConversionWorker(session_paths, output_folder, config, parent=self)
        self._worker.log_message.connect(self._append_log)
        self._worker.step_progress.connect(self._on_step_progress)
        self._worker.session_progress.connect(self._on_session_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _append_log(self, msg: str) -> None:
        self._log_edit.append(msg)

    def _on_step_progress(self, step_name: str, done: int, total: int) -> None:
        self._step_bar.setRange(0, total)
        self._step_bar.setValue(done)
        self._step_label.setText(step_name)
        self._step_bar.setFormat(f"{done} / {total}")

    def _on_session_progress(self, done: int, total: int) -> None:
        self._session_bar.setValue(done)
        self._session_bar.setFormat(f"Session {done} / {total}")

    def _on_finished(self) -> None:
        self._run_btn.setEnabled(True)
        self._step_bar.setFormat("Done")
        self._step_label.setText("Step")
        self._append_log("--- Conversion complete ---")

    def _on_error(self, msg: str) -> None:
        self._run_btn.setEnabled(True)
        self._step_bar.setFormat("Error")
        self._step_label.setText("Step")
        self._append_log(f"ERROR: {msg}")
        QMessageBox.critical(self, "Conversion failed", msg)
