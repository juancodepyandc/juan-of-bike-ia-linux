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
from .config import TEXT_MODULES
from .storage import (Status, atomic_json, assert_unchanged, digest, file_hash, fingerprint,
                      promote, read_json)


def execute_preference_cycle(c, cycle_number=1):
    os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True,max_split_size_mb:128')
    import torch
    from safetensors.torch import save_file, load_file
    from .backends import make_backend, make_backend as reload_backend, resolve_paths, visual_tasks
    from .judges import make_judge
    from .evaluation import promotion_gate, write_html
    from .cloud import QuotaUnavailable, train_on_kaggle
    from .preference_train import train_preferences
    from .results import publish_shortcuts
    from .runner import Cancelled
    from .failure_memory import replay_tasks, record_failure
    torch.set_num_threads(4)
    state = Path(c["state_dir"])
    run_id = c["module"] + "-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    status = Status(state, run_id, c["module"])
    run = status.run
    run.mkdir(parents=True)
    atomic_json(run / "config.json", c)
    backend = None
    inference_service_was_active = False
    started = time.monotonic()
    from .resources import start_heartbeat
    stop_heartbeat = start_heartbeat(status, started)

    def check():
        if (run / "stop_signal.txt").exists():
            raise Cancelled("Arrêt demandé")
        if time.monotonic() - started > c["max_hours"] * 3600:
            raise Cancelled("Durée maximale du cycle atteinte")
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
        from .resources import configure_torch_memory, suspend_inference_service
        configure_torch_memory()
        inference_service_was_active = suspend_inference_service(state)
        if c["stage"] != "remote":
            from .resources import release_idle_comfy
            if not release_idle_comfy():
                raise RuntimeError("ComfyUI a une génération en cours : relancer après sa fin pour partager le GPU")
        paths = resolve_paths(c)
        manifest = fingerprint(paths.values())
        base_id = digest(manifest)
        atomic_json(run / "base_manifest.json", manifest)
        registry = read_json(state / "registry" / f"{c['module']}.json", {})
        if registry and registry["base_fingerprint"] != base_id:
            raise RuntimeError("La base a changé depuis l'audit du champion")
        from .lineage import prepare as prepare_parent
        lineage=prepare_parent(c,run,manifest)
        atomic_json(run/'config.json',c)
        task_dir = run / "tasks"
        task_dir.mkdir()
        pref_dir = run / "preferences"
        pref_dir.mkdir()
        status.update("curriculum", "Création de sujets difficiles et des références de comparaison…", progress_percent=2)
        resume = None
        if c.get("resume_run"):
            resume = (state / "runs" / c["resume_run"]).resolve()
            if not resume.is_relative_to((state / "runs").resolve()):
                raise ValueError("Cycle à reprendre invalide")
            old = read_json(resume / "config.json")
            for key in ("module", "models", "generation", "rank", "max_layers", "seed", "train_tasks", "eval_tasks"):
                compatible = (all(c[key].get(k) == v for k, v in old[key].items())
                              if key in {"models", "generation"} else old[key] == c[key])
                if not compatible:
                    raise ValueError("Reprise incompatible : " + key)
            # New defaults for unrelated modalities must not change the identity
            # of an already measured generation profile.
            c = {**c, "generation": old["generation"]}
            atomic_json(run / "config.json", c)
            assert_unchanged(read_json(resume / "base_manifest.json"))
            c = {**c, "prepared_tasks": str(resume / "tasks/curriculum.json")}
        if c.get("prepared_tasks"):
            tasks = read_json(c["prepared_tasks"])
        elif c["module"] == "3d":
            tasks = visual_tasks(c, task_dir, check, paths)
        else:
            tasks = None
        status.update("loading", "Chargement du vrai modèle et des juges…", progress_percent=4)
        if c['stage'] != 'remote':
            from .resources import reclaim_comfy_ram
            reclaim_comfy_ram(state)
        backend = make_backend(c, paths)
        judge = make_judge(c, paths)
        if tasks is None:
            tasks = backend.prepare_tasks(task_dir, check, getattr(judge, "sandbox", None))
        tasks=[{**task,'split':'train' if i<c['train_tasks'] else 'audit'} for i,task in enumerate(tasks)]
        # Reuse only failures from former training subjects. The audit slice
        # stays untouched, so hard-negative replay cannot invalidate the gate.
        if not c.get("resume_run"):
            tasks = replay_tasks(tasks, c, state)
        replayed = sum(1 for task in tasks[:c["train_tasks"]]
                       if task.get("origin") == "observed_failure_replay")
        if replayed:
            status.update("curriculum", f"{replayed} échec(s) mesuré(s) rejoué(s) comme cas prioritaires.",
                          failure_replay_tasks=replayed)
        if len(tasks) < c["train_tasks"] + c["eval_tasks"] or c["train_tasks"] < 2:
            raise ValueError("Au moins 2 sujets d'apprentissage/validation distincts sont requis")
        from .curriculum import validate_tasks
        validate_tasks(tasks, c)
        atomic_json(task_dir / "curriculum.json", tasks)

        if c.get('training_start') is not None:
            if c.get('initial_adapter'):backend.adapter.load(c['initial_adapter'])
        elif registry:
            if file_hash(registry["adapter"]) != registry["sha256"]:
                raise RuntimeError("L'adaptateur champion a changé")
            backend.adapter.load(registry["adapter"])
        elif c.get("initial_adapter"):
            backend.adapter.load(c["initial_adapter"])
        backend.adapter.save(pref_dir / "initial.safetensors")
        parent_sha=file_hash(pref_dir/'initial.safetensors')
        status.flush(local_generations_planned=c['train_tasks']*c['rollouts_per_task'],local_generations_done=0)
        
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
            try:
                backend.generate(task, seed, path)
                torch.cuda.synchronize()
            except Exception as exc:
                if not isinstance(exc, Cancelled):
                    record_failure(state, c["module"], task,
                                   {"judge": {"score": 0.0, "valid": False,
                                              "metrics": {}, "reasons": [str(exc)[:500]]}},
                                   error=exc, run_id=run_id,
                                   limit=c.get("failure_memory_limit", 256))
                raise
            peak = torch.cuda.max_memory_allocated()/2**30
            if peak > c["max_vram_gb"]:
                raise RuntimeError("Budget VRAM dépassé : aucun changement silencieux des paramètres")
            scored = judge.score(path, task)
            status.flush(judge_score=scored["score"])
            row = {"task_id": task["id"], "prompt": task["prompt"], "seed": seed, "artifact": str(path),
                   "family":task.get('family'),"style":task.get('style'),
                   "audit_group":task.get('audit_group'),"difficulty":task.get('difficulty'),
                   "judge": scored, "sha256": file_hash(path), "seconds": time.monotonic()-start,
                   "peak_vram_gb": peak, "generation_digest": generation_id,
                   "activation_drift": backend.adapter.drift, "attempts": 1}
            atomic_json(path.with_suffix(".evaluation.json"), row)
            if not scored["valid"] or scored["score"] < c.get("failure_score_threshold", .999):
                record_failure(state, c["module"], task, row, run_id=run_id,
                               limit=c.get("failure_memory_limit", 256))
            if c["module"] == "3d":
                save_file(backend.last_latent, str(path.with_suffix(".latent.safetensors")))
            status.flush(latest_artifact=str(path))
            return row

        audit_tasks = tasks[c["train_tasks"]:]
        candidate = run / "candidate.safetensors"
        cloud_metrics = None
        if c.get("resume_audit"):
            if not resume or not (resume / "candidate.safetensors").is_file():
                raise ValueError("Audit à reprendre : candidat entraîné absent")
            previous_weights = resume / "candidate.safetensors"
            if file_hash(previous_weights) != file_hash(resume / "trained/candidate.safetensors"):
                raise ValueError("Le candidat sauvegardé a changé")
            shutil.copy2(previous_weights, candidate)
            (run / 'trained').mkdir(exist_ok=True)
            shutil.copy2(previous_weights, run / 'trained/candidate.safetensors')
            training_metrics = read_json(resume / "training_metrics.json")
            atomic_json(run / "training_metrics.json", training_metrics)
            unload()
        else:
            training_tasks = tasks[:c["train_tasks"]]
            if resume and (resume / "preferences/preferences.json").is_file():
                shutil.copytree(resume / "preferences", pref_dir, dirs_exist_ok=True)
                if 'training_start' in c:backend.adapter.save(pref_dir/'initial.safetensors')
                records = read_json(pref_dir / "preferences.json")
                if not records:
                    raise ValueError("Ce cycle ne contient pas de préférences réutilisables")
                status.update("resuming", "Reprise des préférences mesurées ; les essais ne sont pas régénérés.")
            else:
                (run / "self_play").mkdir(exist_ok=True)
                if resume and 'training_start' not in c:
                    shutil.copy2(resume / "preferences/initial.safetensors", pref_dir / "initial.safetensors")
                    backend.adapter.load(pref_dir / "initial.safetensors")
                records = []
                for i, task in enumerate(training_tasks):
                    samples = []
                    for j in range(c["rollouts_per_task"]):
                        status.update("self_play", f"Auto-évaluation : {task['id']} · essai {j+1}/{c['rollouts_per_task']}",
                                      progress_percent=5+20*(i+j/c["rollouts_per_task"])/len(training_tasks))
                        seed = c["seed"] + i*100+j
                        if c.get('reuse_rollouts') and not resume:
                            seed=int(digest({'task':task['prompt'],'parent':parent_sha,'sample':j})[:8],16)%2147483647
                        from .rollout_cache import key as cache_key, lookup as cache_lookup, save as cache_save
                        identifier=cache_key(task,seed,generation_id,parent_sha)
                        stored=cache_lookup(state,identifier,latent=c['module']=='3d') if c.get('reuse_rollouts') and not resume else None
                        cached = resume / "self_play" / f"{task['id']}_graine_{seed}.evaluation.json" if resume else None
                        if stored:
                            from .rollout_cache import materialize
                            stored=materialize(stored,run/'self_play'/f'{task["id"]}_graine_{seed}{backend.suffix}',latent=c['module']=='3d')
                            stored['judge']=judge.score(stored['artifact'],task)
                            samples.append(stored)
                            atomic_json(run/'self_play'/f'{task["id"]}_graine_{seed}.evaluation.json',stored)
                            status.flush(reusing_self_play=True,latest_artifact=stored['artifact'])
                        elif cached and cached.is_file():
                            row = read_json(cached)
                            if (row["prompt"] != task["prompt"] or row["generation_digest"] != generation_id
                                    or row["sha256"] != file_hash(row["artifact"])):
                                raise ValueError("L’essai à reprendre a changé ou utilise un autre profil")
                            status.flush(reusing_self_play=True)
                            samples.append(row)
                        else:
                            row=generate(task, seed, run / "self_play")
                            samples.append(row)
                            if c.get('reuse_rollouts'):cache_save(state,identifier,row,latent=c['module']=='3d')
                        status.flush(local_generations_done=i*c['rollouts_per_task']+j+1)
                    # Keep invalid/low-scoring samples as hard negatives. A
                    # failed render with a measured artifact is supervision;
                    # silently dropping it teaches nothing.
                    ranked = sorted(samples, key=lambda s: (bool(s["judge"].get("valid")),
                                                             float(s["judge"].get("score", -1.0))))
                    if len(ranked) < 2 or not ranked[-1]["judge"].get("valid"):
                        continue
                    loser, winner = ranked[0], ranked[-1]
                    # For code, one bounded correction can provide a genuinely judged preference.
                    if c["module"] in TEXT_MODULES and c.get("oracle_teaching"):
                        # Trusted synthetic labels for TRAINING tasks only. This is
                        # supervision, never a claim that the model produced them.
                        reference = run / "self_play" / (task["id"] + "_oracle"+backend.suffix)
                        if c['module'] in {'conversation','learning'}:
                            reference.write_text(json.dumps(task['expected_json'],ensure_ascii=False))
                        else:
                            from .challenge_curriculum import oracle_program
                            reference.write_text(oracle_program(task))
                        reference_score = judge.score(reference, task)
                        if reference_score["score"] != 1.0:
                            raise ValueError("La réponse de référence synthétique est incompatible avec son oracle")
                        atomic_json(reference.with_suffix(".supervision.json"), {
                            "origin": "verified_executable_oracle", "task_id": task["id"],
                            "note": "Étiquette d’apprentissage calculée, pas une réponse générée par le modèle."})
                        winner = {**winner, "artifact": str(reference), "judge": reference_score,
                                  "origin": "verified_executable_oracle"}
                    elif c["module"] in TEXT_MODULES and winner["judge"]["score"] < 1.0:
                        check()
                        repair = Path(loser["artifact"]).with_stem(Path(loser["artifact"]).stem + "_correction")
                        backend.generate(task, c["seed"] + i*100+99, repair, feedback=[
                            {"role": "assistant", "content": Path(winner["artifact"]).read_text()},
                            {"role": "user", "content": "Correct your answer. Verification results: " + str(winner["judge"]["metrics"])}])
                        repaired = judge.score(repair, task)
                        if repaired["valid"] and repaired["score"] > winner["judge"]["score"]:
                            winner = {**loser, "artifact": str(repair), "judge": repaired}
                    if winner["judge"]["score"] - loser["judge"]["score"] <= 1e-5:
                        continue
                    record = {"task_id": task["id"], "prompt": task["prompt"], "split": "train",
                              "chosen_score": winner["judge"]["score"], "rejected_score": loser["judge"]["score"],
                              "chosen_origin": winner.get("origin", "model_rollout"), "rejected_origin": "model_rollout"}
                    if c["module"] in TEXT_MODULES:
                        record.update(system_prompt="Follow the instructions precisely. Return only the requested JSON." if c["module"] in {"conversation", "learning"} else "Write correct Python. Return only the complete Python code, without examples or tests.", chosen=Path(winner["artifact"]).read_text(), rejected=Path(loser["artifact"]).read_text())
                    else:
                        chosen = load_file(str(Path(winner["artifact"]).with_suffix(".latent.safetensors")))
                        rejected = load_file(str(Path(loser["artifact"]).with_suffix(".latent.safetensors")))
                        if not torch.equal(chosen["cond"], rejected["cond"]):
                            raise ValueError("Conditionnement 3D différent au sein d'une préférence")
                        filename = task["id"] + ".safetensors"
                        save_file({"chosen": chosen["latent"], "rejected": rejected["latent"], "cond": chosen["cond"]}, str(pref_dir/filename))
                        record["tensors"] = filename
                    records.append(record)
                if len(records) < c.get('minimum_preference_pairs',2):
                    raise RuntimeError("Pas assez de préférences fiables sur les essais générés. Les objets et scores restent disponibles dans self_play ; augmenter les sujets/essais.")
                # A validation set made from the last successful family can be
                # a single pair (the old 3D cycle had 3 train / 1 validation).
                # Select several deterministic, spaced training subjects before
                # writing the manifest.  This makes Kaggle model selection
                # depend on more than one object/style and keeps validation
                # disjoint from the pairs used for gradient updates.
                task_order = {task['id']: index for index, task in enumerate(training_tasks)}
                ordered = sorted(records, key=lambda row: task_order.get(row['task_id'], 10**9))
                minimum_validation = c.get('minimum_validation_pairs', 1)
                minimum_training = c.get('minimum_training_pairs', 1)
                target = min(max(minimum_validation, len(ordered)//4),
                             max(0, len(ordered)-minimum_training))
                validation_indices = set()
                if target:
                    for position in range(target):
                        # Evenly spread validation over the curriculum rather
                        # than concentrating it on one content family.
                        index = round(position * (len(ordered)-1) / max(1, target-1))
                        validation_indices.add(index)
                for index, record in enumerate(ordered):
                    record['split'] = 'validation' if index in validation_indices else 'train'
                records = ordered
                if (sum(row['split']=='validation' for row in records) < minimum_validation or
                        sum(row['split']=='train' for row in records) < minimum_training):
                    raise RuntimeError("Préférences fiables insuffisantes pour séparer apprentissage et validation")
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
        status.update("local_audit", "Retour sur la RTX 5070 Ti : comparaison des vrais fichiers à paramètres identiques…", progress_percent=80, training_location="local")
        if c['module']=='3d' and c.get('defer_audit_references'):
            from .challenge_curriculum import materialize_references
            materialize_references(c,audit_tasks,check)
            atomic_json(task_dir/'curriculum.json',tasks)
            if c['stage']!='remote':reclaim_comfy_ram(state)
        backend = reload_backend(c, paths)
        rows = {"base": [], "champion": [], "candidate": []}
        # Long 3D audits are deliberately resumable in bounded chunks.  The
        # TRELLIS/CUDA extension can accumulate allocator state over dozens of
        # exports even when every individual render stays within the VRAM
        # budget.  A chunk boundary keeps all completed rows durable and lets
        # the next process resume from them without weakening the audit.
        audit_generated = 0
        audit_limit = int(c.get("audit_limit", 0) or 0)
        if lineage and lineage.get('parent_run_id') and lineage.get('parent_run_id')!=registry.get('run_id'):
            rows['parent']=[]
        for branch in rows:
            is_champion = (branch == "champion")
            has_champion_weights = registry or (c.get("initial_adapter") if not lineage else None)
            if is_champion and not has_champion_weights:
                rows[branch] = rows["base"]
                continue
            if branch == "base":
                backend.adapter.enabled = False
            else:
                backend.adapter.enabled = True
                if is_champion:
                    backend.adapter.load(registry["adapter"] if registry else c["initial_adapter"])
                elif branch=='parent':
                    backend.adapter.load(c['initial_adapter'])
                else:
                    backend.adapter.load(candidate)
            for task in audit_tasks:
                for seed in c["eval_seeds"]:
                    status.update("local_audit", f"Comparaison RTX · {branch} · {task['id']} · graine {seed}", progress_percent=85)
                    cached = resume / "audit" / branch / f"{task['id']}_graine_{seed}.evaluation.json" if c.get("resume_audit") else None
                    if cached and cached.is_file():
                        row = read_json(cached)
                        if (row["prompt"] != task["prompt"] or row["generation_digest"] != generation_id
                                or row["sha256"] != file_hash(row["artifact"])):
                            raise ValueError("Audit sauvegardé incompatible ou modifié")
                        # A resumed audit already validated this artifact with
                        # the same generation digest.  Re-scoring every cached
                        # GLB would rerun the CUDA rasterizer for all 96 base
                        # rows at every chunk boundary; the hash check above
                        # still makes tampering fail closed.
                        if not c.get("resume_audit_reuse_scores", True):
                            row["judge"] = judge.score(row["artifact"], task)
                        atomic_json(run / 'audit' / branch / cached.name, row)
                        rows[branch].append(row)
                    else:
                        if audit_limit and audit_generated >= audit_limit:
                            raise Cancelled(f"Bloc d'audit terminé ({audit_generated} rendu(s)); reprise automatique")
                        rows[branch].append(generate(task, seed, run / "audit" / branch))
                        audit_generated += 1
        unload()
        assert_unchanged(manifest)
        if lineage and 'parent' not in rows:
            rows['parent']=rows['champion'] if lineage.get('parent_run_id') else rows['base']
        gate = promotion_gate(rows["base"], rows["champion"], rows["candidate"], c, parent=rows.get('parent'))
        report = {"schema": 1, "run_id": run_id, "module": c["module"], "base_fingerprint": base_id,
                  "candidate_sha256": file_hash(candidate), **rows, "gate": gate, "hardware": hardware,
                  "generation": c["generation"], "training": training_metrics, "cloud": cloud_metrics,
                  "config_digest": digest(c), "elapsed_seconds": time.monotonic()-started,
                  "algorithm": training_metrics.get("algorithm"), "lineage":lineage,
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
        stop_heartbeat()
        unload()
        from .resources import restore_inference_service
        try:
            restore_inference_service(inference_service_was_active, state)
        except Exception:
            pass
