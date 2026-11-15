"""Primitives géométriques du moteur de scènes, toutes prêtes pour l'export (UV en mètres, normales).

Toute primitive passe par `finaliser` : normales lissées sur les surfaces courbes (angle < seuil),
arêtes vives conservées, UV triplanaires en MÈTRES (voir `monde.ir`). Les sommets sont dédoublés là où
la projection ou la normale change, si bien que l'exporteur n'a rien à recalculer.

Repère : Y vers le haut, sol en XZ (voir `monde.ir`). Les profils et polygones au sol s'écrivent (x, z).
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np
import trimesh
from shapely.geometry import Polygon
from trimesh.visual import TextureVisuals

LISSAGE_DEG = 35.0


def finaliser(m: trimesh.Trimesh, lissage_deg: float = LISSAGE_DEG) -> trimesh.Trimesh:
    """Normales par coin (lissées entre faces à moins de `lissage_deg`), UV triplanaires en mètres."""
    m = trimesh.Trimesh(vertices=np.asarray(m.vertices, dtype=np.float64), faces=np.asarray(m.faces), process=False)
    # Triangles d'aire nulle (toits, berges, raccords) : sans effet visuel, mais ils font tomber
    # `vertex_faces` de trimesh dans une boucle lente avec une trace d'erreur (village du 15/11/2026).
    if len(m.faces):
        m.update_faces(m.nondegenerate_faces(height=1e-10))
    m.remove_unreferenced_vertices()
    if len(m.faces) == 0:
        return m
    nf = len(m.faces)
    fn = m.face_normals
    aire = m.area_faces
    axe = np.abs(fn).argmax(axis=1)
    signe = np.sign(fn[np.arange(nf), axe])
    signe[signe == 0] = 1.0
    code = axe * 2 + (signe > 0)

    coins_v = m.faces.reshape(-1)
    coins_f = np.repeat(np.arange(nf), 3)
    vf = m.vertex_faces                                        # (V, K), complété par -1
    inc = vf[coins_v]
    valides = inc >= 0
    inc0 = np.where(valides, inc, 0)
    seuil = math.cos(math.radians(lissage_deg))
    produits = np.einsum("ckj,cj->ck", fn[inc0], fn[coins_f])
    poids = aire[inc0] * (valides & (produits >= seuil))
    normales = np.einsum("ck,ckj->cj", poids, fn[inc0])
    longueur = np.linalg.norm(normales, axis=1)
    vides = longueur < 1e-12
    normales[vides] = fn[coins_f[vides]]
    longueur[vides] = 1.0
    normales /= longueur[:, None]

    # Dédoublement : même sommet, même projection, même normale (au millième) → un seul sommet.
    cles = np.column_stack([coins_v, code[coins_f], np.round(normales * 1000).astype(np.int64)])
    _, premier, inverse = np.unique(cles, axis=0, return_index=True, return_inverse=True)
    inverse = inverse.reshape(-1)
    positions = m.vertices[coins_v[premier]]
    normales_u = normales[premier]
    code_u = code[coins_f[premier]]

    x, y, z = positions[:, 0], positions[:, 1], positions[:, 2]
    u = np.select([code_u == 1, code_u == 0, code_u == 3, code_u == 2, code_u == 5, code_u == 4],
                  [-z, z, x, x, x, -x])
    v = np.select([code_u <= 1, code_u == 3, code_u == 2, code_u >= 4], [y, -z, z, y])
    sortie = trimesh.Trimesh(vertices=positions, faces=inverse.reshape(-1, 3), vertex_normals=normales_u,
                             process=False)
    sortie.visual = TextureVisuals(uv=np.column_stack([u, v]))
    return sortie


def transformer(m: trimesh.Trimesh, matrice: np.ndarray) -> trimesh.Trimesh:
    """Copie transformée ; les UV (en mètres, liés à l'objet) et les normales suivent."""
    copie = m.copy()
    copie.apply_transform(np.asarray(matrice, dtype=np.float64))
    return copie


def translation(m: trimesh.Trimesh, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> trimesh.Trimesh:
    t = np.eye(4)
    t[:3, 3] = [dx, dy, dz]
    return transformer(m, t)


def rotation_y(angle: float) -> np.ndarray:
    c, s = math.cos(angle), math.sin(angle)
    r = np.eye(4)
    r[:3, :3] = [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]
    return r


def fusionner(maillages: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
    liste = [m for m in maillages if m is not None and len(m.faces)]
    if not liste:
        return trimesh.Trimesh()
    if len(liste) == 1:
        return liste[0].copy()
    uvs = [np.asarray(getattr(m.visual, "uv", None)) if getattr(m.visual, "uv", None) is not None
           else np.zeros((len(m.vertices), 2)) for m in liste]
    normales = [np.asarray(m.vertex_normals) for m in liste]
    sommets, faces, decalage = [], [], 0
    for m in liste:
        sommets.append(np.asarray(m.vertices))
        faces.append(np.asarray(m.faces) + decalage)
        decalage += len(m.vertices)
    sortie = trimesh.Trimesh(vertices=np.vstack(sommets), faces=np.vstack(faces),
                             vertex_normals=np.vstack(normales), process=False)
    sortie.visual = TextureVisuals(uv=np.vstack(uvs))
    return sortie


# ── Primitives (bas de la forme à y = base, centrée en x et z sauf mention) ─────────────────────────
def boite(lx: float, ly: float, lz: float, *, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> trimesh.Trimesh:
    """Pavé de dimensions lx × ly × lz, centre du dessous en (x, y, z)."""
    m = trimesh.creation.box(extents=[max(lx, 1e-4), max(ly, 1e-4), max(lz, 1e-4)])
    m.apply_translation([x, y + ly / 2.0, z])
    return finaliser(m)


def boite_arrondie(lx: float, ly: float, lz: float, rayon: float, *, x: float = 0.0, y: float = 0.0,
                   z: float = 0.0, subdivisions: int = 2) -> trimesh.Trimesh:
    """Pavé aux arêtes arrondies (coussins, matelas, plateaux) : enveloppe convexe de 8 sphères."""
    r = max(1e-4, min(rayon, lx / 2.0 - 1e-4, ly / 2.0 - 1e-4, lz / 2.0 - 1e-4))
    sphere = trimesh.creation.icosphere(subdivisions=subdivisions, radius=r)
    points = []
    for sx in (-1, 1):
        for sy in (0, 1):
            for sz in (-1, 1):
                centre = np.array([sx * (lx / 2.0 - r), r + sy * (ly - 2.0 * r), sz * (lz / 2.0 - r)])
                points.append(sphere.vertices + centre)
    m = trimesh.convex.convex_hull(np.vstack(points))
    m.apply_translation([x, y, z])
    return finaliser(m)


def cylindre(rayon: float, hauteur: float, *, x: float = 0.0, y: float = 0.0, z: float = 0.0,
             sections: int = 24) -> trimesh.Trimesh:
    """Cylindre vertical, base en (x, y, z)."""
    m = trimesh.creation.cylinder(radius=max(rayon, 1e-4), height=max(hauteur, 1e-4), sections=sections)
    m.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2.0, [1, 0, 0]))
    m.apply_translation([x, y + hauteur / 2.0, z])
    return finaliser(m)


def revolution(profil: Sequence[tuple[float, float]], *, x: float = 0.0, y: float = 0.0, z: float = 0.0,
               sections: int = 32) -> trimesh.Trimesh:
    """Solide de révolution autour d'un axe vertical : profil [(rayon, hauteur), ...] du bas vers le haut.
    Un rayon nul ferme le solide sur l'axe (pied de lampe, vase, bol, abat-jour)."""
    points = np.array([[max(0.0, r), h] for r, h in profil], dtype=np.float64)
    m = trimesh.creation.revolve(points, sections=sections)
    m.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2.0, [1, 0, 0]))
    m.apply_translation([x, y, z])
    return finaliser(m)


