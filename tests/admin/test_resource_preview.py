from figure_data.admin.resource_preview import build_resource_query_preview
from figure_data.admin.resource_query import ResourceFilter, ResourceQuery


def test_build_candidate_cli_preview() -> None:
    preview = build_resource_query_preview(
        ResourceQuery(
            resource="relationship_candidates",
            select=("id", "review_status"),
            filters=(ResourceFilter(field="review_status", operator="eq", value="unreviewed"),),
            order_by="id",
            order_direction="desc",
            limit=50,
            offset=0,
        )
    )

    assert preview == (
        "figure-data review-candidates --kind relationship "
        "--status unreviewed --limit 50"
    )


def test_build_generic_resource_preview() -> None:
    preview = build_resource_query_preview(
        ResourceQuery(
            resource="persons",
            select=("id", "primary_name_zh_hant"),
            filters=(ResourceFilter(field="primary_name_zh_hant", operator="ilike", value="蘇"),),
            order_by="id",
            order_direction="asc",
            limit=20,
            offset=0,
        )
    )

    assert preview == (
        "resource=persons select=id,primary_name_zh_hant "
        "where=primary_name_zh_hant ilike 蘇 order_by=id asc limit=20 offset=0"
    )
