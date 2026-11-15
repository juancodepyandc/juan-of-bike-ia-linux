"""Étape identité du pipeline : après un refus d'identité, le rendu suivant reçoit plus de pixels du sujet
refusé (seconde ancre, références à 1 MP), jamais plus de texte.

Essai réel du 15/11/2026 (« Zig et Sharko en version réaliste ») : avec une seule ancre par sujet, Zig est
sorti en hyène tachetée générique. Ici, tout est simulé : ni recherche d'images, ni rendu, ni modèle de
vision ; seuls l'enchaînement et les paramètres transmis sont vérifiés.
"""
from __future__ import annotations

import contextlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import aurora_3d_pipeline as pipeline  # noqa: E402
import flux_reference_synth  # noqa: E402
import identite_visuelle  # noqa: E402
import juge_identite  # noqa: E402
from test_reference_identite import contrat, dossier, entree, sujet  # noqa: E402


def image(chemin: Path) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.full((8, 8, 3), 200, dtype=np.uint8)).save(chemin)
    return chemin


def verdict(refuses: dict[int, list[str]]) -> dict:
    sujets = [{"index": i, "nom": n, "axes_refuses": refuses.get(i, []),
               "raisons": [f"{n} : identité non reconnue"] if refuses.get(i) else []} for i, n in enumerate(("Tavik", "Morvo"))]
    return {"schema": juge_identite.SCHEMA, "verdict": "refuse" if refuses else "accepte", "sujets": sujets,
            "attribution": {"permutation": [0, 1]}}


class EssaiRenforce(unittest.TestCase):
    def lancer(self, verdicts: list[dict]):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            ancres = {n: [image(racine / n / f"ancre_{k}.png") for k in (1, 2)] for n in ("tavik", "morvo")}
            c = contrat(sujet("Tavik", "une hyène", "hyena", "qui court"), sujet("Morvo", "un requin", "shark", "qui nage"))
            c["source"] = "llm"
            d = dossier(entree(0, "Tavik", "hyena", ancres["tavik"]), entree(1, "Morvo", "shark", ancres["morvo"]))
            rendus = []

            def synth(positif, run_id, **options):
                rendus.append({"positif": positif, **options})
                chemin = image(Path(options["output_dir"]) / f"{run_id}_reference.png")
                return {"ok": True, "reference_path": str(chemin)}

            juges = list(verdicts)
            sortie = racine / "run"
            sortie.mkdir()
            with contextlib.ExitStack() as pile:
                pile.enter_context(patch.object(pipeline, "_assurer_comfyui", lambda *a, **k: True))
                pile.enter_context(patch.object(identite_visuelle, "etablir", lambda *a, **k: d))
                pile.enter_context(patch.object(flux_reference_synth, "synth", synth))
                pile.enter_context(patch.object(juge_identite, "juger_reference", lambda *a, **k: juges.pop(0)))
                resultat = pipeline._reference_par_identite(c, "essai", sortie, "on", [])
            return resultat, rendus, ancres

    def test_le_sujet_refuse_recoit_une_seconde_ancre_et_des_references_a_1_mp(self):
        resultat, rendus, ancres = self.lancer([verdict({0: ["identite"]}), verdict({})])
        self.assertTrue(resultat["ok"], resultat)
        self.assertEqual(len(rendus), 2)
        premier, second = rendus
        self.assertEqual(premier["reference_images"], [str(ancres["tavik"][0]), str(ancres["morvo"][0])])
        self.assertEqual(premier["reference_megapixels"], flux_reference_synth.REFERENCE_MEGAPIXELS)
        self.assertEqual(second["reference_images"],
                         [str(ancres["tavik"][0]), str(ancres["tavik"][1]), str(ancres["morvo"][0])])
        self.assertEqual(second["reference_megapixels"], 1.0)
        self.assertIn("reference image 2 shows character 1 (hyena)", second["positif"])
        self.assertIn("CORRECTIONS", second["positif"])

    def test_un_refus_qui_ne_porte_pas_sur_l_identite_ne_change_pas_les_pixels(self):
        resultat, rendus, ancres = self.lancer([verdict({1: ["style"]}), verdict({})])
        self.assertTrue(resultat["ok"], resultat)
        self.assertEqual(rendus[1]["reference_images"], [str(ancres["tavik"][0]), str(ancres["morvo"][0])])
        self.assertEqual(rendus[1]["reference_megapixels"], flux_reference_synth.REFERENCE_MEGAPIXELS)


if __name__ == "__main__":
    unittest.main()