def tronc_de_cone(rayon_bas: float, rayon_haut: float, hauteur: float, *, x: float = 0.0, y: float = 0.0,
                  z: float = 0.0, sections: int = 24) -> trimesh.Trimesh:
    return revolution([(0.0, 0.0), (rayon_bas, 0.0), (rayon_haut, hauteur), (0.0, hauteur)], x=x, y=y, z=z,
                      sections=sections)


def extrusion(polygone: Polygon | Sequence[tuple[float, float]], hauteur: float, *, y: float = 0.0) -> trimesh.Trimesh:
    """Prisme vertical : polygone au sol (x, z), éventuellement troué, extrudé de y à y + hauteur."""
    poly = polygone if isinstance(polygone, Polygon) else Polygon(polygone)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or poly.area <= 1e-9:
        return trimesh.Trimesh()
    m = trimesh.creation.extrude_polygon(poly, max(hauteur, 1e-4))
    echange = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=np.float64)
    m.apply_transform(echange)          # (x, y_plan, h) → (x, h, z) : réflexion ; trimesh retourne les faces
    m.apply_translation([0.0, y, 0.0])
    return finaliser(m)


def sphere(rayon: float, *, x: float = 0.0, y: float = 0.0, z: float = 0.0, subdivisions: int = 3) -> trimesh.Trimesh:
    m = trimesh.creation.icosphere(subdivisions=subdivisions, radius=max(rayon, 1e-4))
    m.apply_translation([x, y, z])
    return finaliser(m, lissage_deg=60.0)


