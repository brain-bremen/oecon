import logging
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import dh5io
import dh5io.cont
import dh5io.operations
import dhspec
import numpy as np
import scipy.signal as signal
from dh5io import DH5File
from open_ephys.analysis.recording import Recording

import oecon.version
from oecon.scaling import scale_to_16_bit_range

logger = logging.getLogger(__name__)


@dataclass
class DecimationConfig:
    downsampling_factor: int = 30
    ftype: str = "fir"
    zero_phase: bool = True
    filter_order: int | None = 600
    included_channel_names: list[str] | None = None  # doall if None
    start_block_id: int = 2001
    scale_max_abs_to: np.int16 | None = None
    max_workers: int = 4  # Number of parallel workers for channel processing


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


def _process_single_channel(args):
    """Process a single channel - separated for parallel execution"""
    (
        channel_index,
        channel_name,
        oe_cont,
        config,
        global_channel_index,
        dh5_cont_id,
        included_channel_names,
    ) = args

    # skip channel if not in included channels
    if channel_name not in included_channel_names:
        return None

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
        decimated_samples, scaling_factor = scale_to_16_bit_range(decimated_samples)
    else:
        # use original scaling factor (bit_volts)
        scaling_factor = oe_cont.metadata.bit_volts[channel_index]
        decimated_samples /= scaling_factor
        decimated_samples = decimated_samples.astype(np.int16)

    region_index = dhspec.cont.create_empty_index_array(1)
    region_index[0]["time"] = np.int64(oe_cont.timestamps[0] * 1e9)
    region_index[0]["offset"] = 0

    # Return processed data instead of writing directly
    return {
        "dh5_cont_id": dh5_cont_id,
        "data": decimated_samples,
        "index": region_index,
        "sample_period_ns": np.int32(
            1.0 / oe_cont.metadata.sample_rate * 1e9 * config.downsampling_factor
        ),
        "name": f"{oe_cont.metadata.stream_name}/{channel_name}/LFP",
        "channels": channel_info,
        "calibration": np.array(np.float64(scaling_factor)),
    }


def _decimate_channels_parallel(
    oe_cont,
    oe_metadata,
    config,
    dh5file,
    included_channel_names,
    global_channel_index,
    dh5_cont_id,
):
    """Process channels in parallel with thread-safe HDF5 writing"""

    # Prepare arguments for parallel processing
    channel_args = []
    current_global_idx = global_channel_index
    current_dh5_id = dh5_cont_id

    for channel_index, channel_name in enumerate(oe_metadata.channel_names):
        if channel_name in included_channel_names:
            channel_args.append(
                (
                    channel_index,
                    channel_name,
                    oe_cont,
                    config,
                    current_global_idx,
                    current_dh5_id,
                    included_channel_names,
                )
            )
            current_global_idx += 1
            current_dh5_id += 1

    # Process channels in parallel
    processed_results = []
    max_workers = min(
        len(channel_args), config.max_workers
    )  # Use configurable max workers

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_channel = {
            executor.submit(_process_single_channel, args): args[1]
            for args in channel_args
        }

        for future in as_completed(future_to_channel):
            channel_name = future_to_channel[future]
            try:
                result = future.result()
                if result is not None:
                    processed_results.append(result)
            except Exception as exc:
                logger.error(f"Channel {channel_name} generated an exception: {exc}")
                raise

    # Sort results by dh5_cont_id to maintain order
    processed_results.sort(key=lambda x: x["dh5_cont_id"])

    # Write results to HDF5 file sequentially (thread-safe)
    hdf5_lock = threading.Lock()
    for result in processed_results:
        with hdf5_lock:
            dh5io.cont.create_cont_group_from_data_in_file(
                file=dh5file._file,
                cont_group_id=result["dh5_cont_id"],
                data=result["data"],
                index=result["index"],
                sample_period_ns=result["sample_period_ns"],
                name=result["name"],
                channels=result["channels"],
                calibration=result["calibration"],
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

        logger.info(
            f"Decimating ({oe_metadata.sample_rate} -> {oe_metadata.sample_rate / config.downsampling_factor} Hz) {oe_metadata.num_channels} channels continuous data from {oe_metadata.source_node_name} ({oe_metadata.source_node_id})"
        )

        # Use parallel processing for channel decimation
        _decimate_channels_parallel(
            oe_cont=oe_cont,
            oe_metadata=oe_metadata,
            config=config,
            dh5file=dh5file,
            included_channel_names=included_channel_names,
            global_channel_index=global_channel_index,
            dh5_cont_id=dh5_cont_id,
        )

        # Update counters for next stream
        num_processed_channels = sum(
            1 for name in oe_metadata.channel_names if name in included_channel_names
        )
        dh5_cont_id += num_processed_channels
        global_channel_index += num_processed_channels

    dh5io.operations.add_operation_to_file(
        dh5file._file,
        "decimate_raw_data",
        f"oecon_v{oecon.version.get_version_from_pyproject()}",
    )

    config.included_channel_names = included_channel_names
    return config
