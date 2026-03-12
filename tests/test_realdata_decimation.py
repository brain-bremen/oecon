from conftest import skip_if_no_data

N_SAMPLES_RAW = 1_774_200
DOWNSAMPLING_FACTOR = 30
N_SAMPLES_LFP = N_SAMPLES_RAW // DOWNSAMPLING_FACTOR  # 59140
SAMPLE_PERIOD_NS = 1_000_000  # 1 kHz → 1 ms period
LFP_CONT_IDS = [2001, 2002]


@skip_if_no_data
def test_decimation_cont_ids(golden_dh5):
    ids = golden_dh5.get_cont_group_ids()
    for cont_id in LFP_CONT_IDS:
        assert cont_id in ids, f"Expected LFP CONT block {cont_id} not found"


@skip_if_no_data
def test_decimation_sample_count(golden_dh5):
    for cont_id in LFP_CONT_IDS:
        cont = golden_dh5.get_cont_group_by_id(cont_id)
        assert abs(cont.n_samples - N_SAMPLES_LFP) <= 2, (
            f"CONT {cont_id}: expected ~{N_SAMPLES_LFP} samples, got {cont.n_samples}"
        )


@skip_if_no_data
def test_decimation_sample_period(golden_dh5):
    for cont_id in LFP_CONT_IDS:
        cont = golden_dh5.get_cont_group_by_id(cont_id)
        assert cont.sample_period == SAMPLE_PERIOD_NS, (
            f"CONT {cont_id}: expected sample_period {SAMPLE_PERIOD_NS} ns, got {cont.sample_period}"
        )
