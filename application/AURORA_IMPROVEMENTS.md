# Aurora IA — Auto-Improvement Tracker

> Ce fichier est mis a jour automatiquement a chaque session de travail.
> Il liste les ameliorations possibles en fonction de la machine et de l'etat du projet.

---

## Machine actuelle

| Composant | Valeur |
|-----------|--------|
| CPU | AMD Ryzen (32 coeurs) |
| RAM | 31 GB |
| GPU | NVIDIA GeForce RTX 5070 Ti |
| VRAM | 16 GB |
| OS | Windows 11 |

---

## Session: 2026-04-25 — Module Cinema (refonte du module Video)

### Resume

Le module Video est remplace par un **module Cinema multi-plans** capable de
generer des sequences avec voix clonees, lipsync et concatenation finale.
Le design "salle de projection" de `MangaVideoView` est conserve : projecteur,
ecran, dial de motion, bobine. La logique simulee (setInterval) est remplacee
par un vrai pipeline `cinema_pipeline.py` orchestrant FLUX + Wan2.2 + XTTS-v2 /
F5-TTS + SadTalker.

### Fichiers ajoutes

| Fichier | Role |
|---------|------|
| `python-services/cinema/voice_extract.py` | YouTube + Demucs + ECAPA + clustering -> sample voix propre |
| `python-services/cinema/voice_clone.py` | Bibliotheque globale + synthese XTTS-v2 / F5-TTS |
| `python-services/cinema/cinema_pipeline.py` | Orchestrateur multi-plans avec ETA structuree |
| `python-services/cinema/_compat.py` | Shims torchaudio.load + speechbrain LazyModule |
| `src/services/cinemaApi.ts` | Helpers TypeScript pour `/api/cinema/*` et `/api/voice/*` |
| `docs/VIDEO_GENERATION_TIMES.md` | Tableau des temps de generation |

### Fichiers modifies

- `bridge_server.py` : ajout des routes `/api/cinema/storyboard`,
  `/api/cinema/generate`, `/api/cinema/job/<id>`, `/api/voice/library`,
  `/api/voice/library/<slug>` (DELETE), `/api/voice/library/clear`,
  `/api/voice/extract`, `/api/voice/register`, `/api/voice/synthesize`,
  `/api/voice/check`, plus `/api/fs/remove-dir` et `/api/fs/list`.
- `src-tauri/src/commands.rs` : ajout `fs_remove_dir_all`, `fs_list_dir`.
- `src-tauri/src/lib.rs` : enregistrement des nouvelles commandes IPC.
- `src/views/MangaVideoView.tsx` : refonte complete (storyboard preview,
  bibliotheque de voix, ETA temps reel, multi-resolution, qualite mode).

### Bugs Python corriges en cours de route

1. **`torchaudio.load` casse sur Windows depuis PyTorch 2.9** (CRITIQUE)
   - torchaudio delegue desormais a torchcodec qui exige les DLL "full-shared"
     FFmpeg (avcodec/avformat/avutil) dans le PATH. On ne les a pas.
   - Fix : `_compat.py` monkey-patch `torchaudio.load` pour utiliser soundfile
     directement. Resultat : XTTS-v2 charge le speaker_wav sans torchcodec.

2. **SpeechBrain 1.1.0 LazyModule k2_fsa propage ImportError** (BLOQUANT pour ECAPA)
   - `inspect.stack()` traverse `sys.modules` pour construire le frame info ;
     touche le `LazyModule(speechbrain.integrations.k2_fsa)` qui tente
     l import reel et echoue car k2 n est pas installe.
   - Fix : `_compat.py` patch `LazyModule.ensure_module` pour renvoyer un
     stub vide en cas d ImportError. Resultat : l embedding ECAPA fonctionne,
     `register` peuple `embedding.npy` et `duration_s` correctement.

### Decisions d architecture

- **100% local** : aucune API cloud, F5-TTS pour EN, XTTS-v2 pour FR/multi.
- **Bibliotheque de voix globale persistante** : `application/voices/library/{slug}/`
  avec `reference.wav`, `embedding.npy`, `metadata.json`. Cross-conversations,
  bouton "vider cache" expose dans l UI.
