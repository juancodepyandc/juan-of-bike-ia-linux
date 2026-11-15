#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le milieu qu'un mouvement implique, construit autour du corps animé, et la porte qui le mesure.

15/11/2026 — « Zig et Sharko en version réaliste : Zig la hyène qui court et Sharko le requin qui
nage » a livré un requin qui nage à sec : aucune étape ne lisait le milieu, la composition
`mouvement_couleurs.glb` ne contenait aucun volume d'eau (part immergée : 0,0 à chaque instant) et
la revue sémantique l'écrivait conforme d'office. Ici, une loi générale, sans liste de mots :

  1. le milieu vient du contrat de demande (`milieu.matiere`, `milieu.relation`), jamais d'un
     mot-clé : l'ancienne lecture par mots (« couleur » pris pour un liquide) n'est jamais lue ;
  2. un sujet immergé dans un liquide reçoit un volume fermé construit autour de la boîte que son
     corps balaie RÉELLEMENT sur le clip, échantillonnée dans le fichier livré (au moins 24 instants,
     12 par seconde) après son recalage, et gonflée en proportion de sa longueur de corps au repos ;
  3. si l'empreinte de ce volume touche un sujet posé au sol, les sujets immergés sont déplacés
     selon l'axe HORIZONTAL de moindre pénétration (la verticale porte la gravité, donc la relation
     « sur » de l'autre sujet) ; le recalage déplacé est rendu ;
  4. ce qui est lu mais pas encore construit (à la surface, dans l'air, émissions, couples matière
     /relation sans constructeur) est rapporté « lu, non construit », jamais tu, et la porte refuse
     de certifier ce qu'elle ne peut pas mesurer ;
  5. `porte_milieu` mesure sur le fichier composé, pas sur les paramètres de construction : la
     surface et le fond sont lus sur les faces du volume à chaque instant, la part immergée est une
     part de SURFACE (sommets pondérés par l'aire : la densité du maillage ne biaise pas la mesure).

Le volume est écrit directement en glTF par `glb_io`, sans aller-retour Blender (les écrivains glTF
ne partagent pas la même convention verticale). f3d 2.5.0 n'applique que les cibles de morphing 0 à
3 et affiche les poids par défaut à t = 0 (sondes de l'enquête du 15/11) : la vague tient en DEUX
cibles en quadrature, a·sin(kx − ωt) = a·[sin kx · cos ωt − cos kx · sin ωt], et les poids par
défaut valent w(0). Les seuils de la porte forment une famille de cliquet séparée
(`modele/renforce/judge_ratchet_milieu.json`) : le cliquet global est au niveau 878 et ne peut plus
durcir ses seuils physiques, saturés.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animation_multi_sujets as ams  # noqa: E402
import echantillon_animation as ea  # noqa: E402
import glb_io  # noqa: E402

SCHEMA = "aurora.milieu-scene.v1"
SCHEMA_PORTE = "aurora.porte-milieu.v1"
NOM_VOLUME = "milieu_liquide"

# ── Placement autour du corps (proportions de la longueur de corps L au repos, étape 5 du plan) ──
MARGE_SURFACE = 0.05     # surface = plus haut sommet balayé + amplitude + 0,05 L
MARGE_FOND = 0.05        # fond = plus bas sommet balayé − 0,05 L
GONFLEMENT = 0.15        # empreinte = boîte balayée gonflée de 0,15 L de chaque côté
JEU_SEPARATION = 0.02    # jeu laissé entre l'empreinte déplacée et un sujet d'un autre milieu
SEPARATIONS_MAX = 8      # un déplacement peut pousser vers un autre sujet : essais bornés et rapportés

# ── Vague ──────────────────────────────────────────────────────────────────────────────────────
# Longueur d'onde = un corps ; cambrure k·a = 0,25, sous la limite de déferlement de Stokes
# (k·a ≈ 0,44) : la houle reste linéaire, donc la somme de deux cibles est exacte.
ONDE_PAR_CORPS = 1.0
CAMBRURE = 0.25
G = 9.81
CELLULES_PAR_ONDE = 16   # 16 échantillons par longueur d'onde : huit fois Nyquist
CELLULES_MAX = 192
CLES_PAR_PERIODE = 24    # poids LINEAR entre clés : l'amplitude ne creuse que de 1 − cos(π/24) = 0,86 %
# Lisibilité d'un volume vu en coupe (décision 5 du plan) dans un viewer qui ignore la transmission.
# Mesuré le 15/11/2026 : f3d 2.5.0 (VTK 9.3) ignore l'alpha de baseColorFactor — un volume BLEND à
# 0,45 sortait opaque et cachait le nageur, même avec --opacity=0.45 — mais lit l'alpha de la texture
# de couleur de base. L'alpha vit donc dans une texture blanche (facteur alpha 1) : le produit
# glTF facteur × texture vaut toujours 0,45 pour les viewers conformes (three.js).
ALPHA_VOLUME = 0.45
RUGOSITE_EAU = 0.05
TEXTURE_ALPHA_COTE = 4

# ── Échantillonnage temporel ───────────────────────────────────────────────────────────────────
INSTANTS_MIN = 24
FREQUENCE_HZ = 12.0

# ── Optique de l'eau pure aux longueurs d'onde dominantes des primaires (R 650, V 550, B 450 nm) ──
# absorption a (m⁻¹) : Pope & Fry 1997 ; diffusion b(λ) = 0,00288·(λ/500)^−4,32 m⁻¹ (Morel 1974),
# rétrodiffusion b_b = b/2. Le contrat ne nomme pas encore le liquide : l'eau pure est le liquide
# d'un nageur tant qu'aucun champ ne dit autre chose ; tout autre liquide passe par `optique=`.
EAU_PURE = {"nom": "eau_pure", "longueurs_onde_nm": [650.0, 550.0, 450.0],
            "absorption_m": [0.340, 0.0565, 0.00922], "ior": 1.33}

# ── Cliquet de la porte du milieu (famille séparée, seuils qui ne font que se resserrer) ──────
SEUILS_DEPART = {"tau_imm": 0.95, "tau_x": 0.02}
SEUILS_BUTEE = {"tau_imm": 0.99, "tau_x": 0.005}
CRANS_CLIQUET = 8

# ── f3d ────────────────────────────────────────────────────────────────────────────────────────
F3D = Path("/home/juan/.local/bin/f3d")
# 15/11/2026 : 15,6 Go sur 16,3 Go de mémoire vidéo étaient pris par d'autres travaux pendant le
# contrôle, et les gels du poste ont été requalifiés en panne GPU/pilote (Xid 109 + 31). Les rendus
# de contrôle passent donc par défaut par Mesa en logiciel (llvmpipe), qui ne touche pas au GPU.
ENV_RENDU_LOGICIEL = {"__GLX_VENDOR_LIBRARY_NAME": "mesa", "LIBGL_ALWAYS_SOFTWARE": "1",
                      "GALLIUM_DRIVER": "llvmpipe"}


# ── Petits outils ──────────────────────────────────────────────────────────────────────────────
def _cle_nom(nom: Any) -> str:
    texte = unicodedata.normalize("NFD", str(nom or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(texte.casefold().split())


def _classe_milieu(milieu: Any) -> str:
    """« immerge » (liquide + immergé, construit), « sol » (solide + sur : comportement existant,
    le recalage pose le point le plus bas au sol), « aucun » (rien de lu), sinon « non_construit »."""
    if not isinstance(milieu, dict):
        return "aucun"
    matiere, relation = milieu.get("matiere"), milieu.get("relation")
    if matiere is None and relation is None:
        return "aucun"
    if matiere == "liquide" and relation == "immerge":
        return "immerge"
    if matiere == "solide" and relation == "sur":
        return "sol"
    return "non_construit"


def _libelle_milieu(milieu: Any) -> str:
    milieu = milieu if isinstance(milieu, dict) else {}
    return f"{milieu.get('matiere')}/{milieu.get('relation')}"


def _recalage_parts(recalage: dict | None) -> tuple[float, np.ndarray]:
    if not recalage:
        return 1.0, np.zeros(3)
    return float(recalage.get("echelle", 1.0)), np.array(recalage.get("translation", [0.0, 0.0, 0.0]), dtype=np.float64)


def _flottants(valeurs: Iterable[float], chiffres: int = 6) -> list[float]:
    return [round(float(v), chiffres) for v in valeurs]


# ── Optique ────────────────────────────────────────────────────────────────────────────────────
def couleur_milieu_profond(optique: dict | None = None) -> list[float]:
    """Couleur linéaire d'un milieu optiquement profond : réflectance ∝ b_b / (a + b_b), max = 1.

    Pour l'eau pure : (0,0069 ; 0,084 ; 1) — le bleu de l'eau profonde vient de l'absorption du rouge
    (0,34 m⁻¹ à 650 nm contre 0,009 m⁻¹ à 450 nm) et de la diffusion en λ^−4,32, pas d'un choix de teinte.
    """
    optique = optique or EAU_PURE
    a = np.array(optique["absorption_m"], dtype=np.float64)
    lam = np.array(optique["longueurs_onde_nm"], dtype=np.float64)
    bb = 0.5 * 0.00288 * (lam / 500.0) ** -4.32
    r = bb / (a + bb)
    return _flottants(r / r.max(), 4)


def couleur_attenuation(optique: dict | None, distance_m: float) -> list[float]:
    """Lumière blanche transmise après `distance_m` de milieu : exp(−a·d) (Beer-Lambert)."""
    optique = optique or EAU_PURE
    a = np.array(optique["absorption_m"], dtype=np.float64)
    return _flottants(np.exp(-a * max(float(distance_m), 0.0)), 4)


def periode_houle(longueur_onde: float, profondeur: float, g: float = G) -> float:
    """Période d'une houle de gravité : ω² = g·k·tanh(k·h) (relation de dispersion, profondeur finie)."""
    k = 2.0 * math.pi / float(longueur_onde)
    return 2.0 * math.pi / math.sqrt(g * k * math.tanh(k * max(float(profondeur), 1e-9)))


# ── Construction du volume liquide ─────────────────────────────────────────────────────────────
def _lisse(u: np.ndarray) -> np.ndarray:
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def construire_volume_liquide(centre_xz, empreinte_xz, fond_y: float, surface_y: float, duree_s: float, *,
                              amplitude: float, longueur_onde: float, couleur, chemin,
                              direction_xz=(1.0, 0.0), periodes: int | None = None, alpha: float = ALPHA_VOLUME,
                              optique: dict | None = None, nom: str = NOM_VOLUME) -> dict[str, Any]:
    """Écrit un volume liquide FERMÉ (aucune arête de bord) dont la surface ondule, sans Blender.

    - Surface : grille au pas de λ/16 portant exactement 2 cibles de morphing en quadrature,
      A = a·f·sin(k·s) et B = −a·f·cos(k·s) (s = abscisse le long de `direction_xz`), avec leurs
      normales ; poids animés w = (cos ωt, sin ωt) ⇒ hauteur a·f·sin(k·s − ωt), une houle qui avance.
    - f s'annule en douceur (smoothstep, dérivée nulle au bord) sur une marge min(λ/2, ¼ du plus
      petit côté) : le bord de la surface ne bouge jamais, les parois restent planes et soudées.
    - Parois et fond ont leurs propres sommets (arêtes vives) aux positions EXACTES du bord de la
      grille : soudé par position, le volume est une variété fermée à tout instant.
    - Période = duree_s / n, n entier ≥ 1 tiré de la dispersion ω² = g·k·tanh(k·h) : la boucle est
      sans couture, w(0) = w(T), et les poids par défaut valent w(0) (ce que f3d montre à t = 0).
    - Matériau : alphaMode BLEND, alpha ≈ 0,45 porté par une texture de couleur de base blanche
      (seul alpha que lit f3d 2.5.0, mesuré), facteur = couleur du liquide ; UV planaires par face,
      au Jacobien non dégénéré ; KHR_materials_transmission 1,0, KHR_materials_ior (1,33 pour
      l'eau) et KHR_materials_volume (atténuation de Beer-Lambert sur l'épaisseur).
    - extras.aurora_milieu du nœud : matière, surface, fond, empreinte, vague.
    """
    optique = optique or EAU_PURE
    cx, cz = (float(v) for v in centre_xz)
    lx, lz = (float(v) for v in empreinte_xz)
    fond_y, surface_y, duree_s = float(fond_y), float(surface_y), float(duree_s)
    amplitude, longueur_onde = float(amplitude), float(longueur_onde)
    profondeur = surface_y - fond_y
    if lx <= 0 or lz <= 0 or profondeur <= 0:
        raise ValueError("volume liquide dégénéré : empreinte et profondeur doivent être positives")
    if duree_s <= 0 or longueur_onde <= 0:
        raise ValueError("volume liquide : durée et longueur d'onde doivent être positives")
    if not 0.0 <= amplitude < 0.5 * profondeur:
        raise ValueError("volume liquide : une vague d'amplitude ≥ profondeur/2 toucherait le fond")
    direction = np.array(direction_xz, dtype=np.float64)
    direction = direction / np.linalg.norm(direction) if np.linalg.norm(direction) > 0 else np.array([1.0, 0.0])
    k = 2.0 * math.pi / longueur_onde
    periode_physique = periode_houle(longueur_onde, profondeur)
    n = int(periodes) if periodes else max(1, int(round(duree_s / periode_physique)))
    n = max(1, n)
    periode = duree_s / n

    cellule = longueur_onde / CELLULES_PAR_ONDE
    nx = int(np.clip(math.ceil(lx / cellule), 4, CELLULES_MAX))
    nz = int(np.clip(math.ceil(lz / cellule), 4, CELLULES_MAX))
    xs = (cx + np.linspace(-0.5 * lx, 0.5 * lx, nx + 1)).astype(np.float32).astype(np.float64)
    zs = (cz + np.linspace(-0.5 * lz, 0.5 * lz, nz + 1)).astype(np.float32).astype(np.float64)
    sy, fy = float(np.float32(surface_y)), float(np.float32(fond_y))
    X, Z = np.meshgrid(xs, zs)                                     # (nz+1, nx+1) : ligne = z, colonne = x
    marge = min(0.5 * longueur_onde, 0.25 * min(lx, lz))
    f = _lisse(np.minimum(X - xs[0], xs[-1] - X) / marge) * _lisse(np.minimum(Z - zs[0], zs[-1] - Z) / marge)
    phase = k * ((X - cx) * direction[0] + (Z - cz) * direction[1])
    hauteur_a = amplitude * f * np.sin(phase)
    hauteur_b = -amplitude * f * np.cos(phase)
    bord = np.zeros_like(f, dtype=bool)
    bord[0, :] = bord[-1, :] = bord[:, 0] = bord[:, -1] = True
    hauteur_a[bord] = 0.0                                          # exactement nul : soudure garantie
    hauteur_b[bord] = 0.0
    da_dz, da_dx = np.gradient(hauteur_a, zs, xs)
    db_dz, db_dx = np.gradient(hauteur_b, zs, xs)

    positions, normales, faces, coordonnees_uv = [], [], [], []
    delta_a, delta_b, dnorm_a, dnorm_b = [], [], [], []
    compte = 0

    def bloc(points, normale_bloc, triangles_bloc, uv, da=None, db=None, na=None, nb=None):
        nonlocal compte
        points = np.asarray(points, dtype=np.float64)
        positions.append(points)
        normales.append(np.broadcast_to(np.asarray(normale_bloc, dtype=np.float64), points.shape) if np.ndim(normale_bloc) == 1
                        else np.asarray(normale_bloc, dtype=np.float64))
        coordonnees_uv.append(np.asarray(uv, dtype=np.float64))
        nuls = np.zeros_like(points)
        delta_a.append(nuls if da is None else da)
        delta_b.append(nuls if db is None else db)
        dnorm_a.append(nuls if na is None else na)
        dnorm_b.append(nuls if nb is None else nb)
        faces.append(np.asarray(triangles_bloc, dtype=np.int64) + compte)
        compte += len(points)

    # surface : sommet (i, j) = j·(nx+1) + i
    largeur = nx + 1
    haut = np.stack([X.ravel(), np.full(X.size, sy), Z.ravel()], axis=1)
    i, j = np.meshgrid(np.arange(nx), np.arange(nz))
    a_ = (j * largeur + i).ravel()
    b_ = a_ + largeur
    c_ = a_ + 1
    d_ = b_ + 1
    tri_haut = np.concatenate([np.stack([a_, b_, c_], 1), np.stack([c_, b_, d_], 1)])
    zero = np.zeros(X.size)
    plan_uv = lambda x, z: np.stack([(x - xs[0]) / lx, (z - zs[0]) / lz], axis=1)  # noqa: E731
    bloc(haut, [0.0, 1.0, 0.0], tri_haut, plan_uv(X.ravel(), Z.ravel()),
         da=np.stack([zero, hauteur_a.ravel(), zero], 1), db=np.stack([zero, hauteur_b.ravel(), zero], 1),
         na=np.stack([-da_dx.ravel(), zero, -da_dz.ravel()], 1), nb=np.stack([-db_dx.ravel(), zero, -db_dz.ravel()], 1))

    def paroi(coords_haut, normale, abscisse):
        m = len(coords_haut)
        bas = coords_haut.copy()
        bas[:, 1] = fy
        q = np.arange(m - 1)
        tri = np.concatenate([np.stack([q, q + 1, q + m], 1), np.stack([q + 1, q + m + 1, q + m], 1)])
        uv = np.concatenate([np.stack([abscisse, np.zeros(m)], 1), np.stack([abscisse, np.ones(m)], 1)])
        bloc(np.concatenate([coords_haut, bas]), normale, tri, uv)

    ligne = lambda xs_, zs_: np.stack([xs_, np.full(len(xs_), sy), zs_], axis=1)  # noqa: E731
    paroi(ligne(xs, np.full(len(xs), zs[0])), [0.0, 0.0, -1.0], (xs - xs[0]) / lx)
    paroi(ligne(xs, np.full(len(xs), zs[-1])), [0.0, 0.0, 1.0], (xs - xs[0]) / lx)
    paroi(ligne(np.full(len(zs), xs[0]), zs), [-1.0, 0.0, 0.0], (zs - zs[0]) / lz)
    paroi(ligne(np.full(len(zs), xs[-1]), zs), [1.0, 0.0, 0.0], (zs - zs[0]) / lz)
    # fond : éventail depuis le centre sur l'anneau du bord, mêmes subdivisions que les parois
    anneau = ([(x, zs[0]) for x in xs] + [(xs[-1], z) for z in zs[1:]]
              + [(x, zs[-1]) for x in xs[-2::-1]] + [(xs[0], z) for z in zs[-2:0:-1]])
    anneau_pts = np.array([[x, fy, z] for x, z in anneau])
    centre = np.array([[0.5 * (xs[0] + xs[-1]), fy, 0.5 * (zs[0] + zs[-1])]])
    r = len(anneau_pts)
    q = np.arange(r)
    fond = np.concatenate([centre, anneau_pts])
    bloc(fond, [0.0, -1.0, 0.0], np.stack([np.zeros(r, dtype=np.int64), 1 + q, 1 + (q + 1) % r], 1),
         plan_uv(fond[:, 0], fond[:, 2]))

    P = np.concatenate(positions).astype(np.float32)
    N = np.concatenate(normales).astype(np.float32)
    UV = np.concatenate(coordonnees_uv).astype(np.float32)
    F = np.concatenate(faces)
    # Orientation vers l'extérieur : la boîte est convexe, chaque face doit s'éloigner du centre.
    centre_boite = np.array([0.5 * (xs[0] + xs[-1]), 0.5 * (sy + fy), 0.5 * (zs[0] + zs[-1])])
    p0, p1, p2 = (P[F[:, m]].astype(np.float64) for m in range(3))
    sens = np.einsum("ij,ij->i", np.cross(p1 - p0, p2 - p0), (p0 + p1 + p2) / 3.0 - centre_boite)
    F[sens < 0] = F[sens < 0][:, [0, 2, 1]]
    cibles = [(np.concatenate(delta_a).astype(np.float32), np.concatenate(dnorm_a).astype(np.float32)),
              (np.concatenate(delta_b).astype(np.float32), np.concatenate(dnorm_b).astype(np.float32))]

    cles = n * CLES_PAR_PERIODE + 1
    temps = np.linspace(0.0, duree_s, cles).astype(np.float32)
    angle = 2.0 * math.pi * np.arange(cles) / CLES_PAR_PERIODE
    poids = np.stack([np.cos(angle), np.sin(angle)], axis=1)
    poids[::CLES_PAR_PERIODE] = [1.0, 0.0]                        # w(0) = w(T) au bit près
    poids = poids.astype(np.float32)

    blob = bytearray()
    vues: list[dict] = []
    accesseurs: list[dict] = []

    def ajouter(tableau, *, type_="VEC3", composante=5126, cible=None, bornes=False) -> int:
        while len(blob) % 4:
            blob.append(0)
        donnees = np.ascontiguousarray(tableau).tobytes()
        vue = {"buffer": 0, "byteOffset": len(blob), "byteLength": len(donnees)}
        if cible:
            vue["target"] = cible
        blob.extend(donnees)
        vues.append(vue)
        acc = {"bufferView": len(vues) - 1, "componentType": composante, "count": int(len(tableau)), "type": type_}
        if bornes:
            plat = np.asarray(tableau).reshape(len(tableau), -1)
            acc["min"], acc["max"] = plat.min(axis=0).tolist(), plat.max(axis=0).tolist()
        accesseurs.append(acc)
        return len(accesseurs) - 1

    i_pos = ajouter(P, cible=34962, bornes=True)
    i_nor = ajouter(N, cible=34962)
    i_uv = ajouter(UV, type_="VEC2", cible=34962)
    i_ind = ajouter(F.astype(np.uint32).ravel(), type_="SCALAR", composante=5125, cible=34963)
    i_cibles = [{"POSITION": ajouter(dp, cible=34962, bornes=True), "NORMAL": ajouter(dn, cible=34962)}
                for dp, dn in cibles]
    i_temps = ajouter(temps, type_="SCALAR", bornes=True)
    i_poids = ajouter(poids.ravel(), type_="SCALAR")
    from PIL import Image
    octet_alpha = int(round(float(np.clip(alpha, 0.0, 1.0)) * 255.0))
    tampon = io.BytesIO()
    Image.new("RGBA", (TEXTURE_ALPHA_COTE, TEXTURE_ALPHA_COTE), (255, 255, 255, octet_alpha)).save(tampon, "PNG")
    while len(blob) % 4:
        blob.append(0)
    vues.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(tampon.getvalue())})
    blob.extend(tampon.getvalue())
    i_image_vue = len(vues) - 1
    epaisseur = min(profondeur, lx, lz)
    extras = {"matiere": "liquide", "surface_y": sy, "fond_y": fy, "centre_xz": [cx, cz],
              "empreinte_xz": [lx, lz], "amplitude": amplitude, "longueur_onde": longueur_onde,
              "direction_xz": _flottants(direction), "periode_s": periode, "periodes": n,
              "periode_physique_s": periode_physique, "optique": optique.get("nom"),
              "alpha": octet_alpha / 255.0}
    doc = {
        "asset": {"version": "2.0", "generator": "AuroraIA milieu_scene"},
        "extensionsUsed": ["KHR_materials_ior", "KHR_materials_transmission", "KHR_materials_volume"],
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"name": nom, "mesh": 0, "extras": {"aurora_milieu": extras}}],
        "meshes": [{"name": nom, "weights": [1.0, 0.0], "extras": {"targetNames": ["onde_sin", "onde_cos"]},
                    "primitives": [{"attributes": {"POSITION": i_pos, "NORMAL": i_nor, "TEXCOORD_0": i_uv},
                                    "indices": i_ind, "material": 0, "mode": 4, "targets": i_cibles}]}],
        "images": [{"bufferView": i_image_vue, "mimeType": "image/png", "name": "alpha_milieu"}],
        "samplers": [{"magFilter": 9729, "minFilter": 9729, "wrapS": 33071, "wrapT": 33071}],
        "textures": [{"source": 0, "sampler": 0}],
        "materials": [{
            "name": f"{optique.get('nom', 'liquide')}", "alphaMode": "BLEND", "doubleSided": False,
            "pbrMetallicRoughness": {"baseColorFactor": [*(float(c) for c in couleur), 1.0],
                                     "baseColorTexture": {"index": 0},
                                     "metallicFactor": 0.0, "roughnessFactor": RUGOSITE_EAU},
            "extensions": {
                "KHR_materials_transmission": {"transmissionFactor": 1.0},
                "KHR_materials_ior": {"ior": float(optique.get("ior", 1.33))},
                "KHR_materials_volume": {"thicknessFactor": float(epaisseur), "attenuationDistance": float(epaisseur),
                                         "attenuationColor": couleur_attenuation(optique, epaisseur)}}}],
        "animations": [{"name": "milieu", "channels": [{"sampler": 0, "target": {"node": 0, "path": "weights"}}],
                        "samplers": [{"input": i_temps, "output": i_poids, "interpolation": "LINEAR"}]}],
        "accessors": accesseurs, "bufferViews": vues,
    }
    while len(blob) % 4:
        blob.append(0)
    doc["buffers"] = [{"byteLength": len(blob)}]
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    glb_io.save(str(chemin), doc, bytes(blob))
    return {"ok": True, "chemin": str(chemin), "sommets": int(len(P)), "triangles": int(len(F)), "cibles": 2,
            "grille": [nx, nz], **extras}


