from figure_data.db.base import Base
from figure_data.db.models import identity, import_batch, office, person, relationship, source


def test_models_use_figure_data_schema() -> None:
    modules = [import_batch, identity, office, person, relationship, source]
    assert modules

    for table in Base.metadata.tables.values():
        assert table.schema == "figure_data"


def test_relationship_candidates_have_stable_source_identity_constraint() -> None:
    table = Base.metadata.tables["figure_data.relationship_candidates"]
    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("source_name", "source_table", "source_pk") in constraint_columns
