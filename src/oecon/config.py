import json
import logging
import os
from os import PathLike

from pydantic import BaseModel, Field, model_validator

from oecon.decimation import DecimationConfig
from oecon.events import EventPreprocessingConfig
from oecon.raw import RawConfig
from oecon.trialmap import TrialMapConfig
from oecon.mua import ContinuousMuaConfig

VERSION = 1

logger = logging.getLogger(__name__)


class SpikeCuttingConfig(BaseModel):
    pass


class OpenEphysToDhConfig(BaseModel):
    raw_config: RawConfig | None
    decimation_config: DecimationConfig | None
    event_config: EventPreprocessingConfig | None
    trialmap_config: TrialMapConfig | None
    spike_cutting_config: SpikeCuttingConfig | None
    continuous_mua_config: ContinuousMuaConfig | None
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
