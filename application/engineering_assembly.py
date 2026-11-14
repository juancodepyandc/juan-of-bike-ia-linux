"""Graphe d'assemblage : des pièces (nœuds) reliées par des liaisons typées (arêtes).

Ce module fait le travail d'un ingénieur avant le premier perçage :
  1. il normalise les exigences (pièces, matières, procédés, positions, liaisons) ;
  2. il développe les motifs (quatre bras disposés en croix, n pieds alignés) et décompose une
     pièce que le procédé ne sait pas faire d'un bloc (un bac en bois devient cinq panneaux
     assemblés, avec les liaisons d'angle qui conviennent) ;
  3. il place chaque pièce par contact (« dessus », « derrière », « centré sur », « en rayon »),
     comme les contraintes d'un logiciel de CAO, sans coordonnées dictées par la demande ;
  4. il mesure sur les solides les interfaces réelles entre deux pièces (faces en contact ou face à
     face avec un écart), là où les liaisons pourront poser leurs usinages.

Repère de conception : millimètres, Z vers le haut, X vers la droite vue de face, la face avant
regarde −Y. L'export glTF le convertit (+Y haut, face avant +Z, droite +X : convention du moteur
articulé `python-services/articulated_motion.py`).

Aucune règle ne dépend d'un sujet : seulement de la géométrie, des matières et des procédés.
"""
from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from application import engineering_standards as normes

SCHEMA_GRAPHE = "aurora.graphe-assemblage.v1"
FORMES = ("bloc", "cylindre", "tube", "bac", "equerre")
SYNONYMES_FORMES = {"plaque": "bloc", "panneau": "bloc", "barre": "bloc", "bras": "bloc", "planche": "bloc",
                    "disque": "cylindre", "axe": "cylindre", "rond": "cylindre", "boitier": "bac", "caisse": "bac",
                    "boite": "bac", "contenant": "bac", "cornière": "equerre", "corniere": "equerre"}
TYPES_LIAISON = ("vis", "boulon_ecrou", "emmanchement", "clip", "charniere", "colle", "soudure", "queue_aronde", "aimant")
SYNONYMES_LIAISON = {"visse": "vis", "vissage": "vis", "boulon": "boulon_ecrou", "boulonnage": "boulon_ecrou",
                     "tourillon": "emmanchement", "goupille": "emmanchement", "chevillage": "emmanchement",
                     "ajustement_serre": "emmanchement", "clips": "clip", "clipsage": "clip", "encliquetage": "clip",
                     "loquet_clip": "clip", "pivot": "charniere", "charnière": "charniere", "collage": "colle",
                     "adhesif": "colle", "queue_d_aronde": "queue_aronde", "queue d'aronde": "queue_aronde",
                     "magnetique": "aimant", "aimants": "aimant"}
COTES = {"dessus": np.array([0.0, 0.0, 1.0]), "dessous": np.array([0.0, 0.0, -1.0]),
         "avant": np.array([0.0, -1.0, 0.0]), "arriere": np.array([0.0, 1.0, 0.0]),
         "gauche": np.array([-1.0, 0.0, 0.0]), "droite": np.array([1.0, 0.0, 0.0])}
SYNONYMES_COTES = {"devant": "avant", "derriere": "arriere", "derrière": "arriere", "haut": "dessus", "bas": "dessous",
                   "sur": "dessus", "sous": "dessous", "face": "avant", "dos": "arriere", "interieur": "dedans",
                   "dans": "dedans", "dedans": "dedans", "autour": "dessus"}
OPPOSE = {"dessus": "dessous", "dessous": "dessus", "avant": "arriere", "arriere": "avant", "gauche": "droite",
          "droite": "gauche"}
MAX_PIECES = 400
TOL = 1e-4


class ErreurConception(ValueError):
    """Exigence inexploitable ou conception impossible : le message dit pourquoi, en français."""


# --------------------------------------------------------------------------- géométrie de base

def manifold():
    import manifold3d
    return manifold3d


def segments(rayon: float) -> int:
    return int(min(96, max(24, round(2 * math.pi * rayon / 0.6))))


def boite(taille, centre=(0.0, 0.0, 0.0)):
    m3 = manifold()
    taille = [float(x) for x in taille]
    return m3.Manifold.cube(taille, True).translate(tuple(float(c) for c in centre))


def cylindre(rayon: float, hauteur: float, axe, centre, nseg: int | None = None):
    """Cylindre d'axe quelconque, centré sur `centre`."""
    m3 = manifold()
    c = m3.Manifold.cylinder(float(hauteur), float(rayon), float(rayon), nseg or segments(rayon), True)
    return c.transform(matrice_vers_3x4(alignement_z_vers(axe, centre)))


def cone(r_bas: float, r_haut: float, hauteur: float, axe, base, nseg: int | None = None):
    """Tronc de cône dont la base (rayon r_bas) est sur `base`, s'élevant selon `axe`."""
    m3 = manifold()
    c = m3.Manifold.cylinder(float(hauteur), float(r_bas), float(r_haut), nseg or segments(max(r_bas, r_haut)), False)
    return c.transform(matrice_vers_3x4(alignement_z_vers(axe, base)))


def prisme_hexagonal(sur_plats: float, hauteur: float, axe, centre, rotation_deg: float = 0.0):
    m3 = manifold()
    r = sur_plats / math.sqrt(3.0)
    pts = [(r * math.cos(math.radians(60 * k + rotation_deg)), r * math.sin(math.radians(60 * k + rotation_deg)))
           for k in range(6)]
    p = m3.Manifold.extrude(m3.CrossSection([pts]), float(hauteur)).translate((0.0, 0.0, -hauteur / 2.0))
    return p.transform(matrice_vers_3x4(alignement_z_vers(axe, centre)))


def extrusion_profil(points_2d, longueur: float, repere: np.ndarray):
    """Profil 2D (x, y) extrudé sur z ∈ [0, longueur], puis posé par la matrice 4×4 `repere`."""
    m3 = manifold()
    pts = [(float(x), float(y)) for x, y in points_2d]
    if _aire_signee(pts) < 0:
        pts = pts[::-1]
    p = m3.Manifold.extrude(m3.CrossSection([pts]), float(longueur))
    return p.transform(matrice_vers_3x4(repere))


def _aire_signee(pts) -> float:
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                     for i in range(len(pts)))


def matrice_vers_3x4(M: np.ndarray):
    return [[float(M[i, j]) for j in range(4)] for i in range(3)]


def alignement_z_vers(axe, origine) -> np.ndarray:
    """Matrice 4×4 qui envoie +Z sur `axe` et l'origine sur `origine`."""
    a = np.asarray(axe, dtype=float)
    a = a / np.linalg.norm(a)
    z = np.array([0.0, 0.0, 1.0])
    M = np.eye(4)
    c = float(np.dot(z, a))
    if c > 1 - 1e-12:
        R = np.eye(3)
    elif c < -1 + 1e-12:
        R = np.diag([1.0, -1.0, -1.0])
    else:
        v = np.cross(z, a)
        s = np.linalg.norm(v)
        K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        R = np.eye(3) + K + K @ K * ((1 - c) / (s * s))
    M[:3, :3] = R
    M[:3, 3] = np.asarray(origine, dtype=float)
    return M


