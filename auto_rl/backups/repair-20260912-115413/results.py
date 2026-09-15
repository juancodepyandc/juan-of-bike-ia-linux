"""Human-readable, stable shortcuts to each module's latest comparison."""
from pathlib import Path
import os
from .config import ROOT

FOLDERS = {"3d": "3D_Trellis", "image": "Images", "code": "Code_Qwen", "audio": "Voix_Audio"}


def publish_shortcuts(module, run):
    run = Path(run).resolve()
    folder = ROOT / "Outputs" / "Comparaisons" / FOLDERS[module]
    folder.mkdir(parents=True, exist_ok=True)
    for name, target in (("DERNIER_CYCLE", run), (run.name, run)):
        temporary = folder / ("." + name + ".tmp")
        temporary.unlink(missing_ok=True)
        temporary.symlink_to(target, target_is_directory=True)
        os.replace(temporary, folder / name)
    (folder / "LIRE_MOI.txt").write_text(
        "Ouvrir DERNIER_CYCLE/comparison.html pour comparer les rendus et les scores.\n"
        "AVANT_BASE : fichiers générés avec les poids d'origine.\n"
        "AVANT_CHAMPION : précédent modèle validé, s'il existe.\n"
        "APRES_CANDIDAT : nouveau modèle, pas nécessairement meilleur.\n"
        "SUJETS : images de référence et descriptions des difficultés.\n"
        "Les modèles d'origine restent intacts. Seul un candidat validé devient champion.\n")
    for name, target in (("AVANT_BASE", run / "audit/base"), ("AVANT_CHAMPION", run / "audit/champion"),
                         ("APRES_CANDIDAT", run / "audit/candidate"), ("SUJETS", run / "tasks")):
        alias = run / name
        if not alias.exists() and not alias.is_symlink():
            alias.symlink_to(target, target_is_directory=True)
    return str(folder)
