from figure_data.cbdb.source_identity import build_source_pk, hash_source_row


def test_build_source_pk_uses_single_key() -> None:
    row = {"c_personid": 25403, "c_name_chn": "諸葛亮"}

    assert build_source_pk(row, ["c_personid"]) == "c_personid=25403"


def test_build_source_pk_is_stable_for_composite_keys() -> None:
    row = {"c_assoc_code": 339, "c_personid": 1, "c_assoc_id": 2}

    assert build_source_pk(row, ["c_personid", "c_assoc_id", "c_assoc_code"]) == (
        "c_assoc_code=339|c_assoc_id=2|c_personid=1"
    )


def test_hash_source_row_is_order_independent() -> None:
    left = {"b": 2, "a": 1}
    right = {"a": 1, "b": 2}

    assert hash_source_row(left) == hash_source_row(right)
