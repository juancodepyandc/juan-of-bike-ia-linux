#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mouvement articulé d'un objet reconstruit : une pièce bouge par rapport au reste.

« Coffre avec une animation d'ouverture » faisait osciller le maillage ENTIER de ±15° autour
d'un axe du monde (motion_intent_bpy_runner.bake_mechanical_simple) : aucune séparation du
couvercle, aucune charnière, aucun sens d'ouverture. Ce module fait le travail d'un animateur
mécanique, sur n'importe quel objet dont une pièce rigide bouge par rapport à une base :

1. plan cinématique lu dans la demande par le modèle de langage (sémantique seulement : quelle
   pièce, de quel côté, quelle liaison, quelle chronologie) ;
2. coupe trouvée sur la géométrie réelle : énergie de couture mesurée le long de l'axe de la
   pièce mobile (arêtes vives orientées comme une couture, rétrécissement ou marche de la
   section, rupture de couleur dans la texture), le plan ne donne qu'une estimation ;
3. découpe exacte des triangles (UV et texture conservées) ;
4. ce que la reconstruction n'a jamais vu est construit : fermeture des coupes et, pour un
   contenant, une vraie cavité (rebord, parois, fond) dont la couleur est mesurée sur les texels
   voisins de la coupe ;
5. liaison tirée de la géométrie : charnière ajustée sur le bord de la coupe du côté
   d'attache, côté choisi par la physique quand la demande ne le dit pas ; glissière selon la
   normale de la face ;
