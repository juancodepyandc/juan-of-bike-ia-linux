# DEPRECATED — extension_chrome/

**Status: deprecated as of v82l7 (2026-05-03).**

This directory is **no longer the source of truth** for the Aurora-Connect Chrome
extension. The canonical location is now:

```
application/extension/
```

That folder is auto-bumped by `bump-extension-version.py` whenever any of its
files change, and the bridge endpoint `/api/cowork/extension/version` reads
`application/extension/manifest.json` first. The Aurora-Connect extension polls
this endpoint and triggers `chrome.runtime.reload()` automatically when the
version differs.

## Why is this folder still here?

It is kept **strictly as a fallback** for development environments that
installed the extension unpacked from this directory **before** the migration
to `application/extension/`. The bridge falls back to reading this manifest
only if `application/extension/manifest.json` is missing — see
`bridge_server.py::cowork_ext_version`.

## What you should do

- **New install / fresh clone:** load the unpacked extension from
  `application/extension/`. Do not load from `extension_chrome/`.
- **Existing install pointing here:** remove the extension from
  `chrome://extensions`, then re-load unpacked from `application/extension/`.
- **Editing the extension:** edit files under `application/extension/` only.
  Changes here will not propagate (the version-bump tool ignores this folder).

## Schedule for removal

This folder will be removed once all known dev environments have migrated.
There is no fixed date — the bridge fallback path makes the removal safe to
defer until the legacy install footprint is empty.

## Owner

`cowork-connector-keeper` (see `.claude/agents/cowork-connector-keeper.md`).
