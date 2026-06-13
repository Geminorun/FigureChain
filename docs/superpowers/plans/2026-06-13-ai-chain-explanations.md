# AI 人物链解释 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为已经审核通过的人物链生成、保存、读取并展示可追溯的 AI 解释，不改变最短路径算法和事实源。

**Architecture:** `figure_data` 负责生成链解释、保存 `ai_chain_explanations`、记录 `ai_runs`，并通过 CLI 触发生成；`figure_chain` 只提供读取已生成解释的 FastAPI endpoint，并在查链响应中返回稳定 `chain_hash`；`frontend` 只通过 Next.js route handler 读取已生成解释并作为可选附加层展示。PostgreSQL 仍是事实源，Neo4j 仍只做路径投影，AI 输出不得创建 encounter、不得写 Neo4j、不得阻塞 `/api/v1/chains/shortest`。

**Tech Stack:** Python 3.12, Typer, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL JSONB, FastAPI, Next.js, React, TypeScript, pytest, ruff, mypy, Vitest, Playwright.

---

## Scope Check

本计划实现阶段 4 的 Plan 3：人物链解释。

本计划实现：

- `figure_data.ai_chain_explanations` 数据表和 migration。
- `chain_explanation` prompt 与 Pydantic 输出 schema。
- 链解释 `chain_hash` 计算。
- 从已审核路径和 encounter detail 组装 AI 输入。
- 链解释输出策略校验：只允许引用输入中的 `encounter_id` 和 `source_ref_id`。
- `figure-data generate-chain-explanation` CLI，使用 fake provider 可本地 smoke。
- `figure-data inspect-chain-explanation --hash <chain_hash>` CLI。
- FastAPI 只读 endpoint：
  - `GET /api/v1/ai/chains/explanations/{chain_hash}`
  - `GET /api/v1/ai/runs/{run_id}`
- `ShortestChainResponse.chain_hash`，供前端读取已生成解释。
- Next.js route handler、hook、类型和查链结果中的可选 AI 解释面板。
- README 中链解释生成、读取和验证说明。

本计划不实现：

- 在 `/api/v1/chains/shortest` 中调用模型。
- 通过 FastAPI 触发 AI 生成。
- 无路径探索建议。
- RAG、embedding、pgvector 或文本召回。
- 真实 provider SDK。
- 批量全库生成链解释。
- 让 AI 修改 candidates、encounters、encounter_evidence 或 Neo4j。
- 审核后台 UI。

## Prerequisite Contract

执行本计划前必须完成并修复 Plan 1/Plan 2 的 AI 基础设施。

必须满足：

```powershell
uv run --no-sync python -m pytest tests/ai tests/db/test_ai_candidate_suggestion_model_metadata.py tests/db/test_ai_candidate_suggestion_migration.py -q
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync python -m alembic current
```

预期：

```text
AI foundation and candidate suggestion tests pass.
alembic current shows 20260613_0002 (head).
```

Plan 1/2 还必须已经修复以下失败留痕边界：

- provider 抛出异常时，`ai_runs.status` 必须写为 `failed`。
- schema、policy 或 provider 失败时，CLI 不能因为事务 rollback 丢失 failed AI run。

若上述边界没有测试覆盖，先补充并修复，再执行本计划。

## File Structure

新增：

```text
src/figure_data/ai/chain_context.py
src/figure_data/ai/chain_formatting.py
src/figure_data/ai/chain_hash.py
src/figure_data/ai/chain_policy.py
src/figure_data/ai/chain_repository.py
src/figure_data/ai/chain_service.py
src/figure_data/db/models/ai_chain.py
alembic/versions/20260613_0003_create_ai_chain_explanations.py

src/figure_chain/routers/ai.py
src/figure_chain/services/ai.py

frontend/app/api/figure-chain/ai/chains/explanations/[chainHash]/route.ts
frontend/app/api/figure-chain/ai/runs/[runId]/route.ts
frontend/src/components/chain-explanation-panel.tsx
frontend/src/hooks/use-chain-explanation.ts

tests/ai/test_chain_context.py
tests/ai/test_chain_formatting.py
tests/ai/test_chain_hash.py
tests/ai/test_chain_policy.py
tests/ai/test_chain_prompt_schema.py
tests/ai/test_chain_repository.py
tests/ai/test_chain_service.py
tests/ai/test_chain_explanation_cli.py
tests/db/test_ai_chain_explanation_model_metadata.py
tests/db/test_ai_chain_explanation_migration.py
tests/figure_chain/test_ai_api.py
frontend/tests/unit/chain-explanation-panel.test.tsx
frontend/tests/unit/use-chain-explanation.test.tsx
```

修改：

```text
src/figure_data/ai/prompts.py
src/figure_data/ai/provider.py
src/figure_data/ai/schemas.py
src/figure_data/ai/service.py
src/figure_data/cli.py
src/figure_data/db/enums.py
src/figure_data/db/models/__init__.py
src/figure_chain/dependencies.py
src/figure_chain/errors.py
src/figure_chain/routers/__init__.py
src/figure_chain/schemas.py
src/figure_chain/services/chains.py
tests/figure_chain/test_chains_api.py
frontend/src/components/chain-result.tsx
frontend/src/lib/figure-chain-types.ts
frontend/src/test/fixtures.ts
frontend/tests/unit/api-client.test.ts
frontend/tests/unit/chain-result.test.tsx
tests/test_readme_commands.py
README.md
```

职责边界：

- `figure_data.ai.chain_*`：生成、保存和格式化链解释，允许调用 provider。
- `figure_chain.services.ai`：只读已生成解释和 AI run，不调用 provider。
- `figure_chain.services.chains`：只计算 `chain_hash`，不生成解释。
- Next.js route handlers：只代理 FastAPI，不复制业务逻辑。
- React 组件：只展示已生成解释；解释不可用时原路径照常显示。

## Task 1: AI Chain Explanation Model And Migration

**Files:**

- Modify: `src/figure_data/db/enums.py`
- Create: `src/figure_data/db/models/ai_chain.py`
- Modify: `src/figure_data/db/models/__init__.py`
- Create: `alembic/versions/20260613_0003_create_ai_chain_explanations.py`
- Create: `tests/db/test_ai_chain_explanation_model_metadata.py`
- Create: `tests/db/test_ai_chain_explanation_migration.py`

- [ ] **Step 1: Add failing metadata tests**

Create `tests/db/test_ai_chain_explanation_model_metadata.py`:

```python
from sqlalchemy import CheckConstraint, UniqueConstraint

from figure_data.db.base import Base
from figure_data.db.enums import AIChainExplanationStatus, AIErrorCode
from figure_data.db.models import ai_chain


def test_ai_chain_explanation_enums_define_values() -> None:
    assert AIChainExplanationStatus.GENERATED.value == "generated"
    assert AIChainExplanationStatus.ARCHIVED.value == "archived"
    assert AIErrorCode.INVALID_CHAIN_CONTEXT.value == "invalid_chain_context"


def test_ai_chain_explanation_model_uses_figure_data_schema() -> None:
    assert ai_chain
    assert Base.metadata.tables["figure_data.ai_chain_explanations"].schema == "figure_data"


def test_ai_chain_explanation_model_links_ai_run() -> None:
    table = Base.metadata.tables["figure_data.ai_chain_explanations"]
    foreign_keys = {foreign_key.target_fullname for foreign_key in table.c.ai_run_id.foreign_keys}

    assert "figure_data.ai_runs.id" in foreign_keys


def test_ai_chain_explanation_model_declares_constraints() -> None:
    table = Base.metadata.tables["figure_data.ai_chain_explanations"]
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

    assert "ck_ai_chain_explanations_status" in check_names
    assert "ck_ai_chain_explanations_max_depth" in check_names
    assert ("chain_hash",) in unique_columns


def test_ai_chain_explanation_model_declares_indexes() -> None:
    table = Base.metadata.tables["figure_data.ai_chain_explanations"]
    index_names = {index.name for index in table.indexes}

    assert {
        "ix_figure_data_ai_chain_explanations_source_target",
        "ix_figure_data_ai_chain_explanations_ai_run_id",
        "ix_figure_data_ai_chain_explanations_status",
        "ix_figure_data_ai_chain_explanations_created_at",
    }.issubset(index_names)
```

- [ ] **Step 2: Add failing migration tests**

Create `tests/db/test_ai_chain_explanation_migration.py`:

```python
from pathlib import Path


MIGRATION_PATH = Path("alembic/versions/20260613_0003_create_ai_chain_explanations.py")


def test_ai_chain_explanation_migration_depends_on_candidate_suggestions() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision: str = "20260613_0003"' in migration_source
    assert 'down_revision: str | None = "20260613_0002"' in migration_source


def test_ai_chain_explanation_migration_uses_explicit_operations() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Base.metadata.create_all" not in migration_source
    assert "Base.metadata.drop_all" not in migration_source
    assert "DROP SCHEMA" not in migration_source
    assert 'op.create_table("ai_chain_explanations"' in migration_source
    assert 'op.drop_table("ai_chain_explanations"' in migration_source


def test_ai_chain_explanation_migration_declares_constraints() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "fk_ai_chain_explanations_ai_run_id_ai_runs" in migration_source
    assert "uq_ai_chain_explanations_chain_hash" in migration_source
    assert "ck_ai_chain_explanations_status" in migration_source
    assert "ck_ai_chain_explanations_max_depth" in migration_source
```

- [ ] **Step 3: Run model and migration tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/db/test_ai_chain_explanation_model_metadata.py tests/db/test_ai_chain_explanation_migration.py -q
```

Expected:

```text
FAIL because chain explanation enums, model, and migration do not exist yet.
```

- [ ] **Step 4: Add enums**

Append to `src/figure_data/db/enums.py`:

```python


class AIChainExplanationStatus(StrEnum):
    GENERATED = "generated"
    ARCHIVED = "archived"
```

Add this member to `AIErrorCode`:

```python
INVALID_CHAIN_CONTEXT = "invalid_chain_context"
```

- [ ] **Step 5: Create ORM model**

Create `src/figure_data/db/models/ai_chain.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from figure_data.db.base import Base


class AIChainExplanation(Base):
    __tablename__ = "ai_chain_explanations"
    __table_args__ = (
        CheckConstraint(
            "status in ('generated', 'archived')",
            name=conv("ck_ai_chain_explanations_status"),
        ),
        CheckConstraint(
            "max_depth >= 1 and max_depth <= 30",
            name=conv("ck_ai_chain_explanations_max_depth"),
        ),
        UniqueConstraint("chain_hash", name="uq_ai_chain_explanations_chain_hash"),
        Index(
            "ix_figure_data_ai_chain_explanations_source_target",
            "source_person_id",
            "target_person_id",
        ),
        Index("ix_figure_data_ai_chain_explanations_ai_run_id", "ai_run_id"),
        Index("ix_figure_data_ai_chain_explanations_status", "status"),
        Index("ix_figure_data_ai_chain_explanations_created_at", "created_at"),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    ai_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("figure_data.ai_runs.id"),
        nullable=False,
    )
    chain_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_person_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    target_person_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    max_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    encounter_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    edge_explanations: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    source_ref_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

If `ruff` flags the SQLAlchemy import line length, split it into a parenthesized import block.

- [ ] **Step 6: Export model module**

Modify `src/figure_data/db/models/__init__.py`:

```python
from figure_data.db.models import (
    ai,
    ai_candidate,
    ai_chain,
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
    "ai_chain",
    "encounter",
    "identity",
    "import_batch",
    "office",
    "person",
    "relationship",
    "source",
]
```

- [ ] **Step 7: Create migration**

Create `alembic/versions/20260613_0003_create_ai_chain_explanations.py`:

