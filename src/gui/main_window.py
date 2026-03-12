import logging
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QComboBox, QSpinBox, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from open_ephys.analysis.session import Session

from oecon.config import (
    ContinuousMuaConfig, DecimationConfig, EventPreprocessingConfig,
    OpenEphysToDhConfig, OutputFormat, RawConfig, SpikeConfig,
    TrialMapConfig, load_config_from_file, save_config_to_file,
)
from oecon.convert_open_ephys_to_dh5 import convert_open_ephys_recording_to_dh5

from gui.config_widget import ConfigStepWidget

# (tab label, OpenEphysToDhConfig field name, model class, enabled by default)
_TAB_CONFIGS = [
    ("Raw",       "raw_config",            RawConfig,                False),
    ("Events",    "event_config",          EventPreprocessingConfig, True),
    ("Trial Map", "trialmap_config",       TrialMapConfig,           True),
    ("LFP",       "decimation_config",     DecimationConfig,         True),
    ("MUA",       "continuous_mua_config", ContinuousMuaConfig,      True),
    ("Spikes",        "spike_config",          SpikeConfig,             False),
]


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
    finished: Signal = Signal()
    error: Signal = Signal(str)

    def __init__(
        self,
        session_path: Path,
        output_folder: Path,
        config: OpenEphysToDhConfig,
        parent=None,
    ):
        super().__init__(parent)
        self._session_path = session_path
        self._output_folder = output_folder
        self._config = config

    def run(self) -> None:
        handler = _QtLogHandler(self.log_message)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        try:
            session = Session(str(self._session_path))
            session_name = str(self._output_folder / self._session_path.name)
            for node in session.recordnodes:
                for recording in node.recordings:
                    convert_open_ephys_recording_to_dh5(
                        recording=recording,
                        session_name=session_name,
                        config=self._config,
                    )
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            root_logger.removeHandler(handler)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OEcon")
        self.setMinimumSize(720, 680)
        self._worker: _ConversionWorker | None = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)

        # Session / output paths
        top_form = QFormLayout()
        top_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._session_edit = QLineEdit()
        self._session_edit.setPlaceholderText("Select Open Ephys session folder…")
        session_btn = QPushButton("Browse")
        session_btn.clicked.connect(self._pick_session)
        session_row = QHBoxLayout()
        session_row.addWidget(self._session_edit)
        session_row.addWidget(session_btn)
        top_form.addRow("Session:", session_row)

        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("Defaults to session parent folder")
        output_btn = QPushButton("Browse")
        output_btn.clicked.connect(self._pick_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self._output_edit)
        output_row.addWidget(output_btn)
        top_form.addRow("Output:", output_row)

        meta_row = QHBoxLayout()
        self._format_combo = QComboBox()
        self._format_combo.addItem(OutputFormat.DH5.value.upper(), userData=OutputFormat.DH5)
        meta_row.addWidget(QLabel("Format:"))
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
        top_form.addRow("", meta_row)

        root.addLayout(top_form)

        # Step tabs
        self._tabs = QTabWidget()
        self._tab_widgets: dict[str, ConfigStepWidget] = {}
        for tab_name, field_name, model_class, enabled in _TAB_CONFIGS:
            widget = ConfigStepWidget(model_class, enabled_by_default=enabled)
            self._tab_widgets[field_name] = widget
            self._tabs.addTab(widget, tab_name)
        root.addWidget(self._tabs, stretch=1)

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
        path = QFileDialog.getExistingDirectory(self, "Select Open Ephys session folder")
        if path:
            self._session_edit.setText(path)
            if not self._output_edit.text():
                self._output_edit.setText(str(Path(path).parent))

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

    def _load_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load config", filter="JSON (*.json)")
        if not path:
            return
        try:
            self._apply_config(load_config_from_file(path))
        except Exception as exc:
            QMessageBox.critical(self, "Load failed", str(exc))

    def _save_config(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save config", filter="JSON (*.json)"
        )
        if not path:
            return
        try:
            save_config_to_file(path, self._build_config())
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _run(self) -> None:
        session_str = self._session_edit.text().strip()
        if not session_str:
            QMessageBox.warning(self, "No session", "Please select a session folder.")
            return

        session_path = Path(session_str)
        output_str = self._output_edit.text().strip()
        output_folder = Path(output_str) if output_str else session_path.parent
        output_folder.mkdir(parents=True, exist_ok=True)

        try:
            config = self._build_config()
        except Exception as exc:
            QMessageBox.critical(self, "Config error", str(exc))
            return

        self._log_edit.clear()
        self._run_btn.setEnabled(False)

        self._worker = _ConversionWorker(session_path, output_folder, config, parent=self)
        self._worker.log_message.connect(self._append_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _append_log(self, msg: str) -> None:
        self._log_edit.append(msg)

    def _on_finished(self) -> None:
        self._run_btn.setEnabled(True)
        self._append_log("--- Conversion complete ---")

    def _on_error(self, msg: str) -> None:
        self._run_btn.setEnabled(True)
        self._append_log(f"ERROR: {msg}")
        QMessageBox.critical(self, "Conversion failed", msg)
