"""Build the professor notebooks: Colab trains, Kaggle examines.

Both notebooks embed the same hash-checked sources as the API-driven Kaggle
kernels (``auto_rl/professor/kaggle_runner.py``): there is one engine, not a
demonstration copy. Pass ``--diagnosis`` to embed the examiner's diagnosis in
the Colab notebook, so the trainer needs no credential to obtain it.
"""
import argparse
import base64
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from auto_rl.professor import kaggle_runner  # noqa: E402
from auto_rl.professor.students import STUDENTS  # noqa: E402
from auto_rl.professor.suites import MODULES  # noqa: E402


def cell(kind, source, tag=None):
    result = {"cell_type": kind, "metadata": {"tags": [tag]} if tag else {}, "source": source.splitlines(keepends=True)}
    if kind == "code":
        result.update(execution_count=None, outputs=[])
    return result


def notebook(cells):
    for index, item in enumerate(cells):
        item["id"] = f"aurora-professeur-{index}"
    return {"nbformat": 4, "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "accelerator": "GPU", "colab": {"provenance": []}},
            "cells": cells}


CATALOGUE = "\n".join(f"- `{tag}` → `{entry['hf']}` ({', '.join(entry['modules'])})" for tag, entry in STUDENTS.items())
MODULE_LIST = "\n".join(f"- `{name}` : {text}" for name, text in MODULES.items())

EXAMINER_INTRO = f"""# Aurora — professeur : examinateur (Kaggle)

Cette machine **ne s'entraîne jamais**. Elle fait passer des examens à un vrai modèle de l'application :

1. `diagnose` : mesure le modèle de base et publie ses points faibles par module, compétence et sous-compétence ;
2. `verify` : compare, sur des questions jamais vues, le modèle de base et le candidat entraîné ailleurs, puis rend un verdict (`promote`, `reject` ou `inconclusive`) selon une règle fixée à l'avance.

Les corrigés sont déterministes (exécution de tests, de requêtes SQL, comparateur de preuves des missions, égalité JSON typée…). Aucune note ne vient d'une loss ou d'un modèle juge. Les questions d'examen ne quittent pas cette machine : seuls des scores agrégés et des empreintes sortent.

Activer **GPU** et **Internet** dans les réglages du notebook. Pour `verify`, ajouter en entrée la sortie du notebook entraîneur ou le jeu de données privé contenant l'adaptateur.

Élèves connus :
{CATALOGUE}

Modules :
{MODULE_LIST}
"""

EXAMINER_PARAMETERS = '''ROLE = "diagnose"            # "diagnose" ou "verify"
STUDENT = "qwen2.5:7b"       # étiquette Ollama d'un modèle réellement appelé par Aurora
MODULES = None               # None = tous ; sinon par exemple "business,media,conversation"
PROFILE = "standard"         # "standard" ou "full" ("smoke" = répétition technique seulement)
CYCLE = 0                    # numéro du cycle : chaque cycle tire un examen de vérification inédit
BUDGET_MINUTES = 240

AURORA_OPTIONS = {"role": ROLE, "student": STUDENT, "profile": PROFILE, "modules": MODULES, "cycle": CYCLE,
                  "budget_minutes": BUDGET_MINUTES, "overrides": {}}
print(AURORA_OPTIONS)
'''

EXAMINER_RESULT = '''import json
from pathlib import Path
work = Path("/kaggle/working/aurora_professor")
if AURORA_OPTIONS["role"] == "diagnose":
    report = json.loads((work / "diagnosis.json").read_text())
    print("Examen complet :", report["complete"], "| précision macro :", round(report["summary"]["overall"]["macro_accuracy"], 4))
    for row in report["weak_points"]:
        print(f"{row['accuracy']:.3f}  [{row['ci95'][0]:.2f}, {row['ci95'][1]:.2f}]  n={row['items']:4d}  {row['skill']}" + ("" if row["trainable"] else "  (mesuré, sans données d'entraînement directes)"))
else:
    verdict = json.loads((work / f"verdict_{AURORA_OPTIONS['cycle']}.json").read_text())
    print("VERDICT :", verdict["verdict"], "| installable :", verdict["promotable"])
    for reason in verdict["reasons"]:
        print(" -", reason)
    for skill, table in verdict["skills"].items():
        print(f"{table['base_accuracy']:.3f} -> {table['candidate_accuracy']:.3f}  ({table['gain']:+.3f}, p={table['mcnemar_p']:.3f}, n={table['items']})  {skill}")
'''