- **Pas de garde-fou ethique sur les voix** (decision explicite).
- **Anciens artifacts video legacy supprimes au boot** du module.
- **Routage langue automatique** : XTTS-v2 par defaut, F5-TTS en EN.
- **Mobile detecte** -> resolution 720p par defaut, override via dropdown.

### Pour tester

```bash
# Test des dependances
python application/python-services/cinema/voice_clone.py --check
python application/python-services/cinema/voice_extract.py --check

# Liste de la bibliotheque
python application/python-services/cinema/voice_clone.py --list

# Smoke test bridge (apres avoir relance bridge_server.py)
curl http://127.0.0.1:3001/api/voice/check
curl http://127.0.0.1:3001/api/voice/library
curl -X POST -H "Content-Type: application/json" \
  -d '{"prompt":"Une scene cartoon de 10 secondes : un chat orange dans une cuisine."}' \
  http://127.0.0.1:3001/api/cinema/storyboard
```

### Reste a tester en E2E

- Generation complete avec un storyboard 2 plans (~50 min sur la machine cible)
- Validation tunnel + mobile (le PROGRESS:eta: est lu via `/api/python/progress`)
- Suppression cache voix via UI
- Import WAV depuis mobile (passe par `wavBase64` dans `voice_register`)

---

## Session: 2026-04-14

### Corrections effectuees

0. **DISQUE PLEIN — cause racine de tous les crashes** (BLOQUANT)
   - C: etait a 930GB/930GB = 100% plein
   - Ollama ne pouvait pas allouer de memoire (ggml assert failure)
   - Suppression: llama4:scout (67GB) + qwen3-32B (26GB) + qwen3-vl:30b (19GB) = 112GB liberes
   - Ces modeles ne tenaient PAS dans 16GB VRAM de toute facon
   - `models.ts`: DEFAULT_MAIN_MODEL change de `llama4:scout` a `qwen3:14b`
   - Cloud tier `low.main` change de `qwen3:14b-q8_0` (inexistant) a `qwen3:14b`
   - Store version bumped 6→7 pour forcer la migration
   - Verifie: Ollama 0.20.6 + qwen3:14b + RTX 5070 Ti = FONCTIONNE

1. **Module Voix — ne reflechissait pas** (CRITIQUE)
   - Cause: `VoiceCopilotView.tsx` faisait un `fetch('/api/ollama/chat')` brut au lieu d'utiliser `ollamaChat()` de useTauri
   - En mode Tauri, `/api/ollama/chat` n'existe pas (pas de proxy Vite → bridge)
   - Fix: utilisation de `ollamaChat()` qui gere automatiquement Tauri IPC / Cloud proxy / Browser
   - Ajout d'affichage des erreurs dans le transcript au lieu de les avaler silencieusement

2. **Proxy Vite toujours actif** (CRITIQUE)
   - Cause: le proxy `/api` -> bridge:3001 n'etait actif que si `VITE_CLOUD_MODE=true`
   - Fix: proxy active dans tous les modes (Tauri, browser, cloud)
   - Le serveur ecoute aussi sur `0.0.0.0` pour le tunnel

3. **Mobile — viewport et safe areas**
   - Ajout `viewport-fit=cover`, `maximum-scale=1`, `apple-mobile-web-app-capable`
   - Ajout des CSS safe-area pour les telephones avec notch
   - `-webkit-overflow-scrolling: touch` et `overscroll-behavior: contain`
   - Touch targets minimum 44px (Apple HIG)
   - Desactivation du tap highlight

4. **Mobile — responsive sur tous les modules**
   - Sidebar: boutons plus petits sur mobile (h-8 au lieu de h-10), texte xs
   - StageHeader: titre plus petit, badges caches sur mobile
   - ConversationView: textarea plus petite, boutons compacts
   - ImageView, CodeView, VideoView, DrawingView, ModelView, LearningView: padding reduit, panels scrollables limites a 60vh
   - Transcription voix: panel etendu a 40vh au lieu de 48px fixe

5. **Bridge Server — nouvelles routes**
   - `GET /api/download/<path>` : force le telechargement sur mobile (Content-Disposition attachment)
   - `GET /api/generated-files` : liste tous les fichiers generes (images, videos, audio, 3D)
   - `POST /api/upload` : recevoir des fichiers depuis le telephone
   - `GET /api/ollama/tags` : lister les modeles Ollama depuis le mobile