# ── Fermeture d'un maillage ────────────────────────────────────────────────────────────────────
def fermeture(points, triangles, *, tolerance: float | None = None) -> dict[str, Any]:
    """Arêtes de bord et non-manifold après soudure par position (sommets dédoublés pour les normales).

    Une variété fermée a chaque arête partagée par exactement deux triangles ; orientée de façon
    cohérente, chaque arête orientée n'apparaît qu'une fois, et son volume signé est positif.
    """
    p = np.asarray(points, dtype=np.float64)
    t = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    if not len(p) or not len(t):
        return {"ferme": False, "aretes_de_bord": 0, "aretes_non_manifold": 0, "euler": 0,
                "orientation_coherente": False, "volume_signe": 0.0, "triangles": 0}
    diagonale = float(np.linalg.norm(np.ptp(p, axis=0))) or 1.0
    pas = tolerance or diagonale * 1e-6
    _, soude = np.unique(np.round(p / pas).astype(np.int64), axis=0, return_inverse=True)
    tw = soude.reshape(-1)[t]
    garde = (tw[:, 0] != tw[:, 1]) & (tw[:, 1] != tw[:, 2]) & (tw[:, 0] != tw[:, 2])
    tw, t = tw[garde], t[garde]
    orientees = np.concatenate([tw[:, [0, 1]], tw[:, [1, 2]], tw[:, [2, 0]]])
    _, compte = np.unique(np.sort(orientees, axis=1), axis=0, return_counts=True)
    _, compte_oriente = np.unique(orientees, axis=0, return_counts=True)
    a, b, c = p[t[:, 0]], p[t[:, 1]], p[t[:, 2]]
    volume = float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)
    bord, multiples = int((compte == 1).sum()), int((compte > 2).sum())
    return {"ferme": bord == 0 and multiples == 0, "aretes_de_bord": bord, "aretes_non_manifold": multiples,
            "euler": int(len(np.unique(tw)) - len(compte) + len(tw)),
            "orientation_coherente": bool((compte_oriente == 1).all()), "volume_signe": volume,
            "triangles": int(len(tw))}


