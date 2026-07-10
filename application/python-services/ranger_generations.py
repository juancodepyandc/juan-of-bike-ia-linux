import re
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent / "output" / "3d" / "generations"

MOTIFS_ETAPES = (
    "_mesh.glb", "_mesh_opt.glb", "_mesh_ao.glb", "_mesh_rough.glb",
    "_mesh_smooth.glb", "_mesh_fidelity.glb", "_mesh_reuv.glb",
    "_mesh_assaini.glb", "_RIGGED.glb", "_scene_src.glb",
    "_normal.png", "_motion.json", "_intent.json",
    "_materials_pre_vision.json", "_materials_vision.json",
    "_prompt.txt",
)


def _est_etape(nom: str) -> bool:
    return any(nom.endswith(m) for m in MOTIFS_ETAPES)


def ranger(dossier: Path) -> int:
    etapes = dossier / "etapes"
    bouges = 0
    for f in sorted(dossier.iterdir()):
        if not f.is_file():
            continue
        if _est_etape(f.name):
            etapes.mkdir(exist_ok=True)
            dest = etapes / f.name
            if dest.exists():
                dest.unlink()
            shutil.move(str(f), str(dest))
            bouges += 1
    return bouges


def main() -> int:
    total = 0
    for dossier in sorted(RACINE.iterdir()):
        if not dossier.is_dir() or dossier.name.startswith("_"):
            continue
        if len(sys.argv) > 1 and dossier.name in sys.argv[1:]:
            print(f"{dossier.name}: SAUTE (generation en cours)")
            continue
        n = ranger(dossier)
        if n:
            print(f"{dossier.name}: {n} fichier(s) range(s) dans etapes/")
            total += n
    print(f"TOTAL: {total} fichier(s) ranges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
