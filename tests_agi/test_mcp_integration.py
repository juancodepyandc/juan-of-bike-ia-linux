import unittest
import asyncio
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from agi_core.mission_tools import MissionTools

class TestMCPIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_run_mcp_tool_success(self):
        # Create a mock agent and workspace
        agent = MagicMock()
        workspace = tempfile.mkdtemp()
        agent.workspace = workspace

        # Create a dummy .mcp.json
        resp_init = '{"jsonrpc": "2.0", "id": "init_mock", "result": {"protocolVersion": "2024-11-05"}}'
        resp_call = '{"jsonrpc": "2.0", "id": "call_mock", "result": {"success": true}}'
        resp_str = f"{resp_init}\\n{resp_call}"

        mcp_config = {
            "mcpServers": {
                "test-server": {
                    "command": "python",
                    "args": ["-c", f"import sys; print('{resp_str}')"]
                }
            }
        }
        with open(os.path.join(workspace, ".mcp.json"), "w") as f:
            json.dump(mcp_config, f)

        tools = MissionTools(agent, "/tmp", "python")

        args = {
            "server_name": "test-server",
            "tool_name": "dummy_tool",
            "args": {}
        }

        result = await tools.execute('run_mcp_tool', args)

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['result']['success'], True)

    async def test_run_mcp_tool_server_not_found(self):
        agent = MagicMock()
        agent.workspace = "/tmp"
        tools = MissionTools(agent, "/tmp", "python")

        args = {
            "server_name": "non_existent_server",
            "tool_name": "dummy_tool",
            "args": {}
        }

        with patch('agi_core.context.discover_mcp', return_value=[]):
            result = await tools.execute('run_mcp_tool', args)

        self.assertEqual(result['status'], 'error')
        self.assertIn('not found', result['message'])

if __name__ == '__main__':
    unittest.main()