```python
"""create AI chain explanations table

Revision ID: 20260613_0003
Revises: 20260613_0002
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260613_0003"
down_revision: str | None = "20260613_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "ai_chain_explanations",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("ai_run_id", _uuid(), nullable=False),
        sa.Column("chain_hash", sa.Text(), nullable=False),
        sa.Column("source_person_id", _uuid(), nullable=False),
        sa.Column("target_person_id", _uuid(), nullable=False),
        sa.Column("max_depth", sa.Integer(), nullable=False),
        sa.Column("encounter_ids", postgresql.JSONB(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("edge_explanations", postgresql.JSONB(), nullable=False),
        sa.Column("source_ref_ids", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('generated', 'archived')",
            name="ck_ai_chain_explanations_status",
        ),
        sa.CheckConstraint(
            "max_depth >= 1 and max_depth <= 30",
            name="ck_ai_chain_explanations_max_depth",
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["figure_data.ai_runs.id"],
            name="fk_ai_chain_explanations_ai_run_id_ai_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_chain_explanations"),
        sa.UniqueConstraint("chain_hash", name="uq_ai_chain_explanations_chain_hash"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_chain_explanations_source_target",
        "ai_chain_explanations",
        ["source_person_id", "target_person_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_chain_explanations_ai_run_id",
        "ai_chain_explanations",
        ["ai_run_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_chain_explanations_status",
        "ai_chain_explanations",
        ["status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_chain_explanations_created_at",
        "ai_chain_explanations",
        ["created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_figure_data_ai_chain_explanations_created_at",
        table_name="ai_chain_explanations",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_chain_explanations_status",
        table_name="ai_chain_explanations",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_chain_explanations_ai_run_id",
        table_name="ai_chain_explanations",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_chain_explanations_source_target",
        table_name="ai_chain_explanations",
        schema=SCHEMA,
    )
    op.drop_table("ai_chain_explanations", schema=SCHEMA)
```

- [ ] **Step 8: Run Task 1 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/db/test_ai_chain_explanation_model_metadata.py tests/db/test_ai_chain_explanation_migration.py -q
uv run --no-sync ruff check src/figure_data/db tests/db/test_ai_chain_explanation_model_metadata.py tests/db/test_ai_chain_explanation_migration.py
uv run --no-sync mypy src/figure_data/db tests/db/test_ai_chain_explanation_model_metadata.py tests/db/test_ai_chain_explanation_migration.py
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
git add src/figure_data/db/enums.py src/figure_data/db/models/__init__.py src/figure_data/db/models/ai_chain.py alembic/versions/20260613_0003_create_ai_chain_explanations.py tests/db/test_ai_chain_explanation_model_metadata.py tests/db/test_ai_chain_explanation_migration.py
git commit -m "feat: 添加 AI 人物链解释表"
```

## Task 2: Chain Prompt, Schema, Hash, And Policy

**Files:**

- Modify: `src/figure_data/ai/prompts.py`
- Modify: `src/figure_data/ai/provider.py`
- Modify: `src/figure_data/ai/schemas.py`
- Create: `src/figure_data/ai/chain_hash.py`
- Create: `src/figure_data/ai/chain_policy.py`
- Create: `tests/ai/test_chain_prompt_schema.py`
- Create: `tests/ai/test_chain_hash.py`
- Create: `tests/ai/test_chain_policy.py`

- [ ] **Step 1: Add failing prompt and schema tests**

Create `tests/ai/test_chain_prompt_schema.py`:

```python
from pydantic import ValidationError
from pytest import raises

from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.schemas import ChainExplanationOutput


def test_chain_explanation_prompt_is_registered() -> None:
    prompt = get_prompt_definition("chain_explanation")

    assert prompt.prompt_key == "chain_explanation"
    assert prompt.purpose == "chain_explanation"
    assert prompt.output_schema_name == "chain_explanation_output"
    assert prompt.output_schema_version == "1"
    assert "{chain_json}" in prompt.user_prompt_template
    assert "不得编造史料" in prompt.system_prompt


def test_chain_explanation_output_accepts_valid_payload() -> None:
    output = ChainExplanationOutput.model_validate(
        {
            "summary": "这条人物链由一条已审核见面边组成。",
            "edge_explanations": [
                {
                    "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                    "explanation": "许几曾谒见韩琦，证据来自已审核 encounter。",
                    "evidence_basis": "encounter_evidence",
                    "source_ref_ids": [3853784],
                }
            ],
            "source_notes": ["source_ref 3853784 提供页码和 notes。"],
            "limitations": ["AI 解释只是对已审核证据的重述。"],
            "display_language": "zh-Hans",
        }
    )

    assert output.display_language == "zh-Hans"
    assert output.edge_explanations[0].source_ref_ids == [3853784]


def test_chain_explanation_output_rejects_empty_edges() -> None:
    with raises(ValidationError):
        ChainExplanationOutput.model_validate(
            {
                "summary": "缺少边解释。",
                "edge_explanations": [],
                "source_notes": [],
                "limitations": [],
                "display_language": "zh-Hans",
            }
        )
```

- [ ] **Step 2: Add failing hash tests**

Create `tests/ai/test_chain_hash.py`:

```python
from figure_data.ai.chain_hash import compute_chain_hash


def test_compute_chain_hash_is_stable_for_same_payload() -> None:
    first = compute_chain_hash(
        source_person_id="source",
        target_person_id="target",
        max_depth=12,
        encounter_ids=["e1", "e2"],
        prompt_key="chain_explanation",
        prompt_version="2026-06-13.1",
        output_schema_version="1",
        language="zh-Hans",
    )
    second = compute_chain_hash(
        source_person_id="source",
        target_person_id="target",
        max_depth=12,
        encounter_ids=["e1", "e2"],
        prompt_key="chain_explanation",
        prompt_version="2026-06-13.1",
        output_schema_version="1",
        language="zh-Hans",
    )

    assert first == second
    assert len(first) == 64


def test_compute_chain_hash_changes_when_edge_order_changes() -> None:
    forward = compute_chain_hash(
        source_person_id="source",
        target_person_id="target",
        max_depth=12,
        encounter_ids=["e1", "e2"],
        prompt_key="chain_explanation",
        prompt_version="2026-06-13.1",
        output_schema_version="1",
        language="zh-Hans",
    )
    reversed_edges = compute_chain_hash(
        source_person_id="source",
        target_person_id="target",
        max_depth=12,
        encounter_ids=["e2", "e1"],
        prompt_key="chain_explanation",
        prompt_version="2026-06-13.1",
        output_schema_version="1",
        language="zh-Hans",
    )

    assert forward != reversed_edges
```

- [ ] **Step 3: Add failing policy tests**

Create `tests/ai/test_chain_policy.py`:

```python
from pytest import raises

from figure_data.ai.chain_policy import validate_chain_explanation_policy
from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.schemas import ChainExplanationOutput


def chain_output(**overrides: object) -> ChainExplanationOutput:
    payload = {
        "summary": "这条人物链由一条已审核见面边组成。",
        "edge_explanations": [
            {
                "encounter_id": "e1",
                "explanation": "解释 e1。",
                "evidence_basis": "encounter_evidence",
                "source_ref_ids": [101],
            }
        ],
        "source_notes": ["source_ref 101"],
        "limitations": ["AI 解释不是新证据。"],
        "display_language": "zh-Hans",
    }
    payload.update(overrides)
    return ChainExplanationOutput.model_validate(payload)


def test_chain_policy_accepts_known_references() -> None:
    validate_chain_explanation_policy(
        chain_output(),
        allowed_encounter_ids={"e1"},
        allowed_source_ref_ids={101},
    )


def test_chain_policy_rejects_unknown_encounter_id() -> None:
    with raises(AIOutputPolicyViolation, match="unknown encounter_id"):
        validate_chain_explanation_policy(
            chain_output(
                edge_explanations=[
                    {
                        "encounter_id": "missing",
                        "explanation": "解释不存在的边。",
                        "evidence_basis": "encounter_evidence",
                        "source_ref_ids": [101],
                    }
                ]
            ),
            allowed_encounter_ids={"e1"},
            allowed_source_ref_ids={101},
        )


def test_chain_policy_rejects_unknown_source_ref_id() -> None:
    with raises(AIOutputPolicyViolation, match="unknown source_ref_id"):
        validate_chain_explanation_policy(
            chain_output(),
            allowed_encounter_ids={"e1"},
            allowed_source_ref_ids={999},
        )
```

- [ ] **Step 4: Run Task 2 tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_chain_prompt_schema.py tests/ai/test_chain_hash.py tests/ai/test_chain_policy.py -q
```

Expected:

```text
FAIL because chain prompt, schema, hash, and policy modules do not exist yet.
```

- [ ] **Step 5: Add schema**

Append to `src/figure_data/ai/schemas.py`:

```python


class ChainEdgeExplanationOutput(BaseModel):
    encounter_id: str = Field(min_length=1)
    explanation: str = Field(min_length=1, max_length=2000)
    evidence_basis: Literal["encounter_evidence", "source_ref", "structured_candidate"]
    source_ref_ids: list[int] = Field(default_factory=list, max_length=50)


class ChainExplanationOutput(BaseModel):
    summary: str = Field(min_length=1, max_length=3000)
    edge_explanations: list[ChainEdgeExplanationOutput] = Field(min_length=1, max_length=30)
    source_notes: list[str] = Field(default_factory=list, max_length=50)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    display_language: Literal["zh-Hans", "zh-Hant", "en"] = "zh-Hans"
```

- [ ] **Step 6: Add prompt**

Modify `src/figure_data/ai/prompts.py`:

```python
CHAIN_EXPLANATION_PROMPT = PromptDefinition(
    prompt_key="chain_explanation",
    prompt_version="2026-06-13.1",
    purpose="chain_explanation",
    system_prompt=(
        "你是 FigureChain 的人物链解释助手。"
        "你只能解释输入 JSON 中已经审核通过的 path encounters。"
        "不得编造史料、页码、人物关系或见面场景。"
        "不得把 AI 解释称为新证据。"
        "每条 edge_explanation 必须引用输入中的 encounter_id。"
        "source_ref_ids 只能来自输入 JSON。"
        "如果缺少原文，只能说明来源为结构化候选关系或审核摘要。"
        "只返回 JSON object。"
    ),
    user_prompt_template=(
        "请解释以下已审核人物链。"
        "输入 JSON：\n{chain_json}\n"
        "输出字段必须为 summary, edge_explanations, source_notes, limitations, display_language。"
    ),
    output_schema_name="chain_explanation_output",
    output_schema_version="1",
)

PROMPT_DEFINITIONS = (
    AI_FOUNDATION_DIAGNOSTIC_PROMPT,
    CANDIDATE_REVIEW_SUGGESTION_PROMPT,
    CHAIN_EXPLANATION_PROMPT,
)
```

- [ ] **Step 7: Add hash module**

Create `src/figure_data/ai/chain_hash.py`:

```python
from __future__ import annotations

import hashlib
import json


def compute_chain_hash(
    *,
    source_person_id: str,
    target_person_id: str,
    max_depth: int,
    encounter_ids: list[str],
    prompt_key: str,
    prompt_version: str,
    output_schema_version: str,
    language: str,
) -> str:
    payload = {
        "source_person_id": source_person_id,
        "target_person_id": target_person_id,
        "max_depth": max_depth,
        "encounter_ids": encounter_ids,
        "prompt_key": prompt_key,
        "prompt_version": prompt_version,
        "output_schema_version": output_schema_version,
        "language": language,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

- [ ] **Step 8: Add policy module**

Create `src/figure_data/ai/chain_policy.py`:

```python
from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.schemas import ChainExplanationOutput


