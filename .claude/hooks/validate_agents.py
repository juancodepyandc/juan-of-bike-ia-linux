#!/usr/bin/env python3
"""Aurora agent system linter.

Verifies the integrity of the multi-agent architecture:

1. Every `.claude/agents/<name>.md` has well-formed YAML frontmatter with
   required fields (name, description, model).
2. The frontmatter `name` matches the file basename.
3. `model` is `claude-opus-4-7` everywhere (the user explicitly pinned this).
4. Every agent file is referenced in `.claude/agent-tracker/state.json` —
   either as a top-level lead, a sub_agent under some lead, or a crosscut.
5. Every agent referenced in `state.json` has a corresponding `.md` file.
6. KNOWN_AGENTS in `track_agent_dispatch.py` matches the union of agents.

Exit 0 on green; exit 1 + report to stderr otherwise. Designed to be invoked
from `/aurora-validate` slash command and from CI.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"
TRACKER = REPO_ROOT / ".claude" / "agent-tracker" / "state.json"
TRACKER_HOOK = REPO_ROOT / ".claude" / "hooks" / "track_agent_dispatch.py"

REQUIRED_FIELDS = ("name", "description", "model")
PINNED_MODEL = "claude-opus-4-7"
COMMAND_REQUIRED_FIELDS = ("description",)

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Match `python <path>` invocations inside bash code fences. We strip
# anything starting with `-` or `--` (flags) and pick the first non-flag
# token as the script path. Also accepts `python3` and `py`.
PYTHON_INVOKE_RE = re.compile(
    r"\b(?:python3?|py)\s+([^\s\-`][^\s`]*)",
)
BASH_FENCE_RE = re.compile(r"```(?:bash|sh|shell)\s*\n(.*?)```", re.DOTALL)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Tiny frontmatter parser — flat key: value pairs only, which is what
    every agent file uses. Avoids a yaml dependency."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    out: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        out[key.strip()] = val.strip()
    return out


def collect_state_agents(state: dict) -> set[str]:
    names: set[str] = set()
    leads = state.get("leads") or {}
    for lead_name, body in leads.items():
        names.add(lead_name)
        for sub in (body or {}).get("sub_agents", []) or []:
            names.add(sub)
    for cc in state.get("crosscut") or []:
        names.add(cc)
    # Master orchestrator is implicit — add it.
    names.add("aurora-orchestrator")
    return names


def collect_known_agents() -> set[str]:
    """Extract KNOWN_AGENTS = {…} literal from track_agent_dispatch.py."""
    if not TRACKER_HOOK.exists():
        return set()
    text = TRACKER_HOOK.read_text(encoding="utf-8")
    match = re.search(r"KNOWN_AGENTS\s*=\s*\{(.*?)\}", text, re.DOTALL)
    if not match:
        return set()
    return set(re.findall(r'"([a-z0-9_-]+)"', match.group(1)))


def main() -> int:
    errors: list[str] = []

    if not AGENTS_DIR.is_dir():
        sys.stderr.write(f"ERROR: agents dir missing at {AGENTS_DIR}\n")
        return 1
    if not TRACKER.exists():
        sys.stderr.write(f"ERROR: tracker state.json missing at {TRACKER}\n")
        return 1

    file_agents: set[str] = set()
    docs_files = {"README.md", "EXAMPLES.md"}
    for md in sorted(AGENTS_DIR.glob("*.md")):
        if md.name in docs_files:
            continue
        text = md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm is None:
            errors.append(f"{md.name}: missing or malformed YAML frontmatter")
            continue
        for field in REQUIRED_FIELDS:
            if field not in fm:
                errors.append(f"{md.name}: missing required field '{field}'")
        name = fm.get("name", "")
        expected = md.stem
        if name != expected:
            errors.append(f"{md.name}: frontmatter name '{name}' != filename stem '{expected}'")
        model = fm.get("model", "")
        if model != PINNED_MODEL:
            errors.append(f"{md.name}: model '{model}' != pinned '{PINNED_MODEL}'")
        file_agents.add(expected)

    try:
        state = json.loads(TRACKER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"state.json unreadable: {exc}")
        state = {}

    state_agents = collect_state_agents(state)
    known_agents = collect_known_agents()

    only_in_files = file_agents - state_agents
    only_in_state = state_agents - file_agents
    only_in_known = known_agents - file_agents
    missing_from_known = file_agents - known_agents

    for n in sorted(only_in_files):
        errors.append(f"agent '{n}' has a .md file but is not in state.json (lead/sub_agent/crosscut)")
    for n in sorted(only_in_state):
        errors.append(f"agent '{n}' is referenced in state.json but has no .md file")
    for n in sorted(only_in_known):
        errors.append(f"KNOWN_AGENTS contains '{n}' but no .md file")
    for n in sorted(missing_from_known):
        errors.append(f"agent '{n}' has a .md file but is missing from KNOWN_AGENTS")

    # Lint slash commands — every .claude/commands/*.md must have:
    #   1. well-formed YAML frontmatter with the `description` field
    #   2. every `python <path>` invocation in its bash blocks resolves
    #      to a real file (catches drift when scripts are renamed/moved)
    command_count = 0
    if COMMANDS_DIR.is_dir():
        for md in sorted(COMMANDS_DIR.glob("*.md")):
            text = md.read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            if fm is None:
                errors.append(f"commands/{md.name}: missing or malformed YAML frontmatter")
                continue
            for field in COMMAND_REQUIRED_FIELDS:
                if field not in fm:
                    errors.append(f"commands/{md.name}: missing required field '{field}'")
            for fence in BASH_FENCE_RE.findall(text):
                for script in PYTHON_INVOKE_RE.findall(fence):
                    # Skip module invocations (`python -m foo`) or stdin pipes.
                    if script.startswith(("-", "<", '"', "'")):
                        continue
                    # Strip any quoting that crept into the path.
                    script = script.strip("\"'")
                    # Resolve relative to repo root (slash-doc commands are
                    # always copy-pasted from the repo root).
                    target = REPO_ROOT / script
                    if not target.is_file():
                        errors.append(
                            f"commands/{md.name}: references non-existent script "
                            f"`{script}`"
                        )
            command_count += 1

    if errors:
        sys.stderr.write(f"FAIL — {len(errors)} issue(s):\n")
        for err in errors:
            sys.stderr.write(f"  - {err}\n")
        return 1

    total = len(file_agents)
    leads = sum(1 for a in file_agents if a.endswith("-lead"))
    sys.stdout.write(
        f"OK — {total} agents, {leads} leads, {command_count} commands, "
        f"all model={PINNED_MODEL}, state.json + KNOWN_AGENTS coherent.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
