"""Lightweight inspection of an Open Ephys session (no data loading)."""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StreamInfo:
    name: str
    num_channels: int
    sample_rate: float
    duration_s: float | None  # derived from .dat file size


@dataclass
class RecordingInfo:
    experiment_index: int  # 0-based
    recording_index: int   # 0-based
    directory: str
    streams: list[StreamInfo] = field(default_factory=list)
    event_stream_names: list[str] = field(default_factory=list)

    @property
    def duration_s(self) -> float | None:
        """Duration of the first continuous stream, or None."""
        return self.streams[0].duration_s if self.streams else None

    @property
    def num_continuous_channels(self) -> int:
        return sum(s.num_channels for s in self.streams)

    @property
    def num_event_streams(self) -> int:
        return len(self.event_stream_names)


@dataclass
class SessionInfo:
    path: Path
    total_size_bytes: int
    recordings: list[RecordingInfo] = field(default_factory=list)

    @property
    def num_recordings(self) -> int:
        return len(self.recordings)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _folder_size(path: Path) -> int:
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for fname in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, fname))
            except OSError:
                pass
    return total


def _dat_duration(dat_path: str, num_channels: int, sample_rate: float) -> float | None:
    try:
        size = os.path.getsize(dat_path)
        num_samples = size // (num_channels * 2)  # int16 → 2 bytes
        return num_samples / sample_rate
    except OSError:
        return None


def _inspect_recording(rec_dir: str, exp_idx: int, rec_idx: int) -> RecordingInfo:
    oebin_path = os.path.join(rec_dir, "structure.oebin")
    streams: list[StreamInfo] = []
    if os.path.isfile(oebin_path):
        with open(oebin_path) as f:
            info = json.load(f)
        for cont in info.get("continuous", []):
            name = cont.get("stream_name") or cont.get("folder_name", "?")
            num_ch = int(cont.get("num_channels", 0))
            sr = float(cont.get("sample_rate", 0))
            dat = os.path.join(rec_dir, "continuous", cont["folder_name"], "continuous.dat")
            dur = _dat_duration(dat, num_ch, sr) if num_ch and sr else None
            streams.append(StreamInfo(name=name, num_channels=num_ch, sample_rate=sr, duration_s=dur))

    # Event streams: enumerate events/*/TTL* directories
    event_names: list[str] = []
    for d in sorted(glob.glob(os.path.join(rec_dir, "events", "*", "TTL*"))):
        parent = os.path.basename(os.path.dirname(d))
        stream = ".".join(parent.split(".")[1:]) or parent  # strip node prefix
        if stream not in event_names:
            event_names.append(stream)

    return RecordingInfo(
        experiment_index=exp_idx,
        recording_index=rec_idx,
        directory=rec_dir,
        streams=streams,
        event_stream_names=event_names,
    )


def _find_recordings(node_dir: str) -> list[tuple[int, int, str]]:
    """Return (exp_idx, rec_idx, path) for all recordings in a record-node dir."""
    result = []
    exp_dirs = sorted(glob.glob(os.path.join(node_dir, "experiment*")))
    for exp_idx, exp_dir in enumerate(exp_dirs):
        rec_dirs = sorted(glob.glob(os.path.join(exp_dir, "recording*")))
        for rec_idx, rec_dir in enumerate(rec_dirs):
            result.append((exp_idx, rec_idx, rec_dir))
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def inspect_session(session_path: Path) -> SessionInfo:
    """Return a :class:`SessionInfo` for the given Open Ephys session folder.

    This function only reads metadata (JSON + file sizes) — it does not
    memory-map or load any signal data.
    """
    size = _folder_size(session_path)
    recordings: list[RecordingInfo] = []

    node_dirs = sorted(glob.glob(str(session_path / "Record Node *")))
    if not node_dirs:
        node_dirs = [str(session_path)]

    for node_dir in node_dirs:
        for exp_idx, rec_idx, rec_dir in _find_recordings(node_dir):
            recordings.append(_inspect_recording(rec_dir, exp_idx, rec_idx))

    return SessionInfo(path=session_path, total_size_bytes=size, recordings=recordings)


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n //= 1024
    return f"{n:.1f} PB"


def _fmt_duration(s: float | None) -> str:
    if s is None:
        return "?"
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _fmt_rate(hz: float) -> str:
    return f"{hz / 1000:.1f} kHz" if hz >= 1000 else f"{hz:.0f} Hz"


def format_session_info(info: SessionInfo) -> str:
    """Return a human-readable summary string of *info*."""
    lines: list[str] = []
    lines.append(f"Session : {info.path.name}")
    lines.append(f"Size    : {_fmt_size(info.total_size_bytes)}")
    lines.append(f"Recordings: {info.num_recordings}")

    for rec in info.recordings:
        lines.append(
            f"\n  Exp {rec.experiment_index + 1} / Rec {rec.recording_index + 1}"
            f"  [{_fmt_duration(rec.duration_s)}]"
        )
        if rec.streams:
            stream_parts = [
                f"{s.name} ({s.num_channels} ch, {_fmt_rate(s.sample_rate)})"
                for s in rec.streams
            ]
            lines.append(f"    Continuous : {',  '.join(stream_parts)}")
        else:
            lines.append("    Continuous : —")
        if rec.event_stream_names:
            lines.append(f"    Events     : {',  '.join(rec.event_stream_names)}")
        else:
            lines.append("    Events     : —")

    return "\n".join(lines)
