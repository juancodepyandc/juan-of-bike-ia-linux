# HANDOFF — Migration AuroraIA 3D pipeline vers Hunyuan3D-2

**Date** : 2026-05-14
**Session précédente** : 298 itérations procédurales Blender Python livrées (proc_*.py), pipeline jugé "low-poly stylisé débutant" par l'utilisateur — pas réaliste.
**Décision** : abandonner pipeline procédural primitives, migrer vers **Hunyuan3D-2** (Tencent, open-source MIT, 100% gratuit).

---

## 1. Hardware confirmé (machine Juan)

- **GPU** : NVIDIA GeForce RTX 5070 Ti, **16 GB VRAM** (16303 MiB), CUDA 13.2 driver 595.79
- **CPU** : AMD Ryzen 9 9950X (16 cores)
- **RAM** : 31 GB
- **OS** : Windows 11 Famille 10.0.26200
- **Python** : 3.12.8 (`python` et `py -3` dispo)
- **Git** : 2.53.0
- **Disque C:** : 132 GB libres
- **`nvcc` PAS dans PATH** — il faudra installer CUDA Toolkit ou utiliser PyTorch pré-buildé

**Note critique RTX 5070 Ti (Blackwell, SM 12.0)** : nécessite **PyTorch nightly avec CUDA 12.8+** (pas la version stable 2.x avec CUDA 12.4). Wheels stables ne supportent pas encore SM 12.0.

---

## 2. Pipeline AuroraIA actuel (à conserver)

**Repo** : `C:\Users\Juan\Desktop\ia\AuroraIA-v2\`
**Git remote** : `https://github.com/juancodepyandc/juan-of-bike-ia.git`
**Dernier commit procédural** : `f53ce90` (297e Maldives), `2151fdb` (294e Jamaica coffee)
**Total proc_*.py** : 297 fichiers dans `application/python-services/proc_*.py`
**Output pack format** : `application/output/3d/pbr_<name>_pack/` contenant `.glb` + `.py` + 3 screenshots PNG
**Blender version** : 4.2.12 LTS portable dans `application/_blender/blender-4.2.12-windows-x64/blender.exe`
**CDP screenshot script** : `cdp_tunnel_test_3d.mjs` (ligne 18 = `const MESHES = ['pbr_<name>_proc.glb']`, modifier par scene)

**À garder** : structure `output/3d/pbr_*_pack/` + CDP screenshots + Git workflow.
**À remplacer** : `proc_*.py` Blender procédural → scripts qui appellent Hunyuan3D-2.

---

## 3. Plan d'installation Hunyuan3D-2

### Step 1 — Cloner le repo Hunyuan3D-2

```powershell
cd C:\Users\Juan\Desktop\ia
git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git
cd Hunyuan3D-2
```

Repo officiel : https://github.com/Tencent-Hunyuan/Hunyuan3D-2
Models HuggingFace : `tencent/Hunyuan3D-2` (auto-download au premier run)

### Step 2 — Venv Python 3.12 isolé

