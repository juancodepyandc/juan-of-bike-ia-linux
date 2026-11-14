"""Build the two cloud notebooks from native entrypoints, never embedded fake trainers."""
import json
import base64
import hashlib
import inspect
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from auto_rl.remote_lab import SHARED_SUITES
from auto_rl.source_bundle import build_bundle, extract_bundle


def cell(kind, source):
    result = {"cell_type": kind, "metadata": {}, "source": source.splitlines(keepends=True)}
    if kind == "code":
        result.update(execution_count=None, outputs=[])
    return result


def build(kaggle_owner=None):
    blob, manifest = build_bundle(ROOT, ["auto_rl.remote_lab", "auto_rl.source_bundle", "mcp.hub", "mcp.cowork.server", *SHARED_SUITES])
    bootstrap = '''from pathlib import Path, PurePosixPath
import base64, hashlib, io, json, os, stat, sys, zipfile
''' + inspect.getsource(extract_bundle) + f'''
SOURCE_SHA256 = {hashlib.sha256(blob).hexdigest()!r}
source_bytes = base64.b64decode({base64.b64encode(blob).decode()!r})
# A unique, hash-named directory keeps source revisions separate.
REPO = extract_bundle(source_bytes, Path.cwd() / "aurora_native_sources" / SOURCE_SHA256[:16], SOURCE_SHA256)
sys.path.insert(0, str(REPO))
print("Native source files verified:", {len(manifest)})
'''
    setup = '''from pathlib import Path
import os, sys, json
from auto_rl.remote_lab import probe_resources, validate_native, run_payload
print(json.dumps(probe_resources(), indent=2))
'''
    dependencies = '''import subprocess, sys
from importlib.metadata import version, PackageNotFoundError
# Reuse the VM's numerical stack; install only the missing browser dependencies.
requirements = {"playwright": "1.61.0", "psutil": "7.2.2"}
missing = []
for name, expected in requirements.items():
    try:
        installed = version(name)
    except PackageNotFoundError:
        installed = None
    if installed != expected:
        missing.append(f"{name}=={expected}")
if missing:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", *missing], check=True, timeout=180)
subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], check=True, timeout=240)
'''
    bench = '''from uuid import uuid4
OUTPUT = Path.cwd() / "aurora_experiments" / uuid4().hex
report = validate_native(OUTPUT)
print(json.dumps(report, indent=2))
assert report["passed"], f"Inspect {OUTPUT / 'native_tests.log'}"
# Passing software contracts does not measure generation quality.
'''
    training = '''# Fill from a package produced by Aurora's native cloud pipeline.
# Keep False for preflight. Training is a separate, deliberate cell action.
RUN_TRAINING = False
JOB_ID = ""
PAYLOAD_SHA256 = ""
INPUTS = Path.cwd() / "aurora_inputs"
REQUIREMENTS_FILE = INPUTS / "measured_requirements.json"
SESSION_SECONDS = None  # Your explicit budget, including checkpoint/export margin.
if RUN_TRAINING:
    assert SESSION_SECONDS is not None and SESSION_SECONDS > 0
    requirements = json.loads(REQUIREMENTS_FILE.read_text())
    receipt = run_payload(job_id=JOB_ID, payload_hash=PAYLOAD_SHA256,
                          inputs=INPUTS, output=Path.cwd() / "aurora_experiments",
                          requirements=requirements, session_seconds=SESSION_SECONDS)
    print(json.dumps(receipt, indent=2))
else:
    print("Preflight only. No training started and no model promoted.")
'''
    for name, title, purpose, body in (
        ("Aurora_Verification_Kaggle.ipynb", "Aurora — vérification Kaggle", "VM de test : contrats natifs MCP, navigateur et gouvernance. Les générations de chaque module exigent en plus un corpus indépendant et leurs moteurs réels.", bench),
        ("Aurora_Training_Colab.ipynb", "Aurora — calcul natif Colab", "VM de calcul : matériel mesuré, lot natif empreinté, budget explicite et export vérifié. Un GPU G4 ou une capacité donnée ne sont jamais supposés.", training),
    ):
        notebook = {"nbformat": 4, "nbformat_minor": 5,
                    "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                    "cells": [cell("markdown", f"# {title}\n\n{purpose}\n\nSources Python natives incluses et empreintées, sans poids ni identifiants. Exécuter les cellules dans l’ordre ; la cellule de dépendances installe le navigateur requis. Aucun entraînement ni promotion automatique. Pour entraîner un moteur non inclus dans ce banc, fournir son checkout vérifié complet et le lot natif correspondant.\n"), cell("code", bootstrap), cell("code", dependencies), cell("code", setup), cell("code", body)]}
        for index, item in enumerate(notebook["cells"]):
            item["id"] = f"aurora-{index}"
        for item, tag in zip(notebook["cells"][1:], ("source-bootstrap", "dependencies", "preflight", "experiment")):
            item["metadata"]["tags"] = [tag]
        (ROOT / "notebooks" / name).write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + "\n")
        if "Verification" in name and kaggle_owner:
            kernel = ROOT / "notebooks" / "kaggle_native_validation"
            kernel.mkdir(exist_ok=True)
            (kernel / name).write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + "\n")
            metadata = {"id": f"{kaggle_owner}/aurora-native-lab-validation", "title": "Aurora Native Lab Validation",
                        "code_file": name, "language": "python", "kernel_type": "notebook",
                        "is_private": True, "enable_gpu": False, "enable_internet": True,
                        "dataset_sources": [], "competition_sources": [], "kernel_sources": []}
            (kernel / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kaggle-owner", help="Authenticated account for a separate private validation notebook")
    build(parser.parse_args().kaggle_owner)
