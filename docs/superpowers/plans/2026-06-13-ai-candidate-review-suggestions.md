# AI 候选审核建议 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Plan 1 的 AI 基础设施之上，为单个候选关系生成结构化 AI 审核建议，并把建议留存在 PostgreSQL 的独立 AI 表中。

**Architecture:** PostgreSQL 继续作为事实源，本计划新增 `ai_candidate_review_suggestions` 作为建议表，只保存 AI 建议和人工后续响应字段，不修改 candidates、encounters、encounter_evidence 或 Neo4j。`src/figure_data/ai/` 复用 Plan 1 的 provider、prompt registry、schema validation、AI run repository，并新增候选上下文、候选建议 repository/service/formatting；`src/figure_data/cli.py` 只新增薄 CLI。

**Tech Stack:** Python 3.12, Typer, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL JSONB, pytest, ruff, mypy.

---

## Scope Check

本计划实现阶段 4 的 Plan 2：候选审核建议。

本计划实现：

- 核对 Plan 1 已经提供的 AI 基础设施契约。
- 新增 `figure_data.ai_candidate_review_suggestions` ORM model 和 Alembic migration。
- 新增 AI 候选建议枚举。
- 新增 `candidate_review_suggestion` prompt definition。
- 新增候选建议 Pydantic 输出 schema。
- 新增输出策略校验，防止模型引用输入中不存在的 `source_ref_id`。
- 新增候选详情到 AI 输入快照的转换逻辑。
- 新增候选建议 repository。
- 新增候选建议生成 service。
- 新增 CLI：
  - `figure-data suggest-candidate-review --kind relationship --id 960698 --created-by lyl`
  - `figure-data list-ai-candidate-suggestions --status generated --limit 20`
  - `figure-data inspect-ai-candidate-suggestion --id <uuid>`
- README 中新增候选审核建议说明。

本计划不实现：

- 真实 provider SDK。
- 批量全库生成建议。
- 自动执行 `promote-encounter`、`reject-candidate` 或 `mark-candidate-review`。
- 自动修改候选 `review_status`。
- 自动创建、更新或撤回 encounter。
- 写入 Neo4j。
- 审核后台 UI。
- 人物链解释。
- RAG、embedding 或 pgvector 查询。

## Prerequisite Contract

本计划允许与 Plan 1 并行撰写，但执行前必须确认 Plan 1 已完成并提供以下契约。若实际实现和下列名称不一致，先把本计划中的 import 和调用点调整为 Plan 1 的真实名称，再开始 Task 1。

Plan 1 需要已经存在：

```text
src/figure_data/ai/errors.py
  AIError
  AIPromptError
  AIProviderConfigurationError
  AIProviderError
  AIOutputValidationError
  AIRunNotFoundError

src/figure_data/ai/provider.py
  AIProvider
  FakeAIProvider
  DisabledAIProvider
  create_ai_provider(settings)

src/figure_data/ai/prompts.py
  get_prompt_definition(prompt_key, prompt_version=None)
  PROMPT_DEFINITIONS

src/figure_data/ai/schemas.py
  AIFoundationDiagnosticOutput

src/figure_data/ai/service.py
  run_ai_prompt(...)
  AIRunResult

src/figure_data/ai/types.py
  PromptDefinition
  AIProviderRequest
  AIProviderResponse
  NewAIRun
  AIRunRecord

src/figure_data/ai/validation.py
  validate_ai_output(raw_text, schema)
  model_to_snapshot(model)

src/figure_data/db/models/ai.py
  AIPromptVersion
  AIRun

alembic/versions/20260613_0001_create_ai_foundation_tables.py
  revision = "20260613_0001"
```

执行前验证命令：

```powershell
uv run --no-sync python -m pytest tests/ai/test_provider.py tests/ai/test_prompts.py tests/ai/test_validation.py tests/ai/test_service.py -q
uv run --no-sync python -m pytest tests/db/test_ai_model_metadata.py tests/db/test_ai_migration.py -q
uv run --no-sync figure-data inspect-ai-run --help
```

预期：

```text
Plan 1 tests pass.
inspect-ai-run help exits 0.
```

## File Structure

新增：

```text
src/figure_data/ai/candidate_context.py
src/figure_data/ai/candidate_formatting.py
src/figure_data/ai/candidate_policy.py
src/figure_data/ai/candidate_repository.py
src/figure_data/ai/candidate_service.py
src/figure_data/db/models/ai_candidate.py
alembic/versions/20260613_0002_create_ai_candidate_review_suggestions.py

tests/ai/test_candidate_context.py
tests/ai/test_candidate_formatting.py
tests/ai/test_candidate_policy.py
tests/ai/test_candidate_prompt_schema.py
tests/ai/test_candidate_repository.py
tests/ai/test_candidate_service.py
tests/ai/test_candidate_suggestion_cli.py
tests/db/test_ai_candidate_suggestion_model_metadata.py
tests/db/test_ai_candidate_suggestion_migration.py
```

修改：

```text
src/figure_data/ai/errors.py
src/figure_data/ai/prompts.py
src/figure_data/ai/schemas.py
src/figure_data/ai/service.py
src/figure_data/cli.py
src/figure_data/db/enums.py
src/figure_data/db/models/__init__.py
tests/test_readme_commands.py
README.md
```

职责边界：

- `ai/candidate_context.py`：只把现有候选详情转换成 AI 输入快照，并检查同一无向人物对是否已有 active path encounter。
- `ai/candidate_policy.py`：只做候选建议输出的业务边界校验。
- `ai/candidate_repository.py`：只读写 `ai_candidate_review_suggestions`。
- `ai/candidate_service.py`：编排候选读取、prompt 输入、provider 调用、AI run、输出策略校验和建议写入。
- `ai/candidate_formatting.py`：只处理 CLI 输出文本。
- `cli.py`：只做参数解析、session/provider 组装、错误映射和输出。

## Task 1: Candidate Suggestion Model And Migration

**Files:**

- Modify: `src/figure_data/db/enums.py`
- Create: `src/figure_data/db/models/ai_candidate.py`
- Modify: `src/figure_data/db/models/__init__.py`
- Create: `alembic/versions/20260613_0002_create_ai_candidate_review_suggestions.py`
- Create: `tests/db/test_ai_candidate_suggestion_model_metadata.py`
- Create: `tests/db/test_ai_candidate_suggestion_migration.py`

- [ ] **Step 1: Add failing metadata tests**

Create `tests/db/test_ai_candidate_suggestion_model_metadata.py`:

```python
from sqlalchemy import CheckConstraint, UniqueConstraint

from figure_data.db.base import Base
from figure_data.db.enums import AICandidateReviewSuggestedAction, AICandidateSuggestionStatus
from figure_data.db.models import ai_candidate


def test_ai_candidate_suggestion_enums_define_values() -> None:
    assert AICandidateReviewSuggestedAction.PROMOTE_CANDIDATE.value == "promote_candidate"
    assert AICandidateReviewSuggestedAction.NEEDS_HUMAN_REVIEW.value == "needs_human_review"
    assert AICandidateReviewSuggestedAction.REJECT_DUPLICATE.value == "reject_duplicate"
    assert AICandidateReviewSuggestedAction.INSUFFICIENT_EVIDENCE.value == "insufficient_evidence"
    assert AICandidateReviewSuggestedAction.NOT_PATH_CANDIDATE.value == "not_path_candidate"
    assert AICandidateSuggestionStatus.GENERATED.value == "generated"
    assert AICandidateSuggestionStatus.ARCHIVED.value == "archived"


def test_ai_candidate_suggestion_model_uses_figure_data_schema() -> None:
    assert ai_candidate
    assert Base.metadata.tables["figure_data.ai_candidate_review_suggestions"].schema == "figure_data"


def test_ai_candidate_suggestion_model_links_ai_run() -> None:
    table = Base.metadata.tables["figure_data.ai_candidate_review_suggestions"]

    foreign_keys = {
        foreign_key.target_fullname for foreign_key in table.c.ai_run_id.foreign_keys
    }

    assert "figure_data.ai_runs.id" in foreign_keys


def test_ai_candidate_suggestion_model_declares_constraints() -> None:
    table = Base.metadata.tables["figure_data.ai_candidate_review_suggestions"]

    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert "ck_ai_candidate_review_suggestions_kind" in check_names
    assert "ck_ai_candidate_review_suggestions_action" in check_names
    assert "ck_ai_candidate_review_suggestions_status" in check_names
    assert "ck_ai_candidate_review_suggestions_priority_score" in check_names
    assert ("ai_run_id", "candidate_kind", "candidate_id") in unique_columns


def test_ai_candidate_suggestion_model_declares_indexes() -> None:
    table = Base.metadata.tables["figure_data.ai_candidate_review_suggestions"]
    index_names = {index.name for index in table.indexes}

    assert {
        "ix_figure_data_ai_candidate_review_suggestions_candidate",
        "ix_figure_data_ai_candidate_review_suggestions_status",
        "ix_figure_data_ai_candidate_review_suggestions_action",
        "ix_figure_data_ai_candidate_review_suggestions_created_at",
    }.issubset(index_names)
```

- [ ] **Step 2: Add failing migration tests**

Create `tests/db/test_ai_candidate_suggestion_migration.py`:

