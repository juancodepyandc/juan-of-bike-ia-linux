from __future__ import annotations

import gc
import os
import signal
import threading
import time
import uuid
from pathlib import Path

from .config import validate
from .storage import (Status, assert_unchanged, atomic_json, digest, exclusive_lock,
                      file_hash, fingerprint, promote, read_json)


class Cancelled(Exception):
    pass


def execute_cycle(c, cycle_number=1):
    if c.get("trainer") == "preference_lora":
        from .preference_cycle import execute_preference_cycle
        return execute_preference_cycle(c, cycle_number)
    import shutil
    import os
    os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True,max_split_size_mb:128')
    import torch
    torch.set_num_threads(4)
    from .adapters import es_gradient, project
    from .backends import make_backend, resolve_paths, visual_tasks, audio_tasks
    from .evaluation import promotion_gate, write_html
    from .judges import make_judge

    state = Path(c["state_dir"])
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    status = Status(state, run_id, c["module"])
    run = status.run
    run.mkdir(parents=True)
    atomic_json(run / "config.json", c)
    start = time.monotonic()
    deadline = start + c["max_hours"] * 3600
    backend = None
    inference_service_was_active = False
    heartbeat_stop = threading.Event()

    def check():
        if (run / "stop_signal.txt").exists():
            raise Cancelled("Arrêt demandé")
        if time.monotonic() > deadline:
            raise Cancelled("Durée maximale atteinte")
        if shutil.disk_usage(state).free / 2 ** 30 < c["minimum_free_gb"]:
            raise Cancelled("Réserve d'espace disque atteinte")

    def heartbeat():
        import subprocess
        while not heartbeat_stop.wait(5):
            try:
                r = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=4)
                gpu, memory = map(float, r.stdout.splitlines()[0].split(","))
                status.flush(gpu_percent=gpu, gpu_memory_gb=memory / 1024,
                             elapsed_seconds=time.monotonic() - start, heartbeat_at=time.time())
            except Exception:
                pass

    try:


        status.update("preflight", "Vérification des modèles et ressources locales…", cycle=cycle_number)
        if not torch.cuda.is_available():
            raise RuntimeError("Un GPU CUDA est requis pour les cycles réels")
        if torch.cuda.get_device_properties(0).total_memory / 2 ** 30 < c["max_vram_gb"]:
            raise RuntimeError("Le budget configuré dépasse la mémoire du GPU")
        check()
        from .resources import configure_torch_memory, suspend_inference_service
        configure_torch_memory()
        inference_service_was_active = suspend_inference_service(state)
        if c["stage"] != "remote":
            from .resources import release_idle_comfy
            if not release_idle_comfy():
                raise RuntimeError("ComfyUI a une génération en cours : relancer après sa fin pour partager le GPU")
        threading.Thread(target=heartbeat, daemon=True).start()
        paths = resolve_paths(c)
        base_manifest = fingerprint(paths.values())
        atomic_json(run / "base_manifest.json", base_manifest)
        base_id = digest(base_manifest)
        hardware = {"gpu": torch.cuda.get_device_name(0), "cuda": torch.version.cuda,
                    "torch": torch.__version__, "capability": list(torch.cuda.get_device_capability()),
                    "memory_total_gb": torch.cuda.get_device_properties(0).total_memory / 2 ** 30}
        generation_id = digest({"generation": c["generation"], "hardware": hardware,
                                "base": base_id, "judge": {k: c[k] for k in ("render_views", "render_size")}})
        registry = read_json(state / "registry" / (c["module"] + ".json"), {})
        if registry and registry["base_fingerprint"] != base_id:
            raise RuntimeError("Le champion utilise une autre base ou une autre version des juges. Audit séparé requis.")
        from .lineage import prepare as prepare_parent
        lineage=prepare_parent(c,run,base_manifest)
        atomic_json(run/'config.json',c)
        task_dir = run / "tasks"
        task_dir.mkdir()
        status.update("curriculum", "Préparation des sujets d'entraînement et de l'audit réservé…", progress_percent=3)
        if c.get("prepared_tasks"):
            tasks = read_json(c["prepared_tasks"])
        elif c["module"] in {"3d", "image"}:
            tasks = visual_tasks(c, task_dir, check, paths)
        elif c["module"] == "audio":
            tasks = audio_tasks(c)
        else:
            tasks = None
        status.update("loading", "Chargement du modèle de base gelé et des juges…", progress_percent=5)
        if c['stage'] != 'remote' and c['module'] not in {'image','video'}:
            from .resources import reclaim_comfy_ram
            reclaim_comfy_ram(state)
        backend = make_backend(c, paths)
        judge = make_judge(c, paths)
        if tasks is None:
            tasks = backend.prepare_tasks(task_dir, check, getattr(judge, "sandbox", None))
        tasks=[{**task,'split':'train' if i<c['train_tasks'] else 'audit'} for i,task in enumerate(tasks)]
        # Feed only previously observed training failures back into the next
        # training batch.  The audit slice remains byte-for-byte held out.
        from .failure_memory import replay_tasks, record_failure
        tasks = replay_tasks(tasks, c, state)
        replayed = sum(1 for task in tasks[:c["train_tasks"]]
                       if task.get("origin") == "observed_failure_replay")
        if replayed:
            status.update("curriculum", f"{replayed} échec(s) mesuré(s) rejoué(s) comme cas prioritaires.",
                          failure_replay_tasks=replayed)
        from .curriculum import validate_tasks
        validate_tasks(tasks, c)
        atomic_json(task_dir / "curriculum.json", tasks)
        train_tasks, eval_tasks = tasks[:c["train_tasks"]], tasks[c["train_tasks"]:]
        if c.get('training_start') is not None:
            if c.get('initial_adapter'):backend.adapter.load(c['initial_adapter'])
        elif registry:
            if file_hash(registry["adapter"]) != registry["sha256"]:
                raise RuntimeError("L'empreinte de l'adaptateur champion ne correspond plus")
            backend.adapter.load(registry["adapter"])
        elif c.get("initial_adapter"):
            backend.adapter.load(c["initial_adapter"])
        champion_vector = backend.adapter.vector()
        cloud_metrics = None
        remote_history = []
        if c["stage"] != "remote":
            c = {**c, "iterations": c["local_epochs"]}
        if c["execution"] in {"hybrid", "kaggle"} and c["stage"] != "remote" and c.get("trainer") != "surrogate_es":
            from .cloud import train_on_kaggle, QuotaUnavailable
            initial_file = run / "initial.safetensors"
            backend.adapter.save(initial_file)
            backend.close()
            del backend
            backend = None
            gc.collect()
            torch.cuda.empty_cache()
            files = [(initial_file, "initial.safetensors"), (task_dir / "curriculum.json", "tasks.json")]
            if c["module"] == "image":
                files.append((c["aesthetic_weights"], "aesthetic.safetensors"))
            spec = {"model_revisions": {k: Path(v).name for k, v in paths.items() if k != "aesthetic"}}
            try:
                remote_dir, remote_manifest = train_on_kaggle(c, run, files, spec, status, check)
                cloud_metrics = read_json(remote_dir / "training_metrics.json")
                remote_history = read_json(remote_dir / "training.json", [])
                backend = make_backend(c, paths)
                backend.adapter.load(remote_dir / "candidate.safetensors")
                c = {**c, "iterations": 0}
            except QuotaUnavailable as e:
                if c["execution"] != "hybrid" or not c["fallback_on_quota"]:
                    raise
                status.update("quota_fallback", "Quota Kaggle épuisé : 50 époques locales.", quota_reason=str(e))
                backend = make_backend(c, paths)
                backend.adapter.load(initial_file)
        initial = backend.adapter.vector()
        train_seed = c["seed"] + cycle_number * 1000
        eval_count = len(eval_tasks) * len(c["eval_seeds"]) * (3 if registry else 2)
        total_generations = c["iterations"] * (c["directions"] * 2 + 1) * len(train_tasks) + len(train_tasks) + eval_count
        completed = 0
        observations = []
        backend.check = check

        def evaluate(vector, subset, seeds, label, training=False):
            nonlocal completed
            backend.adapter.set_vector(vector)
            backend.adapter.enabled = True
            directory = run / label
            directory.mkdir(parents=True, exist_ok=True)
            rows, rewards = [], []
            for task in subset:
                for seed in seeds:
                    check()
                    backend.adapter.reset_drift()
                    torch.cuda.reset_peak_memory_stats()
                    path = directory / f"{task['id']}_s{seed}{backend.suffix}"
                    stamp = time.monotonic()
                    status.update("training" if training else "evaluating",
                                  f"{'Apprentissage' if training else 'Audit'} · {label} · {task['id']} · graine {seed}",
                                  progress_percent=min(94, 8 + 85 * completed / total_generations))
                    try:
                        with torch.inference_mode():
                            backend.generate(task, seed, path)
                        torch.cuda.synchronize()
                    except Exception as exc:
                        if training and not isinstance(exc, Cancelled):
                            record_failure(state, c["module"], task,
                                           {"judge": {"score": 0.0, "valid": False,
                                                      "metrics": {}, "reasons": [str(exc)[:500]]}},
                                           error=exc, run_id=run_id,
                                           limit=c.get("failure_memory_limit", 256))
                        raise
                    seconds = time.monotonic() - stamp
                    vram = max(torch.cuda.max_memory_allocated() / 2 ** 30, getattr(backend, "last_peak_vram_gb", 0.0))
                    if vram > c["max_vram_gb"]:
                        raise RuntimeError("Budget VRAM dépassé : réduire explicitement le profil avant de relancer")
                    scored = judge.score(path, task)
                    drift = backend.adapter.drift
                    kl = backend.kl_to_base(task, path) if c["module"] == "code" else None
                    penalty = kl if kl is not None else drift
                    reward = scored["score"] - c["drift_penalty"] * penalty if scored["valid"] else -1.0
                    if training and c["module"] == "code" and scored["score"] < 1:
                        # Feedback is training-only; every audit uses one attempt.
                        feedback = [{"role": "assistant", "content": path.read_text()},
                                    {"role": "user", "content": "Correct the code. Test feedback: " +
                                     str(scored["metrics"])}]
                        repair = path.with_stem(path.stem + "_repair")
                        check()
                        backend.generate(task, seed, repair, feedback=feedback)
                        repair_score = judge.score(repair, task, attempts=2)
                        atomic_json(repair.with_suffix(".judge.json"), repair_score)
                        reward = max(reward, repair_score["score"] - c["drift_penalty"] * backend.adapter.drift)
                    row = {"task_id": task["id"], "prompt": task["prompt"], "seed": seed,
                           "family":task.get('family'),"style":task.get('style'),
                           "audit_group":task.get('audit_group'),"difficulty":task.get('difficulty'),
                           "artifact": str(path), "sha256": file_hash(path), "judge": scored,
                           "activation_drift": drift, "seconds": seconds, "peak_vram_gb": vram,
                           "kl_base_to_candidate": kl,
                           "generation_digest": generation_id, "attempts": 1}
                    atomic_json(path.with_suffix(".evaluation.json"), row)
                    status.flush(latest_artifact=str(path),local_generations_done=completed+1,
                                 local_generations_planned=total_generations-eval_count)
                    if training and (not scored["valid"] or scored["score"] < c.get("failure_score_threshold", .999)):
                        record_failure(state, c["module"], task, row, run_id=run_id,
                                       limit=c.get("failure_memory_limit", 256))
                    rows.append(row)
                    rewards.append(reward)
                    completed += 1
                    status.update("training" if training else "evaluating", f"Score mesuré : {scored['score']:.4f}",
                                  judge_score=scored["score"], loss=-reward,
                                  progress_percent=min(94, 8 + 85 * completed / total_generations))
            average = sum(rewards) / len(rewards)
            if training:
                observations.append({"vector": vector.tolist(), "reward": average})
            return rows, average

        _, best_reward = evaluate(initial, train_tasks, [train_seed], "train/start", True)
        best = initial.clone()
        rng = torch.Generator().manual_seed(train_seed)
        training_history = remote_history
        for iteration in range(c["iterations"]):
            status.flush(epoch=iteration+1, epochs=c["iterations"], job_id=c.get("job_id"))
            noises, positive, negative = [], [], []
            for direction in range(c["directions"]):
                if c.get('coordinate_search'):
                    noise=torch.zeros_like(initial)
                    noise[(iteration*c['directions']+direction)%initial.numel()]=1
                else:noise = torch.randn(initial.shape, generator=rng)
                noises.append(noise)
                for sign, dest in ((1, positive), (-1, negative)):
                    vector = project(initial + sign * c["sigma"] * noise, c["trust_radius"])
                    _, reward = evaluate(vector, train_tasks, [train_seed],
                        f"train/i{iteration}_d{direction}_{'plus' if sign == 1 else 'minus'}", True)
                    dest.append(reward)
                    if reward > best_reward:
                        best, best_reward = vector.clone(), reward
            gradient = es_gradient(noises, positive, negative, c["sigma"])
            if c.get('coordinate_search'):
                gradient=sum(((p-n)/(2*c['sigma']))*direction for direction,p,n in zip(noises,positive,negative))
            initial = project(initial + c["learning_rate"] * gradient, c["trust_radius"])
            _, reward = evaluate(initial, train_tasks, [train_seed], f"train/i{iteration}_update", True)
            if reward > best_reward:
                best, best_reward = initial.clone(), reward
            training_history.append({"iteration": iteration, "positive": positive, "negative": negative,
                                     "reward": reward, "gradient_norm": float(gradient.norm())})
            atomic_json(run / "training.json", training_history)
            backend.adapter.set_vector(best)
            backend.adapter.save(run / "checkpoint.safetensors")
            # Keep only two epochs of training artifacts; audit files are retained.
            for old in (run / "train").glob("i*_"):
                pass
            if iteration >= 2:
                for old in (run / "train").glob(f"i{iteration-2}_*"):
                    shutil.rmtree(old)
        # Candidate fixed BEFORE any held-out generation. Audit never chooses it.
        backend.adapter.set_vector(best)
        if c.get("trainer") == "surrogate_es" and c["execution"] in {"hybrid", "kaggle"}:
            from .cloud import train_on_kaggle
            backend.adapter.set_vector(best)
            initial_file=run/"surrogate_initial.safetensors"
            backend.adapter.save(initial_file)
            atomic_json(run/"observations.json", observations)
            result_dir, _ = train_on_kaggle(c,run,[(initial_file,"initial.safetensors"),(run/"observations.json","observations.json")],{"surrogate_es":True},status,check)
            backend.adapter.load(result_dir/"candidate.safetensors")
            best=backend.adapter.vector()
            cloud_metrics=read_json(result_dir/"training_metrics.json")
            atomic_json(run/"training_metrics.json",cloud_metrics)
        candidate_path = run / "candidate.safetensors"
        backend.adapter.save(candidate_path)
        if torch.equal(best, champion_vector):
            status.update("evaluating", "Aucun gain d'entraînement : l'audit vérifiera le candidat inchangé.")
        base_rows, _ = evaluate(torch.zeros_like(best), eval_tasks, c["eval_seeds"], "audit/base")
        has_champion = registry or (c.get("initial_adapter") if not lineage else None)
        if has_champion:
            if registry:backend.adapter.load(registry['adapter'])
            champion_vector=backend.adapter.vector()
            champion_rows, _ = evaluate(champion_vector, eval_tasks, c["eval_seeds"], "audit/champion")
        else:
            champion_rows = base_rows
        parent_rows=None
        if lineage and lineage.get('parent_run_id') and lineage.get('parent_run_id')!=registry.get('run_id'):
            backend.adapter.load(c['initial_adapter'])
            parent_rows,_=evaluate(backend.adapter.vector(),eval_tasks,c['eval_seeds'],'audit/parent')
        backend.adapter.load(candidate_path)
        candidate_rows, _ = evaluate(backend.adapter.vector(), eval_tasks, c["eval_seeds"], "audit/candidate")
        if lineage and parent_rows is None:
            parent_rows=champion_rows if lineage.get('parent_run_id') else base_rows
        assert_unchanged(base_manifest)
        gate = promotion_gate(base_rows, champion_rows, candidate_rows, c, parent=parent_rows)
        if torch.equal(best, champion_vector):
            gate["eligible"] = False
            gate["reasons"].append("Poids identiques au champion : aucun apprentissage retenu")
        report = {"schema": 1, "run_id": run_id, "module": c["module"], "algorithm": "measured_reward_surrogate_ES" if c.get("trainer") == "surrogate_es" else "antithetic_ES_low_rank_weight_subspace",
                  "base_fingerprint": base_id, "candidate_sha256": file_hash(candidate_path),
                  "base": base_rows, "champion": champion_rows, "candidate": candidate_rows,
                  "gate": gate, "training": training_history, "hardware": hardware,
                  "generation": c["generation"], "config_digest": digest(c),
                  "cloud": cloud_metrics,
                  "elapsed_seconds": time.monotonic() - start, "lineage":lineage,"parent":parent_rows,
                  "limitations": ["Aucune garantie de zéro régression hors audit.",
                                  "Dérive d'activations et rayon des poids : garde-fous, pas une KL.",
                                  "Les corrections apprises concernent un sous-espace de faible rang."]}
        if c.get("trainer") == "surrogate_es":
            report["limitations"].append("Kaggle optimise les coefficients des corrections de poids à partir des récompenses mesurées sur le PC.")
        if c["module"] in {"image", "video"} and c.get("trainer") == "surrogate_es":
            report["limitations"].extend([
                "Kaggle ajuste une approximation de récompense sur les essais locaux, puis les coefficients des corrections de poids. Le générateur reste sur le PC.",
                "La VRAM ComfyUI est échantillonnée toutes les deux secondes par nvidia-smi ; un pic bref peut échapper à cette mesure.",
                "La dérive d’activations interne de ComfyUI n’est pas instrumentée ; seul le rayon des coefficients est limité."])
        atomic_json(run / "report.json", report)
        comparison = write_html(run, report)
        from .results import publish_shortcuts
        folder = publish_shortcuts(c["module"], run)
        report_id = digest(report)
        backend.close()
        del backend
        backend = None
        gc.collect()
        torch.cuda.empty_cache()
        status.update("awaiting_validation", "Comparaison prête : examiner puis valider ou rejeter.",
            progress_percent=100, waiting_validation=True, eligible=gate["eligible"],
            improvement=gate.get("gain_points"), report=comparison, report_digest=report_id,
            file_base=base_rows[0]["artifact"], file_new=candidate_rows[0]["artifact"], results_folder=folder,
            rejection_reasons=gate["reasons"])
        if c["stage"] == "remote":
            status.update("remote_complete", "Candidat Kaggle sauvegardé ; validation finale requise sur la RTX.", waiting_validation=False)
            return "REMOTE_DONE"
        if c["mode"] == "auto":
            decision = "ACCEPT" if gate["eligible"] else "REJECT"
        else:
            while True:
                check()
                message = read_json(run / "validation_signal.txt")
                if message:
                    if message.get("run_id") != run_id or message.get("report_digest") != report_id:
                        raise ValueError("Signal de validation périmé ou destiné à un autre rapport")
                    decision = message.get("decision")
                    if decision not in {"ACCEPT", "REJECT"}:
                        raise ValueError("Signal de validation invalide")
                    break
                time.sleep(0.5)
        check()
        if decision == "ACCEPT":
            assert_unchanged(base_manifest)
            saved = read_json(run / "report.json")
            if digest(saved) != report_id:
                raise RuntimeError("Le rapport a changé depuis la comparaison")
            record = promote(state, c["module"], run_id, candidate_path, report, registry.get("run_id"))
            if c["module"] == "image":
                from .photo_queue import mark_validated
                mark_validated(c, tasks, report, run)
            status.update("accepted", f"{record['name']} devient le champion. La base est intacte.",
                          waiting_validation=False, champion_version=record["version"])
        else:
            status.update("rejected", "Candidat rejeté. Comparaison conservée dans l'historique.", waiting_validation=False)
        return decision
    except (KeyboardInterrupt, Cancelled) as e:
        status.update("cancelled", str(e) or "Cycle arrêté à la demande", waiting_validation=False)
        return "STOP"
    except Exception as e:
        import traceback
        (run / "error.log").write_text(traceback.format_exc())
        status.update("error", f"{type(e).__name__} : {e}", waiting_validation=False,
                      error_log=str(run / "error.log"))
        return "ERROR"
    finally:
        heartbeat_stop.set()
        if backend:
            backend.close()
        from .resources import restore_inference_service
        try:
            restore_inference_service(inference_service_was_active, state)
        except Exception:
            # A failed restart is recorded by systemd; never hide the original
            # training result or exception behind cleanup.
            pass


def run_cycles(config):
    c = validate(config)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    allocator = os.environ.get("PYTORCH_CUDA_ALLOC_CONF", "")
    if "expandable_segments" not in allocator:
        allocator = (allocator + "," if allocator else "") + "expandable_segments:True"
    if "max_split_size_mb" not in allocator:
        allocator = (allocator + "," if allocator else "") + "max_split_size_mb:128"
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = allocator
    state = Path(c["state_dir"])
    state.mkdir(parents=True, exist_ok=True)
    rejected = 0
    with exclusive_lock(state / "cycle.lock"):
        for i in range(1, c["cycles"] + 1):
            # Fresh train/audit seeds per cycle, with the seed recorded in config.
            cycle_config = {**c, "seed": c["seed"] + (i - 1) * 100003}
            outcome = execute_cycle(cycle_config, i)
            if outcome in {"STOP", "ERROR"}:
                return 130 if outcome == "STOP" else 1
            rejected = rejected + 1 if outcome == "REJECT" else 0
            if rejected >= c["max_rejections"]:
                break
    return 0
