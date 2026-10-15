## 2026-10-12 - Prevent isolated generation split in 3D pipeline
**Learning:** The pipeline defaults to orchestrating scenes, parsing the prompt into multiple objects when possible. A user explicitly requesting a single base block without an assembly context had their subject split into disconnected meshes because the 3D intent mapper wasn't appending the proper flag to the pipeline configuration.
**Action:** When a user expresses intent for `referenceFraming === 'isolated_subject'` and `subjectKind !== 'assembly'`, we must proactively inject `--no-scene` into `auroraArgs` passed to `python-services/aurora_3d_pipeline.py`.
## 2026-10-15 - ReactMarkdown re-renders
**Learning:** `ReactMarkdown` takes a `components` prop to customize rendering. If this prop is defined inline within the component (e.g., `<ReactMarkdown components={{...}}>`), it will fail referential equality checks on every render, causing the entire Markdown tree to needlessly re-render.
**Action:** When passing complex objects like component maps to external libraries, wrap them in `useMemo` (e.g., `const markdownComponents = useMemo(() => ({...}), [deps])`) to preserve object reference and avoid unnecessary rerenders.

## 2026-10-15 - subprocess stdin resource leaks in Python 3.10-3.13 causing CI hangs
**Learning:** When using `subprocess.Popen` to interact with an MCP server (e.g. `call_mcp_stdio`), it's critical to explicitly `proc.stdin.close()` before calling `proc.terminate()` or `proc.wait()`. Failing to close the standard input pipe leads to the child process deadlocking or waiting indefinitely for input in older Python versions (and Windows runners), causing CI check runners to eventually hit the exit code 1 or timeout.
**Action:** In `finally` blocks that manage `subprocess.Popen`, explicitly check `proc.stdin` and safely call `.close()` on it before proceeding to `proc.terminate()`.

## 2026-10-15 - pathlib.Path.as_posix() in assertions for Windows compatibility
**Learning:** Hardcoding `str(Path(...))` or expecting specific string representations in tests for filesystem paths will break on Windows due to the backslash `\` directory separator, whereas Linux uses `/`. The test `test_real_input_transfers_before_dispatch_and_same_key_never_dispatches_twice` was failing because the manifest contained posix path strings (as produced by our application using `target.as_posix()`), but the test expected `str(target)` which resulted in backslashes on Windows CI.
**Action:** When serializing paths to JSON or comparing path strings in tests that must run cross-platform, consistently use `Path.as_posix()` rather than `str(Path(...))` to normalize to forward slashes.

## 2026-10-15 - fix sys reference inside subprocess cleanup finally block
**Learning:** Adding `import sys` inside a `finally` block creates an `UnboundLocalError` if the `try` block crashes early before the import is executed or another `import sys` previously defined gets shadowed by the late import.
**Action:** Import `sys` at the top of the function if it will be needed inside the `finally` block or other conditional branches.