```python
from pathlib import Path


MIGRATION_PATH = Path(
    "alembic/versions/20260613_0002_create_ai_candidate_review_suggestions.py"
)


def test_ai_candidate_suggestion_migration_exists_and_depends_on_ai_foundation() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision: str = "20260613_0002"' in migration_source
    assert 'down_revision: str | None = "20260613_0001"' in migration_source


def test_ai_candidate_suggestion_migration_uses_explicit_operations() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Base.metadata.create_all" not in migration_source
    assert "Base.metadata.drop_all" not in migration_source
    assert "DROP SCHEMA" not in migration_source
    assert 'op.create_table("ai_candidate_review_suggestions"' in migration_source
    assert 'op.drop_table("ai_candidate_review_suggestions"' in migration_source


def test_ai_candidate_suggestion_migration_declares_constraints() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "fk_ai_candidate_review_suggestions_ai_run_id_ai_runs" in migration_source
    assert "uq_ai_candidate_review_suggestions_run_candidate" in migration_source
    assert "ck_ai_candidate_review_suggestions_kind" in migration_source
    assert "ck_ai_candidate_review_suggestions_action" in migration_source
    assert "ck_ai_candidate_review_suggestions_status" in migration_source
    assert "ck_ai_candidate_review_suggestions_priority_score" in migration_source
```

- [ ] **Step 3: Run model and migration tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/db/test_ai_candidate_suggestion_model_metadata.py tests/db/test_ai_candidate_suggestion_migration.py -q
```

Expected:

```text
FAIL because enums, model, and migration do not exist yet.
```

- [ ] **Step 4: Add candidate suggestion enums**

Append to `src/figure_data/db/enums.py`:

```python


class AICandidateReviewSuggestedAction(StrEnum):
    PROMOTE_CANDIDATE = "promote_candidate"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    REJECT_DUPLICATE = "reject_duplicate"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_PATH_CANDIDATE = "not_path_candidate"


class AICandidateSuggestionStatus(StrEnum):
    GENERATED = "generated"
    ARCHIVED = "archived"
```

- [ ] **Step 5: Create ORM model**

Create `src/figure_data/db/models/ai_candidate.py`:

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base


class AICandidateReviewSuggestion(Base):
    __tablename__ = "ai_candidate_review_suggestions"
    __table_args__ = (
        CheckConstraint(
            "candidate_kind in ('relationship', 'kinship')",
            name="ck_ai_candidate_review_suggestions_kind",
        ),
        CheckConstraint(
            "suggested_action in ("
            "'promote_candidate', 'needs_human_review', 'reject_duplicate', "
            "'insufficient_evidence', 'not_path_candidate'"
            ")",
            name="ck_ai_candidate_review_suggestions_action",
        ),
        CheckConstraint(
            "status in ('generated', 'archived')",
            name="ck_ai_candidate_review_suggestions_status",
        ),
        CheckConstraint(
            "priority_score >= 0 and priority_score <= 100",
            name="ck_ai_candidate_review_suggestions_priority_score",
        ),
        UniqueConstraint(
            "ai_run_id",
            "candidate_kind",
            "candidate_id",
            name="uq_ai_candidate_review_suggestions_run_candidate",
        ),
        Index(
            "ix_figure_data_ai_candidate_review_suggestions_candidate",
            "candidate_kind",
            "candidate_id",
        ),
        Index("ix_figure_data_ai_candidate_review_suggestions_status", "status"),
        Index("ix_figure_data_ai_candidate_review_suggestions_action", "suggested_action"),
        Index("ix_figure_data_ai_candidate_review_suggestions_created_at", "created_at"),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    ai_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("figure_data.ai_runs.id"),
        nullable=False,
    )
    candidate_kind: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_id: Mapped[int] = mapped_column(Integer, nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_summary_draft: Mapped[str] = mapped_column(Text, nullable=False)
    risk_flags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    supporting_source_ref_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    review_questions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 6: Export model module**

Modify `src/figure_data/db/models/__init__.py` so the new module is imported:

```python
from figure_data.db.models import (
    ai,
    ai_candidate,
    encounter,
    identity,
    import_batch,
    office,
    person,
    relationship,
    source,
)

