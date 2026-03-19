import json
import logging
import os
from enum import StrEnum
from os import PathLike
from typing import Any

from pydantic import BaseModel, Field, model_validator

from oecon.decimation import DecimationConfig
from oecon.events import EventPreprocessingConfig
from oecon.raw import RawConfig
from oecon.trialmap import TrialMapConfig
from oecon.mua import ContinuousMuaConfig

VERSION = 1

logger = logging.getLogger(__name__)


class SpikeConfig(BaseModel):
    pass  # fields added later


class OutputFormat(StrEnum):
    DH5 = "dh5"
    NWB = "nwb"


class DH5OutputOptions(BaseModel):
    """DH5-specific output configuration."""

    validate_structure: bool = Field(
        default=True,
        description="Validate DH5 structure after creation",
    )
    compression: str | None = Field(
        default=None,
        description="HDF5 compression algorithm (e.g., 'gzip', 'lzf')",
    )
    add_brainbox_outcome_names: bool = Field(
        default=False,
        title="Add BrainBox Outcome Names",
        description="Add BrainBox-compatible outcome names (SUCCESS, EARLY, LATE, EYE_ERROR) "
        "as float64 attributes. Required for backwards compatibility with MATLAB toolbox.",
    )


class NWBOutputOptions(BaseModel):
    """NWB-specific output configuration."""

    experimenter: list[str] = Field(
        default_factory=lambda: ["Unknown"],
        description="Names of experimenters",
    )
    institution: str = Field(
        default="Unknown",
        description="Institution name",
    )
    lab: str = Field(
        default="Unknown",
        description="Lab name",
    )
    session_description: str = Field(
        default="Open Ephys recording",
        description="Description of the recording session",
    )
    use_lfp_extension: bool = Field(
        default=True,
        description="Use ndx-lfp extension for LFP data",
    )
    electrode_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional electrode metadata",
    )


class OpenEphysToDhConfig(BaseModel):
    # Processing configurations (format-agnostic)
    raw_config: RawConfig | None = None
    decimation_config: DecimationConfig | None = None
    event_config: EventPreprocessingConfig | None = None
    trialmap_config: TrialMapConfig | None = None
    continuous_mua_config: ContinuousMuaConfig | None = None
    spike_config: SpikeConfig | None = None

    # Output format selection
    output_format: OutputFormat = OutputFormat.DH5

    # Format-specific output options
    dh5_output_options: DH5OutputOptions | None = Field(
        default_factory=DH5OutputOptions,
        description="DH5-specific output options (used only when output_format is DH5)",
    )
    nwb_output_options: NWBOutputOptions | None = Field(
        default_factory=NWBOutputOptions,
        description="NWB-specific output options (used only when output_format is NWB)",
    )

    # General settings
    n_jobs: int = 1
    config_version: int = VERSION
    oecon_version: str = Field(
        default_factory=lambda: __import__(
            "oecon.version"
        ).version.get_version_from_pyproject()
    )

    @model_validator(mode="after")
    def set_oecon_version(self) -> "OpenEphysToDhConfig":
        self.oecon_version = __import__(
            "oecon.version"
        ).version.get_version_from_pyproject()
        return self


def save_config_to_file(config_filename: PathLike, config: OpenEphysToDhConfig) -> None:
    logger.info(f"Saving configration to {config_filename}")
    with open(config_filename, mode="w") as config_file:
        config_file.write(config.model_dump_json(indent=2))


def load_config_from_file(config_path: PathLike) -> OpenEphysToDhConfig:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    logger.info(f"Loading configuration from {config_path}")
    with open(config_path, "r") as f:
        config_data = json.load(f)

    if "config_version" not in config_data:
        logger.warning(
            "Configuration file does not contain a version. Assuming version {VERSION}. This may fail."
        )
        config_data["config_version"] = VERSION

    if config_data["config_version"] > VERSION:
        raise ValueError(
            f"Configuration file version {config_data['config_version']} is newer than supported version {VERSION}."
        )

    return OpenEphysToDhConfig.model_validate(config_data)
