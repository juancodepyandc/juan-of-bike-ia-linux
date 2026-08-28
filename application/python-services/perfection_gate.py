#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""perfection_gate — le PIPELINE juge la livraison, pas un humain.

Doctrine (25/07, verbatim utilisateur): « c'est à mon IA de dire s'il est
parfait ou non sinon il refait » ; « pas de trou ou de défaut que l'image n'a
pas ». Cette porte tourne dans le chemin partagé (UI/Tunnel/CLI) juste avant
la livraison:

  1. TROUS: audit des bords ouverts (trimesh) + rebouchage Blender
     (fill_holes) si necessaire; re-audit apres.
  2. ORIENTATION: verifiee en ESPACE glTF BRUT (jamais via un aller-retour
     Blender qui annule l'erreur — cause racine du « à l'envers »); debout =
     hauteur sur Y; face = jugee par VLM sur projections brutes +Z/-Z;
     correction ecrite DIRECTEMENT dans les buffers de sommets.
  3. GOUTTIERES: dilatation d'atlas (mouchetures).
  4. JUGE FINAL: rendus textures multi-vues compares a la REFERENCE par le
     VLM — liste des defauts que l'image n'a pas; parfait=false => la
     livraison est REFUSEE (le pipeline relance, jamais de livraison trompeuse).

Sortie: {parfait: bool, reparations: [...], defauts: [...], score: int}
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PS = Path(__file__).resolve().parent


def _blender() -> str:
    import shutil
    return shutil.which("blender") or "blender"


# ---------------------------------------------------------------- trous ----
def _signature_texture(glb: str):
    """Signature de la couleur livree: luminance + rapport de striure.

    Le rapport compare les ecarts VERTICAUX aux ecarts HORIZONTAUX. Une texture
    saine est isotrope (~1.0); un remplissage qui bave le long des lignes le
    fait exploser. C'est la mesure qui a permis de nommer le coupable quand la
    texture du personnage VIZION est sortie en trainees (0.97 -> 8.95).
    """
    import io as _io
    import numpy as _np
    from PIL import Image as _Im
    from pygltflib import GLTF2 as _G
    g = _G().load(glb)
    blob = g.binary_blob()
    pbr = getattr(g.materials[0], "pbrMetallicRoughness", None) if g.materials else None
    if pbr is None or pbr.baseColorTexture is None:
        return None
    src = g.textures[pbr.baseColorTexture.index].source
    if src is None or g.images[src].bufferView is None:
        return None
    bv = g.bufferViews[g.images[src].bufferView]
    a = _np.asarray(_Im.open(_io.BytesIO(
        blob[bv.byteOffset:bv.byteOffset + bv.byteLength])).convert("RGB"),
        dtype=_np.float32)
    dv = float(_np.abs(_np.diff(a, axis=0)).mean())
    dh = float(_np.abs(_np.diff(a, axis=1)).mean())
    return {"luma": float(a.mean()), "striure": dv / max(dh, 1e-6)}


def _reparation_texture_sure(glb: str, reparer, etiquette: str):
    """Applique `reparer(entree, sortie)` seulement si elle PROUVE qu'elle n'a
    pas abime la couleur livree.

    Doctrine deja etablie ailleurs dans ce depot pour la geometrie: une etape
    doit prouver qu'elle n'a rien detruit. Paye ici: le despeckle d'atlas,
    ecrit pour des atlas TRELLIS degeneres (des milliers de micro-chartes
    ecrasees sur UN texel), a ete applique tel quel a un atlas de service
    legitimement fragmente — 276 927 ilots sur 567 523 (48%) declares
    "parasites" puis relocalises, texture rendue en trainees horizontales et
    logo VIZION efface. Rendu (ok, detail).
    """
    import shutil as _sh
    import tempfile as _tf
    avant = _signature_texture(glb)
    if avant is None:                       # pas de couleur a proteger
        return reparer(glb, glb), "sans texture a proteger"
    tmp = _tf.mktemp(suffix=".glb")
    try:
        res = reparer(glb, tmp)
        if not os.path.isfile(tmp) or os.path.getsize(tmp) < 1000:
            return res, "sortie vide — ignoree"
        apres = _signature_texture(tmp)
        if apres is None:
            return res, "texture perdue — ignoree"
        # seuils larges: on ne veut attraper que la DESTRUCTION, pas un
        # nettoyage legitime (qui laisse la striure autour de 1).
        _seuil = max(1.8, 2.5 * float(avant["striure"]))
        if apres["striure"] > _seuil:
            return res, ("REFUSEE: striure %.2f -> %.2f (le remplissage bave, "
                         "couleur d'origine conservee)"
                         % (avant["striure"], apres["striure"]))
        _sh.copyfile(tmp, glb)
        return res, "appliquee (striure %.2f -> %.2f)" % (avant["striure"],
                                                          apres["striure"])
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _fond_lisible(glb: str) -> str:
    """Force du fond pour que le SUJET se detache au rendu de controle.

    Un sujet noir sur fond gris sombre est illisible: le juge a condamne a
    0/100 une chaise de bureau noire pourtant conforme, faute de la voir
    (28/08). On mesure la luminance de la couleur livree et on prend le fond
    inverse — sombre pour un sujet clair, clair pour un sujet sombre.
    """
    try:
        sig = _signature_texture(glb)
        if not sig:
            return "3.0"
        luma = float(sig.get("luma") or 0.0)
        if luma < 60:      # sujet sombre -> fond clair
            return "8.0"
        if luma > 190:     # sujet tres clair -> fond assombri
            return "1.2"
        return "3.0"
    except Exception:  # noqa: BLE001
        return "3.0"