__all__ = [
    "ai",
    "ai_candidate",
    "encounter",
    "identity",
    "import_batch",
    "office",
    "person",
    "relationship",
    "source",
]
```

If Plan 1 did not name its model module `ai`, keep the Plan 1 module name and add only `ai_candidate` beside it.

- [ ] **Step 7: Create migration**

Create `alembic/versions/20260613_0002_create_ai_candidate_review_suggestions.py`:

```python
"""create AI candidate review suggestions table

Revision ID: 20260613_0002
Revises: 20260613_0001
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260613_0002"
down_revision: str | None = "20260613_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "ai_candidate_review_suggestions",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("ai_run_id", _uuid(), nullable=False),
        sa.Column("candidate_kind", sa.Text(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.Column("priority_score", sa.Integer(), nullable=False),
        sa.Column("evidence_summary_draft", sa.Text(), nullable=False),
        sa.Column("risk_flags", postgresql.JSONB(), nullable=False),
        sa.Column("supporting_source_ref_ids", postgresql.JSONB(), nullable=False),
        sa.Column("review_questions", postgresql.JSONB(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "candidate_kind in ('relationship', 'kinship')",
            name="ck_ai_candidate_review_suggestions_kind",
        ),
        sa.CheckConstraint(
            "suggested_action in ("
            "'promote_candidate', 'needs_human_review', 'reject_duplicate', "
            "'insufficient_evidence', 'not_path_candidate'"
            ")",
            name="ck_ai_candidate_review_suggestions_action",
        ),
        sa.CheckConstraint(
            "status in ('generated', 'archived')",
            name="ck_ai_candidate_review_suggestions_status",
        ),
        sa.CheckConstraint(
            "priority_score >= 0 and priority_score <= 100",
            name="ck_ai_candidate_review_suggestions_priority_score",
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["figure_data.ai_runs.id"],
            name="fk_ai_candidate_review_suggestions_ai_run_id_ai_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_candidate_review_suggestions"),
        sa.UniqueConstraint(
            "ai_run_id",
            "candidate_kind",
            "candidate_id",
            name="uq_ai_candidate_review_suggestions_run_candidate",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_candidate_review_suggestions_candidate",
        "ai_candidate_review_suggestions",
        ["candidate_kind", "candidate_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_candidate_review_suggestions_status",
        "ai_candidate_review_suggestions",
        ["status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_candidate_review_suggestions_action",
        "ai_candidate_review_suggestions",
        ["suggested_action"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_candidate_review_suggestions_created_at",
        "ai_candidate_review_suggestions",
        ["created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_figure_data_ai_candidate_review_suggestions_created_at",
        table_name="ai_candidate_review_suggestions",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_candidate_review_suggestions_action",
        table_name="ai_candidate_review_suggestions",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_candidate_review_suggestions_status",
        table_name="ai_candidate_review_suggestions",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_candidate_review_suggestions_candidate",
        table_name="ai_candidate_review_suggestions",
        schema=SCHEMA,
    )
    op.drop_table("ai_candidate_review_suggestions", schema=SCHEMA)
```

- [ ] **Step 8: Run Task 1 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/db/test_ai_candidate_suggestion_model_metadata.py tests/db/test_ai_candidate_suggestion_migration.py -q
uv run --no-sync ruff check src/figure_data/db tests/db/test_ai_candidate_suggestion_model_metadata.py tests/db/test_ai_candidate_suggestion_migration.py
uv run --no-sync mypy src/figure_data/db tests/db/test_ai_candidate_suggestion_model_metadata.py tests/db/test_ai_candidate_suggestion_migration.py
```

Expected:

```text
All Task 1 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 9: Commit Task 1**

Run:

```powershell
git add src/figure_data/db/enums.py src/figure_data/db/models/__init__.py src/figure_data/db/models/ai_candidate.py alembic/versions/20260613_0002_create_ai_candidate_review_suggestions.py tests/db/test_ai_candidate_suggestion_model_metadata.py tests/db/test_ai_candidate_suggestion_migration.py
git commit -m "feat: 添加 AI 候选审核建议表"
```

## Task 2: Candidate Prompt, Schema, And Policy Guard

**Files:**

- Modify: `src/figure_data/ai/errors.py`
- Modify: `src/figure_data/ai/service.py`
- Modify: `src/figure_data/ai/schemas.py`
- Modify: `src/figure_data/ai/prompts.py`
- Create: `src/figure_data/ai/candidate_policy.py`
- Create: `tests/ai/test_candidate_prompt_schema.py`
- Create: `tests/ai/test_candidate_policy.py`
- Modify: `tests/ai/test_service.py`

- [ ] **Step 1: Add failing prompt and schema tests**

Create `tests/ai/test_candidate_prompt_schema.py`:

```python
from pydantic import ValidationError
from pytest import raises

from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.schemas import CandidateReviewSuggestionOutput


def test_candidate_review_prompt_is_registered() -> None:
    prompt = get_prompt_definition("candidate_review_suggestion")

    assert prompt.prompt_key == "candidate_review_suggestion"
    assert prompt.purpose == "candidate_review_suggestion"
    assert prompt.output_schema_name == "candidate_review_suggestion_output"
    assert prompt.output_schema_version == "1"
    assert "{candidate_json}" in prompt.user_prompt_template
    assert "不得自动提升" in prompt.system_prompt


def test_candidate_review_suggestion_output_accepts_valid_payload() -> None:
    output = CandidateReviewSuggestionOutput.model_validate(
        {
            "suggested_action": "needs_human_review",
            "priority_score": 72,
            "evidence_summary_draft": "结构化关系显示二人可能有直接互动，需要审核原始来源。",
            "risk_flags": ["source_text_missing"],
            "supporting_source_ref_ids": [101, 102],
            "review_questions": ["是否能找到原书页码对应文字？"],
            "explanation": "该建议只基于输入的候选关系和 source_ref 信息。",
        }
    )

    assert output.suggested_action == "needs_human_review"
    assert output.priority_score == 72
    assert output.supporting_source_ref_ids == [101, 102]


def test_candidate_review_suggestion_output_rejects_invalid_action() -> None:
    with raises(ValidationError):
        CandidateReviewSuggestionOutput.model_validate(
            {
                "suggested_action": "promote_encounter_now",
                "priority_score": 72,
                "evidence_summary_draft": "结构化关系显示二人可能有直接互动。",
                "risk_flags": [],
                "supporting_source_ref_ids": [],
                "review_questions": [],
                "explanation": "该建议只基于输入。",
            }
        )
```

- [ ] **Step 2: Add failing policy tests**

Create `tests/ai/test_candidate_policy.py`:

```python
from pytest import raises

from figure_data.ai.candidate_policy import validate_candidate_review_suggestion_policy
from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.schemas import CandidateReviewSuggestionOutput


def suggestion_output(**overrides: object) -> CandidateReviewSuggestionOutput:
    payload = {
        "suggested_action": "needs_human_review",
        "priority_score": 50,
        "evidence_summary_draft": "结构化关系显示二人可能有互动，需要人工查证。",
        "risk_flags": ["source_text_missing"],
        "supporting_source_ref_ids": [101],
        "review_questions": ["是否有原文可支持见面？"],
        "explanation": "仅基于候选关系和来源引用生成。",
    }
    payload.update(overrides)
    return CandidateReviewSuggestionOutput.model_validate(payload)


def test_candidate_policy_accepts_known_source_ref_ids() -> None:
    validate_candidate_review_suggestion_policy(
        suggestion_output(),
        allowed_source_ref_ids={101, 102},
    )


def test_candidate_policy_rejects_unknown_source_ref_ids() -> None:
    with raises(AIOutputPolicyViolation, match="unknown source_ref_id"):
        validate_candidate_review_suggestion_policy(
            suggestion_output(supporting_source_ref_ids=[999]),
            allowed_source_ref_ids={101, 102},
        )


def test_candidate_policy_rejects_empty_explanation_after_strip() -> None:
    output = suggestion_output(explanation="   ")

    with raises(AIOutputPolicyViolation, match="explanation is required"):
        validate_candidate_review_suggestion_policy(output, allowed_source_ref_ids={101})
```

- [ ] **Step 3: Add failing service guard test**

Append to `tests/ai/test_service.py`:

```python
from figure_data.ai.errors import AIOutputPolicyViolation


def test_run_ai_prompt_records_policy_failure() -> None:
    repository = FakeRunRepository()
    provider = FakeAIProvider(raw_text='{"message":"ready","echo_id":"abc","warnings":[]}')

    def reject_output(output: object) -> None:
        raise AIOutputPolicyViolation("policy rejected output")

    with raises(AIOutputPolicyViolation):
        run_ai_prompt(
            session=object(),
            prompt=get_prompt_definition("ai_foundation_diagnostic"),
            provider=provider,
            output_schema=AIFoundationDiagnosticOutput,
            input_variables={"echo_id": "abc"},
            input_snapshot={"echo_id": "abc"},
            model_name="fake-history-model",
            max_output_tokens=1200,
            created_by="tester",
            repository=repository,
            output_guard=reject_output,
        )

    assert repository.succeeded == []
    assert repository.failed[0]["error_code"] == "output_policy_violation"
    assert repository.failed[0]["error_message"] == "policy rejected output"
```

If `tests/ai/test_service.py` does not yet import `raises`, `get_prompt_definition`, `AIFoundationDiagnosticOutput`, `FakeAIProvider`, and `run_ai_prompt`, add the imports used by the existing Plan 1 tests.

- [ ] **Step 4: Run Task 2 tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_candidate_prompt_schema.py tests/ai/test_candidate_policy.py tests/ai/test_service.py -q
```

Expected:

```text
FAIL because candidate schema, prompt, policy, and output_guard do not exist yet.
```

- [ ] **Step 5: Add policy violation error**

Append to `src/figure_data/ai/errors.py`:

```python


class AIOutputPolicyViolation(AIOutputValidationError):
    """Raised when model output is valid JSON but violates FigureChain business boundaries."""
```

- [ ] **Step 6: Extend run_ai_prompt with output_guard**

Modify `src/figure_data/ai/service.py` so the imports and `run_ai_prompt` signature include a guard:

```python
from collections.abc import Callable

from figure_data.ai.errors import AIOutputPolicyViolation, AIOutputValidationError
```

Use this type alias near `OutputModel`:

```python
OutputGuard = Callable[[OutputModel], None]
```

Update `run_ai_prompt`:

```python
def run_ai_prompt(
    *,
    session: Session | object,
    prompt: PromptDefinition,
    provider: AIProvider,
    output_schema: type[OutputModel],
    input_variables: dict[str, object],
    input_snapshot: dict[str, Any],
    model_name: str,
    max_output_tokens: int,
    created_by: str,
    repository: AIRunRepository | None = None,
    output_guard: OutputGuard[OutputModel] | None = None,
) -> AIRunResult:
    resolved_repository = repository or PostgresAIRunRepository()
    prompt_version_id = resolved_repository.ensure_prompt_version(session, prompt)  # type: ignore[arg-type]
    input_hash = _stable_hash(
        {
            "prompt_key": prompt.prompt_key,
            "prompt_version": prompt.prompt_version,
            "input": input_snapshot,
        }
    )
    run_id = resolved_repository.create_run(
        session,  # type: ignore[arg-type]
        NewAIRun(
            purpose=prompt.purpose,
            provider=getattr(provider, "provider_name", "unknown"),
            model_name=model_name,
            prompt_version_id=prompt_version_id,
            input_hash=input_hash,
            input_snapshot=input_snapshot,
            created_by=created_by,
        ),
    )
    request = AIProviderRequest(
        system_prompt=prompt.system_prompt,
        user_prompt=prompt.user_prompt_template.format(**input_variables),
        model_name=model_name,
        max_output_tokens=max_output_tokens,
    )
    response = provider.generate(request)
    try:
        output = validate_ai_output(response.raw_text, output_schema)
        if output_guard is not None:
            output_guard(output)
    except AIOutputPolicyViolation as exc:
        resolved_repository.mark_failed(
            session,  # type: ignore[arg-type]
            run_id=run_id,
            error_code=AIErrorCode.OUTPUT_POLICY_VIOLATION.value,
            error_message=str(exc),
            raw_output=response.raw_text,
        )
        raise
    except AIOutputValidationError as exc:
        resolved_repository.mark_failed(
            session,  # type: ignore[arg-type]
            run_id=run_id,
            error_code=AIErrorCode.SCHEMA_INVALID.value,
            error_message=str(exc),
            raw_output=response.raw_text,
        )
        raise
    resolved_repository.mark_succeeded(
        session,  # type: ignore[arg-type]
        run_id=run_id,
        output_snapshot=model_to_snapshot(output),
        raw_output=response.raw_text,
    )
    return AIRunResult(run_id=run_id, output=output)
```

Keep the existing `_stable_hash` implementation unchanged.

- [ ] **Step 7: Add candidate output schema**

Append to `src/figure_data/ai/schemas.py`:

```python
from typing import Literal


class CandidateReviewSuggestionOutput(BaseModel):
    suggested_action: Literal[
        "promote_candidate",
        "needs_human_review",
        "reject_duplicate",
        "insufficient_evidence",
        "not_path_candidate",
    ]
    priority_score: int = Field(ge=0, le=100)
    evidence_summary_draft: str = Field(min_length=1, max_length=2000)
    risk_flags: list[str] = Field(default_factory=list, max_length=20)
    supporting_source_ref_ids: list[int] = Field(default_factory=list, max_length=50)
    review_questions: list[str] = Field(default_factory=list, max_length=20)
    explanation: str = Field(min_length=1, max_length=2000)
```

If `BaseModel` and `Field` are already imported by Plan 1, only add the `Literal` import and the new class.

- [ ] **Step 8: Add candidate prompt**

Modify `src/figure_data/ai/prompts.py` by adding this prompt definition after the diagnostic prompt:

```python
CANDIDATE_REVIEW_SUGGESTION_PROMPT = PromptDefinition(
    prompt_key="candidate_review_suggestion",
    prompt_version="2026-06-13.1",
    purpose="candidate_review_suggestion",
    system_prompt=(
        "你是 FigureChain 的候选关系审核助手。"
        "你只能基于输入 JSON 中的候选关系、人物、source_ref 和审核状态作答。"
        "不得编造史料、页码、人物关系或见面场景。"
        "不得自动提升 encounter，不得要求系统绕过人工审核。"
        "priority_score 只表示人工审核优先级，不表示历史事实置信度。"
        "当缺少原文时，必须说明来源为结构化资料或页码线索。"
        "只返回 JSON object。"
    ),
    user_prompt_template=(
        "请为以下候选关系生成一个审核建议。"
        "输入 JSON：\n{candidate_json}\n"
        "输出字段必须为 suggested_action, priority_score, evidence_summary_draft, "
        "risk_flags, supporting_source_ref_ids, review_questions, explanation。"
    ),
    output_schema_name="candidate_review_suggestion_output",
    output_schema_version="1",
)
```

Then include it in `PROMPT_DEFINITIONS`:

```python
PROMPT_DEFINITIONS = (
    AI_FOUNDATION_DIAGNOSTIC_PROMPT,
    CANDIDATE_REVIEW_SUGGESTION_PROMPT,
)
```

- [ ] **Step 9: Create candidate policy module**

Create `src/figure_data/ai/candidate_policy.py`:

```python
from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.schemas import CandidateReviewSuggestionOutput


def validate_candidate_review_suggestion_policy(
    output: CandidateReviewSuggestionOutput,
    *,
    allowed_source_ref_ids: set[int],
) -> None:
    unknown_source_ref_ids = [
        source_ref_id
        for source_ref_id in output.supporting_source_ref_ids
        if source_ref_id not in allowed_source_ref_ids
    ]
    if unknown_source_ref_ids:
        joined = ",".join(str(source_ref_id) for source_ref_id in unknown_source_ref_ids)
        raise AIOutputPolicyViolation(f"unknown source_ref_id in AI output: {joined}")
    if not output.explanation.strip():
        raise AIOutputPolicyViolation("explanation is required")
    if not output.evidence_summary_draft.strip():
        raise AIOutputPolicyViolation("evidence_summary_draft is required")
```

- [ ] **Step 10: Run Task 2 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_candidate_prompt_schema.py tests/ai/test_candidate_policy.py tests/ai/test_service.py -q
uv run --no-sync ruff check src/figure_data/ai tests/ai/test_candidate_prompt_schema.py tests/ai/test_candidate_policy.py tests/ai/test_service.py
uv run --no-sync mypy src/figure_data/ai tests/ai/test_candidate_prompt_schema.py tests/ai/test_candidate_policy.py tests/ai/test_service.py
```

Expected:

```text
All Task 2 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 11: Commit Task 2**

Run:

```powershell
git add src/figure_data/ai/errors.py src/figure_data/ai/service.py src/figure_data/ai/schemas.py src/figure_data/ai/prompts.py src/figure_data/ai/candidate_policy.py tests/ai/test_candidate_prompt_schema.py tests/ai/test_candidate_policy.py tests/ai/test_service.py
git commit -m "feat: 添加 AI 候选建议 prompt 与策略校验"
```

## Task 3: Candidate Prompt Context

**Files:**

- Create: `src/figure_data/ai/candidate_context.py`
- Create: `tests/ai/test_candidate_context.py`

- [ ] **Step 1: Add failing candidate context tests**

Create `tests/ai/test_candidate_context.py`:

```python
from uuid import UUID

from figure_data.ai.candidate_context import (
    candidate_review_prompt_input_from_detail,
)
from figure_data.review.types import (
    CandidateDetail,
    CandidateKind,
    CandidatePerson,
    CandidateSourceRef,
    PromotionReadiness,
)


def candidate_person(name: str, person_id: str, cbdb_id: int) -> CandidatePerson:
    return CandidatePerson(
        person_id=UUID(person_id),
        cbdb_id=cbdb_id,
        primary_name_zh_hant=name,
        primary_name_zh_hans=name,
        primary_name_romanized=None,
        birth_year=1000,
        death_year=1060,
        external_ids=[f"cbdb:{cbdb_id}"],
    )


def candidate_detail() -> CandidateDetail:
    return CandidateDetail(
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        person_a=candidate_person("许几", "00000000-0000-0000-0000-000000000101", 101),
        person_b=candidate_person("韩琦", "00000000-0000-0000-0000-000000000102", 102),
        candidate_strength="high",
        candidate_basis="direct_interaction_likely",
        relation_label="谒见",
        source_work_id=123,
        pages="卷一",
        notes="许几谒韩琦于魏",
        review_status="unreviewed",
        reviewed_by=None,
        review_note=None,
        promoted_encounter_id=None,
        source_name="cbdb",
        source_table="ASSOC_DATA",
        source_pk="960698",
        raw_cbdb_snapshot={"source_table": "ASSOC_DATA", "source_pk": "960698"},
        source_refs=[
            CandidateSourceRef(
                source_ref_id=501,
                source_work_id=123,
                title_zh="宋史",
                title_en=None,
                pages="卷一",
                notes="许几谒韩琦于魏",
            )
        ],
        promotion_readiness=PromotionReadiness(
            default_promotable=True,
            default_path_eligible=True,
            reasons=[],
        ),
    )


def test_candidate_review_prompt_input_preserves_traceable_fields() -> None:
    prompt_input = candidate_review_prompt_input_from_detail(
        candidate_detail(),
        has_active_path_encounter_for_pair=False,
    )
    payload = prompt_input.model_dump(mode="json")

    assert payload["candidate"]["kind"] == "relationship"
    assert payload["candidate"]["id"] == 960698
    assert payload["candidate"]["candidate_strength"] == "high"
    assert payload["candidate"]["candidate_basis"] == "direct_interaction_likely"
    assert payload["candidate"]["review_status"] == "unreviewed"
    assert payload["candidate"]["promotion_readiness"]["default_promotable"] is True
    assert payload["candidate"]["has_active_path_encounter_for_pair"] is False
    assert payload["person_a"]["primary_name_zh_hant"] == "许几"
    assert payload["person_b"]["primary_name_zh_hant"] == "韩琦"
    assert payload["source_refs"][0]["source_ref_id"] == 501


def test_candidate_review_prompt_input_marks_existing_path_encounter() -> None:
    prompt_input = candidate_review_prompt_input_from_detail(
        candidate_detail(),
        has_active_path_encounter_for_pair=True,
    )

    assert prompt_input.candidate.has_active_path_encounter_for_pair is True
```

- [ ] **Step 2: Run context tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_candidate_context.py -q
```

Expected:

```text
FAIL because candidate_context.py does not exist yet.
```

- [ ] **Step 3: Create candidate context module**

Create `src/figure_data/ai/candidate_context.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.db.enums import EncounterKind, EncounterStatus
from figure_data.review.types import CandidateDetail, CandidatePerson, CandidateSourceRef


class CandidateReviewPersonInput(BaseModel):
    person_id: str | None
    cbdb_id: int | None
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    external_ids: list[str] = Field(default_factory=list)


class CandidateReviewSourceRefInput(BaseModel):
    source_ref_id: int
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    notes: str | None


class CandidateReviewPromotionReadinessInput(BaseModel):
    default_promotable: bool
    default_path_eligible: bool
    reasons: list[str] = Field(default_factory=list)


class CandidateReviewCandidateInput(BaseModel):
    kind: str
    id: int
    candidate_strength: str
    candidate_basis: str
    relation_label: str | None
    source_work_id: int | None
    pages: str | None
    notes: str | None
    review_status: str
    reviewed_by: str | None
    review_note: str | None
    promoted_encounter_id: str | None
    source_name: str
    source_table: str
    source_pk: str
    has_active_path_encounter_for_pair: bool
    promotion_readiness: CandidateReviewPromotionReadinessInput


class CandidateReviewPromptInput(BaseModel):
    candidate: CandidateReviewCandidateInput
    person_a: CandidateReviewPersonInput
    person_b: CandidateReviewPersonInput
    source_refs: list[CandidateReviewSourceRefInput]


def build_candidate_review_prompt_input(
    session: Session,
    detail: CandidateDetail,
) -> CandidateReviewPromptInput:
    return candidate_review_prompt_input_from_detail(
        detail,
        has_active_path_encounter_for_pair=has_active_path_encounter_for_pair(
            session,
            detail,
        ),
    )


def candidate_review_prompt_input_from_detail(
    detail: CandidateDetail,
    *,
    has_active_path_encounter_for_pair: bool,
) -> CandidateReviewPromptInput:
    return CandidateReviewPromptInput(
        candidate=CandidateReviewCandidateInput(
            kind=detail.candidate_kind.value,
            id=detail.candidate_id,
            candidate_strength=detail.candidate_strength,
            candidate_basis=detail.candidate_basis,
            relation_label=detail.relation_label,
            source_work_id=detail.source_work_id,
            pages=detail.pages,
            notes=detail.notes,
            review_status=detail.review_status,
            reviewed_by=detail.reviewed_by,
            review_note=detail.review_note,
            promoted_encounter_id=(
                str(detail.promoted_encounter_id) if detail.promoted_encounter_id else None
            ),
            source_name=detail.source_name,
            source_table=detail.source_table,
            source_pk=detail.source_pk,
            has_active_path_encounter_for_pair=has_active_path_encounter_for_pair,
            promotion_readiness=CandidateReviewPromotionReadinessInput(
                default_promotable=detail.promotion_readiness.default_promotable,
                default_path_eligible=detail.promotion_readiness.default_path_eligible,
                reasons=detail.promotion_readiness.reasons,
            ),
        ),
        person_a=_person_input(detail.person_a),
        person_b=_person_input(detail.person_b),
        source_refs=[_source_ref_input(source_ref) for source_ref in detail.source_refs],
    )


def has_active_path_encounter_for_pair(session: Session, detail: CandidateDetail) -> bool:
    person_a_id = detail.person_a.person_id
    person_b_id = detail.person_b.person_id
    if person_a_id is None or person_b_id is None:
        return False
    value = session.execute(
        text(
            """
            select count(*) > 0
            from figure_data.encounters e
            where e.status = :status
              and e.path_eligible is true
              and e.encounter_kind = :encounter_kind
              and (
                (e.person_a_id = :person_a_id and e.person_b_id = :person_b_id)
                or
                (e.person_a_id = :person_b_id and e.person_b_id = :person_a_id)
              )
            """
        ),
        {
            "status": EncounterStatus.ACTIVE.value,
            "encounter_kind": EncounterKind.DIRECT_INTERACTION.value,
            "person_a_id": person_a_id,
            "person_b_id": person_b_id,
        },
    ).scalar_one()
    return bool(value)


def _person_input(person: CandidatePerson) -> CandidateReviewPersonInput:
    return CandidateReviewPersonInput(
        person_id=str(person.person_id) if person.person_id else None,
        cbdb_id=person.cbdb_id,
        primary_name_zh_hant=person.primary_name_zh_hant,
        primary_name_zh_hans=person.primary_name_zh_hans,
        primary_name_romanized=person.primary_name_romanized,
        birth_year=person.birth_year,
        death_year=person.death_year,
        external_ids=person.external_ids,
    )


def _source_ref_input(source_ref: CandidateSourceRef) -> CandidateReviewSourceRefInput:
    return CandidateReviewSourceRefInput(
        source_ref_id=source_ref.source_ref_id,
        source_work_id=source_ref.source_work_id,
        title_zh=source_ref.title_zh,
        title_en=source_ref.title_en,
        pages=source_ref.pages,
        notes=source_ref.notes,
    )
```

- [ ] **Step 4: Run Task 3 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_candidate_context.py -q
uv run --no-sync ruff check src/figure_data/ai/candidate_context.py tests/ai/test_candidate_context.py
uv run --no-sync mypy src/figure_data/ai/candidate_context.py tests/ai/test_candidate_context.py
```

Expected:

```text
All Task 3 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 5: Commit Task 3**

Run:

```powershell
git add src/figure_data/ai/candidate_context.py tests/ai/test_candidate_context.py
git commit -m "feat: 组装 AI 候选审核上下文"
```

## Task 4: Candidate Suggestion Repository

**Files:**

- Create: `src/figure_data/ai/candidate_repository.py`
- Create: `tests/ai/test_candidate_repository.py`

- [ ] **Step 1: Add failing repository tests**

Create `tests/ai/test_candidate_repository.py`:

```python
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from figure_data.ai.candidate_repository import (
    CandidateSuggestionListFilters,
    NewCandidateReviewSuggestion,
    create_candidate_review_suggestion,
    get_candidate_review_suggestion,
    list_candidate_review_suggestions,
)
from figure_data.review.types import CandidateKind


@dataclass
class ScalarResult:
    value: object

    def scalar_one(self) -> object:
        return self.value


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> "MappingResult":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self.rows

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []
        self.suggestion_id = UUID("00000000-0000-0000-0000-000000000201")

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> object:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(params or {})
        if "insert into figure_data.ai_candidate_review_suggestions" in sql:
            return ScalarResult(self.suggestion_id)
        row = {
            "id": self.suggestion_id,
            "ai_run_id": UUID("00000000-0000-0000-0000-000000000301"),
            "candidate_kind": "relationship",
            "candidate_id": 960698,
            "suggested_action": "needs_human_review",
            "priority_score": 70,
            "evidence_summary_draft": "结构化关系显示二人可能有互动。",
            "risk_flags": ["source_text_missing"],
            "supporting_source_ref_ids": [501],
            "review_questions": ["是否有原文？"],
            "explanation": "只基于输入材料。",
            "status": "generated",
            "reviewed_by": None,
            "reviewed_at": None,
            "review_note": None,
            "created_at": "2026-06-13T00:00:00+00:00",
        }
        return MappingResult([row])


def new_suggestion() -> NewCandidateReviewSuggestion:
    return NewCandidateReviewSuggestion(
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        suggested_action="needs_human_review",
        priority_score=70,
        evidence_summary_draft="结构化关系显示二人可能有互动。",
        risk_flags=["source_text_missing"],
        supporting_source_ref_ids=[501],
        review_questions=["是否有原文？"],
        explanation="只基于输入材料。",
    )


def test_create_candidate_review_suggestion_inserts_generated_record() -> None:
    session = FakeSession()

    suggestion_id = create_candidate_review_suggestion(session, new_suggestion())  # type: ignore[arg-type]

    assert suggestion_id == session.suggestion_id
    assert "insert into figure_data.ai_candidate_review_suggestions" in session.statements[0]
    assert session.params[0]["candidate_kind"] == "relationship"
    assert session.params[0]["status"] == "generated"


def test_list_candidate_review_suggestions_filters_status_and_kind() -> None:
    session = FakeSession()

    rows = list_candidate_review_suggestions(
        session,  # type: ignore[arg-type]
        CandidateSuggestionListFilters(
            status="generated",
            candidate_kind=CandidateKind.RELATIONSHIP,
            limit=10,
        ),
    )

    assert rows[0].candidate_id == 960698
    assert "where" in session.statements[0].lower()
    assert session.params[0]["status"] == "generated"
    assert session.params[0]["candidate_kind"] == "relationship"


def test_get_candidate_review_suggestion_loads_record() -> None:
    session = FakeSession()

    record = get_candidate_review_suggestion(session, session.suggestion_id)  # type: ignore[arg-type]

    assert record.id == session.suggestion_id
    assert record.ai_run_id == UUID("00000000-0000-0000-0000-000000000301")
    assert record.risk_flags == ["source_text_missing"]
```

- [ ] **Step 2: Run repository tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_candidate_repository.py -q
```

Expected:

```text
FAIL because candidate_repository.py does not exist yet.
```

- [ ] **Step 3: Create repository module**

Create `src/figure_data/ai/candidate_repository.py`:

```python
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.db.enums import AICandidateSuggestionStatus
from figure_data.review.types import CandidateKind


class AICandidateSuggestionNotFoundError(ValueError):
    """Raised when an AI candidate suggestion record cannot be found."""


@dataclass(frozen=True)
class NewCandidateReviewSuggestion:
    ai_run_id: UUID
    candidate_kind: CandidateKind
    candidate_id: int
    suggested_action: str
    priority_score: int
    evidence_summary_draft: str
    risk_flags: list[str]
    supporting_source_ref_ids: list[int]
    review_questions: list[str]
    explanation: str


@dataclass(frozen=True)
class CandidateSuggestionRecord:
    id: UUID
    ai_run_id: UUID
    candidate_kind: CandidateKind
    candidate_id: int
    suggested_action: str
    priority_score: int
    evidence_summary_draft: str
    risk_flags: list[str]
    supporting_source_ref_ids: list[int]
    review_questions: list[str]
    explanation: str
    status: str
    reviewed_by: str | None
    reviewed_at: object | None
    review_note: str | None
    created_at: object


@dataclass(frozen=True)
class CandidateSuggestionListFilters:
    status: str | None = None
    candidate_kind: CandidateKind | None = None
    candidate_id: int | None = None
    limit: int = 20


def create_candidate_review_suggestion(
    session: Session,
    suggestion: NewCandidateReviewSuggestion,
) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_candidate_review_suggestions (
              id, ai_run_id, candidate_kind, candidate_id, suggested_action,
              priority_score, evidence_summary_draft, risk_flags,
              supporting_source_ref_ids, review_questions, explanation,
              status, reviewed_by, reviewed_at, review_note, created_at
            ) values (
              gen_random_uuid(), :ai_run_id, :candidate_kind, :candidate_id,
              :suggested_action, :priority_score, :evidence_summary_draft,
              cast(:risk_flags as jsonb), cast(:supporting_source_ref_ids as jsonb),
              cast(:review_questions as jsonb), :explanation, :status,
              null, null, null, :created_at
            )
            returning id
            """
        ),
        {
            "ai_run_id": suggestion.ai_run_id,
            "candidate_kind": suggestion.candidate_kind.value,
            "candidate_id": suggestion.candidate_id,
            "suggested_action": suggestion.suggested_action,
            "priority_score": suggestion.priority_score,
            "evidence_summary_draft": suggestion.evidence_summary_draft,
            "risk_flags": json.dumps(suggestion.risk_flags, ensure_ascii=False),
            "supporting_source_ref_ids": json.dumps(
                suggestion.supporting_source_ref_ids,
                ensure_ascii=False,
            ),
            "review_questions": json.dumps(suggestion.review_questions, ensure_ascii=False),
            "explanation": suggestion.explanation,
            "status": AICandidateSuggestionStatus.GENERATED.value,
            "created_at": datetime.now(UTC),
        },
    ).scalar_one()
    return value if isinstance(value, UUID) else UUID(str(value))


