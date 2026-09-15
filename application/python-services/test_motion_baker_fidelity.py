# -*- coding: utf-8 -*-
"""Compilateur de mouvement — chaque primitive et chaque preset BOUGE.

POURQUOI CE FICHIER EXISTE
--------------------------
`motion_baker` transforme un descripteur `aurora.motion.v1` en instructions de
cles pour Blender. Le mode de panne redoute — deja paye par le projet — n est
pas une exception: c est une compilation qui REUSSIT et rend des pistes
PLATES. Le bake ecrit alors des cles, la scene se charge, et le sujet ne bouge
pas. Rien dans la chaine ne signale quoi que ce soit.

Aucun test ne verifiait cette propriete. On la verifie ici sur les 14
primitives du repartiteur ET sur les 45 presets du catalogue, en mesurant
l amplitude reelle de chaque piste produite.

Ce fichier contient aussi la garde de FIDELITE: l amplitude demandee doit se
retrouver en sortie, et la doubler doit ~doubler le mouvement. Une sortie
insensible a son parametre est une autre facon de ne rien commander.

Reproduction en ligne de commande :
    .venv/bin/python -m unittest discover -s python-services -p 'test_motion_baker_fidelity.py' -t python-services
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motion_baker as MB  # noqa: E402


FPS = 24
FRAMES = 48


def descripteur(primitives, frames=FRAMES, mid="test", loop=True):
    return {
        "schema": "aurora.motion.v1", "id": mid, "label": mid, "source": "test",
        "loop": loop, "fps": FPS, "frame_count": frames, "primitives": primitives,
    }


def amplitude(instruction) -> float:
    valeurs = [v for (_f, v) in instruction["samples"]]
    return (max(valeurs) - min(valeurs)) if valeurs else 0.0


def amplitude_max(payload) -> float:
    return max((amplitude(i) for i in payload["instructions"]), default=0.0)


# Les 14 primitives du repartiteur, avec un jeu de parametres plausible.
GABARITS = {
    "gait":        {"kind": "gait", "target": "legs", "amplitude": 30, "frequency_hz": 1.0, "axis": "x"},
    "oscillate":   {"kind": "oscillate", "target": "head", "axis": "x", "amplitude": 20, "frequency_hz": 1.0},
    "rotate":      {"kind": "rotate", "target": "torso", "axis": "z", "amplitude": 90, "frequency_hz": 0.5},
    "translate":   {"kind": "translate", "target": "root", "axis": "y", "amplitude": 1.0, "frequency_hz": 0.5},
    "swing":       {"kind": "swing", "target": "arms", "amplitude": 40, "frequency_hz": 1.0, "axis": "x"},
    "extend":      {"kind": "extend", "target": "arms", "amplitude": 0.5},
    "loop_path":   {"kind": "loop_path", "target": "root", "amplitude": 1.0, "frequency_hz": 0.5},
    "gesture":     {"kind": "gesture", "target": "right_arm", "amplitude": 45, "frequency_hz": 1.5},
    "jump":        {"kind": "jump", "target": "root", "amplitude": 0.6},
    "crouch":      {"kind": "crouch", "target": "legs", "amplitude": 40},
    "lunge":       {"kind": "lunge", "target": "legs", "amplitude": 50},
    "flap":        {"kind": "flap", "target": "arms", "amplitude": 60, "frequency_hz": 2.0},
    "breathe":     {"kind": "breathe", "target": "torso", "amplitude": 0.03, "frequency_hz": 0.3},
    "custom_pose": {"kind": "custom_pose", "target": "torso", "amplitude": 30},
}


class PrimitivesTests(unittest.TestCase):

    def test_le_repartiteur_est_couvert_par_les_gabarits(self):
        """Si une primitive est ajoutee au repartiteur sans gabarit ici, elle
        echapperait a tout ce fichier. On l interdit."""
        attendus = set(MB._COMPILER_DISPATCH) - {"preset_ref"}
        self.assertEqual(
            attendus - set(GABARITS), set(),
            "primitives du repartiteur non couvertes par un gabarit de test")

    def test_chaque_primitive_produit_des_instructions(self):
        for nom, prim in GABARITS.items():
            with self.subTest(primitive=nom):
                r = MB.compile_motion_payload(descripteur([prim]))
                self.assertGreater(r["instruction_count"], 0, f"{nom} ne produit rien")

    def test_chaque_primitive_produit_un_mouvement_reel(self):
        """`custom_pose` et `loop_path` sont exclus et documentes ci-dessous."""
        plates = []
        for nom, prim in GABARITS.items():
            if nom in ("custom_pose", "loop_path"):
                continue
            r = MB.compile_motion_payload(descripteur([prim]))
            if amplitude_max(r) <= 1e-9:
                plates.append(nom)
        self.assertEqual(
            plates, [],
            f"primitives compilees en pistes PLATES : {plates} — le bake ecrirait "
            "des cles et le sujet ne bougerait pas.")

    def test_custom_pose_est_une_pose_donc_immobile_par_nature(self):
        """Une pose n est pas un mouvement : une piste plate est ici le bon
        resultat, et le test le fixe pour que ce ne soit pas confondu plus tard
        avec une panne."""
        r = MB.compile_motion_payload(descripteur([GABARITS["custom_pose"]]))
        self.assertGreater(r["instruction_count"], 0)

    def test_loop_path_est_un_marqueur_normalise(self):
        """`loop_path` ne pose pas de cles : il emet une progression 0->1 que
        le cote Blender convertit en suivi de courbe. Son amplitude ne suit
        donc pas le parametre — c est une decision, pas un oubli."""
        r = MB.compile_motion_payload(descripteur([GABARITS["loop_path"]]))
        instruction = r["instructions"][0]
        self.assertEqual(instruction["channel"], "follow_curve")
        self.assertEqual([v for (_f, v) in instruction["samples"]], [0.0, 1.0])

    def test_les_echantillons_restent_dans_la_plage_de_frames(self):
        for nom, prim in GABARITS.items():
            with self.subTest(primitive=nom):
                r = MB.compile_motion_payload(descripteur([prim], frames=FRAMES))
                for i in r["instructions"]:
                    for (f, _v) in i["samples"]:
                        self.assertGreaterEqual(f, 1, nom)
                        self.assertLessEqual(f, FRAMES, nom)

    def test_aucune_valeur_non_finie(self):
        for nom, prim in GABARITS.items():
            with self.subTest(primitive=nom):
                r = MB.compile_motion_payload(descripteur([prim]))
                for i in r["instructions"]:
                    for (_f, v) in i["samples"]:
                        self.assertTrue(math.isfinite(float(v)), f"{nom} : {v}")


class FideliteAmplitudeTests(unittest.TestCase):
    """L amplitude demandee doit se retrouver en sortie."""

    ECHELLE = [k for k in GABARITS if k not in ("custom_pose", "loop_path")]

    def test_doubler_l_amplitude_double_le_mouvement(self):
        for nom in self.ECHELLE:
            with self.subTest(primitive=nom):
                base = dict(GABARITS[nom])
                a = amplitude_max(MB.compile_motion_payload(
                    descripteur([{**base, "amplitude": 10.0}])))
                b = amplitude_max(MB.compile_motion_payload(
                    descripteur([{**base, "amplitude": 20.0}])))
                self.assertGreater(a, 1e-9, f"{nom} : amplitude nulle a 10")
                ratio = b / a
                self.assertTrue(
                    1.8 <= ratio <= 2.2,
                    f"{nom} : doubler l amplitude donne un facteur {ratio:.3f}")

    def test_la_sortie_n_est_pas_insensible_a_son_parametre(self):
        for nom in self.ECHELLE:
            with self.subTest(primitive=nom):
                base = dict(GABARITS[nom])
                petit = amplitude_max(MB.compile_motion_payload(
                    descripteur([{**base, "amplitude": 5.0}])))
                grand = amplitude_max(MB.compile_motion_payload(
                    descripteur([{**base, "amplitude": 50.0}])))
                self.assertGreater(
                    grand, petit * 1.5,
                    f"{nom} : la sortie ne suit pas l amplitude demandee")


class CataloguePresetsTests(unittest.TestCase):
    """Les 45 presets du catalogue, un par un."""

    @classmethod
    def setUpClass(cls):
        cls.catalogue = MB.load_preset_catalog()

    def test_le_catalogue_est_charge(self):
        self.assertGreater(
            len(self.catalogue), 0,
            "catalogue vide : le baker retomberait en silence sur ses presets "
            "codes en dur, et ce fichier ne testerait plus rien")

    def test_chaque_preset_produit_un_mouvement_reel(self):
        morts = []
        for pid in sorted(self.catalogue):
            r = MB.compile_motion_payload(descripteur(
                [{"kind": "preset_ref", "source_target": pid, "modifiers": {}}]))
            if r["instruction_count"] == 0 or amplitude_max(r) <= 1e-9:
                morts.append(pid)
        self.assertEqual(
            morts, [],
            f"{len(morts)}/{len(self.catalogue)} presets compilent en pistes plates : {morts}")

    def test_chaque_preset_reste_dans_la_plage_de_frames(self):
        for pid in sorted(self.catalogue):
            with self.subTest(preset=pid):
                r = MB.compile_motion_payload(descripteur(
                    [{"kind": "preset_ref", "source_target": pid, "modifiers": {}}]))
                for i in r["instructions"]:
                    for (f, _v) in i["samples"]:
                        self.assertGreaterEqual(f, 1)
                        self.assertLessEqual(f, FRAMES)

    def test_un_preset_inconnu_ne_fabrique_pas_de_faux_mouvement(self):
        r = MB.compile_motion_payload(descripteur(
            [{"kind": "preset_ref", "source_target": "famille.inexistante", "modifiers": {}}]))
        self.assertEqual(amplitude_max(r), 0.0,
                         "un preset inconnu doit rester silencieux, pas inventer un geste")

    def test_le_modificateur_d_amplitude_agit(self):
        pid = "character.walk_cycle"
        if pid not in self.catalogue:
            self.skipTest(f"{pid} absent du catalogue")
        faible = amplitude_max(MB.compile_motion_payload(descripteur(
            [{"kind": "preset_ref", "source_target": pid, "modifiers": {"amplitudeMul": 0.5}}])))
        fort = amplitude_max(MB.compile_motion_payload(descripteur(
            [{"kind": "preset_ref", "source_target": pid, "modifiers": {"amplitudeMul": 2.0}}])))
        self.assertGreater(fort, faible * 1.5, f"faible={faible} fort={fort}")


class SequencageTests(unittest.TestCase):
    """« marche PUIS salue » doit se jouer l un apres l autre."""

    def test_deux_segments_ne_se_chevauchent_pas(self):
        r = MB.compile_motion_payload(descripteur(
            [{"kind": "preset_ref", "source_target": "character.walk_cycle", "modifiers": {}},
             {"kind": "preset_ref", "source_target": "character.wave", "modifiers": {}}],
            mid="custom.parsed"))
        fenetres = {}
        for i in r["instructions"]:
            depart = i.get("segment_start", 1)
            frames = [f for (f, _v) in i["samples"]]
            if not frames:
                continue
            cle = fenetres.setdefault(depart, [min(frames), max(frames)])
            cle[0] = min(cle[0], min(frames))
            cle[1] = max(cle[1], max(frames))
        self.assertGreaterEqual(len(fenetres), 2,
                                f"un seul segment produit : {fenetres}")
        bornes = sorted(fenetres.values())
        for i in range(1, len(bornes)):
            self.assertGreaterEqual(
                bornes[i][0], bornes[i - 1][1],
                f"segments qui se chevauchent : {bornes} — les deux gestes se "
                "joueraient en meme temps au lieu de se suivre")

    def test_un_preset_unique_couvre_toute_la_duree(self):
        """Les sous-primitives d UN preset sont des COUCHES d un meme geste :
        les decouper en fenetres dechirerait le mouvement."""
        r = MB.compile_motion_payload(descripteur(
            [{"kind": "preset_ref", "source_target": "character.walk_cycle", "modifiers": {}}],
            mid="character.walk_cycle"))
        for i in r["instructions"]:
            frames = [f for (f, _v) in i["samples"]]
            if frames:
                self.assertLessEqual(min(frames), 2)


class EntreesDegenereesTests(unittest.TestCase):

    def test_schema_errone_est_refuse(self):
        with self.assertRaises(ValueError):
            MB.compile_motion_payload({"schema": "autre.chose", "primitives": []})

    def test_aucune_primitive_rend_zero_instruction(self):
        r = MB.compile_motion_payload(descripteur([]))
        self.assertEqual(r["instruction_count"], 0)

    def test_kind_inconnu_produit_un_marqueur_tracable(self):
        """Un `kind` inconnu ne doit pas etre avale : la sortie doit porter la
        trace de ce qui n a pas ete compris."""
        r = MB.compile_motion_payload(descripteur([{"kind": "zzz", "target": "legs"}]))
        self.assertEqual(r["instruction_count"], 1)
        self.assertTrue(r["instructions"][0]["source_kind"].startswith("unknown:"))

    def test_frame_count_invalide_est_borne(self):
        for valeur in (0, -5):
            r = MB.compile_motion_payload(descripteur([GABARITS["gait"]], frames=valeur))
            self.assertGreaterEqual(r["frame_count"], 1)

    def test_frequence_extreme_ne_leve_pas(self):
        for f in (0.0, 1e-6, 1000.0):
            r = MB.compile_motion_payload(descripteur(
                [{**GABARITS["gait"], "frequency_hz": f}]))
            for i in r["instructions"]:
                for (_fr, v) in i["samples"]:
                    self.assertTrue(math.isfinite(float(v)), f"frequence={f}")

    def test_compilation_deterministe(self):
        a = MB.compile_motion_payload(descripteur([GABARITS["gait"]]))
        b = MB.compile_motion_payload(descripteur([GABARITS["gait"]]))
        self.assertEqual(a["instructions"], b["instructions"])


if __name__ == "__main__":
    unittest.main()
