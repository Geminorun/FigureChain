# AI RAG Prompt Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Plan 4 的 RAG 检索结果作为可选上下文接入候选审核建议和人物链解释 prompt，并保持 AI/RAG 不写事实源、不改 Neo4j 的边界。

**Architecture:** 新增一个共享 retrieval context 模型，把 `search_rag_evidence()` 的结果转换为可序列化、可回溯、可限制的 prompt 输入片段。候选建议和链解释服务在生成 prompt snapshot 前可选检索 RAG 上下文；输出 schema 只增加可选追踪字段，事实字段仍只来自候选详情、encounter 和 encounter evidence。RAG 缺失时生成流程继续运行，并在 prompt 输入中记录缺失状态。

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy 2.x, Typer, PostgreSQL/pgvector, pytest, ruff, mypy.

---

## Scope Check

本计划实现阶段 4 收口 spec 的 Plan 1：RAG 上下文接入 AI prompt。

本计划实现：

- 共享 `AIRetrievalContextItem` prompt 输入模型。
- 候选审核建议 prompt 输入新增 `retrieval_context` 和 `retrieval_context_status`。
- 人物链解释 prompt 输入新增 `retrieval_context` 和 `retrieval_context_status`。
- 候选审核建议输出 schema 新增 `retrieval_source_ref_ids`、`retrieval_document_ids`、`retrieval_limitations`。
- 人物链解释输出 schema 新增 `retrieval_document_ids`、`retrieval_notes`。
- 候选建议和链解释 service 在构建 prompt snapshot 前调用可注入的 RAG 检索函数。
- policy guard 校验模型引用的 retrieval ids 必须来自输入上下文。
- README 说明 RAG 上下文只进入 prompt，不是事实源。

本计划不实现：

- 无路径探索建议。
- AI 评测命令或阶段 4 验收报告。
- FastAPI 新生成接口。
- 前端展示 RAG 原始片段。
- 真实 embedding provider SDK。
- 自动创建、修改或删除 candidates、encounters、encounter_evidence 或 Neo4j 边。

## Prerequisite Contract

执行前当前分支应具备以下能力：

- `src/figure_data/ai/retrieval_service.py` 提供 `search_rag_evidence()`。
- `src/figure_data/ai/retrieval_repository.py` 的 `RetrievalSearchResult` 包含 `document_id`、`source_kind`、`source_pk`、`source_ref_id`、`encounter_evidence_id`、`score` 和 `content_text`。
- `src/figure_data/ai/candidate_service.py` 已通过 `run_ai_prompt()` 生成并保存候选建议。
- `src/figure_data/ai/chain_service.py` 已通过 `run_ai_prompt()` 生成并保存链解释。
- `src/figure_data/ai/prompts.py` 注册了 `candidate_review_suggestion` 和 `chain_explanation` prompt。
- RAG 索引已经可以通过 `figure-data build-rag-index` 构建；没有索引时检索返回空列表。

执行前运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\python.exe -m alembic heads
```

预期：

```text
pytest passes.
ruff passes.
mypy passes.
alembic heads shows 20260613_0004 (head).
```

如果本机 `uv` 可用，也可以使用项目约定命令：

```powershell
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync python -m alembic heads
```

## File Structure

新增：

```text
src/figure_data/ai/retrieval_context.py
tests/ai/test_retrieval_context.py
```

修改：

```text
src/figure_data/ai/candidate_context.py
src/figure_data/ai/candidate_policy.py
src/figure_data/ai/candidate_service.py
src/figure_data/ai/chain_context.py
src/figure_data/ai/chain_policy.py
src/figure_data/ai/chain_service.py
src/figure_data/ai/prompts.py
src/figure_data/ai/provider.py
src/figure_data/ai/schemas.py
tests/ai/test_candidate_context.py
tests/ai/test_candidate_policy.py
tests/ai/test_candidate_prompt_schema.py
tests/ai/test_candidate_service.py
tests/ai/test_chain_context.py
tests/ai/test_chain_policy.py
tests/ai/test_chain_prompt_schema.py
tests/ai/test_chain_service.py
tests/ai/test_provider.py
tests/test_readme_commands.py
README.md
```

职责边界：

- `retrieval_context.py`：只负责 RAG 检索结果到 prompt context 的转换、query 构造和 id 提取；不访问数据库、不调用模型。
- `candidate_context.py`：只扩展候选 prompt 输入模型，不发起检索。
- `candidate_service.py`：编排候选详情、RAG 检索、prompt snapshot、AI 调用和保存建议。
- `chain_context.py`：只扩展链解释 prompt 输入模型，不发起检索。
- `chain_service.py`：编排已审核路径、限定范围 RAG 检索、prompt snapshot、AI 调用和保存解释。
- `schemas.py`：只定义模型结构化输出字段。
- `candidate_policy.py` 和 `chain_policy.py`：只校验输出引用的 id 是否来自输入上下文。
- `prompts.py`：只更新 prompt 文案，强调 RAG 召回上下文不是已审核证据。

## Task 1: Shared Retrieval Context Model And Helpers

**Files:**

- Create: `src/figure_data/ai/retrieval_context.py`
- Create: `tests/ai/test_retrieval_context.py`

- [ ] **Step 1: Add failing retrieval context tests**

Create `tests/ai/test_retrieval_context.py`:

```python
from uuid import UUID

from figure_data.ai.retrieval_context import (
    AIRetrievalContextItem,
    build_candidate_retrieval_query,
    build_chain_retrieval_queries,
    retrieval_context_items_from_search_results,
    retrieval_document_ids,
    retrieval_source_ref_ids,
)
from figure_data.ai.retrieval_repository import RetrievalSearchResult


def search_result(
    *,
    document_id: str = "00000000-0000-0000-0000-000000000501",
    source_kind: str = "source_ref",
    source_pk: str = "source_ref:3853784",
    source_ref_id: int | None = 3853784,
    encounter_evidence_id: int | None = None,
    content_text: str = "许几谒见韩琦。\n\t有页码。",
) -> RetrievalSearchResult:
    return RetrievalSearchResult(
        document_id=UUID(document_id),
        source_kind=source_kind,
        source_pk=source_pk,
        source_ref_id=source_ref_id,
        encounter_evidence_id=encounter_evidence_id,
        source_work_id=111,
        title_zh="续资治通鉴长编",
        title_en=None,
        pages="卷一",
        chunk_index=0,
        content_text=content_text,
        text_hash="abc",
        score=0.88,
    )


def test_retrieval_context_items_preserve_trace_fields_and_snippet() -> None:
    items = retrieval_context_items_from_search_results(
        [search_result()],
        provider="fake",
        model_name="fake-hash-embedding",
        embedding_dimensions=8,
    )

    assert items == [
        AIRetrievalContextItem(
            document_id="00000000-0000-0000-0000-000000000501",
            source_kind="source_ref",
            source_pk="source_ref:3853784",
            source_ref_id=3853784,
            encounter_evidence_id=None,
            source_work_id=111,
            title_zh="续资治通鉴长编",
            title_en=None,
            pages="卷一",
            score=0.88,
            snippet="许几谒见韩琦。 有页码。",
            provider="fake",
            model_name="fake-hash-embedding",
            embedding_dimensions=8,
        )
    ]


def test_retrieval_context_limits_snippet_length() -> None:
    items = retrieval_context_items_from_search_results(
        [search_result(content_text="甲" * 240)],
        provider="fake",
        model_name="fake-hash-embedding",
        embedding_dimensions=8,
        snippet_chars=20,
    )

    assert items[0].snippet == "甲" * 20


def test_retrieval_context_id_helpers_ignore_missing_values() -> None:
    items = retrieval_context_items_from_search_results(
        [
            search_result(),
            search_result(
                document_id="00000000-0000-0000-0000-000000000502",
                source_kind="encounter_evidence",
                source_pk="encounter_evidence:12",
                source_ref_id=3853784,
                encounter_evidence_id=12,
            ),
            search_result(
                document_id="00000000-0000-0000-0000-000000000501",
                source_ref_id=None,
            ),
        ],
        provider="fake",
        model_name="fake-hash-embedding",
        embedding_dimensions=8,
    )

    assert retrieval_document_ids(items) == {
        "00000000-0000-0000-0000-000000000501",
        "00000000-0000-0000-0000-000000000502",
    }
    assert retrieval_source_ref_ids(items) == {3853784}


