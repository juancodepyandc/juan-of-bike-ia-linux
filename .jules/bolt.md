## 2026-10-12 - Prevent isolated generation split in 3D pipeline
**Learning:** The pipeline defaults to orchestrating scenes, parsing the prompt into multiple objects when possible. A user explicitly requesting a single base block without an assembly context had their subject split into disconnected meshes because the 3D intent mapper wasn't appending the proper flag to the pipeline configuration.
**Action:** When a user expresses intent for `referenceFraming === 'isolated_subject'` and `subjectKind !== 'assembly'`, we must proactively inject `--no-scene` into `auroraArgs` passed to `python-services/aurora_3d_pipeline.py`.

## 2026-10-19 - [⚡ Bolt: ReactMarkdown rendering bottleneck fix]
**Learning:** ReactMarkdown is computationally expensive to render because it parses the markdown string every time it renders. Also passing inline props like `components={ ... }` to it creates a new reference on every render, thus forcing a full re-parse and re-render of the markdown tree, even if the content itself hasn't changed.
**Action:** Always wrap `ReactMarkdown` in a `React.memo` (or `memo` from `react`) component, and ensure all non-primitive props passed to it, such as `components`, are memoized using `useMemo` so that they maintain referential equality across renders.
