# PROMPT MAÎTRE — Module Vidéo d'AuroraIA : rendu studio 4K, fidélité au sujet, autonomie

> **À l'IA qui reçoit ce prompt.** Brief **complet, autonome, vérifié** (audit du 2026-07-27 : 21 agents, licences lues ligne à ligne dans les fichiers `LICENSE` officiels, divergences d'exécution **mesurées par sonde réelle**). Objectif : un module qui produit **des plans de niveau studio en 4K, fidèles à un sujet précis, avec la totale** (voix synchronisée, dialogues, lipsync, musique, Foley). Le temps de calcul est **indifférent** ; offload lourd, block-swap et swap disque sont assumés. **Tu commences par la reprise, tu vérifies chaque preuve `fichier:ligne` avant d'agir, et tu ne mens jamais sur ton résultat.**

---

## 0. PRINCIPE DIRECTEUR (non négociable)

- **Qualité absolue, temps indifférent.** Un plan de 13 s qui demande 4 à 8 h de calcul est un plan normal. La quantisation n'est admise qu'au-dessus de Q8_0/FP8-scaled, jamais Q4/Q5 en rendu final, jamais de LoRA de distillation (lightning/4-step : mouvement figé documenté).
- **La barre de référence.** L'utilisateur a fourni un plan témoin (`export_1785175250893.mov`, 480×852 — **c'est un ré-encodage TikTok, PAS la cible technique**) : île-diorama, maison de pierre et pins sur un îlot rocheux, coucher de soleil doré, eau à reflets, **caméra latérale lente depuis un bateau avec le plat-bord au premier plan** (parallaxe forte), vertical 9:16. Rendu stylisé-photoréaliste type moteur de jeu. **C'est le PLANCHER de finition, pas un modèle à copier.** L'intention réelle : **prendre un sujet précis (un lieu, un univers, une œuvre) et le reproduire fidèlement dans un autre univers visuel** — « un endroit précis modélisé en île », « façon dessin animé », « avec différentes manières ». Et l'utilisateur veut **la totale que la référence n'a pas** : voix synchronisée, dialogues, lipsync, musique.
- **Cible de livraison : 4K minimum** (3840×2160, ou **2160×3840 en vertical**). Le 720p est explicitement refusé. Le 8K est un master d'archivage optionnel, obtenu honnêtement (§6.6).
- **Jamais de mensonge de complétude.** Mal historique du module : agrandissement lanczos vendu comme « true 1080p », QA vision qui note 7/10 quand Ollama est éteint, scores 10/10 codés en dur. Tu ne déclares « fini » que ce que tu as **exécuté et observé** (fichier regardé, métriques mesurées).
- **Découverte de chantiers en route.** Ce prompt est un plancher. Tout manque découvert est ajouté au journal, priorisé par impact qualité, et traité.
- **Langue.** Livrables humains en **français** ; code en anglais ; **prompts de génération en anglais** (grammaire Wan officielle).

---

## 1. ENVIRONNEMENT RÉEL (mesuré le 2026-07-27 — ne rien deviner)

- **Dépôt** `AuroraIA`, code sous `application/`. Branche de travail à créer : **`refonte/module-video`**.
- **Matériel** : RTX 5070 Ti **16 Go VRAM** (Blackwell sm_120, FP8 matériel) · **30 Go RAM** · **SWAP 31 Go** (⚠️ *pas 71* — mesuré `free -g` ; le block-swap consomme de la RAM hôte : **porter le swap à ~64 Go avant les sessions fp16**) · NVMe 915 Go dont **~90 Go libres (90 % plein)** — c'est la contrainte la plus dure du dossier · **3 ports USB 20 Gbps** (un SSD NVMe externe y ferait ~2 Go/s).
- **Services** (état mesuré) : **bridge Flask 3001 UP** · **ComfyUI 0.27.0 UP** sur 8188 (lancé avec `--novram`) · **tunnel cloudflared MORT** (`tunnel_url.txt` date du 17/07, URL injoignable, aucun process) · **Vite 1420 non démarré**.
- **ComfyUI** : `modele/comfyui/`. `custom_nodes/` contient **uniquement `ComfyUI-GGUF`** — tout le reste est à installer. **Aucun poids vidéo Wan dans ComfyUI.** ⚠️ **Le module vidéo n'utilise PAS ComfyUI pour générer** : le moteur est `diffusers` en subprocess ; ComfyUI ne sert qu'aux keyframes FLUX et à `/free`.
- **Poids réels** : `Wan2.2-TI2V-5B-Diffusers` **32 Go (complet, le seul moteur fonctionnel)** · `Lightricks/LTX-Video` 33 Go (ancien LTXV 0.9.8) · **`Wan2.2-T2V-A14B` 260 Ko et `I2V-A14B` 444 Ko = INDEX SEULS, poids absents** · **aucun GGUF QuantStack** · `flux2-dev-Q4_K_M.gguf` 20 Go · `qwen_image_2512_fp8` · Kokoro-82M · **chatterbox 13 Go orphelin**. Repos MuseTalk/SadTalker **absents**.
- **Venvs divergents (mesuré)** : `application/.venv` a `imageio_ffmpeg` mais **pas `gguf`** ; `modele/comfyui/venv` a `gguf` mais **pas `imageio_ffmpeg`**. **Aucun des deux ne peut faire le trajet complet.** `/usr/bin/python` **n'existe pas** ; `python3` système n'a pas torch.
- **Ollama installé** : `qwen3-coder-next:q4_K_M` (52 G), `qwen3.6:27b`, `deepseek-r1:32b`, `devstral`, `qwen3-vl:8b`, `qwen3-vl:30b`, `qwen3-coder:30b`, `qwen3:30b-a3b-instruct`, `nomic-embed-text`. ⚠️ La chaîne de résolution du storyboard (`qwen3:14b` → … → `qwen2.5-coder:7b`, bridge_server.py) **ne matche RIEN d'installé** → retombe sur « premier installé ».
- **Tests** : Node ≥ 22.6, depuis `application/` : `node --experimental-strip-types --test src/__tests__/{cinemaApi,videoCompositionPlanner,videoPromptComposer,videoBrollSynthesizer,videoTempoDetector,videoSubtitleExport,videoDrawingExpertBar}.test.ts` → **baseline 133 verts** (117 strictement vidéo). **Aucun test Python** sur cinema_pipeline/storyboard_norm.

