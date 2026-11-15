"""Prompt de référence par identité : les pixels du dossier portent l'identité, le contrat le style.

Run du 15/11/2026, « Zig et Sharko en version réaliste : Zig la hyène qui court et Sharko le requin
qui nage » : l'identité venait de deux dictionnaires écrits en dur, et le même short rayé est
apparu sur les deux personnages (§ 1.38 : l'encodeur Mistral-3 dessine les mots du positif).
Les noms et les données ci-dessous sont inventés ; les ancres sont de petites images générées par
le test. Les clés des dictionnaires existants ne sont lues que pour vérifier que le prompt ne
dépend jamais d'un nom.
"""
from __future__ import annotations

import ast
import re
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "application" / "python-services"
sys.path.insert(0, str(SERVICES))
import reference_identite as ri  # noqa: E402

# Mots de vêtement que le positif ne doit JAMAIS contenir : liste du test, indépendante du lexique
# du module (sinon le test ne vérifierait que lui-même).
VETEMENT_RX = re.compile(r"\b(clothing|clothes|outfits?|shorts|garments?|trousers|shirts?|swimwear|swimsuit|"
                         r"wearing|vetements?|tenue)\b", re.I)


def reperes_de_repos() -> str:
    """REST_POSE_CUES du pipeline, lu dans sa source sans importer le pipeline (lourd)."""
    arbre = ast.parse((SERVICES / "aurora_3d_pipeline.py").read_text(encoding="utf-8"))
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign) and any(getattr(c, "id", None) == "REST_POSE_CUES" for c in noeud.targets):
            return ast.literal_eval(noeud.value)
    raise AssertionError("REST_POSE_CUES introuvable dans aurora_3d_pipeline.py")


REPOS = reperes_de_repos()


def sujet(nom, nature, nature_en, mouvement, *, nomme=True, matiere="solide", relation="sur"):
    return {"nom": nom, "nomme": nomme, "nature": nature, "nature_en": nature_en,
            "clause": " ".join(x for x in (nom, nature, mouvement) if x), "mouvement": mouvement,
            "mouvement_en": "a person moves", "milieu": {"matiere": matiere, "relation": relation,
                                                         "justification": mouvement}}


def contrat(*sujets, texte="version réaliste", cible="photo"):
    return {"schema": ri.SCHEMA_CONTRAT, "source": "llm", "demande": "demande gabarit", "sujets": list(sujets),
            "style": {"texte": texte, "cible": cible, "justification": texte}}


def entree(index, nom, nature_en, ancres, *, vetements="none", couleurs=("tan", "dark brown"),
           plan="upright biped with a long snout", origine="cel_2d", source="vision", etabli=True, raison=None):
    return {"index": index, "nom": nom, "nature_en": nature_en, "etabli": etabli, "raison": raison,
            "ancres": [str(a) for a in ancres], "retenues": [],
            "attributs": {"plan_du_corps": plan, "vetements": vetements, "couleurs": list(couleurs),
                          "style_origine": origine, "source": source},
            "requetes": [], "domaines": []}


def dossier(*entrees):
    return {"schema": ri.SCHEMA_DOSSIER, "demande": "demande gabarit", "sujets": list(entrees), "duree_s": 0.1}


class AvecAncres(unittest.TestCase):
    def setUp(self):
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.addCleanup(self._dossier.cleanup)

    def ancre(self, nom: str) -> Path:
        chemin = self.racine / nom
        chemin.parent.mkdir(parents=True, exist_ok=True)
        pixels = np.zeros((12, 8, 4), np.uint8)
        pixels[2:10, 2:6] = (120, 80, 40, 255)
        Image.fromarray(pixels, "RGBA").save(chemin)
        return chemin

    def duo(self, *, vetements=("none", "aucun vêtement"), origine="cel_2d", **style):
        """Deux sujets nommés inventés, une ancre chacun."""
        a, b = self.ancre("tavik/ancre_1.png"), self.ancre("morvo/ancre_1.png")
        c = contrat(sujet("Tavik", "une hyène", "hyena", "qui court"),
                    sujet("Morvo", "un requin", "shark", "qui nage", matiere="liquide", relation="immerge"), **style)
        d = dossier(entree(0, "Tavik", "hyena", [a], vetements=vetements[0], origine=origine),
                    entree(1, "Morvo", "shark", [b], vetements=vetements[1], couleurs=("blue-grey", "white belly"),
                           plan="muscular upright biped", origine=origine))
        return c, d, a, b

    def prompt(self, c, d, *, animation=True, **options):
        return ri.prompt_reference_identite(c, d, animation=animation, rest_pose_cues=REPOS, **options)


