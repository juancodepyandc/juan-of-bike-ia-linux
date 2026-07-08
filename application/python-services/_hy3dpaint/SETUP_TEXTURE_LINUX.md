# Texture PBR (Hunyuan Paint 2.1) — pré-requis Linux / RTX 50xx

Sans ces éléments, la génération 3D sort un **mesh gris sans couleur** (fallback `shape_only`).
Tout est déjà installé sur cette machine ; ce fichier sert à reproduire sur une install neuve.

## 1. Poids RealESRGAN (enrichissement ×4 des vues)
```bash
mkdir -p _hy3dpaint/ckpt
curl -L -o _hy3dpaint/ckpt/RealESRGAN_x4plus.pth \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth
```

## 2. Extensions compilées (CUDA + C++)
Nécessite CUDA 12.8 (`/usr/local/cuda-12.8`), gcc ≤ 14. Cible Blackwell = sm_120.
```bash
export CUDA_HOME=/usr/local/cuda-12.8 PATH=$CUDA_HOME/bin:$PATH
export TORCH_CUDA_ARCH_LIST="12.0"
# rastériseur CUDA
pip install --no-build-isolation ./_hy3dpaint/custom_rasterizer
# inpaint mesh (pybind11 CPU) — build in-place (import relatif) ET install top-level (is_available)
( cd _hy3dpaint/DifferentiableRenderer && python setup.py build_ext --inplace && pip install --no-build-isolation . )
```
`is_available()` fait un `import mesh_inpaint_processor` top-level → les DEUX (inplace + venv) sont requis.

## 3. Paquets Python (⚠️ `--no-deps` pour ne pas casser numpy 2.4)
```bash
pip install --no-deps realesrgan basicsr addict future yapf lmdb
pip install --no-deps pytorch-lightning torchmetrics lightning-utilities
pip install fast_simplification
```
`basicsr` importe `torchvision.transforms.functional_tensor` (retiré en tv≥0.17) : réglé au runtime par
`_apply_torchvision_fix()` (appelé dans `paint_pbr_v21._build_pipeline`, AVANT l'import realesrgan).

## 4. Correctifs code déjà appliqués
- `_hy3dpaint/utils/multiview_utils.py` : `DiffusionPipeline.from_pretrained(..., trust_remote_code=True, ...)`
  (diffusers récent l'exige pour le custom_pipeline).
- `hunyuan3d_run.py` : libère la VRAM du pipeline **shape** avant le **paint** (sinon OOM à toutes les résolutions
  sur 16 Go — l'offload CPU est ignoré par la pile hy3dgen).
- `cache_paths.py` : `_default_models_root()` → `~/.cache` sur Linux local (plus `/workspace`).
- `bridge_server.py::_build_python_env` : épingle `HF_HOME` sur le hub qui contient réellement les poids
  (`~/.cache/huggingface`) au lieu de `modele/huggingface` (vide).

## 5. Environnement d'exécution
Poids réels dans `~/.cache/huggingface`. Le bridge exporte automatiquement `HF_HOME`, `AURORA_MODELS`,
`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` pour les sous-process.

## Réalité 16 Go
Paint 8 vues : OOM à 1024/768 → l'échelle de secours retombe à **512** (RealESRGAN interne → atlas **2048**).
Vrai **8K** = une passe RealESRGAN de plus sur l'atlas final (2048 → 8192, en tuiles).
