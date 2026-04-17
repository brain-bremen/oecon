from conftest import skip_if_no_data

N_CHANNELS = 2
N_SAMPLES = 1_774_200
RAW_CONT_IDS = [1, 2]  # Raw data now goes to RAW range (1-1600), not ANALOG range


@skip_if_no_data
def test_raw_cont_ids(golden_dh5):
    ids = golden_dh5.get_cont_group_ids()
    for cont_id in RAW_CONT_IDS:
        assert cont_id in ids, f"Expected raw CONT block {cont_id} not found"


@skip_if_no_data
def test_raw_sample_count(golden_dh5):
    for cont_id in RAW_CONT_IDS:
        cont = golden_dh5.get_cont_group_by_id(cont_id)
        assert cont.n_samples == N_SAMPLES, (
            f"CONT {cont_id}: expected {N_SAMPLES} samples, got {cont.n_samples}"
        )
