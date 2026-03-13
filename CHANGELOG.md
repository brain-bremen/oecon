# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **GUI** (`oecon-gui`): new PySide6 application for converting Open Ephys sessions, with groupboxes for Input, Output, Config, Progress, and Log
- **Session inspector** (`oecon-inspect`): new standalone GUI app for browsing Open Ephys sessions without converting; shows recordings, streams, channel names, and event counts per stream
- **Multi-session support**: multiple Open Ephys sessions can be added and converted in one run
- **Config includes session paths and output folder**: saving a config captures everything needed to reproduce a run; loading it re-populates the session list and output folder
- **Progress bars**: per-step/channel and per-session progress bars driven by an `on_progress` callback threaded through the conversion pipeline
- **CLI progress via tqdm**: step and session progress bars in the terminal; log output redirected through `tqdm` to prevent interleaving
- **Persistent settings**: last-used session directory and config file path remembered across restarts
- **Open Ephys session validation**: selected folders are validated as proper sessions; accepts full session root (contains `Record Node *`) or a single experiment folder inside one
- **Config validation**: invalid config values are now caught and reported as human-readable bullet-point lists

### Fixed

- Config JSON filename now uses 1-based experiment/recording indices (`_exp1_rec1.config.json`) consistent with the DH5 output filename

---

## [0.1.5] and earlier

Initial development — conversion pipeline, CLI, pydantic config models, real-data integration tests.
