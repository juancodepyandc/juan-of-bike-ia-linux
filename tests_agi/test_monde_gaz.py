"""Gaz simulés (Navier-Stokes) et liquides en veine : lois physiques mesurées, fichiers relus.

16/11/2026, Juan : « pas un effet bulle mais un vrai effet, comme les rivières et fontaines qui coulent ».
- un gaz est un VOLUME simulé (projection incompressible exacte, bouffée qui s'éteint, flux qui boucle sans
  saut), écrit dans le GLB et relu ;
- un jet d'eau est une VEINE continue (rayon par conservation du débit, couronne qui retombe dans la vasque,
  eau vive qui défile) ; une fontaine déclare sa buse et sa vasque, la scène l'en fait jaillir ;
- la bouche et la direction d'une émission se lisent sur l'image de référence.
Résolutions réduites : la physique est la même, seule la finesse change."""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from monde import animation_gltf, composer, emetteurs, emissions_objet, export_gltf, gaz, meubles  # noqa: E402
from monde import geometrie as g  # noqa: E402
from monde import reperage_emission, volume_gltf  # noqa: E402
from monde.ir import Instance, Noeud, Partie, Pose, Scene  # noqa: E402


def lire_gltf(chemin: Path) -> dict:
    d = chemin.read_bytes()
    n = struct.unpack_from("<I", d, 12)[0]
    return json.loads(d[20:20 + n])


class Solveur(unittest.TestCase):
    def test_la_projection_rend_la_vitesse_incompressible(self):
        grille = gaz._Grille((12, 10, 8), 0.02)
        rng = np.random.default_rng(0)
        u = rng.normal(size=grille.formes["u"]).astype(np.float32)
        v = rng.normal(size=grille.formes["v"]).astype(np.float32)
        w = rng.normal(size=grille.formes["w"]).astype(np.float32)
        gaz._projeter(grille, u, v, w, 0.01)
        div = (u[1:] - u[:-1] + v[:, 1:] - v[:, :-1] + w[:, :, 1:] - w[:, :, :-1]) / grille.h
        self.assertLess(float(np.abs(div).max()), 1e-2 * float(np.abs(u).mean()) / grille.h)

    def test_un_vent_uniforme_traverse_le_domaine_ouvert_sans_changer(self):
        grille = gaz._Grille((10, 8, 8), 0.05)
        u = np.full(grille.formes["u"], 0.4, np.float32)
        v = np.zeros(grille.formes["v"], np.float32)
        w = np.zeros(grille.formes["w"], np.float32)
        gaz._projeter(grille, u, v, w, 0.02)
        self.assertTrue(np.allclose(u, 0.4, atol=1e-5))