def validate_chain_explanation_policy(
    output: ChainExplanationOutput,
    *,
    allowed_encounter_ids: set[str],
    allowed_source_ref_ids: set[int],
) -> None:
    seen_encounter_ids: set[str] = set()
    for edge in output.edge_explanations:
        if edge.encounter_id not in allowed_encounter_ids:
            raise AIOutputPolicyViolation(f"unknown encounter_id in AI output: {edge.encounter_id}")
        seen_encounter_ids.add(edge.encounter_id)
        unknown_source_ref_ids = [
            source_ref_id
            for source_ref_id in edge.source_ref_ids
            if source_ref_id not in allowed_source_ref_ids
        ]
        if unknown_source_ref_ids:
            joined = ",".join(str(source_ref_id) for source_ref_id in unknown_source_ref_ids)
            raise AIOutputPolicyViolation(f"unknown source_ref_id in AI output: {joined}")
    missing_edges = sorted(allowed_encounter_ids - seen_encounter_ids)
    if missing_edges:
        raise AIOutputPolicyViolation(
            f"missing edge explanation for encounter_id: {','.join(missing_edges)}"
        )
    if not output.summary.strip():
        raise AIOutputPolicyViolation("summary is required")
```

- [ ] **Step 9: Extend fake provider for chain explanation**

Modify `src/figure_data/ai/provider.py` so `_fake_response_for_request` detects chain explanation prompts:

```python
def _fake_response_for_request(request: AIProviderRequest) -> str:
    if "edge_explanations" in request.user_prompt and "encounters" in request.user_prompt:
        return _fake_chain_explanation_response(request)
    if "suggested_action" in request.user_prompt and "source_refs" in request.user_prompt:
        return _fake_candidate_suggestion_response(request)
    return '{"message":"ready","echo_id":"diagnostic","warnings":[]}'
```

Add:

```python
def _fake_chain_explanation_response(request: AIProviderRequest) -> str:
    payload = _extract_first_json_object(request.user_prompt)
    encounters = payload.get("encounters", [])
    if not isinstance(encounters, list):
        encounters = []
    edge_explanations = []
    source_ref_ids: list[int] = []
    for encounter in encounters:
        if not isinstance(encounter, dict):
            continue
        encounter_id = str(encounter.get("encounter_id", ""))
        refs = encounter.get("source_refs", [])
        edge_source_ref_ids = [
            ref["source_ref_id"]
            for ref in refs
            if isinstance(ref, dict) and isinstance(ref.get("source_ref_id"), int)
        ]
        source_ref_ids.extend(edge_source_ref_ids)
        edge_explanations.append(
            {
                "encounter_id": encounter_id,
                "explanation": "该 fake 解释基于已审核 encounter 和 evidence 生成。",
                "evidence_basis": "encounter_evidence",
                "source_ref_ids": edge_source_ref_ids[:3],
            }
        )
    return json.dumps(
        {
            "summary": "这条人物链由已审核的 encounter 连接，AI 仅重述已给出的证据。",
            "edge_explanations": edge_explanations,
            "source_notes": [f"引用 source_ref: {source_ref_id}" for source_ref_id in source_ref_ids],
            "limitations": ["AI 解释不是新的历史证据。"],
            "display_language": "zh-Hans",
        },
        ensure_ascii=False,
    )
```

- [ ] **Step 10: Run Task 2 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_chain_prompt_schema.py tests/ai/test_chain_hash.py tests/ai/test_chain_policy.py tests/ai/test_provider.py -q
uv run --no-sync ruff check src/figure_data/ai tests/ai/test_chain_prompt_schema.py tests/ai/test_chain_hash.py tests/ai/test_chain_policy.py
uv run --no-sync mypy src/figure_data/ai tests/ai/test_chain_prompt_schema.py tests/ai/test_chain_hash.py tests/ai/test_chain_policy.py
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
git add src/figure_data/ai/prompts.py src/figure_data/ai/provider.py src/figure_data/ai/schemas.py src/figure_data/ai/chain_hash.py src/figure_data/ai/chain_policy.py tests/ai/test_chain_prompt_schema.py tests/ai/test_chain_hash.py tests/ai/test_chain_policy.py tests/ai/test_provider.py
git commit -m "feat: 添加 AI 人物链解释 prompt 与策略校验"
```

## Task 3: Chain Context, Repository, Service, And CLI

**Files:**

- Create: `src/figure_data/ai/chain_context.py`
- Create: `src/figure_data/ai/chain_repository.py`
- Create: `src/figure_data/ai/chain_service.py`
- Create: `src/figure_data/ai/chain_formatting.py`
- Modify: `src/figure_data/ai/service.py`
- Modify: `src/figure_data/cli.py`
- Create: `tests/ai/test_chain_context.py`
- Create: `tests/ai/test_chain_repository.py`
- Create: `tests/ai/test_chain_service.py`
- Create: `tests/ai/test_chain_formatting.py`
- Create: `tests/ai/test_chain_explanation_cli.py`

- [ ] **Step 1: Add failing context tests**

Create `tests/ai/test_chain_context.py`:

```python
from datetime import UTC, datetime
from uuid import UUID

from figure_data.ai.chain_context import build_chain_explanation_prompt_input
from figure_data.encounters.types import EncounterDetail, EncounterEvidenceDetail
from figure_data.graph.types import ChainEdge, ChainLookupResult, ChainPath, ChainPerson
from figure_data.review.types import CandidatePerson, CandidateSourceRef


ENCOUNTER_ID = "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"


def encounter_detail() -> EncounterDetail:
    now = datetime(2026, 6, 13, tzinfo=UTC)
    return EncounterDetail(
        encounter_id=UUID(ENCOUNTER_ID),
        status="active",
        encounter_kind="direct_interaction",
        certainty_level="high",
        path_eligible=True,
        source_work_id=7596,
        pages="11905",
        evidence_summary="许几谒韩琦于魏",
        review_note=None,
        reviewed_by="lyl",
        reviewed_at=now,
        person_a=CandidatePerson(
            person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
            cbdb_id=780,
            primary_name_zh_hant="許幾",
            primary_name_zh_hans="许几",
            primary_name_romanized="Xu Ji",
            birth_year=1054,
            death_year=1115,
            external_ids=["780"],
        ),
        person_b=CandidatePerson(
            person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
            cbdb_id=630,
            primary_name_zh_hant="韓琦",
            primary_name_zh_hans="韩琦",
            primary_name_romanized="Han Qi",
            birth_year=1008,
            death_year=1075,
            external_ids=["630"],
        ),
        evidence=[
            EncounterEvidenceDetail(
                evidence_id=12,
                candidate_table="relationship_candidates",
                candidate_id=960664,
                source_ref_id=3853784,
                source_work_id=7596,
                pages="11905",
                evidence_kind="candidate",
                evidence_summary="许几谒韩琦于魏",
                created_at=now,
            )
        ],
        source_refs=[
            CandidateSourceRef(
                source_ref_id=3853784,
                source_work_id=7596,
                title_zh=None,
                title_en=None,
                pages="11905",
                notes="以诸生谒韩琦于魏",
            )
        ],
    )


def chain_result() -> ChainLookupResult:
    return ChainLookupResult(
        source_person_id="38966b03-8aa7-5143-8021-2d266889b6c5",
        target_person_id="46cfdf66-08c4-5876-964b-4a95d098afe9",
        max_depth=12,
        path=ChainPath(
            people=(
                ChainPerson(
                    person_id="38966b03-8aa7-5143-8021-2d266889b6c5",
                    display_name="許幾",
                    birth_year=1054,
                    death_year=1115,
                    cbdb_external_id="780",
                ),
                ChainPerson(
                    person_id="46cfdf66-08c4-5876-964b-4a95d098afe9",
                    display_name="韓琦",
                    birth_year=1008,
                    death_year=1075,
                    cbdb_external_id="630",
                ),
            ),
            edges=(
                ChainEdge(
                    encounter_id=ENCOUNTER_ID,
                    encounter_kind="direct_interaction",
                    certainty_level="high",
                    pages="11905",
                    evidence_summary="许几谒韩琦于魏",
                ),
            ),
        ),
    )


def test_build_chain_explanation_prompt_input_uses_only_reviewed_context() -> None:
    prompt_input = build_chain_explanation_prompt_input(
        result=chain_result(),
        encounter_details={ENCOUNTER_ID: encounter_detail()},
        language="zh-Hans",
    )
    payload = prompt_input.model_dump(mode="json")

    assert payload["source_person_id"] == "38966b03-8aa7-5143-8021-2d266889b6c5"
    assert payload["target_person_id"] == "46cfdf66-08c4-5876-964b-4a95d098afe9"
    assert payload["people"][0]["display_name"] == "許幾"
    assert payload["encounters"][0]["encounter_id"] == ENCOUNTER_ID
    assert payload["encounters"][0]["source_refs"][0]["source_ref_id"] == 3853784
```

- [ ] **Step 2: Add failing repository, service, formatting, and CLI tests**

Create `tests/ai/test_chain_repository.py`:

```python
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from figure_data.ai.chain_repository import (
    NewChainExplanation,
    create_chain_explanation,
    get_chain_explanation_by_hash,
)


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

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []
        self.explanation_id = UUID("00000000-0000-0000-0000-000000000401")

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> object:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(params or {})
        if "insert into figure_data.ai_chain_explanations" in sql:
            return ScalarResult(self.explanation_id)
        row = {
            "id": self.explanation_id,
            "ai_run_id": UUID("00000000-0000-0000-0000-000000000301"),
            "chain_hash": "known-chain-hash",
            "source_person_id": UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
            "target_person_id": UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
            "max_depth": 12,
            "encounter_ids": ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
            "language": "zh-Hans",
            "summary": "这条人物链由一条已审核见面边组成。",
            "edge_explanations": [
                {
                    "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                    "explanation": "许几曾谒见韩琦。",
                    "evidence_basis": "encounter_evidence",
                    "source_ref_ids": [3853784],
                }
            ],
            "source_ref_ids": [3853784],
            "status": "generated",
            "created_at": "2026-06-13T00:00:00+00:00",
        }
        return MappingResult([row])


def new_explanation() -> NewChainExplanation:
    return NewChainExplanation(
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        chain_hash="known-chain-hash",
        source_person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
        target_person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
        max_depth=12,
        encounter_ids=["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
        language="zh-Hans",
        summary="这条人物链由一条已审核见面边组成。",
        edge_explanations=[
            {
                "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                "explanation": "许几曾谒见韩琦。",
                "evidence_basis": "encounter_evidence",
                "source_ref_ids": [3853784],
            }
        ],
        source_ref_ids=[3853784],
    )


def test_create_chain_explanation_inserts_generated_record() -> None:
    session = FakeSession()

    explanation_id = create_chain_explanation(
        session,  # type: ignore[arg-type]
        new_explanation(),
    )

    assert explanation_id == session.explanation_id
    assert "insert into figure_data.ai_chain_explanations" in session.statements[0]
    assert session.params[0]["chain_hash"] == "known-chain-hash"
    assert session.params[0]["status"] == "generated"


def test_get_chain_explanation_by_hash_loads_trace_fields() -> None:
    session = FakeSession()

    record = get_chain_explanation_by_hash(
        session,  # type: ignore[arg-type]
        "known-chain-hash",
    )

    assert record.id == session.explanation_id
    assert record.ai_run_id == UUID("00000000-0000-0000-0000-000000000301")
    assert record.chain_hash == "known-chain-hash"
    assert record.summary == "这条人物链由一条已审核见面边组成。"
    assert record.edge_explanations[0]["encounter_id"] == (
        "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"
    )
    assert record.source_ref_ids == [3853784]
```