---

## 2. CONTRAINTES DURES (violation = échec)

1. **Modifier UNIQUEMENT le module vidéo** (+ `python-services/cinema`, `video_generate.py`, vues/services vidéo TS, routes bridge vidéo de façon additive). Les autres modules sont **consommés comme services**. Ne jamais reproduire la régression historique sur `voice_tts`/`web_*`.
2. **JAMAIS d'install dans `application/.venv`** pour les briques lourdes → venv isolé (`~/.local/share/auroraia/venvs/<nom>`) ou venv ComfyUI pour les custom nodes. **Exception ciblée autorisée** : ajouter `gguf` à `application/python-services/requirements.txt` et `imageio-ffmpeg` au venv ComfyUI (§8, corriger la divergence).
3. **Un seul gros process GPU à la fois.** La file GPU existe désormais (`video_gpu_queue.py`) mais **Tauri la contourne** (§8) — à corriger.
4. **Discipline disque : réservation calculée, pas plancher fixe.** Un plancher constant de 20 Go est **numériquement faux** au 4K/8K : 13 s à 30 fps = 390 frames ; **4K 16 bits ≈ 19,4 Go/séquence, 8K 16 bits ≈ 78 Go/séquence**, et la chaîne fait cohabiter plusieurs séquences. → `needed_gb = f(l × h × frames × bits × étages_simultanés)` évalué **avant** de démarrer, refus honnête sinon. **Intermédiaires en FFV1/ProRes, séquences PNG interdites au-delà de 1440p.** Gisements purgeables : chatterbox 13 Go, doublon flux1-dev 17 Go, LTX-Video 33 Go si abandonné, TI2V-5B 32 Go si le draft bascule.
5. **DEUX PROFILS DE LICENCE ÉTANCHES** (§2.5 ci-dessous) — c'est une loi, pas une note.
6. **Ne pas polluer la racine.** Artefacts → `output/videos/`, `temp/cinema/` (avec GC).
7. **Aucun secret committé.**

### 2.5 Les deux rosters de licence (VÉRIFIÉS ligne à ligne dans les fichiers LICENSE)

**🔴 Le point le plus important de ce document.** L'utilisateur a écrit à Tencent et reçu « usage personnel possible, commercial risqué ». **Le contrat écrit est PLUS DUR que ce mail** :

> `TENCENT HUNYUAN COMMUNITY LICENSE`, ligne 3 : *« THIS LICENSE AGREEMENT DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA »*. Art. 1.l : *« "Territory" shall mean the worldwide territory, **excluding** the territory of the European Union… »*. Art. 5.c : *« You must not use, reproduce, modify, distribute, or display the Tencent Hunyuan Works, **Output or results**… outside the Territory. Any such use outside the Territory is **unlicensed and unauthorized** »*.

**Depuis la France il n'y a AUCUNE concession de droits — ni personnelle, ni commerciale — et les vidéos produites (« Output ») sont visées.** Un mail informel du support n'amende pas un contrat écrit. Texte **identique** pour HunyuanVideo-Foley. ⇒ **Hunyuan est éliminé du chemin par défaut, pas seulement du chemin lucratif.**

| Roster | Briques |
|---|---|
| **✅ COMMERCIAL** (Apache/MIT vérifiés) | **Wan 2.1/2.2 (Apache 2.0 pur, aucun appendice — vérifié)** : T2V-A14B, I2V-A14B, TI2V-5B, S2V-14B, Animate-14B · **VACE** (ali-vilab) · **Wan2.2-VACE-Fun-A14B** (alibaba-pai) · **SeedVR2** (ByteDance-Seed, Apache 2.0, ICLR 2026) · **Phantom**, **Stand-In**, **InfiniteTalk/MultiTalk** (MeiGen-AI), **LatentSync** (ByteDance) · **CosyVoice** · **ACE-Step 1.5** · **Qwen-Image / Qwen-Image-Edit-2511** (Apache 2.0) · **FLUX.1-schnell** · **MMAudio** |
| **🔴 PERSONNEL SEULEMENT — refus dur en profil commercial** | **HunyuanVideo 1.5 + HunyuanVideo-Foley** (exclusion territoriale UE) · **FLUX.1/FLUX.2 [dev]** (*FLUX [dev] Non-Commercial License* — faire tourner le modèle dans un pipeline lucratif est un usage commercial du modèle) · **InsightFace/ArcFace** packs `buffalo_l`/`antelopev2`/`inswapper_128` (*non-commercial research only*) et **ReActor** · **GIMM-VFI** et **KEEP** (S-Lab, NC) · tout CC-BY-NC (Fish Speech) · **DA3-Large/Giant** (CC BY-NC ; **DA3Metric-Large et DA3-Small/Base sont Apache**) |
| **🟠 À TRANCHER avant usage lucratif** | **LTX-2 / LTX-2.3** (*LTX-2 Community License* — **PAS Apache**, gratuit sous **10 M$ de CA** agrégé ; art. 18 interdit d'entraîner un modèle vidéo concurrent) · `ltxv-13b` local (licence LTXV antérieure, **différente**) · **SkyReels-V3** (Skywork Community, commercial autorisé, PDF à lire) · Stable Audio Open · MAGREF, Uni3C, MatAnyone, RVC, Matchering (GPL — vigilance sur le mode d'appel) |

**Conséquences structurelles à traiter :**
- **La porte de qualité elle-même était NC** : ArcFace est le pivot du scoring d'identité → en profil commercial, adopter un embedder permissif ou une métrique alternative.
- **Le chemin keyframes était NC** : FLUX [dev] → remplacer par **Qwen-Image / Qwen-Image-Edit-2511** (Apache) ou Wan 2.2 T2I en profil commercial.
- **Foley** : MMAudio devient le défaut commercial. Consigner honnêtement que les benchmarks 2026 placent Hunyuan-Foley **devant** — le profil commercial paie une perte mesurable, compensée par une bibliothèque de SFX libres.
- **`ltxv-13b` (15 Go) et `chatterbox` (13 Go)** : dormants, aucun code ne les référence → purger ou câbler.

