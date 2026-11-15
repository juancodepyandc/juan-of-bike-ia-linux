#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dossier d'identité des sujets nommés, établi par ACCORD d'images réelles indépendantes.

LOI. L'identité d'un sujet nommé est le groupe d'images réelles, venues de sources indépendantes,
qui se ressemblent entre elles : un intrus n'a pas de jumeau. Aucune mémoire de modèle de langage,
aucun dictionnaire de noms, aucune liste de mots : les requêtes ne sont faites que des mots du contrat
de demande, et la décision ne repose que sur des comparaisons RELATIVES entre images.

Pourquoi (run du 15/11/2026, « Zig et Sharko en version réaliste : Zig la hyène qui court et Sharko le
requin qui nage ») : les personnages livrés étaient faux. Leur apparence venait de dictionnaires écrits
en dur et de FLUX nourri au texte seul ; aucune vraie image n'avait été regardée, aucun vote d'accord
n'existait dans le code. Ce module produit la preuve visuelle que les étapes suivantes (référence
conditionnée, juge d'identité) consomment.

Chaîne, pour chaque sujet `nomme=true` du contrat `aurora.lecture-demande.v2` :
  1. Requêtes : « {nom} {autres noms} », « {nom} {nature_en} », « {nom} {nature} ». Rien d'autre.
  2. Recherche Bing Images d'abord (`reference_visual_search.search_bing_images`, 1,7-3,3 s mesurées
     par requête) ; quand Bing rend moins que demandé, les fournisseurs d'images de `crawl4ai_search`
     (Wikimedia, Openverse) complètent — simples candidats soumis au MÊME vote (mesuré le 04/09 :
     Wikimedia apparie sur le seul nom, 0 pertinent sur 8). `search_via_crawl4ai` n'est PAS appelé :
     sans l'ancienne API `WebCrawler` (absente de ce venv, vérifié le 15/11), son sous-processus lance
     `pip install crawl4ai[sync]` puis `playwright install chromium`, et le délai de 25 s ne tue que
     l'enfant direct — l'installation continuerait dans le venv partagé.
  3. Téléchargement (`download_image`, au plus `max_par_sujet` images par sujet ; la miniature Bing
     sert de second essai). Fusion des doublons par empreinte perceptuelle dHash (et son miroir) :
     un miroir compte une fois. Une source = un domaine : un domaine compte une fois dans le vote.
  4. Détourage BiRefNet (`birefnet-general` via rembg, comme `photo_rectifier.py`), forcé sur CPU,
     puis composantes connexes : plusieurs personnages sur une image deviennent des découpes séparées
     (on garde les composantes d'au moins 4 % de l'image). Les découpes identiques d'images
     différentes (le même dessin officiel recollé sur plusieurs affiches) fusionnent aussi.
  5. Qui est qui : CLIP texte-image sur les `nature_en` du contrat ; une découpe va à la nature
     la plus probable seulement si elle est au moins deux fois plus probable que la suivante.
  6. Accord : graphe des k plus proches voisins MUTUELS des empreintes DINOv2 parmi les découpes du
     sujet ; on garde la composante soutenue par le plus de domaines (≥ 3 découpes, ≥ 2 domaines),
     strictement plus soutenue que la suivante, et dont la cohésion dépasse le fond de plus de deux
     écarts-types de ce fond (sinon ce sont des voisins de hasard). Une découpe plus proche, en
     moyenne, du groupe retenu d'un autre sujet est retirée.
  7. Ancres : le membre le plus NET du groupe (médoïde corrigé : central dans le groupe et le moins
     semblable à ce qui n'est pas le sujet — une découpe où le sujet touche un autre personnage perd),
     plus le plus net d'un AUTRE domaine (corps entier préféré, pas exigé), écrites en PNG RGBA sous
     `cache_dir/<sujet>/`. Le `score` des retenues est cette netteté.
  8. Attributs : seulement par la vision injectée `decrire(ancres, nature_en)` ; sans elle,
     `source: "non_evalue"` — jamais d'attribut inventé.
  Sans accord : `etabli=false` et la raison précise ; l'appelant pose la question à l'utilisateur.

Pourquoi des règles relatives seulement : DINOv2 sépare mieux deux personnages d'une même série que
CLIP, mais ses similarités absolues se chevauchent (mesuré le 15/11 : Sharko réel contre Sharko réel
0,56, Zig contre Sharko 0,48 à 0,66). Un seuil fixe accepterait l'un et refuserait l'autre ; un rang
(« voisins mutuels »), une majorité de sources et une comparaison de moyennes ne dépendent pas de
l'échelle.

Tout appel de modèle ou de réseau est injectable (`chercher`, `telecharger`, `decouper`, `embarquer`,
`scorer_texte`, `decrire`) : les tests tournent sur des images synthétiques, sans poids ni réseau.

CLI : `--contrat <json> --cache <dossier> [--journal <dossier>]` imprime UNE ligne JSON (le dossier
`aurora.identite-visuelle.v1`) ; les traces vont sur stderr. Avec `--journal`, `identite.json` (le
dossier + le journal complet : requêtes, candidats, décisions, votes, domaines, ancres, temps) et
`planche_identite.png` (ancres et découpes retenues) y sont écrits.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import io
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

SCHEMA = "aurora.identite-visuelle.v1"
SCHEMA_CONTRAT = "aurora.lecture-demande.v2"

# Composante gardée comme découpe : au moins 4 % de la surface de l'image. Un personnage entier en
# occupe bien plus ; textes, signatures, éclats de détourage et figurants minuscules restent dessous.
PART_MIN_COMPOSANTE = 0.04
# Qui est qui : la nature retenue doit être au moins DEUX FOIS plus probable que la suivante (écart de
# logits CLIP ≥ ln 2). Un rapport de vraisemblance, indépendant de l'échelle des scores.
RAPPORT_CLIP_MIN = 2.0
# Un accord : au moins 3 découpes venues d'au moins 2 domaines (deux images d'un même site ne sont pas
# deux témoins).
MIN_DECOUPES_GROUPE = 3
MIN_DOMAINES_GROUPE = 2
# Groupe ou hasard : silhouette de Rousseeuw sur les distances 1 − cos, (b − a) / max(a, b), avec a la
# distance moyenne interne du groupe et b sa distance moyenne au fond. Un rapport de distances, sans
# similarité absolue ; sous 0,25, Kaufman et Rousseeuw (1990) ne voient « aucune structure
# substantielle ». Mesuré le 15/11/2026 : Zig 0,52, Sharko 0,40 (groupes réels, fond fait de leurs
# propres images avec accessoires ou de personnages mêlés) ; six images sans rapport chaînées par le
# hasard 0,08. Une première règle « fond + 2 écarts-types » refusait Zig et Sharko : leur fond n'était
# pas du bruit mais eux-mêmes, et sa dispersion écrasait l'écart.
SILHOUETTE_MIN = 0.25
# BiRefNet travaille en 1024×1024 : au-delà, les pixels ne servent qu'à coûter de la mémoire.
COTE_MAX_IMAGE = 1024
# dHash 8×8 horizontal + 8×8 vertical = 128 bits, pris sur le contenu recadré (deux sujets posés sur des
# fonds blancs de tailles différentes sont comparés sur eux-mêmes). Mesuré le 15/11/2026 sur les images
# des tests : une copie rééchantillonnée, ré-encodée en JPEG q70 ou retournée diffère de 0 à 6 bits ;
# deux poses différentes du même personnage de 18 à 60 bits (médiane 33). Un seuil à 15 % (19 bits)
# fusionnait deux poses distinctes ; à 10 % (12 bits) les deux familles sont séparées. Doublon : au plus
# 10 % de bits différents ET mêmes proportions à 15 % près.
TAILLE_DHASH = 8
PART_BITS_DOUBLON = 0.10
TOLERANCE_PROPORTIONS = 0.15
# Vignette couleur 4×4 du contenu : une copie garde ses couleurs. Mesuré le 15/11/2026 (écart moyen sur
# 255) : copie rééchantillonnée 1,7, JPEG q70 1,6, miroir 0 ; deux personnages différents 35,6. La
# tolérance de 12 laisse place aux écarts de profil couleur d'un site miroir (tolérance de mesure, pas
# un critère d'identité).
COTE_VIGNETTE_COULEUR = 4
ECART_COULEUR_DOUBLON = 12.0
# Écart minimal au fond (sur 255) pour qu'un pixel compte comme contenu au recadrage : bruit JPEG exclu.
ECART_FOND_CONTENU = 24
TELECHARGEMENTS_PARALLELES = 8
RECHERCHES_PARALLELES = 3

_ICI = Path(__file__).resolve().parent
CACHE_PAR_DEFAUT = _ICI.parents[1] / ".aurora" / "identite"

Chercher = Callable[[str, int], list]
Telecharger = Callable[[str], Image.Image]
Decouper = Callable[[Image.Image], Image.Image]
Embarquer = Callable[[list], np.ndarray]
ScorerTexte = Callable[[list, list], np.ndarray]
Decrire = Callable[[list, str], dict]


def _dire(message: str) -> None:
    print(f"[identite_visuelle] {message}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
#  Textes du contrat
# ---------------------------------------------------------------------------

def _texte(valeur: Any) -> str:
    return " ".join(str(valeur).split()) if valeur not in (None, "") else ""


def _normaliser(texte: str) -> str:
    """Forme de comparaison : casse, accents et espaces neutralisés (« Hyène » = « hyene »)."""
    decompose = unicodedata.normalize("NFKD", texte or "")
    return " ".join("".join(c for c in decompose if not unicodedata.combining(c)).casefold().split())


def _slug(nom: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", nom or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-") or "sujet"


def sujets_nommes(contrat: dict) -> list[int]:
    """Indices (dans le contrat) des sujets nommés : `nomme` vrai et un nom non vide."""
    sujets = contrat.get("sujets") if isinstance(contrat, dict) else None
    if not isinstance(sujets, list):
        return []
    return [i for i, s in enumerate(sujets)
            if isinstance(s, dict) and s.get("nomme") is True and _texte(s.get("nom"))]


def construire_requetes(contrat: dict, index: int) -> list[str]:
    """Requêtes d'un sujet, faites des SEULS mots du contrat.

    « {nom} {autres noms} » : le contexte de l'œuvre est donné par les autres noms de la même demande
    (Zig n'est cherché qu'avec Sharko) ; la requête n'est pas émise sans autre nom, car un nom seul
    apparie n'importe quel homonyme (mesuré le 04/09 sur Wikimedia). Puis « {nom} {nature_en} » et
    « {nom} {nature} ». Doublons retirés (casse et accents ignorés).
    """
    sujets = contrat.get("sujets") or []
    sujet = sujets[index]
    nom = _texte(sujet.get("nom"))
    autres: list[str] = []
    for j in sujets_nommes(contrat):
        autre = _texte(sujets[j].get("nom"))
        if j != index and autre and _normaliser(autre) != _normaliser(nom) \
                and _normaliser(autre) not in {_normaliser(a) for a in autres}:
            autres.append(autre)
    brutes: list[str] = []
    if autres:
        brutes.append(" ".join([nom, *autres]))
    for cle in ("nature_en", "nature"):
        nature = _texte(sujet.get(cle))
        if nature:
            brutes.append(f"{nom} {nature}")
    requetes: list[str] = []
    for requete in brutes:
        if _normaliser(requete) not in {_normaliser(r) for r in requetes}:
            requetes.append(requete)
    return requetes


# ---------------------------------------------------------------------------
#  Images : fond blanc, carré, empreinte perceptuelle, domaine
# ---------------------------------------------------------------------------

def sur_blanc(image: Image.Image) -> Image.Image:
    """RGB ; la transparence posée sur blanc (sinon le décor caché sous l'alpha nul réapparaît)."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        fond = Image.new("RGB", rgba.size, (255, 255, 255))
        fond.paste(rgba, mask=rgba.getchannel("A"))
        return fond
    return image.convert("RGB")


def carre_blanc(image: Image.Image, marge: float = 0.06) -> Image.Image:
    """La découpe ENTIÈRE centrée dans un carré blanc.

    DINOv2 et CLIP redimensionnent au plus petit côté puis recadrent au centre : un personnage debout
    (proportions 1:2) perdait sa tête et ses pieds avant d'être comparé. Le carré garde la silhouette.
    """
    rgb = sur_blanc(image)
    cote = max(1, int(round(max(rgb.size) * (1.0 + 2.0 * marge))))
    toile = Image.new("RGB", (cote, cote), (255, 255, 255))
    toile.paste(rgb, ((cote - rgb.width) // 2, (cote - rgb.height) // 2))
    return toile


def _recadrer_contenu(image: Image.Image) -> Image.Image:
    """Recadre sur le contenu : le fond est la couleur médiane du bord, le contenu ce qui s'en écarte."""
    rgb = sur_blanc(image)
    a = np.asarray(rgb, dtype=np.int16)
    if a.shape[0] < 3 or a.shape[1] < 3:
        return rgb
    bord = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    fond = np.median(bord, axis=0)
    contenu = np.abs(a - fond).max(axis=2) > ECART_FOND_CONTENU
    if not contenu.any():
        return rgb
    ys, xs = np.nonzero(contenu)
    return rgb.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))


