# AuroraIA Linux / Blackwell Migration

## Recommendation

Use Ubuntu 24.04 LTS on bare metal. It is the safest target for NVIDIA Blackwell, CUDA, PyTorch, Tauri, ComfyUI, Blender, cloudflared and 3D CUDA extensions.

Detected migration target:

- CPU: AMD Ryzen 9 9950X.
- RAM: 32 GB.
- GPU: NVIDIA GeForce RTX 5070 Ti, 16 GB VRAM.
- GPU architecture: Blackwell, compute capability 12.0.

## Hard truth on TRELLIS.2

Linux is worth it for this workstation, but TRELLIS.2 is not guaranteed in full local mode on this GPU. Microsoft lists TRELLIS.2 as Linux-tested and requires at least 24 GB VRAM, verified on A100/H100. The RTX 5070 Ti has 16 GB VRAM.

That means:

- Hunyuan3D 2.1 PBR remains the best realistic local 3D production path.
- TRELLIS.2 is installed as an experimental Linux stack, ready for low-resolution/offload attempts or a future 24 GB+ GPU.
- For guaranteed TRELLIS.2 quality, use 24 GB+ local GPU or cloud GPU.

## One-shot install on Linux

```bash
git clone https://github.com/juancodepyandc/juan-of-bike-ia-linux.git
cd juan-of-bike-ia-linux

bash scripts/linux/aurora-first-run.sh --max-quality --with-trellis2
```

The first Tauri launch on Linux also runs a runtime check. If host tools,
ComfyUI, Hunyuan3D, the Python venv, PyTorch CUDA, Ollama, Blender or
cloudflared are missing, Tauri opens a Linux terminal and starts the same
first-run initializer from the repository.

Manual equivalent:

```bash
bash scripts/linux/bootstrap-ubuntu2404.sh --install-nvidia-driver
# reboot if the NVIDIA driver was installed or changed

bash scripts/linux/install-aurora-stack.sh --with-hunyuan --with-comfyui --prefetch-models --max-quality
bash scripts/linux/install-trellis2.sh
bash scripts/linux/install-ollama-models.sh --max-quality
bash scripts/linux/verify-linux-stack.sh
```

## Run

```bash
./start-aurora.sh
```

With Cloudflare quick tunnel:

```bash
AURORA_START_TUNNEL=1 ./start-aurora.sh
```

The repository intentionally excludes generated outputs, local secrets, ComfyUI installs, model weights and CUDA/tool caches. The Linux scripts recreate the runtime locally after cloning.
