# Amélioration des modèles & stratégies — tous les modules (hors 3D & bridge)

Date : 2026-07-11. Machine cible : RTX 5070 Ti 16 Go VRAM + 30 Go RAM + 71 Go swap.
Contrainte respectée : **aucune** modification du bridge ni du module 3D (un test
`aurora_3d_pipeline.py` tournait). Le swap (71 Go) permet de charger de gros modèles
mais **très lentement** (<1 tok/s) → on privilégie ce qui tient en VRAM+RAM.

Audit initial : 11 modules notés « distance à la perfection » (0 = parfait, 100 =
cassé). Classement pire→meilleur : Cinéma 64, Chat 62, Code 58, Apprentissage 55,
Voix-TTS 48, Cowork 48, Voix-STT 40, Image 37, Vision 27, Vidéo 27, Cyber 24.

---

## ✅ DÉJÀ APPLIQUÉ (sûr, testé — 4228/4229 tests TS OK, Python compile)

### Chat / Conversation (le plus critique)
- `models.ts` : modèle principal `llama4:scout` (67 Go, **jamais installé**) →
  `qwen3:30b-a3b-instruct-2507-q4_K_M` (installé, Apache-2.0, MoE 3B actifs, rapide).
- **Bug corrigé** : `detectBestMainModel` matchait `qwen3` trop largement et
  choisissait `qwen3-vl:8b` (un modèle **vision**) comme cerveau du chat. Désormais
  il exclut les modèles `-vl`/`-coder`/`-embed` et remet le bon modèle instruct en tête.
- Fallback chat au démarrage : était un **modèle code** (`AUXILIARY_ANALYSIS_MODEL`) →
  nouveau `MAIN_FALLBACK_MODEL` (le modèle instruct) dans `appStore.ts`.
- Sampling de la prose : `temperature 0.2` (sec, répétitif) → preset officiel Qwen3
  `0.7 / top_p 0.8 / top_k 20` (les appels JSON restent en basse température).

### Code
- `models.ts` : modèle code primaire `qwen3-coder-next:q8_0` (~85 Go, absent) /
  `q4_K_M` (51 Go, injouable) → `qwen3-coder:30b` (18 Go, installé, tient en 16 Go).
  Le Next reste réservé au chemin **cloud ≥48 Go**.
- **Bug corrigé** : `qwen3-coder:30b` était marqué « legacy » → il se faisait rediriger
  vers un modèle absent. Retiré du set legacy + alias auto-référent nettoyé.
- Sampling code : `top_p 0.1` (étouffait le MoE) → preset Qwen3-Coder
  `temp 0.3 / top_p 0.8 / top_k 20 / repeat 1.05`. **Ces paramètres étaient en plus
  jamais transmis** par la couche de résilience → corrigé (transmission ajoutée).

### Apprentissage / Académie
- Toutes les évaluations utilisaient `gemma3:12b` (**jamais installé** → l'éval tombait
  en silence sur du « sac de mots »). Remplacé par `LEARNING_EVAL_MODEL` (modèle instruct
  installé) dans : `learningSemanticEval.ts`, `oralModeClassifier.ts`,
  `ParcoursAssistantBubble.tsx`, `ParcoursActiveSession.tsx`.
  *(NB : `threeDMotionIntent.ts` et `ModelView.tsx` utilisent aussi `gemma3:12b` mais
  sont 3D → non touchés, à corriger avec le module 3D plus tard.)*

### Voix — STT
- `models.ts` : pointeur `Voxtral-Small-24B` (fantôme, ~55 Go, appel commenté) →
  `whisper-large-v3-turbo` (ce qui tourne vraiment).
- **Nouveau** : modèle français dédié `bofenghuang/whisper-large-v3-french-distil-dec16`
  (meilleur WER FR, ~2× plus rapide) en **tentative prioritaire avec repli automatique**
  sur large-v3-turbo (aucune régression possible). Activé par défaut, désactivable via
  `AURORA_WHISPER_FR=0`.
