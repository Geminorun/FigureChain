from __future__ import annotations

from opencc import OpenCC  # type: ignore[import-untyped]

_OPENCC = OpenCC("t2s")
_NULL_INT_VALUES = {"", "0", "-9999", "None", "none", "NULL", "null"}


def normalize_int(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in _NULL_INT_VALUES:
        return None
    return int(text)


def normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def to_simplified(value: str | None) -> str | None:
    if value is None:
        return None
    return _OPENCC.convert(value)


def build_search_name(value: str | None) -> str | None:
    if value is None:
        return None
    compact = "".join(value.split())
    return compact.lower() or None
