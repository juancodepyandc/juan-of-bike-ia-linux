"""forge_layers — segmente un portrait en calques PNG selon un rig.yaml.

Implements step 06 of the Character Forge brief:
  reference_portrait.png + rig.yaml  -->  layers/{NN_layerId}.png
using ComfyUI custom nodes:
  - GroundingDinoSAMSegment (segment_anything)  - prompt-driven masks
  - BiRefNetRMBG                                 - alpha refinement
  - AILab_LamaRemover                            - inpaint the hole left
                                                   behind the removed layer

The script submits a single workflow per rig layer (kind != static) to the
ComfyUI HTTP API and polls /history until completion. Output PNGs (32-bit
with transparent alpha) are copied into the destination directory.

Usage:
  python forge_layers.py \\
    --portrait public/avatars/caine.png \\
    --rig public/avatars/caine_rig.json \\
    --out   public/avatars/caine_layers
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
WORKSPACE = str(Path(__file__).resolve().parent.parent)


def emit(pct: int, detail: str) -> None:
    print(f"PROGRESS:{pct}:{detail}", flush=True)


# --- ComfyUI HTTP helpers ----------------------------------------------------

def comfy_up() -> bool:
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=3):
            return True
    except Exception:
        return False


def comfy_post(path: str, payload: dict, timeout: int = 30) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{COMFY_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def comfy_upload_image(local_path: str, name: str) -> str:
    """Upload an image into ComfyUI's input/ folder and return its name."""
    boundary = uuid.uuid4().hex
    with open(local_path, "rb") as f:
        body = f.read()
    parts = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + body + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{COMFY_URL}/upload/image",
        data=parts,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
    return result.get("name", name)


def comfy_view(filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
    qs = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": folder_type})
    with urllib.request.urlopen(f"{COMFY_URL}/view?{qs}", timeout=60) as r:
        return r.read()


def comfy_poll_until_done(prompt_id: str, timeout: int = 600) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=5) as r:
                hist = json.loads(r.read())
                if prompt_id in hist:
                    return hist[prompt_id]
        except Exception:
            pass
        time.sleep(1.5)
    raise TimeoutError(f"ComfyUI workflow {prompt_id} did not complete in {timeout}s")


# --- Prompt heuristics -------------------------------------------------------

# Map layer ids to GroundingDINO text prompts. Layers with explicit prompt in
# the rig override this mapping.
LAYER_PROMPT_HINTS = {
    "star_eye":  "the star-shaped eye",
    "moon_eye":  "the crescent moon eye",
    "left_eye":  "the left eye",
    "right_eye": "the right eye",
    "eye":       "the eye",
    "eyes":      "the eyes",
    "mouth":     "the mouth",
    "lips":      "the lips",
    "eyebrow":   "the eyebrow",
    "eyebrows":  "the eyebrows",
    "hair":      "the hair",
    "hat":       "the hat",
    "hat_L":     "the left horn of the hat",
    "hat_R":     "the right horn of the hat",
    "hat_band":  "the band of the hat",
    "horn":      "the horn",
    "collar":    "the collar",
    "neck":      "the neck",
    "head":      "the head",
    "face":      "the face",
    "body":      "the body",
    "cape":      "the cape",
    "scarf":     "the scarf",
    "accessory": "the accessory",
    "sparkles":  "the sparkles",
    "backdrop":  "the background",
}


def layer_text_prompt(layer_id: str, explicit_prompt: str | None = None) -> str:
    if explicit_prompt:
        return explicit_prompt
    raw = layer_id.strip().lower()
    if raw in LAYER_PROMPT_HINTS:
        return LAYER_PROMPT_HINTS[raw]
    # Fallback: transform snake_case / camelCase into a prompt
    words = re.sub(r"([A-Z])", r" \1", raw.replace("_", " ")).strip().lower()
    return f"the {words}"


