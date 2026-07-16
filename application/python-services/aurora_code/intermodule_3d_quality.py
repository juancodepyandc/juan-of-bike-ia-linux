#!/usr/bin/env python3
"""Client 3D "qualite max" du module Code (WS15).

Le module Code consomme le module 3D COMME UN SERVICE (aucune modification du
module 3D) mais avec trois exigences que l'ancien client ne remplissait pas:

1. QUALITE MAX demandee au pipeline: ``multi_view=True`` (chemin MV-Adapter ->
   TRELLIS multi-vues, le chemin qualite verifie du projet) et
   ``purpose="product"`` (reglages hauts du worker: mnv=8, textures 1024).
2. INTELLIGENCE DE REPRISE: chaque GLB est note via ``/api/3d/mesh-score``;
   sous le seuil du scorer on tente ``/api/3d/auto-rescue`` puis un re-run
   force du pipeline, en gardant le MEILLEUR candidat — jusqu'au seuil ou
   epuisement du budget (borne honnete, pas de boucle infinie).
3. ZERO ACCUMULATION + SORTIES DISTINCTES: l'asset retenu est copie dans les
   sorties CODE (``output/code_assets/<run>/models``); les runs 3D commandes
   par le Code (repertoires ``output/3d/generations/<run-id-code>``) sont
   SUPPRIMES apres usage. Les runs 3D qui n'appartiennent pas au Code ne sont
   jamais touches.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import time
from typing import Any, Callable

PostFn = Callable[..., dict[str, Any]]
FindExistingFn = Callable[..., "pathlib.Path | None"]

# Signatures des workers 3D lourds (GPU/CPU) qu'on ne doit JAMAIS concurrencer.
# Lancer une 2e generation 3D pendant qu'une premiere tourne sature la VRAM
# (16 Go) et la RAM -> gel machine constate. Regle du projet: un seul process
# lourd a la fois.
_HEAVY_3D_MARKERS = ("hunyuan3d_run.py", "aurora_trellis", "mv_adapter", "dreamgaussian_run.py")


def _heavy_3d_process_running() -> str | None:
    """Retourne la ligne de commande du 1er worker 3D lourd detecte, sinon None.

    Protection anti-gel: si un worker 3D tourne deja (module 3D, autre onglet,
    rescue en cours), le module Code NE lance PAS une generation concurrente.
    """
    try:
        out = subprocess.run(
            ["ps", "-eo", "args"], capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception:  # noqa: BLE001 — pas de ps -> on ne bloque pas, on laisse passer
        return None
    for line in out.splitlines():
        if any(marker in line for marker in _HEAVY_3D_MARKERS):
            return line.strip()[:200]
    return None

# Nombre max de runs pipeline (1 initial + 1 re-run force). Chaque run peut en
# plus tenter un auto-rescue. Budget borne = "jusqu'a ce que ce soit bon" sans
# boucle infinie.
MAX_PIPELINE_RUNS = 2
SCORE_FLOOR_FALLBACK = 70


def _score_mesh(post: PostFn, base_url: str, mesh: pathlib.Path, kind: str,
                timeout: int, detail: dict[str, Any]) -> dict[str, Any] | None:
    """Note un GLB via le scorer du module 3D. None si le scorer est indisponible."""
    try:
        resp = post(base_url, "/api/3d/mesh-score", {"mesh_path": str(mesh), "kind": kind}, timeout=timeout)
        verdict = resp.get("score") if isinstance(resp.get("score"), dict) else None
        if not resp.get("ok") or not verdict:
            raise ValueError(str(resp.get("error") or "score indisponible"))
        return {
            "score": int(verdict.get("overall_score") or 0),
            "retry": bool(verdict.get("retry_recommended", False)),
            "threshold": int(verdict.get("retry_threshold") or SCORE_FLOOR_FALLBACK),
            "failedAxes": list(verdict.get("failed_axes") or []),
        }
    except Exception as error:  # noqa: BLE001 — le score ne doit jamais faire crasher la livraison
        detail.setdefault("scoreErrors", []).append(str(error))
        return None


def _find_reference_image(run_dir: pathlib.Path) -> pathlib.Path | None:
    """Retrouve l'image de reference FLUX du run (necessaire a auto-rescue)."""
    if not run_dir.is_dir():
        return None
    candidates = sorted(run_dir.glob("*reference*.png")) or sorted(run_dir.glob("*.png"))
    return candidates[0] if candidates else None


