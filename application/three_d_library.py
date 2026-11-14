"""Bibliothèque 3D par projet, pour le visualiseur.

`/api/3d/list` renvoie chaque GLB à plat : une génération y apparaît sous quatre fichiers aux noms
identiques d'un projet à l'autre (`modele_couleurs.glb`, `modele_geometrie.glb`,
`mouvement_couleurs.glb`, `mouvement_geometrie.glb`), sans titre ni aperçu, et la vue 3D n'offrait
qu'un sélecteur de fichier brut pour rouvrir un modèle. Ce module regroupe les fichiers par
génération : titre tiré de la demande, vignette tirée des aperçus déjà rendus, livrable par défaut
(l'animé s'il existe, sinon le modèle en couleurs) et variantes nommées pour un humain.
"""
from __future__ import annotations

import json
import os
import re
import struct
from typing import Any

MODELE_EXTS = (".glb", ".gltf")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
DOSSIERS_DE_ROLE = {"modele": "modele", "mouvement": "mouvement", "work": "travail", "travail": "travail"}


_ANIME_CACHE: dict[tuple[str, int, int], bool] = {}


def _est_anime(chemin: str, st: os.stat_result) -> bool:
    """Le GLB porte-t-il une animation ? Lu dans son bloc JSON, sans charger la géométrie."""
    cle = (chemin, int(st.st_mtime), st.st_size)
    if cle in _ANIME_CACHE:
        return _ANIME_CACHE[cle]
    anime = False
    try:
        with open(chemin, "rb") as fichier:
            entete = fichier.read(20)
            if len(entete) == 20 and entete[:4] == b"glTF":
                longueur, type_bloc = struct.unpack_from("<II", entete, 12)
                if type_bloc == 0x4E4F534A and 0 < longueur < 64 * 1024 * 1024:
                    anime = bool(json.loads(fichier.read(longueur)).get("animations"))
    except (OSError, ValueError):
        anime = False
    _ANIME_CACHE[cle] = anime
    return anime


def _role(dossier_role: str, nom: str, anime: bool = False) -> tuple[str, int]:
    """Libellé lisible et rang de préférence (plus petit = livrable plus probable)."""
    n = nom.lower()
    geometrie = "geometrie" in n or "geometry" in n
    if anime and dossier_role != "travail":
        return ("Animé — géométrie", 3) if geometrie else ("Animé — couleurs", 0)
    if dossier_role == "mouvement":
        return ("Animé — géométrie", 3) if geometrie else ("Animé — couleurs", 0)
    if dossier_role == "modele":
        return ("Géométrie seule", 4) if geometrie else ("Couleurs", 1)
    if dossier_role == "travail":
        return (f"Intermédiaire — {nom}", 8)
    return (nom, 5)


def _titre(dossier_projet: str, identifiant: str) -> str:
    """La demande de l'utilisateur, jamais le prompt technique envoyé au générateur."""
    # 1. format de l'interface : en-tête clé=valeur (session, run) puis la demande
    chemin = os.path.join(dossier_projet, "prompt", "prompt.txt")
    try:
        with open(chemin, encoding="utf-8") as fichier:
            lignes = [l.strip() for l in fichier.read().splitlines()]
        if any(re.match(r"^(run_id|session_id)=", l) for l in lignes):
            demande = [l for l in lignes if l and not re.match(r"^[a-z_]+=", l)]
            if demande:
                return demande[-1][:160]
    except OSError:
        pass
    # 2. la demande lue par le pipeline (journal d'audit)
    try:
        with open(os.path.join(dossier_projet, "journal", "audit.json"), encoding="utf-8") as fichier:
            audit = json.load(fichier)
        etapes = audit if isinstance(audit, list) else audit.get("audit", [])
        for etape in etapes:
            if isinstance(etape, dict) and etape.get("stage") == "lecture_demande" and etape.get("demande"):
                return str(etape["demande"])[:160]
    except (OSError, ValueError, AttributeError):
        pass
    # repli : le nom du dossier de conversation, sans l'identifiant de run
    parent = os.path.basename(os.path.dirname(dossier_projet)) if identifiant else ""
    base = parent or os.path.basename(dossier_projet)
    run = os.path.basename(dossier_projet)
    if run and base.endswith(run):
        base = base[: -len(run)]
    base = re.sub(r"_[0-9a-f]{8}(-[0-9a-f]{4}){1,4}$", "", base)
    texte = re.sub(r"[_-]+", " ", base).strip()
    return texte or os.path.basename(dossier_projet)


