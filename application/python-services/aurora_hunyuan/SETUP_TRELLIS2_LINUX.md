# TRELLIS.2 (microsoft/TRELLIS.2-4B) — géométrie 3D propre depuis 1 image

TRELLIS.2 remplace la chaîne Hunyuan-2mv (4 vues FLUX indépendantes → double-visage/fragmenté).
Une seule image → géométrie **cohérente** + PBR, reconstruite en interne. **Peak VRAM ~3.6 Go**
sur RTX 5070 Ti 16 Go (les 24 Go du README ne sont PAS nécessaires en inférence), ~4 min/objet.

Branché comme **voie principale** dans `aurora_3d_pipeline.run_pipeline` (Stage 2), fallback
automatique sur Hunyuan3D si `aurora_trellis_wrapper.is_available()` est False.

## Repo + modèle (déjà présents)
- Repo : `/home/juan/.local/share/auroraia/external/TRELLIS.2` (module `trellis2`)
- Modèle : `microsoft/TRELLIS.2-4B` (cache HF)
- Encodeur image : `facebook/dinov3-vitl16-pretrain-lvd1689m` (miroir `camenduru/...` en cache)

## 1. Dépendances Python (venv de l'app)
```bash
PIP=/home/juan/AuroraIA/application/.venv/bin/pip
$PIP install easydict plyfile lpips kornia timm matplotlib zstandard
$PIP install /tmp/ext/utils3d --no-build-isolation   # clone EasternJournalist/utils3d @ 9a4eb15
```

## 2. Kernels CUDA (ordre imposé : flex_gemm AVANT o_voxel)
Env commun : `CUDA_HOME=/usr/local/cuda-12.8`, `PATH=$CUDA_HOME/bin:$PATH`,
`TORCH_CUDA_ARCH_LIST=12.0` (Blackwell sm_120), `CC=gcc-13 CXX=g++-13`.
```bash
# clones : JeffreyXiang/FlexGEMM, JeffreyXiang/CuMesh (recursive), NVlabs/nvdiffrast (v0.4.0)
$PIP install /tmp/ext/FlexGEMM  --no-build-isolation          # ~7 min
$PIP install /tmp/ext/CuMesh    --no-build-isolation          # ~17 min
$PIP install /home/juan/.local/share/auroraia/external/TRELLIS.2/o-voxel --no-build-isolation --no-deps
$PIP install /tmp/ext/nvdiffrast --no-build-isolation
```
Aucun mur Blackwell : nvcc 12.8 cible sm_120, xformers tourne (flash_attn PAS requis).

## 3. Patch compat transformers 5.x (DINOv3)
transformers 5.13 imbrique les layers DINOv3 : `DINOv3ViTModel.model.layer` (avant `.layer` direct).
Patché dans le repo TRELLIS.2 (hors git de l'app), à REFAIRE si le repo est réinstallé :
- `trellis2/modules/image_feature_extractor.py` (~L86) et
- `trellis2/trainers/flow_matching/mixins/image_conditioned.py` (~L88) :
  `for i, layer_module in enumerate(self.model.layer)` →
  `_layers = getattr(self.model,"layer",None) or self.model.model.layer` puis `enumerate(_layers)`.

## 4. Runtime
Le wrapper `aurora_trellis_wrapper.py` met déjà : `ATTN_BACKEND=xformers`,
`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, `CUDA_HOME` (nvdiffrast JIT-compile au 1er usage),
et ajoute le repo au `sys.path`. Test : `python aurora_hunyuan/aurora_trellis_wrapper.py <img> out.glb`.

## 6. Mode PRÉCISION MAX — 1536_cascade via allocateur managé (spill GPU→RAM)
Le 1536_cascade (géométrie fine: fentes, résistances, cheveux au mm) OOM à l'extraction sur 16 Go.
Solution: allocateur CUDA managé (`cudaMallocManaged`) qui fait déborder l'extraction sur la RAM (30 Go).
Prouvé: tensor 18 Go sur GPU 16 Go, 0 OOM. Lent (page-faults PCIe) mais complet.
```bash
DST=/home/juan/.local/share/auroraia/external/TRELLIS.2
CUDART=/home/juan/.local/opt/miniforge3/envs/trellis2/lib/python3.10/site-packages/nvidia/cuda_runtime/lib/libcudart.so.12
gcc -shared -fPIC -O2 -o "$DST/managed_alloc.so" "$DST/managed_alloc.c" "$CUDART"
```
Activer: `AURORA_TRELLIS2_MANAGED=1 AURORA_TRELLIS2_QUALITY=1536_cascade`. Le wrapper installe l'allocateur
au chargement (avant toute alloc CUDA) + patch decode_latent (libère les latents avant CuMesh, ~1-3 Go).
