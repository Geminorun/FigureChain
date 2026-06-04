from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateClassification:
    strength: str
    basis: str


ASSOCIATION_CLASSIFICATION: dict[int, CandidateClassification] = {
    339: CandidateClassification("high", "direct_interaction_likely"),
    340: CandidateClassification("high", "direct_interaction_likely"),
    634: CandidateClassification("high", "direct_interaction_likely"),
    635: CandidateClassification("high", "direct_interaction_likely"),
    108: CandidateClassification("high", "direct_interaction_likely"),
    49: CandidateClassification("high", "direct_interaction_likely"),
    50: CandidateClassification("high", "direct_interaction_likely"),
    95: CandidateClassification("high", "direct_interaction_likely"),
    158: CandidateClassification("high", "direct_interaction_likely"),
    159: CandidateClassification("high", "direct_interaction_likely"),
    156: CandidateClassification("high", "direct_interaction_likely"),
    157: CandidateClassification("high", "direct_interaction_likely"),
    404: CandidateClassification("high", "co_presence_likely"),
    22: CandidateClassification("high", "direct_interaction_likely"),
    23: CandidateClassification("high", "direct_interaction_likely"),
    36: CandidateClassification("high", "direct_interaction_likely"),
    37: CandidateClassification("high", "direct_interaction_likely"),
    19: CandidateClassification("high", "direct_interaction_likely"),
    20: CandidateClassification("high", "direct_interaction_likely"),
    130: CandidateClassification("high", "direct_interaction_likely"),
    131: CandidateClassification("high", "direct_interaction_likely"),
    197: CandidateClassification("medium", "co_presence_likely"),
    268: CandidateClassification("medium", "co_presence_likely"),
    117: CandidateClassification("medium", "co_presence_likely"),
    120: CandidateClassification("medium", "co_presence_likely"),
    13: CandidateClassification("medium", "unknown"),
    14: CandidateClassification("medium", "unknown"),
    11: CandidateClassification("medium", "unknown"),
    12: CandidateClassification("medium", "unknown"),
    15: CandidateClassification("medium", "unknown"),
    16: CandidateClassification("medium", "unknown"),
    429: CandidateClassification("not_applicable", "textual_or_indirect"),
    430: CandidateClassification("not_applicable", "textual_or_indirect"),
    437: CandidateClassification("not_applicable", "textual_or_indirect"),
    438: CandidateClassification("not_applicable", "textual_or_indirect"),
    43: CandidateClassification("not_applicable", "textual_or_indirect"),
    44: CandidateClassification("not_applicable", "textual_or_indirect"),
    32: CandidateClassification("not_applicable", "textual_or_indirect"),
    33: CandidateClassification("not_applicable", "textual_or_indirect"),
    132: CandidateClassification("not_applicable", "textual_or_indirect"),
    133: CandidateClassification("not_applicable", "textual_or_indirect"),
}

KINSHIP_CLOSE_HIGH = {75, 111, 134, 135}


def classify_association_code(code: int | None) -> CandidateClassification:
    if code is None:
        return CandidateClassification("low", "unknown")
    return ASSOCIATION_CLASSIFICATION.get(code, CandidateClassification("low", "unknown"))


def classify_kinship_code(
    code: int | None,
    *,
    label_zh: str | None,
    upstep: int | None,
    downstep: int | None,
    marstep: int | None,
) -> CandidateClassification:
    if code in KINSHIP_CLOSE_HIGH:
        return CandidateClassification("high", "family_close")
    close_tokens = ["父", "母", "子", "女", "兄", "弟", "姊", "妹", "妻", "夫"]
    if label_zh and any(token in label_zh for token in close_tokens):
        return CandidateClassification("high", "family_close")
    if upstep is not None and upstep >= 3:
        return CandidateClassification("background", "family_distant")
    if marstep is not None and marstep > 0:
        return CandidateClassification("medium", "family_close")
    if downstep is not None and downstep >= 3:
        return CandidateClassification("background", "family_distant")
    return CandidateClassification("not_applicable", "unknown")