### 2.8 Provenance et propriété intellectuelle du CONTENU
La fidélité au sujet est le cœur de la demande ; les droits d'exploitation des références sont la responsabilité de l'utilisateur, mais le pipeline **trace** et **avertit** :
- **Univers de marque** (Fortnite, séries animées…) : ne jamais nommer une IP tierce dans un prompt de production ; ne pas entraîner un LoRA de style sur des captures de l'œuvre pour un usage lucratif. **Décrire l'univers par ses attributs** (palette, échelle de stylisation, traitement de la lumière, densité géométrique, ambient occlusion).
- **Lieux réels** : la France **n'a pas de liberté de panorama** pour l'usage commercial. La fiche canon de lieu porte un champ `statut_juridique` (`libre`/`à vérifier`/`restreint`) remonté dans `warnings[]`.
- **Voix/visages** : bibliothèque de voix = voix de l'utilisateur, entourage consentant, ou libres de droits. Le garde-fou `public_figure` existant (préset de style, pas de clone) **reste en place**.

---

## 3. ÉTAT RÉEL (vérifié le 2026-07-27)

### 3.1 ✅ Ce qui est DÉJÀ LIVRÉ (par la session précédente — à préserver, ne pas refaire)
WS-V0 est **réellement en place et vérifié dans le code** : `python-services/storage/aurora_storage.py` + `setup_key.py` + tests, **6 routes `/api/storage/*`**, **file GPU `video_gpu_queue.py`** (enqueue/acquire/release/cancel, attente des jobs 3D, prévol `ensure_space`), propagation **seed + negative_prompt + motion_interp** au worker, `PR_SET_PDEATHSIG` anti-orphelin, aperçu keyframes async, self-test transformé en micro-rendu réel, `config/video_model_strategy.json`, `REFONTE_VIDEO_JOURNAL.md`, `docs/VIDEO_WEIGHTS_INVENTORY.md`, route `/api/video/gallery`.
**Le module a tourné pour de vrai** (26/07, 10 jobs) : E2E I2V premium mesuré **832×480 natif, 65 images/24 fps, 60 steps, 227 s, pic VRAM 94 %**, sortie 1280×720. **CosyVoice 3 installé en venv isolé** et validé sur deux synthèses françaises.
⚠️ **Mais `video_model_strategy.json` pose `"license_selection_blocking": false`** et *« les licences n'influencent pas la sélection »* → **directement contredit par §2.5 : à basculer.**

### 3.2 🔴 Ce qui BLOQUE la cible 4K / vertical / fidélité
1. **Clamp aveugle à l'orientation** — `video_generate.py:943-946` : `wan_w=min(width,…,1280)` / `wan_h=min(height,…,720)`. **Une demande 9:16 en 720×1280 sort en 720×720 CARRÉ.** La table de budget `:853-863` est **exclusivement paysage**. → le format de la référence est **impossible aujourd'hui**.
2. **« 4K » qui ment** — `cinema_pipeline.py:110-118` : `parse_resolution` connaît `"4k"` mais **pas `"8k"`**, et `.get(label,1080)` fait retomber toute étiquette inconnue sur 1080p **en silence**. `:141-174` : « 4K » = 1920×1080 généré puis **lanczos ×2**. `:2803-2811` revendique *« true 720p/1080p instead of upscaled-in-name »* pour un `scale=lanczos+unsharp` — **mensonge encore actif**.
3. **8 bits partout** — `libx264` seul (`cinema_pipeline.py:1088,1259,1379,1655,2839,2861`), **aucun x265**. Sur un dégradé de ciel coucher de soleil (exactement la référence), **banding garanti**.
4. **Upscale = redimensionnement** — `cinema_pipeline.py:2822` `scale=…:lanczos,unsharp` tracé `lanczos_upscale_unsharp`. C'est le « 720p mou » refusé.
5. **Aucun contrôle structurel** — grep VACE/depth/canny/control **vide** dans `video_generate.py` et `cinema_pipeline.py`. La capacité « lieu fidèle restylé » n'a **aucun code**.
6. **A14B jamais téléchargeable en l'état** — index seuls + `gguf` absent de `.venv` → le chemin « premium Q8 » annoncé (`video_generate.py:33-35`) **n'a jamais pu s'exécuter**.

### 3.2 bis ✅ Livré et validé le 2026-07-27 (session Claude)
- **Correctif d'orientation** (`video_generate.py`) : les budgets et plafonds natifs sont transposés en portrait. **Prouvé en rendu réel** — une demande 9:16 sort en **704×1280** (avant : 720×720 carré). Test A : 97 frames, 60 steps, 804 s, validation frame passée.
- **4 correctifs d'interpréteur** (`bridge_server.py`) : `["python", …]` → `sys.executable`. `/api/python/run` renvoyait *« No such file or directory »* à **chaque** appel ; vérifié réparé en direct.
- **`video_upscale_chain.py`** : chaîne de finition (deflicker → reconstruction x4 → descente → interpolation → grain → master 10 bits), reprise après interruption, cinq champs de vérité, refus d'étiqueter « 4K » sans reconstruction. Validée : 176×320 → 720×1308, ProRes 10 bits. *(Contournement : `realesrgan`/`basicsr` sont cassés dans ce venv — alias `torchvision.transforms.functional_tensor` posé en mémoire, jamais de patch du venv.)*
- **`video_longform.py`** : orchestrateur de long métrage, scène par scène, reprise, **estimation calibrée sur mesures réelles**. Ordres de grandeur : 2 min → 8 h ; 10 min → 1 j 18 h ; 30 min → 5 j ; **90 min → 16 jours**. ⚠️ Piège évité : le pipeline **ne génère pas à la résolution cible** (le budget adaptatif plafonne la surface à ~0,51 Mpix) — estimer sur la cible surestime d'un **facteur 4**. **Aucun texte à l'image par défaut.**
- **`image_to_motion.py`** : animation d'image importée avec **garde faciale**. Mesure le visage, le projette dans la résolution de génération, et agit **avant** de générer (recadrage auto, adoucissement du mouvement, refus explicite). Détection par tuiles 2/3/4/6 car BlazeFace rate un visage sous ~5 % de la largeur. Validé : visage 139 px dans une photo 3840×2160 → retrouvé → recadré → **185 px en génération**. **BlazeFace/mediapipe (Apache) et non InsightFace (NC)** — corrige une des dépendances non-commerciales de §2.5.
- **SeedVR2 7B sharp fp16 + VAE téléchargés** (16 Go) dans `modele/comfyui/models/SEEDVR2/` — à câbler dans la chaîne (WS-V1).