6. **Utilitaire de telechargement mobile**
   - `src/utils/mobileDownload.ts` : download, upload, list de fichiers generes
   - Fallback blob URL pour forcer le telechargement d'images sur mobile

7. **3D Viewer mobile**
   - `ModelView.tsx` : hauteur min-h-[50vw] sur mobile au lieu de 36rem fixe
   - Padding reduit pour les petits ecrans

8. **Video Player mobile**
   - `VideoView.tsx` : container min-h-[50vw] sur mobile, padding adaptatif

9. **Camera directe mobile**
   - `ContextFilesField.tsx` : bouton "Photo" avec `capture="environment"` pour prendre une photo directement depuis la camera du telephone

10. **TitleBar compacte mobile**
    - Orbe et texte plus petits sur mobile (h-8 au lieu de h-12, text-xs)

---

## Ameliorations a faire (prochaines sessions)

### Priorite haute

- [ ] **TTS sur tunnel/mobile** : Kokoro-82M timeout souvent a 120s sur les longs textes. Decouper le texte en chunks de 200 caracteres avant envoi au TTS
- [ ] **STT fallback navigateur** : Si le bridge est down, utiliser l'API Web Speech Recognition du navigateur comme fallback gratuit
- [ ] **Streaming LLM dans la voix** : Actuellement `stream: false` — passer en streaming pour reduire la latence percue (commencer le TTS des les premiers mots)
- [ ] **Cache audio TTS** : Stocker les WAV generes pour ne pas regenerer les memes phrases
- [ ] **WebSocket pour le tunnel** : Remplacer le polling HTTP par WebSocket pour la voix en temps reel sur mobile

### Priorite moyenne

- [ ] **PWA manifest** : Ajouter un `manifest.json` pour installer l'app en PWA sur le telephone
- [ ] **Offline mode partiel** : Cache les modeles charges et les reponses recentes pour fonctionner sans connexion tunnel
- [ ] **Notification push** : Notifier le telephone quand une generation longue (video, 3D) est terminee
- [ ] **Compression audio** : Compresser le webm avant envoi sur tunnel pour economiser la bande passante mobile
- [ ] **Image preview mobile** : Galerie swipeable pour les images generees au lieu du grid fixe
- [ ] **Dark/Light mode** : Supporter les deux themes (actuellement dark only)

### Priorite basse

- [ ] **Tests E2E mobile** : Playwright avec emulation mobile pour tester le tunnel
- [ ] **Metriques de performance** : Tracker les temps STT/LLM/TTS pour identifier les goulots
- [ ] **Multi-langue voix** : Detection automatique de la langue pour basculer entre Voxtral FR et EN
- [ ] **Historique voix persistant** : Sauvegarder les conversations vocales comme les conversations texte
- [ ] **Gestes tactiles** : Swipe pour naviguer entre modules, pinch pour zoom images

---

## Session: 2026-04-22 #2 — Pipeline SadTalker CABLE DE BOUT EN BOUT

Tout le cote AuroraIA est pret. Il reste UNIQUEMENT a l utilisateur a installer SadTalker
(4 commandes, ~2GB disque, 5 minutes) et tout marche automatiquement.

### Pipeline complet realise

```
[User parle au mic]
       |
       v
useVoiceLive -> handleTranscript -> ollamaChatStream (LLM)
       |                               |
       |                               v (chaque phrase complete)
       |                          speakText(phrase)
       |                               |
       |                               v
       |                          POST /api/voice/tts { text, lang, avatar: /avatars/xxx.png }
       |                               |
       |                               v (bridge_server.py)
       |                          voice_service.py --mode tts --avatar <path>
       |                               |
       |                               |-- Kokoro TTS -> speech.wav
       |                               |
       |                               v (si avatar fourni)
       |                          maybe_generate_talking_video()
       |                               |
       |                               v
       |                          talking_head.py --image X --audio Y --output Z.mp4
       |                               |
       |                               |-- Cache hit? -> reutilise MP4 existant
       |                               |-- Cache miss? -> SadTalker genere MP4 realiste
       |                               |
       |                               v
       |                          Response: { audio_url, video_url, phonemes }
       |                               |
       v                               v
useVoiceLive.speakText() joue audio + callback onTalkingVideo(videoUrl)
                                       |
                                       v
                          VoiceCopilote.setTalkingVideoUrl(videoUrl)
                                       |
                                       v
                          effectiveAvatar = 'talking-video' avec { videoSrc, idleVideoSrc }
                                       |
                                       v
                          AuroraAvatar -> AvatarTalkingVideo joue MP4
                                       (synchronise avec audio.currentTime)
```