def list_candidate_review_suggestions(
    session: Session,
    filters: CandidateSuggestionListFilters,
) -> list[CandidateSuggestionRecord]:
    params: dict[str, Any] = {"limit": filters.limit}
    where = _build_where(filters, params)
    rows = session.execute(
        text(
            f"""
            select
              id, ai_run_id, candidate_kind, candidate_id, suggested_action,
              priority_score, evidence_summary_draft, risk_flags,
              supporting_source_ref_ids, review_questions, explanation,
              status, reviewed_by, reviewed_at, review_note, created_at
            from figure_data.ai_candidate_review_suggestions
            {where}
            order by created_at desc, id
            limit :limit
            """
        ),
        params,
    ).mappings().all()
    return [_record_from_row(cast(Mapping[str, Any], row)) for row in rows]


def get_candidate_review_suggestion(
    session: Session,
    suggestion_id: UUID,
) -> CandidateSuggestionRecord:
    row = session.execute(
        text(
            """
            select
              id, ai_run_id, candidate_kind, candidate_id, suggested_action,
              priority_score, evidence_summary_draft, risk_flags,
              supporting_source_ref_ids, review_questions, explanation,
              status, reviewed_by, reviewed_at, review_note, created_at
            from figure_data.ai_candidate_review_suggestions
            where id = :suggestion_id
            """
        ),
        {"suggestion_id": suggestion_id},
    ).mappings().one_or_none()
    if row is None:
        raise AICandidateSuggestionNotFoundError(
            f"AI candidate suggestion not found: {suggestion_id}"
        )
    return _record_from_row(cast(Mapping[str, Any], row))


