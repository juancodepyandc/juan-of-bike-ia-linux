---
description: Verify the environment can run Aurora — Python, Node, mesh deps, services, git hooks (PASS / WARN / FAIL per check)
allowed-tools: Bash
---

```bash
python .claude/hooks/aurora_env_check.py
```

JSON output (for piping):

```bash
python .claude/hooks/aurora_env_check.py --json
```

Runs 10 independent checks (no aborts):

| # | Check | What it validates |
|---|---|---|
| 1 | `python_version` | >= 3.12 (mesh tooling stdlib reqs) |
| 2 | `node_version` | >= 22 (`--experimental-strip-types --test`) |
| 3 | `python_mesh_deps` | `trimesh`, `numpy`, `Pillow` installed |
| 4 | `disk_free` | >= 10 GiB on the repo drive (3D outputs) |
| 5 | `bridge_health` | `http://127.0.0.1:3001/api/health` responds |
| 6 | `ollama_tags` | `http://127.0.0.1:11434/api/tags` responds (WARN if down) |
| 7 | `comfyui_port` | TCP `127.0.0.1:8188` accepts connections (WARN) |
| 8 | `git_repo` | inside a git work tree |
| 9 | `git_hooks_path` | `core.hooksPath = .claude/git-hooks` (WARN if not set) |
| 10 | `agents_directory` | `.claude/agents/` has >= 30 `.md` files |

Exit `0` if no FAIL (warnings allowed), `1` if any FAIL.

Use it:
- After `git clone` to confirm the system can run
- Before debugging "why is X failing" (often it's an env issue, not code)
- In CI as a fast pre-flight before the heavier test suite

Live verdict on the Aurora dev box (today):
```
[aurora-env] running 10 environment checks...
  [ok  ] python_version               3.12.8
  [ok  ] node_version                 v24.14.0
  [ok  ] python_mesh_deps             trimesh=4.11.5, numpy=2.4.4, Pillow=12.1.1
  [ok  ] disk_free                    276.0 GiB free
  [ok  ] bridge_health                http://127.0.0.1:3001/api/health → 200
  [ok  ] ollama_tags                  http://127.0.0.1:11434/api/tags → 200
  [ok  ] comfyui_port                 127.0.0.1:8188 accepting connections
  [ok  ] git_repo                     inside a git work tree
  [ok  ] git_hooks_path               .claude/git-hooks (Aurora hooks active)
  [ok  ] agents_directory             38 agent .md files

[aurora-env] OK — 0 warn, 10 pass
```