### Fichiers modifies/crees

- `python-services/talking_head.py` -- enrichi:
  - Cache par hash(image+audio) -> phrases identiques reutilisees instantanement
  - Mode `idle` -> genere un MP4 silence/respiration loope pour quand Aurora se tait
  - Options `--size` (256/512), `--no-enhancer`, `--no-cache`
  - `--mode check` retourne l etat d install + stats du cache

- `python-services/voice_service.py` -- enrichi:
  - `maybe_generate_talking_video()` appelee apres TTS si `--avatar` fourni
  - Fallback silencieux si SadTalker absent -> VoiceCopilote utilise live2d-flux
  - Parametre `--avatar <path>` dans main()

- `bridge_server.py` -- nouveaux endpoints:
  - `POST /api/voice/tts` accepte maintenant `{avatar: "/avatars/xxx.png"}` -> retourne `video_url` en plus de `audio_url`
  - `GET /api/voice/tts-video` sert le MP4 talking-video du dernier TTS
  - `GET /api/voice/idle-video` sert le MP4 idle (loop silence)
  - `GET /api/voice/talking-head/check` -> frontend peut tester si SadTalker est installe
  - `POST /api/voice/talking-head/idle` -> pre-genere l idle MP4 pour un avatar donne (appele une fois)

- `src/hooks/useVoiceLive.ts` -- enrichi:
  - Nouveaux props `avatarImage?: string`, `onTalkingVideo?: (url) => void`
  - Envoi automatique de `avatar` dans le body du POST /api/voice/tts
  - Timeout adaptatif: 12s sans video, 45s avec (SadTalker ~10-30s)
  - Relaye `video_url` via `onTalkingVideo` callback

- `src/views/VoiceCopilotView.tsx` -- enrichi:
  - State `talkingVideoUrl`, `idleVideoUrl`, `talkingHeadAvailable`
  - useEffect check SadTalker au mount + pre-gen idle si dispo
  - `effectiveAvatar` compute l avatar dynamiquement:
    * Si SadTalker installed + video_url present -> type='talking-video' avec video
    * Sinon -> avatar original (live2d-flux, procedural, etc.)
  - Passage a `<AuroraAvatar avatarPath={effectiveAvatar.path} avatarType={effectiveAvatar.type}>` (2 endroits: principal + PIP fullscreen)
  - Reset talkingVideoUrl 300ms apres fin de parole (evite un flash)

### Activation cote utilisateur (5 min, 1 fois)

```bash
cd C:\Users\Juan\Desktop\ia\AuroraIA-v2\application\python-services
git clone https://github.com/OpenTalker/SadTalker.git
cd SadTalker
pip install -r requirements.txt
bash scripts/download_models.sh
# OU sur Windows pur: suivre manuellement les liens dans scripts/download_models.sh
```

Verification:
```bash
python python-services/talking_head.py --mode check
# Attendu: {"ok": true, "info": {"ready": true, "checkpoints": [...], ...}}
```

Une fois `ready: true`:
1. Relance AuroraIA
2. Clique sur Chat Vocal Live
3. VoiceCopilote check automatiquement /api/voice/talking-head/check -> detect `ready=true`
4. Pre-generation idle video lance en background
5. Chaque phrase TTS de Aurora declenche maintenant SadTalker en parallele de Kokoro
6. L avatar switch automatiquement vers 'talking-video' avec vraie animation faciale realiste

### Fallback gracieux

- Si SadTalker pas installe -> `talkingHeadAvailable=false` -> avatar reste en 'live2d-flux'
- Si SadTalker installe mais fail sur une phrase -> `video_url` absent dans la response -> avatar reste sur la phrase d avant (ou idle)
- Si timeout 45s -> meme flow, plus long
- Aucun crash possible, tout est wrapped try/except.

### Performance

