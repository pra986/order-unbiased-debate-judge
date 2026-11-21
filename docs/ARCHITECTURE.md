# Architecture — Order-Unbiased Debate Judge

## System Design

```
DebateArgument (Propose) ──┐
                           ├──> Motion Alignment Gate ──> Pass 1 (Propose, Oppose)
DebateArgument (Oppose)  ──┘                                     │
                                                                 ▼
Artifact Emitter <── Bias Reconciliation <── Pass 2 (Oppose, Propose)
(propose.md, oppose.md, decide.md)
```

## Core Principles

1. **Both-Context Visibility**: Every judge pass receives both `propose` and `oppose` arguments together.
2. **Order-Swapped Dual Passes**: Pass 1 evaluates `(Propose, Oppose)`; Pass 2 evaluates `(Oppose, Propose)`. If the winner changes, `positional_bias_detected = True`.
3. **3-Axis Evidence Rubric**: Scores `evidence` (0–10), `logic` (0–10), and `rebuttal` (0–10). Off-topic arguments are penalized on `evidence` and `rebuttal`.
4. **Motion Alignment Gate**: Raises `ValueError` if `propose.motion.strip() != oppose.motion.strip()`.
5. **Auditable Artifacts**: Emits `propose.md`, `oppose.md`, and `decide.md`.
