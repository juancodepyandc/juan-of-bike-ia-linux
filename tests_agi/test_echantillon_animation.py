"""Positions monde des sommets d'un GLB à l'instant t : pistes, hiérarchie, peau, morphing.

15/11/2026 — Le milieu d'un sujet animé se construit autour du volume que son corps balaie
réellement ; la pose de liaison seule (`boite_repos`) ne le voit pas. Chaque loi de lecture glTF
est vérifiée ici sur un GLB synthétique écrit par le test.
"""
from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
import animation_multi_sujets as ams  # noqa: E402
import echantillon_animation as ea  # noqa: E402
import glb_io  # noqa: E402


class Fabrique:
    """Écrit un GLB minimal accesseur par accesseur."""

    def __init__(self):
        self.blob = bytearray()
        self.doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": []}], "nodes": [],
                    "meshes": [], "accessors": [], "bufferViews": []}

    def acc(self, tableau, type_, *, ctype=5126, normalise=False, bornes=False):
        tableau = np.ascontiguousarray(tableau)
        while len(self.blob) % 4:
            self.blob.append(0)
        self.doc["bufferViews"].append({"buffer": 0, "byteOffset": len(self.blob), "byteLength": tableau.nbytes})
        self.blob.extend(tableau.tobytes())
        acc = {"bufferView": len(self.doc["bufferViews"]) - 1, "componentType": ctype,
               "count": int(tableau.shape[0]), "type": type_}
        if normalise:
            acc["normalized"] = True
        if bornes:
            plat = tableau.reshape(tableau.shape[0], -1)
            acc["min"], acc["max"] = plat.min(0).tolist(), plat.max(0).tolist()
        self.doc["accessors"].append(acc)
        return len(self.doc["accessors"]) - 1

    def maillage(self, positions, triangles=None, **attributs):
        prim = {"attributes": {"POSITION": self.acc(np.asarray(positions, np.float32), "VEC3", bornes=True), **attributs}}
        if triangles is not None:
            prim["indices"] = self.acc(np.asarray(triangles, np.uint32).ravel(), "SCALAR", ctype=5125)
        self.doc["meshes"].append({"primitives": [prim]})
        return len(self.doc["meshes"]) - 1

    def noeud(self, **champs):
        self.doc["nodes"].append(champs)
        return len(self.doc["nodes"]) - 1

    def animation(self, canaux):
        """canaux : [(noeud, chemin, temps, valeurs, interpolation)]."""
        anim = {"channels": [], "samplers": []}
        for noeud, chemin, temps, valeurs, mode in canaux:
            temps = np.asarray(temps, np.float32)
            valeurs = np.asarray(valeurs, np.float32)
            entree = self.acc(temps, "SCALAR", bornes=True)
            type_ = {1: "SCALAR", 3: "VEC3", 4: "VEC4"}[valeurs.shape[1] if valeurs.ndim > 1 else 1]
            sortie = self.acc(valeurs, type_)
            anim["samplers"].append({"input": entree, "output": sortie, "interpolation": mode})
            anim["channels"].append({"sampler": len(anim["samplers"]) - 1, "target": {"node": noeud, "path": chemin}})
        self.doc.setdefault("animations", []).append(anim)

    def charger(self, dossier, nom="essai.glb"):
        self.doc["buffers"] = [{"byteLength": len(self.blob)}]
        chemin = Path(dossier) / nom
        glb_io.save(str(chemin), self.doc, bytes(self.blob))
        return glb_io.load(str(chemin))


TRIANGLE = [[1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 1.0, 0.0]]


def _quat_y(degres):
    r = math.radians(degres) / 2.0
    return [0.0, math.sin(r), 0.0, math.cos(r)]


def _une_piste(dossier, chemin, temps, valeurs, mode="LINEAR", sommets=TRIANGLE):
    f = Fabrique()
    m = f.maillage(sommets)
    n = f.noeud(mesh=m)
    f.doc["scenes"][0]["nodes"] = [n]
    f.animation([(n, chemin, temps, valeurs, mode)])
    return f.charger(dossier)


