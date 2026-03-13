# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **GUI**: new PySide6 application (`oecon-gui`) with layout organised into labelled groupboxes — Input, Output, Config, Progress, Log
- **Multi-session support**: add multiple Open Ephys sessions via the session inspector tree; sessions are all shown simultaneously with their recordings, streams, channel names, and event counts
- **Session inspector** (`oecon-inspect`): new standalone GUI app for browsing Open Ephys sessions without converting
- **Config includes session paths and output folder**: saving a config now captures everything needed to reproduce a run; loading it re-populates the session list and output folder
- **Progress bars**: per-step/channel progress bar and per-session progress bar, always visible; driven by `on_progress` callback threaded through the conversion pipeline
- **CLI progress via tqdm**: step and session progress bars in the terminal; log output redirected through `tqdm` to prevent interleaving
- **Persistent settings**: last-used session directory and config file path remembered across restarts (via `QSettings`)
- **Multi-directory picker**: select multiple session folders in a single file dialog
- **Open Ephys session validation**: selected folders are validated as proper sessions before adding; accepts full session root (contains `Record Node *`) or a single experiment folder inside one
- **Human-readable Pydantic validation errors**: config errors shown as bullet-point lists instead of raw JSON
- **Version in window title**: both `oecon-gui` and `oecon-inspect` display the current version
- **Event counts in inspector**: number of events shown per event stream in the session tree
- **Dark theme**: Fusion style with explicit dark palette to avoid unreadable text under KDE light themes

### Fixed

- Config JSON filename now uses 1-based experiment/recording indices (`_exp1_rec1.config.json`) consistent with the DH5 output filename

---

## [0.1.5] and earlier

Initial development — conversion pipeline, CLI, pydantic config models, real-data integration tests.
