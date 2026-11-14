"""Autonomous Self-Coding MCP Server Forge (`agi_core/mcp_forge.py`).

Permet à AuroraIA de coder, auditer par AST, enregistrer dans `.aurora/mcp_config.json`,
sonder en direct (`initialize` + `tools/list`) et invoquer (`tools/call`) de nouveaux
serveurs MCP JSON-RPC 2.0 stdio de manière 100 % autonome et sans hardcode.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

from agi_core.context import invoke_mcp_tool, probe_mcp_tools


_FORBIDDEN_CALLS = {
    "os.system",
    "pty.spawn",
}


def audit_mcp_server_ast(source_code: str) -> dict[str, Any]:
    """Vérifie la validité syntaxique AST et la sûreté structurelle du code Python d'un serveur MCP."""
    if not isinstance(source_code, str) or not source_code.strip():
        raise ValueError("MCP server source code must be a non-empty string")
    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        raise ValueError(f"Invalid Python syntax in MCP server code: {exc}") from exc

    functions: list[str] = []
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                func_name = f"{node.func.value.id}.{node.func.attr}"
            if func_name in _FORBIDDEN_CALLS:
                violations.append(f"Forbidden unsafe call: {func_name}")

    if violations:
        raise ValueError("MCP AST safety audit failed: " + "; ".join(violations))

    return {
        "valid_syntax": True,
        "functions": functions,
        "line_count": len(source_code.splitlines()),
        "sha256": hashlib.sha256(source_code.encode("utf-8")).hexdigest(),
    }