# ── Cliquet des seuils ─────────────────────────────────────────────────────────────────────────
def _chemin_cliquet(chemin: str | Path | None) -> Path:
    if chemin is not None:
        return Path(chemin)
    env = os.environ.get("AURORA_CLIQUET_MILIEU")
    return Path(env) if env else Path(__file__).resolve().parents[2] / "modele" / "renforce" / "judge_ratchet_milieu.json"


def seuils_du_niveau(niveau: int) -> dict[str, float]:
    """Famille monotone : du départ (0,95 ; 0,02) à la butée (0,99 ; 0,005) en huit crans réguliers."""
    f = min(max(int(niveau), 0), CRANS_CLIQUET) / CRANS_CLIQUET
    return {cle: SEUILS_DEPART[cle] + f * (SEUILS_BUTEE[cle] - SEUILS_DEPART[cle]) for cle in SEUILS_DEPART}


def lire_seuils_milieu(chemin: str | Path | None = None) -> dict[str, Any]:
    """Seuils de la porte : ceux du niveau lu, resserrés par d'éventuels seuils explicites, jamais relâchés.

    Un fichier illisible ne relâche rien : la porte prend alors la butée (les seuils les plus stricts).
    """
    p = _chemin_cliquet(chemin)
    if not p.is_file():
        return {**SEUILS_DEPART, "ratchet_level": 0, "famille": "milieu", "source": "depart"}
    try:
        etat = json.loads(p.read_text(encoding="utf-8"))
        niveau = etat.get("ratchet_level", 0)
        if not isinstance(etat, dict) or type(niveau) is not int or niveau < 0:
            raise ValueError("compteur invalide")
    except (OSError, ValueError, AttributeError) as exc:
        return {**SEUILS_BUTEE, "ratchet_level": None, "famille": "milieu", "source": str(p),
                "avertissement": f"cliquet illisible ({type(exc).__name__}) : seuils les plus stricts"}
    seuils = seuils_du_niveau(niveau)
    explicite_imm, explicite_x = etat.get("tau_imm"), etat.get("tau_x")
    if isinstance(explicite_imm, (int, float)):
        seuils["tau_imm"] = min(SEUILS_BUTEE["tau_imm"], max(seuils["tau_imm"], float(explicite_imm)))
    if isinstance(explicite_x, (int, float)):
        seuils["tau_x"] = max(SEUILS_BUTEE["tau_x"], min(seuils["tau_x"], float(explicite_x)))
    return {**seuils, "ratchet_level": niveau, "famille": "milieu", "source": str(p)}