def _build_where(filters: CandidateSuggestionListFilters, params: dict[str, Any]) -> str:
    clauses: list[str] = []
    if filters.status:
        clauses.append("status = :status")
        params["status"] = filters.status
    if filters.candidate_kind is not None:
        clauses.append("candidate_kind = :candidate_kind")
        params["candidate_kind"] = filters.candidate_kind.value
    if filters.candidate_id is not None:
        clauses.append("candidate_id = :candidate_id")
        params["candidate_id"] = filters.candidate_id
    if not clauses:
        return ""
    return "where " + " and ".join(clauses)


def _record_from_row(row: Mapping[str, Any]) -> CandidateSuggestionRecord:
    return CandidateSuggestionRecord(
        id=_uuid(row["id"]),
        ai_run_id=_uuid(row["ai_run_id"]),
        candidate_kind=CandidateKind(str(row["candidate_kind"])),
        candidate_id=int(row["candidate_id"]),
        suggested_action=str(row["suggested_action"]),
        priority_score=int(row["priority_score"]),
        evidence_summary_draft=str(row["evidence_summary_draft"]),
        risk_flags=_string_list(row["risk_flags"]),
        supporting_source_ref_ids=_int_list(row["supporting_source_ref_ids"]),
        review_questions=_string_list(row["review_questions"]),
        explanation=str(row["explanation"]),
        status=str(row["status"]),
        reviewed_by=row["reviewed_by"],
        reviewed_at=row["reviewed_at"],
        review_note=row["review_note"],
        created_at=row["created_at"],
    )


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _loaded_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []
    return []


