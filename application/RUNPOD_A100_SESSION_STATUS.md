# RunPod A100 session status - AuroraIA-v2

Date: 2026-04-11

This file records the live RunPod machine selected for the AuroraIA-v2 premium cloud path, so Claude/Codex can continue from the verified state instead of re-discussing hardware.

## Verified pod

User ran:

```bash
nvidia-smi
df -h /workspace
echo $RUNPOD_POD_ID
echo $RUNPOD_PUBLIC_IP
echo $RUNPOD_TCP_PORT_22
```

Observed:

- Pod id: `ewbt172rf41o5c`
- Public IP: `195.26.233.76`
- SSH TCP port: `45726`
- GPU: `NVIDIA A100-SXM4-80GB`
- VRAM: `81920 MiB`
- Driver: `570.124.06`
- CUDA: `12.8`
- GPU memory used before install: `1 MiB`
- `/workspace` mount: `mfs#us-wa-1.runpod.net:9421`
- `df -h /workspace` showed a shared filesystem with large available capacity.

## Decision

Use the stable NVIDIA/CUDA path:

- `1x A100 SXM 80GB`
- Runpod PyTorch template
- AuroraIA-v2 cloud launcher: `cloud/start.sh`
- Workspace: `/workspace/aurora`
- Outputs: `/workspace/output`
- Models: `/workspace/models`

Do not switch to MI300X/ROCm for this first stable session. The current AuroraIA-v2 cloud path uses NVIDIA/CUDA assumptions (`nvidia-smi`, CUDA PyTorch, ComfyUI CUDA path).

## Next pod commands

Install system/runtime prerequisites:

```bash
apt-get update
apt-get install -y curl wget git unzip ffmpeg ca-certificates
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs
node -v
npm -v
python -m pip install --upgrade pip setuptools wheel
curl -fsSL https://ollama.com/install.sh | sh
git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /opt/comfyui
python -m pip install -r /opt/comfyui/requirements.txt
```

Then put AuroraIA-v2 in `/workspace/aurora`, either by Git clone or ZIP upload.

Launch:

```bash
cd /workspace/aurora
npm install
python -m pip install -r cloud/requirements.txt
chmod +x cloud/start.sh
export AURORA_WORKSPACE=/workspace/aurora
export AURORA_OUTPUT=/workspace/output
export AURORA_MODELS=/workspace/models
bash cloud/start.sh
```

Expected URL:

```text
https://ewbt172rf41o5c-1420.proxy.runpod.net
```

For download via SCP from Windows later:

```powershell
mkdir "$env:USERPROFILE\Desktop\aurora-results" -Force
scp -P 45726 -r root@195.26.233.76:/workspace/output/* "$env:USERPROFILE\Desktop\aurora-results\"
```

## Immediate checks after launch

Inside pod:

```bash
curl http://127.0.0.1:11434/api/tags
curl http://127.0.0.1:8188/system_stats
curl http://127.0.0.1:3001/api/health
```

From browser:

```text
https://ewbt172rf41o5c-1420.proxy.runpod.net
https://ewbt172rf41o5c-1420.proxy.runpod.net/api/health
https://ewbt172rf41o5c-1420.proxy.runpod.net/api/download/list
```

