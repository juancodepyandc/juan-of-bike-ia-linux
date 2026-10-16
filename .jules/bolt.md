## 2026-10-12 - Prevent isolated generation split in 3D pipeline
**Learning:** The pipeline defaults to orchestrating scenes, parsing the prompt into multiple objects when possible. A user explicitly requesting a single base block without an assembly context had their subject split into disconnected meshes because the 3D intent mapper wasn't appending the proper flag to the pipeline configuration.
**Action:** When a user expresses intent for `referenceFraming === 'isolated_subject'` and `subjectKind !== 'assembly'`, we must proactively inject `--no-scene` into `auroraArgs` passed to `python-services/aurora_3d_pipeline.py`.

## 2026-10-16 - Memoize ReactMarkdown components object
**Learning:** ReactMarkdown will unmount and remount every single overridden DOM node on every render if the `components` prop is an inline object. This is especially disastrous for components that update frequently, like the typewriter effect revealing tokens in the `ChatBubble`.
**Action:** Always wrap `components={{...}}` configurations passed to `ReactMarkdown` with `useMemo`, with dependencies for any closed-over props (like `onQuickPrompt`).