### 3.3 🔴 Ruptures de PARITÉ CLI / bridge / Tauri / tunnel (MESURÉES par sonde)
| | CLI direct | Bridge `/run-async` | Tauri natif | Bridge `/run` |
|---|---|---|---|---|
| interpréteur | `/usr/bin/python3` | `application/.venv` | `modele/comfyui/venv` | ~~`python` introuvable~~ **CORRIGÉ** |
| `gguf` | non | **non** | **oui** | — |
| `imageio_ffmpeg` | non | **oui** | **non** | — |
| `HF_HOME`, `COMFYUI_DIR`, `PYTORCH_CUDA_ALLOC_CONF` | absents | **posés** | **absents** | — |

- ✅ **CORRIGÉ ce jour** : `bridge_server.py` lançait `["python", …]` (binaire inexistant) en **4 endroits** (`/api/python/run`, voice STT, talking-head check/idle) → `sys.executable`. Vérifié en direct : `/api/python/run` exécute désormais réellement le script. *(C'était le chemin du navigateur local ET le repli 404/HTML.)*
- 🔴 **`toAssetUrl` (`useTauri.ts:1699-1719`)** ne retire que des préfixes Windows/docker → produit `/api/asset//home/juan/…` → **404 en navigateur et en tunnel**, alors que la forme relative renvoie 200. **La vidéo s'affiche en Tauri et est invisible via le tunnel.** Trois résolveurs d'URL concurrents coexistent.
- 🔴 **Deux moteurs selon le skin** (`App.tsx:120-125`) : v1/v3/v4 → `cinema_pipeline.py` ; `VideoView` → `video_generate.py`. Deux jeux de paramètres, deux dossiers, deux résolveurs.
- 🔴 **La moitié de la logique vit en TypeScript** (`VideoView.tsx:424-484` : contrat de référence EN, motionSuffix, distillation Ollama, résolution de durée, `composeWanPrompt`) et **n'existe pas en CLI** → même texte = deux vidéos sans rapport.
- 🔴 **Le seed n'est JAMAIS envoyé par l'UI** (`grep "'--seed'" src/` = **vide**) → **la reproductibilité est structurellement impossible**, donc aucun test de parité n'est possible aujourd'hui.
- 🔴 **`resolution:'720p'` codé en dur** (`useVideoViewLogic.ts:159`) alors que le défaut CLI est **1080p** → l'UI **dégrade sous son propre défaut**. **`quality_mode` jamais envoyé** → forcé `balanced` → **`premium` (3 tentatives QA, gate strict, 97 frames) est INATTEIGNABLE depuis toute UI.**
- 🔴 **Tauri contourne la file GPU** (`commands.rs:1767-1806` spawn direct) → vidéo + 3D simultanées possibles sur la même carte.
- 🔴 **`/api/tunnel/url` ment** : renvoie `ok:true` sans test de vie sur une URL morte depuis 10 jours.
- 🔴 **`/api/python/progress` est un flux GLOBAL** → deux jobs se maintiennent mutuellement « vivants », le watchdog anti-gel ne détecte jamais un vrai gel.
- 🔴 **JOB ZOMBIE — constaté en direct le 2026-07-27.** Un `cinema_pipeline.py` a été tué par l'OOM killer (`stderr.log` **vide**, process disparu, aucun code de sortie) et le bridge a continué d'annoncer `status: "running"` **indéfiniment**. Aucune détection de liveness du process. C'est un échec silencieux de premier ordre : l'UI aurait affiché « en cours » pour toujours. → **Le suivi de job doit vérifier que le PID est vivant**, et passer en `died` avec un diagnostic (dernier stage atteint, RAM au moment de la mort) sinon.
- 🔴 **AUCUNE GARDE MÉMOIRE (RAM) — cause racine de la mort ci-dessus.** La file GPU sérialise les jobs GPU, et `ensure_space()` garde le disque, mais **rien ne garde la RAM**. Or le rendu cinéma coexiste avec ComfyUI (FLUX2 Q4 = 20 Go), des téléchargements, et toute tâche CPU lourde ; avec 30 Go de RAM et 31 Go de swap, l'OOM killer arbitre. **Reproduit involontairement** : un téléchargement de 16 Go + une inférence RealESRGAN CPU + mediapipe lancés pendant un rendu ont fait monter la mémoire à 20 Go + 14 Go de swap et tué le pipeline. → Étendre le prévol à la **RAM** (refus ou mise en file si la mémoire disponible est insuffisante), et **décharger ComfyUI** (`/free`) avant tout job de rendu, ce que le pipeline fait déjà entre ses étapes mais pas au démarrage.
- 🔴 **CSP Tauri** : `media-src` **sans `https:`** → une vidéo servie par le tunnel est bloquée dans le shell Tauri ; `assetProtocol.scope` ne couvre pas le tier froid.

---

## 4. LOIS INVIOLABLES

1. **Anti-orphelin.** Toute capacité livrée est appelée en production et ajoutée à `src/__tests__/videoNoOrphanCapabilities.test.ts`.
2. **Zéro échec silencieux.** Tout repli est remonté dans `result.warnings[]` et pèse sur le grade. Un plan non noté est « non noté avec pénalité », jamais 7/10.
3. **Vérité de rendu — CINQ champs obligatoires** dans le JSON de job et dans l'UI : *résolution native de diffusion*, *résolution après chaque étage SR*, *résolution du master*, *profondeur de bits*, *liste ordonnée des modèles SR réellement exécutés*. **Interdiction d'écrire « 4K » si aucun modèle de restauration par diffusion n'a tourné.**
4. **Deux lois de résolution, à ne jamais confondre.**
   **(a) GÉNÉRATION** : la diffusion reste à la **résolution native d'entraînement** — 1280×720 paysage, **720×1280 vertical** pour Wan A14B. Demander 1080p+ à Wan est une **faute technique** (structures dupliquées, horizons répétés) : le modèle apprend une statistique d'échelle.
   **(b) LIVRAISON (nouvelle)** : **aucun livrable sous 3840×2160 / 2160×3840**. Le 4K s'atteint **uniquement par reconstruction par diffusion** (SeedVR2 + passe refiner), **jamais par un filtre d'agrandissement**. Un master obtenu par lanczos est un **échec de chantier**, pas un livrable dégradé.
5. **Profil de licence.** Chaque brique du manifeste porte `perso` | `commercial`. Un job en profil `commercial` **REFUSE** de charger une brique `perso` (erreur honnête, jamais de repli muet). Le profil est inscrit dans le résultat et dans les métadonnées du master.
6. **Chaîne 10 bits de bout en bout.** Tous les intermédiaires en ≥10 bits ; dither léger avant l'encodage 8 bits de livraison. C'est ce qui règle le banding du ciel — **plus visible à l'écran que le passage de 1080p à 4K**.
7. **Parité stricte.** CLI, bridge, Tauri et tunnel produisent **le même résultat pour le même spec**. Toute logique de génération vit en **Python**, jamais en TypeScript.
8. **Sérialisation GPU** (file unique, tous chemins), **réservation d'espace disque calculée**, et **garde RAM** avant tout job — les trois, pas seulement la première (§3.3 : un job a été tué par l'OOM killer faute de garde mémoire).
10. **Liveness des jobs.** Un job dont le process est mort ne reste JAMAIS `running` : le suivi vérifie le PID et bascule en `died` avec diagnostic. Un statut qui ment est pire qu'une erreur.
9. **QA mesurée, jamais synthétique.** Aucun score en dur ; le grade porte sur le **pire** passage QA ; la couverture QA est exposée.