- `beam_size 1 → 5` (meilleure précision, coût négligeable).

### Voix — TTS
- `models.ts` : pointeur `fish-speech-1.5` (mort, licence non-commerciale) →
  `Kokoro-82M` (ce qui tourne, Apache-2.0).
- **Fuite corrigée** : le TTS envoyait le texte à **Azure (edge-tts) par défaut**. Rendu
  **local-first** (Piper puis Kokoro) ; edge-tts est maintenant opt-in via
  `AURORA_ALLOW_CLOUD_TTS=1`.
- Retiré l'injection de tags `[excited]`/`[laughter]`/etc. (destinés à Fish-Speech/XTTS)
  qui étaient **lus à voix haute** par Kokoro/Piper.

### Cowork
- Fallback `llama4:scout` codé en dur → `MAIN_FALLBACK_MODEL`.

### Image (FLUX, module standalone)
- Preset `realistic` : `guidance 5.5 → 4.5` (au-delà de ~5 FLUX-dev sur-sature = effet
  « IA »), `steps 45 → 34` (dev converge vers ~30). `technical_render` idem (4.8 / 34).

### Vidéo
- **Bug corrigé** : la stratégie très basse VRAM passait un repo GGUF à `WanPipeline`
  (`family:"wan"`) → crash garanti. Corrigé en `family:"wan_gguf"` (chemin GGUF correct).

### Cyber
- `scrypt` N par défaut `2**15 → 2**17` (minimum OWASP 2025).
- **Nouveau** : refang des IOCs (`hxxp`, `evil[.]tk`, `mail[at]x`) — les rapports de
  menace defangés sont maintenant correctement extraits (+ 4 tests).

### Divers
- Messages Rust (`commands.rs`) qui conseillaient « migrez vers llama4:scout » corrigés.

---

## 🔧 À LANCER APRÈS LE TEST 3D (installs lourds — NE PAS faire pendant le test)

> Raison : ces étapes téléchargent plusieurs Go et/ou installent des paquets. Chatterbox
> et MuseTalk exigent un **venv isolé** (ne JAMAIS installer dans `application/.venv`, ça
> casserait FLUX/le pipeline 3D — cf. ta mémoire).

### 1. Cinéma — restauration (module le plus cassé : lipsync + clonage vocal HS)
Aujourd'hui chaque plan de dialogue dégrade en silence (voix non clonée, pas de lipsync).

- **MuseTalk (lipsync)** — actuellement `musetalk_available()` renvoie toujours faux :
  ```bash
  cd /home/juan/AuroraIA/application/python-services
  python cinema/download_musetalk.py           # télécharge les poids
  git clone https://github.com/TMElyralab/MuseTalk.git MuseTalk   # chemin attendu
  ```
- **Clonage vocal → Chatterbox** (MIT, français, poids ~13 Go déjà dans le cache HF) :
  ```bash
  # venv ISOLÉ existant : ~/.local/share/auroraia/venvs/chatterbox
  ~/.local/share/auroraia/venvs/chatterbox/bin/pip install chatterbox-tts
  ```
  Puis re-câbler `cinema/voice_clone.py` (routing `_get_xtts`/`_get_f5`) vers Chatterbox
  en primaire (XTTS-v2 = licence non-commerciale + non importable ; F5 = CC-BY-NC).
- **Musique → ACE-Step 1.5** (Apache-2.0, <4 Go, meilleur que MusicGen-medium CC-BY-NC) :
  remplacer `facebook/musicgen-medium` dans `cinema/musicgen_render.py`.
  ⚠️ Vérifier les termes de licence ACE-Step avant usage commercial.
- Supprimer la branche morte SadTalker (`talking_head.py`) une fois MuseTalk en place.

### 2. Voix TTS — moteur expressif offline
- Ajouter `_run_tts_chatterbox()` dans `voice_service.py` avant Piper (voix par persona,
  français expressif, offline). Même install que Cinéma ci-dessus.
