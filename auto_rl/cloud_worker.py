"""Kaggle entry point. Exports weights and measured metrics, never promotes."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path
from .cloud import safe_extract
from .storage import atomic_json, digest, file_hash


def main(job_id, payload_hash):
    work = Path("/kaggle/working")
    root = Path("/tmp/aurora_inputs")
    out = work / "aurora_export"
    out.mkdir(exist_ok=True)
    spec = None
    error = None
    try:
        root.mkdir(parents=True, exist_ok=True)
        matches = [p for p in Path("/kaggle/input").rglob("payload.bin") if file_hash(p) == payload_hash]
        if len(matches) != 1:
            raise RuntimeError(f"Lot absent, périmé ou corrompu : {len(matches)} fichiers correspondent à l'empreinte attendue")
        safe_extract(matches[0], root)
        spec = json.loads((root / "spec.json").read_text())
        if spec.get("job_id") != job_id:
            raise ValueError("Le lot appartient à un autre cycle")
        if spec.get("probe"):
            import torch
            atomic_json(out / "probe.json", {"cuda": torch.cuda.is_available(), "torch": torch.__version__,
                        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                        "job_id": job_id, "payload_verified": True})
            if not torch.cuda.is_available():
                raise RuntimeError("Kaggle n'a pas alloué de GPU")
            return
        c = spec["config"]
        # Parent weights are already pinned in initial.safetensors. Never resolve
        # a local development registry from the fresh Kaggle filesystem.
        c.pop('training_start',None)
        os.environ["HF_HUB_OFFLINE"] = "0"
        os.environ["TRANSFORMERS_OFFLINE"] = "0"
        from huggingface_hub import hf_hub_download, snapshot_download
        cache = "/tmp/aurora_hf/hub"
        started = time.monotonic()
        def callback(row):
            payload = {**row, "job_id": job_id, "epochs": spec["epochs"],
                       "status": f"Kaggle · époque {row['epoch']} · loss {row['loss']:.5f}",
                       "progress_percent": min(94, 95*row["epoch"]/spec["epochs"])}
            if 'autonomous_elapsed_seconds' in row:
                payload['progress_percent']=min(94,95*row['autonomous_elapsed_seconds']/c.get('training_budget_seconds',1800))
            if row.get('diagnosis'):
                payload['status']='Correction autonome : '+row['diagnosis']['explanation']
            print("AURORA_STATUS " + json.dumps(payload), flush=True)
        def training_seconds(default):
            # A radical Kaggle run uses the whole reserved session after the
            # export margin. Standard runs keep their explicit budget.
            if c.get('kaggle_max_session'):
                return max(1, spec['training_seconds']-(time.monotonic()-started))
            return min(c.get('training_budget_seconds', default),
                       max(1, spec['training_seconds']-(time.monotonic()-started)))
        if spec.get("surrogate_es"):
            from .surrogate import optimize
            optimize(c, root, out, callback)
            return
        if c["trainer"] == "preference_lora":
            if c["module"] == "3d":
                source_zip = root / "trellis_dense_source.zip"
                source_dir = root / "trellis_dense_source"
                if source_zip.is_file():
                    safe_extract(source_zip, root / "trellis_source", max_bytes=20*2**20)
                elif source_dir.is_dir():
                    shutil.copytree(source_dir, root / "trellis_source", dirs_exist_ok=True)
                else:
                    raise FileNotFoundError("Source Trellis introuvable dans le dataset Kaggle")
                c["trellis_root"] = str(root / "trellis_source")
                name = "ckpts/ss_flow_img_dit_1_3B_64_bf16"
                model_config = hf_hub_download(c["models"]["3d"], name + ".json", revision=spec["model_revision"], cache_dir=cache)
                hf_hub_download(c["models"]["3d"], name + ".safetensors", revision=spec["model_revision"], cache_dir=cache)
                c["training_model_path"] = model_config[:-5]
            else:
                c["training_model_path"] = snapshot_download(c["models"][c["module"]], revision=spec["model_revision"], cache_dir=cache,
                    allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model"])
            if (root / "preferences.json").exists():
                records = json.loads((root / "preferences.json").read_text())
                if c.get('kaggle_parallel_trials'):
                    from .parallel_preferences import train
                    train(c,records,root,out,training_seconds(1800),callback)
                    return
                if c.get('autonomous_3d'):
                    from .autonomous_train import supervise
                    supervise(c,records,root,out,training_seconds(1800),callback)
                    return
                from .preference_train import train_preferences
                train_preferences(c, records, root, out, spec["epochs"], training_seconds(spec['training_seconds']), callback)
            else:
                from .config import STATE
                from .preference_cycle import execute_preference_cycle
                paths = {}
                for key, model in spec.get("model_revisions", {}).items():
                    if key == "image" and c["module"] == "3d":
                        continue
                    patterns = ["*.json", "*.txt", "*.model", "*.safetensors", "*.bin", "*.pth", "voices/*.pt"]
                    paths[key] = snapshot_download(c["models"][key], revision=model, cache_dir=cache, allow_patterns=patterns)
                    c["models"][key] = paths[key]
                c.update(state_dir=str(STATE), stage="remote", execution="local",
                         max_hours=max(0.01, min(c.get('training_budget_seconds',spec['training_seconds']),spec["training_seconds"]-(time.monotonic()-started))/3600),
                         minimum_free_gb=2, job_id=job_id, prepared_tasks=str(root / "tasks.json"),
                         initial_adapter=str(root / "initial.safetensors"))
                execute_preference_cycle(c)
                from .storage import read_json
                s = read_json(STATE / "status.json")
                run = STATE / "runs" / s["run_id"]
                if (run / "candidate.safetensors").is_file():
                    shutil.copy2(run / "candidate.safetensors", out / "candidate.safetensors")
                for name in ("training.json", "report.json", "training_metrics.json"):
                    if (run / name).is_file():
                        shutil.copy2(run / name, out / name)
                shutil.copytree(run, out / "run_export", dirs_exist_ok=True)
        else:
            from .config import STATE
            from .runner import execute_cycle
            if c["module"] == "audio":
                subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-cache-dir",
                                "kokoro", "soundfile", "faster-whisper"], check=True)
                subprocess.run(["apt-get", "update", "-qq"], check=True)
                subprocess.run(["apt-get", "install", "-y", "-qq", "espeak-ng"], check=True)
            paths = {}
            for key, model in spec["model_revisions"].items():
                patterns = ["*.json", "*.txt", "*.model", "*.safetensors", "*.bin", "*.pth", "voices/*.pt"]
                if key == "image":
                    patterns = ["*.json", "*.txt", "*.fp16.safetensors"]
                paths[key] = snapshot_download(c["models"][key], revision=model, cache_dir=cache, allow_patterns=patterns)
                c["models"][key] = paths[key]
            c.update(state_dir=str(STATE), stage="remote", execution="local", iterations=spec["epochs"],
                     max_hours=max(0.01, min(c.get('training_budget_seconds',spec['training_seconds']),spec["training_seconds"]-(time.monotonic()-started))/3600),
                     minimum_free_gb=2, job_id=job_id, prepared_tasks=str(root / "tasks.json"),
                     initial_adapter=str(root / "initial.safetensors"))
            if c["module"] == "image":
                c["aesthetic_weights"] = str(root / "aesthetic.safetensors")
            result = execute_cycle(c)
            from .storage import read_json
            s = read_json(STATE / "status.json")
            run = STATE / "runs" / s["run_id"]
            candidate = run / "candidate.safetensors"
            if not candidate.is_file():
                candidate = run / "checkpoint.safetensors"
            if not candidate.is_file():
                raise RuntimeError(s["status"])
            shutil.copy2(candidate, out / "candidate.safetensors")
            for name in ("training.json", "report.json"):
                if (run / name).is_file():
                    shutil.copy2(run / name, out / name)
            history = read_json(run / "training.json", [])
            atomic_json(out / "training_metrics.json", {"completed_epochs": len(history), "requested_epochs": spec["epochs"],
                        "elapsed_seconds":time.monotonic()-started,
                        "outcome": result, "algorithm": "antithetic_ES_low_rank_weight_subspace"})
            shutil.copytree(run, out / "run_export", dirs_exist_ok=True)
    except BaseException as e:
        error = f"{type(e).__name__}: {e}"
        (out / "error.log").write_text(traceback.format_exc())
        print(error, flush=True)
    finally:
        # spec is hashed as originally submitted, not the worker's rewritten paths.
        original_spec = json.loads((root / "spec.json").read_text()) if (root / "spec.json").is_file() else None
        manifest = {"job_id": job_id, "spec_digest": digest(original_spec), "error": error,
                    "files": {str(p.relative_to(out)): file_hash(p) for p in out.rglob("*") if p.is_file() and p.name != "result.json"}}
        atomic_json(out / "result.json", manifest)
        temporary = work / "aurora_result.tmp.zip"
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as z:
            for p in out.rglob("*"):
                if p.is_file():
                    z.write(p, str(p.relative_to(out)))
        os.replace(temporary, work / "aurora_result.zip")
        print("AURORA_RESULT " + json.dumps(manifest), flush=True)
