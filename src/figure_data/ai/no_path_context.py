from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.ai.retrieval_repository import RetrievalSearchResult
from figure_data.graph.types import ChainLookupResult


class InvalidNoPathContextError(ValueError):
    """Raised when no-path exploration is not based on a no-path result."""


class NoPathPersonInput(BaseModel):
    person_id: str
    display_name: str
    birth_year: int | None
    death_year: int | None
    cbdb_external_id: str | None


class NoPathEndpointGraphStatsInput(BaseModel):
    person_id: str
    active_path_encounter_count: int = Field(ge=0)


class NoPathCandidateSummaryInput(BaseModel):
    candidate_kind: Literal["relationship", "kinship"]
    candidate_id: int
    person_a_id: str | None
    person_b_id: str | None
    person_a_name: str | None
    person_b_name: str | None
    candidate_strength: str
    candidate_basis: str
    relation_label: str | None
    source_work_id: int | None
    source_ref_id: int | None
    pages: str | None
    review_status: str


class NoPathRetrievalContextInput(BaseModel):
    document_id: str
    source_kind: str
    source_pk: str
    source_ref_id: int | None
    encounter_evidence_id: int | None
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    score: float
    snippet: str


class NoPathPromptInput(BaseModel):
    source_person_id: str
    target_person_id: str
    max_depth: int
    path_status: Literal["no_path"]
    language: str
    source_person: NoPathPersonInput
    target_person: NoPathPersonInput
    source_stats: NoPathEndpointGraphStatsInput
    target_stats: NoPathEndpointGraphStatsInput
    candidate_summaries: list[NoPathCandidateSummaryInput] = Field(default_factory=list)
    retrieval_context: list[NoPathRetrievalContextInput] = Field(default_factory=list)
    graph_context: dict[str, object] = Field(default_factory=dict)


def assemble_no_path_prompt_input(
    *,
    result: ChainLookupResult,
    people: dict[str, NoPathPersonInput],
    endpoint_stats: dict[str, NoPathEndpointGraphStatsInput],
    candidate_summaries: list[NoPathCandidateSummaryInput],
    retrieval_context: list[NoPathRetrievalContextInput],
    language: str,
) -> NoPathPromptInput:
    if result.path is not None:
        raise InvalidNoPathContextError("no-path exploration requires a no-path result")
    try:
        source_person = people[result.source_person_id]
        target_person = people[result.target_person_id]
        source_stats = endpoint_stats[result.source_person_id]
        target_stats = endpoint_stats[result.target_person_id]
    except KeyError as exc:
        raise InvalidNoPathContextError(
            f"missing no-path endpoint context: {exc}"
        ) from exc
    return NoPathPromptInput(
        source_person_id=result.source_person_id,
        target_person_id=result.target_person_id,
        max_depth=result.max_depth,
        path_status="no_path",
        language=language,
        source_person=source_person,
        target_person=target_person,
        source_stats=source_stats,
        target_stats=target_stats,
        candidate_summaries=candidate_summaries,
        retrieval_context=retrieval_context,
        graph_context={
            "projection_source": "Neo4j shortest path projection",
            "path_edge_filter": "active/high/direct_interaction/path_eligible",
        },
    )


def retrieval_context_from_search_results(
    results: list[RetrievalSearchResult],
    *,
    snippet_chars: int = 240,
) -> list[NoPathRetrievalContextInput]:
    return [
        NoPathRetrievalContextInput(
            document_id=str(result.document_id),
            source_kind=result.source_kind,
            source_pk=result.source_pk,
            source_ref_id=result.source_ref_id,
            encounter_evidence_id=result.encounter_evidence_id,
            source_work_id=result.source_work_id,
            title_zh=result.title_zh,
            title_en=result.title_en,
            pages=result.pages,
            score=result.score,
            snippet=_normalize_snippet(result.content_text, snippet_chars=snippet_chars),
        )
        for result in results
    ]


def build_no_path_retrieval_query(prompt_input: NoPathPromptInput) -> str:
    terms: list[str | None] = [
        prompt_input.source_person.display_name,
        prompt_input.target_person.display_name,
    ]
    for candidate in prompt_input.candidate_summaries[:5]:
        terms.extend(
            [
                candidate.person_a_name,
                candidate.person_b_name,
                candidate.relation_label,
            ]
        )
    return " ".join(term.strip() for term in terms if term and term.strip())


def no_path_allowed_candidate_keys(prompt_input: NoPathPromptInput) -> set[tuple[str, int]]:
    return {
        (candidate.candidate_kind, candidate.candidate_id)
        for candidate in prompt_input.candidate_summaries
    }