class Gaz(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.brume = gaz.simuler("brume", direction=(0.93, 0.37, 0.0), graine=1, resolution=40, nom="b")
        cls.vapeur = gaz.simuler("vapeur", graine=2, resolution=32, nom="v")
        cls.flamme = gaz.simuler("flamme", graine=3, resolution=32, nom="f")

    def test_un_coup_de_vaporisateur_porte_comme_un_vrai(self):
        m = self.brume.mesures
        self.assertTrue(0.12 < m["portee_m"] < 0.6, m)          # une bouffée de parfum : 20 à 40 cm
        self.assertLess(m["largeur_m"], 0.4, m)
        self.assertLess(m["masse_pic_image"], 20, m)             # le nuage est le plus fourni juste après le jet

    def test_une_bouffee_est_eteinte_avant_de_recommencer(self):
        self.assertLess(self.brume.mesures["raccord_boucle"], 0.02)
        self.assertEqual(len(self.brume.images), int(round(emetteurs.LOIS["brume"].duree_boucle * 30)))

    def test_un_flux_continu_boucle_sans_saut(self):
        # le raccord fin → début change autant que deux images voisines quelconques
        self.assertLess(self.vapeur.mesures["raccord_boucle"], 2.5, self.vapeur.mesures)
        self.assertLess(self.flamme.mesures["raccord_boucle"], 2.5, self.flamme.mesures)

    def test_la_vapeur_monte_et_la_flamme_porte_sa_chaleur(self):
        self.assertGreater(self.vapeur.mesures["hauteur_m"], 0.1)
        self.assertEqual(self.flamme.canaux, ("densite", "chaleur"))
        self.assertEqual(self.flamme.images[0].shape[-1], 2)
        self.assertGreater(int(self.flamme.images[5][..., 1].max()), 100)

    def test_un_volume_pose_a_l_echelle_garde_son_epaisseur_optique(self):
        place = self.brume.place((1.0, 2.0, 3.0), 4.0)
        self.assertAlmostEqual(place.pas, 4.0 * self.brume.pas)
        self.assertAlmostEqual(place.coin[1], 2.0 + 4.0 * self.brume.coin[1])
        self.assertAlmostEqual(place.optique()["extinction"] * 4.0, self.brume.optique()["extinction"], places=3)

    def test_f3d_peut_relire_le_volume(self):
        with tempfile.TemporaryDirectory() as tmp:
            vti = gaz.ecrire_vti(self.brume, 9, Path(tmp) / "b.vti")
            racine = ET.parse(vti).getroot()
        image = racine.find("ImageData")
        nx, ny, nz = self.brume.dims
        self.assertEqual(image.get("WholeExtent"), f"0 {nx - 1} 0 {ny - 1} 0 {nz - 1}")

    def test_un_gaz_inconnu_est_une_erreur(self):
        with self.assertRaises(KeyError):
            gaz.simuler("arc_en_ciel")

    def test_le_volume_est_ecrit_dans_le_glb_et_relu(self):
        scene = Scene(Noeud("table", parties=[Partie(g.cylindre(0.04, 0.09), "ceramique", "tasse")]))
        with tempfile.TemporaryDirectory() as tmp:
            glb = Path(tmp) / "t.glb"
            export_gltf.exporter(scene, glb, resolution=32)
            ecrit = volume_gltf.injecter(glb, [self.flamme])
            relus = volume_gltf.lire(glb)
            gltf = lire_gltf(glb)
        self.assertTrue(ecrit["ok"])
        self.assertEqual(len(relus), 1)
        meta = relus[0]["meta"]
        self.assertEqual(meta["schema"], "aurora.volume.v1")
        self.assertEqual(meta["canaux"], ["densite", "chaleur"])
        self.assertTrue(all(np.array_equal(a, b) for a, b in zip(relus[0]["images"], self.flamme.images)))
        self.assertTrue(np.all(np.diff(meta["decalages"]) > 0))
        indice = next(i for i, n in enumerate(gltf["nodes"]) if n.get("name") == "f")
        self.assertIn(indice, gltf["scenes"][0]["nodes"])          # posé à la racine : boîte en coordonnées scène
        self.assertEqual(gltf["buffers"][0]["byteLength"] % 4, 0)


class Veine(unittest.TestCase):
    def test_un_jet_vertical_monte_en_veine_et_retombe_dans_la_vasque(self):
        noeud, pistes, m = emetteurs.veine(emetteurs.Emission("jet_liquide", origine=(0.0, 2.4, 0.0), nom="jet"),
                                           niveau=1.7, receptacle=0.5)
        self.assertTrue(m["brisee_au_sommet"])
        self.assertTrue(0.8 < m["hauteur_max_m"] < 1.05, m)       # v²/2g ≈ 0,99 m pour 4,4 m/s (94 % à la rupture)
        self.assertLessEqual(m["rayon_couronne_m"], 0.5)          # la couronne retombe DANS la vasque
        # conservation du débit : la veine s'épaissit en ralentissant, jusqu'à r₀/√0,25 = 2 r₀ (± ondulation)
        self.assertTrue(1.6 * m["rayon_buse_m"] < m["rayon_max_m"] < 2.6 * m["rayon_buse_m"], m)
        self.assertEqual(len(pistes), m["gouttes"])
        veine = noeud.parties[0].maillage
        uv = np.asarray(veine.visual.uv)
        self.assertAlmostEqual(float(uv[:, 1].max()), m["longueur_veine_m"], places=3)   # v le long de l'écoulement

    def test_un_jet_incline_arrive_entier_au_sol(self):
        _, _, m = emetteurs.veine(emetteurs.Emission("jet_liquide", origine=(0.0, 0.5, 0.0), direction=(1.0, 1.0, 0.0),
                                                     nom="arc"), niveau=0.0)
        self.assertFalse(m["brisee_au_sommet"])
        self.assertGreater(m["longueur_veine_m"], 2.0)

    def test_l_eau_vive_coule_dans_le_glb(self):
        noeud, pistes, _ = emetteurs.veine(emetteurs.Emission("jet_liquide", origine=(0.0, 1.0, 0.0), nom="jet"),
                                           niveau=0.3, receptacle=0.4)
        with tempfile.TemporaryDirectory() as tmp:
            glb = Path(tmp) / "j.glb"
            export_gltf.exporter(Scene(Noeud("racine", enfants=[noeud])), glb, resolution=32)
            res = animation_gltf.injecter(glb, pistes)
            gltf = lire_gltf(glb)
        flux = {m["name"]: (m.get("extras") or {}).get("aurora_flow") for m in gltf["materials"]}["eau_vive"]
        self.assertEqual((flux["masque"], flux["defilement"], flux["schema"]), ("aucun", "continu", "aurora.flow.v1"))
        self.assertGreater(flux["vitesse_uv"], 1.0)
        self.assertTrue(res["ok"])

    def test_un_gaz_n_est_pas_une_veine(self):
        with self.assertRaises(KeyError):
            emetteurs.veine(emetteurs.Emission("brume", origine=(0, 0, 0)), niveau=0.0)


class Fontaine(unittest.TestCase):
    def test_une_fontaine_declare_sa_buse_et_jaillit_dans_la_scene(self):
        objet = meubles.generer("fontaine", graine=3, hauteur=2.6)
        bouche = objet.meta["bouches"][0]
        self.assertAlmostEqual(bouche["position"][1], objet.hauteur, places=3)   # la buse est au sommet
        self.assertLess(bouche["niveau"], bouche["position"][1])
        self.assertGreater(bouche["receptacle"], 0.1)
        pose = Pose(5.0, -3.0, 0.4, 0.2)
        jets, pistes = composer.emissions_des_objets(Noeud("ville", instances=[Instance(objet, pose, "fontaine")]))
        self.assertEqual(len(jets), 1)
        base = jets[0].parties[0].maillage.vertices
        depart = base[: emetteurs.SECTIONS_VEINE + 1].mean(axis=0)
        attendu = pose.matrice() @ np.array([*bouche["position"], 1.0])
        self.assertTrue(np.allclose(depart, attendu[:3], atol=0.02), (depart, attendu))
        self.assertGreater(len(pistes), 0)


class Reperage(unittest.TestCase):
    def test_bouche_et_direction_lues_sur_une_image(self):
        from PIL import Image
        H, W = 400, 400
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        fond = 200.0 + 30.0 * x / W
        image = np.repeat(fond[..., None], 3, axis=2)
        objet = (x > 150) & (x < 210) & (y > 150) & (y < 330)
        image[objet] = (60, 40, 40)
        # panache clair qui part du haut-droit de l'objet vers la droite en montant (cône de 12°)
        sx, sy = 212.0, 160.0
        d = np.array([0.95, -0.31])
        d /= np.linalg.norm(d)
        rel_x, rel_y = x - sx, y - sy
        le_long = rel_x * d[0] + rel_y * d[1]
        travers = -rel_x * d[1] + rel_y * d[0]
        cone = (le_long > 0) & (le_long < 170) & (np.abs(travers) < 3 + 0.21 * le_long)
        image[cone] = np.minimum(255, image[cone] + 45)
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "r.png"
            Image.fromarray(image.astype(np.uint8)).save(ref)
            rep = reperage_emission.reperer(ref, "brume", masque=objet, vision=False)
        self.assertIsNotNone(rep)
        bx, by = rep["bouche_px"]
        self.assertTrue(185 < bx < 240 and 140 < by < 185, rep)          # sans vision : sommet du cône, ±5 %
        self.assertGreater(float(np.dot(rep["direction_image"], d)), 0.95, rep)
        sommets = np.array([[-0.3, -0.9, -0.2], [0.3, 0.9, 0.2]])
        origine, direction = reperage_emission.vers_modele(rep, sommets)
        self.assertGreater(direction[0], 0.9)                       # vers la droite de la vue de face (+X)
        self.assertGreater(direction[1], 0.0)                       # et en montant (+Y)
        self.assertGreater(origine[1], 0.6)                         # au haut de l'objet


class EmissionsObjet(unittest.TestCase):
    def test_un_objet_livre_recoit_un_gaz_simule(self):
        scene = Scene(Noeud("flacon", parties=[Partie(g.cylindre(0.05, 0.15), "verre", "flacon")]))
        with tempfile.TemporaryDirectory() as tmp:
            entree, sortie = Path(tmp) / "m.glb", Path(tmp) / "e.glb"
            export_gltf.exporter(scene, entree, resolution=32)
            rapport = emissions_objet.ajouter(entree, sortie, [{"type": "vapeur", "point": "haut"}], resolution=28)
            relus = volume_gltf.lire(sortie)
        self.assertTrue(rapport["ok"], rapport)
        self.assertEqual(rapport["emissions"][0]["rendu"], "volume")
        self.assertEqual(rapport["emissions"][0]["source"], "boite")
        self.assertEqual(len(relus), 1)
        meta, images = relus[0]["meta"], relus[0]["images"]
        nx, ny, nz = meta["dims"]
        bas, haut = np.asarray(meta["boite"]["min"]), np.asarray(meta["boite"]["max"])
        y = bas[1] + (np.arange(ny) + 0.5) * (haut[1] - bas[1]) / ny
        masse = sum((im.astype(np.float64) / 255.0) ** 2 for im in images).sum(axis=(0, 2))
        self.assertGreater(float((masse * y).sum() / masse.sum()), 0.15)   # la vapeur monte au-dessus du flacon


if __name__ == "__main__":
    unittest.main()
