# juan of bike IA — AuroraIA-v2

Copilote IA local · Tauri + React + Python · 100 % offline.

9 modules interactifs :
- **Conversation** · chat Ollama streaming avec pièces jointes (texte + images via Qwen3-VL) et narration
- **Academy** · cours / fiches BAC / exos / quiz générés par IA, exam blanc, grading, hints progressifs, révision Leitner, export PDF / Anki
- **Image** · atelier FLUX avec wheel de styles
- **Vidéo** · Wan2.2 T2V/I2V · projecteur cinéma
- **Code** · modèle expert · collection de cartes, diff viewer
- **Dessin** · sumi-e + sketch2img
- **3D** · Hunyuan3D · DreamGaussian · Blender · Meshroom
- **Voice** · copilote vocal continu avec caméra + vision + Character Forge
- **Cyber** · dojo de katas · labs IA interactifs · grading + flag auto-validation

## Stack

- **Frontend** : Tauri v2 + React 19 + TypeScript + Vite + Tailwind v4
- **Backend local** : Ollama, ComfyUI, bridge Python Flask
- **Modèles** : qwen3-vl, SAM2, GroundingDINO, BiRefNet, LaMa, FLUX, Wan2.2, Hunyuan3D

## Démarrage

```bash
cd application
npm install
npm run dev               # Vite dev server on :1420
python bridge_server.py   # Python bridge on :3001 (runtime invoque ComfyUI à la demande)
```

Migration Linux / Blackwell / Trellis : voir [LINUX_MIGRATION.md](LINUX_MIGRATION.md).

## Structure

```
AuroraIA-v2/
├─ application/
│  ├─ src/                # React + TS
│  ├─ src-tauri/          # Rust Tauri shell
│  ├─ python-services/    # scripts Python (Forge, layers, BAC resources, …)
│  ├─ bridge_server.py    # passerelle Flask entre front et Python
│  └─ public/             # assets statiques
└─ modele/                # ComfyUI + poids (exclus du repo via .gitignore)
```

## Fonctionnalités avancées

- **Character Forge** : pipeline 8 étapes (intent → traits → rig → portrait → variations → segmentation → assemblage → publish) avec reprise sur reload et file d'attente
- **Mobile Grimoire** : shell séparé auto-détecté sur mobile/tablette, swipe 2 doigts entre pages, queue Forge persistante, notifications PWA
- **Export** : conversations en Markdown / PDF, fiches BAC en PDF, decks Anki en TSV
- **Integration BAC** : scraping ecebac.fr pour calibrer les exos sur les vrais sujets STI2D / NSI / PC / SVT session 2026
- **Recherche globale** : Ctrl/⌘ + K, panneau Settings permanent Ctrl/⌘ + ,

---

Projet privé. Ne pas publier les poids de modèles ni les clés API.
