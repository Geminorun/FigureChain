from figure_data.importing.context import ImportContext
from figure_data.importing.relationships import transform_relationship_row


def test_transform_relationship_row_sets_classification_and_review_status() -> None:
    context = ImportContext(source_name="cbdb", source_snapshot="cbdb_20260530")
    row = {
        "c_assoc_id": 1,
        "c_personid": 25403,
        "c_assoc_id2": 21204,
        "c_assoc_code": 95,
        "c_assoc_year": 231,
        "c_source": 1,
        "c_pages": "1a",
        "c_notes": "sample",
    }

    record = transform_relationship_row(row, context)

    assert record["candidate_strength"] == "high"
    assert record["candidate_basis"] == "direct_interaction_likely"
    assert record["review_status"] == "unreviewed"
    assert record["source_pk"] == "c_assoc_id=1"
