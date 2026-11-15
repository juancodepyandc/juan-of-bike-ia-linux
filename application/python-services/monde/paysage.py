"""Paysages procéduraux du moteur « monde » : relief, eau, sol par pente et altitude, végétation dispersée.

Lois générales (aucune règle par sujet ni par lieu ; tout vient des vocabulaires RELIEFS et BIOMES) :
- relief : champ fractal PÉRIODIQUE synthétisé par spectre (FFT), pic d'énergie à la longueur d'onde du
  relief, pente spectrale fractale au-delà ; une part de bruit « en crêtes » proportionnelle à la raideur
  du relief (amplitude / longueur d'onde) ; puis une érosion thermique douce (la matière glisse là où la
  pente dépasse l'angle de talus) et un léger lissage. Les hauteurs finales tiennent dans [0, amplitude].
- eau : surface plane à un niveau ; le relief est creusé là où l'eau est demandée (cuvette au point le
  plus bas pour un lac, vallée à fond plat le long d'une courbe pour une rivière, rivage le long d'un bord
  pour la mer). Le fond est pris SOUS tout le relief non creusé (moins une profondeur bornée par
  l'amplitude) : seule l'eau demandée inonde ; une rivière suit le plus bas de plusieurs tracés ; les berges suivent un profil à deux pentes (rive douce, puis flanc de vallée),
  le relief naturel reprenant dès qu'il passe sous ce profil.
- sol : matériau du biome ; pente forte → roche ; altitude haute d'un relief élevé (> 50 m) → neige ; une
  bande de rivage (sable pour la mer, gravier pour une eau douce) ; le fond immergé en sable ou terre.
- végétation : échantillonnage de Poisson (Bridson) à la densité par hectare du biome, en évitant l'eau,
  les pentes de plus de 35° et la neige ; chaque objet est posé sur le relief (enfoncé selon la pente pour
  ne jamais flotter). Le budget de triangles est tenu en éclaircissant uniformément (rapporté).

`disperser` est réutilisable ailleurs (parcs d'une ville) ; `objet_provisoire` fabrique des silhouettes
simples aux dimensions moyennes du vocabulaire tant que le vrai générateur d'objets n'est pas branché :
toute fabrique a la signature `fabrique(categorie, graine, options) -> Objet`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

import numpy as np
import trimesh
from shapely.geometry.base import BaseGeometry
from trimesh.visual import TextureVisuals

from monde import geometrie as g
from monde import vocabulaire as voc
from monde.ir import Instance, Noeud, Objet, Partie, Pose

Fabrique = Callable[[str, int, dict], Objet]

PENTE_MAX_VEGETATION_DEG = 35.0      # au-delà, rien ne pousse ni ne tient (test mesuré)
PARTS_EAU = {"lac": 0.12, "riviere": 0.07, "mer": 0.38}   # part de la surface visée par type d'eau
PENTE_RIVE_DEG = 10.0              # rive douce le long de l'eau (lac, rivière)…
LARGEUR_RIVE_M = 22.0              # … sur cette largeur…
PENTE_FLANC_DEG = 30.0             # … puis flanc de vallée (sous les 35° où la végétation tient encore)


def _profil_berge(distance_rivage: np.ndarray) -> np.ndarray:
    """Élévation (m) au-dessus du fond à une distance (m) du bord de la pièce d'eau creusée."""
    d = np.maximum(0.0, distance_rivage)
    rive = np.minimum(d, LARGEUR_RIVE_M) * math.tan(math.radians(PENTE_RIVE_DEG))
    return rive + np.maximum(0.0, d - LARGEUR_RIVE_M) * math.tan(math.radians(PENTE_FLANC_DEG))


def _distance_rivage(elevation_m: float) -> float:
    """Inverse de `_profil_berge` : distance (m) au bord du fond où la berge atteint `elevation_m`."""
    rive_max = LARGEUR_RIVE_M * math.tan(math.radians(PENTE_RIVE_DEG))
    if elevation_m <= rive_max:
        return elevation_m / math.tan(math.radians(PENTE_RIVE_DEG))
    return LARGEUR_RIVE_M + (elevation_m - rive_max) / math.tan(math.radians(PENTE_FLANC_DEG))


def _profondeur_rel(A: float) -> float:
    """Profondeur d'eau en fraction de l'amplitude : 2 m ou 6 % de l'amplitude, jamais plus de sa moitié."""
    return min(max(2.0, 0.06 * A), 0.5 * A) / A
AMPLITUDE_NEIGE_M = 50.0             # un relief plus haut a des sommets enneigés
BUDGET_PAYSAGE = 1_000_000