class LiaisonImageSujet(AvecAncres):
    def test_le_sujet_k_est_le_personnage_de_l_image_de_reference_k(self):
        c, d, a, b = self.duo()
        sortie = self.prompt(c, d)
        positif = sortie["positif"]
        self.assertIn("the character of reference image 1 (hyena)", positif)
        self.assertIn("the character of reference image 2 (shark)", positif)
        self.assertLess(positif.index("Character 1, the first from the left"),
                        positif.index("Character 2, the second from the left"))
        self.assertEqual(sortie["references"], [str(a), str(b)])
        self.assertEqual(sortie["roles"], ["reference image 1 shows character 1 (hyena)",
                                           "reference image 2 shows character 2 (shark)"])
        for role in sortie["roles"]:
            self.assertIn(role, positif)
        self.assertIn("image 1", sortie["convention"])
        self.assertIn("NON MESURÉ", sortie["convention"])

    def test_aucun_nom_n_est_ecrit_et_le_prompt_ne_depend_pas_du_nom(self):
        c, d, _, _ = self.duo()
        reference = self.prompt(c, d)
        for nom in ("Tavik", "Morvo"):
            self.assertNotIn(nom.lower(), reference["positif"].lower())
            self.assertNotIn(nom.lower(), reference["negatif"].lower())
        cles = cles_des_dictionnaires()
        # Tant qu'un dictionnaire existe, sa lecture doit en trouver les clés (le retrait des
        # dictionnaires, prévu au plan, laisse ce test valide avec les seuls noms inventés).
        if any("CANONICAL_CHARACTER_LORE" in p.read_text(encoding="utf-8") for p in SOURCES_DICTIONNAIRES):
            self.assertTrue(cles)
        for cle in cles + ["Quellbrin", "Ostra Vay"]:
            with self.subTest(cle=cle):
                c2, d2 = renommer(c, d, {"Tavik": cle})
                self.assertEqual(self.prompt(c2, d2)["positif"], reference["positif"])

    def test_n_sujets_entiers_cote_a_cote_separes_sur_la_meme_ligne_de_sol(self):
        a, b, e = self.ancre("a.png"), self.ancre("b.png"), self.ancre("e.png")
        c = contrat(sujet("Tavik", "une hyène", "hyena", "qui court"), sujet("Morvo", "un requin", "shark", "qui nage"),
                    sujet("Pelune", "un hibou", "owl", "qui vole"))
        d = dossier(entree(0, "Tavik", "hyena", [a]), entree(1, "Morvo", "shark", [b]), entree(2, "Pelune", "owl", [e]))
        sortie = self.prompt(c, d)
        positif = sortie["positif"]
        for attendu in ("Exactly three (3) separate full-body characters side by side", "complete from head to feet",
                        "clear empty gap", "not touching", "same ground line", "plain seamless neutral white background"):
            self.assertIn(attendu, positif)
        self.assertIn("characters touching each other", sortie["negatif"])
        self.assertEqual([t["position"] for t in sortie["sujets"]], [1, 2, 3])