def safe_filename(layer_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", layer_id.strip()) or "layer"


# --- Workflow builder --------------------------------------------------------

def build_segment_workflow(portrait_name: str, layer_id: str, text_prompt: str, index: int) -> dict:
    """Minimal ComfyUI workflow that extracts one layer as a PNG with alpha.

    Nodes:
      1  LoadImage
      2  GroundingDinoModelLoader
      3  SAMModelLoader
      4  GroundingDinoSAMSegment  -> (IMAGE with alpha, MASK)
      5  SaveImage                 -> layer PNG with transparent background
    """
    return {
        "prompt": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": portrait_name},
            },
            "2": {
                "class_type": "GroundingDinoModelLoader (segment anything)",
                "inputs": {"model_name": "GroundingDINO_SwinT_OGC (694MB)"},
            },
            "3": {
                "class_type": "SAMModelLoader (segment anything)",
                "inputs": {"model_name": "sam_vit_h (2.56GB)"},
            },
            "4": {
                "class_type": "GroundingDinoSAMSegment (segment anything)",
                "inputs": {
                    "sam_model": ["3", 0],
                    "grounding_dino_model": ["2", 0],
                    "image": ["1", 0],
                    "prompt": text_prompt,
                    "threshold": 0.30,
                },
            },
            "5": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["4", 0],
                    "filename_prefix": f"forge_{index:02d}_{safe_filename(layer_id)}",
                },
            },
        },
        "client_id": uuid.uuid4().hex,
    }


def build_inpaint_workflow(portrait_name: str, joined_prompt: str) -> dict:
    """Fill holes behind all animated layers with LaMa so the base portrait
    can scroll under moving pieces without showing a cut-out silhouette."""
    return {
        "prompt": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": portrait_name},
            },
            "2": {
                "class_type": "GroundingDinoModelLoader (segment anything)",
                "inputs": {"model_name": "GroundingDINO_SwinT_OGC (694MB)"},
            },
            "3": {
                "class_type": "SAMModelLoader (segment anything)",
                "inputs": {"model_name": "sam_vit_h (2.56GB)"},
            },
            "4": {
                "class_type": "GroundingDinoSAMSegment (segment anything)",
                "inputs": {
                    "sam_model": ["3", 0],
                    "grounding_dino_model": ["2", 0],
                    "image": ["1", 0],
                    "prompt": joined_prompt,
                    "threshold": 0.30,
                },
            },
            # AILab_LamaRemover real signature: images, masks, removal_strength, edge_smoothness
            "5": {
                "class_type": "AILab_LamaRemover",
                "inputs": {
                    "images": ["1", 0],
                    "masks": ["4", 1],
                    "removal_strength": 230,
                    "edge_smoothness": 8,
                },
            },
            "6": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["5", 0],
                    "filename_prefix": "forge_base_inpainted",
                },
            },
        },
        "client_id": uuid.uuid4().hex,
    }


