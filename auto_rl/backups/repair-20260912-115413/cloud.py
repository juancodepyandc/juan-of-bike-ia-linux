"""Private Kaggle jobs with bounded quota use and verified, run-scoped results."""
from __future__ import annotations
import base64
import io
import json
import os
import re
import shutil
import subprocess
import time
import uuid
import zipfile
from pathlib import Path
from .config import ROOT
from .storage import atomic_json, digest, file_hash, read_json

KAGGLE = ROOT / "cycle_app_venv/bin/kaggle"
BRIDGE = [str(ROOT / "cycle_app_venv/bin/python"), str(Path(__file__).with_name("kaggle_bridge.py"))]


class QuotaUnavailable(RuntimeError):
    pass


def quota_error(message):
    return bool(re.search(r"quota.*(exceed|exhaust|insufficient|reach)|not enough.*gpu|no.*gpu.*hours|gpu.*quota.*(0|limit)", message, re.I))


def command(argv, timeout=120):
    p = subprocess.run([str(a) for a in argv], capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        message = (p.stderr + "\n" + p.stdout)[-5000:]
        if quota_error(message):
            raise QuotaUnavailable(message)
        raise RuntimeError(message)
    return p.stdout


def quota():
    return json.loads(command([*BRIDGE, "quota"]))


def safe_extract(archive, destination, max_bytes=4 * 2 ** 30):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as z:
        if sum(i.file_size for i in z.infolist()) > max_bytes:
            raise ValueError("Archive trop volumineuse")
        for item in z.infolist():
            target = (destination / item.filename).resolve()
            mode = item.external_attr >> 16
            if not target.is_relative_to(destination) or (mode & 0o170000) == 0o120000:
                raise ValueError("Chemin ou lien interdit dans l'archive")
        z.extractall(destination)


def build_kernel(package_dir, kernel_dir, c, job_id, payload_hash):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(Path(package_dir).glob("*.py")):
            z.write(p, "auto_rl/" + p.name)
    blob = base64.b64encode(buffer.getvalue()).decode()
    try:
        hf_token = Path("/home/juan/.cache/huggingface/token").read_text().strip()
    except:
        hf_token = ""

    bootstrap = f'''# Aurora private training job. No base weights are overwritten.
import base64,io,os,sys,zipfile,subprocess
from pathlib import Path
root=Path('/kaggle/working/aurora_job')
root.mkdir(exist_ok=True)
zipfile.ZipFile(io.BytesIO(base64.b64decode({blob!r}))).extractall(root)
sys.path.insert(0,str(root))
os.environ['AURORA_KAGGLE_WORKER']='1'
os.environ['HF_HOME']='/tmp/aurora_hf'
os.environ['HF_TOKEN']={hf_token!r}
subprocess.run([sys.executable,'-m','pip','install','--quiet','--no-cache-dir','safetensors','huggingface_hub','numpy<3','pillow','transformers==4.57.6','accelerate','bitsandbytes','diffusers==0.39.0','sentencepiece'],check=True)
from auto_rl.cloud_worker import main
main({job_id!r},{payload_hash!r})
'''
    kernel_dir = Path(kernel_dir)
    kernel_dir.mkdir(parents=True, exist_ok=True)
    (kernel_dir / "train.py").write_text(bootstrap)
    metadata = {"id": c["kaggle_kernel"], "title": "Aurora Universal Trainer", "code_file": "train.py",
                "language": "python", "kernel_type": "script", "is_private": "true",
                "enable_gpu": "true", "enable_internet": "true", "machine_shape": "NvidiaTeslaT4",
                "dataset_sources": [c["kaggle_dataset"]], "competition_sources": [], "kernel_sources": []}
    atomic_json(kernel_dir / "kernel-metadata.json", metadata)


def train_on_kaggle(c, run, input_files, training_spec, status, check):
    run = Path(run)
    job_id = uuid.uuid4().hex
    status.update("cloud_preflight", "Lecture du quota Kaggle disponible…", training_location="kaggle")
    q = quota()
    status.flush(kaggle_quota=q)
    # Preserve a margin to export the final checkpoint before platform cutoff.
    available = int(q["remaining_seconds"] - 600)
    if available < 900:
        raise QuotaUnavailable("Quota GPU Kaggle insuffisant pour une session et sa sauvegarde")
    timeout = min(c["kaggle_timeout_seconds"], available)
    payload_dir = run / "kaggle_upload"
    payload_dir.mkdir()
    training_spec = {**training_spec, "job_id": job_id, "config": c,
                     "training_seconds": timeout - 600,
                     "epochs": 10000 if c["kaggle_max_session"] else c["kaggle_epochs"]}
    atomic_json(payload_dir / "spec.json", training_spec)
    with zipfile.ZipFile(payload_dir / "payload.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(payload_dir / "spec.json", "spec.json")
        for source, relative in input_files:
            relative = Path(relative)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Chemin d'envoi invalide")
            z.write(source, str(relative))
    # Only the explicit training payload is uploaded; no home directory or secrets.
    (payload_dir / "spec.json").unlink()
    atomic_json(payload_dir / "dataset-metadata.json", {"title": "Aurora RL Training Batches", "id": c["kaggle_dataset"],
                "licenses": [{"name": "other"}], "description": "Private synthetic training artifacts. Model and code licenses remain applicable."})
    marker = Path(c["state_dir"]) / "kaggle_dataset_created.json"
    status.update("uploading", "Envoi du vrai lot d'entraînement dans le dataset Kaggle privé…")
    if read_json(marker, {}).get("id") == c["kaggle_dataset"]:
        command([KAGGLE, "datasets", "version", "-p", payload_dir, "-m", "Aurora job " + job_id], timeout=600)
    else:
        try:
            command([KAGGLE, "datasets", "create", "-p", payload_dir], timeout=600)
        except RuntimeError as e:
            if not re.search(r"already exists|already been taken|409", str(e), re.I):
                raise
            command([KAGGLE, "datasets", "version", "-p", payload_dir, "-m", "Aurora job " + job_id], timeout=600)
        atomic_json(marker, {"id": c["kaggle_dataset"]})
    # Dataset processing is asynchronous. Wait for its actual READY status.
    until = time.monotonic() + 600
    while True:
        check()
        answer = command([KAGGLE, "datasets", "status", c["kaggle_dataset"]]).lower()
        if "ready" in answer:
            time.sleep(15) # Wait for Kaggle backend to synchronize datasets with kernels
            break
        if "error" in answer or time.monotonic() > until:
            raise RuntimeError("Dataset Kaggle non disponible : " + answer)
        time.sleep(5)
    kernel_dir = run / "kaggle_kernel"
    build_kernel(Path(__file__).parent, kernel_dir, c, job_id, file_hash(payload_dir / "payload.zip"))
    previous = json.loads(command([*BRIDGE, "status", c["kaggle_kernel"]]))
    if previous["status"] in {"running", "queued"}:
        raise RuntimeError("Un entraînement Kaggle est déjà actif sur ce kernel")
    status.update("cloud_starting", "Lancement de l'entraînement réel sur Kaggle…", job_id=job_id)
    response = command([*BRIDGE, "push", kernel_dir, str(timeout)])
    matches = [line[len("AURORA_PUSH "):] for line in response.splitlines() if line.startswith("AURORA_PUSH ")]
    if not matches:
        raise RuntimeError("Kaggle n'a pas retourné d'identifiant de version")
    pushed = json.loads(matches[-1])
    if pushed.get("error"):
        if quota_error(pushed["error"]):
            raise QuotaUnavailable(pushed["error"])
        raise RuntimeError(pushed["error"])
    pinned = f"{c['kaggle_kernel']}/{pushed['version']}"
    atomic_json(run / "kaggle_job.json", {**pushed, "job_id": job_id, "pinned": pinned, "timeout": timeout})
    status.update("cloud_training", "Kaggle : entraînement en file d'attente…", kaggle_url=pushed["url"], job_id=job_id)
    log_path = run / "kaggle_live.log"
    with log_path.open("w") as logs:
        stream = subprocess.Popen([str(KAGGLE), "kernels", "logs", pinned, "--follow"], stdout=logs, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout + 900
        try:
            offset, failures = 0, 0
            while True:
                check()
                try:
                    remote = json.loads(command([*BRIDGE, "status", pinned]))
                    failures = 0
                except RuntimeError:
                    failures += 1
                    if failures >= 5:
                        raise
                    time.sleep(5)
                    continue
                with log_path.open() as log:
                    log.seek(offset)
                    for line in log:
                        token = line.find("AURORA_STATUS ")
                        if token >= 0:
                            try:
                                metrics = json.loads(line[token + len("AURORA_STATUS "):])
                                if metrics.get("job_id") == job_id:
                                    status.update("cloud_training", metrics.get("status", "Entraînement Kaggle"),
                                        **{k: metrics[k] for k in ("epoch", "epochs", "loss", "judge_score", "progress_percent") if k in metrics})
                            except ValueError:
                                pass
                    offset = log.tell()
                if remote["status"] not in {"running", "queued"}:
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("Délai Kaggle dépassé")
                for _ in range(c["kaggle_poll_seconds"]):
                    check()
                    time.sleep(1)
        except BaseException:
            try:
                command([*BRIDGE, "cancel", pinned], timeout=30)
            except Exception as e:
                status.flush(remote_stop_error=str(e), kaggle_url=pushed["url"])
            raise
        finally:
            stream.terminate()
            try:
                stream.wait(timeout=5)
            except subprocess.TimeoutExpired:
                stream.kill()
    status.update("downloading", "Récupération et contrôle des poids entraînés sur Kaggle…")
    output_dir = run / "kaggle_download"
    output_dir.mkdir()
    command([KAGGLE, "kernels", "output", pinned, "-p", output_dir,
             "--file-pattern", r"aurora_result\.zip$", "--force"], timeout=600)
    archives = list(output_dir.rglob("aurora_result.zip"))
    if len(archives) != 1:
        if quota_error(remote.get("failure", "")):
            raise QuotaUnavailable(remote["failure"])
        raise RuntimeError("Kaggle n'a produit aucun résultat exploitable. " + remote.get("failure", "") + f" Journal : {log_path}")
    result_dir = run / "cloud_result"
    safe_extract(archives[0], result_dir)
    manifest = read_json(result_dir / "result.json")
    if not manifest or manifest.get("job_id") != job_id or manifest.get("spec_digest") != digest(training_spec):
        raise ValueError("Résultat Kaggle périmé ou destiné à un autre cycle")
    for name, sha in manifest["files"].items():
        path = (result_dir / name).resolve()
        if not path.is_relative_to(result_dir.resolve()) or file_hash(path) != sha:
            raise ValueError("Empreinte du résultat Kaggle incorrecte")
    if manifest.get("error"):
        raise RuntimeError("Entraînement Kaggle : " + manifest["error"])
    return result_dir, manifest
