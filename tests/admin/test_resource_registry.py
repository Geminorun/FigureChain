from figure_data.admin.resource_registry import (
    get_resource_definition,
    list_resource_definitions,
)


def test_registry_exposes_first_batch_resources() -> None:
    resources = {resource.name for resource in list_resource_definitions()}

    assert resources == {
        "relationship_candidates",
        "kinship_candidates",
        "encounters",
        "encounter_evidence",
        "persons",
        "source_refs",
        "source_works",
        "ai_generation_jobs",
        "ai_job_events",
        "graph_projection_batches",
        "admin_operations",
    }


def test_relationship_candidate_links_are_explicit() -> None:
    resource = get_resource_definition("relationship_candidates")
    links = {column.name: column.link for column in resource.columns}

    assert links["id"] == "candidate:relationship"
    assert links["person_a_id"] == "person"
    assert links["person_b_id"] == "person"
    assert links["promoted_encounter_id"] == "encounter"


def test_registry_rejects_unknown_resource() -> None:
    try:
        get_resource_definition("raw_sql")
    except KeyError as exc:
        assert "raw_sql" in str(exc)
    else:
        raise AssertionError("unknown resources must fail closed")
