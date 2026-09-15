#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Expertise des ARTEFACTS BINAIRES REELS presents sur le disque.

On ouvre les GLB, les MP4, les WAV et les images que les modules ont
REELLEMENT ecrits, et on mesure ce qu'ils contiennent. Pas de fixture, pas de
compilation : les octets livres.

Ce qu'on cherche, c'est la panne SILENCIEUSE — le fichier qui existe, s'ouvre,
fait le bon poids, et ne contient rien :

  - un GLB monochrome ou noir (le bake de couleurs n'a rien pose) ;
  - un GLB annonce anime dont aucune image-cle ne bouge ;
  - une video dont toutes les images sont IDENTIQUES (rendu fige) ou noires ;
  - un son de la bonne duree mais SILENCIEUX ;
  - une image de la bonne taille mais uniforme.

Chaque constat est rendu avec le chemin du fichier et la mesure qui le fonde.

    .venv/bin/python scripts/expertise-artefacts.py [--json] [--limite N]
"""

from __future__ import annotations

import json
import subprocess
import sys
import struct
import wave
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE / "output"

import numpy as np  # noqa: E402


# ---------------------------------------------------------------------------
#  GLB — conteneur binaire glTF 2.0
# ---------------------------------------------------------------------------
def json_du_glb(chemin: Path) -> dict | None:
    """Extrait le morceau JSON d'un GLB, sans bibliotheque tierce.

    Format (specification glTF 2.0, chapitre 4) : entete de 12 octets
    (magic 'glTF', version, longueur totale), puis des morceaux
    [longueur:u32][type:u32][donnees]. Le premier morceau est le JSON.
    """
    with open(chemin, "rb") as fp:
        entete = fp.read(12)
        if len(entete) < 12 or entete[:4] != b"glTF":
            return None
        while True:
            brut = fp.read(8)
            if len(brut) < 8:
                return None
            longueur, type_ = struct.unpack("<II", brut)
            donnees = fp.read(longueur)
            if type_ == 0x4E4F534A:  # 'JSON'
                return json.loads(donnees.decode("utf-8"))


# Suffixes qui DECLARENT une variante volontairement depouillee. Les signaler
# serait un faux positif — et c'en fut un : la premiere version de ce script a
# rendu 3 constats sur 3, tous faux.
#   `_clay`      : rendu d'argile, monochrome PAR DEFINITION (on juge la forme
#                  sans la texture — pratique standard en modelisation) ;
#   `_geometrie` : compagnon geometrie-seule ; ici `modele_geometrie.glb`
#                  (294 Mo) est pose a cote de `modele_couleurs.glb` (294 Mo) ;
#   `_shape`     : etape de forme, anterieure a la texture
#                  (`happy_balanced_shape.glb` precede `happy_definitive.glb`).
VARIANTES_SANS_COULEUR = ("_clay", "_geometrie", "_geometry", "_shape", "_mask",
                          "_ao", "_normal", "_depth", "_wireframe")


def expertise_glb(chemin: Path) -> dict:
    constats = []
    variante = any(chemin.stem.endswith(v) for v in VARIANTES_SANS_COULEUR)
    fiche = {"fichier": str(chemin.relative_to(SORTIE)), "octets": chemin.stat().st_size}

    racine = json_du_glb(chemin)
    if racine is None:
        constats.append(("conteneur-illisible", "ce n est pas un GLB valide : morceau JSON introuvable"))
        return {**fiche, "constats": constats}

    # --- structure declaree ---
    fiche["generateur"] = (racine.get("asset") or {}).get("generator")
    fiche["version"] = (racine.get("asset") or {}).get("version")
    fiche["mailles"] = len(racine.get("meshes") or [])
    fiche["materiaux"] = len(racine.get("materials") or [])
    fiche["textures"] = len(racine.get("textures") or [])
    fiche["images"] = len(racine.get("images") or [])
    fiche["animations"] = len(racine.get("animations") or [])
    fiche["squelettes"] = len(racine.get("skins") or [])

    if fiche["version"] != "2.0":
        constats.append(("version-inattendue", f"asset.version = {fiche['version']!r}"))

    # --- une animation declaree doit avoir des echantillonneurs ---
    for i, anim in enumerate(racine.get("animations") or []):
        voies = anim.get("channels") or []
        ech = anim.get("samplers") or []
        if not voies or not ech:
            constats.append(("animation-vide",
                             f"animation {i} : {len(voies)} voie(s), {len(ech)} echantillonneur(s)"))

    # --- materiaux physiquement plausibles ---
    # Un t-shirt, une peau, du bois ou du tissu ne sont PAS metalliques. Un
    # metallic proche de 1 avec une rugosite basse rend n importe quel sujet
    # en metal poli — c est le rendu "plastique". Mesure le 27/08: les etapes
    # de rig et d animation du service reecrivaient metallic=0.0 en 1.0, et
    # le defaut ne se voyait qu a l oeil, apres avoir paye la generation.
    metal_max, rugo_min = 0.0, 1.0
    for mat in (racine.get("materials") or []):
        pbr = mat.get("pbrMetallicRoughness") or {}
        m = pbr.get("metallicFactor")
        r = pbr.get("roughnessFactor")
        m = 1.0 if m is None else float(m)
        r = 1.0 if r is None else float(r)
        if pbr.get("metallicRoughnessTexture") is not None:
            continue          # pilote par une carte: le facteur ne dit rien
        metal_max = max(metal_max, m)
        rugo_min = min(rugo_min, r)
    if racine.get("materials"):
        fiche["metallic_max"] = round(metal_max, 3)
        fiche["roughness_min"] = round(rugo_min, 3)
        if metal_max >= 0.5 and rugo_min <= 0.6:
            constats.append(("materiau-plastique",
                             f"metallic {metal_max:.2f} et roughness {rugo_min:.2f} : "
                             "surface rendue en metal poli, aspect plastique"))
        elif rugo_min <= 0.25:
            constats.append(("materiau-trop-brillant",
                             f"roughness {rugo_min:.2f} : tout reflete comme du verre mouille"))

    # --- geometrie et couleurs REELLES ---
    try:
        import trimesh
        maille = trimesh.load(str(chemin), force="mesh")
        sommets = int(len(maille.vertices))
        faces = int(len(maille.faces))
        fiche["sommets"] = sommets
        fiche["faces"] = faces
        if sommets < 1000:
            constats.append(("geometrie-indigente", f"{sommets} sommets, {faces} faces"))

        couleurs = None
        visuel = getattr(maille, "visual", None)
        if visuel is not None and getattr(visuel, "kind", None) == "vertex":
            couleurs = np.asarray(visuel.vertex_colors)[:, :3]
        elif visuel is not None and getattr(visuel, "kind", None) == "texture":
            fiche["couleur"] = "texture"
        if couleurs is not None and len(couleurs):
            distinctes = len(np.unique(couleurs.reshape(-1, 3), axis=0))
            luminance = 0.2126 * couleurs[:, 0] + 0.7152 * couleurs[:, 1] + 0.0722 * couleurs[:, 2]
            fiche["couleurs_distinctes"] = int(distinctes)
            fiche["luminance_moyenne"] = round(float(luminance.mean()), 1)
            fiche["ecart_type_luminance"] = round(float(luminance.std()), 2)
            if distinctes <= 2 and not variante:
                constats.append(("maillage-monochrome",
                                 f"{distinctes} couleur(s) distincte(s) sur {sommets} sommets"))
            elif float(luminance.mean()) < 12 and float(luminance.std()) < 8 and not variante:
                constats.append(("maillage-noir",
                                 f"luminance moyenne {luminance.mean():.1f}, ecart-type {luminance.std():.1f}"))
        elif fiche.get("couleur") != "texture" and fiche["textures"] == 0 and not variante:
            constats.append(("aucune-couleur",
                             "ni couleurs de sommet ni texture : le modele sortira blanc"))
    except Exception as exc:  # noqa: BLE001
        constats.append(("geometrie-illisible", f"{type(exc).__name__}: {str(exc)[:80]}"))

    if variante:
        fiche["variante_declaree"] = chemin.stem.rsplit("_", 1)[-1]
    return {**fiche, "constats": constats}


# ---------------------------------------------------------------------------
#  VIDEO — ffprobe pour les metadonnees, ffmpeg pour le CONTENU
# ---------------------------------------------------------------------------
def ffprobe(chemin: Path) -> dict | None:
    try:
        sortie = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(chemin)],
            capture_output=True, text=True, timeout=120)
        return json.loads(sortie.stdout) if sortie.stdout.strip() else None
    except Exception:  # noqa: BLE001
        return None


def profil_de_mouvement(chemin: Path, cote: int = 96) -> dict | None:
    """Ecart entre CHAQUE image et la precedente, sur toute la video.

    La premiere version echantillonnait six images et concluait « figee » si
    elles se ressemblaient. C'est trop grossier : sur `shot_01_silent.mp4`,
    trois images prises ailleurs donnaient deux valeurs distinctes, ce qui
    aurait pu passer pour du mouvement. Le profil COMPLET tranche : 140 images
    sur 140 y sont identiques a la precedente.
    """
    try:
        proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(chemin), "-vf", f"scale={cote}:{cote}",
             "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            capture_output=True, timeout=600)
        taille = cote * cote
        n = len(proc.stdout) // taille
        if n < 2:
            return None
        images = [np.frombuffer(proc.stdout[i * taille:(i + 1) * taille], dtype=np.uint8).astype(np.int16)
                  for i in range(n)]
        ecarts = np.array([float(np.abs(images[i] - images[i - 1]).mean()) for i in range(1, n)])
        return {
            "images": n,
            "ecart_moyen": round(float(ecarts.mean()), 3),
            "ecart_median": round(float(np.median(ecarts)), 3),
            "ecart_max": round(float(ecarts.max()), 3),
            "part_identiques": round(float((ecarts < 0.05).mean()), 4),
            "luminance_moyenne": round(float(np.mean([im.mean() for im in images])), 1),
        }
    except Exception:  # noqa: BLE001
        return None


def expertise_video(chemin: Path) -> dict:
    constats = []
    fiche = {"fichier": str(chemin.relative_to(SORTIE)), "octets": chemin.stat().st_size}
    meta = ffprobe(chemin)
    if not meta or not meta.get("streams"):
        constats.append(("illisible", "ffprobe ne rend aucun flux"))
        return {**fiche, "constats": constats}

    flux_v = next((f for f in meta["streams"] if f.get("codec_type") == "video"), None)
    flux_a = next((f for f in meta["streams"] if f.get("codec_type") == "audio"), None)
    if not flux_v:
        constats.append(("sans-flux-video", "le fichier ne porte aucun flux video"))
        return {**fiche, "constats": constats}

    duree = float((meta.get("format") or {}).get("duration") or 0)
    fiche["codec"] = flux_v.get("codec_name")
    fiche["resolution"] = f"{flux_v.get('width')}x{flux_v.get('height')}"
    fiche["duree_s"] = round(duree, 2)
    fiche["images"] = int(flux_v.get("nb_frames") or 0)
    fiche["audio"] = bool(flux_a)
    fr = flux_v.get("avg_frame_rate") or "0/1"
    try:
        num, den = fr.split("/")
        fiche["ips"] = round(float(num) / float(den), 2) if float(den) else 0.0
    except Exception:  # noqa: BLE001
        fiche["ips"] = 0.0

    if duree <= 0.05:
        constats.append(("duree-nulle", f"duree annoncee {duree}s"))
    if fiche["ips"] <= 0:
        constats.append(("cadence-nulle", f"avg_frame_rate = {fr}"))

    # --- le CONTENU bouge-t-il vraiment ? ---
    profil = profil_de_mouvement(chemin)
    if profil is None:
        constats.append(("images-inextractibles", "ffmpeg ne rend pas d image exploitable"))
    else:
        fiche.update(profil)
        if profil["part_identiques"] >= 0.99:
            constats.append(("video-figee",
                             f"{int(profil['part_identiques'] * (profil['images'] - 1))} images sur "
                             f"{profil['images'] - 1} sont identiques a la precedente "
                             f"(ecart moyen {profil['ecart_moyen']} niveau sur 255) : "
                             "c est une photo encodee en video"))
        elif profil["part_identiques"] >= 0.30 and profil["ecart_moyen"] < 0.5:
            # La part d'images identiques ne suffit PAS a elle seule : un vrai
            # plan comporte des temps d'arret. Mesure : `shot_001.mp4` a 35 %
            # d'images identiques mais un ecart moyen de 2,156 et des pointes a
            # 19,2 — c'est un plan qui bouge, avec des poses. Le signaler serait
            # un faux positif. On exige donc AUSSI que le mouvement d'ensemble
            # soit imperceptible (moins d'un demi-niveau sur 255).
            constats.append(("mouvement-imperceptible",
                             f"{profil['part_identiques'] * 100:.0f} % des images identiques a la "
                             f"precedente ET ecart moyen de {profil['ecart_moyen']} niveau sur 255"))
        if profil["luminance_moyenne"] < 6:
            constats.append(("video-noire", f"luminance moyenne {profil['luminance_moyenne']}/255"))

    return {**fiche, "constats": constats}


# ---------------------------------------------------------------------------
#  AUDIO — un fichier de la bonne duree peut etre silencieux
# ---------------------------------------------------------------------------
def expertise_audio(chemin: Path) -> dict:
    constats = []
    fiche = {"fichier": str(chemin.relative_to(SORTIE)), "octets": chemin.stat().st_size}
    try:
        with wave.open(str(chemin), "rb") as w:
            canaux, largeur, freq, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            brut = w.readframes(min(n, freq * 30))
    except Exception as exc:  # noqa: BLE001
        constats.append(("illisible", f"{type(exc).__name__}: {str(exc)[:70]}"))
        return {**fiche, "constats": constats}

    duree = n / float(freq) if freq else 0.0
    fiche.update({"canaux": canaux, "frequence_hz": freq, "duree_s": round(duree, 2)})
    if duree <= 0.05:
        constats.append(("duree-nulle", f"{duree:.3f}s"))
        return {**fiche, "constats": constats}

    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(largeur)
    if dtype is None:
        constats.append(("format-inattendu", f"{largeur} octets par echantillon"))
        return {**fiche, "constats": constats}
    ech = np.frombuffer(brut, dtype=dtype).astype(np.float64)
    if dtype is np.uint8:
        ech -= 128
    plein = float(np.iinfo(dtype).max if dtype is not np.uint8 else 127)
    crete = float(np.abs(ech).max() / plein) if len(ech) else 0.0
    rms = float(np.sqrt(np.mean((ech / plein) ** 2))) if len(ech) else 0.0
    fiche["crete"] = round(crete, 4)
    fiche["rms"] = round(rms, 5)
    if crete < 0.001:
        constats.append(("audio-silencieux", f"crete {crete:.5f} : le fichier ne porte aucun son"))
    elif rms < 0.0005:
        constats.append(("audio-quasi-silencieux", f"rms {rms:.6f}"))
    return {**fiche, "constats": constats}


# ---------------------------------------------------------------------------
#  IMAGE
# ---------------------------------------------------------------------------
def expertise_image(chemin: Path) -> dict:
    constats = []
    fiche = {"fichier": str(chemin.relative_to(SORTIE)), "octets": chemin.stat().st_size}
    try:
        from PIL import Image
        with Image.open(chemin) as im:
            fiche["taille"] = f"{im.width}x{im.height}"
            fiche["mode"] = im.mode
            a = np.asarray(im.convert("RGB").resize((96, 96)), dtype=np.float32)
    except Exception as exc:  # noqa: BLE001
        constats.append(("illisible", f"{type(exc).__name__}: {str(exc)[:70]}"))
        return {**fiche, "constats": constats}
    lum = 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]
    fiche["luminance_moyenne"] = round(float(lum.mean()), 1)
    fiche["ecart_type"] = round(float(lum.std()), 2)
    if float(lum.std()) < 2:
        constats.append(("image-uniforme",
                         f"ecart-type de luminance {lum.std():.2f} : aplat sans contenu"))
    return {**fiche, "constats": constats}


# ---------------------------------------------------------------------------
def main() -> int:
    args = sys.argv[1:]
    json_out = "--json" in args
    limite = 1000
    if "--limite" in args:
        limite = int(args[args.index("--limite") + 1])

    familles = [
        ("3D (GLB)", sorted((SORTIE / "3d").rglob("*.glb"))[:limite], expertise_glb),
        ("video (MP4)", sorted((SORTIE / "video").rglob("*.mp4"))[:limite], expertise_video),
        ("voix (WAV)", sorted((SORTIE / "voix").rglob("*.wav"))[:limite], expertise_audio),
        ("images", (sorted((SORTIE / "image").rglob("*.png"))
                    + sorted((SORTIE / "3d").rglob("*_reference.png")))[:limite], expertise_image),
    ]

    rapport = {}
    for nom, fichiers, fonction in familles:
        fiches = [fonction(f) for f in fichiers]
        rapport[nom] = fiches
        if json_out:
            continue
        avec = [f for f in fiches if f["constats"]]
        octets = sum(f["octets"] for f in fiches)
        print(f"\n\033[1m{nom}\033[0m — {len(fiches)} fichier(s) reel(s) ouverts, "
              f"{octets / 1_048_576:.1f} Mio lus")
        print("-" * 100)
        for f in fiches:
            if not f["constats"]:
                continue
            print(f"  \033[31m{len(f['constats'])}\033[0m  {f['fichier']}")
            for code, detail in f["constats"]:
                print(f"        \033[31m{code}\033[0m : {detail}")
        if not avec:
            print("  \033[32maucun constat\033[0m")
        # resume chiffre de la famille
        if nom.startswith("3D") and fiches:
            s = [f.get("sommets", 0) for f in fiches if "sommets" in f]
            if s:
                print(f"  sommets : min {min(s):,} / median {sorted(s)[len(s)//2]:,} / max {max(s):,}"
                      .replace(",", " "))
            anim = sum(1 for f in fiches if f.get("animations", 0) > 0)
            tex = sum(1 for f in fiches if f.get("textures", 0) > 0)
            print(f"  {anim}/{len(fiches)} portent une animation ; {tex}/{len(fiches)} portent une texture")
        if nom.startswith("video") and fiches:
            d = [f.get("duree_s", 0) for f in fiches if f.get("duree_s")]
            e = [f.get("ecart_moyen") for f in fiches if f.get("ecart_moyen") is not None]
            if d:
                print(f"  duree : min {min(d)}s / median {sorted(d)[len(d)//2]}s / max {max(d)}s")
            if e:
                print(f"  ecart moyen entre images : min {min(e)} / median {sorted(e)[len(e)//2]} / max {max(e)}")
            fig = sum(1 for f in fiches if f.get("part_identiques", 0) >= 0.99)
            print(f"  {fig}/{len(fiches)} video(s) entierement figee(s)")
        if nom.startswith("voix") and fiches:
            c = [f.get("crete", 0) for f in fiches if "crete" in f]
            if c:
                print(f"  crete : min {min(c)} / median {sorted(c)[len(c)//2]} / max {max(c)}")

    if json_out:
        print(json.dumps(rapport, ensure_ascii=False, indent=2, default=str))
    else:
        total = sum(len(f["constats"]) for fs in rapport.values() for f in fs)
        fichiers = sum(len(fs) for fs in rapport.values())
        print("\n" + "=" * 100)
        print(f"{fichiers} artefacts reels ouverts et mesures — {total} constat(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
