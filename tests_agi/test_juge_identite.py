"""Juge d'identité : une référence générée jugée contre de vraies ancres et contre la demande.

15/11/2026 — « Zig et Sharko en version réaliste » : FLUX a rendu une hyène tachetée réelle et un requin
générique portant le même short rayé, et la porte qualité a noté 100/100 parce qu'elle comparait le modèle
à cette référence synthétique elle-même. Ici, les modèles sont des faux injectés et les images sont
dessinées par le test (aucune image protégée dans le dépôt) : des sujets inventés, « Ari » (un disque) et
« Bru » (un bâton), dont la teinte, la forme et d'éventuelles rayures (le vêtement ajouté) se lisent dans
les pixels. Le faux juge de vision lit réellement ces pixels ; le faux plongement aussi.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
import juge_identite as ji  # noqa: E402

PALETTE = {"orange": (255, 140, 0), "bleu": (30, 90, 230), "violet": (150, 60, 200)}
JAUNE, ROUGE = (250, 220, 0), (220, 20, 20)
NATURES = {"disque": "un disque", "baton": "un bâton"}
TOUT_FAVORABLE = {"meme_personnage": True, "plan_du_corps_conforme": True, "vetement_ajoute": False,
                  "nature_conforme": True, "style_conforme": True}


# ── Images synthétiques ────────────────────────────────────────────────────────────────────────────
def dessiner(chemin, teinte, forme, *, rayures=False, echelle=1.0, decalage=(0, 0), nuance=0, taille=256):
    """Un sujet détouré (RGBA, fond transparent) : disque ou bâton, rayures jaune/rouge en option."""
    image = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    trace = ImageDraw.Draw(image)
    couleur = tuple(int(min(255, max(0, c + nuance))) for c in PALETTE[teinte]) + (255,)
    cx, cy = taille // 2 + decalage[0], taille // 2 + decalage[1]
    if forme == "disque":
        rayon = int(80 * echelle)
        trace.ellipse((cx - rayon, cy - rayon, cx + rayon, cy + rayon), fill=couleur)
    else:
        demi_l, demi_h = int(28 * echelle), int(110 * echelle)
        trace.rectangle((cx - demi_l, cy - demi_h, cx + demi_l, cy + demi_h), fill=couleur)
    if rayures:
        tableau = np.asarray(image).copy()
        corps = tableau[..., 3] > 0
        ys, _ = np.nonzero(corps)
        y0, y1 = int(ys.min()), int(ys.max())
        bande = np.zeros_like(corps)
        bande[y0 + (y1 - y0) * 3 // 5: y0 + (y1 - y0) * 4 // 5 + 1, :] = True
        colonnes = ((np.arange(tableau.shape[1]) // 6) % 2 == 0)[None, :]
        zone = corps & bande
        tableau[zone & colonnes] = JAUNE + (255,)
        tableau[zone & ~colonnes] = ROUGE + (255,)
        image = Image.fromarray(tableau, "RGBA")
    image.save(chemin)
    return str(chemin)


def lire(chemin):
    """Ce qu'un œil verrait : teinte du corps, forme (rapport hauteur/largeur), rayures."""
    tableau = np.asarray(Image.open(chemin).convert("RGBA"), dtype=np.float64)
    opaque = tableau[..., 3] > 128
    rgb = tableau[..., :3]
    rayure = opaque & ((np.linalg.norm(rgb - JAUNE, axis=-1) < 40) | (np.linalg.norm(rgb - ROUGE, axis=-1) < 40))
    moyenne = rgb[opaque & ~rayure].mean(axis=0)
    ys, xs = np.nonzero(opaque)
    rapport = (np.ptp(ys) + 1) / (np.ptp(xs) + 1)
    return {"teinte": min(PALETTE, key=lambda k: np.linalg.norm(moyenne - np.array(PALETTE[k]))),
            "forme": "baton" if rapport > 1.6 else "disque",
            "rayures": bool(rayure.sum() > 0.02 * opaque.sum())}


def faux_plongements(chemins):
    """Plongement « vu des pixels » : couleur moyenne (dominante) et forme. Non normalisé exprès : la
    normalisation L2 est l'affaire du juge."""
    vecteurs = []
    for chemin in chemins:
        tableau = np.asarray(Image.open(chemin).convert("RGBA"), dtype=np.float64)
        opaque = tableau[..., 3] > 128
        couleur = tableau[..., :3][opaque].mean(axis=0) / 255.0
        ys, xs = np.nonzero(opaque)
        hauteur, largeur = np.ptp(ys) + 1, np.ptp(xs) + 1
        vecteurs.append(np.concatenate([3.0 * couleur, [0.125 * hauteur / largeur,
                                                         0.5 * opaque.sum() / float(hauteur * largeur)]]))
    return np.array(vecteurs)


