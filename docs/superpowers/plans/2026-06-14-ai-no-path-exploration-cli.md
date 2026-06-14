# AI No-Path Exploration CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为“当前图中没有最短路径”的查询生成可追踪、可审核、不会写入事实源的 AI 探索建议 CLI。

**Architecture:** `figure_data` 继续作为离线数据与审核工具层，CLI 只负责参数解析、依赖组装和格式化输出；核心逻辑放入 `src/figure_data/ai/no_path_*`。服务层复用 `find_chain()` 判定是否真的无路径，再从 PostgreSQL 读取端点、邻接统计、候选关系摘要，并可选调用现有 RAG 检索；AI 输出只落 `ai_runs`，不新建候选、不提升 encounter、不写 Neo4j、不进入 FastAPI/前端主流程。

**Tech Stack:** Python 3.12, Typer, Pydantic v2, SQLAlchemy 2.x, PostgreSQL, Neo4j driver, pgvector/RAG retrieval, pytest, ruff, mypy.

---

## Scope Check

本计划实现阶段 4 收口 spec 的 Plan 2：无路径探索建议 CLI。

本计划实现：

- `no_path_exploration` prompt 定义与 Pydantic 输出 schema。
- `FakeAIProvider` 对 no-path prompt 的 deterministic JSON 输出。
- no-path prompt input builder：
  - 校验 `ChainLookupResult.path is None`。
  - 读取 source/target 人物显示信息。
  - 统计两端 active path encounter 数量。
  - 列出两端附近尚未提升为 path encounter 的候选关系摘要。
  - 可选接入 RAG 检索片段作为上下文。
- no-path policy guard：
  - 禁止把“当前图中无路径”表述为“历史上无关系/未见面/证明不存在路径”。
  - 禁止输出“直接提升/自动写入 encounter/写 Neo4j”的含义。
  - 校验候选、source_ref、retrieval_document、endpoint person id 必须来自输入上下文。
- `figure-data suggest-no-path-exploration` CLI。
- README 和 README 命令测试。

本计划不实现：

- 自动创建 candidate。
- 自动提升 encounter。
- 自动修改 candidates、encounters、encounter_evidence 或 Neo4j。
- 新增 no-path 专用数据库表。
- FastAPI 生成接口或前端展示。
- 真实模型 SDK。
- 批量生成无路径建议。

无路径建议的持久化边界：

- 本阶段只写 `figure_data.ai_runs`。
- `output_snapshot` 中保存结构化 no-path 输出。
- `input_snapshot` 中保存端点、图状态、候选摘要、RAG 片段和模型输入版本。
- 后续若需要产品化列表页，再单独设计 no-path artifact 表；本计划不提前加表。

## Prerequisite Contract

执行前当前分支应具备以下能力：

- `src/figure_data/graph/pathfinding.py` 提供 `find_chain()`，无路径时返回 `ChainLookupResult(path=None)`。
- `src/figure_data/ai/service.py` 提供 `run_ai_prompt()` 和 `record_failed_ai_prompt()`。
- `src/figure_data/ai/retrieval_service.py` 提供 `search_rag_evidence()`。
- `figure-data inspect-ai-run` 能查看 `ai_runs`。
- PostgreSQL 是事实源；Neo4j 只是可重建图投影。

执行前运行：

```powershell
uv run --no-sync python -m pytest tests/ai tests/graph -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync python -m alembic heads
```

预期：

```text
pytest passes.
ruff passes.
mypy passes.
alembic heads shows the current single head.
```

如果本机不用 `uv`，可使用 `.venv` 中的等价命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ai tests/graph -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\python.exe -m alembic heads
```

## File Structure

新增：

```text
src/figure_data/ai/no_path_context.py
src/figure_data/ai/no_path_policy.py
src/figure_data/ai/no_path_service.py
src/figure_data/ai/no_path_formatting.py

tests/ai/test_no_path_prompt_schema.py
tests/ai/test_no_path_context.py
tests/ai/test_no_path_policy.py
tests/ai/test_no_path_service.py
tests/ai/test_no_path_formatting.py
tests/ai/test_no_path_cli.py
```

修改：

```text
src/figure_data/ai/schemas.py
src/figure_data/ai/prompts.py
src/figure_data/ai/provider.py
src/figure_data/cli.py
tests/ai/test_provider.py
tests/test_readme_commands.py
README.md
```

职责边界：

- `no_path_context.py`：构建 prompt input；可以读 PostgreSQL；不调用 AI provider；不写事实表。
- `no_path_policy.py`：校验模型输出的引用范围和禁用含义；不访问数据库。
- `no_path_service.py`：编排 `find_chain()`、context builder、可选 RAG、AI prompt 运行和失败留痕。
- `no_path_formatting.py`：把服务返回结果格式化为 CLI 文本。
- `cli.py`：只做参数解析、session/driver/provider 组装、事务提交/回滚、错误映射。
- `schemas.py`：只定义 AI 结构化输出。
- `prompts.py`：只定义 prompt 文案和版本。
- `provider.py`：只扩展 fake provider 的 no-path deterministic 输出。

## Task 1: No-Path Prompt Schema And Fake Provider

**Files:**

- Modify: `src/figure_data/ai/schemas.py`
- Modify: `src/figure_data/ai/prompts.py`
- Modify: `src/figure_data/ai/provider.py`
- Create: `tests/ai/test_no_path_prompt_schema.py`
- Modify: `tests/ai/test_provider.py`

- [ ] **Step 1: Add failing schema and prompt tests**

Create `tests/ai/test_no_path_prompt_schema.py`:

```python
from pydantic import ValidationError
from pytest import raises

from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.schemas import NoPathExplorationOutput


def test_no_path_exploration_output_schema_accepts_review_targets() -> None:
    output = NoPathExplorationOutput.model_validate(
        {
            "summary": "当前图投影在给定深度内没有连接这两个人物。",
            "likely_reasons": ["两端附近已审核 direct_interaction 边数量较少。"],
            "suggested_review_targets": [
                {
                    "target_type": "candidate",
                    "candidate_kind": "relationship",
                    "candidate_id": 960698,
                    "source_ref_id": 3853784,
                    "retrieval_document_id": None,
                    "person_id": None,
                    "reason": "该候选连接到 source 端点附近，适合人工复核。",
                    "review_question": "原始 source_ref 是否能证明直接互动？",
                }
            ],
            "retrieval_context": [
                {
                    "retrieval_document_id": "00000000-0000-0000-0000-000000000501",
                    "source_kind": "source_ref",
                    "source_ref_id": 3853784,
                    "score": 0.87,
                    "note": "召回片段只作为检索上下文。",
                }
            ],
            "limitations": ["这不是历史上不存在关系的证明。"],
            "display_language": "zh-Hans",
        }
    )

    assert output.suggested_review_targets[0].target_type == "candidate"
    assert output.suggested_review_targets[0].candidate_id == 960698
    assert output.retrieval_context[0].source_ref_id == 3853784


def test_no_path_exploration_output_requires_summary() -> None:
    with raises(ValidationError):
        NoPathExplorationOutput.model_validate(
            {
                "summary": "",
                "likely_reasons": [],
                "suggested_review_targets": [],
                "retrieval_context": [],
                "limitations": [],
                "display_language": "zh-Hans",
            }
        )


def test_no_path_exploration_prompt_is_registered() -> None:
    prompt = get_prompt_definition("no_path_exploration")

    assert prompt.prompt_key == "no_path_exploration"
    assert prompt.purpose == "no_path_exploration"
    assert prompt.output_schema_name == "no_path_exploration_output"
    assert "{no_path_json}" in prompt.user_prompt_template
    assert "不得" in prompt.system_prompt
```

- [ ] **Step 2: Run schema and prompt tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_no_path_prompt_schema.py -q
```

Expected:

```text
ImportError or AttributeError for NoPathExplorationOutput.
unknown prompt: no_path_exploration.
```

- [ ] **Step 3: Add no-path output schemas**

