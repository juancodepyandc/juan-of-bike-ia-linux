"""Direct LTX-Video render — bypasses video_generate.py's strategy chain.

Why this exists: video_generate.py uses an "ltx_group" offload mode that
deadlocks on PyTorch 2.12 nightly + Blackwell sm_120 (the user's environment).
A minimal call with no offload completes the same workload in ~3 minutes
instead of hanging indefinitely. Cinema pipeline calls this directly.

Usage:
    python ltx_direct_render.py --prompt "..." --output out.mp4 \
        [--width 768] [--height 432] [--num-frames 49] [--num-steps 30]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--negative", default="blurry, low quality, distorted anatomy, artifacts, watermark, frozen frame, static image, no motion")
    ap.add_argument("--output", required=True)
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--height", type=int, default=432)
    ap.add_argument("--num-frames", type=int, default=49)
    ap.add_argument("--num-steps", type=int, default=30)
    ap.add_argument("--guidance", type=float, default=3.2)
    # If set, the rendered frames are stretched onto exactly this many seconds
    # of playback (export_fps = num_frames / target_duration). This lets the
    # caller fit the clip to a known voice duration WITHOUT freeze-padding.
    # The output is then frame-interpolated up to 24 fps for smooth motion.
    ap.add_argument("--target-duration", type=float, default=0.0)
    args = ap.parse_args()

    # Round to multiples of 32 (LTX requirement)
    w = (args.width // 32) * 32
    h = (args.height // 32) * 32
    if w < 256: w = 256
    if h < 256: h = 256

    emit("init", f"Direct LTX path width={w} height={h} frames={args.num_frames} steps={args.num_steps}")

    try:
        import torch
        from diffusers import LTXPipeline
        from diffusers.utils import export_to_video
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"import failed: {exc}"}), flush=True)
        return 2

    if not torch.cuda.is_available():
        print(json.dumps({"ok": False, "error": "CUDA not available"}), flush=True)
        return 2

    t0 = time.time()
    emit("loading", "LTX pipeline (cache local)")
    try:
        pipe = LTXPipeline.from_pretrained(
            "Lightricks/LTX-Video",
            torch_dtype=torch.bfloat16,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"pipeline load failed: {exc}"}), flush=True)
        return 3

    emit("gpu_move", f"VRAM available: {torch.cuda.mem_get_info()[0] / 1e9:.1f} GB")
    pipe.to("cuda")
    emit("loaded", f"On GPU in {time.time() - t0:.1f}s, VRAM used {torch.cuda.memory_allocated() / 1e9:.1f} GB")

    def _on_step_end(_pipe, step_index, _t, kw):
        emit("step", f"{step_index + 1}/{args.num_steps}")
        return kw

    t1 = time.time()
    emit("sampling", f"Starting {args.num_steps} steps")
    try:
        result = pipe(
            prompt=args.prompt,
            negative_prompt=args.negative,
            width=w,
            height=h,
            num_frames=args.num_frames,
            num_inference_steps=args.num_steps,
            guidance_scale=args.guidance,
            # Lower decode noise = sharper first frames + fewer hallucinations
            # at the start of the clip. 0.025 was leaving ~5 noisy frames at
            # the head; 0.012 collapses that to 1-2 frames at most.
            decode_timestep=0.025,
            decode_noise_scale=0.012,
            callback_on_step_end=_on_step_end,
        )
    except Exception as exc:
        # Free VRAM in case of error so the next attempt has room
        del pipe
        torch.cuda.empty_cache()
        print(json.dumps({"ok": False, "error": f"sampling failed: {exc}"}), flush=True)
        return 4
    sample_s = time.time() - t1

    frames = result.frames[0]
    emit("encoding", f"{len(frames)} frames produced in {sample_s:.1f}s")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Compute the export fps so the rendered frames fully cover the requested
    # target duration (no freeze-padding needed). If no target was given, fall
    # back to LTX's native 24 fps.
    if args.target_duration > 0.1:
        # Floor at 8 fps so motion stays watchable, cap at 24 so a short
        # target doesn't fast-forward.
        export_fps = max(8.0, min(24.0, len(frames) / float(args.target_duration)))
    else:
        export_fps = 24.0
    emit("export_fps", f"{export_fps:.2f} fps for {len(frames)} frames -> {len(frames) / export_fps:.2f}s")

    # Write the sampled frames at the adaptive fps first
    raw_path = out_path.with_suffix(".raw.mp4")
    try:
        export_to_video(frames, str(raw_path), fps=export_fps)
    except TypeError:
        export_to_video(frames, str(raw_path))

    # Free VRAM before the ffmpeg pass so we don't keep 14 GB pinned
    del pipe
    torch.cuda.empty_cache()

    # Frame-interpolate the (potentially low-fps) raw to a smooth 24 fps via
    # ffmpeg's `minterpolate` motion estimator -- this is how RIFE works in
    # spirit, but built into ffmpeg with no extra deps. On a 6 s clip the
    # extra pass costs ~5 s and the perceived motion goes from "slideshow"
    # to "fluid".
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg = "ffmpeg"

    if export_fps < 23.5:
        emit("interpolate", f"minterpolate {export_fps:.1f} -> 24 fps")
        cmd = [
            ffmpeg, "-y",
            "-i", str(raw_path),
            "-vf", f"minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-loglevel", "error",
            str(out_path),
        ]
        import subprocess
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            # Fallback: just rename the raw without interpolation
            try:
                raw_path.rename(out_path)
            except Exception:
                pass
            emit("interpolate_warn", proc.stderr[-200:] if proc.stderr else "minterpolate failed")
        else:
            try:
                raw_path.unlink()
            except Exception:
                pass
    else:
        # No interpolation needed -- just rename
        try:
            if out_path.exists():
                out_path.unlink()
            raw_path.rename(out_path)
        except Exception:
            pass

    print(json.dumps({
        "ok": True,
        "output": str(out_path),
        "frames": len(frames),
        "export_fps": round(export_fps, 2),
        "sample_seconds": round(sample_s, 1),
        "total_seconds": round(time.time() - t0, 1),
        "size_bytes": out_path.stat().st_size if out_path.exists() else 0,
    }), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
