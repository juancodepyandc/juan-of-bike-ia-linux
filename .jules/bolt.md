## 2026-10-12 - Prevent isolated generation split in 3D pipeline
**Learning:** The pipeline defaults to orchestrating scenes, parsing the prompt into multiple objects when possible. A user explicitly requesting a single base block without an assembly context had their subject split into disconnected meshes because the 3D intent mapper wasn't appending the proper flag to the pipeline configuration.
**Action:** When a user expresses intent for `referenceFraming === 'isolated_subject'` and `subjectKind !== 'assembly'`, we must proactively inject `--no-scene` into `auroraArgs` passed to `python-services/aurora_3d_pipeline.py`.

## 2023-11-07 - React.memo with Optional Handlers
**Learning:** When refactoring mapped components (like `ChatBubble` in a list) to use `React.memo` and stable top-level handlers, ensure that optional handlers (e.g. `onEdit`) are safely invoked with optional chaining (`onEdit?.(id)`). The original inline lambda safely ignored `undefined` implementations due to React's event pooling, but wrapping the call inside another inline function `() => onEdit(id)` makes TypeScript flag a possible `undefined` invocation and can crash at runtime.
**Action:** Always verify optional handlers passed to memoized components, ensuring robust conditional execution like `onAction?.()`.