```powershell
cd C:\Users\Juan\Desktop\ia\Hunyuan3D-2
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### Step 3 — PyTorch nightly CUDA 12.8 (OBLIGATOIRE pour RTX 5070 Ti Blackwell SM 12.0)

```powershell
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
```

Vérifier :
```powershell
python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda, torch.cuda.get_device_name(0))"
```
Attendu : `True 12.8 NVIDIA GeForce RTX 5070 Ti`

### Step 4 — Dépendances Hunyuan3D-2

```powershell
pip install -r requirements.txt
```

Si `requirements.txt` plante (souvent xformers/flash-attn), installer manuellement le minimum :
```powershell
pip install diffusers transformers accelerate trimesh pymeshlab opencv-python pillow numpy einops omegaconf rembg onnxruntime-gpu huggingface_hub safetensors
```

### Step 5 — Custom CUDA kernels Hunyuan (optionnel mais perf×3)

```powershell
cd hy3dgen\texgen\custom_rasterizer
python setup.py install
cd ..\..\..
cd hy3dgen\texgen\differentiable_renderer
python setup.py install
cd ..\..\..
```

Si échec compile : skip, le pipeline marche sans (juste plus lent).

### Step 6 — Premier test

```powershell
python minimal_demo.py
```
Ou créer `test_smoke.py` :
```python
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained('tencent/Hunyuan3D-2')
mesh = pipe(image='input.png')[0]
mesh.export('output.glb')
```

Premier run télécharge ~10GB de modèles dans `%USERPROFILE%\.cache\huggingface\hub\`.

---

## 4. Pipeline cible pour la nouvelle loop

**Workflow** :
1. **Prompt texte** → **image** (via FLUX.1-schnell gratuit ou SDXL local)
2. **Image** → **mesh 3D PBR** via Hunyuan3D-2 (shape + texture)
3. **Mesh** → `.glb` exporté dans `application/output/3d/pbr_<scene>_pack/`
4. **CDP screenshot** sur viewer (réutiliser `cdp_tunnel_test_3d.mjs` actuel)
5. **Git commit + push**

**Stack 100% gratuit** :
- **Hunyuan3D-2** : shape generation (open MIT)
- **Hunyuan3D-Paint** : PBR textures multiview (inclus dans le repo)
- **FLUX.1-schnell** (ou **SDXL-Turbo**) : text→image local (gratuit, Apache 2.0)
- **rembg** : background removal automatique image→3D
- **Blender 4.2.12** : juste pour final GLB cleanup si besoin

**Pas besoin de** : OpenAI API, Meshy API, Stable AI subscription — tout local et gratuit.

---

## 5. Script template pour la nouvelle loop

```python
# pipeline_hunyuan_realistic.py — REMPLACE proc_*.py
import torch
from diffusers import FluxPipeline
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
from hy3dgen.texgen import Hunyuan3DPaintPipeline
from rembg import remove
from PIL import Image
import sys, os

SCENE_NAME = sys.argv[1]  # ex: "japanese_zen_garden"
PROMPT = sys.argv[2]  # ex: "stone lantern in moss garden, photoreal, soft morning light"

# 1. Text-to-image
flux = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16).to("cuda")
img = flux(PROMPT, num_inference_steps=4, guidance_scale=0.0).images[0]
img.save(f"tmp_{SCENE_NAME}.png")

# 2. Remove background
img_nobg = remove(img)

# 3. Image-to-3D shape
shape_pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained('tencent/Hunyuan3D-2')
mesh = shape_pipe(image=img_nobg)[0]

# 4. Apply PBR textures
paint_pipe = Hunyuan3DPaintPipeline.from_pretrained('tencent/Hunyuan3D-2')
mesh = paint_pipe(mesh, image=img_nobg)

# 5. Export
out_dir = f"application/output/3d/pbr_{SCENE_NAME}_pack/"
os.makedirs(out_dir, exist_ok=True)
mesh.export(f"{out_dir}/pbr_{SCENE_NAME}_proc.glb")

# 6. Copy to viewer dir
import shutil
shutil.copy(f"{out_dir}/pbr_{SCENE_NAME}_proc.glb", "application/public/_pbr_test/")
print(f"DONE: {out_dir}")
```

---

## 6. Loop nouvelle conversation à recréer

Le prompt loop sera de la forme :

```
/loop Pipeline 3D AuroraIA v2 — HUNYUAN3D-2 RÉALISTE.

État : 298 procéduraux abandonnés (low-poly stylisé). Nouveau pipeline Hunyuan3D-2 local.

Workflow par itération :
1. Définir scène (ex: "japonais zen garden lantern moss")
2. Générer image via FLUX.1-schnell
3. Hunyuan3D-2 image→mesh + Hunyuan3D-Paint textures PBR
4. Export GLB dans output/3d/pbr_<name>_pack/
5. CDP screenshot via cdp_tunnel_test_3d.mjs
6. Git commit + push
7. ScheduleWakeup pour scène suivante