Create `tests/ai/test_chain_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.ai.chain_context import InvalidChainContextError
from figure_data.ai.chain_repository import ChainExplanationRecord, NewChainExplanation
from figure_data.ai.chain_service import (
    ChainExplanationGenerationResult,
    generate_chain_explanation_for_result,
    save_chain_explanation_output,
)
from figure_data.ai.schemas import ChainExplanationOutput
from figure_data.ai.types import AIProviderRequest, AIProviderResponse
from figure_data.encounters.types import EncounterDetail, EncounterEvidenceDetail
from figure_data.graph.types import ChainEdge, ChainLookupResult, ChainPath, ChainPerson
from figure_data.review.types import CandidatePerson, CandidateSourceRef


class FakeProvider:
    provider_name = "fake"

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        return AIProviderResponse(
            raw_text="{}",
            provider=self.provider_name,
            model_name=request.model_name,
        )


@dataclass
class FakeChainRepository:
    created: list[NewChainExplanation] = field(default_factory=list)
    explanation_id: UUID = UUID("00000000-0000-0000-0000-000000000401")

    def create(self, session: object, explanation: NewChainExplanation) -> UUID:
        self.created.append(explanation)
        return self.explanation_id

    def get_by_hash(self, session: object, chain_hash: str) -> ChainExplanationRecord:
        created = self.created[0]
        return ChainExplanationRecord(
            id=self.explanation_id,
            ai_run_id=created.ai_run_id,
            chain_hash=chain_hash,
            source_person_id=created.source_person_id,
            target_person_id=created.target_person_id,
            max_depth=created.max_depth,
            encounter_ids=created.encounter_ids,
            language=created.language,
            summary=created.summary,
            edge_explanations=created.edge_explanations,
            source_ref_ids=created.source_ref_ids,
            status="generated",
            created_at="2026-06-13T00:00:00+00:00",
        )


@dataclass
class FakeRunRepository:
    prompt_version_id: UUID = UUID("00000000-0000-0000-0000-000000000302")
    run_id: UUID = UUID("00000000-0000-0000-0000-000000000301")
    failed: list[dict[str, object]] = field(default_factory=list)

    def ensure_prompt_version(self, session: object, prompt: object) -> UUID:
        return self.prompt_version_id

    def create_run(self, session: object, run: object) -> UUID:
        return self.run_id

    def mark_succeeded(
        self,
        session: object,
        *,
        run_id: UUID,
        output_snapshot: dict[str, Any],
        raw_output: str,
    ) -> None:
        return None

    def mark_failed(
        self,
        session: object,
        *,
        run_id: UUID,
        error_code: str,
        error_message: str,
        raw_output: str | None,
    ) -> None:
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

    def __call__(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        output = ChainExplanationOutput.model_validate(
            {
                "summary": "这条人物链由一条已审核见面边组成。",
                "edge_explanations": [
                    {
                        "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                        "explanation": "许几曾谒见韩琦。",
                        "evidence_basis": "encounter_evidence",
                        "source_ref_ids": [3853784],
                    }
                ],
                "source_notes": ["source_ref 3853784 提供页码和 notes。"],
                "limitations": ["AI 解释只是对已审核证据的重述。"],
                "display_language": "zh-Hans",
            }
        )
        return SimpleNamespace(
            run_id=UUID("00000000-0000-0000-0000-000000000301"),
            output=output,
        )


def chain_result() -> ChainLookupResult:
    return ChainLookupResult(
        source_person_id="38966b03-8aa7-5143-8021-2d266889b6c5",
        target_person_id="46cfdf66-08c4-5876-964b-4a95d098afe9",
        max_depth=12,
        path=ChainPath(
            people=(
                ChainPerson(
                    person_id="38966b03-8aa7-5143-8021-2d266889b6c5",
                    display_name="许几",
                    birth_year=1010,
                    death_year=1080,
                    cbdb_external_id="123",
                ),
                ChainPerson(
                    person_id="46cfdf66-08c4-5876-964b-4a95d098afe9",
                    display_name="韩琦",
                    birth_year=1008,
                    death_year=1075,
                    cbdb_external_id="456",
                ),
            ),
            edges=(
                ChainEdge(
                    encounter_id="e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                    encounter_kind="direct_interaction",
                    certainty_level="high",
                    pages="卷一",
                    evidence_summary="许几曾谒见韩琦。",
                ),
            ),
        ),
    )


def no_path_result() -> ChainLookupResult:
    return ChainLookupResult(
        source_person_id="38966b03-8aa7-5143-8021-2d266889b6c5",
        target_person_id="46cfdf66-08c4-5876-964b-4a95d098afe9",
        max_depth=12,
        path=None,
    )


def encounter_detail() -> EncounterDetail:
    now = datetime(2026, 6, 13, tzinfo=UTC)
    return EncounterDetail(
        encounter_id=UUID("e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"),
        person_a=CandidatePerson(
            person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
            cbdb_id=123,
            primary_name_zh_hant="許幾",
            primary_name_zh_hans="许几",
            primary_name_romanized=None,
            birth_year=1010,
            death_year=1080,
            external_ids=[],
        ),
        person_b=CandidatePerson(
            person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
            cbdb_id=456,
            primary_name_zh_hant="韓琦",
            primary_name_zh_hans="韩琦",
            primary_name_romanized=None,
            birth_year=1008,
            death_year=1075,
            external_ids=[],
        ),
        encounter_kind="direct_interaction",
        certainty_level="high",
        path_eligible=True,
        source_work_id=111,
        pages="卷一",
        evidence_summary="许几曾谒见韩琦。",
        review_note="人工审核通过。",
        status="active",
        reviewed_by="tester",
        reviewed_at=now,
        created_at=now,
        updated_at=now,
        evidence=[
            EncounterEvidenceDetail(
                evidence_id=1,
                candidate_table="relationship_candidates",
                candidate_id=960698,
                source_ref_id=3853784,
                source_work_id=111,
                pages="卷一",
                evidence_kind="candidate_source",
                evidence_summary="许几曾谒见韩琦。",
                created_at=now,
            )
        ],
        source_refs=[
            CandidateSourceRef(
                source_ref_id=3853784,
                source_work_id=111,
                title_zh="续资治通鉴长编",
                title_en=None,
                pages="卷一",
                notes="许几谒见韩琦。",
            )
        ],
    )


def settings() -> Any:
    return SimpleNamespace(ai_model="fake-history-model", ai_max_output_tokens=1200)


def test_save_chain_explanation_output_writes_ai_table_only() -> None:
    repository = FakeChainRepository()
    output = ChainExplanationOutput.model_validate(
        {
            "summary": "这条人物链由一条已审核见面边组成。",
            "edge_explanations": [
                {
                    "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                    "explanation": "许几曾谒见韩琦。",
                    "evidence_basis": "encounter_evidence",
                    "source_ref_ids": [3853784],
                }
            ],
            "source_notes": [],
            "limitations": [],
            "display_language": "zh-Hans",
        }
    )

    record = save_chain_explanation_output(
        session=object(),
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        chain_hash="known-chain-hash",
        source_person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
        target_person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
        max_depth=12,
        encounter_ids=["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
        language="zh-Hans",
        output=output,
        repository=repository,
    )

    assert record.id == repository.explanation_id
    assert repository.created[0].chain_hash == "known-chain-hash"
    assert repository.created[0].summary == "这条人物链由一条已审核见面边组成。"
    assert repository.created[0].source_ref_ids == [3853784]


def test_generate_chain_explanation_for_result_calls_prompt_runner() -> None:
    repository = FakeChainRepository()
    runner = CapturingPromptRunner()

    result = generate_chain_explanation_for_result(
        session=object(),
        result=chain_result(),
        encounter_details={
            "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f": encounter_detail(),
        },
        settings=settings(),
        provider=FakeProvider(),
        created_by="tester",
        language="zh-Hans",
        repository=repository,
        run_prompt=runner,
    )

    assert isinstance(result, ChainExplanationGenerationResult)
    assert result.explanation.chain_hash == repository.created[0].chain_hash
    assert runner.kwargs["output_schema"] is ChainExplanationOutput
    assert "chain_json" in runner.kwargs["input_variables"]
    assert callable(runner.kwargs["output_guard"])


def test_generate_chain_explanation_for_result_records_invalid_context_failure() -> None:
    repository = FakeChainRepository()
    run_repository = FakeRunRepository()

    with raises(InvalidChainContextError):
        generate_chain_explanation_for_result(
            session=object(),
            result=no_path_result(),
            encounter_details={},
            settings=settings(),
            provider=FakeProvider(),
            created_by="tester",
            language="zh-Hans",
            repository=repository,
            run_repository=run_repository,
        )

    assert repository.created == []
    assert run_repository.failed[0]["error_code"] == "invalid_chain_context"
```

Create `tests/ai/test_chain_formatting.py`:

```python
from uuid import UUID

from figure_data.ai.chain_formatting import format_chain_explanation_detail
from figure_data.ai.chain_repository import ChainExplanationRecord


def explanation_record() -> ChainExplanationRecord:
    return ChainExplanationRecord(
        id=UUID("00000000-0000-0000-0000-000000000401"),
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        chain_hash="known-chain-hash",
        source_person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
        target_person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
        max_depth=12,
        encounter_ids=["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
        language="zh-Hans",
        summary="这条人物链由一条已审核见面边组成。",
        edge_explanations=[
            {
                "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                "explanation": "许几曾谒见韩琦。",
                "evidence_basis": "encounter_evidence",
                "source_ref_ids": [3853784],
            }
        ],
        source_ref_ids=[3853784],
        status="generated",
        created_at="2026-06-13T00:00:00+00:00",
    )


def test_format_chain_explanation_detail_outputs_trace_fields() -> None:
    lines = format_chain_explanation_detail(explanation_record())

    assert "ai_chain_explanation\t00000000-0000-0000-0000-000000000401" in lines
    assert "ai_run\t00000000-0000-0000-0000-000000000301" in lines
    assert "chain_hash\tknown-chain-hash" in lines
    assert "summary\t这条人物链由一条已审核见面边组成。" in lines
    assert "edge_explanation\te4f22ec2-22f7-4cda-bcc1-73aa83d0685f\t许几曾谒见韩琦。" in lines
    assert "source_ref\t3853784" in lines
```

Create `tests/ai/test_chain_explanation_cli.py`:

