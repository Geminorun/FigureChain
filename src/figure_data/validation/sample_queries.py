from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from figure_data.search.person_search import PersonSearchResult, search_people
from figure_data.validation.report import ValidationCheck


@dataclass(frozen=True)
class SamplePersonQuery:
    query: str
    expected_external_id: str
    expected_top_n: int = 1


SAMPLE_PERSON_QUERIES = [
    SamplePersonQuery("诸葛亮", "25403"),
    SamplePersonQuery("諸葛亮", "25403"),
    SamplePersonQuery("Zhuge Liang", "25403"),
    SamplePersonQuery("司马懿", "21204"),
    SamplePersonQuery("司馬懿", "21204"),
    SamplePersonQuery("Sima Yi", "21204"),
    SamplePersonQuery("司马炎", "21207"),
    SamplePersonQuery("司馬炎", "21207"),
    SamplePersonQuery("汪兆铭", "79335"),
    SamplePersonQuery("汪兆銘", "79335"),
    SamplePersonQuery("汪精卫", "79335", expected_top_n=5),
    SamplePersonQuery("Wang Zhaoming", "79335", expected_top_n=5),
]


def validate_sample_person_queries(session: Session) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    for sample in SAMPLE_PERSON_QUERIES:
        results = search_people(session, sample.query, limit=max(5, sample.expected_top_n))
        matched_position = _find_external_id_position(results, sample.expected_external_id)
        checks.append(
            ValidationCheck(
                name=f"search:{sample.query}",
                passed=matched_position is not None and matched_position <= sample.expected_top_n,
                detail=_sample_detail(sample, len(results), matched_position),
            )
        )
    return checks


def _find_external_id_position(
    results: Sequence[PersonSearchResult],
    expected_external_id: str,
) -> int | None:
    for index, result in enumerate(results, start=1):
        if expected_external_id in result.external_ids:
            return index
    return None


def _sample_detail(
    sample: SamplePersonQuery,
    matches: int,
    matched_position: int | None,
) -> str:
    position = "none" if matched_position is None else str(matched_position)
    return (
        f"expected_external_id={sample.expected_external_id}, "
        f"expected_top_n={sample.expected_top_n}, matched_position={position}, matches={matches}"
    )