def no_path_allowed_source_ref_ids(prompt_input: NoPathPromptInput) -> set[int]:
    candidate_refs = {
        candidate.source_ref_id
        for candidate in prompt_input.candidate_summaries
        if candidate.source_ref_id is not None
    }
    retrieval_refs = {
        item.source_ref_id
        for item in prompt_input.retrieval_context
        if item.source_ref_id is not None
    }
    return candidate_refs | retrieval_refs


def no_path_allowed_retrieval_document_ids(prompt_input: NoPathPromptInput) -> set[str]:
    return {item.document_id for item in prompt_input.retrieval_context}


def no_path_allowed_person_ids(prompt_input: NoPathPromptInput) -> set[str]:
    return {prompt_input.source_person_id, prompt_input.target_person_id}


def build_no_path_prompt_input(
    *,
    session: Session | object,
    result: ChainLookupResult,
    retrieval_context: list[NoPathRetrievalContextInput],
    candidate_limit: int,
    language: str,
) -> NoPathPromptInput:
    if result.path is not None:
        raise InvalidNoPathContextError("no-path exploration requires a no-path result")
    person_ids = [result.source_person_id, result.target_person_id]
    people = _load_people_by_ids(session, person_ids)
    endpoint_stats = {
        person_id: NoPathEndpointGraphStatsInput(
            person_id=person_id,
            active_path_encounter_count=_count_active_path_encounters(
                session,
                person_id,
            ),
        )
        for person_id in person_ids
    }
    candidate_summaries = _list_endpoint_candidate_summaries(
        session,
        person_ids=person_ids,
        limit=candidate_limit,
    )
    return assemble_no_path_prompt_input(
        result=result,
        people=people,
        endpoint_stats=endpoint_stats,
        candidate_summaries=candidate_summaries,
        retrieval_context=retrieval_context,
        language=language,
    )


def _load_people_by_ids(
    session: Session | object,
    person_ids: list[str],
) -> dict[str, NoPathPersonInput]:
    executable = cast(Any, session)
    rows = (
        executable.execute(
            text(
                """
                select
                  p.id::text as person_id,
                  coalesce(
                    p.primary_name_zh_hant,
                    p.primary_name_zh_hans,
                    p.primary_name_romanized,
                    p.id::text
                  ) as display_name,
                  p.birth_year,
                  p.death_year,
                  cbdb.external_id as cbdb_external_id
                from figure_data.persons p
                left join figure_data.person_external_ids cbdb
                  on cbdb.person_id = p.id
                 and cbdb.source_name = 'cbdb'
                where p.id::text = any(:person_ids)
                """
            ),
            {"person_ids": person_ids},
        )
        .mappings()
        .all()
    )
    people = {
        str(row["person_id"]): _person_from_row(cast(Mapping[str, Any], row))
        for row in rows
    }
    missing = [person_id for person_id in person_ids if person_id not in people]
    if missing:
        raise InvalidNoPathContextError(
            "missing endpoint person in PostgreSQL: " + ",".join(missing)
        )
    return people


def _count_active_path_encounters(session: Session | object, person_id: str) -> int:
    executable = cast(Any, session)
    value = executable.execute(
        text(
            """
            select count(*)::integer
            from figure_data.encounters
            where status = 'active'
              and path_eligible = true
              and certainty_level = 'high'
              and encounter_kind = 'direct_interaction'
              and (person_a_id::text = :person_id or person_b_id::text = :person_id)
            """
        ),
        {"person_id": person_id},
    ).scalar_one()
    return int(value)


