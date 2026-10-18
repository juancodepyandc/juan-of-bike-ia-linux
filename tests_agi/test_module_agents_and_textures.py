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
    get_master_agents,
    get_module_agent,
    get_module_hierarchy,
    list_module_agents,
    resolve_agent_for_target,
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
            "conversation",
            "chat",
            "code",
            "image",
            "drawing",
            "3d",
            "3d-texture",
            "3d-viewer",
            "3d-motion",
            "voice",
            "video",
            "learning",
            "simulator",
            "cyber",
            "business",
            "training",
            "missions",
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

    def test_master_and_feature_subagents_disjoint_hierarchy(self):
        masters = get_master_agents()
        self.assertGreaterEqual(len(masters), 19)
        hierarchy = get_module_hierarchy()
        self.assertEqual(hierarchy["schema_version"], "aurora.hierarchy.v2")
        self.assertGreaterEqual(hierarchy["total_agents"], 95)

        for mod_name, mod_data in hierarchy["modules"].items():
            with self.subTest(module=mod_name):
                master = mod_data["master"]
                self.assertIsNotNone(master, f"Module {mod_name} must have a Master Agent")
                subs = mod_data["feature_subagents"]
                self.assertGreaterEqual(len(subs), 2, f"Module {mod_name} must have dedicated Feature Sub-Agents")
                seen_features = set()
                for sub in subs:
                    self.assertEqual(sub["role_type"], "subagent")
                    self.assertTrue(sub.get("parent_agent") or sub.get("parent_master"))
                    feature = sub.get("feature", "")
                    self.assertTrue(feature, f"Sub-agent {sub['name']} must declare an exclusive feature")
                    self.assertNotIn(feature, seen_features, f"Duplicate feature {feature} in module {mod_name}")
                    seen_features.add(feature)
                    self.assertTrue(
                        sub.get("files_owned") or sub.get("routes_owned"),
                        f"Sub-agent {sub['name']} must declare files_owned or routes_owned",
                    )
                    self.assertTrue(
                        sub.get("never_touch"),
                        f"Sub-agent {sub['name']} must declare never_touch boundaries",
                    )

        # Verify deterministic resolution for specific files/routes/features
        r_3d_cad = resolve_agent_for_target("3d-cad-engineering")
        self.assertEqual(r_3d_cad["selected_agent"]["name"], "3d-cad-engineering")
        self.assertEqual(r_3d_cad["master_agent"]["name"], "3d-lead")

        r_img_stop = resolve_agent_for_target("image-job-cancellation")
        self.assertEqual(r_img_stop["selected_agent"]["name"], "image-job-cancellation")
        self.assertEqual(r_img_stop["master_agent"]["name"], "image-lead")

        r_code_design = resolve_agent_for_target("code-design-architect")
        self.assertEqual(r_code_design["selected_agent"]["name"], "code-design-architect")
        self.assertEqual(r_code_design["master_agent"]["name"], "code-lead")

    def test_workspace_and_global_agent_md_and_agi_brain_router(self):
        from agi_core.agi_brain import AGIBrainRouter, discover_markdown_agents
        from application.agent_registry import materialize_agent_md_files

        sync_res = materialize_agent_md_files(
            workspace_dir=str(self.root / "ws"),
            global_dir=str(self.root / "gl"),
        )
        self.assertTrue(sync_res["ok"])
        self.assertEqual(sync_res["total_agents"], len(AGENTS))

        ws_dir = Path(sync_res["workspace_agents_dir"])
        gl_dir = Path(sync_res["global_agents_dir"])
        for agent_name in ("aurora-orchestrator", "3d-lead", "3d-cad-engineering", "image-lead", "image-job-cancellation", "code-lead", "code-design-architect"):
            self.assertTrue((ws_dir / agent_name / "agent.md").is_file(), f"Missing Workspace agent.md for {agent_name}")
            self.assertTrue((gl_dir / agent_name / "agent.md").is_file(), f"Missing Global agent.md for {agent_name}")

        discovered = discover_markdown_agents(self.root / "ws")
        self.assertGreaterEqual(len(discovered), len(AGENTS))

        router = AGIBrainRouter(ROOT)
        plan_cad = router.plan_execution("Génère une pièce mécanique CAO B-Rep paramétrique STEP et STL avec assemblage sans collision BVH", active_module="3d")
        self.assertTrue(plan_cad["ok"])
        self.assertIn("3d-lead", plan_cad["masters_involved"])
        applicator_names = [a["applicator_agent"] for a in plan_cad["applicators"]]
        self.assertTrue(
            "3d-cad-engineering" in applicator_names or "3d-assembly-kinematics" in applicator_names,
            f"Expected 3D CAD or Assembly applicator in {applicator_names}",
        )
        self.assertTrue(plan_cad["anti_drift_contract"]["zero_mixing"])

    def test_autonomous_agi_operational_loops_firewall_and_self_healing(self):
        import tempfile
        from agi_core.agi_loops import (
            LOOP_PHASES,
            CognitiveExecutiveLoop,
            EpisodicSkillEvolutionLoop,
            ScopeFirewallEnforcementLoop,
            SelfHealingDiagnosticLoop,
        )

        loop = CognitiveExecutiveLoop(ROOT)
        plan = loop.build_autonomous_loop_plan(
            "Conçois un assemblage CAO STEP et génère les textures PBR 8K et vérifie le score financier business",
            active_module="3d",
        )
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["schema_version"], "aurora.agi_loops.v2")
        self.assertEqual(tuple(plan["loop_phases"]), LOOP_PHASES)
        self.assertEqual(len(plan["phases_trace"]), 7)
        self.assertGreaterEqual(len(plan["dag_nodes"]), 2)
        self.assertEqual(len(plan["operational_loops"]), 8)
        self.assertTrue(all(plan["operational_loops"].values()))
        self.assertIn("counterfactual_evaluation", plan)
        self.assertEqual(len(plan["counterfactual_evaluation"]["hypotheses"]), 3)
        self.assertGreaterEqual(len(plan["handoff_contracts"]), 1)

        # Firewall must block never_touch breaches and TODO placeholders
        fw = ScopeFirewallEnforcementLoop(loop.router)
        ok_check = fw.validate_action(
            "3d-cad-engineering",
            target_files=["application/engineering_design_api.py"],
            proposed_content="def build_solid():\n    return True\n",
        )
        self.assertTrue(ok_check["ok"])

        breach_check = fw.validate_action(
            "3d-cad-engineering",
            target_files=["application/python-services/aurora_hunyuan/hunyuan3d_run.py"],
            proposed_content="def stub():\n    # TODO: implement later\n    raise NotImplementedError\n",
        )
        self.assertFalse(breach_check["ok"])
        violation_types = {v["type"] for v in breach_check["violations"]}
        self.assertIn("never_touch_breach", violation_types)
        self.assertIn("anti_placeholder_breach", violation_types)

        # Self-healing diagnostic loop must classify errors and assign the right applicator
        healer = SelfHealingDiagnosticLoop(loop.router)
        diag = healer.diagnose_and_plan_repair(
            "ModuleNotFoundError: No module named 'business_intelligence' in application/bridge_server.py",
            failing_file="application/bridge_server.py",
        )
        self.assertTrue(diag["ok"])
        self.assertEqual(diag["signature_id"], "python_module_not_found")
        self.assertEqual(diag["extracted_symbol"], "business_intelligence")
        self.assertTrue(diag["assigned_applicator"])

        # Goal Watchdog loop must detect tool oscillation and semantic drift
        wd_res = loop.watchdog.evaluate_trajectory(
            "Génère un assemblage CAO STEP paramétrique avec visserie ISO",
            executed_steps=[
                {"tool": "read_file", "target": "foo.py"},
                {"tool": "read_file", "target": "foo.py"},
                {"tool": "read_file", "target": "foo.py"},
            ],
            current_output="unrelated text",
        )
        self.assertTrue(wd_res["oscillation_detected"])
        self.assertTrue(wd_res["needs_course_correction"])

        # Episodic skill evolution loop records and persists telemetry
        with tempfile.TemporaryDirectory() as tmp_dir:
            evo = EpisodicSkillEvolutionLoop(tmp_dir)
            state = evo.record_cycle(
                request="Test cycle AGI",
                complexity="multi_module",
                masters=["3d-lead", "business-ceo"],
                applicators=["3d-cad-engineering", "business-financial-analyst"],
                verified=True,
                self_healed=True,
                notes="Auto-healed and verified",
            )
            self.assertEqual(state["total_cycles"], 1)
            self.assertEqual(state["successful_cycles"], 1)
            self.assertEqual(state["self_healed_cycles"], 1)
            self.assertEqual(state["applicator_stats"]["3d-cad-engineering"]["verified"], 1)

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

    def test_scientific_oracle_math_and_cyber_formal_verification(self):
        services_dir = ROOT / "application" / "python-services"
        if str(services_dir) not in sys.path:
            sys.path.insert(0, str(services_dir))
        from scientific_oracle import (
            analyze_cyber_code_dynamically,
            verify_mathematical_conjecture,
        )

        # 1. Exact algebraic & Z3 SMT theorem proving
        valid = verify_mathematical_conjecture("(a + b)**2 == a**2 + 2*a*b + b**2", domain="int")
        self.assertEqual(valid["status"], "PROVEN_VALID")
        self.assertTrue(valid["algebraic_identity"])

        # 2. Falsification of a false conjecture with concrete Z3 counterexample
        false_conj = verify_mathematical_conjecture("n**2 > 2*n", domain="pos_int")
        self.assertEqual(false_conj["status"], "FALSIFIED")
        self.assertIsNotNone(false_conj["counterexample"])
        n_val = int(false_conj["counterexample"]["n"])
        self.assertFalse(n_val**2 > 2 * n_val)

        # 3. Dynamic 0-day AST + Z3 BitVec32 & TOCTOU analysis
        vuln_code = (
            "async def process_packet(pkt_id, offset, length, data):\n"
            "    if offset + length <= 1024:\n"
            "        await record_audit(pkt_id)\n"
            "        return data[offset]\n"
        )
        cyber = analyze_cyber_code_dynamically(vuln_code, language="python")
        self.assertEqual(cyber["analyzed_function"], "process_packet")
        self.assertEqual(cyber["formal_verification_status"], "PROVEN_VULNERABLE")
        self.assertGreaterEqual(cyber["findings_count"], 3)
        cwes = " ".join(f["cwe"] for f in cyber["findings"])
        self.assertIn("CWE-190", cwes)
        self.assertIn("CWE-125", cwes)
        self.assertIn("CWE-362", cwes)

        # 4. 3-Regime Adaptive Epistemic Routing (KNOWN_CANONICAL vs KNOWN_OPTIMIZABLE vs UNKNOWN_EXPLORATORY)
        from scientific_oracle import (
            classify_epistemic_regime,
            evaluate_competing_hypotheses,
            verify_optimization_pareto,
        )

        r_known = classify_epistemic_regime("Trier une liste avec un algorithme de tri standard")
        self.assertEqual(r_known["regime"], "KNOWN_CANONICAL")
        self.assertFalse(r_known["should_reinvent"])

        r_opt = classify_epistemic_regime(
            "Optimiser la complexité O(n^2) de cette fonction",
            code="def dup(items):\n    for i in items:\n        for j in items:\n            pass\n",
        )
        self.assertEqual(r_opt["regime"], "KNOWN_OPTIMIZABLE")
        self.assertFalse(r_opt["should_reinvent"])

        r_unk = classify_epistemic_regime("Auditer une faille 0-day inconnue et tester une conjecture inédite")
        self.assertEqual(r_unk["regime"], "UNKNOWN_EXPLORATORY")
        self.assertTrue(r_unk["should_reinvent"])

        # 5. Pareto Optimization Verification (semantic equivalence + loop-depth reduction)
        base_code = (
            "def sum_squares(items):\n"
            "    total = 0\n"
            "    for x in items:\n"
            "        for _ in range(1):\n"
            "            total += x * x\n"
            "    return total\n"
        )
        opt_code = (
            "def sum_squares(items):\n"
            "    return sum(x * x for x in items)\n"
        )
        pareto = verify_optimization_pareto(base_code, opt_code, entry_function="sum_squares")
        self.assertTrue(pareto["ok"])
        self.assertTrue(pareto["semantic_equivalence"])
        self.assertEqual(pareto["status"], "PROVEN_OPTIMIZED")
        self.assertTrue(pareto["loop_depth_reduced"])

        # 6. Multi-Hypothesis Exploration & Skill Capitalization
        exp = evaluate_competing_hypotheses(
            "Identify closed-form sum of first n odd numbers",
            [
                {"id": "H1", "statement": "Sum is n*(n+1)", "conjecture": "n*(n + 1) == n**2", "domain": "pos_int"},
                {"id": "H2", "statement": "Odd k-th term expansion (2*k - 1) + 1 == 2*k", "conjecture": "(2*k - 1) + 1 == 2*k", "domain": "pos_int"},
            ],
            workspace=self.root,
            capitalize_skill_name="odd-sum-invariant",
        )
        self.assertTrue(exp["ok"])
        self.assertEqual(exp["evaluated_hypotheses"][0]["status"], "FALSIFIED")
        self.assertEqual(exp["evaluated_hypotheses"][1]["status"], "VERIFIED")
        self.assertEqual(exp["winning_hypothesis"]["id"], "H2")
        self.assertTrue((self.root / ".aurora" / "skills" / "odd-sum-invariant" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()