Append these models to `src/figure_data/ai/schemas.py` after `ChainExplanationOutput`:

```python
class NoPathReviewTargetOutput(BaseModel):
    target_type: Literal[
        "candidate",
        "source_ref",
        "retrieval_document",
        "endpoint_neighbor",
    ]
    candidate_kind: Literal["relationship", "kinship"] | None = None
    candidate_id: int | None = Field(default=None, ge=1)
    source_ref_id: int | None = Field(default=None, ge=1)
    retrieval_document_id: str | None = Field(default=None, min_length=1, max_length=80)
    person_id: str | None = Field(default=None, min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=1000)
    review_question: str = Field(min_length=1, max_length=1000)


class NoPathRetrievalContextOutput(BaseModel):
    retrieval_document_id: str = Field(min_length=1, max_length=80)
    source_kind: str = Field(min_length=1, max_length=80)
    source_ref_id: int | None = Field(default=None, ge=1)
    score: float = Field(ge=-1.0, le=1.0)
    note: str = Field(min_length=1, max_length=1000)


class NoPathExplorationOutput(BaseModel):
    summary: str = Field(min_length=1, max_length=3000)
    likely_reasons: list[str] = Field(default_factory=list, max_length=20)
    suggested_review_targets: list[NoPathReviewTargetOutput] = Field(
        default_factory=list,
        max_length=20,
    )
    retrieval_context: list[NoPathRetrievalContextOutput] = Field(
        default_factory=list,
        max_length=20,
    )
    limitations: list[str] = Field(default_factory=list, max_length=20)
    display_language: Literal["zh-Hans", "zh-Hant", "en"] = "zh-Hans"
```

- [ ] **Step 4: Register no-path prompt**

In `src/figure_data/ai/prompts.py`, add this `PromptDefinition` after `CHAIN_EXPLANATION_PROMPT`:

```python
NO_PATH_EXPLORATION_PROMPT = PromptDefinition(
    prompt_key="no_path_exploration",
    prompt_version="2026-06-14.1",
    purpose="no_path_exploration",
    system_prompt=(
        "你是 FigureChain 的无路径探索建议助手。"
        "你只能基于输入 JSON 中的端点人物、当前图查询结果、邻接统计、候选关系摘要和 RAG 召回片段作答。"
        "你必须把结论限定为当前图投影和给定 max_depth 下没有路径。"
        "不得声称历史上两人没有关系、没有见过面或系统证明不存在路径。"
        "不得编造人物关系、见面场景、史料页码或 source_ref。"
        "不得建议直接提升候选为 encounter，不得建议自动写入 Neo4j。"
        "suggested_review_targets 只能列出输入中已有的 candidate、source_ref、retrieval_document 或 endpoint person id。"
        "RAG 召回片段只能称为检索上下文，不能称为已审核证据。"
        "只返回 JSON object。"
    ),
    user_prompt_template=(
        "请为以下无路径查询生成探索建议。"
        "输入 JSON：\n{no_path_json}\n"
        "输出字段必须为 summary, likely_reasons, suggested_review_targets, "
        "retrieval_context, limitations, display_language。"
    ),
    output_schema_name="no_path_exploration_output",
    output_schema_version="1",
)
```

Then add `NO_PATH_EXPLORATION_PROMPT` to `PROMPT_DEFINITIONS`:

```python
PROMPT_DEFINITIONS = (
    AI_FOUNDATION_DIAGNOSTIC_PROMPT,
    CANDIDATE_REVIEW_SUGGESTION_PROMPT,
    CHAIN_EXPLANATION_PROMPT,
    NO_PATH_EXPLORATION_PROMPT,
)
```

- [ ] **Step 5: Add failing fake provider test**

Append to `tests/ai/test_provider.py`:

```python
def test_fake_ai_provider_generates_no_path_exploration_from_prompt_input() -> None:
    provider = FakeAIProvider()
    response = provider.generate(
        AIProviderRequest(
            system_prompt="system",
            user_prompt=(
                "请为以下无路径查询生成探索建议。输入 JSON：\n"
                "{"
                '"candidate_summaries":[{'
                '"candidate_kind":"relationship",'
                '"candidate_id":960698,'
                '"source_ref_id":3853784'
                "}],"
                '"retrieval_context":[{'
                '"document_id":"00000000-0000-0000-0000-000000000501",'
                '"source_kind":"source_ref",'
                '"source_ref_id":3853784,'
                '"score":0.88'
                "}]"
                "}\n"
                "输出字段必须为 summary, likely_reasons, suggested_review_targets, "
                "retrieval_context, limitations, display_language。"
            ),
            model_name="fake-model",
            max_output_tokens=128,
        )
    )

    assert '"suggested_review_targets":' in response.raw_text
    assert '"target_type": "candidate"' in response.raw_text
    assert '"candidate_id": 960698' in response.raw_text
    assert '"retrieval_document_id": "00000000-0000-0000-0000-000000000501"' in response.raw_text
```

- [ ] **Step 6: Run fake provider test and confirm it fails**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_provider.py::test_fake_ai_provider_generates_no_path_exploration_from_prompt_input -q
```

Expected:

```text
AssertionError because FakeAIProvider still returns diagnostic JSON.
```

- [ ] **Step 7: Implement fake provider no-path response**

In `src/figure_data/ai/provider.py`, update `_fake_response_for_request()`:

```python
def _fake_response_for_request(request: AIProviderRequest) -> str:
    if "edge_explanations" in request.user_prompt and "encounters" in request.user_prompt:
        return _fake_chain_explanation_response(request)
    if "suggested_action" in request.user_prompt and "source_refs" in request.user_prompt:
        return _fake_candidate_suggestion_response(request)
    if "likely_reasons" in request.user_prompt and "suggested_review_targets" in request.user_prompt:
        return _fake_no_path_exploration_response(request)
    return '{"message":"ready","echo_id":"diagnostic","warnings":[]}'
```

Add this helper before `_extract_first_json_object()`:

```python
def _fake_no_path_exploration_response(request: AIProviderRequest) -> str:
    payload = _extract_first_json_object(request.user_prompt)
    candidates = payload.get("candidate_summaries", [])
    retrieval_context = payload.get("retrieval_context", [])
    if not isinstance(candidates, list):
        candidates = []
    if not isinstance(retrieval_context, list):
        retrieval_context = []

    suggested_targets: list[dict[str, object]] = []
    first_candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else None
    if first_candidate is not None:
        suggested_targets.append(
            {
                "target_type": "candidate",
                "candidate_kind": first_candidate.get("candidate_kind") or "relationship",
                "candidate_id": first_candidate.get("candidate_id"),
                "source_ref_id": first_candidate.get("source_ref_id"),
                "retrieval_document_id": None,
                "person_id": None,
                "reason": "该候选位于端点附近，适合作为人工复核入口。",
                "review_question": "该候选的原始资料是否能支持直接互动？",
            }
        )

    retrieval_outputs: list[dict[str, object]] = []
    for item in retrieval_context[:3]:
        if not isinstance(item, dict):
            continue
        document_id = item.get("document_id")
        if not isinstance(document_id, str):
            continue
        retrieval_outputs.append(
            {
                "retrieval_document_id": document_id,
                "source_kind": item.get("source_kind") or "unknown",
                "source_ref_id": item.get("source_ref_id"),
                "score": item.get("score") or 0.0,
                "note": "该项是 fake provider 复述的召回上下文。",
            }
        )

    return json.dumps(
        {
            "summary": "当前图投影在给定深度内没有返回连接路径，建议从端点附近候选和召回片段开始复核。",
            "likely_reasons": [
                "端点附近可用于路径搜索的 active direct_interaction 边可能不足。",
                "部分关系仍停留在候选或资料线索阶段，尚未被人工审核为 path encounter。",
            ],
            "suggested_review_targets": suggested_targets,
            "retrieval_context": retrieval_outputs,
            "limitations": [
                "该建议不证明历史上两人没有关系或没有见过面。",
                "AI 输出不能直接创建 encounter，也不能修改 Neo4j。",
            ],
            "display_language": "zh-Hans",
        },
        ensure_ascii=False,
    )