6. amplitude bornée par collision (grille d'occupation remplie de la base) ;
7. export glTF : un nœud par pièce, nœud mobile pivoté sur la liaison, animation de nœud ;
8. porte de vérification qui relit le fichier écrit et mesure tout elle-même.

Convention d'orientation (glTF, celle des rendus du pipeline) : +Y en haut, la face avant de
l'objet regarde +Z, la droite vue de face est +X.

Portée : la pièce mobile occupe toute une face de l'objet (couvercle, rabat, coque, porte
pleine, abattant). Une pièce partielle (un tiroir parmi plusieurs, un bouton) exige une
segmentation par région qui n'est pas faite ici : le module le dit et refuse, il ne déplace
jamais l'objet entier en appelant cela un succès.
"""
from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path
from typing import Any, Callable

import numpy as np

SCHEMA_PLAN = "aurora.plan-cinematique.v1"
SCHEMA_EXTRAS = "aurora.articulation.v1"
OLLAMA_URL = "http://127.0.0.1:11434"
MODELE_SOUHAITE = "orcarouter/Qwen3.8-27B-Uncensored:latest"

SIDES: dict[str, np.ndarray] = {
    "top": np.array([0.0, 1.0, 0.0]), "bottom": np.array([0.0, -1.0, 0.0]),
    "front": np.array([0.0, 0.0, 1.0]), "back": np.array([0.0, 0.0, -1.0]),
    "right": np.array([1.0, 0.0, 0.0]), "left": np.array([-1.0, 0.0, 0.0]),
}
OPPOSITE = {"top": "bottom", "bottom": "top", "front": "back", "back": "front", "right": "left", "left": "right"}
LIAISONS = ("charniere", "glissiere")

# Seuils de la porte de vérification (relatifs à la diagonale de l'objet).
MIN_DEPLACEMENT_RELATIF = 0.08     # la pièce mobile doit réellement bouger
TOLERANCE_AXE_RELATIVE = 1e-4      # les points de l'axe de charnière restent fixes
MAX_PENETRATION = 0.003            # part des points de la pièce mobile enfoncés dans la base
AMPLITUDE_MIN_DEG = 15.0           # en dessous, l'objet ne s'ouvre pas vraiment


# --------------------------------------------------------------------------- plan

_CONSIGNE_PLAN = (
    "Tu es un ingénieur en animation mécanique. On te donne une demande de mouvement pour un objet 3D "
    "reconstruit d'une seule pièce. Décris le mouvement comme une liaison mécanique entre une pièce "
    "mobile et une base. Réponds UNIQUEMENT par un objet JSON de cette forme :\n"
    '{"mouvement_de_piece": true, "piece_mobile": "...", "piece_fixe": "...", '
    '"position_piece_mobile": "top", "piece_couvre_toute_la_face": true, "articulation": "charniere", '
    '"cote_attache": "back", "fraction_estimee": 0.3, "amplitude_deg": 105, "course_relative": 0.6, '
    '"base_contenant": true, "duree_s": 2.0, "maintien_s": 1.0, "retour": false, "boucle": false}\n'
    "Conventions : top = dessus, bottom = dessous, front = face avant (celle qu'on regarde), back = arrière, "
    "left et right vus de face.\n"
    "- mouvement_de_piece : true si UNE PARTIE de l'objet bouge par rapport au reste (couvercle, porte, "
    "rabat, abattant, tiroir, levier) ; false si l'objet entier bouge, tourne ou flotte.\n"
    "- position_piece_mobile : de quel côté de l'objet se trouve la pièce mobile.\n"
    "- piece_couvre_toute_la_face : true si la pièce mobile occupe tout ce côté (le couvercle d'un coffre, "
    "l'écran d'un ordinateur portable) ; false si elle n'en occupe qu'une partie (un tiroir parmi d'autres, "
    "un bouton, une trappe).\n"
    "- articulation : charniere (rotation autour d'un bord) ou glissiere (translation).\n"
    "- cote_attache : pour une charnière, le côté où se trouve l'axe (un coffre s'ouvre par l'arrière : back) ; "
    "inconnu si la demande et l'usage courant ne permettent pas de le dire.\n"
    "- fraction_estimee : part approximative de la hauteur (ou profondeur) de l'objet occupée par la pièce "
    "mobile, entre 0.05 et 0.6.\n"
    "- amplitude_deg : angle d'ouverture d'une charnière ; course_relative : course d'une glissière rapportée "
    "à la taille de l'objet.\n"
    "- base_contenant : true si la base est un contenant qui s'ouvre (on doit voir l'intérieur).\n"
    "- duree_s, maintien_s, retour, boucle : chronologie demandée (une « ouverture » s'ouvre et reste ouverte : "
    "retour false).\n"
    "Pas de texte hors du JSON."
)


def _interroger_ollama(demande: str, modele: str, timeout_s: float = 120.0) -> str:
    corps = json.dumps({
        "model": modele, "stream": False, "format": "json", "think": False,
        "options": {"temperature": 0.0, "num_predict": 500},
        "messages": [{"role": "system", "content": _CONSIGNE_PLAN}, {"role": "user", "content": demande}],
    }).encode("utf-8")
    requete = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=corps, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(requete, timeout=timeout_s) as reponse:
        return str(json.loads(reponse.read().decode("utf-8")).get("message", {}).get("content", ""))


def _extraire_json(texte: str) -> dict[str, Any] | None:
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut < 0 or fin <= debut:
        return None
    try:
        valeur = json.loads(texte[debut:fin + 1])
    except ValueError:
        return None
    return valeur if isinstance(valeur, dict) else None


def _nombre(valeur: Any, defaut: float, bas: float, haut: float) -> float:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)) or not math.isfinite(valeur):
        return defaut
    return float(min(haut, max(bas, valeur)))


def _booleen(valeur: Any, defaut: bool) -> bool:
    return valeur if isinstance(valeur, bool) else defaut


def valider_plan(brut: Any, demande: str) -> dict[str, Any]:
    """Plan normalisé ; `ok: False` avec la raison quand la réponse sort du contrat."""
    if not isinstance(brut, dict) or not isinstance(brut.get("mouvement_de_piece"), bool):
        return {"schema": SCHEMA_PLAN, "ok": False, "demande": demande, "raison": "réponse du modèle hors contrat"}
    plan: dict[str, Any] = {"schema": SCHEMA_PLAN, "ok": True, "demande": demande,
                            "mouvement_de_piece": brut["mouvement_de_piece"]}
    if not plan["mouvement_de_piece"]:
        return plan
    position = brut.get("position_piece_mobile")
    articulation = brut.get("articulation")
    if position not in SIDES or articulation not in LIAISONS:
        return {**plan, "ok": False, "raison": "position ou liaison de la pièce mobile hors contrat"}
    attache = brut.get("cote_attache")
    if articulation == "charniere" and (attache not in SIDES or attache in (position, OPPOSITE[position])):
        attache = "inconnu"
    plan.update({
        "piece_mobile": str(brut.get("piece_mobile") or "pièce mobile")[:80],
        "piece_fixe": str(brut.get("piece_fixe") or "base")[:80],
        "position_piece_mobile": position,
        "piece_couvre_toute_la_face": _booleen(brut.get("piece_couvre_toute_la_face"), True),
        "articulation": articulation,
        "cote_attache": attache if articulation == "charniere" else None,
        "fraction_estimee": _nombre(brut.get("fraction_estimee"), 0.3, 0.05, 0.6),
        "amplitude_deg": _nombre(brut.get("amplitude_deg"), 100.0, 5.0, 180.0),
        "course_relative": _nombre(brut.get("course_relative"), 0.6, 0.05, 1.0),
        "base_contenant": _booleen(brut.get("base_contenant"), False),
        "duree_s": _nombre(brut.get("duree_s"), 2.0, 0.3, 20.0),
        "maintien_s": _nombre(brut.get("maintien_s"), 1.0, 0.0, 20.0),
        "retour": _booleen(brut.get("retour"), False),
        "boucle": _booleen(brut.get("boucle"), False),
    })
    return plan


def planifier(demande: str, *, interroger: Callable[[str], str] | None = None,
              modele: str | None = None) -> dict[str, Any]:
    """Lit la demande en plan cinématique. Le modèle donne la sémantique, jamais une mesure."""
    demande = " ".join(str(demande or "").split())
    if not demande:
        return {"schema": SCHEMA_PLAN, "ok": False, "demande": "", "raison": "demande vide"}
    if interroger is None:
        if modele is None:
            try:
                from llm_disponible import resoudre_modele
                modele = resoudre_modele(MODELE_SOUHAITE, "texte", bavard=False)
            except Exception:  # noqa: BLE001
                modele = MODELE_SOUHAITE
        modele_choisi = modele

        def interroger(texte: str) -> str:
            return _interroger_ollama(texte, modele_choisi)
    try:
        reponse = interroger(demande)
    except Exception as exc:  # noqa: BLE001
        return {"schema": SCHEMA_PLAN, "ok": False, "demande": demande, "raison": f"modèle injoignable : {type(exc).__name__}"}
    return valider_plan(_extraire_json(str(reponse)), demande)


# --------------------------------------------------------------------------- géométrie

def charger(path: str | Path):
    """Maillage texturé tel quel (doublons UV conservés) et copie soudée pour la géométrie."""
    import trimesh
    maillage = trimesh.load(str(path), force="mesh", process=False)
    if not isinstance(maillage, trimesh.Trimesh) or len(maillage.faces) == 0:
        raise ValueError("le fichier ne contient pas de maillage exploitable")
    soude = trimesh.Trimesh(vertices=np.asarray(maillage.vertices).copy(),
                            faces=np.asarray(maillage.faces).copy(), process=True)
    return maillage, soude


def _image_de_couleur(maillage):
    visuel = getattr(maillage, "visual", None)
    materiau = getattr(visuel, "material", None)
    image = getattr(materiau, "baseColorTexture", None) or getattr(materiau, "image", None)
    facteur = np.asarray(getattr(materiau, "baseColorFactor", None) if getattr(materiau, "baseColorFactor", None) is not None
                         else [255, 255, 255, 255], dtype=float)[:3]
    if facteur.max() > 1.0:
        facteur = facteur / 255.0
    return image, facteur


def couleurs_des_faces(maillage) -> np.ndarray | None:
    """Couleur de chaque face lue dans la texture au centre UV de la face (0..1), ou None."""
    visuel = getattr(maillage, "visual", None)
    uv = getattr(visuel, "uv", None)
    image, facteur = _image_de_couleur(maillage)
    if uv is not None and image is not None and len(uv) == len(maillage.vertices):
        pixels = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        hauteur, largeur = pixels.shape[:2]
        centre = np.asarray(uv, dtype=np.float64)[maillage.faces].mean(axis=1)
        x = np.clip(np.rint((centre[:, 0] % 1.0) * (largeur - 1)), 0, largeur - 1).astype(int)
        y = np.clip(np.rint((1.0 - (centre[:, 1] % 1.0)) * (hauteur - 1)), 0, hauteur - 1).astype(int)
        return pixels[y, x] * facteur[None, :]
    couleurs = getattr(visuel, "face_colors", None)
    if couleurs is not None and len(couleurs) == len(maillage.faces):
        return np.asarray(couleurs, dtype=np.float32)[:, :3] / 255.0
    return None


def _lisser(valeurs: np.ndarray, sigma: float) -> np.ndarray:
    rayon = max(1, int(3 * sigma))
    noyau = np.exp(-0.5 * (np.arange(-rayon, rayon + 1) / sigma) ** 2)
    noyau /= noyau.sum()
    return np.convolve(valeurs, noyau, mode="same")


def _normaliser(valeurs: np.ndarray) -> np.ndarray:
    maximum = float(np.max(valeurs)) if len(valeurs) else 0.0
    return valeurs / maximum if maximum > 1e-12 else np.zeros_like(valeurs)


def trouver_couture(maillage, soude, axe: np.ndarray, fraction_estimee: float,
                    couleurs: np.ndarray | None = None, nb_cases: int = 240) -> dict[str, Any]:
    """Position de la couture entre la base et la pièce mobile, mesurée le long de `axe`.

    `fraction` vaut 0 côté base et 1 côté pièce mobile. La fraction estimée par le plan ne sert
    qu'à borner la recherche et comme faible a priori : la position retenue est celle où l'énergie
    de couture mesurée est la plus forte.
    """
    axe = np.asarray(axe, dtype=float) / np.linalg.norm(axe)
    t = soude.vertices @ axe
    t_min, t_max = float(t.min()), float(t.max())
    etendue = t_max - t_min
    if etendue <= 1e-9:
        raise ValueError("objet plat selon l'axe de la pièce mobile")
    estimation = 1.0 - fraction_estimee
    bas, haut = max(0.05, 1.0 - 2.2 * fraction_estimee), min(0.97, 1.0 - 0.3 * fraction_estimee)
    centres = (np.arange(nb_cases) + 0.5) / nb_cases
    fenetre = (centres >= bas) & (centres <= haut)

    # (a) arêtes vives orientées comme une couture (perpendiculaires à l'axe)
    angles = np.asarray(soude.face_adjacency_angles)
    vives = angles > math.radians(20.0)
    aretes = np.asarray(soude.face_adjacency_edges)[vives]
    pli = np.zeros(nb_cases)
    pos_aretes = poids_aretes = np.zeros(0)
    if len(aretes):
        a0, a1 = soude.vertices[aretes[:, 0]], soude.vertices[aretes[:, 1]]
        vecteur = a1 - a0
        longueur = np.linalg.norm(vecteur, axis=1)
        direction = vecteur / np.maximum(longueur[:, None], 1e-12)
        poids_aretes = longueur * (1.0 - np.abs(direction @ axe)) * np.minimum(1.0, angles[vives] / math.radians(60.0))
        pos_aretes = ((0.5 * (a0 + a1)) @ axe - t_min) / etendue
        pli, _ = np.histogram(pos_aretes, bins=nb_cases, range=(0.0, 1.0), weights=poids_aretes)
        pli = _lisser(pli, 1.5)

    # (b) section : rainure (creux local) ou marche (changement brusque)
    profil = np.zeros(nb_cases)
    cases_fenetre = np.flatnonzero(fenetre)
    if len(cases_fenetre):
        echantillon = cases_fenetre[np.linspace(0, len(cases_fenetre) - 1, min(60, len(cases_fenetre))).astype(int)]
        hauteurs = centres[echantillon] * etendue
        origine = soude.bounds.mean(axis=0) + (t_min - soude.bounds.mean(axis=0) @ axe) * axe
        aires = []
        try:
            sections = soude.section_multiplane(plane_origin=origine, plane_normal=axe, heights=list(hauteurs))
        except Exception:  # noqa: BLE001
            sections = [None] * len(hauteurs)
        for section in sections:
            aire = 0.0
            if section is not None:
                try:
                    aire = float(sum(p.area for p in section.polygons_full))
                    if aire <= 0.0 and len(section.vertices) >= 3:
                        from shapely.geometry import MultiPoint
                        aire = float(MultiPoint([tuple(v) for v in section.vertices]).convex_hull.area)
                except Exception:  # noqa: BLE001
                    aire = 0.0
            aires.append(aire)
        aires = np.asarray(aires)
        if aires.max() > 0:
            aires_cases = np.interp(centres, centres[echantillon], aires)
            moyenne = float(aires[aires > 0].mean())
            delta = 3
            avant = np.roll(aires_cases, delta)
            apres = np.roll(aires_cases, -delta)
            creux = np.maximum(0.0, 0.5 * (avant + apres) - aires_cases) / moyenne
            marche = np.abs(apres - avant) / moyenne
            profil = creux + 0.5 * marche
            profil[~fenetre] = 0.0

    # (c) rupture de couleur dans la texture
    couleur = np.zeros(nb_cases)
    if couleurs is not None and len(couleurs) == len(maillage.faces):
        centres_faces = maillage.triangles_center @ axe
        position = (centres_faces - t_min) / etendue
        aire_faces = np.asarray(maillage.area_faces)
        ordre = np.argsort(position)
        position, aire_faces, valeurs = position[ordre], aire_faces[ordre], couleurs[ordre]
        cumul_poids = np.concatenate([[0.0], np.cumsum(aire_faces)])
        cumul_couleur = np.vstack([np.zeros((1, 3)), np.cumsum(valeurs * aire_faces[:, None], axis=0)])
        bande = 0.04

        def moyenne_entre(bas_b: np.ndarray, haut_b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            i0 = np.searchsorted(position, bas_b, side="left")
            i1 = np.searchsorted(position, haut_b, side="right")
            poids = cumul_poids[i1] - cumul_poids[i0]
            somme = cumul_couleur[i1] - cumul_couleur[i0]
            return somme / np.maximum(poids[:, None], 1e-12), poids

        dessous, p_dessous = moyenne_entre(centres - bande, centres)
        dessus, p_dessus = moyenne_entre(centres, centres + bande)
        couleur = np.linalg.norm(dessus - dessous, axis=1)
        couleur[(p_dessous <= 0) | (p_dessus <= 0)] = 0.0
        couleur = _lisser(couleur, 1.0)

    pli_n, profil_n, couleur_n = (_normaliser(np.where(fenetre, x, 0.0)) for x in (pli, profil, couleur))
    a_priori = np.exp(-0.5 * ((centres - estimation) / 0.18) ** 2)
    energie = 0.45 * pli_n + 0.30 * profil_n + 0.25 * couleur_n + 0.12 * a_priori
    energie[~fenetre] = -1.0
    meilleur = int(np.argmax(energie))
    fraction = float(centres[meilleur])
    # Accroche fine : la couture est une ligne d'arêtes vives ; on se pose sur sa hauteur exacte au
    # lieu du centre de la case, puis un epsilon côté base pour que la face qui borde la couture
    # (le dessous d'un couvercle qui déborde) parte avec la pièce mobile au lieu de rester collée.
    accroche = "case"
    voisinage = (np.abs(pos_aretes - fraction) <= 2.5 / nb_cases) & (poids_aretes > 0)
    if voisinage.any():
        pas_fin = 1e-4
        cles = np.round(pos_aretes[voisinage] / pas_fin).astype(np.int64)
        uniques, inverse = np.unique(cles, return_inverse=True)
        sommes = np.bincount(inverse, weights=poids_aretes[voisinage])
        if sommes.max() >= 0.25 * float(poids_aretes[voisinage].sum()):
            fraction = float(uniques[int(np.argmax(sommes))] * pas_fin) - 0.002
            accroche = "arete_vive"
    mesure = 0.45 * pli_n[meilleur] + 0.30 * profil_n[meilleur] + 0.25 * couleur_n[meilleur]
    centre = soude.bounds.mean(axis=0)
    origine_plan = centre + ((t_min + fraction * etendue) - centre @ axe) * axe
    return {
        "fraction": round(fraction, 5), "estimation": round(estimation, 4), "accroche": accroche,
        "ecart_estimation": round(fraction - estimation, 4),
        "energie_mesuree": round(float(mesure), 4),
        "composantes": {"aretes_vives": round(float(pli_n[meilleur]), 4),
                        "section": round(float(profil_n[meilleur]), 4),
                        "couleur": round(float(couleur_n[meilleur]), 4)},
        "origine": origine_plan.tolist(), "normale": axe.tolist(),
        "etendue": etendue, "t_min": t_min,
    }


def couper(maillage, origine, normale):
    """Les deux côtés du plan, triangles coupés exactement, UV et matériau conservés."""
    from trimesh.intersections import slice_mesh_plane
    normale = np.asarray(normale, dtype=float)
    mobile = slice_mesh_plane(maillage, plane_normal=normale, plane_origin=origine)
    base = slice_mesh_plane(maillage, plane_normal=-normale, plane_origin=origine)
    return mobile, base


def polygones_de_coupe(soude, origine, normale):
    """Polygones fermés de la section (shapely) et la matrice 2D→3D de leur plan."""
    from shapely.geometry import MultiPoint, Polygon
    section = soude.section(plane_origin=origine, plane_normal=normale)
    if section is None:
        raise ValueError("le plan de coupe ne traverse pas l'objet")
    plan2d, vers_3d = section.to_2D()
    polygones = [p for p in plan2d.polygons_full if p.area > 0]
    if not polygones and len(plan2d.vertices) >= 3:
        enveloppe = MultiPoint([tuple(v) for v in plan2d.vertices]).convex_hull
        if isinstance(enveloppe, Polygon) and enveloppe.area > 0:
            polygones = [enveloppe]
    if not polygones:
        raise ValueError("section de coupe sans contour fermé")
    plus_grand = max(p.area for p in polygones)
    polygones = [p for p in polygones if p.area >= 0.005 * plus_grand]
    return polygones, np.asarray(vers_3d, dtype=float)


def _vers_3d(points2d: np.ndarray, vers_3d: np.ndarray, decalage: np.ndarray | None = None) -> np.ndarray:
    homogenes = np.column_stack([points2d, np.zeros(len(points2d)), np.ones(len(points2d))])
    points = (vers_3d @ homogenes.T).T[:, :3]
    return points + (decalage if decalage is not None else 0.0)


def _orienter(triangles: np.ndarray, normale_voulue: np.ndarray) -> np.ndarray:
    normales = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    inverses = normales @ normale_voulue < 0
    triangles = triangles.copy()
    triangles[inverses] = triangles[inverses][:, [0, 2, 1]]
    return triangles


def _maillage_de_triangles(triangles: np.ndarray):
    import trimesh
    if len(triangles) == 0:
        return trimesh.Trimesh()
    sommets = triangles.reshape(-1, 3)
    faces = np.arange(len(sommets)).reshape(-1, 3)
    resultat = trimesh.Trimesh(vertices=sommets, faces=faces, process=False)
    resultat.merge_vertices()
    return resultat


def trianguler(polygones, vers_3d: np.ndarray, normale_voulue: np.ndarray, decalage=None):
    import shapely
    triangles = []
    for polygone in polygones:
        for triangle in shapely.constrained_delaunay_triangles(polygone).geoms:
            triangles.append(np.asarray(triangle.exterior.coords)[:3])
    if not triangles:
        return _maillage_de_triangles(np.zeros((0, 3, 3)))
    tri2d = np.asarray(triangles)
    tri3d = _vers_3d(tri2d.reshape(-1, 2), vers_3d, decalage).reshape(-1, 3, 3)
    return _maillage_de_triangles(_orienter(tri3d, normale_voulue))


def construire_cavite(polygones, vers_3d: np.ndarray, normale: np.ndarray, profondeur: float, paroi: float):
    """Rebord, parois intérieures et fond d'un contenant ouvert sous la coupe."""
    from shapely.geometry import Polygon
    normale = np.asarray(normale, dtype=float)
    pieces = []
    for polygone in polygones:
        interieur = polygone.buffer(-paroi, join_style="mitre")
        if interieur.is_empty or interieur.area < 0.2 * polygone.area:
            pieces.append(trianguler([polygone], vers_3d, normale))
            continue
        # Le même contour, densifié une seule fois, borde le rebord, les parois et le fond :
        # des sommets différents de part et d'autre feraient des jonctions en T (trous).
        interieur = interieur.segmentize(max(paroi, 1e-6))
        interieurs = [g for g in getattr(interieur, "geoms", [interieur]) if isinstance(g, Polygon) and g.area > 0]
        rebord = polygone.difference(interieur)
        rebords = [g for g in getattr(rebord, "geoms", [rebord]) if isinstance(g, Polygon) and g.area > 0]
        pieces.append(trianguler(rebords, vers_3d, normale))
        fond = -normale * profondeur
        pieces.append(trianguler(interieurs, vers_3d, normale, decalage=fond))
        for creux in interieurs:
            anneau = np.asarray(creux.exterior.coords)[:-1]
            haut = _vers_3d(anneau, vers_3d)
            bas = haut + fond
            suivant = np.roll(np.arange(len(anneau)), -1)
            quads = np.concatenate([
                np.stack([haut, bas, bas[suivant]], axis=1),
                np.stack([haut, bas[suivant], haut[suivant]], axis=1),
            ])
            centre = _vers_3d(np.asarray(creux.centroid.coords), vers_3d)[0] + 0.5 * fond
            milieux = quads.mean(axis=1)
            normales = np.cross(quads[:, 1] - quads[:, 0], quads[:, 2] - quads[:, 0])
            vers_centre = centre - milieux
            vers_centre -= np.outer(vers_centre @ normale, normale)
            inverses = np.einsum("ij,ij->i", normales, vers_centre) < 0
            quads[inverses] = quads[inverses][:, [0, 2, 1]]
            pieces.append(_maillage_de_triangles(quads))
    import trimesh
    pieces = [p for p in pieces if len(p.faces)]
    resultat = trimesh.util.concatenate(pieces) if pieces else trimesh.Trimesh()
    if len(resultat.faces):
        resultat.merge_vertices()
    return resultat