def audit_trous(glb: str) -> dict:
    """Audit APRES SOUDURE virtuelle: sur un maillage a ilots UV, chaque
    couture compte comme bord ouvert (des millions de faux positifs — le
    rebouchage aveugle prenait 30 min pour rien). Les VRAIS trous sont les
    frontieres qui subsistent une fois les doublons de position fusionnes."""
    import numpy as np
    import trimesh
    sc = trimesh.load(glb, force="mesh", process=False)
    v = np.asarray(sc.vertices)
    f = np.asarray(sc.faces)
    # soudure virtuelle: grille 0.4 mm relative a la taille du sujet
    taille = float(np.linalg.norm(v.max(0) - v.min(0))) or 1.0
    grille = np.round(v / (taille * 4e-4)).astype(np.int64)
    _, inv = np.unique(grille, axis=0, return_inverse=True)
    fs = inv[f]
    fs = fs[(fs[:, 0] != fs[:, 1]) & (fs[:, 1] != fs[:, 2]) & (fs[:, 0] != fs[:, 2])]
    e = np.sort(np.concatenate([fs[:, (0, 1)], fs[:, (1, 2)], fs[:, (0, 2)]]), axis=1)
    _, c = np.unique(e, axis=0, return_counts=True)
    bords = int((c == 1).sum())
    return {"bords_ouverts": bords, "etanche": bords == 0}


def reboucher(glb: str, cotes_max: int = 64) -> dict:
    script = (
        "import bpy, sys\n"
        "glb = sys.argv[-1]\n"
        "bpy.ops.wm.read_factory_settings(use_empty=True)\n"
        "bpy.ops.import_scene.gltf(filepath=glb)\n"
        "for o in list(bpy.context.scene.objects):\n"
        "    if o.type != 'MESH':\n"
        "        continue\n"
        "    bpy.ops.object.select_all(action='DESELECT')\n"
        "    o.select_set(True)\n"
        "    bpy.context.view_layer.objects.active = o\n"
        "    bpy.ops.object.mode_set(mode='EDIT')\n"
        "    bpy.ops.mesh.select_all(action='SELECT')\n"
        "    bpy.ops.mesh.remove_doubles(threshold=0.0004)\n"
        "    bpy.ops.mesh.fill_holes(sides=%d)\n"
        "    bpy.ops.object.mode_set(mode='OBJECT')\n"
        "bpy.ops.object.select_all(action='SELECT')\n"
        "bpy.ops.export_scene.gltf(filepath=glb, export_animations=True,\n"
        "                          export_animation_mode='ACTIONS')\n"
        "print('REBOUCHE_OK')\n" % cotes_max)
    r = subprocess.run([_blender(), "-b", "--python-expr", script, "--", glb],
                       capture_output=True, text=True, timeout=1800)
    return {"ok": "REBOUCHE_OK" in (r.stdout or "")}


