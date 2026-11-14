"""Export d'un assemblage : STL par pièce, glTF articulé, vue éclatée, coupe, rendus f3d.

glTF : un nœud par pièce (quincaillerie comprise). Une pièce articulée est portée par un nœud
pivot placé sur l'axe de sa liaison, comme dans `python-services/articulated_motion.py` :
extras `aurora_liaison` sur le nœud pivot, extras `aurora_articulation` (schéma
aurora.articulation.v1) sur le document, convention +Y haut / face avant +Z / droite +X, mètres.

Une seule animation, « montage_puis_mouvement », raconte l'assemblage : vue éclatée à t = 0, les
pièces rejoignent leur place dans l'ordre de la gamme, puis chaque charnière s'ouvre et se referme.
Une seule piste par visionneuse : la vue 3D de l'application joue toutes les animations d'un
fichier ensemble, deux animations sur les mêmes nœuds se mélangeraient.
"""
from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from application import engineering_standards as normes
from application.engineering_assembly import Piece, boite_englobante, vers_trimesh

# Repère de conception (mm, Z haut, face avant −Y) → glTF (m, Y haut, face avant +Z)
C = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]])
ECHELLE = 0.001
F3D = Path.home() / ".local" / "bin" / "f3d"


def vers_gltf(p) -> np.ndarray:
    return (C @ np.asarray(p, dtype=float).T).T * ECHELLE


def vecteur_gltf(v) -> np.ndarray:
    return C @ np.asarray(v, dtype=float)


# --------------------------------------------------------------------------- STL

def exporter_stl(pieces: dict[str, Piece], dossier: Path) -> dict[str, str]:
    chemins = {}
    for p in pieces.values():
        sous = dossier / ("quincaillerie" if p.est_quincaillerie else "pieces")
        sous.mkdir(parents=True, exist_ok=True)
        m = vers_trimesh(p.final)
        m.apply_translation(-m.bounds[0])         # pièce posée à l'origine, cotes en mm
        chemin = sous / f"{p.id}.stl"
        m.export(chemin)
        chemins[p.id] = str(chemin)
    return chemins


# --------------------------------------------------------------------------- glTF

def _materiau(p: Piece) -> dict[str, Any]:
    m = normes.MATIERES[p.matiere]
    rgb = [min(255, c * p.teinte) for c in m["couleur"]]
    lin = normes.lineaire(tuple(rgb))
    return {"name": f"{m['nom']} · {p.id}" if not p.est_quincaillerie else m["nom"],
            "pbrMetallicRoughness": {"baseColorFactor": [*lin, 1.0], "metallicFactor": float(m["metal"]),
                                     "roughnessFactor": float(m["rugosite"])},
            "doubleSided": False}


def _maillage_lisse(solide):
    import trimesh
    m = vers_trimesh(solide)
    try:
        lisse = trimesh.graph.smooth_shade(m, angle=math.radians(32.0))
    except Exception:  # noqa: BLE001 — repli : normales à plat
        lisse = m
    return lisse


class _Tampon:
    def __init__(self) -> None:
        self.donnees = bytearray()
        self.vues: list[dict[str, Any]] = []
        self.accesseurs: list[dict[str, Any]] = []

    def ajouter(self, tableau: np.ndarray, type_: str, composante: int, cible: int | None = None,
                bornes: bool = False) -> int:
        while len(self.donnees) % 4:
            self.donnees.append(0)
        debut = len(self.donnees)
        octets = tableau.tobytes()
        self.donnees.extend(octets)
        vue = {"buffer": 0, "byteOffset": debut, "byteLength": len(octets)}
        if cible:
            vue["target"] = cible
        self.vues.append(vue)
        acc = {"bufferView": len(self.vues) - 1, "componentType": composante, "count": int(len(tableau)), "type": type_}
        if bornes:
            t = tableau.reshape(len(tableau), -1)
            acc["min"] = [float(x) for x in t.min(axis=0)]
            acc["max"] = [float(x) for x in t.max(axis=0)]
        self.accesseurs.append(acc)
        return len(self.accesseurs) - 1


def _adoucir(x: np.ndarray) -> np.ndarray:
    return x * x * (3.0 - 2.0 * x)


