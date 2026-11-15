"""Lecture d'une phrase en programme de scène (monde.programme) : contrat, correction unique, complétude.

Aucun modèle réel : `interroger` est remplacé par une fonction qui rend des réponses écrites d'avance et
compte les appels. Les essais avec le vrai modèle local sont dans
application/output/3d/essais/monde/programme/ (hors dépôt).
"""
from __future__ import annotations

import copy
import json
import socket
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from monde import programme as prog, vocabulaire as voc  # noqa: E402


class Faux:
    """Modèle factice : rend les réponses dans l'ordre et garde les messages reçus."""

    def __init__(self, *reponses):
        self.reponses = list(reponses)
        self.messages: list[str] = []

    def __call__(self, message: str) -> str:
        self.messages.append(message)
        r = self.reponses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)


def maison(**sur):
    brut = {
        "type_scene": "interieur", "titre": "Maison", "style": {"texte": "réaliste", "architecture": None},
        "interieur": {"complet": False, "hauteur_plafond": 2.6, "pieces": [
            {"nom": "entrée", "fonction": "entree", "surface_m2": 5, "adjacente_a": ["salon", "cuisine", "chambre"],
             "sol": None, "murs": None, "complete": False, "meubles": [], "sans": []},
            {"nom": "salon", "fonction": "salon", "surface_m2": 24, "adjacente_a": ["entrée"], "sol": None,
             "murs": "platre_peint:vert_sauge", "complete": False,
             "meubles": [{"categorie": "canape", "nombre": 1, "relations": [["contre_mur", None]],
                          "materiaux": {"structure": "cuir"}}], "sans": []},
            {"nom": "cuisine", "fonction": "cuisine", "surface_m2": 11, "adjacente_a": ["entrée"], "sol": None,
             "murs": None, "complete": False, "meubles": [], "sans": []},
            {"nom": "chambre", "fonction": "chambre", "surface_m2": 13, "adjacente_a": ["entrée"], "sol": None,
             "murs": None, "complete": False, "meubles": [], "sans": []},
            {"nom": "salle d'eau", "fonction": "salle_d_eau", "surface_m2": 4, "adjacente_a": ["entrée"],
             "sol": None, "murs": None, "complete": False, "meubles": [], "sans": []},
        ]},
        "ville": None, "nature": None, "notes": [], "raison": "trois pièces autour d'une entrée",
    }
    brut.update(sur)
    return brut


DEMANDE = "un intérieur de maison réaliste avec salon cuisine chambre et un canapé"

VILLE = {"type_scene": "ville", "titre": "Ville", "style": {"texte": "moderne", "architecture": "moderne"},
         "interieur": None, "nature": None,
         "ville": {"taille_m": [800, 600], "trame": "grille", "zones": [{"type": "residentiel", "part": 60},
                                                                        {"type": "parc", "part": 20},
                                                                        {"type": "centre", "part": 20}],
                   "etages": None, "largeur_rues_m": 14, "riviere": False, "arbres_alignement": True,
                   "voitures": True, "style": "moderne"},
         "notes": [], "raison": ""}


def piece(programme, nom):
    return next(p for p in programme["interieur"]["pieces"] if p["nom"] == nom)


