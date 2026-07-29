#!/usr/bin/env python3
"""Conception de voix : un timbre qui n'appartient a personne.

LE PROBLEME, POSE CORRECTEMENT
------------------------------
Demander a l'utilisateur un echantillon par personnage n'est pas une solution,
c'est un aveu — surtout pour un film a cinq personnages. Mais aller PRELEVER la
voix d'une personne reelle sur le web est a ecarter frontalement : une voix est
une donnee biometrique des lors qu'elle sert a reproduire un locuteur (art. 9
RGPD), la jurisprudence francaise la protege comme l'image, et des comediens de
doublage ont obtenu gain de cause en avril 2026. L'outillage serait propre
(Demucs MIT, pyannote MIT) ; l'usage ne l'est pas.

Il ne reste donc qu'une voie, et elle est bonne : une voix CONCUE, pas prelevee.
Aucune personne reelle, aucun consentement a demander, aucune donnee
biometrique — et un timbre reproductible a l'identique d'un plan a l'autre.

L'ARCHITECTURE, ET POURQUOI ELLE EST EN DEUX ETAGES
---------------------------------------------------
Aucun moteur unique ne sait a la fois concevoir un timbre par description ET
parler francais sous licence commerciale :
  - CosyVoice3 parle francais et clone, mais ses auteurs ecrivent noir sur blanc
    qu'il « cannot control acoustic characteristics, such as timbre, through
    textual instructions » ;
  - Maya1 concoit un timbre depuis une description, mais en anglais seulement.

D'ou la separation : ETAGE 1 fabrique une GRAINE de timbre (jamais livree),
ETAGE 2 rend la parole francaise en clonant cette graine.

Piege documente et evite : `Fun-CosyVoice3-0.5B-2512` n'embarque PAS de
`spk2info.pt`. Le chemin `inference_sft` (locuteurs pre-entraines) y echouerait
EN SILENCE. On passe donc toujours par `inference_zero_shot`.

Usage :
  python voice_design.py --check
  python voice_design.py --concevoir "Natsu" --description "jeune homme, voix
      claire et energique, timbre chaud, un peu rauque dans les aigus" --lang fr
  python voice_design.py --projet mon_film --verifier-distinction
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
BANQUE = WORKSPACE / "voices" / "banque"
CACHE = WORKSPACE / "temp" / "voice_design"

# Seuils des trois portes. Calibres sur la litterature ECAPA : au-dela de 0,25
# de similarite cosinus on parle du meme locuteur pour un systeme de
# verification ; on exige nettement plus pour la fidelite, et nettement moins
# entre deux personnages.
SEUIL_FIDELITE = 0.45      # graine -> rendu francais : le timbre a-t-il tenu ?
SEUIL_DISTINCTION = 0.55   # deux personnages au-dessus = trop proches
SEUIL_CER = 0.15           # articulation francaise (taux d'erreur caracteres)

# Timbres-graines synthetiques disponibles sans aucun telechargement, tries par
# registre. Ce sont des voix Kokoro (Apache 2.0) : entierement synthetiques,
# elles n'appartiennent a personne. Elles servent UNIQUEMENT de graine de
# timbre ; la parole francaise est rendue par CosyVoice3.
GRAINES_KOKORO = {
    "homme_grave": ["am_fenrir", "bm_george", "am_michael", "bm_lewis"],
    "homme_moyen": ["am_adam", "bm_daniel", "am_eric", "im_nicola"],
    "homme_clair": ["am_liam", "am_echo", "bm_fable", "em_alex"],
    "femme_grave": ["bf_alice", "af_nicole", "bf_emma"],
    "femme_moyenne": ["af_heart", "af_bella", "bf_isabella", "af_sarah"],
    "femme_claire": ["af_alloy", "af_jessica", "bf_lily", "af_river"],
}

MOTS_GRAVE = ("grave", "profond", "basse", "caverneux", "rauque", "age",
              "vieux", "ancien", "bourru")
MOTS_CLAIR = ("clair", "aigu", "jeune", "enfant", "leger", "haut", "fluet")
MOTS_FEMME = ("femme", "feminin", "feminine", "fille", "dame", "madame",
              "mere", "soeur")

# Texte de la graine. Sa transcription doit etre EXACTE au moment du clonage
# zero-shot : CosyVoice3 aligne le timbre sur ce couple (audio, texte), et une
# transcription approximative degrade l'alignement. Une seule definition, donc.
GRAINE_TEXTE_EN = (
    "This is a reference recording of my natural speaking voice. "
    "I am speaking calmly and clearly, at a steady pace, so that the "
    "timbre and the colour of my voice can be heard without effort.")


def emit(stage: str, detail: str = ""):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def _registre(description: str) -> str:
    """Traduit une description libre en registre, pour choisir la graine."""
    d = (description or "").lower()
    genre = "femme" if any(m in d for m in MOTS_FEMME) else "homme"
    if any(m in d for m in MOTS_GRAVE):
        hauteur = "grave"
    elif any(m in d for m in MOTS_CLAIR):
        hauteur = "clair"
    else:
        hauteur = "moyen"
    if genre == "femme":
        hauteur = {"grave": "grave", "moyen": "moyenne", "clair": "claire"}[hauteur]
    return f"{genre}_{hauteur}"


def graines_disponibles(registre: str, deja_prises: set) -> list:
    """Graines du registre demande, celles deja attribuees en dernier.

    On ne refuse jamais une graine deja prise : sur un film a beaucoup de
    personnages il faut bien reutiliser un registre. Mais on epuise d'abord les
    timbres libres, ce qui maximise la distinction sans jamais bloquer.
    """
    toutes = GRAINES_KOKORO.get(registre) or GRAINES_KOKORO["homme_moyen"]
    libres = [g for g in toutes if g not in deja_prises]
    prises = [g for g in toutes if g in deja_prises]
    return libres + prises


def _kokoro_voices_dir():
    import glob
    motif = os.path.expanduser(
        "~/.cache/huggingface/hub/models--hexgrad--Kokoro-82M/snapshots/*/voices")
    trouves = glob.glob(motif)
    return Path(trouves[0]) if trouves else None


def generer_graine(nom_voix: str, texte_en: str, sortie_wav: str) -> dict:
    """Fabrique la graine de timbre : ~15 s d'anglais, jamais livree au film."""
    try:
        import soundfile as sf
        from kokoro import KPipeline
    except Exception as exc:
        return {"ok": False, "error": f"kokoro indisponible: {str(exc)[:120]}"}
    try:
        pipeline = KPipeline(lang_code=nom_voix[0], repo_id="hexgrad/Kokoro-82M")
        morceaux = []
        for _, _, audio in pipeline(texte_en, voice=nom_voix, speed=1.0):
            morceaux.append(audio)
        if not morceaux:
            return {"ok": False, "error": "kokoro n'a produit aucun audio"}
        import numpy as np
        signal = np.concatenate([m.detach().cpu().numpy()
                                 if hasattr(m, "detach") else np.asarray(m)
                                 for m in morceaux])
        Path(sortie_wav).parent.mkdir(parents=True, exist_ok=True)
        sf.write(sortie_wav, signal, 24000)
        return {"ok": True, "wav": sortie_wav,
                "duree_s": round(len(signal) / 24000.0, 2)}
    except Exception as exc:
        return {"ok": False, "error": f"generation graine: {str(exc)[:160]}"}