```

- [ ] **Step 8: Run Task 1 tests and commit**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_no_path_prompt_schema.py tests/ai/test_provider.py -q
uv run --no-sync ruff check src/figure_data/ai tests/ai
uv run --no-sync mypy src/figure_data/ai tests/ai
```

Expected:

```text
All selected tests pass.
ruff passes.
mypy passes.
```

Commit:

```powershell
git add src/figure_data/ai/schemas.py src/figure_data/ai/prompts.py src/figure_data/ai/provider.py tests/ai/test_no_path_prompt_schema.py tests/ai/test_provider.py
git commit -m "feat: 添加无路径探索 AI schema"
```

## Task 2: No-Path Context Builder

**Files:**

- Create: `src/figure_data/ai/no_path_context.py`
- Create: `tests/ai/test_no_path_context.py`

- [ ] **Step 1: Add failing context tests**

Create `tests/ai/test_no_path_context.py`:

```python
from uuid import UUID

from pytest import MonkeyPatch, raises

from figure_data.ai.no_path_context import (
    InvalidNoPathContextError,
    NoPathCandidateSummaryInput,
    NoPathEndpointGraphStatsInput,
    NoPathPersonInput,
    NoPathRetrievalContextInput,
    assemble_no_path_prompt_input,
    build_no_path_prompt_input,
    build_no_path_retrieval_query,
    no_path_allowed_candidate_keys,
    no_path_allowed_person_ids,
    no_path_allowed_retrieval_document_ids,
    no_path_allowed_source_ref_ids,
    retrieval_context_from_search_results,
)
from figure_data.ai.retrieval_repository import RetrievalSearchResult
from figure_data.graph.types import ChainLookupResult, ChainPath

SOURCE_PERSON_ID = "38966b03-8aa7-5143-8021-2d266889b6c5"
TARGET_PERSON_ID = "46cfdf66-08c4-5876-964b-4a95d098afe9"


def no_path_result() -> ChainLookupResult:
    return ChainLookupResult(
        source_person_id=SOURCE_PERSON_ID,
        target_person_id=TARGET_PERSON_ID,
        max_depth=12,
        path=None,
    )


def person(person_id: str, name: str) -> NoPathPersonInput:
    return NoPathPersonInput(
        person_id=person_id,
        display_name=name,
        birth_year=1010,
        death_year=1080,
        cbdb_external_id="123",
    )


def test_assemble_no_path_prompt_input_requires_no_path() -> None:
    result = ChainLookupResult(
        source_person_id=SOURCE_PERSON_ID,
        target_person_id=TARGET_PERSON_ID,
        max_depth=12,
        path=ChainPath(people=(), edges=()),
    )

    with raises(InvalidNoPathContextError, match="requires a no-path result"):
        assemble_no_path_prompt_input(
            result=result,
            people={
                SOURCE_PERSON_ID: person(SOURCE_PERSON_ID, "许几"),
                TARGET_PERSON_ID: person(TARGET_PERSON_ID, "韩琦"),
            },
            endpoint_stats={
                SOURCE_PERSON_ID: NoPathEndpointGraphStatsInput(
                    person_id=SOURCE_PERSON_ID,
                    active_path_encounter_count=1,
                ),
                TARGET_PERSON_ID: NoPathEndpointGraphStatsInput(
                    person_id=TARGET_PERSON_ID,
                    active_path_encounter_count=2,
                ),
            },
            candidate_summaries=[],
            retrieval_context=[],
            language="zh-Hans",
        )


def test_assemble_no_path_prompt_input_preserves_traceable_context() -> None:
    candidate = NoPathCandidateSummaryInput(
        candidate_kind="relationship",
        candidate_id=960698,
        person_a_id=SOURCE_PERSON_ID,
        person_b_id="00000000-0000-0000-0000-000000000999",
        person_a_name="许几",
        person_b_name="某人",
        candidate_strength="high",
        candidate_basis="direct_interaction_likely",
        relation_label="曾谒见",
        source_work_id=111,
        source_ref_id=3853784,
        pages="卷一",
        review_status="unreviewed",
    )
    retrieval = NoPathRetrievalContextInput(
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
        snippet="许几 谒见 韩琦",
    )

    prompt_input = assemble_no_path_prompt_input(
        result=no_path_result(),
        people={
            SOURCE_PERSON_ID: person(SOURCE_PERSON_ID, "许几"),
            TARGET_PERSON_ID: person(TARGET_PERSON_ID, "韩琦"),
        },
        endpoint_stats={
            SOURCE_PERSON_ID: NoPathEndpointGraphStatsInput(
                person_id=SOURCE_PERSON_ID,
                active_path_encounter_count=1,
            ),
            TARGET_PERSON_ID: NoPathEndpointGraphStatsInput(
                person_id=TARGET_PERSON_ID,
                active_path_encounter_count=2,
            ),
        },
        candidate_summaries=[candidate],
        retrieval_context=[retrieval],
        language="zh-Hans",
    )

    assert prompt_input.path_status == "no_path"
    assert prompt_input.source_person.display_name == "许几"
    assert prompt_input.target_person.display_name == "韩琦"
    assert prompt_input.candidate_summaries == [candidate]
    assert prompt_input.retrieval_context == [retrieval]
    assert no_path_allowed_candidate_keys(prompt_input) == {("relationship", 960698)}
    assert no_path_allowed_source_ref_ids(prompt_input) == {3853784}
    assert no_path_allowed_retrieval_document_ids(prompt_input) == {
        "00000000-0000-0000-0000-000000000501"
    }
    assert no_path_allowed_person_ids(prompt_input) == {SOURCE_PERSON_ID, TARGET_PERSON_ID}


def test_retrieval_context_from_search_results_normalizes_snippet() -> None:
    result = RetrievalSearchResult(
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
        content_text="许几\n\t谒见 韩琦",
        text_hash="abc",
        score=0.88,
    )

    items = retrieval_context_from_search_results([result], snippet_chars=20)

    assert items[0].document_id == "00000000-0000-0000-0000-000000000501"
    assert items[0].snippet == "许几 谒见 韩琦"


def test_build_no_path_retrieval_query_uses_endpoint_and_candidate_names() -> None:
    prompt_input = assemble_no_path_prompt_input(
        result=no_path_result(),
        people={
            SOURCE_PERSON_ID: person(SOURCE_PERSON_ID, "许几"),
            TARGET_PERSON_ID: person(TARGET_PERSON_ID, "韩琦"),
        },
        endpoint_stats={
            SOURCE_PERSON_ID: NoPathEndpointGraphStatsInput(
                person_id=SOURCE_PERSON_ID,
                active_path_encounter_count=1,
            ),
            TARGET_PERSON_ID: NoPathEndpointGraphStatsInput(
                person_id=TARGET_PERSON_ID,
                active_path_encounter_count=2,
            ),
        },
        candidate_summaries=[
            NoPathCandidateSummaryInput(
                candidate_kind="relationship",
                candidate_id=960698,
                person_a_id=SOURCE_PERSON_ID,
                person_b_id="00000000-0000-0000-0000-000000000999",
                person_a_name="许几",
                person_b_name="某人",
                candidate_strength="high",
                candidate_basis="direct_interaction_likely",
                relation_label="曾谒见",
                source_work_id=111,
                source_ref_id=3853784,
                pages="卷一",
                review_status="unreviewed",
            )
        ],
        retrieval_context=[],
        language="zh-Hans",
    )

    assert build_no_path_retrieval_query(prompt_input) == "许几 韩琦 许几 某人 曾谒见"


def test_build_no_path_prompt_input_uses_repository_helpers(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "figure_data.ai.no_path_context._load_people_by_ids",
        lambda session, person_ids: {
            SOURCE_PERSON_ID: person(SOURCE_PERSON_ID, "许几"),
            TARGET_PERSON_ID: person(TARGET_PERSON_ID, "韩琦"),
        },
    )
    monkeypatch.setattr(
        "figure_data.ai.no_path_context._count_active_path_encounters",
        lambda session, person_id: 3,
    )
    monkeypatch.setattr(
        "figure_data.ai.no_path_context._list_endpoint_candidate_summaries",
        lambda session, person_ids, limit: [],
    )

    prompt_input = build_no_path_prompt_input(
        session=object(),
        result=no_path_result(),
        retrieval_context=[],
        candidate_limit=5,
        language="zh-Hans",
    )

    assert prompt_input.source_stats.active_path_encounter_count == 3
    assert prompt_input.target_stats.active_path_encounter_count == 3
```