class FauxJuge:
    """Un « modèle de vision » qui lit les pixels : il compare le CANDIDAT (repéré dans la question) aux
    ANCRES ; le style des candidats, invisible dans ces dessins, lui est donné."""

    def __init__(self, style_candidats="photo", cible="photo", en_texte=False):
        self.style_ok = style_candidats == cible
        self.en_texte = en_texte
        self.appels = []

    def __call__(self, images, question):
        self.appels.append((list(images), question))
        position = int(re.search(r"Image (\d+) = CANDIDAT", question).group(1)) - 1
        candidat = lire(images[position])
        ancres = [lire(p) for i, p in enumerate(images) if i != position]
        reponse = {"nature_conforme": NATURES[candidat["forme"]] in question, "style_conforme": self.style_ok}
        if ancres:
            reponse["meme_personnage"] = all(a["teinte"] == candidat["teinte"] and a["forme"] == candidat["forme"]
                                             for a in ancres)
            reponse["plan_du_corps_conforme"] = all(a["forme"] == candidat["forme"] for a in ancres)
            reponse["vetement_ajoute"] = candidat["rayures"] and not any(a["rayures"] for a in ancres)
        return ("Voici mon avis : " + json.dumps(reponse)) if self.en_texte else reponse


class Contrariant:
    """Enveloppe un juge et renverse une réponse au PREMIER vote de chaque candidat (avis partagé)."""

    def __init__(self, juge, cle):
        self.juge, self.cle, self.vus = juge, cle, set()

    def __call__(self, images, question):
        reponse = dict(self.juge(images, question))
        position = int(re.search(r"Image (\d+) = CANDIDAT", question).group(1)) - 1
        if images[position] not in self.vus:
            self.vus.add(images[position])
            reponse[self.cle] = not reponse[self.cle]
        return reponse


def faux_decouper(specs):
    """Découpage factice : écrit une découpe par spécification, de gauche à droite."""
    appels = []

    def decouper(image, dossier, run_id):
        appels.append((image, dossier, run_id))
        sortie = Path(dossier)
        sortie.mkdir(parents=True, exist_ok=True)
        resultat = []
        for k, (teinte, forme, rayures) in enumerate(specs):
            chemin = dessiner(sortie / f"{run_id}_char{k}_ref.png", teinte, forme, rayures=rayures)
            resultat.append({"index": k, "ref_path": chemin})
        return resultat
    decouper.appels = appels
    return decouper


# ── Contrats ───────────────────────────────────────────────────────────────────────────────────────
DEMANDE = "Ari et Bru en version réaliste : Ari le disque qui roule et Bru le bâton qui nage"


def contrat(cible="photo", texte="version réaliste", sujets=None):
    sujets = sujets or [("Ari", "un disque", "disc", "solide", "sur"), ("Bru", "un bâton", "stick", "liquide", "immerge")]
    return {
        "schema": "aurora.lecture-demande.v2", "source": "llm", "demande": DEMANDE,
        "sujets": [{"nom": nom, "nomme": True, "nature": nature, "nature_en": nature_en,
                    "clause": f"{nom} {nature}", "mouvement": "", "mouvement_en": "",
                    "milieu": {"matiere": matiere, "relation": relation, "justification": ""}}
                   for nom, nature, nature_en, matiere, relation in sujets],
        "style": {"texte": texte, "cible": cible, "justification": texte},
        "sujet": DEMANDE, "sujet_en": "", "mouvement": "", "exemplaires": len(sujets),
        "corps_articule": True, "conception": False,
    }