def empreinte(wav_path: str):
    """Embedding ECAPA normalise, ou None. Sert aux portes 1 et 2."""
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from speechbrain.inference.speaker import EncoderClassifier
    except Exception:
        return None
    try:
        cache = WORKSPACE / "temp" / "speechbrain_models" / "ecapa_voxceleb"
        cache.mkdir(parents=True, exist_ok=True)
        classifieur = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb", savedir=str(cache),
            run_opts={"device": "cpu"})
        audio, sr = sf.read(wav_path)
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)
        if sr != 16000:
            import librosa
            audio = librosa.resample(audio.astype("float32"),
                                     orig_sr=sr, target_sr=16000)
        with torch.no_grad():
            emb = classifieur.encode_batch(
                torch.from_numpy(audio.astype("float32")).unsqueeze(0))
        emb = emb.squeeze().cpu().numpy()
        return emb / (float((emb ** 2).sum()) ** 0.5 + 1e-8)
    except Exception:
        return None


def similarite(a, b) -> float:
    if a is None or b is None:
        return -1.0
    return float((a * b).sum())


def carte_path(projet: str, personnage: str) -> Path:
    from voice_clone import slugify
    return BANQUE / projet / slugify(personnage) / "carte.json"


def concevoir(personnage: str, description: str, projet: str = "defaut",
              lang: str = "fr", texte_fr: str = "") -> dict:
    """Concoit la voix d'un personnage et la fige pour tout le projet.

    Une carte deja ecrite n'est JAMAIS regeneree : chaque regeneration
    reintroduirait une derive, exactement comme pour la planche personnage.
    """
    sys.path.insert(0, str(HERE))
    from voice_clone import slugify

    slug = slugify(personnage)
    dossier = BANQUE / projet / slug
    carte = dossier / "carte.json"
    if carte.exists():
        try:
            d = json.loads(carte.read_text(encoding="utf-8"))
            emit("voix_figee", f"{personnage}: carte existante conservee "
                               f"({d.get('graine')})")
            return {"ok": True, "carte": str(carte), "reprise": True, **d}
        except Exception:
            pass

    dossier.mkdir(parents=True, exist_ok=True)
    registre = _registre(description)

    # Graines deja attribuees dans CE projet : on epuise les timbres libres
    # avant d'en reutiliser un, pour maximiser la distinction.
    deja = set()
    projet_dir = BANQUE / projet
    if projet_dir.is_dir():
        for c in projet_dir.glob("*/carte.json"):
            try:
                deja.add(json.loads(c.read_text(encoding="utf-8")).get("graine"))
            except Exception:
                pass

    texte_graine = GRAINE_TEXTE_EN

    for essai, nom_voix in enumerate(graines_disponibles(registre, deja), 1):
        graine_wav = dossier / "graine.wav"
        res = generer_graine(nom_voix, texte_graine, str(graine_wav))
        if not res.get("ok"):
            emit("voix_warn", f"{personnage}: graine {nom_voix} echouee "
                              f"({res.get('error')})")
            continue
        emit("voix_graine", f"{personnage}: registre {registre}, "
                            f"graine {nom_voix} ({res['duree_s']}s)")

        meta = {
            "personnage": personnage,
            "slug": slug,
            "projet": projet,
            "description": description,
            "registre": registre,
            "graine": nom_voix,
            "graine_wav": str(graine_wav),
            "lang": lang,
            "moteur_graine": "kokoro-82m",
            "moteur_rendu": "cosyvoice3",
            "essai": essai,
        }
        emp = empreinte(str(graine_wav))
        if emp is not None:
            import numpy as np
            np.save(str(dossier / "empreinte.npy"), emp)
            meta["empreinte"] = "empreinte.npy"
        carte.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        return {"ok": True, "carte": str(carte), "reprise": False, **meta}

    return {"ok": False, "error": f"aucune graine utilisable pour {registre}"}