- [ ] **Step 2: Run context tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_no_path_context.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.ai.no_path_context'
```

- [ ] **Step 3: Implement no-path context models and assembly helpers**

Create `src/figure_data/ai/no_path_context.py` with these imports and models:

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.ai.retrieval_repository import RetrievalSearchResult
from figure_data.graph.types import ChainLookupResult


class InvalidNoPathContextError(ValueError):
    """Raised when a no-path exploration request is not based on a no-path result."""


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
```

Add these pure helpers:

```python
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
        raise InvalidNoPathContextError(f"missing no-path endpoint context: {exc}") from exc
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
    terms = [
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
        item.source_ref_id for item in prompt_input.retrieval_context if item.source_ref_id is not None
    }
    return candidate_refs | retrieval_refs


def no_path_allowed_retrieval_document_ids(prompt_input: NoPathPromptInput) -> set[str]:
    return {item.document_id for item in prompt_input.retrieval_context}


def no_path_allowed_person_ids(prompt_input: NoPathPromptInput) -> set[str]:
    return {prompt_input.source_person_id, prompt_input.target_person_id}


def _normalize_snippet(value: str, *, snippet_chars: int) -> str:
    normalized = " ".join(value.split())
    return normalized[:snippet_chars]
```

- [ ] **Step 4: Implement PostgreSQL-backed context builder**

Append to `src/figure_data/ai/no_path_context.py`:

```python
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
            active_path_encounter_count=_count_active_path_encounters(session, person_id),
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
    rows = (
        session.execute(  # type: ignore[attr-defined]
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
        str(row["person_id"]): _person_from_row(cast(Mapping[str, Any], row)) for row in rows
    }
    missing = [person_id for person_id in person_ids if person_id not in people]
    if missing:
        raise InvalidNoPathContextError("missing endpoint person in PostgreSQL: " + ",".join(missing))
    return people


def _count_active_path_encounters(session: Session | object, person_id: str) -> int:
    value = session.execute(  # type: ignore[attr-defined]
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
```

Append candidate listing query:

```python
def _list_endpoint_candidate_summaries(
    session: Session | object,
    *,
    person_ids: list[str],
    limit: int,
) -> list[NoPathCandidateSummaryInput]:
    rows = (
        session.execute(  # type: ignore[attr-defined]
            text(
                """
                select *
                from (
                  select
                    'relationship' as candidate_kind,
                    rc.id as candidate_id,
                    rc.person_a_id::text as person_a_id,
                    rc.person_b_id::text as person_b_id,
                    coalesce(pa.primary_name_zh_hant, pa.primary_name_zh_hans, pa.primary_name_romanized) as person_a_name,
                    coalesce(pb.primary_name_zh_hant, pb.primary_name_zh_hans, pb.primary_name_romanized) as person_b_name,
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
                    coalesce(pa.primary_name_zh_hant, pa.primary_name_zh_hans, pa.primary_name_romanized) as person_a_name,
                    coalesce(pb.primary_name_zh_hant, pb.primary_name_zh_hans, pb.primary_name_romanized) as person_b_name,
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


def _optional_int(value: object) -> int | None:
    return None if value is None else int(cast(Any, value))


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
```

- [ ] **Step 5: Run Task 2 tests and commit**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_no_path_context.py -q
uv run --no-sync ruff check src/figure_data/ai/no_path_context.py tests/ai/test_no_path_context.py
uv run --no-sync mypy src/figure_data/ai/no_path_context.py tests/ai/test_no_path_context.py
```

Expected:

```text
All selected tests pass.
ruff passes.
mypy passes.
```

Commit:

```powershell
git add src/figure_data/ai/no_path_context.py tests/ai/test_no_path_context.py
git commit -m "feat: 构建无路径探索上下文"
```

## Task 3: No-Path Output Policy Guard

**Files:**

- Create: `src/figure_data/ai/no_path_policy.py`
- Create: `tests/ai/test_no_path_policy.py`

- [ ] **Step 1: Add failing policy tests**

Create `tests/ai/test_no_path_policy.py`:

```python
from pytest import raises

from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.no_path_policy import validate_no_path_exploration_policy
from figure_data.ai.schemas import NoPathExplorationOutput


def output(**overrides: object) -> NoPathExplorationOutput:
    payload: dict[str, object] = {
        "summary": "当前图投影在给定深度内没有返回连接路径。",
        "likely_reasons": ["端点附近可用 path encounter 边较少。"],
        "suggested_review_targets": [
            {
                "target_type": "candidate",
                "candidate_kind": "relationship",
                "candidate_id": 960698,
                "source_ref_id": 3853784,
                "retrieval_document_id": None,
                "person_id": None,
                "reason": "该候选位于端点附近。",
                "review_question": "原始资料是否能支持直接互动？",
            }
        ],
        "retrieval_context": [
            {
                "retrieval_document_id": "00000000-0000-0000-0000-000000000501",
                "source_kind": "source_ref",
                "source_ref_id": 3853784,
                "score": 0.88,
                "note": "该项是召回上下文。",
            }
        ],
        "limitations": ["这不是历史上不存在关系的证明。"],
        "display_language": "zh-Hans",
    }
    payload.update(overrides)
    return NoPathExplorationOutput.model_validate(payload)


def test_no_path_policy_accepts_known_references() -> None:
    validate_no_path_exploration_policy(
        output(),
        allowed_candidate_keys={("relationship", 960698)},
        allowed_source_ref_ids={3853784},
        allowed_retrieval_document_ids={"00000000-0000-0000-0000-000000000501"},
        allowed_person_ids={
            "38966b03-8aa7-5143-8021-2d266889b6c5",
            "46cfdf66-08c4-5876-964b-4a95d098afe9",
        },
    )


def test_no_path_policy_rejects_unknown_candidate() -> None:
    with raises(AIOutputPolicyViolation, match="unknown candidate"):
        validate_no_path_exploration_policy(
            output(),
            allowed_candidate_keys={("relationship", 1)},
            allowed_source_ref_ids={3853784},
            allowed_retrieval_document_ids={"00000000-0000-0000-0000-000000000501"},
            allowed_person_ids=set(),
        )


def test_no_path_policy_rejects_unknown_retrieval_document() -> None:
    with raises(AIOutputPolicyViolation, match="unknown retrieval_document_id"):
        validate_no_path_exploration_policy(
            output(),
            allowed_candidate_keys={("relationship", 960698)},
            allowed_source_ref_ids={3853784},
            allowed_retrieval_document_ids={"00000000-0000-0000-0000-000000000999"},
            allowed_person_ids=set(),
        )


def test_no_path_policy_rejects_forbidden_claims() -> None:
    with raises(AIOutputPolicyViolation, match="forbidden no-path claim"):
        validate_no_path_exploration_policy(
            output(summary="系统证明不存在路径。"),
            allowed_candidate_keys={("relationship", 960698)},
            allowed_source_ref_ids={3853784},
            allowed_retrieval_document_ids={"00000000-0000-0000-0000-000000000501"},
            allowed_person_ids=set(),
        )