TRAINER_INTRO = f"""# Aurora — professeur : entraîneur (Colab)

Cette machine **entraîne** un vrai modèle de l'application sur ses points faibles mesurés, et ne décide jamais s'il est meilleur : ce verdict appartient à l'examinateur Kaggle.

Ce qu'elle reçoit : `diagnosis.json` (scores agrégés par compétence et empreintes des questions d'examen, jamais les questions). Ce qu'elle produit : un adaptateur LoRA, son reçu d'entraînement et le plan du curriculum.

Déroulement : *Exécution → Tout exécuter*. Choisir un runtime **GPU**. La cellule de contrôle refuse de démarrer si la mémoire mesurée ne suffit pas pour l'élève diagnostiqué : aucun GPU ni capacité n'est supposé.

Secrets Colab facultatifs (icône clé) : `HF_TOKEN` pour un modèle à accès restreint ; `KAGGLE_API_TOKEN` (jeton récent `KGAT_…`) ou bien `KAGGLE_USERNAME` et `KAGGLE_KEY` (kaggle.json) pour déposer l'adaptateur dans un jeu de données privé et lancer l'examen Kaggle automatiquement. Sans eux, l'adaptateur est seulement enregistré dans Google Drive (`Aurora_Professeur/`) et l'examen reste à lancer.

Cycle suivant : avec `CONTINUE_FROM = "compte/jeu-de-données"`, la machine télécharge l'adaptateur du cycle précédent et le diagnostic de ce candidat publiés par l'examinateur, puis **prolonge** cet adaptateur sur des exercices inédits au lieu de repartir du modèle de base. L'examinateur compare alors le nouvel adaptateur à la base et à l'adaptateur précédent sur les mêmes questions.

Élèves connus :
{CATALOGUE}
"""

TRAINER_PARAMETERS = '''PROFILE = "standard"         # "standard" ou "full" ("smoke" = répétition technique seulement)
MODULES = None               # None = ceux du diagnostic ; sinon un sous-ensemble, par exemple "business,media"
CYCLE = 0
BUDGET_MINUTES = 300         # budget total ; l'adaptateur est sauvegardé avant la fin
OVERRIDES = {}               # par exemple {"curriculum": 8000, "epochs": 2}
CONTINUE_FROM = None         # jeu de données Kaggle privé "compte/nom" : reprendre l'adaptateur du cycle précédent
'''