def build_jsonrpc_mcp_server_code(
    *,
    server_name: str,
    description: str,
    tools_spec: list[dict[str, Any]],
    helper_imports: list[str] | None = None,
    helper_code: str = "",
) -> str:
    """Génère le code Python complet et autonome d'un serveur MCP JSON-RPC 2.0 stdio
    (`protocolVersion: 2024-11-05`) à partir d'une liste de spécifications d'outils."""
    if not tools_spec or not isinstance(tools_spec, list):
        raise ValueError("At least one tool specification is required to synthesize an MCP server")

    imports_block = [
        "import json",
        "import math",
        "import hashlib",
        "import os",
        "from pathlib import Path",
        "import re",
        "import sys",
        "from typing import Any",
    ]
    for imp in helper_imports or []:
        if isinstance(imp, str) and imp.strip() and imp.strip() not in imports_block:
            imports_block.append(imp.strip())

    tool_defs_code: list[str] = []
    registry_entries: list[dict[str, Any]] = []
    dispatch_lines: list[str] = []

    for idx, spec in enumerate(tools_spec):
        if not isinstance(spec, dict):
            continue
        t_name = re.sub(r"[^a-zA-Z0-9_-]", "_", str(spec.get("name") or f"tool_{idx}").strip())
        fn_name = "_tool_" + re.sub(r"[^a-zA-Z0-9_]", "_", t_name)
        t_desc = str(spec.get("description") or f"Autonomous MCP tool {t_name}").strip()
        schema = spec.get("inputSchema") or spec.get("parameters") or {
            "type": "object",
            "properties": {},
        }
        impl = str(spec.get("code") or spec.get("implementation") or "").strip()

        if impl:
            # Si l'implémentation définit déjà `def ...`, l'extraire ou l'encapsuler proprement
            parsed_impl = ast.parse(impl)
            fn_defs = [n for n in parsed_impl.body if isinstance(n, ast.FunctionDef)]
            if fn_defs:
                user_fn_name = fn_defs[0].name
                indented_impl = "\n".join("    " + line for line in impl.splitlines())
                tool_defs_code.append(
                    f"def {fn_name}(arguments: dict[str, Any]) -> Any:\n"
                    f"{indented_impl}\n"
                    f"    return {user_fn_name}(**arguments) if isinstance(arguments, dict) else {user_fn_name}(arguments)\n"
                )
            else:
                indented_body = "\n".join("    " + line for line in impl.splitlines())
                tool_defs_code.append(
                    f"def {fn_name}(arguments: dict[str, Any]) -> Any:\n"
                    f"    args = arguments if isinstance(arguments, dict) else {{}}\n"
                    f"{indented_body}\n"
                )
        else:
            # Synthèse d'une fonction analytique déterministe inspectant ses arguments
            tool_defs_code.append(
                f"def {fn_name}(arguments: dict[str, Any]) -> Any:\n"
                f"    args = arguments if isinstance(arguments, dict) else {{}}\n"
                f"    return {{'ok': True, 'tool': {json.dumps(t_name)}, 'processed_arguments': args}}\n"
            )

        registry_entries.append({
            "name": t_name,
            "description": t_desc,
            "inputSchema": schema,
        })
        dispatch_lines.append(f"    {json.dumps(t_name)}: {fn_name},")

    tools_json_literal = json.dumps(registry_entries, ensure_ascii=False, indent=2)
    server_doc = f'"""Autonomous MCP Server `{server_name}`: {description}"""'

    code_parts = [
        "#!/usr/bin/env python3",
        "# -*- coding: utf-8 -*-",
        server_doc,
        "from __future__ import annotations",
        "",
        *imports_block,
        "",
        helper_code.strip() if helper_code.strip() else "",
        "",
        *tool_defs_code,
        f"TOOLS_MANIFEST = json.loads({json.dumps(tools_json_literal)})",
        "",
        "TOOL_HANDLERS = {",
        *dispatch_lines,
        "}",
        "",
        "def _handle_rpc(msg: dict[str, Any]) -> dict[str, Any] | None:",
        "    mid = msg.get('id')",
        "    method = msg.get('method', '')",
        "    params = msg.get('params') or {}",
        "    if method == 'initialize':",
        "        return {",
        "            'jsonrpc': '2.0',",
        "            'id': mid,",
        "            'result': {",
        "                'protocolVersion': '2024-11-05',",
        "                'capabilities': {'tools': {}},",
        f"                'serverInfo': {{'name': {json.dumps(server_name)}, 'version': '1.0.0'}},",
        "            },",
        "        }",
        "    if method.startswith('notifications/'):",
        "        return None",
        "    if method == 'tools/list':",
        "        return {'jsonrpc': '2.0', 'id': mid, 'result': {'tools': TOOLS_MANIFEST}}",
        "    if method == 'tools/call':",
        "        t_name = params.get('name', '')",
        "        t_args = params.get('arguments') or {}",
        "        handler = TOOL_HANDLERS.get(t_name)",
        "        if handler is None:",
        "            return {",
        "                'jsonrpc': '2.0',",
        "                'id': mid,",
        "                'result': {'isError': True, 'content': [{'type': 'text', 'text': f'Unknown tool: {t_name}'}]},",
        "            }",
        "        try:",
        "            out = handler(t_args)",
        "            text_out = json.dumps(out, ensure_ascii=False) if not isinstance(out, str) else out",
        "            return {",
        "                'jsonrpc': '2.0',",
        "                'id': mid,",
        "                'result': {'isError': False, 'content': [{'type': 'text', 'text': text_out}], 'structuredContent': out if isinstance(out, dict) else {'value': out}},",
        "            }",
        "        except Exception as exc:",
        "            return {",
        "                'jsonrpc': '2.0',",
        "                'id': mid,",
        "                'result': {'isError': True, 'content': [{'type': 'text', 'text': str(exc)}]},",
        "            }",
        "    if mid is not None:",
        "        return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'Method not found: {method}'}}",
        "    return None",
        "",
        "def main() -> None:",
        "    for raw_line in sys.stdin:",
        "        line = raw_line.strip()",
        "        if not line:",
        "            continue",
        "        try:",
        "            msg = json.loads(line)",
        "        except Exception:",
        "            continue",
        "        if not isinstance(msg, dict):",
        "            continue",
        "        resp = _handle_rpc(msg)",
        "        if resp is not None:",
        "            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + '\\n')",
        "            sys.stdout.flush()",
        "",
        "if __name__ == '__main__':",
        "    main()",
        "",
    ]
    return "\n".join(code_parts)


