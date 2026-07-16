#!/usr/bin/env python3
from __future__ import annotations

import io
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import intermodule_assets as assets  # noqa: E402
import intermodule_asset_reuse as asset_reuse  # noqa: E402
import intermodule_rag as rag  # noqa: E402


class InterModuleAssetsTests(unittest.TestCase):
    def test_flux_workflow_uses_installed_flux2_nodes(self) -> None:
        workflow = assets.build_flux_workflow("premium dashboard", 42)
        self.assertEqual(workflow["11"]["inputs"]["type"], "flux2")
        self.assertEqual(workflow["12"]["inputs"]["unet_name"], "flux2_dev_fp8mixed.safetensors")
        self.assertEqual(workflow["9"]["class_type"], "SaveImage")

    def test_optimizer_writes_avif_webp_and_responsive_urls(self) -> None:
        source = Image.new("RGB", (1600, 900), "#4477aa")
        raw = io.BytesIO()
        source.save(raw, "PNG")
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            out_dir = root / "output" / "code_assets" / "proof"
            result = assets.optimize_image(raw.getvalue(), root, out_dir, "hero")
            mime_types = {variant["mimeType"] for variant in result["variants"]}
            self.assertIn("image/avif", mime_types)
            self.assertIn("image/webp", mime_types)
            self.assertIn("/api/code/assets/file/proof/", result["srcset"])
            self.assertIn("assets/generated/proof/", result["projectSrcset"])
            self.assertNotIn("base64", str(result))

    def test_3d_reuse_after_fresh_failure_is_flagged_stale(self) -> None:
        # WS15: une generation 3D fraiche qui echoue et retombe sur un vieux GLB
        # sans rapport doit etre signalee (stale + warning), pas livree en silence.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            old_glb = root / "output" / "3d" / "generations" / "otherrun" / "mesh.glb"
            old_glb.parent.mkdir(parents=True, exist_ok=True)
            old_glb.write_bytes(b"glTF" + b"\x00" * 4096)  # > 1024 octets
            out_dir = root / "output" / "code_assets" / "proof"

            # post_json simule un pipeline frais en echec (aucun final_mesh).
            with patch.object(assets, "post_json", return_value={"ok": False, "error": "pipeline ko"}):
                asset, detail = assets.generate_3d_asset(
                    base_url="http://x", root=root, out_dir=out_dir,
                    prompt="un vaisseau", run_id="freshrun", fresh=True,
                    allow_existing=True, source_run_id="", timeout=5,
                )

            self.assertIsNotNone(asset)
            self.assertTrue(asset["stale"], "un GLB reutilise apres echec frais doit etre stale")
            self.assertIn("peut", (asset["warning"] or "").lower())
            self.assertTrue(detail.get("staleAssetWarning"))

    def test_3d_quality_loop_requests_max_quality_rescues_and_cleans_up(self) -> None:
        # WS15 qualite: multi_view=True + purpose=product demandes; score bas ->
        # auto-rescue -> re-score haut -> asset livre; runs commandes SUPPRIMES,
        # runs etrangers preserves.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            generations = root / "output" / "3d" / "generations"
            foreign = generations / "run-dun-autre-module" / "mesh.glb"
            foreign.parent.mkdir(parents=True, exist_ok=True)
            foreign.write_bytes(b"glTF" + b"\x00" * 4096)
            out_dir = root / "output" / "code_assets" / "proof"
            calls: list[tuple[str, dict]] = []
            score_calls = {"n": 0}

            def fake_post(base_url, path, payload, timeout=30):
                calls.append((path, payload))
                if path == "/api/3d/run-pipeline":
                    mesh = generations / payload["run_id"] / "final_materials.glb"
                    mesh.parent.mkdir(parents=True, exist_ok=True)
                    mesh.write_bytes(b"glTF" + b"\x00" * 4096)
                    (mesh.parent / "flux_reference.png").write_bytes(b"\x89PNG fake")
                    return {"ok": True, "pipeline": {"ok": True, "final_mesh": str(mesh)}}
                if path == "/api/3d/mesh-score":
                    score_calls["n"] += 1
                    low = score_calls["n"] == 1
                    return {"ok": True, "score": {
                        "overall_score": 48 if low else 91,
                        "retry_recommended": low, "retry_threshold": 70,
                        "failed_axes": ["surface_quality"] if low else [],
                    }}
                if path == "/api/3d/auto-rescue":
                    rescued = pathlib.Path(payload["output"]) / "rescued.glb"
                    rescued.parent.mkdir(parents=True, exist_ok=True)
                    rescued.write_bytes(b"glTF" + b"\x00" * 5000)
                    return {"ok": True, "rescue": {"ok": True, "final_mesh": str(rescued), "final_score": 91}}
                raise AssertionError(f"endpoint inattendu: {path}")

            with patch.object(assets, "post_json", side_effect=fake_post):
                asset, detail = assets.generate_3d_asset(
                    base_url="http://x", root=root, out_dir=out_dir,
                    prompt="figurine dragon", run_id="coderun", fresh=True,
                    allow_existing=True, source_run_id="", timeout=5,
                )

            self.assertIsNotNone(asset)
            pipeline_calls = [payload for path, payload in calls if path == "/api/3d/run-pipeline"]
            self.assertTrue(all(p["multi_view"] is True for p in pipeline_calls), "multi_view=True (TRELLIS) obligatoire")
            self.assertTrue(all(p["purpose"] == "product" for p in pipeline_calls), "purpose=product (reglages hauts)")
            self.assertTrue(any(path == "/api/3d/auto-rescue" for path, _ in calls), "rescue attendu sous le seuil")
            self.assertFalse(asset["stale"])
            self.assertEqual(asset["metadata"]["qualityScore"], 91)
            self.assertTrue(asset["metadata"]["rescueUsed"])
            # Sorties distinctes: l asset vit dans code_assets, les runs commandes sont purges.
            self.assertTrue((out_dir / "models").is_dir())
            self.assertEqual(detail.get("cleanedCommissionedRuns"), [p["run_id"] for p in pipeline_calls[:1]])
            self.assertFalse((generations / pipeline_calls[0]["run_id"]).exists(), "run commande doit etre supprime")
            self.assertTrue(foreign.exists(), "les runs des autres modules ne doivent JAMAIS etre touches")

    def test_bundle_requires_every_requested_asset(self) -> None:
        fake_asset = lambda kind: ({
            "id": kind,
            "kind": kind,
            "role": "proof",
            "path": f"assets/{kind}",
            "mimeType": "application/octet-stream",
            "bytes": 1,
            "sourceModule": kind,
            "bridgeEndpoint": f"/api/{kind}",
            "optimized": True,
        }, {"requestedEndpoint": f"/api/{kind}"})
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(assets, "workspace_root", return_value=pathlib.Path(tmp)), \
                patch.object(assets, "generate_image_asset", return_value=fake_asset("image")), \
                patch.object(assets, "generate_voice_asset", return_value=fake_asset("voice")), \
                patch.object(assets, "build_rag_trace", return_value={"results": [], "fetchedPages": 0}):
            bundle = assets.build_bundle({
                "prompt": "preuve",
                "runId": "test",
                "requestedKinds": ["image", "voice"],
            })
        self.assertEqual(bundle["missingRequired"], [])
        self.assertEqual({item["kind"] for item in bundle["assets"]}, {"image", "voice"})
        self.assertEqual(bundle["deferred"][0]["kind"], "music_sfx")

    def test_reuses_validated_asset_and_rewrites_every_bundle_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source_dir = root / "output" / "code_assets" / "source-proof"
            (source_dir / "images").mkdir(parents=True)
            (source_dir / "images" / "hero.avif").write_bytes(b"primary")
            (source_dir / "images" / "hero.webp").write_bytes(b"variant")
            assets.write_json(source_dir / "asset-bundle.json", {
                "assets": [{
                    "id": "image-hero", "kind": "image", "metadata": {"seed": 7},
                    "path": "assets/generated/source-proof/images/hero.avif",
                    "storagePath": "output/code_assets/source-proof/images/hero.avif",
                    "previewUrl": "/api/code/assets/file/source-proof/images/hero.avif",
                    "srcset": "/api/code/assets/file/source-proof/images/hero.avif 1280w",
                    "projectSrcset": "assets/generated/source-proof/images/hero.avif 1280w",
                    "variants": [{
                        "storagePath": "output/code_assets/source-proof/images/hero.webp",
                        "path": "assets/generated/source-proof/images/hero.webp",
                        "previewUrl": "/api/code/assets/file/source-proof/images/hero.webp",
                    }],
                }],
            })
            target_dir = root / "output" / "code_assets" / "selected-proof"
            asset, detail = asset_reuse.reuse_asset_from_bundle(
                root, target_dir, "source-proof", "image",
            )
        self.assertIsNotNone(asset)
        self.assertTrue(detail["reusedExistingAsset"])
        self.assertIn("selected-proof", asset["path"])
        self.assertIn("selected-proof", asset["variants"][0]["previewUrl"])
        self.assertEqual(asset["metadata"]["reusedFromRunId"], "source-proof")

    def test_reuse_rejects_a_file_outside_its_source_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source_dir = root / "output" / "code_assets" / "source-proof"
            source_dir.mkdir(parents=True)
            (root / "outside.bin").write_bytes(b"secret")
            assets.write_json(source_dir / "asset-bundle.json", {
                "assets": [{
                    "kind": "voice",
                    "storagePath": "outside.bin",
                }],
            })
            asset, detail = asset_reuse.reuse_asset_from_bundle(
                root, root / "output" / "code_assets" / "target", "source-proof", "voice",
            )
        self.assertIsNone(asset)
        self.assertIn("hors bundle", detail["reuseError"])

    def test_requested_asset_kinds_deduplicates_and_filters(self) -> None:
        selected = asset_reuse.requested_asset_kinds(
            {"requestedKinds": ["image", "image", "unknown", "voice"]},
            ("image", "model3d", "voice"),
        )
        self.assertEqual(selected, ["image", "voice"])