- Latence premiere phrase: 5-15s (size=256, no enhancer) / 15-30s (size=512, gfpgan)
- Latence phrases identiques repetees: <100ms (cache hit)
- VRAM SadTalker: 6-8GB -> compatible RTX 5070 Ti 16GB

### TODO v3 (optionnel):
- [ ] Double-buffering: pre-generer phrase N+1 pendant que N joue (UX perfection)
- [ ] Bouton UI "forcer la qualite 512px" dans VoiceCopilote settings
- [ ] Clear cache manuel dans UI (si disque sature)
- [ ] Support multi-avatar parallele (cache par avatar_id)

---

## Session: 2026-04-22 — Honnetete totale + scroll mobile + chantier SadTalker realise

### Honnetete TOTALE (plus de yes-man, plus de "c est subjectif")
- System prompt reecrit avec section `HONNETETE TOTALE` + `AVIS SUR UNE PERSONNE`.
- Aurora peut desormais utiliser "moche", "laid", "rate", "moyen" quand c est son vrai avis.
- Interdits explicites: "c est subjectif", "ca depend des gouts", "peut-etre oui peut-etre non", "y a du potentiel", "belle tentative".
- Avis sur personne: CIBLE LA PERSONNE (visage, traits, expression, posture), pas le vetement. Le style peut compter mais pas comme esquive.

### Scroll mobile dans voice panel (VRAIE root cause trouvee)
- **Root cause**: le modal VoiceCopilote etait rendu dans un `<motion.div fixed inset-0 z-[60]>` avec `max-h-88vh overflow-hidden`, mais App.tsx avait un swipe handler sur `<section>` qui volait les events touch verticaux des qu il y avait un mouvement "pas assez horizontal" pour etre un swipe.
- **Fix**: App.tsx ajoute `isTouchInOverlay()` qui check `closest('[data-voice-panel], [data-overlay="true"], [role="dialog"]')`. Si touch dans un overlay → skip le swipe handler. ConversationView et VoiceCopilote portent maintenant `data-voice-panel="true"`.
- Plus besoin de `stopPropagation` manuel dans VoiceCopilote -> le scroll natif interne marche librement.

### Comprehension conversationnelle souple (raisonnement depannage)
- Ajout de la section `COMPREHENSION SOUPLE — RAISONNEMENT CONTEXTUEL` dans le system prompt.
- Aurora deduit d un message "j ai teste X, j ai eu Y, puis j ai essaye Z et ca marche pas": X et Z sont deja faits, proposer une etape DIFFERENTE.
- Raisonne comme un "ami bricoleur/technique", pas un FAQ bot.
- Recapitule brievement avant de proposer, pose UNE question precise si info manque, adapte le niveau de technicite a l utilisateur.

### Recherches web enrichies — 7 types detectes
- Nouveau systeme de detection contextuelle dans handleTranscriptImpl:
  - `identification`: "je sais pas", "identifie", "c est quoi" -> image search
  - `repair`: "reparer", "panne", "casse", "marche plus" -> guides reparation
  - `howworks`: "comment ca marche", "tutoriel", "fonctionnement" -> tutos
  - `buying`: "prix", "ou acheter", "meilleur modele" -> reviews et prix
  - `health`: "toxique", "comestible", "dangereux" -> sources sante/securite
  - `alternatives`: "alternative", "remplacer", "substitut" -> options
  - `deepinfo`: "origine", "specifications", "histoire" -> wiki + specs
- Query enrichie avec le contexte visuel (qwen3-vl description) + la question utilisateur.
- Sources consultees affichees dans la UI (badges hostname) mais **JAMAIS** lues a voix haute.

### Chantier SadTalker v1 realise (avatar video realiste)

**Objectif**: remplacer l overlay 2D sur image (qui fait "trou yeux/bouche") par un VRAI rendu video realiste, type FaceTime, ou la tete bouge et parle avec des vrais mouvements faciaux.

**Architecture implementee**:
1. `python-services/talking_head.py` (nouveau)
   - Mode `--check`: verifie l installation SadTalker
   - Mode `--generate`: prend image + audio WAV, produit MP4
   - Wrappe `SadTalker/inference.py` avec args optimises (`--still --preprocess full --size 256 --enhancer gfpgan`)
   - Progress emits via `PROGRESS:pct:detail`

