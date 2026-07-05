#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_DIR="$ROOT_DIR/application"
EXTERNAL_DIR="${AURORA_EXTERNAL_DIR:-$HOME/.local/share/auroraia/external}"
HY3D_DIR="$EXTERNAL_DIR/Hunyuan3D-2"
HY3D21_DIR="$EXTERNAL_DIR/Hunyuan3D-2.1"

if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
  echo "Missing $APP_DIR/.venv. Run install-aurora-stack.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1091
. "$APP_DIR/.venv/bin/activate"

mkdir -p "$EXTERNAL_DIR"

clone_or_update() {
  local repo="$1"
  local dir="$2"
  if [ -d "$dir/.git" ]; then
    git -C "$dir" pull --ff-only
  else
    git clone "$repo" "$dir"
  fi
}

echo "[1/5] Clone Hunyuan3D runtimes"
clone_or_update https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git "$HY3D_DIR"
clone_or_update https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1.git "$HY3D21_DIR"

echo "[2/5] Python dependencies"
if [ -f "$HY3D_DIR/requirements.txt" ]; then
  python -m pip install -r "$HY3D_DIR/requirements.txt"
fi
if [ -f "$HY3D21_DIR/requirements.txt" ]; then
  python -m pip install -r "$HY3D21_DIR/requirements.txt"
fi

echo "[3/5] Editable installs or path links"
for dir in "$HY3D_DIR" "$HY3D21_DIR"; do
  if [ -f "$dir/pyproject.toml" ] || [ -f "$dir/setup.py" ]; then
    python -m pip install -e "$dir"
  fi
done

site_packages="$(python - <<'PY'
import site
paths = site.getsitepackages()
print(paths[0] if paths else site.getusersitepackages())
PY
)"
{
  echo "$HY3D_DIR"
  echo "$HY3D21_DIR"
  echo "$ROOT_DIR/application/python-services/_hy3dpaint"
} > "$site_packages/aurora-hunyuan3d.pth"

echo "[4/5] CUDA extensions when sources are present"
for ext_dir in \
  "$HY3D_DIR/hy3dgen/texgen/custom_rasterizer" \
  "$HY3D21_DIR/hy3dpaint/custom_rasterizer" \
  "$ROOT_DIR/application/python-services/_hy3dpaint/custom_rasterizer"; do
  if [ -d "$ext_dir" ]; then
    (cd "$ext_dir" && python -m pip install -e .)
  fi
done

for compile_script in \
  "$HY3D21_DIR/hy3dpaint/DifferentiableRenderer/compile_mesh_painter.sh" \
  "$ROOT_DIR/application/python-services/_hy3dpaint/DifferentiableRenderer/compile_mesh_painter.sh"; do
  if [ -f "$compile_script" ]; then
    (cd "$(dirname "$compile_script")" && bash "$compile_script") || {
      echo "Warning: mesh painter compilation failed at $compile_script"
    }
  fi
done

echo "[5/5] Import check"
python - <<'PY'
import importlib.util
for mod in ["hy3dgen", "torch", "trimesh", "pymeshlab", "rembg"]:
    print(f"{mod}: {bool(importlib.util.find_spec(mod))}")
PY

cat > "$ROOT_DIR/.env.linux.example" <<EOF
PYTHONPATH=$HY3D_DIR:$HY3D21_DIR:\$PYTHONPATH
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
TOKENIZERS_PARALLELISM=false
HF_HUB_ENABLE_HF_TRANSFER=1
EOF

echo "Hunyuan3D external runtime installed under $EXTERNAL_DIR"