@contextlib.contextmanager
def _verrou(chemin: Path):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.with_suffix(chemin.suffix + ".lock").open("a+b") as flux:
        if os.name == "nt":
            yield
            return
        import fcntl
        fcntl.flock(flux.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(flux.fileno(), fcntl.LOCK_UN)


def durcir_cliquet_milieu(chemin: str | Path | None = None) -> dict[str, Any]:
    """Un tour de boucle : niveau strictement croissant, seuils resserrés d'un cran (jusqu'à la butée).

    Jamais appelé par la porte elle-même : c'est la boucle d'amélioration qui avance le cliquet.
    """
    p = _chemin_cliquet(chemin)
    with _verrou(p):
        etat: dict[str, Any] = {}
        if p.is_file():
            etat = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(etat, dict) or type(etat.get("ratchet_level", 0)) is not int:
                raise ValueError("cliquet du milieu invalide ; conservé pour inspection")
        avant = lire_seuils_milieu(p) if p.is_file() else {**SEUILS_DEPART}
        niveau = int(etat.get("ratchet_level", 0)) + 1
        cran = seuils_du_niveau(niveau)
        etat.update({"famille": "milieu", "ratchet_level": niveau,
                     "history_runs": int(etat.get("history_runs", 0)) + 1,
                     "tau_imm": max(cran["tau_imm"], float(avant["tau_imm"])),
                     "tau_x": min(cran["tau_x"], float(avant["tau_x"]))})
        descripteur, temporaire = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=p.parent)
        try:
            with os.fdopen(descripteur, "w", encoding="utf-8") as flux:
                json.dump(etat, flux, ensure_ascii=False, indent=2)
            os.replace(temporaire, p)
        finally:
            Path(temporaire).unlink(missing_ok=True)
    return lire_seuils_milieu(p)


# ── Mesure d'un sujet animé ────────────────────────────────────────────────────────────────────
def mesurer_sujet(glb: str | Path, recalage: dict | None = None, *, echantillon: int | None = None) -> dict[str, Any]:
    """Boîte balayée sur le clip et boîte de repos, dans le repère de la scène (recalage appliqué)."""
    doc, blob = glb_io.load(str(glb))
    ech = ea.Echantillonneur(doc, blob, echantillon=echantillon)
    duree_s = ea.duree(doc, blob=blob)
    instants = ea.instants_reguliers(duree_s, minimum=INSTANTS_MIN, frequence_hz=FREQUENCE_HZ)
    balayee = ech.boite(instants if duree_s > 0 else [0.0])
    repos = ech.boite([None])
    if balayee is None or repos is None:
        raise ValueError(f"{glb} : aucun maillage dans la scène")
    echelle, translation = _recalage_parts(recalage)
    bmin, bmax = echelle * balayee[0] + translation, echelle * balayee[1] + translation
    rmin, rmax = echelle * repos[0] + translation, echelle * repos[1] + translation
    return {"duree_s": duree_s, "instants": int(len(instants)), "balayee": [bmin, bmax], "repos": [rmin, rmax],
            "longueur_corps": float((rmax - rmin).max())}


def _touche(pied_lo: np.ndarray, pied_hi: np.ndarray, fond_y: float, surface_y: float,
            boite: tuple[np.ndarray, np.ndarray]) -> bool:
    lo, hi = boite
    return bool(min(pied_hi[0], hi[0]) - max(pied_lo[0], lo[0]) > 0
                and min(pied_hi[1], hi[2]) - max(pied_lo[1], lo[2]) > 0
                and min(surface_y, hi[1]) - max(fond_y, lo[1]) > 0)


def _sortie_minimale(pied_lo: np.ndarray, pied_hi: np.ndarray, boite: tuple[np.ndarray, np.ndarray],
                     jeu: float) -> tuple[np.ndarray, str, float]:
    """Plus petit déplacement horizontal de l'empreinte qui la sort de la boîte (axe de moindre pénétration)."""
    lo, hi = boite
    candidats = [(float(hi[0] - pied_lo[0]) + jeu, "+x", np.array([1.0, 0.0, 0.0])),
                 (float(pied_hi[0] - lo[0]) + jeu, "-x", np.array([-1.0, 0.0, 0.0])),
                 (float(hi[2] - pied_lo[1]) + jeu, "+z", np.array([0.0, 0.0, 1.0])),
                 (float(pied_hi[1] - lo[2]) + jeu, "-z", np.array([0.0, 0.0, -1.0]))]
    distance, axe, sens = min(candidats, key=lambda c: c[0])
    return sens * distance, axe, distance


