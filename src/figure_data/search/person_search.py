from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class PersonSearchResult:
    person_id: str
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    index_year: int | None
    dynasty_code: int | None
    matching_aliases: list[str]
    external_ids: list[str]


PERSON_QUERY_ALIASES: dict[str, list[str]] = {
    "汪精卫": ["汪精衛", "汪兆铭", "汪兆銘"],
    "汪精衛": ["汪精卫", "汪兆铭", "汪兆銘"],
}


def expand_person_search_queries(query: str) -> list[str]:
    variants = [query, *PERSON_QUERY_ALIASES.get(query, [])]
    return list(dict.fromkeys(variants))


def build_person_search_sql(query: str, limit: int) -> tuple[str, dict[str, Any]]:
    sql = """
    with matched as (
      select p.id::text as person_id,
             p.primary_name_zh_hant,
             p.primary_name_zh_hans,
             p.primary_name_romanized,
             p.birth_year,
             p.death_year,
             p.index_year,
             p.dynasty_code,
             array_remove(array_agg(distinct a.alias_zh_hant), null) as matching_aliases,
             array_remove(array_agg(distinct e.external_id), null) as external_ids,
             min(case
               when p.primary_name_zh_hant = any(:query_variants)
                 or p.primary_name_zh_hans = any(:query_variants) then 1
               when a.alias_zh_hant = any(:query_variants)
                 or a.alias_zh_hans = any(:query_variants) then 2
               when lower(p.primary_name_romanized) = lower(:query) then 3
               when p.primary_name_zh_hant like any(:prefix_variants)
                 or p.primary_name_zh_hans like any(:prefix_variants) then 4
               when a.alias_zh_hant like any(:prefix_variants)
                 or a.alias_zh_hans like any(:prefix_variants) then 5
               else 6
             end) as match_rank
      from figure_data.persons p
      left join figure_data.person_aliases a on a.person_id = p.id
      left join figure_data.person_external_ids e on e.person_id = p.id
      where p.primary_name_zh_hant = any(:query_variants)
         or p.primary_name_zh_hans = any(:query_variants)
         or a.alias_zh_hant = any(:query_variants)
         or a.alias_zh_hans = any(:query_variants)
         or lower(p.primary_name_romanized) = lower(:query)
         or p.primary_name_zh_hant like any(:contains_variants)
         or p.primary_name_zh_hans like any(:contains_variants)
         or a.alias_zh_hant like any(:contains_variants)
         or a.alias_zh_hans like any(:contains_variants)
      group by p.id
    )
    select * from matched
    order by match_rank asc, index_year nulls last, primary_name_zh_hant asc
    limit :limit
    """
    query_variants = expand_person_search_queries(query)
    return sql, {
        "query": query,
        "query_variants": query_variants,
        "prefix_variants": [f"{variant}%" for variant in query_variants],
        "contains_variants": [f"%{variant}%" for variant in query_variants],
        "limit": limit,
    }


def search_people(session: Session, query: str, limit: int = 10) -> list[PersonSearchResult]:
    sql, params = build_person_search_sql(query, limit)
    rows = session.execute(text(sql), params).mappings().all()
    return [person_search_result_from_row(cast(Mapping[str, Any], row)) for row in rows]


def person_search_result_from_row(row: Mapping[str, Any]) -> PersonSearchResult:
    return PersonSearchResult(
        person_id=str(row["person_id"]),
        primary_name_zh_hant=row["primary_name_zh_hant"],
        primary_name_zh_hans=row["primary_name_zh_hans"],
        primary_name_romanized=row["primary_name_romanized"],
        birth_year=row["birth_year"],
        death_year=row["death_year"],
        index_year=row["index_year"],
        dynasty_code=row["dynasty_code"],
        matching_aliases=list(row["matching_aliases"] or []),
        external_ids=list(row["external_ids"] or []),
    )