class InterModuleRagTests(unittest.TestCase):
    def test_extracts_rows_and_nested_page_text(self) -> None:
        rows = rag.result_rows({"resultsList": [{"title": "A", "url": "https://example.test"}]})
        self.assertEqual(rows[0]["title"], "A")
        self.assertEqual(rag.extracted_text({"result": {"markdown": "contenu utile"}}), "contenu utile")
        self.assertEqual(rag.extracted_text({"ok": False, "error": "crawler indisponible"}), "")

    def test_hash_fallback_is_normalized_and_semantic_ranking_is_stable(self) -> None:
        first = rag.hashed_embedding("design system accessible responsive")
        second = rag.hashed_embedding("design system responsive")
        unrelated = rag.hashed_embedding("rust compiler bytecode")
        self.assertGreater(rag.cosine(first, second), rag.cosine(first, unrelated))
        self.assertAlmostEqual(rag.cosine(first, first), 1.0, places=6)

    def test_direct_fetch_normalizes_unicode_urls(self) -> None:
        response = MagicMock()
        response.read.return_value = b"<main>reference utile</main>"
        response.__enter__.return_value = response
        with patch.object(rag.urllib.request, "urlopen", return_value=response) as urlopen:
            text = rag.fetch_page_text("https://exemple.test/contrôle?q=créatif")
        requested_url = urlopen.call_args.args[0].full_url
        self.assertEqual(requested_url, "https://exemple.test/contr%C3%B4le?q=cr%C3%A9atif")
        self.assertEqual(text, "reference utile")


if __name__ == "__main__":
    unittest.main()