def test_build_candidate_retrieval_query_uses_candidate_people_and_sources() -> None:
    query = build_candidate_retrieval_query(
        person_a_names=["许几", "Xu Ji"],
        person_b_names=["韩琦"],
        relation_label="曾谒见",
        candidate_basis="direct_interaction_likely",
        source_titles=["续资治通鉴长编"],
        notes=["以诸生谒韩琦于魏"],
    )

    assert query == "许几 Xu Ji 韩琦 曾谒见 direct_interaction_likely 续资治通鉴长编 以诸生谒韩琦于魏"


def test_build_chain_retrieval_queries_scope_by_source_ref() -> None:
    queries = build_chain_retrieval_queries(
        people_names=["许几", "韩琦"],
        encounter_summaries=["许几以诸生谒韩琦于魏"],
        source_ref_ids=[3853784, 3853784, 3853790],
    )

    assert queries == [
        (3853784, "许几 韩琦 许几以诸生谒韩琦于魏"),
        (3853790, "许几 韩琦 许几以诸生谒韩琦于魏"),
    ]
```

- [ ] **Step 2: Run Task 1 tests and confirm they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ai/test_retrieval_context.py -q
```

Expected:

```text
FAIL because figure_data.ai.retrieval_context does not exist.
```

- [ ] **Step 3: Create retrieval context helper module**

Create `src/figure_data/ai/retrieval_context.py`:

```python
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from figure_data.ai.retrieval_repository import RetrievalSearchResult


class AIRetrievalContextItem(BaseModel):
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
    snippet: str = Field(min_length=1, max_length=500)
    provider: str
    model_name: str
    embedding_dimensions: int


def retrieval_context_items_from_search_results(
    results: list[RetrievalSearchResult],
    *,
    provider: str,
    model_name: str,
    embedding_dimensions: int,
    snippet_chars: int = 240,
) -> list[AIRetrievalContextItem]:
    return [
        AIRetrievalContextItem(
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
            snippet=_snippet(result.content_text, snippet_chars=snippet_chars),
            provider=provider,
            model_name=model_name,
            embedding_dimensions=embedding_dimensions,
        )
        for result in results
        if _snippet(result.content_text, snippet_chars=snippet_chars)
    ]


def retrieval_document_ids(items: list[AIRetrievalContextItem]) -> set[str]:
    return {item.document_id for item in items}


def retrieval_source_ref_ids(items: list[AIRetrievalContextItem]) -> set[int]:
    return {item.source_ref_id for item in items if item.source_ref_id is not None}


def build_candidate_retrieval_query(
    *,
    person_a_names: list[str | None],
    person_b_names: list[str | None],
    relation_label: str | None,
    candidate_basis: str | None,
    source_titles: list[str | None],
    notes: list[str | None],
) -> str:
    return _join_terms(
        [
            *person_a_names,
            *person_b_names,
            relation_label,
            candidate_basis,
            *source_titles,
            *notes,
        ]
    )


def build_chain_retrieval_queries(
    *,
    people_names: list[str],
    encounter_summaries: list[str],
    source_ref_ids: list[int],
) -> list[tuple[int, str]]:
    query = _join_terms([*people_names, *encounter_summaries])
    seen: set[int] = set()
    scoped_queries: list[tuple[int, str]] = []
    for source_ref_id in source_ref_ids:
        if source_ref_id in seen:
            continue
        seen.add(source_ref_id)
        scoped_queries.append((source_ref_id, query))
    return scoped_queries


def _join_terms(values: list[str | None]) -> str:
    return " ".join(value.strip() for value in values if value and value.strip())


def _snippet(value: str, *, snippet_chars: int) -> str:
    return re.sub(r"\s+", " ", value).strip()[:snippet_chars]
```

- [ ] **Step 4: Run Task 1 tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ai/test_retrieval_context.py -q
.\.venv\Scripts\ruff.exe check src/figure_data/ai/retrieval_context.py tests/ai/test_retrieval_context.py
.\.venv\Scripts\mypy.exe src/figure_data/ai/retrieval_context.py tests/ai/test_retrieval_context.py
```

Expected:

```text
All Task 1 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add src/figure_data/ai/retrieval_context.py tests/ai/test_retrieval_context.py
git commit -m "feat: 添加 AI RAG 上下文模型"
```

## Task 2: Candidate Prompt Schema, Prompt Text, And Policy

**Files:**

- Modify: `src/figure_data/ai/candidate_context.py`
- Modify: `src/figure_data/ai/schemas.py`
- Modify: `src/figure_data/ai/candidate_policy.py`
- Modify: `src/figure_data/ai/prompts.py`
- Test: `tests/ai/test_candidate_context.py`
- Test: `tests/ai/test_candidate_prompt_schema.py`
- Test: `tests/ai/test_candidate_policy.py`

- [ ] **Step 1: Add failing candidate context tests**

Append to `tests/ai/test_candidate_context.py`:

```python
from figure_data.ai.retrieval_context import AIRetrievalContextItem
```

Append these tests:

```python
def retrieval_item() -> AIRetrievalContextItem:
    return AIRetrievalContextItem(
        document_id="00000000-0000-0000-0000-000000000501",
        source_kind="source_ref",
        source_pk="source_ref:3853784",
        source_ref_id=3853784,
        encounter_evidence_id=None,
        source_work_id=111,
        title_zh="续资治通鉴长编",
        title_en=None,
        pages="卷一",
        score=0.88,
        snippet="许几谒见韩琦。",
        provider="fake",
        model_name="fake-hash-embedding",
        embedding_dimensions=8,
    )


def test_candidate_review_prompt_input_accepts_retrieval_context() -> None:
    prompt_input = candidate_review_prompt_input_from_detail(
        candidate_detail(),
        has_active_path_encounter_for_pair=False,
        retrieval_context=[retrieval_item()],
        retrieval_context_status="available",
    )

    payload = prompt_input.model_dump(mode="json")

    assert payload["retrieval_context_status"] == "available"
    assert payload["retrieval_context"][0]["document_id"] == (
        "00000000-0000-0000-0000-000000000501"
    )
    assert payload["retrieval_context"][0]["source_ref_id"] == 3853784


def test_candidate_review_prompt_input_defaults_to_missing_retrieval_context() -> None:
    prompt_input = candidate_review_prompt_input_from_detail(
        candidate_detail(),
        has_active_path_encounter_for_pair=False,
    )

    payload = prompt_input.model_dump(mode="json")

    assert payload["retrieval_context"] == []
    assert payload["retrieval_context_status"] == "missing"
```

`candidate_detail()` 是 `tests/ai/test_candidate_context.py` 中已有的 fixture helper。

- [ ] **Step 2: Add failing candidate schema and policy tests**

Append to `tests/ai/test_candidate_prompt_schema.py`:

```python
def test_candidate_review_suggestion_output_accepts_retrieval_trace_fields() -> None:
    output = CandidateReviewSuggestionOutput.model_validate(
        {
            "suggested_action": "needs_human_review",
            "priority_score": 50,
            "evidence_summary_draft": "结构化关系显示二人可能有互动，需要人工查证。",
            "risk_flags": ["retrieval_context_missing"],
            "supporting_source_ref_ids": [3853784],
            "review_questions": ["是否有原文？"],
            "explanation": "RAG 召回上下文仅供辅助阅读。",
            "retrieval_source_ref_ids": [3853784],
            "retrieval_document_ids": ["00000000-0000-0000-0000-000000000501"],
            "retrieval_limitations": ["RAG 召回不是已审核证据。"],
        }
    )

    assert output.retrieval_source_ref_ids == [3853784]
    assert output.retrieval_document_ids == ["00000000-0000-0000-0000-000000000501"]
    assert output.retrieval_limitations == ["RAG 召回不是已审核证据。"]


def test_candidate_review_prompt_mentions_retrieval_context_boundary() -> None:
    prompt = get_prompt_definition("candidate_review_suggestion")

    assert "retrieval_context" in prompt.user_prompt_template
    assert "RAG 召回上下文不是已审核事实" in prompt.system_prompt
