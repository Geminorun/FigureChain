from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpansionCandidate:
    candidate_id: int
    person_a_id: str
    person_b_id: str
    person_a_name: str | None
    person_b_name: str | None
    cbdb_person_a_id: int | None
    cbdb_person_b_id: int | None
    candidate_strength: str
    candidate_basis: str
    relation_label: str | None
    source_work_id: int | None
    source_ref_id: int | None
    pages: str | None
    review_status: str
    active_path_neighbors: int
    score: int