class Pistes(unittest.TestCase):
    def test_translation_lineaire_bornee_avant_et_apres_le_clip(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc, blob = _une_piste(tmp, "translation", [0.0, 1.0], [[0, 0, 0], [0, 0, 2]])
            milieu = ea.points_animes(doc, blob, 0.5)[0][1]
            avant = ea.points_animes(doc, blob, -1.0)[0][1]
            apres = ea.points_animes(doc, blob, 5.0)[0][1]
        self.assertTrue(np.allclose(milieu[:, 2], 1.0))
        self.assertTrue(np.allclose(avant[:, 2], 0.0))
        self.assertTrue(np.allclose(apres[:, 2], 2.0))

    def test_step_tient_la_valeur_jusqu_a_la_cle_suivante(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc, blob = _une_piste(tmp, "translation", [0.0, 1.0, 2.0], [[0, 0, 0], [1, 0, 0], [3, 0, 0]], "STEP")
            lus = [ea.points_animes(doc, blob, t)[0][1][1, 0] for t in (0.99, 1.0, 1.5, 2.5)]
        self.assertEqual([round(float(v), 6) for v in lus], [0.0, 1.0, 1.0, 3.0])

    def test_rotation_par_slerp_a_vitesse_angulaire_constante_et_plus_court_chemin(self):
        """Au quart du temps d'un quart de tour : 22,5° exactement (une moyenne normalisée donnerait 21,6°)."""
        with tempfile.TemporaryDirectory() as tmp:
            for fin in (_quat_y(90.0), [-c for c in _quat_y(90.0)]):     # q et −q : même rotation
                doc, blob = _une_piste(tmp, "rotation", [0.0, 1.0], [_quat_y(0.0), fin])
                x, _, z = ea.points_animes(doc, blob, 0.25)[0][1][0]
                self.assertAlmostEqual(math.degrees(math.atan2(-z, x)), 22.5, places=3)

    def test_cubicspline_suit_la_spline_d_hermite_de_la_specification(self):
        # clés : (tangente entrante, valeur, tangente sortante) ; à u = 1/4 : h01 = 0,15625, h10 = 0,140625
        valeurs = [[0, 0, 0], [0, 0, 0], [2, 0, 0], [0, 0, 0], [4, 0, 0], [0, 0, 0]]
        with tempfile.TemporaryDirectory() as tmp:
            doc, blob = _une_piste(tmp, "translation", [0.0, 1.0], valeurs, "CUBICSPLINE")
            x = ea.points_animes(doc, blob, 0.25)[0][1][1, 0]
        self.assertAlmostEqual(float(x), 4 * 0.15625 + 2 * 0.140625, places=5)

    def test_duree_et_instants_reguliers(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc, blob = _une_piste(tmp, "translation", [0.0, 4.0], [[0, 0, 0], [0, 0, 2]])
            self.assertEqual(ea.duree(doc), 4.0)
            instants = ea.instants_reguliers(ea.duree(doc))
            boite = ea.boite_balayee(doc, blob, instants)
        self.assertEqual(len(instants), 49)                       # 12 par seconde, bornes incluses
        self.assertEqual((instants[0], instants[-1]), (0.0, 4.0))
        self.assertAlmostEqual(float(boite[0][2]), 0.0, places=6)
        self.assertAlmostEqual(float(boite[1][2]), 2.0, places=6)
        self.assertEqual(len(ea.instants_reguliers(1.0)), 24)     # jamais moins de 24 instants


class HierarchieEtMorphing(unittest.TestCase):
    def test_un_enfant_suit_la_rotation_de_son_parent(self):
        f = Fabrique()
        m = f.maillage([[0.0, 0.0, 0.0]])
        enfant = f.noeud(mesh=m, translation=[1.0, 0.0, 0.0])
        parent = f.noeud(children=[enfant], rotation=[0.0, 0.0, math.sin(math.pi / 4), math.cos(math.pi / 4)])
        f.doc["scenes"][0]["nodes"] = [parent]
        with tempfile.TemporaryDirectory() as tmp:
            doc, blob = f.charger(tmp)
            p = ea.points_animes(doc, blob, None)[0][1][0]
        self.assertTrue(np.allclose(p, [0.0, 1.0, 0.0], atol=1e-9))

    def test_poids_de_morphing_animes_sinon_ceux_du_maillage(self):
        f = Fabrique()
        delta = f.acc(np.tile(np.array([0.0, 1.0, 0.0], np.float32), (3, 1)), "VEC3", bornes=True)
        m = f.maillage(TRIANGLE)
        f.doc["meshes"][m]["primitives"][0]["targets"] = [{"POSITION": delta}]
        f.doc["meshes"][m]["weights"] = [0.25]
        n = f.noeud(mesh=m)
        f.doc["scenes"][0]["nodes"] = [n]
        f.animation([(n, "weights", [0.0, 1.0], [[0.0], [1.0]], "LINEAR")])
        with tempfile.TemporaryDirectory() as tmp:
            doc, blob = f.charger(tmp)
            repos = ea.points_animes(doc, blob, None)[0][1]
            mi = ea.points_animes(doc, blob, 0.5)[0][1]
        self.assertTrue(np.allclose(repos[:, 1] - np.array(TRIANGLE)[:, 1], 0.25))
        self.assertTrue(np.allclose(mi[:, 1] - np.array(TRIANGLE)[:, 1], 0.5))

    def test_cible_clairsemee_sans_bufferview(self):
        f = Fabrique()
        indices = f.acc(np.array([1], np.uint16), "SCALAR", ctype=5123)
        valeurs = f.acc(np.array([[0.0, 0.0, 3.0]], np.float32), "VEC3")
        f.doc["accessors"].append({"componentType": 5126, "count": 3, "type": "VEC3", "min": [0, 0, 0], "max": [0, 0, 3],
                                   "sparse": {"count": 1,
                                              "indices": {"bufferView": f.doc["accessors"][indices]["bufferView"],
                                                          "componentType": 5123},
                                              "values": {"bufferView": f.doc["accessors"][valeurs]["bufferView"]}}})
        clairseme = len(f.doc["accessors"]) - 1
        m = f.maillage(TRIANGLE)
        f.doc["meshes"][m]["primitives"][0]["targets"] = [{"POSITION": clairseme}]
        f.doc["meshes"][m]["weights"] = [1.0]
        n = f.noeud(mesh=m)
        f.doc["scenes"][0]["nodes"] = [n]
        with tempfile.TemporaryDirectory() as tmp:
            doc, blob = f.charger(tmp)
            p = ea.points_animes(doc, blob, None)[0][1]
        self.assertEqual(p[:, 2].round(6).tolist(), [0.0, 3.0, 0.0])


def _rig(f, *, piste_os=True):
    """Deux os : j0 à l'origine, j1 à (0,1,0) qui glisse de +1 en x sur 1 s. Poids en octets normalisés.

    Le nœud du maillage porte une translation (5,5,5) : la spécification veut qu'elle soit ignorée.
    """
    positions = [[0, 0, 0], [0, 2, 0], [0, 1, 0]]
    articulations = f.acc(np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 1, 0, 0]], np.uint8), "VEC4", ctype=5121)
    poids = f.acc(np.array([[255, 0, 0, 0], [255, 0, 0, 0], [128, 127, 0, 0]], np.uint8), "VEC4", ctype=5121,
                  normalise=True)
    inverses = np.stack([np.eye(4), np.eye(4)])
    inverses[1][1, 3] = -1.0                                   # inverse de la liaison de j1 (monde (0,1,0))
    ibm = f.acc(np.stack([m.T.ravel() for m in inverses]).astype(np.float32), "MAT4")
    m = f.maillage(positions, None, JOINTS_0=articulations, WEIGHTS_0=poids)
    j1 = f.noeud(name="j1", translation=[0.0, 1.0, 0.0])
    j0 = f.noeud(name="j0", children=[j1])
    armature = f.noeud(name="armature", children=[j0])
    corps = f.noeud(name="corps", mesh=m, skin=0, translation=[5.0, 5.0, 5.0])
    f.doc["skins"] = [{"joints": [j0, j1], "inverseBindMatrices": ibm}]
    f.doc["scenes"][0]["nodes"] = [armature, corps]
    if piste_os:
        f.animation([(j1, "translation", [0.0, 1.0], [[0, 1, 0], [1, 1, 0]], "LINEAR")])
    return corps


