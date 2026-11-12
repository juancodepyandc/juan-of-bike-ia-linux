"""Run professor roles on private Kaggle GPU kernels and bring the evidence back.

Two kernels, two machines: the examiner (``diagnose`` and ``verify``) and the
trainer (``train``). A kernel receives the other one's output as a read-only
input, so the trainer sees ``diagnosis.json`` and the examiner sees the adapter;
nothing else crosses. Sources are embedded and hash-checked; credentials never
appear in a kernel.

    python -m auto_rl.professor.kaggle_runner launch --owner USER --role diagnose --student qwen2.5:7b
    python -m auto_rl.professor.kaggle_runner wait   --owner USER --role diagnose
    python -m auto_rl.professor.kaggle_runner fetch  --owner USER --role diagnose --output DIR
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import inspect
import json
import re
import time
from pathlib import Path

from ..source_bundle import build_bundle, extract_bundle
from .records import atomic_json, file_hash

ROOT = Path(__file__).resolve().parents[2]
# The launcher travels too: the Colab trainer imports it from the extracted sources to publish its adapter
# and start the examiner, and the bundle it rebuilds there must be the one it was extracted from.
BUNDLE_MODULES = ["auto_rl.professor.run", "auto_rl.professor.train", "auto_rl.professor.kaggle_runner", "auto_rl.source_bundle"]
KERNELS = {"diagnose": ("aurora-professeur-examinateur", "Aurora Professeur Examinateur"),
           "verify": ("aurora-professeur-examinateur", "Aurora Professeur Examinateur"),
           "train": ("aurora-professeur-entraineur", "Aurora Professeur Entraineur")}


def kernel_name(role, student, cycle=0):
    """``(slug, title)`` of one student's kernel: each student has its own examiner and trainer,
    so two students can be examined or trained at the same time without sharing a machine.

    A later cycle has its own pair (suffix ``-cN``): the verdict and the files of an earlier cycle
    stay downloadable after the next one has run, so a promoted delivery is never overwritten.
    """
    slug, title = KERNELS[role]
    words = [re.sub(r"[^a-z0-9]", "", part) for part in re.split(r"[:/\s]+", student.lower())]
    words = [word for word in words if word] + ([f"c{int(cycle)}"] if cycle else [])
    return slug + "-" + "-".join(words), title + " " + " ".join(word.capitalize() for word in words)

#: Minimum library versions; a newer preinstalled version is kept as is.
REQUIREMENTS = {"transformers": "4.57.0", "peft": "0.13.0", "bitsandbytes": "0.43.0", "accelerate": "0.34.0", "datasets": "3.0.0"}

_BOOTSTRAP = '''# Aurora professor - generated, private. Sources are embedded and hash-checked; no credential is stored here.
import base64, hashlib, io, json, os, re, shutil, stat, subprocess, sys, time, zipfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path, PurePosixPath

{extract}

OPTIONS = {options}
SOURCE_SHA256 = {digest!r}
SOURCES = base64.b64decode({blob!r})
BASE = Path({base!r})
WORK = BASE / "aurora_professor"
WORK.mkdir(parents=True, exist_ok=True)
# Sources live outside the output folder: only evidence is published as kernel output.
REPO = extract_bundle(SOURCES, Path({sources!r}) / SOURCE_SHA256[:16], SOURCE_SHA256)
print("AURORA_BOOT " + json.dumps({{"sources": SOURCE_SHA256, "role": OPTIONS["role"]}}), flush=True)


def numbers(text):
    return tuple(int(part) for part in re.findall(r"\\d+", text)[:3])


missing = []
for name, minimum in {requirements!r}.items():
    try:
        current = version(name)
    except PackageNotFoundError:
        current = None
    if current is None or numbers(current) < numbers(minimum):
        missing.append(name + ">=" + minimum)
if missing:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", *missing], check=True, timeout=900)

env = dict(os.environ, PYTHONPATH=str(REPO), AURORA_PROFESSOR_ALLOW_CODE_EXECUTION="1", HF_HOME={hf_home!r},
           TOKENIZERS_PARALLELISM="false", HF_HUB_DISABLE_PROGRESS_BARS="1", PYTHONUNBUFFERED="1")
try:                                        # optional, only for gated base models
    from kaggle_secrets import UserSecretsClient
    env["HF_TOKEN"] = UserSecretsClient().get_secret("HF_TOKEN")
except Exception:
    pass

argv = [sys.executable, "-m", "auto_rl.professor.run", OPTIONS["role"], "--student", OPTIONS["student"],
        "--profile", OPTIONS["profile"], "--cycle", str(OPTIONS["cycle"]), "--work", str(WORK),
        "--budget-minutes", str(OPTIONS["budget_minutes"])]
if OPTIONS.get("modules"):
    argv += ["--modules", OPTIONS["modules"]]
if OPTIONS.get("skills"):
    argv += ["--skills", OPTIONS["skills"]]
for key, value in (OPTIONS.get("overrides") or {{}}).items():
    argv += ["--" + key.replace("_", "-"), str(value)]
inputs = Path({inputs!r})
# An adapter kept under ``init_adapter`` is the one a continued training started from, never the candidate.
adapters = sorted(inputs.rglob("adapter_config.json")) if inputs.is_dir() else []
candidates = [path for path in adapters if path.parent.name != "init_adapter"]
earlier = [path for path in adapters if path.parent.name == "init_adapter"]
embedded = OPTIONS.pop("diagnosis_b64", None)       # a diagnosis carried by the launcher (retraining from the base)
if OPTIONS["role"] == "train":
    if embedded:
        raw = base64.b64decode(embedded)
        OPTIONS["diagnosis_sha256"] = hashlib.sha256(raw).hexdigest()
        carried = Path({hf_home!r}).parent / "aurora_launcher_inputs" / "diagnosis.json"
        carried.parent.mkdir(parents=True, exist_ok=True)
        carried.write_bytes(raw)
        found = [carried]
    else:
        wanted = "diagnosis_next_*.json" if OPTIONS.get("continue") else "diagnosis.json"
        found = sorted(inputs.rglob(wanted)) if inputs.is_dir() else []
        if len(found) != 1:
            raise SystemExit("Expected exactly one %s from the examiner, found %d" % (wanted, len(found)))
    argv += ["--diagnosis", str(found[0])]
    if OPTIONS.get("continue"):
        if len(candidates) != 1:
            raise SystemExit("Expected exactly one adapter to continue, found %d" % len(candidates))
        argv += ["--init-adapter", str(candidates[0].parent)]
if OPTIONS["role"] == "verify":
    if len(candidates) != 1:
        raise SystemExit("Expected exactly one adapter from the trainer, found %d" % len(candidates))
    adapter = WORK / "training" / "adapter"
    if adapter.exists():
        shutil.rmtree(adapter)
    shutil.copytree(candidates[0].parent, adapter)
    for receipt in (candidates[0].parent.parent / "train_receipt.json", candidates[0].parent / "train_receipt.json"):
        if receipt.is_file():                # kernel output layout, then flat dataset layout
            shutil.copy2(receipt, adapter.parent / "train_receipt.json")
            break
    argv += ["--adapter", str(adapter)]
    flat = sorted(inputs.rglob("init_adapter_config.json")) if inputs.is_dir() else []
    before = WORK / "training" / "init_adapter"
    if before.exists():
        shutil.rmtree(before)
    if len(earlier) == 1:                    # same unseen items for the adapter this candidate continues
        shutil.copytree(earlier[0].parent, before)
    elif len(flat) == 1:                     # flat dataset layout: files prefixed with ``init_``
        before.mkdir(parents=True)
        for path in sorted(flat[0].parent.glob("init_adapter_*")):
            shutil.copy2(path, before / path.name[len("init_"):])
    if before.is_dir():
        argv += ["--previous-adapter", str(before)]

started = time.time()
# Lines are relayed one by one so a notebook cell shows progress, not only a script log.
process = subprocess.Popen(argv, env=env, cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
beat = time.time()
with (WORK / "run.log").open("a", encoding="utf-8") as log:
    for line in process.stdout:
        log.write(line)
        log.flush()
        if line.startswith("AURORA_") or "Error" in line or "Traceback" in line or line.startswith("  File "):
            print(line, end="", flush=True)
        elif time.time() - beat > 120:           # a quiet phase (downloads, model load) stays observable
            beat = time.time()
            print("AURORA_HEARTBEAT " + json.dumps({{"elapsed_seconds": round(beat - started), "last": line.strip()[-160:]}}), flush=True)
code = process.wait()
if code:
    print("".join((WORK / "run.log").read_text(encoding="utf-8", errors="replace").splitlines(True)[-60:]), flush=True)
files = {{}}
for path in sorted(WORK.rglob("*")):
    if path.is_file():
        sha = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1 << 22), b""):
                sha.update(block)
        files[path.relative_to(WORK).as_posix()] = sha.hexdigest()
disk = {{p: shutil.disk_usage(p).free // 2 ** 30 for p in ("/tmp", str(BASE)) if os.path.isdir(p)}}
manifest = {{"kind": "aurora_professor_remote_run", "options": OPTIONS, "sources_sha256": SOURCE_SHA256, "exit_code": code,
            "elapsed_seconds": round(time.time() - started, 1), "free_disk_gb": disk, "files": files}}
(BASE / "aurora_professor_manifest.json").write_text(json.dumps(manifest, indent=2))
print("AURORA_DONE " + json.dumps({{k: manifest[k] for k in ("exit_code", "elapsed_seconds", "free_disk_gb")}}), flush=True)
if code:
    raise SystemExit(code)
'''


def bundle():
    """Embedded, hash-pinned sources of the professor package (no weights, no credentials)."""
    blob, manifest = build_bundle(ROOT, BUNDLE_MODULES)
    return blob, hashlib.sha256(blob).hexdigest(), manifest


def script(options=None, *, base="/kaggle/working", inputs="/kaggle/input", hf_home="/tmp/aurora_hf",
           sources="/tmp/aurora_sources"):
    """Self-contained runner for one role; the same text runs in a Kaggle kernel or a notebook cell.

    Without ``options`` the runner reads a ``AURORA_OPTIONS`` dict defined by an
    earlier notebook cell, so the person running the notebook sees every setting.
    """
    blob, digest, _ = bundle()
    chosen = "dict(AURORA_OPTIONS)" if options is None else "json.loads(%r)" % json.dumps(options, ensure_ascii=False)
    return _BOOTSTRAP.format(extract=inspect.getsource(extract_bundle), options=chosen,
                             digest=digest, blob=base64.b64encode(blob).decode(), base=base, inputs=inputs,
                             hf_home=hf_home, sources=sources, requirements=REQUIREMENTS)


def write_kernel(folder, owner, role, *, student, profile="standard", modules=None, cycle=0, budget_minutes=240,
                 overrides=None, gpu=True, dataset_sources=(), skills=None, continue_adapter=False, diagnosis=None):
    """Create the kernel folder (script + metadata). Nothing is uploaded by this function.

    ``continue_adapter`` (trainer only) continues the adapter of the previous cycle with the examiner's
    ``diagnosis_next_N.json``; both are read from the examiner's last output, or from ``dataset_sources``.
    ``diagnosis`` (trainer only) embeds a diagnosis file in the kernel: a later cycle that trains a NEW
    adapter from the base model needs the base diagnosis, which the examiner's last output no longer holds.
    """
    slug, title = kernel_name(role, student, cycle)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    options = {"role": role, "student": student, "profile": profile, "modules": modules, "skills": skills, "cycle": cycle,
               "budget_minutes": budget_minutes, "overrides": overrides or {}}
    if role == "train" and continue_adapter:
        if not cycle:
            raise ValueError("A first cycle has no adapter to continue")
        options["continue"] = True
    if role == "train" and diagnosis:
        if continue_adapter:
            raise ValueError("A continued cycle reads the examiner's diagnosis of the candidate, not an embedded one")
        options["diagnosis_b64"] = base64.b64encode(Path(diagnosis).read_bytes()).decode()
    (folder / "kernel.py").write_text(script(options), encoding="utf-8")
    options = {key: value for key, value in options.items() if key != "diagnosis_b64"}      # launch.json stays small
    sources = []
    if role == "train" and diagnosis:
        sources = []
    elif role == "train" and not dataset_sources:
        # A continued cycle reads the previous examiner (its verdict's diagnosis and the adapter it examined).
        sources = [f"{owner}/{kernel_name('diagnose', student, cycle - 1 if continue_adapter else cycle)[0]}"]
    elif role == "verify" and not dataset_sources:
        sources = [f"{owner}/{kernel_name('train', student, cycle)[0]}"]
    metadata = {"id": f"{owner}/{slug}", "title": title, "code_file": "kernel.py", "language": "python",
                "kernel_type": "script", "is_private": True, "enable_gpu": bool(gpu), "enable_internet": True,
                "machine_shape": "NvidiaTeslaT4" if gpu else "", "dataset_sources": list(dataset_sources),
                "competition_sources": [], "kernel_sources": sources, "model_sources": []}
    atomic_json(folder / "kernel-metadata.json", metadata)
    atomic_json(folder / "launch.json", {"options": options, "sources_sha256": bundle()[1],
                                         "kernel_sha256": file_hash(folder / "kernel.py")})
    return metadata


def _api():
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    return api


def whoami():
    """Kaggle account of the configured credential (the owner of the private kernels)."""
    name = _api().config_values.get("username")
    if not name:
        raise RuntimeError("The Kaggle credential does not identify an account")
    return name


def launch(folder, *, timeout_seconds):
    """Upload and start the kernel. This spends Kaggle GPU quota: call it deliberately."""
    answer = _api().kernels_push(str(folder), timeout=str(int(timeout_seconds)))
    if getattr(answer, "error", None):
        raise RuntimeError(str(answer.error))
    return {"ref": answer.ref, "url": answer.url, "version": answer.version_number}


def state(reference):
    answer = _api().kernels_status(reference)
    return {"status": str(answer.status).split(".")[-1].lower(), "failure": answer.failure_message}


def logs(reference, *, markers=("AURORA_", "Error", "Traceback"), tail=40, window_seconds=25):
    """Last marked lines of a kernel log (status lines and failures), newest last.

    A running session only exposes a live stream, so it is read for a bounded
    window in a helper thread; a finished session returns its stored log.
    """
    import threading
    api, collected = _api(), []

    def read():
        try:
            for event in api.kernels_logs_stream(reference):
                collected.append(str(event.get("data", "")))
        except Exception as exc:                 # a quiet or closed stream is not a kernel failure
            collected.append(f"(log stream ended: {type(exc).__name__})")
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    reader.join(window_seconds)
    text = "\n".join(collected) or (api.kernels_logs(reference) or "")
    lines = [part.strip()[:400] for part in text.splitlines() if any(marker in part for marker in markers)]
    return lines[-tail:]


def quota():
    """Remaining weekly GPU seconds as reported by Kaggle."""
    gpu = _api().quota_view().gpu_quota
    return {"remaining_seconds": max(0, (gpu.total_time_allowed - gpu.time_used - gpu.time_reserved).total_seconds()),
            "used_seconds": gpu.time_used.total_seconds()}


def publish_adapter(owner, training_folder, *, slug="aurora-professeur-adaptateurs", note="adapter", student=None, extra=()):
    """Upload a trained adapter as a PRIVATE Kaggle dataset a kernel can mount (Colab path, continued cycles).

    Files are stored flat: an adapter is a configuration and one weight file. ``student`` gives each
    student its own dataset, so two students never read each other's latest version; ``extra`` adds
    files such as the examiner's ``diagnosis_next_N.json``.
    """
    import tempfile
    training_folder = Path(training_folder)
    title = "Aurora Professeur Adaptateurs"
    if student:
        words = kernel_name("train", student)[0].removeprefix(KERNELS["train"][0])
        slug, title = slug + words, title + words.replace("-", " ")
    with tempfile.TemporaryDirectory(prefix="aurora_adapter_") as temporary:
        staging = Path(temporary)
        names = []
        for path in sorted((training_folder / "adapter").iterdir()):
            if path.is_file() and path.suffix in {".json", ".safetensors"}:
                (staging / path.name).write_bytes(path.read_bytes())
                names.append(path.name)
        for added in ("train_receipt.json",):
            if (training_folder / added).is_file():
                (staging / added).write_bytes((training_folder / added).read_bytes())
        for path in sorted((training_folder / "init_adapter").glob("adapter_*")):
            if path.is_file() and path.suffix in {".json", ".safetensors"}:      # the adapter this one continues
                (staging / ("init_" + path.name)).write_bytes(path.read_bytes())
        for added in extra:
            (staging / Path(added).name).write_bytes(Path(added).read_bytes())
        if "adapter_config.json" not in names:
            raise ValueError("No adapter to publish in " + str(training_folder))
        atomic_json(staging / "dataset-metadata.json", {"title": title, "id": f"{owner}/{slug}",
                                                        "licenses": [{"name": "other"}]})
        api = _api()
        try:
            api.dataset_status(f"{owner}/{slug}")
            api.dataset_create_version(str(staging), version_notes=note, quiet=True)
        except Exception:
            api.dataset_create_new(str(staging), public=False, quiet=True)
    return f"{owner}/{slug}"


def wait(reference, *, poll_seconds=60, timeout_seconds=12 * 3600, report=print):
    """Poll until the kernel leaves the queue/run states; returns the final state."""
    deadline, last = time.monotonic() + timeout_seconds, None
    while True:
        current = state(reference)
        if current["status"] != last:
            report(json.dumps({"kernel": reference, **current}))
            last = current["status"]
        if current["status"] not in {"queued", "running"}:
            return current
        if time.monotonic() > deadline:
            raise TimeoutError(f"{reference} still {current['status']}")
        time.sleep(poll_seconds)


def fetch(reference, output):
    """Download the kernel output and check every file against the remote manifest."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    _api().kernels_output(reference, path=str(output), force=True, quiet=True)
    manifest_path = output / "aurora_professor_manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("The kernel produced no manifest: inspect its log before trusting any file")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mismatched = [name for name, sha in manifest["files"].items()
                  if not (output / "aurora_professor" / name).is_file() or file_hash(output / "aurora_professor" / name) != sha]
    if mismatched:
        raise RuntimeError(f"{len(mismatched)} downloaded files differ from the remote manifest, e.g. {mismatched[:3]}")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("build", "launch", "wait", "fetch", "status", "logs", "quota", "publish"))
    parser.add_argument("--owner")
    parser.add_argument("--role", choices=sorted(KERNELS))
    parser.add_argument("--student", default="qwen2.5:7b")
    parser.add_argument("--profile", default="standard")
    parser.add_argument("--modules")
    parser.add_argument("--skills")
    parser.add_argument("--cycle", type=int, default=0)
    parser.add_argument("--budget-minutes", type=float, default=240)
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cpu", action="store_true", help="Rehearsal without GPU quota")
    parser.add_argument("--dataset-source", action="append", default=[], help="owner/slug holding an adapter (Colab path)")
    parser.add_argument("--override", action="append", default=[], help="name=value passed to the role, e.g. curriculum=4000")
    parser.add_argument("--continue-adapter", action="store_true",
                        help="train: continue the previous cycle's adapter with the examiner's diagnosis_next file")
    parser.add_argument("--diagnosis", type=Path, help="train: embed this diagnosis (a new adapter from the base at a later cycle)")
    parser.add_argument("--training", type=Path, help="publish: folder holding adapter/ (a fetched training folder)")
    parser.add_argument("--extra", action="append", default=[], type=Path, help="publish: extra file, e.g. diagnosis_next_0.json")
    args = parser.parse_args(argv)
    if args.command == "quota":
        print(json.dumps(quota()))
        return 0
    if args.command == "publish":
        if not args.owner or not args.training:
            parser.error("publish requires --owner and --training")
        print(json.dumps({"dataset": publish_adapter(args.owner, args.training, student=args.student, extra=args.extra,
                                                     note=f"cycle {args.cycle} {args.student}")}))
        return 0
    if not args.owner or not args.role:
        parser.error("--owner and --role are required")
    slug = kernel_name(args.role, args.student, args.cycle)[0]
    reference = f"{args.owner}/{slug}"
    folder = args.folder or ROOT / "Outputs" / "auto_rl" / "professor" / "kernels" / slug / args.role
    if args.command in ("build", "launch"):
        overrides = dict(pair.split("=", 1) for pair in args.override)
        metadata = write_kernel(folder, args.owner, args.role, student=args.student, profile=args.profile, modules=args.modules,
                                cycle=args.cycle, budget_minutes=args.budget_minutes, overrides=overrides, gpu=not args.cpu,
                                dataset_sources=args.dataset_source, skills=args.skills,
                                continue_adapter=args.continue_adapter, diagnosis=args.diagnosis)
        result = {"folder": str(folder), "kernel": metadata["id"], "gpu": metadata["enable_gpu"]}
        if args.command == "launch":
            result.update(launch(folder, timeout_seconds=args.budget_minutes * 60 + 1500))
        print(json.dumps(result))
    elif args.command == "status":
        print(json.dumps(state(reference)))
    elif args.command == "logs":
        print("\n".join(logs(reference)))
    elif args.command == "wait":
        print(json.dumps(wait(reference)))
    else:
        if args.output is None:
            parser.error("fetch requires --output")
        manifest = fetch(reference, args.output)
        print(json.dumps({"exit_code": manifest["exit_code"], "files": len(manifest["files"]), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
