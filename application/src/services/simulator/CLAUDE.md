# Simulator services — owned by `simulator-lead`

When editing files in this directory, `simulator-physics-engine` (engine files) or `simulator-scene-io` (IO + store + types) rules apply.

## Hard rules

- **Pure compute layer.** No DOM imports, no Three.js imports. The view layer renders.
- **Determinism**: same seed + same scene → same trajectory. No `Math.random()` outside seeded RNG. No `Date.now()` in tick.
- **Fixed dt** integration (1/60 default). Don't use frame-time as dt — sim explodes on lag.
- **`load(save(scene))` round-trip** must deep-equal `scene`. Adding a field = update types + defaults + sceneIO + migration.
- **Schema versioning** in saved scenes. Bumping requires migration in `sceneIO`, not a wipe.
- **Particle pool** in `defaults.ts` — reuse, never allocate per frame.
- **Reaction rules** declarative pairs `(reactants, products, rate)` only — no hardcoded side effects.

See `.claude/agents/simulator-lead.md` for the full lead spec.