class Peau(unittest.TestCase):
    def test_les_os_placent_la_peau_et_le_noeud_du_maillage_est_ignore(self):
        f = Fabrique()
        _rig(f)
        with tempfile.TemporaryDirectory() as tmp:
            doc, blob = f.charger(tmp)
            repos = ea.points_animes(doc, blob, None)[0][1]
            fin = ea.points_animes(doc, blob, 1.0)[0][1]
        self.assertTrue(np.allclose(repos, [[0, 0, 0], [0, 2, 0], [0, 1, 0]], atol=1e-9))
        self.assertTrue(np.allclose(fin[0], [0, 0, 0]))          # tout sur j0 : immobile
        self.assertTrue(np.allclose(fin[1], [1, 2, 0]))          # tout sur j1 : suit l'os
        self.assertAlmostEqual(float(fin[2, 0]), 127 / 255, places=6)   # 128/255 + 127/255 = 1

    def test_la_pose_de_repos_rejoint_boite_repos(self):
        f = Fabrique()
        _rig(f)
        with tempfile.TemporaryDirectory() as tmp:
            doc, blob = f.charger(tmp)
            lo, hi = ea.Echantillonneur(doc, blob).boite([None])
            ref_lo, ref_hi = ams.boite_repos(doc, blob)
        self.assertTrue(np.allclose(lo, ref_lo) and np.allclose(hi, ref_hi))