def test_no_path_policy_rejects_direct_promotion_wording() -> None:
    bad_output = output(
        suggested_review_targets=[
            {
                "target_type": "candidate",
                "candidate_kind": "relationship",
                "candidate_id": 960698,
                "source_ref_id": 3853784,
                "retrieval_document_id": None,
                "person_id": None,
                "reason": "可以直接提升为 encounter。",
                "review_question": "是否写入 Neo4j？",
            }
        ]
    )

    with raises(AIOutputPolicyViolation, match="forbidden no-path claim"):
        validate_no_path_exploration_policy(
            bad_output,
            allowed_candidate_keys={("relationship", 960698)},
            allowed_source_ref_ids={3853784},
            allowed_retrieval_document_ids={"00000000-0000-0000-0000-000000000501"},
            allowed_person_ids=set(),
        )
```

- [ ] **Step 2: Run policy tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_no_path_policy.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.ai.no_path_policy'
```

- [ ] **Step 3: Implement policy guard**

Create `src/figure_data/ai/no_path_policy.py`:

```python
from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.schemas import NoPathExplorationOutput


FORBIDDEN_PHRASES = (
    "两人没有关系",
    "二人没有关系",
    "历史上没有关系",
    "两人没有见过面",
    "二人没有见过面",
    "历史上没有见过面",
    "从未见过面",
    "系统证明不存在路径",
    "证明不存在路径",
    "可以证明不存在",
    "直接提升",
    "自动提升",
    "直接创建 encounter",
    "自动创建 encounter",
    "写入 Neo4j",
)


def validate_no_path_exploration_policy(
    output: NoPathExplorationOutput,
    *,
    allowed_candidate_keys: set[tuple[str, int]],
    allowed_source_ref_ids: set[int],
    allowed_retrieval_document_ids: set[str],
    allowed_person_ids: set[str],
) -> None:
    _reject_forbidden_claims(output)
    for target in output.suggested_review_targets:
        if target.target_type == "candidate":
            if target.candidate_kind is None or target.candidate_id is None:
                raise AIOutputPolicyViolation("candidate target requires candidate_kind and candidate_id")
            key = (target.candidate_kind, target.candidate_id)
            if key not in allowed_candidate_keys:
                raise AIOutputPolicyViolation(
                    f"unknown candidate in AI output: {target.candidate_kind}:{target.candidate_id}"
                )
        if target.source_ref_id is not None and target.source_ref_id not in allowed_source_ref_ids:
            raise AIOutputPolicyViolation(f"unknown source_ref_id in AI output: {target.source_ref_id}")
        if (
            target.retrieval_document_id is not None
            and target.retrieval_document_id not in allowed_retrieval_document_ids
        ):
            raise AIOutputPolicyViolation(
                f"unknown retrieval_document_id in AI output: {target.retrieval_document_id}"
            )
        if target.person_id is not None and target.person_id not in allowed_person_ids:
            raise AIOutputPolicyViolation(f"unknown person_id in AI output: {target.person_id}")

    for item in output.retrieval_context:
        if item.retrieval_document_id not in allowed_retrieval_document_ids:
            raise AIOutputPolicyViolation(
                f"unknown retrieval_document_id in AI output: {item.retrieval_document_id}"
            )
        if item.source_ref_id is not None and item.source_ref_id not in allowed_source_ref_ids:
            raise AIOutputPolicyViolation(f"unknown source_ref_id in AI output: {item.source_ref_id}")


def _reject_forbidden_claims(output: NoPathExplorationOutput) -> None:
    texts: list[str] = [output.summary]
    texts.extend(output.likely_reasons)
    texts.extend(output.limitations)
    for target in output.suggested_review_targets:
        texts.extend([target.reason, target.review_question])
    for item in output.retrieval_context:
        texts.append(item.note)

    joined = "\n".join(texts)
    for phrase in FORBIDDEN_PHRASES:
        if phrase in joined:
            raise AIOutputPolicyViolation(f"forbidden no-path claim: {phrase}")
```

- [ ] **Step 4: Run Task 3 tests and commit**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_no_path_policy.py -q
uv run --no-sync ruff check src/figure_data/ai/no_path_policy.py tests/ai/test_no_path_policy.py
uv run --no-sync mypy src/figure_data/ai/no_path_policy.py tests/ai/test_no_path_policy.py
```

Expected:

```text
All selected tests pass.
ruff passes.
mypy passes.
```

Commit:

```powershell
git add src/figure_data/ai/no_path_policy.py tests/ai/test_no_path_policy.py
git commit -m "feat: 添加无路径探索输出边界校验"
```

## Task 4: No-Path Service And AI Run Orchestration

**Files:**

- Create: `src/figure_data/ai/no_path_service.py`
- Create: `tests/ai/test_no_path_service.py`

- [ ] **Step 1: Add failing service tests**

Create `tests/ai/test_no_path_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.ai.no_path_context import (
    InvalidNoPathContextError,
    NoPathEndpointGraphStatsInput,
    NoPathPersonInput,
    assemble_no_path_prompt_input,
)
from figure_data.ai.no_path_service import (
    NoPathExplorationResult,
    generate_no_path_exploration_for_result,
)
from figure_data.ai.schemas import NoPathExplorationOutput
from figure_data.ai.service import AIRunResult
from figure_data.ai.types import AIProviderRequest, AIProviderResponse
from figure_data.graph.types import ChainLookupResult, ChainPath

SOURCE_PERSON_ID = "38966b03-8aa7-5143-8021-2d266889b6c5"
TARGET_PERSON_ID = "46cfdf66-08c4-5876-964b-4a95d098afe9"


class FakeProvider:
    provider_name = "fake"

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        return AIProviderResponse(raw_text="{}", provider=self.provider_name, model_name=request.model_name)


@dataclass
class FakeRunRepository:
    prompt_version_id: UUID = UUID("00000000-0000-0000-0000-000000000302")
    run_id: UUID = UUID("00000000-0000-0000-0000-000000000301")
    failed: list[dict[str, object]] = field(default_factory=list)

    def ensure_prompt_version(self, session: object, prompt: object) -> UUID:
        return self.prompt_version_id

    def create_run(self, session: object, run: object) -> UUID:
        return self.run_id

    def mark_succeeded(self, session: object, *, run_id: UUID, output_snapshot: dict[str, Any], raw_output: str) -> None:
        return None

    def mark_failed(self, session: object, *, run_id: UUID, error_code: str, error_message: str, raw_output: str | None) -> None:
        self.failed.append(
            {
                "run_id": run_id,
                "error_code": error_code,
                "error_message": error_message,
                "raw_output": raw_output,
            }
        )


class CapturingPromptRunner:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def __call__(self, **kwargs: object) -> AIRunResult[NoPathExplorationOutput]:
        self.kwargs = kwargs
        output = NoPathExplorationOutput.model_validate(
            {
                "summary": "当前图投影在给定深度内没有返回连接路径。",
                "likely_reasons": ["端点附近可用边较少。"],
                "suggested_review_targets": [],
                "retrieval_context": [],
                "limitations": ["这不是历史上不存在关系的证明。"],
                "display_language": "zh-Hans",
            }
        )
        return AIRunResult(
            run_id=UUID("00000000-0000-0000-0000-000000000301"),
            output=output,
        )


def settings() -> Any:
    return SimpleNamespace(ai_model="fake-history-model", ai_max_output_tokens=1200)


def no_path_result(*, path: ChainPath | None = None) -> ChainLookupResult:
    return ChainLookupResult(
        source_person_id=SOURCE_PERSON_ID,
        target_person_id=TARGET_PERSON_ID,
        max_depth=12,
        path=path,
    )


def context_builder(**kwargs: object) -> object:
    result = kwargs["result"]
    assert isinstance(result, ChainLookupResult)
    return assemble_no_path_prompt_input(
        result=result,
        people={
            SOURCE_PERSON_ID: NoPathPersonInput(
                person_id=SOURCE_PERSON_ID,
                display_name="许几",
                birth_year=1010,
                death_year=1080,
                cbdb_external_id="123",
            ),
            TARGET_PERSON_ID: NoPathPersonInput(
                person_id=TARGET_PERSON_ID,
                display_name="韩琦",
                birth_year=1008,
                death_year=1075,
                cbdb_external_id="456",
            ),
        },
        endpoint_stats={
            SOURCE_PERSON_ID: NoPathEndpointGraphStatsInput(
                person_id=SOURCE_PERSON_ID,
                active_path_encounter_count=1,
            ),
            TARGET_PERSON_ID: NoPathEndpointGraphStatsInput(
                person_id=TARGET_PERSON_ID,
                active_path_encounter_count=2,
            ),
        },
        candidate_summaries=[],
        retrieval_context=[],
        language="zh-Hans",
    )