```python
from types import SimpleNamespace
from types import TracebackType
from uuid import UUID

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.ai.chain_repository import ChainExplanationRecord
from figure_data.ai.chain_service import ChainExplanationGenerationResult
from figure_data.ai.errors import AIOutputValidationError
from figure_data.cli import app

runner = CliRunner()


class DummyDriver:
    def close(self) -> None:
        return None


class DummyGraphSession:
    def __enter__(self) -> object:
        return object()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
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


class TrackingSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def explanation_record() -> ChainExplanationRecord:
    return ChainExplanationRecord(
        id=UUID("00000000-0000-0000-0000-000000000401"),
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        chain_hash="known-chain-hash",
        source_person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
        target_person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
        max_depth=12,
        encounter_ids=["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
        language="zh-Hans",
        summary="这条人物链由一条已审核见面边组成。",
        edge_explanations=[
            {
                "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                "explanation": "许几曾谒见韩琦。",
                "evidence_basis": "encounter_evidence",
                "source_ref_ids": [3853784],
            }
        ],
        source_ref_ids=[3853784],
        status="generated",
        created_at="2026-06-13T00:00:00+00:00",
    )


def patch_runtime(monkeypatch: MonkeyPatch, session: object | None = None) -> None:
    resolved_session = session or DummySession()
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr(
        "figure_data.cli.create_session_factory",
        lambda settings: lambda: resolved_session,
    )
    monkeypatch.setattr("figure_data.cli.create_neo4j_driver", lambda settings: DummyDriver())
    monkeypatch.setattr(
        "figure_data.cli.get_neo4j_config",
        lambda settings: SimpleNamespace(database="neo4j"),
    )
    monkeypatch.setattr(
        "figure_data.cli.graph_session",
        lambda driver, database: DummyGraphSession(),
    )


def test_chain_explanation_help_commands_exit_zero() -> None:
    for command in ("generate-chain-explanation", "inspect-chain-explanation"):
        result = runner.invoke(app, [command, "--help"])

        assert result.exit_code == 0


def test_generate_chain_explanation_command_outputs_created_explanation(
    monkeypatch: MonkeyPatch,
) -> None:
    patch_runtime(monkeypatch)
    record = explanation_record()
    monkeypatch.setattr(
        "figure_data.cli.generate_chain_explanation_for_shortest_path",
        lambda **kwargs: ChainExplanationGenerationResult(
            ai_run_id=record.ai_run_id,
            chain_hash=record.chain_hash,
            explanation=record,
        ),
    )

    result = runner.invoke(
        app,
        [
            "generate-chain-explanation",
            "--from",
            "许几",
            "--to",
            "韩琦",
            "--created-by",
            "tester",
        ],
    )

    assert result.exit_code == 0
    assert "ai_chain_explanation" in result.output
    assert "chain_hash\tknown-chain-hash" in result.output


def test_generate_chain_explanation_command_commits_failed_ai_run(
    monkeypatch: MonkeyPatch,
) -> None:
    session = TrackingSession()
    patch_runtime(monkeypatch, session=session)

    def raise_validation_error(**kwargs: object) -> object:
        raise AIOutputValidationError("model output failed schema validation")

    monkeypatch.setattr(
        "figure_data.cli.generate_chain_explanation_for_shortest_path",
        raise_validation_error,
    )

    result = runner.invoke(
        app,
        [
            "generate-chain-explanation",
            "--from",
            "许几",
            "--to",
            "韩琦",
            "--created-by",
            "tester",
        ],
    )

    assert result.exit_code == 1
    assert "model output failed schema validation" in result.stderr
    assert session.committed is True
    assert session.rolled_back is False
    assert session.closed is True


def test_inspect_chain_explanation_command_outputs_detail(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr(
        "figure_data.cli.create_session_factory",
        lambda settings: lambda: DummySession(),
    )
    monkeypatch.setattr(
        "figure_data.cli.get_chain_explanation_by_hash",
        lambda session, chain_hash: explanation_record(),
    )

    result = runner.invoke(app, ["inspect-chain-explanation", "--hash", "known-chain-hash"])

    assert result.exit_code == 0
    assert "source_ref\t3853784" in result.output
```

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_chain_repository.py tests/ai/test_chain_service.py tests/ai/test_chain_formatting.py tests/ai/test_chain_explanation_cli.py -q
```

Expected before implementation:

```text
FAIL because chain repository, service, formatting, and CLI modules do not exist yet.
```

- [ ] **Step 3: Implement context module**

Create `src/figure_data/ai/chain_context.py` with Pydantic input models and a builder:

```python
from __future__ import annotations

from pydantic import BaseModel, Field

from figure_data.encounters.types import EncounterDetail
from figure_data.graph.types import ChainLookupResult


class ChainExplanationPersonInput(BaseModel):
    person_id: str
    display_name: str
    birth_year: int | None
    death_year: int | None
    cbdb_external_id: str | None


class ChainExplanationSourceRefInput(BaseModel):
    source_ref_id: int
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    notes: str | None


class ChainExplanationEvidenceInput(BaseModel):
    evidence_id: int
    candidate_table: str | None
    candidate_id: int | None
    source_ref_id: int | None
    source_work_id: int | None
    pages: str | None
    evidence_kind: str
    evidence_summary: str


class ChainExplanationEncounterInput(BaseModel):
    encounter_id: str
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    evidence_summary: str
    review_note: str | None
    source_work_id: int | None
    pages: str | None
    evidence: list[ChainExplanationEvidenceInput] = Field(default_factory=list)
    source_refs: list[ChainExplanationSourceRefInput] = Field(default_factory=list)


class ChainExplanationPromptInput(BaseModel):
    source_person_id: str
    target_person_id: str
    max_depth: int
    language: str
    people: list[ChainExplanationPersonInput]
    encounters: list[ChainExplanationEncounterInput]


class InvalidChainContextError(ValueError):
    """Raised when a path cannot be explained from reviewed encounter evidence."""


def build_chain_explanation_prompt_input(
    *,
    result: ChainLookupResult,
    encounter_details: dict[str, EncounterDetail],
    language: str,
) -> ChainExplanationPromptInput:
    if result.path is None:
        raise InvalidChainContextError("chain explanation requires a found path")
    people = [
        ChainExplanationPersonInput(
            person_id=person.person_id,
            display_name=person.display_name,
            birth_year=person.birth_year,
            death_year=person.death_year,
            cbdb_external_id=person.cbdb_external_id,
        )
        for person in result.path.people
    ]
    encounters: list[ChainExplanationEncounterInput] = []
    for edge in result.path.edges:
        detail = encounter_details.get(edge.encounter_id)
        if detail is None:
            raise InvalidChainContextError(f"missing encounter detail: {edge.encounter_id}")
        if not detail.evidence:
            raise InvalidChainContextError(f"missing encounter evidence: {edge.encounter_id}")
        encounters.append(_encounter_input(detail))
    return ChainExplanationPromptInput(
        source_person_id=result.source_person_id,
        target_person_id=result.target_person_id,
        max_depth=result.max_depth,
        language=language,
        people=people,
        encounters=encounters,
    )


def _encounter_input(detail: EncounterDetail) -> ChainExplanationEncounterInput:
    return ChainExplanationEncounterInput(
        encounter_id=str(detail.encounter_id),
        encounter_kind=detail.encounter_kind,
        certainty_level=detail.certainty_level,
        path_eligible=detail.path_eligible,
        evidence_summary=detail.evidence_summary,
        review_note=detail.review_note,
        source_work_id=detail.source_work_id,
        pages=detail.pages,
        evidence=[
            ChainExplanationEvidenceInput(
                evidence_id=evidence.evidence_id,
                candidate_table=evidence.candidate_table,
                candidate_id=evidence.candidate_id,
                source_ref_id=evidence.source_ref_id,
                source_work_id=evidence.source_work_id,
                pages=evidence.pages,
                evidence_kind=evidence.evidence_kind,
                evidence_summary=evidence.evidence_summary,
            )
            for evidence in detail.evidence
        ],
        source_refs=[
            ChainExplanationSourceRefInput(
                source_ref_id=source_ref.source_ref_id,
                source_work_id=source_ref.source_work_id,
                title_zh=source_ref.title_zh,
                title_en=source_ref.title_en,
                pages=source_ref.pages,
                notes=source_ref.notes,
            )
            for source_ref in detail.source_refs
        ],
    )
```

- [ ] **Step 4: Implement repository, service, formatting, and CLI**

Modify `src/figure_data/ai/service.py` to add a reusable failed-run recorder below `run_ai_prompt()`:

```python
def record_failed_ai_prompt(
    *,
    session: Session | object,
    prompt: PromptDefinition,
    provider_name: str,
    model_name: str,
    input_snapshot: dict[str, Any],
    created_by: str,
    error_code: str,
    error_message: str,
    repository: AIRunRepository | None = None,
) -> UUID:
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
            provider=provider_name,
            model_name=model_name,
            prompt_version_id=prompt_version_id,
            input_hash=input_hash,
            input_snapshot=input_snapshot,
            created_by=created_by,
        ),
    )
    resolved_repository.mark_failed(
        session,  # type: ignore[arg-type]
        run_id=run_id,
        error_code=error_code,
        error_message=error_message,
        raw_output=None,
    )
    return run_id
```

Create `src/figure_data/ai/chain_repository.py`:

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


class AIChainExplanationNotFoundError(ValueError):
    """Raised when an AI chain explanation cannot be found."""


@dataclass(frozen=True)
class NewChainExplanation:
    ai_run_id: UUID
    chain_hash: str
    source_person_id: UUID
    target_person_id: UUID
    max_depth: int
    encounter_ids: list[str]
    language: str
    summary: str
    edge_explanations: list[dict[str, object]]
    source_ref_ids: list[int]


@dataclass(frozen=True)
class ChainExplanationRecord:
    id: UUID
    ai_run_id: UUID
    chain_hash: str
    source_person_id: UUID
    target_person_id: UUID
    max_depth: int
    encounter_ids: list[str]
    language: str
    summary: str
    edge_explanations: list[dict[str, object]]
    source_ref_ids: list[int]
    status: str
    created_at: datetime | str


def create_chain_explanation(session: Session, explanation: NewChainExplanation) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_chain_explanations (
              id, ai_run_id, chain_hash, source_person_id, target_person_id,
              max_depth, encounter_ids, language, summary, edge_explanations,
              source_ref_ids, status, created_at
            ) values (
              gen_random_uuid(), :ai_run_id, :chain_hash, :source_person_id,
              :target_person_id, :max_depth, cast(:encounter_ids as jsonb),
              :language, :summary, cast(:edge_explanations as jsonb),
              cast(:source_ref_ids as jsonb), :status, :created_at
            )
            returning id
            """
        ),
        {
            "ai_run_id": explanation.ai_run_id,
            "chain_hash": explanation.chain_hash,
            "source_person_id": explanation.source_person_id,
            "target_person_id": explanation.target_person_id,
            "max_depth": explanation.max_depth,
            "encounter_ids": json.dumps(explanation.encounter_ids, ensure_ascii=False),
            "language": explanation.language,
            "summary": explanation.summary,
            "edge_explanations": json.dumps(
                explanation.edge_explanations,
                ensure_ascii=False,
            ),
            "source_ref_ids": json.dumps(explanation.source_ref_ids),
            "status": "generated",
            "created_at": datetime.now(UTC),
        },
    ).scalar_one()
    return value if isinstance(value, UUID) else UUID(str(value))


def get_chain_explanation_by_hash(session: Session, chain_hash: str) -> ChainExplanationRecord:
    row = (
        session.execute(
            text(
                """
                select
                  id, ai_run_id, chain_hash, source_person_id, target_person_id,
                  max_depth, encounter_ids, language, summary, edge_explanations,
                  source_ref_ids, status, created_at
                from figure_data.ai_chain_explanations
                where chain_hash = :chain_hash
                  and status = 'generated'
                """
            ),
            {"chain_hash": chain_hash},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AIChainExplanationNotFoundError(f"AI chain explanation not found: {chain_hash}")
    return _record_from_row(cast(Mapping[str, Any], row))


def _record_from_row(row: Mapping[str, Any]) -> ChainExplanationRecord:
    return ChainExplanationRecord(
        id=_uuid(row["id"]),
        ai_run_id=_uuid(row["ai_run_id"]),
        chain_hash=str(row["chain_hash"]),
        source_person_id=_uuid(row["source_person_id"]),
        target_person_id=_uuid(row["target_person_id"]),
        max_depth=int(row["max_depth"]),
        encounter_ids=list(row["encounter_ids"]),
        language=str(row["language"]),
        summary=str(row["summary"]),
        edge_explanations=list(row["edge_explanations"]),
        source_ref_ids=[int(source_ref_id) for source_ref_id in row["source_ref_ids"]],
        status=str(row["status"]),
        created_at=cast(datetime | str, row["created_at"]),
    )


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
```

Create `src/figure_data/ai/chain_formatting.py`:

```python
from figure_data.ai.chain_repository import ChainExplanationRecord


def format_chain_explanation_detail(record: ChainExplanationRecord) -> list[str]:
    lines = [
        f"ai_chain_explanation\t{record.id}",
        f"ai_run\t{record.ai_run_id}",
        f"chain_hash\t{record.chain_hash}",
        f"source_person_id\t{record.source_person_id}",
        f"target_person_id\t{record.target_person_id}",
        f"max_depth\t{record.max_depth}",
        f"language\t{record.language}",
        f"status\t{record.status}",
        f"created_at\t{record.created_at}",
        f"summary\t{record.summary}",
    ]
    for encounter_id in record.encounter_ids:
        lines.append(f"encounter\t{encounter_id}")
    for edge in record.edge_explanations:
        encounter_id = str(edge["encounter_id"])
        explanation = str(edge["explanation"])
        lines.append(f"edge_explanation\t{encounter_id}\t{explanation}")
    for source_ref_id in record.source_ref_ids:
        lines.append(f"source_ref\t{source_ref_id}")
    return lines
```