def empreinte_dhash(image: Image.Image, taille: int = TAILLE_DHASH) -> np.ndarray:
    """dHash horizontal + vertical (2·taille² bits) de l'image posée sur blanc, en niveaux de gris."""
    gris = sur_blanc(image).convert("L")
    h = np.asarray(gris.resize((taille + 1, taille), Image.Resampling.LANCZOS), dtype=np.int16)
    v = np.asarray(gris.resize((taille, taille + 1), Image.Resampling.LANCZOS), dtype=np.int16)
    return np.concatenate([(h[:, 1:] > h[:, :-1]).ravel(), (v[1:, :] > v[:-1, :]).ravel()])


def distance_empreintes(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(np.asarray(a) != np.asarray(b)))


@dataclass
class Signature:
    """Empreinte d'une image et de son miroir, avec les proportions et les couleurs grossières du contenu."""

    directe: np.ndarray
    miroir: np.ndarray
    proportions: float
    couleurs: np.ndarray
    couleurs_miroir: np.ndarray


def _vignette_couleurs(image: Image.Image) -> np.ndarray:
    return np.asarray(image.resize((COTE_VIGNETTE_COULEUR, COTE_VIGNETTE_COULEUR), Image.Resampling.BOX),
                      dtype=np.float32)


def signature_visuelle(image: Image.Image, recadrer: bool = True) -> Signature:
    contenu = _recadrer_contenu(image) if recadrer else sur_blanc(image)
    miroir = ImageOps.mirror(contenu)
    return Signature(empreinte_dhash(contenu), empreinte_dhash(miroir), contenu.width / max(1, contenu.height),
                     _vignette_couleurs(contenu), _vignette_couleurs(miroir))


def sont_doublons(a: Signature, b: Signature) -> bool:
    """Même image (copie, ré-encodage, changement d'échelle ou miroir) : proportions, gradients ET couleurs concordent.

    Le dHash ne voit que le signe des gradients en niveaux de gris : deux personnages DIFFÉRENTS dessinés
    dans des poses voisines peuvent le partager (mesuré le 15/11 : un violet et un turquoise à 12 bits
    sur 128, fusionnés à tort). Une copie garde ses couleurs : la vignette 4×4 en couleur, dans la même
    orientation que l'empreinte retenue, doit concorder aussi.
    """
    if abs(math.log(max(a.proportions, 1e-6) / max(b.proportions, 1e-6))) > math.log(1.0 + TOLERANCE_PROPORTIONS):
        return False
    limite = PART_BITS_DOUBLON * a.directe.size
    for empreinte, couleurs in ((b.directe, b.couleurs), (b.miroir, b.couleurs_miroir)):
        if distance_empreintes(a.directe, empreinte) <= limite and \
                float(np.mean(np.abs(a.couleurs - couleurs))) <= ECART_COULEUR_DOUBLON:
            return True
    return False


def domaine(url: str) -> str:
    """Domaine enregistrable approché d'une URL : un site compte une fois, quels que soient ses sous-domaines.

    Sans liste publique des suffixes (absente du venv), règle générale : les deux derniers labels,
    trois quand le dernier est un code pays à deux lettres précédé d'un label court (« co.uk »,
    « com.br »). `fr.pinterest.com` et `pinterest.com` sont donc une seule source.
    """
    hote = (urllib.parse.urlparse(url or "").hostname or "").lower().strip(".")
    if not hote:
        return ""
    if re.fullmatch(r"[0-9.]+", hote) or ":" in hote:
        return hote
    labels = hote.split(".")
    if len(labels) >= 3 and len(labels[-1]) == 2 and len(labels[-2]) <= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _normaliser_image(image: Image.Image) -> Image.Image:
    """Mode RGB/RGBA et plus grand côté borné à COTE_MAX_IMAGE (proportions gardées)."""
    image = ImageOps.exif_transpose(image) if hasattr(image, "getexif") else image
    possede_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    image = image.convert("RGBA" if possede_alpha else "RGB")
    if max(image.size) > COTE_MAX_IMAGE:
        echelle = COTE_MAX_IMAGE / float(max(image.size))
        image = image.resize((max(1, round(image.width * echelle)), max(1, round(image.height * echelle))),
                             Image.Resampling.LANCZOS)
    return image


def _empreinte_pixels(image: Image.Image) -> str:
    h = hashlib.sha1()
    h.update(f"{image.mode}:{image.width}x{image.height}:".encode())
    h.update(image.tobytes())
    return h.hexdigest()[:16]


class _Partition:
    """Union-find minimal (regroupement des doublons et composantes du graphe d'accord)."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def racine(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def unir(self, a: int, b: int) -> None:
        ra, rb = self.racine(a), self.racine(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def groupes(self) -> list[list[int]]:
        par_racine: dict[int, list[int]] = {}
        for i in range(len(self.parent)):
            par_racine.setdefault(self.racine(i), []).append(i)
        return sorted(par_racine.values(), key=lambda g: g[0])


def regrouper_doublons(signatures: Sequence[Signature]) -> list[list[int]]:
    """Groupes d'indices des images qui sont des copies l'une de l'autre (transitif)."""
    partition = _Partition(len(signatures))
    for a in range(len(signatures)):
        for b in range(a + 1, len(signatures)):
            if sont_doublons(signatures[a], signatures[b]):
                partition.unir(a, b)
    return partition.groupes()


# ---------------------------------------------------------------------------
#  Découpes : composantes connexes du détourage
# ---------------------------------------------------------------------------

def decoupes_par_composantes(rgba: Image.Image, part_min: float = PART_MIN_COMPOSANTE) -> list[dict]:
    """Une découpe RGBA par composante connexe du masque d'au moins `part_min` de l'image.

    Deux personnages séparés sur une image de groupe deviennent deux découpes ; deux personnages qui
    se touchent restent une seule découpe mêlée (le vote d'accord la laisse de côté : elle n'a de
    jumeau ni d'un côté ni de l'autre). La frange semi-transparente d'un pixel autour de la
    composante est gardée (bord doux du détourage).
    """
    import cv2

    arr = np.asarray(rgba.convert("RGBA")).copy()
    alpha = arr[..., 3]
    hauteur, largeur = alpha.shape
    surface = float(hauteur * largeur)
    nombre, etiquettes, stats, _ = cv2.connectedComponentsWithStats((alpha > 127).astype(np.uint8), connectivity=8)
    noyau = np.ones((3, 3), np.uint8)
    decoupes: list[dict] = []
    for k in range(1, nombre):
        aire = int(stats[k, cv2.CC_STAT_AREA])
        if aire < part_min * surface:
            continue
        x, y, w, h = (int(v) for v in stats[k, :4])
        x0, y0 = max(0, x - 1), max(0, y - 1)
        x1, y1 = min(largeur, x + w + 1), min(hauteur, y + h + 1)
        zone = cv2.dilate((etiquettes[y0:y1, x0:x1] == k).astype(np.uint8), noyau) > 0
        morceau = arr[y0:y1, x0:x1].copy()
        morceau[..., 3] = np.where(zone, morceau[..., 3], 0)
        decoupes.append({
            "rgba": Image.fromarray(morceau, "RGBA"),
            "bbox": [x, y, w, h],
            "part": aire / surface,
            "bord": bool(x == 0 or y == 0 or x + w >= largeur or y + h >= hauteur),
        })
    decoupes.sort(key=lambda d: (d["bbox"][0], d["bbox"][1]))
    return decoupes


