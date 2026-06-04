from figure_data.validation.sample_queries import SAMPLE_PERSON_QUERIES


def test_sample_queries_include_simplified_and_traditional_names() -> None:
    assert "诸葛亮" in SAMPLE_PERSON_QUERIES
    assert "諸葛亮" in SAMPLE_PERSON_QUERIES
    assert "Wang Zhaoming" in SAMPLE_PERSON_QUERIES