# ── Composition avec les milieux ───────────────────────────────────────────────────────────────
def composer_avec_milieux(entrees: list[dict[str, Any]], sortie: str | Path, *,
                          composer: Callable[[list, Any], dict] | None = None, echantillon: int | None = None,
                          chemin_cliquet: str | Path | None = None, seuils: dict | None = None,
                          rapport: str | Path | None = None) -> dict[str, Any]:
    """Compose les sujets animés ET le milieu que chacun demande dans UN seul GLB, puis le juge.

    entrees : [{"glb", "nom", "recalage": dict|None, "milieu": {"matiere", "relation"}, "emissions"?}].
    Le volume liquide devient une entrée de plus du compositeur : sa piste de poids rejoint
    l'animation commune. Rend {"ok", "sortie", "milieux", "deplacements", "porte", ...}.
    """
    composer = composer or ams.composer
    sortie = Path(sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    entrees = [{**e, "recalage": json.loads(json.dumps(e.get("recalage"))) if e.get("recalage") else None}
               for e in entrees]
    for rang, e in enumerate(entrees):
        e["nom"] = str(e.get("nom") or f"sujet_{rang + 1}")[:60]
    debut = time.monotonic()
    mesures = [mesurer_sujet(e["glb"], e.get("recalage"), echantillon=echantillon) for e in entrees]
    classes = [_classe_milieu(e.get("milieu")) for e in entrees]
    milieux: list[dict[str, Any]] = []
    for e, classe in zip(entrees, classes):
        milieu = e.get("milieu") if isinstance(e.get("milieu"), dict) else {}
        etat = {"immerge": "construit", "sol": "sol_existant", "aucun": "aucun_milieu_lu",
                "non_construit": "lu, non construit"}[classe]
        detail = {"immerge": "volume liquide fermé construit autour de la boîte balayée",
                  "sol": "comportement existant : le recalage pose le point le plus bas au sol",
                  "aucun": "le contrat ne dit aucun milieu pour ce sujet",
                  "non_construit": f"milieu « {_libelle_milieu(milieu)} » lu, aucun constructeur pour l'instant"}[classe]
        milieux.append({"sujet": e["nom"], "matiere": milieu.get("matiere"), "relation": milieu.get("relation"),
                        "justification": milieu.get("justification"), "etat": etat, "detail": detail})
        if e.get("emissions"):
            milieux.append({"sujet": e["nom"], "emissions": e["emissions"], "etat": "lu, non construit",
                            "detail": "émissions lues, aucun constructeur dans cette composition"})

    immerges = [k for k, c in enumerate(classes) if c == "immerge"]
    obstacles = [k for k, c in enumerate(classes) if c in ("sol", "aucun")]
    deplacements: list[dict[str, Any]] = []
    volume: dict[str, Any] | None = None
    erreur_volume = None
    a_composer = [{"glb": str(e["glb"]), "nom": e["nom"], "recalage": e.get("recalage")} for e in entrees]
    if immerges:
        bmin = np.min([mesures[k]["balayee"][0] for k in immerges], axis=0)
        bmax = np.max([mesures[k]["balayee"][1] for k in immerges], axis=0)
        corps = max(mesures[k]["longueur_corps"] for k in immerges)
        longueur_onde = ONDE_PAR_CORPS * corps
        amplitude = CAMBRURE * longueur_onde / (2.0 * math.pi)
        surface_y = float(bmax[1] + amplitude + MARGE_SURFACE * corps)
        fond_y = float(bmin[1] - MARGE_FOND * corps)
        pied_lo = bmin[[0, 2]] - GONFLEMENT * corps
        pied_hi = bmax[[0, 2]] + GONFLEMENT * corps
        for _ in range(SEPARATIONS_MAX):
            intrus = [k for k in obstacles if _touche(pied_lo, pied_hi, fond_y, surface_y, mesures[k]["balayee"])]
            if not intrus:
                break
            k = intrus[0]
            vecteur, axe, distance = _sortie_minimale(pied_lo, pied_hi, mesures[k]["balayee"], JEU_SEPARATION * corps)
            pied_lo, pied_hi = pied_lo + vecteur[[0, 2]], pied_hi + vecteur[[0, 2]]
            for m in immerges:
                echelle, translation = _recalage_parts(entrees[m].get("recalage"))
                entrees[m]["recalage"] = {"echelle": echelle, "translation": _flottants(translation + vecteur, 9)}
                mesures[m]["balayee"] = [mesures[m]["balayee"][0] + vecteur, mesures[m]["balayee"][1] + vecteur]
                a_composer[m]["recalage"] = entrees[m]["recalage"]
            deplacements.append({"sujets": [entrees[m]["nom"] for m in immerges], "contre": entrees[k]["nom"],
                                 "axe": axe, "vecteur_m": _flottants(vecteur), "distance_m": round(distance, 6),
                                 "raison": f"l'empreinte du milieu liquide touchait {entrees[k]['nom']}, "
                                           f"posé dans un autre milieu"})
        else:
            if any(_touche(pied_lo, pied_hi, fond_y, surface_y, mesures[k]["balayee"]) for k in obstacles):
                deplacements.append({"echec": f"séparation impossible en {SEPARATIONS_MAX} déplacements ; "
                                              "l'intrusion est mesurée par la porte"})
        duree_scene = max((m["duree_s"] for m in mesures), default=0.0)
        if duree_scene <= 0:
            duree_scene = periode_houle(longueur_onde, surface_y - fond_y)
        try:
            volume = construire_volume_liquide(
                0.5 * (pied_lo + pied_hi), pied_hi - pied_lo, fond_y, surface_y, duree_scene,
                amplitude=amplitude, longueur_onde=longueur_onde, couleur=couleur_milieu_profond(EAU_PURE),
                chemin=sortie.with_name(f"{sortie.stem}_{NOM_VOLUME}.glb"))
            volume["longueur_corps_m"] = corps
            a_composer.append({"glb": volume["chemin"], "nom": NOM_VOLUME, "recalage": None})
        except (ValueError, OSError) as exc:          # rapporté, et la porte refusera l'absence d'eau
            erreur_volume = f"{type(exc).__name__}: {exc}"[:300]

    composition = composer(a_composer, sortie)
    attentes = {"sujets": [{"racine": e["nom"], "nom": e["nom"], "milieu": e.get("milieu"),
                            "emissions": e.get("emissions")} for e in entrees],
                "instants": max(m["instants"] for m in mesures) if mesures else INSTANTS_MIN}
    compose = Path(str(composition.get("sortie") or sortie))
    if composition.get("ok") and compose.is_file():
        porte = porte_milieu(compose, attentes, seuils=seuils, chemin_cliquet=chemin_cliquet, echantillon=echantillon)
    else:
        porte = {"schema": SCHEMA_PORTE, "ok": False, "glb": str(compose), "mesures": {},
                 "raisons": [f"composition échouée : {composition.get('error') or 'aucun fichier écrit'}"]}
    resultat = {
        "schema": SCHEMA, "ok": bool(composition.get("ok")) and bool(porte.get("ok")),
        "sortie": str(composition.get("sortie") or sortie), "milieux": milieux, "deplacements": deplacements,
        "volume": volume, "erreur_volume": erreur_volume,
        "entrees": [{"glb": str(e["glb"]), "nom": e["nom"], "recalage": e.get("recalage"), "milieu": e.get("milieu")}
                    for e in entrees],
        "sujets_mesures": [{"nom": e["nom"], "duree_s": m["duree_s"], "instants": m["instants"],
                            "longueur_corps_m": round(m["longueur_corps"], 6),
                            "boite_balayee_m": [_flottants(m["balayee"][0]), _flottants(m["balayee"][1])]}
                           for e, m in zip(entrees, mesures)],
        "composition": composition, "porte": porte, "duree_calcul_s": round(time.monotonic() - debut, 2)}
    if rapport:
        Path(rapport).parent.mkdir(parents=True, exist_ok=True)
        Path(rapport).write_text(json.dumps(resultat, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultat


# ── Porte du milieu ────────────────────────────────────────────────────────────────────────────
def _une_hauteur_par_xz(points: np.ndarray, garder: Callable) -> np.ndarray:
    pas = max(float(np.linalg.norm(np.ptp(points, axis=0))), 1.0) * 1e-7
    _, inverse = np.unique(np.round(points[:, [0, 2]] / pas).astype(np.int64), axis=0, return_inverse=True)
    inverse = inverse.reshape(-1)
    xz = np.zeros((inverse.max() + 1, 2))
    xz[inverse] = points[:, [0, 2]]
    y = np.full(len(xz), -np.inf if garder is np.maximum else np.inf)
    garder.at(y, inverse, points[:, 1])
    return np.stack([xz[:, 0], y, xz[:, 1]], axis=1)


class _SurfaceLiquide:
    """Le liquide tel que le fichier le montre à un instant : surface et fond lus sur ses faces.

    Dedans ⟺ (x, z) dans l'empreinte (enveloppe des sommets de la surface), au-dessus du fond et
    sous la surface animée à ce (x, z, t). Seuls les points dans la bande [min, max] de la surface
    (ou du fond) sont interpolés : les autres sont tranchés par comparaison directe.
    """

    def __init__(self, sommets: np.ndarray, triangles: np.ndarray):
        self.valide = False
        if not len(triangles):
            return
        a, b, c = (sommets[triangles[:, k]] for k in range(3))
        normales = np.cross(b - a, c - a)
        normes = np.linalg.norm(normales, axis=1)
        utiles = normes > 0
        ny = np.zeros(len(normales))
        ny[utiles] = normales[utiles, 1] / normes[utiles]
        haut = np.unique(triangles[utiles & (ny > 0.5)].ravel())
        bas = np.unique(triangles[utiles & (ny < -0.5)].ravel())
        if len(haut) < 3 or len(bas) < 3:
            return
        self.indices_haut = haut
        self.haut = _une_hauteur_par_xz(sommets[haut], np.maximum)
        self.bas = _une_hauteur_par_xz(sommets[bas], np.minimum)
        xz = self.haut[:, [0, 2]]
        self.lo, self.hi = xz.min(axis=0), xz.max(axis=0)
        aire_boite = float(np.prod(self.hi - self.lo))
        if aire_boite <= 0:
            return
        from scipy.spatial import ConvexHull, Delaunay
        try:
            aire = float(ConvexHull(xz).volume)
        except Exception:  # noqa: BLE001 — points alignés : pas d'empreinte
            return
        self.rectangle = abs(aire - aire_boite) <= 1e-6 * aire_boite
        self._triangulation = None if self.rectangle else Delaunay(xz)
        self.h_min, self.h_max = float(self.haut[:, 1].min()), float(self.haut[:, 1].max())
        self.b_min, self.b_max = float(self.bas[:, 1].min()), float(self.bas[:, 1].max())
        self._interpolateurs: dict[str, Any] = {}
        self.valide = True

    def _hauteur(self, quoi: str, xz: np.ndarray) -> np.ndarray:
        if quoi not in self._interpolateurs:
            from scipy.interpolate import LinearNDInterpolator
            source = self.haut if quoi == "haut" else self.bas
            self._interpolateurs[quoi] = LinearNDInterpolator(source[:, [0, 2]], source[:, 1])
        return self._interpolateurs[quoi](xz)

    def contient(self, p: np.ndarray) -> np.ndarray:
        if not self.valide or not len(p):
            return np.zeros(len(p), dtype=bool)
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        dedans = (x >= self.lo[0]) & (x <= self.hi[0]) & (z >= self.lo[1]) & (z <= self.hi[1])
        if not self.rectangle and dedans.any():
            idx = np.nonzero(dedans)[0]
            dedans[idx] = self._triangulation.find_simplex(p[idx][:, [0, 2]]) >= 0
        sous = y <= self.h_min
        bande = dedans & ~sous & (y <= self.h_max)
        if bande.any():
            with np.errstate(invalid="ignore"):
                sous[bande] = y[bande] <= self._hauteur("haut", p[bande][:, [0, 2]])
        dessus = y >= self.b_max
        bande = dedans & ~dessus & (y >= self.b_min)
        if bande.any():
            with np.errstate(invalid="ignore"):
                dessus[bande] = y[bande] >= self._hauteur("bas", p[bande][:, [0, 2]])
        return dedans & sous & dessus


def _triangles_noeud(doc: dict, blob: bytes, noeud: dict) -> np.ndarray:
    morceaux, decalage = [], 0
    for prim in doc["meshes"][noeud["mesh"]].get("primitives", []):
        morceaux.append(ea.triangles(doc, blob, prim) + decalage)
        decalage += int(doc["accessors"][prim["attributes"]["POSITION"]]["count"])
    return np.concatenate(morceaux) if morceaux else np.zeros((0, 3), dtype=np.int64)


def alpha_texture(doc: dict, blob: bytes, indice_texture: int | None) -> float | None:
    """Alpha moyen de l'image d'une texture embarquée (1 pour une image sans alpha) ; None si illisible."""
    if indice_texture is None:
        return None
    try:
        source = doc["textures"][int(indice_texture)]["source"]
        from PIL import Image
        with Image.open(io.BytesIO(glb_io.image_bytes(doc, blob, source))) as image:
            if "A" not in image.getbands():
                return 1.0
            return float(np.asarray(image.getchannel("A"), dtype=np.float64).mean() / 255.0)
    except Exception:  # noqa: BLE001 — image externe ou corrompue : alpha inconnu, dit tel quel
        return None


def _translucide(doc: dict, blob: bytes, noeud: dict) -> dict[str, Any]:
    """Translucidité au sens glTF (facteur × texture, ou transmission) ET telle que f3d la montre.

    Mesuré le 15/11/2026 : f3d 2.5.0 ignore l'alpha du facteur et la transmission ; seul l'alpha de la
    texture de couleur de base rend le liquide transparent. Un volume « translucide » que f3d dessine
    opaque cache le sujet immergé : la porte le refuse.
    """
    lu: dict[str, Any] = {"alphaMode": None, "alpha_facteur": None, "alpha_texture": None, "alpha": None,
                          "transmission": None}
    for prim in doc["meshes"][noeud["mesh"]].get("primitives", []):
        if "material" not in prim:
            continue
        mat = doc["materials"][prim["material"]]
        pbr = mat.get("pbrMetallicRoughness") or {}
        lu["alphaMode"] = mat.get("alphaMode", "OPAQUE")
        lu["alpha_facteur"] = float(pbr.get("baseColorFactor", [1, 1, 1, 1])[3])
        lu["alpha_texture"] = alpha_texture(doc, blob, (pbr.get("baseColorTexture") or {}).get("index"))
        lu["alpha"] = lu["alpha_facteur"] * (1.0 if lu["alpha_texture"] is None else lu["alpha_texture"])
        lu["transmission"] = float(((mat.get("extensions") or {}).get("KHR_materials_transmission") or {})
                                   .get("transmissionFactor", 0.0))
    melange = lu["alphaMode"] == "BLEND" and lu["alpha"] is not None and lu["alpha"] < 1.0
    lu["translucide"] = bool(melange or (lu["transmission"] or 0.0) > 0.0)
    lu["translucide_f3d"] = bool(lu["alphaMode"] == "BLEND" and lu["alpha_texture"] is not None
                                 and lu["alpha_texture"] < 1.0)
    return lu


def _orientation(points: np.ndarray, poids: np.ndarray) -> tuple[np.ndarray, float]:
    """Centre surfacique et angle (degrés) entre l'axe long du corps et le plan horizontal."""
    centre = (poids[:, None] * points).sum(axis=0) / poids.sum()
    q = points - centre
    covariance = (q * poids[:, None]).T @ q / poids.sum()
    _, vecteurs = np.linalg.eigh(covariance)
    return centre, float(np.degrees(np.arcsin(min(1.0, abs(float(vecteurs[1, -1]))))))


def porte_milieu(glb_path: str | Path, attentes: dict[str, Any] | None, *, seuils: dict | None = None,
                 chemin_cliquet: str | Path | None = None, echantillon: int | None = None) -> dict[str, Any]:
    """Juge, sur le fichier composé, que chaque sujet est dans le milieu que son mouvement implique.

    attentes : {"sujets": [{"racine"|"nom", "milieu": {...}, "emissions"?}], "instants"?} — le contrat
    de demande v2 convient tel quel quand ses noms sont ceux des racines de la composition.
    M1 nœud liquide présent, fermé (à 4 instants), translucide ; M2 part de surface de chaque sujet
    immergé dans le volume ≥ τ_imm à CHAQUE instant (≥ 24) ; M4 intrusion des autres sujets ≤ τ_x ;
    M5 mouvement de surface mesuré dans le fichier ; M6 ≤ 4 cibles (f3d n'en applique que 4),
    1 animation, w(0) = w(T), poids par défaut = w(0). Rapportés sans bloquer : orientation du corps
    et trajet du centre des sujets immergés (un nageur debout qui mime n'est PAS refusé ici).
    """
    attentes = attentes or {}
    seuils = dict(seuils) if seuils else lire_seuils_milieu(chemin_cliquet)
    tau_imm, tau_x = float(seuils["tau_imm"]), float(seuils["tau_x"])
    doc, blob = glb_io.load(str(glb_path))
    ech = ea.Echantillonneur(doc, blob, echantillon=echantillon)
    ech_eau = ech if echantillon is None else ea.Echantillonneur(doc, blob)
    noeuds = doc.get("nodes") or []
    raisons: list[str] = []

    def sous_arbre(racine: int) -> list[int]:
        vus, pile = [], [racine]
        while pile:
            i = pile.pop()
            vus.append(i)
            pile.extend(noeuds[i].get("children", []))
        return vus

    liquides = [i for i in ech.maillages
                if ((noeuds[i].get("extras") or {}).get("aurora_milieu") or {}).get("matiere") == "liquide"]
    racines_par_nom: dict[str, list[int]] = {}
    for r in ech.racines_scene:
        racines_par_nom.setdefault(_cle_nom(noeuds[r].get("name")), []).append(r)
    maillages_scene = set(ech.maillages) - set(liquides)
    sujets = []
    for k, attendu in enumerate(attentes.get("sujets") or []):
        nom = str(attendu.get("racine") or attendu.get("nom") or f"sujet_{k + 1}")
        classe = _classe_milieu(attendu.get("milieu"))
        mailles = [i for r in racines_par_nom.get(_cle_nom(nom), []) for i in sous_arbre(r) if i in maillages_scene]
        sujet = {"nom": nom, "classe": classe, "milieu": attendu.get("milieu"), "noeuds": mailles, "parts": [],
                 "centres": [], "angles": []}
        if mailles:
            sujet["poids"] = np.concatenate([ea.aires_sommets(doc, blob, int(noeuds[i]["mesh"]), echantillon=echantillon)
                                             for i in mailles])
        else:
            raisons.append(f"{nom} : introuvable dans le fichier (aucune racine de ce nom avec un maillage)")
        if classe == "non_construit":
            raisons.append(f"{nom} : milieu « {_libelle_milieu(attendu.get('milieu'))} » lu, non construit — "
                           "rien à mesurer, donc rien à certifier")
        if attendu.get("emissions"):
            raisons.append(f"{nom} : émissions lues, non construites — rien à mesurer, donc rien à certifier")
        sujets.append(sujet)
    mesures: dict[str, Any] = {}
    requis = any(s["classe"] == "immerge" for s in sujets)

    # M1 — nœud liquide présent, fermé, translucide
    m1: dict[str, Any] = {"requis": requis, "noeuds_liquides": [noeuds[i].get("name") for i in liquides]}
    triangles_eau = {i: _triangles_noeud(doc, blob, noeuds[i]) for i in liquides}
    if liquides:
        lus = [_translucide(doc, blob, noeuds[i]) for i in liquides]
        m1.update({"translucide": all(lu["translucide"] for lu in lus),
                   "translucide_f3d": all(lu["translucide_f3d"] for lu in lus), "materiaux": lus})
    elif requis:
        raisons.append("M1 : aucun volume liquide dans le fichier alors qu'un sujet doit y être immergé")

    duree_s = ea.duree(doc, blob=blob)
    instants = ea.instants_reguliers(duree_s, minimum=max(INSTANTS_MIN, int(attentes.get("instants") or 0)),
                                     frequence_hz=FREQUENCE_HZ)
    controles_fermeture = {0, len(instants) // 4, len(instants) // 2, (3 * len(instants)) // 4}
    pire_fermeture: dict[str, Any] | None = None
    hauteurs_surface: dict[int, list[np.ndarray]] = {i: [] for i in liquides}
    indices_haut: dict[int, np.ndarray] = {}
    noeuds_sujets = sorted({i for s in sujets for i in s["noeuds"]})
    for rang, t in enumerate(instants):
        t = float(t)
        points = dict(ech.points(t, noeuds_sujets)) if noeuds_sujets else {}
        points_eau = dict(ech_eau.points(t, liquides)) if liquides else {}
        surfaces = []
        for i in liquides:
            surfaces.append(_SurfaceLiquide(points_eau[i], triangles_eau[i]))
            if rang in controles_fermeture:
                ferme = fermeture(points_eau[i], triangles_eau[i])
                if pire_fermeture is None or (ferme["aretes_de_bord"] + ferme["aretes_non_manifold"]
                                              > pire_fermeture["aretes_de_bord"] + pire_fermeture["aretes_non_manifold"]):
                    pire_fermeture = {**ferme, "instant_s": t, "noeud": noeuds[i].get("name")}
            if i not in indices_haut and surfaces[-1].valide:
                indices_haut[i] = surfaces[-1].indices_haut
            if i in indices_haut:
                hauteurs_surface[i].append(points_eau[i][indices_haut[i], 1].copy())
        for s in sujets:
            if not s["noeuds"]:
                continue
            p = np.concatenate([points[i] for i in s["noeuds"]])
            dedans = np.zeros(len(p), dtype=bool)
            for surface in surfaces:
                dedans |= surface.contient(p)
            s["parts"].append(float(s["poids"][dedans].sum() / max(float(s["poids"].sum()), 1e-30)))
            if s["classe"] == "immerge":
                centre, angle = _orientation(p, s["poids"])
                s["centres"].append(centre)
                s["angles"].append(angle)

    if liquides:
        m1["fermeture"] = pire_fermeture
        m1["ferme"] = bool(pire_fermeture and pire_fermeture["ferme"])
        m1["ok"] = bool(m1["ferme"] and m1["translucide"] and m1["translucide_f3d"])
        if not m1["ferme"]:
            raisons.append(f"M1 : volume liquide ouvert ({(pire_fermeture or {}).get('aretes_de_bord')} arêtes de bord, "
                           f"{(pire_fermeture or {}).get('aretes_non_manifold')} non manifold)")
        if not m1["translucide"]:
            raisons.append("M1 : volume liquide opaque (ni alpha BLEND < 1 ni transmission)")
        elif not m1["translucide_f3d"]:
            raisons.append("M1 : volume liquide opaque dans f3d (son alpha n'est pas porté par la texture de "
                           "couleur de base, le seul que f3d 2.5.0 lit) : le sujet immergé y serait caché")
    else:
        m1["ok"] = not requis
    mesures["M1"] = m1

    # M2 — immersion de chaque sujet immergé ; M4 — intrusion des autres
    m2, m4, rapports = {}, {}, {}
    for s in sujets:
        if not s["noeuds"]:
            continue
        parts = np.array(s["parts"])
        if s["classe"] == "immerge":
            pire = int(np.argmin(parts))
            ok = bool(parts.min() >= tau_imm)
            m2[s["nom"]] = {"part_min": round(float(parts.min()), 6), "part_moyenne": round(float(parts.mean()), 6),
                            "instant_min_s": round(float(instants[pire]), 4), "seuil": tau_imm,
                            "instants": int(len(parts)), "parts": _flottants(parts, 4), "ok": ok}
            if not ok:
                raisons.append(f"M2 : {s['nom']} n'est immergé qu'à {parts.min():.3f} de sa surface à "
                               f"t = {instants[pire]:.2f} s (seuil {tau_imm:.3f})")
            centres = np.array(s["centres"])
            angles = np.array(s["angles"])
            pas_xz = np.linalg.norm(np.diff(centres[:, [0, 2]], axis=0), axis=1) if len(centres) > 1 else np.zeros(0)
            moyen = float(angles.mean())
            rapports[s["nom"]] = {
                "angle_axe_long_horizontale_deg": {"moyen": round(moyen, 2), "min": round(float(angles.min()), 2),
                                                   "max": round(float(angles.max()), 2)},
                "lecture": ("corps couché (axe long proche de l'horizontale)" if moyen < 30.0 else
                            "corps debout (axe long proche de la verticale)" if moyen > 60.0 else "corps oblique"),
                "centre_surfacique": {"depart_m": _flottants(centres[0]), "arrivee_m": _flottants(centres[-1]),
                                      "deplacement_net_xz_m": round(float(np.linalg.norm(centres[-1, [0, 2]] - centres[0, [0, 2]])), 4),
                                      "parcours_xz_m": round(float(pas_xz.sum()), 4),
                                      "amplitude_verticale_m": round(float(np.ptp(centres[:, 1])), 4)},
                "bloquant": False}
        else:
            pire = int(np.argmax(parts))
            ok = bool(parts.max() <= tau_x)
            m4[s["nom"]] = {"part_max": round(float(parts.max()), 6), "instant_max_s": round(float(instants[pire]), 4),
                            "seuil": tau_x, "milieu": _libelle_milieu(s["milieu"]), "ok": ok}
            if not ok:
                raisons.append(f"M4 : {s['nom']} ({_libelle_milieu(s['milieu'])}) est à {parts.max():.3f} dans le "
                               f"liquide à t = {instants[pire]:.2f} s (seuil {tau_x:.3f})")
    mesures["M2"], mesures["M4"] = m2, m4
    if requis and not m2:
        raisons.append("M2 : aucun sujet immergé mesurable")

    # M5 — la surface bouge, mesuré dans le fichier
    if liquides:
        crete = 0.0
        for i in liquides:
            if hauteurs_surface[i]:
                pile = np.stack(hauteurs_surface[i])
                crete = max(crete, float(np.ptp(pile, axis=0).max()))
        echelle_scene = float(np.linalg.norm(np.ptp(np.concatenate([dict(ech_eau.points(0.0, liquides))[i]
                                                                    for i in liquides]), axis=0)))
        m5_ok = crete > 1e-6 * max(echelle_scene, 1e-9)
        mesures["M5"] = {"deplacement_crete_a_creux_max_m": round(crete, 6), "instants": int(len(instants)), "ok": m5_ok}
        if not m5_ok:
            raisons.append("M5 : la surface du liquide ne bouge pas dans le fichier")

        # M6 — ce que f3d et les viewers peuvent jouer
        animations = len(doc.get("animations") or [])
        details = []
        for i in liquides:
            maillage = doc["meshes"][noeuds[i]["mesh"]]
            cibles = max((len(p.get("targets", [])) for p in maillage.get("primitives", [])), default=0)
            w0, wt, defaut = ech.poids_morph(i, 0.0), ech.poids_morph(i, duree_s), ech.poids_morph(i, None)
            details.append({"noeud": noeuds[i].get("name"), "cibles": cibles, "w0": _flottants(w0), "wT": _flottants(wt),
                            "defaut": _flottants(defaut), "boucle": bool(np.allclose(w0, wt, atol=1e-4)),
                            "defaut_egal_w0": bool(np.allclose(defaut, w0, atol=1e-4))})
        m6_ok = (animations == 1 and all(d["cibles"] <= 4 and d["boucle"] and d["defaut_egal_w0"] for d in details))
        mesures["M6"] = {"animations": animations, "volumes": details, "ok": m6_ok}
        if not m6_ok:
            raisons.append(f"M6 : {animations} animation(s), " + "; ".join(
                f"{d['noeud']} : {d['cibles']} cible(s), boucle {d['boucle']}, défaut = w(0) {d['defaut_egal_w0']}"
                for d in details))
    elif requis:
        mesures["M5"] = {"ok": False, "raison": "aucun liquide"}
        mesures["M6"] = {"ok": False, "raison": "aucun liquide"}

    return {"schema": SCHEMA_PORTE, "ok": not raisons, "glb": str(glb_path), "duree_s": duree_s,
            "instants": int(len(instants)), "seuils": seuils, "mesures": mesures, "rapports": rapports,
            "raisons": raisons}


# ── Rendus f3d ─────────────────────────────────────────────────────────────────────────────────
def commande_f3d(glb: str | Path, png: str | Path, instant: float, *, resolution=(600, 600),
                 f3d: str | Path = F3D, options: Iterable[str] = ()) -> list[str]:
    """Commande f3d d'un rendu à un instant : +Y en haut, translucidité (peeling) pour le liquide."""
    largeur, hauteur = (int(v) for v in resolution)
    return [str(f3d), str(glb), f"--output={png}", f"--resolution={largeur},{hauteur}", "--up=+Y",
            f"--animation-time={float(instant):g}", "--translucency-support", "--filename=false",
            "--axis=false", "--grid=false", *options]


def rendre_f3d(glb: str | Path, png: str | Path, instant: float, *, resolution=(600, 600), logiciel: bool = True,
               executer: Callable[..., Any] | None = None, f3d: str | Path = F3D, delai_s: float = 900.0,
               options: Iterable[str] = ()) -> dict[str, Any]:
    """Rend un instant ; mesure la part de pixels blanc pur (#FFFFFF), qui trahit une surexposition."""
    png = Path(png)
    png.parent.mkdir(parents=True, exist_ok=True)
    commande = commande_f3d(glb, png, instant, resolution=resolution, f3d=f3d, options=options)
    env = dict(os.environ)
    if logiciel:
        env.update(ENV_RENDU_LOGICIEL)
    executer = executer or subprocess.run
    debut = time.monotonic()
    try:
        res = executer(commande, env=env, capture_output=True, text=True, timeout=delai_s)
        code, erreur = int(getattr(res, "returncode", 1)), str(getattr(res, "stderr", "") or "")[-600:]
    except Exception as exc:  # noqa: BLE001 — rendu manqué : rapporté
        code, erreur = -1, f"{type(exc).__name__}: {exc}"[:600]
    sortie = {"ok": code == 0 and png.is_file(), "png": str(png), "instant_s": float(instant), "code": code,
              "logiciel": logiciel, "duree_s": round(time.monotonic() - debut, 2), "commande": commande}
    if sortie["ok"]:
        from PIL import Image
        with Image.open(png) as image:
            pixels = np.asarray(image.convert("RGB"))
        sortie["part_blanc_pur"] = round(float(np.all(pixels == 255, axis=2).mean()), 6)
    else:
        sortie["erreur"] = erreur
    return sortie


def direction_camera_laterale(centres_xz: Iterable[Iterable[float]], elevation_deg: float = 20.0) -> list[float]:
    """Direction de vue perpendiculaire à l'axe principal des sujets, légèrement plongeante.

    15/11/2026 : la direction par défaut de la configuration f3d du poste (−1, −0,5, −1) plaçait le
    volume d'eau entre la caméra et Zig. Regarder perpendiculairement à la ligne qui joint les
    sujets les montre côte à côte, sans que l'un cache l'autre ; la caméra est du côté +z (avant
    glTF), ou +x quand les sujets s'alignent sur z.
    """
    centres = np.asarray(list(centres_xz), dtype=np.float64).reshape(-1, 2)
    normale = np.array([0.0, 1.0])
    if len(centres) >= 2 and float(np.ptp(centres, axis=0).max()) > 0:
        _, _, axes = np.linalg.svd(centres - centres.mean(axis=0))
        normale = np.array([-axes[0][1], axes[0][0]])
    if normale[1] < -1e-9 or (abs(normale[1]) <= 1e-9 and normale[0] < 0):
        normale = -normale
    e = math.radians(elevation_deg)
    return _flottants([-normale[0] * math.cos(e), -math.sin(e), -normale[1] * math.cos(e)], 4)


def planche_f3d(glb: str | Path, dossier: str | Path, instants: Iterable[float], *, prefixe: str = "f3d",
                resolution=(600, 600), logiciel: bool = True, executer: Callable[..., Any] | None = None,
                f3d: str | Path = F3D, options: Iterable[str] = ()) -> dict[str, Any]:
    """Un rendu f3d par instant, puis une planche côte à côte légendée par l'instant."""
    dossier = Path(dossier)
    options = list(options)
    rendus = [rendre_f3d(glb, dossier / f"{prefixe}_t{float(t):g}.png", float(t), resolution=resolution,
                         logiciel=logiciel, executer=executer, f3d=f3d, options=options) for t in instants]
    reussis = [r for r in rendus if r["ok"]]
    resultat: dict[str, Any] = {"ok": bool(rendus) and len(reussis) == len(rendus), "rendus": rendus}
    if reussis:
        from PIL import Image, ImageDraw
        images = [Image.open(r["png"]).convert("RGB") for r in reussis]
        largeur, hauteur = images[0].size
        planche = Image.new("RGB", (largeur * len(images), hauteur), (24, 28, 36))
        for rang, (image, r) in enumerate(zip(images, reussis)):
            planche.paste(image.resize((largeur, hauteur)), (rang * largeur, 0))
            dessin = ImageDraw.Draw(planche)
            dessin.rectangle([(rang * largeur + 10, 10), (rang * largeur + 120, 36)], fill=(15, 20, 28))
            dessin.text((rang * largeur + 18, 16), f"t = {r['instant_s']:g} s", fill=(240, 245, 255))
        chemin = dossier / f"planche_{prefixe}.png"
        planche.save(chemin)
        resultat["planche"] = str(chemin)
        resultat["part_blanc_pur_max"] = max(r["part_blanc_pur"] for r in reussis)
    return resultat


# ── Entrées depuis un run ──────────────────────────────────────────────────────────────────────
def milieux_depuis_contrat(contrat: dict[str, Any]) -> dict[str, dict]:
    """{nom normalisé: milieu} lu dans un contrat aurora.lecture-demande.v2."""
    return {_cle_nom(s.get("nom")): s.get("milieu") for s in contrat.get("sujets") or []
            if isinstance(s, dict) and s.get("nom") and isinstance(s.get("milieu"), dict)}


def entrees_depuis_animation(chemin: str | Path, milieux: dict[str, dict]) -> list[dict[str, Any]]:
    """Entrées de `composer_avec_milieux` tirées d'un animation_multi_sujets.json (GLB, nom, recalage)."""
    rapport = json.loads(Path(chemin).read_text(encoding="utf-8"))
    entrees = []
    for rang, sujet in enumerate(rapport.get("sujets") or []):
        nom = str(sujet.get("sujet") or f"sujet_{rang + 1}")
        entrees.append({"glb": sujet["glb"], "nom": nom, "recalage": sujet.get("recalage"),
                        "milieu": milieux.get(_cle_nom(nom))})
    return entrees


def _lire_milieu_cli(texte: str) -> tuple[str, dict]:
    nom, _, valeur = texte.partition("=")
    matiere, _, relation = valeur.partition("/")
    return _cle_nom(nom), {"matiere": matiere.strip() or None, "relation": relation.strip() or None,
                           "justification": "ligne de commande"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compose des sujets animés avec le milieu de leur mouvement, puis le juge")
    ap.add_argument("--animation", help="animation_multi_sujets.json d'un run (GLB, noms, recalages)")
    ap.add_argument("--entrees", help="JSON : liste d'entrées {glb, nom, recalage, milieu}")
    ap.add_argument("--contrat", help="contrat aurora.lecture-demande.v2 (sujets[].nom, sujets[].milieu)")
    ap.add_argument("--milieu", action="append", default=[], help="NOM=matiere/relation, ex. Sharko=liquide/immerge")
    ap.add_argument("--sortie", help="GLB composé à écrire")
    ap.add_argument("--porte-seule", help="GLB déjà composé à juger, sans rien construire")
    ap.add_argument("--rapport", help="JSON du rapport complet")
    ap.add_argument("--f3d", default="", help="instants des rendus f3d, ex. 0,1,2,3")
    ap.add_argument("--gpu", action="store_true", help="rendu f3d sur le GPU (logiciel Mesa par défaut)")
    ap.add_argument("--echantillon", type=int, help="sommets par primitive (défaut : tous)")
    ap.add_argument("--cliquet", help="judge_ratchet_milieu.json à lire (défaut : modele/renforce/)")
    a = ap.parse_args(argv)
    milieux: dict[str, dict] = {}
    if a.contrat:
        milieux.update(milieux_depuis_contrat(json.loads(Path(a.contrat).read_text(encoding="utf-8"))))
    milieux.update(dict(_lire_milieu_cli(m) for m in a.milieu))
    if a.entrees:
        entrees = json.loads(Path(a.entrees).read_text(encoding="utf-8"))
    elif a.animation:
        entrees = entrees_depuis_animation(a.animation, milieux)
    else:
        ap.error("--animation ou --entrees est requis")
    if a.porte_seule:
        attentes = {"sujets": [{"racine": e["nom"], "nom": e["nom"], "milieu": e.get("milieu")} for e in entrees]}
        res: dict[str, Any] = {"porte": porte_milieu(a.porte_seule, attentes, chemin_cliquet=a.cliquet,
                                                     echantillon=a.echantillon)}
        res["ok"], res["sortie"] = res["porte"]["ok"], a.porte_seule
    else:
        if not a.sortie:
            ap.error("--sortie est requis pour composer")
        res = composer_avec_milieux(entrees, a.sortie, echantillon=a.echantillon, chemin_cliquet=a.cliquet)
    if a.f3d:
        instants = [float(x) for x in a.f3d.split(",") if x.strip()]
        dossier = Path(a.rapport or res["sortie"]).parent
        res["f3d"] = planche_f3d(res["sortie"], dossier, instants, prefixe=Path(res["sortie"]).stem,
                                 logiciel=not a.gpu)
        centres = [0.5 * (np.array(s["boite_balayee_m"][0]) + np.array(s["boite_balayee_m"][1]))[[0, 2]]
                   for s in res.get("sujets_mesures") or []]
        if len(centres) >= 2:
            direction = direction_camera_laterale(centres)
            res["f3d_laterale"] = planche_f3d(res["sortie"], dossier, instants,
                                              prefixe=f"{Path(res['sortie']).stem}_laterale", logiciel=not a.gpu,
                                              options=[f"--camera-direction={','.join(f'{v:g}' for v in direction)}"])
    if a.rapport:
        Path(a.rapport).parent.mkdir(parents=True, exist_ok=True)
        Path(a.rapport).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    porte = res.get("porte") or {}
    print(json.dumps({"ok": res.get("ok"), "sortie": res.get("sortie"), "raisons": porte.get("raisons"),
                      "deplacements": res.get("deplacements"), "milieux": res.get("milieux")}, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