```

Append to `tests/ai/test_candidate_policy.py`:

```python
def candidate_output(**updates: object) -> CandidateReviewSuggestionOutput:
    payload: dict[str, object] = {
        "suggested_action": "needs_human_review",
        "priority_score": 50,
        "evidence_summary_draft": "结构化关系显示二人可能有互动，需要人工查证。",
        "risk_flags": [],
        "supporting_source_ref_ids": [3853784],
        "review_questions": ["是否有原文？"],
        "explanation": "该建议基于输入资料。",
        "retrieval_source_ref_ids": [],
        "retrieval_document_ids": [],
        "retrieval_limitations": [],
    }
    payload.update(updates)
    return CandidateReviewSuggestionOutput.model_validate(payload)


def test_candidate_policy_accepts_known_retrieval_ids() -> None:
    validate_candidate_review_suggestion_policy(
        candidate_output(
            retrieval_source_ref_ids=[3853784],
            retrieval_document_ids=["00000000-0000-0000-0000-000000000501"],
        ),
        allowed_source_ref_ids={3853784},
        allowed_retrieval_source_ref_ids={3853784},
        allowed_retrieval_document_ids={"00000000-0000-0000-0000-000000000501"},
    )


def test_candidate_policy_rejects_unknown_retrieval_source_ref_id() -> None:
    with raises(AIOutputPolicyViolation, match="unknown retrieval source_ref_id"):
        validate_candidate_review_suggestion_policy(
            candidate_output(retrieval_source_ref_ids=[999999]),
            allowed_source_ref_ids={3853784},
            allowed_retrieval_source_ref_ids={3853784},
            allowed_retrieval_document_ids=set(),
        )


def test_candidate_policy_rejects_unknown_retrieval_document_id() -> None:
    with raises(AIOutputPolicyViolation, match="unknown retrieval document_id"):
        validate_candidate_review_suggestion_policy(
            candidate_output(retrieval_document_ids=["missing-document"]),
            allowed_source_ref_ids={3853784},
            allowed_retrieval_source_ref_ids=set(),
            allowed_retrieval_document_ids={"00000000-0000-0000-0000-000000000501"},
        )
```

Ensure `tests/ai/test_candidate_policy.py` has these imports:

```python
from pytest import raises

from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.schemas import CandidateReviewSuggestionOutput
```

- [ ] **Step 3: Run Task 2 tests and confirm they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ai/test_candidate_context.py tests/ai/test_candidate_prompt_schema.py tests/ai/test_candidate_policy.py -q
```

Expected:

```text
FAIL because candidate prompt input, output schema, prompt text and policy do not support retrieval context yet.
```

- [ ] **Step 4: Extend candidate prompt input model**

Modify `src/figure_data/ai/candidate_context.py`.

Add import:

```python
from typing import Literal

from figure_data.ai.retrieval_context import AIRetrievalContextItem
```

Change `CandidateReviewPromptInput` to:

```python
class CandidateReviewPromptInput(BaseModel):
    candidate: CandidateReviewCandidateInput
    person_a: CandidateReviewPersonInput
    person_b: CandidateReviewPersonInput
    source_refs: list[CandidateReviewSourceRefInput]
    retrieval_context: list[AIRetrievalContextItem] = Field(default_factory=list)
    retrieval_context_status: Literal["available", "missing"] = "missing"
```

Change `candidate_review_prompt_input_from_detail()` signature:

```python
def candidate_review_prompt_input_from_detail(
    detail: CandidateDetail,
    *,
    has_active_path_encounter_for_pair: bool,
    retrieval_context: list[AIRetrievalContextItem] | None = None,
    retrieval_context_status: Literal["available", "missing"] = "missing",
) -> CandidateReviewPromptInput:
```

Add the new fields to the returned `CandidateReviewPromptInput`:

```python
        source_refs=[_source_ref_input(source_ref) for source_ref in detail.source_refs],
        retrieval_context=retrieval_context or [],
        retrieval_context_status=retrieval_context_status,
```

Leave `build_candidate_review_prompt_input()` default behavior unchanged by not passing retrieval context there.

- [ ] **Step 5: Extend candidate output schema and policy**

Modify `src/figure_data/ai/schemas.py` by adding these fields to `CandidateReviewSuggestionOutput`:

```python
    retrieval_source_ref_ids: list[int] = Field(default_factory=list, max_length=50)
    retrieval_document_ids: list[str] = Field(default_factory=list, max_length=50)
    retrieval_limitations: list[str] = Field(default_factory=list, max_length=20)
```

Modify `src/figure_data/ai/candidate_policy.py`:

```python
def validate_candidate_review_suggestion_policy(
    output: CandidateReviewSuggestionOutput,
    *,
    allowed_source_ref_ids: set[int],
    allowed_retrieval_source_ref_ids: set[int] | None = None,
    allowed_retrieval_document_ids: set[str] | None = None,
) -> None:
    resolved_retrieval_source_ref_ids = allowed_retrieval_source_ref_ids or set()
    resolved_retrieval_document_ids = allowed_retrieval_document_ids or set()
    unknown_source_ref_ids = [
        source_ref_id
        for source_ref_id in output.supporting_source_ref_ids
        if source_ref_id not in allowed_source_ref_ids
    ]
    if unknown_source_ref_ids:
        joined = ",".join(str(source_ref_id) for source_ref_id in unknown_source_ref_ids)
        raise AIOutputPolicyViolation(f"unknown source_ref_id in AI output: {joined}")
    unknown_retrieval_source_ref_ids = [
        source_ref_id
        for source_ref_id in output.retrieval_source_ref_ids
        if source_ref_id not in resolved_retrieval_source_ref_ids
    ]
    if unknown_retrieval_source_ref_ids:
        joined = ",".join(str(source_ref_id) for source_ref_id in unknown_retrieval_source_ref_ids)
        raise AIOutputPolicyViolation(f"unknown retrieval source_ref_id in AI output: {joined}")
    unknown_retrieval_document_ids = [
        document_id
        for document_id in output.retrieval_document_ids
        if document_id not in resolved_retrieval_document_ids
    ]
    if unknown_retrieval_document_ids:
        joined = ",".join(unknown_retrieval_document_ids)
        raise AIOutputPolicyViolation(f"unknown retrieval document_id in AI output: {joined}")
    if not output.explanation.strip():
        raise AIOutputPolicyViolation("explanation is required")
    if not output.evidence_summary_draft.strip():
        raise AIOutputPolicyViolation("evidence_summary_draft is required")
```

- [ ] **Step 6: Update candidate prompt text**

Modify `CANDIDATE_REVIEW_SUGGESTION_PROMPT` in `src/figure_data/ai/prompts.py`.

Add this sentence into `system_prompt` before `"只返回 JSON object。"`:

```python
        "retrieval_context 是 RAG 召回上下文，不是已审核事实，不得把它当作自动提升依据。"
        "如果引用 retrieval_context，只能写入 retrieval_source_ref_ids、retrieval_document_ids 或 retrieval_limitations。"
```

Update `user_prompt_template` output field list:

```python
        "输出字段必须为 suggested_action, priority_score, evidence_summary_draft, "
        "risk_flags, supporting_source_ref_ids, review_questions, explanation, "
        "retrieval_source_ref_ids, retrieval_document_ids, retrieval_limitations。"
```

- [ ] **Step 7: Run Task 2 tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ai/test_candidate_context.py tests/ai/test_candidate_prompt_schema.py tests/ai/test_candidate_policy.py -q
.\.venv\Scripts\ruff.exe check src/figure_data/ai/candidate_context.py src/figure_data/ai/candidate_policy.py src/figure_data/ai/prompts.py src/figure_data/ai/schemas.py tests/ai/test_candidate_context.py tests/ai/test_candidate_prompt_schema.py tests/ai/test_candidate_policy.py
.\.venv\Scripts\mypy.exe src/figure_data/ai/candidate_context.py src/figure_data/ai/candidate_policy.py src/figure_data/ai/prompts.py src/figure_data/ai/schemas.py tests/ai/test_candidate_context.py tests/ai/test_candidate_prompt_schema.py tests/ai/test_candidate_policy.py
```

Expected:

```text
All Task 2 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 8: Commit Task 2**