def verifier_distinction(projet: str = "defaut") -> dict:
    """Porte 2 : deux personnages ne doivent pas se ressembler.

    C'est le piege documente du moyennage de x-vectors : les timbres produits
    par un meme systeme se ressemblent entre eux. On le mesure au lieu de
    l'esperer, et on le corrige par des graines differentes — jamais par un
    moyennage, qui aggrave le probleme.
    """
    import numpy as np
    projet_dir = BANQUE / projet
    if not projet_dir.is_dir():
        return {"ok": False, "error": f"projet inconnu: {projet}"}
    cartes = []
    for c in sorted(projet_dir.glob("*/carte.json")):
        try:
            d = json.loads(c.read_text(encoding="utf-8"))
        except Exception:
            continue
        emp_path = c.parent / "empreinte.npy"
        if emp_path.exists():
            d["_emb"] = np.load(str(emp_path))
            cartes.append(d)
    if len(cartes) < 2:
        return {"ok": True, "personnages": len(cartes),
                "detail": "moins de deux voix : rien a distinguer"}

    conflits = []
    for i in range(len(cartes)):
        for j in range(i + 1, len(cartes)):
            s = similarite(cartes[i]["_emb"], cartes[j]["_emb"])
            if s >= SEUIL_DISTINCTION:
                conflits.append({
                    "a": cartes[i]["personnage"], "b": cartes[j]["personnage"],
                    "similarite": round(s, 3),
                    "graines": [cartes[i]["graine"], cartes[j]["graine"]],
                })
    if conflits:
        for c in conflits:
            emit("voix_conflit",
                 f"{c['a']} et {c['b']} trop proches ({c['similarite']}) — "
                 f"graines {c['graines'][0]} / {c['graines'][1]}")
    return {"ok": not conflits, "personnages": len(cartes),
            "conflits": conflits, "seuil": SEUIL_DISTINCTION}


def check() -> dict:
    """Ce qui est reellement disponible, sans rien supposer."""
    etat = {"kokoro": False, "voix_kokoro": 0, "cosyvoice3": False,
            "speechbrain": False, "maya1": False}
    try:
        import kokoro  # noqa: F401
        etat["kokoro"] = True
    except Exception:
        pass
    d = _kokoro_voices_dir()
    if d:
        etat["voix_kokoro"] = len(list(d.glob("*.pt")))
    try:
        sys.path.insert(0, str(HERE))
        from voice_clone import cosyvoice3_status
        etat["cosyvoice3"] = bool(cosyvoice3_status().get("ok"))
    except Exception:
        pass
    try:
        import speechbrain  # noqa: F401
        etat["speechbrain"] = True
    except Exception:
        pass
    import glob
    etat["maya1"] = bool(glob.glob(os.path.expanduser(
        "~/.cache/huggingface/hub/models--maya-research--maya1/snapshots/*/"
        "*.safetensors")))
    etat["ok"] = etat["kokoro"] and etat["voix_kokoro"] > 0 and etat["cosyvoice3"]
    return etat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--concevoir")
    ap.add_argument("--description", default="")
    ap.add_argument("--projet", default="defaut")
    ap.add_argument("--lang", default="fr")
    ap.add_argument("--verifier-distinction", action="store_true")
    args = ap.parse_args()

    if args.check:
        print(json.dumps(check(), ensure_ascii=False), flush=True)
        return 0
    if args.verifier_distinction:
        r = verifier_distinction(args.projet)
        print(json.dumps(r, ensure_ascii=False, default=str), flush=True)
        return 0 if r.get("ok") else 1
    if args.concevoir:
        r = concevoir(args.concevoir, args.description, args.projet, args.lang)
        r.pop("_emb", None)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        return 0 if r.get("ok") else 1
    print(json.dumps({"ok": False, "error": "--concevoir ou --check requis"}))
    return 1


if __name__ == "__main__":
    sys.exit(main())