def _string_list(value: object) -> list[str]:
    return [str(item) for item in _loaded_list(value)]


def _int_list(value: object) -> list[int]:
    return [int(item) for item in _loaded_list(value)]
```

- [ ] **Step 4: Run Task 4 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_candidate_repository.py -q
uv run --no-sync ruff check src/figure_data/ai/candidate_repository.py tests/ai/test_candidate_repository.py
uv run --no-sync mypy src/figure_data/ai/candidate_repository.py tests/ai/test_candidate_repository.py
```

Expected:

```text
All Task 4 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 5: Commit Task 4**

Run:

```powershell
git add src/figure_data/ai/candidate_repository.py tests/ai/test_candidate_repository.py
git commit -m "feat: 添加 AI 候选建议仓储"
```

## Task 5: Candidate Suggestion Service

**Files:**

- Create: `src/figure_data/ai/candidate_service.py`
- Create: `tests/ai/test_candidate_service.py`

- [ ] **Step 1: Add failing service tests**

Create `tests/ai/test_candidate_service.py`:

```python
from uuid import UUID

from figure_data.ai.candidate_repository import (
    CandidateSuggestionRecord,
    NewCandidateReviewSuggestion,
)
from figure_data.ai.candidate_service import save_candidate_review_suggestion_output
from figure_data.ai.schemas import CandidateReviewSuggestionOutput
from figure_data.review.types import CandidateKind


class FakeRepository:
    def __init__(self) -> None:
        self.created: list[NewCandidateReviewSuggestion] = []
        self.suggestion_id = UUID("00000000-0000-0000-0000-000000000201")

    def create(self, session: object, suggestion: NewCandidateReviewSuggestion) -> UUID:
        self.created.append(suggestion)
        return self.suggestion_id

    def get(self, session: object, suggestion_id: UUID) -> CandidateSuggestionRecord:
        created = self.created[0]
        return CandidateSuggestionRecord(
            id=suggestion_id,
            ai_run_id=created.ai_run_id,
            candidate_kind=created.candidate_kind,
            candidate_id=created.candidate_id,
            suggested_action=created.suggested_action,
            priority_score=created.priority_score,
            evidence_summary_draft=created.evidence_summary_draft,
            risk_flags=created.risk_flags,
            supporting_source_ref_ids=created.supporting_source_ref_ids,
            review_questions=created.review_questions,
            explanation=created.explanation,
            status="generated",
            reviewed_by=None,
            reviewed_at=None,
            review_note=None,
            created_at="2026-06-13T00:00:00+00:00",
        )


def test_save_candidate_review_suggestion_output_writes_ai_table_only() -> None:
    repository = FakeRepository()
    output = CandidateReviewSuggestionOutput.model_validate(
        {
            "suggested_action": "needs_human_review",
            "priority_score": 80,
            "evidence_summary_draft": "结构化关系显示二人可能有互动。",
            "risk_flags": ["source_text_missing"],
            "supporting_source_ref_ids": [501],
            "review_questions": ["是否有原文？"],
            "explanation": "只基于输入材料。",
        }
    )

    record = save_candidate_review_suggestion_output(
        session=object(),
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        output=output,
        repository=repository,
    )

    assert record.id == repository.suggestion_id
    assert repository.created[0].candidate_kind is CandidateKind.RELATIONSHIP
    assert repository.created[0].candidate_id == 960698
    assert repository.created[0].suggested_action == "needs_human_review"
```

- [ ] **Step 2: Run service tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_candidate_service.py -q
```

Expected:

```text
FAIL because candidate_service.py does not exist yet.
```

- [ ] **Step 3: Create service module**

Create `src/figure_data/ai/candidate_service.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.ai.candidate_context import build_candidate_review_prompt_input
from figure_data.ai.candidate_policy import validate_candidate_review_suggestion_policy
from figure_data.ai.candidate_repository import (
    CandidateSuggestionRecord,
    NewCandidateReviewSuggestion,
    create_candidate_review_suggestion,
    get_candidate_review_suggestion,
)
from figure_data.ai.provider import AIProvider, create_ai_provider
from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.schemas import CandidateReviewSuggestionOutput
from figure_data.ai.service import run_ai_prompt
from figure_data.config import Settings
from figure_data.review.candidate_detail import get_candidate_detail
from figure_data.review.types import CandidateKind


class CandidateSuggestionRepository(Protocol):
    def create(self, session: object, suggestion: NewCandidateReviewSuggestion) -> UUID:
        """Create a candidate suggestion."""

    def get(self, session: object, suggestion_id: UUID) -> CandidateSuggestionRecord:
        """Load a candidate suggestion."""


class PostgresCandidateSuggestionRepository:
    def create(self, session: object, suggestion: NewCandidateReviewSuggestion) -> UUID:
        return create_candidate_review_suggestion(session, suggestion)  # type: ignore[arg-type]

    def get(self, session: object, suggestion_id: UUID) -> CandidateSuggestionRecord:
        return get_candidate_review_suggestion(session, suggestion_id)  # type: ignore[arg-type]


@dataclass(frozen=True)
class CandidateReviewSuggestionResult:
    ai_run_id: UUID
    suggestion: CandidateSuggestionRecord


def generate_candidate_review_suggestion(
    *,
    session: Session,
    settings: Settings,
    kind: CandidateKind,
    candidate_id: int,
    created_by: str,
    provider: AIProvider | None = None,
    repository: CandidateSuggestionRepository | None = None,
) -> CandidateReviewSuggestionResult:
    detail = get_candidate_detail(session, kind, candidate_id)
    prompt_input = build_candidate_review_prompt_input(session, detail)
    prompt_snapshot = prompt_input.model_dump(mode="json")
    candidate_json = json.dumps(prompt_snapshot, ensure_ascii=False, sort_keys=True)
    allowed_source_ref_ids = {source_ref.source_ref_id for source_ref in detail.source_refs}
    prompt = get_prompt_definition("candidate_review_suggestion")
    model_name = _require_ai_model(settings)
    resolved_provider = provider or create_ai_provider(settings)

    run_result = run_ai_prompt(
        session=session,
        prompt=prompt,
        provider=resolved_provider,
        output_schema=CandidateReviewSuggestionOutput,
        input_variables={"candidate_json": candidate_json},
        input_snapshot=prompt_snapshot,
        model_name=model_name,
        max_output_tokens=settings.ai_max_output_tokens,
        created_by=created_by,
        output_guard=lambda output: validate_candidate_review_suggestion_policy(
            output,
            allowed_source_ref_ids=allowed_source_ref_ids,
        ),
    )
    output = run_result.output
    if not isinstance(output, CandidateReviewSuggestionOutput):
        raise TypeError("candidate review output schema returned an unexpected model")
    suggestion = save_candidate_review_suggestion_output(
        session=session,
        ai_run_id=run_result.run_id,
        candidate_kind=kind,
        candidate_id=candidate_id,
        output=output,
        repository=repository,
    )
    return CandidateReviewSuggestionResult(ai_run_id=run_result.run_id, suggestion=suggestion)


def save_candidate_review_suggestion_output(
    *,
    session: object,
    ai_run_id: UUID,
    candidate_kind: CandidateKind,
    candidate_id: int,
    output: CandidateReviewSuggestionOutput,
    repository: CandidateSuggestionRepository | None = None,
) -> CandidateSuggestionRecord:
    resolved_repository = repository or PostgresCandidateSuggestionRepository()
    suggestion_id = resolved_repository.create(
        session,
        NewCandidateReviewSuggestion(
            ai_run_id=ai_run_id,
            candidate_kind=candidate_kind,
            candidate_id=candidate_id,
            suggested_action=output.suggested_action,
            priority_score=output.priority_score,
            evidence_summary_draft=output.evidence_summary_draft,
            risk_flags=output.risk_flags,
            supporting_source_ref_ids=output.supporting_source_ref_ids,
            review_questions=output.review_questions,
            explanation=output.explanation,
        ),
    )
    return resolved_repository.get(session, suggestion_id)


def _require_ai_model(settings: Settings) -> str:
    if settings.ai_model is None:
        raise ValueError("FIGURE_AI_MODEL is required for candidate review suggestions")
    return settings.ai_model
```