def _rescue_mesh(post: PostFn, base_url: str, mesh: pathlib.Path, run_dir: pathlib.Path,
                 kind: str, timeout: int, detail: dict[str, Any]) -> pathlib.Path | None:
    """Tente la chaine de rescue du module 3D; retourne le mesh repare ou None."""
    reference = _find_reference_image(run_dir)
    if reference is None:
        detail.setdefault("rescueErrors", []).append("reference FLUX introuvable dans le run")
        return None
    try:
        resp = post(base_url, "/api/3d/auto-rescue", {
            "mesh": str(mesh), "reference": str(reference),
            # Le rescue ecrit DANS le run commande -> couvert par le nettoyage final.
            "output": str(run_dir / "code_rescue"), "kind": kind,
        }, timeout=timeout)
        rescue = resp.get("rescue") if isinstance(resp.get("rescue"), dict) else {}
        rescued = pathlib.Path(str(rescue.get("final_mesh") or ""))
        if resp.get("ok") and rescue.get("ok") and rescued.is_file():
            detail["rescueFinalScore"] = rescue.get("final_score")
            return rescued
        detail.setdefault("rescueErrors", []).append(str(resp.get("error") or rescue.get("error") or "rescue sans mesh final"))
    except Exception as error:  # noqa: BLE001
        detail.setdefault("rescueErrors", []).append(str(error))
    return None


def _run_pipeline_once(post: PostFn, base_url: str, root: pathlib.Path, prompt: str,
                       pipeline_run_id: str, force: bool, timeout: int,
                       find_existing: FindExistingFn,
                       detail: dict[str, Any]) -> pathlib.Path | None:
    """Un run pipeline 3D en qualite max; retourne le GLB produit ou None."""
    try:
        response = post(base_url, "/api/3d/run-pipeline", {
            "prompt": prompt[:1000], "run_id": pipeline_run_id,
            # QUALITE MAX: multi-vues (MV-Adapter -> TRELLIS) + reglages "product".
            "purpose": "product", "multi_view": True, "force": force,
        }, timeout=timeout)
        pipeline = response.get("pipeline") if isinstance(response.get("pipeline"), dict) else {}
        detail["transportOk"] = bool(response.get("ok"))
        detail["pipelineOk"] = bool(pipeline.get("ok", response.get("ok")))
        run_root = (root / "output" / "3d" / "generations" / pipeline_run_id).resolve()
        final_mesh = pathlib.Path(str(pipeline.get("final_mesh") or "")).resolve()
        if final_mesh.is_file() and final_mesh.is_relative_to(run_root):
            return final_mesh
        if not detail["pipelineOk"]:
            detail["pipelineError"] = pipeline.get("error") or "audit 3D interne rejete"
        fallback = find_existing(root, pipeline_run_id)
        if fallback is None:
            detail["pipelineError"] = response.get("error") or "GLB absent apres pipeline"
        return fallback
    except Exception as error:  # noqa: BLE001
        detail["pipelineError"] = str(error)
        return None


def _cleanup_commissioned_runs(root: pathlib.Path, run_ids: list[str],
                               detail: dict[str, Any]) -> None:
    """Supprime les runs 3D COMMANDES PAR LE CODE apres copie de l'asset retenu.

    Zero accumulation dans l'arbre du module 3D; seuls les repertoires dont le
    nom correspond exactement a un run demande par ce client sont retires.
    """
    base = root / "output" / "3d" / "generations"
    removed: list[str] = []
    for run_id in run_ids:
        candidate = (base / run_id).resolve()
        if candidate.is_dir() and candidate.parent == base.resolve():
            shutil.rmtree(candidate, ignore_errors=True)
            removed.append(run_id)
    detail["cleanedCommissionedRuns"] = removed


