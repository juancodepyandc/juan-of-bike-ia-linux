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
    # 31/07 (recherche): ref_scale renforce l'IMAGE sans renforcer le texte
    # (la branche inconditionnelle a la reference a zero) — c'est LE levier
    # anti-derive d'identite. Exposes pour la porte corrective du pipeline.
    ap.add_argument("--guidance_scale", type=float, default=3.0)
    ap.add_argument("--reference_conditioning_scale", type=float, default=1.0)
    ap.add_argument("--negative_prompt", default="watermark, ugly, deformed, disfigured, wrong anatomy, different person")
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
    # init_custom_adapter DUPLIQUE les modules d'attention de l'UNet; par defaut
    # ils naissent en fp32 (~20 Go d'anon mesures a l'OOM kernel: anon-rss 19.8G
    # en 16 s). En fp16 des la creation: moitie moins, l'init tient dans le
    # plafond memoire au lieu d'exiger une machine vide.
    torch.set_default_dtype(torch.float16)
    try:
        pipe.init_custom_adapter(num_views=num_views)
    finally:
        torch.set_default_dtype(torch.float32)
    pipe.load_custom_adapter("huanngzh/mv-adapter",
                             weight_name="mvadapter_i2mv_sdxl.safetensors")
    pipe.to(dtype=torch.float16)
    pipe.enable_vae_slicing()
    # PLEIN GPU comme le vendor. L'offload CPU casse l'attention-reference de
    # MV-Adapter (KeyError 'attn1.processor': le cache des etats de reference
    # n'est pas peuple sous hooks d'offload — teste, plante a l'inference). La
    # boite noire montre que la VRAM n'a jamais ete la cause des gels (toujours
    # basse aux morts): le vrai gain est le chargement fp16 (RAM /2) ci-dessus.
    # PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True (pose par l'appelant)
    # reduit la gourmandise de l'allocateur (~15.8G observes en vendor).
    pipe.to("cuda")
    pipe.cond_encoder.to(device="cuda", dtype=torch.float16)
    # Rendre a l'OS les arenes hote liberees par le transfert GPU: sans ca la RSS
    # reste a ~14.7G (arenes retenues) et l'inference empile par-dessus -> 27.5G
    # mesures = ne tient que sur machine vide. Apres trim: le pic total tient
    # dans le plafond memoire du pipeline.
    import ctypes
    import gc
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:  # noqa: BLE001
        pass
    print("[offload] fp16 direct + plein GPU + malloc_trim (offload retire: casse l'attention-reference)",
          flush=True)

    # ENTREE = RGBA OBLIGATOIRE (27/07, cause racine du multi-vues).
    # Le vendor n'appelle son preprocess_image QUE si remove_bg_fn est fourni
    # OU si l'image est RGBA (inference_i2mv_sdxl.py:152-156). En compositant
    # sur blanc et en passant du RGB, on sautait: recadrage sur la boite du
    # sujet, mise a l'echelle 0.9, centrage, resize 768x768 et surtout le
    # FOND GRIS 128 qui est le zero du VAE et la convention d'entrainement de
    # MV-Adapter. D'ou des vues hors distribution: decor halluciné, aplats
    # noirs, derive d'identite. On garantit donc un alpha.
    try:
        from PIL import Image as _Im
        _src = _Im.open(args.image)
        if "A" not in _src.getbands():
            try:
                from rembg import remove as _rembg
                # matting: les cheveux/meches survivent au detourage (31/07)
                try:
                    _src = _rembg(_src.convert("RGB"), alpha_matting=True,
                                  alpha_matting_foreground_threshold=240,
                                  alpha_matting_background_threshold=15,
                                  alpha_matting_erode_size=5)
                except Exception:  # noqa: BLE001 - PYMATTING PLANTE: masque simple
                    _src = _rembg(_src.convert("RGB"))
                print("[offload] alpha cree (rembg) pour le pretraitement vendor",
                      flush=True)
            except Exception as _re:  # noqa: BLE001
                print("[offload] rembg indisponible (%r) — alpha opaque force"
                      % (_re,), flush=True)
                _src = _src.convert("RGBA")
        else:
            _src = _src.convert("RGBA")
        _tmp = args.output + ".entree_rgba.png"
        _src.save(_tmp)
        args.image = _tmp
        print("[offload] entree RGBA -> preprocess vendor actif "
              "(bbox 0.9, 768x768, fond gris 128)", flush=True)
    except Exception as _e:  # noqa: BLE001
        print("[offload] preparation RGBA impossible (%r) — entree brute"
              % (_e,), flush=True)

    images, _ref = vendor.run_pipeline(
        pipe,
        num_views=num_views,
        text=args.text,
        image=args.image,
        height=768,
        width=768,
        num_inference_steps=args.num_inference_steps,
        guidance_scale=args.guidance_scale,
        seed=args.seed,
        remove_bg_fn=None,
        device="cuda",
        azimuth_deg=args.azimuth_deg,
        reference_conditioning_scale=args.reference_conditioning_scale,
        negative_prompt=args.negative_prompt,
    )
    vendor.make_image_grid(images, rows=1).save(args.output)
    print("[offload] strip ecrite: %s" % args.output, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