- [ ] **Step 4: Run Task 5 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_candidate_service.py -q
uv run --no-sync ruff check src/figure_data/ai/candidate_service.py tests/ai/test_candidate_service.py
uv run --no-sync mypy src/figure_data/ai/candidate_service.py tests/ai/test_candidate_service.py
```

Expected:

```text
All Task 5 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 5: Commit Task 5**

Run:

```powershell
git add src/figure_data/ai/candidate_service.py tests/ai/test_candidate_service.py
git commit -m "feat: 生成并保存 AI 候选审核建议"
```

## Task 6: Candidate Suggestion CLI And Formatting

**Files:**

- Create: `src/figure_data/ai/candidate_formatting.py`
- Modify: `src/figure_data/cli.py`
- Create: `tests/ai/test_candidate_formatting.py`
- Create: `tests/ai/test_candidate_suggestion_cli.py`

- [ ] **Step 1: Add failing formatting tests**

Create `tests/ai/test_candidate_formatting.py`:

```python
from uuid import UUID

from figure_data.ai.candidate_formatting import (
    format_candidate_suggestion_detail,
    format_candidate_suggestion_summaries,
)
from figure_data.ai.candidate_repository import CandidateSuggestionRecord
from figure_data.review.types import CandidateKind


def suggestion_record() -> CandidateSuggestionRecord:
    return CandidateSuggestionRecord(
        id=UUID("00000000-0000-0000-0000-000000000201"),
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        suggested_action="needs_human_review",
        priority_score=80,
        evidence_summary_draft="结构化关系显示二人可能有互动。",
        risk_flags=["source_text_missing"],
        supporting_source_ref_ids=[501],
        review_questions=["是否有原文？"],
        explanation="只基于输入材料。",
        status="generated",
        reviewed_by=None,
        reviewed_at=None,
        review_note=None,
        created_at="2026-06-13T00:00:00+00:00",
    )


def test_format_candidate_suggestion_summaries_outputs_tsv() -> None:
    lines = format_candidate_suggestion_summaries([suggestion_record()])

    assert lines[0].startswith("id\tai_run_id\tcandidate_kind")
    assert "needs_human_review" in lines[1]
    assert "source_text_missing" in lines[1]


def test_format_candidate_suggestion_detail_outputs_trace_fields() -> None:
    lines = format_candidate_suggestion_detail(suggestion_record())

    assert "ai_candidate_suggestion\t00000000-0000-0000-0000-000000000201" in lines
    assert "ai_run\t00000000-0000-0000-0000-000000000301" in lines
    assert "candidate\trelationship\t960698" in lines
    assert "supporting_source_ref\t501" in lines
```

- [ ] **Step 2: Add failing CLI tests**

Create `tests/ai/test_candidate_suggestion_cli.py`:

```python
from uuid import UUID

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.ai.candidate_repository import CandidateSuggestionRecord
from figure_data.ai.candidate_service import CandidateReviewSuggestionResult
from figure_data.cli import app
from figure_data.review.types import CandidateKind


runner = CliRunner()


class DummySession:
    def __enter__(self) -> object:
        return object()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


class DummyFactory:
    def __call__(self) -> DummySession:
        return DummySession()


def suggestion_record() -> CandidateSuggestionRecord:
    return CandidateSuggestionRecord(
        id=UUID("00000000-0000-0000-0000-000000000201"),
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        suggested_action="needs_human_review",
        priority_score=80,
        evidence_summary_draft="结构化关系显示二人可能有互动。",
        risk_flags=["source_text_missing"],
        supporting_source_ref_ids=[501],
        review_questions=["是否有原文？"],
        explanation="只基于输入材料。",
        status="generated",
        reviewed_by=None,
        reviewed_at=None,
        review_note=None,
        created_at="2026-06-13T00:00:00+00:00",
    )


def patch_session(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummyFactory())


def test_suggest_candidate_review_command_outputs_created_suggestion(
    monkeypatch: MonkeyPatch,
) -> None:
    patch_session(monkeypatch)
    record = suggestion_record()
    monkeypatch.setattr(
        "figure_data.cli.generate_candidate_review_suggestion",
        lambda **kwargs: CandidateReviewSuggestionResult(
            ai_run_id=record.ai_run_id,
            suggestion=record,
        ),
    )

    result = runner.invoke(
        app,
        [
            "suggest-candidate-review",
            "--kind",
            "relationship",
            "--id",
            "960698",
            "--created-by",
            "tester",
        ],
    )

    assert result.exit_code == 0
    assert "ai_candidate_suggestion" in result.output
    assert "candidate\trelationship\t960698" in result.output


def test_list_ai_candidate_suggestions_command_outputs_rows(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.list_candidate_review_suggestions",
        lambda session, filters: [suggestion_record()],
    )

    result = runner.invoke(
        app,
        ["list-ai-candidate-suggestions", "--status", "generated", "--limit", "5"],
    )

    assert result.exit_code == 0
    assert "candidate_kind" in result.output
    assert "relationship" in result.output


def test_inspect_ai_candidate_suggestion_command_outputs_detail(
    monkeypatch: MonkeyPatch,
) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.get_candidate_review_suggestion",
        lambda session, suggestion_id: suggestion_record(),
    )

    result = runner.invoke(
        app,
        [
            "inspect-ai-candidate-suggestion",
            "--id",
            "00000000-0000-0000-0000-000000000201",
        ],
    )

    assert result.exit_code == 0
    assert "supporting_source_ref\t501" in result.output
```

- [ ] **Step 3: Run CLI tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_candidate_formatting.py tests/ai/test_candidate_suggestion_cli.py -q
```

Expected:

```text
FAIL because formatting and CLI commands do not exist yet.
```

- [ ] **Step 4: Create formatting module**

Create `src/figure_data/ai/candidate_formatting.py`:

```python
from figure_data.ai.candidate_repository import CandidateSuggestionRecord


def format_candidate_suggestion_summaries(
    rows: list[CandidateSuggestionRecord],
) -> list[str]:
    output = [
        "\t".join(
            [
                "id",
                "ai_run_id",
                "candidate_kind",
                "candidate_id",
                "suggested_action",
                "priority_score",
                "risk_flags",
                "status",
                "created_at",
            ]
        )
    ]
    for row in rows:
        output.append(
            "\t".join(
                [
                    str(row.id),
                    str(row.ai_run_id),
                    row.candidate_kind.value,
                    str(row.candidate_id),
                    row.suggested_action,
                    str(row.priority_score),
                    ",".join(row.risk_flags),
                    row.status,
                    _text(row.created_at),
                ]
            )
        )
    return output


def format_candidate_suggestion_detail(record: CandidateSuggestionRecord) -> list[str]:
    lines = [
        f"ai_candidate_suggestion\t{record.id}",
        f"ai_run\t{record.ai_run_id}",
        f"candidate\t{record.candidate_kind.value}\t{record.candidate_id}",
        f"suggested_action\t{record.suggested_action}",
        f"priority_score\t{record.priority_score}",
        f"status\t{record.status}",
        f"evidence_summary_draft\t{record.evidence_summary_draft}",
        f"explanation\t{record.explanation}",
        f"reviewed_by\t{_text(record.reviewed_by)}",
        f"review_note\t{_text(record.review_note)}",
        f"created_at\t{_text(record.created_at)}",
    ]
    for risk_flag in record.risk_flags:
        lines.append(f"risk_flag\t{risk_flag}")
    for source_ref_id in record.supporting_source_ref_ids:
        lines.append(f"supporting_source_ref\t{source_ref_id}")
    for question in record.review_questions:
        lines.append(f"review_question\t{question}")
    return lines


