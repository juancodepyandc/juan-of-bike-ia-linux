#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Modèles de vision locaux (DINOv2, CLIP) chargés depuis le cache Hugging Face, sans réseau.

Pourquoi ce module (15/11/2026) : le chargement de CLIP échouait EN SILENCE — un jeton Hugging Face
expiré faisait tomber `from_pretrained` sur une erreur réseau avalée, et l'appelant continuait sans
modèle. Ici un modèle local se charge localement ou échoue bruyamment :
  - toujours `local_files_only=True` : aucun appel réseau, aucun jeton lu ;
  - un modèle absent lève `ModeleLocalAbsent` (une `RuntimeError`) qui NOMME le modèle manquant ;
  - `HF_HUB_OFFLINE` n'est jamais posé : ce serait global au processus et couperait les autres
    modules du pont qui, eux, ont le droit de télécharger.

Deux modèles :
  - `facebook/dinov2-base` (Apache-2.0) : empreinte d'identité visuelle (jeton CLS normalisé). Il
    sépare mieux deux personnages d'une même série que CLIP (mesuré le 15/11 : CLIP-B/32 donne 0,80
    à 0,85 entre Zig et Sharko, DINOv2 0,48 à 0,66), mais aucun seuil absolu ne tient : les
    appelants n'en font que des comparaisons RELATIVES ;
  - `openai/clip-vit-large-patch14` : rapprochement texte-image (« qui est la hyène, qui est le
    requin »). Repli sur `openai/clip-vit-base-patch32` SEULEMENT si le grand est absent du cache, et
    le repli est dit (stderr + `etat_modeles()`), jamais silencieux.

Mesuré sur ce poste le 15/11/2026 : le cache de CLIP-L/14 contient les poids et le tokenizer mais
PAS `preprocessor_config.json`. Ce fichier ne porte que la préparation d'image documentée d'OpenAI
(redimensionnement bicubique au plus petit côté, recadrage central, moyennes et écarts-types CLIP),
qui sont exactement les valeurs par défaut de `CLIPImageProcessor`. Le préprocesseur est alors
reconstruit à partir de `vision_config.image_size` du modèle lui-même, et la reconstruction est
notée dans `etat_modeles()` — le modèle n'est pas « absent » pour autant.

