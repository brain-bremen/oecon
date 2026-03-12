import numpy as np
from conftest import skip_if_no_data

N_TRIALS = 12


@skip_if_no_data
def test_trialmap_nonempty(golden_dh5):
    tm = golden_dh5.get_trialmap()
    assert tm is not None and len(tm) > 0


@skip_if_no_data
def test_trialmap_trial_count(golden_dh5):
    tm = golden_dh5.get_trialmap()
    assert len(tm) == N_TRIALS, f"Expected {N_TRIALS} trials, got {len(tm)}"


@skip_if_no_data
def test_trialmap_positive_durations(golden_dh5):
    tm = golden_dh5.get_trialmap()
    durations_s = tm.end_time_float_seconds - tm.start_time_float_seconds
    assert np.all(durations_s > 0), "Some trials have non-positive duration"


@skip_if_no_data
def test_trialmap_sequential_trial_numbers(golden_dh5):
    tm = golden_dh5.get_trialmap()
    assert np.all(np.diff(tm.trial_numbers) == 1), "Trial numbers are not sequential"
