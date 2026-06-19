# Real Provider Config Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加安全的 OpenAI-compatible 真实 Provider 适配器，并保持 fake provider 作为默认测试路径。

**Architecture:** `figure_data.ai` 继续提供统一 provider protocol，真实 provider 只通过 `create_ai_provider(settings)` 创建。真实调用必须显式开启，provider adapter 负责 HTTP 调用、错误映射和 redaction；业务 service 仍只依赖 `AIProvider` protocol。

**Tech Stack:** Python 3.12、Pydantic Settings、httpx、pytest、ruff、mypy。

---

## Reference

- `docs/superpowers/specs/2026-06-19-real-ai-provider-jobs-observability-design.md`
- `src/figure_data/ai/provider.py`
- `src/figure_data/ai/service.py`
- `src/figure_data/ai/types.py`
- `src/figure_data/config.py`
- `tests/ai/test_provider.py`
- `tests/test_config.py`

## Scope

本计划只接入真实 provider 的配置、HTTP adapter、错误映射和安全 redaction。不接入 Redis/RQ worker，不新增数据库迁移，不改变 AI job 状态机。

## File Structure

Create:

- `src/figure_data/ai/openai_compatible_provider.py`：OpenAI-compatible HTTP provider adapter。
- `src/figure_data/ai/redaction.py`：日志、异常和 metadata 的敏感信息清理工具。
- `tests/ai/test_openai_compatible_provider.py`：真实 provider adapter 单元测试，使用 fake HTTP client。
- `tests/ai/test_redaction.py`：redaction 单元测试。

Modify:

- `pyproject.toml`：把 `httpx` 加入运行时依赖。
- `src/figure_data/config.py`：新增真实 provider 二次开关和 provider 默认值。
- `src/figure_data/ai/types.py`：扩展 provider request/response metadata。
- `src/figure_data/ai/errors.py`：增加可识别的 provider timeout/rate-limit/configuration 错误类型。
- `src/figure_data/ai/provider.py`：接入 `openai_compatible` provider factory。
- `tests/test_config.py`：覆盖新增配置默认值和 env override。
- `tests/ai/test_provider.py`：覆盖真实 provider 未显式开启时失败、fake provider 不受影响。

## Task 1: Add Runtime Dependency And Settings

**Files:**

- Modify: `pyproject.toml`
- Modify: `src/figure_data/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Add tests in `tests/test_config.py`:

```python
def test_ai_real_provider_defaults_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    settings = Settings()

    assert settings.ai_provider is None
    assert settings.ai_allow_real_provider is False
    assert settings.ai_timeout_seconds == 30.0


