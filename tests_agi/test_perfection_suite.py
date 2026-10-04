import unittest
import asyncio
import tempfile
import os
import shutil
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from agi_core.bus import AsyncEventBus, global_bus
from agi_core.llm_gateway import LLMGateway
from agi_core.memory import OmniscientMemory
from agi_core.mission_agent import _cli_load_context_for_workspace
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "aurora-remote-cli"))
from aurora_cli.transfers import receive_file, _digest

class TestPerfectionLoop(unittest.IsolatedAsyncioTestCase):
    """
    Contrats ciblés hors ligne : bus local, découverte et livraison de fichiers.
    Les modèles sont substitués ; cette suite ne mesure pas leur qualité.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    async def test_module_conversation_llm_gateway_resilience(self):
        """Vérifie la résolution dynamique et la résilience de la passerelle neuronale."""
        gateway = LLMGateway()
        with patch.object(gateway, "get_available_models", AsyncMock(return_value=[gateway.default_model])):
            available_models = await gateway.get_available_models()
            self.assertIsInstance(available_models, list)
            resolved = await gateway.resolve_model()
        self.assertTrue(len(resolved) > 0)
        self.assertIn(":", resolved)

    async def test_module_mission_ipc_bus_stream_integrity(self):
        """Vérifie le dispatch local, sans transport TCP ni modèle réel."""
        events_received = []
        async def on_event(payload):
            events_received.append(payload)

        global_bus.subscribe("perfection.mission.event", on_event)

        # Envoi de 10 événements séquentiels complexes
        for i in range(10):
            await global_bus.publish("perfection.mission.event", {
                "step": f"step_{i}",
                "data": {"value": i * 42, "checksum": f"chk_{i}"}
            })
        await asyncio.sleep(0.1)

        self.assertEqual(len(events_received), 10)
        for i, ev in enumerate(events_received):
            self.assertEqual(ev["step"], f"step_{i}")
            self.assertEqual(ev["data"]["value"], i * 42)

    def test_module_cyber_and_cowork_sandbox_traversal_defense(self):
        """Rejette les cas de traversée de chemin inclus dans ce corpus."""
        attacks = [
            {"filename": "../../../../etc/shadow"},
            {"filename": "..\\..\\windows\\system32\\cmd.exe"},
            {"filename": "/root/.ssh/id_rsa"},
            {"filename": "sub/../../../../secret.key"},
            {"filename": "safe/../../../outside.txt"},
            {"filename": "file\x00escape.txt"},
        ]
        for attack in attacks:
            with self.subTest(filename=attack["filename"]):
                with self.assertRaises(ValueError):
                    receive_file(attack, client=None, workspace=self.workspace)

    def test_module_context_deep_discovery(self):
        """Vérifie la découverte multi-niveaux et l'extraction de métadonnées pour skills et MCP."""
        skills_dir = self.workspace / ".aurora" / "skills" / "quantum-optimizer"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: quantum-optimizer\ndescription: Ultra-complex multi-variable optimization engine\n---\n# Docs",
            encoding="utf-8"
        )

        mcp_file = self.workspace / ".aurora" / "mcp_config.json"
        mcp_file.write_text(json.dumps({
            "mcpServers": {
                "neural-cuda": {
                    "tools": [{"name": "gemm_fp8"}, {"name": "attention_flash"}]
                }
            }
        }), encoding="utf-8")

        ctx = _cli_load_context_for_workspace(str(self.workspace))
        self.assertEqual(ctx["skills_count"], 1)
        self.assertEqual(ctx["mcp_tools_count"], 2)
        self.assertIn("quantum-optimizer", ctx["skills_summary"])
        self.assertIn("Ultra-complex", ctx["skills_summary"])

if __name__ == "__main__":
    unittest.main()
