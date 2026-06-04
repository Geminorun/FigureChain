from figure_data.search.person_search import build_person_search_sql, person_search_result_from_row


def test_search_sql_prioritizes_exact_primary_name() -> None:
    sql, params = build_person_search_sql("诸葛亮", limit=10)

    assert "primary_name_zh_hans = :query" in sql
    assert "alias_zh_hans = :query" in sql
    assert "order by match_rank asc" in sql.lower()
    assert params["query"] == "诸葛亮"
    assert params["limit"] == 10


def test_search_result_mapping_ignores_sql_rank_column() -> None:
    result = person_search_result_from_row(
        {
            "person_id": "person-1",
            "primary_name_zh_hant": "諸葛亮",
            "primary_name_zh_hans": "诸葛亮",
            "primary_name_romanized": "Zhuge Liang",
            "birth_year": 181,
            "death_year": 234,
            "index_year": 220,
            "dynasty_code": 30,
            "matching_aliases": ["孔明"],
            "external_ids": ["25403"],
            "match_rank": 1,
        }
    )

    assert result.person_id == "person-1"
    assert result.matching_aliases == ["孔明"]
