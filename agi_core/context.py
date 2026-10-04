"""Shared, bounded discovery for bridge and mission workers; no service startup."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
import time
from uuid import uuid4
from contextlib import contextmanager


def data_dir() -> Path:
    if os.environ.get("AURORA_DATA_DIR"):
        return Path(os.environ["AURORA_DATA_DIR"]).expanduser()
    if os.name == "nt" and not os.environ.get("XDG_DATA_HOME"):
        legacy = Path.home() / '.local/share/aurora'
        if any((legacy/name).exists() for name in ('dynamic_agents.json','cli_sessions.json','missions.sqlite3','connections.json')):
            return legacy
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "aurora"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "aurora"


def _read_json(path: Path, *, strict: bool = False) -> dict:
    try:
        if path.stat().st_size > 1024 * 1024:
            if strict:
                raise ValueError("Existing registry is too large; left untouched")
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        if strict and not isinstance(value, dict):
            raise ValueError("Existing registry is invalid; left untouched")
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        if strict and path.exists():
            raise ValueError("Existing registry cannot be read; left untouched") from None
        return {}


def _frontmatter(content: str) -> dict:
    meta = {}
    if not content.startswith("---\n"):
        return meta
    for line in content.split("---", 2)[1].splitlines():
        match = re.match(r"^(name|description):\s*(.*)$", line)
        if match:
            value = match[2].strip()
            try:
                value = json.loads(value)
            except ValueError:
                value = value.strip("'\"")
            if isinstance(value, str):
                meta[match[1]] = value
    return meta


def discover_skills(workspace: str) -> list[dict]:
    root = Path(workspace).expanduser().resolve()
    locations = [("project", root / ".aurora/skills"),
                 ("project", root.parent / ".aurora/skills"),
                 ("user", Path.home() / ".aurora/skills")]
    if os.name != "nt":
        locations.append(("global", Path("/etc/aurora/skills")))
    found, seen = [], set()
    for level, base in locations:
        try:
            entries = sorted(base.iterdir())
        except OSError:
            continue
        for entry in entries[:200]:
            if entry.name in seen:
                continue
            source = entry / "SKILL.md"
            try:
                if not source.is_file() or source.stat().st_size > 65536:
                    continue
                content = source.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            seen.add(entry.name)
            found.append({"name": entry.name, "description": "", "triggers": [],
                          **_frontmatter(content), "level": level, "path": str(entry),
                          "file": str(source), "content": content})
    return found


def discover_mcp(workspace: str) -> list[dict]:
    root = Path(workspace).expanduser().resolve()
    sources = [root / ".aurora/mcp_config.json", root / ".mcp.json",
               root.parent / ".aurora/mcp_config.json", root.parent / ".mcp.json"]
    found, seen = [], set()
    for source in sources:
        configured = _read_json(source).get("mcpServers", {})
        if not isinstance(configured, dict):
            continue
        for name, cfg in configured.items():
            if name in seen or not isinstance(cfg, dict):
                continue
            seen.add(name)
            tools = cfg.get("tools", [])
            found.append({"name": name, "command": cfg.get("command", ""),
                          "args": cfg.get("args", []), "env": cfg.get("env", {}),
                          "source": str(source), "tools": tools if isinstance(tools, list) else []})
    return found


def load_context(workspace: str) -> dict:
    skills = discover_skills(workspace)
    servers = discover_mcp(workspace)
    connections = _read_json(data_dir() / "connections.json").get("connections", [])
    active = [c.get("service") for c in connections
              if isinstance(c, dict) and c.get("active") and isinstance(c.get("service"), str)] if isinstance(connections, list) else []
    registered = _read_json(data_dir() / "dynamic_agents.json").get("agents", [])
    saved = [{"name": a.get("name", ""), "role": a.get("role", "")[:8000],
              "permissions": a.get("permissions", "STANDARD")}
             for a in registered if isinstance(a, dict) and a.get("type") == "saved"
             and isinstance(a.get("role", ""), str)] if isinstance(registered, list) else []
    # Configured MCP tools are declarations, not evidence of executability.
    public_servers = [{"name": s["name"], "tools": [t.get("name", "") for t in s["tools"]
                       if isinstance(t, dict)]} for s in servers]
    bodies, remaining = [], 24000
    for skill in skills[:10]:
        body = skill["content"][:min(8000, remaining)]
        bodies.append(f"--- Skill {skill['name']} ({skill['level']}) ---\n{body}")
        remaining -= len(body)
        if remaining <= 0:
            break
    return {"skills": [{k: v for k, v in s.items() if k != "content"} for s in skills],
            "skills_count": len(skills), "skills_summary": "\n".join(
                f"- {s['name']}: {s['description']}" for s in skills[:10]),
            "skills_context": "\n\n".join(bodies), "mcp_servers": public_servers,
            "mcp_tools_count": sum(len(s["tools"]) for s in public_servers),
            "mcp_status": "configured_unverified", "connections": active,
            "connections_count": len(active), "saved_agents": saved}


def create_skill(workspace: str, name: str, description: str, instructions: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
        raise ValueError("Invalid skill name")
    if not isinstance(description, str) or not isinstance(instructions, str) or not instructions.strip():
        raise ValueError("Skill instructions are required")
    content = (f"---\nname: {json.dumps(name)}\ndescription: {json.dumps(description, ensure_ascii=False)}\n"
               f"---\n\n{instructions.strip()}\n")
    if len(content.encode("utf-8")) > 65536:
        raise ValueError("Skill exceeds 64 KiB")
    root = Path(workspace).expanduser().resolve()
    target = (root / ".aurora/skills" / name / "SKILL.md").resolve()
    if not target.is_relative_to(root):
        raise ValueError("Skill directory escapes workspace")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite an existing skill, including through a symlink.
    with target.open("x", encoding="utf-8") as stream:
        stream.write(content)
    return str(target)


@contextmanager
def _registry_lock(root: Path):
    fd = os.open(root / ".agents.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.name == "nt":
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def create_agent(name: str, role: str, model: str, permissions: str, mission_id: str) -> dict:
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    with _registry_lock(root):
        return _create_agent(name, role, model, permissions, mission_id)


def _create_agent(name: str, role: str, model: str, permissions: str, mission_id: str) -> dict:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
        raise ValueError("Invalid agent name")
    if not isinstance(role, str) or not role.strip() or len(role) > 8000:
        raise ValueError("A bounded agent role is required")
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    target = root / "dynamic_agents.json"
    store = _read_json(target, strict=True)
    agents = store.setdefault("agents", [])
    if not isinstance(agents, list):
        raise ValueError("Invalid existing agent registry; left untouched")
    if any(a.get("name") == name for a in agents if isinstance(a, dict)):
        raise ValueError("Agent already exists; left untouched")
    agent = {"id": "dyn_" + uuid4().hex[:12], "name": name, "role": role,
             "system_prompt": role, "type": "saved", "model": model,
             "permissions": permissions, "created_by": mission_id,
             "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "status": "idle", "tools": [], "runtime_seconds": 0, "results": []}
    agents.append(agent)
    fd, temp = tempfile.mkstemp(prefix=".agents-", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(store, stream, ensure_ascii=False, indent=2)
        os.replace(temp, target)
    finally:
        Path(temp).unlink(missing_ok=True)
    return agent