# ---------------------------------------------------------------------------
#  Accord : graphe des k plus proches voisins mutuels
# ---------------------------------------------------------------------------

def k_voisins(n: int) -> int:
    """k du graphe d'accord : croît comme √n, et reste SÉLECTIF (k ≤ n − 2).

    Avec k = n − 1, chaque découpe aurait toutes les autres pour voisines : trois images quelconques
    formeraient un triangle « d'accord ». Le graphe doit pouvoir dire non.
    """
    return max(1, min(n - 2, int(round(math.sqrt(max(n, 1))))))


def graphe_accord(similarites: np.ndarray, k: int) -> tuple[list[list[int]], list[tuple[int, int]]]:
    """Composantes connexes et arêtes du graphe des k plus proches voisins MUTUELS.

    j est voisin de i si moins de k découpes sont STRICTEMENT plus proches de i : les ex aequo au rang k
    sont tous voisins (une similarité partout égale relie tout le monde, et le second temps du vote
    constate alors qu'il n'existe aucune paire non jumelle à qui comparer le groupe). Une arête exige
    la réciprocité : un intrus voit bien un plus proche voisin dans le groupe, mais les membres du
    groupe ont plus proche que lui.
    """
    n = int(similarites.shape[0])
    voisins: list[set[int]] = []
    for i in range(n):
        ligne = np.asarray(similarites[i], dtype=np.float64).copy()
        ligne[i] = -np.inf
        voisins.append({j for j in range(n) if j != i and int(np.count_nonzero(ligne > ligne[j])) < k})
    partition = _Partition(n)
    aretes: list[tuple[int, int]] = []
    for i in range(n):
        for j in sorted(voisins[i]):
            if j > i and i in voisins[j]:
                aretes.append((i, j))
                partition.unir(i, j)
    return partition.groupes(), aretes


def _moyenne(valeurs: np.ndarray) -> float | None:
    return float(np.mean(valeurs)) if np.size(valeurs) else None


def silhouette(similarite_interne: float, similarite_externe: float) -> float:
    """Silhouette de Rousseeuw exprimée depuis des similarités cosinus : (b − a) / max(a, b) sur 1 − cos.

    1 : le groupe est infiniment plus serré qu'avec l'extérieur ; 0 : aucune différence ; < 0 : plus
    proche de l'extérieur que de lui-même.
    """
    a, b = 1.0 - float(similarite_interne), 1.0 - float(similarite_externe)
    return (b - a) / max(a, b, 1e-9)


# ---------------------------------------------------------------------------
#  Fonctions par défaut (réseau, détourage, modèles) — toutes remplaçables
# ---------------------------------------------------------------------------

def _importer_voisin(nom: str):
    """Importe un module frère de python-services, que ce fichier soit lancé en script ou importé."""
    if str(_ICI) not in sys.path:
        sys.path.insert(0, str(_ICI))
    return __import__(nom)


def chercher_par_defaut(requete: str, limite: int) -> list[dict]:
    """Bing Images d'abord ; Wikimedia et Openverse (fournisseurs de crawl4ai_search) en complément."""
    rvs = _importer_voisin("reference_visual_search")
    resultats: list[dict] = []
    vus: set[str] = set()

    def ajouter(candidat: dict, moteur: str) -> None:
        url = str(candidat.get("imageUrl") or "").strip()
        if url and url not in vus:
            vus.add(url)
            resultats.append({
                "imageUrl": url,
                "pageUrl": str(candidat.get("pageUrl") or ""),
                "thumbUrl": str(candidat.get("thumbUrl") or ""),
                "title": str(candidat.get("title") or ""),
                "engine": moteur,
            })

    for candidat in rvs.search_bing_images(requete, limite) or []:
        ajouter(candidat, "bing-images")
    if len(resultats) < limite:
        try:
            c4 = _importer_voisin("crawl4ai_search")
            for fournisseur, moteur in ((c4._images_wikimedia, "crawl4ai:wikimedia"),
                                        (c4._images_openverse, "crawl4ai:openverse")):
                try:
                    lignes = fournisseur(requete, limite) or []
                except Exception:  # noqa: BLE001 — une source morte n'en tue pas une autre
                    continue
                for ligne in lignes:
                    ajouter({"imageUrl": ligne.get("url"), "pageUrl": ligne.get("sourcePage"),
                             "thumbUrl": ligne.get("thumb"), "title": ligne.get("alt")}, moteur)
        except Exception:  # noqa: BLE001
            pass
    return resultats


def telecharger_par_defaut(url: str) -> Image.Image:
    """`reference_visual_search.download_image` : image raster décodée et vérifiée (≥ 64 px)."""
    rvs = _importer_voisin("reference_visual_search")
    reponse = rvs.download_image(url)
    if not reponse.get("ok"):
        raise RuntimeError(str(reponse.get("error") or "téléchargement refusé"))
    with Image.open(io.BytesIO(base64.b64decode(reponse["base64"]))) as image:
        image.load()
        return image.copy()


def _fils_cpu() -> int:
    """Fils de calcul CPU : `AURORA_IDENTITE_FILS`, sinon 8 au plus (d'autres agents partagent le poste)."""
    try:
        demande = int(os.environ.get("AURORA_IDENTITE_FILS") or 0)
    except ValueError:
        demande = 0
    return demande if demande > 0 else max(1, min(8, os.cpu_count() or 4))


class DecoupeurBiRefNet:
    """Détourage BiRefNet (`birefnet-general`, rembg) sur CPU, avec cache des masques par contenu.

    Forcé sur CPU (le GPU de 16 Go est partagé avec FLUX/TRELLIS) et borné en fils de calcul. Le masque
    est mis en cache sous `dossier_cache/<empreinte>.png` : un second run sur les mêmes images ne
    repaie pas le détourage. Un alpha déjà présent dans l'image (PNG transparent) est combiné au
    masque, comme dans `photo_rectifier`.
    """

    def __init__(self, dossier_cache: Path | None = None, modele: str = "birefnet-general",
                 fils: int | None = None) -> None:
        self.dossier_cache = Path(dossier_cache) if dossier_cache else None
        self.modele = modele
        self.fils = fils or _fils_cpu()
        self._session = None
        self.appels = 0
        self.depuis_cache = 0

    def _ouvrir(self):
        if self._session is None:
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.intra_op_num_threads = self.fils
            options.inter_op_num_threads = 1
            # Mesuré le 15/11/2026 sur ce poste (une image, 8 fils) : 13,6 Go de mémoire résidente avec
            # l'arène CPU d'onnxruntime, 7,4 Go sans, pour 7,6 s par image au lieu de 6,4 s. Le poste
            # (30 Go, partagé, déjà gelé) passe avant les 20 % de temps.
            options.enable_cpu_mem_arena = False
            options.enable_mem_pattern = False
            try:
                from rembg.sessions import sessions_class

                classe = next((c for c in sessions_class if c.name() == self.modele), None)
                if classe is None:
                    raise RuntimeError(f"session rembg inconnue : {self.modele}")
                self._session = classe(self.modele, options, providers=["CPUExecutionProvider"])
            except ImportError:
                import rembg

                self._session = rembg.new_session(self.modele, providers=["CPUExecutionProvider"])
        return self._session

    def __call__(self, image: Image.Image) -> Image.Image:
        rgb = sur_blanc(image)
        cle = f"{_empreinte_pixels(rgb)}_{self.modele}"
        chemin = self.dossier_cache / f"{cle}.png" if self.dossier_cache else None
        alpha = None
        if chemin is not None and chemin.is_file():
            try:
                with Image.open(chemin) as cache:
                    alpha = cache.convert("L").copy()
                if alpha.size != rgb.size:
                    alpha = None
                else:
                    self.depuis_cache += 1
            except Exception:  # noqa: BLE001 — cache abîmé : on recalcule
                alpha = None
        if alpha is None:
            import rembg

            alpha = rembg.remove(rgb, session=self._ouvrir()).convert("RGBA").getchannel("A")
            self.appels += 1
            if chemin is not None:
                chemin.parent.mkdir(parents=True, exist_ok=True)
                provisoire = chemin.with_suffix(".tmp.png")
                alpha.save(provisoire)
                os.replace(provisoire, chemin)
        if image.mode == "RGBA":
            existant = np.asarray(image.getchannel("A"))
            transparent = float((existant < 25).mean())
            if 0.02 <= transparent <= 0.95:
                alpha = Image.fromarray(np.minimum(np.asarray(alpha), existant))
        sortie = rgb.convert("RGBA")
        sortie.putalpha(alpha)
        return sortie

    def fermer(self) -> None:
        """Rend la mémoire de la session ONNX (≈ 1 Go de poids, plus les activations 1024²)."""
        self._session = None
        import gc

        gc.collect()


def embarquer_par_defaut(images: list) -> np.ndarray:
    return _importer_voisin("modeles_locaux").embed_images(images)


def scorer_texte_par_defaut(images: list, textes: list) -> np.ndarray:
    return _importer_voisin("modeles_locaux").clip_text_image_scores(images, textes)


