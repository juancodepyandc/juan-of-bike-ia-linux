# AuroraIA-v2 — Deploiement Cloud RunPod

Guide complet : de la location de la machine au premier test de chaque module.
Budget : **15$/mois max**. Zero installation cote client. 1-clic.

---

## Table des matieres

1. [Architecture Cloud vs Local](#1-architecture)
2. [Tiers GPU — Bas / Mid / Haut](#2-tiers-gpu)
3. [Guide etape par etape](#3-guide-etape-par-etape)
4. [Structure des fichiers cloud](#4-structure-fichiers)
5. [Modifications code appliquees](#5-modifications-code)
6. [Voix sur le cloud](#6-voix)
7. [Recuperer les resultats sur son PC](#7-resultats)
8. [Tests de chaque module](#8-tests)
9. [Budget et optimisation](#9-budget)
10. [FAQ](#10-faq)

---

## 1. Architecture

### Local (AuroraIA-v2 Tauri — inchange)
```
PC de Juan (RTX 5070 Ti 16GB / Ryzen 9 9950X / 32GB RAM)
  └─ Tauri Desktop ←IPC→ Rust backend → Python, Ollama, ComfyUI
```

### Cloud (RunPod — nouveau mode)
```
┌────────────────── RunPod Pod (GPU Cloud) ──────────────────┐
│                                                             │
│  Ollama (:11434)   ComfyUI (:8188)   Python Services       │
│       │                 │                  │                │
│  ┌────┴─────────────────┴──────────────────┴──────┐        │
│  │         Cloud Bridge (FastAPI :3001)            │        │
│  │  - Reverse proxy Ollama + ComfyUI              │        │
│  │  - Execution scripts Python (3D, video, voix)  │        │
│  │  - Filesystem distant (read/write/serve)       │        │
│  │  - STT + TTS endpoints                         │        │
│  │  - Progress polling                            │        │
│  └────────────────────┬───────────────────────────┘        │
│                       │                                     │
│  ┌────────────────────┴───────────────────────────┐        │
│  │         Vite Dev Server (:1420)                │        │
│  │  - Frontend React AuroraIA-v2                  │        │
│  │  - Proxy /api/* et /proxy/* → Bridge           │        │
│  └────────────────────────────────────────────────┘        │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTPS (RunPod Proxy)
                          ↓
┌─────────────────────────────────────────┐
│  Navigateur de Juan (PC local)          │
│  - Micro → MediaRecorder → HTTP → STT  │
│  - TTS audio ← HTTP ← Cloud Bridge     │
│  - Images/Videos/3D en temps reel       │
│  - Aucun GPU local requis              │
└─────────────────────────────────────────┘
```

**Le mode local Tauri reste 100% intact.** Les modifications ajoutent un mode `cloud`
active par `VITE_CLOUD_MODE=true`. Sans cette variable, tout fonctionne comme avant.

---

## 2. Tiers GPU

Le code detecte automatiquement la VRAM du GPU et selectionne les modeles optimaux.

### LOW — RTX 3090 / RTX 4090 (24GB) — ~0.22-0.44$/hr

| Module | Modele | VRAM |
|--------|--------|------|
| LLM Chat | qwen3:14b-q8_0 | ~15GB |
| LLM Code | qwen2.5-coder:14b-q8_0 | ~15GB |
| Vision | qwen3-vl:8b | ~8GB |
| Images | FLUX schnell fp8 | ~12GB |
| Video | LTX-Video | ~9GB |
| 3D | Hunyuan3D 2.1 | ~8GB |
| STT | Whisper large-v3 | ~3GB |
| TTS | Kokoro-82M | ~0.3GB |

**Ideal pour** : Chat, code, images, videos courtes.
**Limite** : Videos longues plus lentes, 3D basique.

### MID — A40 / A6000 (48GB) — ~0.39-0.44$/hr (RECOMMANDE)

| Module | Modele | VRAM |
|--------|--------|------|
| LLM Chat | qwen3:32b (Q6_K) | ~24GB |
| LLM Code | qwen3-coder:30b-a3b | ~20GB |
| Vision | qwen3-vl:30b | ~20GB |
| Images | FLUX dev fp8 | ~13GB |
| Video | Wan 2.2 A14B | ~14GB |
| 3D | Hunyuan3D 2.1 (shape+texture) | ~10GB |
| STT | Voxtral-Small-24B | ~14GB |
| TTS | Kokoro-82M | ~0.3GB |

**Ideal pour** : Tous les modules, qualite elevee, bon compromis budget.
**Performance** : Videos longues OK, 3D avec texture, voix naturelle, autonomie complete.

### HIGH — A100 (80GB) — ~1.09$/hr

| Module | Modele | VRAM |
|--------|--------|------|
| LLM Chat | llama4:scout (MoE 16x17B) | ~67GB |
| LLM Code | qwen3-coder:30b-a3b-q8_0 | ~30GB |
| Vision | qwen3-vl:30b (Q8) | ~30GB |
| Images | FLUX dev fp16 | ~26GB |
| Video | Wan 2.2 A14B (full) | ~20GB |
| 3D | Hunyuan3D 2.1 (full pipeline) | ~10GB |
| STT | Voxtral-Small-24B | ~14GB |
| TTS | Kokoro-82M | ~0.3GB |

**Ideal pour** : Qualite maximale, raisonnement avance, videos longues haute qualite.
**Limite** : ~10h pour 15$, sessions courtes mais puissantes.

### Budget pour 15$/mois

| Tier | GPU | $/hr | Vol. 50GB | Heures GPU |
|------|-----|------|-----------|-----------|
| LOW | RTX 3090 | 0.22$ | 3.50$ | ~52h |
| **MID** | **A40 48GB** | **0.39$** | **3.50$** | **~29h** |
| HIGH | A100 80GB | 1.09$ | 3.50$ | ~10h |

---

## 3. Guide etape par etape

### Etape 1 : Creer un compte RunPod

1. Aller sur **runpod.io** et creer un compte
2. Ajouter 15$ de credit (carte bancaire ou crypto)

### Etape 2 : Creer un Network Volume

1. **Sidebar** → **Storage** → **Network Volumes**
2. **+ Create Network Volume**
   - Nom : `aurora-models`
   - Region : **EU-RO-1** (Europe, moins cher) ou **US-TX-3**
   - Taille : **50 GB**
   - Cliquer **Create**
3. Cout : ~3.50$/mois — stocke les modeles IA + resultats entre sessions

### Etape 3 : Deployer un Pod GPU

1. **Sidebar** → **Pods** → **+ Deploy**
2. **Community Cloud** (moins cher que Secure)
3. Choisir le GPU :
   - **Recommande : A40 48GB** (~0.39$/hr)
   - Alternative budget : RTX 3090 24GB (~0.22$/hr)
   - Alternative puissance : A100 80GB (~1.09$/hr)
4. **Configuration** :
   - Template : **RunPod Pytorch 2.4** (CUDA 12.4, Python 3.11)
   - Container Disk : **20 GB**
   - Volume : selectionner `aurora-models` → Mount path : `/workspace`
   - Expose HTTP Ports : **1420, 3001, 8188**
5. **Deploy**

### Etape 4 : Connexion SSH

Une fois le pod Running :
1. Cliquer sur **Connect** → **SSH** ou **Web Terminal**
2. Pour SSH depuis ton PC :
```bash
# RunPod fournit la commande SSH dans l'interface, ex:
ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519
```

### Etape 5 : Setup initial (une seule fois)

```bash
# 1. Cloner le projet
cd /workspace
git clone <TON_REPO_URL> aurora
# OU uploader un zip via le File Browser RunPod
cd aurora

# 2. Installer les dependances Node.js
npm install

# 3. Installer les dependances Python du bridge
pip install -r cloud/requirements.txt

# 4. Installer Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 5. Installer ComfyUI
git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /opt/comfyui
cd /opt/comfyui && pip install -r requirements.txt
cd /workspace/aurora

# 6. Installer les deps Python AuroraIA
pip install faster-whisper soundfile scipy kokoro>=0.9.4 transformers>=4.45.0 accelerate

# 7. Rendre le script executable
chmod +x cloud/start.sh
```

### Etape 6 : Premier lancement

```bash
cd /workspace/aurora
bash cloud/start.sh
```

Le script :
1. Demarre Ollama
2. Detecte la VRAM et pull les modeles adaptes (premiere fois : 10-20 min)
3. Telecharge les modeles FLUX si absents (premiere fois : 5-10 min)
4. Demarre ComfyUI
5. Demarre le Cloud Bridge (port 3001)
6. Demarre le frontend Vite (port 1420)

**Les telechargements suivants = 0 sec** (tout est sur le Network Volume).

### Etape 7 : Acceder a AuroraIA depuis ton navigateur

Ouvrir dans Chrome/Firefox :
```
https://<POD_ID>-1420.proxy.runpod.net
```

L'URL exacte est dans le dashboard RunPod → ton pod → **Connect** → **HTTP Service [1420]**

L'interface AuroraIA s'affiche. Tous les modules sont actifs.

---

## 4. Structure des fichiers cloud

```
AuroraIA-v2/
├── cloud/                          ← NOUVEAU
│   ├── cloud_bridge.py             ← Serveur API (remplace Tauri IPC)
│   ├── start.sh                    ← Demarrage automatique
│   └── requirements.txt            ← Deps Python du bridge
├── src/
│   ├── utils/runtime.ts            ← +isCloudRuntime()
│   ├── hooks/useTauri.ts           ← +branches cloud pour toutes les fonctions
│   ├── hooks/useVoiceLive.ts       ← +STT/TTS cloud via HTTP
│   └── config/models.ts            ← +CLOUD_MODEL_TIERS (low/mid/high)
├── vite.config.ts                  ← +proxy /api, /proxy vers bridge
├── package.json                    ← +script start:cloud
├── python-services/                ← INCHANGE
├── src-tauri/                      ← INCHANGE (mode local)
└── ...
```

---

## 5. Modifications code appliquees

### `src/utils/runtime.ts`
- RuntimeMode : `'browser' | 'tauri'` → `'browser' | 'tauri' | 'cloud'`
- `isCloudRuntime()` : true quand `VITE_CLOUD_MODE=true`
- `getCloudBridgeUrl()` : URL du bridge

### `src/hooks/useTauri.ts`
- `ollamaBaseUrl()` / `comfyBaseUrl()` : cloud = `/proxy/ollama` et `/proxy/comfy`
- `cloudInvoke()` : fetch vers le bridge
- Progress polling : `_startCloudProgressPolling()` pour `onPythonProgress`
- **Toutes les fonctions** ont une branche `if (isCloudRuntime()) { ... }` :
  - `runPythonScript` → POST `/api/python/run`
  - `runWorkspaceCommand` → POST `/api/command/run`
  - `spawnWorkspaceCommand` → POST `/api/command/spawn`
  - `detectHardware` → GET `/api/hardware`
  - `checkServiceStatus` → GET `/api/services/status`
  - `getWorkspacePath` → GET `/api/fs/workspace-path`
  - `fs*` (exists, mkdir, readText, writeText, readBinary, writeBinary) → POST `/api/fs/*`
  - `runtimeEnsureService` → POST `/api/runtime/ensure-service`
  - `runtimePrepareOllamaModel` → POST `/api/runtime/prepare-model`
  - `toAssetUrl` → `/api/asset/{path}`

### `src/hooks/useVoiceLive.ts`
- `transcribeAudio` : cloud → POST `/api/voice/stt` (FormData avec blob audio)
- `speakText` : cloud → POST `/api/voice/tts` → recoit blob WAV → `Audio.play()`
- Enregistrement micro : identique (MediaRecorder dans le navigateur)

### `src/config/models.ts`
- `CLOUD_MODEL_TIERS` : 3 tiers (low/mid/high) avec modeles par module
- `detectCloudTier(vramGb)` : retourne low/mid/high
- `selectAdaptivePrimaryModel` : en cloud, utilise VRAM pour choisir le tier

### `vite.config.ts`
- Proxy `/api/*` → bridge :3001
- Proxy `/proxy/*` → bridge :3001 (reverse proxy Ollama/ComfyUI)
- `host: '0.0.0.0'` en mode cloud

### `cloud/cloud_bridge.py` (FastAPI)
Serveur complet avec :
- Reverse proxy Ollama (streaming support)
- Reverse proxy ComfyUI
- Execution Python scripts avec capture PROGRESS
- Filesystem operations
- Voice STT (upload audio → transcription)
- Voice TTS (texte → fichier WAV)
- Asset serving (images, videos, 3D)
- Download/list des resultats
- Detection hardware + tier GPU
- Health check

### `cloud/start.sh`
Script bash qui lance tout dans l'ordre :
1. Ollama + pull modeles adaptes au tier
2. Telechargement modeles FLUX si absents
3. ComfyUI
4. Cloud Bridge
5. Vite frontend

---

## 6. Voix sur le cloud

Aucune commande speciale necessaire. Le flux :

1. **Enregistrement** : Le navigateur local utilise `MediaRecorder` (micro du PC)
2. **Envoi** : Le blob audio est envoye au Cloud Bridge via `POST /api/voice/stt`
3. **STT** : Le pod GPU execute Voxtral-Small-24B (ou Whisper) → transcription texte
4. **LLM** : Le texte va a Ollama via le proxy → reponse IA
5. **TTS** : `POST /api/voice/tts` → le pod genere un WAV avec Kokoro
6. **Lecture** : Le navigateur recoit le WAV et le joue sur les haut-parleurs

Le ton naturel/emotif vient du system prompt LLM + Kokoro voix `ff_siwis`.
Tout tourne sur le cloud, rien a configurer cote client.

---

## 7. Recuperer les resultats sur son PC

### Methode 1 — Telechargement via le bridge

Le Cloud Bridge expose :
- `GET /api/download/list` : liste tous les fichiers generes par categorie
- `GET /api/download/{category}/{filename}` : telecharge un fichier

Categories : `images`, `videos`, `models3d`, `voice`, `saves`

### Methode 2 — SCP depuis le terminal

```bash
# Images
scp -P <PORT> root@<IP>:/workspace/output/images/* ~/Desktop/aurora-results/images/

# Videos
scp -P <PORT> root@<IP>:/workspace/output/videos/* ~/Desktop/aurora-results/videos/

# Modeles 3D (GLB, OBJ, STL)
scp -P <PORT> root@<IP>:/workspace/output/models3d/* ~/Desktop/aurora-results/3d/

# Sauvegardes de sessions
scp -P <PORT> root@<IP>:/workspace/output/saves/* ~/Desktop/aurora-results/saves/

# TOUT d'un coup
scp -rP <PORT> root@<IP>:/workspace/output/ ~/Desktop/aurora-results/
```

### Methode 3 — File Browser RunPod

Dans le dashboard RunPod : pod → **Connect** → **File Browser**
Naviguer vers `/workspace/output/` et telecharger.

### Formats des fichiers generes

| Module | Format | Exploitable dans |
|--------|--------|-----------------|
| Images | PNG | Photoshop, GIMP, tout editeur |
| Videos | MP4 | Premiere, DaVinci, VLC |
| 3D | GLB, OBJ | Blender, imprimante 3D (STL via Blender) |
| 3D imprimable | STL (export Blender) | Cura, PrusaSlicer |
| Voix | WAV | Audacity, tout lecteur |
| Saves | JSON | Rechargeable dans AuroraIA |

### Pour l'impression 3D

Les modeles GLB/OBJ generes par Hunyuan3D sont convertis en mesh.
Pour imprimer en 3D :
1. Ouvrir le GLB dans Blender (deja installe sur le pod)
2. Le script `blender_bridge.py` peut exporter en STL
3. Verifier : manifold, wall thickness, supports
4. Charger le STL dans le slicer (Cura, PrusaSlicer)

---

## 8. Tests de chaque module

Apres le premier lancement (`bash cloud/start.sh`), ouvrir l'URL RunPod dans le navigateur.

### 8.1 Verification services

```bash
# Sur le pod via SSH
nvidia-smi                                        # GPU + VRAM
curl http://127.0.0.1:11434/api/tags | python -m json.tool   # Ollama models
curl http://127.0.0.1:8188/system_stats | python -m json.tool # ComfyUI
curl http://127.0.0.1:3001/api/health | python -m json.tool   # Cloud Bridge
curl http://127.0.0.1:3001/api/cloud/tier | python -m json.tool # Tier GPU
```

### 8.2 Test Conversation (LLM)

1. Ouvrir le module **Copilote** dans le sidebar
2. Taper : "Explique-moi comment fonctionne un moteur electrique"
3. Verifier :
   - [ ] Reponse en streaming (tokens apparaissent un par un)
   - [ ] Reponse coherente et detaillee
   - [ ] Ton naturel en francais

### 8.3 Test Image (FLUX)

1. Ouvrir le module **Image**
2. Prompt : "Un chateau medieval au coucher de soleil, style peinture a l'huile"
3. Verifier :
   - [ ] Image generee et affichee dans l'interface
   - [ ] Qualite haute (details, couleurs)
   - [ ] Possibilite de telecharger le PNG

### 8.4 Test Video (Wan 2.2 / LTX-Video)

1. Ouvrir le module **Video**
2. Prompt : "Un chat qui joue avec une balle de laine, mouvement fluide"
3. Verifier :
   - [ ] Video generee et jouable dans l'interface
   - [ ] Mouvements fluides
   - [ ] Possibilite de telecharger le MP4

### 8.5 Test 3D (Hunyuan3D)

1. Ouvrir le module **3D**
2. Prompt : "Un engrenage mecanique imprimable en 3D"
3. Verifier :
   - [ ] Modele 3D genere et visible dans le viewer Three.js
   - [ ] Rotation/zoom fonctionnent
   - [ ] Export GLB/OBJ disponible

### 8.6 Test Code

1. Ouvrir le module **Code**
2. Prompt : "Cree une page web responsive avec un header, une grille de cards et un footer"
3. Verifier :
   - [ ] Code genere avec coloration syntaxique
   - [ ] Apercu fonctionnel
   - [ ] Auto-correction active

### 8.7 Test Voix

1. Dans le module **Copilote**, cliquer sur le bouton micro
2. Parler : "Bonjour, comment tu t'appelles ?"
3. Verifier :
   - [ ] Phase "Ecoute" s'active (micro vert)
   - [ ] Transcription automatique apres silence
   - [ ] Reponse LLM en texte
   - [ ] Reponse vocale (TTS) avec ton naturel

### 8.8 Test Sauvegarde / Reprise

1. Generer quelques resultats (image, conversation)
2. Sauvegarder la session
3. Arreter le pod (RunPod dashboard → Stop)
4. Relancer le pod + `bash cloud/start.sh`
5. Verifier :
   - [ ] Les modeles sont deja la (pas de re-telechargement)
   - [ ] Les sauvegardes sont recuperables
   - [ ] Les resultats precedents sont dans `/workspace/output/`

### 8.9 Test Telechargement resultats

```bash
# Depuis le PC local (remplacer IP et PORT)
scp -rP <PORT> root@<IP>:/workspace/output/ ~/Desktop/aurora-cloud/

# Verifier que les fichiers s'ouvrent :
# - PNG dans un viewer d'images
# - MP4 dans VLC
# - GLB dans https://gltf-viewer.donmccurdy.com/
```

---

## 9. Budget et optimisation

### Ne pas gaspiller

1. **TOUJOURS arreter le pod** quand tu ne l'utilises pas
   - RunPod dashboard → ton pod → **Stop**
   - Le Network Volume reste (modeles + resultats preserves)
   - Tu ne paies le GPU que quand le pod tourne

2. **Spot instances** : Si disponibles, ~30% moins cher (peut etre interrompu)

3. **Community Cloud** : Toujours moins cher que Secure Cloud

4. **Premiere session** : Prevoir ~30 min de GPU pour les telechargements
   Toutes les sessions suivantes : ~30 sec de boot

### Suivi conso

- RunPod dashboard → **Billing** → voir les depenses en temps reel
- Configurer une alerte budget a 14$ pour eviter les surprises

---

## 10. FAQ

**Q: Mon mode local Tauri est-il modifie ?**
Non. Sans `VITE_CLOUD_MODE=true`, le code fonctionne exactement comme avant.
Les branches cloud sont ignorees quand `isCloudRuntime()` retourne false.

**Q: Faut-il un GPU local pour le mode cloud ?**
Non. Le navigateur fait uniquement l'affichage + micro/haut-parleurs.

**Q: La voix fonctionne sans installation locale ?**
Oui. `MediaRecorder` (micro) et `Audio` (haut-parleurs) sont natifs au navigateur.
Le STT et TTS tournent sur le pod.

**Q: Mes resultats sont perdus si j'arrete le pod ?**
Non, si tu as un Network Volume. `/workspace/` persiste entre sessions.

**Q: Les fichiers 3D sont-ils imprimables ?**
Les GLB/OBJ de Hunyuan3D sont des meshes. Pour imprimer :
GLB → Blender → Export STL → Slicer (Cura/PrusaSlicer).
Le bridge Blender (`blender_bridge.py`) automatise la conversion.

**Q: Comment changer de tier GPU ?**
Arreter le pod → Deployer un nouveau pod avec un autre GPU.
Le Network Volume reste le meme, les modeles sont preserves.
Les modeles du nouveau tier seront pulls automatiquement par `start.sh`.

**Q: Puis-je reprendre un projet commence en local ?**
Oui. Copier les saves de `%APPDATA%\AuroraIA\saves\` vers `/workspace/output/saves/` sur le pod.

**Q: Comment voir les logs en cas de probleme ?**
```bash
tail -f /tmp/ollama.log         # Ollama
tail -f /tmp/comfyui.log        # ComfyUI
tail -f /tmp/cloud_bridge.log   # Cloud Bridge
tail -f /tmp/vite.log           # Frontend
```