def ellipsoide(rx: float, ry: float, rz: float, *, x: float = 0.0, y: float = 0.0, z: float = 0.0,
               subdivisions: int = 3, bruit: float = 0.0, graine: int = 0) -> trimesh.Trimesh:
    """Ellipsoïde centré en (x, y, z) ; `bruit` (fraction du rayon) bosselle la surface (feuillage, rocher)."""
    m = trimesh.creation.icosphere(subdivisions=subdivisions, radius=1.0)
    v = m.vertices.copy()
    if bruit > 0.0:
        rng = np.random.default_rng(graine)
        frequences = rng.normal(size=(4, 3)) * 2.5
        phases = rng.uniform(0, 2 * math.pi, size=4)
        deformation = sum(np.sin(v @ f + p) for f, p in zip(frequences, phases)) / 4.0
        v *= (1.0 + bruit * deformation)[:, None]
    v *= [rx, ry, rz]
    v += [x, y, z]
    return finaliser(trimesh.Trimesh(vertices=v, faces=m.faces, process=False), lissage_deg=60.0)


def segment(p0: Sequence[float], p1: Sequence[float], rayon: float, *, sections: int = 12) -> trimesh.Trimesh:
    """Cylindre entre deux points 3D (barres, bras, pieds inclinés, branches)."""
    a, b = np.asarray(p0, dtype=np.float64), np.asarray(p1, dtype=np.float64)
    longueur = float(np.linalg.norm(b - a))
    if longueur < 1e-6:
        return trimesh.Trimesh()
    m = trimesh.creation.cylinder(radius=max(rayon, 1e-4), height=longueur, sections=sections)
    direction = (b - a) / longueur
    m.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], direction))
    m.apply_translation((a + b) / 2.0)
    return finaliser(m)


def plaque(polygone: Polygon | Sequence[tuple[float, float]], epaisseur: float, *, y: float = 0.0) -> trimesh.Trimesh:
    """Dalle horizontale (sol, plafond, plateau) de dessus à y, épaisseur vers le bas."""
    return extrusion(polygone, epaisseur, y=y - epaisseur)


def rectangle_xz(x0: float, z0: float, x1: float, z1: float) -> Polygon:
    return Polygon([(x0, z0), (x1, z0), (x1, z1), (x0, z1)])