def generate_quality_3d_asset(
    *,
    base_url: str,
    root: pathlib.Path,
    out_dir: pathlib.Path,
    prompt: str,
    run_id: str,
    fresh: bool,
    allow_existing: bool,
    source_run_id: str,
    timeout: int,
    post: PostFn,
    find_existing: FindExistingFn,
    slugify: Callable[[str], str],
    project_path: Callable[[pathlib.Path, pathlib.Path], str],
    storage_path: Callable[[pathlib.Path, pathlib.Path], str],
    preview_url: Callable[[pathlib.Path, pathlib.Path], str],
    subject_kind: str = "generic",
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    started = time.monotonic()
    detail: dict[str, Any] = {"requestedEndpoint": "/api/3d/run-pipeline", "multiViewRequested": True}
    commissioned: list[str] = []
    best: tuple[pathlib.Path, dict[str, Any] | None] | None = None
    rescue_used = False

    if fresh:
        busy = _heavy_3d_process_running()
        if busy is not None:
            # Un worker 3D lourd tourne deja -> on NE lance PAS une generation
            # concurrente (protection anti-gel). On se rabat sur un asset
            # existant si permis, sinon echec explicite (jamais silencieux).
            detail["blockedByConcurrent3d"] = busy
            fresh = False
            if not allow_existing:
                detail["error"] = ("Une generation 3D lourde tourne deja "
                                   "(un seul process lourd a la fois): " + busy)
                return None, detail
    if fresh:
        for attempt in range(1, MAX_PIPELINE_RUNS + 1):
            pipeline_run_id = slugify(source_run_id or f"{run_id}-3d") if attempt == 1 \
                else slugify(f"{run_id}-3d-retry{attempt}")
            commissioned.append(pipeline_run_id)
            detail["actualEndpoint"] = "/api/3d/run-pipeline"
            mesh = _run_pipeline_once(post, base_url, root, prompt, pipeline_run_id,
                                      force=attempt > 1, timeout=timeout,
                                      find_existing=find_existing, detail=detail)
            if mesh is None:
                continue
            verdict = _score_mesh(post, base_url, mesh, subject_kind, timeout, detail)
            if best is None or (verdict and (best[1] is None or verdict["score"] > best[1]["score"])):
                best = (mesh, verdict)
            if verdict is None or (not verdict["retry"] and verdict["score"] >= verdict["threshold"]):
                break  # qualite atteinte (ou scorer indisponible: on livre sans boucler)
            # Sous le seuil: intelligence de reprise — rescue d'abord, re-run ensuite.
            run_dir = root / "output" / "3d" / "generations" / pipeline_run_id
            rescued = _rescue_mesh(post, base_url, mesh, run_dir, subject_kind, timeout, detail)
            if rescued is not None:
                rescue_used = True
                rescued_verdict = _score_mesh(post, base_url, rescued, subject_kind, timeout, detail)
                if rescued_verdict is None or rescued_verdict["score"] >= (best[1] or {}).get("score", 0):
                    best = (rescued, rescued_verdict)
                if rescued_verdict is None or (not rescued_verdict["retry"]
                                               and rescued_verdict["score"] >= rescued_verdict["threshold"]):
                    break
        detail["pipelineAttempts"] = len(commissioned)

    source: pathlib.Path | None = best[0] if best else None
    final_verdict = best[1] if best else None

    if source is None and allow_existing:
        source = find_existing(root, source_run_id)
        detail.setdefault("actualEndpoint", "pipeline-output-cache")
        detail["reusedExistingPipelineAsset"] = bool(source)
    if source is None:
        _cleanup_commissioned_runs(root, commissioned, detail)
        detail["error"] = detail.get("pipelineError") or "aucun GLB pipeline trouve"
        return None, detail

    stale = bool(fresh and detail.get("reusedExistingPipelineAsset", False))
    if stale:
        detail["staleAssetWarning"] = ("Generation 3D fraiche echouee: GLB existant reutilise, "
                                       "peut ne pas correspondre au prompt.")
    below_floor = bool(final_verdict and (final_verdict["retry"]
                                          or final_verdict["score"] < final_verdict["threshold"]))
    if below_floor:
        detail["qualityWarning"] = (f"Score qualite {final_verdict['score']}/{final_verdict['threshold']} "
                                    f"apres {len(commissioned)} run(s) + rescue: meilleur candidat livre, axes faibles: "
                                    f"{', '.join(final_verdict['failedAxes']) or 'n/a'}")

    # Copie dans les sorties CODE (distinction stricte code vs 3D)...
    target = out_dir / "models" / f"{slugify(source.stem)}.glb"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    try:
        pipeline_run = source.resolve().relative_to((root / "output" / "3d" / "generations").resolve()).parts[0]
    except (ValueError, IndexError):
        pipeline_run = "unknown"
    # ... puis suppression des intermediaires 3D commandes par le Code.
    if fresh and not stale:
        _cleanup_commissioned_runs(root, commissioned, detail)

    detail["durationMs"] = round((time.monotonic() - started) * 1000)
    return {
        "id": "model-primary",
        "kind": "model3d",
        "role": "product-model",
        "path": project_path(out_dir, target),
        "storagePath": storage_path(root, target),
        "previewUrl": preview_url(out_dir, target),
        "mimeType": "model/gltf-binary",
        "bytes": target.stat().st_size,
        "sourceModule": "3d",
        "bridgeEndpoint": "/api/3d/run-pipeline",
        "optimized": True,
        "stale": stale,
        "warning": detail.get("staleAssetWarning") or detail.get("qualityWarning"),
        "metadata": {
            "sourcePath": storage_path(root, source) if source.exists() else str(source),
            "pipelineRunId": pipeline_run,
            "freshPipelineRun": fresh and not stale,
            "multiViewRequested": True,
            "purpose": "product",
            "qualityScore": final_verdict["score"] if final_verdict else None,
            "qualityThreshold": final_verdict["threshold"] if final_verdict else None,
            "qualityBelowFloor": below_floor,
            "rescueUsed": rescue_used,
            "pipelineAttempts": len(commissioned),
            "cleanedIntermediates": len(detail.get("cleanedCommissionedRuns", [])),
        },
    }, detail