Run:

```powershell
git add src/figure_data/ai/candidate_context.py src/figure_data/ai/candidate_policy.py src/figure_data/ai/prompts.py src/figure_data/ai/schemas.py tests/ai/test_candidate_context.py tests/ai/test_candidate_prompt_schema.py tests/ai/test_candidate_policy.py
git commit -m "feat: 扩展候选建议 RAG 上下文 schema"
```

## Task 3: Candidate Service RAG Integration

**Files:**

- Modify: `src/figure_data/ai/candidate_service.py`
- Modify: `src/figure_data/ai/provider.py`
- Test: `tests/ai/test_candidate_service.py`
- Test: `tests/ai/test_provider.py`

- [ ] **Step 1: Add failing candidate service tests**

Append to `tests/ai/test_candidate_service.py`:

```python
from types import SimpleNamespace
from typing import Any

from pytest import MonkeyPatch

from figure_data.ai.candidate_service import generate_candidate_review_suggestion
from figure_data.ai.service import AIRunResult
from figure_data.ai.types import AIProviderRequest, AIProviderResponse
from figure_data.ai.retrieval_repository import RetrievalSearchResult
from figure_data.ai.retrieval_service import SearchRagEvidenceResult
from tests.ai.test_candidate_context import candidate_detail
```

Add these helpers:

```python
class FakeProvider:
    provider_name = "fake"

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        return AIProviderResponse(
            raw_text="{}",
            provider=self.provider_name,
            model_name=request.model_name,
        )


class CapturingPromptRunner:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}
        self.run_id = UUID("00000000-0000-0000-0000-000000000301")

    def __call__(self, **kwargs: object) -> AIRunResult[CandidateReviewSuggestionOutput]:
        self.kwargs = kwargs
        output = CandidateReviewSuggestionOutput.model_validate(
            {
                "suggested_action": "needs_human_review",
                "priority_score": 50,
                "evidence_summary_draft": "结构化关系显示二人可能有互动，需要人工查证。",
                "risk_flags": [],
                "supporting_source_ref_ids": [501],
                "review_questions": ["是否有原文？"],
                "explanation": "该建议基于输入资料。",
                "retrieval_source_ref_ids": [3853784],
                "retrieval_document_ids": [
                    "00000000-0000-0000-0000-000000000501",
                ],
                "retrieval_limitations": ["RAG 召回上下文不是已审核事实。"],
            }
        )
        return AIRunResult(run_id=self.run_id, output=output)


def settings() -> Any:
    return SimpleNamespace(
        ai_model="fake-history-model",
        ai_max_output_tokens=1200,
        embedding_provider="fake",
        embedding_model="fake-hash-embedding",
        embedding_dimensions=8,
    )


def fake_retrieval_search(**kwargs: object) -> SearchRagEvidenceResult:
    return SearchRagEvidenceResult(
        query="许几 韩琦",
        provider="fake",
        model_name="fake-hash-embedding",
        results=[
            RetrievalSearchResult(
                document_id=UUID("00000000-0000-0000-0000-000000000501"),
                source_kind="source_ref",
                source_pk="source_ref:3853784",
                source_ref_id=3853784,
                encounter_evidence_id=None,
                source_work_id=111,
                title_zh="续资治通鉴长编",
                title_en=None,
                pages="卷一",
                chunk_index=0,
                content_text="许几谒见韩琦。",
                text_hash="abc",
                score=0.88,
            )
        ],
    )
```

Add this test near the existing `generate_candidate_review_suggestion` service tests:

```python
def test_generate_candidate_review_suggestion_adds_retrieval_context(
    monkeypatch: MonkeyPatch,
) -> None:
    session = object()
    repository = FakeRepository()
    provider = FakeProvider()
    monkeypatch.setattr(
        "figure_data.ai.candidate_service.get_candidate_detail",
        lambda session, kind, candidate_id: candidate_detail(),
    )
    runner = CapturingPromptRunner()
    monkeypatch.setattr("figure_data.ai.candidate_service.run_ai_prompt", runner)

    result = generate_candidate_review_suggestion(
        session=session,  # type: ignore[arg-type]
        settings=settings(),
        kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        created_by="lyl",
        provider=provider,
        repository=repository,
        retrieval_search=fake_retrieval_search,
    )

    assert result.ai_run_id == runner.run_id
    prompt_snapshot = runner.kwargs["input_snapshot"]
    assert prompt_snapshot["retrieval_context_status"] == "available"
    assert prompt_snapshot["retrieval_context"][0]["document_id"] == (
        "00000000-0000-0000-0000-000000000501"
    )
```

Add another test:

```python
def test_generate_candidate_review_suggestion_runs_without_retrieval_results(
    monkeypatch: MonkeyPatch,
) -> None:
    session = object()
    repository = FakeRepository()
    provider = FakeProvider()
    monkeypatch.setattr(
        "figure_data.ai.candidate_service.get_candidate_detail",
        lambda session, kind, candidate_id: candidate_detail(),
    )
    runner = CapturingPromptRunner()
    monkeypatch.setattr("figure_data.ai.candidate_service.run_ai_prompt", runner)

    def empty_retrieval_search(**kwargs: object) -> SearchRagEvidenceResult:
        return SearchRagEvidenceResult(
            query="许几 韩琦",
            provider="fake",
            model_name="fake-hash-embedding",
            results=[],
        )

    generate_candidate_review_suggestion(
        session=session,  # type: ignore[arg-type]
        settings=settings(),
        kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        created_by="lyl",
        provider=provider,
        repository=repository,
        retrieval_search=empty_retrieval_search,
    )

    prompt_snapshot = runner.kwargs["input_snapshot"]
    assert prompt_snapshot["retrieval_context_status"] == "missing"
    assert prompt_snapshot["retrieval_context"] == []
```

The import from `tests.ai.test_candidate_context` reuses the repository's existing candidate fixture and avoids copying a large `CandidateDetail` fixture into this file.

- [ ] **Step 2: Add failing fake provider tests**

Append to `tests/ai/test_provider.py`:

```python
def test_fake_ai_provider_preserves_candidate_retrieval_trace_fields() -> None:
    provider = FakeAIProvider()

    response = provider.generate(
        AIProviderRequest(
            system_prompt="system",
            user_prompt=(
                '输入 JSON：{"candidate":{"id":1},"source_refs":[{"source_ref_id":3853784}],'
                '"retrieval_context":[{"document_id":"00000000-0000-0000-0000-000000000501",'
                '"source_ref_id":3853784}]} '
                "输出字段必须为 suggested_action, priority_score, evidence_summary_draft, "
                "risk_flags, supporting_source_ref_ids, review_questions, explanation, "
                "retrieval_source_ref_ids, retrieval_document_ids, retrieval_limitations。"
            ),
            model_name="fake-model",
            max_output_tokens=1200,
        )
    )

    payload = json.loads(response.raw_text)

    assert payload["retrieval_source_ref_ids"] == [3853784]
    assert payload["retrieval_document_ids"] == [
        "00000000-0000-0000-0000-000000000501"
    ]
    assert payload["retrieval_limitations"] == ["RAG 召回上下文不是已审核事实。"]
```

Add this import to the top of `tests/ai/test_provider.py`:

```python
import json
```

- [ ] **Step 3: Run Task 3 tests and confirm they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ai/test_candidate_service.py tests/ai/test_provider.py -q
```

Expected:

```text
FAIL because candidate service does not call retrieval_search and fake provider does not emit retrieval trace fields.
```

- [ ] **Step 4: Integrate RAG search into candidate service**

Modify imports in `src/figure_data/ai/candidate_service.py`:

```python
from collections.abc import Callable

