"""Le milieu qu'un mouvement implique, construit autour du corps animé, et la porte qui le mesure.

15/11/2026 — « Sharko le requin qui nage » a été livré à sec : aucun volume d'eau dans la
composition (part immergée 0,0 à chaque instant). Les sujets de ces tests sont écrits par le test :
une capsule « nageur » couchée, avec peau et animation (la racine avance, la queue bat), et un
« marcheur » immobile posé au sol.
"""
from __future__ import annotations

import json
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
import milieu_scene as ms  # noqa: E402

LIQUIDE = {"matiere": "liquide", "relation": "immerge", "justification": "nage"}
SOL = {"matiere": "solide", "relation": "sur", "justification": "marche"}


def ellipsoide(demi_axes, centre, n_lat=10, n_lon=16):
    """Ellipsoïde fermé (deux pôles, anneaux) : positions (N, 3) et triangles (F, 3)."""
    points = [[0.0, 1.0, 0.0]]
    for i in range(1, n_lat):
        phi = math.pi * i / n_lat
        points += [[math.sin(phi) * math.cos(2 * math.pi * j / n_lon), math.cos(phi),
                    math.sin(phi) * math.sin(2 * math.pi * j / n_lon)] for j in range(n_lon)]
    points.append([0.0, -1.0, 0.0])
    tri = [[0, 1 + (j + 1) % n_lon, 1 + j] for j in range(n_lon)]
    for i in range(n_lat - 2):
        a, b = 1 + i * n_lon, 1 + (i + 1) * n_lon
        for j in range(n_lon):
            k = (j + 1) % n_lon
            tri += [[a + j, a + k, b + j], [a + k, b + k, b + j]]
    sud, dernier = len(points) - 1, 1 + (n_lat - 2) * n_lon
    tri += [[sud, dernier + j, dernier + (j + 1) % n_lon] for j in range(n_lon)]
    return np.array(points) * np.array(demi_axes) + np.array(centre), np.array(tri)


class Fabrique:
    def __init__(self):
        self.blob = bytearray()
        self.doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": []}], "nodes": [],
                    "meshes": [], "accessors": [], "bufferViews": []}

    def acc(self, tableau, type_, *, ctype=5126, bornes=False):
        tableau = np.ascontiguousarray(tableau)
        while len(self.blob) % 4:
            self.blob.append(0)
        self.doc["bufferViews"].append({"buffer": 0, "byteOffset": len(self.blob), "byteLength": tableau.nbytes})
        self.blob.extend(tableau.tobytes())
        acc = {"bufferView": len(self.doc["bufferViews"]) - 1, "componentType": ctype,
               "count": int(tableau.shape[0]), "type": type_}
        if bornes:
            plat = tableau.reshape(tableau.shape[0], -1)
            acc["min"], acc["max"] = plat.min(0).tolist(), plat.max(0).tolist()
        self.doc["accessors"].append(acc)
        return len(self.doc["accessors"]) - 1

    def ecrire(self, chemin):
        self.doc["buffers"] = [{"byteLength": len(self.blob)}]
        glb_io.save(str(chemin), self.doc, bytes(self.blob))
        return Path(chemin)


def _translation(v):
    m = np.eye(4)
    m[:3, 3] = v
    return m


def _quat_y(degres):
    r = math.radians(degres) / 2.0
    return [0.0, math.sin(r), 0.0, math.cos(r)]