class MotsDuPositif(AvecAncres):
    def test_le_positif_ne_contient_jamais_de_mot_de_vetement(self):
        a, b = self.ancre("a.png"), self.ancre("b.png")
        c = contrat(sujet("Tavik", "une hyène", "hyena", "qui court"), sujet("Morvo", "un requin", "shark", "qui nage"))
        for vetements in (("none", "none"), ("none", "striped swim shorts"), (None, "a red outfit")):
            with self.subTest(vetements=vetements):
                d = dossier(
                    entree(0, "Tavik", "hyena", [a], vetements=vetements[0],
                           couleurs=("tan", "red striped shorts", "blue outfit"), plan="upright biped wearing clothes"),
                    entree(1, "Morvo", "shark", [b], vetements=vetements[1], couleurs=("blue-grey", "white t-shirt")))
                sortie = self.prompt(c, d)
                self.assertIsNone(VETEMENT_RX.search(sortie["positif"]), sortie["positif"])
                # aucun attribut lu par la vision n'est recopié : ni vêtement, ni couleur, ni plan du corps
                for texte in ("red striped shorts", "blue outfit", "upright biped", "white t-shirt", "colours: tan",
                              "blue-grey"):
                    self.assertNotIn(texte, sortie["positif"])
                self.assertEqual([t["absence_de_vetement"] for t in sortie["sujets"]], [False, False])

    def test_aucune_absence_de_vetement_n_est_ecrite(self):
        # « aucun vêtement visible » peut vouloir dire « non observé » (ancre en buste) : l'écrire dévêtait
        # une personne réelle. L'identité passe par les pixels, le texte ne dit rien des vêtements.
        c, d, _, _ = self.duo()
        positif = self.prompt(c, d)["positif"]
        self.assertNotIn("bare", positif.lower())
        self.assertNotIn("naked", positif.lower())
        self.assertIsNone(VETEMENT_RX.search(positif))

    def test_aucun_attribut_du_dossier_n_est_recopie_en_texte(self):
        # un attribut écrit pour un sujet fuyait vers l'autre (le short sur les deux) : seuls les pixels portent l'identité
        c, d, _, _ = self.duo()
        d["sujets"][1]["attributs"]["plan_du_corps"] = "muscular upright biped, Morvo's dorsal fin"
        sortie = self.prompt(c, d)
        self.assertNotIn("morvo", sortie["positif"].lower())
        self.assertNotIn("body plan:", sortie["positif"])
        self.assertNotIn("colours:", sortie["positif"])

    def test_la_lecture_de_l_absence_ne_devine_rien(self):
        for texte in ("none", "None.", "aucun vêtement visible", "it wears nothing", "pas de vêtement", "nu", "no clothing"):
            self.assertTrue(ri.dit_l_absence_de_vetement(texte), texte)
        for texte in (None, "", "n/a", "no shorts", "striped swim shorts", "unknown", "only a scarf"):
            self.assertFalse(ri.dit_l_absence_de_vetement(texte), texte)


class Negatif(AvecAncres):
    def test_le_negatif_ne_retire_jamais_de_vetement(self):
        c, d, _, _ = self.duo()
        negatif = self.prompt(c, d)["negatif"]
        for mot in ("clothing", "shorts", "outfit"):
            self.assertNotIn(mot, negatif)

    def test_une_absence_n_entre_au_negatif_que_si_elle_vaut_pour_chaque_sujet(self):
        for vetements in (("none", "striped swim shorts"), ("none", None)):
            with self.subTest(vetements=vetements):
                c, d, _, _ = self.duo(vetements=vetements)
                sortie = self.prompt(c, d)
                self.assertNotIn("shorts", sortie["negatif"])
                self.assertNotIn("clothing", sortie["negatif"])
                self.assertFalse(sortie["decisions"]["absences"])
                self.assertIn("non ecrites", sortie["decisions"]["raison_absences"])
        # Un sujet non nommé n'a pas de dossier : ce qu'il porte n'est pas établi.
        b = self.ancre("b.png")
        c = contrat(sujet(None, "un homme", "man", "qui court", nomme=False), sujet("Morvo", "un requin", "shark", "qui nage"))
        d = dossier(entree(1, "Morvo", "shark", [b]))
        self.assertNotIn("clothing", self.prompt(c, d)["negatif"])

    def test_les_marques_du_medium_d_origine_seulement_quand_les_styles_different(self):
        marques = ("cartoon", "cel shading", "ink outlines", "flat 2D")
        c, d, _, _ = self.duo(cible="photo")
        sortie = self.prompt(c, d)
        for marque in marques:
            self.assertIn(marque, sortie["negatif"])
        self.assertEqual(sortie["decisions"]["marques_origine"], list(marques))
        for cible in ("cel_2d", None, "autre"):
            with self.subTest(cible=cible):
                c, d, _, _ = self.duo(cible=cible)
                negatif = self.prompt(c, d)["negatif"]
                for marque in marques:
                    self.assertNotIn(marque, negatif)
        c, d, _, _ = self.duo(origine=None)
        self.assertNotIn("cel shading", self.prompt(c, d)["negatif"])
        # Une figurine d'un personnage dessiné garde ses proportions « cartoon » : seules les marques
        # du médium plat sont niées.
        c, d, _, _ = self.duo(cible="figurine")
        negatif = self.prompt(c, d)["negatif"]
        self.assertIn("cel shading", negatif)
        self.assertNotIn("cartoon", negatif)

    def test_le_style_vient_du_contrat(self):
        c, d, _, _ = self.duo(cible="photo")
        positif = self.prompt(c, d)["positif"]
        self.assertIn("photorealistic", positif)
        self.assertIn("« version réaliste »", positif)
        self.assertIn("only the rendering medium changes", positif)


