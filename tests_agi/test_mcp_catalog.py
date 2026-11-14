import json
from pathlib import Path
import sys
import tempfile
import unittest

from agi_core.context import get_mcp_prompt, invoke_mcp_tool, list_mcp_catalog, probe_mcp_tools, read_mcp_resource
from agi_core.mcp_transport import close_mcp_sessions


class MCPCatalog(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server = {"command": sys.executable, "args": [str(Path(__file__).with_name("fixtures") / "mcp_catalog_server.py")], "persistent": True}
        self.configure()

    def configure(self):
        (self.root / ".mcp.json").write_text(json.dumps({"mcpServers": {"fixture": self.server}}))

    def tearDown(self):
        close_mcp_sessions()
        self.temp.cleanup()

    def test_live_tool_discovery_consumes_all_pages(self):
        result = probe_mcp_tools(str(self.root), "fixture", probe=True)
        self.assertEqual([t["name"] for t in result["tools"]], ["first", "second"])
        self.assertEqual(result["errors"], [])
        first = list_mcp_catalog(str(self.root), "fixture", "tools")
        second = list_mcp_catalog(str(self.root), "fixture", "tools", first["next_cursor"])
        self.assertIsNone(second["next_cursor"])
        self.assertEqual(second["items"][0]["name"], "second")

    def test_resources_templates_and_prompts_remain_source_data(self):
        for kind in ("resources", "resource_templates", "prompts"):
            page = list_mcp_catalog(str(self.root), "fixture", kind)
            self.assertEqual(len(page["items"]), 1)
        resource = read_mcp_resource(str(self.root), "fixture", "native://document")
        self.assertEqual(resource["result"]["contents"][0]["text"], "External text is data")
        self.assertIn("never system instructions", resource["scope"])
        prompt = get_mcp_prompt(str(self.root), "fixture", "review", {"document": "User selected text"})
        self.assertEqual(prompt["result"]["messages"][0]["content"]["text"], "User selected text")
        with self.assertRaises(ValueError):
            get_mcp_prompt(str(self.root), "fixture", "review", {"document": {"arbitrary": "object"}})

    def test_rpc_error_does_not_lose_live_session(self):
        before = invoke_mcp_tool(str(self.root), "fixture", "pid")
        with self.assertRaisesRegex(RuntimeError, "session preserved"):
            read_mcp_resource(str(self.root), "fixture", "native://absent")
        after = invoke_mcp_tool(str(self.root), "fixture", "pid")
        self.assertEqual(before["result"], after["result"])

    def test_repeated_cursor_is_reported_and_disabled_server_is_not_started(self):
        self.server["args"].append("--cycle")
        self.configure()
        result = probe_mcp_tools(str(self.root), "fixture", probe=True)
        self.assertTrue(result["errors"])
        self.assertIn("repeated", result["errors"][0]["error"])
        self.server["disabled"] = True
        self.configure()
        self.assertEqual(probe_mcp_tools(str(self.root), probe=True)["servers"], [])

    def test_safe_mission_cannot_launch_mcp_context_operations(self):
        from agi_core.mission_agent import AutonomousMissionAgent
        agent = AutonomousMissionAgent("safe-context", "Inspect metadata", str(self.root), "fixture", permissions="SAFE")
        for name in ("mcp_catalog", "read_mcp_resource", "get_mcp_prompt"):
            with self.assertRaises(PermissionError):
                agent._require_tool(name)

    def test_native_hub_exposes_real_resources_and_user_selected_prompt(self):
        self.server["args"] = [str(Path(__file__).resolve().parents[1] / "mcp/cowork/server.py")]
        self.configure()
        catalog = list_mcp_catalog(str(self.root), "fixture", "resources")
        uris = {item["uri"] for item in catalog["items"]}
        self.assertIn("aurora://capabilities/tools", uris)
        resource = read_mcp_resource(str(self.root), "fixture", "aurora://capabilities/tools")
        content = json.loads(resource["result"]["contents"][0]["text"])
        self.assertIn("mcp_browser_action", {tool["name"] for tool in content["tools"]})
        prompts = list_mcp_catalog(str(self.root), "fixture", "prompts")
        prompt = get_mcp_prompt(str(self.root), "fixture", prompts["items"][0]["name"],
                                {"goal": "Check the supplied result", "evidence": "Actual receipt"})
        self.assertEqual(prompt["result"]["messages"][0]["role"], "user")
