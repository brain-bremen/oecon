"""Tests for trialmap.py module, especially Operation writing."""
import h5py
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from vstim.tdr import TrialOutcome

from oecon.trialmap import (
    TrialMapConfig,
    process_oe_trialmap,
    parse_trial_start_message,
    parse_trial_end_message,
    TrialStartMessage,
    TrialEndMessage,
    BRAINBOX_OUTCOME_MAPPING,
)
from oecon.events import Messages
from dh5io import DH5File
from dh5io.create import create_dh_file


@pytest.fixture
def mock_recording():
    """Create a mock Recording object."""
    recording = Mock()
    recording.directory = Path("/fake/path")
    recording.info = {
        "events": [
            {
                "source_processor": "Message Center",
                "folder_name": "events",
                "stream_name": "messages",
            }
        ]
    }
    return recording


@pytest.fixture
def mock_messages():
    """Create mock trial messages."""
    from oecon.events import EventMetadata

    metadata = EventMetadata(
        channel_name="messages",
        folder_name="MessageCenter",
        identifier="message-center.messages",
        sample_rate=30000.0,
        stream_name="messages",
        type="Messages",
        description="Message Center messages",
        source_processor="Message Center",
    )

    messages = Messages(
        metadata=metadata,
        text=np.array([
            b"VSTIM: TRIAL_START 1 TRIALTYPE 0 TIMESEQUENCE 0 FRAME 1032",
            b"VSTIM: TRIAL_END 1 TRIALTYPE 0 TIMESEQUENCE 0 FRAME 2048 OUTCOME 1",
            b"VSTIM: TRIAL_START 2 TRIALTYPE 1 TIMESEQUENCE 1 FRAME 3064",
            b"VSTIM: TRIAL_END 2 TRIALTYPE 1 TIMESEQUENCE 1 FRAME 4080 OUTCOME 5",
        ]),
        timestamps=np.array([1.0, 2.0, 3.0, 4.0]),
        sample_numbers=np.array([30000, 60000, 90000, 120000]),
    )
    return messages


@pytest.fixture
def tmp_dh5_file(tmp_path):
    """Create a temporary DH5 file for testing."""
    dh5_path = tmp_path / "test.dh5"

    # Create a proper DH5 file with valid structure
    dh5file = create_dh_file(str(dh5_path), overwrite=True, validate=True)
    yield dh5file
    # DH5File will be closed automatically when the h5py file is closed


class TestTrialMessageParsing:
    """Tests for trial message parsing functions."""

    def test_parse_trial_start_message(self):
        msg = "TRIAL_START 1 TRIALTYPE 0 TIMESEQUENCE 0 FRAME 1032"
        result = parse_trial_start_message(msg)

        assert isinstance(result, TrialStartMessage)
        assert result.trial_index == 1
        assert result.trial_type_number == 0
        assert result.time_sequence_index == 0
        assert result.frame_number == 1032

    def test_parse_trial_end_message(self):
        msg = "TRIAL_END 1 TRIALTYPE 0 TIMESEQUENCE 0 FRAME 2048 OUTCOME 1"
        result = parse_trial_end_message(msg)

        assert isinstance(result, TrialEndMessage)
        assert result.trial_index == 1
        assert result.trial_type_number == 0
        assert result.frame_number == 2048
        assert result.outcome == TrialOutcome.Hit


