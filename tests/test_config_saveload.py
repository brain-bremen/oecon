import os
from pathlib import Path
import tempfile
import pytest
import json


from oecon.config import (
    OpenEphysToDhConfig,
    RawConfig,
    DecimationConfig,
    EventPreprocessingConfig,
    TrialMapConfig,
    SpikeCuttingConfig,
    save_config_to_file,
    load_config_from_file,
    VERSION,
)
from oecon.mua import ContinuousMuaConfig


def make_sample_config():
    return OpenEphysToDhConfig(
        raw_config=RawConfig(),
        decimation_config=DecimationConfig(),
        event_config=EventPreprocessingConfig(),
        trialmap_config=TrialMapConfig(),
        spike_cutting_config=SpikeCuttingConfig(),
        continuous_mua_config=ContinuousMuaConfig()
    )


def test_save_and_load_config_roundtrip():
    config = make_sample_config()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(os.path.join(tmpdir, "test_config.json"))
        save_config_to_file(config_path, config)
        loaded_config = load_config_from_file(config_path)
        assert config == loaded_config
        assert loaded_config.raw_config == config.raw_config
        assert loaded_config.decimation_config == config.decimation_config
        assert loaded_config.event_config == config.event_config
        assert loaded_config.trialmap_config == config.trialmap_config


def test_save_config_creates_file():
    config = make_sample_config()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(os.path.join(tmpdir, "test_config.json"))
        save_config_to_file(config_path, config)
        assert os.path.exists(config_path)
        with open(config_path, "r") as f:
            data = f.read()
            assert '"raw_config"' in data
            assert '"decimation_config"' in data


def test_load_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_config_from_file(Path("nonexistent_config_file.json"))


def test_save_and_load_config_with_none_fields():
    config = OpenEphysToDhConfig(
        raw_config=None,
        decimation_config=None,
        event_config=None,
        trialmap_config=None,
        spike_cutting_config=None,
        continuous_mua_config=None
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(os.path.join(tmpdir, "test_config_none.json"))
        save_config_to_file(config_path, config)
        loaded_config = load_config_from_file(config_path)
        assert loaded_config.raw_config is None
        assert loaded_config.decimation_config is None
        assert loaded_config.event_config is None
        assert loaded_config.trialmap_config is None
        assert loaded_config.spike_cutting_config is None


def test_load_config_with_newer_version(tmp_path):
    # Create a config dict with a newer version than supported
    config_data = {
        "raw_config": None,
        "decimation_config": None,
        "event_config": None,
        "trialmap_config": None,
        "spike_cutting_config": None,
        "config_version": VERSION + 1,
    }
    config_path = tmp_path / "newer_version_config.json"
    with open(config_path, "w") as f:
        json.dump(config_data, f)
    import oecon.config as config_mod

    with pytest.raises(ValueError) as excinfo:
        config_mod.load_config_from_file(config_path)
    assert "newer than supported version" in str(excinfo.value)