---

## 5. MÉTHODE

Pour chaque chantier : **Reprise** (vérifier §3 preuve par preuve) → **Recherche** si limite → **Implémentation** → **Exécution réelle observée** → **Auto-correction** → **Validation** (§9-10) → **Traçabilité** : APPENDRE à `application/REFONTE_VIDEO_JOURNAL.md` (existant, ne pas écraser).
**Git** : branche `refonte/module-video`, commits atomiques français, tests verts à chaque commit. Baseline **≥ 133 tests** maintenue et augmentée.

---

## 6. ARCHITECTURE CIBLE

### 6.1 Génération — socle
- **Wan 2.2 A14B I2V d'abord** (le pipeline studio est *keyframe-image → I2V*, donc **l'I2V prime ; le T2V est optionnel** tant que le disque est contraint), en **GGUF Q8_0 ou fp8_scaled**, via **kijai/ComfyUI-WanVideoWrapper** + ComfyUI-GGUF + **SageAttention2** + torch.compile. MoE 2 experts chargés **séquentiellement** (jamais ensemble). **720×1280 vertical natif** ou 1280×720, **81 frames**, 20+20 steps (boundary ~0.875), CFG 3,5-4 / 3-3,5, shift 5,0 T2V / 3,0 I2V, umt5-xxl **FP16 en RAM (jamais Q4)**, VAE tiled.
- **Draft** : TI2V-5B (déjà sur disque) ou MagCache — **étiquetés « draft »**, jamais livrés.
- **Interdits en final** : LoRA lightning/distillation, TeaCache, Q4/Q5, 1080p natif.

