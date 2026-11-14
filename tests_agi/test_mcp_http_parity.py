"""Actual Flask endpoints and actual MCP pipes, without importing the running bridge."""
import ast
import json
from pathlib import Path
import sys
import tempfile
import unittest

from flask import Blueprint, Flask, g, jsonify, request

from agi_core.mcp_transport import close_mcp_sessions


class MCPHttpParity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        server = {"command": sys.executable, "args": [str(Path(__file__).with_name("fixtures") / "mcp_catalog_server.py")],
                  "persistent": True, "env": {"FIXTURE_PRIVATE_TOKEN": "private-test-value"}}
        (self.root / ".mcp.json").write_text(json.dumps({"mcpServers": {"fixture": server}}))
        source = Path(__file__).resolve().parents[1] / "application/routes/cli_bp_routes.py"
        names = {"_cli_auth_required", "_cli_discover_mcp", "_cli_mcp_rpc", "cli_mcp_list", "cli_mcp_tools",
                 "cli_mcp_call", "_cli_mcp_read_operation", "cli_mcp_catalog", "cli_mcp_context_operation"}
        functions = [node for node in ast.parse(source.read_text()).body if isinstance(node, ast.FunctionDef) and node.name in names]
        self.assertEqual(len(functions), len(names))
        def authenticate():
            token = request.headers.get("Authorization")
            return token in {"Bearer owner", "Bearer safe"}, {"permissions": "SAFE" if token == "Bearer safe" else "STANDARD"}, "unauthorized"
        bp = Blueprint("mcp_contract", __name__)
        namespace = {"request": request, "g": g, "jsonify": jsonify, "cli_bp": bp,
                     "WORKSPACE": str(self.root), "_ext_auth": authenticate, "_CLI_MCP_SPAWN_TIMEOUT": 12}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)
        app = Flask(__name__)
        app.register_blueprint(bp)
        self.client = app.test_client()
        self.headers = {"Authorization": "Bearer owner"}

    def tearDown(self):
        close_mcp_sessions()
        self.temp.cleanup()

    def test_shared_transport_preserves_state_and_pagination_via_http(self):
        listed = self.client.get("/api/cli/mcp/tools", headers=self.headers).json
        self.assertEqual([t["name"] for t in listed["tools"]], ["first", "second"])
        before = self.client.post("/api/cli/mcp/call", headers=self.headers, json={"server": "fixture", "tool": "pid"}).json
        resource = self.client.post("/api/cli/mcp/resource", headers=self.headers, json={"server": "fixture", "uri": "native://document"}).json
        self.assertTrue(resource["ok"])
        after = self.client.post("/api/cli/mcp/call", headers=self.headers, json={"server": "fixture", "tool": "pid"}).json
        self.assertEqual(before["result"], after["result"])
        self.assertTrue(self.client.post("/api/cli/mcp/close", headers=self.headers, json={"server": "fixture"}).json["result"]["closed"])

    def test_credentials_not_returned_by_catalog_and_no_anonymous_execution(self):
        response = self.client.get("/api/cli/mcp/list", headers=self.headers)
        self.assertNotIn("private-test-value", response.get_data(as_text=True))
        self.assertNotIn("env", response.json["servers"][0])
        self.assertEqual(self.client.get("/api/cli/mcp/tools").status_code, 401)

    def test_safe_keys_can_inspect_declarations_but_not_execute_context_operations(self):
        headers = {"Authorization": "Bearer safe"}
        self.assertEqual(self.client.get("/api/cli/mcp/tools", headers=headers).json["total"], 0)
        for path, data in (("call", {"tool": "pid"}), ("resource", {"uri": "native://document"}),
                           ("prompt", {"name": "review"}), ("close", {})):
            self.assertEqual(self.client.post(f"/api/cli/mcp/{path}", headers=headers, json={"server": "fixture", **data}).status_code, 403)
        self.assertEqual(self.client.get("/api/cli/mcp/catalog?server=fixture&kind=tools", headers=headers).status_code, 403)

    def test_context_routes_preserve_explicit_cursor_and_string_arguments(self):
        first = self.client.get("/api/cli/mcp/catalog?server=fixture&kind=tools", headers=self.headers).json["result"]
        second = self.client.get("/api/cli/mcp/catalog", headers=self.headers,
                                 query_string={"server": "fixture", "kind": "tools", "cursor": first["next_cursor"]}).json["result"]
        self.assertEqual(second["items"][0]["name"], "second")
        prompt = self.client.post("/api/cli/mcp/prompt", headers=self.headers,
                                  json={"server": "fixture", "name": "review", "arguments": {"document": "Selected text"}}).json
        self.assertTrue(prompt["ok"])
        self.assertEqual(prompt["result"]["result"]["messages"][0]["content"]["text"], "Selected text")