def rotation_z(angle_deg: float) -> np.ndarray:
    a = math.radians(angle_deg)
    M = np.eye(4)
    M[:2, :2] = [[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]
    return M


def translation(v) -> np.ndarray:
    M = np.eye(4)
    M[:3, 3] = np.asarray(v, dtype=float)
    return M


def rotation_axe(axe, angle_rad: float, pivot) -> np.ndarray:
    a = np.asarray(axe, dtype=float)
    a = a / np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    R = np.eye(3) + math.sin(angle_rad) * K + (1 - math.cos(angle_rad)) * K @ K
    M = np.eye(4)
    M[:3, :3] = R
    p = np.asarray(pivot, dtype=float)
    M[:3, 3] = p - R @ p
    return M


def vers_trimesh(solide):
    import trimesh
    m = solide.to_mesh64()
    sommets = np.asarray(m.vert_properties, dtype=np.float64)[:, :3]
    faces = np.asarray(m.tri_verts, dtype=np.int64)
    return trimesh.Trimesh(vertices=sommets, faces=faces, process=True)


def volume(solide) -> float:
    return float(solide.volume()) if not solide.is_empty() else 0.0


def boite_englobante(solide) -> np.ndarray:
    b = solide.bounding_box()
    return np.array([b[:3], b[3:]], dtype=float)


def union(solides):
    m3 = manifold()
    solides = [s for s in solides if s is not None and not s.is_empty()]
    if not solides:
        return m3.Manifold()
    if len(solides) == 1:
        return solides[0]
    return m3.Manifold.batch_boolean(solides, m3.OpType.Add)


# --------------------------------------------------------------------------- pièces

@dataclass
class Piece:
    id: str
    nom: str
    forme: str
    dims: list[float]
    matiere: str
    procede: str
    origine: str = "fabrique"            # fabrique | achete | standard (quincaillerie normalisée) | procede
    fonction: str = ""
    reference: str = ""
    paroi: float | None = None
    fond: float | None = None
    ouverture: str = "dessus"
    axe: str = "z"
    position: dict[str, Any] | None = None
    motif: dict[str, Any] | None = None
    trous_existants: dict[str, Any] | None = None
    base_id: str | None = None           # pièce d'origine d'une instance de motif ou d'un panneau
    instance: int | None = None
    orientation_deg: float = 0.0         # rotation autour de Z (repère de conception)
    centre: np.ndarray = field(default_factory=lambda: np.zeros(3))
    solide: Any = None                   # solide de base, repère monde
    ajouts: list[Any] = field(default_factory=list)
    retraits: list[Any] = field(default_factory=list)
    final: Any = None
    article: dict[str, Any] | None = None    # quincaillerie : norme, d, longueur, désignation…
    hote: str | None = None              # pièce qui porte la quincaillerie (prémontage, vue éclatée)
    approche: np.ndarray | None = None   # direction d'où la pièce arrive (quincaillerie)
    liaison: str | None = None           # liaison qui a créé la quincaillerie
    teinte: float = 1.0

    @property
    def est_quincaillerie(self) -> bool:
        return self.origine in ("standard", "procede")

    def taille_locale(self) -> np.ndarray:
        if self.forme in ("bloc", "bac"):
            return np.asarray(self.dims[:3], dtype=float)
        if self.forme == "equerre":
            longueur, aile_a, aile_b, _ = self.dims
            return np.array([longueur, aile_a, aile_b], dtype=float)
        d, h = (self.dims[0], self.dims[-1])
        axe = "xyz".index(self.axe)
        taille = np.array([d, d, d], dtype=float)
        taille[axe] = h
        return taille

    def repere(self) -> np.ndarray:
        return translation(self.centre) @ rotation_z(self.orientation_deg)


def solide_de_forme(p: Piece):
    """Solide de base dans le repère local (centré sur sa boîte englobante), puis posé."""
    t = p.taille_locale()
    if p.forme == "bloc":
        local = boite(t)
    elif p.forme == "cylindre":
        local = cylindre(p.dims[0] / 2.0, p.dims[-1], np.eye(3)["xyz".index(p.axe)], (0, 0, 0))
    elif p.forme == "tube":
        d_ext, d_int, h = p.dims
        axe = np.eye(3)["xyz".index(p.axe)]
        local = cylindre(d_ext / 2.0, h, axe, (0, 0, 0)) - cylindre(d_int / 2.0, h + 2.0, axe, (0, 0, 0))
    elif p.forme == "bac":
        paroi = float(p.paroi)
        fond = float(p.fond if p.fond is not None else paroi)
        ouvert = COTES[p.ouverture]
        k = int(np.argmax(np.abs(ouvert)))
        interieur = t - 2 * paroi
        interieur[k] = t[k] - fond + 2.0
        decal = np.zeros(3)
        decal[k] = np.sign(ouvert[k]) * (fond / 2.0 + 1.0)
        local = boite(t) - boite(interieur, decal)
    elif p.forme == "equerre":
        longueur, aile_a, aile_b, ep = p.dims
        # aile horizontale (Y) et aile verticale (Z), extrudées le long de X, coin en (y_min, z_min)
        h1 = boite([longueur, aile_a, ep], (0, 0, -aile_b / 2.0 + ep / 2.0))
        h2 = boite([longueur, ep, aile_b], (0, -aile_a / 2.0 + ep / 2.0, 0))
        local = h1 + h2
    else:
        raise ErreurConception(f"forme inconnue : {p.forme}")
    return local.transform(matrice_vers_3x4(p.repere()))


# --------------------------------------------------------------------------- normalisation

def _slug(texte: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "_", t).strip("_").lower()
    return t[:48] or "piece"


def _nombre(valeur, bas: float, haut: float, defaut: float | None = None, nom: str = "valeur") -> float:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)) or not math.isfinite(valeur):
        if defaut is None:
            raise ErreurConception(f"{nom} : nombre requis")
        return float(defaut)
    if not bas <= valeur <= haut:
        raise ErreurConception(f"{nom} = {valeur} hors de l'intervalle [{bas}, {haut}]")
    return float(valeur)


def normaliser_cote(cote: Any) -> str | None:
    if not isinstance(cote, str):
        return None
    c = _slug(cote)
    c = SYNONYMES_COTES.get(c, c)
    return c if c in COTES or c == "dedans" else None