class TestTrialmapOperation:
    """Tests for Operation creation in trialmap processing."""

    @patch('oecon.trialmap.get_messages_from_recording')
    def test_trialmap_creates_operation(self, mock_get_messages, tmp_dh5_file, mock_recording, mock_messages):
        """Verify that process_oe_trialmap creates an Operation in the DH5 file."""
        from oecon.file_writer import DH5Writer

        mock_get_messages.return_value = mock_messages

        config = TrialMapConfig(
            use_message_center_messages=True,
            trial_start_ttl_line=None,
        )

        # Wrap DH5File in a DH5Writer
        file_writer = DH5Writer(tmp_dh5_file)

        # Process trialmap
        result_config = process_oe_trialmap(config, mock_recording, file_writer)

        # Check that Operation was created
        operations = list(tmp_dh5_file._file["/Operations"].keys())
        trialmap_ops = [op for op in operations if "Write trialmap" in op]

        assert len(trialmap_ops) == 1, "Should create exactly one 'Write trialmap' operation"

        # Check operation attributes
        operation_group = tmp_dh5_file._file[f"/Operations/{trialmap_ops[0]}"]
        assert "Date" in operation_group.attrs
        assert "Operator name" in operation_group.attrs
        assert "Tool" in operation_group.attrs
        assert "oecon.trialmap" in operation_group.attrs["Tool"]
        assert "(v" in operation_group.attrs["Tool"]  # Check version format

    @patch('oecon.trialmap.get_messages_from_recording')
    def test_vstim_outcome_attributes_are_int32(self, mock_get_messages, tmp_dh5_file, mock_recording, mock_messages):
        """Verify that vstim.tdr.TrialOutcome names are written as int32."""
        from oecon.file_writer import DH5Writer

        mock_get_messages.return_value = mock_messages

        config = TrialMapConfig(
            use_message_center_messages=True,
            trial_start_ttl_line=None,
        )

        # Wrap DH5File in a DH5Writer
        file_writer = DH5Writer(tmp_dh5_file)

        # Process trialmap
        process_oe_trialmap(config, mock_recording, file_writer)

        # Check TRIALMAP dataset attributes
        trialmap_dataset = tmp_dh5_file._file["/TRIALMAP"]
        for outcome in TrialOutcome:
            assert outcome.name in trialmap_dataset.attrs, f"Missing outcome in dataset: {outcome.name}"
            attr_value = trialmap_dataset.attrs[outcome.name]
            assert isinstance(attr_value, (np.int32, int)), f"{outcome.name} should be int32"
            assert attr_value == outcome.value, f"{outcome.name} value mismatch"

        # Check Operation attributes
        operations = list(tmp_dh5_file._file["/Operations"].keys())
        trialmap_op = [op for op in operations if "Write trialmap" in op][0]
        operation_group = tmp_dh5_file._file[f"/Operations/{trialmap_op}"]

        for outcome in TrialOutcome:
            assert outcome.name in operation_group.attrs, f"Missing outcome in operation: {outcome.name}"
            attr_value = operation_group.attrs[outcome.name]
            assert isinstance(attr_value, (np.int32, int)), f"{outcome.name} should be int32"
            assert attr_value == outcome.value, f"{outcome.name} value mismatch"

    @patch('oecon.trialmap.get_messages_from_recording')
    def test_brainbox_outcome_names_optional(self, mock_get_messages, tmp_dh5_file, mock_recording, mock_messages):
        """Verify that BrainBox outcome names are added when configured."""
        from oecon.file_writer import DH5Writer
        from oecon.config import DH5OutputOptions

        mock_get_messages.return_value = mock_messages

        config = TrialMapConfig(
            use_message_center_messages=True,
            trial_start_ttl_line=None,
        )

        # Wrap DH5File in a DH5Writer with BrainBox names enabled
        dh5_options = DH5OutputOptions(add_brainbox_outcome_names=True)
        file_writer = DH5Writer(tmp_dh5_file, options=dh5_options)

        # Process trialmap
        process_oe_trialmap(config, mock_recording, file_writer)

        # Check TRIALMAP dataset
        trialmap_dataset = tmp_dh5_file._file["/TRIALMAP"]

        # Check that vstim names are present as int32 in dataset
        for outcome in TrialOutcome:
            assert outcome.name in trialmap_dataset.attrs
            assert isinstance(trialmap_dataset.attrs[outcome.name], (np.int32, int))

        # Check that BrainBox names are present as float64 in dataset
        for bb_name, vstim_outcome in BRAINBOX_OUTCOME_MAPPING.items():
            assert bb_name in trialmap_dataset.attrs, f"Missing BrainBox name in dataset: {bb_name}"
            attr_value = trialmap_dataset.attrs[bb_name]
            assert isinstance(attr_value, (np.float64, float)), f"{bb_name} should be float64"
            assert attr_value == float(vstim_outcome.value), f"{bb_name} should map to vstim code {vstim_outcome.value}"

        # Check Operation (only vstim names, not BrainBox names)
        operations = list(tmp_dh5_file._file["/Operations"].keys())
        trialmap_op = [op for op in operations if "Write trialmap" in op][0]
        operation_group = tmp_dh5_file._file[f"/Operations/{trialmap_op}"]

        # Check that vstim names are present as int32 in operation
        for outcome in TrialOutcome:
            assert outcome.name in operation_group.attrs
            assert isinstance(operation_group.attrs[outcome.name], (np.int32, int))

    @patch('oecon.trialmap.get_messages_from_recording')
    def test_brainbox_names_not_added_when_disabled(self, mock_get_messages, tmp_dh5_file, mock_recording, mock_messages):
        """Verify that BrainBox names are NOT added when add_brainbox_outcome_names=False."""
        from oecon.file_writer import DH5Writer
        from oecon.config import DH5OutputOptions

        mock_get_messages.return_value = mock_messages

        config = TrialMapConfig(
            use_message_center_messages=True,
            trial_start_ttl_line=None,
        )

        # Wrap DH5File in a DH5Writer with BrainBox names disabled (default)
        dh5_options = DH5OutputOptions(add_brainbox_outcome_names=False)
        file_writer = DH5Writer(tmp_dh5_file, options=dh5_options)

        # Process trialmap
        process_oe_trialmap(config, mock_recording, file_writer)

        # Check TRIALMAP dataset - BrainBox names should NOT be present when disabled
        trialmap_dataset = tmp_dh5_file._file["/TRIALMAP"]
        for bb_name in BRAINBOX_OUTCOME_MAPPING.keys():
            assert bb_name not in trialmap_dataset.attrs, f"BrainBox name {bb_name} should not be in dataset when disabled"

        # Vstim outcome names should still be present (always added)
        for outcome in TrialOutcome:
            assert outcome.name in trialmap_dataset.attrs

    @patch('oecon.trialmap.get_messages_from_recording')
    def test_brainbox_mapping_correctness(self, mock_get_messages, tmp_dh5_file, mock_recording, mock_messages):
        """Verify that BrainBox outcome names map to the correct vstim codes."""
        from oecon.file_writer import DH5Writer
        from oecon.config import DH5OutputOptions

        mock_get_messages.return_value = mock_messages

        config = TrialMapConfig(
            use_message_center_messages=True,
            trial_start_ttl_line=None,
        )

        # Wrap DH5File in a DH5Writer with BrainBox names enabled
        dh5_options = DH5OutputOptions(add_brainbox_outcome_names=True)
        file_writer = DH5Writer(tmp_dh5_file, options=dh5_options)

        # Process trialmap
        process_oe_trialmap(config, mock_recording, file_writer)

        # Verify mapping
        expected_mapping = {
            "SUCCESS": TrialOutcome.Hit,       # 1
            "EARLY": TrialOutcome.Early,       # 5
            "LATE": TrialOutcome.Late,         # 6
            "EYE_ERROR": TrialOutcome.EyeErr,  # 7
        }

        # Check TRIALMAP dataset
        trialmap_dataset = tmp_dh5_file._file["/TRIALMAP"]
        for bb_name, expected_outcome in expected_mapping.items():
            attr_value = trialmap_dataset.attrs[bb_name]
            assert attr_value == float(expected_outcome.value), (
                f"{bb_name} should map to {expected_outcome.name} (value={expected_outcome.value}) in dataset"
            )

        # Note: BrainBox names are only added to TRIALMAP dataset, not to Operation attributes
        # Operation only contains vstim outcome names
