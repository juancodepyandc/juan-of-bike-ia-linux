# Learning sub-services — owned by `learning-lead`

When editing files in this directory, `learning-lead` (and its sub-agents `learning-quiz-verifier` / `learning-bac-curator`) rules apply.

## Hard rules

- llama4:scout is **Meta**, not Qwen3 — never inject `/no_think` tokens (no-op for Meta).
- `quiz_verify` mode: after generation, re-prompt the model with questions+answers and ask it to flag wrong ones. Replace flagged answers before display.
- ClarificationDialog must be a real popup, not `throw new Error(question)`.
- BAC curriculum coverage is FR-specific (Maths, PC, SVT, HG, Philo, LV1/LV2, Spécialités).
- Mind map deck format: nested JSON, max depth 4 (UI breaks beyond).
- Lab views (LabPhysics, LabChemistry, LabAstronomy, LabElectronics) consume `simulator-lead` services — don't import physics directly, go through `application/src/services/simulator/`.

See `.claude/agents/learning-lead.md` for the full lead spec.
