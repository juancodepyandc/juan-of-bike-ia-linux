"""Tests for module agents, per-module sub-agent creation, 3D texture/PBR guarantees, viewer routing, and self-correction."""
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agi_core.context import (
    create_agent,
    create_module_subagent,
    list_agents_for_module,
    resolve_agent,
)
from agi_core.mission_agent import AutonomousMissionAgent
from agi_core.runtime_policy import RuntimePolicy
from application.agent_registry import (
    AGENTS,
    MODULE_PRIMARY_AGENTS,
    get_module_agent,
    list_module_agents,
)


class TestModuleAgentsAndTextures(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = patch.dict(os.environ, {"AURORA_DATA_DIR": str(self.root / "runtime")})
        env.start()
        self.addCleanup(env.stop)

    def test_every_module_has_dedicated_agent_with_subagent_capability(self):
        expected_modules = {
            "orchestration",
            "chat",
            "code",
            "image",
            "3d",
            "3d-texture",
            "3d-viewer",
            "3d-motion",
            "voice",
            "video",
            "learning",
            "cyber",
            "bridge",
            "cowork",
            "memory",
            "mcp",
            "skills",
            "cli-tunnel",
        }
        for mod in expected_modules:
            with self.subTest(module=mod):
                agent = get_module_agent(mod)
                self.assertIsNotNone(agent, f"Missing module agent for {mod}")
                self.assertTrue(agent.get("can_create_subagents"), f"{mod} lead must support sub-agents")
                mod_list = list_module_agents(mod)
                self.assertTrue(len(mod_list) >= 1)

    def test_each_module_can_create_and_list_its_own_subagents(self):
        for mod in ("code", "3d", "3d-texture", "3d-viewer", "voice", "mcp"):
            sub_name = f"{mod}-sub-specialist"
            created = create_module_subagent(
                mod,
                sub_name,
                f"Sub-agent spécialisé pour le module {mod}",
                preferred_tools=["read_file", "verify"],
                verification_focus=f"Vérification dédiée {mod}",
            )
            self.assertTrue(created["passed"])
            self.assertTrue(created["changed"])
            self.assertEqual(created["module"], mod)
            self.assertTrue(created["can_create_subagents"])

            # Idempotent re-ensure never fails
            reused = create_module_subagent(
                mod,
                sub_name,
                f"Sub-agent spécialisé pour le module {mod}",
            )
            self.assertTrue(reused["passed"])
            self.assertFalse(reused["changed"])

            listed = list_agents_for_module(mod, str(self.root))
            names = {a["name"] for a in listed}
            self.assertIn(sub_name, names)
            lead = get_module_agent(mod)
            self.assertIn(lead["name"], names)

    async def test_module_agent_worker_can_create_and_spawn_its_own_subagent(self):
        parent = AutonomousMissionAgent(
            "mod-delegation",
            "Delegate to 3d-lead which creates and spawns its own 3d-uv-subagent",
            str(self.root),
            "fixture:local",
            "AUTONOMOUS",
            policy=RuntimePolicy(request_audit=False, recovery_attempts=0),
        )
        parent._emit = AsyncMock()
        parent.state["plan"] = ["Delegate to 3d-lead"]
        parent.state["criteria"] = ["Sub-agent output exists"]
        check = {"kind": "file", "path": "uv_report.json", "criterion": "Sub-agent output exists"}

        sub_worker_runs = []

        async def mock_worker_report(agent_self, child):
            if child.depth == 1:
                # Depth-1 module agent (3d-lead) creates its own sub-agent and spawns it
                self.assertTrue(child.can_create_subagents)
                self.assertEqual(child.module, "3d")
                child.state["plan"] = ["Create and run UV sub-agent"]
                child.state["criteria"] = ["UV file written"]
                sub_created = await child._execute(
                    "create_agent",
                    {
                        "name": "3d-uv-subagent",
                        "role": "Unwrap UV islands and write uv_report.json",
                    },
                )
                self.assertTrue(sub_created["changed"])
                self.assertEqual(sub_created["module"], "3d")
                self.assertEqual(sub_created["parent_agent"], "3d-lead")

                sub_check = {"kind": "file", "path": "uv_report.json", "criterion": "UV file written"}
                sub_res = await child._execute(
                    "spawn_agent",
                    {
                        "agent": "3d-uv-subagent",
                        "task": "Write uv_report.json",
                        "checks": [sub_check],
                    },
                )
                self.assertTrue(sub_res["passed"])
                return {
                    "status": "completed",
                    "goal": child.request_text,
                    "report": "3d-lead delegated to 3d-uv-subagent",
                    "criteria": child.state["criteria"],
                    "verified": child.state["criteria"],
                    "executed_tools": ["create_agent", "spawn_agent"],
                    "evidence": [],
                }
            else:
                # Depth-2 sub-agent executes the leaf task and cannot spawn further
                self.assertEqual(child.depth, 2)
                self.assertFalse(child.can_create_subagents)
                with self.assertRaises(PermissionError):
                    child._require_tool("spawn_agent")
                sub_worker_runs.append(child.agent_name)
                (self.root / "uv_report.json").write_text(
                    json.dumps({"uv_islands": 4, "textured": True}), encoding="utf-8"
                )
                return {
                    "status": "completed",
                    "goal": child.request_text,
                    "report": "UV report written",
                    "criteria": ["UV file written"],
                    "verified": ["UV file written"],
                    "executed_tools": ["write_file"],
                    "evidence": [],
                }

        with patch.object(AutonomousMissionAgent, "_worker_report", mock_worker_report):
            res = await parent._execute(
                "spawn_agent",
                {
                    "agent": "3d-lead",
                    "task": "Produce uv_report.json via module sub-agent",
                    "checks": [check],
                },
            )
        self.assertTrue(res["passed"])
        self.assertEqual(sub_worker_runs, ["3d-uv-subagent"])

    def test_3d_texture_detection_and_material_classification_never_skip_textures(self):
        py_services = str(ROOT / "application" / "python-services")
        if py_services not in sys.path:
            sys.path.insert(0, py_services)
        from auto_rescue_mesh import _mesh_has_texture
        from aurora_3d_pipeline import (
            _a_de_la_couleur,
            _a_une_texture_image,
            _explicit_material_requested,
        )
        from material_intel_classifier import classify, to_canonical
        from glb_material_writer import apply_manifest

        # 1. Neutral grey GLB must NOT be treated as already colored or textured
        sphere = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
        sphere.visual = trimesh.visual.TextureVisuals(
            material=trimesh.visual.material.PBRMaterial(
                baseColorFactor=[128, 128, 128, 255],
                roughnessFactor=0.6,
            )
        )
        grey_glb = self.root / "neutral_grey.glb"
        sphere.export(str(grey_glb))

        loaded = trimesh.load(str(grey_glb), force="mesh")
        self.assertFalse(_mesh_has_texture(loaded))
        self.assertFalse(_mesh_has_texture(grey_glb))
        self.assertFalse(_a_de_la_couleur(grey_glb))
        self.assertFalse(_a_une_texture_image(grey_glb))

        # 2. Explicit material/texture prompts are detected
        self.assertTrue(_explicit_material_requested("épée en acier brossé avec poignée en cuir", "prop"))
        self.assertTrue(_explicit_material_requested("table en bois sculpté verni", "prop"))
        self.assertTrue(_explicit_material_requested("personnage avec texture détaillée", "character"))

        # 3. Classify wood/woven/fibrous materials and apply canonical manifest with baseColor to GLB
        with patch.dict(os.environ, {"AURORA_MATINTEL_NO_LLM": "1"}):
            manifest = classify("table en bois sculpté chêne", "prop")
        classes = [z["material_class"] for z in manifest["zones"]]
        self.assertIn("wood", classes)
        manifest["zones"][0]["channels"]["base_color"] = "#8b5a2b"
        canonical = to_canonical(manifest)
        self.assertTrue(len(canonical["zones"]) >= 1)
        self.assertEqual(canonical["zones"][0]["label"], "wood")
        self.assertEqual(canonical["zones"][0]["channels"].get("baseColor"), "#8b5a2b")

        colored_glb = self.root / "colored_wood.glb"
        res = apply_manifest(grey_glb, canonical, colored_glb)
        self.assertTrue(res.get("ok"), f"apply_manifest failed: {res}")
        self.assertTrue(_a_de_la_couleur(colored_glb))

    def test_viewer_routes_output_3d_through_bridge_api_and_never_forbidden_output_path(self):
        viewer_html = (Path(__file__).resolve().parents[1] / "application" / "aurora_viewer.html").read_text(encoding="utf-8")
        self.assertIn("/api/3d/file/", viewer_html)
        self.assertIn("/api/asset/", viewer_html)
        model_view = (Path(__file__).resolve().parents[1] / "application" / "src" / "views" / "ModelView.tsx").read_text(encoding="utf-8")
        self.assertIn("localMeshPath", model_view)
        self.assertIn("_gltfLoader.parse", model_view)
        self.assertIn("auto-rescue", model_view)
        self.assertIn("setWorkspace('model')", model_view)

    async def test_autonomous_mission_self_corrects_on_repeated_unverified_completion(self):
        agent = AutonomousMissionAgent(
            "self-correct",
            "Write exact text 'OK' into status.txt and verify it",
            str(self.root),
            "fixture:local",
            "AUTONOMOUS",
            policy=RuntimePolicy(stall_attempts=2, recovery_attempts=2, request_audit=False),
        )
        agent._emit = AsyncMock()
        agent._review_completion = AsyncMock(return_value={"approved": True, "unmet": [], "reason": "OK"})
        criterion = "status.txt has OK"
        check = {"kind": "text", "path": "status.txt", "equals": "OK", "criterion": criterion}

        replies = iter([
            {"tool": "set_plan", "args": {"steps": ["Write and verify"], "criteria": [criterion], "required_tools": []}},
            {"tool": "write_file", "args": {"path": "status.txt", "content": "OK"}},
            # Premature finish twice without verify -> triggers self-correction recovery instead of aborting
            {"tool": "finish", "args": {"message": "Premature 1"}},
            {"tool": "finish", "args": {"message": "Premature 2"}},
            # After recovery dispatches verify, agent finishes cleanly
            {"tool": "finish", "args": {"message": "Verified after self-correction"}},
        ])

        async def stream(messages):
            yield json.dumps(next(replies))

        async def generate(system, payload, model, **kwargs):
            val = json.loads(payload)
            return json.dumps({
                "request_quote": "Write exact text 'OK' into status.txt",
                "evidence_ids": [val["observations"][-1]["id"]],
                "hypothesis": "status.txt was written but verify was not executed before finish.",
                "expected_observation": "Running verify on status.txt marks the criterion verified.",
                "next_action": {"tool": "verify", "args": {"checks": [check]}},
            })

        with patch.object(agent, "_chat_chunks", stream), patch.object(agent.gateway, "generate", generate):
            result = await agent.run()
        self.assertEqual(result, "Verified after self-correction")
        self.assertEqual(agent.state["status"], "completed")
        self.assertEqual(agent.state["verified"], [criterion])


if __name__ == "__main__":
    unittest.main()
