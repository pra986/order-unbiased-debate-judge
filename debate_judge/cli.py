"""Runnable CLI demo entrypoint for Order-Unbiased Debate Judge."""

from __future__ import annotations

import argparse
from pathlib import Path

from debate_judge.engine import OrderUnbiasedDebateJudge


DEFAULT_MOTION = "AI agents should be regulated by an international oversight body"


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the debate judge CLI."""
    parser = argparse.ArgumentParser(
        prog="debate_judge.cli",
        description="Run dual-pass order-unbiased debate judging and emit markdown artifacts.",
    )
    parser.add_argument(
        "--motion",
        default=DEFAULT_MOTION,
        help="Debate motion to evaluate.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts",
        help="Directory where propose.md, oppose.md, and decide.md will be written.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the debate judge CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    judge = OrderUnbiasedDebateJudge()
    propose, oppose = judge.build_default_arguments(args.motion)
    verdict = judge.judge(propose, oppose, output_dir=Path(args.output_dir))

    print(f"Motion: {verdict.motion}")
    print(f"Winner: {verdict.winner.upper()}")
    print(
        f"Pass 1 (propose-first): {verdict.pass_1_winner.upper()} | "
        f"Pass 2 (oppose-first): {verdict.pass_2_winner.upper()}"
    )
    print(f"Positional bias detected: {verdict.positional_bias_detected}")
    print(
        f"Scores -> Propose: {verdict.propose_score.total:.2f} | "
        f"Oppose: {verdict.oppose_score.total:.2f}"
    )
    print("Artifacts written:")
    for path in verdict.artifacts_written:
        print(f"  - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
