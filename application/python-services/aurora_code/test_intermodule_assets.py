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
