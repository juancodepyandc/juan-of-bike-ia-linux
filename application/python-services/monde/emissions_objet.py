"""Émissions posées sur un objet livré : le flacon vaporise, la tasse fume, la bougie brûle, la fontaine jaillit.

Le contrat de demande dit, par sujet, la matière émise (`emission.type`) et d'où elle part (`emission.point` :
haut, avant, bas). Depuis le 16/11/2026 :
- la BOUCHE et la DIRECTION sont lues sur l'image de référence quand elle montre l'émission
  (`monde.reperage_emission` : la vision pointe la bouche, le panache donne la direction), sinon déduites de la
  boîte englobante et du point du contrat ;
- un GAZ (brume, fumée, vapeur, flamme) est simulé par les équations de Navier-Stokes (`monde.gaz`) à sa taille
  réelle, puis posé à l'échelle du modèle comme volume animé dans le GLB (`monde.volume_gltf`) — plus de nuage
  de sphères ;
- un LIQUIDE (jet, gouttes) reste fait de vraies gouttes animées (`monde.emetteurs`).
Le modèle et ses émissions sont réécrits ensemble (`emission_couleurs.glb`, à côté du modèle) ; les volumes
sont aussi écrits en VTK et rendus par f3d (vérification indépendante de notre viewer).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from monde import animation_gltf, emetteurs, export_gltf, gaz, volume_gltf

# Taille réelle typique de la source de chaque émission (m) : l'émission suit la taille du modèle livré.
TAILLE_SOURCE = {"brume": 0.15, "vapeur": 0.10, "flamme": 0.25, "fumee": 1.0, "jet_liquide": 0.8, "gouttes": 0.3}
DIRECTIONS = {"haut": (0.0, 1.0, 0.12), "avant": (0.0, 0.2, 1.0), "bas": (0.0, -1.0, 0.0)}
POINT_PAR_DEFAUT = {"brume": "avant", "gouttes": "bas"}
INSTANTS_VERIFIES = (0.15, 0.45, 1.2)      # s : jet, nuage formé, dissipation


def emissions_du_contrat(contrat: dict | None) -> list[dict[str, Any]]:
    if not isinstance(contrat, dict) or contrat.get("source") != "llm":
        return []
    return [dict(s["emission"]) for s in contrat.get("sujets") or []
            if isinstance(s.get("emission"), dict) and s["emission"].get("type") in emetteurs.LOIS]


def _source_par_la_boite(bornes: np.ndarray, point: str) -> tuple[np.ndarray, np.ndarray]:
    (x0, y0, z0), (x1, y1, z1) = bornes
    hauteur = max(1e-6, y1 - y0)
    cx, cz = (x0 + x1) / 2.0, (z0 + z1) / 2.0
    origine = {"haut": (cx, y1 + 0.01 * hauteur, cz), "avant": (cx, y0 + 0.88 * hauteur, z1 + 0.01 * hauteur),
               "bas": (cx, y0, cz)}[point]
    d = np.asarray(DIRECTIONS[point], dtype=np.float64)
    return np.asarray(origine, dtype=np.float64), d / np.linalg.norm(d)


def _sommets_monde(scene: trimesh.Scene) -> np.ndarray:
    morceaux = []
    for nom_noeud in scene.graph.nodes_geometry:
        matrice, nom_geo = scene.graph[nom_noeud]
        geo = scene.geometry.get(nom_geo)
        if isinstance(geo, trimesh.Trimesh) and len(geo.vertices):
            morceaux.append(trimesh.transform_points(np.asarray(geo.vertices), matrice))
    return np.concatenate(morceaux) if morceaux else np.zeros((1, 3))


def verifier_f3d(volume, glb: Path, dossier_apercus: Path, dossier_verifications: Path, indice: int) -> dict[str, Any]:
    """Le volume relu en VTK et rendu par f3d à trois instants, et le GLB livré rendu de face : jamais notre code."""
    import milieu_scene
    rendus = []
    mn, mx = volume.boite
    centre = 0.5 * (np.asarray(mn) + np.asarray(mx))
    for t in INSTANTS_VERIFIES:
        i = min(len(volume.images) - 1, int(round(t * volume.fps)))
        vti = gaz.ecrire_vti(volume, i, dossier_verifications / f"emission_{indice}_{volume.milieu}_{t:.2f}s.vti")
        png = dossier_apercus / f"emission_{indice}_{volume.milieu}_volume_{t:.2f}s.png"
        res = milieu_scene.rendre_f3d(vti, png, 0.0, resolution=(700, 700), logiciel=True,
                                      options=("--volume", "--camera-direction=0,0,-1",
                                               f"--camera-focal-point={centre[0]},{centre[1]},{centre[2]}"))
        rendus.append({"instant_s": t, "image": i, "vti": str(vti), **{k: res.get(k) for k in ("ok", "png", "erreur")}})
    res = milieu_scene.rendre_f3d(glb, dossier_apercus / "emission_couleurs_face.png", 0.5, resolution=(900, 900),
                                  logiciel=True, options=("-a", "-t", "--camera-direction=0,0,-1"))
    rendus.append({"glb": str(glb), **{k: res.get(k) for k in ("ok", "png", "erreur")}})
    return {"ok": all(r.get("ok") for r in rendus), "rendus": rendus}


def ajouter(glb_entree: str | Path, glb_sortie: str | Path, emissions: list[dict[str, Any]], *,
            reference: str | Path | None = None, resolution: int | None = None,
            dossier_apercus: str | Path | None = None, dossier_verifications: str | Path | None = None) -> dict[str, Any]:
    """Réécrit le modèle avec ses émissions animées ; rend le rapport (bouches, échelles, mesures physiques)."""
    scene = trimesh.load(str(glb_entree), force="scene")
    bornes = np.asarray(scene.bounds)
    hauteur = max(1e-6, float(bornes[1][1] - bornes[0][1]))
    sommets = None
    pistes_toutes: dict[str, dict] = {}
    extras: dict[str, dict] = {}
    volumes, rapport = [], []
    for k, emission in enumerate(emissions):
        type_ = emission["type"]
        point = emission.get("point") or POINT_PAR_DEFAUT.get(type_, "haut")
        origine, direction = _source_par_la_boite(bornes, point)
        reperage, source = None, "boite"
        if reference and Path(reference).is_file():
            from monde import reperage_emission
            reperage = reperage_emission.reperer(reference, type_)
            if reperage:
                if sommets is None:
                    sommets = _sommets_monde(scene)
                origine, direction = reperage_emission.vers_modele(reperage, sommets)
                source = f"reference ({reperage['source_bouche']})"
        echelle = hauteur / TAILLE_SOURCE[type_]
        entree = {"type": type_, "point": point, "source": source, "origine": [round(float(v), 4) for v in origine],
                  "direction": [round(float(v), 4) for v in direction], "echelle": round(float(echelle), 4)}
        if type_ in gaz.GAZ:
            volume = gaz.simuler(type_, direction=tuple(direction), graine=k + 1, resolution=resolution,
                                 nom=f"emission_{k}_{type_}")
            volumes.append(volume.place(origine, echelle))
            rapport.append({**entree, "rendu": "volume", "dims": list(volume.dims), "images": len(volume.images),
                            "pas_reel_m": round(volume.pas, 5), "mesures_reelles": volume.mesures})
            continue
        noeud, pistes, mesures = emetteurs.construire(emetteurs.Emission(
            type_, origine=tuple(origine), direction=tuple(direction), echelle=echelle, nom=f"emission_{k}_{type_}",
            graine=k + 1))
        for inst in noeud.instances:
            for partie in inst.objet.parties:
                maillage = export_gltf._preparer(partie.maillage, partie.materiau, 256)
                scene.add_geometry(maillage, node_name=inst.nom, geom_name=inst.nom, transform=inst.pose.matrice())
                extras[inst.nom] = {"emission": type_}
        pistes_toutes.update(pistes)
        rapport.append({**entree, "rendu": "gouttes", **mesures})
    glb_sortie = Path(glb_sortie)
    glb_sortie.parent.mkdir(parents=True, exist_ok=True)
    glb_sortie.write_bytes(scene.export(file_type="glb", include_normals=True,
                                        tree_postprocessor=lambda arbre: export_gltf._matrices_en_trs(arbre, extras)))
    sortie: dict[str, Any] = {"ok": True, "glb": str(glb_sortie), "emissions": rapport}
    if pistes_toutes:
        injection = animation_gltf.injecter(glb_sortie, pistes_toutes, nom="emission")
        sortie.update(ok=bool(injection["ok"]), canaux=injection["canaux"], absents=injection["absents"])
    if volumes:
        ecrit = volume_gltf.injecter(glb_sortie, volumes)
        relus = volume_gltf.lire(glb_sortie)                   # la preuve : le fichier contient bien les volumes
        sortie["volumes"] = ecrit["volumes"]
        sortie["ok"] = sortie["ok"] and ecrit["ok"] and len(relus) == len(volumes)
        if dossier_apercus and dossier_verifications:
            sortie["verification_f3d"] = [verifier_f3d(v, glb_sortie, Path(dossier_apercus), Path(dossier_verifications), i)
                                          for i, v in enumerate(volumes)]
    return sortie


def main(argv: list[str] | None = None) -> int:
    """Rejoue l'étape des émissions sur un run livré (le module natif, sans relancer la reconstruction)."""
    import argparse
    import json
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True, help="dossier du run livré (modele/, reference/, apercus/, journal/)")
    ap.add_argument("--type", required=True, choices=sorted(emetteurs.LOIS))
    ap.add_argument("--point", choices=sorted(DIRECTIONS))
    ap.add_argument("--resolution", type=int)
    a = ap.parse_args(argv)
    run = Path(a.run)
    reference = run / "reference" / "face.png"
    rapport = ajouter(run / "modele" / "modele_couleurs.glb", run / "modele" / "emission_couleurs.glb",
                      [{"type": a.type, "point": a.point}], reference=reference if reference.is_file() else None,
                      resolution=a.resolution, dossier_apercus=run / "apercus",
                      dossier_verifications=run / "journal" / "verifications")
    print(json.dumps(rapport, ensure_ascii=False, indent=1, default=str))
    return 0 if rapport.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