- Boucler la prosodie : `voiceProsody.ts` calcule des indices pause/énergie qui sont
  ensuite **jetés** — les brancher sur la vitesse Kokoro + silences inter-chunks.

### 3. Apprentissage — RAG local (recherche sémantique)
Le « grounding » est actuellement mot-clé seulement (Wikipedia/DDG), sans embeddings.
  ```bash
  ollama pull bge-m3        # MIT, ~1,2 Go, multilingue FR excellent
  ```
Puis dans `learningResearch.ts` : embed requête+chunks, garder le top-k par cosinus avant
de construire les blocs de sources. (Optionnel : `bge-reranker-v2-m3`.)

### 4. Vidéo — qualité 14B (ta carte peut le faire en GGUF)
- Câbler une stratégie **Wan 2.2 A14B GGUF Q5_K_M** en tête de la branche `<22 Go`
  (gated `quality_mode=='premium'`, repli TI2V-5B). Le loader `wan_gguf` existe déjà.
  Passer `WAN_GGUF_QUANT_DEFAULT` de `Q4_K_M` à `Q5_K_M`.
- Fallback LTX : `Lightricks/LTX-Video` → `Lightricks/LTX-2.3-fp8` (8 steps, 16 Go OK).
  ⚠️ Licence « LTX-2 Community » (pas Apache) — vérifier avant usage commercial.

### 5. Cyber — analyste local opt-in
- Nouveau passage d'analyse IOC/forensics via Ollama (`qwen3:30b-a3b-instruct-2507`) avec
  prompt système strictement **défensif** (résume / mappe MITRE — jamais d'étapes
  offensives). Désactivé par défaut, derrière les garde-fous `_safety`.

---

## ⚠️ DÉCISIONS 3D-PARTAGÉ / LICENCE — TON FEU VERT REQUIS (ne pas auto-appliquer)

- **Modèle vision `qwen3-vl:30b`** (`DEFAULT_VISION_MODEL`) : partagé avec le 3D
  (`character_research.py`, `vlm_judge.py`, `material_vision_pass.py`). C'est le
  meilleur de sa catégorie — **on n'y touche pas**. (Les tiers *live*/*fallback* que j'ai
  passés à 8b n'affectent QUE le TS, pas le 3D.)
- **Licence FLUX.1-dev** (image) : non-commerciale. Le remplacer est souhaitable pour une
  posture EU/permissive, MAIS `flux_reference_synth.py` (feeder 3D) réutilise la même
  stack FLUX. Options si tu veux basculer : (a) `flux1-schnell-fp8` (Apache-2.0, même
  graphe) pour le standalone seul ; (b) Qwen-Image fp8 (Apache-2.0, déjà téléchargé,
  meilleure adhérence au prompt). **Garder le feeder 3D explicitement sur FLUX.**
- **Vision QA cinéma** (`cinema_pipeline.py:61`, `AURORA_VISION_MODEL`) : touche un chemin
  partagé avec le 3D et concurrence Wan/LTX pour la VRAM — à décider ensemble.

---

## Fichiers modifiés (récap)
`src/config/models.ts`, `src/stores/appStore.ts`, `src/hooks/useTauri.ts`,
`src/services/conversationOrchestrator.ts`, `src/services/ollamaResilience.ts`,
`src/services/codeOrchestrator.ts`, `src/services/learningSemanticEval.ts`,
`src/services/oralModeClassifier.ts`, `src/services/coworkExecutor.ts`,
`src/views/learning/ParcoursAssistantBubble.tsx`,
`src/views/learning/ParcoursActiveSession.tsx`, `src/utils/fluxWorkflow.ts`,
`src/__tests__/codeModelSelection.test.ts`, `src/__tests__/iocParser.test.ts`,
`src/services/cyber/iocParser.ts`, `python-services/voice_service.py`,
`python-services/video_generate.py`, `python-services/cyber/password_ops.py`,
`src-tauri/src/commands.rs`.