from figure_data.ai.candidate_context import CandidateReviewPromptInput
from figure_data.ai.retrieval_context import (
    build_candidate_retrieval_query,
    retrieval_context_items_from_search_results,
    retrieval_document_ids,
    retrieval_source_ref_ids,
)
from figure_data.ai.retrieval_service import (
    SearchRagEvidenceOptions,
    SearchRagEvidenceResult,
    search_rag_evidence,
)
```

Change `generate_candidate_review_suggestion()` signature:

```python
def generate_candidate_review_suggestion(
    *,
    session: Session,
    settings: Settings,
    kind: CandidateKind,
    candidate_id: int,
    created_by: str,
    provider: AIProvider | None = None,
    repository: CandidateSuggestionRepository | None = None,
    retrieval_limit: int = 5,
    retrieval_search: Callable[..., SearchRagEvidenceResult] = search_rag_evidence,
) -> CandidateReviewSuggestionResult:
```

Replace the prompt input construction block with:

```python
    detail = get_candidate_detail(session, kind, candidate_id)
    base_prompt_input = build_candidate_review_prompt_input(session, detail)
    retrieval_result = retrieval_search(
        session=session,
        settings=settings,
        options=SearchRagEvidenceOptions(
            query=_candidate_retrieval_query(base_prompt_input),
            source_ref_id=None,
            limit=retrieval_limit,
        ),
    )
    retrieval_context = retrieval_context_items_from_search_results(
        retrieval_result.results,
        provider=retrieval_result.provider,
        model_name=retrieval_result.model_name,
        embedding_dimensions=settings.embedding_dimensions,
    )
    prompt_input = base_prompt_input.model_copy(
        update={
            "retrieval_context": retrieval_context,
            "retrieval_context_status": "available" if retrieval_context else "missing",
        }
    )
```

Update `output_guard`:

```python
        output_guard=lambda output: validate_candidate_review_suggestion_policy(
            output,
            allowed_source_ref_ids=allowed_source_ref_ids,
            allowed_retrieval_source_ref_ids=retrieval_source_ref_ids(retrieval_context),
            allowed_retrieval_document_ids=retrieval_document_ids(retrieval_context),
        ),
```

Add helper at the bottom of the file before `_require_ai_model()`:

```python
def _candidate_retrieval_query(prompt_input: CandidateReviewPromptInput) -> str:
    candidate_input = prompt_input.candidate
    source_refs = prompt_input.source_refs
    return build_candidate_retrieval_query(
        person_a_names=[
            prompt_input.person_a.primary_name_zh_hant,
            prompt_input.person_a.primary_name_zh_hans,
            prompt_input.person_a.primary_name_romanized,
        ],
        person_b_names=[
            prompt_input.person_b.primary_name_zh_hant,
            prompt_input.person_b.primary_name_zh_hans,
            prompt_input.person_b.primary_name_romanized,
        ],
        relation_label=candidate_input.relation_label,
        candidate_basis=candidate_input.candidate_basis,
        source_titles=[
            source_ref.title_zh or source_ref.title_en
            for source_ref in source_refs
        ],
        notes=[candidate_input.notes, *[source_ref.notes for source_ref in source_refs]],
    )
```

- [ ] **Step 5: Update fake provider candidate output**

Modify `_fake_candidate_suggestion_response()` in `src/figure_data/ai/provider.py`.

After `source_ref_ids` computation, add:

```python
    retrieval_context = payload.get("retrieval_context", [])
    if not isinstance(retrieval_context, list):
        retrieval_context = []
    retrieval_source_ref_ids = [
        item["source_ref_id"]
        for item in retrieval_context
        if isinstance(item, dict) and isinstance(item.get("source_ref_id"), int)
    ]
    retrieval_document_ids = [
        item["document_id"]
        for item in retrieval_context
        if isinstance(item, dict) and isinstance(item.get("document_id"), str)
    ]
```

Add these fields to the returned JSON object:

```python
            "retrieval_source_ref_ids": retrieval_source_ref_ids[:3],
            "retrieval_document_ids": retrieval_document_ids[:3],
            "retrieval_limitations": (
                ["RAG 召回上下文不是已审核事实。"] if retrieval_document_ids else []
            ),
```

- [ ] **Step 6: Run Task 3 tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ai/test_candidate_service.py tests/ai/test_provider.py -q
.\.venv\Scripts\ruff.exe check src/figure_data/ai/candidate_service.py src/figure_data/ai/provider.py tests/ai/test_candidate_service.py tests/ai/test_provider.py
.\.venv\Scripts\mypy.exe src/figure_data/ai/candidate_service.py src/figure_data/ai/provider.py tests/ai/test_candidate_service.py tests/ai/test_provider.py
```

Expected:

```text
All Task 3 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 7: Commit Task 3**

Run:

```powershell
git add src/figure_data/ai/candidate_service.py src/figure_data/ai/provider.py tests/ai/test_candidate_service.py tests/ai/test_provider.py
git commit -m "feat: 接入候选建议 RAG prompt 上下文"
```

## Task 4: Chain Prompt Schema, Prompt Text, And Policy

**Files:**

- Modify: `src/figure_data/ai/chain_context.py`
- Modify: `src/figure_data/ai/schemas.py`
- Modify: `src/figure_data/ai/chain_policy.py`
- Modify: `src/figure_data/ai/prompts.py`
- Test: `tests/ai/test_chain_context.py`
- Test: `tests/ai/test_chain_prompt_schema.py`
- Test: `tests/ai/test_chain_policy.py`

- [ ] **Step 1: Add failing chain context tests**

Append to `tests/ai/test_chain_context.py`:

```python
from figure_data.ai.retrieval_context import AIRetrievalContextItem
```

Append this helper:

```python
def retrieval_item() -> AIRetrievalContextItem:
    return AIRetrievalContextItem(
        document_id="00000000-0000-0000-0000-000000000501",
        source_kind="encounter_evidence",
        source_pk="encounter_evidence:12",
        source_ref_id=3853784,
        encounter_evidence_id=12,
        source_work_id=111,
        title_zh="续资治通鉴长编",
        title_en=None,
        pages="卷一",
        score=0.88,
        snippet="许几以诸生谒韩琦于魏。",
        provider="fake",
        model_name="fake-hash-embedding",
        embedding_dimensions=8,
    )
```

Append these tests:

```python
def test_build_chain_explanation_prompt_input_accepts_retrieval_context() -> None:
    prompt_input = build_chain_explanation_prompt_input(
        result=chain_result(),
        encounter_details={ENCOUNTER_ID: encounter_detail()},
        language="zh-Hans",
        retrieval_context=[retrieval_item()],
        retrieval_context_status="available",
    )

    payload = prompt_input.model_dump(mode="json")

    assert payload["retrieval_context_status"] == "available"
    assert payload["retrieval_context"][0]["document_id"] == (
        "00000000-0000-0000-0000-000000000501"
    )
    assert payload["retrieval_context"][0]["encounter_evidence_id"] == 12


def test_build_chain_explanation_prompt_input_defaults_to_missing_retrieval_context() -> None:
    prompt_input = build_chain_explanation_prompt_input(
        result=chain_result(),
        encounter_details={ENCOUNTER_ID: encounter_detail()},
        language="zh-Hans",
    )

    payload = prompt_input.model_dump(mode="json")

    assert payload["retrieval_context"] == []
    assert payload["retrieval_context_status"] == "missing"
```

`chain_result()`, `encounter_detail()` and `ENCOUNTER_ID` are existing helpers in `tests/ai/test_chain_context.py`.

- [ ] **Step 2: Add failing chain schema and policy tests**

Append to `tests/ai/test_chain_prompt_schema.py`:

```python
def test_chain_explanation_output_accepts_retrieval_trace_fields() -> None:
    output = ChainExplanationOutput.model_validate(
        {
            "summary": "许几与韩琦之间有已审核 encounter。",
            "edge_explanations": [
                {
                    "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                    "explanation": "许几曾谒见韩琦。",
                    "evidence_basis": "encounter_evidence",
                    "source_ref_ids": [3853784],
                }
            ],
            "source_notes": ["来源于已审核 evidence。"],
            "limitations": ["AI 解释不是新证据。"],
            "display_language": "zh-Hans",
            "retrieval_document_ids": ["00000000-0000-0000-0000-000000000501"],
            "retrieval_notes": ["RAG 召回上下文只用于辅助说明。"],
        }
    )

    assert output.retrieval_document_ids == [
        "00000000-0000-0000-0000-000000000501"
    ]
    assert output.retrieval_notes == ["RAG 召回上下文只用于辅助说明。"]