### 6.2 Fidélité — QUATRE types d'entités (et non deux)
La bibliothèque d'entités couvre **PERSONNAGE**, **OBJET**, **LIEU**, **UNIVERS DE STYLE**. Distinguer nettement :
- **LoRA d'IDENTITÉ** (personnage/objet) : rank 32/alpha 16, trigger token, dataset 20-50 images, **le low-noise porte l'identité** ; entraîner **les deux experts** (musubi-tuner les traite séparément), fp8_base + blocks_to_swap 20-30, une nuit sur la 5070 Ti. Force 0.8-1.0 low / 0.4-0.7 high.
- **LoRA de STYLE (univers)** : **recette totalement différente** — **40 à 120 images de CONTENU VARIÉ** (paysages, architecture, eau, ciel, végétation, plans larges et serrés : si toutes les images sont des îles, la LoRA apprend « île » et non « style »), **captions inversées** (décrire le contenu en détail, **jamais le style**, trigger en tête → le modèle attribue le résidu au token), **rank 8-16** (rank 32-64 mémorise les compositions), lr 1e-4, 1500-3000 steps. **Deux LoRA (high+low)** obligatoires.
- **Auto-distillation de style** (la méthode qui rend un univers reproductible et évite le scraping d'IP) : générer 80-150 images avec un prompt long décrivant les **attributs** du look voulu → en faire juger 40-60 par le VLM contre référence (le `perfection_gate` du dépôt fait déjà ce type de jugement) → entraîner la LoRA sur les validées. Transforme « j'ai eu un beau plan une fois » en « je refais ce look sur 10 sujets ».
- **Zero-shot** : **Wan2.2-VACE-Fun-A14B** (Apache, seul VACE porté sur Wan 2.2) ; visage réaliste + **Stand-In** ; multi-sujets **Phantom 14B**. **Référence TOUJOURS détourée (SAM/RMBG)** — une réf avec fond pollue la scène.
- **Filet** : ReActor+GPEN **exclu du profil commercial** (InsightFace NC).

### 6.3 Reconnaissabilité d'un LIEU — la contrainte est géométrique, pas sémantique
Le modèle ne doit pas « se souvenir » du lieu, il doit être **empêché de déplacer les volumes**.
- ❌ **depth seul** : garde les volumes, perd la silhouette → « une maison », pas « CETTE maison ».
- ❌ **canny seul** : garde la silhouette mais impose les arêtes de texture → stylisation timide, photo « peinte ». **Piège n°1.**
- ✅ **La combinaison qui gagne** : **depth FORT** (poids 0,8-1,0, 100 % des steps ; **Video-Depth-Anything** ou DA3 — prendre **DA3Metric-Large/Small/Base, Apache** ; Large/Giant sont NC) **+ canny FAIBLE (0,3-0,5), coupé à 40-60 % des steps, et MASQUÉ PAR SEGMENTATION** — arêtes conservées **uniquement sur la structure bâtie et le rocher, jamais sur le feuillage, l'eau, le ciel**. *C'est le levier le plus rentable de tout l'audit* : un canny non masqué sur des pins = des milliers d'arêtes parasites qui tuent la stylisation. **+ image de référence** qui porte le style (VACE accepte « vidéo de contrôle + image de référence » : la vidéo porte la GÉOMÉTRIE, l'image porte le STYLE — séparation propre). Normales (NormalCrafter) en complément si les façades gondolent.
- **Mode « RESTYLE V2V depuis plaque réelle »** (absent aujourd'hui) : plaque filmée/reconstruite → depth+normales+canny masqué → VACE control + réf de style.

### 6.4 Contrôle réalisateur, caméra et parallaxe
- **Parallaxe crédible = vraie géométrie.** La référence oppose un premier plan à ~1 m et un fond à ~300 m : **aucun modèle de diffusion ne produit ce rapport de façon fiable depuis un prompt**.
  1. **Proxy 3D** : DA3 depuis 1-N photos → nuage de points / 3DGS / `.glb` → import Blender (`blender_bridge.py` existe) → caméra posée → rendu de **vidéo guide** (couleur brute + depth + canny masqué) à 720×1280, 81 frames. Le guide peut être troué : il ne sert qu'à contraindre.
  2. **🔑 Le premier plan se MODÉLISE, il ne se génère pas.** Le plat-bord et la rambarde = géométrie triviale (~30 min), 15 % du cadre, **90 % de la sensation de parallaxe**. Les rendre en 4K avec alpha et **compositer par-dessus** : net, stable, zéro flicker, mouvement exact. Demander à la diffusion un plat-bord cohérent sur 13 s est un combat perdu.
  3. **Uni3C** (0,95 B, plug-and-play sur nuages de points) si l'on veut rester 100 % diffusion ; **Wan2.2-Fun-Camera-Control-A14B** (pan/zoom/rotation, 2 passes high/low) si l'on n'a qu'une photo.
- **FLF2V** natif pour les raccords ; **frames ancrées VACE** à positions arbitraires (le mode le plus « réalisateur » et le plus sous-estimé) → c'est là que le `VideoKeyframeEditor` (aujourd'hui cul-de-sac) trouve son sens.
- **Editing** : SAM3 (+ **MatAnyone** pour l'alpha temporel) → dilatation 10-15 px → VACE inpaint.

### 6.5 Voix, lipsync, dialogues (la « totale » que la référence n'a pas)
- **Voix FR** : **Fun-CosyVoice 3** (déjà installé en venv isolé et validé) ; **RVC** en post-processeur pour verrouiller le timbre ; **MFA 3** (modèle FR, erreur < 15 ms) pour phonèmes/visèmes et QC du lipsync ; WhisperX pour les sous-titres.
- **Lipsync** : image fixe qui parle → **Wan2.2-S2V-14B** (corps + visage + caméra) ; long → **InfiniteTalk** ; resynchroniser une vidéo Wan → **InfiniteTalk V2V** + finition **LatentSync 1.6** (512, 25 fps en entrée, visage ≥ 200 px) ; plusieurs personnages dans un plan → **MultiTalk** (`model_multitalk.py` déjà présent). **Interpolation toujours APRÈS le lipsync.**
- **Audio** : **MMAudio** (Foley, profil commercial) · **ACE-Step 1.5** (musique, remplace MusicGen) · DeepFilterNet3 · ducking sidechain · **Matchering** · **loudnorm -14 LUFS**.

### 6.6 La chaîne 4K — ordonnée (l'ORDRE compte plus que le choix des modèles)
> **Le 4K natif en une passe n'existe pas sur 16 Go.** Même LTX-2.3, seul à revendiquer du « 4K natif », le fabrique par une **échelle multi-étages** (base basse → upsampler latent ×2 → raffinement en tuiles latentes). **C'est l'échelle qui fait le 4K, pas le modèle — et elle est reproductible avec n'importe quel générateur.**

0. **PLAQUE FIXE 4K** — modèle d'IMAGE (**Qwen-Image-Edit pour la fidélité structurelle**, puis refiner tuilé pour la lumière). Un modèle d'image atteint nativement ce qu'aucun modèle vidéo n'atteint. Cette plaque **fixe la géométrie, la lumière, le look**, sert de **référence de style VACE**, et porte la « correspondance au sujet ». **On itère sur une IMAGE (30 s/essai), pas sur une vidéo (40 min).**
1. **I2V à résolution native** — Wan 2.2 I2V A14B, **720×1280 strictement**, plaque réduite en Lanczos comme conditionnement, 81 frames, segments chaînés.
2. **Montée de taille NEUTRE** — 720×1280 → 1080×1920 (Lanczos ou **RealESRNet** — préférer RealESRNet à 4x-UltraSharp qui affûte agressivement et donne l'aspect « gravé »). Le GAN change la taille, il n'invente rien.
3. **RAFFINEMENT V2V bas denoise — l'étage qui donne la « matière »** : Wan 2.2 **expert BAS BRUIT** (littéralement conçu pour le détail fin), **denoise 0,25-0,30**, **MÊME SEED et MÊME PROMPT** qu'à l'étage 1, en tuiles (768, chevauchement 128, seam fixing). **⚠️ À 1080×1920, JAMAIS à 4K** : raffiner en 4K avec un modèle entraîné en 720p est **hors distribution** → chaque tuile croit voir une scène complète et injecte une micro-structure locale, le résultat paraît « grouillant ». *C'est la raison n°1 des raffinements 4K ratés.*
4. **INTERPOLATION** — RIFE 4.x (16 → 30/48 fps). Ici et pas ailleurs : avant l'upscale (sinon on paie 4×), après le lipsync.
5. **SEEDVR2 v2.5 → 4K** (l'étage long) — `seedvr2_ema_7b_sharp_fp16` (16,5 Go ; fp8 8,24 Go en repli). **7B et non 3B** : le 3B préserve un signal bruité, **le 7B crée du détail sur une entrée déjà propre** — la nôtre sort d'un générateur. BlockSwap 36, VAE tiling encoder 1024 / decoder 768, **batch_size 33 (contrainte 4n+1 impérative — un batch hors formule casse la temporalité)**, uniform batch ON, temporal_overlap 4, torch.compile ON, **postprocess de correction colorimétrique ON** (c'est lui qui recolle les dérives entre tuiles). **UNE SEULE passe** (un ×3 vaut mieux que deux ×1,7 : un upscaler de diffusion **re-synthétise**, empiler les passes empile les hallucinations).
6. **8K (optionnel, honnête)** — 4K → RealESRGAN → Lanczos vers 4320×7680 + grain 0,5 %. **JAMAIS une 2e passe SeedVR2.** Master d'archivage uniquement.
7. **MASTER** — ProRes 422 HQ 10 bits Rec.709 (~1,4 Go/13 s) ou x265 CRF 12-14 10 bits. **Pas de HDR** : toute la chaîne est entraînée en SDR 8 bits ; « sortir en HDR » = étirer du SDR = faux HDR mal géré par les plateformes. **`--tune grain` seulement si du grain a été ajouté volontairement.** Livraison : **YouTube en 4K même pour une audience 1080p** (débit alloué supérieur) ; TikTok en 1080×1920 **par réduction Lanczos du master 4K**, jamais par un rendu natif.
8. **Finitions** (§R4) : deflicker **avant** l'upscale ; étalonnage par **LUT généré** (zéro flicker par construction) + color-match inter-plans ; **grain par frame en DERNIER** (l'arme anti-plastique, dosé différemment en 4K qu'en 720p) ; DoF via depth ; compositing du premier plan 3D.

**Coût honnête : 4 à 8 h par plan de 13 s** — acceptable puisque le temps est indifférent. **Reprise après interruption obligatoire** (si le process meurt à la frame 250, il repart de 250) : exigence d'architecture, pas un confort, vu l'historique de gels de la machine.

### 6.7 Veille (à re-vérifier en début de chantier, sources primaires uniquement)
- **Wan 2.7 : poids ouverts NON CONFIRMÉS au 2026-07-27.** Vérification directe de `huggingface.co/Wan-AI` : **rien au-delà de la série Wan 2.2**. Les seules sources affirmant « Apache 2.0 » sont **wan27.org / nemovideo / creativeaishow** — du SEO. **Ne rien planifier dessus.** Re-vérifier uniquement sur `huggingface.co/Wan-AI`, `github.com/Wan-Video`, `blog.comfy.org`. Wan 2.5/2.6 : API seulement.
- Axes à surveiller : successeurs SeedVR2 / **FlashVSR** (3× plus rapide, artefacts en grille → **previews oui, master non**) · **GroundShot** et sa métrique *Environment/Scene Consistency* (cohérence de décor mesurée **après masquage des sujets** — exactement la métrique manquante) · **SANA-WM** (NVIDIA, 2,6 B, 6-DoF métrique sur un seul GPU) · **Stylos** (stylisation 3DGS — **encore de la recherche, pas de la production**) · **HY-World 2.0** (80 B+17 B : **hors de portée** de cette machine).

---

## 7. CHANTIERS

**WS-V0 ✅ FAIT** (§3.1) — sauf : basculer `license_selection_blocking` à **true** et implémenter le refus dur du profil commercial (loi §4.5).

**WS-V-P — PARITÉ D'ABORD** *(prérequis absolu : sans elle, aucun test de qualité ne veut rien dire).*
1. **Contrat unique** : `python-services/video_job_spec.py` — dataclass `VideoJobSpec` + JSON Schema versionné, contenant **tous** les paramètres (prompt utilisateur ET composé, seed, negative, w/h/aspect, frames, fps, quality_mode, profil de licence, échelle de repli **explicite**), sérialisation canonique → `spec_hash` sha256.
2. **Rapatrier la logique TS en Python** : `video_spec_builder.py` reçoit `videoPromptComposer.ts`, `resolveVideoDuration`, `MOTION_PRESETS`, `buildVideoProfiles`. L'UI n'envoie qu'une **intention** et **reçoit le spec résolu à afficher avant lancement**. Test de garde interdisant leur réapparition en TS.
3. **Point d'entrée unique** `POST /api/video/render` ; `/api/cinema/generate` et le chemin `video_generate.py` deviennent des **adaptateurs**. CLI = `video_render --spec` ou `--prompt …` passant par le **même** builder, avec `--print-spec`.
4. **Supprimer `run_python_script` côté Rust** et router Tauri par le bridge → restaure d'un coup file GPU, verrou 3D, prévol de stockage, journal par job, reprise.
5. **Contrat de résultat unique** `result.json` avec **`rel_path` TOUJOURS relatif au workspace** (un test refuse tout chemin absolu) → tue le 404 à la racine.
6. **Un seul résolveur d'asset TS** (supprimer `toAssetUrl`, `localFileToBridgeUrl`, `cinemaAssetUrl`) ; corriger la CSP Tauri (`media-src` + `https:`) et le scope du tier froid.
7. **Câbler ce qui est inatteignable** : seed, negative_prompt, `quality_mode` (dont **premium**), `resolution` (≥1440p), `aspect` **9:16**.
8. **Hygiène** : un seul interpréteur déclaré (`AURORA_PYTHON`), `gguf` dans `.venv`, `imageio-ffmpeg` côté ComfyUI, test qui échoue si les deux venvs divergent. `/api/tunnel/url` avec test de vie. `/api/python/progress` par jobId.
**DoD** : `test_video_parity.py --dry` (compare les `spec_hash` des 3 chemins, quelques secondes) **vert** ; `--real` (2 rendus seed fixe 512×320×25, compare `result.json` puis PSNR > 45 dB) vert ; `--tunnel` vert après test de vie. **Une vidéo générée est visible à l'identique en Tauri, en navigateur local et via le tunnel.**

**WS-V1 — Moteur 4K.** Installer les custom nodes (WanVideoWrapper, SeedVR2, VideoHelperSuite, Frame-Interpolation, TiledDiffusion, controlnet_aux, segment-anything) + poids **A14B I2V Q8** + `gguf` dans `.venv`. Corriger le **clamp d'orientation** (`:943-946`) et la **table de budget paysage** (`:853-863`). Implémenter la chaîne §6.6 dans `video_upscale_chain.py` (**par étage, frames sur disque, reprise après interruption, manifeste JSON par étage**). Supprimer `lanczos_upscale_unsharp` du chemin de livraison. Faire échouer explicitement `"8k"` au lieu de retomber sur 1080p.
**DoD** : un plan 5 s généré en **1280×720 natif ET en 720×1280 natif (vertical NON dégradé en carré)**, tous deux observés ; un master **3840×2160 vérifié par ffprobe** ; **mesure objective de netteté (énergie haute-fréquence/MTF) prouvant le gain vs le même plan agrandi en lanczos** ; absence de couture de tuiles ; absence de banding sur un dégradé de ciel ; **10 bits confirmé** ; VRAM stable sur 3 rendus.

**WS-V11 — Fiche canon de LIEU (« structure pack »).** Acquisition (photos/vidéo/drone) → reconstruction (DA3 → nuage de points/3DGS/glb ; COLMAP+3DGS si beaucoup de photos) → **pack de contrôle réutilisable** : depth temporellement stable, normales, canny **masqué par segmentation**, masque de premier plan, descripteur de reconnaissabilité (silhouette + repères), **champ `statut_juridique`**. Étage stockage : catégorie `location_pack` à ajouter au manifeste.
**DoD** : le **même lieu se re-tourne sous 3 angles et dans 2 univers sans nouvelle capture**, reconnaissable à l'œil **et par le juge VLM interrogé en aveugle**.

**WS-V12 — Transfert d'univers.** Fiche canon de STYLE (10-30 références décrites **par attributs, jamais par la marque**) → **LoRA de style** (recette §6.2, double high/low) → application **V2V par VACE depth+canny masqué** sur le structure pack → keyframe de tête restylée par **Qwen-Image-Edit-2511** → **porte à DEUX SEUILS ANTAGONISTES** : *(a)* reconnaissabilité (similarité structurelle vs plaque d'origine ≥ seuil **+ juge VLM en aveugle : « quel lieu est-ce ? »**) et *(b)* transformation (similarité de style vs références ≥ seuil **ET** distance colorimétrique/texturale au réel ≥ seuil). Un score qui maximise la fidélité produit une photo ; un score qui maximise le style produit un lieu méconnaissable.
**DoD** : un même sujet livré dans **3 univers distincts**, les 3 reconnus comme le même sujet par le juge en aveugle, les 3 jugés stylistiquement distincts.

**WS-V13 — Vertical natif 4K.** Génération native 720×1280 ; **grammaire de composition verticale** (couche de premier plan pour la parallaxe, safe-areas UI TikTok/Reels, règle de la première seconde) ; trajectoire caméra lente commandée ; sous-titres ASS burn-in ; **master 2160×3840**. ⚠️ Le recadrage 9:16 depuis un master 16:9 **détruit** une composition verticale d'auteur (le sujet de parallaxe est dans le coin inférieur) — le crop reste pour les dérivés seulement.
**DoD** : produire un plan **dépassant la référence de l'utilisateur** (sujet précis reconnaissable, restylé, coucher de soleil, premier plan en parallaxe, 13 s, **2160×3840**), **avec dialogue synchronisé et musique** — jugé supérieur à la référence par le juge VLM et au visionnage.

**WS-V2/V3/V4/V5/V6/V7** — identité personnage, contrôle réalisateur, film multi-plans, voix/lipsync, post-prod, audio : conserver les objectifs, avec les corrections de licence (§2.5) et la chaîne 4K (§6.6).

**WS-V8 — Front unifié** : une implémentation par capacité, panneaux qualité factorisés, suivi des jobs secondaires, galerie persistante, **labels honnêtes** (moteurs/fps/résolutions réels), suppression des vues mortes.

**WS-V9 — QA honnête** : lois §4.2/4.9, couverture QA exposée, scoring par take, tests Python (`storyboard_norm`, gates, durées), garde anti-orphelin, métriques sous `output/video-metrics/`.

**WS-V10 — Autonomie** : détection de limite → recherche → installation isolée → **A/B au barème réel sur mêmes prompts/seeds** → adoption ou retrait propre. Veille §6.7 outillée.

---

## 8. TESTS & VALIDATION

- **Baseline** ≥ 133 tests TS verts, augmentée. Corriger `cinemaApi.test.ts:186-199` (contrat `voice_slug` vs `character`).
- **Parité** : `test_video_parity.py --dry|--real|--tunnel` (WS-V-P) — c'est le test qui aurait attrapé le 720p codé en dur, le `quality_mode` forcé et le seed manquant.
- **Validation d'un rendu = quadruple** : *(a)* métriques objectives (ffprobe résolution/bits/codec, **netteté effective**, banding, coutures, flicker, identité/reconnaissabilité) ; *(b)* juge VLM ; *(c)* **ton visionnage réel du fichier** (frame par frame sur les raccords et les lèvres) ; *(d)* **parité des 3 chemins**. *Un fichier 4K dont la netteté effective est celle d'un 720p est un ÉCHEC, pas un livrable.*

## 9. DEFINITION OF DONE
(a) DoD du chantier verts **par exécution réelle observée** ; (b) baseline maintenue ; (c) aucune régression (vidéo, voix partagée, FLUX/3D) ; (d) anti-orphelin à jour ; (e) zéro échec silencieux ; (f) profil de licence respecté et tracé ; (g) journal écrit avec temps réels et preuves de licence.

## 10. LIVRABLES
1. Code (branche `refonte/module-video`), commits atomiques français.
2. `REFONTE_VIDEO_JOURNAL.md` (existant — **appendre**).
3. `docs/VIDEO_WEIGHTS_INVENTORY.md` avec deux colonnes obligatoires : **`profil`** (perso|commercial|à trancher) et **`preuve_licence`** (URL du LICENSE consulté + date). *Une ligne sans preuve vaut « à trancher », donc interdite en profil commercial.*
4. Tests (baseline + Python + parité + smoke E2E + anti-orphelin).
5. Récapitulatif final : reste à faire, risques, validations live longues.

---

**Commence par WS-V-P (la parité), puis WS-V1 (le 4K), puis WS-V11→V13 (la fidélité au sujet et le vertical). Le seul critère est la qualité finale — et tu ne mens jamais sur ton résultat.**
