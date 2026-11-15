"""Local vision models (DINOv2, CLIP) load from the local Hugging Face cache or fail loudly, naming the model.

15/11/2026: CLIP loading failed SILENTLY (an expired Hugging Face token made `from_pretrained` hit the
network, the error was swallowed and callers went on without a model). modeles_locaux always passes
`local_files_only=True`, never sets `HF_HUB_OFFLINE` for the whole process, says when it falls back
from CLIP-L/14 to B/32, and rebuilds only the image preparation when `preprocessor_config.json` is
missing from the cache (measured on this machine for CLIP-L/14).

The encoders are tested with numpy fakes injected as bundles: no weights are needed. Tests that patch
transformers' loaders are skipped where transformers is not installed. A real-model smoke test runs only
with AURORA_TEST_MODELES_REELS=1.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
import modeles_locaux as ml  # noqa: E402

HAS_TRANSFORMERS = importlib.util.find_spec("transformers") is not None


class FauxProcesseur:
    """Image processor fake: records what it was given, returns the raw pixels."""

    def __init__(self) -> None:
        self.vus: list[Image.Image] = []

    def __call__(self, images, return_tensors):
        self.vus.extend(images)
        return {"pixel_values": np.stack([np.asarray(im, dtype=np.float32) for im in images])}


class FauxDino:
    """Three tokens per image; only the first (CLS) carries the colour, the others are constant."""

    def __call__(self, pixel_values):
        n = pixel_values.shape[0]
        cls = np.concatenate([pixel_values.mean(axis=(1, 2)), np.full((n, 1), 7.0)], axis=1)
        return SimpleNamespace(last_hidden_state=np.stack([cls, np.zeros_like(cls), np.full_like(cls, 50.0)], axis=1))


class FauxClip:
    logit_scale = np.log(100.0)

    def get_text_features(self, ids):
        return np.concatenate([ids, np.ones_like(ids)], axis=1)

    def get_image_features(self, pixel_values):
        moyenne = pixel_values.mean(axis=(1, 2, 3))[:, None]
        return np.concatenate([moyenne, 255.0 - moyenne], axis=1)


def faux_tokenizer(textes, padding, truncation, return_tensors):
    return {"ids": np.array([[float(len(t))] for t in textes], dtype=np.float32)}


def normaliser(m: np.ndarray) -> np.ndarray:
    return m / np.linalg.norm(m, axis=1, keepdims=True)


class TestEncoders(unittest.TestCase):
    def test_dinov2_embedding_is_the_l2_normalised_cls_token(self):
        bundle = {"processeur": FauxProcesseur(), "modele": FauxDino(), "appareil": "cpu"}
        images = [Image.new("RGB", (8, 8), c) for c in ((255, 0, 0), (0, 0, 255), (250, 5, 0))]
        e = ml.embed_images(images, bundle=bundle, lot=2)
        self.assertEqual(e.shape, (3, 4))
        self.assertEqual(e.dtype, np.float32)
        np.testing.assert_allclose(np.linalg.norm(e, axis=1), 1.0, rtol=1e-5)
        attendu = normaliser(np.array([[255, 0, 0, 7], [0, 0, 255, 7], [250, 5, 0, 7]], dtype=np.float64))
        np.testing.assert_allclose(e, attendu, rtol=1e-5)  # token 0, not a mean over tokens

    def test_transparency_is_laid_on_white_not_on_the_hidden_background(self):
        processeur = FauxProcesseur()
        decoupe = Image.new("RGBA", (8, 8), (0, 0, 0, 0))   # fully transparent black
        decoupe.putpixel((3, 3), (200, 10, 10, 255))
        ml.embed_images([decoupe], bundle={"processeur": processeur, "modele": FauxDino(), "appareil": "cpu"})
        vu = np.asarray(processeur.vus[0])
        self.assertEqual(processeur.vus[0].mode, "RGB")
        self.assertEqual(tuple(vu[0, 0]), (255, 255, 255))
        self.assertEqual(tuple(vu[3, 3]), (200, 10, 10))

    def test_clip_scores_are_cosines_times_the_learned_scale(self):
        bundle = {"modele": FauxClip(), "tokenizer": faux_tokenizer, "preparation": FauxProcesseur(), "appareil": "cpu"}
        images = [Image.new("RGB", (4, 4), (v, v, v)) for v in (30, 200)]
        textes = ["a", "abcdef", "abc"]
        scores = ml.clip_text_image_scores(images, textes, bundle=bundle)
        self.assertEqual(scores.shape, (2, 3))
        img = normaliser(np.array([[30.0, 225.0], [200.0, 55.0]]))
        txt = normaliser(np.array([[1.0, 1.0], [6.0, 1.0], [3.0, 1.0]]))
        np.testing.assert_allclose(scores, 100.0 * img @ txt.T, rtol=1e-4)

    def test_empty_inputs_return_empty_arrays_without_loading_anything(self):
        with mock.patch.object(ml, "charger_dinov2", side_effect=AssertionError("must not load")), \
                mock.patch.object(ml, "charger_clip", side_effect=AssertionError("must not load")):
            self.assertEqual(ml.embed_images([]).shape[0], 0)
            self.assertEqual(ml.clip_text_image_scores([], ["x"]).shape, (0, 1))


class TestFallbackAndSingletons(unittest.TestCase):
    def tearDown(self) -> None:
        ml.liberer()
        ml._notes.clear()

    def test_falls_back_to_the_small_clip_only_when_the_large_is_absent_and_says_so(self):
        def charger(nom, appareil):
            if nom == "grand":
                raise ml.ModeleLocalAbsent("modèle local absent du cache Hugging Face : grand")
            return {"nom": nom, "appareil": appareil, "notes": []}

        erreurs = io.StringIO()
        with contextlib.redirect_stderr(erreurs):
            bundle = ml.premier_clip_disponible(("grand", "petit"), "cpu", charger=charger)
        self.assertEqual(bundle["nom"], "petit")
        self.assertIn("grand absent du cache : repli sur petit", bundle["notes"][0])
        self.assertIn("repli sur petit", erreurs.getvalue())

    def test_a_present_but_broken_large_model_is_not_hidden_by_a_fallback(self):
        def charger(nom, appareil):
            if nom == "grand":
                raise RuntimeError("modèle local illisible : grand")
            return {"nom": nom, "notes": []}

        with self.assertRaisesRegex(RuntimeError, "illisible : grand"):
            ml.premier_clip_disponible(("grand", "petit"), "cpu", charger=charger)

    def test_no_clip_at_all_names_every_missing_model(self):
        def charger(nom, appareil):
            raise ml.ModeleLocalAbsent(f"modèle local absent du cache Hugging Face : {nom}")

        with self.assertRaises(RuntimeError) as contexte:
            ml.premier_clip_disponible(("grand", "petit"), "cpu", charger=charger)
        self.assertIn("grand", str(contexte.exception))
        self.assertIn("petit", str(contexte.exception))

    def test_singleton_loads_once_and_records_notes(self):
        appels = []

        def fabrique(nom, appareil):
            appels.append((nom, appareil))
            return {"nom": nom, "appareil": appareil, "notes": ["préparation reconstruite"]}

        with mock.patch.object(ml, "charger_dinov2_depuis_cache", fabrique):
            ml.charger_dinov2()
            ml.charger_dinov2()
            self.assertEqual(appels, [(ml.DINOV2, "cpu")])
            etat = ml.etat_modeles()
            self.assertEqual(etat["charges"]["dinov2:cpu"]["nom"], ml.DINOV2)
            self.assertIn("préparation reconstruite", etat["notes"])
            ml.liberer()
            ml.charger_dinov2()
            self.assertEqual(len(appels), 2)

    def test_never_touches_the_process_environment(self):
        source = Path(ml.__file__).read_text(encoding="utf-8")
        self.assertNotIn("environ", source)
        self.assertNotIn("putenv", source)


@unittest.skipUnless(HAS_TRANSFORMERS, "transformers is not installed")
class TestLoadersWithTransformers(unittest.TestCase):
    def test_absent_model_raises_a_runtime_error_naming_it(self):
        interrupteurs = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
        avant = {cle: os.environ.get(cle) for cle in interrupteurs}
        for charger in (ml.charger_dinov2_depuis_cache, ml.charger_clip_depuis_cache):
            with self.assertRaises(RuntimeError) as contexte:
                charger("aurora-test/modele-qui-n-existe-pas", "cpu")
            self.assertIsInstance(contexte.exception, ml.ModeleLocalAbsent)
            self.assertIn("aurora-test/modele-qui-n-existe-pas", str(contexte.exception))
        # offline switches are process-wide: the bridge's other modules may download, so never set them
        self.assertEqual({cle: os.environ.get(cle) for cle in interrupteurs}, avant)

    def test_every_load_is_local_files_only(self):
        import transformers

        modele = mock.MagicMock()
        with mock.patch.object(transformers.AutoImageProcessor, "from_pretrained", return_value=object()) as proc, \
                mock.patch.object(transformers.AutoModel, "from_pretrained", return_value=modele) as mod:
            bundle = ml.charger_dinov2_depuis_cache("org/dino", "cpu")
        self.assertTrue(proc.call_args.kwargs["local_files_only"])
        self.assertTrue(mod.call_args.kwargs["local_files_only"])
        modele.eval.assert_called_once()
        self.assertEqual(bundle["appareil"], "cpu")

    def test_missing_preprocessor_is_rebuilt_from_the_model_config_and_noted(self):
        import transformers

        modele = mock.MagicMock()
        modele.config.vision_config.image_size = 336
        with mock.patch.object(transformers.CLIPModel, "from_pretrained", return_value=modele), \
                mock.patch.object(transformers.CLIPTokenizerFast, "from_pretrained", return_value=object()), \
                mock.patch.object(transformers.CLIPImageProcessor, "from_pretrained",
                                  side_effect=OSError("preprocessor_config.json absent")) as prep:
            bundle = ml.charger_clip_depuis_cache("org/clip", "cpu")
        self.assertTrue(prep.call_args.kwargs["local_files_only"])
        self.assertEqual(bundle["preparation"].crop_size, {"height": 336, "width": 336})
        self.assertEqual(bundle["preparation"].size, {"shortest_edge": 336})
        self.assertIn("preprocessor_config.json absent du cache", bundle["notes"][0])


@unittest.skipUnless(os.environ.get("AURORA_TEST_MODELES_REELS") == "1", "real local models: AURORA_TEST_MODELES_REELS=1")
class TestRealLocalModels(unittest.TestCase):
    def test_real_dinov2_on_cpu(self):
        images = [Image.new("RGB", (64, 64), c) for c in ((200, 30, 30), (30, 30, 200))]
        e = ml.embed_images(images)
        self.assertEqual(e.shape, (2, 768))
        np.testing.assert_allclose(np.linalg.norm(e, axis=1), 1.0, rtol=1e-4)
        ml.liberer()


if __name__ == "__main__":
    unittest.main()
