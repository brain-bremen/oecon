import logging
from pathlib import Path

import dh5io
import dh5io.create
from open_ephys.analysis.recording import Recording

from oecon.config import (
    DecimationConfig,
    EventPreprocessingConfig,
    OpenEphysToDhConfig,
    RawConfig,
    TrialMapConfig,
    ContinuousMuaConfig,
    save_config_to_file,
)
from oecon.decimation import decimate_raw_data
from oecon.events import process_oe_events
from oecon.raw import process_oe_raw_data
from oecon.trialmap import process_oe_trialmap
from oecon.mua import extract_continuous_mua
from oecon.version import get_version_from_pyproject

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def convert_open_ephys_recording_to_dh5(
    recording: Recording,
    session_name: str,
    config: OpenEphysToDhConfig | None = None,
):
    assert recording.continuous is not None, (
        "No continuous data found in the recording."
    )

    if len(recording.continuous) == 0:
        raise ValueError(
            "No continuous data found in the recording. This is not supported."
        )

    board_names = [
        f"{cont.metadata.source_node_name}:{cont.metadata.source_node_id}"
        for cont in recording.continuous
    ]
    dh5filename = f"{session_name}_exp{recording.experiment_index + 1}_rec{recording.recording_index + 1}.dh5"
    logger.info(
        f"Start converting OpenEphys recording from {recording.directory} to {dh5filename} using oecon v{get_version_from_pyproject()}"
    )
    dh5file = dh5io.create.create_dh_file(
        dh5filename, overwrite=True, boards=board_names, validate=False
    )

    if config is None:
        config = OpenEphysToDhConfig(
            raw_config=None,  # RawConfig(split_channels_into_cont_blocks=True),
            decimation_config=DecimationConfig(),
            event_config=EventPreprocessingConfig(network_events_offset=1000),
            trialmap_config=TrialMapConfig(),
            continuous_mua_config=ContinuousMuaConfig(),
        )

    if config.raw_config is not None:
        config.raw_config = process_oe_raw_data(config.raw_config, recording, dh5file)

    if config.event_config is not None:
        config.event_config = process_oe_events(
            config.event_config, recording=recording, dh5file=dh5file
        )

    if config.trialmap_config is not None:
        config.trialmap_config = process_oe_trialmap(
            config.trialmap_config, recording=recording, dh5file=dh5file
        )

    if config.decimation_config is not None:
        config.decimation_config = decimate_raw_data(
            config.decimation_config, recording=recording, dh5file=dh5file
        )

    if config.continuous_mua_config is not None:
        decimation_config = config.decimation_config
        if decimation_config is None:
            decimation_config = DecimationConfig()

        config.continuous_mua_config = extract_continuous_mua(
            config=config.continuous_mua_config,
            decimation_config=decimation_config,
            recording=recording,
            dh5file=dh5file,
        )

    config_filename = Path(
        f"{session_name}_exp{recording.experiment_index}_rec{recording.recording_index}.config.json"
    )
    save_config_to_file(config_filename, config)

    logger.info(
        f"Finished converting OpenEphys recording from {recording.directory} to {dh5filename}"
    )
    # report resulting file size in a human readable format
