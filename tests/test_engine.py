"""Pytest suite for Order-Unbiased Debate Judge."""

from __future__ import annotations

from pathlib import Path

import pytest

from debate_judge import DebateArgument, OrderUnbiasedDebateJudge, RubricScore


def _make_pair(motion: str = "AI agents should be audited before deployment") -> tuple[DebateArgument, DebateArgument]:
    propose = DebateArgument(
        motion=motion,
        stance="propose",
        thesis="Mandatory audits before AI agent deployment prevent cascading failures.",
        key_points=[
            "Independent audits verify agent safety before production deployment.",
            "Standardized audit logs improve accountability across vendors.",
        ],
        evidence=[
            "Pre-deployment red-teaming catches prompt-injection regressions early.",
            "Aviation and finance rely on pre-release audits to bound tail risk.",
        ],
        rebuttals=[
            "Tiered audits keep deployment fast for low-risk internal agents.",
        ],
    )
    oppose = DebateArgument(
        motion=motion,
        stance="oppose",
        thesis="Blanket pre-deployment audits slow AI agent iteration without guaranteeing safety.",
        key_points=[
            "Static audits age quickly as models and toolchains evolve.",
        ],
        evidence=[
            "Continuous runtime monitoring detects drift missed by one-time audits.",
        ],
        rebuttals=[
            "Post-deployment telemetry catches emergent agent failures faster.",
        ],
    )
    return propose, oppose


def test_judge_receives_both_contexts_and_enforces_same_motion() -> None:
    seen_calls: list[tuple[str, str, str]] = []

    def recording_pass(first: DebateArgument, second: DebateArgument, order_label: str):
        seen_calls.append((first.stance, second.stance, order_label))
        p_score = RubricScore(evidence=8.0, logic=8.0, rebuttal=7.0)
        o_score = RubricScore(evidence=6.0, logic=6.0, rebuttal=6.0)
        return p_score, o_score, "propose"

    propose, oppose = _make_pair()
    judge = OrderUnbiasedDebateJudge(judge_pass_fn=recording_pass)
    verdict = judge.judge(propose, oppose)

    assert len(seen_calls) == 2
    assert seen_calls[0] == ("propose", "oppose", "propose_first")
    assert seen_calls[1] == ("oppose", "propose", "oppose_first")
    assert verdict.winner == "propose"
    assert not verdict.positional_bias_detected

    mismatched_oppose = oppose.model_copy(update={"motion": "Different unrelated motion"})
    with pytest.raises(ValueError, match="Motion mismatch"):
        judge.judge(propose, mismatched_oppose)


def test_order_swap_inconsistency_flagged_as_positional_bias() -> None:
    def first_position_biased_pass(first: DebateArgument, second: DebateArgument, order_label: str):
        # Always favors whichever argument appears first
        if first.stance == "propose":
            return (
                RubricScore(evidence=9.0, logic=9.0, rebuttal=8.0),
                RubricScore(evidence=6.0, logic=6.0, rebuttal=6.0),
                "propose",
            )
        return (
            RubricScore(evidence=6.0, logic=6.0, rebuttal=6.0),
            RubricScore(evidence=9.0, logic=9.0, rebuttal=8.0),
            "oppose",
        )

    propose, oppose = _make_pair()
    judge = OrderUnbiasedDebateJudge(judge_pass_fn=first_position_biased_pass)
    verdict = judge.judge(propose, oppose)

    assert verdict.pass_1_winner == "propose"
    assert verdict.pass_2_winner == "oppose"
    assert verdict.positional_bias_detected is True
    assert verdict.winner == "tie"
    assert "Positional bias detected" in verdict.decision_rationale


def test_off_topic_argument_penalized_by_rubric() -> None:
    motion = "AI agents should be regulated by an international oversight body"
    propose, _ = _make_pair(motion=motion)
    off_topic_oppose = DebateArgument(
        motion=motion,
        stance="oppose",
        thesis="Sourdough fermentation depends on ambient kitchen temperature.",
        key_points=[
            "Wild yeast cultures thrive with regular flour hydration.",
            "Cold proofing deepens crust blister formation.",
        ],
        evidence=[
            "Bakers track dough pH during bulk fermentation.",
        ],
        rebuttals=[
            "Steam injection improves oven spring.",
        ],
    )

    judge = OrderUnbiasedDebateJudge()
    verdict = judge.judge(propose, off_topic_oppose)

    assert verdict.propose_score.on_topic is True
    assert verdict.oppose_score.on_topic is False
    assert verdict.oppose_score.off_topic_penalty > 0.0
    assert verdict.propose_score.total > verdict.oppose_score.total
    assert verdict.winner == "propose"


def test_markdown_artifacts_written_non_empty(tmp_path: Path) -> None:
    judge = OrderUnbiasedDebateJudge()
    propose, oppose = judge.build_default_arguments(
        "AI agents should be regulated by an international oversight body"
    )
    verdict = judge.judge(propose, oppose, output_dir=tmp_path)

    expected_files = ["propose.md", "oppose.md", "decide.md"]
    assert len(verdict.artifacts_written) == 3

    for filename in expected_files:
        artifact = tmp_path / filename
        assert artifact.exists(), f"Missing {filename}"
        content = artifact.read_text(encoding="utf-8").strip()
        assert len(content) > 0, f"Empty {filename}"