TRAINER_DIAGNOSIS = '''import base64, json, os
from pathlib import Path
DIAGNOSIS_B64 = __DIAGNOSIS__
inputs = Path("/content/aurora_inputs")
inputs.mkdir(parents=True, exist_ok=True)
target = inputs / "diagnosis.json"
if DIAGNOSIS_B64:
    target.write_bytes(base64.b64decode(DIAGNOSIS_B64))
elif not target.is_file() and not CONTINUE_FROM:
    from google.colab import files
    print("Déposer le fichier diagnosis.json produit par l'examinateur Kaggle.")
    uploaded = files.upload()
    if len(uploaded) != 1:
        raise SystemExit("Un seul fichier diagnosis.json est attendu")
    target.write_bytes(next(iter(uploaded.values())))
try:
    from google.colab import userdata
    for name in ("HF_TOKEN", "KAGGLE_API_TOKEN", "KAGGLE_USERNAME", "KAGGLE_KEY"):
        try:
            os.environ[name] = userdata.get(name)
        except Exception:
            pass
except ImportError:
    pass
if CONTINUE_FROM:
    # Cycle suivant : l'examinateur a publié l'adaptateur précédent et le diagnostic de ce candidat.
    if not (os.environ.get("KAGGLE_API_TOKEN") or (os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))):
        raise SystemExit("CONTINUE_FROM demande les secrets Kaggle pour télécharger l'adaptateur précédent ; sinon mettre CONTINUE_FROM = None")
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "kaggle", "six"], check=True)
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    continued = inputs / "continued"
    api.dataset_download_files(CONTINUE_FROM, path=str(continued), unzip=True, quiet=True)
    found = sorted(continued.glob("diagnosis_next_*.json"))
    if len(found) != 1 or not (continued / "adapter_config.json").is_file():
        raise SystemExit("Le jeu de données ne contient pas un adaptateur et son diagnostic diagnosis_next_N.json")
    for stale in continued.glob("init_adapter_*"):          # l'adaptateur d'avant ne sert pas à l'entraîneur
        stale.unlink()
    target = found[0]
diagnosis = json.loads(target.read_text())
if diagnosis.get("kind") != "aurora_professor_diagnosis" or not diagnosis.get("complete"):
    raise SystemExit("Diagnostic absent ou incomplet : relancer l'examinateur avant d'entraîner")
STUDENT = diagnosis["student"]["tag"]
print("Élève diagnostiqué :", STUDENT, "→", diagnosis["student"]["hf"],
      "| candidat déjà entraîné, reprise de son adaptateur" if CONTINUE_FROM else "| modèle de base")
for row in diagnosis["weak_points"][:12]:
    print(f"  {row['accuracy']:.3f}  n={row['items']:4d}  {row['skill']}")
AURORA_OPTIONS = {"role": "train", "student": STUDENT, "profile": PROFILE, "cycle": CYCLE, "continue": bool(CONTINUE_FROM),
                  "modules": MODULES or ",".join(diagnosis["modules"]), "budget_minutes": BUDGET_MINUTES, "overrides": OVERRIDES}
'''

TRAINER_ADMISSION = '''import subprocess
query = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.free,memory.total", "--format=csv,noheader,nounits"],
                       capture_output=True, text=True)
gpus = [line.split(", ") for line in query.stdout.strip().splitlines()] if query.returncode == 0 else []
free = [float(g[1]) / 1024 for g in gpus]
print("GPU mesurés :", [(g[0], f"{float(g[1]) / 1024:.1f} Gio libres / {float(g[2]) / 1024:.1f}") for g in gpus] or "aucun")
entry = diagnosis["student"]
# Les modèles à experts groupés ne se quantifient pas en 4 bits avec la bibliothèque actuelle : il faut leur taille en 16 bits.
weights = entry["full_gb"] if entry.get("expert_tensors") else entry["four_bit_gb"]
need = weights + 5.0
usable = sum(max(0.0, f - 1.5) for f in free)
if usable < need and entry["params_b"] > 2.0:
    raise SystemExit(f"Mémoire GPU insuffisante pour {STUDENT} : {usable:.1f} Gio utilisables, {need:.1f} nécessaires "
                     + ("(modèle à experts, non quantifiable en 4 bits). " if entry.get("expert_tensors") else "en 4 bits. ")
                     + "Choisir un runtime plus grand, ou demander à l'examinateur un diagnostic pour un élève plus petit.")
print("Admission acceptée pour", STUDENT)
'''