# ---------------------------------------------------------- orientation ----
def _projection_brute(glb: str, sortie: str, azimuts=(0, 180)) -> bool:
    """Projections matplotlib de la geometrie BRUTE (espace du viewer)."""
    try:
        import numpy as np
        import trimesh
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.collections import PolyCollection
        m = trimesh.load(glb, force="mesh", process=False)
        v = np.asarray(m.vertices)
        f = np.asarray(m.faces)
        rng = np.random.default_rng(7)
        idx = rng.choice(len(f), min(120000, len(f)), replace=False)
        fig, axes = plt.subplots(1, len(azimuts), figsize=(5.5 * len(azimuts), 5.5))
        if len(azimuts) == 1:
            axes = [axes]
        for ax, az in zip(axes, azimuts):
            th = np.radians(az)
            Rm = np.array([[np.cos(th), 0, np.sin(th)], [0, 1, 0],
                           [-np.sin(th), 0, np.cos(th)]])
            vv = v @ Rm.T
            tris = vv[f[idx]]
            ordre = np.argsort(tris[:, :, 2].mean(axis=1))
            tris = tris[ordre]
            n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
            nz = n[:, 2] / (np.linalg.norm(n, axis=1) + 1e-9)
            pc = PolyCollection(tris[:, :, (0, 1)],
                                facecolors=plt.cm.gray(np.clip(0.25 + 0.75 * np.abs(nz), 0, 1)),
                                edgecolors="none")
            ax.add_collection(pc)
            ax.autoscale()
            ax.set_aspect("equal")
            ax.axis("off")
        plt.tight_layout()
        plt.savefig(sortie, dpi=75)
        plt.close(fig)
        return True
    except Exception:  # noqa: BLE001
        return False


def _tourner_buffers(glb: str, yaw_deg: float) -> bool:
    """Rotation autour de Y (lacet) ecrite dans les buffers. Zero Blender."""
    import numpy as np
    from pygltflib import GLTF2
    g = GLTF2().load(glb)
    blob = bytearray(g.binary_blob())
    th = np.radians(yaw_deg)
    Rm = np.array([[np.cos(th), 0, np.sin(th)], [0, 1, 0],
                   [-np.sin(th), 0, np.cos(th)]], dtype=np.float64)
    vus = set()
    for mesh in g.meshes:
        for prim in mesh.primitives:
            for nom in ("POSITION", "NORMAL"):
                idx = getattr(prim.attributes, nom)
                if idx is None or idx in vus:
                    continue
                vus.add(idx)
                acc = g.accessors[idx]
                bv = g.bufferViews[acc.bufferView]
                off = (bv.byteOffset or 0) + (acc.byteOffset or 0)
                a = np.frombuffer(blob, dtype=np.float32, count=acc.count * 3,
                                  offset=off).reshape(-1, 3).astype(np.float64)
                a = a @ Rm.T
                if nom == "POSITION":
                    acc.min = [float(x) for x in a.min(0)]
                    acc.max = [float(x) for x in a.max(0)]
                blob[off:off + acc.count * 12] = a.astype(np.float32).tobytes()
    g.set_binary_blob(bytes(blob))
    g.save(glb)
    return True


def tourner_buffers_z(glb: str, roll_deg: float) -> bool:
    """Rotation dans le PLAN IMAGE (axe Z viewer), ecrite dans les buffers.

    Etape 6 du plan toutes-poses (01/08): apres un redressement 2D de la
    reference, le modele reconstruit est debout — cette rotation inverse le
    remet dans la pose REELLE de la photo. UN seul ecrivain glTF (ici),
    jamais un aller-retour Blender (piege des conventions verticales).
    """
    import numpy as np
    from pygltflib import GLTF2
    g = GLTF2().load(glb)
    blob = bytearray(g.binary_blob())
    th = np.radians(roll_deg)
    Rm = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0],
                   [0, 0, 1]], dtype=np.float64)
    vus = set()
    for mesh in g.meshes:
        for prim in mesh.primitives:
            for nom in ("POSITION", "NORMAL"):
                idx = getattr(prim.attributes, nom)
                if idx is None or idx in vus:
                    continue
                vus.add(idx)
                acc = g.accessors[idx]
                bv = g.bufferViews[acc.bufferView]
                off = (bv.byteOffset or 0) + (acc.byteOffset or 0)
                a = np.frombuffer(blob, dtype=np.float32, count=acc.count * 3,
                                  offset=off).reshape(-1, 3).astype(np.float64)
                a = a @ Rm.T
                if nom == "POSITION":
                    acc.min = [float(x) for x in a.min(0)]
                    acc.max = [float(x) for x in a.max(0)]
                blob[off:off + acc.count * 12] = a.astype(np.float32).tobytes()
    g.set_binary_blob(bytes(blob))
    g.save(glb)
    return True


