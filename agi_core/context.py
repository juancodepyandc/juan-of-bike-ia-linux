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
    meta: dict = {}
    if not content.startswith("---\n") and not content.startswith("---\r\n"):
        return meta
    triggers: list[str] = []
    in_triggers = False
    for line in content.split("---", 2)[1].splitlines():
        match = re.match(r"^(name|description):\s*(.*)$", line)
        if match:
            in_triggers = False
            value = match[2].strip()
            try:
                value = json.loads(value)
            except ValueError:
                value = value.strip("'\"")
            if isinstance(value, str):
                meta[match[1]] = value
        elif re.match(r"^triggers:\s*$", line.strip()):
            in_triggers = True
        elif in_triggers and re.match(r"^\s*-\s+(.+)$", line):
            raw_trigger = re.sub(r"^\s*-\s+", "", line).strip().strip("'\"")
            if raw_trigger:
                triggers.append(raw_trigger)
        elif line.strip() and not line.startswith(" "):
            in_triggers = False
    if triggers:
        meta["triggers"] = triggers
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


def discover_official_agents() -> list[dict]:
    try:
        from application.agent_registry import list_agents
    except ImportError:
        try:
            from agent_registry import list_agents
        except ImportError:
            return []
    state = _read_json(data_dir() / "cli_agent_state.json")
    disabled = state.get("disabled", [])
    if not isinstance(disabled, list):
        disabled = []
    return [a for a in list_agents(disabled=disabled) if a.get("enabled", True)]


def resolve_agent(name: str, workspace: str | None = None) -> dict | None:
    if not isinstance(name, str) or not name.strip():
        return None
    registered = _read_json(data_dir() / "dynamic_agents.json").get("agents", [])
    if isinstance(registered, list):
        for a in registered:
            if (isinstance(a, dict) and a.get("type") == "saved"
                    and a.get("name") == name and isinstance(a.get("role", ""), str)):
                raw_tools = a.get("preferred_tools") or a.get("tools") or []
                return {
                    "name": a.get("name", ""),
                    "role": a.get("role", "")[:8000],
                    "domain": str(a.get("domain", ""))[:200],
                    "module": str(a.get("module") or a.get("domain") or "")[:200],
                    "parent_agent": str(a.get("parent_agent", ""))[:80],
                    "can_create_subagents": bool(a.get("can_create_subagents", True)),
                    "permissions": a.get("permissions", "STANDARD"),
                    "preferred_tools": [t for t in raw_tools if isinstance(t, str)] if isinstance(raw_tools, list) else [],
                    "verification_focus": str(a.get("verification_focus", ""))[:2000],
                    "origin": "saved",
                }
    for official in discover_official_agents():
        if official.get("name") == name:
            return {
                "name": official["name"],
                "role": (official.get("role") or official.get("description") or "")[:8000],
                "description": official.get("description", ""),
                "domain": official.get("domain", ""),
                "module": official.get("module") or official.get("domain") or "",
                "parent_agent": official.get("parent_agent", ""),
                "can_create_subagents": bool(official.get("can_create_subagents", True)),
                "permissions": official.get("permissions", "STANDARD"),
                "preferred_tools": official.get("preferred_tools", []),
                "verification_focus": official.get("verification_focus", ""),
                "origin": "official",
            }
    return None


def call_mcp_stdio(server: dict, method: str, params: dict, *,
                   timeout: float = 12.0, cwd: str | None = None) -> tuple[dict | None, str | None]:
    """Run one JSON-RPC request against an MCP stdio server with a bounded wait."""
    import select
    import subprocess
    command = server.get("command", "")
    raw_args = server.get("args", [])
    cmd = [command] + (list(raw_args) if isinstance(raw_args, list) else [])
    if not cmd or not isinstance(cmd[0], str) or not cmd[0].strip():
        return None, "MCP server command is empty"
    raw_env = server.get("env", {})
    env = {**os.environ, **(raw_env if isinstance(raw_env, dict) else {})}
    proc = None
    reader = None
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=env, cwd=cwd or os.getcwd(),
        )
        reader = proc.stdout
        if reader is None:
            return None, "MCP stdout unavailable"
        reader_fd = reader.fileno()
        deadline = time.monotonic() + timeout

        def send_rpc(mid: int, rpc_method: str, rpc_params: dict) -> None:
            payload = json.dumps({"jsonrpc": "2.0", "id": mid, "method": rpc_method, "params": rpc_params}) + "\n"
            if proc.stdin is None or proc.stdin.closed:
                raise OSError("MCP stdin closed")
            proc.stdin.write(payload.encode("utf-8"))
            proc.stdin.flush()

        send_rpc(1, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "aurora-agi", "version": "1.3.0"},
        })
        send_rpc(2, method, params)
        buf = b""
        while True:
            while b"\n" in buf:
                line, _, buf = buf.partition(b"\n")
                try:
                    msg = json.loads(line.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    continue
                if isinstance(msg, dict) and msg.get("id") == 2:
                    if "error" in msg and isinstance(msg["error"], dict):
                        return None, str(msg["error"].get("message") or msg["error"])
                    return msg, None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None, "MCP server timed out (no response)"
            ready, _, _ = select.select([reader_fd], [], [], min(remaining, 2.0))
            if not ready:
                if proc.poll() is not None and not buf:
                    return None, "MCP server exited before responding"
                continue
            chunk = os.read(reader_fd, 65536)
            if not chunk:
                return None, "MCP server closed while waiting for response"
            buf += chunk
            if len(buf) > 1_000_000:
                return None, "MCP server response too large"
    except OSError as exc:
        return None, f"MCP request failed: {exc}"
    finally:
        try:
            if reader is not None and not reader.closed:
                reader.close()
        except Exception:
            pass
        try:
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2.0)
        except Exception:
            pass