TRAINER_EXPORT = '''import json, os, shutil, sys
from pathlib import Path
work = Path("/content/aurora_professor")
receipt = json.loads((work / "training" / "train_receipt.json").read_text())
print("Pas effectués :", receipt["steps"], "| arrêt :", receipt["stopped"], "| loss de développement :",
      round(receipt["initial_dev_loss"], 4), "→", round(receipt["selected_dev_loss"], 4))
print("Une loss plus basse ne prouve pas de meilleures réponses : seul l'examen apparié de Kaggle décide.")
archive = shutil.make_archive(f"/content/aurora_adaptateur_cycle{CYCLE}", "zip", root_dir=work, base_dir="training")
shutil.copy2(work / "curriculum.json", "/content/curriculum.json")
if os.environ.get("KAGGLE_API_TOKEN") or (os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY")):
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "kaggle", "six"], check=True)
    sys.path.insert(0, str(REPO))
    from auto_rl.professor import kaggle_runner
    owner = kaggle_runner.whoami()
    dataset = kaggle_runner.publish_adapter(owner, work / "training", student=STUDENT, note=f"cycle {CYCLE} {STUDENT}")
    print("Adaptateur déposé dans le jeu de données privé", dataset)
    folder = Path("/content/aurora_examinateur")
    kaggle_runner.write_kernel(folder, owner, "verify", student=STUDENT, profile=PROFILE, modules=AURORA_OPTIONS["modules"],
                               cycle=CYCLE, budget_minutes=240, dataset_sources=[dataset])
    print("Examen lancé :", kaggle_runner.launch(folder, timeout_seconds=240 * 60 + 1500))
else:
    try:
        from google.colab import drive
        drive.mount("/content/drive")
        target = Path("/content/drive/MyDrive/Aurora_Professeur")
        target.mkdir(exist_ok=True)
        shutil.copy2(archive, target / Path(archive).name)
        shutil.copy2("/content/curriculum.json", target / f"curriculum_cycle{CYCLE}.json")
        print("Adaptateur enregistré dans Google Drive :", target / Path(archive).name)
    except Exception as exc:
        print("Drive indisponible (", exc, ") : télécharger", archive, "depuis le panneau Fichiers.")
'''


def build(diagnosis=None, output=None, cycle=0, continue_from=None):
    """Write both notebooks. ``output`` (default ``notebooks/``) lets a run-specific copy with an
    embedded diagnosis live outside the repository; ``cycle`` presets the trainer's cycle number and
    ``continue_from`` the private dataset holding the adapter to continue."""
    out = Path(output) if output else ROOT / "notebooks"
    out.mkdir(parents=True, exist_ok=True)
    kaggle_cells = [cell("markdown", EXAMINER_INTRO), cell("code", EXAMINER_PARAMETERS, "parameters"),
                    cell("code", kaggle_runner.script(), "professor-run"), cell("code", EXAMINER_RESULT, "result")]
    (out / "Aurora_Professeur_Examinateur_Kaggle.ipynb").write_text(
        json.dumps(notebook(kaggle_cells), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    embedded = repr(base64.b64encode(Path(diagnosis).read_bytes()).decode()) if diagnosis else "None"
    parameters = TRAINER_PARAMETERS.replace("CYCLE = 0", f"CYCLE = {int(cycle)}")
    if continue_from:
        parameters = parameters.replace("CONTINUE_FROM = None", f"CONTINUE_FROM = {str(continue_from)!r}")
    colab_cells = [cell("markdown", TRAINER_INTRO), cell("code", parameters, "parameters"),
                   cell("code", TRAINER_DIAGNOSIS.replace("__DIAGNOSIS__", embedded), "diagnosis"),
                   cell("code", TRAINER_ADMISSION, "admission"),
                   cell("code", kaggle_runner.script(base="/content", inputs="/content/aurora_inputs", hf_home="/content/hf_cache",
                                                sources="/content/aurora_sources"), "professor-run"),
                   cell("code", TRAINER_EXPORT, "export")]
    (out / "Aurora_Professeur_Entraineur_Colab.ipynb").write_text(
        json.dumps(notebook(colab_cells), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"sources_sha256": kaggle_runner.bundle()[1], "diagnosis_embedded": bool(diagnosis)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnosis", type=Path, help="diagnosis.json to embed in the Colab trainer notebook")
    parser.add_argument("--output", type=Path, help="folder for the notebooks (default: notebooks/ of the repository)")
    parser.add_argument("--cycle", type=int, default=0, help="cycle number preset in the Colab trainer notebook")
    parser.add_argument("--continue-from", help="private Kaggle dataset (owner/slug) holding the adapter to continue")
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.diagnosis, arguments.output, arguments.cycle, arguments.continue_from)))
