from conftest import skip_if_no_data

N_SAMPLES_RAW = 1_774_200
DOWNSAMPLING_FACTOR = 30
N_SAMPLES_MUA = N_SAMPLES_RAW // DOWNSAMPLING_FACTOR  # 59140
MUA_CONT_IDS = [4001, 4002]


@skip_if_no_data
def test_mua_cont_ids(golden_dh5):
    ids = golden_dh5.get_cont_group_ids()
    for cont_id in MUA_CONT_IDS:
        assert cont_id in ids, f"Expected MUA CONT block {cont_id} not found"


@skip_if_no_data
def test_mua_sample_count(golden_dh5):
    for cont_id in MUA_CONT_IDS:
        cont = golden_dh5.get_cont_group_by_id(cont_id)
        assert abs(cont.n_samples - N_SAMPLES_MUA) <= 2, (
            f"CONT {cont_id}: expected ~{N_SAMPLES_MUA} samples, got {cont.n_samples}"
        )
