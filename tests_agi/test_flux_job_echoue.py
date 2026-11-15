"""Un rendu FLUX que ComfyUI termine en erreur est rapporté tout de suite, et un manque de mémoire GPU
est corrigé une fois (mémoire libérée, nouvelle soumission).

Essai réel du 15/11/2026 (identité Zig et Sharko) : le rendu a échoué en « CUDA out of memory » parce
qu'un modèle Ollama avait été rechargé pendant le rendu par un autre processus. Le job restait dans
l'historique de ComfyUI avec status_str « error » et completed False ; `poll_history` n'attendait que
« completed » et l'appelant attendait les 1800 s du délai en silence. Aucun ComfyUI réel ici : le
transport est simulé et l'adresse visée n'a aucun service.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
import flux_reference_synth as frs  # noqa: E402

COMFY_FERME = "http://127.0.0.1:9"


def historique(prompt_id: str, message: str) -> bytes:
    return json.dumps({prompt_id: {"status": {"status_str": "error", "completed": False, "messages": [
        ["execution_start", {"prompt_id": prompt_id}],
        ["execution_error", {"prompt_id": prompt_id, "node_id": "31", "node_type": "SamplerCustomAdvanced",
                             "exception_message": message}]]}, "outputs": {}}}).encode("utf-8")


def repondre(corps: bytes):
    @contextlib.contextmanager
    def ouvrir(url, *args, **kwargs):
        yield io.BytesIO(corps)
    return ouvrir


class JobEchoue(unittest.TestCase):
    def test_un_job_en_erreur_est_rapporte_tout_de_suite_avec_sa_cause(self):
        corps = historique("abc", "CUDA out of memory. Tried to allocate 360.00 MiB.")
        debut = time.monotonic()
        with patch("urllib.request.urlopen", repondre(corps)):
            with self.assertRaises(frs.JobFailedError) as erreur:
                frs.poll_history("abc", comfy_base=COMFY_FERME, timeout_s=60, interval_s=0.01)
        self.assertLess(time.monotonic() - debut, 5)            # et non les 60 s du délai
        self.assertTrue(erreur.exception.memoire)
        self.assertIn("SamplerCustomAdvanced", str(erreur.exception))
        self.assertIn("out of memory", str(erreur.exception))

    def test_une_autre_erreur_n_est_pas_prise_pour_un_manque_de_memoire(self):
        with patch("urllib.request.urlopen", repondre(historique("abc", "Missing node type: ReferenceLatent"))):
            with self.assertRaises(frs.JobFailedError) as erreur:
                frs.poll_history("abc", comfy_base=COMFY_FERME, timeout_s=60, interval_s=0.01)
        self.assertFalse(erreur.exception.memoire)


class SynthApresEchec(unittest.TestCase):
    def rendre(self, echecs: list[frs.JobFailedError]):
        soumissions, liberations = [], []

        def poster(workflow, comfy_base=None):
            soumissions.append(workflow)
            return f"job{len(soumissions)}"

        def attendre(prompt_id, **_):
            if echecs:
                raise echecs.pop(0)
            return {"status": {"completed": True}}

        def ecrire(url, chemin):
            Path(chemin).parent.mkdir(parents=True, exist_ok=True)
            Path(chemin).write_bytes(b"png")
            return 3

        with tempfile.TemporaryDirectory() as dossier, contextlib.ExitStack() as pile:
            pile.enter_context(patch.object(frs, "build_workflow", lambda *a, **k: {"31": {"inputs": {"seed": 1}}}))
            pile.enter_context(patch.object(frs, "post_prompt", poster))
            pile.enter_context(patch.object(frs, "poll_history", attendre))
            pile.enter_context(patch.object(frs, "_liberer_comfy", lambda base: liberations.append(base)))
            pile.enter_context(patch.object(frs, "output_path_from_history", lambda entree, base=None: "http://simule/v"))
            pile.enter_context(patch.object(frs, "fetch_to", ecrire))
            pile.enter_context(patch("urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("hors réseau"))))
            resultat = frs.synth("a red cube", "essai", output_dir=Path(dossier), comfy_base=COMFY_FERME)
        return resultat, soumissions, liberations

    def test_un_manque_de_memoire_libere_puis_resoumet_une_fois(self):
        resultat, soumissions, liberations = self.rendre([frs.JobFailedError("oom", memoire=True)])
        self.assertTrue(resultat["ok"], resultat)
        self.assertEqual((len(soumissions), len(liberations)), (2, 1))

    def test_un_second_manque_de_memoire_n_est_pas_resoumis_sans_fin(self):
        resultat, soumissions, _ = self.rendre([frs.JobFailedError("oom", memoire=True),
                                                frs.JobFailedError("oom encore", memoire=True)])
        self.assertFalse(resultat["ok"])
        self.assertIn("oom encore", resultat["error"])
        self.assertEqual(len(soumissions), 2)

    def test_une_autre_erreur_est_rendue_sans_nouvel_essai(self):
        resultat, soumissions, liberations = self.rendre([frs.JobFailedError("Missing node type", memoire=False)])
        self.assertFalse(resultat["ok"])
        self.assertIn("Missing node type", resultat["error"])
        self.assertEqual((len(soumissions), len(liberations)), (1, 0))


if __name__ == "__main__":
    unittest.main()