def couleur_interieure(maillage, couleurs: np.ndarray | None, couture: dict[str, Any]) -> list[float]:
    """Couleur des faces intérieures : médiane des texels juste sous la coupe, assombrie comme
    une surface intérieure peu éclairée. Sans texture : facteur du matériau."""
    axe = np.asarray(couture["normale"])
    if couleurs is not None and len(couleurs) == len(maillage.faces):
        position = (maillage.triangles_center @ axe - couture["t_min"]) / couture["etendue"]
        bande = (position >= couture["fraction"] - 0.06) & (position < couture["fraction"])
        if bande.sum() >= 3:
            return [float(c) for c in np.clip(np.median(couleurs[bande], axis=0) * 0.55, 0.0, 1.0)]
        return [float(c) for c in np.clip(np.median(couleurs, axis=0) * 0.55, 0.0, 1.0)]
    _, facteur = _image_de_couleur(maillage)
    return [float(c) for c in np.clip(facteur * 0.55, 0.0, 1.0)]


def ajuster_charniere(polygones, vers_3d: np.ndarray, cote: str, normale: np.ndarray) -> dict[str, Any]:
    """Axe de charnière ajusté sur le bord de la coupe situé du côté `cote`."""
    direction_cote = SIDES[cote]
    points = []
    for polygone in polygones:
        contour = polygone.segmentize(max(polygone.length / 400.0, 1e-6))
        points.append(_vers_3d(np.asarray(contour.exterior.coords)[:-1], vers_3d))
    points = np.vstack(points)
    projection = points @ direction_cote
    etendue = float(projection.max() - projection.min())
    choisis = points[projection >= projection.max() - 0.03 * max(etendue, 1e-9)]
    if len(choisis) < 2:
        raise ValueError("bord de charnière introuvable sur la coupe")
    centre = choisis.mean(axis=0)
    _, _, vecteurs = np.linalg.svd(choisis - centre)
    direction = vecteurs[0]
    direction = direction - (direction @ normale) * normale - (direction @ direction_cote) * direction_cote
    if np.linalg.norm(direction) < 1e-6:
        direction = np.cross(normale, direction_cote)
    direction /= np.linalg.norm(direction)
    pivot = centre + (projection.max() - centre @ direction_cote) * direction_cote
    ecarts = (choisis - pivot) - np.outer((choisis - pivot) @ direction, direction)
    residu = float(np.sqrt(np.mean(np.sum(ecarts ** 2, axis=1))))
    longueur = float((choisis @ direction).max() - (choisis @ direction).min())
    return {"cote": cote, "pivot": pivot.tolist(), "axe": direction.tolist(),
            "residu": residu, "longueur": longueur, "points": int(len(choisis))}