# ---------------------------------------------------------------------------
#  Structures de travail
# ---------------------------------------------------------------------------

@dataclass
class Candidat:
    url: str
    page: str
    miniature: str
    moteur: str
    titre: str
    requetes: list[str] = field(default_factory=list)


@dataclass
class Copie:
    """Une image téléchargée depuis UNE adresse."""

    url: str
    page: str
    domaine: str
    moteur: str
    via: str
    image: Image.Image
    requetes: set[str] = field(default_factory=set)
    sujets: set[int] = field(default_factory=set)


@dataclass
class ImageSource:
    """Une image après fusion de ses copies : un miroir compte une fois."""

    id: str
    image: Image.Image
    copies: list[Copie]

    @property
    def representant(self) -> Copie:
        return self.copies[0]

    @property
    def domaine(self) -> str:
        return self.representant.domaine


@dataclass
class Noeud:
    """Une découpe (après fusion des découpes identiques venues d'images différentes)."""

    id: str
    rgba: Image.Image
    image_id: str
    bbox: list[int]
    part: float
    bord: bool
    domaine: str
    source_url: str
    page: str
    images: list[str] = field(default_factory=list)
    domaines_miroirs: list[str] = field(default_factory=list)
    sujet: int | None = None
    decision: str = ""
    scores_texte: dict[str, float] = field(default_factory=dict)


def _attributs_non_evalues() -> dict:
    return {"plan_du_corps": None, "vetements": None, "couleurs": [], "style_origine": None, "source": "non_evalue"}


def _normaliser_attributs(brut: Any) -> dict:
    """Ne garde que les champs du schéma ; rien n'est complété ni deviné."""
    if not isinstance(brut, dict):
        return _attributs_non_evalues()
    sortie = _attributs_non_evalues()
    for cle in ("plan_du_corps", "vetements", "style_origine"):
        valeur = brut.get(cle)
        sortie[cle] = valeur.strip() if isinstance(valeur, str) and valeur.strip() else None
    couleurs = brut.get("couleurs")
    sortie["couleurs"] = [str(c).strip() for c in couleurs if str(c).strip()] if isinstance(couleurs, list) else []
    sortie["source"] = "vision"
    return sortie


def _arrondi(valeur: float | None, chiffres: int = 4) -> float | None:
    return None if valeur is None else round(float(valeur), chiffres)


# ---------------------------------------------------------------------------
#  Étapes
# ---------------------------------------------------------------------------

def _rechercher(requetes: dict[int, list[str]], chercher: Chercher, limite: int,
                journal: dict) -> dict[int, list[Candidat]]:
    """Chaque requête distincte une fois ; candidats d'un sujet entrelacés requête par requête (rang d'abord)."""
    distinctes: dict[str, str] = {}
    for liste in requetes.values():
        for requete in liste:
            distinctes.setdefault(_normaliser(requete), requete)

    def lancer(requete: str) -> tuple[str, list, float, str | None]:
        debut = time.monotonic()
        try:
            return requete, list(chercher(requete, limite) or []), time.monotonic() - debut, None
        except Exception as exc:  # noqa: BLE001 — une requête morte est notée, pas fatale
            return requete, [], time.monotonic() - debut, f"{type(exc).__name__}: {exc}"[:240]

    with ThreadPoolExecutor(max_workers=RECHERCHES_PARALLELES) as pool:
        reponses = {r[0]: r for r in pool.map(lancer, list(distinctes.values()))}
    for requete, resultats, duree, erreur in reponses.values():
        moteurs: dict[str, int] = {}
        for r in resultats:
            moteurs[str(r.get("engine") or "?")] = moteurs.get(str(r.get("engine") or "?"), 0) + 1
        journal["requetes"].append({"requete": requete, "resultats": len(resultats), "moteurs": moteurs,
                                    "duree_s": round(duree, 2), "erreur": erreur})

    candidats: dict[int, list[Candidat]] = {}
    for index, liste in requetes.items():
        par_requete = [reponses[distinctes[_normaliser(r)]][1] for r in liste]
        ordre: list[Candidat] = []
        par_url: dict[str, Candidat] = {}
        for rang in range(max((len(p) for p in par_requete), default=0)):
            for requete, resultats in zip(liste, par_requete):
                if rang >= len(resultats):
                    continue
                brut = resultats[rang]
                url = str(brut.get("imageUrl") or "").strip()
                if not url:
                    continue
                if url in par_url:
                    if requete not in par_url[url].requetes:
                        par_url[url].requetes.append(requete)
                    continue
                candidat = Candidat(url=url, page=str(brut.get("pageUrl") or ""),
                                    miniature=str(brut.get("thumbUrl") or ""),
                                    moteur=str(brut.get("engine") or ""), titre=str(brut.get("title") or "")[:160],
                                    requetes=[requete])
                par_url[url] = candidat
                ordre.append(candidat)
        candidats[index] = ordre
    return candidats


def _telecharger(candidats: dict[int, list[Candidat]], telecharger: Telecharger, dossier_images: Path,
                 max_par_sujet: int, journal: dict) -> list[Copie]:
    """Au plus `max_par_sujet` images réussies par sujet ; une image déjà obtenue pour un autre sujet compte aussi."""
    tentes: dict[str, Copie | str] = {}

    def un(candidat: Candidat) -> tuple[Candidat, Copie | str, bool]:
        chemin = dossier_images / f"{hashlib.sha1(candidat.url.encode('utf-8')).hexdigest()[:24]}.png"
        if chemin.is_file():
            try:
                with Image.open(chemin) as cache:
                    image = _normaliser_image(cache.copy())
                return candidat, Copie(candidat.url, candidat.page, domaine(candidat.page or candidat.url),
                                       candidat.moteur, "cache", image), True
            except Exception:  # noqa: BLE001 — cache illisible : on retélécharge
                pass
        erreurs: list[str] = []
        for adresse, via in ((candidat.url, "original"), (candidat.miniature, "miniature")):
            if not adresse or (via == "miniature" and adresse == candidat.url):
                continue
            try:
                image = telecharger(adresse)
                if image is None:
                    raise RuntimeError("aucune image rendue")
                image = _normaliser_image(image)
                if min(image.size) < 64:
                    raise RuntimeError(f"image trop petite {image.size}")
            except Exception as exc:  # noqa: BLE001 — l'échec est noté, on essaie la miniature
                erreurs.append(f"{via}: {type(exc).__name__}: {exc}"[:200])
                continue
            try:
                dossier_images.mkdir(parents=True, exist_ok=True)
                provisoire = chemin.with_suffix(".tmp.png")
                image.save(provisoire, format="PNG", compress_level=1)
                os.replace(provisoire, chemin)
            except OSError:
                pass
            return candidat, Copie(candidat.url, candidat.page, domaine(candidat.page or candidat.url),
                                   candidat.moteur, via, image), False
        return candidat, " | ".join(erreurs) or "aucune adresse", False

    for index, liste in candidats.items():
        reussis = 0
        essais = 0
        position = 0
        while reussis < max_par_sujet and position < len(liste) and essais < 3 * max_par_sujet:
            lot: list[Candidat] = []
            while position < len(liste) and len(lot) < max_par_sujet - reussis:
                candidat = liste[position]
                position += 1
                deja = tentes.get(candidat.url)
                if isinstance(deja, Copie):
                    deja.sujets.add(index)
                    deja.requetes.update(candidat.requetes)
                    reussis += 1
                    if reussis >= max_par_sujet:
                        break
                elif deja is None:
                    lot.append(candidat)
            if not lot:
                continue
            essais += len(lot)
            with ThreadPoolExecutor(max_workers=TELECHARGEMENTS_PARALLELES) as pool:
                for candidat, issue, depuis_cache in pool.map(un, lot):
                    tentes[candidat.url] = issue
                    entree = {"url": candidat.url, "page": candidat.page, "domaine": domaine(candidat.page or candidat.url),
                              "moteur": candidat.moteur, "requetes": list(candidat.requetes), "sujet": index}
                    if isinstance(issue, Copie):
                        issue.sujets.add(index)
                        issue.requetes.update(candidat.requetes)
                        reussis += 1
                        entree.update({"ok": True, "via": issue.via, "taille": list(issue.image.size),
                                       "cache": depuis_cache})
                    else:
                        entree.update({"ok": False, "erreur": issue})
                    journal["telechargements"].append(entree)
    return [c for c in tentes.values() if isinstance(c, Copie)]


def _fusionner_images(copies: list[Copie], journal: dict) -> list[ImageSource]:
    """Les copies d'une même image (miroirs) deviennent UNE image ; la plus grande la représente."""
    signatures = [signature_visuelle(c.image, recadrer=True) for c in copies]
    sources: list[ImageSource] = []
    for groupe in regrouper_doublons(signatures):
        membres = sorted((copies[i] for i in groupe), key=lambda c: -(c.image.width * c.image.height))
        source = ImageSource(id=_empreinte_pixels(membres[0].image), image=membres[0].image, copies=membres)
        sources.append(source)
        if len(membres) > 1:
            journal["doublons_images"].append({
                "image": source.id, "representant": membres[0].url,
                "copies": [{"url": c.url, "domaine": c.domaine} for c in membres],
            })
    return sources