def forge_and_register_mcp_server(
    *,
    workspace: str | Path,
    server_name: str,
    description: str = "",
    tools_spec: list[dict[str, Any]] | None = None,
    server_code: str | None = None,
    helper_imports: list[str] | None = None,
    helper_code: str = "",
    python_executable: str | None = None,
    self_test_tool: str | None = None,
    self_test_args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Synthétise ou valide un serveur MCP JSON-RPC 2.0 stdio, l'écrit dans
    `<workspace>/.aurora/mcp_servers/<server_name>_mcp.py`, l'enregistre dans
    `<workspace>/.aurora/mcp_config.json`, et effectue immédiatement le handshake
    live (`probe_mcp_tools(..., probe=True)`) pour certifier son fonctionnement."""
    clean_server = re.sub(r"[^a-zA-Z0-9_-]", "-", (server_name or "").strip()).strip("-_")
    if not clean_server:
        raise ValueError("A valid MCP server_name is required")

    ws_root = Path(workspace).expanduser().resolve()
    if server_code and server_code.strip():
        final_code = server_code
        declared_tools = [
            {
                "name": str(t.get("name", "")),
                "description": str(t.get("description", "")),
                "inputSchema": t.get("inputSchema") or t.get("parameters") or {"type": "object"},
            }
            for t in (tools_spec or [])
            if isinstance(t, dict) and t.get("name")
        ]
    else:
        if not tools_spec:
            raise ValueError("Provide either `tools_spec` or `server_code` to create an MCP server")
        final_code = build_jsonrpc_mcp_server_code(
            server_name=clean_server,
            description=description or f"Autonomous MCP server {clean_server}",
            tools_spec=tools_spec,
            helper_imports=helper_imports,
            helper_code=helper_code,
        )
        declared_tools = [
            {
                "name": re.sub(r"[^a-zA-Z0-9_-]", "_", str(t.get("name") or "")),
                "description": str(t.get("description") or ""),
                "inputSchema": t.get("inputSchema") or t.get("parameters") or {"type": "object"},
            }
            for t in tools_spec
            if isinstance(t, dict) and t.get("name")
        ]

    # 1. Audit AST syntaxique & sécurité
    ast_audit = audit_mcp_server_ast(final_code)

    # 2. Écriture atomique du script serveur MCP dans `.aurora/mcp_servers/`
    mcp_dir = ws_root / ".aurora" / "mcp_servers"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    script_path = (mcp_dir / f"{clean_server}_mcp.py").resolve()
    if not script_path.is_relative_to(ws_root):
        raise ValueError("MCP server script path escapes workspace")
    script_path.write_text(final_code, encoding="utf-8")
    try:
        script_path.chmod(0o755)
    except OSError:
        pass

    # 3. Enregistrement atomique dans `<workspace>/.aurora/mcp_config.json`
    cfg_path = ws_root / ".aurora" / "mcp_config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    current_cfg: dict[str, Any] = {}
    if cfg_path.is_file():
        try:
            loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                current_cfg = loaded
        except Exception:
            current_cfg = {}

    servers_map = current_cfg.setdefault("mcpServers", {})
    if not isinstance(servers_map, dict):
        servers_map = {}
        current_cfg["mcpServers"] = servers_map

    py_exec = python_executable or sys.executable or "python3"
    servers_map[clean_server] = {
        "command": py_exec,
        "args": [str(script_path)],
        "description": description or f"Autonomous MCP server {clean_server}",
        "tools": declared_tools,
    }

    fd, tmp_cfg = tempfile.mkstemp(prefix=".mcp-cfg-", dir=str(cfg_path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(current_cfg, stream, ensure_ascii=False, indent=2)
        os.replace(tmp_cfg, cfg_path)
    finally:
        Path(tmp_cfg).unlink(missing_ok=True)

    # 4. Sonde JSON-RPC 2.0 stdio en direct (`initialize` + `tools/list`)
    probe_res = probe_mcp_tools(str(ws_root), clean_server, probe=True, timeout=10.0)
    live_tools = [t for t in probe_res.get("tools", []) if t.get("status") == "live_probed"]

    # 5. Auto-test optionnel d'un outil via `tools/call`
    self_test_result = None
    if self_test_tool and live_tools:
        self_test_result = invoke_mcp_tool(
            str(ws_root),
            clean_server,
            self_test_tool,
            self_test_args or {},
            timeout=10.0,
        )

    return {
        "ok": len(live_tools) > 0 and not probe_res.get("errors"),
        "server": clean_server,
        "script_path": str(script_path),
        "config_path": str(cfg_path),
        "ast_audit": ast_audit,
        "live_probed_tools": live_tools,
        "probe_errors": probe_res.get("errors", []),
        "self_test": self_test_result,
    }
