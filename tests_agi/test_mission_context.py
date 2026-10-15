import unittest
import tempfile
import os
import json
from agi_core.mission_agent import _cli_load_context_for_workspace

class TestMissionContext(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace = self.tmp_dir.name

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_discover_custom_skills(self):
        # Create a mock skill
        skill_dir = os.path.join(self.workspace, ".aurora", "skills", "code-architect")
        os.makedirs(skill_dir, exist_ok=True)
        skill_file = os.path.join(skill_dir, "SKILL.md")
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write("---\nname: code-architect\ndescription: Expert in robust system architecture\n---\n# Skill Content")

        ctx = _cli_load_context_for_workspace(self.workspace)
        self.assertEqual(ctx["skills_count"], 1)
        self.assertIn("code-architect", ctx["skills_summary"])
        self.assertIn("Expert in robust system architecture", ctx["skills_summary"])

    def test_discover_mcp_servers(self):
        # Create a mock mcp_config.json
        aurora_dir = os.path.join(self.workspace, ".aurora")
        os.makedirs(aurora_dir, exist_ok=True)
        mcp_file = os.path.join(aurora_dir, "mcp_config.json")
        with open(mcp_file, "w", encoding="utf-8") as f:
            json.dump({
                "mcpServers": {
                    "git-server": {"tools": [{"name": "git_status"}, {"name": "git_diff"}]},
                    "fs-server": {"tools": [{"name": "read_dir"}]}
                }
            }, f)

        ctx = _cli_load_context_for_workspace(self.workspace)
        self.assertEqual(ctx["mcp_tools_count"], 3)

    def test_skill_triggers_and_official_agent_resolution(self):
        from agi_core.context import discover_skills, resolve_agent
        skill_dir = os.path.join(self.workspace, ".aurora", "skills", "mesh-audit")
        os.makedirs(skill_dir, exist_ok=True)
        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: mesh-audit\ndescription: Verify watertight meshes\ntriggers:\n  - glb\n  - mesh\n---\n# Instructions")
        skills = discover_skills(self.workspace)
        skill = next(s for s in skills if s["name"] == "mesh-audit")
        self.assertEqual(skill["triggers"], ["glb", "mesh"])

        code_lead = resolve_agent("code-lead", self.workspace)
        self.assertIsNotNone(code_lead)
        self.assertEqual(code_lead["domain"], "code")
        self.assertIn("search_code", code_lead["preferred_tools"])
        self.assertTrue(code_lead["role"])

    def test_search_code_and_mcp_stdio_tools(self):
        import asyncio
        import sys
        from pathlib import Path
        from types import SimpleNamespace
        from agi_core.mission_tools import MissionTools

        src_dir = Path(self.workspace) / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "engine.py").write_text("def compute_kinematics(angle: float) -> float:\n    return angle * 2.0\n", encoding="utf-8")

        fake_agent = SimpleNamespace(
            workspace=self.workspace,
            permissions="AUTONOMOUS",
            _file_path=lambda p=".": (Path(self.workspace) / p).resolve() if p else Path(self.workspace).resolve(),
            _require_tool=lambda name: None,
        )
        tools = MissionTools(fake_agent, Path(self.workspace), sys.executable)
        search_res = asyncio.run(tools.execute("search_code", {"query": "compute_kinematics", "path": "src"}))
        self.assertEqual(search_res["total_matches"], 1)
        self.assertEqual(search_res["matches"][0]["relative_path"], "src/engine.py")
        self.assertIn("def compute_kinematics", search_res["matches"][0]["content"])

        mcp_script = Path(self.workspace) / "mock_mcp.py"
        mcp_script.write_text(
            "import json, sys\n"
            "for line in sys.stdin:\n"
            "    msg = json.loads(line)\n"
            "    mid = msg.get('id')\n"
            "    method = msg.get('method')\n"
            "    if method == 'initialize':\n"
            "        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': mid, 'result': {'protocolVersion': '2024-11-05'}}) + '\\n')\n"
            "    elif method == 'tools/list':\n"
            "        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': mid, 'result': {'tools': [{'name': 'echo_val', 'description': 'Echo value'}]}})+ '\\n')\n"
            "    elif method == 'tools/call':\n"
            "        val = msg.get('params', {}).get('arguments', {}).get('x', '')\n"
            "        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': mid, 'result': {'content': [{'type': 'text', 'text': f'ECHO:{val}'}]}})+ '\\n')\n"
            "    sys.stdout.flush()\n",
            encoding="utf-8",
        )
        mcp_cfg = Path(self.workspace) / ".mcp.json"
        mcp_cfg.write_text(json.dumps({
            "mcpServers": {
                "local-echo": {
                    "command": sys.executable,
                    "args": [str(mcp_script)],
                }
            }
        }), encoding="utf-8")

        listed = asyncio.run(tools.execute("list_mcp_tools", {"probe": True}))
        self.assertEqual(listed["total"], 1)
        self.assertEqual(listed["tools"][0]["name"], "echo_val")
        called = asyncio.run(tools.execute("call_mcp_tool", {"server": "local-echo", "tool": "echo_val", "arguments": {"x": "42"}}))
        self.assertIn("ECHO:42", json.dumps(called))

if __name__ == "__main__":
    unittest.main()

