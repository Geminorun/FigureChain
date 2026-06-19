from pathlib import Path

from figure_data.ai.real_provider_evaluation import load_stage5d_evaluation_fixture


def test_load_stage5d_evaluation_fixture() -> None:
    fixture = load_stage5d_evaluation_fixture(
        Path("docs/superpowers/fixtures/stage5d-real-provider-eval-small.json")
    )

    assert len(fixture.samples) >= 3
    assert {sample.sample_type for sample in fixture.samples} >= {
        "candidate_review_suggestion",
        "chain_explanation",
        "no_path_exploration",
    }
