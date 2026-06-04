from figure_data.cbdb.classification import classify_association_code, classify_kinship_code


def test_classify_association_direct_visit() -> None:
    result = classify_association_code(339)

    assert result.strength == "high"
    assert result.basis == "direct_interaction_likely"


def test_classify_association_letter_as_not_applicable() -> None:
    result = classify_association_code(429)

    assert result.strength == "not_applicable"
    assert result.basis == "textual_or_indirect"


def test_unknown_association_defaults_to_low_unknown() -> None:
    result = classify_association_code(999999)

    assert result.strength == "low"
    assert result.basis == "unknown"


def test_classify_kinship_parent() -> None:
    result = classify_kinship_code(75, label_zh="父", upstep=1, downstep=0, marstep=0)

    assert result.strength == "high"
    assert result.basis == "family_close"
