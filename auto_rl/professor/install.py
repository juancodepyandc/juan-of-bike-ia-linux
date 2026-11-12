"""Install a verified reinforced model in Ollama on the PC, then make it the default.

    python -m auto_rl.professor.install status
    python -m auto_rl.professor.install deliver  --owner COMPTE --student qwen2.5:7b --activate   # fetch, install, examine, activate
    python -m auto_rl.professor.install install  --delivery DIR      # side by side, then examined through Ollama
    python -m auto_rl.professor.install activate --tag qwen2.5:7b    # the application's tag now serves the reinforced weights
    python -m auto_rl.professor.install rollback --tag qwen2.5:7b

Three gates stand between a training run and the application:

1. the examiner's verdict must be ``promote`` for a model the application calls;
2. the delivered files must match the hashes the examiner recorded;
3. the model must win the same paired exam again *as served by Ollama*, because
   quantisation or an unsupported adapter can erase a gain.

Activation keeps the original weights under ``<tag>-aurora-base`` and re-points
the application's tag, so every caller (interface, bridge, missions, CLI) uses
the reinforced model without any code change. ``rollback`` restores the tag.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from .compare import compare
from .evaluate import evaluate, read_results
from .inference import OllamaStudent
from .records import atomic_json, file_hash, read_json
from .run import installable_problems
from .students import resolve
from .suites import GATE_SLOT, Library, build_exam

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "Outputs" / "auto_rl" / "professor"
BACKUP_SUFFIX = "-aurora-base"


def ollama(*arguments, timeout=3600):
    """Run the Ollama command line; its absence is reported, never worked around."""
    try:
        done = subprocess.run(["ollama", *arguments], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise RuntimeError("La commande `ollama` est introuvable sur cette machine") from None
    if done.returncode:
        raise RuntimeError(f"ollama {' '.join(arguments[:2])} a échoué : {(done.stderr or done.stdout).strip()[-600:]}")
    return done.stdout


def full_tag(name):
    """Ollama lists an untagged model as NAME:latest; every comparison uses that form."""
    return name if ":" in name.rsplit("/", 1)[-1] else name + ":latest"


def installed_tags(url):
    with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=30) as response:
        return {full_tag(model["name"]): model.get("digest") for model in json.load(response).get("models", [])}


def _state():
    """installed.json: per application tag, every installed candidate and which one (if any) is active.

    The first version kept one record per tag and lost the active candidate when another was installed.
    """
    state = read_json(STATE / "installed.json", {})
    for tag, entry in list(state.items()):
        if "candidate_tag" in entry:                     # first format: one record per tag
            state[tag] = {"candidates": {entry["candidate_tag"]: entry},
                          "active": entry["candidate_tag"] if entry.get("active") else None,
                          "backup_digest": None, "active_digest": None}
    return state


def _save(state):
    atomic_json(STATE / "installed.json", state)


def check_delivery(delivery):
    """Gate 1 and 2: a promotable verdict whose adapter hash matches the delivered file."""
    delivery = Path(delivery).resolve()                 # the Modelfile is written elsewhere: its paths must be absolute
    verdicts = sorted(delivery.rglob("verdict_*.json"))
    if len(verdicts) != 1:
        raise ValueError(f"Un seul verdict est attendu dans la livraison, {len(verdicts)} trouvés")
    verdict = json.loads(verdicts[0].read_text(encoding="utf-8"))
    student = resolve(verdict["student"]["tag"])
    # The examiner's own rule, applied again here: the file may come from an older examiner or be edited.
    problems = [] if verdict.get("kind") == "aurora_professor_verdict" else ["ce fichier n'est pas un verdict de l'examinateur"]
    problems += installable_problems(verdict)
    if not verdict.get("promotable"):
        problems.append("l'examinateur n'a pas déclaré ce verdict installable")
    # ``init_adapter`` is the adapter a continued cycle started from: it travels for the comparison, never for delivery.
    adapters = [path for path in sorted(delivery.rglob("adapter_model.safetensors")) if path.parent.name != "init_adapter"]
    if len(adapters) != 1 or file_hash(adapters[0]) != verdict.get("adapter_sha256"):
        problems.append("l'adaptateur livré ne correspond pas à celui que l'examinateur a évalué")
    # A delivery may hold a failed export beside a later successful one: the receipt that lists files is the one to check.
    receipts = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in sorted(delivery.rglob("export_receipt.json"))]
    export, receipt = next(((path, found) for path, found in receipts if found.get("files")), receipts[0] if receipts else (None, {"files": {}}))
    files = {}
    for name, entry in receipt.get("files", {}).items():
        path = export.parent / name
        if not path.is_file() or file_hash(path) != entry["sha256"]:
            problems.append(f"{name} absent ou différent du reçu d'export")
        else:
            files[name] = path
    if receipt.get("adapter_sha256") not in (None, verdict.get("adapter_sha256")):
        problems.append("l'export a été produit à partir d'un autre adaptateur")
    if not files:
        problems.append("aucun fichier GGUF vérifié dans la livraison (adapter.gguf ou modèle fusionné)")      # == NO_GGUF
    return {"verdict": verdict, "verdict_sha256": file_hash(verdicts[0]), "student": student, "files": files, "problems": problems}


def modelfile(base_tag, files):
    """Prefer the small adapter on top of the installed base; else a merged quantised model."""
    if "adapter.gguf" in files:
        return f"FROM {base_tag}\nADAPTER {files['adapter.gguf']}\n", "adapter"
    merged = next(path for name, path in files.items() if name.startswith("merged-"))
    # Keep the base tag's template, parameters and system prompt; only its weights are replaced.
    inherited = [line for line in ollama("show", "--modelfile", base_tag).splitlines() if not re.match(r"\s*(FROM\b|#)", line)]
    return f"FROM {merged}\n" + "\n".join(inherited) + "\n", "merged"


def deployment_exam(base_tag, candidate_tag, folder, *, modules, per_skill, cycle, url, context, expected_skills=None):
    """Gate 3: the paired exam, answered by Ollama exactly as the application is served."""
    library = Library()

    def draw(count):
        drawn, drawn_notes = build_exam("gate", min(count, GATE_SLOT), modules=modules, cycle=cycle, library=library)
        # Generated programs are never executed on a workstation: those items are left to the cloud examiner.
        drawn_notes["left_to_cloud"] = sorted({i["skill"] for i in drawn if i["grader"]["type"] == "python_tests"}
                                              - {i["skill"] for i in drawn if i["grader"]["type"] != "python_tests"})
        return [item for item in drawn if item["grader"]["type"] != "python_tests"], drawn_notes
    items, notes = draw(per_skill)
    families = len({item["skill"] for item in items})
    if families and len(items) < 260:
        items, notes = draw(-(-260 // families))         # enough items to decide, within one gate slot per skill
    notes["skills_examined"] = sorted({item["skill"] for item in items})
    # The same exam as in the cloud, as served: a skill that is missing here (a public source that could not be
    # loaded, the `datasets` package absent) makes this exam incomplete, and an incomplete exam activates nothing.
    notes["skills_missing"] = sorted(set(expected_skills or ()) - set(notes["skills_examined"]) - set(notes["left_to_cloud"]))
    folder = Path(folder)
    for name, tag in (("base", base_tag), ("candidate", candidate_tag)):
        evaluate(OllamaStudent(tag, url=url, context=context), items, folder / name, batch_size=1, label=f"ollama_{name}")
    result = compare(read_results(folder / "base"), read_results(folder / "candidate"))
    missing = notes["skills_missing"] or sorted(notes["source_errors"])
    if missing and result["verdict"] == "promote":
        result["verdict"] = "inconclusive"
        result["reasons"].insert(0, "the exam as served lacks part of the cloud exam: " + ", ".join(missing)
                                 + " (install the `datasets` package and check the network, then install again)")
    result["exam"] = {"items": len(items), "notes": notes, "served_by": "ollama", "base_tag": base_tag, "candidate_tag": candidate_tag}
    atomic_json(folder / "deployment_verdict.json", result)
    return result


NO_GGUF = "aucun fichier GGUF vérifié dans la livraison (adapter.gguf ou modèle fusionné)"


def convert_locally(delivery):
    """Convert the delivered adapter on this machine when the examiner's own export produced nothing.

    Only for a delivery whose single problem is the missing GGUF: the verdict and the adapter hash are
    already verified. The conversion scripts come from the package index; errors are returned, not hidden.
    """
    from .export import export
    delivery = Path(delivery)
    checked = check_delivery(delivery)
    if checked["problems"] != [NO_GGUF]:
        return checked
    adapter = next(path.parent for path in sorted(delivery.rglob("adapter_model.safetensors")) if path.parent.name != "init_adapter")
    receipt = export(checked["student"], adapter, delivery / "export_local")
    checked = check_delivery(delivery)
    if receipt["errors"]:
        checked["problems"].append("conversion locale impossible : " + " ; ".join(f"{k} — {v[:200]}" for k, v in receipt["errors"].items()))
    return checked


def install(delivery, *, url="http://127.0.0.1:11434", per_skill=40, context=8192, exam=True):
    checked = convert_locally(delivery)
    if checked["problems"]:
        raise ValueError("Livraison refusée : " + " ; ".join(checked["problems"]))
    verdict, student = checked["verdict"], checked["student"]
    base_tag = full_tag(student["tag"])
    tags = installed_tags(url)
    state = _state()
    entry = state.setdefault(base_tag, {"candidates": {}, "active": None, "backup_digest": None, "active_digest": None})
    backup = base_tag + BACKUP_SUFFIX
    # While a candidate is active the original weights are the backup; otherwise the tag itself is the original
    # (it may have been updated since an earlier rollback, which makes an old backup stale).
    source = backup if entry["active"] else base_tag
    if source not in tags:
        raise RuntimeError(f"Le modèle de base {source} n'est pas installé dans Ollama")
    if entry["active"] and entry.get("backup_digest") and tags[backup] != entry["backup_digest"]:
        raise RuntimeError(f"La sauvegarde {backup} a changé depuis l'activation : vérifier avant toute installation")
    candidate = f"{base_tag}-aurora-renforce-c{verdict['cycle']}"
    text, kind = modelfile(source, checked["files"])
    with tempfile.TemporaryDirectory(prefix="aurora_modelfile_") as temporary:
        path = Path(temporary) / "Modelfile"
        path.write_text(text, encoding="utf-8")
        ollama("create", candidate, "-f", str(path))
    record = {"base_tag": base_tag, "candidate_tag": candidate, "kind": kind, "installed_at": time.time(), "built_from": source,
              "built_from_digest": tags[source], "verdict_sha256": checked["verdict_sha256"], "adapter_sha256": verdict["adapter_sha256"],
              "cloud_gain": verdict["overall"]["macro_gain"], "cloud_gain_ci": verdict["overall"]["macro_gain_ci"],
              "candidate_digest": installed_tags(url).get(candidate), "deployment": None}
    if exam:
        result = deployment_exam(source, candidate, STATE / "deployment" / candidate.replace("/", "_").replace(":", "_"),
                                 modules=verdict["modules"], per_skill=per_skill, cycle=verdict["cycle"] + 1000,
                                 url=url, context=context, expected_skills=sorted(verdict.get("skills") or {}))
        notes = result["exam"]["notes"]
        record["deployment"] = {"verdict": result["verdict"], "reasons": result["reasons"],
                                "macro_gain": result["overall"]["macro_gain"], "macro_gain_ci": result["overall"]["macro_gain_ci"],
                                "items": result["overall"]["items"], "regressions": result["regressions"],
                                "skills_examined": notes["skills_examined"], "skills_missing": notes["skills_missing"],
                                "left_to_cloud": notes["left_to_cloud"], "source_errors": notes["source_errors"]}
    entry["candidates"][candidate] = record              # the active candidate, if another one, stays recorded
    _save(state)
    return {**record, "active": entry["active"]}


def activate(tag, *, url="http://127.0.0.1:11434", candidate=None):
    """Point the application's tag at the reinforced weights, keeping the original under a backup tag."""
    tag = full_tag(tag)
    state = _state()
    entry = state.get(tag)
    if not entry or not entry["candidates"]:
        raise ValueError(f"Aucun modèle renforcé installé pour {tag}")
    name = candidate or max(entry["candidates"], key=lambda key: entry["candidates"][key]["installed_at"])
    record = entry["candidates"].get(name)
    if not record:
        raise ValueError(f"Aucun candidat {name} installé pour {tag}")
    deployment = record.get("deployment") or {}
    if deployment.get("verdict") != "promote":
        raise ValueError("Activation refusée : le modèle n'a pas regagné l'examen apparié tel que servi par Ollama "
                         f"(verdict : {deployment.get('verdict', 'examen non exécuté')})")
    tags = installed_tags(url)
    if not record.get("candidate_digest") or tags.get(name) != record["candidate_digest"]:
        raise ValueError("Le modèle installé a changé depuis son examen : relancer l'installation")
    backup = tag + BACKUP_SUFFIX
    if entry["active"]:
        # The tag serves an earlier candidate: the backup must still hold the original weights.
        if tags.get(tag) != entry.get("active_digest") or (entry.get("backup_digest") and tags.get(backup) != entry["backup_digest"]):
            raise ValueError(f"{tag} ou sa sauvegarde {backup} a changé depuis la dernière activation : vérifier avant d'activer")
    else:
        # The tag serves the original: keep exactly it as the backup (a backup left by an earlier rollback may be stale).
        if tags.get(tag) != record.get("built_from_digest"):
            raise ValueError(f"{tag} a changé depuis l'installation du candidat : relancer l'installation")
        ollama("cp", tag, backup)
        entry["backup_digest"] = installed_tags(url).get(backup)
    ollama("cp", name, tag)
    entry.update(active=name, active_digest=installed_tags(url).get(tag), activated_at=time.time(),
                 rollback=f"python -m auto_rl.professor.install rollback --tag {tag}")
    _save(state)
    return {**record, "active": name, "backup_tag": backup, "rollback": entry["rollback"]}