def test_chain_explanation_prompt_mentions_retrieval_context_boundary() -> None:
    prompt = get_prompt_definition("chain_explanation")

    assert "retrieval_context" in prompt.user_prompt_template
    assert "RAG 召回上下文不是已审核证据" in prompt.system_prompt
```

Append to `tests/ai/test_chain_policy.py`:

```python
def chain_output(**updates: object) -> ChainExplanationOutput:
    payload: dict[str, object] = {
        "summary": "许几与韩琦之间有已审核 encounter。",
        "edge_explanations": [
            {
                "encounter_id": "e1",
                "explanation": "许几曾谒见韩琦。",
                "evidence_basis": "encounter_evidence",
                "source_ref_ids": [3853784],
            }
        ],
        "source_notes": [],
        "limitations": ["AI 解释不是新证据。"],
        "display_language": "zh-Hans",
        "retrieval_document_ids": [],
        "retrieval_notes": [],
    }
    payload.update(updates)
    return ChainExplanationOutput.model_validate(payload)


def test_chain_policy_accepts_known_retrieval_document_ids() -> None:
    validate_chain_explanation_policy(
        chain_output(
            retrieval_document_ids=["00000000-0000-0000-0000-000000000501"]
        ),
        allowed_encounter_ids={"e1"},
        allowed_source_ref_ids={3853784},
        allowed_retrieval_document_ids={"00000000-0000-0000-0000-000000000501"},
    )


def test_chain_policy_rejects_unknown_retrieval_document_ids() -> None:
    with raises(AIOutputPolicyViolation, match="unknown retrieval document_id"):
        validate_chain_explanation_policy(
            chain_output(retrieval_document_ids=["missing-document"]),
            allowed_encounter_ids={"e1"},
            allowed_source_ref_ids={3853784},
            allowed_retrieval_document_ids={"00000000-0000-0000-0000-000000000501"},
        )
```

Ensure `tests/ai/test_chain_policy.py` has these imports:

```python
from pytest import raises

from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.schemas import ChainExplanationOutput
```

- [ ] **Step 3: Run Task 4 tests and confirm they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ai/test_chain_context.py tests/ai/test_chain_prompt_schema.py tests/ai/test_chain_policy.py -q
```

Expected:

```text
FAIL because chain prompt input, output schema, prompt text and policy do not support retrieval context yet.
```

- [ ] **Step 4: Extend chain prompt input model**

Modify `src/figure_data/ai/chain_context.py`.

Add import:

```python
from typing import Literal

from figure_data.ai.retrieval_context import AIRetrievalContextItem
```

Change `ChainExplanationPromptInput`:

```python
class ChainExplanationPromptInput(BaseModel):
    source_person_id: str
    target_person_id: str
    max_depth: int
    language: str
    people: list[ChainExplanationPersonInput]
    encounters: list[ChainExplanationEncounterInput]
    retrieval_context: list[AIRetrievalContextItem] = Field(default_factory=list)
    retrieval_context_status: Literal["available", "missing"] = "missing"
```

Change `build_chain_explanation_prompt_input()` signature:

```python
def build_chain_explanation_prompt_input(
    *,
    result: ChainLookupResult,
    encounter_details: dict[str, EncounterDetail],
    language: str,
    retrieval_context: list[AIRetrievalContextItem] | None = None,
    retrieval_context_status: Literal["available", "missing"] = "missing",
) -> ChainExplanationPromptInput:
```

Add the new fields to the returned `ChainExplanationPromptInput`:

```python
        people=people,
        encounters=encounters,
        retrieval_context=retrieval_context or [],
        retrieval_context_status=retrieval_context_status,
```

- [ ] **Step 5: Extend chain output schema and policy**

Modify `src/figure_data/ai/schemas.py` by adding these fields to `ChainExplanationOutput`:

```python
    retrieval_document_ids: list[str] = Field(default_factory=list, max_length=50)
    retrieval_notes: list[str] = Field(default_factory=list, max_length=50)
```

Modify `src/figure_data/ai/chain_policy.py` signature:

```python
def validate_chain_explanation_policy(
    output: ChainExplanationOutput,
    *,
    allowed_encounter_ids: set[str],
    allowed_source_ref_ids: set[int],
    allowed_retrieval_document_ids: set[str] | None = None,
) -> None:
```

Add after the source ref validation loop and before `missing_edges`:

```python
    resolved_retrieval_document_ids = allowed_retrieval_document_ids or set()
    unknown_retrieval_document_ids = [
        document_id
        for document_id in output.retrieval_document_ids
        if document_id not in resolved_retrieval_document_ids
    ]
    if unknown_retrieval_document_ids:
        joined = ",".join(unknown_retrieval_document_ids)
        raise AIOutputPolicyViolation(f"unknown retrieval document_id in AI output: {joined}")
```

- [ ] **Step 6: Update chain prompt text**

Modify `CHAIN_EXPLANATION_PROMPT` in `src/figure_data/ai/prompts.py`.

Add this sentence into `system_prompt` before `"只返回 JSON object。"`:

```python
        "retrieval_context 是 RAG 召回上下文，不是已审核证据；只能用于补充来源说明或限制说明。"
        "不得用 retrieval_context 编造输入之外的人物关系或见面场景。"
```

Update `user_prompt_template` output field list:

```python
        "输出字段必须为 summary, edge_explanations, source_notes, limitations, "
        "display_language, retrieval_document_ids, retrieval_notes。"
```

- [ ] **Step 7: Run Task 4 tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ai/test_chain_context.py tests/ai/test_chain_prompt_schema.py tests/ai/test_chain_policy.py -q
.\.venv\Scripts\ruff.exe check src/figure_data/ai/chain_context.py src/figure_data/ai/chain_policy.py src/figure_data/ai/prompts.py src/figure_data/ai/schemas.py tests/ai/test_chain_context.py tests/ai/test_chain_prompt_schema.py tests/ai/test_chain_policy.py
.\.venv\Scripts\mypy.exe src/figure_data/ai/chain_context.py src/figure_data/ai/chain_policy.py src/figure_data/ai/prompts.py src/figure_data/ai/schemas.py tests/ai/test_chain_context.py tests/ai/test_chain_prompt_schema.py tests/ai/test_chain_policy.py
```

Expected:

```text
All Task 4 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 8: Commit Task 4**

Run:

```powershell
git add src/figure_data/ai/chain_context.py src/figure_data/ai/chain_policy.py src/figure_data/ai/prompts.py src/figure_data/ai/schemas.py tests/ai/test_chain_context.py tests/ai/test_chain_prompt_schema.py tests/ai/test_chain_policy.py
git commit -m "feat: 扩展链解释 RAG 上下文 schema"
```

## Task 5: Chain Service RAG Integration

**Files:**

- Modify: `src/figure_data/ai/chain_service.py`
- Modify: `src/figure_data/ai/provider.py`
- Test: `tests/ai/test_chain_service.py`
- Test: `tests/ai/test_provider.py`

- [ ] **Step 1: Add failing chain service tests**

Append to `tests/ai/test_chain_service.py`:

```python
from figure_data.ai.retrieval_repository import RetrievalSearchResult
from figure_data.ai.retrieval_service import SearchRagEvidenceResult
```

Modify the existing `settings()` helper in `tests/ai/test_chain_service.py`:

```python
def settings() -> Any:
    return SimpleNamespace(
        ai_model="fake-history-model",
        ai_max_output_tokens=1200,
        embedding_provider="fake",
        embedding_model="fake-hash-embedding",
        embedding_dimensions=8,
    )
```

Add helper:

```python
def fake_chain_retrieval_search(**kwargs: object) -> SearchRagEvidenceResult:
    return SearchRagEvidenceResult(
        query="许几 韩琦",
        provider="fake",
        model_name="fake-hash-embedding",
        results=[
            RetrievalSearchResult(
                document_id=UUID("00000000-0000-0000-0000-000000000601"),
                source_kind="encounter_evidence",
                source_pk="encounter_evidence:12",
                source_ref_id=3853784,
                encounter_evidence_id=12,
                source_work_id=111,
                title_zh="续资治通鉴长编",
                title_en=None,
                pages="卷一",
                chunk_index=0,
                content_text="许几以诸生谒韩琦于魏。",
                text_hash="abc",
                score=0.88,
            )
        ],
    )
```