def normaliser(exigences: dict[str, Any]) -> dict[str, Any]:
    """Contrôle et complète les exigences ; lève ErreurConception avec la liste des écarts."""
    if not isinstance(exigences, dict):
        raise ErreurConception("exigences : objet requis")
    ecarts: list[str] = []
    procede_general = normes.resoudre_procede(exigences.get("procede"))
    matiere_generale = normes.resoudre_matiere(exigences.get("matiere"))
    pieces_brutes = exigences.get("pieces")
    if not isinstance(pieces_brutes, list) or not pieces_brutes:
        raise ErreurConception("aucune pièce décrite")
    if len(pieces_brutes) > 64:
        raise ErreurConception("plus de 64 pièces décrites : décomposer en sous-ensembles")
    pieces: list[dict[str, Any]] = []
    ids: set[str] = set()
    alias: dict[str, str] = {}
    hypotheses_moteur: list[str] = []
    for i, brut in enumerate(pieces_brutes):
        if not isinstance(brut, dict):
            ecarts.append(f"pièce {i + 1} : objet requis")
            continue
        pid = _slug(brut.get("id") or brut.get("nom") or f"piece_{i + 1}")
        base = pid
        k = 2
        while pid in ids:
            pid = f"{base}_{k}"
            k += 1
        ids.add(pid)
        for cle in (brut.get("id"), brut.get("nom")):
            if isinstance(cle, str) and cle.strip():
                alias.setdefault(_slug(cle), pid)
        forme = _slug(brut.get("forme") or "bloc")
        forme = SYNONYMES_FORMES.get(forme, forme)
        if forme not in FORMES:
            ecarts.append(f"{pid} : forme « {brut.get('forme')} » inconnue (formes : {', '.join(FORMES)})")
            continue
        dims = brut.get("dimensions_mm")
        attendu = {"bloc": 3, "bac": 3, "cylindre": 2, "tube": 3, "equerre": 4}[forme]
        if not isinstance(dims, list) or len(dims) != attendu or not all(
                isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and 0.3 <= x <= 5000 for x in dims):
            ecarts.append(f"{pid} : dimensions_mm doit contenir {attendu} nombres entre 0,3 et 5000 mm pour la forme {forme}")
            continue
        origine = brut.get("origine", "fabrique")
        origine = "achete" if _slug(str(origine)) in ("achete", "achat", "commerce", "purchased", "acheter") else "fabrique"
        mat = normes.resoudre_matiere(brut.get("matiere"))
        if origine == "achete" and mat is None:
            mat = "composant"
        mat = mat or matiere_generale or "pla"
        proc = normes.resoudre_procede(brut.get("procede"))
        if origine == "achete":
            proc = "achat"
        proc = proc or (procede_general if procede_general and procede_general != "achat" else None) \
            or normes.PROCEDE_PAR_FAMILLE[normes.MATIERES[mat]["famille"]]
        piece = {"id": pid, "nom": str(brut.get("nom") or pid)[:80], "fonction": str(brut.get("fonction") or "")[:200],
                 "forme": forme, "dims": [float(x) for x in dims], "matiere": mat, "procede": proc, "origine": origine,
                 "reference": str(brut.get("reference") or "")[:120]}
        if forme == "tube" and not dims[1] < dims[0]:
            ecarts.append(f"{pid} : le diamètre intérieur d'un tube doit être inférieur à l'extérieur")
        if forme == "bac":
            paroi = brut.get("paroi_mm")
            if not isinstance(paroi, (int, float)) or isinstance(paroi, bool) or not 0.4 <= paroi <= min(dims) / 2.5:
                # non précisée (ou impossible) : règle d'ingénierie, consignée comme hypothèse
                valeur, regle = normes.paroi_par_defaut(dims, proc, mat)
                paroi = min(valeur, min(dims) / 2.5)
                hypotheses_moteur.append(f"{pid} : épaisseur de paroi non précisée, {paroi:g} mm retenus ({regle})")
            piece["paroi"] = round(float(paroi), 2)
            fond = brut.get("fond_mm")
            piece["fond"] = round(float(fond), 2) if isinstance(fond, (int, float)) and 0.4 <= fond < dims[2] / 2 else piece["paroi"]
            ouverture = normaliser_cote(brut.get("ouverture") or "dessus")
            piece["ouverture"] = ouverture if ouverture in COTES else "dessus"
            angles = brut.get("assemblage_angles")
            if isinstance(angles, str) and angles.strip():
                t = _slug(angles)
                piece["assemblage_angles"] = SYNONYMES_LIAISON.get(t, t)
        if forme in ("cylindre", "tube"):
            axe = str(brut.get("axe") or "z").lower()
            piece["axe"] = axe if axe in ("x", "y", "z") else "z"
        if forme == "equerre" and not dims[3] < min(dims[1], dims[2]):
            ecarts.append(f"{pid} : l'épaisseur d'une équerre doit être inférieure à ses ailes")
        if brut.get("base") is True:
            piece["base"] = True
        if isinstance(brut.get("position"), dict):
            piece["position"] = dict(brut["position"])
        motif = brut.get("motif")
        quantite = brut.get("quantite", brut.get("nombre"))
        if isinstance(motif, dict) and isinstance(motif.get("nombre"), (int, float)) and motif["nombre"] >= 2:
            piece["motif"] = dict(motif)
        elif isinstance(quantite, int) and not isinstance(quantite, bool) and 2 <= quantite <= 64:
            # quantité sans disposition : en couronne autour de la référence (bras, pieds, plots), alignée sinon
            pos = brut.get("position") if isinstance(brut.get("position"), dict) else {}
            cote = normaliser_cote(pos.get("cote")) if pos else None
            piece["motif"] = ({"type": "polaire", "nombre": quantite, "angle_depart_deg": 0.0}
                              if cote in ("dessus", "dessous", None) else
                              {"type": "lineaire", "nombre": quantite, "pas_mm": float(dims[0]) * 1.5, "direction": "x"})
            hypotheses_moteur.append(f"{pid} : {quantite} exemplaires sans disposition précisée, "
                                     + ("en couronne" if piece["motif"]["type"] == "polaire" else "alignés"))
        trous = brut.get("trous_existants")
        if origine == "achete" and isinstance(trous, dict) and (
                (isinstance(trous.get("entraxe_mm"), list) and len(trous["entraxe_mm"]) == 2 and all(
                    isinstance(x, (int, float)) and x > 0 for x in trous["entraxe_mm"]))
                or (isinstance(trous.get("diametre_cercle_mm"), (int, float)) and trous["diametre_cercle_mm"] > 0)):
            piece["trous_existants"] = dict(trous)
        orient = brut.get("orientation_deg")
        if isinstance(orient, (int, float)) and math.isfinite(orient):
            piece.setdefault("position", {})["orientation_deg"] = float(orient)
        pieces.append(piece)
    if ecarts:
        raise ErreurConception(" ; ".join(ecarts))

    def resoudre(ref: Any) -> str | None:
        if not isinstance(ref, str) or not ref.strip():
            return None
        s = _slug(ref)
        if s in ids:
            return s
        return alias.get(s)

    racines = [p for p in pieces if p.get("base")] or [p for p in pieces if not p.get("position")]
    racine = racines[0] if racines else pieces[0]
    racine.pop("position", None)
    for p in pieces:
        pos = p.get("position")
        if p is racine:
            continue
        if not pos:
            pos = {"par_rapport_a": racine["id"], "cote": "dessus"}
            p["position"] = pos
        ref = resoudre(pos.get("par_rapport_a"))
        if ref is None or ref == p["id"]:
            ecarts.append(f"{p['id']} : position « par_rapport_a » doit nommer une autre pièce")
            continue
        pos["par_rapport_a"] = ref
        cote = normaliser_cote(pos.get("cote") or "dessus")
        if cote is None:
            ecarts.append(f"{p['id']} : côté « {pos.get('cote')} » inconnu")
            continue
        pos["cote"] = cote
        if pos.get("centre_sur") is not None:
            centre = resoudre(pos.get("centre_sur"))
            if centre is None:
                ecarts.append(f"{p['id']} : « centre_sur » nomme une pièce inconnue")
            else:
                pos["centre_sur"] = centre
    # Les positions doivent former un arbre enraciné (pas de cycle).
    parents = {p["id"]: (p.get("position") or {}).get("par_rapport_a") for p in pieces}
    for pid in parents:
        vus = set()
        n = pid
        while parents.get(n):
            if n in vus:
                ecarts.append(f"positions circulaires autour de {pid}")
                break
            vus.add(n)
            n = parents[n]
    liaisons = []
    for j, brut in enumerate(exigences.get("liaisons") or []):
        if not isinstance(brut, dict):
            ecarts.append(f"liaison {j + 1} : objet requis")
            continue
        entre = [resoudre(r) for r in (brut.get("entre") or [])]
        if len(entre) < 2 or any(e is None for e in entre) or len(set(entre)) != len(entre):
            ecarts.append(f"liaison {j + 1} : « entre » doit nommer au moins deux pièces distinctes connues "
                          f"(reçu {brut.get('entre')}, pièces : {', '.join(sorted(ids))})")
            continue
        type_brut = _slug(brut.get("type") or "")
        type_ = SYNONYMES_LIAISON.get(type_brut, type_brut)
        if type_ not in TYPES_LIAISON:
            ecarts.append(f"liaison {j + 1} : type « {brut.get('type')} » inconnu ({', '.join(TYPES_LIAISON)})")
            continue
        if type_ != "boulon_ecrou" and len(entre) != 2:
            ecarts.append(f"liaison {j + 1} : une liaison {type_} relie exactement deux pièces")
            continue
        liaison = {"id": _slug(brut.get("id") or f"{type_}_{'_'.join(entre)}")[:60], "type": type_, "entre": entre,
                   "demontable": bool(brut.get("demontable", type_ in ("vis", "boulon_ecrou", "aimant", "clip"))),
                   "justification": str(brut.get("justification") or "")[:300]}
        bord = normaliser_cote(brut.get("bord")) if brut.get("bord") else None
        if bord in COTES:
            liaison["bord"] = bord
        for cle, bas, haut in (("effort_N", 0.0, 1e6), ("amplitude_deg", 5.0, 270.0), ("nombre", 1, 64)):
            v = brut.get(cle)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and bas <= v <= haut:
                liaison[cle] = float(v) if cle != "nombre" else int(v)
        liaisons.append(liaison)
    if ecarts:
        raise ErreurConception(" ; ".join(ecarts))
    vus_ids: set[str] = set()
    for l in liaisons:
        base = l["id"]
        k = 2
        while l["id"] in vus_ids:
            l["id"] = f"{base}_{k}"
            k += 1
        vus_ids.add(l["id"])
    return {"schema": SCHEMA_GRAPHE, "titre": str(exigences.get("titre") or "Assemblage")[:120],
            "fonctions": [str(f)[:160] for f in (exigences.get("fonctions") or []) if isinstance(f, str)][:12],
            "hypotheses": [str(h)[:240] for h in (exigences.get("hypotheses") or []) if isinstance(h, str)][:20] + hypotheses_moteur,
            "contraintes": [str(c)[:240] for c in (exigences.get("contraintes") or []) if isinstance(c, str)][:20],
            "racine": racine["id"], "pieces": pieces, "liaisons": liaisons}