def _decouper_images(sources: list[ImageSource], decouper: Decouper, journal: dict) -> list[Noeud]:
    """Détourage puis composantes ; puis fusion des découpes identiques venues d'images différentes."""
    brutes: list[tuple[ImageSource, dict]] = []
    for source in sources:
        try:
            rgba = decouper(source.image)
            if rgba is None or rgba.size != source.image.size:
                raise RuntimeError("le détourage n'a pas rendu une image de même taille")
        except Exception as exc:  # noqa: BLE001 — une image non détourable n'arrête pas les autres
            journal["decoupes_erreurs"].append({"image": source.id, "url": source.representant.url,
                                                "erreur": f"{type(exc).__name__}: {exc}"[:240]})
            continue
        for morceau in decoupes_par_composantes(rgba):
            brutes.append((source, morceau))
    signatures = [signature_visuelle(m["rgba"], recadrer=False) for _, m in brutes]
    noeuds: list[Noeud] = []
    for groupe in regrouper_doublons(signatures):
        membres = sorted(groupe, key=lambda i: -(brutes[i][1]["rgba"].width * brutes[i][1]["rgba"].height))
        source, morceau = brutes[membres[0]]
        noeud = Noeud(id=_empreinte_pixels(morceau["rgba"]), rgba=morceau["rgba"], image_id=source.id,
                      bbox=morceau["bbox"], part=float(morceau["part"]), bord=bool(morceau["bord"]),
                      domaine=source.domaine, source_url=source.representant.url, page=source.representant.page,
                      images=sorted({brutes[i][0].id for i in membres}),
                      domaines_miroirs=sorted({c.domaine for i in membres for c in brutes[i][0].copies}))
        noeuds.append(noeud)
        if len(membres) > 1:
            journal["doublons_decoupes"].append({"decoupe": noeud.id, "images": noeud.images,
                                                 "domaines": noeud.domaines_miroirs})
    return noeuds


def _attribuer(noeuds: list[Noeud], carres: list[Image.Image], contrat: dict, nommes: list[int],
               sources: dict[str, ImageSource], scorer_texte: ScorerTexte, journal: dict) -> None:
    """Qui est qui : chaque découpe va à la nature du contrat la plus probable, avec une marge.

    Les natures de TOUS les sujets du contrat (nommés ou non) sont candidates : une découpe de la
    nature d'un sujet non nommé n'entre dans le vote d'aucun sujet nommé. Si plusieurs sujets nommés
    partagent la nature gagnante, seuls ceux dont les requêtes ont trouvé l'image restent candidats ;
    s'il en reste plusieurs, la découpe est ambiguë et ne compte pour personne.
    """
    sujets = contrat.get("sujets") or []
    natures: list[str] = []
    sujets_par_nature: dict[str, list[int]] = {}
    for i, sujet in enumerate(sujets):
        nature = _texte(sujet.get("nature_en")) if isinstance(sujet, dict) else ""
        if not nature:
            continue
        cle = _normaliser(nature)
        if cle not in sujets_par_nature:
            sujets_par_nature[cle] = []
            natures.append(nature)
        sujets_par_nature[cle].append(i)
    journal["natures"] = natures
    nommes_set = set(nommes)

    def sujets_trouveurs(noeud: Noeud) -> set[int]:
        trouve: set[int] = set()
        for image_id in noeud.images:
            for copie in sources[image_id].copies:
                trouve |= copie.sujets
        return trouve

    def decider(noeud: Noeud, cle_nature: str) -> None:
        candidats = [i for i in sujets_par_nature.get(cle_nature, []) if i in nommes_set]
        if not candidats:
            noeud.decision = "nature d'un sujet non nommé"
            return
        if len(candidats) > 1:
            candidats = [i for i in candidats if i in sujets_trouveurs(noeud)]
        if len(candidats) == 1:
            noeud.sujet = candidats[0]
            noeud.decision = "attribuée"
        else:
            noeud.decision = "ambiguë : plusieurs sujets nommés de même nature l'ont trouvée"

    if len(natures) == 1:
        journal["attribution"] = "une seule nature dans le contrat : CLIP sans objet, l'accord tranche seul"
        for noeud in noeuds:
            decider(noeud, _normaliser(natures[0]))
        return
    if not natures:
        journal["attribution"] = "aucune nature_en dans le contrat : attribution impossible"
        for noeud in noeuds:
            noeud.decision = "aucune nature dans le contrat"
        return
    scores = np.asarray(scorer_texte(carres, natures), dtype=np.float64)
    if scores.shape != (len(noeuds), len(natures)):
        raise RuntimeError(f"scores CLIP de forme {scores.shape}, attendu {(len(noeuds), len(natures))}")
    seuil = math.log(RAPPORT_CLIP_MIN)
    journal["attribution"] = f"CLIP sur {len(natures)} natures, rapport de probabilité minimal {RAPPORT_CLIP_MIN:g}"
    for noeud, ligne in zip(noeuds, scores):
        ordre = np.argsort(-ligne)
        probabilites = np.exp(ligne - ligne.max())
        probabilites /= probabilites.sum()
        noeud.scores_texte = {natures[j]: round(float(probabilites[j]), 4) for j in range(len(natures))}
        if ligne[ordre[0]] - ligne[ordre[1]] < seuil:
            noeud.decision = "marge CLIP insuffisante entre les natures"
            continue
        decider(noeud, _normaliser(natures[int(ordre[0])]))


def _decrire_composante(membres: list[int], noeuds: list[Noeud], similarites: np.ndarray) -> dict:
    sous = similarites[np.ix_(membres, membres)]
    paires = sous[np.triu_indices(len(membres), 1)]
    return {
        "membres": membres,
        "domaines": sorted({noeuds[m].domaine for m in membres}),
        "images": sorted({noeuds[m].image_id for m in membres}),
        "densite": _moyenne(paires),
    }


def _cle_composante(c: dict) -> tuple:
    return (len(c["domaines"]), len(c["images"]), len(c["membres"]), c["densite"] or 0.0)


def reference_non_jumelles(similarites: np.ndarray, tetes: Sequence[Sequence[int]],
                           tete: Sequence[int], propres: Sequence[int] = ()) -> tuple[str | None, float | None, int]:
    """À quoi comparer un groupe de tête : (nature de la référence, médiane des similarités, nombre de paires).

    1. « fond » : les paires du run dont au moins une découpe n'appartient à AUCUNE tête — ce que la
       recherche rend en plus des identités (décor, logos, mélanges, membres oubliés). Leur médiane est
       la ressemblance typique de deux découpes non jumelles.
    2. « autres identités », s'il n'y a pas de fond : les paires entre cette tête et celles des autres
       sujets (personnages d'une même série : référence plus exigeante que le hasard).
    3. Rien : (None, None, 0).

    Pourquoi pas le seul fond DU SUJET : mesuré le 15/11/2026, il contient souvent le sujet lui-même —
    les quatre découpes de Zig hors du groupe étaient Zig tenant un accessoire ; un personnage de quatre
    images perdait la quatrième (aucun voisin MUTUEL) et le groupe se comparait à lui-même (silhouette
    0,16, refus à tort). La médiane sur tout le run ne bouge pas pour quelques membres oubliés.
    """
    n = int(similarites.shape[0])
    dans_une_tete = np.zeros(n, dtype=bool)
    for groupe in tetes:
        dans_une_tete[list(groupe)] = True
    # Les découpes attribuées au sujet lui-même, hors de sa tête (voisins non mutuels), ne sont pas du
    # hasard : sur un petit run, une seule d'entre elles tirait la médiane du « fond » vers le sujet et
    # faisait refuser un groupe cohérent (15/11/2026).
    sans_propres = dans_une_tete.copy()
    if len(propres):
        dans_une_tete[list(propres)] = True
    haut = np.triu(np.ones((n, n), dtype=bool), 1)
    fond = haut & ~(dans_une_tete[:, None] & dans_une_tete[None, :])
    if not fond.any() and len(propres):
        ailleurs = {m for g in tetes for m in g} - set(tete) - set(propres)
        if not ailleurs:
            # sujet seul dans le run : ses propres découpes écartées restent la seule comparaison possible ;
            # sinon les autres identités de la demande servent de référence (branche suivante)
            fond = haut & ~(sans_propres[:, None] & sans_propres[None, :])
    if fond.any():
        valeurs = similarites[fond]
        return "fond", float(np.median(valeurs)), int(valeurs.size)
    ici = set(tete) | set(propres)
    autres = sorted({m for g in tetes for m in g if m not in ici})
    if autres and tete:
        valeurs = similarites[np.ix_(list(tete), autres)].ravel()
        return "autres identités", float(np.median(valeurs)), int(valeurs.size)
    return None, None, 0


def choisir_tete(membres_sujet: list[int], noeuds: list[Noeud], similarites: np.ndarray) -> dict:
    """Premier temps du vote : la composante de tête du graphe mutuel parmi les découpes du sujet.

    Retenue : la composante soutenue par le plus de domaines (puis d'images), avec au moins 3 découpes
    et 2 domaines, STRICTEMENT plus soutenue que la composante suivante (sinon deux identités se
    disputent le nom : ambigu). `similarites` couvre TOUTES les découpes du run.
    """
    n = len(membres_sujet)
    vote: dict[str, Any] = {"decoupes": [noeuds[m].id for m in membres_sujet], "k": None,
                            "composantes": [], "aretes": [], "tete": None, "groupe": None, "raison": None}
    if n < MIN_DECOUPES_GROUPE:
        vote["raison"] = (f"{n} découpe(s) attribuée(s) au sujet après dédoublonnage : il en faut au moins "
                          f"{MIN_DECOUPES_GROUPE} venant d'au moins {MIN_DOMAINES_GROUPE} domaines pour un accord")
        return vote
    k = k_voisins(n)
    locales = similarites[np.ix_(membres_sujet, membres_sujet)]
    composantes_locales, aretes = graphe_accord(locales, k)
    vote["k"] = k
    vote["aretes"] = [[noeuds[membres_sujet[a]].id, noeuds[membres_sujet[b]].id] for a, b in aretes]
    groupes = [_decrire_composante([membres_sujet[i] for i in c], noeuds, similarites)
               for c in composantes_locales if len(c) >= 2]
    groupes.sort(key=_cle_composante, reverse=True)
    vote["composantes"] = [{"decoupes": [noeuds[m].id for m in g["membres"]], "domaines": g["domaines"],
                            "images": len(g["images"]), "densite": _arrondi(g["densite"])} for g in groupes]
    if groupes:  # proximité de chaque découpe du sujet au groupe de tête : la trace qui permet de recaler
        tete = groupes[0]["membres"]
        vote["proximite_groupe_de_tete"] = {
            noeuds[m].id: _arrondi(_moyenne(similarites[m, [t for t in tete if t != m]]))
            for m in membres_sujet}
    valides = [g for g in groupes if len(g["membres"]) >= MIN_DECOUPES_GROUPE
               and len(g["domaines"]) >= MIN_DOMAINES_GROUPE]
    if not valides:
        tailles = ", ".join(f"{len(g['membres'])} découpes/{len(g['domaines'])} domaine(s)" for g in groupes) or "aucune"
        vote["raison"] = (f"aucun groupe d'accord parmi {n} découpes (k={k}) : composantes jumelles [{tailles}] ; "
                          f"il faut au moins {MIN_DECOUPES_GROUPE} découpes venant d'au moins "
                          f"{MIN_DOMAINES_GROUPE} domaines")
        return vote
    meilleur = valides[0]
    suivant = next((g for g in groupes if g is not meilleur), None)
    if suivant is not None and (len(suivant["domaines"]), len(suivant["images"])) >= \
            (len(meilleur["domaines"]), len(meilleur["images"])):
        vote["raison"] = (f"accord ambigu : deux groupes également soutenus ({len(meilleur['domaines'])} domaines, "
                          f"{len(meilleur['images'])} images chacun) se disputent le nom")
        return vote
    vote["tete"] = list(meilleur["membres"])
    vote["cohesion"] = _arrondi(meilleur["densite"])
    return vote