class Animation(AvecAncres):
    def test_l_animation_ajoute_les_reperes_de_pose_de_repos(self):
        c, d, _, _ = self.duo()
        anime = self.prompt(c, d, animation=True)["positif"]
        self.assertIn(REPOS.strip().rstrip("."), anime)
        self.assertNotIn("qui court", anime)
        statique = self.prompt(c, d, animation=False)["positif"]
        self.assertNotIn(REPOS.strip().rstrip("."), statique)
        self.assertIn("« qui court »", statique)
        with self.assertRaises(ValueError):
            ri.prompt_reference_identite(c, d, animation=True, rest_pose_cues="  ")


class Ancres(AvecAncres):
    def test_une_ancre_par_sujet_dans_l_ordre_quatre_au_plus(self):
        # une seule image par sujet : « image k = sujet k » reste exact
        trois = {nom: [self.ancre("%s/%d.png" % (nom, k)) for k in range(3)] for nom in "abcde"}
        deux_sujets = dossier(entree(1, "B", "x", trois["b"]), entree(0, "A", "x", trois["a"]))
        self.assertEqual(ri.choisir_ancres(deux_sujets), [str(trois["a"][0]), str(trois["b"][0])])
        trois_sujets = dossier(*(entree(i, n, "x", trois[n][:2]) for i, n in enumerate("abc")))
        self.assertEqual(ri.choisir_ancres(trois_sujets), [str(trois[n][0]) for n in "abc"])
        quatre_sujets = dossier(*(entree(i, n, "x", trois[n][:2]) for i, n in enumerate("abcd")))
        self.assertEqual(ri.choisir_ancres(quatre_sujets), [str(trois[n][0]) for n in "abcd"])
        with self.assertRaises(ValueError):
            ri.choisir_ancres(dossier(*(entree(i, n, "x", trois[n][:1]) for i, n in enumerate("abcde"))))

    def test_ancres_absentes_doublons_et_sujets_non_etablis_sont_ecartes(self):
        a = self.ancre("a.png")
        absente = self.racine / "absente.png"
        d = dossier(entree(0, "A", "x", [absente, a, a]), entree(1, "B", "x", [self.ancre("b.png")], etabli=False))
        self.assertEqual(ri.choisir_ancres(d), [str(a)])
        with self.assertRaises(ValueError):
            ri.choisir_ancres(dossier(entree(0, "A", "x", [a]), entree(1, "B", "x", [a])))