# --- Main orchestrator -------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--portrait", required=True, help="Path to reference portrait PNG")
    ap.add_argument("--rig",      required=True, help="Path to rig.json or rig.yaml")
    ap.add_argument("--out",      required=True, help="Output directory for layer PNGs")
    ap.add_argument("--skip-inpaint", action="store_true", help="Do not run LaMa inpaint (faster)")
    ap.add_argument("--only-layer", help="If set, segment JUST this layer id and skip the base inpaint")
    ap.add_argument("--custom-prompt", help="Override the text prompt for the single layer (only-layer mode)")
    args = ap.parse_args()

    portrait_abs = os.path.abspath(args.portrait)
    rig_abs = os.path.abspath(args.rig)
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.isfile(portrait_abs):
        print(json.dumps({"ok": False, "error": f"portrait not found: {portrait_abs}"}))
        return 2
    if not os.path.isfile(rig_abs):
        print(json.dumps({"ok": False, "error": f"rig not found: {rig_abs}"}))
        return 2
    if not comfy_up():
        print(json.dumps({"ok": False, "error": "ComfyUI is not reachable at " + COMFY_URL}))
        return 3

    # Load rig
    with open(rig_abs, "r", encoding="utf-8") as f:
        rig_text = f.read()
    try:
        rig = json.loads(rig_text)
    except json.JSONDecodeError:
        # Try yaml-ish pass-through; the forge service always writes JSON but
        # be forgiving in case a human drops a YAML file.
        try:
            import yaml  # type: ignore
            rig = yaml.safe_load(rig_text)
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"rig parse failed: {e}"}))
            return 2

    all_layers = rig.get("layers", [])
    if args.only_layer:
        layers = [l for l in all_layers if l.get("id") == args.only_layer]
        if not layers:
            print(json.dumps({"ok": False, "error": f"layer id not found: {args.only_layer}"}))
            return 4
        if args.custom_prompt:
            layers[0] = {**layers[0], "prompt": args.custom_prompt}
    else:
        layers = [l for l in all_layers if l.get("kind") and l.get("kind") != "static"]
    if not layers:
        print(json.dumps({"ok": False, "error": "rig has no animated layers (kind != static)"}))
        return 4

    emit(2, f"Upload portrait to ComfyUI ({len(layers)} animated layers)")
    uploaded_name = comfy_upload_image(portrait_abs, os.path.basename(portrait_abs))

    produced: list[dict] = []
    prompts_used: list[str] = []
    for idx, layer in enumerate(layers, start=1):
        layer_id = layer.get("id") or f"layer_{idx}"
        text_prompt = layer_text_prompt(layer_id, layer.get("prompt"))
        prompts_used.append(text_prompt)
        pct = int(5 + (idx / (len(layers) + 1)) * 75)
        emit(pct, f"{layer_id}: SAM2 prompt=\"{text_prompt}\"")

        wf = build_segment_workflow(uploaded_name, layer_id, text_prompt, idx)
        try:
            submit = comfy_post("/prompt", wf)
            prompt_id = submit.get("prompt_id")
            if not prompt_id:
                raise RuntimeError(f"no prompt_id returned: {submit}")
            hist = comfy_poll_until_done(prompt_id, timeout=300)
        except Exception as e:
            emit(pct, f"{layer_id}: skip ({e})")
            produced.append({"layer": layer_id, "ok": False, "error": str(e)})
            continue

        # Grab the SaveImage output (node id "5" in segment workflow)
        outputs = hist.get("outputs", {}).get("5", {})
        imgs = outputs.get("images") or []
        if not imgs:
            produced.append({"layer": layer_id, "ok": False, "error": "no images emitted"})
            continue

        img = imgs[0]
        data = comfy_view(img["filename"], img.get("subfolder", ""), img.get("type", "output"))
        dest = os.path.join(out_dir, f"{idx:02d}_{safe_filename(layer_id)}.png")
        with open(dest, "wb") as f:
            f.write(data)
        produced.append({"layer": layer_id, "ok": True, "path": dest, "prompt": text_prompt})

    # Base layer: inpaint the portrait behind the animated layers so nothing
    # shows through when they displace. Optional because it doubles the time.
    base_path = None
    # Skip LaMa base inpaint in single-layer mode — caller already has a base
    if args.only_layer:
        args.skip_inpaint = True
    if not args.skip_inpaint and produced:
        emit(88, "Inpaint LaMa du portrait base (combler les trous)")
        joined = ", ".join(prompts_used) or "the animated parts"
        wf = build_inpaint_workflow(uploaded_name, joined)
        try:
            submit = comfy_post("/prompt", wf)
            prompt_id = submit.get("prompt_id")
            hist = comfy_poll_until_done(prompt_id, timeout=300)
            imgs = hist.get("outputs", {}).get("6", {}).get("images") or []
            if imgs:
                img = imgs[0]
                data = comfy_view(img["filename"], img.get("subfolder", ""), img.get("type", "output"))
                base_path = os.path.join(out_dir, "00_base.png")
                with open(base_path, "wb") as f:
                    f.write(data)
                emit(95, "Base portrait inpainted prêt")
        except Exception as e:
            emit(88, f"inpaint skipped: {e}")

    emit(100, f"Forge layers prêts ({sum(1 for p in produced if p['ok'])}/{len(produced)})")
    print(json.dumps({
        "ok": True,
        "layers": produced,
        "base": base_path,
        "out_dir": out_dir,
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)