cwd = C:/Users/Juan/Desktop/ia/AuroraIA-v2/
Repo Hunyuan3D-2 = C:/Users/Juan/Desktop/ia/Hunyuan3D-2/
Activer venv : Hunyuan3D-2/venv/Scripts/Activate.ps1
```

---

## 7. Memory files à conserver (déjà dans `C:\Users\Juan\.claude\projects\C--Users-Juan\memory\`)

- `MEMORY.md` — index
- `feedback-3d-quality.md` — règles smooth/bevel (peu pertinent désormais)
- `feedback-3d-landscape-sandwich.md` — règle "1 ground propre + particules" (toujours utile)
- `feedback-never-stop-loop-early.md` — pivot ne pas arrêter (toujours utile)
- `user-academic-background.md` — STI2D/SIN
- **À AJOUTER** : nouvelle memory `feedback-hunyuan3d-pipeline.md` documentant le pivot procédural → Hunyuan3D-2

---

## 8. Standing rules user (à respecter dans nouvelle conv)

- "NE PAS arrêter la boucle. Continuer à améliorer."
- "work without stopping for clarifying questions"
- "1 seul python lourd ; tuer orphelins ; pas le bridge (PID 24364)"
- "git -C .. pour commit ; pas de backtick"
- Push commits (no --no-verify)
- Per-deliverable folders in `application/output/3d/<name>_pack/`
- Si subject existe → pivot fresh subject

---

## 9. Checklist immédiate première session nouvelle conv

1. ✅ Spec hardware OK (RTX 5070 Ti 16GB, Ryzen 9, 31GB RAM)
2. ✅ `git clone Hunyuan3D-2` → `C:\Users\Juan\Desktop\ia\Hunyuan3D-2`
3. ✅ Venv créé : `Hunyuan3D-2\venv\` (Python 3.12.8)
4. ✅ PyTorch nightly cu128 installé : `torch-2.12.0.dev20260408+cu128`
5. ✅ CUDA validé : `cuda_available=True`, `version.cuda=12.8`, `device='NVIDIA GeForce RTX 5070 Ti'`, `capability=(12, 0)` — matmul 2048×2048 OK sur SM 12.0
6. ✅ Requirements Hunyuan3D installés (diffusers 0.38, transformers 5.8.1, trimesh 4.12, etc.)
7. ✅ CUDA Toolkit 12.8.1 installé (`C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8`, full default silent install via network installer). CUDA_HOME persisté au niveau user.
8. ✅ Kernels CUDA buildés : `custom_rasterizer` + `mesh_processor` (`differentiable_renderer`). Patch nécessaire : `hy3dgen/texgen/utils/multiview_utils.py` ligne 34 — ajouter `trust_remote_code=True` à `DiffusionPipeline.from_pretrained(...)` (diffusers récent l'exige).
9. ✅ Smoke test PBR complet validé (2026-05-14 13:27) :
   - Input : `assets/demo.png` (penguin "HY3D" 500×500)
   - Output : `Hunyuan3D-2/smoke_output_pbr.glb` (23.6 MB)
   - **Mesh : 369 231 vertices, 738 462 faces** (vs procédural ~5K faces → ×145 densité)
   - **PBR textures correctes** : noir/blanc penguin, bec orange, pancarte HY (noir) + 3D (rouge), shading roughness OK
   - Timing : shape 57.8s + texture 282.1s = **362s/scène** (6 min)
   - VRAM : 16GB SATURÉ pendant texgen (0 free à la fin) — pour batch prod, activer `enable_model_cpu_offload()` ou décharger entre shape↔texgen
   - Render visuel : `smoke_render_pbr.png` (Blender Cycles 1024×1024, 96 samples, 2.5s)
10. ✅ Pipeline AuroraIA Hunyuan3D livré : 5 scripts dans `application/python-services/aurora_hunyuan/` (copie versionnée) + runtime dans `Hunyuan3D-2/` :
    - `aurora_classify.py` heuristic prompt → SceneProfile (animations, materials, mood, category, refined image prompt)
    - `pipeline_hunyuan_realistic.py` orchestrator SDXL-Turbo → rembg → Hunyuan3D shape+paint → GLB → Blender
    - `aurora_animate.py` Blender data-driven animator dispatchant 12+ types (rotate_y, hover_float, emission_pulse, particles_rain/snow/fire/smoke/dust/sparks, fluid_flow, mechanical_articulate, shake_vibrate, drift_orbit, beauty_turntable)
    - `aurora_critic.py` quality eval (mesh density, texture coverage, exposure, silhouette) → score + flags + suggested_prompt
    - `aurora_loop.py` queue runner avec critic-driven refinement + state file + git commit auto

11. ✅ Validations end-to-end :
    - `vintage_leather_armchair` (statique) : 637s/scène, score 0.66, 460K verts / 921K faces, GLB 28.76 MB
    - `steampunk_clockwork_dragon` (4 animations + mécanique) : 1181s/scène, score 0.65, **1M faces**, GLB 32.69 MB, animations: rotate_y + emission_pulse + particles_smoke + mechanical_articulate
12. ⬜ Lancer la DEFAULT_QUEUE (8 scènes diverses) avec : `python aurora_loop.py --default-queue --min-score 0.65 --max-retries 2` (~80 min batch). Le loop persist state, refine prompt si score bas, commit auto par scène.

## Améliorations futures identifiées
- `flat_texture` flag fréquent → Hunyuan3D-Paint perd la richesse PBR sur scènes très détaillées. Solutions : utiliser Hunyuan3D-Paint NON-turbo (plus lent mais meilleure fidélité), ou injecter "vibrant saturated colors, high contrast materials" dans le prompt.
- CLIP 77-token cap : QUALITY_BOOST raccourci à 4 mots pour ne plus être tronqué.
- Mood priority order fixé : studio_clean > dramatic_night pour éviter "dark brown" → night.
- Composition cues Hunyuan-friendly front-loadées dans `refine_image_prompt`.

---

## 10. Pièges connus

- **PyTorch stable cu124 ne marche PAS sur RTX 5070 Ti** → kernel error sm_120 → utiliser nightly cu128
- **Premier téléchargement modèles** = ~10GB HuggingFace cache, prévoir bande passante
- **VRAM 16GB est juste assez** pour Hunyuan3D-2 full pipeline ; si OOM activer `pipe.enable_model_cpu_offload()`
- **FLUX.1-schnell** = ~12GB modèle, peut être remplacé par SDXL-Turbo (~6GB) si VRAM serrée
- **Windows path** : utiliser `\\` ou raw strings `r"..."` partout (pas `/` mélangé)
- **CDP screenshots** : viewer.html actuel charge GLB via three.js — Hunyuan3D-2 output sera plus dense, vérifier perfs viewer
- **TUER blender.exe** entre runs (`taskkill /F /IM blender.exe`)
- **Pre-receive GitHub** rejette > 100MB par fichier — si mesh GLB final > 100MB, décimer avant commit ou utiliser Git LFS

---

## 11. À copier-coller dans la nouvelle conversation

```
@HANDOFF_HUNYUAN3D.md

Reprise migration AuroraIA pipeline 3D : procédural Blender abandonné après 298 iterations (low-poly stylisé jugé non réaliste). Pivot vers Hunyuan3D-2 local 100% gratuit.

Hardware confirmé : RTX 5070 Ti 16GB VRAM, Ryzen 9 9950X, 31GB RAM, Python 3.12.8, CUDA 13.2 driver, 132GB libres.

Première étape : cloner Hunyuan3D-2, créer venv, installer PyTorch nightly cu128 (obligatoire SM 12.0 Blackwell), tester smoke 1 scène pour valider qualité vs procédural avant lancer nouvelle loop.

cwd = C:/Users/Juan/Desktop/ia/AuroraIA-v2/

Lis le handoff complet dans HANDOFF_HUNYUAN3D.md à la racine du repo et démarre par les checklist points 1-8.
```

---

**Fin du handoff. La nouvelle conversation peut démarrer en collant le bloc ci-dessus + en lisant ce fichier.**
