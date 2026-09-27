"""Garde-fous du cycle 3D : le chien de garde ne doit plus tuer un travail sain.

27/09. Le run `3d-20260915-064158-569d4d` a ete tue (SIGINT, `exit_code` 130,
`diagnostic.last_step` = « Arret demande ») apres 1200.2 s, a 2 % d'avancement,
GPU a 52 %, alors qu'il rendait les 30 references FLUX.2 manquantes. Aucun
mesh n'a ete produit. Aucun echec de modele, aucun manque de memoire : une
horloge.

Deux causes distinctes, verifiees ici :

1. `auto_rl/storage.py:105` ne rafraichit `step_started_at` que si le MESSAGE
   change. La synthese de N references emet le meme message du debut a la
   fin, donc `time.time() - step_started_at` continuait de croitre pendant
   un travail reellement productif.
2. `auto_rl/strategy.py` fixait `local_step_timeout_seconds` a 1200 s alors
   qu'UNE SEULE reference a un `poll_history(timeout_s=1800)`. Le seuil etait
   plus court que le travail le plus long qu'il surveille: un rendu lent et
   sain recevait SIGINT meme avec une progression reelle.

Ces tests verrouillent les deux. Ils ne font appel ni au GPU, ni a ComfyUI,
ni a un modele.

Lancement : application/.venv/bin/python -m unittest discover -s tests_auto_rl
"""
from __future__ import annotations

import time
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_rl import strategy                      # noqa: E402
from auto_rl.storage import Status               # noqa: E402

# `challenge_curriculum.materialize_references` delegue a FLUX.2 avec
# `poll_history(job, timeout_s=...)`. Le chien de garde compare
# `time.time() - step_started_at` a `local_step_timeout_seconds`: le second
# doit couvrir le premier, sinon il coupe un travail sain.
POLL_HISTORY_TIMEOUT_S = 1800


class TestWatchdogVsSingleRender(unittest.TestCase):
    """Le seuil ne doit jamais etre plus court que le travail unitaire."""

    def test_3d_step_timeout_covers_one_reference_render(self):
        c = strategy.apply({"module": "3d", "stage": "local"})
        self.assertGreaterEqual(
            c["local_step_timeout_seconds"], POLL_HISTORY_TIMEOUT_S,
            "le chien de garde tue avant la fin possible d'un rendu de reference")

    def test_3d_preparation_budget_covers_the_reference_phase(self):
        c = strategy.apply({"module": "3d", "stage": "local"})
        # 36 references x ~60 s, plus le self-play qui suit dans la meme
        # phase de preparation.
        self.assertGreater(c["local_preparation_seconds"], 3600)

    def test_autre_module_inchange(self):
        """Le correctif est cible 3D: rien d'autre ne doit bouger."""
        for module in ("image", "video", "animation", "code"):
            c = strategy.apply({"module": module, "stage": "local",
                                "generation": {}})
            self.assertEqual(c["local_step_timeout_seconds"], 1200,
                             "seul le module 3d devait changer")


class TestStatusProgressRefreshesTheClock(unittest.TestCase):
    """`Status.update` doit rafraichir `step_started_at` quand le travail avance."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.status = Status(self._tmp.name, "3d-test", "3d")

    def tearDown(self):
        self._tmp.cleanup()

    def test_message_constante_ne_rafraichit_pas(self):
        """Documente la cause 1: un message identique ne продвигает rien."""
        self.status.update("curriculum", "Creation de sujets et references...")
        first = self.status.data["step_started_at"]
        time.sleep(0.05)
        self.status.update("curriculum", "Creation de sujets et references...")
        self.assertEqual(self.status.data["step_started_at"], first,
                         "un message identique doit conserver l'horodatage d'origine")

    def test_message_change_rafraichit(self):
        """Documente le mecanisme: changer de message rearme le chien de garde."""
        self.status.update("curriculum", "Reference 1/30...")
        first = self.status.data["step_started_at"]
        time.sleep(0.05)
        self.status.update("curriculum", "Reference 2/30...")
        self.assertGreater(self.status.data["step_started_at"], first,
                           "un message different doit rafraichir step_started_at")

    def test_progression_par_reference_rearme_a_each_etape(self):
        """Le vrai correctif: une progression PAR image rearme le chrono.

        On rejoue la forme exacte du message emis par
        `preference_cycle._ref_progress`: a chaque reference le message
        change, donc `step_started_at` avance, donc le chien de garde voit
        un travail vivant meme si la phase dure plus de 1200 s au total.
        """
        self.status.update("curriculum", "Reference 0/30...")
        marks = [self.status.data["step_started_at"]]
        for done in range(1, 31):
            time.sleep(0.002)
            self.status.update("curriculum", "Reference %d/30..." % done)
            marks.append(self.status.data["step_started_at"])
        self.assertTrue(all(b >= a for a, b in zip(marks, marks[1:])),
                        "step_started_at doit etre monotone non decroissant")
        self.assertGreater(marks[-1], marks[0],
                           "la phase doit avoir ete rearmee au moins une fois")


if __name__ == "__main__":
    unittest.main(verbosity=2)