Appareil : CPU par défaut (le GPU de 16 Go est partagé avec FLUX/TRELLIS ; le poste a déjà gelé).
Les singletons sont paresseux : rien n'est importé ni chargé tant qu'on n'encode rien. Les fonctions
d'encodage acceptent un `bundle` injecté pour que les tests n'aient besoin d'aucun poids.
"""
from __future__ import annotations

import contextlib
import sys
import threading
from typing import Any, Callable, Sequence

import numpy as np

DINOV2 = "facebook/dinov2-base"
CLIP_PREFERE = "openai/clip-vit-large-patch14"
CLIP_REPLI = "openai/clip-vit-base-patch32"
APPAREIL_PAR_DEFAUT = "cpu"

_verrou = threading.Lock()
_singletons: dict[str, dict[str, Any]] = {}
_notes: list[str] = []


class ModeleLocalAbsent(RuntimeError):
    """Un modèle demandé n'est pas dans le cache local (ou n'y est pas lisible) : le message le nomme."""


def _dire(message: str) -> None:
    """Trace sur stderr : la sortie standard des CLI appelantes reste réservée à leur ligne JSON."""
    print(f"[modeles_locaux] {message}", file=sys.stderr, flush=True)


def _absent(nom: str, exc: BaseException) -> ModeleLocalAbsent:
    detail = f"{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}"
    return ModeleLocalAbsent(
        f"modèle local absent du cache Hugging Face : {nom} (chargement local_files_only refusé — {detail}). "
        f"Le télécharger une fois (huggingface-cli download {nom}) ; aucun repli silencieux n'est fait.")


def _illisible(nom: str, exc: BaseException) -> RuntimeError:
    return RuntimeError(f"modèle local illisible : {nom} ({type(exc).__name__}: {str(exc)[:200]})")


def _importer_transformers(nom: str):
    try:
        import transformers  # noqa: F401
        return transformers
    except Exception as exc:  # noqa: BLE001 — sans transformers, AUCUN modèle local n'est chargeable
        raise RuntimeError(f"transformers indisponible : impossible de charger {nom} ({type(exc).__name__}: {exc})") from exc


def charger_dinov2_depuis_cache(nom: str = DINOV2, appareil: str = APPAREIL_PAR_DEFAUT) -> dict[str, Any]:
    """Charge DINOv2 (processeur + modèle) depuis le cache local, sans singleton. Lève si absent."""
    transformers = _importer_transformers(nom)
    try:
        processeur = transformers.AutoImageProcessor.from_pretrained(nom, local_files_only=True)
        modele = transformers.AutoModel.from_pretrained(nom, local_files_only=True)
    except OSError as exc:  # fichier introuvable dans le cache : c'est l'absence, dite comme telle
        raise _absent(nom, exc) from exc
    except Exception as exc:  # noqa: BLE001 — présent mais cassé : on le dit aussi, autrement
        raise _illisible(nom, exc) from exc
    modele.eval()
    modele.to(appareil)
    return {"nom": nom, "appareil": appareil, "processeur": processeur, "modele": modele, "notes": []}


def charger_clip_depuis_cache(nom: str, appareil: str = APPAREIL_PAR_DEFAUT) -> dict[str, Any]:
    """Charge un CLIP (modèle + tokenizer + préparation d'image) depuis le cache local, sans singleton.

    Le modèle et le tokenizer sont obligatoires : leur absence lève `ModeleLocalAbsent`. La seule
    préparation d'image manquante est reconstruite depuis la configuration du modèle (voir l'en-tête).
    """
    transformers = _importer_transformers(nom)
    try:
        modele = transformers.CLIPModel.from_pretrained(nom, local_files_only=True)
        try:
            tokenizer = transformers.CLIPTokenizerFast.from_pretrained(nom, local_files_only=True)
        except OSError:
            tokenizer = transformers.CLIPTokenizer.from_pretrained(nom, local_files_only=True)
    except OSError as exc:
        raise _absent(nom, exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise _illisible(nom, exc) from exc
    notes: list[str] = []
    try:
        preparation = transformers.CLIPImageProcessor.from_pretrained(nom, local_files_only=True)
    except OSError:
        taille = int(getattr(modele.config.vision_config, "image_size", 224))
        preparation = transformers.CLIPImageProcessor(
            size={"shortest_edge": taille}, crop_size={"height": taille, "width": taille})
        notes.append(f"{nom} : preprocessor_config.json absent du cache — préparation d'image reconstruite "
                     f"depuis vision_config.image_size={taille} et la normalisation CLIP par défaut")
    modele.eval()
    modele.to(appareil)
    return {"nom": nom, "appareil": appareil, "modele": modele, "tokenizer": tokenizer,
            "preparation": preparation, "notes": notes}


def premier_clip_disponible(candidats: Sequence[str], appareil: str,
                            charger: Callable[[str, str], dict[str, Any]] = charger_clip_depuis_cache
                            ) -> dict[str, Any]:
    """Le premier CLIP du cache dans l'ordre de préférence ; tout repli est noté dans le bundle.

    On ne passe au suivant que sur une ABSENCE (`ModeleLocalAbsent`). Un modèle présent mais illisible
    lève tout de suite : un repli masquerait une panne réelle du cache.
    """
    absences: list[str] = []
    for position, nom in enumerate(candidats):
        try:
            bundle = charger(nom, appareil)
        except ModeleLocalAbsent as exc:
            absences.append(str(exc))
            continue
        if position > 0:
            note = f"{candidats[0]} absent du cache : repli sur {nom} (moins précis)"
            bundle.setdefault("notes", []).append(note)
            _dire(note)
        return bundle
    raise ModeleLocalAbsent("aucun CLIP local disponible — " + " | ".join(absences))


def _singleton(cle: str, fabrique: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    with _verrou:
        bundle = _singletons.get(cle)
        if bundle is None:
            bundle = fabrique()
            _singletons[cle] = bundle
            for note in bundle.get("notes", []):
                if note not in _notes:
                    _notes.append(note)
        return bundle


def charger_dinov2(appareil: str | None = None) -> dict[str, Any]:
    """Singleton paresseux de DINOv2-base sur l'appareil demandé (CPU par défaut)."""
    appareil = appareil or APPAREIL_PAR_DEFAUT
    return _singleton(f"dinov2:{appareil}", lambda: charger_dinov2_depuis_cache(DINOV2, appareil))


def charger_clip(appareil: str | None = None) -> dict[str, Any]:
    """Singleton paresseux de CLIP-L/14 (repli B/32 seulement si L/14 est absent, et dit)."""
    appareil = appareil or APPAREIL_PAR_DEFAUT
    return _singleton(f"clip:{appareil}",
                      lambda: premier_clip_disponible((CLIP_PREFERE, CLIP_REPLI), appareil))


def etat_modeles() -> dict[str, Any]:
    """Ce qui est chargé, sur quel appareil, et chaque écart à la configuration voulue (repli, reconstruction)."""
    with _verrou:
        return {
            "charges": {cle: {"nom": b.get("nom"), "appareil": b.get("appareil")} for cle, b in _singletons.items()},
            "notes": list(_notes),
        }


