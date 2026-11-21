"""Core engine for Order-Unbiased Debate Judge."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from debate_judge.models import DebateArgument, DebateVerdict, RubricScore, VerdictOutcome

JudgePassFn = Callable[
    [DebateArgument, DebateArgument, str],
    tuple[RubricScore, RubricScore, VerdictOutcome],
]

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "should", "that", "the", "to", "with",
}


def _extract_keywords(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {tok for tok in tokens if len(tok) > 2 and tok not in _STOPWORDS}


def _is_on_topic(motion: str, argument: DebateArgument) -> bool:
    motion_kw = _extract_keywords(motion)
    if not motion_kw:
        return True
    arg_text = " ".join(
        [argument.thesis, *argument.key_points, *argument.evidence, *argument.rebuttals]
    )
    arg_kw = _extract_keywords(arg_text)
    overlap = motion_kw & arg_kw
    required = 1 if len(motion_kw) <= 3 else max(2, len(motion_kw) // 3)
    return len(overlap) >= required


def _score_argument(
    motion: str,
    argument: DebateArgument,
    opponent: DebateArgument,
) -> RubricScore:
    evidence_score = min(10.0, 3.0 + 2.0 * len(argument.evidence))
    logic_score = min(10.0, 3.0 + 1.5 * len(argument.key_points) + (1.0 if len(argument.thesis) > 25 else 0.0))
    rebuttal_score = min(10.0, 2.5 + 2.5 * len(argument.rebuttals))

    on_topic = _is_on_topic(motion, argument)
    penalty = 0.0 if on_topic else 12.0

    # Small bonus if rebuttals reference opponent keywords
    opp_kw = _extract_keywords(" ".join(opponent.key_points + [opponent.thesis]))
    reb_kw = _extract_keywords(" ".join(argument.rebuttals))
    if opp_kw & reb_kw:
        rebuttal_score = min(10.0, rebuttal_score + 1.0)

    rationale = (
        f"Evidence={evidence_score:.1f}, Logic={logic_score:.1f}, "
        f"Rebuttal={rebuttal_score:.1f}; on_topic={on_topic}"
    )
    if not on_topic:
        rationale += f" (off-topic penalty -{penalty:.1f})"

    return RubricScore(
        evidence=round(evidence_score, 2),
        logic=round(logic_score, 2),
        rebuttal=round(rebuttal_score, 2),
        on_topic=on_topic,
        off_topic_penalty=penalty,
        rationale=rationale,
    )


def default_judge_pass(
    first: DebateArgument,
    second: DebateArgument,
    order_label: str,
) -> tuple[RubricScore, RubricScore, VerdictOutcome]:
    """Evaluate two arguments presented in a specific order using the rubric."""
    score_first = _score_argument(first.motion, first, second)
    score_second = _score_argument(second.motion, second, first)

    if first.stance == "propose":
        propose_score, oppose_score = score_first, score_second
    else:
        propose_score, oppose_score = score_second, score_first

    if propose_score.total > oppose_score.total:
        winner: VerdictOutcome = "propose"
    elif oppose_score.total > propose_score.total:
        winner = "oppose"
    else:
        winner = "tie"

    return propose_score, oppose_score, winner


class OrderUnbiasedDebateJudge:
    """Dual-pass debate judge that detects positional preference bias."""

    def __init__(self, judge_pass_fn: JudgePassFn | None = None) -> None:
        self._judge_pass_fn = judge_pass_fn or default_judge_pass

    @staticmethod
    def validate_pair(propose: DebateArgument, oppose: DebateArgument) -> str:
        """Ensure both arguments share the exact same motion and opposite stances."""
        if propose.stance != "propose":
            raise ValueError(f"Expected propose stance, got {propose.stance!r}")
        if oppose.stance != "oppose":
            raise ValueError(f"Expected oppose stance, got {oppose.stance!r}")

        p_motion = propose.motion.strip()
        o_motion = oppose.motion.strip()
        if not p_motion or p_motion != o_motion:
            raise ValueError(
                f"Motion mismatch: propose={p_motion!r} vs oppose={o_motion!r}"
            )
        return p_motion

    def build_default_arguments(self, motion: str) -> tuple[DebateArgument, DebateArgument]:
        """Generate structured propose and oppose arguments for local CLI demos."""
        clean_motion = motion.strip()
        propose = DebateArgument(
            motion=clean_motion,
            stance="propose",
            thesis=f"Adopting '{clean_motion}' delivers measurable safeguards and accountability.",
            key_points=[
                f"Establishes clear governance standards for {clean_motion}.",
                "Reduces systemic risk through transparent auditing and compliance.",
                "Aligns cross-border incentives around shared safety benchmarks.",
            ],
            evidence=[
                "Independent audits in high-stakes industries reduce failure rates.",
                "Standardized reporting enables early detection of cascading failures.",
            ],
            rebuttals=[
                "Well-scoped rules preserve innovation via tiered compliance.",
            ],
        )
        oppose = DebateArgument(
            motion=clean_motion,
            stance="oppose",
            thesis=f"Mandating '{clean_motion}' risks stifling innovation and creating bureaucratic bottlenecks.",
            key_points=[
                f"Centralized mandates around {clean_motion} lag behind rapid technical change.",
                "Compliance overhead disproportionately harms smaller teams and open research.",
            ],
            evidence=[
                "Rigid licensing regimes historically slow open-source iteration.",
            ],
            rebuttals=[
                "Targeted sector-level enforcement addresses harms without global bottlenecks.",
            ],
        )
        return propose, oppose

    def judge(
        self,
        propose: DebateArgument,
        oppose: DebateArgument,
        output_dir: str | Path | None = None,
    ) -> DebateVerdict:
        """Run dual-pass order-swapped judging and optionally emit markdown artifacts."""
        motion = self.validate_pair(propose, oppose)

        # Pass 1: Propose presented first, Oppose second
        p1_propose, p1_oppose, pass_1_winner = self._judge_pass_fn(
            propose, oppose, "propose_first"
        )

        # Pass 2: Oppose presented first, Propose second (order-swapped)
        p2_propose, p2_oppose, pass_2_winner = self._judge_pass_fn(
            oppose, propose, "oppose_first"
        )

        positional_bias_detected = pass_1_winner != pass_2_winner

        avg_propose = RubricScore(
            evidence=round((p1_propose.evidence + p2_propose.evidence) / 2, 2),
            logic=round((p1_propose.logic + p2_propose.logic) / 2, 2),
            rebuttal=round((p1_propose.rebuttal + p2_propose.rebuttal) / 2, 2),
            on_topic=p1_propose.on_topic and p2_propose.on_topic,
            off_topic_penalty=round(
                (p1_propose.off_topic_penalty + p2_propose.off_topic_penalty) / 2, 2
            ),
            rationale=f"Pass 1: {p1_propose.rationale} | Pass 2: {p2_propose.rationale}",
        )
        avg_oppose = RubricScore(
            evidence=round((p1_oppose.evidence + p2_oppose.evidence) / 2, 2),
            logic=round((p1_oppose.logic + p2_oppose.logic) / 2, 2),
            rebuttal=round((p1_oppose.rebuttal + p2_oppose.rebuttal) / 2, 2),
            on_topic=p1_oppose.on_topic and p2_oppose.on_topic,
            off_topic_penalty=round(
                (p1_oppose.off_topic_penalty + p2_oppose.off_topic_penalty) / 2, 2
            ),
            rationale=f"Pass 1: {p1_oppose.rationale} | Pass 2: {p2_oppose.rationale}",
        )

        if positional_bias_detected:
            if avg_propose.total > avg_oppose.total:
                winner: VerdictOutcome = "propose"
            elif avg_oppose.total > avg_propose.total:
                winner = "oppose"
            else:
                winner = "tie"
            rationale = (
                f"Positional bias detected: Pass 1 favored {pass_1_winner}, "
                f"while order-swapped Pass 2 favored {pass_2_winner}. "
                f"Resolved via averaged rubric totals (Propose={avg_propose.total:.2f}, "
                f"Oppose={avg_oppose.total:.2f})."
            )
        else:
            winner = pass_1_winner
            rationale = (
                f"Consistent verdict across both presentation orders ({winner}). "
                f"Averaged rubric totals: Propose={avg_propose.total:.2f}, "
                f"Oppose={avg_oppose.total:.2f}."
            )

        verdict = DebateVerdict(
            motion=motion,
            winner=winner,
            propose_score=avg_propose,
            oppose_score=avg_oppose,
            pass_1_winner=pass_1_winner,
            pass_2_winner=pass_2_winner,
            positional_bias_detected=positional_bias_detected,
            decision_rationale=rationale,
        )

        if output_dir is not None:
            verdict.artifacts_written = self.write_artifacts(
                propose=propose,
                oppose=oppose,
                verdict=verdict,
                output_dir=output_dir,
            )

        return verdict

    @staticmethod
    def write_artifacts(
        propose: DebateArgument,
        oppose: DebateArgument,
        verdict: DebateVerdict,
        output_dir: str | Path,
    ) -> list[str]:
        """Write propose.md, oppose.md, and decide.md to output_dir."""
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)

        propose_path = target / "propose.md"
        oppose_path = target / "oppose.md"
        decide_path = target / "decide.md"

        propose_path.write_text(propose.to_markdown(), encoding="utf-8")
        oppose_path.write_text(oppose.to_markdown(), encoding="utf-8")
        decide_path.write_text(verdict.to_markdown(), encoding="utf-8")

        return [str(propose_path), str(oppose_path), str(decide_path)]