Create `src/figure_data/ai/chain_service.py`:

```python
from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.ai.chain_context import (
    ChainExplanationEncounterInput,
    InvalidChainContextError,
    build_chain_explanation_prompt_input,
)
from figure_data.ai.chain_hash import compute_chain_hash
from figure_data.ai.chain_policy import validate_chain_explanation_policy
from figure_data.ai.chain_repository import (
    ChainExplanationRecord,
    NewChainExplanation,
    create_chain_explanation,
    get_chain_explanation_by_hash,
)
from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.provider import AIProvider, create_ai_provider
from figure_data.ai.repository import AIRunRepository
from figure_data.ai.schemas import ChainExplanationOutput
from figure_data.ai.service import AIRunResult, record_failed_ai_prompt, run_ai_prompt
from figure_data.config import Settings
from figure_data.db.enums import AIErrorCode
from figure_data.encounters.query import get_encounter_detail
from figure_data.encounters.types import EncounterDetail
from figure_data.graph.pathfinding import ChainEndpointInput, find_chain
from figure_data.graph.types import ChainLookupResult


class ChainExplanationRepository(Protocol):
    def create(self, session: object, explanation: NewChainExplanation) -> UUID:
        """Create a chain explanation."""

    def get_by_hash(self, session: object, chain_hash: str) -> ChainExplanationRecord:
        """Load a chain explanation by hash."""


class PostgresChainExplanationRepository:
    def create(self, session: object, explanation: NewChainExplanation) -> UUID:
        return create_chain_explanation(session, explanation)  # type: ignore[arg-type]

    def get_by_hash(self, session: object, chain_hash: str) -> ChainExplanationRecord:
        return get_chain_explanation_by_hash(session, chain_hash)  # type: ignore[arg-type]


@dataclass(frozen=True)
class ChainExplanationGenerationResult:
    ai_run_id: UUID
    chain_hash: str
    explanation: ChainExplanationRecord


def generate_chain_explanation_for_shortest_path(
    *,
    session: Session,
    neo4j_session: object,
    settings: Settings,
    source: ChainEndpointInput,
    target: ChainEndpointInput,
    max_depth: int,
    created_by: str,
    language: str = "zh-Hans",
    provider: AIProvider | None = None,
    repository: ChainExplanationRepository | None = None,
    run_repository: AIRunRepository | None = None,
) -> ChainExplanationGenerationResult:
    result = find_chain(session, neo4j_session, source, target, max_depth)
    encounter_details = _load_encounter_details(session, result)
    return generate_chain_explanation_for_result(
        session=session,
        result=result,
        encounter_details=encounter_details,
        settings=settings,
        provider=provider,
        created_by=created_by,
        language=language,
        repository=repository,
        run_repository=run_repository,
    )


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
) -> ChainExplanationGenerationResult:
    prompt = get_prompt_definition("chain_explanation")
    model_name = _require_ai_model(settings)
    resolved_provider = provider or create_ai_provider(settings)
    input_seed = _input_seed(result=result, language=language)
    try:
        prompt_input = build_chain_explanation_prompt_input(
            result=result,
            encounter_details=encounter_details,
            language=language,
        )
    except InvalidChainContextError as exc:
        record_failed_ai_prompt(
            session=session,
            prompt=prompt,
            provider_name=getattr(resolved_provider, "provider_name", "unknown"),
            model_name=model_name,
            input_snapshot=input_seed,
            created_by=created_by,
            error_code=AIErrorCode.INVALID_CHAIN_CONTEXT.value,
            error_message=str(exc),
            repository=run_repository,
        )
        raise

    prompt_snapshot = prompt_input.model_dump(mode="json")
    chain_json = json.dumps(prompt_snapshot, ensure_ascii=False, sort_keys=True)
    encounter_ids = [edge.encounter_id for edge in result.path.edges] if result.path else []
    chain_hash = compute_chain_hash(
        source_person_id=result.source_person_id,
        target_person_id=result.target_person_id,
        max_depth=result.max_depth,
        encounter_ids=encounter_ids,
        prompt_key=prompt.prompt_key,
        prompt_version=prompt.prompt_version,
        output_schema_version=prompt.output_schema_version,
        language=language,
    )
    allowed_encounter_ids = {encounter.encounter_id for encounter in prompt_input.encounters}
    allowed_source_ref_ids = _allowed_source_ref_ids(prompt_input.encounters)
    run_result = run_prompt(
        session=session,
        prompt=prompt,
        provider=resolved_provider,
        output_schema=ChainExplanationOutput,
        input_variables={"chain_json": chain_json},
        input_snapshot=prompt_snapshot,
        model_name=model_name,
        max_output_tokens=settings.ai_max_output_tokens,
        created_by=created_by,
        repository=run_repository,
        output_guard=lambda output: validate_chain_explanation_policy(
            output,
            allowed_encounter_ids=allowed_encounter_ids,
            allowed_source_ref_ids=allowed_source_ref_ids,
        ),
    )
    explanation = save_chain_explanation_output(
        session=session,
        ai_run_id=run_result.run_id,
        chain_hash=chain_hash,
        source_person_id=UUID(result.source_person_id),
        target_person_id=UUID(result.target_person_id),
        max_depth=result.max_depth,
        encounter_ids=encounter_ids,
        language=language,
        output=run_result.output,
        repository=repository,
    )
    return ChainExplanationGenerationResult(
        ai_run_id=run_result.run_id,
        chain_hash=chain_hash,
        explanation=explanation,
    )


def save_chain_explanation_output(
    *,
    session: object,
    ai_run_id: UUID,
    chain_hash: str,
    source_person_id: UUID,
    target_person_id: UUID,
    max_depth: int,
    encounter_ids: list[str],
    language: str,
    output: ChainExplanationOutput,
    repository: ChainExplanationRepository | None = None,
) -> ChainExplanationRecord:
    resolved_repository = repository or PostgresChainExplanationRepository()
    source_ref_ids = sorted(
        {
            source_ref_id
            for edge in output.edge_explanations
            for source_ref_id in edge.source_ref_ids
        }
    )
    _ = resolved_repository.create(
        session,
        NewChainExplanation(
            ai_run_id=ai_run_id,
            chain_hash=chain_hash,
            source_person_id=source_person_id,
            target_person_id=target_person_id,
            max_depth=max_depth,
            encounter_ids=encounter_ids,
            language=language,
            summary=output.summary,
            edge_explanations=[
                edge.model_dump(mode="json") for edge in output.edge_explanations
            ],
            source_ref_ids=source_ref_ids,
        ),
    )
    return resolved_repository.get_by_hash(session, chain_hash)


def _load_encounter_details(
    session: Session,
    result: ChainLookupResult,
) -> dict[str, EncounterDetail]:
    if result.path is None:
        return {}
    return {
        edge.encounter_id: get_encounter_detail(session, UUID(edge.encounter_id))
        for edge in result.path.edges
    }


def _allowed_source_ref_ids(
    encounters: Iterable[ChainExplanationEncounterInput],
) -> set[int]:
    allowed: set[int] = set()
    for encounter in encounters:
        for source_ref in encounter.source_refs:
            allowed.add(source_ref.source_ref_id)
        for evidence in encounter.evidence:
            if evidence.source_ref_id is not None:
                allowed.add(evidence.source_ref_id)
    return allowed


def _input_seed(*, result: ChainLookupResult, language: str) -> dict[str, object]:
    encounter_ids = [] if result.path is None else [edge.encounter_id for edge in result.path.edges]
    return {
        "source_person_id": result.source_person_id,
        "target_person_id": result.target_person_id,
        "max_depth": result.max_depth,
        "language": language,
        "encounter_ids": encounter_ids,
    }


def _require_ai_model(settings: Settings) -> str:
    if settings.ai_model is None:
        raise ValueError("FIGURE_AI_MODEL is required for chain explanations")
    return settings.ai_model
```

Remove `explanation_id` if `ruff` reports an unused local variable in `save_chain_explanation_output()`.

Add imports to `src/figure_data/cli.py`:

```python
from figure_data.ai.chain_context import InvalidChainContextError
from figure_data.ai.chain_formatting import format_chain_explanation_detail
from figure_data.ai.chain_repository import (
    AIChainExplanationNotFoundError,
    get_chain_explanation_by_hash,
)
from figure_data.ai.chain_service import generate_chain_explanation_for_shortest_path
```

Add CLI commands to `src/figure_data/cli.py` after `suggest_candidate_review_command()`:

```python
@app.command("generate-chain-explanation")
def generate_chain_explanation_command(
    from_query: Annotated[str | None, typer.Option("--from")] = None,
    to_query: Annotated[str | None, typer.Option("--to")] = None,
    from_person_id: Annotated[UUID | None, typer.Option("--from-person-id")] = None,
    to_person_id: Annotated[UUID | None, typer.Option("--to-person-id")] = None,
    from_cbdb_id: Annotated[str | None, typer.Option("--from-cbdb-id")] = None,
    to_cbdb_id: Annotated[str | None, typer.Option("--to-cbdb-id")] = None,
    max_depth: Annotated[int, typer.Option("--max-depth", min=1, max=30)] = 12,
    language: Annotated[str, typer.Option("--language")] = "zh-Hans",
    created_by: Annotated[str, typer.Option("--created-by")] = "local",
) -> None:
    """Generate and store an AI explanation for one reviewed shortest chain."""
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
            result = generate_chain_explanation_for_shortest_path(
                session=session,
                neo4j_session=neo4j_session,
                settings=settings,
                source=source,
                target=target,
                max_depth=max_depth,
                created_by=created_by,
                language=language,
            )
        session.commit()
    except (
        AIProviderConfigurationError,
        AIProviderError,
        AIOutputValidationError,
        AIOutputPolicyViolation,
        InvalidChainContextError,
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
    for line in format_chain_explanation_detail(result.explanation):
        _echo_cli_line(line)
```

```python
@app.command("inspect-chain-explanation")
def inspect_chain_explanation_command(
    chain_hash: Annotated[str, typer.Option("--hash")],
) -> None:
    """Inspect one stored AI chain explanation."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            record = get_chain_explanation_by_hash(session, chain_hash)
    except AIChainExplanationNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_chain_explanation_detail(record):
        _echo_cli_line(line)
```

- [ ] **Step 5: Run Task 3 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_chain_context.py tests/ai/test_chain_repository.py tests/ai/test_chain_service.py tests/ai/test_chain_formatting.py tests/ai/test_chain_explanation_cli.py -q
uv run --no-sync figure-data generate-chain-explanation --help
uv run --no-sync figure-data inspect-chain-explanation --help
uv run --no-sync ruff check src/figure_data/ai src/figure_data/cli.py tests/ai
uv run --no-sync mypy src/figure_data/ai src/figure_data/cli.py tests/ai
```

Expected:

```text
All Task 3 tests pass.
Both CLI help commands exit 0.
ruff passes.
mypy passes.
```

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add src/figure_data/ai/chain_context.py src/figure_data/ai/chain_repository.py src/figure_data/ai/chain_service.py src/figure_data/ai/chain_formatting.py src/figure_data/cli.py tests/ai/test_chain_context.py tests/ai/test_chain_repository.py tests/ai/test_chain_service.py tests/ai/test_chain_formatting.py tests/ai/test_chain_explanation_cli.py
git commit -m "feat: 生成并查看 AI 人物链解释"
```

## Task 4: FastAPI Read-Only AI Endpoints

**Files:**

