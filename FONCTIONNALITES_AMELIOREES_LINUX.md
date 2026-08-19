# Fonctionnalites ameliorees Linux

## Verdict OS

Le meilleur choix pour cette machine est Ubuntu 24.04 LTS en bare metal. C'est la cible la plus propre pour NVIDIA Blackwell, CUDA, PyTorch, Tauri, Blender, ComfyUI, cloudflared et les extensions CUDA de TRELLIS/Hunyuan.

Profil detecte cote Windows avant migration:

- CPU: AMD Ryzen 9 9950X, 16 coeurs / 32 threads.
- RAM: 32 GB.
- GPU: NVIDIA GeForce RTX 5070 Ti, 16 GB VRAM.
- Architecture GPU: Blackwell, compute capability 12.0.

## Decision TRELLIS.2

TRELLIS.2 est le meilleur choix qualite si on vise PBR tres haute fidelite et topologie complexe, mais il n'est pas garanti en local complet sur cette carte. Microsoft liste Linux comme cible testee, 24 GB VRAM minimum, avec verification sur A100/H100. Ta RTX 5070 Ti a 16 GB: Linux peut regler les problemes Windows/CUDA, mais pas ajouter les 8 GB manquants.

Decision:

- Oui a Linux pour augmenter fortement la compatibilite Blackwell et CUDA.
- Oui a l'installation TRELLIS.2 dans le repo Linux comme stack experimentale.
- Non a la promesse "TRELLIS.2 full local garanti" sur RTX 5070 Ti 16 GB.
- Pour TRELLIS.2 stable: viser 24 GB+ VRAM local, ou A40/A6000/A100/H100 cloud.

## Meilleurs modeles par module

| Module | Choix Linux recommande | Raison |
| --- | --- | --- |
| 3D local production | Hunyuan3D 2.1 PBR + Blender cleanup | Fonctionne mieux dans 16 GB via stages serialises et low VRAM. |
| 3D max qualite experimental | TRELLIS.2-4B | Superieur pour PBR/topologie, mais 24 GB VRAM recommande. |
| 3D fallback rapide | Stable Fast 3D / DreamGaussian | Utile pour preview ou sujets stylises si Hunyuan/TRELLIS bloque. |
| Images | FLUX FP8 + T5 XXL FP8 | Bon compromis qualite/VRAM pour 16 GB. |
| Video local | Wan2.2 TI2V 5B + LTX fallback | A14B est plutot cloud/24GB+, le 5B est le chemin local realiste. |
| Vision | Qwen3-VL 8B live, Qwen3-VL 30B qualite | 8B rapide en VRAM, 30B avec offload CPU si besoin. |
| Code | Qwen3-Coder 30B-A3B Q4, Qwen3-Coder-Next Q4 si disque/RAM OK | Meilleur niveau code local; Next est plus lourd et peut offloader. |
| Chat general | Qwen3 14B | Meilleur ratio qualite/performance sur 16 GB VRAM + 32 GB RAM. |
| STT/TTS | Voxtral Small 24B + Kokoro, fallback Whisper | Qualite max avec fallback plus leger. |

## Installation Linux depuis GitHub

```bash
git clone https://github.com/juancodepyandc/juan-of-bike-ia-linux.git
cd juan-of-bike-ia-linux

bash scripts/linux/aurora-first-run.sh --max-quality --with-trellis2
```

Le premier lancement Tauri sous Linux lance aussi le check runtime et ouvre
un terminal d'installation si une dependance manque.

Equivalent manuel detaille:

```bash
bash scripts/linux/bootstrap-ubuntu2404.sh --install-nvidia-driver
# reboot si le driver NVIDIA vient d'etre installe

bash scripts/linux/install-aurora-stack.sh --with-hunyuan --with-comfyui --prefetch-models --max-quality
bash scripts/linux/install-trellis2.sh
bash scripts/linux/install-ollama-models.sh --max-quality
bash scripts/linux/verify-linux-stack.sh
```

Demarrage local:

```bash
./start-aurora.sh
```

Le tunnel Cloudflare et la synchronisation de `aurora-live/tunnel.txt` sont
actifs par defaut. Pour lancer sans exposition publique:

```bash
AURORA_START_TUNNEL=0 ./start-aurora.sh
```

## Ce qui n'est pas commite

Le repo Linux ne doit pas contenir les outputs, poids, caches, secrets, ComfyUI installe, snapshots Hugging Face, GLB generes, videos generees, logs, ni dossiers de build. Les scripts les recreent ou les telechargent sur la machine Linux.
