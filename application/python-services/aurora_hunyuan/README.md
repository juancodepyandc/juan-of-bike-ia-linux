# Aurora Hunyuan3D Pipeline

Intelligent text-to-3D pipeline built on top of [Hunyuan3D-2](https://github.com/Tencent-Hunyuan/Hunyuan3D-2) (Tencent) + SDXL-Turbo for AuroraIA-v2. Replaces the abandoned 298-iteration procedural Blender pipeline (`proc_*.py`).

## Architecture

```
text prompt
   |
   v
aurora_classify.py   ----- heuristic SceneProfile (animations, materials, mood, category)
   |
   v  refined image prompt (Hunyuan3D-friendly composition cues)
   |
SDXL-Turbo (4 steps)   ----- input.png 1024x1024
   |
rembg                  ----- input_nobg.png alpha-cut
   |
Hunyuan3D-DiT shape    ----- 300k-500k vert mesh (~58 s on RTX 5070 Ti)
   |
Hunyuan3D-Paint        ----- PBR multi-view textures (~280-330 s)
   |
   v
export GLB             ----- application/output/3d/pbr_<name>_pack/pbr_<name>_proc.glb
   |
aurora_animate.py      ----- Blender Cycles: hero PNG + orbit MP4 + animated MP4
   |                          dispatches profile animations (rotate, pulse, particles, hover, ...)
   v
aurora_critic.py       ----- score [0..1], flags, suggested_prompt
   |
aurora_loop.py         ----- queue runner: retry with refined prompt if score < min_score
```

## Files (live at C:\Users\Juan\Desktop\ia\Hunyuan3D-2\ for runtime imports)

- `aurora_classify.py`    Heuristic prompt -> SceneProfile JSON + `_strip_env_context` to remove "in jungle", "at night", etc. before Hunyuan3D sees the prompt.
- `pipeline_hunyuan_realistic.py`  Single-scene orchestrator (FLUX or SDXL-Turbo image -> saturation boost -> rembg -> Hunyuan3D shape + non-turbo paint -> Blender).
- `aurora_animate.py`     Blender headless animator. Loads HDRI environment map per mood (Poly Haven, in `Hunyuan3D-2/hdri/`). Dispatches every animation type data-driven.
- `aurora_critic.py`      Quality eval (mesh density, texture coverage, exposure, silhouette with corner-sampling bg detection).
- `aurora_loop.py`        Multi-scene queue with critic-driven prompt refinement and git commit per scene.
- `aurora_rebake.py`      Reinhard LAB color transfer from input.png to GLB baseColorTexture; produces `pbr_<name>_proc_rebake.glb` sibling.
- `aurora_rerender.py`    Batch: walk PACK_ALLOWLIST, apply rebake + HDRI animate over existing packs to lift quality after upstream upgrades.

Copies tracked in this directory for repository history. Runtime imports rely on the
copies inside `C:\Users\Juan\Desktop\ia\Hunyuan3D-2\` because `hy3dgen` lives there.

## HDRI assets (not in repo)

Eight 1k Poly Haven HDRIs live in `Hunyuan3D-2/hdri/` (~12 MB total, downloaded once). Mapped to moods in `aurora_animate._HDRI_BY_MOOD`. If a file is missing, the world falls back to a flat color matching the mood.

## Running

Activate venv and ensure CUDA_HOME points to the Toolkit install:

```powershell
$env:CUDA_HOME = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8"
$env:CUDA_PATH = $env:CUDA_HOME
$env:PATH = "$env:CUDA_HOME\bin;$env:PATH"
cd C:\Users\Juan\Desktop\ia\Hunyuan3D-2
```

Single scene:

```powershell
.\venv\Scripts\python.exe aurora_loop.py `
  --prompt "a glowing crystal lantern floating in fog at night" `
  --name crystal_lantern_fog `
  --min-score 0.65 --max-retries 3
```

Default queue (8 diverse prompts):

```powershell
.\venv\Scripts\python.exe aurora_loop.py --default-queue --min-score 0.65 --max-retries 2
```

Custom queue from JSON:

```powershell
.\venv\Scripts\python.exe aurora_loop.py --queue my_scenes.json
```

State persisted in `Hunyuan3D-2/aurora_state.json` (resume-safe).

## Output pack contents

For each scene, `application/output/3d/pbr_<name>_pack/` contains:

- `profile.json`          classifier output + refined image prompt
- `input.png`             SDXL-Turbo 1024x1024 hero image
- `input_nobg.png`        background-removed input fed to Hunyuan3D
- `pbr_<name>_proc.glb`   final PBR mesh, ~10-30 MB typical
- `mesh_meta.json`        verts, faces, shape_s, paint_s, glb_mb
- `hero.png`              Blender Cycles hero render 1024x1024 PBR
- `orbit.mp4`             360-deg turntable, 720p
- `animated.mp4`          if `profile.has_animation` is true, animated render with all applied animations
- `render_meta.json`      list of applied animation types
- `critique.json`         critic score, flags, suggested_prompt for next refinement

## Validation status (2026-05-14)

- Penguin demo end-to-end smoke test PASSED (shape 57 s + paint 282 s, GLB 23.6 MB, hero render shows PBR textures applied correctly).
- First full pipeline run on `vintage_leather_armchair` PASSED with score 0.66, total 637 s. Identified two improvements (mood priority, image composition cues for Hunyuan3D) now applied.

## Known limitations

- VRAM 16 GB saturates during Hunyuan3D-Paint. Pipeline serialises stages to avoid OOM but each scene needs ~6 GB free at start.
- Hunyuan3D-2 license is **Tencent Hunyuan Non-Commercial**: use for research/personal only.
- Custom CUDA kernels (`custom_rasterizer`, `mesh_processor`) require CUDA Toolkit 12.8 + VS Build Tools 2022 installed on the build machine.
- Patch applied locally: `hy3dgen/texgen/utils/multiview_utils.py` line 34 -> `trust_remote_code=True`.

## Extension points (when LLM access available)

- Replace `aurora_classify.classify(prompt)` with an LLM call that returns the same SceneProfile dataclass. Heuristic stays as offline fallback.
- Replace `aurora_critic.refine_prompt` with an LLM-driven refinement.
- Add new animation handlers in `aurora_animate.render_scene` by adding an `elif atype == "X":` branch. New types in classifier are auto-dispatched.
