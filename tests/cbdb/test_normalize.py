from figure_data.cbdb.normalize import build_search_name, normalize_int, to_simplified


def test_normalize_int_maps_cbdb_placeholders_to_none() -> None:
    assert normalize_int(0) is None
    assert normalize_int(-9999) is None
    assert normalize_int("") is None
    assert normalize_int("181") == 181


def test_to_simplified_converts_traditional_name() -> None:
    assert to_simplified("諸葛亮") == "诸葛亮"


def test_build_search_name_removes_spaces_and_lowercases_ascii() -> None:
    assert build_search_name(" Zhuge Liang ") == "zhugeliang"