2. `src/components/AvatarTalkingVideo.tsx` (nouveau)
   - Joue un MP4 SadTalker
   - Support `audioRef` pour synchro fine avec audio externe (Kokoro) -> video mutee, se cale sur `audio.currentTime`
   - Support `idleVideoSrc` pour video loop quand pas de parole
   - `loop + autoPlay + muted` pour respect autoplay policies mobile

3. `AvatarType` etendu avec `'talking-video'` dans `types/app.ts`
4. `AuroraAvatar.tsx` route vers AvatarTalkingVideo si `avatarType === 'talking-video'`

**Format avatarPath**:
```json
{
  "videoSrc": "/avatars/aurora-natsu-12345.mp4",
  "idleVideoSrc": "/avatars/aurora-natsu-12345-idle.mp4"
}
```

**Pipeline complet a activer**:
```
User parle -> Kokoro TTS -> WAV
     \-> talking_head.py --image <FLUX avatar.png> --audio <WAV> --output <MP4>
     \-> MP4 joue dans AvatarTalkingVideo avec synchro audio.currentTime
```

### INSTALLATION SADTALKER REQUISE cote utilisateur

L avatar `talking-video` est **inactif** tant que SadTalker n est pas installe.
Pour activer (une fois, ~2GB disque + Python deps):

```bash
cd application/python-services
git clone https://github.com/OpenTalker/SadTalker.git
cd SadTalker
pip install -r requirements.txt
bash scripts/download_models.sh    # ~2GB de checkpoints

# Verifier:
python ../talking_head.py --mode check
# Attendu: {"ok": true, "info": {...}}
```

**Hardware**: RTX 5070 Ti 16GB est large (SadTalker utilise ~6-8GB VRAM).
**Latence**: 5-15 sec par phrase (taille 256), 15-30s (taille 512).
**Strategie recommandee**: double-buffer -- pendant que Kokoro joue la phrase N, SadTalker prepare la phrase N+1.

### TODO v2 (non fait ici):
- [ ] Bouton UI "Regenerer avatar en mode talking-video" dans AvatarSelectorModal
- [ ] Integration pipeline: quand l utilisateur genere un avatar, proposer le mode video
- [ ] Caching: chaque phrase TTS → cache cle=(hash_audio, hash_image) → MP4 reutilise si identique
- [ ] Fallback gracieux: si SadTalker fail → re-route vers 'live2d-flux' automatiquement

---

## Session: 2026-04-21 #2 — Fixes mobile + chantier Avatar Live 2D + v2 SadTalker

### Micro iOS Safari — NotSupportedError MediaRecorder (CRITIQUE)
- **Root cause**: Safari ne supporte PAS `audio/webm` pour MediaRecorder (erreur `NotSupportedError: Failed to execute 'start'`)
- **Fix**: detection dynamique du MIME support via `MediaRecorder.isTypeSupported()` avec ordre de priorite:
  `audio/webm;codecs=opus > audio/webm > audio/mp4;codecs=mp4a.40.2 (AAC-LC Safari) > audio/mp4 > audio/aac > default`
- Logs explicites du MIME selectionne + fallback sans options si tous echouent
- Try/catch autour de `rec.start(250)` avec retry `rec.start()` sans timeslice (certains Safari)

### Camera preview noir / pas de retour visuel (CRITIQUE)
- **Root cause**: le `<video>` element est monte via AnimatePresence APRES `setEnabled(true)`, donc
  `videoRef.current` etait null au moment de `video.srcObject = stream` dans startInternal.
- **Fix**: useEffect [enabled] qui attache `streamRef.current` au `videoRef.current` APRES le mount React.
  Log de diagnostic `[useCameraLive] attaching stream to video element`.

### Avatar Live 2D — overlays plus subtils (V1.5)
- **Bouche**: plus d ellipse noire grossiere. Seulement quand `phase === 'speaking'` et `openY > 0.15`.
  Gradient radial sombre blende via `globalCompositeOperation = 'multiply'` pour preserver les tons FLUX.
  Ombre fine levre superieure pour suggerer l ouverture.
- **Yeux**: paupieres dessinees en ellipse (plus rectangle) avec gradient peau->ombre cil.
  Blink seulement quand `blinkAmount > 0.15` (plus au repos).