def _text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)
```

- [ ] **Step 5: Add CLI commands**

Add imports to `src/figure_data/cli.py`:

```python
from figure_data.ai.candidate_formatting import (
    format_candidate_suggestion_detail,
    format_candidate_suggestion_summaries,
)
from figure_data.ai.candidate_repository import (
    AICandidateSuggestionNotFoundError,
    CandidateSuggestionListFilters,
    get_candidate_review_suggestion,
    list_candidate_review_suggestions,
)
from figure_data.ai.candidate_service import generate_candidate_review_suggestion
from figure_data.ai.errors import (
    AIOutputPolicyViolation,
    AIOutputValidationError,
    AIProviderConfigurationError,
    AIProviderError,
)
```

Add commands near the existing candidate review commands:

```python
@app.command("suggest-candidate-review")
def suggest_candidate_review_command(
    kind: Annotated[CandidateKind, typer.Option("--kind")],
    candidate_id: Annotated[int, typer.Option("--id", min=1)],
    created_by: Annotated[str, typer.Option("--created-by")],
) -> None:
    """Generate an AI review suggestion for one candidate relationship."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with session_scope(factory) as session:
            result = generate_candidate_review_suggestion(
                session=session,
                settings=settings,
                kind=kind,
                candidate_id=candidate_id,
                created_by=created_by,
            )
    except (
        AIProviderConfigurationError,
        AIProviderError,
        AIOutputValidationError,
        AIOutputPolicyViolation,
        CandidateReviewError,
        ValueError,
    ) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_candidate_suggestion_detail(result.suggestion):
        _echo_cli_line(line)


@app.command("list-ai-candidate-suggestions")
def list_ai_candidate_suggestions_command(
    status: Annotated[str | None, typer.Option("--status")] = "generated",
    kind: Annotated[CandidateKind | None, typer.Option("--kind")] = None,
    candidate_id: Annotated[int | None, typer.Option("--candidate-id", min=1)] = None,
    limit: Annotated[int, typer.Option(min=1, max=200)] = 20,
) -> None:
    """List stored AI candidate review suggestions."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        rows = list_candidate_review_suggestions(
            session,
            CandidateSuggestionListFilters(
                status=status,
                candidate_kind=kind,
                candidate_id=candidate_id,
                limit=limit,
            ),
        )
    for line in format_candidate_suggestion_summaries(rows):
        _echo_cli_line(line)


@app.command("inspect-ai-candidate-suggestion")
def inspect_ai_candidate_suggestion_command(
    suggestion_id: Annotated[UUID, typer.Option("--id")],
) -> None:
    """Inspect one stored AI candidate review suggestion."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            record = get_candidate_review_suggestion(session, suggestion_id)
    except AICandidateSuggestionNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_candidate_suggestion_detail(record):
        _echo_cli_line(line)
```

- [ ] **Step 6: Run Task 6 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_candidate_formatting.py tests/ai/test_candidate_suggestion_cli.py -q
uv run --no-sync figure-data suggest-candidate-review --help
uv run --no-sync figure-data list-ai-candidate-suggestions --help
uv run --no-sync figure-data inspect-ai-candidate-suggestion --help
uv run --no-sync ruff check src/figure_data/ai/candidate_formatting.py src/figure_data/cli.py tests/ai/test_candidate_formatting.py tests/ai/test_candidate_suggestion_cli.py
uv run --no-sync mypy src/figure_data/ai/candidate_formatting.py src/figure_data/cli.py tests/ai/test_candidate_formatting.py tests/ai/test_candidate_suggestion_cli.py
```

Expected:

```text
All Task 6 tests pass.
All three help commands exit 0.
ruff passes.
mypy passes.
```

- [ ] **Step 7: Commit Task 6**

Run:

```powershell
git add src/figure_data/ai/candidate_formatting.py src/figure_data/cli.py tests/ai/test_candidate_formatting.py tests/ai/test_candidate_suggestion_cli.py
git commit -m "feat: 添加 AI 候选审核建议 CLI"
```

## Task 7: Documentation And Final Validation

**Files:**

- Modify: `README.md`
- Modify: `tests/test_readme_commands.py`

- [ ] **Step 1: Add failing README command tests**

Append to `tests/test_readme_commands.py`:

```python
def test_readme_documents_ai_candidate_review_suggestion_commands() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "figure-data suggest-candidate-review" in readme
    assert "figure-data list-ai-candidate-suggestions" in readme
    assert "figure-data inspect-ai-candidate-suggestion" in readme
    assert "AI 候选审核建议不会修改候选审核状态" in readme
```

- [ ] **Step 2: Run README tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/test_readme_commands.py -q
```

Expected:

```text
FAIL because README does not document candidate review suggestion commands yet.
```

- [ ] **Step 3: Update README**

Add this section to `README.md` after the Plan 1 AI foundation section:

````markdown
### AI 候选审核建议

AI 候选审核建议只帮助审核员理解候选关系、整理证据摘要草稿、识别风险点和安排人工审核优先级。AI 候选审核建议不会修改候选审核状态，不会创建 encounter，不会设置 `path_eligible=true`，也不会写入 Neo4j。

生成单个候选建议：

```powershell
uv run --no-sync figure-data suggest-candidate-review --kind relationship --id 960698 --created-by lyl
```

查看已生成建议：

```powershell
uv run --no-sync figure-data list-ai-candidate-suggestions --status generated --limit 20
uv run --no-sync figure-data inspect-ai-candidate-suggestion --id 00000000-0000-0000-0000-000000000001
uv run --no-sync figure-data inspect-ai-run --id 00000000-0000-0000-0000-000000000002
```

人工审核仍使用原有命令：

```powershell
uv run --no-sync figure-data inspect-candidate --kind relationship --id 960698
uv run --no-sync figure-data promote-encounter --kind relationship --id 960698 --reviewed-by lyl --evidence-summary "人工核对后的证据摘要"
uv run --no-sync figure-data mark-candidate-review --kind relationship --id 960698 --reviewed-by lyl --note "需要继续查原书"
uv run --no-sync figure-data reject-candidate --kind relationship --id 960698 --reviewed-by lyl --note "不能证明见面"
```
````

- [ ] **Step 4: Run migrations and automated checks**

Run:

```powershell
uv run --no-sync python -m alembic upgrade head
uv run --no-sync python -m alembic current
uv run --no-sync python -m pytest tests/ai tests/db/test_ai_candidate_suggestion_model_metadata.py tests/db/test_ai_candidate_suggestion_migration.py tests/test_readme_commands.py -q
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync figure-data suggest-candidate-review --help
uv run --no-sync figure-data list-ai-candidate-suggestions --help
uv run --no-sync figure-data inspect-ai-candidate-suggestion --help
uv run --no-sync figure-data inspect-ai-run --help
```

Expected:

```text
alembic current shows 20260613_0002 (head).
pytest passes.
ruff passes.
mypy passes.
All help commands exit 0.
```

- [ ] **Step 5: Run source safety validation**

Run:

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
```

Expected:

```text
validate-encounters passes.
validate-graph passes.
```

If Neo4j is not running in the execution environment, record that `validate-graph` was skipped because Neo4j was unavailable, then run it on the configured local Neo4j before merging the feature.

- [ ] **Step 6: Manual fake-provider smoke**

Use `.env` or shell environment values:

```powershell
$env:FIGURE_AI_ENABLED="true"
$env:FIGURE_AI_PROVIDER="fake"
$env:FIGURE_AI_MODEL="fake-history-model"
uv run --no-sync figure-data suggest-candidate-review --kind relationship --id 960698 --created-by local-smoke
uv run --no-sync figure-data list-ai-candidate-suggestions --status generated --limit 5
```

Expected:

```text
suggest-candidate-review prints ai_candidate_suggestion, ai_run, candidate, suggested_action, priority_score.
list-ai-candidate-suggestions prints the generated suggestion row.
No candidate review_status changes.
No encounter is created by the AI command.
```

- [ ] **Step 7: Commit Task 7**

Run:

```powershell
git add README.md tests/test_readme_commands.py
git commit -m "docs: 说明 AI 候选审核建议命令"
```

## Final Review Checklist

- [ ] `ai_candidate_review_suggestions` is in the `figure_data` schema.
- [ ] `ai_candidate_review_suggestions.ai_run_id` links to `ai_runs.id`.
- [ ] Candidate suggestion generation writes only AI tables.
- [ ] Candidate suggestion generation does not update `relationship_candidates`.
- [ ] Candidate suggestion generation does not update `kinship_candidates`.
- [ ] Candidate suggestion generation does not create or update `encounters`.
- [ ] Candidate suggestion generation does not write Neo4j.
- [ ] AI output references only input `source_ref_id` values.
- [ ] `priority_score` is documented as review priority, not fact confidence.
- [ ] CLI commands are thin shells.
- [ ] Provider calls go through Plan 1 provider abstraction.
- [ ] Prompt definitions stay centralized in `src/figure_data/ai/prompts.py`.
- [ ] Model output validation uses Pydantic schema and policy guard.
- [ ] Failed schema or policy validation writes failed AI run state.
- [ ] README documents that AI suggestions do not bypass manual review.

## Self-Review Notes

- Spec coverage: this plan covers Plan 2 from the stage 4 spec: candidate detail input, source refs, prompt input assembly, `ai_candidate_review_suggestions`, CLI display, and source safety boundaries.
- Scope boundary: this plan excludes chain explanation, frontend, API endpoints, batch generation, RAG, and real provider SDKs.
- Plan 1 dependency: this plan intentionally starts from the Plan 1 AI infrastructure contract. Execution should begin only after Plan 1 tests pass.
- Data safety: every AI write lands in AI-specific tables. Human review commands remain the only path to candidate status changes and encounter promotion.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-13-ai-candidate-review-suggestions.md`. Two execution options:

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
