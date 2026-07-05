---
description: Regenerate CHANGELOG.md from git log of v-tagged commits
allowed-tools: Bash
---

```bash
python .claude/hooks/gen_changelog.py
```

Variants:
- `python .claude/hooks/gen_changelog.py --stdout` — print to stdout (no file write)
- `python .claude/hooks/gen_changelog.py --check` — exit 1 if `CHANGELOG.md` is out of sync with `git log` (used by `/aurora-self-test` gate 8)

Filters commits whose subject starts with `v<digits><suffix>:` (Aurora's versioning convention). Strips `Co-Authored-By:` trailers. Groups by major version (v77 / v78 / ...).

Run after every commit that ships a new `v<...>:` headline so the changelog stays current.