def test_ai_real_provider_env_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("FIGURE_AI_ENABLED", "true")
    monkeypatch.setenv("FIGURE_AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("FIGURE_AI_ALLOW_REAL_PROVIDER", "true")
    monkeypatch.setenv("FIGURE_AI_MODEL", "gpt-test")
    monkeypatch.setenv("FIGURE_AI_API_KEY", "test-key")
    monkeypatch.setenv("FIGURE_AI_BASE_URL", "https://example.test/v1")

    settings = Settings()

    assert settings.ai_enabled is True
    assert settings.ai_provider == "openai_compatible"
    assert settings.ai_allow_real_provider is True
    assert settings.ai_model == "gpt-test"
    assert settings.ai_api_key == "test-key"
    assert settings.ai_base_url == "https://example.test/v1"
```

- [ ] **Step 2: Run failing config tests**

Run:

```powershell
uv run --no-sync pytest tests/test_config.py -q
```

Expected: fails because `Settings.ai_allow_real_provider` does not exist.

- [ ] **Step 3: Add runtime dependency**

Move `httpx>=0.28.0` from `dependency-groups.dev` into `[project].dependencies` in `pyproject.toml`, because the provider adapter will use it at runtime.

- [ ] **Step 4: Add settings field**

In `src/figure_data/config.py`, add:

```python
ai_allow_real_provider: bool = Field(
    default=False,
    alias="FIGURE_AI_ALLOW_REAL_PROVIDER",
)
```

Keep `FIGURE_AI_API_KEY` and `FIGURE_AI_BASE_URL` optional and normalized by the existing validator.

- [ ] **Step 5: Run config tests**

Run:

```powershell
uv run --no-sync pytest tests/test_config.py -q
```

Expected: all config tests pass.

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml src/figure_data/config.py tests/test_config.py
git commit -m "feat: 增加真实 AI provider 配置开关"
```

## Task 2: Extend Provider Types, Errors, And Redaction

**Files:**

- Create: `src/figure_data/ai/redaction.py`
- Modify: `src/figure_data/ai/types.py`
- Modify: `src/figure_data/ai/errors.py`
- Test: `tests/ai/test_redaction.py`
- Test: `tests/ai/test_provider.py`

- [ ] **Step 1: Write redaction tests**

Create `tests/ai/test_redaction.py`:

```python
from figure_data.ai.redaction import redact_sensitive_text, redacted_metadata


def test_redact_sensitive_text_removes_known_secrets() -> None:
    text = "Authorization: Bearer sk-secret\nREDIS_URL=redis://host:6379\nok"

    result = redact_sensitive_text(text)

    assert "sk-secret" not in result
    assert "redis://host:6379" not in result
    assert "[REDACTED]" in result


def test_redacted_metadata_drops_headers_and_masks_keys() -> None:
    result = redacted_metadata(
        {
            "request_id": "req-1",
            "headers": {"Authorization": "Bearer sk-secret"},
            "api_key": "sk-secret",
            "usage": {"total_tokens": 9},
        }
    )

    assert result["request_id"] == "req-1"
    assert result["api_key"] == "[REDACTED]"
    assert "headers" not in result
    assert result["usage"] == {"total_tokens": 9}
```

- [ ] **Step 2: Write provider type tests**

Add to `tests/ai/test_provider.py`:

```python
from figure_data.ai.types import AIProviderResponse, TokenUsage


def test_ai_provider_response_accepts_optional_metadata() -> None:
    response = AIProviderResponse(
        raw_text='{"ok":true}',
        provider="fake",
        model_name="fake-model",
        provider_request_id="req-1",
        latency_ms=25,
        token_usage=TokenUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
        metadata={"safe": "value"},
    )

    assert response.provider_request_id == "req-1"
    assert response.token_usage is not None
    assert response.token_usage.total_tokens == 7
```

- [ ] **Step 3: Run failing tests**

```powershell
uv run --no-sync pytest tests/ai/test_redaction.py tests/ai/test_provider.py -q
```

Expected: fails because redaction module and response metadata types do not exist.

- [ ] **Step 4: Add provider metadata types**

Modify `src/figure_data/ai/types.py`:

```python
@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class AIProviderResponse:
    raw_text: str
    provider: str
    model_name: str
    provider_request_id: str | None = None
    latency_ms: int | None = None
    token_usage: TokenUsage | None = None
    metadata: dict[str, object] | None = None
```

Preserve the existing `AIProviderRequest` fields.

- [ ] **Step 5: Add provider error classes**

Modify `src/figure_data/ai/errors.py`:

```python
class AIProviderTimeoutError(AIProviderError):
    """Raised when the provider request times out."""


class AIProviderRateLimitError(AIProviderError):
    """Raised when the provider returns a rate-limit response."""


class AIProviderUnavailableError(AIProviderError):
    """Raised when the provider is unavailable or returns a retryable server error."""
```

- [ ] **Step 6: Add redaction helpers**

Create `src/figure_data/ai/redaction.py` with:

```python
from __future__ import annotations

import re
from collections.abc import Mapping

SENSITIVE_KEYS = {"authorization", "api_key", "apikey", "token", "password", "secret"}
SECRET_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"redis://[^\s]+", re.IGNORECASE),
    re.compile(r"postgresql(?:\+psycopg)?://[^\s]+", re.IGNORECASE),
]


def redact_sensitive_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def redacted_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in metadata.items():
        normalized = key.lower()
        if normalized == "headers":
            continue
        if any(secret_key in normalized for secret_key in SENSITIVE_KEYS):
            result[key] = "[REDACTED]"
        elif isinstance(value, str):
            result[key] = redact_sensitive_text(value)
        else:
            result[key] = value
    return result
```

- [ ] **Step 7: Run tests**

```powershell
uv run --no-sync pytest tests/ai/test_redaction.py tests/ai/test_provider.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```powershell
git add src/figure_data/ai/types.py src/figure_data/ai/errors.py src/figure_data/ai/redaction.py tests/ai/test_redaction.py tests/ai/test_provider.py
git commit -m "feat: 扩展 AI provider 元数据与脱敏工具"
```

## Task 3: Implement OpenAI-Compatible Provider Adapter

**Files:**

- Create: `src/figure_data/ai/openai_compatible_provider.py`
- Test: `tests/ai/test_openai_compatible_provider.py`

- [ ] **Step 1: Write adapter tests**

Create `tests/ai/test_openai_compatible_provider.py` with fake HTTP client objects that cover:

```python
def test_openai_compatible_provider_parses_chat_completion() -> None:
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        timeout_seconds=30.0,
        http_client=FakeHTTPClient(
            status_code=200,
            payload={
                "id": "chatcmpl-1",
                "choices": [{"message": {"content": '{"message":"ok"}'}}],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 4,
                    "total_tokens": 7,
                },
            },
        ),
    )

    response = provider.generate(
        AIProviderRequest(
            system_prompt="system",
            user_prompt="user",
            model_name="gpt-test",
            max_output_tokens=128,
        )
    )

    assert response.raw_text == '{"message":"ok"}'
    assert response.provider == "openai_compatible"
    assert response.provider_request_id == "chatcmpl-1"
    assert response.token_usage is not None
    assert response.token_usage.total_tokens == 7