class SujetsSansIdentite(AvecAncres):
    def test_un_sujet_nomme_sans_identite_etablie_arrete_la_reference(self):
        c, d, a, _ = self.duo()
        d["sujets"][1].update(etabli=False, raison="aucun accord entre images independantes")
        with self.assertRaises(ri.IdentiteNonEtablie) as refus:
            self.prompt(c, d)
        self.assertEqual(refus.exception.sujets, [{"index": 1, "nom": "Morvo",
                                                   "raison": "aucun accord entre images independantes"}])
        accepte = self.prompt(c, d, accepter_non_etablis=True)
        self.assertEqual(accepte["references"], [str(a)])
        self.assertEqual([t["identite"] for t in accepte["sujets"]], ["etablie", "non_verifiee"])
        self.assertIn("Character 2, the second from the left: shark.", accepte["positif"])
        self.assertNotIn("reference image 2", accepte["positif"])

    def test_un_sujet_non_nomme_est_decrit_par_sa_seule_nature(self):
        b = self.ancre("b.png")
        c = contrat(sujet(None, "un homme", "man", "qui court", nomme=False), sujet("Morvo", "un requin", "shark", "qui nage"))
        sortie = self.prompt(c, dossier(entree(1, "Morvo", "shark", [b])))
        self.assertEqual(sortie["references"], [str(b)])
        self.assertEqual(sortie["roles"], ["reference image 1 shows character 2 (shark)"])
        self.assertIn("Character 1, the first from the left: man.", sortie["positif"])
        self.assertIn("Character 2, the second from the left: the character of reference image 1 (shark)",
                      sortie["positif"])

    def test_un_dossier_numerote_autrement_est_apparie_par_le_nom(self):
        c, d, a, b = self.duo()
        d["sujets"][0]["index"], d["sujets"][1]["index"] = 1, 2
        self.assertEqual(self.prompt(c, d)["references"], [str(a), str(b)])

    def test_contrats_et_dossiers_invalides_sont_refuses(self):
        c, d, _, _ = self.duo()
        for mauvais_contrat in (dict(c, schema="aurora.lecture-demande.v1"), dict(c, source="indisponible"),
                                dict(c, sujets=[])):
            with self.subTest(contrat=mauvais_contrat.get("schema")), self.assertRaises(ValueError):
                self.prompt(mauvais_contrat, d)
        doublon = dossier(dict(d["sujets"][0]), dict(d["sujets"][1], index=0))
        for mauvais_dossier in (dict(d, schema="autre"), doublon):
            with self.assertRaises(ValueError):
                self.prompt(c, mauvais_dossier)


SOURCES_DICTIONNAIRES = (ROOT / "agi_core" / "prompt_intelligence.py",
                         ROOT / "application" / "src" / "services" / "cognitivePromptDirector.ts")


def cles_des_dictionnaires() -> list[str]:
    """Clés des deux dictionnaires d'identité écrits en dur (lus ici, jamais importés par le module)."""
    python, typescript = (p.read_text(encoding="utf-8") if p.is_file() else "" for p in SOURCES_DICTIONNAIRES)
    cles: set[str] = set()
    for noeud in ast.walk(ast.parse(python)):
        cibles = noeud.targets if isinstance(noeud, ast.Assign) else [noeud.target] if isinstance(noeud, ast.AnnAssign) else []
        if any(getattr(c, "id", None) == "CANONICAL_CHARACTER_LORE" for c in cibles) and isinstance(noeud.value, ast.Dict):
            cles.update(k.value for k in noeud.value.keys if isinstance(k, ast.Constant))
    bloc = re.search(r"const CANONICAL_CHARACTER_LORE[^=]*=\s*\{(.*?)\n\}", typescript, re.S)
    if bloc:
        cles.update(a or b for a, b in re.findall(r"^\s{2}(?:'([^']+)'|([A-Za-z_]\w*))\s*:", bloc.group(1), re.M))
    return sorted(cles)


def renommer(c: dict, d: dict, noms: dict) -> tuple[dict, dict]:
    c2 = dict(c, sujets=[dict(s, nom=noms.get(s.get("nom"), s.get("nom"))) for s in c["sujets"]])
    d2 = dict(d, sujets=[dict(e, nom=noms.get(e.get("nom"), e.get("nom"))) for e in d["sujets"]])
    return c2, d2


if __name__ == "__main__":
    unittest.main()