class TestProgramme(unittest.TestCase):
    def test_programme_valide_accepte_en_un_tour(self):
        faux = Faux(maison())
        p = prog.lire_programme(DEMANDE, interroger=faux)
        self.assertEqual(p["source"], "llm")
        self.assertEqual(p["schema"], prog.SCHEMA)
        self.assertEqual(len(faux.messages), 1)
        self.assertEqual(p["type_scene"], "interieur")
        self.assertIsNone(p["ville"])
        self.assertIsNone(p["nature"])
        self.assertEqual(piece(p, "salon")["murs"], "platre_peint:vert_sauge")
        # adjacences rendues symétriques
        self.assertIn("entrée", piece(p, "cuisine")["adjacente_a"])

    def test_cles_invalides_une_seule_correction_puis_acceptee(self):
        faux_brut = maison()
        faux_brut["interieur"]["pieces"][1]["fonction"] = "sejour"
        faux_brut["interieur"]["pieces"][2]["meubles"] = [{"categorie": "four", "nombre": 1, "relations": [],
                                                          "materiaux": {}}]
        faux = Faux(faux_brut, maison())
        p = prog.lire_programme(DEMANDE, interroger=faux)
        self.assertEqual(p["source"], "llm")
        self.assertEqual(len(faux.messages), 2)
        correction = faux.messages[1]
        self.assertIn("'sejour' n'est pas une FONCTION", correction)
        self.assertIn("'four' n'est pas une CATEGORIE", correction)
        self.assertEqual([t["tour"] for t in p["tours"]], [1, 2])
        self.assertTrue(p["tours"][0]["erreurs"])

    def test_cles_invalides_deux_fois_refus_avec_raisons(self):
        faux_brut = maison()
        faux_brut["interieur"]["pieces"][0]["sol"] = "lino"
        faux = Faux(faux_brut, faux_brut, maison())
        p = prog.lire_programme(DEMANDE, interroger=faux)
        self.assertEqual(p["source"], "indisponible")
        self.assertEqual(len(faux.messages), 2)        # une seule correction, jamais deux
        self.assertTrue(any("lino" in e for e in p["erreurs"]))
        self.assertIsNone(p["interieur"])
        self.assertIsNone(p["type_scene"])

    def test_loi_de_completude(self):
        p = prog.lire_programme(DEMANDE, interroger=Faux(maison()))
        salon = piece(p, "salon")
        cats = [m["categorie"] for m in salon["meubles"]]
        # le salon nomme un canapé et n'est pas marqué complet : seul le canapé, rien d'ajouté
        self.assertEqual(cats, ["canape"])
        self.assertFalse(salon["complete"])
        # la cuisine ne nomme aucun meuble : elle reçoit tout le mobilier typique de sa fonction
        cuisine = piece(p, "cuisine")
        self.assertTrue(cuisine["complete"])
        self.assertEqual([m["categorie"] for m in cuisine["meubles"]],
                         [c for c, _n, _r in voc.FONCTIONS_PIECES["cuisine"]["meubles_typiques"]])
        self.assertTrue(all(m["origine"] == "typique" for m in cuisine["meubles"]))

    def test_completude_demande_gagne_sur_nombre_et_materiaux(self):
        brut = maison()
        brut["interieur"]["complet"] = True
        brut["interieur"]["pieces"][1]["meubles"] = [
            {"categorie": "fauteuil", "nombre": 2, "relations": [], "materiaux": {"structure": "velours:bordeaux"}},
            {"categorie": "piano", "nombre": 1, "relations": [["contre_mur", None]], "materiaux": {}}]
        brut["interieur"]["pieces"][1]["sans"] = ["television"]
        brut["style"] = {"texte": None, "architecture": None}
        p = prog.lire_programme("un intérieur de maison complet avec deux fauteuils en velours et un piano, sans télévision",
                                interroger=Faux(brut))
        self.assertEqual(p["source"], "llm", p.get("erreurs"))
        salon = piece(p, "salon")
        par = {m["categorie"]: m for m in salon["meubles"]}
        typiques = {c for c, _n, _r in voc.FONCTIONS_PIECES["salon"]["meubles_typiques"]} - {"television"}
        self.assertTrue(typiques <= set(par))
        self.assertNotIn("television", par)
        self.assertEqual(par["fauteuil"]["nombre"], 2)
        self.assertEqual(par["fauteuil"]["materiaux"], {"structure": "velours:bordeaux"})
        self.assertEqual(par["fauteuil"]["origine"], "demande")
        # la relation typique est conservée quand la demande n'en donne pas
        self.assertEqual(par["fauteuil"]["relations"], [["autour_de", "table_basse"]])
        self.assertEqual(par["piano"]["origine"], "demande")
        self.assertEqual(par["canape"]["origine"], "typique")

    def test_meuble_nomme_absent_est_une_erreur(self):
        brut = maison()
        brut["interieur"]["pieces"][1]["meubles"] = []
        p = prog.lire_programme(DEMANDE.replace("un canapé", "un piano"), interroger=Faux(brut, brut))
        self.assertEqual(p["source"], "indisponible")
        self.assertTrue(any("« piano »" in e for e in p["erreurs"]))

    def test_piece_nommee_absente_est_une_erreur(self):
        p = prog.lire_programme(DEMANDE + " et une salle de bain", interroger=Faux(maison(), maison()))
        self.assertEqual(p["source"], "indisponible")
        self.assertTrue(any("salle de bain" in e for e in p["erreurs"]))

    def test_relation_cible_absente_ou_superflue(self):
        brut = maison()
        brut["interieur"]["pieces"][1]["meubles"][0]["relations"] = [["face_a", "piano"], ["contre_mur", "canape"]]
        ok, erreurs = prog.valider_programme(brut, DEMANDE)
        self.assertIsNone(ok)
        self.assertTrue(any("cible 'piano' absente" in e for e in erreurs))
        self.assertTrue(any("ne prend pas de cible" in e for e in erreurs))

    def test_connexite_et_jour(self):
        brut = maison()
        brut["interieur"]["pieces"][3]["adjacente_a"] = []
        brut["interieur"]["pieces"][0]["adjacente_a"] = ["salon", "cuisine", "garage"]
        _ok, erreurs = prog.valider_programme(brut, DEMANDE)
        self.assertTrue(any("non reliées" in e and "chambre" in e for e in erreurs))
        self.assertTrue(any("'garage'" in e for e in erreurs))
        aveugle = {"type_scene": "interieur", "titre": "wc", "style": {}, "ville": None, "nature": None,
                   "interieur": {"hauteur_plafond": 2.5, "pieces": [
                       {"nom": "wc", "fonction": "wc", "surface_m2": 2, "adjacente_a": [], "meubles": []}]}}
        _ok, erreurs = prog.valider_programme(aveugle, "des toilettes")
        self.assertTrue(any("fenêtre" in e for e in erreurs))

    def test_logement_sans_piece_d_eau_refuse(self):
        # sans sa salle d'eau, la maison du gabarit dort (chambre) et cuisine (cuisine) sans pouvoir se laver
        brut = maison()
        brut["interieur"]["pieces"].pop()
        _ok, erreurs = prog.valider_programme(brut, DEMANDE)
        self.assertTrue(any("pièce d'eau" in e for e in erreurs))
        _ok, erreurs = prog.valider_programme(maison(), DEMANDE)
        self.assertEqual(erreurs, [])

    def test_surface_ramenee_avec_note(self):
        brut = maison()
        brut["interieur"]["pieces"][2]["surface_m2"] = 80          # cuisine 7-20 m² : hors [3,5 ; 30]
        brut["interieur"]["pieces"][3]["surface_m2"] = 21          # dans la fourchette : intact
        p, erreurs = prog.valider_programme(brut, DEMANDE)
        self.assertEqual(erreurs, [])
        self.assertEqual(piece(p, "cuisine")["surface_m2"], 20.0)
        self.assertEqual(piece(p, "chambre")["surface_m2"], 21.0)
        self.assertTrue(any("cuisine" in n and "80" in n for n in p["notes"]))

    def test_normalisation_des_zones(self):
        p = prog.lire_programme("une ville moderne avec un parc", interroger=Faux(VILLE))
        self.assertEqual(p["source"], "llm", p.get("erreurs"))
        parts = {z["type"]: z["part"] for z in p["ville"]["zones"]}
        self.assertAlmostEqual(sum(parts.values()), 1.0, places=3)
        self.assertAlmostEqual(parts["residentiel"], 0.6, places=3)
        self.assertTrue(any("normalisées" in n for n in p["notes"]))
        sans_bati = copy.deepcopy(VILLE)
        sans_bati["ville"]["zones"] = [{"type": "parc", "part": 1}]
        _ok, erreurs = prog.valider_programme(sans_bati, "une ville moderne avec un parc")
        self.assertTrue(any("zone bâtie" in e for e in erreurs))

    def test_bornes_ville(self):
        brut = copy.deepcopy(VILLE)
        brut["ville"].update(taille_m=[50, 3000], largeur_rues_m=80, etages=[8, 3], trame="damier")
        _ok, erreurs = prog.valider_programme(brut, "une ville moderne")
        self.assertTrue(any("taille_m" in e for e in erreurs))
        self.assertTrue(any("largeur_rues_m" in e for e in erreurs))
        self.assertTrue(any("etages" in e for e in erreurs))
        self.assertTrue(any("TRAME" in e for e in erreurs))

    def test_copie_exacte_du_style(self):
        # accents et casse ignorés
        brut = copy.deepcopy(VILLE)
        brut["style"]["texte"] = "MODERNE"
        p, erreurs = prog.valider_programme(brut, "une ville modérne avec un parc")
        self.assertEqual(erreurs, [])
        self.assertEqual(p["style"]["texte"], "MODERNE")
        brut["style"]["texte"] = "contemporaine"
        _ok, erreurs = prog.valider_programme(brut, "une ville moderne avec un parc")
        self.assertTrue(any("mot pour mot" in e for e in erreurs))

    def test_coherence_type_section(self):
        brut = copy.deepcopy(VILLE)
        brut["type_scene"] = "nature"
        _ok, erreurs = prog.valider_programme(brut, "une ville moderne")
        self.assertTrue(any("section remplie est ville" in e for e in erreurs))
        deux = copy.deepcopy(VILLE)
        deux["nature"] = {"biome": "prairie", "relief": "plat", "taille_m": 200, "eau": "aucune"}
        _ok, erreurs = prog.valider_programme(deux, "une ville moderne")
        self.assertTrue(any("exactement une section" in e for e in erreurs))

    def test_nature(self):
        brut = {"type_scene": "nature", "titre": "Forêt", "style": {"texte": None, "architecture": None},
                "interieur": None, "ville": None,
                "nature": {"biome": "foret_de_coniferes", "relief": "montagneux", "taille_m": 600, "eau": "lac"},
                "notes": [], "raison": ""}
        p = prog.lire_programme("une forêt de conifères en montagne avec un lac", interroger=Faux(brut))
        self.assertEqual(p["source"], "llm")
        self.assertEqual(p["nature"]["eau"], "lac")
        brut["nature"]["biome"] = "taiga"
        _ok, erreurs = prog.valider_programme(brut, "une forêt")
        self.assertTrue(any("BIOME" in e for e in erreurs))

    def test_delai_depasse_donne_indisponible(self):
        faux = Faux(socket.timeout("timed out"))
        p = prog.lire_programme(DEMANDE, interroger=faux)
        self.assertEqual(p["source"], "indisponible")
        self.assertIn("timed out", p["raison"])
        self.assertEqual(len(faux.messages), 1)

    def test_json_invalide_donne_indisponible(self):
        faux = Faux("Voici la scène : un salon.", "{pas du json")
        p = prog.lire_programme(DEMANDE, interroger=faux)
        self.assertEqual(p["source"], "indisponible")
        self.assertEqual(len(faux.messages), 2)
        self.assertIn("la réponse n'est pas un objet JSON", p["erreurs"])

    def test_demande_vide(self):
        self.assertEqual(prog.lire_programme("  ", interroger=Faux())["source"], "indisponible")

    def test_consigne_liste_les_vocabulaires(self):
        c = prog.consigne()
        for table in (voc.FONCTIONS_PIECES, voc.RELATIONS, voc.MATERIAUX, voc.STYLES_ARCHI, voc.ZONES_VILLE,
                      voc.BIOMES, voc.RELIEFS):
            for cle in table:
                self.assertIn(cle, c)
        for cle, cat in voc.CATEGORIES.items():
            if not cat["exterieur"]:
                self.assertIn(cle + "[", c)


if __name__ == "__main__":
    unittest.main()