def valider_tete(vote: dict, similarites: np.ndarray, groupes_de_tete: Sequence[Sequence[int]],
                 propres: Sequence[int] = ()) -> dict:
    """Second temps du vote : groupe ou hasard ? Silhouette de la tête face aux paires non jumelles.

    `groupes_de_tete` : les têtes de TOUS les sujets du run (leurs paires internes ne sont pas une
    référence d'étrangers). Sans aucune paire non jumelle, « se ressembler entre soi » ne se distingue
    plus de « n'avoir que soi » : l'accord n'est pas démontrable.
    """
    tete = vote.get("tete")
    if not tete:
        return vote
    nature, reference, paires = reference_non_jumelles(similarites, groupes_de_tete, tete, propres)
    cohesion = float(vote.get("cohesion") or 0.0)
    if reference is None:
        vote["raison"] = (f"aucun élément de comparaison : les {len(tete)} découpes forment un seul groupe et "
                          f"aucune autre découpe n'existe dans le run — l'accord n'est pas démontrable")
        return vote
    # Contre le fond : une vraie structure (silhouette ≥ SILHOUETTE_MIN). Contre d'autres identités seules :
    # au moins plus proche de soi que d'elles — leur séparation fine est le rôle de l'exclusion croisée.
    minimum = SILHOUETTE_MIN if nature == "fond" else 0.0
    valeur = silhouette(cohesion, reference)
    vote.update({"reference": nature, "reference_mediane": _arrondi(reference), "paires_reference": paires,
                 "silhouette": _arrondi(valeur), "silhouette_min": minimum})
    if valeur < minimum or valeur <= 0.0:
        vote["raison"] = (f"groupe non séparé du hasard : silhouette {valeur:.2f} < {minimum:g} face au {nature} "
                          f"(cohésion {cohesion:.3f}, médiane des paires non jumelles {reference:.3f}) ; "
                          f"des voisins de hasard, pas une identité")
        return vote
    vote["groupe"] = list(tete)
    return vote


def voter(membres_sujet: list[int], noeuds: list[Noeud], similarites: np.ndarray,
          autres_tetes: Sequence[Sequence[int]] = ()) -> dict:
    """Vote d'accord complet d'un sujet : tête du graphe mutuel, puis silhouette face aux paires non jumelles."""
    vote = choisir_tete(membres_sujet, noeuds, similarites)
    if vote.get("tete"):
        vote = valider_tete(vote, similarites, [vote["tete"], *autres_tetes])
    return vote


def _exclure_croisement(groupes: dict[int, list[int]], similarites: np.ndarray, noeuds: list[Noeud],
                        contrat: dict, journal: dict) -> dict[int, list[int]]:
    """Retire d'un groupe toute découpe plus proche, en moyenne, du groupe retenu d'un autre sujet.

    Décidé sur les groupes d'avant retrait, pour tous les sujets à la fois (l'ordre des sujets ne
    change rien au résultat). Les moyennes sont comparées telles quelles. Les rapporter à la cohésion
    de chaque groupe ferait perdre au groupe SERRÉ ses vrais membres dès que le voisin est lâche :
    cohésions 0,86 et 0,50, ressemblance croisée 0,545 — chaque membre du groupe serré paraîtrait
    « plus typique » du groupe lâche (+0,045 contre 0). La comparaison brute, elle, ne peut que vider
    le groupe lâche : un refus honnête plutôt qu'une identité fausse.
    """
    sujets = contrat.get("sujets") or []
    retraits: dict[int, set[int]] = {i: set() for i in groupes}
    for a, groupe_a in groupes.items():
        for c in groupe_a:
            autres_membres = [m for m in groupe_a if m != c]
            propre = _moyenne(similarites[c, autres_membres]) if autres_membres else None
            for b, groupe_b in groupes.items():
                if b == a or not groupe_b:
                    continue
                autre = _moyenne(similarites[c, groupe_b])
                if propre is not None and autre is not None and autre > propre:
                    retraits[a].add(c)
                    journal["exclusions"].append({
                        "decoupe": noeuds[c].id, "de": _texte(sujets[a].get("nom")),
                        "plus_proche_de": _texte(sujets[b].get("nom")),
                        "similarite_propre": _arrondi(propre), "similarite_autre": _arrondi(autre)})
    return {a: [m for m in g if m not in retraits[a]] for a, g in groupes.items()}


def _centralites(groupe: list[int], similarites: np.ndarray) -> dict[int, float]:
    return {c: float(np.mean([similarites[c, m] for m in groupe if m != c])) if len(groupe) > 1 else 1.0
            for c in groupe}


def nettetes(groupe: list[int], centralite: dict[int, float], exterieurs: Sequence[int],
             autres_groupes: Sequence[Sequence[int]], similarites: np.ndarray) -> dict[int, float]:
    """Netteté de chaque membre : sa silhouette entre le groupe et ce qui n'est PAS le sujet.

    b = la plus forte ressemblance moyenne du membre au fond du sujet (découpes écartées, non attribuées)
    ou au groupe retenu d'un autre sujet. Le médoïde seul ne suffit pas : mesuré le 15/11/2026, dans le
    groupe de Sharko, des découpes mêlées (Sharko collé à Marina et à Zig sur une affiche) étaient aussi
    centrales (0,69 à 0,72) que les vues de Sharko seul — une ancre mêlée ferait passer Zig dans la
    référence de Sharko. La netteté préfère le membre central qui ne ressemble qu'au sujet.
    """
    sortie: dict[int, float] = {}
    for m in groupe:
        references = [float(np.mean(similarites[m, list(g)])) for g in autres_groupes if len(g)]
        if exterieurs:
            references.append(float(np.mean(similarites[m, list(exterieurs)])))
        sortie[m] = silhouette(centralite[m], max(references)) if references else 1.0
    return sortie


def _ecrire_png(image: Image.Image, chemin: Path) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    provisoire = chemin.with_suffix(".tmp.png")
    image.convert("RGBA").save(provisoire, format="PNG")
    os.replace(provisoire, chemin)
    return chemin.resolve()


def _json_propre(valeur: Any) -> Any:
    if isinstance(valeur, dict):
        return {str(k): _json_propre(v) for k, v in valeur.items()}
    if isinstance(valeur, (list, tuple, set)):
        return [_json_propre(v) for v in valeur]
    if isinstance(valeur, (np.integer,)):
        return int(valeur)
    if isinstance(valeur, (np.floating,)):
        return float(valeur)
    if isinstance(valeur, Path):
        return str(valeur)
    return valeur


# ---------------------------------------------------------------------------
#  Point d'entrée
# ---------------------------------------------------------------------------

