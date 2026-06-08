from figure_data.search.person_search import (
    build_person_search_sql,
    expand_person_search_queries,
    person_search_result_from_row,
)


def test_search_sql_prioritizes_exact_primary_name() -> None:
    sql, params = build_person_search_sql("诸葛亮", limit=10)

    assert "primary_name_zh_hans = any(:query_variants)" in sql
    assert "alias_zh_hans = any(:query_variants)" in sql
    assert "order by match_rank asc" in sql.lower()
    assert params["query"] == "诸葛亮"
    assert params["query_variants"] == ["诸葛亮"]
    assert params["limit"] == 10


def test_search_expands_known_person_name_aliases() -> None:
    assert expand_person_search_queries("汪精卫") == ["汪精卫", "汪精衛", "汪兆铭", "汪兆銘"]


def test_search_expands_known_romanized_name_aliases() -> None:
    assert expand_person_search_queries("Sima Yi") == ["Sima Yi", "司马懿", "司馬懿"]


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