def orienter_face_viewer(glb: str) -> dict:
    """Face vers +Z (la camera du viewer), jugee sur projections BRUTES."""
    sys.path.insert(0, str(PS))
    from vlm_judge import ask_vlm
    with tempfile.TemporaryDirectory() as td:
        azs = (0, 90, 180, 270)
        img = os.path.join(td, "brut.png")
        if not _projection_brute(glb, img, azimuts=azs):
            return {"ok": False, "error": "projection brute indisponible"}
        try:
            verdict = ask_vlm(
                [img],
                "4 projections du MEME sujet 3D (rotations de 90 deg). "
                "Laquelle (1 a 4, de gauche a droite) montre la FACE du sujet "
                "(yeux/visage/avant) tournee vers nous ? Reponds l'index.",
                schema_hint='{"vue_face": 1|2|3|4}', timeout=120)
            iv = int(verdict.get("vue_face"))
            assert iv in (1, 2, 3, 4)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": "VLM: %r" % (exc,)}
        yaw = (-azs[iv - 1]) % 360
        if yaw:
            _tourner_buffers(glb, float(yaw))
        return {"ok": True, "vue_face": iv, "yaw": yaw}


# ---------------------------------------------------- coherence (anime) ----
def verifier_coherence(glb: str) -> dict:
    """Verification STRUCTURELLE d'un maillage ANIME, SANS comparaison a la
    reference photo: une pose de marche/geste ne ressemble jamais a un
    portrait immobile (deja paye ailleurs sous "bras fondus"/"penche" —
    aurora_3d_pipeline separe le livrable statique du fichier anime pour
    cette raison). Le VLM reste juge (seul un oeil detecte un rig qui
    dechire/fusionne la geometrie), mais SEULEMENT sur des defauts
    POSE-INDEPENDANTS (trous, sujet eclate/dechire, taches) — jamais
    "morceaux_manquants" ni "conforme_demande", qui confondent une pose de
    mouvement avec un defaut (mesure: bras replies en marchant = "manquant").
    """
    sys.path.insert(0, str(PS))
    from vlm_judge import ask_vlm
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([_blender(), "-b", "-P",
                            str(PS / "orient_rendu_bpy.py"), "--", glb, td,
                            _fond_lisible(glb)],
                           capture_output=True, text=True, timeout=1200)
        if "VUES4_OK" not in (r.stdout or ""):
            return {"parfait": False, "score": 0,
                    "defauts": ["rendu de controle impossible"]}
        vues = [os.path.join(td, "az%03d.png" % a) for a in (270, 0, 90, 180)]
        try:
            import numpy as _np
            from PIL import Image as _Im
            _fracs = [float((_np.asarray(_Im.open(_v).convert("L")) > 28).mean())
                     for _v in vues]
            _fmax = max(_fracs)
        except Exception:  # noqa: BLE001
            return {"parfait": False, "score": 0,
                    "defauts": ["lecture des rendus impossible"]}
        if _fmax < 0.08:
            return {"parfait": False, "score": 0,
                    "defauts": ["rendu illisible (sujet %.1f%% du cadre: "
                                "debris/eclats probables)" % (100 * _fmax)]}
        votes = []
        for _tour in range(3):
            try:
                v = ask_vlm(
                    vues,
                    "4 vues d'un modele 3D ANIME (une pose de MOUVEMENT, pas "
                    "une pose debout figee — IGNORE la pose elle-meme, "
                    "juge seulement l'integrite du maillage). Reponds "
                    "STRICTEMENT en JSON par OUI/NON factuels:\n"
                    "- trous: des perforations/manques DANS la surface du "
                    "sujet (pas le fond) ?\n"
                    "- eclate: le sujet est DECHIRE/EN LAMBEAUX — des bouts "
                    "de surface qui se detachent, des pointes/lanieres "
                    "qui ne devraient pas exister (PAS juste un membre "
                    "replie ou cache par la pose) ?\n"
                    "- taches: mouchetures ou taches sombres/noires "
                    "parasites bien visibles sur la surface ?\n"
                    'JSON strict: {"trous": true|false, "eclate": '
                    'true|false, "taches": true|false}',
                    schema_hint='{"trous": true|false, "eclate": true|false,'
                               ' "taches": true|false}',
                    timeout=180)
                if isinstance(v, dict):
                    votes.append(v)
            except Exception:  # noqa: BLE001
                continue
        if len(votes) < 2:
            return {"parfait": False, "score": 0,
                    "defauts": ["juge indisponible (%d/3 votes)" % len(votes)]}

        def _maj(cle):
            return sum(1 for v in votes if v.get(cle)) * 2 > len(votes)

        defauts = [d for d, actif in (
            ("trous dans la surface (rig)", _maj("trous")),
            ("sujet dechire/eclate (rig)", _maj("eclate")),
            ("taches/mouchetures (rig)", _maj("taches")),
        ) if actif]
        return {"parfait": not defauts, "score": (0 if defauts else 100),
                "defauts": defauts, "votes": len(votes)}


