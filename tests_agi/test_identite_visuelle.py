"""Identity dossier of named subjects, established by AGREEMENT between independent real pictures.

« Zig et Sharko en version réaliste : Zig la hyène qui court et Sharko le requin qui nage » (15/11/2026):
the delivered characters were wrong. Their appearance came from hard-coded dictionaries and text-only
FLUX renders; no real picture had been looked at and no agreement vote existed in the code.

Every network and model call is injected here. The pictures are drawn by the test (no protected image
is committed): each "character" is a body, a head, legs, a tail and stripes in its own colour, in a new
pose for every picture. The fake vision reads the identity from the body colour:
  - the fake DINOv2 returns the identity's base vector plus a per-picture deviation, with absolute
    similarities that overlap between identities (a tight character at ~0.86, a loose one at ~0.64,
    and 0.52 between two characters of the same "series") — only relative rules can work;
  - the fake CLIP gives the species of the identity a logit 10 above the others.
Invented names are used: nothing in the module may depend on who the subject is.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
import random
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
import identite_visuelle as iv  # noqa: E402

DIM = 48


def _vecteur(graine: str) -> np.ndarray:
    """Deterministic pseudo-random unit vector (independent of numpy's generators)."""
    brut = np.frombuffer(hashlib.shake_256(graine.encode()).digest(4 * DIM), dtype=np.uint32).astype(np.float64)
    v = brut / 2.0 ** 32 - 0.5
    return v / np.linalg.norm(v)


SERIE = _vecteur("serie")


@dataclass(frozen=True)
class Identite:
    cle: str
    couleur: tuple[int, int, int]
    espece: str
    serie: float          # weight of the direction shared by the characters of one "series"
    dispersion: float     # per-picture deviation: within-identity similarity ~ 1 / (1 + dispersion²)

    def base(self) -> np.ndarray:
        propre = _vecteur("identite:" + self.cle)
        propre = propre - (propre @ SERIE) * SERIE
        propre /= np.linalg.norm(propre)
        v = self.serie * SERIE + propre
        return v / np.linalg.norm(v)


NOUK = Identite("nouk", (176, 112, 48), "hyena", 1.6, 0.4)
PILOU = Identite("pilou", (96, 128, 176), "shark", 1.6, 0.75)
HYENE_REELLE = Identite("hyene-reelle", (208, 176, 112), "hyena", 0.0, 0.5)
INTRUS = [Identite(f"intrus-{k}", couleur, "hyena", 0.3, 0.3) for k, couleur in enumerate(
    [(48, 160, 80), (128, 48, 160), (40, 40, 40), (200, 200, 40), (40, 180, 180), (160, 40, 40)])]
REGISTRE = [NOUK, PILOU, HYENE_REELLE, *INTRUS]


def identite_de(image: Image.Image) -> Identite | None:
    """The identity whose colour is the most frequent non-white colour of the picture (the body)."""
    pixels = np.asarray(image.convert("RGB")).reshape(-1, 3)
    avant = pixels[pixels.min(axis=1) < 245]
    if not len(avant):
        return None
    q = (avant // 16).astype(np.int64)
    codes, comptes = np.unique(q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2], return_counts=True)
    code = int(codes[comptes.argmax()])
    rgb = np.array([code // 256, (code // 16) % 16, code % 16]) * 16 + 8
    return min(REGISTRE, key=lambda ident: float(np.sum((np.array(ident.couleur) - rgb) ** 2)))


def faux_embarquer(images: list) -> np.ndarray:
    lignes = []
    for image in images:
        ident = identite_de(image)
        base = ident.base()
        ecart = _vecteur("ecart:" + hashlib.sha1(image.tobytes()).hexdigest())
        ecart = ecart - (ecart @ base) * base
        ecart /= np.linalg.norm(ecart)
        v = base + ident.dispersion * ecart
        lignes.append(v / np.linalg.norm(v))
    return np.array(lignes)


def faux_scorer(images: list, textes: list) -> np.ndarray:
    scores = np.full((len(images), len(textes)), 20.0)
    for i, image in enumerate(images):
        ident = identite_de(image)
        for j, texte in enumerate(textes):
            if ident is not None and texte == ident.espece:
                scores[i, j] = 30.0
    return scores


def faux_decouper(image: Image.Image) -> Image.Image:
    """Background removal on the synthetic pictures: everything that is not white is the subject."""
    rgb = image.convert("RGB")
    alpha = (np.asarray(rgb).min(axis=2) < 245).astype(np.uint8) * 255
    sortie = rgb.convert("RGBA")
    sortie.putalpha(Image.fromarray(alpha))
    return sortie


def dessiner(dessin: ImageDraw.ImageDraw, ident: Identite, cx: float, cy: float, e: float,
             rng: random.Random) -> None:
    w, h = 70 * e * rng.uniform(0.85, 1.15), 44 * e * rng.uniform(0.85, 1.15)
    dessin.ellipse((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), fill=ident.couleur)
    cote = rng.choice((-1, 1))
    r = 20 * e * rng.uniform(0.85, 1.15)
    hx, hy = cx + cote * (w / 2 - 0.4 * r), cy - h / 2 - r * rng.uniform(0.2, 0.7)
    dessin.ellipse((hx - r, hy - r, hx + r, hy + r), fill=ident.couleur)
    for k in range(4):
        px = cx - w / 2 + w * (0.15 + 0.23 * k) + rng.uniform(-4, 4) * e
        dessin.rectangle((px - 4 * e, cy + h / 2 - 6 * e, px + 4 * e, cy + h / 2 + rng.uniform(14, 30) * e),
                         fill=ident.couleur)
    angle = rng.uniform(-1.0, 1.0)
    qx = cx - cote * w / 2
    dessin.line((qx, cy, qx - cote * 34 * e * math.cos(angle), cy - 34 * e * math.sin(angle)),
                fill=ident.couleur, width=max(3, int(6 * e)))
    sombre = tuple(int(c * 0.55) for c in ident.couleur)
    x = cx - 0.35 * w + rng.uniform(0, 10 * e)
    while x < cx + 0.35 * w:
        dessin.line((x, cy - h / 3, x + rng.uniform(-5, 5) * e, cy + h / 3), fill=sombre, width=max(2, int(3 * e)))
        x += rng.uniform(12, 22) * e


def photo(personnages: list[Identite], graine: int) -> Image.Image:
    """One picture: one character, or several side by side (a group picture), each in a new pose."""
    rng = random.Random(graine)
    taille = (320, 240) if len(personnages) == 1 else (200 * len(personnages), 240)
    image = Image.new("RGB", taille, (255, 255, 255))
    dessin = ImageDraw.Draw(image)
    for k, ident in enumerate(personnages):
        e = rng.uniform(1.35, 1.65) if len(personnages) == 1 else rng.uniform(1.0, 1.15)
        dessiner(dessin, ident, taille[0] * (k + 0.5) / len(personnages) + rng.uniform(-10, 10),
                 taille[1] * 0.5 + rng.uniform(-10, 10), e, rng)
    return image


class Monde:
    """A fake web: pictures published on domains, a search engine that returns them, a downloader."""

    def __init__(self) -> None:
        self.images: dict[str, Image.Image] = {}
        self.catalogue: list[dict] = []
        self.requetes: list[str] = []

    def publier(self, image: Image.Image, domaine: str) -> str:
        numero = len(self.catalogue)
        url = f"https://{domaine}/images/{numero}.png"
        self.images[url] = image
        self.catalogue.append({"imageUrl": url, "pageUrl": f"https://{domaine}/page/{numero}", "engine": "faux"})
        return url

    def chercher(self, requete: str, limite: int) -> list[dict]:
        self.requetes.append(requete)
        return list(self.catalogue)[:limite]

    def telecharger(self, url: str) -> Image.Image:
        return self.images[url].copy()


def contrat(*sujets: tuple[str, str, str]) -> dict:
    """A lecture-demande v2 contract from (name, French nature, English nature) triples."""
    lignes = []
    for nom, nature, nature_en in sujets:
        lignes.append({"nom": nom, "nomme": True, "nature": nature, "nature_en": nature_en,
                       "clause": f"{nom} {nature}", "mouvement": "", "mouvement_en": "",
                       "milieu": {"matiere": None, "relation": None, "justification": ""}})
    demande = " et ".join(f"{nom} {nature}" for nom, nature, _ in sujets)
    return {"schema": "aurora.lecture-demande.v2", "source": "llm", "demande": demande, "sujets": lignes,
            "style": {"texte": "", "cible": None, "justification": ""}}


DEUX_SUJETS = contrat(("Nouk", "une hyène", "hyena"), ("Pilou", "un requin", "shark"))


def etablir(monde: Monde, contrat_: dict, dossier: Path, journal: Path | None = None, **options) -> dict:
    return iv.etablir(contrat_, dossier / "cache", journal, chercher=monde.chercher, telecharger=monde.telecharger,
                      decouper=faux_decouper, embarquer=faux_embarquer, scorer_texte=faux_scorer, **options)


def sujet(dossier: dict, nom: str) -> dict:
    return next(s for s in dossier["sujets"] if s["nom"] == nom)


def publier_pilou(monde: Monde) -> list[str]:
    return [monde.publier(photo([PILOU], 100 + k), d)
            for k, d in enumerate(["e-mer.com", "f-wiki.org", "g-art.net", "e-mer.com", "h-fan.org"])]


class TestFakeWorldIsSound(unittest.TestCase):
    """The synthetic pictures must be distinct pictures, otherwise every test below proves nothing."""

    def test_different_poses_of_one_character_are_not_duplicates(self):
        signatures = [iv.signature_visuelle(photo([NOUK], g)) for g in range(1, 12)]
        for a in range(len(signatures)):
            for b in range(a + 1, len(signatures)):
                self.assertFalse(iv.sont_doublons(signatures[a], signatures[b]), (a, b))

    def test_fake_vision_has_overlapping_absolute_similarities(self):
        nouk = faux_embarquer([photo([NOUK], g) for g in range(1, 6)])
        pilou = faux_embarquer([photo([PILOU], g) for g in range(100, 105)])
        intra_nouk = (nouk @ nouk.T)[np.triu_indices(5, 1)]
        intra_pilou = (pilou @ pilou.T)[np.triu_indices(5, 1)]
        croise = (nouk @ pilou.T).ravel()
        self.assertGreater(intra_nouk.min(), 0.8)
        self.assertLess(intra_pilou.mean(), 0.7)
        # no absolute threshold separates "same character" from "same series": a cut at 0.6 refuses
        # most loose-character pairs, a cut at the cross level merges the two characters
        self.assertGreater(croise.max() + 0.08, intra_pilou.min())


class TestRequests(unittest.TestCase):
    EXEMPLE = {
        "schema": "aurora.lecture-demande.v2", "source": "llm",
        "demande": "Zig et Sharko en version réaliste : Zig la hyène qui court et Sharko le requin qui nage",
        "sujets": [
            {"nom": "Zig", "nomme": True, "nature": "une hyène", "nature_en": "hyena", "clause": "Zig la hyène qui court",
             "mouvement": "qui court", "mouvement_en": "a person runs forward",
             "milieu": {"matiere": "solide", "relation": "sur", "justification": "court"}},
            {"nom": "Sharko", "nomme": True, "nature": "un requin", "nature_en": "shark",
             "clause": "Sharko le requin qui nage", "mouvement": "qui nage", "mouvement_en": "a person swims",
             "milieu": {"matiere": "liquide", "relation": "immerge", "justification": "nage"}}],
        "style": {"texte": "version réaliste", "cible": "photo", "justification": "en version réaliste"}}

    def test_queries_are_made_only_of_the_contract_words(self):
        self.assertEqual(iv.construire_requetes(self.EXEMPLE, 0), ["Zig Sharko", "Zig hyena", "Zig une hyène"])
        self.assertEqual(iv.construire_requetes(self.EXEMPLE, 1), ["Sharko Zig", "Sharko shark", "Sharko un requin"])

    def test_a_lone_name_is_never_searched_alone(self):
        seul = contrat(("Nouk", "une hyène", "hyena"))
        self.assertEqual(iv.construire_requetes(seul, 0), ["Nouk hyena", "Nouk une hyène"])

    def test_unnamed_subjects_are_neither_searched_nor_used_as_context(self):
        c = contrat(("Nouk", "une hyène", "hyena"), ("x", "un chat", "cat"))
        c["sujets"][1].update({"nom": None, "nomme": False})
        self.assertEqual(iv.sujets_nommes(c), [0])
        self.assertEqual(iv.construire_requetes(c, 0), ["Nouk hyena", "Nouk une hyène"])

    def test_registrable_domain_counts_a_site_once(self):
        self.assertEqual(iv.domaine("https://fr.pinterest.com/pin/1"), "pinterest.com")
        self.assertEqual(iv.domaine("https://www.pinterest.com/pin/2"), "pinterest.com")
        self.assertEqual(iv.domaine("https://some-show.fandom.com/wiki/X"), "fandom.com")
        self.assertEqual(iv.domaine("https://www.bbc.co.uk/news"), "bbc.co.uk")


class TestPerceptualDuplicates(unittest.TestCase):
    def test_copies_resized_and_mirrored_are_duplicates(self):
        original = photo([NOUK], 7)
        signature = iv.signature_visuelle(original)
        reduite = original.resize((240, 180), Image.Resampling.LANCZOS)
        for copie in (original.copy(), reduite, original.transpose(Image.Transpose.FLIP_LEFT_RIGHT)):
            self.assertTrue(iv.sont_doublons(signature, iv.signature_visuelle(copie)))

    def test_two_characters_in_close_poses_are_not_duplicates(self):
        # same body plan, gradients within the dHash tolerance (measured 10 bits of 128): only colour differs
        a, b = photo([INTRUS[1]], 201), photo([INTRUS[4]], 204)
        sa, sb = iv.signature_visuelle(a), iv.signature_visuelle(b)
        self.assertLessEqual(iv.distance_empreintes(sa.directe, sb.directe), iv.PART_BITS_DOUBLON * sa.directe.size)
        self.assertFalse(iv.sont_doublons(sa, sb))

    def test_same_subject_on_white_canvases_of_another_size_is_compared_on_its_content(self):
        petit = photo([NOUK], 7)
        grand = Image.new("RGB", (640, 480), (255, 255, 255))
        grand.paste(petit, (160, 120))
        self.assertTrue(iv.sont_doublons(iv.signature_visuelle(petit), iv.signature_visuelle(grand)))


class TestComponents(unittest.TestCase):
    def test_two_separate_characters_become_two_cut_outs_and_specks_are_dropped(self):
        image = photo([NOUK, PILOU], 3)
        ImageDraw.Draw(image).rectangle((2, 2, 5, 5), fill=(0, 0, 0))
        decoupes = iv.decoupes_par_composantes(faux_decouper(image))
        self.assertEqual(len(decoupes), 2)
        self.assertEqual([identite_de(d["rgba"]) for d in decoupes], [NOUK, PILOU])
        for d in decoupes:
            self.assertEqual(d["rgba"].mode, "RGBA")
            self.assertGreaterEqual(d["part"], iv.PART_MIN_COMPOSANTE)


class TestAgreement(unittest.TestCase):
    def test_group_found_despite_intruders(self):
        monde = Monde()
        nouk = [monde.publier(photo([NOUK], g), d) for g, d in
                zip(range(1, 6), ["a-fan.com", "b-wiki.org", "c-news.net", "a-fan.com", "d-blog.fr"])]
        intrus = [monde.publier(photo([INTRUS[k]], 50 + k), d) for k, d in enumerate(["x.com", "y.com", "z.com"])]
        pilou = publier_pilou(monde)
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "journal"
            dossier = etablir(monde, DEUX_SUJETS, Path(tmp), journal)
            self.assertEqual(dossier["schema"], "aurora.identite-visuelle.v1")
            n = sujet(dossier, "Nouk")
            self.assertTrue(n["etabli"], n["raison"])
            self.assertEqual({r["source_url"] for r in n["retenues"]}, set(nouk))
            self.assertFalse({r["source_url"] for r in n["retenues"]} & set(intrus))
            self.assertEqual(len(n["ancres"]), 2)
            domaines_ancres = set()
            for chemin in n["ancres"]:
                self.assertTrue(Path(chemin).is_absolute() and Path(chemin).is_file())
                self.assertTrue(str(chemin).startswith(str((Path(tmp) / "cache" / "nouk").resolve())))
                with Image.open(chemin) as ancre:
                    self.assertEqual(ancre.mode, "RGBA")
                    self.assertEqual(identite_de(ancre), NOUK)
                    self.assertGreater(int((np.asarray(ancre)[..., 3] == 0).sum()), 0)  # transparent background
                domaines_ancres.add(next(r["domaine"] for r in n["retenues"]
                                         if Path(r["chemin"]).stem[:10] == Path(chemin).stem.rsplit("_", 1)[-1]))
            self.assertEqual(len(domaines_ancres), 2, "the second anchor comes from another domain")
            self.assertEqual(n["attributs"]["source"], "non_evalue")
            self.assertEqual(n["requetes"], ["Nouk Pilou", "Nouk hyena", "Nouk une hyène"])
            p = sujet(dossier, "Pilou")
            self.assertTrue(p["etabli"], p["raison"])
            # the loose character (~0.64 within) may lose a true picture that is nobody's MUTUAL neighbour
            # among four: the agreement is conservative, it never takes an intruder in exchange
            retenues_p = {r["source_url"] for r in p["retenues"]}
            self.assertTrue(retenues_p <= set(pilou))
            self.assertGreaterEqual(len(retenues_p), 3)
            # the search only ever received the contract's own queries
            self.assertEqual(sorted(set(monde.requetes)), sorted(n["requetes"] + p["requetes"]))
            ecrit = json.loads((journal / "identite.json").read_text(encoding="utf-8"))
            self.assertEqual(ecrit["schema"], "aurora.identite-visuelle.v1")
            for cle in ("requetes", "candidats", "telechargements", "decoupes", "votes", "ancres", "temps"):
                self.assertIn(cle, ecrit["journal"])
            self.assertIn("Nouk", ecrit["journal"]["votes"])
            with Image.open(journal / "planche_identite.png") as planche:
                self.assertGreater(planche.width, 100)

    def test_intruder_of_another_class_passing_clip_is_excluded_by_agreement(self):
        monde = Monde()
        nouk = [monde.publier(photo([NOUK], g), d) for g, d in
                zip(range(1, 6), ["a-fan.com", "b-wiki.org", "c-news.net", "a-fan.com", "d-blog.fr"])]
        # real hyena photos: CLIP says "hyena" too, and they even agree with EACH OTHER (3 pictures, 2 sites)
        reelles = [monde.publier(photo([HYENE_REELLE], 70 + k), d) for k, d in enumerate(["zoo.org", "safari.net", "zoo.org"])]
        publier_pilou(monde)
        with tempfile.TemporaryDirectory() as tmp:
            dossier = etablir(monde, DEUX_SUJETS, Path(tmp))
            n = sujet(dossier, "Nouk")
            self.assertTrue(n["etabli"], n["raison"])
            self.assertEqual({r["source_url"] for r in n["retenues"]}, set(nouk))
            self.assertFalse({r["source_url"] for r in n["retenues"]} & set(reelles))
            for chemin in n["ancres"]:
                with Image.open(chemin) as ancre:
                    self.assertEqual(identite_de(ancre), NOUK)

    def test_mirrors_count_once(self):
        monde = Monde()
        meme = photo([NOUK], 1)
        # one picture re-hosted on three sites plus a reduced copy on a fourth: ONE witness, not four
        for d in ("a-fan.com", "b-wiki.org", "c-news.net"):
            monde.publier(meme.copy(), d)
        monde.publier(meme.resize((256, 192), Image.Resampling.LANCZOS), "d-blog.fr")
        monde.publier(photo([NOUK], 2), "a-fan.com")
        publier_pilou(monde)
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "journal"
            dossier = etablir(monde, DEUX_SUJETS, Path(tmp), journal)
            n = sujet(dossier, "Nouk")
            self.assertFalse(n["etabli"])
            self.assertIn("2 découpe(s)", n["raison"])
            self.assertTrue(sujet(dossier, "Pilou")["etabli"])
            doublons = json.loads((journal / "identite.json").read_text(encoding="utf-8"))["journal"]["doublons_images"]
            self.assertEqual(sorted(len(d["copies"]) for d in doublons), [4])

    def test_group_picture_is_split_between_the_two_subjects(self):
        monde = Monde()
        for g, d in zip(range(1, 4), ["a-fan.com", "b-wiki.org", "c-news.net"]):
            monde.publier(photo([NOUK], g), d)
        for g, d in zip(range(100, 103), ["e-mer.com", "f-wiki.org", "g-art.net"]):
            monde.publier(photo([PILOU], g), d)
        groupe = monde.publier(photo([NOUK, PILOU], 9), "h-affiche.com")
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "journal"
            dossier = etablir(monde, DEUX_SUJETS, Path(tmp), journal)
            n, p = sujet(dossier, "Nouk"), sujet(dossier, "Pilou")
            self.assertTrue(n["etabli"], n["raison"])
            self.assertTrue(p["etabli"], p["raison"])
            de_groupe_n = [r for r in n["retenues"] if r["source_url"] == groupe]
            de_groupe_p = [r for r in p["retenues"] if r["source_url"] == groupe]
            self.assertEqual(len(de_groupe_n), 1)
            self.assertEqual(len(de_groupe_p), 1)
            self.assertNotEqual(de_groupe_n[0]["chemin"], de_groupe_p[0]["chemin"])
            with Image.open(de_groupe_n[0]["chemin"]) as a, Image.open(de_groupe_p[0]["chemin"]) as b:
                self.assertEqual((identite_de(a), identite_de(b)), (NOUK, PILOU))
            decoupes = json.loads((journal / "identite.json").read_text(encoding="utf-8"))["journal"]["decoupes"]
            self.assertEqual(sorted(d["sujet"] for d in decoupes if d["source_url"] == groupe), ["Nouk", "Pilou"])

    def test_no_agreement_means_not_established(self):
        monde = Monde()
        # six pictures, six different characters: each one is an intruder without a twin
        for k, d in enumerate(["a.com", "b.com", "c.com", "d.com", "e.com", "f.com"]):
            monde.publier(photo([INTRUS[k]], 200 + k), d)
        publier_pilou(monde)
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "journal"
            dossier = etablir(monde, DEUX_SUJETS, Path(tmp), journal)
            n = sujet(dossier, "Nouk")
            self.assertFalse(n["etabli"])
            self.assertEqual((n["ancres"], n["retenues"], n["domaines"]), ([], [], []))
            self.assertTrue(sujet(dossier, "Pilou")["etabli"])
            # the VOTE refuses (not a later clean-up): six distinct pictures, six distinct cut-outs
            vote = json.loads((journal / "identite.json").read_text(encoding="utf-8"))["journal"]["votes"]["Nouk"]
            self.assertEqual(len(vote["decoupes"]), 6)
            self.assertIsNone(vote["groupe"])
            self.assertEqual(n["raison"], vote["raison"])

    def test_no_agreement_for_a_lone_subject_either(self):
        monde = Monde()
        for k, d in enumerate(["a.com", "b.com", "c.com", "d.com", "e.com", "f.com"]):
            monde.publier(photo([INTRUS[k]], 200 + k), d)
        with tempfile.TemporaryDirectory() as tmp:
            n = sujet(etablir(monde, contrat(("Nouk", "une hyène", "hyena")), Path(tmp)), "Nouk")
        self.assertFalse(n["etabli"])
        self.assertTrue(n["raison"])

    def test_lone_subject_with_a_real_group_is_established(self):
        monde = Monde()
        nouk = [monde.publier(photo([NOUK], g), d) for g, d in
                zip(range(1, 6), ["a-fan.com", "b-wiki.org", "c-news.net", "a-fan.com", "d-blog.fr"])]
        for k, d in enumerate(["x.com", "y.com"]):
            monde.publier(photo([INTRUS[k]], 50 + k), d)
        with tempfile.TemporaryDirectory() as tmp:
            n = sujet(etablir(monde, contrat(("Nouk", "une hyène", "hyena")), Path(tmp)), "Nouk")
        self.assertTrue(n["etabli"], n["raison"])
        self.assertEqual({r["source_url"] for r in n["retenues"]}, set(nouk))

    def test_agreement_from_a_single_site_is_not_independent(self):
        monde = Monde()
        for g in range(1, 5):
            monde.publier(photo([NOUK], g), "a-fan.com")
        publier_pilou(monde)
        with tempfile.TemporaryDirectory() as tmp:
            n = sujet(etablir(monde, DEUX_SUJETS, Path(tmp)), "Nouk")
            self.assertFalse(n["etabli"])
            self.assertIn("domaine", n["raison"])


class TestVoteRules(unittest.TestCase):
    """The decision rules on hand-made similarity matrices."""

    @staticmethod
    def noeuds(domaines: list[str]) -> list[iv.Noeud]:
        return [iv.Noeud(id=f"n{k}", rgba=Image.new("RGBA", (4, 4)), image_id=f"img{k}", bbox=[0, 0, 4, 4], part=0.5,
                         bord=False, domaine=d, source_url=f"https://{d}/{k}", page="") for k, d in enumerate(domaines)]

    def test_equal_similarities_carry_no_agreement(self):
        noeuds = self.noeuds(["a", "b", "c", "d", "e"])
        vote = iv.voter(list(range(5)), noeuds, np.eye(5))
        self.assertIsNone(vote["groupe"])
        self.assertIn("aucun élément de comparaison", vote["raison"])

    def test_three_cut_outs_alone_cannot_vote_for_themselves(self):
        # three unrelated cut-outs of the subject, three background cut-outs even less related: with
        # k = n - 1 every cut-out would be everybody's neighbour and the triangle would "agree"
        noeuds = self.noeuds(["a", "b", "c", "x", "y", "z"])
        s = np.zeros((6, 6))
        s[0, 1] = s[1, 0] = 0.2
        s[0, 2] = s[2, 0] = 0.1
        s[1, 2] = s[2, 1] = 0.15
        for i in range(3):
            for j in range(3, 6):
                s[i, j] = s[j, i] = 0.01 * (i + j)
        np.fill_diagonal(s, 1.0)
        vote = iv.voter([0, 1, 2], noeuds, s)
        self.assertEqual(vote["k"], 1)
        self.assertIsNone(vote["groupe"])
        self.assertIn("aucun groupe", vote["raison"])  # refused by the selective graph itself

    def test_a_chance_chain_is_refused_against_the_non_twin_pairs(self):
        # six unrelated cut-outs with small random likeness: the mutual graph may chain some of them, but
        # their cohesion is no higher than the typical likeness of two cut-outs that are not twins
        noeuds = self.noeuds(["a", "b", "c", "d", "e", "f"])
        s = np.array([[1.0, 0.31, 0.12, 0.05, 0.22, 0.18],
                      [0.31, 1.0, 0.27, 0.08, 0.10, 0.16],
                      [0.12, 0.27, 1.0, 0.29, 0.07, 0.14],
                      [0.05, 0.08, 0.29, 1.0, 0.26, 0.09],
                      [0.22, 0.10, 0.07, 0.26, 1.0, 0.11],
                      [0.18, 0.16, 0.14, 0.09, 0.11, 1.0]])
        vote = iv.voter(list(range(6)), noeuds, s)
        self.assertIsNone(vote["groupe"])
        self.assertTrue(vote["tete"], "the graph did chain them: the test is about the second stage")
        self.assertIn("hasard", vote["raison"])

    def test_a_real_group_passes_against_the_non_twin_pairs(self):
        noeuds = self.noeuds(["a", "b", "c", "d", "e", "f"])
        s = np.full((6, 6), 0.3)
        s[np.ix_([0, 1, 2, 3], [0, 1, 2, 3])] = 0.75
        np.fill_diagonal(s, 1.0)
        vote = iv.voter(list(range(6)), noeuds, s)
        self.assertEqual(vote["groupe"], [0, 1, 2, 3])
        self.assertGreaterEqual(vote["silhouette"], iv.SILHOUETTE_MIN)

    def test_nothing_to_compare_with_is_not_an_agreement(self):
        noeuds = self.noeuds(["a", "b", "c", "d"])
        s = np.full((4, 4), 0.8)
        np.fill_diagonal(s, 1.0)
        s[0, 1] = s[1, 0] = 0.85
        s[2, 3] = s[3, 2] = 0.84
        s[1, 2] = s[2, 1] = 0.83
        vote = iv.voter(list(range(4)), noeuds, s)
        if vote["tete"] and len(vote["tete"]) == 4:
            self.assertIsNone(vote["groupe"])
            self.assertIn("aucun élément de comparaison", vote["raison"])

    def test_two_equally_supported_groups_are_ambiguous(self):
        noeuds = self.noeuds(["a", "b", "c", "d", "e", "f"])
        similarites = np.full((6, 6), 0.1)
        for groupe in ((0, 1, 2), (3, 4, 5)):
            for i in groupe:
                for j in groupe:
                    similarites[i, j] = 0.8
        np.fill_diagonal(similarites, 1.0)
        vote = iv.voter(list(range(6)), noeuds, similarites)
        self.assertIsNone(vote["groupe"])
        self.assertIn("ambigu", vote["raison"])

    def test_cut_out_closer_to_another_subjects_group_is_removed(self):
        noeuds = self.noeuds(["a", "b", "c", "d", "e", "f", "g"])
        s = np.full((7, 7), 0.2)
        for groupe in ((0, 1, 2, 3), (4, 5, 6)):
            for i in groupe:
                for j in groupe:
                    s[i, j] = 0.8
        s[3, :3] = s[:3, 3] = 0.45     # cut-out 3 joined A's group but looks more like B
        s[3, 4:] = s[4:, 3] = 0.7
        np.fill_diagonal(s, 1.0)
        journal = {"exclusions": []}
        groupes = iv._exclure_croisement({0: [0, 1, 2, 3], 1: [4, 5, 6]}, s, noeuds, DEUX_SUJETS, journal)
        self.assertEqual(groupes, {0: [0, 1, 2], 1: [4, 5, 6]})
        self.assertEqual(journal["exclusions"][0]["plus_proche_de"], "Pilou")

    def test_a_tight_group_keeps_its_members_next_to_a_loose_one(self):
        noeuds = self.noeuds(["a", "b", "c", "d", "e", "f"])
        s = np.full((6, 6), 0.545)
        s[np.ix_([0, 1, 2], [0, 1, 2])] = 0.86
        s[np.ix_([3, 4, 5], [3, 4, 5])] = 0.50
        np.fill_diagonal(s, 1.0)
        groupes = iv._exclure_croisement({0: [0, 1, 2], 1: [3, 4, 5]}, s, noeuds, DEUX_SUJETS, {"exclusions": []})
        self.assertEqual(groupes[0], [0, 1, 2])
        self.assertEqual(groupes[1], [])  # the loose group empties: refused, never mistaken for the other


class TestHonestFailures(unittest.TestCase):
    def monde(self) -> Monde:
        monde = Monde()
        for g, d in zip(range(1, 5), ["a-fan.com", "b-wiki.org", "c-news.net", "d-blog.fr"]):
            monde.publier(photo([NOUK], g), d)
        publier_pilou(monde)
        return monde

    def test_missing_local_model_is_reported_with_its_name(self):
        def absent(_images):
            raise RuntimeError("modèle local absent du cache Hugging Face : facebook/dinov2-base")

        monde = self.monde()
        with tempfile.TemporaryDirectory() as tmp:
            dossier = iv.etablir(DEUX_SUJETS, Path(tmp), None, chercher=monde.chercher,
                                 telecharger=monde.telecharger, decouper=faux_decouper,
                                 embarquer=absent, scorer_texte=faux_scorer)
        for s in dossier["sujets"]:
            self.assertFalse(s["etabli"])
            self.assertIn("facebook/dinov2-base", s["raison"])

    def test_no_search_result_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            dossier = iv.etablir(DEUX_SUJETS, Path(tmp), None, chercher=lambda q, n: [],
                                 telecharger=lambda u: None, decouper=faux_decouper,
                                 embarquer=faux_embarquer, scorer_texte=faux_scorer)
        self.assertTrue(all(not s["etabli"] and "aucune image" in s["raison"] for s in dossier["sujets"]))

    def test_vision_describes_only_from_the_anchors(self):
        appels = []

        def decrire(ancres, nature_en):
            appels.append((list(ancres), nature_en))
            return {"plan_du_corps": "quadrupède", "vetements": None, "couleurs": ["brun"], "style_origine": "dessin",
                    "invente": "ignoré"}

        monde = self.monde()
        with tempfile.TemporaryDirectory() as tmp:
            dossier = etablir(monde, DEUX_SUJETS, Path(tmp), decrire=decrire)
        n = sujet(dossier, "Nouk")
        self.assertEqual(n["attributs"], {"plan_du_corps": "quadrupède", "vetements": None, "couleurs": ["brun"],
                                          "style_origine": "dessin", "source": "vision"})
        self.assertIn((n["ancres"], "hyena"), appels)
        self.assertEqual(len(appels), 2)

    def test_mute_vision_is_not_evaluated_never_invented(self):
        def muette(_ancres, _nature):
            raise TimeoutError("vision indisponible")

        with tempfile.TemporaryDirectory() as tmp:
            dossier = etablir(self.monde(), DEUX_SUJETS, Path(tmp), decrire=muette)
        self.assertTrue(all(s["attributs"]["source"] == "non_evalue" for s in dossier["sujets"]))


class TestCli(unittest.TestCase):
    def test_prints_exactly_one_json_line(self):
        def faux_etablir(contrat_, cache, journal, **_):
            print("bavardage d'une bibliothèque")  # must not reach stdout
            return {"schema": iv.SCHEMA, "demande": contrat_["demande"], "sujets": [], "duree_s": 0.0}

        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "contrat.json"
            chemin.write_text(json.dumps(DEUX_SUJETS, ensure_ascii=False), encoding="utf-8")
            sortie, erreurs = io.StringIO(), io.StringIO()
            with mock.patch.object(iv, "etablir", faux_etablir), contextlib.redirect_stdout(sortie), \
                    contextlib.redirect_stderr(erreurs):
                code = iv.main(["--contrat", str(chemin), "--cache", str(Path(tmp) / "cache")])
        self.assertEqual(code, 0)
        lignes = sortie.getvalue().splitlines()
        self.assertEqual(len(lignes), 1)
        self.assertEqual(json.loads(lignes[0])["schema"], "aurora.identite-visuelle.v1")

    def test_unreadable_contract_is_one_json_error_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "contrat.json"
            chemin.write_text("{pas du json", encoding="utf-8")
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                code = iv.main(["--contrat", str(chemin), "--cache", str(Path(tmp) / "cache")])
        self.assertEqual(code, 2)
        self.assertIn("erreur", json.loads(sortie.getvalue()))


if __name__ == "__main__":
    unittest.main()
