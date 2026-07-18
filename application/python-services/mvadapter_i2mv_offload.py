"""mvadapter_i2mv_offload.py — MV-Adapter i2mv avec offload CPU (anti-saturation VRAM).

Le script vendor (scripts/inference_i2mv_sdxl.py) charge SDXL entierement sur le GPU:
pic mesure 15.8 Go sur une carte de 16.3 Go -> le compositeur du bureau n'a plus de
VRAM, l'affichage se fige. Ce runner reutilise les MEMES fonctions vendor
(prepare_pipeline / run_pipeline, chargees par chemin) et applique
`enable_model_cpu_offload()`: un seul module (unet OU vae OU text encoder) reside sur
le GPU a la fois -> pic ~5-7 Go, sortie STRICTEMENT identique (memes poids, meme
seed), juste un peu plus lent.

Execute dans l'env conda `mvadapter` (comme le vendor). Args = sous-ensemble du
vendor utilises par mvadapter_multiview.py.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys


def _load_vendor(mv_root: str):
    path = os.path.join(mv_root, "scripts", "inference_i2mv_sdxl.py")
    spec = importlib.util.spec_from_file_location("vendor_i2mv", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["vendor_i2mv"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--text", default="high quality")
    ap.add_argument("--output", default="output.png")
    ap.add_argument("--num_inference_steps", type=int, default=50)
    ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--azimuth_deg", type=int, nargs="+",
                    default=[0, 45, 90, 180, 270, 315])
    args = ap.parse_args()

    mv_root = os.environ.get(
        "MV_ROOT", os.path.expanduser("~/.local/share/auroraia/external/MV-Adapter"))
    vendor = _load_vendor(mv_root)

    import torch  # noqa: WPS433 (dans l'env mvadapter)
    from diffusers import AutoencoderKL  # noqa: WPS433
    from mvadapter.pipelines.pipeline_mvadapter_i2mv_sdxl import (  # noqa: WPS433
        MVAdapterI2MVSDXLPipeline)
    from mvadapter.schedulers.scheduling_shift_snr import ShiftSNRScheduler  # noqa: WPS433

    num_views = len(args.azimuth_deg)
    # Chargement DIRECT en fp16 (torch_dtype au from_pretrained): les tenseurs sont
    # castes A LA LECTURE -> pic RAM ~7 Go. Le prepare_pipeline vendor chargeait en
    # fp32 (~14 Go transitoires) puis castait: c'est ce pic qui debordait le plafond
    # memoire et faisait churner le swap (gel machine constate a la boite noire).
    vae = AutoencoderKL.from_pretrained("madebyollin/sdxl-vae-fp16-fix",
                                        torch_dtype=torch.float16)
    pipe = MVAdapterI2MVSDXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        vae=vae, torch_dtype=torch.float16)
    pipe.scheduler = ShiftSNRScheduler.from_scheduler(
        pipe.scheduler, shift_mode="interpolated", shift_scale=8.0,
        scheduler_class=None)
    pipe.init_custom_adapter(num_views=num_views)
    pipe.load_custom_adapter("huanngzh/mv-adapter",
                             weight_name="mvadapter_i2mv_sdxl.safetensors")
    pipe.to(dtype=torch.float16)
    pipe.enable_vae_slicing()
    # LE fix VRAM: un module a la fois sur le GPU (pic ~5-7 Go au lieu de 15.8 qui
    # privait l'affichage). Le cond_encoder (petit) n'est pas toujours couvert par
    # la sequence d'offload diffusers -> on le garde sur le GPU.
    try:
        pipe.enable_model_cpu_offload()
        try:
            pipe.cond_encoder.to(device="cuda", dtype=torch.float16)
        except Exception:  # noqa: BLE001
            pass
        print("[offload] fp16 direct + enable_model_cpu_offload actifs", flush=True)
    except Exception as exc:  # noqa: BLE001
        pipe.to("cuda")
        pipe.cond_encoder.to(device="cuda", dtype=torch.float16)
        print("[offload] indisponible (%r) -> full GPU" % exc, flush=True)

    images, _ref = vendor.run_pipeline(
        pipe,
        num_views=num_views,
        text=args.text,
        image=args.image,
        height=768,
        width=768,
        num_inference_steps=args.num_inference_steps,
        guidance_scale=3.0,
        seed=args.seed,
        remove_bg_fn=None,
        device="cuda",
        azimuth_deg=args.azimuth_deg,
    )
    vendor.make_image_grid(images, rows=1).save(args.output)
    print("[offload] strip ecrite: %s" % args.output, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
