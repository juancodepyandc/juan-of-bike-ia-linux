#!/usr/bin/env python3
"""Bibliotheque video Aurora : une seule arborescence, des noms lisibles.

Probleme resolu : chaque rendu laissait DEUX dossiers derriere lui — celui du
bridge (`temp/cinema/job_<id16>/` avec le final.mp4) et celui du pipeline
(`temp/cinema/job_<timestamp>/` avec 49 fichiers de travail), plus les
`sample_*` d'essai. Pour trois vrais resultats on se retrouvait avec quatorze
dossiers aux noms illisibles, dans un repertoire *temporaire* — donc rien de
citable ni de retrouvable.

Arborescence canonique produite :

  output/videos/
    films/<date>_<titre-lisible>/
        film.mp4            le livrable
        plans/              les plans montes individuellement
        references/         keyframes personnages, decors
        audio/              voix, musique
        storyboard.json
        rapport.json        qualite, duree, modeles, temps de rendu
    clips/<date>_<titre>.mp4
    _travail/               intermediaires, purgeable sans rien perdre

Regles :
  - un livrable n'est JAMAIS supprime, seulement deplace ;
  - les doublons sont detectes par sha256 du contenu, pas par nom ;
  - `--apply` est requis pour ecrire : par defaut le script ne fait que dire
    ce qu'il ferait.

Usage :
  python video_library.py                 # inventaire, ne touche a rien
  python video_library.py --apply         # range
  python video_library.py --apply --purge # range puis vide les intermediaires
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CINEMA_TEMP = os.path.join(WORKSPACE, "temp", "cinema")

# v94 — UN SEUL ENDROIT OU L'ON RECOIT.
# Avant : les livrables etaient a `output/videos/films/<date>_<titre>/`, trois
# niveaux sous une racine `output/` qui contenait 37 entrees, dont 26 preuves
# d'audit de sessions passees. Resultat : on ne trouvait pas son film.
# Desormais tout ce qui est FINI, quel que soit le module, atterrit a plat dans
# `output/RESULTATS/`, prefixe par module (`film_`, `image_`, `modele3d_`).
# Les repertoires de travail vivent ailleurs et sont supprimes apres
# publication : un exemplaire de construction n'a rien a faire a cote d'un
# livrable.
RESULTATS = os.path.join(WORKSPACE, "output", "RESULTATS")
FILMS = RESULTATS
CLIPS = os.path.join(WORKSPACE, "output", "_travail", "clips")
TRAVAIL = os.path.join(WORKSPACE, "output", "_travail")
PREFIXE_FILM = "film_"

DELIVERABLE_NAMES = {"final.mp4", "sample.mp4"}


def slugify(text, maxlen=48):
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
    return (t[:maxlen].rstrip("-")) or "sans-titre"


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def human(n):
    for u in ("o", "Ko", "Mo", "Go"):
        if n < 1024:
            return f"{n:.0f} {u}"
        n /= 1024
    return f"{n:.1f} To"


def probe(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-show_entries", "format=duration", "-of", "json", path],
            capture_output=True, text=True, timeout=30)
        d = json.loads(out.stdout or "{}")
        st = (d.get("streams") or [{}])[0]
        return {"width": st.get("width"), "height": st.get("height"),
                "duration_s": round(float((d.get("format") or {}).get("duration") or 0), 2)}
    except Exception:
        return {}


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def publish_job(job_dir, work_dir, title, final_mp4, kind="film"):
    """Publie un rendu termine dans la bibliotheque et renvoie son dossier.

    Appelee directement par cinema_pipeline a la fin d'un rendu : c'est ce qui
    fait qu'un film apparait dans `output/videos/films/` sans intervention.
    Le job reste intact dans temp/ (on COPIE), pour que la publication ne
    puisse jamais detruire un resultat coutant des heures de calcul.
    """
    if not final_mp4 or not os.path.exists(final_mp4):
        raise RuntimeError(f"livrable introuvable : {final_mp4}")
    if os.path.getsize(final_mp4) < 10000:
        raise RuntimeError(f"livrable trop petit : {final_mp4}")

    date = time.strftime("%Y-%m-%d")
    # Prefixe par module : dans un dossier unique qui recoit TOUS les livrables,
    # c'est ce qui permet de retrouver un film au milieu des images et des GLB.
    base = f"{PREFIXE_FILM}{date}_{slugify(title or os.path.basename(job_dir))}"
    if kind == "sample":
        base += "_essai"
    dest = os.path.join(FILMS, base)
    if os.path.exists(dest):
        dest = os.path.join(FILMS, base + "_" + time.strftime("%Hh%M"))
    for sub in ("plans", "references", "audio"):
        os.makedirs(os.path.join(dest, sub), exist_ok=True)

    shutil.copy2(final_mp4, os.path.join(dest, "film.mp4"))
    for f in ("storyboard.json", "status.json"):
        p = os.path.join(job_dir, f)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(dest, f))

    if work_dir and os.path.isdir(work_dir):
        for f in os.listdir(work_dir):
            p = os.path.join(work_dir, f)
            if not os.path.isfile(p):
                continue
            if f.startswith("char_") and f.endswith(".png"):
                shutil.copy2(p, os.path.join(dest, "references", f))
            elif f.endswith((".wav", ".mp3")):
                shutil.copy2(p, os.path.join(dest, "audio", f))
            elif f.startswith("shot_") and f.endswith(".mp4"):
                shutil.copy2(p, os.path.join(dest, "plans", f))

    film = os.path.join(dest, "film.mp4")
    with open(os.path.join(dest, "rapport.json"), "w") as f:
        json.dump({
            "titre": title, "date": date, "type": kind,
            "video": probe(film), "sha256": sha256(film),
            "source_job": job_dir, "source_work": work_dir,
            "publie_le": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, f, ensure_ascii=False, indent=2)
    return dest


def discover():
    """Inventorie les dossiers de rendu et les classe."""
    entries = []
    if not os.path.isdir(CINEMA_TEMP):
        return entries
    for name in sorted(os.listdir(CINEMA_TEMP)):
        d = os.path.join(CINEMA_TEMP, name)
        if not os.path.isdir(d):
            continue
        files = os.listdir(d)
        deliverables = [f for f in files if f in DELIVERABLE_NAMES]
        size = 0
        for root, _, fs in os.walk(d):
            for f in fs:
                try:
                    size += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        sb = read_json(os.path.join(d, "storyboard.json"))
        entries.append({
            "dir": d, "name": name, "files": files,
            "deliverables": deliverables,
            "has_deliverable": bool(deliverables),
            "title": sb.get("title") or "",
            "size": size,
            "mtime": os.path.getmtime(d),
            "is_work_dir": any(f.startswith("shot_") for f in files),
        })
    return entries


def collect_work_dir(entries, job_entry):
    """Associe au dossier de livraison le dossier de travail du pipeline.

    Le pipeline nomme son dossier `job_<timestamp>` et le bridge `job_<id16>` :
    on apparie par proximite temporelle, le dossier de travail etant cree juste
    apres celui du bridge.
    """
    best, best_dt = None, 1e18
    for e in entries:
        if e is job_entry or not e["is_work_dir"] or e["has_deliverable"]:
            continue
        dt = abs(e["mtime"] - job_entry["mtime"])
        if dt < best_dt and dt < 7200:
            best, best_dt = e, dt
    return best


def organise(apply_changes, purge):
    os.makedirs(FILMS, exist_ok=True)
    os.makedirs(CLIPS, exist_ok=True)
    entries = discover()
    actions, seen_hashes = [], {}
    kept_dirs = set()

    for e in entries:
        if not e["has_deliverable"]:
            continue
        for dname in e["deliverables"]:
            src = os.path.join(e["dir"], dname)
            if os.path.getsize(src) < 10000:
                actions.append(("supprimer-vide", src, "", 0))
                continue
            h = sha256(src)
            if h in seen_hashes:
                actions.append(("doublon", src, seen_hashes[h], os.path.getsize(src)))
                continue
            seen_hashes[h] = src

            date = time.strftime("%Y-%m-%d", time.localtime(e["mtime"]))
            title = slugify(e["title"] or e["name"])
            kind = "sample" if dname == "sample.mp4" else "film"
            base = f"{date}_{title}" + ("_essai" if kind == "sample" else "")
            # Plusieurs essais partagent le meme titre de storyboard : sans
            # suffixe ils s'ecraseraient les uns les autres. On desambiguise
            # par l'heure, qui reste lisible.
            dest_dir = os.path.join(FILMS, base)
            if dest_dir in [a[2] and os.path.dirname(a[2]) for a in actions
                            if a[0] == "ranger"]:
                dest_dir = os.path.join(
                    FILMS, base + "_" + time.strftime("%Hh%M", time.localtime(e["mtime"])))
            actions.append(("ranger", src, os.path.join(dest_dir, "film.mp4"),
                            os.path.getsize(src)))
            kept_dirs.add(e["dir"])
            # le dossier de travail associe sera absorbe : ce n'est pas un residu
            wd = collect_work_dir(entries, e)
            if wd:
                kept_dirs.add(wd["dir"])

            if apply_changes:
                os.makedirs(dest_dir, exist_ok=True)
                os.makedirs(os.path.join(dest_dir, "plans"), exist_ok=True)
                os.makedirs(os.path.join(dest_dir, "references"), exist_ok=True)
                os.makedirs(os.path.join(dest_dir, "audio"), exist_ok=True)
                shutil.copy2(src, os.path.join(dest_dir, "film.mp4"))
                for f in ("storyboard.json", "status.json"):
                    p = os.path.join(e["dir"], f)
                    if os.path.exists(p):
                        shutil.copy2(p, os.path.join(dest_dir, f))

                work = collect_work_dir(entries, e)
                if work:
                    kept_dirs.add(work["dir"])
                    for f in os.listdir(work["dir"]):
                        p = os.path.join(work["dir"], f)
                        if not os.path.isfile(p):
                            continue
                        if f.startswith("char_") and f.endswith(".png"):
                            shutil.copy2(p, os.path.join(dest_dir, "references", f))
                        elif f.endswith((".wav", ".mp3")):
                            shutil.copy2(p, os.path.join(dest_dir, "audio", f))
                        elif f.startswith("shot_") and f.endswith(".mp4"):
                            shutil.copy2(p, os.path.join(dest_dir, "plans", f))

                info = probe(os.path.join(dest_dir, "film.mp4"))
                rapport = {
                    "titre": e["title"], "date": date, "type": kind,
                    "source_dir": e["dir"], "work_dir": work["dir"] if work else None,
                    "video": info, "sha256": h,
                    "range_le": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                with open(os.path.join(dest_dir, "rapport.json"), "w") as f:
                    json.dump(rapport, f, ensure_ascii=False, indent=2)

    # ce qui n'a produit aucun livrable est un residu
    residus = [e for e in entries
               if e["dir"] not in kept_dirs and not e["has_deliverable"]]
    for e in residus:
        actions.append(("residu", e["dir"], "", e["size"]))

    if apply_changes and purge:
        for e in residus:
            shutil.rmtree(e["dir"], ignore_errors=True)
        for e in entries:
            if e["has_deliverable"] and e["dir"] in kept_dirs:
                shutil.rmtree(e["dir"], ignore_errors=True)
        for e in entries:
            w = e["dir"]
            if os.path.isdir(w) and w in kept_dirs:
                shutil.rmtree(w, ignore_errors=True)

    return actions, entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="ecrit reellement (sinon : inventaire seul)")
    ap.add_argument("--purge", action="store_true",
                    help="supprime les dossiers sources apres rangement")
    args = ap.parse_args()

    actions, entries = organise(args.apply, args.purge)

    total_before = sum(e["size"] for e in entries)
    ranges = [a for a in actions if a[0] == "ranger"]
    doublons = [a for a in actions if a[0] == "doublon"]
    residus = [a for a in actions if a[0] == "residu"]
    vides = [a for a in actions if a[0] == "supprimer-vide"]

    print(f"{'=' * 70}")
    print(f"BIBLIOTHEQUE VIDEO — {'RANGEMENT APPLIQUE' if args.apply else 'INVENTAIRE (rien modifie)'}")
    print(f"{'=' * 70}")
    print(f"dossiers examines : {len(entries)}  ({human(total_before)})")
    print()
    print(f"livrables ranges  : {len(ranges)}")
    for _, src, dst, sz in ranges:
        print(f"   {os.path.basename(os.path.dirname(dst)):45s} {human(sz):>9s}")
    print(f"doublons          : {len(doublons)} "
          f"({human(sum(a[3] for a in doublons))} recuperables)")
    for _, src, ref, sz in doublons:
        print(f"   {src.replace(WORKSPACE + '/', '')} == {os.path.basename(os.path.dirname(ref))}")
    print(f"fichiers vides    : {len(vides)}")
    print(f"residus sans livrable : {len(residus)} "
          f"({human(sum(a[3] for a in residus))} recuperables)")
    for _, d, _, sz in residus:
        print(f"   {d.replace(WORKSPACE + '/', ''):55s} {human(sz):>9s}")
    print()
    if not args.apply:
        print("Rien n'a ete modifie. Relance avec --apply (et --purge pour vider).")
    else:
        print(f"Bibliotheque : {FILMS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