def _list_endpoint_candidate_summaries(
    session: Session | object,
    *,
    person_ids: list[str],
    limit: int,
) -> list[NoPathCandidateSummaryInput]:
    executable = cast(Any, session)
    rows = (
        executable.execute(
            text(
                """
                select *
                from (
                  select
                    'relationship' as candidate_kind,
                    rc.id as candidate_id,
                    rc.person_a_id::text as person_a_id,
                    rc.person_b_id::text as person_b_id,
                    coalesce(
                      pa.primary_name_zh_hant,
                      pa.primary_name_zh_hans,
                      pa.primary_name_romanized
                    ) as person_a_name,
                    coalesce(
                      pb.primary_name_zh_hant,
                      pb.primary_name_zh_hans,
                      pb.primary_name_romanized
                    ) as person_b_name,
                    rc.candidate_strength,
                    rc.candidate_basis,
                    rc.association_label as relation_label,
                    rc.source_work_id,
                    source_ref.source_ref_id,
                    rc.pages,
                    rc.review_status
                  from figure_data.relationship_candidates rc
                  left join figure_data.persons pa on pa.id = rc.person_a_id
                  left join figure_data.persons pb on pb.id = rc.person_b_id
                  left join lateral (
                    select sr.id as source_ref_id
                    from figure_data.source_refs sr
                    where sr.ref_source_table = rc.source_table
                      and sr.ref_source_pk = rc.source_pk
                    order by sr.source_work_id nulls last, sr.id
                    limit 1
                  ) source_ref on true
                  left join figure_data.encounters existing_path
                    on existing_path.status = 'active'
                   and existing_path.path_eligible = true
                   and existing_path.certainty_level = 'high'
                   and existing_path.encounter_kind = 'direct_interaction'
                   and (
                     (
                       existing_path.person_a_id = rc.person_a_id
                       and existing_path.person_b_id = rc.person_b_id
                     )
                     or (
                       existing_path.person_a_id = rc.person_b_id
                       and existing_path.person_b_id = rc.person_a_id
                     )
                   )
                  where rc.review_status in ('unreviewed', 'needs_review')
                    and existing_path.id is null
                    and (
                      rc.person_a_id::text = any(:person_ids)
                      or rc.person_b_id::text = any(:person_ids)
                    )
                  union all
                  select
                    'kinship' as candidate_kind,
                    kc.id as candidate_id,
                    kc.person_a_id::text as person_a_id,
                    kc.person_b_id::text as person_b_id,
                    coalesce(
                      pa.primary_name_zh_hant,
                      pa.primary_name_zh_hans,
                      pa.primary_name_romanized
                    ) as person_a_name,
                    coalesce(
                      pb.primary_name_zh_hant,
                      pb.primary_name_zh_hans,
                      pb.primary_name_romanized
                    ) as person_b_name,
                    kc.candidate_strength,
                    kc.candidate_basis,
                    coalesce(kc.kinship_label_zh, kc.kinship_label_en) as relation_label,
                    kc.source_work_id,
                    null::integer as source_ref_id,
                    kc.pages,
                    kc.review_status
                  from figure_data.kinship_candidates kc
                  left join figure_data.persons pa on pa.id = kc.person_a_id
                  left join figure_data.persons pb on pb.id = kc.person_b_id
                  left join figure_data.encounters existing_path
                    on existing_path.status = 'active'
                   and existing_path.path_eligible = true
                   and existing_path.certainty_level = 'high'
                   and existing_path.encounter_kind = 'direct_interaction'
                   and (
                     (
                       existing_path.person_a_id = kc.person_a_id
                       and existing_path.person_b_id = kc.person_b_id
                     )
                     or (
                       existing_path.person_a_id = kc.person_b_id
                       and existing_path.person_b_id = kc.person_a_id
                     )
                   )
                  where kc.review_status in ('unreviewed', 'needs_review')
                    and existing_path.id is null
                    and (
                      kc.person_a_id::text = any(:person_ids)
                      or kc.person_b_id::text = any(:person_ids)
                    )
                ) candidates
                order by
                  case candidate_strength
                    when 'high' then 1
                    when 'medium' then 2
                    when 'low' then 3
                    else 4
                  end,
                  candidate_id
                limit :limit
                """
            ),
            {"person_ids": person_ids, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [_candidate_summary_from_row(cast(Mapping[str, Any], row)) for row in rows]


def _person_from_row(row: Mapping[str, Any]) -> NoPathPersonInput:
    return NoPathPersonInput(
        person_id=str(row["person_id"]),
        display_name=str(row["display_name"]),
        birth_year=_optional_int(row["birth_year"]),
        death_year=_optional_int(row["death_year"]),
        cbdb_external_id=_optional_str(row["cbdb_external_id"]),
    )


def _candidate_summary_from_row(row: Mapping[str, Any]) -> NoPathCandidateSummaryInput:
    return NoPathCandidateSummaryInput(
        candidate_kind=cast(Literal["relationship", "kinship"], str(row["candidate_kind"])),
        candidate_id=int(row["candidate_id"]),
        person_a_id=_optional_str(row["person_a_id"]),
        person_b_id=_optional_str(row["person_b_id"]),
        person_a_name=_optional_str(row["person_a_name"]),
        person_b_name=_optional_str(row["person_b_name"]),
        candidate_strength=str(row["candidate_strength"]),
        candidate_basis=str(row["candidate_basis"]),
        relation_label=_optional_str(row["relation_label"]),
        source_work_id=_optional_int(row["source_work_id"]),
        source_ref_id=_optional_int(row["source_ref_id"]),
        pages=_optional_str(row["pages"]),
        review_status=str(row["review_status"]),
    )


def _normalize_snippet(value: str, *, snippet_chars: int) -> str:
    normalized = " ".join(value.split())
    return normalized[:snippet_chars]


def _optional_int(value: object) -> int | None:
    return None if value is None else int(cast(Any, value))


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