# ── Outils ─────────────────────────────────────────────────────────────────────────────────────────
def _lisse(x: np.ndarray | float, a: float, b: float) -> np.ndarray:
    """smoothstep de a à b (0 avant a, 1 après b)."""
    t = np.clip((np.asarray(x, dtype=np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _graine(*cles: Any) -> int:
    """Graine dérivée stable (indépendante du hachage aléatoire de Python)."""
    h = 2166136261
    for c in cles:
        for octet in str(c).encode("utf-8"):
            h = ((h ^ octet) * 16777619) & 0xFFFFFFFF
    return h


def maillage_brut(sommets: np.ndarray, faces: np.ndarray, normales: np.ndarray, uv: np.ndarray) -> trimesh.Trimesh:
    """Maillage prêt pour l'export (normales par sommet, UV en mètres) sans passer par `finaliser`."""
    m = trimesh.Trimesh(vertices=np.asarray(sommets, dtype=np.float64), faces=np.asarray(faces, dtype=np.int64),
                        vertex_normals=np.asarray(normales, dtype=np.float64), process=False)
    m.visual = TextureVisuals(uv=np.asarray(uv, dtype=np.float64))
    return m


def triangles_objet(objet: Objet) -> int:
    return int(sum(len(p.maillage.faces) for p in objet.parties if p.maillage is not None))


# ── Silhouettes provisoires ────────────────────────────────────────────────────────────────────────
def _moyenne(intervalle: tuple[float, float]) -> float:
    return 0.5 * (float(intervalle[0]) + float(intervalle[1]))


def objet_provisoire(categorie: str, graine: int = 0, options: dict | None = None) -> Objet:
    """Silhouette simple d'une catégorie du vocabulaire, aux dimensions moyennes (ou demandées).

    Repère local (voir `monde.ir`) : centre de l'emprise au sol, face vers +Z. Matériaux : ceux du
    vocabulaire (emplacements de `CATEGORIES[c]["materiaux"]`), remplaçables par options["materiaux"].
    Volontairement léger (quelques dizaines de triangles) : c'est un remplaçant de mise au point.
    """
    options = dict(options or {})
    spec = voc.categorie(categorie)
    rng = np.random.default_rng(_graine("provisoire", categorie, graine))
    L = float(options.get("largeur") or _moyenne(spec["largeur"]))
    P = float(options.get("profondeur") or _moyenne(spec["profondeur"]))
    H = float(options.get("hauteur") or _moyenne(spec["hauteur"]))
    mats = dict(spec["materiaux"])
    mats.update(options.get("materiaux") or {})
    style = options.get("style")
    parties: list[Partie] = []

    def ajoute(m: trimesh.Trimesh, emplacement: str, nom: str = "") -> None:
        cle = mats.get(emplacement) or next(iter(mats.values()))
        parties.append(Partie(m, cle, nom or emplacement))

    if categorie == "arbre":
        style = style or spec["styles"][0]
        if "largeur" not in options:          # houppier proportionné à la hauteur dans la fourchette
            t = (H - spec["hauteur"][0]) / max(1e-6, spec["hauteur"][1] - spec["hauteur"][0])
            L = spec["largeur"][0] + float(np.clip(t, 0, 1)) * (spec["largeur"][1] - spec["largeur"][0])
            if style == "conifere":
                L *= 0.6
            P = L
        r_tronc = max(0.08, 0.018 * H)
        if style == "conifere":
            ajoute(g.cylindre(r_tronc, 0.3 * H, sections=6), "tronc")
            ajoute(g.tronc_de_cone(L / 2.0, 0.0, 0.82 * H, y=0.18 * H, sections=8), "feuillage")
        elif style == "palmier":
            ajoute(g.tronc_de_cone(r_tronc * 1.3, r_tronc * 0.8, 0.9 * H, sections=6), "tronc")
            ajoute(g.ellipsoide(L / 2.0, 0.12 * H, P / 2.0, y=0.9 * H, subdivisions=1, bruit=0.35,
                                graine=int(rng.integers(1 << 30))), "feuillage")
        else:
            haut_tronc = (0.5 if style == "bouleau" else 0.4) * H
            ajoute(g.cylindre(r_tronc, haut_tronc + 0.1 * H, sections=6), "tronc")
            ry = (H - haut_tronc) / 2.0
            ajoute(g.ellipsoide(L / 2.0, ry, P / 2.0, y=haut_tronc + ry, subdivisions=1, bruit=0.18,
                                graine=int(rng.integers(1 << 30))), "feuillage")
    elif categorie in ("buisson", "rocher"):
        bruit = 0.3 if categorie == "rocher" else 0.2
        m = g.ellipsoide(L / 2.0, H / 2.0, P / 2.0, y=H / 2.0, subdivisions=1, bruit=bruit,
                         graine=int(rng.integers(1 << 30)))
        ajoute(g.translation(m, dy=-float(m.bounds[0][1])), next(iter(mats)))     # bosselé, mais posé à y = 0
    elif categorie == "voiture":
        garde = 0.18 * H
        ajoute(g.boite(L, 0.42 * H, P, y=garde), "carrosserie", "caisse")
        ajoute(g.boite(L * 0.86, 0.36 * H, P * 0.5, y=garde + 0.42 * H, z=-0.06 * P), "vitres", "habitacle")
        for sx in (-1, 1):
            for sz in (-1, 1):
                x, z = sx * (L / 2.0 - 0.08), sz * (P / 2.0 - 0.75)
                ajoute(g.segment((x - 0.1 * sx, 0.32, z), (x + 0.1 * sx, 0.32, z), 0.32, sections=8), "pneus", "roue")
    elif categorie == "lampadaire_rue":
        r = 0.07
        ajoute(g.cylindre(r, H, sections=8), "mat")
        porte = min(1.2, max(0.4, P * 2.0))
        ajoute(g.segment((0, H - 0.05, 0), (0, H - 0.05, porte), 0.04, sections=6), "mat", "crosse")
        ajoute(g.boite(0.35, 0.18, 0.5, y=H - 0.3, z=porte), "lanterne")
    elif categorie == "banc_public":
        ajoute(g.boite(L, 0.08, P * 0.65, y=0.42, z=0.05 * P), "lattes", "assise")
        ajoute(g.boite(L, 0.4, 0.06, y=0.5, z=-P / 2.0 + 0.05), "lattes", "dossier")
        for sx in (-1, 1):
            ajoute(g.boite(0.07, 0.42, P * 0.7, x=sx * (L / 2.0 - 0.15)), "structure", "pied")
    elif categorie == "poubelle_rue":
        ajoute(g.cylindre(L / 2.0, H, sections=10), "structure")
    elif categorie == "fontaine":
        r = L / 2.0
        ajoute(g.revolution([(0, 0), (r, 0), (r, 0.5), (r - 0.3, 0.5), (r - 0.3, 0.12), (0, 0.12)], sections=24),
               "structure", "bassin")
        ajoute(g.cylindre(r - 0.3, 0.32, y=0.1, sections=24), "eau")
        ajoute(g.cylindre(0.18, H * 0.75, sections=10), "structure", "colonne")
        ajoute(g.revolution([(0, 0), (0.5, 0.0), (0.8, 0.25), (0.7, 0.3), (0, 0.15)], y=H * 0.72, sections=16),
               "structure", "vasque")
    elif categorie == "parasol":
        ajoute(g.cylindre(0.03, H, sections=6), "mat")
        ajoute(g.tronc_de_cone(L / 2.0, 0.05, 0.45, y=H - 0.45, sections=10), "toile")
    elif categorie == "feu_tricolore":
        ajoute(g.cylindre(0.06, H, sections=8), "mat")
        ajoute(g.boite(0.3, 0.9, 0.25, y=H - 0.9), "feux")
    elif categorie == "panneau":
        ajoute(g.cylindre(0.035, H, sections=6), "mat")
        ajoute(g.boite(L, L, 0.04, y=H - L), "plaque")
    elif categorie == "abribus":
        ajoute(g.boite(L, 0.08, P, y=H - 0.08), "toit")
        ajoute(g.boite(L, H - 0.1, 0.03, z=-P / 2.0 + 0.05), "parois")
        for sx in (-1, 1):
            ajoute(g.boite(0.08, H - 0.08, 0.08, x=sx * (L / 2.0 - 0.05), z=-P / 2.0 + 0.05), "structure", "poteau")
    elif categorie == "table_pique_nique":
        ajoute(g.boite(L, 0.06, P * 0.5, y=H - 0.06), "structure", "plateau")
        for sz in (-1, 1):
            ajoute(g.boite(L, 0.05, 0.3, y=0.42, z=sz * P * 0.38), "structure", "banc")
    elif categorie == "transat":
        ajoute(g.boite(L, 0.08, P * 0.7, y=0.3, z=0.15 * P), "toile", "assise")
        ajoute(g.boite(L, 0.08, P * 0.35, y=0.3, z=-0.3 * P), "toile", "dossier")
    else:
        ajoute(g.boite(L, H, P), next(iter(mats)))
    return Objet(nom=f"{categorie}_{graine}", categorie=categorie, parties=parties, largeur=L, profondeur=P,
                 hauteur=H, meta={"provisoire": True, "style": style})


# ── Échantillonnage de Poisson (Bridson) ───────────────────────────────────────────────────────────
def poisson_disque(x0: float, z0: float, x1: float, z1: float, rayon: float, graine: int = 0,
                   essais: int = 24, maximum: int = 200_000) -> np.ndarray:
    """Points (n, 2) dans [x0, x1] × [z0, z1] deux à deux distants d'au moins `rayon` (Bridson 2007)."""
    rng = np.random.default_rng(graine)
    cellule = rayon / math.sqrt(2.0)
    nx, nz = max(1, int(math.ceil((x1 - x0) / cellule))), max(1, int(math.ceil((z1 - z0) / cellule)))
    grille = -np.ones((nx, nz), dtype=np.int64)
    points: list[tuple[float, float]] = []
    actifs: list[int] = []
    r2 = rayon * rayon

    def ajoute(p: tuple[float, float]) -> None:
        i, j = int((p[0] - x0) / cellule), int((p[1] - z0) / cellule)
        grille[min(i, nx - 1), min(j, nz - 1)] = len(points)
        actifs.append(len(points))
        points.append(p)

    ajoute((float(rng.uniform(x0, x1)), float(rng.uniform(z0, z1))))
    while actifs and len(points) < maximum:
        k = int(rng.integers(len(actifs)))
        px, pz = points[actifs[k]]
        angles = rng.uniform(0.0, 2.0 * math.pi, essais)
        rayons = rayon * np.sqrt(rng.uniform(1.0, 4.0, essais))
        trouve = False
        for a, r in zip(angles, rayons):
            qx, qz = px + r * math.cos(a), pz + r * math.sin(a)
            if not (x0 <= qx < x1 and z0 <= qz < z1):
                continue
            i, j = int((qx - x0) / cellule), int((qz - z0) / cellule)
            ok = True
            for ii in range(max(0, i - 2), min(nx, i + 3)):
                for jj in range(max(0, j - 2), min(nz, j + 3)):
                    v = grille[ii, jj]
                    if v >= 0:
                        dx, dz = points[v][0] - qx, points[v][1] - qz
                        if dx * dx + dz * dz < r2:
                            ok = False
                            break
                if not ok:
                    break
            if ok:
                ajoute((qx, qz))
                trouve = True
                break
        if not trouve:
            actifs[k] = actifs[-1]
            actifs.pop()
    return np.asarray(points, dtype=np.float64).reshape(-1, 2)


@dataclass
class Espece:
    """Une entrée de végétation : catégorie, style (ou None), densité par hectare."""
    categorie: str
    style: str | None
    densite_ha: float
    options: dict = field(default_factory=dict)


def _especes(liste: Iterable) -> list[Espece]:
    sortie = []
    for e in liste:
        if isinstance(e, Espece):
            sortie.append(e)
        else:
            cat, style, densite = e[:3]
            sortie.append(Espece(cat, style, float(densite), dict(e[3]) if len(e) > 3 else {}))
    return sortie


def variantes(espece: Espece, nombre: int, fabrique: Fabrique, graine: int) -> list[Objet]:
    """`nombre` variantes d'une espèce, hauteurs réparties dans la fourchette du vocabulaire."""
    spec = voc.categorie(espece.categorie)
    lo, hi = spec["hauteur"]
    lo = float(espece.options.get("hauteur_min", lo))
    hi = float(espece.options.get("hauteur_max", hi))
    sortie = []
    for k in range(nombre):
        t = (k + 0.5) / nombre
        opts = {kk: v for kk, v in espece.options.items() if kk not in ("hauteur_min", "hauteur_max")}
        if espece.style:
            opts["style"] = espece.style
        opts.setdefault("hauteur", round(lo + t * (hi - lo), 2))
        sortie.append(fabrique(espece.categorie, _graine(graine, espece.categorie, espece.style, k), opts))
    return sortie


def _surface_acceptee(domaine: BaseGeometry, accepter, pente_deg, graine: int, echantillons: int = 6000) -> float:
    """Surface (m²) du domaine où les filtres acceptent un objet : semis uniforme sur la boîte englobante."""
    from shapely import contains_xy

    x0, z0, x1, z1 = domaine.bounds
    rng = np.random.default_rng(_graine(graine, "semis"))
    p = rng.uniform((x0, z0), (x1, z1), size=(echantillons, 2))
    ok = contains_xy(domaine, p[:, 0], p[:, 1])
    if accepter is not None:
        ok &= np.asarray(accepter(p[:, 0], p[:, 1]), dtype=bool)
    if pente_deg is not None:
        ok &= np.asarray(pente_deg(p[:, 0], p[:, 1])) <= PENTE_MAX_VEGETATION_DEG
    return float(ok.mean()) * (x1 - x0) * (z1 - z0)


def disperser_positions(domaine: BaseGeometry | tuple[float, float, float, float], especes: Iterable, *,
                        graine: int = 0, accepter: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None,
                        pente_deg: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None,
                        obstacles: Sequence[tuple[float, float, float]] = (),
                        largeurs: dict[tuple[str, str | None], float] | None = None) -> list[dict[str, Any]]:
    """Positions seules (sans géométrie) : pour chaque espèce, {"espece", "points" (n, 2), "voulu", "largeur"}.

    - densité par hectare de chaque espèce, rapportée à la surface ACCEPTÉE du domaine ;
    - Poisson-disque (Bridson) au rayon 0,6 × l'espacement moyen, puis tirage au nombre voulu ;
    - `accepter(x, z) -> bool[]` exclut des points (eau, allées, neige…), `pente_deg` les pentes > 35° ;
    - les grandes espèces d'abord ; une plus petite ne se pose pas sur l'emprise d'une plus grande ;
    - `obstacles` : disques (x, z, rayon) interdits ; `largeurs` : emprise par (catégorie, style), sinon la
      largeur moyenne du vocabulaire.
    """
    from shapely import contains_xy
    from scipy.spatial import cKDTree

    especes = _especes(especes)
    if isinstance(domaine, tuple):
        domaine = g.rectangle_xz(*domaine)
    if domaine.is_empty or domaine.area < 1.0 or not especes:
        return []
    x0, z0, x1, z1 = domaine.bounds
    jeux = []
    for e in especes:
        largeur = (largeurs or {}).get((e.categorie, e.style))
        if largeur is None:
            spec = voc.categorie(e.categorie)
            largeur = max(_moyenne(spec["largeur"]), _moyenne(spec["profondeur"]))
            if e.style == "conifere":
                largeur *= 0.6
        jeux.append((e, float(largeur)))
    jeux.sort(key=lambda j: -j[1])
    surface_acceptee = _surface_acceptee(domaine, accepter, pente_deg, graine)
    places_xy: list[np.ndarray] = [np.asarray([[o[0], o[1]] for o in obstacles], dtype=np.float64).reshape(-1, 2)]
    places_r: list[np.ndarray] = [np.asarray([o[2] for o in obstacles], dtype=np.float64)]
    sortie = []
    for e, largeur in jeux:
        espacement = math.sqrt(10_000.0 / max(e.densite_ha, 1e-6))
        rayon = max(0.45 * largeur, 0.6 * espacement)
        pts = poisson_disque(x0, z0, x1, z1, rayon, _graine(graine, "poisson", e.categorie, e.style))
        if len(pts):
            pts = pts[contains_xy(domaine, pts[:, 0], pts[:, 1])]
        if len(pts) and accepter is not None:
            pts = pts[np.asarray(accepter(pts[:, 0], pts[:, 1]), dtype=bool)]
        if len(pts) and pente_deg is not None:
            pts = pts[np.asarray(pente_deg(pts[:, 0], pts[:, 1])) <= PENTE_MAX_VEGETATION_DEG]
        tous_xy = np.vstack(places_xy)
        tous_r = np.concatenate(places_r)
        garde = 0.2 * largeur          # dégagement du pied : les houppiers voisins s'interpénètrent
        if len(pts) and len(tous_xy):
            arbre = cKDTree(tous_xy)
            voisins = arbre.query_ball_point(pts, r=garde + float(tous_r.max(initial=0.0)))
            ok = np.ones(len(pts), dtype=bool)
            for i, liste in enumerate(voisins):
                for j in liste:
                    if np.hypot(*(pts[i] - tous_xy[j])) < garde + tous_r[j]:
                        ok[i] = False
                        break
            pts = pts[ok]
        voulu = int(round(e.densite_ha * surface_acceptee / 10_000.0))
        rng = np.random.default_rng(_graine(graine, "choix", e.categorie, e.style))
        if len(pts) > voulu:
            pts = pts[np.sort(rng.choice(len(pts), voulu, replace=False))]
        sortie.append({"espece": e, "points": pts.reshape(-1, 2), "voulu": voulu, "largeur": largeur})
        places_xy.append(pts.reshape(-1, 2))
        places_r.append(np.full(len(pts), garde))
    return sortie


def disperser(domaine: BaseGeometry | tuple[float, float, float, float], especes: Iterable, *,
              fabrique: Fabrique = objet_provisoire, graine: int = 0,
              hauteur: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None,
              accepter: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None,
              pente_deg: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None,
              obstacles: Sequence[tuple[float, float, float]] = (), nb_variantes: int = 6,
              budget_triangles: int | None = None, y: float = 0.0) -> tuple[list[Instance], dict[str, Any]]:
    """Disperse des objets par Poisson-disque (voir `disperser_positions`) et les fabrique.

    `hauteur(x, z)` pose chaque objet sur le relief, au plus bas de son emprise (jamais en l'air), les
    minéraux enfoncés d'un quart de leur hauteur ; `nb_variantes` objets par espèce sont fabriqués puis
    réutilisés ; si le total dépasse `budget_triangles`, éclaircissement uniforme (rapporté).
    Retourne (instances, rapport).
    """
    especes = _especes(especes)
    rapport: dict[str, Any] = {"especes": [], "eclaircissement": 1.0}
    if not especes:
        return [], rapport
    jeux = {}
    for e in especes:
        objets = variantes(e, nb_variantes, fabrique, _graine(graine, "variantes"))
        jeux[(e.categorie, e.style)] = (objets, float(np.mean([triangles_objet(o) for o in objets])),
                                        float(np.mean([max(o.largeur, o.profondeur) for o in objets])))
    positions = disperser_positions(domaine, especes, graine=graine, accepter=accepter, pente_deg=pente_deg,
                                    obstacles=obstacles, largeurs={k: v[2] for k, v in jeux.items()})
    tirages = []
    for p in positions:
        e = p["espece"]
        objets, tri, largeur = jeux[(e.categorie, e.style)]
        tirages.append([e, objets, largeur, tri, p["points"], p["voulu"]])

    total = sum(len(t[4]) * t[3] for t in tirages)
    if budget_triangles is not None and total > budget_triangles > 0:
        f = budget_triangles / total
        rapport["eclaircissement"] = round(f, 4)
        for t in tirages:
            rng = np.random.default_rng(_graine(graine, "eclaircir", t[0].categorie, t[0].style))
            garder = int(math.floor(len(t[4]) * f))
            t[4] = t[4][np.sort(rng.choice(len(t[4]), garder, replace=False))] if garder < len(t[4]) else t[4]

    instances: list[Instance] = []
    for e, objets, largeur, tri, pts, voulu in tirages:
        rng = np.random.default_rng(_graine(graine, "pose", e.categorie, e.style))
        if not len(pts):
            rapport["especes"].append({"categorie": e.categorie, "style": e.style, "voulu": voulu, "pose": 0})
            continue
        choix = rng.integers(len(objets), size=len(pts))
        lacets = rng.uniform(0.0, 2.0 * math.pi, len(pts))
        if hauteur is not None:
            r = 0.3 * largeur
            echant = [hauteur(pts[:, 0] + dx, pts[:, 1] + dz) for dx, dz in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r))]
            sol = np.min(np.vstack(echant), axis=0)
        else:
            sol = np.full(len(pts), float(y))
        mineral = voc.categorie(e.categorie)["groupe"] == "mineral"
        for (px, pz), k, lacet, ys in zip(pts, choix, lacets, sol):
            o = objets[int(k)]
            enfoncement = 0.05 + (0.25 * o.hauteur if mineral else 0.0)
            instances.append(Instance(o, Pose(float(px), float(pz), float(lacet), float(ys) - enfoncement),
                                      meta={"categorie": e.categorie, "style": e.style}))
        rapport["especes"].append({"categorie": e.categorie, "style": e.style, "voulu": voulu, "pose": int(len(pts)),
                                   "triangles_par_objet": round(tri, 1)})
    rapport["triangles"] = int(sum(triangles_objet(i.objet) for i in instances))
    return instances, rapport


# ── Relief ─────────────────────────────────────────────────────────────────────────────────────────
def champ_fractal(n: int, taille: float, longueur_onde: float, graine: int, pente_spectrale: float = 2.0) -> np.ndarray:
    """Champ (n, n) périodique dans [0, 1] : spectre de puissance culminant à 1/longueur_onde, décroissant
    en k^-pente au-delà (fractal), coupé en k² en deçà (pas de bosse plus large que la longueur d'onde)."""
    rng = np.random.default_rng(graine)
    k = np.fft.fftfreq(n, d=taille / n)
    kx, kz = np.meshgrid(k, k, indexing="ij")
    kr = np.hypot(kx, kz)
    k0 = 1.0 / max(longueur_onde, 1e-6)
    rel = np.where(kr > 0, kr / k0, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        puissance = np.where(rel < 1.0, rel ** 2, rel ** (-pente_spectrale - 1.0))
    puissance[0, 0] = 0.0
    phase = rng.uniform(0.0, 2.0 * math.pi, (n, n))
    spectre = np.sqrt(puissance) * np.exp(1j * phase)
    champ = np.real(np.fft.ifft2(spectre))
    champ -= champ.min()
    return champ / max(float(champ.max()), 1e-12)


def eroder(h: np.ndarray, pas: float, iterations: int = 40, talus_deg: float = 40.0, taux: float = 0.25) -> np.ndarray:
    """Érosion thermique : là où la pente vers un voisin dépasse le talus, une part de l'excès descend."""
    h = h.copy()
    seuil = math.tan(math.radians(talus_deg)) * pas
    for _ in range(iterations):
        apport = np.zeros_like(h)
        for axe, dec in ((0, 1), (0, -1), (1, 1), (1, -1)):
            voisin = np.roll(h, dec, axis=axe)
            exces = h - voisin - seuil
            transfert = np.where(exces > 0, taux * 0.25 * exces, 0.0)
            apport -= transfert
            apport += np.roll(transfert, -dec, axis=axe)
        h += apport
    return h


def _flou(h: np.ndarray, passes: int = 1) -> np.ndarray:
    for _ in range(passes):
        h = (4 * h + np.roll(h, 1, 0) + np.roll(h, -1, 0) + np.roll(h, 1, 1) + np.roll(h, -1, 1)) / 8.0
    return h


class Relief:
    """Hauteur du terrain : `relief(x, z) -> y` (vectorisé, interpolation bilinéaire de la grille), pente
    en degrés, niveau de l'eau (None sans eau) et test « dans l'eau »."""

    def __init__(self, hauteurs: np.ndarray, taille: float, niveau_eau: float | None, amplitude: float):
        self.h = hauteurs                       # (n+1, n+1), indice [i, j] ↔ (x, z)
        self.taille = float(taille)
        self.n = hauteurs.shape[0] - 1
        self.pas = self.taille / self.n
        self.niveau_eau = niveau_eau
        self.amplitude = float(amplitude)
        gx, gz = np.gradient(hauteurs, self.pas)
        self._pente = np.degrees(np.arctan(np.hypot(gx, gz)))

    def _bilineaire(self, grille: np.ndarray, x, z) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        z = np.asarray(z, dtype=np.float64)
        u = np.clip((x + self.taille / 2.0) / self.pas, 0.0, self.n - 1e-9)
        v = np.clip((z + self.taille / 2.0) / self.pas, 0.0, self.n - 1e-9)
        i, j = np.floor(u).astype(int), np.floor(v).astype(int)
        fu, fv = u - i, v - j
        return ((1 - fu) * (1 - fv) * grille[i, j] + fu * (1 - fv) * grille[i + 1, j]
                + (1 - fu) * fv * grille[i, j + 1] + fu * fv * grille[i + 1, j + 1])

    def __call__(self, x, z) -> np.ndarray:
        return self._bilineaire(self.h, x, z)

    def pente_deg(self, x, z) -> np.ndarray:
        return self._bilineaire(self._pente, x, z)

    def dans_eau(self, x, z, marge: float = 0.3) -> np.ndarray:
        if self.niveau_eau is None:
            return np.zeros(np.shape(np.asarray(x)), dtype=bool)
        return self(x, z) < self.niveau_eau + marge


def _courbe_traversante(rng: np.random.Generator, taille: float, n: int = 64) -> np.ndarray:
    """Courbe sinueuse (n, 2) qui traverse le carré [-taille/2, taille/2]² d'un bord à l'autre."""
    angle = rng.uniform(0.0, math.pi)
    d = np.array([math.cos(angle), math.sin(angle)])
    perp = np.array([-d[1], d[0]])
    t = np.linspace(-0.75, 0.75, n) * taille
    amp1, amp2 = rng.uniform(0.06, 0.12) * taille, rng.uniform(0.02, 0.05) * taille
    ph1, ph2 = rng.uniform(0, 2 * math.pi, 2)
    lam = rng.uniform(0.8, 1.3) * taille
    decalage = rng.uniform(-0.12, 0.12) * taille
    off = decalage + amp1 * np.sin(2 * math.pi * t / lam + ph1) + amp2 * np.sin(2 * math.pi * t / (lam / 2.7) + ph2)
    return t[:, None] * d[None, :] + off[:, None] * perp[None, :]


def _distance_polyligne(px: np.ndarray, pz: np.ndarray, courbe: np.ndarray) -> np.ndarray:
    a, b = courbe[:-1], courbe[1:]
    ab = b - a
    long2 = np.maximum((ab ** 2).sum(axis=1), 1e-12)
    p = np.stack([px.ravel(), pz.ravel()], axis=1)
    meilleur = np.full(len(p), np.inf)
    for k in range(len(a)):
        t = np.clip(((p - a[k]) @ ab[k]) / long2[k], 0.0, 1.0)
        proj = a[k] + t[:, None] * ab[k]
        meilleur = np.minimum(meilleur, np.hypot(*(p - proj).T))
    return meilleur.reshape(px.shape)


def relief_carre(taille: float, relief: str, *, eau: str = "aucune", graine: int = 0,
                 pas: float | None = None) -> tuple[Relief, dict[str, Any]]:
    """Grille de hauteurs d'un carré de `taille` m centré sur l'origine, eau creusée, dans [0, amplitude]."""
    if relief not in voc.RELIEFS:
        raise KeyError(f"relief hors vocabulaire : {relief!r}")
    if eau not in ("aucune", "lac", "riviere", "mer"):
        raise KeyError(f"type d'eau inconnu : {eau!r}")
    rel = voc.RELIEFS[relief]
    A, lam = float(rel["amplitude"]), float(rel["longueur_onde"])
    pas = float(pas or np.clip(taille / 200.0, 0.75, 2.5))
    n = int(math.ceil(taille / pas))
    pas = taille / n
    rng = np.random.default_rng(_graine("relief", relief, eau, graine))
    # Champ périodique sur une période plus grande que le carré (la périodicité ne se voit pas).
    periode_n = n * 2
    base = champ_fractal(periode_n, taille * 2.0, lam, int(rng.integers(1 << 31)), pente_spectrale=2.4)
    raideur = A / lam
    part_cretes = float(np.clip(raideur * 1.2, 0.0, 0.35))
    if part_cretes > 0.0:
        # Crêtes : un champ lisse replié (|2c - 1|) puis adouci, pour des arêtes sans dents de scie.
        c = champ_fractal(periode_n, taille * 2.0, lam * 1.3, int(rng.integers(1 << 31)), pente_spectrale=2.6)
        cretes = _flou(1.0 - np.abs(2.0 * c - 1.0), 3)
        base = (1.0 - part_cretes) * base + part_cretes * (cretes - cretes.min()) / max(np.ptp(cretes), 1e-9)
    hm = base * A
    hm = eroder(hm, pas, iterations=int(30 + 80 * part_cretes), talus_deg=34.0)
    hm = _flou(hm, 2)
    h0 = hm[: n + 1, : n + 1]
    h0 = (h0 - h0.min()) / max(float(np.ptp(h0)), 1e-9)       # [0, 1]
    xs = np.linspace(-taille / 2.0, taille / 2.0, n + 1)
    X, Z = np.meshgrid(xs, xs, indexing="ij")
    info: dict[str, Any] = {"amplitude": A, "longueur_onde": lam, "pas": pas, "eau": eau, "part_cretes": part_cretes}
    fond, niveau = -0.18, None          # fond de mer (fraction d'amplitude sous le plus bas)
    h = h0
    if eau == "lac":
        flou = h0.copy()
        for _ in range(int(max(2, 0.08 * n))):
            flou = _flou(flou)
        interieur = (np.abs(X) < 0.28 * taille) & (np.abs(Z) < 0.28 * taille)
        idx = np.unravel_index(np.argmin(np.where(interieur, flou, np.inf)), flou.shape)
        cx, cz = X[idx], Z[idx]
        R = math.sqrt(PARTS_EAU["lac"] * taille * taille / math.pi)
        ang = np.arctan2(Z - cz, X - cx)
        ph = rng.uniform(0, 2 * math.pi, 3)
        Ra = R * (1.0 + 0.16 * np.sin(2 * ang + ph[0]) + 0.1 * np.sin(3 * ang + ph[1]) + 0.06 * np.sin(5 * ang + ph[2]))
        r = np.hypot(X - cx, Z - cz)
        prof = _profondeur_rel(A)
        fond = float(h0.min()) - prof                 # sous tout le relief non creusé : seul le lac inonde
        # Le rivage (berge au niveau de l'eau) tombe exactement sur le contour Ra visé.
        h = _flou(np.minimum(h0, fond + _profil_berge(r - Ra + _distance_rivage(0.6 * prof * A)) / A), 2)
        niveau = fond + 0.6 * prof
        info["lac"] = {"centre": (float(cx), float(cz)), "rayon": float(R)}
    elif eau == "riviere":
        # Une rivière suit le fond des vallées : parmi plusieurs tracés possibles, le plus bas en moyenne.
        demi = max(6.0, PARTS_EAU["riviere"] * taille / 2.0)
        grossier = slice(None, None, max(1, n // 60))
        candidats = [_courbe_traversante(rng, taille, n=32) for _ in range(16)]
        cotes = [float(h0[grossier, grossier][_distance_polyligne(X[grossier, grossier], Z[grossier, grossier], c)
                                               < demi].mean()) for c in candidats]
        courbe = candidats[int(np.argmin(cotes))]
        d = _distance_polyligne(X, Z, courbe)
        prof = _profondeur_rel(A)
        # Fond sous TOUT le relief non creusé : seule la rivière demandée inonde.
        fond = float(h0.min()) - prof
        h = _flou(np.minimum(h0, fond + _profil_berge(d - demi + _distance_rivage(0.6 * prof * A)) / A), 2)
        niveau = fond + 0.6 * prof
        info["riviere"] = {"demi_largeur": float(demi), "courbe": courbe.tolist()}
    elif eau == "mer":
        angle = rng.uniform(0.0, 2 * math.pi)
        s = (X * math.cos(angle) + Z * math.sin(angle)) / taille            # [-0.7, 0.7]
        t_long = (-X * math.sin(angle) + Z * math.cos(angle)) / taille
        ph = rng.uniform(0, 2 * math.pi, 2)
        # Trait de côte : le quantile de s qui donne la part de mer visée, ondulé le long du rivage.
        cote = float(np.quantile(s, PARTS_EAU["mer"])) + 0.035 * np.sin(2 * math.pi * 1.3 * t_long + ph[0]) \
            + 0.02 * np.sin(2 * math.pi * 3.1 * t_long + ph[1])
        sp = s - cote                                                        # > 0 : terre
        terre = h0 * _lisse(sp, 0.0, 0.45) + 0.03
        w = _lisse(sp, -0.3, 0.04)                                          # plateau immergé en pente douce
        h = (fond * 1.6) * (1 - w) + terre * w
        niveau = 0.0
        info["mer"] = {"direction": float(angle)}
    hmin, hmax = float(h.min()), float(h.max())
    echelle = A / max(hmax - hmin, 1e-9)
    hauteurs = (h - hmin) * echelle
    niveau_m = None if niveau is None else (niveau - hmin) * echelle
    info["niveau_eau"] = niveau_m
    return Relief(hauteurs, taille, niveau_m, A), info


# ── Maillage du terrain ────────────────────────────────────────────────────────────────────────────
def _materiaux_faces(relief: Relief, biome: str, eau: str, rng: np.random.Generator) -> np.ndarray:
    """Matériau de chaque cellule (n, n) : biome, roche sur forte pente, neige en altitude, rivage."""
    spec = voc.BIOMES[biome]
    n = relief.n
    h = relief.h
    hc = 0.25 * (h[:-1, :-1] + h[1:, :-1] + h[:-1, 1:] + h[1:, 1:])
    pente = 0.25 * (relief._pente[:-1, :-1] + relief._pente[1:, :-1] + relief._pente[:-1, 1:] + relief._pente[1:, 1:])
    bruit = champ_fractal(n, relief.taille, max(8.0, relief.taille / 12.0), int(rng.integers(1 << 31)))
    mats = np.full((n, n), spec["sol"], dtype=object)
    A = relief.amplitude
    rel = (hc - h.min()) / max(A, 1e-9)
    roche = pente > (36.0 + 10.0 * (bruit - 0.5))
    mats[roche] = "roche"
    if A >= AMPLITUDE_NEIGE_M:
        neige = (rel > 0.74 + 0.12 * (bruit - 0.5)) & (pente < 48.0)
        mats[neige] = "neige"
    if relief.niveau_eau is not None:
        lv = relief.niveau_eau
        bande = (2.2 if eau == "mer" else 0.9) + 0.6 * (bruit - 0.5)
        rivage = (hc < lv + bande) & (pente < 30.0)
        mats[rivage] = "sable" if eau == "mer" else "gravier"
        mats[hc < lv - 0.05] = "sable" if eau == "mer" else "terre"
    return mats


def maillage_terrain(relief: Relief, biome: str, eau: str = "aucune", graine: int = 0,
                     jupe: bool = True) -> list[Partie]:
    """Parties du sol (une par matériau) et jupe latérale ; normales du gradient ; UV = (x, -z) en mètres."""
    if biome not in voc.BIOMES:
        raise KeyError(f"biome hors vocabulaire : {biome!r}")
    rng = np.random.default_rng(_graine("sol", biome, graine))
    n, T = relief.n, relief.taille
    xs = np.linspace(-T / 2.0, T / 2.0, n + 1)
    X, Z = np.meshgrid(xs, xs, indexing="ij")
    H = relief.h
    gx, gz = np.gradient(H, relief.pas)
    normales = np.stack([-gx, np.ones_like(H), -gz], axis=-1)
    normales /= np.linalg.norm(normales, axis=-1, keepdims=True)
    sommets = np.stack([X, H, Z], axis=-1).reshape(-1, 3)
    normales = normales.reshape(-1, 3)
    uv = np.stack([X.ravel(), -Z.ravel()], axis=1)
    idx = np.arange((n + 1) * (n + 1)).reshape(n + 1, n + 1)
    a, b, c, d = idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]
    # Orientation : normale vers +Y. (x vers +X = i, z vers +Z = j) : a(i,j) b(i+1,j) c(i+1,j+1) d(i,j+1)
    # le triangle (a, d, c) a une normale (d-a)×(c-a) = (+z)×(x+z) → +Y.
    tri1 = np.stack([a, d, c], axis=-1)
    tri2 = np.stack([a, c, b], axis=-1)
    mats = _materiaux_faces(relief, biome, eau, rng)
    parties = []
    for cle in sorted(set(mats.ravel().tolist())):
        masque = mats == cle
        faces = np.vstack([tri1[masque], tri2[masque]])
        utilises, inverse = np.unique(faces.ravel(), return_inverse=True)
        parties.append(Partie(maillage_brut(sommets[utilises], inverse.reshape(-1, 3), normales[utilises], uv[utilises]),
                              cle, f"sol_{cle}"))
    if jupe:
        base = float(H.min()) - max(2.0, 0.1 * relief.amplitude)
        morceaux = []
        bords = [(H[:, 0], X[:, 0], Z[:, 0], (0.0, -1.0)), (H[:, -1], X[:, -1], Z[:, -1], (0.0, 1.0)),
                 (H[0, :], X[0, :], Z[0, :], (-1.0, 0.0)), (H[-1, :], X[-1, :], Z[-1, :], (1.0, 0.0))]
        for hb, xb, zb, (nx, nz) in bords:
            m = len(hb)
            haut = np.stack([xb, hb, zb], axis=1)
            bas = np.stack([xb, np.full(m, base), zb], axis=1)
            v = np.vstack([haut, bas])
            f = []
            for k in range(m - 1):
                f += [[k, k + 1, m + k + 1], [k, m + k + 1, m + k]]
            f = np.asarray(f)
            # Orientation : la normale doit regarder vers l'extérieur (nx, 0, nz).
            n0 = np.cross(v[f[0, 1]] - v[f[0, 0]], v[f[0, 2]] - v[f[0, 0]])
            if n0[0] * nx + n0[2] * nz < 0:
                f = f[:, ::-1]
            s = xb * (-nz) + zb * nx
            uvj = np.column_stack([np.concatenate([s, s]), np.concatenate([hb, np.full(m, base)])])
            morceaux.append(maillage_brut(v, f, np.tile([nx, 0.0, nz], (2 * m, 1)), uvj))
        parties.append(Partie(g.fusionner(morceaux), "terre", "jupe"))
    return parties


def maillage_eau(relief: Relief, *, pas_facteur: int = 2) -> trimesh.Trimesh | None:
    """Surface plane à `niveau_eau` sur les cellules (grille 2× plus grossière) où le terrain passe dessous,
    et sa tranche le long des bords du carré (vue rasante)."""
    if relief.niveau_eau is None:
        return None
    lv = relief.niveau_eau
    H = relief.h
    k = max(1, int(pas_facteur))
    n = relief.n // k
    Hk = H[: n * k + 1: k, : n * k + 1: k]
    T = relief.taille
    pas = relief.pas * k
    mini = np.minimum.reduce([Hk[:-1, :-1], Hk[1:, :-1], Hk[:-1, 1:], Hk[1:, 1:]])
    masque = mini < lv
    if not masque.any():
        return None
    xs = -T / 2.0 + pas * np.arange(n + 1)
    X, Z = np.meshgrid(xs, xs, indexing="ij")
    idx = np.arange((n + 1) * (n + 1)).reshape(n + 1, n + 1)
    a, b, c, d = idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]
    faces = np.vstack([np.stack([a, d, c], -1)[masque], np.stack([a, c, b], -1)[masque]])
    sommets = np.stack([X, np.full_like(X, lv), Z], -1).reshape(-1, 3)
    utilises, inverse = np.unique(faces.ravel(), return_inverse=True)
    v = sommets[utilises]
    surface = maillage_brut(v, inverse.reshape(-1, 3), np.tile([0.0, 1.0, 0.0], (len(v), 1)),
                            np.column_stack([v[:, 0], -v[:, 2]]))
    tranches = []
    fond = float(H.min()) - 0.5
    for i_bord, axe, signe in ((0, 1, -1.0), (n - 1, 1, 1.0), (0, 0, -1.0), (n - 1, 0, 1.0)):
        ligne = masque[:, i_bord] if axe == 1 else masque[i_bord, :]
        for kk in np.nonzero(ligne)[0]:
            if axe == 1:
                p0 = (xs[kk], xs[0] if signe < 0 else xs[-1])
                p1 = (xs[kk + 1], p0[1])
                nrm = (0.0, signe)
            else:
                p0 = (xs[0] if signe < 0 else xs[-1], xs[kk])
                p1 = (p0[0], xs[kk + 1])
                nrm = (signe, 0.0)
            v4 = np.array([[p0[0], lv, p0[1]], [p1[0], lv, p1[1]], [p1[0], fond, p1[1]], [p0[0], fond, p0[1]]])
            f = np.array([[0, 1, 2], [0, 2, 3]])
            n0 = np.cross(v4[1] - v4[0], v4[2] - v4[0])
            if n0[0] * nrm[0] + n0[2] * nrm[1] < 0:
                f = f[:, ::-1]
            s = v4[:, 0] * (-nrm[1]) + v4[:, 2] * nrm[0]
            tranches.append(maillage_brut(v4, f, np.tile([nrm[0], 0.0, nrm[1]], (4, 1)), np.column_stack([s, v4[:, 1]])))
    return g.fusionner([surface, *tranches])


def terrain(taille: float, relief: str, biome: str, *, eau: str = "aucune", graine: int = 0,
            fabrique: Fabrique = objet_provisoire, budget_triangles: int = BUDGET_PAYSAGE,
            vegetation: bool = True) -> tuple[Noeud, Relief]:
    """Paysage complet d'un carré de `taille` m : (nœud racine, relief) ; `relief(x, z) -> y`.

    Nœuds (tous en fusion) : « sol » (une primitive par matériau + jupe), « eau », « vegetation ».
    """
    if biome not in voc.BIOMES:
        raise KeyError(f"biome hors vocabulaire : {biome!r}")
    rel, info = relief_carre(taille, relief, eau=eau, graine=graine)
    sol = Noeud("sol", parties=maillage_terrain(rel, biome, eau, graine), fusion=True)
    enfants = [sol]
    tri_fixes = sum(len(p.maillage.faces) for p in sol.parties)
    m_eau = maillage_eau(rel)
    if m_eau is not None:
        enfants.append(Noeud("eau", parties=[Partie(m_eau, "eau", "eau")], fusion=True,
                             extras={"niveau": rel.niveau_eau}))
        tri_fixes += len(m_eau.faces)
    rapport_veg: dict[str, Any] = {}
    if vegetation:
        A = rel.amplitude
        hmin = float(rel.h.min())

        def accepter(x, z):
            ok = ~rel.dans_eau(x, z, marge=0.4)
            if A >= AMPLITUDE_NEIGE_M:             # limite des arbres : rien au-dessus des neiges
                ok &= (rel(x, z) - hmin) / A < 0.72
            return ok

        especes = []
        for cat, style, densite in voc.BIOMES[biome]["vegetation"]:
            especes.append(Espece(cat, style, float(densite)))
        instances, rapport_veg = disperser((-taille / 2.0, -taille / 2.0, taille / 2.0, taille / 2.0), especes,
                                           fabrique=fabrique, graine=_graine("vegetation", graine), hauteur=rel,
                                           accepter=accepter, pente_deg=rel.pente_deg,
                                           budget_triangles=max(0, budget_triangles - tri_fixes))
        enfants.append(Noeud("vegetation", instances=instances, fusion=True, extras={"rapport": rapport_veg}))
    racine = Noeud("paysage", enfants=enfants,
                   extras={"relief": relief, "biome": biome, "eau": eau, "taille": taille, "graine": graine,
                           "niveau_eau": rel.niveau_eau, "amplitude": rel.amplitude,
                           "triangles_fixes": int(tri_fixes)})
    return racine, rel


def triangles_noeud(noeud: Noeud) -> int:
    total = 0
    for n in noeud.parcourir():
        total += sum(len(p.maillage.faces) for p in n.parties)
        total += sum(triangles_objet(i.objet) for i in n.instances)
    return total


# ── Démonstration (rendus f3d de contrôle) ─────────────────────────────────────────────────────────
SORTIE_DEMO = "/home/juan/AuroraIA/application/output/3d/essais/monde/ville_paysage"


def demo(taille: float, relief: str, biome: str, eau: str, graine: int, dossier: str | None = None) -> dict[str, Any]:
    """Construit, exporte et rend un paysage (plan, deux aériennes, rasante) ; rend le rapport."""
    import time
    from pathlib import Path

    from monde import export_gltf, rendu
    from monde.ir import Scene

    debut = time.monotonic()
    racine, rel = terrain(taille, relief, biome, eau=eau, graine=graine)
    duree = time.monotonic() - debut
    dossier = Path(dossier or f"{SORTIE_DEMO}/paysage_{biome}_{relief}_{eau}_{graine}")
    rapport = export_gltf.exporter(Scene(racine, extras={"programme": racine.extras}), dossier / "paysage.glb")
    vues = rendu.rendre_vues(dossier / "paysage.glb", dossier,
                             vues=("plan", "aerienne_sud_est", "aerienne_nord_ouest", "rasante"))
    return {"duree_construction_s": round(duree, 2), "export": rapport, "rendu": vues,
            "triangles": triangles_noeud(racine)}


if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser(description="Paysage procédural de contrôle (rendus f3d)")
    p.add_argument("--taille", type=float, default=300.0)
    p.add_argument("--relief", default="montagneux")
    p.add_argument("--biome", default="foret_de_coniferes")
    p.add_argument("--eau", default="lac")
    p.add_argument("--graine", type=int, default=0)
    p.add_argument("--dossier", default=None)
    a = p.parse_args()
    print(json.dumps(demo(a.taille, a.relief, a.biome, a.eau, a.graine, a.dossier), ensure_ascii=False, default=str,
                     indent=1)[:4000])