def etablir(contrat: dict, cache_dir: Path, journal_dir: Path | None = None, *,
            chercher: Chercher | None = None, telecharger: Telecharger | None = None,
            decouper: Decouper | None = None, embarquer: Embarquer | None = None,
            scorer_texte: ScorerTexte | None = None, decrire: Decrire | None = None,
            max_par_sujet: int = 16) -> dict:
    """Établit le dossier d'identité (`aurora.identite-visuelle.v1`) des sujets nommés du contrat.

    Ne lève pas pour une panne de réseau ou de modèle : chaque sujet touché reçoit `etabli=false` et la
    raison exacte (modèle local absent nommé, aucun résultat, aucun accord...), pour que l'appelant
    pose la question au lieu d'inventer. Les fonctions injectées remplacent réseau et modèles.
    """
    debut = time.monotonic()
    cache_dir = Path(cache_dir).expanduser().resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    contrat = contrat if isinstance(contrat, dict) else {}
    demande = _texte(contrat.get("demande"))
    sujets_contrat = contrat.get("sujets") if isinstance(contrat.get("sujets"), list) else []
    max_par_sujet = max(1, int(max_par_sujet))
    temps: dict[str, float] = {}
    journal: dict[str, Any] = {
        "schema_contrat": contrat.get("schema"), "parametres": {
            "max_par_sujet": max_par_sujet, "part_min_composante": PART_MIN_COMPOSANTE,
            "rapport_clip_min": RAPPORT_CLIP_MIN, "min_decoupes_groupe": MIN_DECOUPES_GROUPE,
            "min_domaines_groupe": MIN_DOMAINES_GROUPE, "part_bits_doublon": PART_BITS_DOUBLON,
            "silhouette_min": SILHOUETTE_MIN,
            "k": "max(1, min(n-2, round(sqrt(n))))"},
        "requetes": [], "telechargements": [], "doublons_images": [], "decoupes_erreurs": [],
        "doublons_decoupes": [], "decoupes": [], "votes": {}, "exclusions": [], "ancres": {},
        "pannes": [], "temps": temps,
    }
    if contrat.get("schema") not in (None, SCHEMA_CONTRAT):
        journal["avertissement"] = f"contrat de schéma {contrat.get('schema')!r}, {SCHEMA_CONTRAT!r} attendu"
    nommes = sujets_nommes(contrat)
    requetes = {i: construire_requetes(contrat, i) for i in nommes}
    etats: dict[int, dict[str, Any]] = {i: {"etabli": False, "raison": None, "ancres": [], "retenues": [],
                                           "domaines": [], "attributs": _attributs_non_evalues()} for i in nommes}

    def echec_global(phase: str, exc: BaseException | str) -> None:
        message = exc if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
        journal["pannes"].append({"phase": phase, "erreur": str(message)[:400]})
        for etat in etats.values():
            if not etat["raison"]:
                etat["raison"] = f"{phase} impossible : {str(message)[:300]}"

    noeuds: list[Noeud] = []
    sources: list[ImageSource] = []
    similarites = np.zeros((0, 0))
    if nommes:
        _dire(f"{len(nommes)} sujet(s) nommé(s) ; requêtes : " + " | ".join(r for i in nommes for r in requetes[i]))
        t = time.monotonic()
        candidats = _rechercher(requetes, chercher or chercher_par_defaut, 2 * max_par_sujet, journal)
        temps["recherche_s"] = round(time.monotonic() - t, 2)
        journal["candidats"] = {_texte(sujets_contrat[i].get("nom")): [
            {"url": c.url, "page": c.page, "domaine": domaine(c.page or c.url), "moteur": c.moteur,
             "requetes": c.requetes, "titre": c.titre} for c in liste] for i, liste in candidats.items()}
        _dire(f"recherche : {sum(len(v) for v in candidats.values())} candidats en {temps['recherche_s']} s")

        t = time.monotonic()
        copies = _telecharger(candidats, telecharger or telecharger_par_defaut, cache_dir / "_images",
                              max_par_sujet, journal)
        temps["telechargement_s"] = round(time.monotonic() - t, 2)
        _dire(f"téléchargement : {len(copies)} image(s) en {temps['telechargement_s']} s")
        if not copies:
            echec_global("recherche d'images réelles", "aucune image téléchargée (aucun résultat ou réseau coupé)")

        if copies:
            t = time.monotonic()
            sources = _fusionner_images(copies, journal)
            temps["fusion_doublons_s"] = round(time.monotonic() - t, 2)
            _dire(f"fusion des miroirs : {len(copies)} copies -> {len(sources)} images distinctes")
            t = time.monotonic()
            decoupeur = decouper or DecoupeurBiRefNet(cache_dir / "_detourages")
            try:
                noeuds = _decouper_images(sources, decoupeur, journal)
            except Exception as exc:  # noqa: BLE001 — modèle de détourage absent : dit, pas avalé
                echec_global("détourage", exc)
            finally:
                if hasattr(decoupeur, "fermer"):
                    decoupeur.fermer()
            temps["detourage_s"] = round(time.monotonic() - t, 2)
            if isinstance(decoupeur, DecoupeurBiRefNet):
                journal["detourage"] = {"modele": decoupeur.modele, "calcules": decoupeur.appels,
                                        "depuis_cache": decoupeur.depuis_cache, "fils": decoupeur.fils}
            _dire(f"détourage : {len(noeuds)} découpe(s) distincte(s) en {temps['detourage_s']} s")
            if sources and not noeuds and not journal["pannes"]:
                erreurs = journal["decoupes_erreurs"]
                echec_global("détourage", erreurs[0]["erreur"] if len(erreurs) == len(sources) else
                             f"aucune découpe d'au moins {PART_MIN_COMPOSANTE:.0%} de l'image dans les "
                             f"{len(sources)} images")

        if noeuds:
            carres = [carre_blanc(n.rgba) for n in noeuds]
            par_id = {s.id: s for s in sources}
            t = time.monotonic()
            try:
                _attribuer(noeuds, carres, contrat, nommes, par_id, scorer_texte or scorer_texte_par_defaut, journal)
            except Exception as exc:  # noqa: BLE001 — CLIP absent : qui-est-qui impossible, dit
                echec_global("attribution CLIP", exc)
                noeuds_attribues = False
            else:
                noeuds_attribues = True
            temps["attribution_s"] = round(time.monotonic() - t, 2)
            if noeuds_attribues:
                t = time.monotonic()
                try:
                    empreintes = np.asarray((embarquer or embarquer_par_defaut)(carres), dtype=np.float64)
                    if empreintes.ndim != 2 or empreintes.shape[0] != len(noeuds):
                        raise RuntimeError(f"empreintes de forme {empreintes.shape}, {len(noeuds)} lignes attendues")
                    empreintes /= np.maximum(np.linalg.norm(empreintes, axis=1, keepdims=True), 1e-12)
                    similarites = empreintes @ empreintes.T
                except Exception as exc:  # noqa: BLE001 — DINOv2 absent : aucun vote possible, dit
                    echec_global("empreintes DINOv2", exc)
                temps["empreintes_s"] = round(time.monotonic() - t, 2)

        if similarites.shape[0] == len(noeuds) and noeuds:
            t = time.monotonic()
            groupes: dict[int, list[int]] = {}
            votes = {i: choisir_tete([m for m, n in enumerate(noeuds) if n.sujet == i], noeuds, similarites)
                     for i in nommes}
            # Les découpes attribuées à un AUTRE sujet de la demande sont une autre identité, pas du hasard,
            # même quand elles n'ont pas formé de groupe (15/11/2026 : un second sujet à 2 découpes servait de
            # « fond » et faisait refuser le premier, pourtant cohérent).
            attribues = {j: [m for m, n in enumerate(noeuds) if n.sujet == j] for j in votes}
            tetes = [v["tete"] if v.get("tete") else attribues[j] for j, v in votes.items()]
            tetes = [t for t in tetes if t]
            for i in nommes:
                vote = valider_tete(votes[i], similarites, tetes, attribues.get(i, []))
                journal["votes"][_texte(sujets_contrat[i].get("nom"))] = vote
                if vote["groupe"]:
                    groupes[i] = vote["groupe"]
                else:
                    etats[i]["raison"] = vote["raison"]
            groupes = _exclure_croisement(groupes, similarites, noeuds, contrat, journal)
            for i, groupe in groupes.items():
                nom = _texte(sujets_contrat[i].get("nom"))
                domaines_groupe = {noeuds[m].domaine for m in groupe}
                if len(groupe) < MIN_DECOUPES_GROUPE or len(domaines_groupe) < MIN_DOMAINES_GROUPE:
                    etats[i]["raison"] = (f"groupe réduit à {len(groupe)} découpe(s) de {len(domaines_groupe)} "
                                          f"domaine(s) après retrait des découpes plus proches d'un autre sujet")
                    continue
                centralite = _centralites(groupe, similarites)
                dans_groupe = set(groupe)
                exterieurs = [m for m, n in enumerate(noeuds)
                              if (n.sujet is None or n.sujet == i) and m not in dans_groupe]
                nettete = nettetes(groupe, centralite, exterieurs,
                                   [g for j, g in groupes.items() if j != i], similarites)
                ordre = sorted(groupe, key=lambda m: (-nettete[m], -centralite[m]))
                medoide = ordre[0]
                autres = [m for m in ordre if noeuds[m].domaine != noeuds[medoide].domaine]
                second = sorted(autres, key=lambda m: (noeuds[m].bord, -nettete[m]))[0]
                dossier_sujet = cache_dir / _slug(nom)
                if any(_slug(_texte(sujets_contrat[j].get("nom"))) == _slug(nom) for j in nommes if j != i):
                    dossier_sujet = cache_dir / f"{_slug(nom)}-{i}"
                try:
                    ancres = [str(_ecrire_png(noeuds[m].rgba, dossier_sujet / f"ancre_{rang}_{noeuds[m].id[:10]}.png"))
                              for rang, m in enumerate((medoide, second), start=1)]
                    retenues = [{"chemin": str(_ecrire_png(noeuds[m].rgba, dossier_sujet / "retenues" / f"{noeuds[m].id}.png")),
                                 "domaine": noeuds[m].domaine, "source_url": noeuds[m].source_url,
                                 "score": round(nettete[m], 4)} for m in ordre]
                except OSError as exc:
                    etats[i]["raison"] = f"écriture des ancres impossible : {exc}"
                    continue
                compte: dict[str, int] = {}
                for m in groupe:
                    compte[noeuds[m].domaine] = compte.get(noeuds[m].domaine, 0) + 1
                etats[i].update({"etabli": True, "raison": None, "ancres": ancres, "retenues": retenues,
                                 "domaines": sorted(compte, key=lambda d: (-compte[d], d))})
                journal["ancres"][nom] = [{"decoupe": noeuds[m].id, "chemin": chemin, "domaine": noeuds[m].domaine,
                                           "nettete": round(nettete[m], 4), "centralite": round(centralite[m], 4),
                                           "corps_entier": not noeuds[m].bord}
                                          for m, chemin in zip((medoide, second), ancres)]
                journal["votes"][nom]["membres_finals"] = [
                    {"decoupe": noeuds[m].id, "nettete": round(nettete[m], 4), "centralite": round(centralite[m], 4)}
                    for m in ordre]
            temps["vote_s"] = round(time.monotonic() - t, 2)

        if decrire is not None:
            for i in nommes:
                if not etats[i]["etabli"]:
                    continue
                try:
                    etats[i]["attributs"] = _normaliser_attributs(
                        decrire(list(etats[i]["ancres"]), _texte(sujets_contrat[i].get("nature_en"))))
                except Exception as exc:  # noqa: BLE001 — vision muette : non évalué, jamais inventé
                    journal["pannes"].append({"phase": "attributs", "sujet": _texte(sujets_contrat[i].get("nom")),
                                              "erreur": f"{type(exc).__name__}: {exc}"[:300]})

    for n in noeuds:
        # Chaque découpe reste visible (petit PNG, une fois par contenu) : une décision du vote doit
        # pouvoir être relue image par image, retenue ou non.
        chemin_decoupe = cache_dir / "_decoupes" / f"{n.id}.png"
        try:
            if not chemin_decoupe.is_file():
                _ecrire_png(n.rgba, chemin_decoupe)
        except OSError:
            chemin_decoupe = None
        journal["decoupes"].append({
            "id": n.id, "chemin": str(chemin_decoupe) if chemin_decoupe else None, "image": n.image_id,
            "domaine": n.domaine, "source_url": n.source_url, "page": n.page,
            "bbox": n.bbox, "part_image": round(n.part, 4), "corps_entier": not n.bord,
            "sujet": _texte(sujets_contrat[n.sujet].get("nom")) if n.sujet is not None else None,
            "decision": n.decision, "scores_texte": n.scores_texte})

    for i in nommes:
        if not etats[i]["etabli"] and not etats[i]["raison"]:
            etats[i]["raison"] = "aucune découpe attribuée au sujet"
    dossier = {
        "schema": SCHEMA,
        "demande": demande,
        "sujets": [{
            "index": i,
            "nom": _texte(sujets_contrat[i].get("nom")),
            "nature_en": _texte(sujets_contrat[i].get("nature_en")),
            "etabli": bool(etats[i]["etabli"]),
            "raison": etats[i]["raison"],
            "ancres": etats[i]["ancres"],
            "retenues": etats[i]["retenues"],
            "attributs": etats[i]["attributs"],
            "requetes": requetes[i],
            "domaines": etats[i]["domaines"],
        } for i in nommes],
        "duree_s": round(time.monotonic() - debut, 2),
    }
    temps["total_s"] = dossier["duree_s"]
    for sujet in dossier["sujets"]:
        _dire(f"{sujet['nom']} : " + ("ÉTABLI, ancres " + ", ".join(sujet["ancres"]) if sujet["etabli"]
                                      else "non établi — " + str(sujet["raison"])))
    if journal_dir is not None:
        journal_dir = Path(journal_dir).expanduser().resolve()
        journal_dir.mkdir(parents=True, exist_ok=True)
        try:
            from importlib import import_module

            journal["modeles"] = import_module("modeles_locaux").etat_modeles() if "modeles_locaux" in sys.modules else None
        except Exception:  # noqa: BLE001
            journal["modeles"] = None
        (journal_dir / "identite.json").write_text(
            json.dumps(_json_propre(dossier | {"journal": journal}), ensure_ascii=False, indent=1), encoding="utf-8")
        try:
            ecrire_planche(dossier, journal_dir / "planche_identite.png", journal=journal)
        except Exception as exc:  # noqa: BLE001 — la planche est un témoin, pas une condition
            _dire(f"planche non écrite : {type(exc).__name__}: {exc}")
    return dossier


