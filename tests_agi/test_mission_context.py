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

if __name__ == "__main__":
    unittest.main()