Add test near the existing `test_generate_chain_explanation_for_result_calls_prompt_runner`:

```python
def test_generate_chain_explanation_for_result_adds_scoped_retrieval_context() -> None:
    runner = CapturingPromptRunner()

    result = generate_chain_explanation_for_result(
        session=object(),
        result=chain_result(),
        encounter_details={ENCOUNTER_ID: encounter_detail()},
        settings=settings(),
        provider=FakeProvider(),
        created_by="lyl",
        repository=FakeChainRepository(),
        run_prompt=runner,
        retrieval_search=fake_chain_retrieval_search,
    )

    assert isinstance(result, ChainExplanationGenerationResult)
    prompt_snapshot = runner.kwargs["input_snapshot"]
    assert prompt_snapshot["retrieval_context_status"] == "available"
    assert prompt_snapshot["retrieval_context"][0]["document_id"] == (
        "00000000-0000-0000-0000-000000000601"
    )
    assert prompt_snapshot["retrieval_context"][0]["source_ref_id"] == 3853784
```

Add another test:

```python
def test_generate_chain_explanation_for_result_runs_without_retrieval_results() -> None:
    runner = CapturingPromptRunner()

    def empty_retrieval_search(**kwargs: object) -> SearchRagEvidenceResult:
        return SearchRagEvidenceResult(
            query="许几 韩琦",
            provider="fake",
            model_name="fake-hash-embedding",
            results=[],
        )

    generate_chain_explanation_for_result(
        session=object(),
        result=chain_result(),
        encounter_details={ENCOUNTER_ID: encounter_detail()},
        settings=settings(),
        provider=FakeProvider(),
        created_by="lyl",
        repository=FakeChainRepository(),
        run_prompt=runner,
        retrieval_search=empty_retrieval_search,
    )

    prompt_snapshot = runner.kwargs["input_snapshot"]
    assert prompt_snapshot["retrieval_context_status"] == "missing"
    assert prompt_snapshot["retrieval_context"] == []
```

These tests reuse the current file's existing fake result, encounter detail, provider, repository and prompt runner helpers.

- [ ] **Step 2: Add failing fake provider chain test**

Append to `tests/ai/test_provider.py`:

```python
def test_fake_ai_provider_preserves_chain_retrieval_trace_fields() -> None:
    provider = FakeAIProvider()

    response = provider.generate(
        AIProviderRequest(
            system_prompt="system",
            user_prompt=(
                '输入 JSON：{"encounters":[{"encounter_id":"e1","source_refs":[{"source_ref_id":3853784}]}],'
                '"retrieval_context":[{"document_id":"00000000-0000-0000-0000-000000000601",'
                '"source_ref_id":3853784}]} '
                "输出字段必须为 summary, edge_explanations, source_notes, limitations, "
                "display_language, retrieval_document_ids, retrieval_notes。"
            ),
            model_name="fake-model",
            max_output_tokens=1200,
        )
    )

    payload = json.loads(response.raw_text)

    assert payload["retrieval_document_ids"] == [
        "00000000-0000-0000-0000-000000000601"
    ]
    assert payload["retrieval_notes"] == ["RAG 召回上下文只用于辅助说明。"]
```

- [ ] **Step 3: Run Task 5 tests and confirm they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ai/test_chain_service.py tests/ai/test_provider.py -q
```

Expected:

```text
FAIL because chain service does not call retrieval_search and fake provider does not emit chain retrieval trace fields.
```

- [ ] **Step 4: Integrate scoped RAG search into chain service**

Modify imports in `src/figure_data/ai/chain_service.py`:

```python
from figure_data.ai.chain_context import ChainExplanationPromptInput
from figure_data.ai.retrieval_context import (
    AIRetrievalContextItem,
    build_chain_retrieval_queries,
    retrieval_context_items_from_search_results,
    retrieval_document_ids,
)
from figure_data.ai.retrieval_service import (
    SearchRagEvidenceOptions,
    SearchRagEvidenceResult,
    search_rag_evidence,
)
```

Change `generate_chain_explanation_for_result()` signature:

```python
def generate_chain_explanation_for_result(
    *,
    session: object,
    result: ChainLookupResult,
    encounter_details: dict[str, EncounterDetail],
    settings: Settings,
    provider: AIProvider | None,
    created_by: str,
    language: str = "zh-Hans",
    repository: ChainExplanationRepository | None = None,
    run_repository: AIRunRepository | None = None,
    run_prompt: Callable[..., AIRunResult[ChainExplanationOutput]] = run_ai_prompt,
    retrieval_limit: int = 3,
    retrieval_search: Callable[..., SearchRagEvidenceResult] = search_rag_evidence,
) -> ChainExplanationGenerationResult:
```

After successful base prompt input construction, add:

```python
    retrieval_context = _chain_retrieval_context(
        session=session,
        settings=settings,
        prompt_input=prompt_input,
        retrieval_limit=retrieval_limit,
        retrieval_search=retrieval_search,
    )
    prompt_input = prompt_input.model_copy(
        update={
            "retrieval_context": retrieval_context,
            "retrieval_context_status": "available" if retrieval_context else "missing",
        }
    )
```

Update `output_guard`:

```python
        output_guard=lambda output: validate_chain_explanation_policy(
            output,
            allowed_encounter_ids=allowed_encounter_ids,
            allowed_source_ref_ids=allowed_source_ref_ids,
            allowed_retrieval_document_ids=retrieval_document_ids(retrieval_context),
        ),
```

Add helper before `_load_encounter_details()`:

```python
def _chain_retrieval_context(
    *,
    session: object,
    settings: Settings,
    prompt_input: ChainExplanationPromptInput,
    retrieval_limit: int,
    retrieval_search: Callable[..., SearchRagEvidenceResult],
) -> list[AIRetrievalContextItem]:
    source_ref_ids = _source_ref_ids_for_prompt_input(prompt_input)
    if not source_ref_ids:
        return []
    results: list[AIRetrievalContextItem] = []
    for source_ref_id, query in build_chain_retrieval_queries(
        people_names=[person.display_name for person in prompt_input.people],
        encounter_summaries=[
            encounter.evidence_summary for encounter in prompt_input.encounters
        ],
        source_ref_ids=source_ref_ids,
    ):
        retrieval_result = retrieval_search(
            session=session,
            settings=settings,
            options=SearchRagEvidenceOptions(
                query=query,
                source_ref_id=source_ref_id,
                limit=retrieval_limit,
            ),
        )
        results.extend(
            retrieval_context_items_from_search_results(
                retrieval_result.results,
                provider=retrieval_result.provider,
                model_name=retrieval_result.model_name,
                embedding_dimensions=settings.embedding_dimensions,
            )
        )
    return _deduplicate_retrieval_context(results)


def _source_ref_ids_for_prompt_input(prompt_input: ChainExplanationPromptInput) -> list[int]:
    source_ref_ids: list[int] = []
    for encounter in prompt_input.encounters:
        for source_ref in encounter.source_refs:
            source_ref_ids.append(source_ref.source_ref_id)
        for evidence in encounter.evidence:
            if evidence.source_ref_id is not None:
                source_ref_ids.append(evidence.source_ref_id)
    return source_ref_ids


def _deduplicate_retrieval_context(
    items: list[AIRetrievalContextItem],
) -> list[AIRetrievalContextItem]:
    deduped: list[AIRetrievalContextItem] = []
    seen: set[str] = set()
    for item in items:
        if item.document_id in seen:
            continue
        seen.add(item.document_id)
        deduped.append(item)
    return deduped
```

- [ ] **Step 5: Update fake provider chain output**

Modify `_fake_chain_explanation_response()` in `src/figure_data/ai/provider.py`.

After `encounters` handling, add:

```python
    retrieval_context = payload.get("retrieval_context", [])
    if not isinstance(retrieval_context, list):
        retrieval_context = []
    retrieval_document_ids = [
        item["document_id"]
        for item in retrieval_context
        if isinstance(item, dict) and isinstance(item.get("document_id"), str)
    ]
