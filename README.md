# juan of bike IA — AuroraIA-v2

Copilote IA local · Tauri + React + Python · 100 % offline.

AuroraIA-v2 est un poste de travail IA qui tourne entièrement en local (aucun appel à une API cloud pour l'inférence) : un shell desktop Tauri, une app React, et des modèles Ollama/ComfyUI/HuggingFace pilotés par un bridge Python. Neuf modules couvrent des usages différents mais partagent la même exigence : un résultat livré doit être vérifié (rendu réellement affiché, code réellement exécuté, mesh réellement mesuré), jamais seulement déclaré correct par le pipeline qui l'a produit.

9 modules interactifs :
- **Conversation** · chat Ollama en streaming, pièces jointes texte/image analysées par Qwen3-VL, narration vocale — le pipeline enchaîne analyse → plan → brouillon → vérification → raffinement → livraison plutôt qu'une réponse en un seul passage.
- **Academy** · cours, fiches BAC, exercices et quiz générés par IA calibrés sur les vrais sujets STI2D/NSI/PC/SVT, examen blanc avec correction, indices progressifs, révision espacée (Leitner), export PDF/Anki.
- **Image** · atelier de génération FLUX avec une roue de 15 styles, recherche de références visuelles, et un forge de personnages en plusieurs étapes.
- **Vidéo** · Wan2.2 texte-vers-vidéo et image-vers-vidéo, cohérence d'un plan à l'autre par keyframe d'action, doublage/lipsync, montage automatique jusqu'à un film livré.
- **Code** · génération multi-langages (22 langages en sandbox) avec classification d'intention, plan d'architecture, exécution isolée (conteneur Podman), auto-correction multi-passes, et une porte de qualité visuelle qui rejette un rendu réellement cassé plutôt que de se fier au score déclaré par le modèle.
- **Dessin** · sketch sur canvas interprété par vision (Qwen3-VL) puis rendu par FLUX à fort denoise, du croquis au dessin fini.
- **3D** · génération de mesh (Hunyuan3D, DreamGaussian, Blender procédural, photogrammétrie Meshroom), post-traitement (nettoyage, matériaux PBR), rig automatique et bibliothèque de mouvements (33 presets) avec un moteur cinématique dédié.
- **Voice** · copilote vocal continu (Voxtral STT, Kokoro TTS, lipsync Rhubarb) avec caméra, vision et intégration au Character Forge.
- **Cyber** · labs de sécurité pratiques (CTF, crypto, forensics, hash, réseau, mots de passe, stéganographie, threat intel, websec) en environnement Python sandboxé, avec correction et validation de flag automatiques.

## Stack

- **Frontend** : Tauri v2 + React 19 + TypeScript + Vite + Tailwind v4
- **Backend local** : Ollama (LLMs), ComfyUI (pipelines image/3D), bridge Python Flask (port 3001, expose les capacités Python au frontend et au tunnel Cloudflare)
- **Modèles** : qwen3-vl, SAM2, GroundingDINO, BiRefNet, LaMa, FLUX, Wan2.2, Hunyuan3D, TRELLIS.2, Voxtral, Kokoro

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