def ecrire_nageur(chemin, centre=(0.0, 0.5, 0.0)):
    """Capsule couchée le long de x (1,6 m), deux os : la racine avance de 0,4 m et revient en 2 s,
    la queue (x < −0,3 m) bat de ±20° autour de la verticale."""
    centre = np.array(centre, float)
    pos, tri = ellipsoide((0.8, 0.2, 0.25), centre)
    f = Fabrique()
    i_pos = f.acc(pos.astype(np.float32), "VEC3", bornes=True)
    i_tri = f.acc(tri.astype(np.uint32).ravel(), "SCALAR", ctype=5125)
    articulations = np.zeros((len(pos), 4), np.uint16)
    articulations[pos[:, 0] < centre[0] - 0.3, 0] = 1
    poids = np.zeros((len(pos), 4), np.float32)
    poids[:, 0] = 1.0
    i_j = f.acc(articulations, "VEC4", ctype=5123)
    i_w = f.acc(poids, "VEC4")
    liaisons = [_translation(centre), _translation(centre + [-0.3, 0.0, 0.0])]
    i_ibm = f.acc(np.stack([np.linalg.inv(m).T.ravel() for m in liaisons]).astype(np.float32), "MAT4")
    f.doc["meshes"] = [{"primitives": [{"attributes": {"POSITION": i_pos, "JOINTS_0": i_j, "WEIGHTS_0": i_w},
                                        "indices": i_tri}]}]
    f.doc["nodes"] = [{"name": "armature", "children": [1]},
                      {"name": "racine", "translation": centre.tolist(), "children": [2]},
                      {"name": "queue", "translation": [-0.3, 0.0, 0.0]},
                      {"name": "corps", "mesh": 0, "skin": 0}]
    f.doc["skins"] = [{"joints": [1, 2], "inverseBindMatrices": i_ibm}]
    f.doc["scenes"] = [{"nodes": [0, 3]}]
    canaux, echantillonneurs = [], []
    for noeud, chemin_, temps, valeurs, type_ in (
            (1, "translation", [0.0, 1.0, 2.0], [centre, centre + [0.4, 0, 0], centre], "VEC3"),
            (2, "rotation", [0.0, 0.5, 1.5, 2.0], [_quat_y(0), _quat_y(20), _quat_y(-20), _quat_y(0)], "VEC4")):
        entree = f.acc(np.array(temps, np.float32), "SCALAR", bornes=True)
        sortie = f.acc(np.array(valeurs, np.float32), type_)
        echantillonneurs.append({"input": entree, "output": sortie, "interpolation": "LINEAR"})
        canaux.append({"sampler": len(echantillonneurs) - 1, "target": {"node": noeud, "path": chemin_}})
    f.doc["animations"] = [{"name": "nage", "channels": canaux, "samplers": echantillonneurs}]
    return f.ecrire(chemin)


def ecrire_marcheur(chemin, x=4.0):
    """Corps debout immobile, pieds au sol (y = 0), sans animation."""
    pos, tri = ellipsoide((0.25, 0.8, 0.2), (x, 0.8, 0.0))
    f = Fabrique()
    i_pos = f.acc(pos.astype(np.float32), "VEC3", bornes=True)
    i_tri = f.acc(tri.astype(np.uint32).ravel(), "SCALAR", ctype=5125)
    f.doc["meshes"] = [{"primitives": [{"attributes": {"POSITION": i_pos}, "indices": i_tri}]}]
    f.doc["nodes"] = [{"name": "corps", "mesh": 0}]
    f.doc["scenes"] = [{"nodes": [0]}]
    return f.ecrire(chemin)


def _volume(dossier, **reglages):
    parametres = dict(centre_xz=(0.0, 0.0), empreinte_xz=(3.2, 2.4), fond_y=-0.2, surface_y=0.8, duree_s=2.0,
                      amplitude=0.06, longueur_onde=0.8, couleur=ms.couleur_milieu_profond(),
                      chemin=Path(dossier) / "eau.glb")
    parametres.update(reglages)
    return ms.construire_volume_liquide(**parametres)