# --------------------------------------------------------------------------- motifs et décomposition

def developper_motifs(graphe: dict[str, Any], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """Une pièce à motif devient n instances ; ce qui se place sur elle et ses liaisons suivent."""
    g = copy.deepcopy(graphe)
    pieces = {p["id"]: p for p in g["pieces"]}
    instances: dict[str, list[str]] = {}

    def nombre_motif(p) -> int:
        m = p.get("motif") or {}
        n = m.get("nombre")
        return int(n) if isinstance(n, (int, float)) and not isinstance(n, bool) and 2 <= n <= 64 else 0

    def aire_empreinte(d) -> float:
        if d["forme"] in ("cylindre", "tube") and d.get("axe", "z") == "z":
            return math.pi * d["dims"][0] ** 2 / 4.0
        if d["forme"] == "equerre":
            return d["dims"][0] * d["dims"][1]
        if d["forme"] in ("cylindre", "tube"):
            return d["dims"][0] * d["dims"][-1]
        return d["dims"][0] * d["dims"][1]

    ordre = _ordre_positions(g)
    nouvelles: list[dict[str, Any]] = []
    for pid in ordre:
        p = pieces[pid]
        ref = (p.get("position") or {}).get("par_rapport_a")
        pos = p.get("position") or {}
        if ref in instances and not pos.get("centre_sur") and not nombre_motif(p) \
                and aire_empreinte(p) > 1.5 * aire_empreinte(pieces[ref]):
            # plus grande qu'une instance : une seule pièce, centrée sur le centre du motif
            centre_motif = (pieces[ref].get("position") or {}).get("par_rapport_a")
            if centre_motif:
                pos["centre_sur"] = centre_motif
                decisions.append({"sujet": pid, "decision": f"pièce unique posée sur les {len(instances[ref])} {ref}",
                                  "raison": f"son empreinte dépasse celle d'un {ref} : elle les couvre tous, centrée sur {centre_motif}"})
        n = nombre_motif(p)
        if n and ref in instances and n == len(instances[ref]) and pos.get("centre_sur") in (None, ref):
            # posée sur une pièce répétée avec un motif du même nombre : une par instance, pas une ronde autour de la première
            decisions.append({"sujet": pid, "decision": f"suit les {n} {ref} (une par instance)",
                              "raison": "motif de même nombre que la pièce répétée qui la porte"})
            p.pop("motif", None)
            n = 0
        if n:
            m = p["motif"]
            type_m = _slug(m.get("type") or "polaire")
            copies = []
            for k in range(n):
                c = copy.deepcopy(p)
                c["id"] = f"{pid}_{k + 1}"
                c["base_id"] = pid
                c["instance"] = k + 1
                c.pop("motif", None)
                if type_m.startswith("lin"):
                    pas = float(m.get("pas_mm") or 0.0) or (p["dims"][0] * 1.5)
                    direction = str(m.get("direction") or "x").lower()
                    c["_motif_decalage"] = {"axe": direction if direction in ("x", "y", "z") else "x",
                                            "valeur": (k - (n - 1) / 2.0) * pas}
                else:
                    depart = float(m.get("angle_depart_deg") or 0.0)
                    c["_motif_angle"] = depart + k * 360.0 / n
                    c["_motif_nombre"] = n
                    if isinstance(m.get("rayon_mm"), (int, float)) and m["rayon_mm"] > 0:
                        c["_motif_rayon"] = float(m["rayon_mm"])
                copies.append(c)
            instances[pid] = [c["id"] for c in copies]
            nouvelles.extend(copies)
            decisions.append({"sujet": pid, "decision": f"motif {type_m} de {n} exemplaires",
                              "raison": "la demande décrit des pièces identiques répétées"})
        elif ref in instances and not ((p.get("position") or {}).get("centre_sur") not in (None, ref)
                                       and (p.get("position") or {}).get("centre_sur") not in instances):
            # posée sur une pièce répétée et centrée sur elle : répétée avec elle (un moteur par bras) ;
            # centrée sur une pièce unique, elle reste unique et s'appuie sur toutes les instances
            copies = []
            for k, ref_k in enumerate(instances[ref]):
                c = copy.deepcopy(p)
                c["id"] = f"{pid}_{k + 1}"
                c["base_id"] = pid
                c["instance"] = k + 1
                c["position"]["par_rapport_a"] = ref_k
                if c["position"].get("centre_sur") == ref:
                    c["position"]["centre_sur"] = ref_k          # centré sur SA propre instance
                copies.append(c)
            instances[pid] = [c["id"] for c in copies]
            nouvelles.extend(copies)
        else:
            nouvelles.append(p)
    # positions qui visent une pièce démultipliée sans la suivre : la première instance porte le contact
    for p in nouvelles:
        pos = p.get("position")
        if pos and pos.get("par_rapport_a") in instances:
            pos["_contact_multiple"] = instances[pos["par_rapport_a"]]
            pos["par_rapport_a"] = instances[pos["par_rapport_a"]][0]
        if pos and pos.get("centre_sur") in instances:
            pos["centre_sur"] = instances[pos["centre_sur"]][0]
    g["pieces"] = nouvelles
    liaisons = []
    for l in g["liaisons"]:
        multiples = [e for e in l["entre"] if e in instances]
        if not multiples:
            liaisons.append(l)
            continue
        n = len(instances[multiples[0]])
        if any(len(instances[e]) != n for e in multiples):
            raise ErreurConception(f"liaison {l['id']} : motifs de tailles différentes")
        for k in range(n):
            c = copy.deepcopy(l)
            c["id"] = f"{l['id']}_{k + 1}"
            c["entre"] = [instances[e][k] if e in instances else e for e in l["entre"]]
            liaisons.append(c)
    g["liaisons"] = liaisons
    return g


def _ordre_positions(g: dict[str, Any]) -> list[str]:
    pieces = {p["id"]: p for p in g["pieces"]}
    ordre: list[str] = []
    vus: set[str] = set()

    def visiter(pid: str) -> None:
        if pid in vus:
            return
        vus.add(pid)
        pos = pieces[pid].get("position") or {}
        for cle in ("par_rapport_a", "centre_sur"):
            if pos.get(cle) in pieces:
                visiter(pos[cle])
        ordre.append(pid)

    for pid in pieces:
        visiter(pid)
    return ordre


def decomposer_contenants(graphe: dict[str, Any], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """Un bac que son procédé ne sait pas produire d'un bloc devient des panneaux assemblés.

    Règle de fabrication : on imprime ou on moule un bac d'une pièce ; on l'usine d'une pièce s'il
    est petit ; en bois, en plaque découpée ou en tôle, on l'assemble à partir de panneaux. Les
    liaisons d'angle sont choisies pour que le montage reste possible pièce par pièce.
    """
    g = copy.deepcopy(graphe)
    nouvelles: list[dict[str, Any]] = []
    nouvelles_liaisons: list[dict[str, Any]] = []
    for p in g["pieces"]:
        if p["forme"] != "bac" or p["origine"] != "fabrique":
            nouvelles.append(p)
            continue
        proc = p["procede"]
        monobloc = normes.PROCEDES[proc]["imprime"] or proc == "moulage" or (proc == "usinage" and max(p["dims"]) <= 250)
        if monobloc:
            nouvelles.append(p)
            continue
        if p["ouverture"] != "dessus":
            raise ErreurConception(f"{p['id']} : décomposition en panneaux disponible pour un bac ouvert sur le dessus")
        W, D, H = p["dims"]
        t = float(p["paroi"])
        tf = float(p["fond"])
        famille = normes.MATIERES[p["matiere"]]["famille"]
        demande = p.get("assemblage_angles")
        angle = demande if demande in ("queue_aronde", "emmanchement", "vis", "colle", "soudure") else (
            "soudure" if famille == "metal" and proc == "tolerie" else "vis" if famille == "metal" else "emmanchement")
        base = p["id"]
        paroi_min = float(normes.PROCEDES[proc]["paroi_min"])
        # règles de menuiserie : une vis dans la tranche exige ~3 fois son avant-trou en largeur, un tourillon
        # Ø5 deux parois minimales autour de lui ; sous ces épaisseurs, l'assemblage est collé
        vissable = t >= max(9.0, 2 * paroi_min + 3.0)
        chevillable = t >= 2 * paroi_min + 5.0
        if angle == "emmanchement" and not chevillable:
            angle = "colle"
        if angle == "queue_aronde" and t < 2 * paroi_min + 6.0:
            angle = "colle"
        panneaux = {
            "fond": ([W, D, tf], [0.0, 0.0, -H / 2 + tf / 2], "fond"),
            "avant": ([W, t, H - tf], [0.0, -D / 2 + t / 2, tf / 2], "face avant"),
            "arriere": ([W, t, H - tf], [0.0, D / 2 - t / 2, tf / 2], "face arrière"),
            "gauche": ([t, D - 2 * t, H - tf], [-W / 2 + t / 2, 0.0, tf / 2], "côté gauche"),
            "droite": ([t, D - 2 * t, H - tf], [W / 2 - t / 2, 0.0, tf / 2], "côté droit"),
        }
        for cle, (taille, decalage, nom) in panneaux.items():
            nouvelles.append({"id": f"{base}_{cle}", "nom": f"{p['nom']} — {nom}", "forme": "bloc", "dims": taille,
                              "matiere": p["matiere"], "procede": proc, "origine": "fabrique",
                              "fonction": f"panneau du {p['nom']}", "reference": "", "base_id": base,
                              "_panneau_de": base, "_decalage_panneau": decalage,
                              "position": p.get("position"), "base": p.get("base", False)})
        for mur in ("avant", "arriere", "gauche", "droite"):
            if vissable or angle == "soudure":
                nouvelles_liaisons.append({"id": f"{base}_fond_{mur}_{'vis' if angle != 'soudure' else 'soudure'}",
                                           "type": "vis" if angle != "soudure" else "soudure",
                                           "entre": [f"{base}_fond", f"{base}_{mur}"], "demontable": False,
                                           "justification": "fond vissé par-dessous dans la tranche du panneau (fil long)"})
            if angle != "soudure":
                nouvelles_liaisons.append({"id": f"{base}_fond_{mur}_colle", "type": "colle",
                                           "entre": [f"{base}_fond", f"{base}_{mur}"], "demontable": False,
                                           "justification": "collage du fond sur toute la tranche"})
        for cote in ("gauche", "droite"):
            for face in ("avant", "arriere"):
                if angle == "colle":
                    nouvelles_liaisons.append({"id": f"{base}_{face}_{cote}_colle", "type": "colle",
                                               "entre": [f"{base}_{face}", f"{base}_{cote}"], "demontable": False,
                                               "justification": f"angle {face}/{cote} collé (panneaux trop minces pour tourillons)"})
                    continue
                nouvelles_liaisons.append({"id": f"{base}_{face}_{cote}_{angle}", "type": angle,
                                           "entre": [f"{base}_{face}", f"{base}_{cote}"], "demontable": False,
                                           "justification": f"angle {face}/{cote}"})
                if angle in ("emmanchement", "queue_aronde"):
                    nouvelles_liaisons.append({"id": f"{base}_{face}_{cote}_colle", "type": "colle",
                                               "entre": [f"{base}_{face}", f"{base}_{cote}"], "demontable": False,
                                               "justification": "collage de l'angle"})
        decisions.append({"sujet": base, "decision": f"bac fabriqué en 5 panneaux, angles par {angle}",
                          "raison": f"le procédé « {normes.PROCEDES[proc]['nom']} » ne produit pas un bac d'un seul bloc ; "
                                    + ("fond soudé" if angle == "soudure" else "fond vissé et collé par-dessous" if vissable
                                       else f"panneaux de {t:g} mm : fond collé (trop mince pour une vis dans la tranche)")
                                    + ", angles " + ("soudés" if angle == "soudure" else "collés" if angle == "colle"
                                                     else "assemblés puis collés" if angle != "vis" else "vissés")})
    ids = {p["id"] for p in nouvelles}
    for p in nouvelles:
        pos = p.get("position")
        if pos and pos.get("par_rapport_a") not in ids:
            pos["_contenant"] = pos["par_rapport_a"]
        if pos and pos.get("centre_sur") and pos["centre_sur"] not in ids:
            pos["_centre_contenant"] = pos["centre_sur"]
    g["pieces"] = nouvelles
    g["liaisons"] = g["liaisons"] + nouvelles_liaisons
    return g


# --------------------------------------------------------------------------- placement

def _vers_piece(d: dict[str, Any]) -> Piece:
    p = Piece(id=d["id"], nom=d["nom"], forme=d["forme"], dims=list(d["dims"]), matiere=d["matiere"],
              procede=d["procede"], origine=d["origine"], fonction=d.get("fonction", ""),
              reference=d.get("reference", ""), paroi=d.get("paroi"), fond=d.get("fond"),
              ouverture=d.get("ouverture", "dessus"), axe=d.get("axe", "z"), position=d.get("position"),
              trous_existants=d.get("trous_existants"), base_id=d.get("base_id"), instance=d.get("instance"))
    return p


def _englobante(p: Piece) -> np.ndarray:
    return boite_englobante(p.solide)


def placer(graphe: dict[str, Any], decisions: list[dict[str, Any]]) -> dict[str, Piece]:
    """Pose chaque pièce par contact avec sa référence. Rend les pièces placées (repère monde)."""
    donnees = {d["id"]: d for d in graphe["pieces"]}
    enveloppes: dict[str, Piece] = {}     # enveloppe d'un contenant décomposé, pour s'y référer
    pieces: dict[str, Piece] = {}
    contenants: dict[str, dict[str, Any]] = {}
    for d in graphe["pieces"]:
        if d.get("_panneau_de"):
            contenants.setdefault(d["_panneau_de"], {"panneaux": [], "position": d.get("position"),
                                                     "base": d.get("base")})["panneaux"].append(d)

    def obtenir(ref: str) -> Piece:
        if ref in pieces:
            return pieces[ref]
        if ref in enveloppes:
            return enveloppes[ref]
        raise ErreurConception(f"référence de position inconnue : {ref}")

    def poser(p: Piece, pos: dict[str, Any] | None, angle_motif: float | None, decal_motif: dict | None,
              rayon_motif: float | None = None, nombre_motif: int | None = None) -> None:
        """Contact selon la normale du côté choisi, alignements et décalages dans le repère local de la
        pièce de centrage (un bras tourné à 45° s'aligne sur sa propre longueur, pas sur les axes du monde)."""
        if not pos:
            p.orientation_deg = 0.0
            p.centre = np.array([0.0, 0.0, p.taille_locale()[2] / 2.0])
            p.solide = solide_de_forme(p)
            return
        ref = obtenir(pos["_contenant"] if pos.get("_contenant") else pos["par_rapport_a"])
        centre_ref = obtenir(pos["centre_sur"]) if pos.get("centre_sur") else (
            obtenir(pos["_centre_contenant"]) if pos.get("_centre_contenant") else ref)
        cote = pos["cote"]
        orientation = float(pos.get("orientation_deg") or 0.0)
        p.orientation_deg = centre_ref.orientation_deg + (angle_motif or 0.0) + orientation
        Rc = rotation_z(centre_ref.orientation_deg)[:3, :3]
        refs_contact = [obtenir(r) for r in pos.get("_contact_multiple", [])] or [ref]
        alignement = pos.get("alignement") or {}
        if isinstance(alignement, str):
            alignement = {"_": alignement}
        if isinstance(alignement, dict) and "axe" in alignement:
            # variantes d'écriture d'une lecture libre : {"axe": "x", "valeur"|"bord"|"type"|"sens": "max"}
            valeur = next((alignement[k] for k in ("valeur", "bord", "type", "sens", "cote") if k in alignement), None)
            alignement = {str(alignement["axe"]).lower(): valeur} if valeur is not None else {}
        # 1. normale de contact (monde) et position le long de cette normale
        if cote == "dedans":
            if ref.forme != "bac":
                raise ErreurConception(f"{p.id} : « dedans » exige une référence creuse (bac)")
            n_w = np.array([0.0, 0.0, 1.0])
            fond = float(ref.fond if ref.fond is not None else ref.paroi)
            le_long = float(_englobante(ref)[0][2]) + fond + float(pos.get("hauteur_mm") or 0.0) + demi_etendue(p, n_w)
        else:
            n_w = COTES[cote] if cote in ("dessus", "dessous") else rotation_z(ref.orientation_deg)[:3, :3] @ COTES[cote]
            le_long = max(projection_max(r, n_w) for r in refs_contact) + demi_etendue(p, n_w)
        # 2. axes du plan de contact dans le repère de centrage
        axes = [Rc @ np.eye(3)[i] for i in range(3)]
        noms = ["x", "y", "z"]
        plan = [(noms[i], a) for i, a in enumerate(axes) if abs(float(a @ n_w)) < 0.5]
        c = n_w * le_long
        cible_alignement = {"avant": ("y", "min"), "arriere": ("y", "max"), "gauche": ("x", "min"), "droite": ("x", "max"),
                            "dessus": ("z", "max"), "haut": ("z", "max"), "dessous": ("z", "min"), "bas": ("z", "min")}
        voulu: dict[str, str] = {}
        for cle, valeur in alignement.items():
            v = _slug(str(valeur))
            if cle in ("x", "y", "z") and v in ("min", "max", "centre"):
                voulu[cle] = v
            elif v in cible_alignement:
                axe, sens = cible_alignement[v]
                voulu[axe] = sens
        for nom, a in plan:
            centre_a = float(np.asarray(centre_ref.centre) @ a)
            if cote == "dedans":
                bb = _englobante(ref)
                centre_a = float(((bb[0] + bb[1]) / 2.0) @ a)
            sens = voulu.get(nom)
            if sens is None and nom == "z" and cote not in ("dessus", "dessous", "dedans"):
                sens = "min"                      # posé au même niveau que sa référence
            if sens == "max":
                pos_a = centre_a + demi_etendue(centre_ref, a) - demi_etendue(p, a)
            elif sens == "min":
                pos_a = centre_a - demi_etendue(centre_ref, a) + demi_etendue(p, a)
            else:
                pos_a = centre_a
            c = c + a * pos_a
        # 3. disposition rayonnante (motif polaire) : la longueur locale X pointe vers l'extérieur
        radial = pos.get("radial") if isinstance(pos.get("radial"), dict) else None
        if angle_motif is not None and radial is None and cote in ("dessus", "dessous"):
            radial = {}
        if radial is not None and cote in ("dessus", "dessous"):
            direction = rotation_z(p.orientation_deg)[:3, :3] @ np.array([1.0, 0.0, 0.0])
            longueur = float(p.taille_locale()[0])
            sortie = _sortie_empreinte(centre_ref, direction)
            # rayon intérieur minimal : deux pièces voisines de cette largeur ne se chevauchent pas au centre
            r_min = 0.0
            if nombre_motif and nombre_motif >= 2 and p.forme in ("bloc", "equerre"):
                r_min = (float(p.taille_locale()[1]) / 2.0) / math.tan(math.pi / nombre_motif) + 0.5
            if isinstance(radial.get("rayon_extremite_mm"), (int, float)) and radial["rayon_extremite_mm"] > 0:
                R = float(radial["rayon_extremite_mm"])
                if R - longueur < r_min:
                    nouvelle = R - r_min
                    if nouvelle < 0.3 * longueur:
                        raise ErreurConception(f"{p.id} : extrémité à {R:g} mm du centre impossible pour {nombre_motif} pièces de "
                                               f"{p.taille_locale()[1]:g} mm de large (rayon intérieur minimal {r_min:.1f} mm)")
                    decisions.append({"sujet": p.id, "decision": f"longueur ramenée de {longueur:g} à {nouvelle:.1f} mm",
                                      "raison": f"l'extrémité reste à {R:g} mm du centre (entraxe demandé) ; plus longues, les "
                                                f"{nombre_motif} pièces se chevaucheraient au centre (rayon intérieur ≥ {r_min:.1f} mm)"})
                    p.dims[0] = round(nouvelle, 2)
                    longueur = nouvelle
                r_centre = R - longueur / 2.0
            elif rayon_motif:
                r_centre = float(rayon_motif)
            elif p.forme in ("bloc", "equerre") and longueur >= 2.0 * float(p.taille_locale()[1]):
                recouvrement = radial.get("recouvrement_mm")
                if not isinstance(recouvrement, (int, float)) or recouvrement <= 0:
                    recouvrement = min(longueur * 0.3, sortie * 0.6)
                    decisions.append({"sujet": p.id, "decision": f"recouvrement de {recouvrement:.1f} mm sur {centre_ref.id}",
                                      "raison": "pièce rayonnante : environ un tiers de sa longueur pris sur la pièce centrale"})
                r_centre = max(sortie - float(recouvrement), r_min) + longueur / 2.0
            else:
                # pièce compacte répétée en cercle (pieds, plots) : à l'intérieur de l'empreinte, près du bord
                r_centre = max(0.0, sortie - float(max(p.taille_locale()[:2])) / 2.0 - 0.05 * sortie)
            vertical = n_w * float(c @ n_w)
            plan_c = np.asarray(centre_ref.centre, dtype=float)
            plan_c = plan_c - n_w * float(plan_c @ n_w)
            c = vertical + plan_c + direction * r_centre
        if decal_motif:
            c = c + Rc @ np.eye(3)["xyz".index(decal_motif["axe"])] * decal_motif["valeur"]
        decalage = pos.get("decalage_mm")
        if isinstance(decalage, list) and 1 <= len(decalage) <= 3 and all(isinstance(x, (int, float)) for x in decalage):
            dv = np.zeros(3)
            dv[:len(decalage)] = decalage
            c = c + Rc @ dv
        p.centre = c
        p.solide = solide_de_forme(p)

    ordre = _ordre_positions(graphe)
    faits: set[str] = set()
    for pid in ordre:
        d = donnees[pid]
        if d.get("_panneau_de"):
            base = d["_panneau_de"]
            if base not in enveloppes:
                info = contenants[base]
                env = Piece(id=base, nom=base, forme="bac", dims=[0, 0, 0], matiere=d["matiere"], procede=d["procede"])
                # enveloppe = boîte de tous les panneaux
                W = max(x["dims"][0] for x in info["panneaux"])
                D = max(x["dims"][1] for x in info["panneaux"])
                H = sum(x["dims"][2] for x in info["panneaux"] if x["id"].endswith("_fond")) + \
                    max(x["dims"][2] for x in info["panneaux"] if not x["id"].endswith("_fond"))
                env.dims = [W, D, H]
                fond_d = next(x for x in info["panneaux"] if x["id"].endswith("_fond"))
                env.paroi = next(x for x in info["panneaux"] if x["id"].endswith("_gauche"))["dims"][0]
                env.fond = fond_d["dims"][2]
                poser(env, info["position"], None, None)
                enveloppes[base] = env
            env = enveloppes[base]
            p = _vers_piece(d)
            p.orientation_deg = env.orientation_deg
            p.centre = env.centre + rotation_z(env.orientation_deg)[:3, :3] @ np.asarray(d["_decalage_panneau"], dtype=float)
            p.solide = solide_de_forme(p)
            pieces[pid] = p
            faits.add(pid)
            continue
        p = _vers_piece(d)
        poser(p, d.get("position"), d.get("_motif_angle"), d.get("_motif_decalage"), d.get("_motif_rayon"),
              d.get("_motif_nombre"))
        pieces[pid] = p
        faits.add(pid)
    for p in pieces.values():
        p.teinte = 0.94 + 0.12 * ((sum(map(ord, p.id)) % 7) / 6.0)
    return pieces


def demi_etendue(p: Piece, direction) -> float:
    """Demi-étendue de la boîte locale de p selon une direction du monde."""
    R = rotation_z(p.orientation_deg)[:3, :3]
    d = R.T @ np.asarray(direction, dtype=float)
    return float(np.abs(d) @ (p.taille_locale() / 2.0))


def projection_max(p: Piece, direction) -> float:
    return float(np.asarray(p.centre, dtype=float) @ np.asarray(direction, dtype=float)) + demi_etendue(p, direction)


def _sortie_empreinte(p: Piece, direction: np.ndarray) -> float:
    """Distance du centre de `p` au bord de son empreinte horizontale, selon `direction`."""
    from shapely.geometry import LineString
    emp = empreinte_horizontale(p)
    c = np.asarray(p.centre[:2])
    grand = float(np.linalg.norm(_englobante(p)[1] - _englobante(p)[0])) * 2 + 10
    ligne = LineString([tuple(c), tuple(c + direction[:2] * grand)])
    inter = emp.boundary.intersection(ligne)
    if inter.is_empty:
        return 0.0
    pts = [inter] if inter.geom_type == "Point" else list(getattr(inter, "geoms", []))
    distances = [float(np.linalg.norm(np.array([q.x, q.y]) - c)) for q in pts if q.geom_type == "Point"]
    return max(distances) if distances else 0.0


def empreinte_horizontale(p: Piece):
    from shapely.geometry import Polygon
    t = p.taille_locale()
    R = rotation_z(p.orientation_deg)[:3, :3]
    coins = [np.array(p.centre) + R @ np.array([sx * t[0] / 2, sy * t[1] / 2, 0.0])
             for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    if p.forme in ("cylindre", "tube") and p.axe == "z":
        from shapely.geometry import Point
        return Point(p.centre[0], p.centre[1]).buffer(p.dims[0] / 2.0, 64)
    return Polygon([(q[0], q[1]) for q in coins])


# --------------------------------------------------------------------------- interfaces

@dataclass
class Interface:
    a: str
    b: str
    normale: np.ndarray        # de A vers B
    origine: np.ndarray        # point du plan de la face de A
    e1: np.ndarray
    e2: np.ndarray
    polygone: Any              # shapely, coordonnées (e1, e2) relatives à `origine`
    ecart: float               # 0 = contact
    face_a: Any = None         # polygone complet de la face de A (même repère)
    face_b: Any = None

    @property
    def aire(self) -> float:
        return float(self.polygone.area)

    def monde(self, u: float, v: float, w: float = 0.0) -> np.ndarray:
        return self.origine + self.e1 * u + self.e2 * v + self.normale * w

    def plan(self, point) -> tuple[float, float]:
        d = np.asarray(point, dtype=float) - self.origine
        return float(d @ self.e1), float(d @ self.e2)


def base_plan(n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ref = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    e1 = np.cross(ref, n)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    return e1, e2


def faces_planes(solide) -> list[dict[str, Any]]:
    """Faces planes d'un solide : normale, point, polygone 2D (union de ses triangles)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    m = vers_trimesh(solide)
    groupes = [list(f) for f in m.facets]
    dans = set(i for g in groupes for i in g)
    groupes += [[i] for i in range(len(m.faces)) if i not in dans]
    faces = []
    for g in groupes:
        n = m.face_normals[g[0]]
        if not np.isfinite(n).all():
            continue
        n = n / np.linalg.norm(n)
        aire = float(m.area_faces[g].sum())
        if aire < 0.5:
            continue
        p0 = m.vertices[m.faces[g[0]][0]]
        e1, e2 = base_plan(n)
        tris = []
        for i in g:
            pts = m.vertices[m.faces[i]] - p0
            poly = Polygon([(float(q @ e1), float(q @ e2)) for q in pts])
            if poly.area > 1e-9:
                tris.append(poly)
        if not tris:
            continue
        faces.append({"normale": n, "point": p0, "e1": e1, "e2": e2, "polygone": unary_union(tris).buffer(0)})
    return faces


def interfaces(a: Piece, b: Piece, ecart_max: float = 60.0, solide_a=None, solide_b=None) -> list[Interface]:
    """Faces planes de A et B qui se regardent (normales opposées) et se recouvrent."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    sa, sb = solide_a or a.solide, solide_b or b.solide
    ba, bb = boite_englobante(sa), boite_englobante(sb)
    marge = ecart_max
    if np.any(ba[0] - marge > bb[1]) or np.any(bb[0] - marge > ba[1]):
        return []
    fa, fb = faces_planes(sa), faces_planes(sb)
    resultat: list[Interface] = []
    for x in fa:
        for y in fb:
            if float(x["normale"] @ y["normale"]) > -0.9995:
                continue
            ecart = float((y["point"] - x["point"]) @ x["normale"])
            if ecart < -1e-3 or ecart > ecart_max:
                continue
            # polygone de B dans le repère de la face de A
            coords = []
            for poly in getattr(y["polygone"], "geoms", [y["polygone"]]):
                ext = [y["point"] + y["e1"] * u + y["e2"] * v for u, v in poly.exterior.coords]
                trous = [[y["point"] + y["e1"] * u + y["e2"] * v for u, v in r.coords] for r in poly.interiors]
                proj = lambda P: [(float((q - x["point"]) @ x["e1"]), float((q - x["point"]) @ x["e2"])) for q in P]
                coords.append(Polygon(proj(ext), [proj(t) for t in trous]))
            poly_b = unary_union(coords).buffer(0)
            commun = x["polygone"].intersection(poly_b)
            if commun.is_empty or commun.area < 1.0:
                continue
            resultat.append(Interface(a=a.id, b=b.id, normale=x["normale"].copy(), origine=x["point"].copy(),
                                      e1=x["e1"].copy(), e2=x["e2"].copy(), polygone=commun.buffer(0),
                                      ecart=max(0.0, ecart), face_a=x["polygone"], face_b=poly_b))
    resultat.sort(key=lambda i: (i.ecart > 1e-3, -i.aire))
    return resultat


def interface_principale(a: Piece, b: Piece, bord: str | None = None, solide_a=None, solide_b=None) -> Interface | None:
    """Plus grande interface en contact, sinon la plus proche face à face (écart)."""
    cands = interfaces(a, b, solide_a=solide_a, solide_b=solide_b)
    if not cands:
        return None
    contacts = [c for c in cands if c.ecart <= 1e-3]
    if contacts:
        return max(contacts, key=lambda c: c.aire)
    # face à face : la grande face d'une carte au-dessus d'un fond, pas son chant près d'une paroi
    return max(cands, key=lambda c: c.aire / (1.0 + c.ecart / 5.0))


def profondeur(solide, point, direction, maximum: float = 2000.0) -> float:
    """Épaisseur de matière traversée depuis `point` (sur la surface) le long de `direction`."""
    d = np.asarray(direction, dtype=float)
    d = d / np.linalg.norm(d)
    p0 = np.asarray(point, dtype=float) + d * 1e-3
    p1 = p0 + d * maximum
    hits = solide.ray_cast(tuple(map(float, p0)), tuple(map(float, p1)))
    if not hits:
        return 0.0
    return float(hits[0].distance) * maximum + 1e-3