```

Also cover:

- HTTP 429 raises `AIProviderRateLimitError`.
- HTTP 500 raises `AIProviderUnavailableError`.
- timeout raises `AIProviderTimeoutError`.
- malformed payload raises `AIProviderUnavailableError`.
- error messages do not include API key.

- [ ] **Step 2: Run failing adapter tests**

```powershell
uv run --no-sync pytest tests/ai/test_openai_compatible_provider.py -q
```

Expected: fails because the adapter module does not exist.

- [ ] **Step 3: Create adapter**

Implement `src/figure_data/ai/openai_compatible_provider.py`:

```python
class OpenAICompatibleProvider:
    provider_name = "openai_compatible"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        http_client: HTTPClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._http_client = http_client or httpx.Client(timeout=timeout_seconds)

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        started = time.monotonic()
        payload = {
            "model": request.model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "max_tokens": request.max_output_tokens,
            "temperature": 0,
        }
        try:
            response = self._http_client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
        except TimeoutException as exc:
            raise AIProviderTimeoutError("provider request timed out") from exc
        except Exception as exc:
            raise AIProviderUnavailableError(redact_sensitive_text(str(exc))) from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        return self._parse_response(response, request, latency_ms)
```

Use helper functions to parse `choices[0].message.content`, `id`, and `usage`. Keep helpers private.

- [ ] **Step 4: Run adapter tests**

```powershell
uv run --no-sync pytest tests/ai/test_openai_compatible_provider.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/figure_data/ai/openai_compatible_provider.py tests/ai/test_openai_compatible_provider.py
git commit -m "feat: 增加 OpenAI compatible provider"
```

## Task 4: Wire Provider Factory And Safety Gates

**Files:**

- Modify: `src/figure_data/ai/provider.py`
- Test: `tests/ai/test_provider.py`

- [ ] **Step 1: Write factory tests**

Add to `tests/ai/test_provider.py`:

```python
def test_real_provider_requires_explicit_allow_flag() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        FIGURE_AI_ENABLED=True,
        FIGURE_AI_PROVIDER="openai_compatible",
        FIGURE_AI_MODEL="gpt-test",
        FIGURE_AI_API_KEY="test-key",
        FIGURE_AI_BASE_URL="https://example.test/v1",
    )

    with pytest.raises(AIProviderConfigurationError):
        create_ai_provider(settings)


def test_real_provider_requires_api_key() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        FIGURE_AI_ENABLED=True,
        FIGURE_AI_PROVIDER="openai_compatible",
        FIGURE_AI_ALLOW_REAL_PROVIDER=True,
        FIGURE_AI_MODEL="gpt-test",
        FIGURE_AI_BASE_URL="https://example.test/v1",
    )

    with pytest.raises(AIProviderConfigurationError):
        create_ai_provider(settings)
```

- [ ] **Step 2: Run failing factory tests**

```powershell
uv run --no-sync pytest tests/ai/test_provider.py -q
```

Expected: fails because factory does not support `openai_compatible`.

- [ ] **Step 3: Update provider factory**

Modify `src/figure_data/ai/provider.py`:

```python
if settings.ai_provider == "openai_compatible":
    if not settings.ai_allow_real_provider:
        raise AIProviderConfigurationError("real AI provider is not explicitly allowed")
    if settings.ai_api_key is None:
        raise AIProviderConfigurationError("FIGURE_AI_API_KEY is required")
    if settings.ai_base_url is None:
        raise AIProviderConfigurationError("FIGURE_AI_BASE_URL is required")
    return OpenAICompatibleProvider(
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
        timeout_seconds=settings.ai_timeout_seconds,
    )
```

Keep fake and disabled branches unchanged.

- [ ] **Step 4: Run factory tests**

```powershell
uv run --no-sync pytest tests/ai/test_provider.py tests/ai/test_openai_compatible_provider.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/figure_data/ai/provider.py tests/ai/test_provider.py
git commit -m "feat: 接入真实 AI provider 工厂"
```

## Task 5: Verify Plan 1

**Files:**

- Modify only files touched by Tasks 1-4.

- [ ] **Step 1: Run focused backend tests**

```powershell
uv run --no-sync pytest tests/test_config.py tests/ai/test_provider.py tests/ai/test_openai_compatible_provider.py tests/ai/test_redaction.py -q
```

Expected: pass.

- [ ] **Step 2: Run static checks**

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected: both pass.

- [ ] **Step 3: Confirm no real provider call in tests**

Search test output and code:

```powershell
rg -n "FIGURE_AI_ALLOW_REAL_PROVIDER|openai_compatible|httpx.Client" tests src/figure_data/ai
```

Expected: tests use fake HTTP client; no test requires external network.

- [ ] **Step 4: Commit final fixes if needed**

If verification required fixes:

```powershell
git add pyproject.toml src/figure_data tests
git commit -m "test: 补充真实 provider 安全回归"
```

If no fixes were needed, do not create an empty commit.
