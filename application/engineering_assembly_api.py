"""Route du pont pour concevoir un assemblage depuis une demande (web, natif et CLI partagent ce contrat).

POST /api/3d/assembly           {"demande": "..."} ou {"exigences": {...}, "demande": "..."} → 202 {job_id}
GET  /api/3d/assembly/<job_id>  état, verdict, contrôles, fichiers servis par /api/3d/file/…

Un seul travail à la fois (le modèle de langage local et la mémoire sont partagés). Le travail tourne
dans un processus séparé, borné dans le temps ; son reçu survit à un redémarrage du pont.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

from flask import jsonify, request

RACINE_DEPOT = Path(__file__).resolve().parents[1]
DUREE_MAX_S = 2400


def register_assembly_routes(bp, workspace):
    workspace = Path(workspace)
    sorties = workspace / "output" / "3d" / "assemblages"
    racine_3d = workspace / "output" / "3d"
    recus = workspace / ".aurora" / "assembly-receipts"
    recus.mkdir(parents=True, exist_ok=True, mode=0o700)
    travaux: dict[str, dict] = {}
    verrou = threading.Lock()

    def proprietaire():
        from application.device_pairing import request_identity
        return hashlib.sha256((request_identity(workspace) or "local-workspace").encode()).hexdigest()

    def enregistrer(job_id, job):
        chemin = recus / f"{job_id}.json"
        tmp = chemin.with_suffix(".tmp")
        tmp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(chemin)

    def url(chemin: str | None) -> str | None:
        if not chemin:
            return None
        try:
            rel = Path(chemin).resolve().relative_to(racine_3d.resolve())
        except ValueError:
            return None
        return "/api/3d/file/" + rel.as_posix()

    def executer(job_id, cmd, dossier):
        resultat = {"ok": False, "raison": "travail interrompu"}
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=DUREE_MAX_S,
                                  cwd=str(RACINE_DEPOT))
            lignes = proc.stdout.strip()
            debut = lignes.find("{")
            resultat = json.loads(lignes[debut:]) if debut >= 0 else {"ok": False, "raison": proc.stderr[-400:]}
        except subprocess.TimeoutExpired:
            resultat = {"ok": False, "raison": f"conception plus longue que {DUREE_MAX_S} s"}
        except (OSError, ValueError) as exc:
            resultat = {"ok": False, "raison": f"résultat illisible : {exc}"[:300]}
        rapport_path = Path(resultat.get("dossier") or dossier) / "rapport.json"
        if rapport_path.is_file():
            try:
                rapport = json.loads(rapport_path.read_text(encoding="utf-8"))
                f = rapport.get("fichiers") or {}
                resultat["fichiers_url"] = {"assemblage": url(f.get("assemblage")), "eclate": url(f.get("eclate")),
                                            "coupe": url(f.get("coupe")),
                                            "dossier": url(str(Path(f.get("dossier", dossier)) / "DOSSIER.md")),
                                            "apercus": {k: url(v) for k, v in (f.get("apercus") or {}).items()}}
                resultat["nomenclature"] = rapport.get("nomenclature")
                resultat["gamme"] = [e.get("texte") for e in rapport.get("gamme") or []]
                resultat["decisions"] = rapport.get("decisions")
            except (OSError, ValueError):
                pass
        with verrou:
            travaux[job_id].update(etat="termine" if resultat.get("ok") else "echec", resultat=resultat)
            enregistrer(job_id, travaux[job_id])

    @bp.route("/api/3d/assembly", methods=["POST"])
    def lancer_assemblage():
        donnees = request.get_json(silent=True) or {}
        demande = " ".join(str(donnees.get("demande") or "").split())[:2000]
        exigences = donnees.get("exigences")
        if not demande and not isinstance(exigences, dict):
            return jsonify(ok=False, error="Décrire l'objet à concevoir (demande) ou fournir ses exigences."), 400
        job_id = "asm_" + uuid4().hex
        stamp = time.strftime("%m%d%H%M")
        base = re.sub(r"[^a-z0-9]+", "_", demande.lower())[:40].strip("_") or "assemblage"
        dossier = sorties / f"{base}_{stamp}_{job_id[4:10]}"
        with verrou:
            if any(j["etat"] == "en_cours" for j in travaux.values()):
                return jsonify(ok=False, error="Une conception est déjà en cours. Attendre sa fin."), 409
            travaux[job_id] = {"proprietaire": proprietaire(), "cree": time.time(), "etat": "en_cours",
                               "demande": demande, "dossier": str(dossier)}
        dossier.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, "-m", "application.engineering_assembly_pipeline", "--sortie", str(dossier)]
        if isinstance(exigences, dict):
            (dossier / "exigences.json").write_text(json.dumps(exigences, ensure_ascii=False), encoding="utf-8")
            cmd += ["--exigences", str(dossier / "exigences.json")]
        if demande:
            cmd += ["--demande", demande]
        enregistrer(job_id, travaux[job_id])
        threading.Thread(target=executer, args=(job_id, cmd, dossier), daemon=True).start()
        return jsonify(ok=True, job_id=job_id, dossier=str(dossier)), 202

    @bp.route("/api/3d/assembly/<job_id>", methods=["GET"])
    def etat_assemblage(job_id):
        if not re.fullmatch(r"asm_[0-9a-f]{32}", job_id):
            return jsonify(ok=False, error="Identifiant invalide."), 400
        with verrou:
            job = travaux.get(job_id)
        if job is None:
            try:
                job = json.loads((recus / f"{job_id}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return jsonify(ok=False, error="Conception introuvable."), 404
            if job.get("etat") == "en_cours":
                job["etat"] = "echec"
                job["resultat"] = {"ok": False, "raison": "le pont a redémarré pendant la conception ; rien n'a été relancé"}
        if job.get("proprietaire") != proprietaire():
            return jsonify(ok=False, error="Conception introuvable."), 404
        corps = {"ok": True, "etat": job["etat"], "demande": job.get("demande")}
        corps.update(job.get("resultat") or {})          # une fois fini, « ok » est celui de la conception
        return jsonify(corps)
