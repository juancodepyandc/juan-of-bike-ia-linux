"""Several subjects in one request: each animated with its own movement, then recomposed in place.

« Zig la hyène qui court et Sharko le requin qui nage » (15/11/2026): the two characters were already
rebuilt separately, but the animation step received the merged scene and rigged it as ONE body.
"""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
import animation_multi_sujets as ams  # noqa: E402
import glb_io  # noqa: E402


def write_glb(path: Path, *, offset=(0.0, 0.0, 0.0), animated=False, skin_scale=None) -> Path:
    """A one-triangle model; optionally a translation track, or a skin whose armature is scaled."""
    pos = (np.array([[0, 0, 0], [1, 0, 0], [0, 2, 0]], np.float32) + np.array(offset, np.float32))
    blob = bytearray(pos.tobytes())
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
           "nodes": [{"name": "corps", "mesh": 0}], "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(blob)}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
                          "min": pos.min(0).tolist(), "max": pos.max(0).tolist()}]}
    if animated:
        times = np.array([0.0, 1.0], np.float32)
        values = np.array([[0, 0, 0], [0, 0, 1]], np.float32)
        for arr, kind in ((times, "SCALAR"), (values, "VEC3")):
            doc["bufferViews"].append({"buffer": 0, "byteOffset": len(blob), "byteLength": arr.nbytes})
            acc = {"bufferView": len(doc["bufferViews"]) - 1, "componentType": 5126, "count": len(arr), "type": kind}
            if kind == "SCALAR":
                acc.update({"min": [0.0], "max": [1.0]})
            doc["accessors"].append(acc)
            blob.extend(arr.tobytes())
        doc["animations"] = [{"channels": [{"sampler": 0, "target": {"node": 0, "path": "translation"}}],
                              "samplers": [{"input": 1, "output": 2}]}]
    if skin_scale is not None:
        joints = np.zeros((3, 4), np.uint16)
        weights = np.tile(np.array([1, 0, 0, 0], np.float32), (3, 1))
        ibm = np.eye(4, dtype=np.float32).reshape(1, 16)
        for arr, kind, ctype in ((joints, "VEC4", 5123), (weights, "VEC4", 5126), (ibm, "MAT4", 5126)):
            doc["bufferViews"].append({"buffer": 0, "byteOffset": len(blob), "byteLength": arr.nbytes})
            doc["accessors"].append({"bufferView": len(doc["bufferViews"]) - 1, "componentType": ctype,
                                     "count": len(arr), "type": kind})
            blob.extend(arr.tobytes())
        base = len(doc["accessors"]) - 3
        doc["meshes"][0]["primitives"][0]["attributes"].update({"JOINTS_0": base, "WEIGHTS_0": base + 1})
        doc["nodes"] = [{"name": "armature", "scale": [skin_scale] * 3, "children": [1]},
                        {"name": "os"}, {"name": "corps", "mesh": 0, "skin": 0}]
        doc["skins"] = [{"joints": [1], "inverseBindMatrices": base + 2}]
        doc["scenes"] = [{"nodes": [0, 2]}]
    doc["buffers"] = [{"byteLength": len(blob)}]
    glb_io.save(str(path), doc, bytes(blob))
    return path