def test_generate_no_path_exploration_for_result_calls_prompt_runner() -> None:
    runner = CapturingPromptRunner()

    result = generate_no_path_exploration_for_result(
        session=object(),
        result=no_path_result(),
        settings=settings(),
        provider=FakeProvider(),
        created_by="tester",
        language="zh-Hans",
        candidate_limit=5,
        rag_limit=0,
        context_builder=context_builder,
        run_prompt=runner,
    )

    assert isinstance(result, NoPathExplorationResult)
    assert result.ai_run_id == UUID("00000000-0000-0000-0000-000000000301")
    assert runner.kwargs["output_schema"] is NoPathExplorationOutput
    assert "no_path_json" in runner.kwargs["input_variables"]
    assert callable(runner.kwargs["output_guard"])


def test_generate_no_path_exploration_records_path_found_as_failed_run() -> None:
    run_repository = FakeRunRepository()

    with raises(InvalidNoPathContextError):
        generate_no_path_exploration_for_result(
            session=object(),
            result=no_path_result(path=ChainPath(people=(), edges=())),
            settings=settings(),
            provider=FakeProvider(),
            created_by="tester",
            language="zh-Hans",
            candidate_limit=5,
            rag_limit=0,
            run_repository=run_repository,
            context_builder=context_builder,
            run_prompt=CapturingPromptRunner(),
        )

    assert run_repository.failed[0]["error_code"] == "input_invalid"
```

- [ ] **Step 2: Run service tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_no_path_service.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.ai.no_path_service'
```

- [ ] **Step 3: Implement no-path service**

Create `src/figure_data/ai/no_path_service.py`:

```python
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.ai.embedding_provider import EmbeddingProviderConfigurationError
from figure_data.ai.no_path_context import (
    InvalidNoPathContextError,
    NoPathPromptInput,
    NoPathRetrievalContextInput,
    build_no_path_prompt_input,
    build_no_path_retrieval_query,
    no_path_allowed_candidate_keys,
    no_path_allowed_person_ids,
    no_path_allowed_retrieval_document_ids,
    no_path_allowed_source_ref_ids,
    retrieval_context_from_search_results,
)
from figure_data.ai.no_path_policy import validate_no_path_exploration_policy
from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.provider import AIProvider, create_ai_provider
from figure_data.ai.repository import AIRunRepository
from figure_data.ai.retrieval_service import SearchRagEvidenceOptions, search_rag_evidence
from figure_data.ai.schemas import NoPathExplorationOutput
from figure_data.ai.service import AIRunResult, record_failed_ai_prompt, run_ai_prompt
from figure_data.config import Settings
from figure_data.db.enums import AIErrorCode
from figure_data.graph.pathfinding import ChainEndpointInput, find_chain
from figure_data.graph.types import ChainLookupResult


class ContextBuilder(Protocol):
    def __call__(
        self,
        *,
        session: Session | object,
        result: ChainLookupResult,
        retrieval_context: list[NoPathRetrievalContextInput],
        candidate_limit: int,
        language: str,
    ) -> NoPathPromptInput:
        """Build no-path prompt input."""


@dataclass(frozen=True)
class NoPathExplorationResult:
    ai_run_id: UUID
    output: NoPathExplorationOutput
```

Append orchestration functions:

```python
def generate_no_path_exploration(
    *,
    session: Session,
    neo4j_session: object,
    settings: Settings,
    source: ChainEndpointInput,
    target: ChainEndpointInput,
    max_depth: int,
    created_by: str,
    language: str = "zh-Hans",
    candidate_limit: int = 10,
    rag_limit: int = 5,
    provider: AIProvider | None = None,
    run_repository: AIRunRepository | None = None,
) -> NoPathExplorationResult:
    result = find_chain(session, neo4j_session, source, target, max_depth)
    return generate_no_path_exploration_for_result(
        session=session,
        result=result,
        settings=settings,
        provider=provider,
        created_by=created_by,
        language=language,
        candidate_limit=candidate_limit,
        rag_limit=rag_limit,
        run_repository=run_repository,
    )


def generate_no_path_exploration_for_result(
    *,
    session: Session | object,
    result: ChainLookupResult,
    settings: Settings,
    provider: AIProvider | None,
    created_by: str,
    language: str = "zh-Hans",
    candidate_limit: int = 10,
    rag_limit: int = 5,
    run_repository: AIRunRepository | None = None,
    context_builder: ContextBuilder = build_no_path_prompt_input,
    run_prompt: Callable[..., AIRunResult[NoPathExplorationOutput]] = run_ai_prompt,
) -> NoPathExplorationResult:
    prompt = get_prompt_definition("no_path_exploration")
    model_name = _require_ai_model(settings)
    resolved_provider = provider or create_ai_provider(settings)
    input_seed = _input_seed(result=result, language=language, candidate_limit=candidate_limit, rag_limit=rag_limit)

    try:
        prompt_input = context_builder(
            session=session,
            result=result,
            retrieval_context=[],
            candidate_limit=candidate_limit,
            language=language,
        )
        prompt_input = _with_optional_retrieval_context(
            session=session,
            settings=settings,
            prompt_input=prompt_input,
            result=result,
            language=language,
            candidate_limit=candidate_limit,
            rag_limit=rag_limit,
            context_builder=context_builder,
        )
    except InvalidNoPathContextError as exc:
        record_failed_ai_prompt(
            session=session,
            prompt=prompt,
            provider_name=getattr(resolved_provider, "provider_name", "unknown"),
            model_name=model_name,
            input_snapshot=input_seed,
            created_by=created_by,
            error_code=AIErrorCode.INPUT_INVALID.value,
            error_message=str(exc),
            repository=run_repository,
        )
        raise

    prompt_snapshot = prompt_input.model_dump(mode="json")
    no_path_json = json.dumps(prompt_snapshot, ensure_ascii=False, sort_keys=True)
    run_result = run_prompt(
        session=session,
        prompt=prompt,
        provider=resolved_provider,
        output_schema=NoPathExplorationOutput,
        input_variables={"no_path_json": no_path_json},
        input_snapshot=prompt_snapshot,
        model_name=model_name,
        max_output_tokens=settings.ai_max_output_tokens,
        created_by=created_by,
        repository=run_repository,
        output_guard=lambda output: validate_no_path_exploration_policy(
            output,
            allowed_candidate_keys=no_path_allowed_candidate_keys(prompt_input),
            allowed_source_ref_ids=no_path_allowed_source_ref_ids(prompt_input),
            allowed_retrieval_document_ids=no_path_allowed_retrieval_document_ids(prompt_input),
            allowed_person_ids=no_path_allowed_person_ids(prompt_input),
        ),
    )
    return NoPathExplorationResult(
        ai_run_id=run_result.run_id,
        output=run_result.output,
    )
```

Append RAG helper and model check:

```python
def _with_optional_retrieval_context(
    *,
    session: Session | object,
    settings: Settings,
    prompt_input: NoPathPromptInput,
    result: ChainLookupResult,
    language: str,
    candidate_limit: int,
    rag_limit: int,
    context_builder: ContextBuilder,
) -> NoPathPromptInput:
    if rag_limit <= 0:
        return prompt_input
    query = build_no_path_retrieval_query(prompt_input)
    if not query:
        return prompt_input
    try:
        retrieval_result = search_rag_evidence(
            session=session,
            settings=settings,
            options=SearchRagEvidenceOptions(query=query, source_ref_id=None, limit=rag_limit),
        )
    except (EmbeddingProviderConfigurationError, ValueError):
        return prompt_input
    retrieval_context = retrieval_context_from_search_results(retrieval_result.results)
    return context_builder(
        session=session,
        result=result,
        retrieval_context=retrieval_context,
        candidate_limit=candidate_limit,
        language=language,
    )


def _input_seed(
    *,
    result: ChainLookupResult,
    language: str,
    candidate_limit: int,
    rag_limit: int,
) -> dict[str, object]:
    return {
        "source_person_id": result.source_person_id,
        "target_person_id": result.target_person_id,
        "max_depth": result.max_depth,
        "path_status": "found" if result.path is not None else "no_path",
        "language": language,
        "candidate_limit": candidate_limit,
        "rag_limit": rag_limit,
    }


def _require_ai_model(settings: Settings) -> str:
    if settings.ai_model is None:
        raise ValueError("FIGURE_AI_MODEL is required for no-path exploration")
    return settings.ai_model
```

- [ ] **Step 4: Run Task 4 tests and commit**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_no_path_service.py -q
uv run --no-sync ruff check src/figure_data/ai/no_path_service.py tests/ai/test_no_path_service.py
uv run --no-sync mypy src/figure_data/ai/no_path_service.py tests/ai/test_no_path_service.py
```

Expected:

```text
All selected tests pass.
ruff passes.
mypy passes.
```

Commit:

```powershell
git add src/figure_data/ai/no_path_service.py tests/ai/test_no_path_service.py
git commit -m "feat: 添加无路径探索 AI 服务"
```

## Task 5: No-Path CLI And Formatting

**Files:**

- Create: `src/figure_data/ai/no_path_formatting.py`
- Modify: `src/figure_data/cli.py`
- Create: `tests/ai/test_no_path_formatting.py`
- Create: `tests/ai/test_no_path_cli.py`

- [ ] **Step 1: Add failing formatting tests**

Create `tests/ai/test_no_path_formatting.py`:

```python
from uuid import UUID

from figure_data.ai.no_path_formatting import format_no_path_exploration_result
from figure_data.ai.no_path_service import NoPathExplorationResult
from figure_data.ai.schemas import NoPathExplorationOutput


def test_format_no_path_exploration_result_outputs_summary_targets_and_limitations() -> None:
    result = NoPathExplorationResult(
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        output=NoPathExplorationOutput.model_validate(
            {
                "summary": "当前图投影在给定深度内没有返回连接路径。",
                "likely_reasons": ["端点附近可用边较少。"],
                "suggested_review_targets": [
                    {
                        "target_type": "candidate",
                        "candidate_kind": "relationship",
                        "candidate_id": 960698,
                        "source_ref_id": 3853784,
                        "retrieval_document_id": None,
                        "person_id": None,
                        "reason": "该候选位于端点附近。",
                        "review_question": "原始资料是否能支持直接互动？",
                    }
                ],
                "retrieval_context": [
                    {
                        "retrieval_document_id": "00000000-0000-0000-0000-000000000501",
                        "source_kind": "source_ref",
                        "source_ref_id": 3853784,
                        "score": 0.88,
                        "note": "该项是召回上下文。",
                    }
                ],
                "limitations": ["这不是历史上不存在关系的证明。"],
                "display_language": "zh-Hans",
            }
        ),
    )

    lines = format_no_path_exploration_result(result)

    assert lines[0] == "ai_run_id\t00000000-0000-0000-0000-000000000301"
    assert "summary\t当前图投影在给定深度内没有返回连接路径。" in lines
    assert "reason\t0\t端点附近可用边较少。" in lines
    assert any(line.startswith("target\t0\tcandidate\trelationship\t960698") for line in lines)
    assert any(line.startswith("retrieval\t0\t00000000-0000-0000-0000-000000000501") for line in lines)
```

- [ ] **Step 2: Add failing CLI tests**

Create `tests/ai/test_no_path_cli.py`:

```python
from types import TracebackType
from uuid import UUID

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.ai.no_path_service import NoPathExplorationResult
from figure_data.ai.schemas import NoPathExplorationOutput
from figure_data.cli import app

runner = CliRunner()


class DummyDriver:
    def close(self) -> None:
        return None


class DummySession:
    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None

    def __enter__(self) -> object:
        return object()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


def patch_dependencies(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: lambda: DummySession())
    monkeypatch.setattr("figure_data.cli.create_neo4j_driver", lambda settings: DummyDriver())
    monkeypatch.setattr(
        "figure_data.cli.get_neo4j_config",
        lambda settings: type("C", (), {"database": "neo4j"})(),
    )
    monkeypatch.setattr("figure_data.cli.graph_session", lambda driver, database: DummySession())


def test_suggest_no_path_exploration_help_exits_zero() -> None:
    result = runner.invoke(app, ["suggest-no-path-exploration", "--help"])

    assert result.exit_code == 0
    assert "suggest-no-path-exploration" in result.output