def ecrire_gltf(chemin: Path, pieces: dict[str, Piece], cinematique: dict[str, Any], gamme: dict[str, Any],
                ecarts: dict[str, np.ndarray], extras: dict[str, Any], *, eclate: bool = False,
                animer: bool = True, solides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Écrit le GLB. `eclate` pose chaque pièce à son écart de vue éclatée (fichier statique)."""
    solides = solides or {p.id: p.final for p in pieces.values()}
    tampon = _Tampon()
    materiaux: list[dict[str, Any]] = []
    index_mat: dict[str, int] = {}
    noeuds: list[dict[str, Any]] = [{"name": "assemblage", "children": []}]
    maillages: list[dict[str, Any]] = []
    corps_de = cinematique["racine_de"]
    articulations = cinematique["articulations"] if not eclate else []
    mobile_de: dict[str, dict[str, Any]] = {}
    for art in articulations:
        for pid in cinematique["corps"][art["corps_mobile"]]:
            mobile_de[pid] = art
    pivots: dict[str, int] = {}
    for art in articulations:
        pivot_g = vers_gltf(art["pivot"])
        axe_g = vecteur_gltf(art["axe"])
        noeud = {"name": f"articulation:{art['liaison']}", "translation": [float(x) for x in pivot_g], "children": [],
                 "extras": {"aurora_liaison": {"type": "charniere", "pivot": [float(x) for x in pivot_g],
                                               "axe": [float(x) for x in axe_g], "cote": art.get("cote"),
                                               "amplitude_demandee_deg": art["amplitude_demandee_deg"],
                                               "amplitude_retenue_deg": art.get("amplitude_retenue_deg"),
                                               "bornee_par_collision": art.get("bornee_par_collision"),
                                               "fixe": art["fixe"], "mobile": art["mobile"], "liaison": art["liaison"],
                                               "pivot_cad_mm": [float(x) for x in art["pivot"]],
                                               "axe_cad": [float(x) for x in art["axe"]]}}}
        noeuds.append(noeud)
        pivots[art["liaison"]] = len(noeuds) - 1
        noeuds[0]["children"].append(len(noeuds) - 1)
    index_noeud: dict[str, int] = {}
    for pid in gamme["ordre"] + [p for p in pieces if p not in gamme["ordre"]]:
        p = pieces[pid]
        cle = f"{p.matiere}:{p.id if not p.est_quincaillerie else ''}"
        if cle not in index_mat:
            materiaux.append(_materiau(p))
            index_mat[cle] = len(materiaux) - 1
        m = _maillage_lisse(solides[pid])
        art = mobile_de.get(pid)
        origine = np.asarray(art["pivot"]) if art else np.zeros(3)
        sommets = vers_gltf(m.vertices - origine).astype(np.float32)
        normales = (C @ np.asarray(m.vertex_normals, dtype=float).T).T.astype(np.float32)
        faces = np.asarray(m.faces, dtype=np.uint32).reshape(-1)
        a_pos = tampon.ajouter(sommets, "VEC3", 5126, 34962, bornes=True)
        a_nor = tampon.ajouter(normales, "VEC3", 5126, 34962)
        a_ind = tampon.ajouter(faces, "SCALAR", 5125, 34963)
        maillages.append({"name": pid, "primitives": [{"attributes": {"POSITION": a_pos, "NORMAL": a_nor}, "indices": a_ind,
                                                        "material": index_mat[cle]}]})
        noeud = {"name": pid, "mesh": len(maillages) - 1,
                 "extras": {"aurora_piece": {"id": pid, "nom": p.nom, "matiere": normes.MATIERES[p.matiere]["nom"],
                                             "procede": normes.PROCEDES[p.procede]["nom"], "origine": p.origine,
                                             "designation": (p.article or {}).get("designation"),
                                             "corps": corps_de.get(pid), "liaison": p.liaison}}}
        if eclate:
            noeud["translation"] = [float(x) for x in vecteur_gltf(ecarts[pid]) * ECHELLE]
        noeuds.append(noeud)
        index_noeud[pid] = len(noeuds) - 1
        parent = pivots[art["liaison"]] if art else 0
        noeuds[parent]["children"].append(len(noeuds) - 1)
    doc: dict[str, Any] = {"asset": {"version": "2.0", "generator": "AuroraIA engineering_assembly"},
                           "scene": 0, "scenes": [{"name": "assemblage", "nodes": [0]}],
                           "nodes": noeuds, "meshes": maillages, "materials": materiaux}
    chrono: dict[str, Any] = {}
    if animer and not eclate:
        chrono = _animation(doc, tampon, pieces, gamme, ecarts, index_noeud, articulations, pivots)
    doc["accessors"] = tampon.accesseurs
    doc["bufferViews"] = tampon.vues
    while len(tampon.donnees) % 4:
        tampon.donnees.append(0)
    doc["buffers"] = [{"byteLength": len(tampon.donnees)}]
    doc["extras"] = {**extras, "aurora_montage_chronologie": chrono}
    if articulations:
        doc["extras"]["aurora_articulation"] = {
            "schema": "aurora.articulation.v1", "source": "assemblage",
            "liaisons": [noeuds[pivots[a["liaison"]]]["extras"]["aurora_liaison"] for a in articulations],
            "convention": "+Y haut, face avant +Z, droite vue de face +X ; mètres"}
    _ecrire_glb(chemin, doc, bytes(tampon.donnees))
    return chrono


def _animation(doc, tampon: _Tampon, pieces, gamme, ecarts, index_noeud, articulations, pivots) -> dict[str, Any]:
    canaux, echantillonneurs = [], []
    duree_etape = 0.55
    t = 0.6
    debuts: dict[str, float] = {}
    for etape in gamme["etapes"]:
        for pid in etape["pieces"]:
            debuts.setdefault(pid, t)
        t += duree_etape if etape["type"] != "fixation" else duree_etape * 0.6
    fin_montage = t + 0.3
    fin = fin_montage + 0.6
    ouvertures = []
    for art in articulations:
        debut_o = fin
        ouvertures.append((art, debut_o))
        fin = debut_o + 1.6 + 1.0 + 1.6
    fin += 0.4
    pas = np.linspace(0.0, 1.0, 9)
    for pid, idx in index_noeud.items():
        e = vecteur_gltf(ecarts.get(pid, np.zeros(3))) * ECHELLE
        if not np.any(np.abs(e) > 1e-9):
            continue
        t0 = debuts.get(pid, 0.6)
        temps = [0.0] + [t0 + duree_etape * x for x in pas] + [fin]
        valeurs = [e] + [e * (1.0 - _adoucir(np.array(x))) for x in pas] + [np.zeros(3)]
        a_t = tampon.ajouter(np.asarray(temps, dtype=np.float32), "SCALAR", 5126, bornes=True)
        a_v = tampon.ajouter(np.asarray(valeurs, dtype=np.float32), "VEC3", 5126)
        echantillonneurs.append({"input": a_t, "output": a_v, "interpolation": "LINEAR"})
        canaux.append({"sampler": len(echantillonneurs) - 1, "target": {"node": idx, "path": "translation"}})
    for art, debut_o in ouvertures:
        axe = vecteur_gltf(art["axe"])
        axe = axe / np.linalg.norm(axe)
        amplitude = math.radians(float(art.get("amplitude_retenue_deg") or art["amplitude_demandee_deg"]))
        temps = [0.0, debut_o]
        angles = [0.0, 0.0]
        for x in pas[1:]:
            temps.append(debut_o + 1.6 * x)
            angles.append(amplitude * float(_adoucir(np.array(x))))
        temps.append(debut_o + 2.6)
        angles.append(amplitude)
        for x in pas[1:]:
            temps.append(debut_o + 2.6 + 1.6 * x)
            angles.append(amplitude * (1.0 - float(_adoucir(np.array(x)))))
        temps.append(fin)
        angles.append(0.0)
        quats = [[*(axe * math.sin(a / 2.0)), math.cos(a / 2.0)] for a in angles]
        a_t = tampon.ajouter(np.asarray(temps, dtype=np.float32), "SCALAR", 5126, bornes=True)
        a_v = tampon.ajouter(np.asarray(quats, dtype=np.float32), "VEC4", 5126)
        echantillonneurs.append({"input": a_t, "output": a_v, "interpolation": "LINEAR"})
        canaux.append({"sampler": len(echantillonneurs) - 1, "target": {"node": pivots[art["liaison"]], "path": "rotation"}})
    if canaux:
        doc["animations"] = [{"name": "montage_puis_mouvement", "channels": canaux, "samplers": echantillonneurs}]
    ouvert = {a["liaison"]: round(d + 2.1, 3) for a, d in ouvertures}
    return {"duree_s": round(fin, 3), "assemble_a_s": round(fin_montage + 0.3, 3), "ouvert_a_s": ouvert,
            "debut_par_piece_s": {k: round(v, 3) for k, v in debuts.items()}}


def _ecrire_glb(chemin: Path, doc: dict[str, Any], binaire: bytes) -> None:
    js = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(binaire)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(".tmp")
    with open(temporaire, "wb") as f:
        f.write(b"glTF" + struct.pack("<II", 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(binaire), 0x004E4942) + binaire)
    temporaire.replace(chemin)


# --------------------------------------------------------------------------- relecture indépendante

def relire(chemin: Path) -> dict[str, Any]:
    """Relit le GLB écrit : nœuds, maillages fermés, extras, animation qui finit assemblée."""
    import trimesh
    raw = Path(chemin).read_bytes()
    longueur = struct.unpack_from("<I", raw, 12)[0]
    doc = json.loads(raw[20:20 + longueur])
    scene = trimesh.load(str(chemin), force="scene", process=False)
    noms = [n.get("name") for n in doc["nodes"]]
    fermes, total = 0, 0
    for nom in scene.graph.nodes_geometry:
        _, geom = scene.graph[nom]
        m = scene.geometry[geom].copy()
        m.merge_vertices(merge_tex=True, merge_norm=True)
        total += 1
        fermes += int(m.is_watertight)
    anim = doc.get("animations") or []
    pivots = [n for n in doc["nodes"] if (n.get("extras") or {}).get("aurora_liaison")]
    return {"noeuds": len(noms), "maillages": total, "maillages_fermes": fermes, "animations": [a["name"] for a in anim],
            "canaux": sum(len(a["channels"]) for a in anim), "pivots": len(pivots),
            "extras": sorted((doc.get("extras") or {}).keys())}


# --------------------------------------------------------------------------- coupe

def solides_en_coupe(pieces: dict[str, Piece], origine, normale) -> dict[str, Any]:
    """Chaque pièce coupée par un plan (moitié du côté opposé à la normale conservée)."""
    n = np.asarray(normale, dtype=float)
    n = n / np.linalg.norm(n)
    decalage = float(np.asarray(origine, dtype=float) @ n)
    sortie = {}
    for p in pieces.values():
        s = p.final.trim_by_plane(tuple(map(float, -n)), -decalage)
        sortie[p.id] = s
    return sortie


def plan_de_coupe(pieces: dict[str, Piece]) -> tuple[np.ndarray, np.ndarray] | None:
    """Plan passant par l'axe d'une fixation représentative : les usinages des deux pièces y sont visibles."""
    ordre = ("ISO 4762", "ISO 10642", "DIN 7997", "ISO 7380", "DIN 68150", "ISO 2338", "aimant N42", "insert à chaud")
    for norme in ordre:
        for p in pieces.values():
            if (p.article or {}).get("norme") != norme:
                continue
            axe = np.asarray(p.approche, dtype=float)
            if not np.any(axe):
                continue
            c = boite_englobante(p.final).mean(axis=0)
            # normale du plan : perpendiculaire à l'axe, la plus horizontale possible, vue de face si possible
            for cand in (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0])):
                if abs(float(cand @ axe)) < 0.2:
                    return c, cand
    return None


# --------------------------------------------------------------------------- rendus f3d

VUES = {
    "assemble": "-1,-0.78,-1.3",       # trois quarts avant droit, au-dessus
    "arriere": "0.95,-0.62,1.15",
    "dessous": "-0.7,1.0,-0.9",
}


def rendre(dossier_apercus: Path, assemble: Path, eclate: Path, coupe: Path | None, chrono: dict[str, Any],
           resolution: int = 1100, normale_coupe=None) -> dict[str, str]:
    dossier_apercus.mkdir(parents=True, exist_ok=True)
    f3d = str(F3D) if F3D.is_file() else shutil.which("f3d")
    if not f3d:
        return {}
    sorties: dict[str, str] = {}
    commun = [f"--resolution={resolution},{int(resolution * 0.78)}", "--up=+Y", "--ambient-occlusion=true",
              "--anti-aliasing=true", "--tone-mapping=true", "--grid=false", "--axis=false", "--filename=false",
              "--bg-color=0.86,0.88,0.91", "--animation-progress=false", "--progress=false"]

    def f(nom: str, fichier: Path, direction: str, temps: float | None = None, index: int | None = None):
        sortie = dossier_apercus / nom
        cmd = [f3d, str(fichier), f"--output={sortie}", f"--camera-direction={direction}", *commun]
        if temps is not None:
            cmd += [f"--animation-index={0 if index is None else index}", f"--animation-time={temps}"]
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        if sortie.is_file():
            sorties[nom] = str(sortie)

    t_asm = chrono.get("assemble_a_s")
    f("f3d_01_assemble.png", assemble, VUES["assemble"], t_asm)
    f("f3d_02_eclate.png", eclate, VUES["assemble"])
    f("f3d_03_arriere.png", assemble, VUES["arriere"], t_asm)
    f("f3d_04_dessous.png", assemble, VUES["dessous"], t_asm)
    for k, (liaison, t_ouvert) in enumerate((chrono.get("ouvert_a_s") or {}).items()):
        f(f"f3d_05_mouvement_{k + 1}.png", assemble, VUES["assemble"], t_ouvert)
    if coupe is not None and coupe.is_file():
        # la caméra regarde la face coupée de face (le côté conservé est opposé à la normale)
        n = vecteur_gltf(normale_coupe if normale_coupe is not None else [1.0, 0.0, 0.0])
        regard = -n / np.linalg.norm(n) + np.array([0.0, -0.22, 0.0]) + (np.array([0.0, 0.0, -0.18]) if abs(n[2]) < 0.5 else 0)
        f("f3d_06_coupe.png", coupe, ",".join(f"{x:.3f}" for x in regard))
    return sorties
