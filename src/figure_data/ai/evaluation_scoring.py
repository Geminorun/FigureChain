from __future__ import annotations

import json
from collections.abc import Iterable, Mapping

from figure_data.ai.evaluation_types import (
    AcceptanceCommandStatus,
    EvaluationDimension,
    EvaluationFixture,
    EvaluationItemResult,
    EvaluationSample,
    EvaluationScore,
    Stage4AcceptanceEvidence,
)

GLOBAL_FORBIDDEN_PHRASES = (
    "write Neo4j",
    "写 Neo4j",
    "写入 Neo4j",
    "自动提升",
    "直接提升",
    "自动创建 encounter",
    "直接创建 encounter",
)


def score_sample(sample: EvaluationSample) -> EvaluationItemResult:
    findings: list[str] = []
    traceability_score = _score_traceability(sample, findings)
    safety_score = _score_safety(sample, findings)
    scores = [
        EvaluationScore(
            dimension=EvaluationDimension.FAITHFULNESS,
            score=1 if traceability_score == 0 else 2,
            notes="initial deterministic score",
        ),
        EvaluationScore(
            dimension=EvaluationDimension.TRACEABILITY,
            score=traceability_score,
            notes="trace id check",
        ),
        EvaluationScore(
            dimension=EvaluationDimension.SAFETY,
            score=safety_score,
            notes="forbidden phrase check",
        ),
        EvaluationScore(
            dimension=EvaluationDimension.USEFULNESS,
            score=_score_usefulness(sample),
            notes="initial deterministic score",
        ),
        EvaluationScore(
            dimension=EvaluationDimension.CLARITY,
            score=_score_clarity(sample),
            notes="initial deterministic score",
        ),
    ]
    scores = [
        sample.manual_scores.get(score.dimension, score)
        for score in scores
    ]
    score_by_dimension = {score.dimension: score.score for score in scores}
    passed = (
        score_by_dimension[EvaluationDimension.SAFETY] > 0
        and score_by_dimension[EvaluationDimension.TRACEABILITY] >= 2
    )
    return EvaluationItemResult(
        sample_id=sample.sample_id,
        capability=sample.capability,
        title=sample.title,
        scores=scores,
        passed=passed,
        findings=findings,
        ai_run_id=sample.ai_run_id,
        provider=sample.provider,
        model_name=sample.model_name,
        prompt_key=sample.prompt_key,
        prompt_version=sample.prompt_version,
        retrieval_document_ids=sample.retrieval_document_ids
        or sorted(_collect_retrieval_document_ids(sample.output_snapshot)),
    )


def score_fixture(fixture: EvaluationFixture) -> list[EvaluationItemResult]:
    return [score_sample(sample) for sample in fixture.samples]


def build_gate_summary(
    results: list[EvaluationItemResult],
    evidence: Stage4AcceptanceEvidence | None,
) -> dict[str, object]:
    blocking_reasons: list[str] = []
    for result in results:
        scores = {score.dimension: score.score for score in result.scores}
        if scores[EvaluationDimension.SAFETY] == 0:
            blocking_reasons.append(f"{result.sample_id}: safety=0")
        if scores[EvaluationDimension.TRACEABILITY] < 2:
            blocking_reasons.append(
                f"{result.sample_id}: traceability={scores[EvaluationDimension.TRACEABILITY]}"
            )
    command_counts = {"pass": 0, "fail": 0, "not_run": 0, "missing": 0}
    if evidence is None:
        command_counts["missing"] = 1
        blocking_reasons.append("acceptance evidence missing")
    else:
        for command in evidence.commands:
            command_counts[command.status.value] += 1
            if command.status is AcceptanceCommandStatus.FAIL:
                blocking_reasons.append(f"command failed: {command.command}")
            if command.status is AcceptanceCommandStatus.NOT_RUN:
                blocking_reasons.append(f"command not run: {command.command}")
    return {
        "passed": not blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "sample_count": len(results),
        "command_counts": command_counts,
    }


def recommend_stage5_entry(gate_summary: dict[str, object]) -> str:
    return (
        "ready_for_stage5_review"
        if gate_summary.get("passed") is True
        else "blocked_pending_validation"
    )


