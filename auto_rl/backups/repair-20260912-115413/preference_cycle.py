"""Generate judged self-play, train LoRA on Kaggle, audit on the user's GPU."""
from __future__ import annotations
import gc
import json
import os
import shutil
import time
import uuid
import zipfile
from pathlib import Path
from .storage import (Status, atomic_json, assert_unchanged, digest, file_hash, fingerprint,
                      promote, read_json)


def execute_preference_cycle(c, cycle_number=1):
    import torch
    from safetensors.torch import save_file, load_file
    from .backends import make_backend, make_backend as reload_backend, resolve_paths, visual_tasks
    from .judges import make_judge
    from .evaluation import promotion_gate, write_html
    from .cloud import QuotaUnavailable, train_on_kaggle
    from .preference_train import train_preferences
    from .results import publish_shortcuts
    from .runner import Cancelled
    torch.set_num_threads(4)
    state = Path(c["state_dir"])
    run_id = c["module"] + "-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    status = Status(state, run_id, c["module"])
    run = status.run
    run.mkdir(parents=True)
    atomic_json(run / "config.json", c)
    backend = None
    started = time.monotonic()

    def check():
        if (run / "stop_signal.txt").exists():
            raise Cancelled("Arrêt demandé")
        if shutil.disk_usage(state).free < c["minimum_free_gb"] * 2**30:
            raise Cancelled("Réserve de disque atteinte")

    def unload():
        nonlocal backend
        if backend is not None:
            backend.close()
            backend = None
        gc.collect()
        torch.cuda.empty_cache()

    try:


        status.update("preflight", "Préparation du cycle hybride : modèles locaux et profil RTX 5070 Ti…", cycle=cycle_number)
        if not torch.cuda.is_available():
            raise RuntimeError("GPU CUDA local requis")
        check()
        paths = resolve_paths(c)
        manifest = fingerprint(paths.values())
        base_id = digest(manifest)
        atomic_json(run / "base_manifest.json", manifest)
        registry = read_json(state / "registry" / f"{c['module']}.json", {})
        if registry and registry["base_fingerprint"] != base_id:
            raise RuntimeError("La base a changé depuis l'audit du champion")
        task_dir = run / "tasks"
        task_dir.mkdir()
        pref_dir = run / "preferences"
        pref_dir.mkdir()
        status.update("curriculum", "Création de sujets difficiles et des références de comparaison…", progress_percent=2)
        if c.get("prepared_tasks"):
            tasks = read_json(c["prepared_tasks"])
        elif c["module"] == "3d":
            tasks = visual_tasks(c, task_dir, check, paths)
        else:
            tasks = None
        status.update("loading", "Chargement du vrai modèle et des juges…", progress_percent=4)
        backend = make_backend(c, paths)
        judge = make_judge(c, paths)
        if tasks is None:
            tasks = backend.prepare_tasks(task_dir, check, judge.sandbox)
        if len(tasks) < c["train_tasks"] + c["eval_tasks"] or c["train_tasks"] < 2:
            raise ValueError("Au moins 2 sujets d'apprentissage/validation distincts sont requis")
        atomic_json(task_dir / "curriculum.json", tasks)

        if registry:
            if file_hash(registry["adapter"]) != registry["sha256"]:
                raise RuntimeError("L'adaptateur champion a changé")
            backend.adapter.load(registry["adapter"])
        elif c.get("initial_adapter"):
            backend.adapter.load(c["initial_adapter"])
        backend.adapter.save(pref_dir / "initial.safetensors")
        
        if c["execution"] == "kaggle_only" and c["stage"] != "remote":
            status.update("cloud_starting", "Envoi intégral du cycle sur Kaggle… (Curriculum généré localement)", cycle=cycle_number)
            spec = {"model_revisions": {k: Path(v).name for k, v in paths.items() if k != "aesthetic"}, 
                    "model_revision": Path(paths[c["module"]]).name,
                    "module": c["module"]}
            files = [(task_dir / "curriculum.json", "tasks.json"), (pref_dir / "initial.safetensors", "initial.safetensors")]
            if c["module"] == "3d":
                source = Path(c["trellis_root"])
                source_zip = run / "trellis_dense_source.zip"
                with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED) as z:
                    for subdir in ("trellis2/modules/attention", "trellis2/modules/transformer"):
                        for p in (source/subdir).glob("*.py"):
                            z.write(p, str(p.relative_to(source)))
                    for name in ("trellis2/models/sparse_structure_flow.py", "trellis2/modules/norm.py", "LICENSE"):
                        if (source/name).is_file():
                            z.write(source/name, name)
                files.append((source_zip, "trellis_dense_source.zip"))
            
            # Unload local backend before remote training to save VRAM and avoid memory leaks
            unload()
            
            remote_dir, remote_manifest = train_on_kaggle(c, run, files, spec, status, check)
            
            for name in ("report.json", "candidate.safetensors", "training_metrics.json"):
                if (remote_dir / name).is_file():
                    shutil.copy2(remote_dir / name, run / name)
            if (remote_dir / "run_export").is_dir():
                shutil.copytree(remote_dir / "run_export", run, dirs_exist_ok=True)
                
            report = read_json(run / "report.json")
            if not report:
                raise RuntimeError("Kaggle n'a pas renvoyé de rapport d'audit complet.")
            gate = report["gate"]
            report_digest = digest(report)
            status.update("awaiting_validation", "Comparaison prête : rendus et scores disponibles (Kaggle).", progress_percent=100,
                report=str(run / "report.json"), results_folder=str(run), report_digest=report_digest, waiting_validation=True,
                eligible=gate["eligible"], rejection_reasons=gate["reasons"], improvement=gate.get("gain_points"),
                file_base=report["base"][0]["artifact"], file_new=report["candidate"][0]["artifact"])
            
            if c["mode"] == "auto":
                decision = "ACCEPT" if gate["eligible"] else "REJECT"
            else:
                while True:
                    check()
                    msg = read_json(run / "validation_signal.txt")
                    if msg:
                        if msg.get("run_id") != run_id or msg.get("report_digest") != report_digest:
                            raise ValueError("Signal de validation périmé")
                        decision = msg.get("decision")
                        if decision not in {"ACCEPT", "REJECT"}:
                            raise ValueError("Décision invalide")
                        break
                    time.sleep(0.5)
            check()
            if decision == "ACCEPT":
                registry = read_json(state / "registry" / f"{c['module']}.json", {})
                record = promote(state, c["module"], run_id, run / "candidate.safetensors", report, registry.get("run_id"))
                if c["module"] == "3d":
                    from .photo_queue import mark_validated
                    mark_validated(c, tasks, report, run)
                status.update("accepted", f"{record['name']} validé.", waiting_validation=False)
            else:
                status.update("rejected", "Candidat rejeté.", waiting_validation=False)
            return decision

        hardware = {"gpu": torch.cuda.get_device_name(0), "torch": torch.__version__, "cuda": torch.version.cuda}
        generation_id = digest({"hardware": hardware, "generation": c["generation"], "base": base_id})

        def generate(task, seed, directory):
            check()
            directory.mkdir(parents=True, exist_ok=True)
            name = task["id"] + "_graine_" + str(seed)
            path = directory / (name + backend.suffix)
            start = time.monotonic()
            torch.cuda.reset_peak_memory_stats()
            backend.adapter.reset_drift()
            backend.generate(task, seed, path)
            torch.cuda.synchronize()
            peak = torch.cuda.max_memory_allocated()/2**30
            if peak > c["max_vram_gb"]:
                raise RuntimeError("Budget VRAM dépassé : aucun changement silencieux des paramètres")
            scored = judge.score(path, task)
            row = {"task_id": task["id"], "prompt": task["prompt"], "seed": seed, "artifact": str(path),
                   "judge": scored, "sha256": file_hash(path), "seconds": time.monotonic()-start,
                   "peak_vram_gb": peak, "generation_digest": generation_id,
                   "activation_drift": backend.adapter.drift, "attempts": 1}
            atomic_json(path.with_suffix(".evaluation.json"), row)
            if c["module"] == "3d":
                save_file(backend.last_latent, str(path.with_suffix(".latent.safetensors")))
            return row

        records = []
        training_tasks = tasks[:c["train_tasks"]]
        audit_tasks = tasks[c["train_tasks"]:]
        for i, task in enumerate(training_tasks):
            samples = []
            for j in range(c["rollouts_per_task"]):
                status.update("self_play", f"Auto-évaluation : {task['id']} · essai {j+1}/{c['rollouts_per_task']}",
                              progress_percent=5+20*(i+j/c["rollouts_per_task"])/len(training_tasks))
                samples.append(generate(task, c["seed"] + i*100+j, run / "self_play"))
            good = [s for s in samples if s["judge"]["valid"]]
            if len(good) < 2:
                continue
            good.sort(key=lambda s: s["judge"]["score"])
            loser, winner = good[0], good[-1]
            # For code, one bounded correction can provide a genuinely judged preference.
            if c["module"] == "code" and winner["judge"]["score"] - loser["judge"]["score"] <= 1e-5:
                repair = Path(loser["artifact"]).with_stem(Path(loser["artifact"]).stem + "_correction")
                backend.generate(task, c["seed"] + i*100+99, repair, feedback=[
                    {"role": "assistant", "content": Path(loser["artifact"]).read_text()},
                    {"role": "user", "content": "Correct this code. Failed unit tests: " + str(loser["judge"]["metrics"])}])
                repaired = judge.score(repair, task)
                if repaired["score"] > winner["judge"]["score"]:
                    winner = {**loser, "artifact": str(repair), "judge": repaired}
            if winner["judge"]["score"] - loser["judge"]["score"] <= 1e-5:
                continue
            record = {"task_id": task["id"], "prompt": task["prompt"], "split": "train",
                      "chosen_score": winner["judge"]["score"], "rejected_score": loser["judge"]["score"]}
            if c["module"] == "code":
                record.update(chosen=Path(winner["artifact"]).read_text(), rejected=Path(loser["artifact"]).read_text())
            else:
                chosen = load_file(str(Path(winner["artifact"]).with_suffix(".latent.safetensors")))
                rejected = load_file(str(Path(loser["artifact"]).with_suffix(".latent.safetensors")))
                if not torch.equal(chosen["cond"], rejected["cond"]):
                    raise ValueError("Conditionnement 3D différent au sein d'une préférence")
                filename = task["id"] + ".safetensors"
                save_file({"chosen": chosen["latent"], "rejected": rejected["latent"], "cond": chosen["cond"]}, str(pref_dir/filename))
                record["tensors"] = filename
            records.append(record)
        if len(records) < 2:
            raise RuntimeError("Pas assez de préférences fiables sur les essais générés. Les objets et scores restent disponibles dans self_play ; augmenter les sujets/essais.")
        records[-1]["split"] = "validation"
        atomic_json(pref_dir / "preferences.json", records)
        files = [(p, p.name) for p in pref_dir.iterdir() if p.is_file()]
        model_path = paths[c["module"]]
        spec = {"model_revision": Path(model_path).name, "module": c["module"]}
        if c["module"] == "3d":
            source_zip = pref_dir / "trellis_dense_source.zip"
            source = Path(c["trellis_root"])
            with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED) as z:
                for subdir in ("trellis2/modules/attention", "trellis2/modules/transformer"):
                    for p in (source/subdir).glob("*.py"):
                        z.write(p, str(p.relative_to(source)))
                for name in ("trellis2/models/sparse_structure_flow.py", "trellis2/modules/norm.py", "LICENSE"):
                    z.write(source/name, name)
            files.append((source_zip, source_zip.name))
        unload()
        output = run / "trained"
        output.mkdir()
        cloud_metrics = None
        if c["execution"] in {"hybrid", "kaggle"}:
            try:
                remote_dir, remote_manifest = train_on_kaggle(c, run, files, spec, status, check)
                shutil.copy2(remote_dir / "candidate.safetensors", output / "candidate.safetensors")
                cloud_metrics = read_json(remote_dir / "training_metrics.json")
                training_metrics = cloud_metrics
            except QuotaUnavailable as e:
                if c["execution"] != "hybrid" or not c["fallback_on_quota"]:
                    raise
                status.update("quota_fallback", "Quota Kaggle épuisé : reprise locale, 50 époques.", quota_reason=str(e), training_location="local")
        if not (output / "candidate.safetensors").is_file():
            local_c = {**c, "training_model_path": str(Path(model_path)/"ckpts/ss_flow_img_dit_1_3B_64_bf16") if c["module"] == "3d" else model_path}
            def callback(row):
                status.update("training", f"Entraînement local · époque {row['epoch']}/{c['local_epochs']}",
                    epoch=row["epoch"], epochs=c["local_epochs"], loss=row["loss"],
                    validation_loss=row["validation_loss"], progress_percent=25+55*row["epoch"]/c["local_epochs"], training_location="local")
            training_metrics = train_preferences(local_c, records, pref_dir, output, c["local_epochs"], c["max_hours"]*3600, callback, check)
        candidate = run / "candidate.safetensors"
        shutil.copy2(output / "candidate.safetensors", candidate)
        atomic_json(run / "training_metrics.json", training_metrics)
        status.update("local_audit", "Retour sur la RTX 5070 Ti : comparaison des vrais fichiers à paramètres identiques…", progress_percent=80)
        backend = reload_backend(c, paths)
        rows = {"base": [], "champion": [], "candidate": []}
        for branch in rows:
            is_champion = (branch == "champion")
            has_champion_weights = registry or c.get("initial_adapter")
            if is_champion and not has_champion_weights:
                rows[branch] = rows["base"]
                continue
            if branch == "base":
                backend.adapter.enabled = False
            else:
                backend.adapter.enabled = True
                if is_champion:
                    backend.adapter.load(registry["adapter"] if registry else c["initial_adapter"])
                else:
                    backend.adapter.load(candidate)
            for task in audit_tasks:
                for seed in c["eval_seeds"]:
                    status.update("local_audit", f"Comparaison RTX · {branch} · {task['id']} · graine {seed}", progress_percent=85)
                    rows[branch].append(generate(task, seed, run / "audit" / branch))
        unload()
        assert_unchanged(manifest)
        gate = promotion_gate(rows["base"], rows["champion"], rows["candidate"], c)
        report = {"schema": 1, "run_id": run_id, "module": c["module"], "base_fingerprint": base_id,
                  "candidate_sha256": file_hash(candidate), **rows, "gate": gate, "hardware": hardware,
                  "generation": c["generation"], "training": training_metrics, "cloud": cloud_metrics,
                  "config_digest": digest(c), "elapsed_seconds": time.monotonic()-started,
                  "algorithm": training_metrics.get("algorithm"),
                  "limitations": ["Le juge et les préférences synthétiques sont imparfaits.",
                                  "Un gain de loss sur Kaggle n'est pas un gain de qualité démontré.",
                                  "Aucune garantie de zéro régression hors de l'audit."]}
        atomic_json(run / "report.json", report)
        page = write_html(run, report)
        folder = publish_shortcuts(c["module"], run)
        report_digest = digest(report)
        status.update("awaiting_validation", "Comparaison prête : rendus et scores disponibles.", progress_percent=100,
            report=page, results_folder=folder, report_digest=report_digest, waiting_validation=True,
            eligible=gate["eligible"], rejection_reasons=gate["reasons"], improvement=gate.get("gain_points"),
            file_base=rows["base"][0]["artifact"], file_new=rows["candidate"][0]["artifact"])
        if c["mode"] == "auto":
            decision = "ACCEPT" if gate["eligible"] else "REJECT"
        else:
            while True:
                check()
                msg = read_json(run / "validation_signal.txt")
                if msg:
                    if msg.get("run_id") != run_id or msg.get("report_digest") != report_digest:
                        raise ValueError("Signal de validation périmé")
                    decision = msg.get("decision")
                    if decision not in {"ACCEPT", "REJECT"}:
                        raise ValueError("Décision invalide")
                    break
                time.sleep(0.5)
        check()
        if decision == "ACCEPT":
            assert_unchanged(manifest)
            if digest(read_json(run / "report.json")) != report_digest:
                raise ValueError("Le rapport a changé après l'audit")
            record = promote(state, c["module"], run_id, candidate, report, registry.get("run_id"))
            if c["module"] == "3d":
                from .photo_queue import mark_validated
                mark_validated(c, tasks, report, run)
            status.update("accepted", f"{record['name']} validé. Le prochain cycle repart de ces poids.", waiting_validation=False)
        else:
            status.update("rejected", "Candidat conservé pour comparaison ; champion inchangé.", waiting_validation=False)
        return decision
    except (KeyboardInterrupt, Cancelled) as e:
        status.update("cancelled", str(e) or "Arrêt demandé", waiting_validation=False)
        return "STOP"
    except Exception as e:
        import traceback
        (run / "error.log").write_text(traceback.format_exc())
        status.update("error", str(e), waiting_validation=False, error_log=str(run / "error.log"))
        publish_shortcuts(c["module"], run)
        return "ERROR"
    finally:
        unload()