def _vignette(dossier_projet: str) -> str | None:
    """Premier aperçu existant, du plus parlant au plus brut."""
    candidats = []
    for sous, motifs in (("apercus", (r"^f3d_.*t0", r"_mesh_vue000\.", r"front", r"\.(png|jpe?g|webp)$")),
                         ("reference", (r"^face\.", r"\.(png|jpe?g|webp)$")),
                         ("work", (r"_reference\.", r"_GEOMETRIE_front\."))):
        dossier = os.path.join(dossier_projet, sous)
        try:
            noms = sorted(os.listdir(dossier))
        except OSError:
            continue
        for rang, motif in enumerate(motifs):
            for nom in noms:
                if nom.lower().endswith(IMAGE_EXTS) and re.search(motif, nom, re.IGNORECASE):
                    candidats.append((len(candidats), rang, os.path.join(dossier, nom)))
                    break
            if candidats:
                break
        if candidats:
            break
    return candidats[0][2] if candidats else None


def projets_3d(racines: list[str]) -> list[dict[str, Any]]:
    """Projets 3D (une génération = un projet) trouvés sous les racines, du plus récent au plus ancien.

    Les chemins rendus sont relatifs à la première racine, préfixés par le nom de la racine pour les
    suivantes, comme dans `/api/3d/list`, et servis par `/api/3d/file/<chemin>`.
    """
    projets: dict[str, dict[str, Any]] = {}
    for index, racine in enumerate(racines):
        racine = os.path.realpath(racine)
        if not os.path.isdir(racine):
            continue
        prefixe = os.path.basename(racine) + "/" if index else ""

        def relatif(chemin: str) -> str:
            return prefixe + os.path.relpath(chemin, racine).replace(os.sep, "/")

        for dossier, sous, fichiers in os.walk(racine, followlinks=False):
            sous[:] = [d for d in sous if not d.startswith(".")]
            for nom in fichiers:
                if not nom.lower().endswith(MODELE_EXTS):
                    continue
                plein = os.path.join(dossier, nom)
                try:
                    st = os.stat(plein)
                except OSError:
                    continue
                parent = os.path.basename(dossier)
                role_dossier = DOSSIERS_DE_ROLE.get(parent, "")
                dossier_projet = os.path.dirname(dossier) if role_dossier else dossier
                cle = relatif(dossier_projet)
                projet = projets.setdefault(cle, {"id": cle, "dossier": cle, "_plein": dossier_projet,
                                                  "_racine": racine, "_prefixe": prefixe,
                                                  "variantes": [], "modifie": 0})
                libelle, rang = _role(role_dossier, nom, _est_anime(plein, st))
                projet["variantes"].append({"role": libelle, "rang": rang, "nom": nom, "chemin": relatif(plein),
                                            "url": "/api/3d/file/" + relatif(plein), "octets": st.st_size,
                                            "modifie": int(st.st_mtime), "intermediaire": role_dossier == "travail"})
                projet["modifie"] = max(projet["modifie"], int(st.st_mtime))

    resultat = []
    for projet in projets.values():
        variantes = projet["variantes"]
        livrables = [v for v in variantes if not v["intermediaire"]]
        if livrables:
            variantes = livrables          # un projet livré ne montre pas ses fichiers de travail
        variantes.sort(key=lambda v: (v["rang"], -v["modifie"], v["nom"]))
        plein, racine_p, prefixe_p = projet.pop("_plein"), projet.pop("_racine"), projet.pop("_prefixe")
        vignette = _vignette(plein)
        resultat.append({
            "id": projet["id"],
            "dossier": projet["dossier"],
            "titre": _titre(plein, projet["id"]),
            "modifie": projet["modifie"],
            "livrable": {k: variantes[0][k] for k in ("role", "nom", "url", "octets")},
            "anime": any(v["role"].startswith("Animé") for v in variantes),
            "variantes": [{k: v[k] for k in ("role", "nom", "url", "octets")} for v in variantes],
            "vignette": ("/api/3d/file/" + prefixe_p + os.path.relpath(vignette, racine_p).replace(os.sep, "/"))
            if vignette and os.path.realpath(vignette).startswith(racine_p + os.sep) else None,
        })
    resultat.sort(key=lambda p: (-p["modifie"], p["id"]))
    return resultat
