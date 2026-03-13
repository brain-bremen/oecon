import numpy as np
import pytest
from pathlib import Path

from conftest import skip_if_no_data, DATA_FOLDER

_TTL_FOLDER = (
    DATA_FOLDER
    / "Record Node 101/experiment1/recording1/events/NI-DAQmx-110.USB-6343/TTL"
)

# VtlOn (VStim code 1000) + network_events_offset (1000) = 2000
VTLON_CODE = 2000
TTL_TOLERANCE_NS = 50_000_000  # 50 ms


@skip_if_no_data
def test_events_nonempty(golden_dh5):
    ev = golden_dh5.get_events_array()
    assert ev is not None and len(ev) > 0


@skip_if_no_data
def test_events_sorted(golden_dh5):
    ev = golden_dh5.get_events_array()
    assert np.all(np.diff(ev["time"]) >= 0), "Events are not sorted by timestamp"


@skip_if_no_data
def test_events_are_network_events(golden_dh5):
    """All events should be VStim network events (code >= 1000 after offset)."""
    ev = golden_dh5.get_events_array()
    assert np.all(ev["event"] >= 1000), "Found event codes below 1000 (unexpected TTL hardware events)"


@skip_if_no_data
def test_vtlon_matches_nidaqmx_ttl_timing(golden_dh5):
    """VtlOn network events should be within 50 ms of NI-DAQmx TTL rising edges."""
    ni_timestamps_s = np.load(_TTL_FOLDER / "timestamps.npy")
    ni_states = np.load(_TTL_FOLDER / "states.npy")
    rising_ts_ns = (ni_timestamps_s[ni_states == 1] * 1e9).astype(np.int64)

    ev = golden_dh5.get_events_array()
    vtlon_ts = ev["time"][ev["event"] == VTLON_CODE]

    assert len(vtlon_ts) > 0, "No VtlOn events found in DH5"
    assert len(vtlon_ts) == len(rising_ts_ns), (
        f"VtlOn count ({len(vtlon_ts)}) != NI-DAQ rising edges ({len(rising_ts_ns)})"
    )

    for t, n in zip(vtlon_ts, rising_ts_ns):
        delta_ns = n - t
        assert 0 < delta_ns <= TTL_TOLERANCE_NS, (
            f"VtlOn at {t/1e9:.3f}s: expected NI-DAQ rising edge 0–50 ms later, "
            f"got {delta_ns/1e6:.1f} ms"
        )