def test_suggest_no_path_exploration_outputs_result(monkeypatch: MonkeyPatch) -> None:
    patch_dependencies(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.generate_no_path_exploration",
        lambda **kwargs: NoPathExplorationResult(
            ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
            output=NoPathExplorationOutput.model_validate(
                {
                    "summary": "当前图投影在给定深度内没有返回连接路径。",
                    "likely_reasons": [],
                    "suggested_review_targets": [],
                    "retrieval_context": [],
                    "limitations": ["这不是历史上不存在关系的证明。"],
                    "display_language": "zh-Hans",
                }
            ),
        ),
    )

    result = runner.invoke(
        app,
        [
            "suggest-no-path-exploration",
            "--from-person-id",
            "38966b03-8aa7-5143-8021-2d266889b6c5",
            "--to-person-id",
            "46cfdf66-08c4-5876-964b-4a95d098afe9",
            "--created-by",
            "tester",
            "--rag-limit",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert "ai_run_id\t00000000-0000-0000-0000-000000000301" in result.output
    assert "summary\t当前图投影在给定深度内没有返回连接路径。" in result.output
```

- [ ] **Step 3: Run formatting and CLI tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_no_path_formatting.py tests/ai/test_no_path_cli.py -q
```

Expected:

```text
ModuleNotFoundError for no_path_formatting or Typer help missing command.
```

- [ ] **Step 4: Implement formatting**

Create `src/figure_data/ai/no_path_formatting.py`:

```python
from figure_data.ai.no_path_service import NoPathExplorationResult


def format_no_path_exploration_result(result: NoPathExplorationResult) -> list[str]:
    output = result.output
    lines = [
        f"ai_run_id\t{result.ai_run_id}",
        f"summary\t{_clean(output.summary)}",
    ]
    for index, reason in enumerate(output.likely_reasons):
        lines.append(f"reason\t{index}\t{_clean(reason)}")
    for index, target in enumerate(output.suggested_review_targets):
        lines.append(
            "\t".join(
                [
                    "target",
                    str(index),
                    target.target_type,
                    target.candidate_kind or "",
                    "" if target.candidate_id is None else str(target.candidate_id),
                    "" if target.source_ref_id is None else str(target.source_ref_id),
                    target.retrieval_document_id or "",
                    target.person_id or "",
                    _clean(target.reason),
                    _clean(target.review_question),
                ]
            )
        )
    for index, item in enumerate(output.retrieval_context):
        lines.append(
            "\t".join(
                [
                    "retrieval",
                    str(index),
                    item.retrieval_document_id,
                    item.source_kind,
                    "" if item.source_ref_id is None else str(item.source_ref_id),
                    str(item.score),
                    _clean(item.note),
                ]
            )
        )
    for index, limitation in enumerate(output.limitations):
        lines.append(f"limitation\t{index}\t{_clean(limitation)}")
    return lines


def _clean(value: str) -> str:
    return " ".join(value.split()).replace("\t", " ")
```

- [ ] **Step 5: Wire CLI command**

In `src/figure_data/cli.py`, add imports near the other AI imports:

```python
from figure_data.ai.no_path_context import InvalidNoPathContextError
from figure_data.ai.no_path_formatting import format_no_path_exploration_result
from figure_data.ai.no_path_service import generate_no_path_exploration
from figure_data.ai.embedding_provider import EmbeddingProviderConfigurationError
```

If `EmbeddingProviderConfigurationError` is already imported by the RAG command block, do not duplicate the import.

Add command after `generate_chain_explanation_command()` or near other AI generation commands:

```python
@app.command("suggest-no-path-exploration")
def suggest_no_path_exploration_command(
    from_query: Annotated[str | None, typer.Option("--from")] = None,
    to_query: Annotated[str | None, typer.Option("--to")] = None,
    from_person_id: Annotated[UUID | None, typer.Option("--from-person-id")] = None,
    to_person_id: Annotated[UUID | None, typer.Option("--to-person-id")] = None,
    from_cbdb_id: Annotated[str | None, typer.Option("--from-cbdb-id")] = None,
    to_cbdb_id: Annotated[str | None, typer.Option("--to-cbdb-id")] = None,
    max_depth: Annotated[int, typer.Option("--max-depth", min=1, max=30)] = 12,
    candidate_limit: Annotated[int, typer.Option("--candidate-limit", min=0, max=50)] = 10,
    rag_limit: Annotated[int, typer.Option("--rag-limit", min=0, max=10)] = 5,
    language: Annotated[str, typer.Option("--language")] = "zh-Hans",
    created_by: Annotated[str, typer.Option("--created-by")] = "local",
) -> None:
    """Generate an AI suggestion for a shortest-path query that currently has no path."""
    source = ChainEndpointInput(
        label="from",
        person_id=from_person_id,
        cbdb_id=from_cbdb_id,
        query=from_query,
    )
    target = ChainEndpointInput(
        label="to",
        person_id=to_person_id,
        cbdb_id=to_cbdb_id,
        query=to_query,
    )
    driver = None
    session = None
    try:
        settings = load_settings()
        factory = create_session_factory(settings)
        driver = create_neo4j_driver(settings)
        config = get_neo4j_config(settings)
        session = factory()
        with graph_session(driver, config.database) as neo4j_session:
            result = generate_no_path_exploration(
                session=session,
                neo4j_session=neo4j_session,
                settings=settings,
                source=source,
                target=target,
                max_depth=max_depth,
                created_by=created_by,
                language=language,
                candidate_limit=candidate_limit,
                rag_limit=rag_limit,
            )
        session.commit()
    except (
        AIProviderConfigurationError,
        AIProviderError,
        AIOutputValidationError,
        AIOutputPolicyViolation,
        InvalidNoPathContextError,
        EmbeddingProviderConfigurationError,
    ) as exc:
        if session is not None:
            session.commit()
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except (GraphOperationError, DriverError, Neo4jError, ValueError) as exc:
        if session is not None:
            session.rollback()
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except Exception:
        if session is not None:
            session.rollback()
        raise
    finally:
        if session is not None:
            session.close()
        if driver is not None:
            driver.close()
    for line in format_no_path_exploration_result(result):
        _echo_cli_line(line)
```

- [ ] **Step 6: Run Task 5 tests and commit**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_no_path_formatting.py tests/ai/test_no_path_cli.py -q
uv run --no-sync ruff check src/figure_data/ai/no_path_formatting.py src/figure_data/cli.py tests/ai/test_no_path_formatting.py tests/ai/test_no_path_cli.py
uv run --no-sync mypy src/figure_data/ai/no_path_formatting.py src/figure_data/cli.py tests/ai/test_no_path_formatting.py tests/ai/test_no_path_cli.py
```

Expected:

```text
All selected tests pass.
ruff passes.
mypy passes.
```

Commit:

```powershell
git add src/figure_data/ai/no_path_formatting.py src/figure_data/cli.py tests/ai/test_no_path_formatting.py tests/ai/test_no_path_cli.py
git commit -m "feat: 添加无路径探索建议 CLI"
```

## Task 6: README And Full Validation

**Files:**

- Modify: `README.md`
- Modify: `tests/test_readme_commands.py`

- [ ] **Step 1: Add failing README command test**

Append to `tests/test_readme_commands.py`:

```python
def test_readme_documents_no_path_exploration_command() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "figure-data suggest-no-path-exploration" in readme
    assert "无路径探索建议不会创建 candidate、不会提升 encounter、不会写 Neo4j" in readme
```

- [ ] **Step 2: Run README test and confirm it fails**

Run:

```powershell
uv run --no-sync python -m pytest tests/test_readme_commands.py::test_readme_documents_no_path_exploration_command -q
```

Expected:

```text
AssertionError because README does not yet mention suggest-no-path-exploration.
```

- [ ] **Step 3: Update README**

Add a short subsection near the current AI/RAG command documentation:

````markdown
### 无路径探索建议

当 `figure-data find-chain` 返回 `no_path` 时，可以生成一份只用于人工判断下一步资料扩展方向的 AI 建议：

```powershell
uv run --no-sync figure-data suggest-no-path-exploration `
  --from-person-id 38966b03-8aa7-5143-8021-2d266889b6c5 `
  --to-person-id 46cfdf66-08c4-5876-964b-4a95d098afe9 `
  --max-depth 12 `
  --candidate-limit 10 `
  --rag-limit 5 `
  --created-by local
````

该命令会先复用 Neo4j 最短路径查询确认当前图投影在给定深度内没有路径，再读取 PostgreSQL 中两端附近的已审核边数量、候选关系摘要，并可选使用本地 RAG 索引召回片段。输出结果只写入 `figure_data.ai_runs`，可通过 `figure-data inspect-ai-run --id <run_id>` 复查。

无路径探索建议不会创建 candidate、不会提升 encounter、不会写 Neo4j，也不能证明历史上两人没有关系或没有见过面。它只是给人工审核提供下一步复核候选、source_ref 或检索片段的方向。
```

- [ ] **Step 4: Run full validation**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai tests/graph tests/test_readme_commands.py -q
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected:

```text
All tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 5: Run optional local smoke with fake provider**

Only run this after `.env` has `FIGURE_AI_ENABLED=true`, `FIGURE_AI_PROVIDER=fake`, `FIGURE_AI_MODEL=fake-history-model`, and Neo4j/PostgreSQL are reachable:

```powershell
uv run --no-sync figure-data suggest-no-path-exploration `
  --from-person-id 38966b03-8aa7-5143-8021-2d266889b6c5 `
  --to-person-id 46cfdf66-08c4-5876-964b-4a95d098afe9 `
  --max-depth 1 `
  --rag-limit 0 `
  --created-by local-smoke
```

Expected:

```text
ai_run_id    <uuid>
summary      当前图投影在给定深度内没有返回连接路径...
limitation   ...
```

If the command exits with “no-path exploration requires a no-path result”, the selected pair has a path at that depth. Pick a pair that `figure-data find-chain ... --max-depth <n>` returns as `no_path`, then rerun.

- [ ] **Step 6: Commit docs and final test updates**

Commit:

```powershell
git add README.md tests/test_readme_commands.py
git commit -m "docs: 补充无路径探索建议 CLI 说明"
```

## Final Review Checklist

Before marking this plan complete, verify:

- `figure-data suggest-no-path-exploration --help` exits 0.
- A path-found query records a failed `ai_run` with `error_code=input_invalid` and exits non-zero.
- A no-path query with fake provider records a succeeded `ai_run`.
- `ai_runs.input_snapshot` contains `path_status=no_path`, endpoint ids, candidate summaries and optional retrieval context.
- AI output references only candidates, source refs, retrieval documents and endpoint person ids present in the input snapshot.
- No code path writes candidates, encounters, encounter_evidence or Neo4j.
- `figure-data inspect-ai-run --id <run_id>` can inspect the generated no-path output.
- `validate-graph` behavior is unchanged.

Final validation commands:

```powershell
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync python -m alembic heads
```

Expected final state:

```text
pytest passes.
ruff passes.
mypy passes.
alembic heads shows one current head.
```