def probe_mcp_tools(workspace: str, server_name: str = "", *, probe: bool = False,
                    timeout: float = 10.0) -> dict:
    servers = discover_mcp(workspace)
    if server_name:
        servers = [s for s in servers if s["name"] == server_name]
        if not servers:
            raise ValueError(f"MCP server '{server_name}' not found")
    tools_out = []
    errors = []
    for srv in servers:
        declared = [
            {"server": srv["name"], "name": t.get("name", ""), "description": t.get("description", ""),
             "schema": t.get("inputSchema", {}), "status": "configured_declaration"}
            for t in srv.get("tools", []) if isinstance(t, dict) and t.get("name")
        ]
        if not probe or not srv.get("command"):
            tools_out.extend(declared)
            continue
        resp, err = call_mcp_stdio(srv, "tools/list", {}, timeout=timeout, cwd=workspace)
        if err or not isinstance(resp, dict):
            errors.append({"server": srv["name"], "error": err or "empty response"})
            tools_out.extend(declared)
            continue
        live_tools = resp.get("result", {}).get("tools", [])
        if isinstance(live_tools, list):
            for t in live_tools:
                if isinstance(t, dict) and t.get("name"):
                    tools_out.append({
                        "server": srv["name"],
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "schema": t.get("inputSchema", {}),
                        "status": "live_probed",
                    })
    return {
        "servers": [s["name"] for s in servers],
        "tools": tools_out,
        "total": len(tools_out),
        "errors": errors,
        "scope": "Live stdio probe when probe=true and command is configured; otherwise static declarations",
    }


def invoke_mcp_tool(workspace: str, server_name: str, tool_name: str,
                    arguments: dict | None = None, *, timeout: float = 12.0) -> dict:
    if not isinstance(server_name, str) or not server_name.strip():
        raise ValueError("MCP server name is required")
    if not isinstance(tool_name, str) or not tool_name.strip():
        raise ValueError("MCP tool name is required")
    if arguments is not None and not isinstance(arguments, dict):
        raise ValueError("MCP tool arguments must be a JSON object")
    servers = discover_mcp(workspace)
    srv = next((s for s in servers if s["name"] == server_name), None)
    if not srv:
        raise ValueError(f"MCP server '{server_name}' not found")
    resp, err = call_mcp_stdio(
        srv, "tools/call", {"name": tool_name, "arguments": arguments or {}},
        timeout=timeout, cwd=workspace,
    )
    if err:
        raise RuntimeError(err)
    if not isinstance(resp, dict):
        raise RuntimeError("Empty MCP response")
    result = resp.get("result", {})
    is_error = bool(isinstance(result, dict) and result.get("isError"))
    if is_error:
        raise RuntimeError(f"MCP tool '{tool_name}' returned error: {json.dumps(result, ensure_ascii=False)[:600]}")
    return {
        "server": server_name,
        "tool": tool_name,
        "result": result,
        "scope": "MCP stdio tool response; verify any file or state side effects independently",
    }


