# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This project uses `uv` for environment and dependency management.

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_decimation.py

# Run a single test by name
uv run pytest tests/test_decimation.py::TestDecimateNpArray::test_decimate_np_array_basic

# Run the CLI tool
uv run oecon <oe_session_path>
uv run oecon <oe_session_path> --config config.json --output-folder /output/dir

# Type checking
uv run mypy src/
```

## Architecture

**OEcon** converts [Open Ephys GUI](https://open-ephys.github.io/gui-docs/) binary recordings into the in-house DAQ-HDF5 (DH5) format used by the cognitive neurophysiology lab.

### Conversion pipeline

The main entry point is `convert_open_ephys_recording_to_dh5()` in `src/oecon/convert_open_ephys_to_dh5.py`. It orchestrates the following steps, each controlled by a config dataclass that is `None` to skip that step:

1. **Raw data** (`raw.py`, `RawConfig`) — copies continuous data into DH5 CONT blocks
2. **Events** (`events.py`, `EventPreprocessingConfig`) — extracts TTL triggers (NI-DAQmx / Acquisition Board) and Network Events (VStim), merges and sorts by timestamp, stores as DH5 event triggers
3. **Trial map** (`trialmap.py`, `TrialMapConfig`) — parses `TRIAL_START`/`TRIAL_END` messages from the Open Ephys Message Center (sent by VStim) and writes a structured trial map to DH5
4. **Decimation** (`decimation.py`, `DecimationConfig`) — FIR/IIR anti-alias filter + downsample to produce LFP data; default factor 30×, stored starting at CONT block 2001
5. **Continuous MUA** (`mua.py`, `ContinuousMuaConfig`) — extracts MUA/ESA envelope from raw data; stored starting at CONT block 4001

Each processing function takes a `(config, recording, dh5file)` signature and returns the (potentially updated) config, which is then serialised alongside each output file as `<session>_exp<n>_rec<n>.config.json`.

### Configuration

`OpenEphysToDhConfig` (in `src/oecon/config.py`) is the top-level config dataclass — a container of all per-step configs. It serialises/deserialises via `save_config_to_file` / `load_config_from_file` using plain JSON. Enums are not yet fully handled in round-trip deserialization (see TODO in `config.py`).

### Event types

Three event classes in `events.py`:
- `Event` — TTL events with `full_words`, `states`, `sample_numbers`, `timestamps`
- `FullWordEvent` — Network Events after deduplication (no `states` field)
- `Messages` — Open Ephys Message Center text messages

`event_from_eventfolder()` dispatches on `metadata.source_processor` to return the appropriate type.

### Output file naming

Each Open Ephys recording produces one DH5 file and config JSON:
```
<session_name>_exp<experiment_index+1>_rec<recording_index+1>.dh5
<session_name>_exp<experiment_index+1>_rec<recording_index+1>.config.json
```
Both use 1-based indexing in the filenames (exp1, rec1, etc.).

### Tests

Real-data integration tests in `tests/test_realdata.py` are **skipped** unless `tests/data/Test/` exists (an actual Open Ephys session folder). All other tests use mocks or synthetic data and run without external data.

The `pytest-plt` fixture (`plt`) is available in tests for inline plotting during development — tests using it will generate plot files when run with `--plt`.
