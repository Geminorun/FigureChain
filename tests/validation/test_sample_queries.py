from figure_data.validation.sample_queries import SAMPLE_PERSON_QUERIES, SamplePersonQuery


def test_sample_queries_include_simplified_and_traditional_names() -> None:
    queries = {sample.query for sample in SAMPLE_PERSON_QUERIES}

    assert "诸葛亮" in queries
    assert "諸葛亮" in queries
    assert "司马炎" in queries
    assert "司馬炎" in queries
    assert "汪精卫" in queries
    assert "Wang Zhaoming" in queries


def test_sample_queries_define_expected_target_identity() -> None:
    wang_jingwei = SamplePersonQuery(
        query="汪精卫",
        expected_external_id="79335",
        expected_top_n=5,
    )

    assert wang_jingwei in SAMPLE_PERSON_QUERIES


def test_sample_queries_validate_historical_sima_yi_identity() -> None:
    sima_yi = SamplePersonQuery(
        query="Sima Yi",
        expected_external_id="21204",
    )

    assert sima_yi in SAMPLE_PERSON_QUERIES
