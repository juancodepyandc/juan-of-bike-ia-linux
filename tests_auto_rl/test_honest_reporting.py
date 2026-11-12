"""Reports and runtime gates must state what was measured, and nothing else.

Every test works on temporary directories: no model, no network, no write into
the repository or a user folder. Pillow is only needed by the report renderer.
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import zipfile

REPO = Path(__file__).resolve().parents[1]


def pillow_usable():
    """Pillow and its compiled core exist for this interpreter; nothing heavy is imported to find out."""
    try:
        return importlib.util.find_spec("PIL._imaging") is not None
    except (ImportError, ValueError):
        return False


PIL_AVAILABLE = pillow_usable()

# Six paired audit samples: 4 wins, 2 losses, mean difference +0.667 point on 100.
BASE_SCORES = (0.27, 0.26, 0.28, 0.25, 0.27, 0.29)
CANDIDATE_SCORES = (0.28, 0.25, 0.30, 0.26, 0.29, 0.28)
BASE_METRICS = {"clip_mean": 0.30, "clip_worst_view": 0.25, "self_intersections": 9000,
                "nonmanifold_edge_fraction": 0.004, "degenerate_face_fraction": 0.0001,
                "fragment_area_fraction": 0.02}
CANDIDATE_METRICS = {"clip_mean": 0.31, "clip_worst_view": 0.26, "self_intersections": 8900,
                     "nonmanifold_edge_fraction": 0.003, "degenerate_face_fraction": 0.0002,
                     "fragment_area_fraction": 0.01}
RUN_ID = "3d-20261101-000000-aaaaaa"


def audit_rows(scores, metrics):
    families, styles = ("owl", "bicycle", "cathedral"), ("clay", "photorealistic")
    return [{"task_id": f"audit_{index:03d}", "seed": 41, "prompt": "sujet d'audit",
             "family": families[index % 3], "style": styles[index % 2],
             "judge": {"score": score, "metrics": dict(metrics)}}
            for index, score in enumerate(scores)]


def write_audited_run(state, *, metrics=True):
    """A finished 3D cycle with its audit report and candidate weights, never promoted."""
    run = state / "runs" / RUN_ID
    run.mkdir(parents=True)
    report = {"run_id": RUN_ID, "base_fingerprint": "f" * 64,
              "base": audit_rows(BASE_SCORES, BASE_METRICS if metrics else {}),
              "candidate": audit_rows(CANDIDATE_SCORES, CANDIDATE_METRICS if metrics else {})}
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (run / "candidate.safetensors").write_bytes(b"candidate weights")
    return run


def write_official_registry_entry(state, run):
    """What `storage.promote` leaves behind once the promotion gate has passed."""
    adapter = run / "candidate.safetensors"
    (state / "registry").mkdir(parents=True, exist_ok=True)
    (state / "registry" / "3d.json").write_text(json.dumps({
        "run_id": run.name, "adapter": str(adapter), "version": 1, "name": "Reinforced_Model_v1",
        "sha256": hashlib.sha256(adapter.read_bytes()).hexdigest()}), encoding="utf-8")


@contextlib.contextmanager
def isolated_registry(root):
    """Point every reader and writer of `modele/renforce/` at a temporary tree."""
    from auto_rl import reinforced_registry as registry
    state = root / "state"
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(registry, "RENFORCE_ROOT", root / "modele" / "renforce"))
        stack.enter_context(patch.object(registry, "STATE", state))
        if PIL_AVAILABLE:
            # The sync also renders the before/after report: keep it out of the
            # repository root and out of any desktop folder.
            from auto_rl import before_after_report as report
            stack.enter_context(patch.object(report, "ROOT", root))
            stack.enter_context(patch.object(report, "BUREAU_STUDIO_DIR", root / "absent" / "studio"))
        yield state


class UngatedAdapterIsNotServed(unittest.TestCase):
    def manifest_only_module(self, root, status):
        """A hash-matching adapter described by a manifest, with no official registry entry."""
        adapter = root / "renforce" / "3d" / "adapter.safetensors"
        adapter.parent.mkdir(parents=True)
        adapter.write_bytes(b"ungated adapter")
        (adapter.parent / "manifest.json").write_text(json.dumps({
            "module": "3d", "status": status, "run_id": RUN_ID, "adapter": str(adapter),
            "sha256": hashlib.sha256(b"ungated adapter").hexdigest(), "score_renforce_100": 27.42,
            "base_model": "microsoft/TRELLIS.2-4B"}), encoding="utf-8")
        return adapter

    def test_manifest_without_registry_entry_is_refused_unless_explicitly_allowed(self):
        from auto_rl import reinforced_registry as registry, runtime
        for status in ("reinforced_available", "candidate_not_promoted"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                state = root / "state"
                state.mkdir()
                adapter = self.manifest_only_module(root, status)
                with patch.object(registry, "RENFORCE_ROOT", root / "renforce"), \
                        patch.object(runtime, "STATE", state), patch.dict(os.environ):
                    os.environ.pop(runtime.UNGATED_OPT_IN_ENV, None)
                    self.assertIsNone(runtime.validated_record("3d", state))
                    for not_an_opt_in in ("", "0", "true", "yes"):
                        os.environ[runtime.UNGATED_OPT_IN_ENV] = not_an_opt_in
                        self.assertIsNone(runtime.validated_record("3d", state))
                    os.environ[runtime.UNGATED_OPT_IN_ENV] = "1"
                    record = runtime.validated_record("3d", state)
                self.assertEqual(Path(record["adapter"]), adapter.resolve())
                self.assertEqual(record["model_id"], "microsoft/TRELLIS.2-4B")
                self.assertIs(record["ungated"], True)

    def test_reinforced_variant_cannot_be_selected_without_a_validated_record(self):
        from auto_rl import versions
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            for variant in ("renforce", "validated"):
                with self.assertRaises(ValueError) as refusal:
                    versions.select("3d", variant, state)
                self.assertIn("Aucune version validée", str(refusal.exception))
                self.assertIn("modèle de base", str(refusal.exception))
            self.assertFalse((state / "inference_preferences.json").exists())
            self.assertEqual(versions.select("3d", "base", state)["variant"], "base")
            self.assertEqual(versions.preference("3d", state), "base")

    def test_select_endpoint_answers_409_with_a_french_error(self):
        """Drive the real handler through a minimal stand-in for Flask."""
        from auto_rl import integration

        class Routes:
            def __init__(self):
                self.handlers = {}

            def register(self, path, **_options):
                def decorator(handler):
                    self.handlers[path] = handler
                    return handler
                return decorator

            get = post = route = register

        body = {}
        flask = types.ModuleType("flask")
        flask.jsonify = lambda payload: payload
        flask.send_file = lambda *args, **kwargs: None
        flask.request = types.SimpleNamespace(headers={}, host="127.0.0.1:3001",
                                              get_json=lambda silent=False: body)
        routes = Routes()
        # Swap only this one entry: patch.dict would also forget every module that
        # register_routes imports for the first time.
        real_flask = sys.modules.get("flask")
        sys.modules["flask"] = flask
        try:
            integration.register_routes(routes, proxy=lambda url: None)
        finally:
            if real_flask is None:
                del sys.modules["flask"]
            else:
                sys.modules["flask"] = real_flask
        select = routes.handlers["/api/models/reinforced-select"]
        with tempfile.TemporaryDirectory() as directory, isolated_registry(Path(directory)) as state, \
                patch.object(integration, "STATE", state):
            body.update(module="3d", variant="renforce")
            payload, status = select()
            self.assertEqual(status, 409)
            self.assertIn("Aucune version validée", payload["error"])
            self.assertFalse((state / "inference_preferences.json").exists())
            # Choosing the base model keeps answering 200 with the module description.
            body.update(variant="base")
            accepted = select()
            self.assertEqual((accepted["variant"], accepted["module_info"]["effective_variant"]), ("base", "base"))
            self.assertIs(accepted["module_info"]["reinforced_available"], False)


class RegistryStatesOnlyWhatWasMeasured(unittest.TestCase):
    def test_sign_test_of_the_published_audit(self):
        from auto_rl.reinforced_registry import sign_test_sentence, sign_test_two_sided
        self.assertAlmostEqual(sign_test_two_sided(52, 44), 0.4752, places=4)
        self.assertEqual(sign_test_two_sided(5, 5), 1.0)
        self.assertLess(sign_test_two_sided(20, 2), 0.05)
        for wins, losses in ((0, 0), (True, 3), (3.0, 4), (None, 2), (-1, 2)):
            self.assertIsNone(sign_test_two_sided(wins, losses))
        self.assertIn("non distinguable", sign_test_sentence(52, 44))
        self.assertEqual(sign_test_sentence(None, 44), "")

    def test_unpromoted_candidate_keeps_its_audit_but_is_not_called_verified(self):
        from auto_rl import reinforced_registry as registry
        with tempfile.TemporaryDirectory() as directory, isolated_registry(Path(directory)) as state:
            root = Path(directory)
            write_audited_run(state)
            renforce = root / "modele" / "renforce"
            # A placeholder left by an earlier sync, when "no audit" was stored as a gain of 0.0.
            (renforce / "code").mkdir(parents=True)
            (renforce / "code" / "manifest.json").write_text(json.dumps({
                "module": "code", "status": "base_only_ready_for_training", "gain_points_100": 0.0}), encoding="utf-8")
            registry.sync_all_reinforced_models(state)
            manifest = json.loads((renforce / "3d" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "candidate_not_promoted")
            self.assertIs(manifest["promoted_officially"], False)
            # The audit itself is real and stays available.
            self.assertAlmostEqual(manifest["gain_points_100"], 0.6667, places=4)
            self.assertEqual((manifest["wins"], manifest["losses"], manifest["samples_audited"]), (4, 2, 6))
            self.assertAlmostEqual(manifest["sign_test_p_two_sided"], 0.6875, places=4)
            # No rigging evaluation exists: nothing numeric may be published for it.
            rigging = manifest["rigging_and_animation_stack"]
            self.assertIs(rigging["measured"], False)
            for axis in rigging["metrics_before_after"].values():
                self.assertEqual(axis, {"before_base": None, "after_reinforced": None, "delta": None, "measured": False})
            # No training metrics were recorded for this run: no invented loss either.
            loss = manifest["axes_gains"]["loss_flow_matching_dpo"]
            self.assertEqual((loss["initial_val_loss"], loss["best_val_loss"], loss["measured"]), (None, None, False))

            gains = (renforce / "3d" / "GAINS.md").read_text(encoding="utf-8")
            master = (renforce / "GAINS_MODELES_RENFORCES.md").read_text(encoding="utf-8")
            for text in (gains, master):
                self.assertIn("Candidat non promu", text)
                for claim in ("VÉRIFIÉ", "Vérifié", "Champion", "78.4", "94.8", "+0.445", "52W/44L", "-78.0"):
                    self.assertNotIn(claim, text)
            # Modules without any audit used to be listed with a gain of `+0.000 pt`.
            self.assertNotIn("`+0.000 pt`", master)
            self.assertIn("non mesuré", gains)
            self.assertIn("4 victoires / 2 défaites sur 6 générations appariées", gains)
            self.assertIn("p = 0.69", gains)
            self.assertIn(f"`{RUN_ID}`, candidat non promu", master)
            self.assertIn("4 victoires / 2 défaites / 0 égalités sur 6 générations appariées", master)

            with patch.dict(os.environ):
                os.environ.pop("AURORA_ALLOW_UNGATED_REINFORCED", None)
                answer = registry.get_reinforced_overview(state)
                os.environ["AURORA_ALLOW_UNGATED_REINFORCED"] = "1"
                with_opt_in = registry.get_reinforced_overview(state)
            # The opt-in is reported for what it is and never turns a candidate into an available model.
            self.assertEqual((answer["ungated_opt_in"], with_opt_in["ungated_opt_in"]), (False, True))
            self.assertIs(with_opt_in["modules"]["3d"]["reinforced_available"], False)
            overview = answer["modules"]
            self.assertEqual(overview["3d"]["status"], "candidate_not_promoted")
            self.assertIs(overview["3d"]["reinforced_available"], False)
            self.assertEqual(overview["3d"]["effective_variant"], "base")
            # A module nobody trained has no gain at all, which is not a gain of zero.
            self.assertIsNone(overview["code"]["gain_points_100"])
            self.assertIs(overview["code"]["measured"], False)
            self.assertIs(overview["code"]["reinforced_available"], False)
            self.assertIn("non mesuré", (renforce / "code" / "GAINS.md").read_text(encoding="utf-8"))

    def test_only_the_official_registry_entry_makes_an_adapter_available(self):
        from auto_rl import reinforced_registry as registry
        with tempfile.TemporaryDirectory() as directory, isolated_registry(Path(directory)) as state:
            root = Path(directory)
            run = write_audited_run(state)
            write_official_registry_entry(state, run)
            registry.sync_all_reinforced_models(state)
            renforce = root / "modele" / "renforce"
            manifest = json.loads((renforce / "3d" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "reinforced_available")
            self.assertIs(manifest["promoted_officially"], True)
            self.assertIn("Modèle renforcé promu", (renforce / "3d" / "GAINS.md").read_text(encoding="utf-8"))
            # Promotion does not turn an unmeasured rig into a measured one.
            self.assertIs(manifest["rigging_and_animation_stack"]["measured"], False)
            backed = registry.get_reinforced_overview(state)
            self.assertIs(backed["modules"]["3d"]["reinforced_available"], True)
            self.assertFalse(backed["master_markdown"].startswith(registry.STALE_SHEET_NOTICE))

            # The same manifest stops counting as soon as the registry no longer backs it,
            # and the sheets rendered from it are flagged instead of shown as they are.
            (state / "registry" / "3d.json").unlink()
            overview = registry.get_reinforced_overview(state)
            stale = overview["modules"]["3d"]
            self.assertEqual(stale["status"], "candidate_not_promoted")
            self.assertIs(stale["promoted_officially"], False)
            self.assertIs(stale["reinforced_available"], False)
            self.assertEqual(stale["effective_variant"], "base")
            self.assertTrue(stale["gains_markdown"].startswith(registry.STALE_SHEET_NOTICE))
            self.assertTrue(overview["master_markdown"].startswith(registry.STALE_SHEET_NOTICE))
            self.assertFalse(overview["modules"]["code"]["gains_markdown"].startswith(registry.STALE_SHEET_NOTICE))

    def test_metrics_absent_from_the_audit_are_none_not_zero(self):
        from auto_rl import reinforced_registry as registry
        with tempfile.TemporaryDirectory() as directory, isolated_registry(Path(directory)) as state:
            run = write_audited_run(state, metrics=False)
            report = json.loads((run / "report.json").read_text(encoding="utf-8"))
            record = registry._build_3d_record_from_report(RUN_ID, run / "candidate.safetensors", report,
                                                          "candidate", promoted=False)
            clip = record["axes_gains"]["style_et_fidelite_multi_vues_clip"]
            self.assertEqual((clip["base"], clip["renforce"], clip["delta_pts"]), (None, None, None))
            self.assertEqual(clip["verdict"], "non mesuré")
            self.assertIsNone(record["axes_gains"]["reduction_auto_intersections"]["delta_intersections"])
            # The composite itself was judged, so it is still reported.
            self.assertAlmostEqual(record["score_base_100"], 27.0, places=4)
            registry.sync_all_reinforced_models(state)
            gains = (Path(directory) / "modele" / "renforce" / "3d" / "GAINS.md").read_text(encoding="utf-8")
            self.assertIn("| `non mesuré` | **`non mesuré`** | **`non mesuré`** | non mesuré |", gains)


@unittest.skipUnless(PIL_AVAILABLE, "Pillow is required to render the before/after report")
class BeforeAfterReportShowsMeasuredValues(unittest.TestCase):
    MEASURED = {"module": "3d", "run_id": "3d-20260927-102144-15d62f", "status": "reinforced_available",
                "promoted_officially": False, "score_base_100": 26.9789, "score_renforce_100": 27.4242,
                "gain_points_100": 0.4452, "wins": 52, "losses": 44, "ties": 0, "samples_audited": 96}

    def render(self, root, manifest=None, pairs=()):
        """Run the real generator inside `root`; returns its summary and the Markdown it wrote."""
        from PIL import Image

        from auto_rl import before_after_report as report
        state = root / "state"
        state.mkdir(exist_ok=True)
        if manifest is not None:
            folder = root / "modele" / "renforce" / "3d"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        for name, family, base, candidate in pairs:
            for branch, (score, intersections) in (("AVANT_BASE", base), ("APRES_CANDIDAT", candidate)):
                folder = state / "runs" / RUN_ID / branch
                folder.mkdir(parents=True, exist_ok=True)
                views = []
                for index in range(2):
                    view = folder / f"{name}_{index}.png"
                    Image.new("RGB", (8, 8), (40, 60, 80)).save(view)
                    views.append(str(view))
                (folder / f"{name}.evaluation.json").write_text(json.dumps({
                    "family": family, "prompt": "sujet d'audit",
                    "judge": {"score": score, "metrics": {"views": views, "self_intersections": intersections}},
                }), encoding="utf-8")
        with patch.object(report, "ROOT", root), patch.object(report, "BUREAU_STUDIO_DIR", root / "absent" / "studio"):
            summary = report.generate_before_after_visual_and_report(state)
        with Image.open(root / "AVANT_APRES_3D_COMPARAISON.png") as image:
            self.assertEqual(image.size, (1680, 1260))
        return summary, (root / "BILAN_AVANT_APRES_ET_GAINS.md").read_text(encoding="utf-8")

    def test_measured_composite_is_shown_without_substitution_or_floor(self):
        with tempfile.TemporaryDirectory() as directory:
            summary, markdown = self.render(Path(directory), self.MEASURED)
        self.assertEqual((summary["score_base_100"], summary["score_renforce_100"], summary["gain_points_100"]),
                         (26.979, 27.424, 0.445))
        self.assertIs(summary["promoted"], False)
        self.assertIn("| **Note Globale de Qualité 3D** | `26.98 / 100` | **`27.42 / 100`** | **`+0.445 pt`**", markdown)
        self.assertIn("52 victoires / 44 défaites sur 96 paires auditées", markdown)
        self.assertIn("p = 0.48 (non distinguable d'une absence de changement au seuil de 5 %)", markdown)
        self.assertIn("candidat non promu", markdown)
        for fabricated in ("70.66", "71.13", "0.470", "+12.38", "-61.9", "5 982", "100 % Automatique"):
            self.assertNotIn(fabricated, markdown)
        self.assertIn("| **Rigging & Animation d'un Personnage 3D** | non mesuré | non mesuré |", markdown)

    def test_zero_or_negative_gain_is_displayed_as_such(self):
        for gain, expected in ((-0.5, "`-0.500 pt`"), (0.0, "`+0.000 pt`")):
            with self.subTest(gain=gain), tempfile.TemporaryDirectory() as directory:
                manifest = {**self.MEASURED, "score_base_100": 27.0, "score_renforce_100": 27.0 + gain,
                            "gain_points_100": gain, "wins": 3, "losses": 9, "samples_audited": 12}
                summary, markdown = self.render(Path(directory), manifest)
                self.assertEqual(summary["gain_points_100"], gain)
                self.assertEqual(summary["score_renforce_100"], 27.0 + gain)
                self.assertIn(expected, markdown)

    def test_missing_scores_read_non_mesure_instead_of_fallback_literals(self):
        with tempfile.TemporaryDirectory() as directory:
            summary, markdown = self.render(Path(directory))
        self.assertEqual((summary["score_base_100"], summary["score_renforce_100"], summary["gain_points_100"]),
                         (None, None, None))
        self.assertIn("| **Note Globale de Qualité 3D** | `non mesuré` | **`non mesuré`** |", markdown)
        self.assertIn("aucune paire d'audit chargée", markdown)
        for fallback in ("26.98", "27.42", "70.66", "71.13"):
            self.assertNotIn(fallback, markdown)

    def test_peaks_and_ranges_come_from_the_loaded_pairs_and_are_labelled_best_cases(self):
        pairs = (
            ("audit_owl_001_graine_41", "owl", (0.40, 1000), (0.50, 400)),       # +10.00 pts, -60.0 %
            ("audit_owl_002_graine_137", "owl", (0.40, 1000), (0.41, 990)),      # same family, smaller gain
            ("audit_bicycle_003_graine_41", "bicycle", (0.30, 2000), (0.28, 2500)),  # -2.00 pts, +25.0 %
        )
        with tempfile.TemporaryDirectory() as directory:
            summary, markdown = self.render(Path(directory), self.MEASURED, pairs)
        self.assertEqual(summary["cases_count"], 2)
        self.assertIn("meilleur cas affiché : **`+10.00 pts`**", markdown)
        self.assertIn("`1 000` à `2 000`", markdown)
        self.assertIn("`400` à `2 500`", markdown)
        self.assertIn("`-60.0 %` à `+25.0 %` sur les 2 cas affichés (le meilleur de chaque famille", markdown)
        self.assertIn("meilleur écart parmi 2 paire(s) examinée(s) pour la famille `owl`", markdown)
        self.assertIn("(**`-2.00 points`**)", markdown)
        self.assertIn("pas un Cas Typique", markdown)
        self.assertNotIn("audit_owl_002_graine_137", markdown)

    def test_promotion_wording_follows_the_official_registry_and_no_rig_is_drawn(self):
        from auto_rl import before_after_report as report
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            run = write_audited_run(state)
            write_official_registry_entry(state, run)
            promoted = {**self.MEASURED, "run_id": RUN_ID, "promoted_officially": True}
            summary, markdown = self.render(root, promoted)
            self.assertIs(summary["promoted"], True)
            self.assertIn("candidat promu (registre officiel)", markdown)
        source = (REPO / "auto_rl" / "before_after_report.py").read_text(encoding="utf-8")
        for removed in ("AUDIT CERTIFIÉ", "70.663", "0.470", "26.979", "27.424", "_draw_rig_skeleton_overlay"):
            self.assertNotIn(removed, source)
        self.assertFalse(hasattr(report, "_draw_rig_skeleton_overlay"))


class SurrogateAndRetiredTrainersSaySo(unittest.TestCase):
    def test_colab_bootstrap_is_refused_unless_explicitly_requested(self):
        from auto_rl import colab_live_bridge as bridge
        with self.assertRaises(RuntimeError) as refusal:
            bridge.generate_colab_bootstrap_script("https://example.invalid")
        self.assertIn("n'entraîne aucun modèle Aurora", str(refusal.exception))
        self.assertIn("auto_rl.professor.kaggle_runner", str(refusal.exception))
        with self.assertRaises(RuntimeError):
            bridge.generate_colab_bootstrap_script("https://example.invalid", allow_surrogate="yes")
        script = bridge.generate_colab_bootstrap_script("https://example.invalid", allow_surrogate=True)
        compile(script, "colab-bootstrap", "exec")
        self.assertIn('"trains_aurora_model": False', script)
        self.assertIn('"kind": "surrogate_on_hashed_text"', script)
        self.assertIn('"train_batch_win_rate_pct"', script)
        for fabricated in ("dataset_coverage_pct", '"win_rate_pct"', "176.9", "540 616"):
            self.assertNotIn(fabricated, script)

    def test_colab_status_and_receipts_say_no_aurora_model_is_trained(self):
        from auto_rl import colab_live_bridge as bridge
        label = {"kind": "surrogate_on_hashed_text", "trains_aurora_model": False}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_file = root / "bridge_state.json"
            with patch.object(bridge, "ROOT", root), patch.object(bridge, "COLAB_BRIDGE_STATE_FILE", state_file):
                job = bridge.claim_next_colab_job({"module": "code"})
                self.assertEqual(job["kind"], "training_job")
                self.assertEqual((job["training_kind"], job["trains_aurora_model"]), ("surrogate_on_hashed_text", False))
                # A worker cannot relabel its own job as a native training.
                bridge.update_colab_live_progress({"module": "code", "epoch": 1, "kind": "native_training",
                                                   "trains_aurora_model": True})
                progress = json.loads(state_file.read_text(encoding="utf-8"))["live_progress"]
                self.assertEqual({key: progress[key] for key in label}, label)
                bridge.receive_colab_trained_weights({
                    "module": "code", "job_id": "surrogate-job",
                    "weights_b64": base64.b64encode(b"opaque bytes").decode(),
                    "metrics": {"final_loss": 0.0, "train_batch_win_rate_pct": 100.0}})
                status = bridge.get_colab_bridge_status()
            receipt = json.loads((root / "modele/renforce/code/colab_h100_runs/surrogate-job_report.json")
                                 .read_text(encoding="utf-8"))
            stored = json.loads(state_file.read_text(encoding="utf-8"))
        for record in (receipt, stored["completed_jobs"][-1], stored["live_progress"], status):
            self.assertEqual({key: record[key] for key in label}, label)
        self.assertIs(receipt["promoted"], False)
        self.assertEqual(receipt["metrics_scope"], "worker_reported_on_training_batches_unverified")

    def test_unshipped_testbench_fails_in_french_and_records_that_nothing_trained(self):
        from auto_rl import cloud_worker
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "provided"
            inputs.mkdir()
            payload = inputs / "payload.bin"
            with zipfile.ZipFile(payload, "w") as archive:
                archive.writestr("spec.json", json.dumps({"job_id": "bench", "multi_module_testbench": True}))
            digest = hashlib.sha256(payload.read_bytes()).hexdigest()
            with contextlib.redirect_stdout(io.StringIO()):
                cloud_worker.main("bench", digest, work=root / "export", root=root / "unpacked",
                                  search_roots=[inputs])
            receipt = json.loads((root / "export/aurora_export/result.json").read_text(encoding="utf-8"))
        self.assertTrue(receipt["error"].startswith("RuntimeError: "))
        self.assertIn("n'a jamais été livré", receipt["error"])
        self.assertIn("aucun entraînement n'a été exécuté", receipt["error"])
        self.assertEqual(set(receipt["files"]), {"error.log"})
        self.assertIsNone(importlib.util.find_spec("auto_rl.kaggle_multi_module_testbench"))

    def test_native_receipt_goes_through_the_real_independent_holdout_gate(self):
        import agi_core.judge_ratchet as ratchet  # the module that really defines the gate
        from auto_rl import remote_lab
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "provided"
            inputs.mkdir()
            payload = inputs / "payload.bin"
            with zipfile.ZipFile(payload, "w") as archive:
                archive.writestr("spec.json", json.dumps({"job_id": "gate-run", "training_seconds": 60}))
            telemetry = {"last_heartbeat": time.time(), "status": "ready", "device_free_vram_gb": [8.0],
                         "available_ram_gb": 16.0, "remaining_seconds": 600}

            def finished_worker(argv, *, log, timeout):
                export = Path(argv[argv.index("--work") + 1]) / "aurora_export"
                export.mkdir(parents=True)
                (export / "result.json").write_text(json.dumps({"job_id": "gate-run", "error": None, "files": {}}),
                                                    encoding="utf-8")
                return 0, "finished"

            # Only the subprocess and the hardware probe are replaced; the import of the
            # gate inside run_payload is the real one and used to raise ModuleNotFoundError.
            with patch.object(remote_lab, "probe_resources", return_value=telemetry), \
                    patch.object(remote_lab, "_run_bounded", side_effect=finished_worker), \
                    patch.object(ratchet, "DEFAULT_STATE", root / "ratchet" / "state.json"):
                receipt = remote_lab.run_payload(
                    job_id="gate-run", payload_hash=hashlib.sha256(payload.read_bytes()).hexdigest(),
                    inputs=inputs, output=root / "outputs", session_seconds=600,
                    requirements={"vram_per_device_gb": 1, "ram_gb": 1, "duration_seconds": 120,
                                  "checkpoint_seconds": 10})
            gate = json.loads((root / "outputs/gate-run/promotion_gate.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["independent_audit"], gate)
        self.assertIs(gate["passed"], False)
        self.assertEqual(gate["observed_cases"], 0)
        self.assertIs(receipt["promoted"], False)
        self.assertIsNone(importlib.util.find_spec("agi_core.anti_hallucination_guard"))

    def test_retired_kaggle_kernel_explains_itself_and_writes_no_stats(self):
        script = REPO / "kaggle_sync" / "kernel" / "train.py"
        with tempfile.TemporaryDirectory() as directory:
            done = subprocess.run([sys.executable, str(script)], cwd=directory, capture_output=True, timeout=120)
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertEqual(done.returncode, 1)
        self.assertIn(b"auto_rl.professor.kaggle_runner", done.stdout)
        source = script.read_text(encoding="utf-8")
        for removed in ("import torch", "json.dump", "open("):
            self.assertNotIn(removed, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
