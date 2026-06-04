from figure_data.search.person_search import build_person_search_sql


def test_search_sql_prioritizes_exact_primary_name() -> None:
    sql, params = build_person_search_sql("诸葛亮", limit=10)

    assert "primary_name_zh_hans = :query" in sql
    assert "alias_zh_hans = :query" in sql
    assert "order by match_rank asc" in sql.lower()
    assert params["query"] == "诸葛亮"
    assert params["limit"] == 10