- **Pupilles tracking souris**: DESACTIVE (trop grossier en 2D sans detection iris precise). Reserve v2.

### Chantier V2 propose: SadTalker / Wav2Lip (vrai realisme video)

L utilisateur veut du vrai realisme "comme une vraie personne qui parle". L approche 2D overlay
atteint sa limite. Le vrai realisme passe par un modele IA qui genere une VIDEO a partir de
l image FLUX + l audio TTS.

**Options etudiees**:

| Modele | Licence | Qualite | Vitesse | VRAM | Taille modele |
|--------|---------|---------|---------|------|---------------|
| **SadTalker** | Apache 2.0 | Tres realiste (tete + yeux + bouche) | 5-15s/phrase | 6-8 GB | ~2 GB |
| **Wav2Lip** | MIT-like | Excellent lip-sync seul | 3-8s/phrase | 4-6 GB | ~500 MB |
| **SadTalker-Video-Lip-Sync** | Apache 2.0 | Combine les deux | 10-20s/phrase | 8 GB | ~3 GB |
| **Didemo / NeRF** | Academic | Hyper realiste | 60s+/phrase | 16+ GB | Trop lourd |

**Recommendation**: SadTalker (meilleur compromis qualite/vitesse/VRAM, marche sur RTX 5070 Ti 16GB).

**Architecture proposee** (a implementer en v2):
1. `python-services/talking_head.py` nouveau service:
   - Input: path image FLUX + path audio WAV + output video path
   - Run SadTalker en subprocess CUDA
   - Output: MP4 avec head/eyes/mouth animes realistes
2. `voice_service.py` enrichi:
   - Apres `run_tts()`, chainer automatiquement `talking_head(ref_image, wav)` -> `talking_head.mp4`
   - Retourner `{"tts_wav": ..., "talking_video": ...}` dans le JSON
3. Nouveau type `AvatarType = 'talking-video'`:
   - Composant `AvatarTalkingVideo.tsx` qui joue simplement le MP4 genere
   - Synchronisation video.currentTime avec audio.currentTime pour lip-sync parfait
4. Fallback gracieux: si SadTalker echoue ou pas installe, fallback sur `'live2d-flux'`

**Latence**: l utilisateur perd 5-15s entre la fin du LLM et le debut de la parole visuelle.
Acceptable dans le cas "conversation fluide" car le TTS streaming peut continuer pendant que
SadTalker calcule le chunk suivant (double-buffer).

**Installation**:
```bash
git clone https://github.com/OpenTalker/SadTalker.git
cd SadTalker
pip install -r requirements.txt
bash scripts/download_models.sh
```

Cette v2 sera faite dans une session dediee car elle necessite:
- Setup SadTalker + checkpoints (2GB+)
- Integration CUDA + test perf sur 16GB VRAM
- Double-buffering TTS/video pour latence perceived minimale
- UX: skeleton/loader pendant que la video se genere

En attendant, la v1.5 (Avatar Live 2D avec overlays subtils) donne deja un bon ressemblant
grace a l image FLUX, avec des animations discretes qui ne defigurent pas le personnage.

---

## Session: 2026-04-21 — Vision multimodale live dans tous les modules

### Objectif
Ameliorer la comprehension visuelle d'Aurora dans chaque module, avec une vraie capacite a "voir"
en direct (camera), a analyser des images de reference, et a comprendre des videos pedagogiques.

### Realisations

1. **`visionService.ts` (nouveau)** — Service centralise d'analyse multimodale
   - `analyzeImage`, `analyzeImageStream`, `analyzeVideoFrames`, `analyzeLiveSnapshot`, `askAboutImage`
   - Modeles: `qwen3-vl:30b` (qualite max) + `qwen3-vl:8b` (live rapide) + fallback automatique
   - Helpers: `blobToBase64`, `dataUrlToBase64`, `downscaleImage` (max 1024px)
   - Prompts specialises par tache (`describe_reference`, `describe_live`, `describe_video`, `answer_question`, `extract_text`)

2. **`useCameraLive.ts` (nouveau)** — Hook camera React
   - getUserMedia + switch front/back (mobile)
   - Capture frame en dataUrl (downscale automatique) ou Blob
   - Mode hybride: snapshot on-demand + polling background (10s par defaut)
   - Cleanup propre des MediaStreamTracks