def porte_structure(glb: str) -> dict:
    """Porte pour le fichier ANIME (rigged): repare (trous, orientation,
    gouttieres) puis verifie la coherence structurelle — jamais une
    comparaison de pose a une photo fixe (methode invalide pour un mouvement,
    cf. verifier_coherence)."""
    reparations = []
    print("PORTE: audit des trous (anime)...", flush=True)
    t0 = audit_trous(glb)
    if t0.get("bords_ouverts", 0) > 200:
        if reboucher(glb).get("ok"):
            t1 = audit_trous(glb)
            reparations.append("trous: %s -> %s bords ouverts"
                               % (t0.get("bords_ouverts"), t1.get("bords_ouverts")))
    print("PORTE: orientation espace brut (anime)...", flush=True)
    o = orienter_face_viewer(glb)
    if o.get("ok") and o.get("yaw"):
        reparations.append("orientation: yaw %s applique (buffers)" % o["yaw"])
    try:
        from texture_despeckle_atlas import despeckle_glb as _dspk_atlas
        dsp, _verdict = _reparation_texture_sure(
            glb, lambda _e, _s: _dspk_atlas(_e, _s), "despeckle_atlas")
        if dsp.get("ok") and dsp.get("islands_purged"):
            reparations.append("%d ilot(s) parasite(s) — %s"
                               % (dsp["islands_purged"], _verdict))
    except Exception:  # noqa: BLE001
        pass
    try:
        from atlas_dilate import dilater
        d = dilater(glb)
        if d.get("ok"):
            reparations.append("gouttieres atlas dilatees")
    except Exception:  # noqa: BLE001
        pass
    try:
        _run = Path(glb).parent
        if _run.name in ("modele", "mouvement", "models", "travail"):
            _run = _run.parent
        verdict_preuves = preuves(glb, str(_run), Path(glb).stem[-40:])
        reparations.append("preuves ecrites: journal/verifications (%s)"
                           % json.dumps({k: verdict_preuves.get(k) for k in
                                         ("faces", "ilots", "ombrage_lisse")}))
    except Exception:  # noqa: BLE001
        pass
    print("PORTE: coherence structurelle (anime)...", flush=True)
    verdict = verifier_coherence(glb)
    verdict["reparations"] = reparations
    return verdict