# ---------------------------------------------------------------------------
#  Planche de contact
# ---------------------------------------------------------------------------

def _police(taille: int):
    try:
        return ImageFont.load_default(size=taille)
    except TypeError:  # Pillow ancien : police bitmap sans taille
        return ImageFont.load_default()


def _damier(taille: tuple[int, int], case: int = 10) -> Image.Image:
    fond = Image.new("RGB", taille, (236, 236, 236))
    dessin = ImageDraw.Draw(fond)
    for y in range(0, taille[1], case):
        for x in range((y // case % 2) * case, taille[0], 2 * case):
            dessin.rectangle((x, y, x + case - 1, y + case - 1), fill=(206, 206, 206))
    return fond


def _vues_ecartees(sujet: dict, journal: dict) -> list[tuple[str, str, str]]:
    """Découpes attribuées au sujet mais non retenues, rangées par composante du vote (groupe de tête d'abord)."""
    nom = sujet.get("nom")
    retenues = {Path(r["chemin"]).stem for r in sujet.get("retenues", [])}
    vote = (journal.get("votes") or {}).get(nom) or {}
    proximite = vote.get("proximite_groupe_de_tete") or {}
    rang_composante = {i: k for k, c in enumerate(vote.get("composantes") or []) for i in c["decoupes"]}
    vues = []
    for d in journal.get("decoupes") or []:
        if d.get("sujet") != nom or d["id"] in retenues or not d.get("chemin"):
            continue
        rang = rang_composante.get(d["id"])
        etiquette = "isolée" if rang is None else ("tête" if rang == 0 else f"comp {rang}")
        vues.append((d["chemin"], f"{etiquette} · {d.get('domaine')} · {proximite.get(d['id'], '')}",
                     "tete" if rang == 0 else "ecartee"))
    vues.sort(key=lambda v: (v[2] != "tete", v[1]))
    return vues


def ecrire_planche(dossier: dict, chemin: Path, journal: dict | None = None, vignette: int = 168,
                   par_ligne: int = 8) -> Path:
    """Planche PNG, par sujet : ancres (cadre vert), découpes retenues (gris), puis — avec le journal — les
    découpes attribuées au sujet que le vote a écartées (cadre rouge ; orange pour le groupe de tête d'un
    sujet non établi), avec leur proximité moyenne au groupe de tête. Sur damier : l'alpha est visible."""
    police, police_titre = _police(12), _police(16)
    couleurs = {"ancre": (0, 150, 60), "retenue": (170, 170, 170), "tete": (230, 140, 0), "ecartee": (200, 40, 40)}
    blocs: list[tuple[str, list[list[tuple[str, str, str]]]]] = []
    for sujet in dossier.get("sujets", []):
        etat = "ÉTABLI" if sujet.get("etabli") else f"NON ÉTABLI — {sujet.get('raison')}"
        titre = f"{sujet.get('nom')} ({sujet.get('nature_en')}) : {etat}"
        domaine_par_id = {Path(r["chemin"]).stem[:10]: r.get("domaine") for r in sujet.get("retenues", [])}
        gardees = [(c, f"ancre {k} · {domaine_par_id.get(Path(c).stem.rsplit('_', 1)[-1], '?')}", "ancre")
                   for k, c in enumerate(sujet.get("ancres", []), 1)]
        gardees += [(r["chemin"], f"{r.get('domaine')} · {r.get('score')}", "retenue") for r in sujet.get("retenues", [])]
        rangees = [gardees]
        if journal:
            rangees.append(_vues_ecartees(sujet, journal))
        blocs.append((titre, rangees))
    hauteur_ligne = vignette + 22

    def lignes(vues: list) -> int:
        return max(1, math.ceil(len(vues) / par_ligne))

    hauteur = 12 + sum(30 + sum(lignes(v) * hauteur_ligne + 16 for v in rangees) for _, rangees in blocs)
    largeur = 12 + par_ligne * (vignette + 8)
    planche = Image.new("RGB", (largeur, max(hauteur, 60)), (255, 255, 255))
    dessin = ImageDraw.Draw(planche)
    y = 12
    for titre, rangees in blocs:
        dessin.text((12, y), titre[:170], fill=(20, 20, 20), font=police_titre)
        y += 30
        for numero, vues in enumerate(rangees):
            dessin.text((12, y), ("gardées (ancres, retenues)" if numero == 0 else "attribuées, écartées par le vote")
                        + ("" if vues else " : aucune"), fill=(90, 90, 90), font=police)
            y += 16
            for position, (fichier, legende, genre) in enumerate(vues):
                x = 12 + (position % par_ligne) * (vignette + 8)
                yy = y + (position // par_ligne) * hauteur_ligne
                case = _damier((vignette, vignette))
                try:
                    with Image.open(fichier) as image:
                        image = image.convert("RGBA")
                        image.thumbnail((vignette - 8, vignette - 8))
                        case.paste(image, ((vignette - image.width) // 2, (vignette - image.height) // 2), image)
                except Exception:  # noqa: BLE001 — fichier disparu : la case le montre vide
                    pass
                planche.paste(case, (x, yy))
                dessin.rectangle((x - 2, yy - 2, x + vignette + 1, yy + vignette + 1), outline=couleurs[genre],
                                 width=1 if genre == "retenue" else 3)
                dessin.text((x, yy + vignette + 4), legende[:34], fill=(40, 40, 40), font=police)
            y += lignes(vues) * hauteur_ligne
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    planche.save(chemin)
    return chemin


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dossier d'identité des sujets nommés par accord d'images réelles")
    parser.add_argument("--contrat", required=True, help="fichier JSON du contrat aurora.lecture-demande.v2")
    parser.add_argument("--cache", default=str(CACHE_PAR_DEFAUT),
                        help="dossier des images, détourages et ancres (hors de l'arborescence servie)")
    parser.add_argument("--journal", help="dossier où écrire identite.json et planche_identite.png")
    parser.add_argument("--max-par-sujet", type=int, default=16)
    args = parser.parse_args(argv)
    # Borne locale au processus CLI (lue par torch à son import) : le poste est partagé.
    os.environ.setdefault("OMP_NUM_THREADS", str(_fils_cpu()))
    sortie = sys.stdout
    try:
        contrat = json.loads(Path(args.contrat).read_text(encoding="utf-8"))
        if not isinstance(contrat, dict):
            raise ValueError("le contrat n'est pas un objet JSON")
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"schema": SCHEMA, "erreur": f"contrat illisible : {type(exc).__name__}: {exc}"},
                         ensure_ascii=False), file=sortie, flush=True)
        return 2
    with contextlib.redirect_stdout(sys.stderr):  # une bibliothèque bavarde ne casse pas la ligne JSON
        dossier = etablir(contrat, Path(args.cache), Path(args.journal) if args.journal else None,
                          max_par_sujet=args.max_par_sujet)
    print(json.dumps(_json_propre(dossier), ensure_ascii=False), file=sortie, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