def load_context(workspace: str) -> dict:
    skills = discover_skills(workspace)
    servers = discover_mcp(workspace)
    connections = _read_json(data_dir() / "connections.json").get("connections", [])
    active = [c.get("service") for c in connections
              if isinstance(c, dict) and c.get("active") and isinstance(c.get("service"), str)] if isinstance(connections, list) else []
    registered = _read_json(data_dir() / "dynamic_agents.json").get("agents", [])
    saved = [
        {
            "name": a.get("name", ""),
            "role": a.get("role", "")[:8000],
            "domain": str(a.get("domain", ""))[:200],
            "module": str(a.get("module") or a.get("domain") or "")[:200],
            "parent_agent": str(a.get("parent_agent", ""))[:80],
            "can_create_subagents": bool(a.get("can_create_subagents", True)),
            "permissions": a.get("permissions", "STANDARD"),
            "preferred_tools": [
                t for t in (a.get("preferred_tools") or a.get("tools") or [])
                if isinstance(t, str)
            ] if isinstance(a.get("preferred_tools") or a.get("tools"), list) else [],
            "verification_focus": str(a.get("verification_focus", ""))[:2000],
        }
        for a in registered if isinstance(a, dict) and a.get("type") == "saved"
        and isinstance(a.get("role", ""), str)
    ] if isinstance(registered, list) else []
    official = discover_official_agents()
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
            "connections_count": len(active), "saved_agents": saved,
            "official_agents_list": official}


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
    with target.open("x", encoding="utf-8", newline="") as stream:
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


def create_agent(name: str, role: str, model: str, permissions: str, mission_id: str, *,
                 preferred_tools: list[str] | None = None, verification_focus: str = "",
                 domain: str = "", module: str = "", parent_agent: str = "",
                 can_create_subagents: bool = True) -> dict:
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    with _registry_lock(root):
        return _create_agent(name, role, model, permissions, mission_id,
                             preferred_tools=preferred_tools,
                             verification_focus=verification_focus,
                             domain=domain,
                             module=module,
                             parent_agent=parent_agent,
                             can_create_subagents=can_create_subagents)


def _create_agent(name: str, role: str, model: str, permissions: str, mission_id: str, *,
                  preferred_tools: list[str] | None = None, verification_focus: str = "",
                  domain: str = "", module: str = "", parent_agent: str = "",
                  can_create_subagents: bool = True) -> dict:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
        raise ValueError("Invalid agent name")
    if not isinstance(role, str) or not role.strip() or len(role) > 8000:
        raise ValueError("A bounded agent role is required")
    clean_tools = [t.strip() for t in (preferred_tools or []) if isinstance(t, str) and t.strip()][:32]
    clean_focus = str(verification_focus or "").strip()[:2000]
    clean_domain = str(domain or module or "").strip()[:200]
    clean_module = str(module or domain or "").strip()[:200]
    clean_parent = str(parent_agent or "").strip()[:80]
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
             "status": "idle", "tools": clean_tools, "preferred_tools": clean_tools,
             "verification_focus": clean_focus, "domain": clean_domain,
             "module": clean_module, "parent_agent": clean_parent,
             "can_create_subagents": bool(can_create_subagents),
             "runtime_seconds": 0, "results": []}
    agents.append(agent)
    fd, temp = tempfile.mkstemp(prefix=".agents-", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(store, stream, ensure_ascii=False, indent=2)
        os.replace(temp, target)
    finally:
        Path(temp).unlink(missing_ok=True)
    return agent


def create_module_subagent(
    module: str,
    name: str,
    role: str,
    *,
    model: str = "local",
    permissions: str = "AUTONOMOUS",
    mission_id: str = "module_factory",
    parent_agent: str = "",
    preferred_tools: list[str] | None = None,
    verification_focus: str = "",
) -> dict:
    """Ensure a module-scoped sub-agent exists, creating it if absent or returning existing."""
    clean_module = (module or "").strip().lower()
    if not clean_module:
        raise ValueError("Module name is required")
    existing = resolve_agent(name)
    if existing is not None:
        return {**existing, "changed": False, "passed": True}
    parent = parent_agent
    if not parent:
        try:
            from application.agent_registry import get_module_agent
        except ImportError:
            try:
                from agent_registry import get_module_agent
            except ImportError:
                get_module_agent = None
        if get_module_agent is not None:
            lead = get_module_agent(clean_module)
            if lead:
                parent = lead["name"]
    created = create_agent(
        name,
        role,
        model,
        permissions,
        mission_id,
        preferred_tools=preferred_tools,
        verification_focus=verification_focus,
        domain=clean_module,
        module=clean_module,
        parent_agent=parent,
        can_create_subagents=True,
    )
    return {**created, "changed": True, "passed": True}


def list_agents_for_module(module: str | None = None, workspace: str | None = None) -> list[dict]:
    """Return both official and dynamically created sub-agents belonging to a module."""
    ctx = load_context(workspace or ".")
    all_agents = list(ctx.get("official_agents_list", [])) + list(ctx.get("saved_agents", []))
    if not module:
        return all_agents
    key = module.strip().lower()
    return [
        a for a in all_agents
        if (a.get("module") or "").lower() == key or (a.get("domain") or "").lower() == key
    ]