class Atelier(unittest.TestCase):
    """Un dossier temporaire avec des ancres « réelles » pour Ari (disques orange) et Bru (bâtons bleus)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier_tmp = Path(self._tmp.name)
        self.cliquet = self.dossier_tmp / "judge_ratchet_identite.json"
        self.ancres = {
            "Ari": [dessiner(self.dossier_tmp / f"ari_{i}.png", "orange", "disque", echelle=e, decalage=d, nuance=n)
                    for i, (e, d, n) in enumerate([(1.0, (0, 0), 0), (0.85, (-12, 6), 12), (1.1, (9, -8), -10)])],
            "Bru": [dessiner(self.dossier_tmp / f"bru_{i}.png", "bleu", "baton", echelle=e, decalage=d, nuance=n)
                    for i, (e, d, n) in enumerate([(1.0, (0, 0), 0), (0.9, (14, 4), 10), (1.05, (-9, -5), -12)])],
        }
        self.image = self.dossier_tmp / "reference.png"
        Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(self.image)

    def tearDown(self):
        self._tmp.cleanup()

    def dossier(self, **remplacements):
        sujets = []
        for i, nom in enumerate(("Ari", "Bru")):
            entree = {"index": i, "nom": nom, "nature_en": ("disc", "stick")[i], "etabli": True, "raison": None,
                      "ancres": list(self.ancres[nom]),
                      "retenues": [{"chemin": a, "domaine": f"source{j}.example", "source_url": "", "score": 1.0}
                                   for j, a in enumerate(self.ancres[nom])],
                      "attributs": {"plan_du_corps": None, "vetements": None, "couleurs": [], "source": "non_evalue"},
                      "requetes": [], "domaines": []}
            entree.update(remplacements.get(nom, {}))
            sujets.append(entree)
        return {"schema": "aurora.identite-visuelle.v1", "demande": DEMANDE, "sujets": sujets, "duree_s": 0.0}

    def juger(self, specs_decoupes, voter, *, contrat_=None, dossier=None, **options):
        options.setdefault("chemin_cliquet", self.cliquet)
        options.setdefault("embarquer", faux_plongements)
        resultat = ji.juger_reference(self.image, dossier or self.dossier(), contrat_ or contrat(),
                                      decouper=faux_decouper(specs_decoupes), voter=voter,
                                      dossier_decoupes=self.dossier_tmp / "decoupes", run_id="essai", **options)
        json.dumps(resultat, allow_nan=False)        # le verdict s'écrit tel quel dans le journal
        return resultat


# ── Verdicts ───────────────────────────────────────────────────────────────────────────────────────
class Verdicts(Atelier):
    def test_bons_sujets_acceptes_avec_votes_decorreles(self):
        juge = FauxJuge()
        resultat = self.juger([("orange", "disque", False), ("bleu", "baton", False)], juge)
        self.assertEqual(resultat["schema"], "aurora.juge-identite.v1")
        self.assertEqual(resultat["verdict"], "accepte", resultat["raison"])
        self.assertIsNone(resultat["raison"])
        self.assertEqual(resultat["attribution"]["permutation"], [0, 1])
        self.assertEqual(resultat["seuils"]["source"], "cliquet")
        self.assertEqual((resultat["seuils"]["votes_requis"], resultat["seuils"]["marge_attribution_min"]), (2, 0.02))
        for sujet in resultat["sujets"]:
            self.assertEqual(sujet["statut"], "accepte")
            self.assertEqual(sujet["axes_refuses"], [])
            self.assertGreater(sujet["attribution"]["marge"], 0.02)
            self.assertTrue(Path(sujet["decoupe"]).is_file())
            # 2 votes unanimes sur 3 suffisent à la base du cliquet : le 3e ne changerait plus rien
            self.assertEqual(len(sujet["votes"]), 3)      # l'identité se juge à l'unanimité : trois votes
            self.assertEqual(set(sujet["axes"]), {"identite", "plan_du_corps", "vetement", "nature", "style"})
        for images, question in juge.appels:
            self.assertLessEqual(len(images), 4)
            self.assertIn("CANDIDAT", question)
        # décorrélation : le candidat ne reste pas à la même place d'un vote à l'autre
        places = [int(re.search(r"Image (\d+) = CANDIDAT", q).group(1)) for _, q in juge.appels[:2]]
        self.assertNotEqual(places[0], places[1])
        self.assertNotEqual(juge.appels[0][0], juge.appels[1][0])

    def test_reponse_texte_du_modele_lue(self):
        resultat = self.juger([("orange", "disque", False), ("bleu", "baton", False)], FauxJuge(en_texte=True))
        self.assertEqual(resultat["verdict"], "accepte", resultat["raison"])

    def test_sujets_inverses_refuses(self):
        # chaque identité est dessinée sur le corps de l'autre : teinte d'Ari sur un bâton, teinte de Bru sur un disque
        resultat = self.juger([("bleu", "disque", False), ("orange", "baton", False)], FauxJuge())
        self.assertEqual(resultat["verdict"], "refuse")
        self.assertEqual(resultat["attribution"]["permutation"], [1, 0])
        for sujet in resultat["sujets"]:
            self.assertEqual(sujet["statut"], "refuse")
            self.assertIn("identite", sujet["axes_refuses"])
            self.assertIn("plan_du_corps", sujet["axes_refuses"])
            self.assertIn("nature", sujet["axes_refuses"])
        ari = resultat["sujets"][0]
        self.assertTrue(any("doit être un disque" in r for r in ari["raisons"]), ari["raisons"])

    def test_ordre_gauche_droite_seul_accepte_et_attribution_transmise(self):
        # bons personnages, simplement placés dans l'autre ordre : l'attribution le dit, la suite s'en sert
        resultat = self.juger([("bleu", "baton", False), ("orange", "disque", False)], FauxJuge())
        self.assertEqual(resultat["verdict"], "accepte", resultat["raison"])
        self.assertEqual(resultat["attribution"]["permutation"], [1, 0])
        self.assertEqual(resultat["sujets"][0]["attribution"]["indice_decoupe"], 1)
        # sauf si le générateur avait reçu l'ordre de mention à respecter
        exige = self.juger([("bleu", "baton", False), ("orange", "disque", False)], FauxJuge(),
                           exiger_ordre_mention=True)
        self.assertEqual(exige["verdict"], "refuse")
        self.assertEqual(exige["axes_refuses"], ["attribution"])
        self.assertTrue(any("ordre de mention" in r for r in exige["sujets"][0]["raisons"]))

    def test_vetement_ajoute_refuse(self):
        resultat = self.juger([("orange", "disque", True), ("bleu", "baton", False)], FauxJuge())
        self.assertEqual(resultat["verdict"], "refuse")
        ari, bru = resultat["sujets"]
        self.assertEqual(ari["axes_refuses"], ["vetement"])
        self.assertTrue(any("vêtement ou accessoire absent des ancres" in r for r in ari["raisons"]))
        self.assertEqual(bru["statut"], "accepte")

    def test_les_corrections_ne_recopient_aucun_attribut_lu(self):
        # les raisons repartent dans la consigne du rendu suivant (« CORRECTIONS ») : « none » y devenait un
        # ordre de dévêtir, et un attribut d'un sujet fuyait vers l'autre
        lus = {"source": "vision", "couleurs": ["orange"], "plan_du_corps": "flat round disc-shaped body",
               "vetements": "none"}
        dossier = self.dossier(Ari={"attributs": lus})
        resultat = self.juger([("orange", "disque", True), ("bleu", "baton", False)], FauxJuge(), dossier=dossier)
        raisons = " ".join(resultat["sujets"][0]["raisons"])
        self.assertIn("vêtement ou accessoire absent des ancres", raisons)
        self.assertNotIn("(none)", raisons)
        self.assertNotIn("disc-shaped", raisons)
        self.assertEqual(resultat["axes_refuses"], ["vetement"])

    def test_dessin_anime_quand_le_contrat_veut_une_photo_refuse(self):
        juge = FauxJuge(style_candidats="cel_2d", cible="photo")
        resultat = self.juger([("orange", "disque", False), ("bleu", "baton", False)], juge)
        self.assertEqual(resultat["verdict"], "refuse")
        for sujet in resultat["sujets"]:
            self.assertEqual(sujet["axes_refuses"], ["style"])
            self.assertTrue(any("« version réaliste »" in r and "PHOTOGRAPHIE" in r for r in sujet["raisons"]))
        self.assertTrue(all("PHOTOGRAPHIE réaliste" in q for _, q in juge.appels))

    def test_juge_muet_ou_illisible_jamais_accepte(self):
        def plante(images, question):
            raise RuntimeError("Ollama injoignable")
        muets = {"vide": lambda i, q: "", "plantage": plante, "hors_contrat": lambda i, q: {"avis": "peut-être"},
                 "texte": lambda i, q: "oui", "rien": lambda i, q: None,
                 "ambigu": lambda i, q: {k: "peut-être" for k in TOUT_FAVORABLE}}
        for nom, voter in muets.items():
            with self.subTest(juge=nom):
                resultat = self.juger([("orange", "disque", False), ("bleu", "baton", False)], voter)
                self.assertEqual(resultat["verdict"], "indisponible")
                for sujet in resultat["sujets"]:
                    self.assertEqual(sujet["statut"], "indisponible")
                    self.assertEqual(len(sujet["votes"]), 3)
                    self.assertTrue(all(d["decision"] == "indisponible" for d in sujet["axes"].values()))
                    self.assertTrue(any("juge muet ou illisible" in r for r in sujet["raisons"]))

    def test_un_seul_vote_favorable_puis_silence_reste_indisponible(self):
        reponses = iter([TOUT_FAVORABLE, "", ""] * 2)
        resultat = self.juger([("orange", "disque", False), ("bleu", "baton", False)],
                              lambda images, question: next(reponses))
        self.assertEqual(resultat["verdict"], "indisponible")

    def test_attribution_ambigue_refusee_sans_appel_de_vision(self):
        juge = FauxJuge()
        resultat = self.juger([("violet", "disque", False), ("violet", "disque", False)], juge)
        self.assertEqual(resultat["verdict"], "refuse")
        self.assertEqual(resultat["axes_refuses"], ["attribution"])
        self.assertEqual(resultat["attribution"]["marge"], 0.0)
        self.assertEqual(juge.appels, [])
        self.assertTrue(all("attribution ambiguë" in s["raisons"][0] for s in resultat["sujets"]))

    def test_nombre_de_silhouettes_different_du_nombre_de_sujets_refuse(self):
        trois = self.juger([("orange", "disque", False), ("bleu", "baton", False), ("violet", "disque", False)],
                           FauxJuge())
        self.assertEqual((trois["verdict"], trois["axes_refuses"]), ("refuse", ["nombre"]))
        self.assertEqual(trois["nombre"], {"decoupes": 3, "sujets": 2})
        aucune = self.juger([], FauxJuge())
        self.assertEqual(aucune["axes_refuses"], ["nombre"])
        self.assertIn("seul corps", aucune["raison"])

    def test_un_seul_sujet_juge_sur_l_image_entiere(self):
        # le découpage ne rend rien pour un sujet seul : TRELLIS reconstruit l'image entière, on juge celle-là
        dessiner(self.image, "orange", "disque")
        dossier = self.dossier()
        dossier["sujets"] = dossier["sujets"][:1]
        un_sujet = contrat(sujets=[("Ari", "un disque", "disc", "solide", "sur")])
        resultat = self.juger([], FauxJuge(), contrat_=un_sujet, dossier=dossier,
                              embarquer=lambda chemins: self.fail("aucun plongement n'est utile pour un seul sujet"))
        self.assertEqual(resultat["verdict"], "accepte", resultat["raison"])
        self.assertEqual(resultat["sujets"][0]["decoupe"], str(self.image))

    def test_modele_de_plongement_absent_indisponible(self):
        def absent(chemins):
            raise ImportError("No module named 'modeles_locaux'")
        juge = FauxJuge()
        resultat = self.juger([("orange", "disque", False), ("bleu", "baton", False)], juge, embarquer=absent)
        self.assertEqual(resultat["verdict"], "indisponible")
        self.assertIn("modeles_locaux", resultat["raison"])
        self.assertEqual(juge.appels, [])

    def test_decoupage_qui_plante_indisponible(self):
        def plante(image, dossier, run_id):
            raise MemoryError("plus de mémoire")
        resultat = ji.juger_reference(self.image, self.dossier(), contrat(), decouper=plante,
                                      embarquer=faux_plongements, voter=FauxJuge(), chemin_cliquet=self.cliquet)
        self.assertEqual(resultat["verdict"], "indisponible")
        self.assertIn("MemoryError", resultat["raison"])

    def test_identite_non_etablie_jamais_acceptee(self):
        dossier = self.dossier(Bru={"etabli": False, "raison": "aucun accord entre sources", "ancres": []})
        resultat = self.juger([("orange", "disque", False), ("bleu", "baton", False)], FauxJuge(), dossier=dossier)
        self.assertEqual(resultat["verdict"], "indisponible")
        ari, bru = resultat["sujets"]
        self.assertEqual(ari["statut"], "accepte")
        self.assertEqual(bru["statut"], "indisponible")
        self.assertTrue(bru["attribution"]["determinee"])     # par élimination : la seule découpe restante
        self.assertTrue(any("non établie : aucun accord entre sources" in r for r in bru["raisons"]))
        self.assertEqual(set(bru["axes"]), {"nature", "style"})   # rien à comparer sans ancre

    def test_entrees_hors_contrat_indisponibles(self):
        cas = {
            "contrat_v1": ({**contrat(), "schema": "aurora.lecture-demande.v1"}, self.dossier()),
            "demande_non_lue": ({**contrat(), "source": "indisponible"}, self.dossier()),
            "dossier_absent": (contrat(), None),
            "autre_demande": (contrat(), {**self.dossier(), "demande": "un chat qui dort"}),
        }
        for nom, (le_contrat, le_dossier) in cas.items():
            with self.subTest(cas=nom):
                resultat = ji.juger_reference(self.image, le_dossier, le_contrat, decouper=faux_decouper([]),
                                              embarquer=faux_plongements, voter=FauxJuge(),
                                              chemin_cliquet=self.cliquet)
                self.assertEqual(resultat["verdict"], "indisponible")
                self.assertTrue(resultat["raison"])

    def test_meme_demande_autrement_ponctuee_reste_jugee(self):
        dossier = {**self.dossier(), "demande": DEMANDE.replace(" : ", ": ").upper()}
        resultat = self.juger([("orange", "disque", False), ("bleu", "baton", False)], FauxJuge(), dossier=dossier)
        self.assertEqual(resultat["verdict"], "accepte", resultat["raison"])

    def test_jamais_plus_de_quatre_images_meme_avec_cinq_ancres(self):
        cinq = [dessiner(self.dossier_tmp / f"ari_plus_{i}.png", "orange", "disque", echelle=0.8 + 0.07 * i)
                for i in range(5)]
        juge = FauxJuge()
        resultat = self.juger([("orange", "disque", False), ("bleu", "baton", False)], juge,
                              dossier=self.dossier(Ari={"ancres": cinq}), seuils=ji.seuils_au_pas(ji.PAS_SATURATION))
        self.assertEqual(resultat["verdict"], "accepte", resultat["raison"])
        appels_ari = [images for images, _ in juge.appels if any("ari_plus" in p for p in images)]
        self.assertEqual(len(appels_ari), 3)                  # unanimité au plafond : 3 votes
        self.assertTrue(all(len(images) <= 4 for images in appels_ari))
        self.assertGreater(len({frozenset(images) for images in appels_ari}), 1)   # les ancres tournent

    def test_vision_desactivee_ne_peut_pas_accepter(self):
        juge = FauxJuge()
        resultat = self.juger([("orange", "disque", False), ("bleu", "baton", False)], juge, vision=False)
        self.assertEqual(resultat["verdict"], "indisponible")
        self.assertEqual(juge.appels, [])
        self.assertEqual(resultat["attribution"]["permutation"], [0, 1])


# ── Le cliquet de la famille « identité » ──────────────────────────────────────────────────────────
class Cliquet(Atelier):
    def test_niveau_strictement_croissant_et_seuils_bornes(self):
        etats = [ji.cliquet_identite(chemin=self.cliquet)]
        etats += [ji.cliquet_identite(avancer=True, chemin=self.cliquet) for _ in range(ji.PAS_SATURATION + 4)]
        niveaux = [e["ratchet_level"] for e in etats]
        self.assertTrue(all(b == a + 1 for a, b in zip(niveaux, niveaux[1:])), niveaux)
        self.assertEqual(etats[0]["pas"], 0)
        fractions = [e["seuils"]["fraction_votes"] for e in etats]
        marges = [e["seuils"]["marge_attribution_min"] for e in etats]
        self.assertEqual(fractions, sorted(fractions))           # jamais de relâchement
        self.assertEqual(marges, sorted(marges))
        self.assertTrue(all(2 / 3 - 1e-12 <= f <= 1.0 for f in fractions))
        self.assertTrue(all(0.02 - 1e-12 <= m <= 0.08 + 1e-12 for m in marges))
        self.assertAlmostEqual(marges[0], 0.02)
        self.assertAlmostEqual(marges[-1], 0.08)
        requis = [ji.votes_requis(f, 3) for f in fractions]
        self.assertEqual((requis[0], requis[-1]), (2, 3))     # 2/3 → 3/3
        self.assertEqual(requis, sorted(requis))
        self.assertEqual(json.loads(self.cliquet.read_text())["ratchet_level"], niveaux[-1])

    def test_ne_lit_jamais_l_etat_global_sature(self):
        globale = self.dossier_tmp / "judge_ratchet_state.json"
        globale.write_text(json.dumps({"ratchet_level": 878, "history_runs": 803}))
        (self.dossier_tmp / "representative_judge_report.json").write_text(
            json.dumps({"progressive_judge_ratchet": {"ratchet_level": 900, "history_runs": 900}}))
        with mock.patch("agi_core.judge_ratchet.DEFAULT_STATE", globale):
            etat = ji.cliquet_identite(chemin=self.cliquet)
            self.assertEqual((etat["pas"], etat["seuils"]["marge_attribution_min"]), (0, 0.02))
            with self.assertRaises(ValueError):
                ji.cliquet_identite(chemin=globale)
        self.assertEqual(json.loads(globale.read_text())["ratchet_level"], 878)

    def test_seul_un_tour_accepte_fait_avancer(self):
        depart = ji.cliquet_identite(chemin=self.cliquet)["ratchet_level"]
        refus = self.juger([("orange", "disque", True), ("bleu", "baton", False)], FauxJuge())
        self.assertFalse(ji.avancer_cliquet(refus, chemin=self.cliquet)["avance"])
        self.assertFalse(ji.avancer_cliquet({"verdict": "accepte"}, chemin=self.cliquet)["avance"])
        self.assertEqual(ji.cliquet_identite(chemin=self.cliquet)["ratchet_level"], depart)
        accepte = self.juger([("orange", "disque", False), ("bleu", "baton", False)], FauxJuge())
        etat = ji.avancer_cliquet(accepte, chemin=self.cliquet)
        self.assertTrue(etat["avance"])
        self.assertEqual(etat["ratchet_level"], depart + 1)

    def test_le_cliquet_durcit_vraiment_le_juge(self):
        specs = [("orange", "disque", False), ("bleu", "baton", False)]
        # un vote sur trois doute du plan du corps : la majorité des 2/3 accepte à la base…
        base = self.juger(specs, Contrariant(FauxJuge(), "plan_du_corps_conforme"))
        self.assertEqual(base["verdict"], "accepte", base["raison"])
        self.assertTrue(all(len(s["votes"]) == 3 for s in base["sujets"]))
        # …l'unanimité exigée au plafond refuse
        plafond = self.juger(specs, Contrariant(FauxJuge(), "plan_du_corps_conforme"),
                             seuils=ji.seuils_au_pas(ji.PAS_SATURATION))
        self.assertEqual(plafond["verdict"], "refuse")
        self.assertEqual(plafond["axes_refuses"], ["plan_du_corps"])
        self.assertEqual(plafond["seuils"]["votes_requis"], 3)

    def test_un_seul_doute_sur_l_identite_refuse_des_la_base(self):
        # essai réel du 15/11/2026 : une hyène générique acceptée par 2 votes contre 1 sur « même personnage »
        base = self.juger([("orange", "disque", False), ("bleu", "baton", False)],
                          Contrariant(FauxJuge(), "meme_personnage"))
        self.assertEqual(base["seuils"]["votes_requis"], 2)          # le cliquet est à sa base…
        self.assertEqual(base["verdict"], "refuse")                  # …et l'identité refuse quand même
        self.assertEqual(base["axes_refuses"], ["identite"])
        self.assertEqual(base["seuils"]["axes_unanimes"], ["identite"])

    def test_seuils_injectes_ramenes_dans_les_bornes(self):
        lache = self.juger([("violet", "disque", False), ("violet", "disque", False)], FauxJuge(),
                           seuils={"fraction_votes": 0.1, "marge_attribution_min": 0.0})
        self.assertEqual((lache["seuils"]["votes_requis"], lache["seuils"]["marge_attribution_min"]), (2, 0.02))
        self.assertEqual(lache["axes_refuses"], ["attribution"])      # une marge nulle reste un refus
        excessif = self.juger([("orange", "disque", False), ("bleu", "baton", False)], FauxJuge(),
                              seuils={"fraction_votes": 5.0, "marge_attribution_min": 3.0})
        self.assertEqual((excessif["seuils"]["votes_requis"], excessif["seuils"]["marge_attribution_min"]), (3, 0.08))

    def test_cliquet_illisible_jamais_relache(self):
        self.cliquet.write_text("{casse")
        resultat = self.juger([("orange", "disque", False), ("bleu", "baton", False)], FauxJuge())
        self.assertTrue(resultat["seuils"]["source"].startswith("plafond"))
        self.assertEqual((resultat["seuils"]["votes_requis"], resultat["seuils"]["marge_attribution_min"]), (3, 0.08))
        self.assertEqual(self.cliquet.read_text(), "{casse")   # conservé pour inspection, jamais remis à zéro


# ── Attribution et modèle livré ────────────────────────────────────────────────────────────────────
class Attribution(unittest.TestCase):
    def test_marges_par_sujet_et_sujet_sans_ancre_par_elimination(self):
        sim = np.array([[0.9, 0.2, np.nan], [0.1, 0.8, np.nan], [0.3, 0.3, np.nan]])
        attribution = ji.attribuer(sim)
        self.assertEqual(attribution["permutation"], [0, 1, 2])
        marges = [s["marge"] for s in attribution["sujets"]]
        self.assertAlmostEqual(marges[0], 0.30)
        self.assertAlmostEqual(marges[1], 0.25)
        self.assertAlmostEqual(marges[2], 0.25)
        self.assertAlmostEqual(attribution["marge"], 0.25)       # meilleure (0,85) − seconde (0,60)
        self.assertTrue(attribution["sujets"][2]["determinee"])

    def test_deux_sujets_sans_ancre_ne_sont_pas_departages(self):
        attribution = ji.attribuer(np.array([[0.9, np.nan, np.nan], [0.1, np.nan, np.nan], [0.2, np.nan, np.nan]]))
        self.assertEqual(attribution["permutation"], [0, None, None])
        self.assertEqual([s["determinee"] for s in attribution["sujets"]], [True, False, False])
        self.assertAlmostEqual(attribution["sujets"][0]["marge"], 0.7)


class ModeleLivre(Atelier):
    def rendus(self, teintes_formes):
        rendus = {}
        for s, (teinte, forme) in enumerate(teintes_formes):
            rendus[s] = [dessiner(self.dossier_tmp / f"rendu_{s}_{vue}.png", teinte, forme, echelle=e)
                         for vue, e in (("face", 1.0), ("profil", 0.9))]
        return rendus

    def test_personnages_livres_acceptes(self):
        juge = FauxJuge()
        resultat = ji.juger_modele(self.rendus([("orange", "disque"), ("bleu", "baton")]), self.dossier(), contrat(),
                                   embarquer=faux_plongements, voter=juge, chemin_cliquet=self.cliquet)
        json.dumps(resultat, allow_nan=False)
        self.assertEqual(resultat["verdict"], "accepte", resultat["raison"])
        self.assertEqual(resultat["mode"], "modele")
        self.assertTrue(all(len(s["rendus"]) == 2 for s in resultat["sujets"]))
        self.assertTrue(all("rendu 3D" in q for _, q in juge.appels))
        # les deux vues servent tour à tour de candidat
        candidats = {images[int(re.search(r"Image (\d+) = CANDIDAT", q).group(1)) - 1] for images, q in juge.appels}
        self.assertEqual(len(candidats), 4)

    def test_personnages_echanges_refuses(self):
        juge = FauxJuge()
        resultat = ji.juger_modele(self.rendus([("bleu", "baton"), ("orange", "disque")]), self.dossier(), contrat(),
                                   embarquer=faux_plongements, voter=juge, chemin_cliquet=self.cliquet)
        self.assertEqual(resultat["verdict"], "refuse")
        self.assertEqual(resultat["axes_refuses"], ["attribution"])
        self.assertIn("ressemble davantage aux ancres de Bru", resultat["sujets"][0]["raisons"][0])
        self.assertEqual(juge.appels, [])

    def test_sujet_sans_personnage_livre_refuse(self):
        rendus = self.rendus([("orange", "disque"), ("bleu", "baton")])
        del rendus[1]
        resultat = ji.juger_modele(rendus, self.dossier(), contrat(), embarquer=faux_plongements, voter=FauxJuge(),
                                   chemin_cliquet=self.cliquet)
        self.assertEqual((resultat["verdict"], resultat["axes_refuses"]), ("refuse", ["nombre"]))
        self.assertIn("Bru", resultat["raison"])


# ── Branchements par défaut (sans aucun appel réseau ni modèle réel) ───────────────────────────────
class Branchements(Atelier):
    def test_decoupage_par_defaut_est_celui_de_trellis(self):
        # deux sujets séparés par un écart net sur une même ligne de sol
        scene = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        trace = ImageDraw.Draw(scene)
        trace.ellipse((90, 280, 490, 680), fill=PALETTE["orange"] + (255,))
        trace.rectangle((660, 160, 820, 880), fill=PALETTE["bleu"] + (255,))
        scene.save(self.image)
        decoupes = self.dossier_tmp / "decoupes_trellis"
        resultat = ji.juger_reference(self.image, self.dossier(), contrat(), embarquer=faux_plongements,
                                      voter=FauxJuge(), chemin_cliquet=self.cliquet, dossier_decoupes=decoupes,
                                      run_id="scene")
        self.assertEqual(resultat["nombre"], {"decoupes": 2, "sujets": 2})
        self.assertEqual(resultat["verdict"], "accepte", resultat["raison"])
        self.assertEqual([Path(s["decoupe"]).name for s in resultat["sujets"]],
                         ["scene_char0_ref.png", "scene_char1_ref.png"])
        self.assertTrue(all(Path(s["decoupe"]).parent == decoupes for s in resultat["sujets"]))

    def test_juge_par_defaut_branche_sur_vlm_judge_sans_reseau(self):
        import vlm_judge
        maquette = self.dossier_tmp / "maquette_vlm.json"
        maquette.write_text(json.dumps({"default": TOUT_FAVORABLE}))
        with mock.patch.dict(os.environ, {"AURORA_VLM_MOCK": str(maquette)}), \
                mock.patch.object(vlm_judge, "_chat", side_effect=AssertionError("aucun appel réseau en test")):
            resultat = self.juger([("orange", "disque", False), ("bleu", "baton", False)], None)
        self.assertEqual(resultat["verdict"], "accepte", resultat["raison"])

    def test_ligne_de_commande_sans_vision(self):
        dessiner(self.image, "orange", "disque")
        dossier = self.dossier()
        dossier["sujets"] = dossier["sujets"][:1]
        chemins = {"dossier": self.dossier_tmp / "identite.json", "contrat": self.dossier_tmp / "contrat.json",
                   "sortie": self.dossier_tmp / "journal" / "identite_verdicts.json"}
        chemins["dossier"].write_text(json.dumps(dossier))
        chemins["contrat"].write_text(json.dumps(contrat(sujets=[("Ari", "un disque", "disc", "solide", "sur")])))
        with mock.patch.object(ji, "CHEMIN_CLIQUET", self.dossier_tmp / "jamais_lu.json"), \
                mock.patch("builtins.print") as imprime:
            code = ji.main(["--image", str(self.image), "--dossier", str(chemins["dossier"]),
                            "--contrat", str(chemins["contrat"]), "--decoupes", str(self.dossier_tmp / "d"),
                            "--sans-vision", "--cliquet", str(self.cliquet), "--sortie", str(chemins["sortie"])])
        self.assertEqual(code, 0)
        ligne = json.loads(imprime.call_args[0][0])
        self.assertEqual(ligne["verdict"], "indisponible")
        self.assertIn("vision désactivée", ligne["raison"])
        self.assertEqual(ligne["seuils"]["chemin_cliquet"], str(self.cliquet))
        self.assertEqual(json.loads(chemins["sortie"].read_text())["verdict"], "indisponible")


if __name__ == "__main__":
    unittest.main()
