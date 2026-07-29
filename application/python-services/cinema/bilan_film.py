#!/usr/bin/env python3
"""Bilan d'un film livre : des mesures, pas des impressions.

Ce que cet outil refuse de faire : dire qu'un film est bon. Il donne les
chiffres qui permettent de le juger sans le regarder, et signale ce qui manque.

Les quatre questions auxquelles il repond :
  1. Le film est-il COMPLET ? (plans livres / demandes, plans abandonnes)
  2. Les plans BOUGENT-ils ? (amplitude ; sous 1, c'est une photo sonorisee)
  3. Le film TIENT-il ensemble ? (constance entre plans, ecart de couleur)
  4. Les voix sont-elles reproduites ou inventees ?

Usage :
  python bilan_film.py                       # dernier film publie
  python bilan_film.py <dossier_du_film>
"""

import glob
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE.parent.parent
RESULTATS = APP / "output" / "RESULTATS"


def _charger(nom, fichier):
    import importlib.util
    spec = importlib.util.spec_from_file_location(nom, str(HERE / fichier))
    m = importlib.util.module_from_spec(spec)
    sys.modules[nom] = m
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    return m


def _ffprobe(path, entries):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", entries, "-of", "csv=p=0:s=x", str(path)],
            capture_output=True, text=True, timeout=30)
        return out.stdout.strip()
    except Exception:
        return "?"


def dernier_film():
    dossiers = [d for d in glob.glob(str(RESULTATS / "film_*")) if os.path.isdir(d)]
    return max(dossiers, key=os.path.getmtime) if dossiers else None


def bilan(dossier: str) -> int:
    dossier = Path(dossier)
    if not dossier.is_dir():
        print(f"dossier introuvable : {dossier}")
        return 1

    print(f"FILM : {dossier.name}")
    print(f"       {dossier}\n")

    film = dossier / "film.mp4"
    if film.exists():
        dims = _ffprobe(film, "stream=width,height")
        duree = _ffprobe(film, "format=duration") or "?"
        print(f"  livrable   : {dims}, {os.path.getsize(film) / 1e6:.1f} Mo")

    rapport = dossier / "rapport.json"
    d = {}
    if rapport.exists():
        try:
            d = json.loads(rapport.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  rapport illisible : {str(exc)[:80]}")

    # 1. COMPLETUDE — un film n'a jamais le droit de pretendre etre entier
    livres, demandes = d.get("plans_livres"), d.get("plans_demandes")
    if demandes:
        etat = "COMPLET" if livres == demandes else "INCOMPLET"
        print(f"  plans      : {livres}/{demandes}  {etat}")
    for p in (d.get("plans_abandonnes") or []):
        print(f"     plan {p.get('plan')} abandonne : {str(p.get('raison'))[:90]}")

    print(f"  moteur     : {d.get('moteur_video') or '?'}")

    # 2. MOUVEMENT — sous 1, le plan est une photographie avec du son
    CP = _charger("cp_bilan", "cinema_pipeline.py")
    # Un seul fichier par plan : le DERNIER de la chaine. Sur un plan dialogue,
    # le `_silent` est un intermediaire volontairement fige que S2V anime
    # ensuite — le compter reviendrait a signaler un defaut qui n'existe pas.
    plans = sorted(glob.glob(str(dossier / "plans" / "*.mp4")))
    par_plan = {}
    for p in plans:
        nom = os.path.basename(p)
        if "seg" in nom or "retry" in nom:
            continue
        cle = nom.split("_")[1] if "_" in nom else nom
        rang = ("synced" in nom) * 3 + ("muxed" in nom) * 2 + ("silent" in nom) * 1
        if rang and rang >= par_plan.get(cle, (0, None))[0]:
            par_plan[cle] = (rang, p)
    finaux = [v[1] for _, v in sorted(par_plan.items())]
    if finaux:
        print("\n  PLANS (amplitude < 1 = photographie sonorisee)")
        figes = 0
        for p in finaux:
            a = CP._mesure_amplitude(p)
            fige = a is not None and a < 1.0
            figes += int(fige)
            print(f"    {os.path.basename(p)[:32]:34} {_ffprobe(p, 'stream=width,height'):>10}"
                  f"  amplitude {str(a):>6}  {'FIGE' if fige else 'anime'}")
        if figes:
            print(f"    -> {figes} plan(s) fige(s)")

    # 3. TENUE D'ENSEMBLE — les mesures objectives du rendu
    mes = d.get("mesures_chiffrees")
    if mes:
        print("\n  PORTE CHIFFREE")
        for p in (mes.get("plans") or []):
            if not p.get("graded"):
                continue
            print(f"    {str(p.get('plan'))[:28]:30} constance={p.get('constance')} "
                  f"derive={p.get('derive_interne')} deltaE={p.get('delta_e')}"
                  f"  {'OK' if p.get('ok') else 'HORS SEUILS'}")
        refuses = mes.get("refuses") or []
        print(f"    -> {len(refuses)} plan(s) hors seuils")
    elif finaux:
        print("\n  PORTE CHIFFREE : non executee sur ce film "
              "(mesure a posteriori possible via porte_chiffree.py --film)")

    # 4. VOIX — reproduite ou inventee, jamais ambigu
    voix = d.get("voix_conçues") or d.get("voix_concues") or {}
    if voix:
        print("\n  VOIX CONCUES")
        for nom, c in voix.items():
            print(f"    {nom:14} registre={c.get('registre')} timbre={c.get('timbre')}")
    for e in (d.get("dialogue_quality") or []):
        print(f"    plan {e.get('shot')} : voix={e.get('voice_engine')} "
              f"lipsync={e.get('lipsync_engine') or 'aucun'} "
              f"amplitude={e.get('motion_amplitude')}")

    amb = d.get("ambiance")
    if amb:
        print(f"\n  AMBIANCE   : {'posee' if amb.get('ok') else 'absente'}"
              f"  {str(amb.get('lieu') or '')}")

    avert = d.get("warnings") or []
    if avert:
        print(f"\n  AVERTISSEMENTS ({len(avert)})")
        for e in avert[:12]:
            print(f"    [{e.get('stage')}] {str(e.get('warning'))[:88]}")
    return 0


def main():
    cible = sys.argv[1] if len(sys.argv) > 1 else dernier_film()
    if not cible:
        print("aucun film publie dans output/RESULTATS/")
        return 1
    return bilan(cible)


if __name__ == "__main__":
    sys.exit(main())
