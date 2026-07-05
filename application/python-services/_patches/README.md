# Patched third-party files

## `mesh_render.py` → `site-packages/hy3dgen/texgen/differentiable_renderer/mesh_render.py`

**Why:** The Hunyuan3D paint module needs the `custom_rasterizer` CUDA extension,
which can't be built on this Windows box (no `nvcc`, CUDA Toolkit install needs admin).
Without it, texture/paint generation crashes.

**What the patch adds:**
- A pure-numpy **CPU triangle rasterizer fallback** (`_cpu_rasterize`: NDC→screen with
  Y-flip, z-buffer, edge functions, perspective-correct barycentrics) wired into
  `raster_rasterize` / `raster_interpolate` when `raster_mode in ('cpu','numpy')`.
- `__init__` falls back to `raster_mode='cpu'` if `import custom_rasterizer` fails.
- `set_mesh`: decimates to ~30k faces for the CPU path **only when there are no UVs yet**
  (so painted UVs are never destroyed).

**How to apply:** after `pip install hy3dgen`, copy this file over the installed one.
Or, on a box with `nvcc`, rebuild `custom_rasterizer` for your arch
(`TORCH_CUDA_ARCH_LIST="8.6;8.9;9.0;12.0"`) and the unpatched module works on GPU (faster).

**Result it unblocks:** `aurora_3d_pipeline.py` now produces a real PBR-textured GLB
(2048² baseColor albedo, ~27% non-grey texels, UVs intact) instead of a grey vertex-color bake.