def liberer() -> None:
    """Rend la mémoire des modèles chargés (≈ 2 Go pour CLIP-L + DINOv2 en float32 sur CPU)."""
    with _verrou:
        _singletons.clear()
    import gc
    gc.collect()


def _vers_rgb(image) -> Any:
    """Image PIL en RGB ; la transparence est posée sur BLANC.

    `convert("RGB")` sur une découpe RGBA rendrait la couleur cachée sous l'alpha nul (souvent le fond
    d'origine ou du noir) : l'encodeur verrait le décor que le détourage venait de retirer.
    """
    from PIL import Image

    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        fond = Image.new("RGB", rgba.size, (255, 255, 255))
        fond.paste(rgba, mask=rgba.getchannel("A"))
        return fond
    return image.convert("RGB")


def _vers_numpy(valeur) -> np.ndarray:
    if hasattr(valeur, "detach"):
        return valeur.detach().float().cpu().numpy()
    return np.asarray(valeur, dtype=np.float32)


def _sans_gradient():
    try:
        import torch
        return torch.inference_mode()
    except Exception:  # noqa: BLE001 — bundle factice des tests, sans torch
        return contextlib.nullcontext()


def _sur_appareil(entrees, appareil: str):
    if appareil and appareil != "cpu" and hasattr(entrees, "to"):
        return entrees.to(appareil)
    return entrees


def _normaliser_l2(matrice: np.ndarray) -> np.ndarray:
    normes = np.linalg.norm(matrice, axis=1, keepdims=True)
    return (matrice / np.maximum(normes, 1e-12)).astype(np.float32)


def embed_images(images: Sequence[Any], *, appareil: str | None = None, lot: int = 8,
                 bundle: dict[str, Any] | None = None) -> np.ndarray:
    """Empreintes DINOv2 (jeton CLS, normalisé L2) des images, forme (n, d), float32.

    Le CLS de `last_hidden_state` est déjà passé par la normalisation finale du modèle (c'est aussi le
    `pooler_output` de transformers). Les similarités entre empreintes sont donc des cosinus directs.
    """
    if not images:
        return np.zeros((0, 0), dtype=np.float32)
    b = bundle or charger_dinov2(appareil)
    dev = b.get("appareil") or APPAREIL_PAR_DEFAUT
    sorties: list[np.ndarray] = []
    with _sans_gradient():
        for debut in range(0, len(images), max(1, lot)):
            paquet = [_vers_rgb(im) for im in images[debut:debut + max(1, lot)]]
            entrees = _sur_appareil(b["processeur"](images=paquet, return_tensors="pt"), dev)
            sortie = b["modele"](**entrees)
            sorties.append(_vers_numpy(sortie.last_hidden_state[:, 0]))
    return _normaliser_l2(np.concatenate(sorties, axis=0))


def clip_text_image_scores(images: Sequence[Any], textes: Sequence[str], *, appareil: str | None = None,
                           lot: int = 8, bundle: dict[str, Any] | None = None) -> np.ndarray:
    """Scores CLIP image-texte, forme (n_images, n_textes) : les `logits_per_image` du modèle.

    Score = cosinus(image, texte) × échelle apprise par CLIP (`exp(logit_scale)`, ≈ 100). Une
    différence de scores est donc un log-rapport de vraisemblance : l'appelant peut exiger qu'un
    texte soit « au moins deux fois plus probable » que le suivant sans aucun seuil absolu.
    """
    if not images or not textes:
        return np.zeros((len(images), len(textes)), dtype=np.float32)
    b = bundle or charger_clip(appareil)
    dev = b.get("appareil") or APPAREIL_PAR_DEFAUT
    modele = b["modele"]
    with _sans_gradient():
        jetons = _sur_appareil(b["tokenizer"](list(textes), padding=True, truncation=True, return_tensors="pt"), dev)
        textes_emb = _normaliser_l2(_vers_numpy(modele.get_text_features(**jetons)))
        images_emb: list[np.ndarray] = []
        for debut in range(0, len(images), max(1, lot)):
            paquet = [_vers_rgb(im) for im in images[debut:debut + max(1, lot)]]
            entrees = _sur_appareil(b["preparation"](images=paquet, return_tensors="pt"), dev)
            images_emb.append(_vers_numpy(modele.get_image_features(**entrees)))
        echelle = float(np.exp(_vers_numpy(modele.logit_scale)).reshape(-1)[0])
    return (echelle * (_normaliser_l2(np.concatenate(images_emb, axis=0)) @ textes_emb.T)).astype(np.float32)