# --------------------------------------------------------------- juge ------
def juger(glb: str, reference: str, contexte: str = "") -> dict:
    """Rendus textures multi-vues vs REFERENCE: liste des defauts que l'image
    n'a pas. parfait=false -> le pipeline REFUSE la livraison et refait."""
    sys.path.insert(0, str(PS))
    from vlm_judge import ask_vlm
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([_blender(), "-b", "-P",
                            str(PS / "orient_rendu_bpy.py"), "--", glb, td,
                            _fond_lisible(glb)],
                           capture_output=True, text=True, timeout=1200)
        if "VUES4_OK" not in (r.stdout or ""):
            return {"parfait": False, "score": 0,
                    "defauts": ["rendu de controle impossible"]}
        vues = [os.path.join(td, "az%03d.png" % a) for a in (270, 0, 90, 180)]
        # PRE-CONTROLE DE LISIBILITE: un modele en debris eparpille une boite
        # enorme -> sujet minuscule et sombre dans le cadre, et le VLM surnote
        # ce qu'il ne voit pas (85/100 attribue a un fragment noir, verifie).
        # Illisible = refus direct, sans VLM.
        try:
            import numpy as _np
            from PIL import Image as _Im
            _fracs = []
            for _v in vues:
                _a = _np.asarray(_Im.open(_v).convert("L"))
                _fracs.append(float((_a > 28).mean()))
            _fmax = max(_fracs)
            if _fmax < 0.08:
                return {"parfait": False, "score": 0,
                        "defauts": ["rendu illisible (sujet %.1f%% du cadre: "
                                    "debris/eclats probables)" % (100 * _fmax)]}
        except Exception:  # noqa: BLE001
            pass
        votes = []
        for _tour in range(3):
            try:
                v = ask_vlm(
                    [reference] + vues,
                    "Image 1 = REFERENCE. Images 2-5 = un modele 3D "
                    "reconstruit, 4 angles. Reponds STRICTEMENT en JSON par "
                    "OUI/NON factuels (ignore le style de rendu et "
                    "l'eclairage):\n"
                    "- trous: des perforations/manques DANS la surface du "
                    "sujet (pas le fond) ?\n"
                    "- morceaux_manquants: un membre/partie du sujet absent "
                    "ou fondu par rapport a la reference ?\n"
                    "- eclate: le sujet est en fragments/debris ?\n"
                    "- taches: mouchetures ou taches sombres parasites bien "
                    "visibles sur la surface ?\n"
                    "- conforme_demande: le modele correspond-il a la "
                    "DEMANDE ecrite ci-dessous ? (un fragment, une piece "
                    "isolee ou un sujet different = false)\n"
                    "- score: fidelite globale 0-100 a la reference "
                    "(silhouette, couleurs, details).\n"
                    "DEMANDE DE L'UTILISATEUR: " + (contexte or "(non fournie)"),
                    schema_hint='{"trous": true|false, '
                                '"morceaux_manquants": true|false, '
                                '"eclate": true|false, "taches": true|false, '
                                '"conforme_demande": true|false, "score": 0}',
                    timeout=180)
                if isinstance(v, dict) and "score" in v:
                    votes.append(v)
            except Exception:  # noqa: BLE001
                continue
        if len(votes) < 2:
            # un juge muet ne valide RIEN (polarite refus — deja payee)
            return {"parfait": False, "score": 0,
                    "defauts": ["juge indisponible (%d/3 votes)" % len(votes)]}

        def _maj(cle):
            return sum(1 for v in votes if v.get(cle)) * 2 > len(votes)

        _scores = sorted(int(v.get("score") or 0) for v in votes)
        _median = _scores[len(_scores) // 2]
        defauts = [d for d, actif in (
            ("trous dans la surface", _maj("trous")),
            ("morceaux manquants/fondus", _maj("morceaux_manquants")),
            ("sujet eclate", _maj("eclate")),
            ("taches/mouchetures", _maj("taches")),
        ) if actif]
        _non_conforme = sum(1 for v in votes
                            if v.get("conforme_demande") is False) * 2 > len(votes)
        if _non_conforme:
            defauts.append("ne correspond pas a la demande")
        critique = (_maj("trous") or _maj("morceaux_manquants")
                    or _maj("eclate") or _non_conforme)
        parfait = (not critique) and _median >= 75
        if not parfait and not defauts and _median < 75:
            defauts = ["fidelite insuffisante (score median %d < 75)" % _median]
        return {"parfait": parfait, "score": _median,
                "defauts": defauts, "votes": len(votes)}


def preuves(glb: str, dossier_run: str, etiquette: str = "livrable") -> dict:
    """Ecrit les PREUVES VISUELLES dans le run de l'utilisateur, pas ailleurs.

    Regle (rappelee le 27/07): tout test doit etre visible dans
    conversations/<run>/journal/verifications — l'utilisateur doit voir
    exactement ce que le systeme voit, sans aller chercher dans un dossier
    temporaire.
    """
    import shutil
    dest = Path(dossier_run) / "journal" / "verifications"
    dest.mkdir(parents=True, exist_ok=True)
    mesures = {"fichier": Path(glb).name}
    try:
        import numpy as _np
        import trimesh as _tm
        m = _tm.load(glb, force="mesh", process=False)
        v, f = len(m.vertices), len(m.faces)
        mesures.update({
            "sommets": v, "faces": f,
            "ratio_sommets_faces": round(v / max(f, 1), 2),
            "ilots": int(getattr(m, "body_count", -1)),
            "etendue_m": [round(float(x), 3) for x in (m.bounds[1] - m.bounds[0])],
        })
        # ratio > 2 = maillage eclate en triangles isoles (ombrage plat)
        mesures["ombrage_lisse"] = mesures["ratio_sommets_faces"] < 2.0
    except Exception as exc:  # noqa: BLE001
        mesures["erreur_mesure"] = repr(exc)
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([_blender(), "-b", "-P",
                            str(PS / "orient_rendu_bpy.py"), "--", glb, td,
                            _fond_lisible(glb)],
                           capture_output=True, text=True, timeout=1800)
        if "VUES4_OK" in (r.stdout or ""):
            for az in (270, 0, 90, 180):
                src = os.path.join(td, "az%03d.png" % az)
                if os.path.isfile(src):
                    shutil.copyfile(src, dest / ("%s_vue%03d.png" % (etiquette, az)))
            mesures["vues"] = 4
        else:
            mesures["vues"] = 0
    (dest / ("%s_mesures.json" % etiquette)).write_text(
        json.dumps(mesures, ensure_ascii=False, indent=1), encoding="utf-8")
    return mesures


def porte(glb: str, reference: str | None, contexte: str = "") -> dict:
    """Repare (trous, orientation, gouttieres) puis JUGE. Ne ment jamais."""
    reparations = []
    print("PORTE: audit des trous...", flush=True)
    t0 = audit_trous(glb)
    # seuil: quelques bords soudes residuels sont invisibles; un vrai trou
    # visible en compte des dizaines groupes.
    if t0.get("bords_ouverts", 0) > 200:
        if reboucher(glb).get("ok"):
            t1 = audit_trous(glb)
            reparations.append("trous: %s -> %s bords ouverts"
                               % (t0.get("bords_ouverts"), t1.get("bords_ouverts")))
    print("PORTE: orientation espace brut...", flush=True)
    o = orienter_face_viewer(glb)
    if o.get("ok") and o.get("yaw"):
        reparations.append("orientation: yaw %s applique (buffers)" % o["yaw"])
    try:
        # ILOTS PARASITES (mesure 06/08, Happy): sur un atlas a dizaines de
        # milliers d'ilots, les charts degeneres (< 1 texel d'aire) sont
        # ecrases par xatlas sur UN SEUL texel arbitraire — des milliers de
        # patchs 3D sans rapport echantillonnent alors la MEME couleur au
        # hasard (mouchetures). atlas_dilate ne corrige que les gouttieres
        # NOIRES; ceci est un defaut different (deja peint, mais au hasard),
        # deja outille (texture_despeckle_atlas.py) mais jamais branche ici.
        from texture_despeckle_atlas import despeckle_glb as _dspk_atlas
        dsp, _verdict = _reparation_texture_sure(
            glb, lambda _e, _s: _dspk_atlas(_e, _s), "despeckle_atlas")
        if dsp.get("ok") and dsp.get("islands_purged"):
            reparations.append("%d ilot(s) parasite(s) — %s"
                               % (dsp["islands_purged"], _verdict))
    except Exception:  # noqa: BLE001
        pass
    try:
        from atlas_dilate import dilater
        d = dilater(glb)
        if d.get("ok"):
            reparations.append("gouttieres atlas dilatees")
    except Exception:  # noqa: BLE001
        pass
    # PREUVES DANS LE RUN (jamais dans un dossier temporaire)
    try:
        _run = Path(glb).parent
        if _run.name in ("modele", "mouvement", "models", "travail"):
            _run = _run.parent
        verdict_preuves = preuves(glb, str(_run), Path(glb).stem[-40:])
        reparations.append("preuves ecrites: journal/verifications (%s)"
                           % json.dumps({k: verdict_preuves.get(k) for k in
                                         ("faces", "ilots", "ombrage_lisse")}))
    except Exception:  # noqa: BLE001
        pass
    print("PORTE: jugement final vs reference...", flush=True)
    verdict = (juger(glb, reference, contexte) if reference
               else {"parfait": False, "score": 0,
                     "defauts": ["reference absente: jugement impossible"]})
    verdict["reparations"] = reparations
    return verdict


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--reference", default=None)
    ap.add_argument("--contexte", default="")
    a = ap.parse_args()
    print(json.dumps(porte(a.glb, a.reference, a.contexte), ensure_ascii=False))
