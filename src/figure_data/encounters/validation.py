from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.validation.report import ValidationCheck


def validate_encounters(session: Session) -> list[ValidationCheck]:
    return [
        _count_check(
            session,
            name="encounters:no_self_loops",
            sql="""
                select count(*)
                from figure_data.encounters
                where person_a_id = person_b_id
            """,
        ),
        _count_check(
            session,
            name="encounters:active_have_evidence",
            sql="""
                select count(*)
                from figure_data.encounters e
                where e.status = 'active'
                  and not exists (
                    select 1
                    from figure_data.encounter_evidence ev
                    where ev.encounter_id = e.id
                  )
            """,
        ),
        _count_check(
            session,
            name="encounters:retracted_not_path_eligible",
            sql="""
                select count(*)
                from figure_data.encounters
                where status = 'retracted'
                  and path_eligible = true
            """,
        ),
        _count_check(
            session,
            name="encounters:path_eligible_certainty",
            sql="""
                select count(*)
                from figure_data.encounters
                where path_eligible = true
                  and certainty_level <> 'high'
                  and nullif(trim(coalesce(review_note, '')), '') is null
            """,
        ),
        _count_check(
            session,
            name="encounters:relationship_promotions_resolve",
            sql="""
                select count(*)
                from figure_data.relationship_candidates rc
                left join figure_data.encounters e
                  on e.id = rc.promoted_encounter_id
                where rc.review_status = 'promoted_to_encounter'
                  and (rc.promoted_encounter_id is null or e.id is null)
            """,
        ),
        _count_check(
            session,
            name="encounters:kinship_promotions_resolve",
            sql="""
                select count(*)
                from figure_data.kinship_candidates kc
                left join figure_data.encounters e
                  on e.id = kc.promoted_encounter_id
                where kc.review_status = 'promoted_to_encounter'
                  and (kc.promoted_encounter_id is null or e.id is null)
            """,
        ),
        _count_check(
            session,
            name="encounters:candidates_single_active_encounter",
            sql="""
                select count(*)
                from (
                  select ev.candidate_table, ev.candidate_id
                  from figure_data.encounter_evidence ev
                  join figure_data.encounters e
                    on e.id = ev.encounter_id
                  where e.status = 'active'
                    and ev.candidate_table is not null
                    and ev.candidate_id is not null
                  group by ev.candidate_table, ev.candidate_id
                  having count(distinct e.id) > 1
                ) duplicate_candidates
            """,
        ),
    ]


def _count_check(session: Session, *, name: str, sql: str) -> ValidationCheck:
    violations = int(session.execute(text(sql)).scalar_one())
    return ValidationCheck(
        name=name,
        passed=violations == 0,
        detail=f"violations={violations}",
    )
