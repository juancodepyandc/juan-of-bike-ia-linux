"""Runtime contracts using temporary data and deterministic model substitutes."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import AsyncMock

from agi_core.bus import AsyncEventBus, probe_sync
from agi_core.context import create_skill, create_agent, load_context
from agi_core.memory import OmniscientMemory
from agi_core.mission_agent import AutonomousMissionAgent


class ContextContracts(unittest.TestCase):
    def test_created_skill_is_used_without_overwriting_existing_instructions(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(create_skill(root, "check-evidence", "Vérifier", "Compare actual tool outputs."))
            before = path.read_bytes()
            context = load_context(root)
            self.assertIn("Compare actual tool outputs.", context["skills_context"])
            with self.assertRaises(FileExistsError):
                create_skill(root, "check-evidence", "Changed", "Changed")
            self.assertEqual(path.read_bytes(), before)

    def test_mcp_config_is_counted_without_claiming_availability_or_leaking_env(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / ".aurora"
            folder.mkdir()
            (folder / "mcp_config.json").write_text(json.dumps({"mcpServers": {
                "example": {"tools": [{"name": "inspect"}], "env": {"TOKEN": "never-in-context"}}}}))
            context = load_context(root)
            self.assertEqual(context["mcp_tools_count"], 1)
            self.assertEqual(context["mcp_status"], "configured_unverified")
            self.assertNotIn("never-in-context", json.dumps(context))

    def test_saved_agent_preserves_registry_and_rejects_duplicate(self):
        with tempfile.TemporaryDirectory() as root, patch.dict("os.environ", {"XDG_DATA_HOME": root}):
            saved = create_agent("reviewer", "Check delivery evidence", "model:local", "AUTONOMOUS", "mis_test")
            store = Path(root) / "aurora/dynamic_agents.json"
            self.assertEqual(json.loads(store.read_text())["agents"][0], saved)
            with self.assertRaises(ValueError):
                create_agent("reviewer", "Replace", "model:local", "FULL", "other")
            self.assertEqual(len(json.loads(store.read_text())["agents"]), 1)

    def test_direct_tools_apply_scope_to_workers(self):
        with tempfile.TemporaryDirectory() as root:
            safe = AutonomousMissionAgent("mis_test", "inspect", root, "model:local", "SAFE")
            safe._require_tool("read_file")
            for tool in ("write_file", "run_command", "create_skill", "spawn_agent"):
                with self.assertRaises(PermissionError):
                    safe._require_tool(tool)
            with self.assertRaises(PermissionError):
                safe._file_path("../outside")
            external = Path(root).parent / "link-target"
            (Path(root) / "link").symlink_to(external)
            with self.assertRaises(PermissionError):
                safe._file_path("link/secret")

    def test_corrupt_agent_registry_is_preserved(self):
        with tempfile.TemporaryDirectory() as root, patch.dict("os.environ", {"XDG_DATA_HOME": root}):
            store = Path(root) / "aurora/dynamic_agents.json"
            store.parent.mkdir()
            store.write_text("broken-data")
            with self.assertRaises(ValueError):
                create_agent("reviewer", "Inspect", "model:local", "AUTONOMOUS", "mis_test")
            self.assertEqual(store.read_text(), "broken-data")


class AsyncContracts(unittest.IsolatedAsyncioTestCase):
    async def test_named_worker_cannot_escalate_parent_permissions(self):
        with tempfile.TemporaryDirectory() as root, patch.dict("os.environ", {"XDG_DATA_HOME": root}):
            create_agent("reviewer", "Check files", "model:local", "FULL", "mis_test")
            parent = AutonomousMissionAgent("mis_test", "Inspect", root, "model:local", "AUTONOMOUS")
            observed = []
            async def run_worker(child, *, worker=False):
                observed.append(child.permissions)
                child.state['status'] = 'completed'
                return "Checked"
            with patch.object(AutonomousMissionAgent, "run", run_worker):
                result = await parent._spawn_task("Inspect", "reviewer")
                self.assertEqual(result['report'], "Checked")
                self.assertEqual(result['status'], "completed")
            self.assertEqual(observed, ["AUTONOMOUS"])

    async def test_mission_runs_two_workers_concurrently_without_inference(self):
        with tempfile.TemporaryDirectory() as root:
            from agi_core.runtime_policy import RuntimePolicy
            parent = AutonomousMissionAgent("mis_test", "Inspect", root, "model:local", policy=RuntimePolicy(parallel_workers=2,request_audit=False))
            (Path(root)/'reports.txt').write_text('concurrency fixture')
            replies = iter([json.dumps({"tool":"set_plan","args":{"steps":["Collect reports"],"criteria":["Reports fixture"]}}),
                            json.dumps({"tool": "spawn_agent", "args": {"tasks": ["One", "Two"],"checks":[{"kind":"file","path":"reports.txt","criterion":"Reports fixture"}]}}),
                            json.dumps({"tool":"verify","args":{"checks":[{"kind":"file","path":"reports.txt","criterion":"Reports fixture"}]}}),
                            json.dumps({"tool": "finish", "args": {"message": "Reports collected"}})])
            active, maximum = 0, 0
            async def chat(messages):
                yield next(replies)
            async def worker(task, *, acceptance_checks=()):
                nonlocal active, maximum
                active += 1
                maximum = max(maximum, active)
                await asyncio.sleep(0.01)
                active -= 1
                return {'status':'completed','report':'Checked '+task,'goal':task}
            with patch.object(parent, "_chat_chunks", chat), patch.object(parent, "_run_sub_agent", worker), patch.object(parent, "_emit", AsyncMock()), patch.object(parent,"_review_completion",AsyncMock(return_value={"approved":True,"unmet":[],"reason":"Concurrency test only"})):
                self.assertEqual(await parent.run(), "Reports collected")
            self.assertEqual(maximum, 2)
            reports = next(e for e in parent.state['evidence'] if e['tool']=='spawn_agent')
            self.assertTrue(reports['ok'])
            self.assertEqual(len(reports['result']['workers']),2)

    async def test_concurrent_agent_creation_keeps_both_roles(self):
        with tempfile.TemporaryDirectory() as root, patch.dict("os.environ", {"XDG_DATA_HOME": root}):
            await asyncio.gather(*(asyncio.to_thread(create_agent, name, "Inspect", "model:local", "AUTONOMOUS", "mis_test")
                                   for name in ("first", "second")))
            store = json.loads((Path(root) / "aurora/dynamic_agents.json").read_text())
            self.assertEqual({a["name"] for a in store["agents"]}, {"first", "second"})

    async def test_bus_health_requires_an_actual_mission_subscriber(self):
        bus = AsyncEventBus()
        server = await asyncio.start_server(bus._handle_client, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            before = await asyncio.to_thread(probe_sync, port=port)
            self.assertTrue(before["ok"])
            self.assertFalse(before["mission_ready"])
            bus.subscribe("mission.start", lambda _: None)
            self.assertTrue((await asyncio.to_thread(probe_sync, port=port))["mission_ready"])
        finally:
            server.close()
            await server.wait_closed()

    async def test_sqlite_memory_survives_restart_without_vector_dependencies(self):
        with tempfile.TemporaryDirectory() as root, patch.dict("sys.modules", {"chromadb": None}):
            memory = OmniscientMemory(root)
            await memory.embed_experience("repair graphics driver", "Module matched to kernel", {})
            restarted = OmniscientMemory(root)
            self.assertIn("Module matched", (await restarted.query_experience("graphics"))[0])
            self.assertEqual(await restarted.query_experience("unrelated-query"), [])