class Composition(unittest.TestCase):
    def test_two_animated_models_become_one_file_with_one_shared_animation(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write_glb(Path(tmp) / "a.glb", animated=True)
            b = write_glb(Path(tmp) / "b.glb", offset=(5, 0, 0), animated=True)
            res = ams.composer([{"glb": str(a), "nom": "Zig"},
                                {"glb": str(b), "nom": "Sharko", "recalage": {"echelle": 2.0, "translation": [1, 0, 0]}}],
                               Path(tmp) / "scene.glb")
            doc, blob = glb_io.load(res["sortie"])
            self.assertEqual(len(doc["animations"]), 1)
            self.assertEqual(len(doc["animations"][0]["channels"]), 2)
            self.assertEqual([doc["nodes"][i]["name"] for i in doc["scenes"][0]["nodes"]], ["Zig", "Sharko"])
            sharko_root = doc["nodes"][doc["scenes"][0]["nodes"][1]]
            self.assertEqual((sharko_root["scale"], sharko_root["translation"]), ([2.0] * 3, [1, 0, 0]))
            # the second model's data still reads back unchanged after the offsets
            second = doc["meshes"][1]["primitives"][0]["attributes"]["POSITION"]
            self.assertTrue(np.allclose(glb_io.accessor(doc, blob, second)[1], [6, 0, 0]))
            track = doc["animations"][0]["samplers"][1]
            self.assertTrue(np.allclose(glb_io.accessor(doc, blob, track["output"])[1], [0, 0, 1]))


class PlacementAndRestPose(unittest.TestCase):
    def test_a_skinned_rig_exported_in_centimetres_is_measured_as_displayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rig = write_glb(Path(tmp) / "rig.glb", offset=(0, 0, 0), skin_scale=0.01)
            doc, blob = glb_io.load(str(rig))
            lo, hi = ams.boite_repos(doc, blob)
            self.assertAlmostEqual(float(hi[1] - lo[1]), 0.02, places=6)

    def test_a_moved_or_rescaled_animation_is_put_back_where_the_character_stood(self):
        placed = (np.array([2.0, 0.0, -1.0]), np.array([3.0, 2.0, 1.0]))
        moved = (np.array([-0.5, 0.0, -0.5]), np.array([0.5, 4.0, 0.5]))
        fix = ams.recalage(placed, moved)
        self.assertAlmostEqual(fix["echelle"], 0.5)
        self.assertEqual(fix["translation"], [2.5, 0.0, 0.0])
        self.assertIsNone(ams.recalage(placed, placed))


class WhoIsWho(unittest.TestCase):
    SUBJECTS = [{"nom": "Zig la hyène", "mouvement": "court"}, {"nom": "Sharko le requin", "mouvement": "nage"}]

    def test_the_vision_answer_names_each_crop_and_its_stance(self):
        with tempfile.TemporaryDirectory() as tmp:
            crops = [str(Path(tmp) / f"c{i}.png") for i in (1, 2)]
            for c in crops:
                Path(c).write_bytes(b"png")
            answers = {crops[0]: {"sujet": 2, "appui": "sans_pattes"}, crops[1]: {"sujet": 1, "appui": "quatre_pattes"}}
            read = ams.identifier_personnages(crops, self.SUBJECTS, demander=lambda img, q: answers[img])
        self.assertEqual([(r["sujet"], r["appui"], r["source"]) for r in read],
                         [(1, "sans_pattes", "vision"), (0, "quatre_pattes", "vision")])

    def test_two_crops_never_take_the_same_subject_and_a_guess_is_labelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            crops = [str(Path(tmp) / f"c{i}.png") for i in (1, 2)]
            for c in crops:
                Path(c).write_bytes(b"png")
            read = ams.identifier_personnages(crops, self.SUBJECTS, demander=lambda img, q: {"sujet": 1})
        self.assertEqual([r["sujet"] for r in read], [0, 1])
        self.assertEqual([r["source"] for r in read], ["vision", "ordre_de_mention_suppose"])

    def test_the_sentence_is_split_by_subject(self):
        reply = json.dumps({"sujets": [{"nom": "Zig la hyène", "mouvement": "qui court"},
                                       {"nom": "Sharko le requin", "mouvement": "qui nage"}]})
        split = ams.repartir_mouvements("Zig la hyène qui court et Sharko le requin qui nage", interroger=lambda t: reply)
        self.assertEqual(split["source"], "llm")
        self.assertEqual([s["mouvement"] for s in split["sujets"]], ["qui court", "qui nage"])
        self.assertEqual(ams.repartir_mouvements("x", interroger=lambda t: "prose")["source"], "indisponible")


class Orchestration(unittest.TestCase):
    def test_each_character_gets_its_own_movement_and_a_failure_stays_static_and_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            zig = write_glb(Path(tmp) / "p1.glb")
            sharko = write_glb(Path(tmp) / "p2.glb", offset=(3, 0, 0))
            calls = []

            def animate(source, output, prompt, model, mode, subject, source_description):
                calls.append((Path(source).name, prompt, subject))
                if "nage" in prompt:
                    raise RuntimeError("rig impossible")
                Path(output).parent.mkdir(parents=True, exist_ok=True)
                write_glb(Path(output), animated=True)
                return {"ok": True, "path": output}

            report = ams.animer_sujets(
                "Zig la hyène qui court et Sharko le requin qui nage",
                [{"index": 0, "glb": str(zig), "reference": None}, {"index": 1, "glb": str(sharko), "reference": None}],
                Path(tmp) / "mouvement", "modele",
                repartir=lambda d: {"source": "llm", "sujets": WhoIsWho.SUBJECTS},
                identifier=lambda refs, sujets: [{"sujet": 0, "appui": "quatre_pattes", "source": "vision"},
                                                 {"sujet": 1, "appui": "sans_pattes", "source": "vision"}],
                animer=animate)
            self.assertEqual(calls, [("p1.glb", "Zig la hyène court", "quadruped"),
                                     ("p2.glb", "Sharko le requin nage", "creature")])
            self.assertFalse(report["ok"])
            self.assertEqual(report["anime"], 1)
            self.assertIn("rig impossible", report["error"])
            doc, _ = glb_io.load(report["path"])
            self.assertEqual(len(doc["scenes"][0]["nodes"]), 2)        # the static one is still in the scene


if __name__ == "__main__":
    unittest.main()