```

Add these fields to the returned JSON object:

```python
            "retrieval_document_ids": retrieval_document_ids[:5],
            "retrieval_notes": (
                ["RAG 召回上下文只用于辅助说明。"] if retrieval_document_ids else []
            ),
```

- [ ] **Step 6: Run Task 5 tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ai/test_chain_service.py tests/ai/test_provider.py -q
.\.venv\Scripts\ruff.exe check src/figure_data/ai/chain_service.py src/figure_data/ai/provider.py tests/ai/test_chain_service.py tests/ai/test_provider.py
.\.venv\Scripts\mypy.exe src/figure_data/ai/chain_service.py src/figure_data/ai/provider.py tests/ai/test_chain_service.py tests/ai/test_provider.py
```

Expected:

```text
All Task 5 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 7: Commit Task 5**

Run:

```powershell
git add src/figure_data/ai/chain_service.py src/figure_data/ai/provider.py tests/ai/test_chain_service.py tests/ai/test_provider.py
git commit -m "feat: 接入链解释 RAG prompt 上下文"
```

## Task 6: Documentation, Smoke, And Safety Validation

**Files:**

- Modify: `README.md`
- Modify: `tests/test_readme_commands.py`

- [ ] **Step 1: Add failing README coverage test**

Append to `tests/test_readme_commands.py`:

```python
def test_readme_documents_rag_prompt_integration_boundary() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "RAG 上下文接入 AI prompt" in readme
    assert "retrieval_context" in readme
    assert "RAG 召回上下文不是已审核事实" in readme
    assert "不会自动创建 encounter" in readme
```

- [ ] **Step 2: Run README test and confirm it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_readme_commands.py -q
```

Expected:

```text
FAIL because README does not document RAG prompt integration yet.
```

- [ ] **Step 3: Update README**

Add this section after `### RAG 证据检索试点`:

```markdown
### RAG 上下文接入 AI prompt

候选审核建议和 AI 人物链解释可以把 `retrieval_context` 放入 prompt 输入。`retrieval_context`
来自本地 RAG 检索索引，包含 retrieval document id、source kind、source ref id、
encounter evidence id、score 和 snippet。

RAG 召回上下文不是已审核事实，不会自动创建 encounter，不会修改 candidate、`encounter_evidence`
或 Neo4j，也不会改变 `/api/v1/chains/shortest` 的结果。模型输出中如果引用 RAG，只能记录
`retrieval_document_ids`、`retrieval_source_ref_ids`、`retrieval_notes` 或
`retrieval_limitations`，仍需人工审核后才可能进入事实源。

没有 RAG 结果时，AI 生成仍可继续运行，prompt 输入中的 `retrieval_context_status` 会记录为
`missing`。
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ai/test_retrieval_context.py tests/ai/test_candidate_context.py tests/ai/test_candidate_policy.py tests/ai/test_candidate_prompt_schema.py tests/ai/test_candidate_service.py tests/ai/test_chain_context.py tests/ai/test_chain_policy.py tests/ai/test_chain_prompt_schema.py tests/ai/test_chain_service.py tests/ai/test_provider.py tests/test_readme_commands.py -q
```

Expected:

```text
All focused AI/RAG prompt integration tests pass.
```

- [ ] **Step 5: Run full backend validation**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\figure-data.exe build-rag-index --help
.\.venv\Scripts\figure-data.exe search-rag-evidence --help
.\.venv\Scripts\figure-data.exe generate-chain-explanation --help
.\.venv\Scripts\figure-data.exe suggest-candidate-review --help
```

Expected:

```text
pytest passes.
ruff passes.
mypy passes.
alembic heads shows 20260613_0004 (head).
All CLI help commands exit 0.
```

- [ ] **Step 6: Run database and source safety validation**

Run:

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\figure-data.exe build-rag-index --source-ref-id 3853784 --limit 2
.\.venv\Scripts\figure-data.exe search-rag-evidence --query "许几 韩琦" --limit 5
.\.venv\Scripts\figure-data.exe validate-encounters
.\.venv\Scripts\figure-data.exe validate-graph
```

Expected:

```text
alembic current shows 20260613_0004 (head).
build-rag-index writes only ai_retrieval index rows.
search-rag-evidence prints result rows with document_id/source_pk/source_ref_id/encounter_evidence_id.
validate-encounters passes.
validate-graph passes.
```

If the sandbox blocks `192.168.8.17:6432` or Neo4j, rerun only the blocked database commands with approved escalation and record the exact output.

- [ ] **Step 7: Run fake-provider prompt integration smoke**

Run:

```powershell
$env:FIGURE_AI_ENABLED="true"
$env:FIGURE_AI_PROVIDER="fake"
$env:FIGURE_AI_MODEL="fake-history-model"
$env:FIGURE_EMBEDDING_PROVIDER="fake"
$env:FIGURE_EMBEDDING_MODEL="fake-hash-embedding"
$env:FIGURE_EMBEDDING_DIMENSIONS="8"
$env:FIGURE_EMBEDDING_BATCH_SIZE="16"
.\.venv\Scripts\figure-data.exe suggest-candidate-review --kind relationship --id 960698 --created-by lyl
.\.venv\Scripts\figure-data.exe generate-chain-explanation --from-person-id 38966b03-8aa7-5143-8021-2d266889b6c5 --to-person-id 46cfdf66-08c4-5876-964b-4a95d098afe9 --max-depth 12 --created-by lyl
.\.venv\Scripts\figure-data.exe validate-encounters
.\.venv\Scripts\figure-data.exe validate-graph
```

Expected:

```text
suggest-candidate-review outputs an ai_candidate_suggestion id and ai_run id.
generate-chain-explanation outputs an ai_chain_explanation and chain_hash.
validate-encounters passes after both AI commands.
validate-graph passes after both AI commands.
No candidate, encounter, encounter_evidence or Neo4j write is caused by RAG prompt context.
```

- [ ] **Step 8: Commit Task 6**

Run:

```powershell
git add README.md tests/test_readme_commands.py
git commit -m "docs: 说明 RAG 上下文接入 AI prompt"
```

## Final Review Checklist

- [ ] `retrieval_context` items include document id, source kind, source pk, source ref id, encounter evidence id, score, provider, model and embedding dimensions.
- [ ] Candidate prompt input includes `retrieval_context` and `retrieval_context_status`.
- [ ] Chain prompt input includes `retrieval_context` and `retrieval_context_status`.
- [ ] Candidate service can run when RAG returns zero results.
- [ ] Chain service can run when RAG returns zero results.
- [ ] Candidate `supporting_source_ref_ids` remain limited to direct candidate source refs.
- [ ] Candidate retrieval ids are validated against input retrieval context.
- [ ] Chain retrieval ids are validated against input retrieval context.
- [ ] Chain RAG search is scoped by path source refs rather than free full-index recall.
- [ ] Prompt text says RAG retrieval context is not reviewed evidence.
- [ ] Fake provider returns retrieval trace fields when retrieval context exists.
- [ ] No new table or migration is introduced.
- [ ] No FastAPI generation endpoint is introduced.
- [ ] `/api/v1/chains/shortest` does not call AI or RAG.
- [ ] RAG prompt integration does not update candidates, encounters, encounter_evidence or Neo4j.
- [ ] README documents the boundary.
- [ ] `validate-encounters` and `validate-graph` pass after fake smoke.

## Self-Review Notes

- Spec coverage: this plan covers RAG context injection for candidate suggestions and chain explanations, prompt schema updates, policy guard updates, fake provider behavior, and no-RAG fallback behavior.
- Scope boundary: this plan deliberately excludes no-path exploration, AI evaluation reports, frontend display and real embedding provider SDK.
- Data safety: all generated RAG usage remains in prompt snapshots, AI output snapshots and existing AI artifact flows. Source facts and graph projection remain untouched.
- Implementation order: shared retrieval context first, then candidate flow, then chain flow, then documentation and safety validation.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-14-ai-rag-prompt-integration.md`. Two execution options:

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
