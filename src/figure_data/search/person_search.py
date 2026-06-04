from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
               when p.primary_name_zh_hant = :query or p.primary_name_zh_hans = :query then 1
               when a.alias_zh_hant = :query or a.alias_zh_hans = :query then 2
               when lower(p.primary_name_romanized) = lower(:query) then 3
               when p.primary_name_zh_hant like :prefix
                 or p.primary_name_zh_hans like :prefix then 4
               when a.alias_zh_hant like :prefix or a.alias_zh_hans like :prefix then 5
               else 6
             end) as match_rank
      from figure_data.persons p
      left join figure_data.person_aliases a on a.person_id = p.id
      left join figure_data.person_external_ids e on e.person_id = p.id
      where p.primary_name_zh_hant = :query
         or p.primary_name_zh_hans = :query
         or a.alias_zh_hant = :query
         or a.alias_zh_hans = :query
         or lower(p.primary_name_romanized) = lower(:query)
         or p.primary_name_zh_hant like :contains
         or p.primary_name_zh_hans like :contains
         or a.alias_zh_hant like :contains
         or a.alias_zh_hans like :contains
      group by p.id
    )
    select * from matched
    order by match_rank asc, index_year nulls last, primary_name_zh_hant asc
    limit :limit
    """
    return sql, {"query": query, "prefix": f"{query}%", "contains": f"%{query}%", "limit": limit}


def search_people(session: Session, query: str, limit: int = 10) -> list[PersonSearchResult]:
    sql, params = build_person_search_sql(query, limit)
    rows = session.execute(text(sql), params).mappings().all()
    return [PersonSearchResult(**dict(row)) for row in rows]