- Modify: `src/figure_chain/schemas.py`
- Modify: `src/figure_chain/errors.py`
- Modify: `src/figure_chain/dependencies.py`
- Modify: `src/figure_chain/routers/__init__.py`
- Create: `src/figure_chain/routers/ai.py`
- Create: `src/figure_chain/services/ai.py`
- Modify: `src/figure_chain/services/chains.py`
- Modify: `tests/figure_chain/test_chains_api.py`
- Create: `tests/figure_chain/test_ai_api.py`

- [ ] **Step 1: Add failing API tests**

Create `tests/figure_chain/test_ai_api.py`:

```python
from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_ai_service
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import AIChainExplanationResponse, AIRunResponse


class FakeAIService:
    def get_chain_explanation(self, chain_hash: str) -> AIChainExplanationResponse:
        if chain_hash != "known":
            raise ApplicationError(
                code=ErrorCode.AI_RESULT_NOT_FOUND,
                message="AI chain explanation was not found",
                details={"chain_hash": chain_hash},
            )
        return AIChainExplanationResponse(
            id=UUID("00000000-0000-0000-0000-000000000401"),
            ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
            chain_hash="known",
            source_person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
            target_person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
            max_depth=12,
            encounter_ids=["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
            language="zh-Hans",
            summary="这条人物链由一条已审核 encounter 组成。",
            edge_explanations=[
                {
                    "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                    "explanation": "许几谒见韩琦。",
                    "evidence_basis": "encounter_evidence",
                    "source_ref_ids": [3853784],
                }
            ],
            source_ref_ids=[3853784],
            status="generated",
            created_at=datetime(2026, 6, 13, tzinfo=UTC),
        )

    def get_ai_run(self, run_id: UUID) -> AIRunResponse:
        return AIRunResponse(
            run_id=run_id,
            purpose="chain_explanation",
            provider="fake",
            model_name="fake-history-model",
            prompt_key="chain_explanation",
            prompt_version="2026-06-13.1",
            status="succeeded",
            schema_valid=True,
            error_code=None,
            error_message=None,
            started_at=datetime(2026, 6, 13, tzinfo=UTC),
            finished_at=datetime(2026, 6, 13, tzinfo=UTC),
            created_by="tester",
        )


def test_get_chain_explanation_returns_stored_result() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()

    with TestClient(app) as client:
        response = client.get("/api/v1/ai/chains/explanations/known")

    assert response.status_code == 200
    body = response.json()
    assert body["chain_hash"] == "known"
    assert body["summary"] == "这条人物链由一条已审核 encounter 组成。"


def test_get_chain_explanation_returns_404_when_missing() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()

    with TestClient(app) as client:
        response = client.get("/api/v1/ai/chains/explanations/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ai_result_not_found"


def test_get_ai_run_returns_trace_metadata() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()

    with TestClient(app) as client:
        response = client.get("/api/v1/ai/runs/00000000-0000-0000-0000-000000000301")

    assert response.status_code == 200
    assert response.json()["prompt_key"] == "chain_explanation"
```

Append to `tests/figure_chain/test_chains_api.py`:

```python
def test_shortest_chain_found_includes_chain_hash() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_chain_service] = lambda: FakeChainService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/shortest",
            json={
                "source": {"person_id": "38966b03-8aa7-5143-8021-2d266889b6c5"},
                "target": {"person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9"},
                "max_depth": 12,
            },
        )

    assert response.status_code == 200
    assert isinstance(response.json()["chain_hash"], str)
    assert len(response.json()["chain_hash"]) == 64
```

- [ ] **Step 2: Run API tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/figure_chain/test_ai_api.py tests/figure_chain/test_chains_api.py -q
```

Expected:

```text
FAIL because AI schemas, router, service, dependency, and chain_hash response do not exist yet.
```

- [ ] **Step 3: Add schemas and error code**

Modify `src/figure_chain/errors.py`:

```python
class ErrorCode(StrEnum):
    ...
    AI_RESULT_NOT_FOUND = "ai_result_not_found"
```

Add to `ERROR_STATUS`:

```python
ErrorCode.AI_RESULT_NOT_FOUND: status.HTTP_404_NOT_FOUND,
```

Modify `src/figure_chain/schemas.py`:

```python
class ShortestChainResponse(BaseModel):
    status: Literal["found", "no_path"]
    source_person_id: str
    target_person_id: str
    max_depth: int
    chain_hash: str | None = None
    path: ChainPathResponse | None


class AIChainExplanationResponse(BaseModel):
    id: UUID
    ai_run_id: UUID
    chain_hash: str
    source_person_id: UUID
    target_person_id: UUID
    max_depth: int
    encounter_ids: list[str]
    language: str
    summary: str
    edge_explanations: list[dict[str, object]]
    source_ref_ids: list[int]
    status: str
    created_at: datetime


class AIRunResponse(BaseModel):
    run_id: UUID
    purpose: str
    provider: str
    model_name: str
    prompt_key: str | None
    prompt_version: str | None
    status: str
    schema_valid: bool
    error_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
    created_by: str
```

- [ ] **Step 4: Compute chain_hash in chain service**

Modify `src/figure_chain/services/chains.py`:

```python
from figure_data.ai.chain_hash import compute_chain_hash
from figure_data.ai.prompts import get_prompt_definition
```

When `result.path is None`, set `chain_hash=None`. When found, compute:

```python
prompt = get_prompt_definition("chain_explanation")
encounter_ids = [edge.encounter_id for edge in result.path.edges]
chain_hash = compute_chain_hash(
    source_person_id=result.source_person_id,
    target_person_id=result.target_person_id,
    max_depth=result.max_depth,
    encounter_ids=encounter_ids,
    prompt_key=prompt.prompt_key,
    prompt_version=prompt.prompt_version,
    output_schema_version=prompt.output_schema_version,
    language="zh-Hans",
)
```

Pass `chain_hash=chain_hash` into `ShortestChainResponse`.

- [ ] **Step 5: Add read-only AI service and router**

Create `src/figure_chain/services/ai.py`:

```python
from uuid import UUID

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import AIChainExplanationResponse, AIRunResponse
from figure_data.ai.chain_repository import (
    AIChainExplanationNotFoundError,
    get_chain_explanation_by_hash,
)
from figure_data.ai.repository import get_ai_run
from figure_data.ai.errors import AIRunNotFoundError


class AIService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_chain_explanation(self, chain_hash: str) -> AIChainExplanationResponse:
        try:
            record = get_chain_explanation_by_hash(self._session, chain_hash)
        except AIChainExplanationNotFoundError as exc:
            raise ApplicationError(
                code=ErrorCode.AI_RESULT_NOT_FOUND,
                message="AI chain explanation was not found",
                details={"chain_hash": chain_hash},
            ) from exc
        return AIChainExplanationResponse(**record.__dict__)

    def get_ai_run(self, run_id: UUID) -> AIRunResponse:
        try:
            record = get_ai_run(self._session, run_id)
        except AIRunNotFoundError as exc:
            raise ApplicationError(
                code=ErrorCode.AI_RESULT_NOT_FOUND,
                message="AI run was not found",
                details={"run_id": str(run_id)},
            ) from exc
        return AIRunResponse(
            run_id=record.run_id,
            purpose=record.purpose,
            provider=record.provider,
            model_name=record.model_name,
            prompt_key=record.prompt_key,
            prompt_version=record.prompt_version,
            status=record.status,
            schema_valid=record.schema_valid,
            error_code=record.error_code,
            error_message=record.error_message,
            started_at=record.started_at,
            finished_at=record.finished_at,
            created_by=record.created_by,
        )