def rotation(axe: np.ndarray, angle: float) -> np.ndarray:
    axe = np.asarray(axe, dtype=float) / np.linalg.norm(axe)
    x, y, z = axe
    c, s = math.cos(angle), math.sin(angle)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


class Occupation:
    """Grille d'occupation remplie d'une pièce : une cavité ouverte reste vide."""

    def __init__(self, maillage, pas: float):
        from scipy import ndimage
        import trimesh
        grille = trimesh.voxel.creation.voxelize(maillage, pitch=pas)
        plein = ndimage.binary_fill_holes(grille.matrix)
        self.profond = ndimage.binary_erosion(plein, iterations=1)
        self.grille = grille

    def penetration(self, points: np.ndarray) -> float:
        indices = np.asarray(self.grille.points_to_indices(points))
        forme = np.array(self.profond.shape)
        dedans = np.all((indices >= 0) & (indices < forme), axis=1)
        if not dedans.any():
            return 0.0
        valides = indices[dedans]
        enfonces = self.profond[valides[:, 0], valides[:, 1], valides[:, 2]]
        return float(enfonces.sum()) / float(len(points))


def _echantillons(maillage, nombre: int = 4000) -> np.ndarray:
    import trimesh
    if len(maillage.faces) == 0:
        return np.zeros((0, 3))
    points, _ = trimesh.sample.sample_surface(maillage, nombre, seed=7)
    return np.vstack([points, maillage.vertices[:: max(1, len(maillage.vertices) // 2000)]])


def amplitude_libre(points: np.ndarray, occupation: Occupation, pivot, axe, signe: int,
                    amplitude_deg: float, pas_deg: float = 2.0) -> tuple[float, list[dict[str, float]]]:
    """Plus grand angle atteignable depuis 0 sans enfoncer la pièce mobile dans la base."""
    pivot = np.asarray(pivot, dtype=float)
    mesures, libre = [], 0.0
    angle = pas_deg
    while angle <= amplitude_deg + 1e-9:
        R = rotation(axe, signe * math.radians(angle))
        tournes = (points - pivot) @ R.T + pivot
        part = occupation.penetration(tournes)
        mesures.append({"angle": round(angle, 2), "penetration": round(part, 5)})
        if part > MAX_PENETRATION:
            break
        libre = angle
        angle += pas_deg
    return libre, mesures


def _assouplir(x: np.ndarray) -> np.ndarray:
    return x * x * (3.0 - 2.0 * x)


def chronologie(plan: dict[str, Any], fin: float, ips: int = 30) -> tuple[np.ndarray, np.ndarray]:
    """Instants et valeur (0→fin) d'une ouverture adoucie, maintien, retour éventuel."""
    duree, maintien = plan["duree_s"], plan["maintien_s"]
    n = max(2, int(round(duree * ips)) + 1)
    temps = list(np.linspace(0.0, duree, n))
    valeurs = list(_assouplir(np.linspace(0.0, 1.0, n)) * fin)
    if maintien > 0:
        temps.append(duree + maintien)
        valeurs.append(fin)
    if plan["retour"]:
        depart = temps[-1]
        retour_t = np.linspace(0.0, duree, n)[1:]
        temps.extend(list(depart + retour_t))
        valeurs.extend(list(fin * (1.0 - _assouplir(retour_t / duree))))
    return np.asarray(temps, dtype=np.float32), np.asarray(valeurs, dtype=np.float64)


def _quaternion(axe: np.ndarray, angle: float) -> list[float]:
    axe = np.asarray(axe, dtype=float) / np.linalg.norm(axe)
    s = math.sin(angle / 2.0)
    return [float(axe[0] * s), float(axe[1] * s), float(axe[2] * s), float(math.cos(angle / 2.0))]


def _materiau_uni(couleur: list[float]):
    import trimesh
    materiau = trimesh.visual.material.PBRMaterial(
        name="interieur_mesure", baseColorFactor=[*couleur, 1.0], metallicFactor=0.0, roughnessFactor=0.85)
    return trimesh.visual.TextureVisuals(material=materiau)


def ecrire_glb(chemin: Path, base_surface, base_interieur, mobile_surface, mobile_dessous,
               liaison: dict[str, Any], temps: np.ndarray, valeurs: np.ndarray, extras: dict[str, Any]) -> None:
    import trimesh
    import glb_io
    pivot = np.asarray(liaison["pivot"], dtype=float)
    scene = trimesh.Scene()
    scene.graph.update(frame_to="base", frame_from=scene.graph.base_frame, matrix=np.eye(4))
    scene.graph.update(frame_to="partie_mobile", frame_from=scene.graph.base_frame,
                       matrix=trimesh.transformations.translation_matrix(pivot))
    scene.add_geometry(base_surface, node_name="base_surface", geom_name="base_surface", parent_node_name="base")
    if len(base_interieur.faces):
        scene.add_geometry(base_interieur, node_name="base_interieur", geom_name="base_interieur", parent_node_name="base")
    surface_locale = mobile_surface.copy()
    surface_locale.apply_translation(-pivot)
    scene.add_geometry(surface_locale, node_name="partie_mobile_surface", geom_name="partie_mobile_surface",
                       parent_node_name="partie_mobile")
    if len(mobile_dessous.faces):
        dessous_local = mobile_dessous.copy()
        dessous_local.apply_translation(-pivot)
        scene.add_geometry(dessous_local, node_name="partie_mobile_dessous", geom_name="partie_mobile_dessous",
                           parent_node_name="partie_mobile")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(scene.export(file_type="glb"))

    doc, blob = glb_io.load(chemin)
    noms = [n.get("name") for n in doc["nodes"]]
    if "partie_mobile" not in noms:
        raise RuntimeError("nœud de la pièce mobile absent de l'export")
    indice = noms.index("partie_mobile")
    noeud = doc["nodes"][indice]
    matrice = noeud.pop("matrix", None)
    if matrice is not None:
        M = np.asarray(matrice, dtype=float).reshape(4, 4).T
        if not np.allclose(M[:3, :3], np.eye(3), atol=1e-6):
            raise RuntimeError("le nœud mobile ne doit porter qu'une translation au repos")
        noeud["translation"] = [float(x) for x in M[:3, 3]]
    else:
        noeud["translation"] = [float(x) for x in pivot]

    if liaison["type"] == "charniere":
        sortie = np.asarray([_quaternion(liaison["axe"], liaison["signe"] * v) for v in valeurs], dtype=np.float32)
        chemin_anim, type_sortie = "rotation", "VEC4"
    else:
        direction = np.asarray(liaison["direction"], dtype=float)
        sortie = np.asarray([pivot + direction * v for v in valeurs], dtype=np.float32)
        chemin_anim, type_sortie = "translation", "VEC3"

    donnees = bytearray(blob)

    def ajouter(tableau: np.ndarray) -> int:
        while len(donnees) % 4:
            donnees.append(0)
        debut = len(donnees)
        donnees.extend(tableau.astype(np.float32).tobytes())
        doc["bufferViews"].append({"buffer": 0, "byteOffset": debut, "byteLength": int(tableau.nbytes)})
        return len(doc["bufferViews"]) - 1

    vue_temps = ajouter(temps)
    doc["accessors"].append({"bufferView": vue_temps, "componentType": 5126, "count": int(len(temps)),
                             "type": "SCALAR", "min": [float(temps.min())], "max": [float(temps.max())]})
    acces_temps = len(doc["accessors"]) - 1
    vue_sortie = ajouter(sortie)
    doc["accessors"].append({"bufferView": vue_sortie, "componentType": 5126, "count": int(len(sortie)),
                             "type": type_sortie})
    acces_sortie = len(doc["accessors"]) - 1
    doc.setdefault("animations", []).append({
        "name": "ouverture" if not extras["plan"].get("retour") else "ouverture_et_retour",
        "samplers": [{"input": acces_temps, "output": acces_sortie, "interpolation": "LINEAR"}],
        "channels": [{"sampler": 0, "target": {"node": indice, "path": chemin_anim}}],
    })
    while len(donnees) % 4:
        donnees.append(0)
    doc["buffers"][0]["byteLength"] = len(donnees)
    doc.setdefault("extras", {})["aurora_articulation"] = extras
    noeud.setdefault("extras", {})["aurora_liaison"] = {k: liaison[k] for k in liaison if k != "signe"}
    glb_io.save(chemin, doc, bytes(donnees))


# --------------------------------------------------------------------------- vérification

def _quaternion_vers_matrice(q: np.ndarray) -> np.ndarray:
    x, y, z, w = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def verifier(chemin: str | Path, *, source_etanche: bool | None = None, source_texturee: bool | None = None) -> dict[str, Any]:
    """Relit le GLB écrit et mesure le mouvement lui-même, sans croire l'écrivain."""
    import trimesh
    import glb_io
    chemin = Path(chemin)
    doc, blob = glb_io.load(chemin)
    noms = [n.get("name") for n in doc.get("nodes", [])]
    controles: dict[str, Any] = {}
    raisons: list[str] = []
    animations = doc.get("animations") or []
    canaux = [c for a in animations for c in a.get("channels", [])]
    cibles = {c["target"]["node"] for c in canaux}
    if "partie_mobile" not in noms or "base" not in noms:
        return {"ok": False, "raisons": ["pièces nommées absentes"], "controles": controles}
    i_mobile, i_base = noms.index("partie_mobile"), noms.index("base")
    controles["noeuds_animes"] = sorted(noms[i] for i in cibles)
    if cibles != {i_mobile}:
        raisons.append("seule la pièce mobile doit être animée (la base ou l'objet entier bouge)")
    if not canaux:
        return {"ok": False, "raisons": ["aucune animation"], "controles": controles}
    canal = canaux[0]
    echant = animations[0]["samplers"][canal["sampler"]]
    temps = glb_io.accessor(doc, blob, echant["input"]).reshape(-1).astype(float)
    sorties = glb_io.accessor(doc, blob, echant["output"]).astype(float)
    translation = np.asarray(doc["nodes"][i_mobile].get("translation", [0.0, 0.0, 0.0]), dtype=float)

    scene = trimesh.load(str(chemin), force="scene", process=False)
    def pieces(prefixe: str):
        resultat = []
        for nom in scene.graph.nodes_geometry:
            if nom.startswith(prefixe):
                transformation, geometrie = scene.graph[nom]
                maillage = scene.geometry[geometrie].copy()
                maillage.apply_transform(transformation)
                resultat.append(maillage)
        return trimesh.util.concatenate(resultat) if resultat else trimesh.Trimesh()
    base, mobile = pieces("base_"), pieces("partie_mobile_")
    if len(base.faces) == 0 or len(mobile.faces) == 0:
        return {"ok": False, "raisons": ["une pièce est vide"], "controles": controles}
    diagonale = float(np.linalg.norm(trimesh.util.concatenate([base, mobile]).extents))

    def poser(points: np.ndarray, k: int) -> np.ndarray:
        if canal["target"]["path"] == "rotation":
            R = _quaternion_vers_matrice(sorties[k])
            return (points - translation) @ R.T + translation
        return points - translation + sorties[k]

    sommets = mobile.vertices[:: max(1, len(mobile.vertices) // 5000)]
    deplacement = float(np.max(np.linalg.norm(poser(sommets, len(temps) - 1) - poser(sommets, 0), axis=1)))
    if not animations[0]["name"].endswith("retour"):
        deplacement_max = deplacement
    else:
        deplacement_max = max(float(np.max(np.linalg.norm(poser(sommets, k) - poser(sommets, 0), axis=1)))
                              for k in range(len(temps)))
    controles["deplacement_relatif"] = round(deplacement_max / diagonale, 4)
    if deplacement_max / diagonale < MIN_DEPLACEMENT_RELATIF:
        raisons.append("la pièce mobile ne bouge presque pas")

    liaison = (doc["nodes"][i_mobile].get("extras") or {}).get("aurora_liaison") or {}
    if canal["target"]["path"] == "rotation":
        axe = np.asarray(liaison.get("axe", [1, 0, 0]), dtype=float)
        pivot = np.asarray(liaison.get("pivot", translation), dtype=float)
        points_axe = np.stack([pivot - axe * diagonale * 0.5, pivot, pivot + axe * diagonale * 0.5])
        derive = max(float(np.max(np.linalg.norm(poser(points_axe, k) - points_axe, axis=1))) for k in range(len(temps)))
        controles["derive_axe_relative"] = float(f"{derive / diagonale:.3g}")
        if derive / diagonale > TOLERANCE_AXE_RELATIVE:
            raisons.append("les points de la charnière se déplacent : la rotation ne suit pas l'axe annoncé")
        angles = []
        for q in sorties:
            q = q / np.linalg.norm(q)
            angle = 2.0 * math.atan2(float(np.linalg.norm(q[:3])), float(q[3]))
            angles.append(angle * (1.0 if float(q[:3] @ axe) >= 0 else -1.0))
        angles = np.abs(np.asarray(angles))
        controles["amplitude_finale_deg"] = round(math.degrees(float(angles.max())), 2)
        ouverture = angles[: int(np.argmax(angles)) + 1]
        if np.any(np.diff(ouverture) < -1e-5):
            raisons.append("l'ouverture n'est pas à sens unique")

    try:
        occupation = Occupation(base, diagonale / 110.0)
        points = _echantillons(mobile, 3000)
        indices = np.linspace(0, len(temps) - 1, min(9, len(temps))).astype(int)
        penetrations = [occupation.penetration(poser(points, k)) for k in indices]
        controles["penetration_max"] = round(float(max(penetrations)), 5)
        if max(penetrations) > MAX_PENETRATION:
            raisons.append("la pièce mobile traverse la base pendant le mouvement")
    except ImportError as exc:
        controles["penetration_max"] = None
        raisons.append(f"collision non mesurable ({exc.name} absent)")

    def etanche(maillage) -> bool:
        copie = maillage.copy()
        copie.merge_vertices(merge_tex=True, merge_norm=True)
        return bool(copie.is_watertight)
    controles["base_etanche"], controles["mobile_etanche"] = etanche(base), etanche(mobile)
    if source_etanche and not (controles["base_etanche"] and controles["mobile_etanche"]):
        raisons.append("la découpe a ouvert des trous dans une pièce")
    textures = sum(1 for m in doc.get("materials", []) if (m.get("pbrMetallicRoughness") or {}).get("baseColorTexture"))
    controles["materiaux_textures"] = textures
    if source_texturee and textures == 0:
        raisons.append("la texture de l'objet a été perdue")
    return {"ok": not raisons, "raisons": raisons, "controles": controles}


# --------------------------------------------------------------------------- orchestration

def animer(entree: str | Path, demande: str, sortie: str | Path, *, plan: dict[str, Any] | None = None,
           interroger: Callable[[str], str] | None = None, rapport: str | Path | None = None,
           ips: int = 30) -> dict[str, Any]:
    """Anime la pièce mobile décrite par `demande` et vérifie le résultat écrit."""
    entree, sortie = Path(entree), Path(sortie)
    resultat: dict[str, Any] = {"schema": SCHEMA_EXTRAS, "entree": str(entree), "sortie": str(sortie), "demande": demande}

    def fin(ok: bool, **elements) -> dict[str, Any]:
        resultat.update(ok=ok, **elements)
        if rapport:
            Path(rapport).parent.mkdir(parents=True, exist_ok=True)
            Path(rapport).write_text(json.dumps(resultat, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
        return resultat

    plan = plan or planifier(demande, interroger=interroger)
    resultat["plan"] = plan
    if not plan.get("ok"):
        return fin(False, raison=f"plan cinématique indisponible : {plan.get('raison')}")
    if not plan["mouvement_de_piece"]:
        return fin(False, raison="la demande ne décrit pas une pièce qui bouge par rapport au reste", hors_portee=True)
    if not plan["piece_couvre_toute_la_face"]:
        return fin(False, hors_portee=True,
                   raison="pièce mobile partielle (elle n'occupe pas tout un côté) : segmentation par région non disponible")

    maillage, soude = charger(entree)
    couleurs = couleurs_des_faces(maillage)
    axe = SIDES[plan["position_piece_mobile"]]
    couture = trouver_couture(maillage, soude, axe, plan["fraction_estimee"], couleurs)
    resultat["couture"] = {k: v for k, v in couture.items() if k not in ("t_min",)}
    origine = np.asarray(couture["origine"])
    mobile_surface, base_surface = couper(maillage, origine, axe)
    if len(mobile_surface.faces) < 0.005 * len(maillage.faces) or len(base_surface.faces) < 0.005 * len(maillage.faces):
        return fin(False, raison="la coupe ne sépare pas deux pièces de taille utile")
    polygones, vers_3d = polygones_de_coupe(soude, origine, axe)
    interieur = couleur_interieure(maillage, couleurs, couture)
    mobile_dessous = trianguler(polygones, vers_3d, -axe)
    hauteur_base = couture["fraction"] * couture["etendue"]
    if plan["base_contenant"]:
        largeur = min(min(p.minimum_rotated_rectangle.exterior.length / 4.0, math.sqrt(p.area)) for p in polygones)
        base_interieur = construire_cavite(polygones, vers_3d, axe, profondeur=0.75 * hauteur_base, paroi=0.07 * largeur)
    else:
        base_interieur = trianguler(polygones, vers_3d, axe)
    for piece in (mobile_dessous, base_interieur):
        if len(piece.faces):
            piece.visual = _materiau_uni(interieur)

    import trimesh
    base_complete = trimesh.util.concatenate([base_surface, base_interieur]) if len(base_interieur.faces) else base_surface
    mobile_complet = trimesh.util.concatenate([mobile_surface, mobile_dessous]) if len(mobile_dessous.faces) else mobile_surface
    diagonale = float(np.linalg.norm(soude.extents))
    occupation = Occupation(base_complete, diagonale / 110.0)
    points = _echantillons(mobile_complet)

    if plan["articulation"] == "charniere":
        candidats = [plan["cote_attache"]] if plan["cote_attache"] != "inconnu" else \
            [c for c in SIDES if c not in (plan["position_piece_mobile"], OPPOSITE[plan["position_piece_mobile"]])]
        essais = []
        for cote in candidats:
            liaison = ajuster_charniere(polygones, vers_3d, cote, axe)
            centre = mobile_complet.centroid
            pivot, direction = np.asarray(liaison["pivot"]), np.asarray(liaison["axe"])
            tourne = (centre - pivot) @ rotation(direction, math.radians(3.0)).T + pivot
            signe = 1 if (tourne - centre) @ axe > 0 else -1
            libre, mesures = amplitude_libre(points, occupation, pivot, direction, signe, plan["amplitude_deg"])
            essais.append({**liaison, "signe": signe, "amplitude_libre_deg": libre, "mesures": mesures[-4:]})
        # La physique tranche ; à égalité (à 2° près), l'arrière, opposé à la face qu'on regarde.
        meilleur_libre = max(e["amplitude_libre_deg"] for e in essais)
        egaux = [e for e in essais if e["amplitude_libre_deg"] >= meilleur_libre - 2.0]
        choisi = next((e for e in egaux if e["cote"] == "back"), egaux[0])
        resultat["essais_charniere"] = [{k: e[k] for k in ("cote", "amplitude_libre_deg", "residu")} for e in essais]
        if choisi["amplitude_libre_deg"] < AMPLITUDE_MIN_DEG:
            return fin(False, raison=f"aucune charnière ne permet d'ouvrir de plus de {AMPLITUDE_MIN_DEG:.0f}° sans traverser la base")
        amplitude = min(plan["amplitude_deg"], choisi["amplitude_libre_deg"])
        liaison = {"type": "charniere", "cote": choisi["cote"], "pivot": choisi["pivot"], "axe": choisi["axe"],
                   "signe": choisi["signe"], "residu_ajustement": round(choisi["residu"], 6),
                   "amplitude_demandee_deg": plan["amplitude_deg"], "amplitude_retenue_deg": round(amplitude, 2),
                   "bornee_par_collision": amplitude < plan["amplitude_deg"] - 1e-6}
        temps, valeurs = chronologie(plan, math.radians(amplitude), ips)
    else:
        direction = axe
        course = plan["course_relative"] * couture["etendue"]
        liaison = {"type": "glissiere", "direction": direction.tolist(),
                   "pivot": np.asarray(mobile_complet.centroid).tolist(), "course": round(course, 6)}
        temps, valeurs = chronologie(plan, course, ips)

    extras = {"schema": SCHEMA_EXTRAS, "plan": {k: plan[k] for k in plan if k not in ("schema", "ok")},
              "couture": resultat["couture"], "liaison": {k: v for k, v in liaison.items() if k != "signe"},
              "couleur_interieure_mesuree": interieur, "convention": "+Y haut, face avant +Z, droite vue de face +X"}
    ecrire_glb(sortie, base_surface, base_interieur, mobile_surface, mobile_dessous, liaison, temps, valeurs, extras)
    resultat["liaison"] = extras["liaison"]
    source_texturee = couleurs is not None and getattr(getattr(maillage, "visual", None), "uv", None) is not None
    verdict = verifier(sortie, source_etanche=bool(soude.is_watertight), source_texturee=source_texturee)
    resultat["verification"] = verdict
    if not verdict["ok"]:
        return fin(False, raison="la vérification du fichier écrit a échoué : " + " ; ".join(verdict["raisons"]))
    return fin(True)


def main() -> int:
    import argparse
    analyseur = argparse.ArgumentParser(description="Anime la pièce mobile d'un objet reconstruit (couvercle, porte, rabat…)")
    analyseur.add_argument("--input", required=True)
    analyseur.add_argument("--request", required=True)
    analyseur.add_argument("--output", required=True)
    analyseur.add_argument("--report", default=None)
    arguments = analyseur.parse_args()
    resultat = animer(arguments.input, arguments.request, arguments.output, rapport=arguments.report)
    print(json.dumps({k: resultat.get(k) for k in ("ok", "raison", "liaison", "couture", "verification")},
                     ensure_ascii=False, indent=2, default=float))
    return 0 if resultat.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
