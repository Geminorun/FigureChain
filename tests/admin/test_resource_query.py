from dataclasses import dataclass, field
from typing import Any

from figure_data.admin.resource_query import ResourceFilter, ResourceQuery, execute_resource_query


@dataclass
class FakeResult:
    rows: list[dict[str, object]]

    def mappings(self) -> "FakeResult":
        return self

    def all(self) -> list[dict[str, object]]:
        return self.rows


@dataclass
class FakeSession:
    statements: list[str] = field(default_factory=list)
    params: list[dict[str, Any]] = field(default_factory=list)

    def execute(self, statement: object, params: dict[str, Any]) -> FakeResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return FakeResult([{"id": "person-1", "primary_name_zh_hant": "蘇軾"}])


def test_execute_resource_query_uses_registered_columns_only() -> None:
    session = FakeSession()

    result = execute_resource_query(
        session,
        ResourceQuery(
            resource="persons",
            select=("id", "primary_name_zh_hant"),
            filters=(ResourceFilter(field="primary_name_zh_hant", operator="ilike", value="蘇"),),
            order_by="id",
            order_direction="asc",
            limit=50,
            offset=0,
        ),
    )

    assert result.resource == "persons"
    assert result.rows == [{"id": "person-1", "primary_name_zh_hant": "蘇軾"}]
    assert "figure_data.persons" in session.statements[0]
    assert "primary_name_zh_hant ilike :filter_0" in session.statements[0]
    assert session.params[0]["filter_0"] == "%蘇%"


def test_execute_resource_query_rejects_unknown_field() -> None:
    session = FakeSession()

    try:
        execute_resource_query(
            session,
            ResourceQuery(
                resource="persons",
                select=("id", "password_hash"),
                filters=(),
                order_by="id",
                order_direction="asc",
                limit=50,
                offset=0,
            ),
        )
    except ValueError as exc:
        assert "password_hash" in str(exc)
    else:
        raise AssertionError("unknown fields must fail closed")


def test_execute_resource_query_clamps_limit_to_200() -> None:
    session = FakeSession()

    execute_resource_query(
        session,
        ResourceQuery(
            resource="persons",
            select=("id",),
            filters=(),
            order_by="id",
            order_direction="asc",
            limit=1000,
            offset=0,
        ),
    )

    assert session.params[0]["limit"] == 200