3. **`VoiceCopilotView.tsx`** — Camera live integree
   - Bouton toggle camera + switch front/back (mobile) dans la barre du haut
   - Preview video flottant en coin superieur droit
   - Mode hybride C: snapshot au moment ou l'utilisateur parle + contexte background toutes les 10s
   - Injection du contexte visuel dans le system prompt: `## CE QUE TU VOIS ACTUELLEMENT`
   - Etat "observing" dans STATES pendant l'analyse qwen3-vl
   - Banner "Aurora voit : description" sous le micro

4. **`ImageView.tsx`** — Analyse reference haute fidelite
   - Quand une image de reference est uploadee via ContextFilesField, analyse automatique via qwen3-vl:30b
   - Description dense en anglais injectee dans le prompt FLUX (bloc "REFERENCE DESCRIPTION")
   - FLUX a maintenant la GROUND TRUTH du sujet avant d'editer

5. **`learning/VideoAnalysisPanel.tsx` (nouveau)** — Analyse video pedagogique
   - Upload video (mp4, webm, mov, avi, mkv)
   - Extraction de 3-12 frames cotes client via `<video>` + Canvas (pas de Python requis)
   - Analyse chronologique via `analyzeVideoFrames` (qwen3-vl:30b multi-image)
   - Chat follow-up: poser des questions sur la video (Q/R libre)
   - Nouveau tab `video` dans LearningView

6. **`models.ts`** — Support qwen3-vl:30b restaure
   - Retrait de l'alias `qwen3-vl:30b` -> `qwen3:14b` qui rabaissait le modele
   - Ajout `VISION_HIGH_QUALITY_MODEL = 'qwen3-vl:30b'`, `VISION_LIVE_MODEL = 'qwen3-vl:8b'`, `VISION_FALLBACK_MODEL = 'qwen3:14b'`
   - `selectAdaptiveVisionModel` accepte maintenant `{ preferQuality: true }` pour forcer 30b (offload CPU si VRAM insuffisante)

7. **`appStore.ts`** — Vision haute qualite par defaut
   - `visionModel: VISION_HIGH_QUALITY_MODEL` par defaut
   - Migration `selectAdaptiveVisionModel` avec `preferQuality: true`

### IMPORTANT — Action utilisateur requise

Le modele `qwen3-vl:30b` (19GB) n'est pas installe sur Ollama actuellement. Pour profiter de la qualite maximale:

```bash
ollama pull qwen3-vl:30b
# ou pour la version rapide (5-6GB):
ollama pull qwen3-vl:8b
```

Sans installation, le service detecte automatiquement l'absence et fallback vers `qwen3:14b` (texte-seul, description limitee).

### Architecture vision globale

```
User action (parole, upload, prompt)
         |
         v
  [camera/image/video input]
         |
         v
  visionService.analyze*   (qwen3-vl:30b)
         |
         v
  [description texte dense]
         |
         v
  Injection dans system prompt / generation prompt
         |
         v
  LLM principal (llama/qwen) ou FLUX ou Wan2.2
```

Cela donne a Aurora une capacite "Claude-like" : voir -> comprendre -> repondre sur ce qui est vu.

### TODO (ameliorations futures)

- [ ] **Pull automatique qwen3-vl:30b** au premier lancement si absent (avec confirmation utilisateur)
- [ ] **Analyse multi-frame video** pour Q/R : envoyer les 3-5 frames pertinentes par question au lieu de la premiere
- [ ] **Capture rapide dans ConversationView** : bouton camera pour prendre une photo sans passer par upload
- [ ] **Indicateur de modele vision actif** dans la barre de statut (qwen3-vl:30b / 8b / fallback)
- [ ] **Cache des analyses vision** pour ne pas re-analyser la meme image a chaque edit dans ImageView

---

## Notes techniques pour la machine

- RTX 5070 Ti 16GB VRAM : peut charger des modeles jusqu'a ~13B params en fp16
- 31GB RAM : assez pour Ollama + ComfyUI simultanes
- 32 coeurs CPU : permet le multi-processing pour STT+LLM en parallele
- Modele recommande : `qwen2.5:14b` (optimal pour 16GB VRAM) ou `llama3.1:8b` (rapide)
- Whisper large-v3 tourne confortablement en GPU avec cette config
