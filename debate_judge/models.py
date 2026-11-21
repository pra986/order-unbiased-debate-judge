"""Data contracts for the Order-Unbiased Debate Judge."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Stance = Literal["propose", "oppose"]
VerdictOutcome = Literal["propose", "oppose", "tie"]


class DebateArgument(BaseModel):
    """Structured argument generated for a single debate stance."""

    motion: str = Field(..., min_length=1, description="Exact debate motion.")
    stance: Stance = Field(..., description="Debate side: propose or oppose.")
    thesis: str = Field(..., min_length=1, description="Core position statement.")
    key_points: list[str] = Field(
        default_factory=list,
        description="Primary structured arguments supporting the thesis.",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Supporting facts, examples, or citations.",
    )
    rebuttals: list[str] = Field(
        default_factory=list,
        description="Anticipated counterarguments and responses.",
    )

    def to_markdown(self) -> str:
        """Render the argument as a clean markdown document."""
        title = "Propose" if self.stance == "propose" else "Oppose"
        lines = [
            f"# {title} Argument",
            "",
            f"**Motion:** {self.motion}",
            "",
            "## Thesis",
            self.thesis,
            "",
            "## Key Points",
        ]
        for idx, point in enumerate(self.key_points, start=1):
            lines.append(f"{idx}. {point}")
        lines.extend(["", "## Evidence"])
        for item in self.evidence:
            lines.append(f"- {item}")
        if self.rebuttals:
            lines.extend(["", "## Rebuttals"])
            for item in self.rebuttals:
                lines.append(f"- {item}")
        lines.append("")
        return "\n".join(lines)


class RubricScore(BaseModel):
    """Rubric evaluation across Evidence, Logic, and Rebuttal dimensions."""

    evidence: float = Field(..., ge=0.0, le=10.0)
    logic: float = Field(..., ge=0.0, le=10.0)
    rebuttal: float = Field(..., ge=0.0, le=10.0)
    on_topic: bool = Field(
        default=True,
        description="Whether the argument directly addresses the debate motion.",
    )
    off_topic_penalty: float = Field(
        default=0.0,
        ge=0.0,
        description="Penalty applied if the argument drifts off the motion.",
    )
    rationale: str = Field(
        default="",
        description="Justification for the assigned rubric scores.",
    )

    @property
    def total(self) -> float:
        """Compute net rubric score after any off-topic penalty."""
        raw = self.evidence + self.logic + self.rebuttal
        return round(max(0.0, raw - self.off_topic_penalty), 2)


class DebateVerdict(BaseModel):
    """Final order-unbiased verdict from dual-pass judging."""

    motion: str = Field(..., min_length=1)
    winner: VerdictOutcome
    propose_score: RubricScore
    oppose_score: RubricScore
    pass_1_winner: VerdictOutcome
    pass_2_winner: VerdictOutcome
    positional_bias_detected: bool = Field(
        default=False,
        description="True when Pass 1 (propose-first) and Pass 2 (oppose-first) disagree.",
    )
    decision_rationale: str = Field(..., min_length=1)
    artifacts_written: list[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        """Render the final decision verdict as decide.md."""
        bias_label = "YES (Positional preference detected)" if self.positional_bias_detected else "NO"
        lines = [
            "# Debate Decision",
            "",
            f"**Motion:** {self.motion}",
            f"**Winner:** {self.winner.upper()}",
            f"**Pass 1 Winner (Propose First):** {self.pass_1_winner.upper()}",
            f"**Pass 2 Winner (Oppose First):** {self.pass_2_winner.upper()}",
            f"**Positional Bias Detected:** {bias_label}",
            "",
            "## Rubric Scores",
            "",
            "| Side | Evidence | Logic | Rebuttal | Penalty | Total | On Topic |",
            "| --- | ---: | ---: | ---: | ---: | ---: | :---: |",
            (
                f"| Propose | {self.propose_score.evidence:.1f} | "
                f"{self.propose_score.logic:.1f} | {self.propose_score.rebuttal:.1f} | "
                f"{self.propose_score.off_topic_penalty:.1f} | {self.propose_score.total:.2f} | "
                f"{'Yes' if self.propose_score.on_topic else 'No'} |"
            ),
            (
                f"| Oppose | {self.oppose_score.evidence:.1f} | "
                f"{self.oppose_score.logic:.1f} | {self.oppose_score.rebuttal:.1f} | "
                f"{self.oppose_score.off_topic_penalty:.1f} | {self.oppose_score.total:.2f} | "
                f"{'Yes' if self.oppose_score.on_topic else 'No'} |"
            ),
            "",
            "## Rationale",
            self.decision_rationale,
            "",
        ]
        return "\n".join(lines)