```

Create `src/figure_chain/routers/ai.py`:

```python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from figure_chain.dependencies import get_ai_service
from figure_chain.schemas import AIChainExplanationResponse, AIRunResponse
from figure_chain.services.ai import AIService

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.get("/chains/explanations/{chain_hash}", response_model=AIChainExplanationResponse)
def chain_explanation(
    chain_hash: str,
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AIChainExplanationResponse:
    return service.get_chain_explanation(chain_hash)


@router.get("/runs/{run_id}", response_model=AIRunResponse)
def ai_run(
    run_id: UUID,
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AIRunResponse:
    return service.get_ai_run(run_id)
```

Modify `src/figure_chain/dependencies.py`:

```python
from figure_chain.services.ai import AIService


def get_ai_service(
    pg_session: Annotated[Session, Depends(get_pg_session)],
) -> AIService:
    return AIService(pg_session)
```

Modify `src/figure_chain/routers/__init__.py` so `api_router()` includes `ai.router`.

- [ ] **Step 6: Run Task 4 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/figure_chain/test_ai_api.py tests/figure_chain/test_chains_api.py -q
uv run --no-sync ruff check src/figure_chain tests/figure_chain
uv run --no-sync mypy src/figure_chain tests/figure_chain
```

Expected:

```text
All Task 4 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 7: Commit Task 4**

Run:

```powershell
git add src/figure_chain/schemas.py src/figure_chain/errors.py src/figure_chain/dependencies.py src/figure_chain/routers/__init__.py src/figure_chain/routers/ai.py src/figure_chain/services/ai.py src/figure_chain/services/chains.py tests/figure_chain/test_ai_api.py tests/figure_chain/test_chains_api.py
git commit -m "feat: 添加 AI 人物链解释读取接口"
```

## Task 5: Next.js Optional AI Explanation Display

**Files:**

- Modify: `frontend/src/lib/figure-chain-types.ts`
- Modify: `frontend/src/test/fixtures.ts`
- Create: `frontend/app/api/figure-chain/ai/chains/explanations/[chainHash]/route.ts`
- Create: `frontend/app/api/figure-chain/ai/runs/[runId]/route.ts`
- Create: `frontend/src/hooks/use-chain-explanation.ts`
- Create: `frontend/src/components/chain-explanation-panel.tsx`
- Modify: `frontend/src/components/chain-result.tsx`
- Modify: `frontend/tests/unit/api-client.test.ts`
- Modify: `frontend/tests/unit/chain-result.test.tsx`
- Create: `frontend/tests/unit/chain-explanation-panel.test.tsx`
- Create: `frontend/tests/unit/use-chain-explanation.test.tsx`

- [ ] **Step 1: Add frontend types**

Modify `frontend/src/lib/figure-chain-types.ts`:

```ts
export type AIChainEdgeExplanation = {
  encounter_id: string;
  explanation: string;
  evidence_basis: string;
  source_ref_ids: number[];
};

export type AIChainExplanation = {
  id: string;
  ai_run_id: string;
  chain_hash: string;
  source_person_id: string;
  target_person_id: string;
  max_depth: number;
  encounter_ids: string[];
  language: string;
  summary: string;
  edge_explanations: AIChainEdgeExplanation[];
  source_ref_ids: number[];
  status: string;
  created_at: string;
};

export type AIRun = {
  run_id: string;
  purpose: string;
  provider: string;
  model_name: string;
  prompt_key: string | null;
  prompt_version: string | null;
  status: string;
  schema_valid: boolean;
  error_code: string | null;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
  created_by: string;
};
```

Add `chain_hash` to `ShortestChainResponse`:

```ts
export type ShortestChainResponse = {
  status: "found" | "no_path";
  source_person_id: string;
  target_person_id: string;
  max_depth: number;
  chain_hash: string | null;
  path: ChainPath | null;
};
```

- [ ] **Step 2: Add route handlers**

Create `frontend/app/api/figure-chain/ai/chains/explanations/[chainHash]/route.ts`:

```ts
import type { NextRequest } from "next/server";

import { forwardToFigureChain } from "@/lib/api-client";

type RouteContext = {
  params: Promise<{ chainHash: string }>;
};

export async function GET(
  request: NextRequest,
  context: RouteContext,
): Promise<Response> {
  const { chainHash } = await context.params;
  return forwardToFigureChain(
    `/api/v1/ai/chains/explanations/${encodeURIComponent(chainHash)}`,
  );
}
```

Create `frontend/app/api/figure-chain/ai/runs/[runId]/route.ts`:

```ts
import type { NextRequest } from "next/server";

import { forwardToFigureChain } from "@/lib/api-client";

type RouteContext = {
  params: Promise<{ runId: string }>;
};

export async function GET(
  request: NextRequest,
  context: RouteContext,
): Promise<Response> {
  const { runId } = await context.params;
  return forwardToFigureChain(`/api/v1/ai/runs/${encodeURIComponent(runId)}`);
}
```

- [ ] **Step 3: Add hook**

Create `frontend/src/hooks/use-chain-explanation.ts`:

```ts
"use client";

import { useEffect, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type { AIChainExplanation } from "@/lib/figure-chain-types";

type ChainExplanationState = {
  explanation: AIChainExplanation | null;
  isLoading: boolean;
  error: DisplayableError | null;
};

export function useChainExplanation(chainHash: string | null) {
  const [state, setState] = useState<ChainExplanationState>({
    explanation: null,
    isLoading: false,
    error: null,
  });

  useEffect(() => {
    if (!chainHash) {
      setState({ explanation: null, isLoading: false, error: null });
      return;
    }

    let cancelled = false;
    setState({ explanation: null, isLoading: true, error: null });

    fetch(`/api/figure-chain/ai/chains/explanations/${encodeURIComponent(chainHash)}`)
      .then(async (response) => {
        const body = (await response.json()) as unknown;
        if (!response.ok) {
          throw parseErrorResponse(body);
        }
        if (!cancelled) {
          setState({
            explanation: body as AIChainExplanation,
            isLoading: false,
            error: null,
          });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            explanation: null,
            isLoading: false,
            error: parseErrorResponse(error),
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [chainHash]);

  return state;
}
```

- [ ] **Step 4: Add explanation panel component**

Create `frontend/src/components/chain-explanation-panel.tsx`:

```tsx
import { Sparkles } from "lucide-react";

import type { AIChainExplanation } from "@/lib/figure-chain-types";

type ChainExplanationPanelProps = {
  explanation: AIChainExplanation | null;
  isLoading: boolean;
  unavailableMessage: string | null;
};

export function ChainExplanationPanel({
  explanation,
  isLoading,
  unavailableMessage,
}: ChainExplanationPanelProps) {
  if (isLoading) {
    return (
      <section className="rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">
        AI 解释加载中...
      </section>
    );
  }

  if (explanation === null) {
    if (!unavailableMessage) {
      return null;
    }
    return (
      <section className="rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">
        {unavailableMessage}
      </section>
    );
  }

  return (
    <section className="space-y-3 rounded border border-stone-200 bg-white p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-stone-700">
        <Sparkles aria-hidden="true" className="h-4 w-4 text-amber-600" />
        <span>AI 解释</span>
      </div>
      <p className="text-sm leading-6 text-stone-800">{explanation.summary}</p>
      <div className="space-y-2">
        {explanation.edge_explanations.map((edge) => (
          <div
            key={edge.encounter_id}
            className="border-l-2 border-amber-300 pl-3 text-sm text-stone-700"
          >
            <p>{edge.explanation}</p>
            <p className="mt-1 text-xs text-stone-500">
              encounter_id: {edge.encounter_id}
            </p>
          </div>
        ))}
      </div>
      <p className="text-xs text-stone-500">
        生成时间：{new Date(explanation.created_at).toLocaleString()}
      </p>
    </section>
  );
}
```

- [ ] **Step 5: Integrate panel into chain result**

Modify `frontend/src/components/chain-result.tsx`:

```tsx
import { ChainExplanationPanel } from "@/components/chain-explanation-panel";
import { useChainExplanation } from "@/hooks/use-chain-explanation";
```

After `validateChainPathShape` succeeds:

```tsx
const explanation = useChainExplanation(result.chain_hash);
const unavailableMessage =
  explanation.error?.code === "ai_result_not_found"
    ? "这条路径暂时还没有生成 AI 解释。"
    : explanation.error
      ? "AI 解释暂不可用，路径和证据仍可正常查看。"
      : null;
```

Render the panel after `<ChainPath />`:

```tsx
<ChainExplanationPanel
  explanation={explanation.explanation}
  isLoading={explanation.isLoading}
  unavailableMessage={unavailableMessage}
/>
```

Keep existing path and evidence behavior unchanged.

- [ ] **Step 6: Add frontend tests**

Update fixtures with `chain_hash`:

```ts
export const shortestChainFound: ShortestChainResponse = {
  status: "found",
  source_person_id: xuJi.person_id,
  target_person_id: hanQi.person_id,
  max_depth: 12,
  chain_hash: "known-chain-hash",
  path: oneHopPath,
};

export const shortestChainNoPath: ShortestChainResponse = {
  status: "no_path",
  source_person_id: xuJi.person_id,
  target_person_id: hanQi.person_id,
  max_depth: 12,
  chain_hash: null,
  path: null,
};
```

Add tests that assert:

- route handlers forward `/api/v1/ai/chains/explanations/{chainHash}` and `/api/v1/ai/runs/{runId}`;
- `ChainExplanationPanel` renders summary and edge explanations;
- `ChainResult` still renders path when explanation returns 404;
- `useChainExplanation(null)` does not fetch.

- [ ] **Step 7: Run Task 5 tests**

Run:

```powershell
npm --prefix frontend run test -- --runInBand
npm --prefix frontend run lint
npm --prefix frontend run typecheck
```

If Vitest rejects `--runInBand`, run:

```powershell
npm --prefix frontend run test
```

Expected:

```text
Frontend unit tests pass.
lint passes.
typecheck passes.
```

- [ ] **Step 8: Commit Task 5**

Run:

```powershell
git add frontend/src/lib/figure-chain-types.ts frontend/src/test/fixtures.ts frontend/app/api/figure-chain/ai/chains/explanations/[chainHash]/route.ts frontend/app/api/figure-chain/ai/runs/[runId]/route.ts frontend/src/hooks/use-chain-explanation.ts frontend/src/components/chain-explanation-panel.tsx frontend/src/components/chain-result.tsx frontend/tests/unit/api-client.test.ts frontend/tests/unit/chain-result.test.tsx frontend/tests/unit/chain-explanation-panel.test.tsx frontend/tests/unit/use-chain-explanation.test.tsx
git commit -m "feat: 前端展示已生成 AI 人物链解释"
```

## Task 6: Documentation And Final Validation

**Files:**

- Modify: `README.md`
- Modify: `tests/test_readme_commands.py`

- [ ] **Step 1: Add failing README tests**

Append to `tests/test_readme_commands.py`:

```python
def test_readme_documents_ai_chain_explanation_commands() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "figure-data generate-chain-explanation" in readme
    assert "figure-data inspect-chain-explanation" in readme
    assert "/api/v1/ai/chains/explanations/{chain_hash}" in readme
    assert "AI 人物链解释不会修改 encounter 或 Neo4j" in readme
```

- [ ] **Step 2: Run README tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/test_readme_commands.py -q
```

Expected:

```text
FAIL because README does not document AI chain explanation commands yet.
```

- [ ] **Step 3: Update README**

Add a section after AI candidate suggestion documentation:

````markdown
### AI 人物链解释

AI 人物链解释只解释已经审核并进入路径的 encounter。AI 人物链解释不会修改 encounter 或 Neo4j，不会替代 evidence，也不会让 `/api/v1/chains/shortest` 阻塞等待模型。

生成一条已审核路径的解释：

```powershell
$env:FIGURE_AI_ENABLED="true"
$env:FIGURE_AI_PROVIDER="fake"
$env:FIGURE_AI_MODEL="fake-history-model"
uv run --no-sync figure-data generate-chain-explanation --from "许几" --to "韩琦" --max-depth 12 --created-by lyl
```

查看解释和 AI run：

```powershell
uv run --no-sync figure-data inspect-chain-explanation --hash <chain_hash>
uv run --no-sync figure-data inspect-ai-run --id <run_id>
```

FastAPI 只读取已生成结果：

```text
GET /api/v1/ai/chains/explanations/{chain_hash}
GET /api/v1/ai/runs/{run_id}
```

前端查链成功后会使用返回的 `chain_hash` 读取已生成解释。解释不存在时，路径和证据详情仍正常展示。
````

- [ ] **Step 4: Run migrations and backend validation**

Run:

```powershell
uv run --no-sync python -m alembic upgrade head
uv run --no-sync python -m alembic current
uv run --no-sync python -m pytest tests/ai tests/db/test_ai_chain_explanation_model_metadata.py tests/db/test_ai_chain_explanation_migration.py tests/figure_chain tests/test_readme_commands.py -q
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync figure-data generate-chain-explanation --help
uv run --no-sync figure-data inspect-chain-explanation --help
```

Expected:

```text
alembic current shows 20260613_0003 (head).
pytest passes.
ruff passes.
mypy passes.
Both chain explanation help commands exit 0.
```

- [ ] **Step 5: Run frontend validation**

Run:

```powershell
npm --prefix frontend run test
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Expected:

```text
Frontend tests pass.
lint passes.
typecheck passes.
build passes.
```

- [ ] **Step 6: Run source safety validation**

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

If Neo4j is unavailable, record the service error and run `validate-graph` before merging.

- [ ] **Step 7: Manual fake-provider smoke**

Run:

```powershell
$env:FIGURE_AI_ENABLED="true"
$env:FIGURE_AI_PROVIDER="fake"
$env:FIGURE_AI_MODEL="fake-history-model"
uv run --no-sync figure-data generate-chain-explanation --from "许几" --to "韩琦" --max-depth 12 --created-by local-smoke
uv run --no-sync figure-data inspect-chain-explanation --hash <printed_chain_hash>
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
```

Expected:

```text
generate-chain-explanation prints ai_chain_explanation, ai_run, chain_hash, summary.
inspect-chain-explanation prints the stored explanation.
validate-encounters still passes.
validate-graph still passes.
No candidate, encounter, encounter_evidence, or Neo4j write is caused by AI explanation generation.
```

- [ ] **Step 8: Commit Task 6**

Run:

```powershell
git add README.md tests/test_readme_commands.py
git commit -m "docs: 说明 AI 人物链解释使用方式"
```

## Final Review Checklist

- [ ] `ai_chain_explanations` is in the `figure_data` schema.
- [ ] `ai_chain_explanations.ai_run_id` links to `ai_runs.id`.
- [ ] `chain_hash` includes source, target, max_depth, ordered encounter ids, prompt version, schema version, and language.
- [ ] `/api/v1/chains/shortest` does not call the model.
- [ ] `/api/v1/chains/shortest` returns `chain_hash` for found paths and `null` for no-path results.
- [ ] Chain explanation generation uses only reviewed path encounter details and evidence.
- [ ] Chain explanation output references only input encounter ids and source ref ids.
- [ ] Failed provider, schema, policy, or invalid context states leave a failed AI run.
- [ ] AI chain explanation generation does not update candidates.
- [ ] AI chain explanation generation does not update encounters.
- [ ] AI chain explanation generation does not update encounter_evidence.
- [ ] AI chain explanation generation does not write Neo4j.
- [ ] FastAPI AI endpoints are read-only.
- [ ] Frontend displays AI explanation as an optional layer and keeps path/evidence usable when explanation is missing.
- [ ] README documents commands, API endpoints, and safety boundary.

## Self-Review Notes

- Spec coverage: this plan covers Plan 3 from the stage 4 spec: chain explanation generation, `ai_chain_explanations`, read-only FastAPI endpoint, and optional frontend display.
- Scope boundary: this plan excludes API-triggered generation, no-path exploration, RAG, embedding, true provider SDKs, and batch generation.
- Plan 1/2 dependency: this plan explicitly requires durable failed `ai_runs` before starting, because chain explanation failures must be observable.
- Data safety: all AI writes remain in AI-specific tables. Existing human-reviewed encounter and graph projection rules remain unchanged.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-13-ai-chain-explanations.md`. Two execution options:

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
