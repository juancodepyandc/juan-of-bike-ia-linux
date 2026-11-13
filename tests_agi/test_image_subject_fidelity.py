"""Verrou de fidélité du sujet (moteur Python du CLI de missions) et parité avec le module Image TS.

Demande réelle signalée : « un vase en forme de coeur avec inscriptions rayen » donnait un
flacon transparent avec une personne. Aucune image n'est générée ici ; on vérifie le prompt
et le négatif envoyés à FLUX.2, et que Python et TypeScript lisent la demande de la même façon.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "application" / "python-services"
APP = ROOT / "application"

REQUEST = "un vase en forme de coeur avec inscriptions rayen"
PARITY_REQUESTS = [
    REQUEST,
    "fais moi un vase en forme de cœur avec l'inscription Rayen",
    "Vase en forme de cœur avec écrit Rayen dessus",
    "un vase en forme de coeur avec le prénom Rayen gravé en lettres dorées",
    'une tasse rouge en céramique avec écrit "Maman"',
    "une plaque gravée au nom de Léa Martin sur fond bois",
    "une bague avec les initiales J.R",
    "un gâteau avec écrit joyeux anniversaire Rayen",
    "une femme qui tient un vase",
    "un chat en forme de nuage",
    "une statue en marbre",
    "un vase en forme de hippocampe",
    "un vase sans inscription",
    "un portrait de Rayen dans un jardin",
    "une bougie en verre transparente",
]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SERVICES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class SubjectFidelityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fid = _load("image_subject_fidelity")
        cls.director = _load("human_prompt_director")

    def test_reported_request_locks_the_vase_and_the_exact_text(self):
        f = self.fid.analyze_subject_fidelity(REQUEST)
        self.assertEqual(f.noun_en, "vase")
        self.assertEqual(f.shape_en, "heart")
        self.assertEqual(f.inscriptions, ["rayen"])
        self.assertTrue(f.object_only)
        self.assertFalse(f.wants_human)

    def test_engraved_name_is_text_not_a_person(self):
        self.assertEqual(self.fid.extract_inscription_texts("une plaque gravée au nom de Léa Martin sur fond bois"), ["Léa Martin"])
        self.assertEqual(self.fid.extract_inscription_texts("un vase sans inscription"), [])
        self.assertNotIn("Rayen", self.fid.strip_inscription_spans("un vase avec l'inscription Rayen"))

    def test_director_prompt_keeps_request_and_moves_people_to_negative(self):
        spec = self.director.direct_prompt(REQUEST)
        prompt = spec["human_prompt"]
        self.assertTrue(prompt.startswith("Main subject: a single heart-shaped vase"))
        self.assertIn(REQUEST, prompt)
        self.assertIn('inscription "rayen"', prompt)
        for word in ("skin", "pores", "woman", "person identity", "fingers"):
            self.assertNotIn(word, prompt)
        negative = [t.strip() for t in spec["negative_prompt"].split(",")]
        for term in ("person", "woman", "hands", "bottle", "perfume bottle", "flacon"):
            self.assertIn(term, negative)
        self.assertNotIn("text", negative)
        self.assertEqual(spec["subject_lock"]["inscriptions"], ["rayen"])

    def test_requested_person_is_not_forbidden(self):
        spec = self.director.direct_prompt("une femme qui tient un vase")
        self.assertNotIn("woman", [t.strip() for t in spec["negative_prompt"].split(",")])
        self.assertIn("Requested object: a vase", spec["human_prompt"])

    def test_python_and_typescript_read_requests_the_same_way(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node absent : parité vérifiée par la CI qui installe Node")
        script = (
            "const m = await import(process.argv[1]);"
            "const reqs = JSON.parse(process.argv[2]);"
            "console.log(JSON.stringify(reqs.map((r) => { const f = m.analyzeSubjectFidelity(r); return {"
            " summary: { noun: f.nounEn, shape: f.shapeEn, shapeFr: f.shapeFr, material: f.materialEn, color: f.colorEn,"
            " inscriptions: f.inscriptions, wantsHuman: f.wantsHuman, wantsAnimal: f.wantsAnimal, objectOnly: f.objectOnly },"
            " lock: m.buildSubjectLockLine(f), negative: m.fidelityNegativeTerms(f) } })))"
        )
        module_url = (APP / "src" / "services" / "imageSubjectFidelity.ts").as_uri()
        proc = subprocess.run(
            [node, "--input-type=module", "-e", script, module_url, json.dumps(PARITY_REQUESTS)],
            cwd=APP, capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0 and "Unknown file extension" in proc.stderr:
            self.skipTest("Node sans lecture native du TypeScript (Node ≥ 22.18 requis)")
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        ts_results = json.loads(proc.stdout.strip().splitlines()[-1])
        for request, ts in zip(PARITY_REQUESTS, ts_results):
            with self.subTest(request=request):
                f = self.fid.analyze_subject_fidelity(request)
                self.assertEqual(f.summary(), ts["summary"])
                self.assertEqual(self.fid.build_subject_lock_line(f), ts["lock"])
                self.assertEqual(self.fid.fidelity_negative_terms(f), ts["negative"])


if __name__ == "__main__":
    unittest.main()
