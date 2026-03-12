import logging
from enum import StrEnum

import dh5io
import dh5io.cont
import dh5io.operations
import dhspec
import numpy as np
import scipy.signal as signal
from dh5io import DH5File
from open_ephys.analysis.recording import Recording
from pydantic import BaseModel, field_validator

import oecon.version
from oecon.scaling import scale_to_16_bit_range

logger = logging.getLogger(__name__)


class FilterType(StrEnum):
    FIR = "fir"
    IIR = "iir"


class DecimationConfig(BaseModel):
    downsampling_factor: int = 30
    ftype: FilterType = FilterType.FIR
    zero_phase: bool = True
    filter_order: int | None = 600
    included_channel_names: list[str] | None = None  # doall if None
    start_block_id: int = 2001
    scale_max_abs_to: int | None = None

    @field_validator("downsampling_factor")
    @classmethod
    def factor_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("downsampling_factor must be >= 1")
        return v


def decimate_np_array(
    data, downsampling_factor, filter_order, filter_type, axis, zero_phase: bool
):
    return signal.decimate(
        x=data,
        q=downsampling_factor,
        n=filter_order,
        ftype=filter_type,
        axis=axis,
        zero_phase=zero_phase,
    )


def decimate_raw_data(
    config: DecimationConfig, recording: Recording, dh5file: DH5File
) -> DecimationConfig:
    assert recording.continuous is not None, (
        "No continuous data found in the recording."
    )

    global_channel_index = 0
    dh5_cont_id = config.start_block_id
    included_channel_names: list[str] = []

    for oe_cont in recording.continuous:
        oe_metadata = oe_cont.metadata

        assert oe_metadata.channel_names is not None, (
            "Channel names are not set in OE data."
        )

        if config.included_channel_names is None:
            logger.debug("No channel selection provided, selecting all channels")
            included_channel_names.extend(oe_metadata.channel_names)
        else:
            included_channel_names.extend(config.included_channel_names)

        # TODO: Use chunks of channels in parallel
        logger.info(
            f"Decimating ({oe_metadata.sample_rate} -> {oe_metadata.sample_rate / config.downsampling_factor} Hz) {oe_metadata.num_channels} channels continuous data from {oe_metadata.source_node_name} ({oe_metadata.source_node_id})"
        )
        for channel_index, channel_name in enumerate(oe_metadata.channel_names):
            # skip channel if not in included channels
            if channel_name not in included_channel_names:
                continue

            samples = oe_cont.get_samples(
                start_sample_index=0,
                end_sample_index=-1,
                selected_channels=None,
                selected_channel_names=[channel_name],
            )
            # samples x channels
            decimated_samples = decimate_np_array(
                data=samples,
                downsampling_factor=config.downsampling_factor,
                filter_order=config.filter_order,
                filter_type=config.ftype,
                axis=0,
                zero_phase=config.zero_phase,
            )

            channel_info = dhspec.cont.create_channel_info(
                GlobalChanNumber=global_channel_index,
                BoardChanNo=channel_index,
                ADCBitWidth=16,
                MaxVoltageRange=10.0,
                MinVoltageRange=10.0,
                AmplifChan0=0,
            )

            logger.debug(f"Data range: {np.min(samples)} - {np.max(samples)}")
            if config.scale_max_abs_to is not None:
                decimated_samples, scaling_factor = scale_to_16_bit_range(
                    decimated_samples
                )
            else:
                # use original scaling factor (bit_volts)
                scaling_factor = oe_cont.metadata.bit_volts[channel_index]
                decimated_samples /= scaling_factor
                decimated_samples = decimated_samples.astype(np.int16)

            region_index = dhspec.cont.create_empty_index_array(1)
            region_index[0]["time"] = np.int64(oe_cont.timestamps[0] * 1e9)
            region_index[0]["offset"] = 0

            dh5io.cont.create_cont_group_from_data_in_file(
                file=dh5file._file,
                cont_group_id=dh5_cont_id,
                data=decimated_samples,
                index=region_index,
                sample_period_ns=np.int32(
                    1.0 / oe_metadata.sample_rate * 1e9 * config.downsampling_factor
                ),
                name=f"{oe_metadata.stream_name}/{channel_name}/LFP",
                channels=channel_info,
                calibration=np.array(np.float64(scaling_factor)),
            )

            dh5_cont_id += 1
            global_channel_index += 1

    dh5io.operations.add_operation_to_file(
        dh5file._file,
        "decimate_raw_data",
        f"oecon_v{oecon.version.get_version_from_pyproject()}",
    )

    config.included_channel_names = included_channel_names
    return config
