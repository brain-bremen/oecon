# oecon — Open Ephys Converter

Converts [Open Ephys GUI](https://open-ephys.github.io/gui-docs/index.html) recordings into
[DAQ-HDF5](https://github.com/cog-neurophys-lab/DAQ-HDF5) (DH5) format.

Conversion steps: LFP decimation, MUA/ESA envelope, TTL events, VStim network events, trial map, raw data copy.

## Installation

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv tool install oecon
```
or for the latest development version:

```bash
uv tool install git+https://github.com/brain-bremen/oecon.git
```

### Update

```bash
uv tool upgrade oecon
```

## GUI

```bash
oecon-gui       # converter
oecon-inspect   # session browser
```

Configs save session paths, output folder, and all step parameters — enough to reproduce a run.

## CLI

```bash
oecon <session_path> [<session_path> ...]
oecon <session_path> --config config.json --output-folder /out
oecon <session_path> --inspect
```

## Library

```python
from oecon import convert_open_ephys_session
convert_open_ephys_session("/path/to/session")
```

## Default CONT block ranges

| Range       | Purpose |
|---|---|
|    1 – 2000 | Raw neural/analog data |
| 2001 – 3600 | LFP |
| 3601 – 4000 | Downsampled analog |
| 4001 – 5600 | MUA/ESA |
| 6001 – 7600 | High-pass filtered raw (reserved) |

Sorted spikes: SPIKE 1–1000.