class VolumeLiquide(unittest.TestCase):
    def test_volume_ferme_oriente_vers_l_exterieur_a_tout_instant(self):
        with tempfile.TemporaryDirectory() as tmp:
            info = _volume(tmp)
            doc, blob = glb_io.load(info["chemin"])
            tri = ea.triangles(doc, blob, doc["meshes"][0]["primitives"][0])
            for t in (0.0, info["periode_s"] / 4, info["periode_s"] / 3, 1.37):
                points = ea.points_animes(doc, blob, t)[0][1]
                f = ms.fermeture(points, tri)
                self.assertEqual((f["aretes_de_bord"], f["aretes_non_manifold"], f["euler"]), (0, 0, 2), t)
                self.assertTrue(f["orientation_coherente"])
                self.assertAlmostEqual(f["volume_signe"], 3.2 * 2.4 * 1.0, delta=0.02 * 3.2 * 2.4)

    def test_deux_cibles_une_animation_boucle_et_materiau_translucide(self):
        with tempfile.TemporaryDirectory() as tmp:
            info = _volume(tmp)
            doc, blob = glb_io.load(info["chemin"])
            ech = ea.Echantillonneur(doc, blob)
            duree = ea.duree(doc)
            w0, wt, defaut = ech.poids_morph(0, 0.0), ech.poids_morph(0, duree), ech.poids_morph(0, None)
        prim = doc["meshes"][0]["primitives"][0]
        mat = doc["materials"][prim["material"]]
        self.assertEqual(len(prim["targets"]), 2)
        self.assertEqual(len(doc["animations"]), 1)
        self.assertAlmostEqual(duree, 2.0, places=6)
        self.assertTrue(np.allclose(w0, wt) and np.allclose(defaut, w0) and np.allclose(w0, [1.0, 0.0]))
        self.assertEqual(mat["alphaMode"], "BLEND")
        # alpha glTF = facteur × texture ≈ 0,45, porté par la texture : le seul alpha que f3d 2.5.0 lit
        pbr = mat["pbrMetallicRoughness"]
        alpha_tex = ms.alpha_texture(doc, blob, pbr["baseColorTexture"]["index"])
        self.assertEqual(pbr["baseColorFactor"][3], 1.0)
        self.assertAlmostEqual(pbr["baseColorFactor"][3] * alpha_tex, 0.45, delta=0.003)
        uv = glb_io.accessor(doc, blob, prim["attributes"]["TEXCOORD_0"]).astype(float)
        tri = ea.triangles(doc, blob, prim)
        e1, e2 = uv[tri[:, 1]] - uv[tri[:, 0]], uv[tri[:, 2]] - uv[tri[:, 0]]
        self.assertTrue(np.all(np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) > 0))   # Jacobien UV non dégénéré
        self.assertEqual(mat["extensions"]["KHR_materials_transmission"]["transmissionFactor"], 1.0)
        self.assertAlmostEqual(mat["extensions"]["KHR_materials_ior"]["ior"], 1.33)
        self.assertIn("KHR_materials_volume", mat["extensions"])
        milieu = doc["nodes"][0]["extras"]["aurora_milieu"]
        self.assertEqual(milieu["matiere"], "liquide")
        self.assertAlmostEqual(milieu["surface_y"], 0.8, places=6)
        self.assertAlmostEqual(milieu["fond_y"], -0.2, places=6)
        self.assertEqual(milieu["periodes"] * milieu["periode_s"], 2.0)

    def test_houle_en_quadrature_qui_avance(self):
        """Une houle qui avance a la même amplitude partout ; une onde stationnaire aurait des nœuds."""
        with tempfile.TemporaryDirectory() as tmp:
            info = _volume(tmp, empreinte_xz=(4.0, 4.0), longueur_onde=0.8)
            doc, blob = glb_io.load(info["chemin"])
            repos = glb_io.accessor(doc, blob, doc["meshes"][0]["primitives"][0]["attributes"]["POSITION"])
            surface = np.nonzero((np.abs(repos[:, 1] - info["surface_y"]) < 1e-6)
                                 & (np.abs(repos[:, 2]) == np.abs(repos[:, 2]).min())
                                 & (np.abs(repos[:, 0]) <= 0.4))[0]
            quart = info["periode_s"] / 4
            d0, dq, dm = (ea.points_animes(doc, blob, t)[0][1][surface, 1] - info["surface_y"]
                          for t in (0.0, quart, 2 * quart))
        self.assertGreaterEqual(len(surface), 5)
        amplitude = np.hypot(d0, dq)
        self.assertTrue(np.allclose(amplitude, info["amplitude"], rtol=0.01), amplitude)
        self.assertTrue(np.allclose(dm, -d0, atol=1e-5))            # demi-période : opposée
        self.assertGreater(float(np.ptp(d0)), info["amplitude"])     # la crête est quelque part, pas partout

    def test_couleur_et_periode_viennent_de_la_physique(self):
        r, v, b = ms.couleur_milieu_profond()
        self.assertTrue(b == 1.0 and r < v < b)                       # le rouge est absorbé le premier
        self.assertAlmostEqual(ms.periode_houle(1.0, 100.0), math.sqrt(2 * math.pi * 1.0 / 9.81), places=4)

    def test_un_maillage_ouvert_est_vu_ouvert(self):
        f = ms.fermeture([[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], [[0, 1, 2], [0, 2, 3]])
        self.assertFalse(f["ferme"])
        self.assertEqual(f["aretes_de_bord"], 4)


class Composition(unittest.TestCase):
    def test_nageur_immerge_et_marcheur_au_sec(self):
        with tempfile.TemporaryDirectory() as tmp:
            nageur, marcheur = ecrire_nageur(Path(tmp) / "n.glb"), ecrire_marcheur(Path(tmp) / "m.glb", x=4.0)
            res = ms.composer_avec_milieux([{"glb": nageur, "nom": "Nageur", "recalage": None, "milieu": LIQUIDE},
                                            {"glb": marcheur, "nom": "Marcheur", "recalage": None, "milieu": SOL}],
                                           Path(tmp) / "scene.glb", rapport=Path(tmp) / "milieu.json")
            doc, _ = glb_io.load(res["sortie"])
            ecrit = json.loads((Path(tmp) / "milieu.json").read_text(encoding="utf-8"))
        porte = res["porte"]
        self.assertTrue(res["ok"], porte["raisons"])
        self.assertEqual(ecrit["sortie"], res["sortie"])
        self.assertEqual(porte["mesures"]["M2"]["Nageur"]["part_min"], 1.0)
        self.assertGreaterEqual(porte["mesures"]["M2"]["Nageur"]["instants"], 24)
        self.assertEqual(porte["mesures"]["M4"]["Marcheur"]["part_max"], 0.0)
        self.assertTrue(porte["mesures"]["M1"]["ferme"] and porte["mesures"]["M1"]["translucide"])
        self.assertGreater(porte["mesures"]["M5"]["deplacement_crete_a_creux_max_m"], 0.0)
        self.assertTrue(porte["mesures"]["M6"]["ok"])
        self.assertEqual(res["deplacements"], [])
        self.assertEqual([m["etat"] for m in res["milieux"]], ["construit", "sol_existant"])
        # une seule animation : les pistes du nageur et la piste de poids de l'eau ensemble
        self.assertEqual(len(doc["animations"]), 1)
        self.assertIn("weights", {c["target"]["path"] for c in doc["animations"][0]["channels"]})
        self.assertEqual([doc["nodes"][i]["name"] for i in doc["scenes"][0]["nodes"]],
                         ["Nageur", "Marcheur", ms.NOM_VOLUME])
        # le volume entoure le balayage réel : la racine avance de 0,4 m, l'empreinte la suit
        volume = res["volume"]
        self.assertGreater(volume["centre_xz"][0] + volume["empreinte_xz"][0] / 2, 1.2)
        self.assertLess(porte["rapports"]["Nageur"]["angle_axe_long_horizontale_deg"]["moyen"], 30.0)

    def test_une_intrusion_deplace_le_nageur_selon_l_axe_de_moindre_penetration(self):
        with tempfile.TemporaryDirectory() as tmp:
            nageur, marcheur = ecrire_nageur(Path(tmp) / "n.glb"), ecrire_marcheur(Path(tmp) / "m.glb", x=1.5)
            res = ms.composer_avec_milieux([{"glb": nageur, "nom": "Nageur", "recalage": None, "milieu": LIQUIDE},
                                            {"glb": marcheur, "nom": "Marcheur", "recalage": None, "milieu": SOL}],
                                           Path(tmp) / "scene.glb")
        self.assertTrue(res["ok"], res["porte"]["raisons"])
        self.assertEqual(len(res["deplacements"]), 1)
        self.assertEqual((res["deplacements"][0]["axe"], res["deplacements"][0]["contre"]), ("-x", "Marcheur"))
        self.assertLess(res["entrees"][0]["recalage"]["translation"][0], 0.0)
        self.assertIsNone(res["entrees"][1]["recalage"])               # le sujet au sol ne bouge pas
        self.assertEqual(res["porte"]["mesures"]["M4"]["Marcheur"]["part_max"], 0.0)
        self.assertEqual(res["porte"]["mesures"]["M2"]["Nageur"]["part_min"], 1.0)

    def test_la_porte_refuse_une_composition_sans_eau(self):
        with tempfile.TemporaryDirectory() as tmp:
            nageur, marcheur = ecrire_nageur(Path(tmp) / "n.glb"), ecrire_marcheur(Path(tmp) / "m.glb")
            ams.composer([{"glb": nageur, "nom": "Nageur"}, {"glb": marcheur, "nom": "Marcheur"}], Path(tmp) / "sec.glb")
            porte = ms.porte_milieu(Path(tmp) / "sec.glb", {"sujets": [{"nom": "Nageur", "milieu": LIQUIDE},
                                                                       {"nom": "Marcheur", "milieu": SOL}]})
        self.assertFalse(porte["ok"])
        self.assertEqual(porte["mesures"]["M2"]["Nageur"]["part_min"], 0.0)
        self.assertTrue(any(r.startswith("M1") for r in porte["raisons"]))
        self.assertTrue(any(r.startswith("M2") for r in porte["raisons"]))

    def test_une_immersion_partielle_est_mesuree_et_refusee(self):
        with tempfile.TemporaryDirectory() as tmp:
            nageur = ecrire_nageur(Path(tmp) / "n.glb")
            eau = _volume(tmp, centre_xz=(0.2, 0.0), empreinte_xz=(3.0, 2.0), fond_y=0.0, surface_y=0.5, amplitude=0.01)
            ams.composer([{"glb": nageur, "nom": "Nageur"}, {"glb": eau["chemin"], "nom": ms.NOM_VOLUME}],
                         Path(tmp) / "mi.glb")
            porte = ms.porte_milieu(Path(tmp) / "mi.glb", {"sujets": [{"nom": "Nageur", "milieu": LIQUIDE}]})
        part = porte["mesures"]["M2"]["Nageur"]["part_min"]
        self.assertFalse(porte["ok"])
        self.assertTrue(0.4 < part < 0.6, part)                        # moitié du corps sous la surface

    def test_un_liquide_que_f3d_dessinerait_opaque_est_refuse(self):
        """15/11/2026 : alpha 0,45 dans le seul facteur ⇒ f3d 2.5.0 dessine le volume opaque et cache le nageur."""
        with tempfile.TemporaryDirectory() as tmp:
            nageur = ecrire_nageur(Path(tmp) / "n.glb")
            eau = _volume(tmp)
            doc, blob = glb_io.load(eau["chemin"])
            pbr = doc["materials"][0]["pbrMetallicRoughness"]
            pbr.pop("baseColorTexture")
            pbr["baseColorFactor"][3] = 0.45                          # translucide pour glTF, opaque pour f3d
            glb_io.save(eau["chemin"], doc, blob)
            ams.composer([{"glb": nageur, "nom": "Nageur"}, {"glb": eau["chemin"], "nom": ms.NOM_VOLUME}],
                         Path(tmp) / "opaque.glb")
            porte = ms.porte_milieu(Path(tmp) / "opaque.glb", {"sujets": [{"nom": "Nageur", "milieu": LIQUIDE}]})
        self.assertFalse(porte["ok"])
        self.assertTrue(porte["mesures"]["M1"]["translucide"])
        self.assertFalse(porte["mesures"]["M1"]["translucide_f3d"])
        self.assertTrue(any("opaque dans f3d" in r for r in porte["raisons"]))

    def test_un_milieu_lu_mais_pas_construit_n_est_jamais_tu(self):
        with tempfile.TemporaryDirectory() as tmp:
            nageur = ecrire_nageur(Path(tmp) / "n.glb")
            res = ms.composer_avec_milieux([{"glb": nageur, "nom": "Flotteur", "recalage": None,
                                             "milieu": {"matiere": "liquide", "relation": "a_la_surface"},
                                             "emissions": ["fumée"]}], Path(tmp) / "scene.glb")
        self.assertFalse(res["ok"])
        self.assertIsNone(res["volume"])
        self.assertEqual([m["etat"] for m in res["milieux"]], ["lu, non construit", "lu, non construit"])
        self.assertEqual(sum("lu, non construit" in r or "non construites" in r for r in res["porte"]["raisons"]), 2)

    def test_le_compositeur_injecte_recoit_le_volume_comme_entree(self):
        appels = []

        def espion(entrees, sortie):
            appels.append([dict(e) for e in entrees])
            return ams.composer(entrees, sortie)

        with tempfile.TemporaryDirectory() as tmp:
            nageur = ecrire_nageur(Path(tmp) / "n.glb")
            res = ms.composer_avec_milieux([{"glb": nageur, "nom": "Nageur", "recalage": None, "milieu": LIQUIDE}],
                                           Path(tmp) / "scene.glb", composer=espion)
        self.assertTrue(res["ok"], res["porte"]["raisons"])
        self.assertEqual(len(appels), 1)
        self.assertEqual([e["nom"] for e in appels[0]], ["Nageur", ms.NOM_VOLUME])
        self.assertTrue(appels[0][1]["glb"].endswith("scene_milieu_liquide.glb"))


class Cliquet(unittest.TestCase):
    def test_les_seuils_ne_font_que_se_resserrer(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "judge_ratchet_milieu.json"
            depart = ms.lire_seuils_milieu(chemin)
            self.assertEqual((depart["tau_imm"], depart["tau_x"]), (0.95, 0.02))
            chemin.write_text(json.dumps({"ratchet_level": 0, "tau_imm": 0.5, "tau_x": 0.5}), encoding="utf-8")
            relache = ms.lire_seuils_milieu(chemin)
            self.assertEqual((relache["tau_imm"], relache["tau_x"]), (0.95, 0.02))   # relâcher est impossible
            niveaux, imm, x = [], [], []
            for _ in range(12):
                s = ms.durcir_cliquet_milieu(chemin)
                niveaux.append(s["ratchet_level"])
                imm.append(s["tau_imm"])
                x.append(s["tau_x"])
            self.assertEqual(niveaux, list(range(1, 13)))                            # strictement croissant
            self.assertTrue(all(b >= a for a, b in zip(imm, imm[1:])) and all(b <= a for a, b in zip(x, x[1:])))
            self.assertGreater(imm[0], 0.95)
            self.assertAlmostEqual(imm[-1], 0.99)
            self.assertAlmostEqual(x[-1], 0.005)
            chemin.write_text("{illisible", encoding="utf-8")
            corrompu = ms.lire_seuils_milieu(chemin)
            self.assertEqual((corrompu["tau_imm"], corrompu["tau_x"]), (0.99, 0.005))  # jamais relâché


class RendusF3D(unittest.TestCase):
    def test_rendu_logiciel_a_l_instant_demande_et_blanc_pur_mesure(self):
        from PIL import Image
        vus = []

        def faux_f3d(commande, env=None, **_):
            vus.append((commande, env))
            sortie = next(a.split("=", 1)[1] for a in commande if a.startswith("--output="))
            image = np.zeros((10, 10, 3), np.uint8)
            image[:5] = 255                                                           # moitié blanc pur
            Image.fromarray(image).save(sortie)
            return type("Fini", (), {"returncode": 0, "stderr": ""})()

        with tempfile.TemporaryDirectory() as tmp:
            res = ms.planche_f3d(Path(tmp) / "scene.glb", tmp, [0, 1.5], prefixe="scene", executer=faux_f3d)
            self.assertTrue(Path(res["planche"]).is_file())
        commande, env = vus[1]
        self.assertTrue(res["ok"])
        self.assertIn("--animation-time=1.5", commande)
        self.assertIn("--up=+Y", commande)
        self.assertIn("--translucency-support", commande)
        self.assertIn("--resolution=600,600", commande)
        self.assertEqual((env["LIBGL_ALWAYS_SOFTWARE"], env["__GLX_VENDOR_LIBRARY_NAME"]), ("1", "mesa"))
        self.assertEqual(res["part_blanc_pur_max"], 0.5)

    def test_la_camera_laterale_regarde_perpendiculairement_aux_sujets(self):
        e = math.radians(20.0)
        alignes_x = ms.direction_camera_laterale([[-1.0, 0.0], [1.0, 0.0]])
        alignes_z = ms.direction_camera_laterale([[0.0, -1.0], [0.0, 1.0]])
        self.assertTrue(np.allclose(alignes_x, [0.0, -math.sin(e), -math.cos(e)], atol=1e-4))
        self.assertTrue(np.allclose(alignes_z, [-math.cos(e), -math.sin(e), 0.0], atol=1e-4))


if __name__ == "__main__":
    unittest.main()
