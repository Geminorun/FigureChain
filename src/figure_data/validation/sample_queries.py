from sqlalchemy.orm import Session

from figure_data.search.person_search import search_people
from figure_data.validation.report import ValidationCheck

SAMPLE_PERSON_QUERIES = [
    "诸葛亮",
    "諸葛亮",
    "Zhuge Liang",
    "司马懿",
    "司馬懿",
    "Sima Yi",
    "汪兆銘",
    "汪兆铭",
    "Wang Zhaoming",
]


def validate_sample_person_queries(session: Session) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    for query in SAMPLE_PERSON_QUERIES:
        results = search_people(session, query, limit=5)
        checks.append(
            ValidationCheck(
                name=f"search:{query}",
                passed=bool(results),
                detail=f"matches={len(results)}",
            )
        )
    return checks