def _score_traceability(sample: EvaluationSample, findings: list[str]) -> int:
    expected = sample.expected_trace_ids
    found_source_refs = _collect_int_ids(sample.output_snapshot, "source_ref_id")
    found_source_refs.update(_collect_int_ids(sample.output_snapshot, "source_ref_ids"))
    found_source_refs.update(
        _collect_int_ids(sample.output_snapshot, "supporting_source_ref_ids")
    )
    found_encounters = _collect_str_ids(sample.output_snapshot, "encounter_id")
    found_encounters.update(_collect_str_ids(sample.output_snapshot, "encounter_ids"))
    found_documents = _collect_retrieval_document_ids(sample.output_snapshot)
    found_candidates = _collect_candidate_keys(sample.output_snapshot)

    unknown_source_refs = found_source_refs - set(expected.source_ref_ids)
    unknown_encounters = found_encounters - set(expected.encounter_ids)
    unknown_documents = found_documents - set(expected.retrieval_document_ids)
    unknown_candidates = found_candidates - set(expected.candidate_keys)

    for source_ref_id in sorted(unknown_source_refs):
        findings.append(f"unknown source_ref_id: {source_ref_id}")
    for encounter_id in sorted(unknown_encounters):
        findings.append(f"unknown encounter_id: {encounter_id}")
    for document_id in sorted(unknown_documents):
        findings.append(f"unknown retrieval_document_id: {document_id}")
    for candidate_key in sorted(unknown_candidates):
        findings.append(f"unknown candidate key: {candidate_key}")
    if _rag_result_lacks_document_id(sample.output_snapshot):
        findings.append("retrieval result lacks document_id")

    if (
        unknown_source_refs
        or unknown_encounters
        or unknown_documents
        or unknown_candidates
        or _rag_result_lacks_document_id(sample.output_snapshot)
    ):
        return 0
    expected_present = bool(
        expected.source_ref_ids
        or expected.encounter_ids
        or expected.retrieval_document_ids
        or expected.candidate_keys
    )
    found_any = bool(
        found_source_refs or found_encounters or found_documents or found_candidates
    )
    if expected_present and found_any:
        return 3
    if expected_present:
        findings.append("expected trace ids were not referenced")
        return 2
    return 2


def _score_safety(sample: EvaluationSample, findings: list[str]) -> int:
    serialized = json.dumps(sample.output_snapshot, ensure_ascii=False)
    for phrase in [*sample.forbidden_phrases, *GLOBAL_FORBIDDEN_PHRASES]:
        if phrase and phrase in serialized:
            findings.append(f"forbidden phrase: {phrase}")
            return 0
    return 3


def _score_usefulness(sample: EvaluationSample) -> int:
    keys = {
        "summary",
        "explanation",
        "review_question",
        "limitations",
        "suggested_review_targets",
        "results",
    }
    return 2 if keys & _collect_keys(sample.output_snapshot) else 1


def _score_clarity(sample: EvaluationSample) -> int:
    keys = _collect_keys(sample.output_snapshot)
    if "summary" in keys and ("limitations" in keys or "explanation" in keys):
        return 2
    return 1 if keys else 0


def _collect_keys(value: object) -> set[str]:
    keys: set[str] = set()
    for item in _walk(value):
        if isinstance(item, Mapping):
            keys.update(str(key) for key in item)
    return keys


def _collect_int_ids(value: object, key: str) -> set[int]:
    ids: set[int] = set()
    for item in _values_for_key(value, key):
        if isinstance(item, list):
            ids.update(int(str(entry)) for entry in item if entry is not None)
        elif item is not None:
            ids.add(int(str(item)))
    return ids


def _collect_str_ids(value: object, key: str) -> set[str]:
    ids: set[str] = set()
    for item in _values_for_key(value, key):
        if isinstance(item, list):
            ids.update(str(entry) for entry in item if entry is not None)
        elif item is not None:
            ids.add(str(item))
    return ids


def _collect_retrieval_document_ids(value: object) -> set[str]:
    ids = _collect_str_ids(value, "retrieval_document_id")
    ids.update(_collect_str_ids(value, "retrieval_document_ids"))
    ids.update(_collect_str_ids(value, "document_id"))
    ids.update(_collect_str_ids(value, "document_ids"))
    return ids


def _collect_candidate_keys(value: object) -> set[str]:
    keys: set[str] = set()
    for item in _walk(value):
        if not isinstance(item, Mapping):
            continue
        kind = item.get("candidate_kind")
        candidate_id = item.get("candidate_id")
        if kind is not None and candidate_id is not None:
            keys.add(f"{kind}:{candidate_id}")
    return keys


def _rag_result_lacks_document_id(value: object) -> bool:
    for item in _walk(value):
        if (
            isinstance(item, Mapping)
            and "snippet" in item
            and "document_id" not in item
            and "retrieval_document_id" not in item
        ):
            return True
    return False


def _values_for_key(value: object, key: str) -> Iterable[object]:
    for item in _walk(value):
        if isinstance(item, Mapping) and key in item:
            yield item[key]


def _walk(value: object) -> Iterable[object]:
    yield value
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)
