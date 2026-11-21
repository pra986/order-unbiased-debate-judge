# Order-Unbiased Debate Judge

**Project 34 (X3: Supplement / Agentic — CrewAI Debate)**

A CrewAI-compatible debate evaluation harness that eliminates LLM-as-a-Judge positional preference bias using **order-swapped dual-judge passes**, **motion-alignment verification**, and an **explicit 3-axis evidence rubric** (Evidence, Logic, Rebuttal).

---

## Architecture Overview

LLM judges frequently exhibit **positional preference bias**—favoring whichever argument appears first (or second) in the prompt regardless of argument quality. `order-unbiased-debate-judge` enforces structural fairness by:

1. Validating that both **Propose** and **Oppose** arguments address the exact same debate motion.
2. Providing the judge with **both contexts simultaneously** in every evaluation pass.
3. Scoring each side independently on a bounded **3-axis rubric** (`Evidence`, `Logic`, `Rebuttal`, 0–10 each).
4. Executing a **second order-swapped judge pass** (`(Oppose, Propose)` after `(Propose, Oppose)`).
5. Comparing pass verdicts to **flag positional preference bias** when the winner flips solely due to presentation order.
6. Emitting auditable Markdown artifacts: `propose.md`, `oppose.md`, and `decide.md`.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for component diagrams and failure-mode analysis.

---

## 6-Stage Workflow

1. **Stage 1 — Motion Normalization & Alignment Gate**: Normalizes the debate motion and verifies that both `DebateArgument` inputs (`propose` and `oppose`) reference the exact same motion string.
2. **Stage 2 — Argument Ingestion & Context Packaging**: Structures `propose` and `oppose` arguments into immutable `DebateArgument` models and writes `propose.md` and `oppose.md`.
3. **Stage 3 — Pass 1 Evaluation (`Propose -> Oppose`)**: Evaluates both arguments in canonical order against the 3-axis rubric (`Evidence`, `Logic`, `Rebuttal`), penalizing off-topic or unsupported claims.
4. **Stage 4 — Pass 2 Evaluation (`Oppose -> Propose`)**: Re-evaluates the exact same arguments in swapped presentation order using the identical rubric.
5. **Stage 5 — Bias Reconciliation & Tie-Breaking**: Compares Pass 1 and Pass 2 winners. If the winner flips upon order swap, sets `positional_bias_detected = True`, averages axis scores across both passes, and resolves the final verdict.
6. **Stage 6 — Artifact Emission (`decide.md`)**: Persists the structured `DebateVerdict` and full rubric breakdown to `decide.md`.

---

## Data Contract

Defined in `debate_judge/models.py`:

- **`DebateArgument`**:
  - `side`: `"propose"` | `"oppose"`
  - `motion`: `str` (must match across both sides)
  - `content`: `str`
  - `sources`: `list[str]`
- **`RubricScore`**:
  - `evidence`: `float` (0.0 – 10.0)
  - `logic`: `float` (0.0 – 10.0)
  - `rebuttal`: `float` (0.0 – 10.0)
  - `total`: `float` (computed sum, 0.0 – 30.0)
  - `rationale`: `str`
- **`DebateVerdict`**:
  - `motion`: `str`
  - `winner`: `"propose"` | `"oppose"` | `"tie"`
  - `propose_score`: `RubricScore`
  - `oppose_score`: `RubricScore`
  - `pass1_winner`: `str`
  - `pass2_winner`: `str`
  - `positional_bias_detected`: `bool`
  - `summary`: `str`

---

## Production Controls

- **Motion-Mismatch Guard**: Rejects evaluations where `propose.motion != oppose.motion` to prevent apples-to-oranges judging.
- **Dual-Pass Order-Swap Invariance Check**: Detects and flags positional bias whenever Pass 1 and Pass 2 disagree.
- **Off-Topic Rubric Penalty**: Explicitly penalizes arguments lacking motion keyword/semantic alignment across Evidence and Rebuttal axes.
- **Deterministic Offline Mode + CrewAI/LLM Adapter**: Ships with a deterministic rubric evaluator for CI/CD and unit testing, plus clean hooks for live CrewAI/OpenAI judge backends.
- **CI Enforcement**: Automated `pytest` suite via `.github/workflows/ci.yml`.

---

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### Run the CLI Demo

```bash
python -m debate_judge.cli --motion "AI agents should be regulated by an international oversight body" --output-dir ./artifacts
```

This generates `propose.md`, `oppose.md`, and `decide.md` in `./artifacts`.

### Run Tests

```bash
pytest -v
```

---

## Attribution

Inspired by and adapted from **`ed-donner/agents`** (`3_crewai/reference/debate`), extending the reference debate crew pattern with dual-pass order-swapped evaluation, positional bias detection, and a 3-axis evidence rubric.

## License

MIT License — see [`LICENSE`](LICENSE) for details.
 an explicit 3-axis evidence rubric.