class AiresEtTriangles(unittest.TestCase):
    def test_aire_par_sommet_somme_des_triangles_adjacents_sur_trois(self):
        f = Fabrique()
        m = f.maillage([[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], [[0, 1, 2], [0, 2, 3]])
        f.doc["scenes"][0]["nodes"] = [f.noeud(mesh=m)]
        with tempfile.TemporaryDirectory() as tmp:
            doc, blob = f.charger(tmp)
            aires = ea.aires_sommets(doc, blob, m)
        self.assertTrue(np.allclose(aires, [1 / 3, 1 / 6, 1 / 3, 1 / 6]))
        self.assertAlmostEqual(float(aires.sum()), 1.0)

    def test_sous_echantillon_aligne_points_et_aires(self):
        rng = np.random.default_rng(3)
        pos = rng.normal(size=(1000, 3))
        tri = rng.integers(0, 1000, size=(1500, 3))
        f = Fabrique()
        m = f.maillage(pos, tri)
        f.doc["scenes"][0]["nodes"] = [f.noeud(mesh=m)]
        with tempfile.TemporaryDirectory() as tmp:
            doc, blob = f.charger(tmp)
            points = ea.points_animes(doc, blob, None, echantillon=100)[0][1]
            aires = ea.aires_sommets(doc, blob, m, echantillon=100)
        self.assertEqual(len(points), len(aires))
        self.assertLessEqual(len(points), 100)
        self.assertTrue(np.allclose(points[1], pos[10], atol=1e-6))   # même pas : un sommet sur dix

    def test_bande_et_eventail_gardent_le_sens(self):
        f = Fabrique()
        m = f.maillage([[0, 0, 0], [0, 0, 1], [1, 0, 0], [1, 0, 1]])
        prim = f.doc["meshes"][m]["primitives"][0]
        prim["mode"] = 5
        with tempfile.TemporaryDirectory() as tmp:
            doc, blob = f.charger(tmp)
            tri = ea.triangles(doc, blob, doc["meshes"][m]["primitives"][0])
        p = np.array([[0, 0, 0], [0, 0, 1], [1, 0, 0], [1, 0, 1]], float)
        normales = np.cross(p[tri[:, 1]] - p[tri[:, 0]], p[tri[:, 2]] - p[tri[:, 0]])
        self.assertEqual(len(tri), 2)
        self.assertTrue(np.all(normales[:, 1] > 0))                # les deux triangles regardent le même côté


if __name__ == "__main__":
    unittest.main()