def rollback(tag, *, url="http://127.0.0.1:11434"):
    tag = full_tag(tag)
    state = _state()
    entry = state.get(tag) or {}
    backup = tag + BACKUP_SUFFIX
    tags = installed_tags(url)
    if backup not in tags:
        raise ValueError(f"Aucune sauvegarde {backup} : le modèle d'origine n'a pas été remplacé par cet outil")
    if entry.get("backup_digest") and tags[backup] != entry["backup_digest"]:
        raise ValueError(f"La sauvegarde {backup} n'est plus celle créée à l'activation : restauration refusée")
    ollama("cp", backup, tag)
    if entry:
        entry.update(active=None, active_digest=None, rolled_back_at=time.time())
        _save(state)
    return {"tag": tag, "restored_from": backup}


def deliver(owner, student, *, url="http://127.0.0.1:11434", per_skill=60, context=8192, activate_after=False, cycle=0,
            dataset=None):
    """Fetch the examiner's verified output from Kaggle, install it, and optionally activate it.

    One command for the PC: every gate still applies, and activation happens only
    if the model wins the paired exam again as served by Ollama. ``cycle`` selects
    which cycle's examiner to fetch (each cycle keeps its own output); ``dataset``
    reads a published delivery (private dataset) instead of the examiner's output.
    """
    import shutil
    from . import kaggle_runner
    slug = kaggle_runner.kernel_name("verify", student, cycle)[0]
    # One fresh folder per source: leftovers of an earlier download would add a second verdict or receipt.
    folder = STATE / "deliveries" / slug / (("dataset-" + dataset.replace("/", "-")) if dataset else "kernel")
    if folder.exists():
        shutil.rmtree(folder)
    if dataset:
        kaggle_runner.fetch_dataset(dataset, folder)
    else:
        kaggle_runner.fetch(f"{owner}/{slug}", folder)
    record = install(folder, url=url, per_skill=per_skill, context=context)
    if activate_after and (record.get("deployment") or {}).get("verdict") == "promote":
        record = activate(record["base_tag"], url=url, candidate=record["candidate_tag"])
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("status", "check", "install", "deliver", "activate", "rollback"))
    parser.add_argument("--delivery", type=Path)
    parser.add_argument("--owner", help="Kaggle account that ran the examiner (deliver)")
    parser.add_argument("--student", help="Ollama tag of the examined model (deliver)")
    parser.add_argument("--activate", action="store_true", help="deliver: activate when the deployment exam is won")
    parser.add_argument("--cycle", type=int, default=0, help="deliver: which cycle's examiner output to fetch")
    parser.add_argument("--dataset", help="deliver: private dataset owner/slug holding a published delivery")
    parser.add_argument("--tag")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--exam-per-skill", type=int, default=60)
    parser.add_argument("--context", type=int, default=8192)
    args = parser.parse_args(argv)
    if args.command == "status":
        result = _state()
    elif args.command == "check":
        checked = check_delivery(args.delivery)
        result = {"student": checked["student"]["tag"], "files": sorted(checked["files"]), "problems": checked["problems"]}
    elif args.command == "install":
        result = install(args.delivery, url=args.ollama_url, per_skill=args.exam_per_skill, context=args.context)
    elif args.command == "deliver":
        if not args.student or not (args.owner or args.dataset):
            parser.error("deliver requires --student and --owner (or --dataset)")
        result = deliver(args.owner, args.student, url=args.ollama_url, per_skill=args.exam_per_skill, context=args.context,
                         activate_after=args.activate, cycle=args.cycle, dataset=args.dataset)
    elif args.command == "activate":
        result = activate(args.tag, url=args.ollama_url)
    else:
        result = rollback(args.tag, url=args.ollama_url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
