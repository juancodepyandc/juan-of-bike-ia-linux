# PROMPT MAÎTRE — Stockage sur clé + Modèles vidéo studio d'AuroraIA (à coder de A à Z)

> **À l'IA qui reçoit ce prompt.** Objectif : coder de bout en bout **(1)** un système de stockage à deux étages (NVMe interne « chaud » + clé USB « froide ») qui **ne manque JAMAIS de place** et **redirige proprement les sorties vers la clé**, et **(2)** le pipeline de génération vidéo studio qui charge ses poids depuis ce stockage vers RAM+VRAM avec swap. Ce document est autonome, factuel (mesures réelles du 2026-07-17), et codable. Il complète `PROMPT_REFONTE_MODULE_VIDEO.md` (qui détaille les chantiers vidéo WS-V0→V10) : **ici on spécifie le SOCLE stockage dont tout le reste dépend**. Le seul critère est la qualité finale ; le temps est indifférent (offload lourd + swap assumés).

---

## 0. LA VÉRITÉ MATÉRIELLE (mesurée — ne rien deviner)

**Trois murs mémoire, à ne jamais confondre :**
1. **VRAM 16 Go** (RTX 5070 Ti, Blackwell sm_120, FP8 matériel) = **plafond dur**. Le modèle actif doit tenir/être block-swappé dans 16 Go où qu'il soit stocké → Q8_0/FP8-scaled + block-swap obligatoires ; jamais BF16 pleinement résident ; **deux gros modèles ne cohabitent JAMAIS** (ils tournent en série avec déchargement).
2. **RAM 30 Go** = **vrai goulot d'exécution**. Le block-swap charge le modèle en RAM puis stream les blocs vers la VRAM ; le débordement tombe sur le **swap (71 Go, NVMe interne)**. C'est ici que vit « l'offload lourd + un peu de swap ».
3. **Disque = simple stockage**. C'est le seul mur que la clé fait tomber.

**Le stockage, chiffré (mesuré) :**
- **NVMe interne** : `nvme0n1p2`, 930 Go, **~77 Go libres seulement (92 % plein)**. Rapide (~2-3 Go/s). Swap dessus.
- **Clé USB** : `/dev/sda`, **982 Go**, reformatée **ext4** (label `AURORA_MODELS`, montée sur `/mnt/aurora_models`). **Vitesse réelle mesurée : ~23 Mo/s (USB 2.0)** — la clé est bridée en 2.0 sur les deux ports testés. **Lecture séquentielle froide uniquement.**
- **Insight décisif** : au runtime le block-swap est **RAM↔VRAM**, jamais disque↔VRAM. Un fichier de poids n'est lu **qu'UNE fois** au chargement (et avec le ComfyUI résident, il reste ensuite en RAM entre les plans). **Donc la lenteur de la clé ne pénalise QUE le chargement initial, pas la génération.**

**Inventaire réel des données (mesuré) :**
| Emplacement | Poids | Chaud/Froid |
|---|---|---|
| Ollama `/usr/share/ollama/.ollama/models` (LLM conv/code/vision/storyboard) | **107 Go** | **CHAUD** — reste interne |
| `~/.cache/huggingface` (vidéo TI2V 32G + LTX 33G, voix…) | **283 Go** | mixte |
| `modele/huggingface` (cache Windows : FLUX, Hunyuan3D, doublons) | **59 Go** | mixte |
| `modele/comfyui/models` (FLUX image + encodeurs) | **22 Go** | mixte (FLUX actif = chaud) |
| `application/output` (vraies sorties livrées) | **605 Mo** | **FROID → clé** |
| `scratchpad` (GLB 3D expérimentaux) | **21 Go** | archive/jetable |
| Orphelins purgeables | chatterbox 13G, doublon flux1-dev 17G | à supprimer |

---

## 1. DOCTRINE DE TIERING (la règle qui décide où va chaque octet)

**Loi d'or : sur la clé (23 Mo/s) → uniquement du FROID** (écrit-une-fois-lu-rarement, ou chargé-une-fois-par-session). **Jamais de CHAUD** (rechargé en boucle).

| Catégorie | Étage | Raison |
|---|---|---|
| **LLM Ollama** (conv, code, storyboard, vision QA) | **INTERNE (chaud)** — INTERDIT sur clé | Rechargés à chaque message/plan ; à 23 Mo/s, charger un 52 Go = ~38 min → app injouable |
| **FLUX en usage** (image, keyframes) | INTERNE (chaud) | Chargé par génération d'image, fréquent |
| **Poids de génération vidéo/3D** (Wan, VACE, S2V, SeedVR2, LTX, TI2V, Hunyuan3D…) | **CLÉ (froid)** | Chargés une fois par session de rendu, résidents ensuite ; ~22 min de charge initiale acceptable |
| **Candidats A/B, alternatives, doublons, orphelins** | **CLÉ (froid)** ou purge | Rarement chargés |
| **Livrables compressés** (x265/AV1, mp4 de diffusion) | **CLÉ (froid)** | Écrits une fois, relus rarement ; playback ≪ 23 Mo/s → aucune pénalité |
| **⚠️ MASTERS 4K/8K et intermédiaires lourds** | **ÉTAGE RAPIDE OBLIGATOIRE (interne ou SSD externe)** | **Un master ProRes 422 HQ 4K30 ≈ 88 Mo/s** — hors de portée d'une clé à 23 Mo/s en lecture comme en écriture (un master 4K de 90 s ≈ 8 Go ≈ **6 min d'écriture**). La clé ne peut PAS porter les masters. |
| **Scratch de rendu** (`temp/cinema/job_*` : frames PNG intermédiaires) | **INTERNE (chaud)** puis final → clé | Écritures rapides intensives pendant le rendu ; seul le `final.mp4` migre sur la clé |

**Staging (chaud temporaire) :** pour une session vidéo qui recharge souvent le même modèle (boucle A/B), on peut **promouvoir** le modèle clé→interne une fois (copie), travailler à pleine vitesse, puis **rétrograder** (supprimer la copie interne, la clé reste la source de vérité). Configurable, avec garde d'espace.

---

## 2. LE SOUS-SYSTÈME À CODER — « Aurora Storage Manager » (A→Z)

Créer `application/python-services/storage/aurora_storage.py` (+ routes bridge `/api/storage/*`). **Aucune modification du code métier des modules** : tout passe par symlinks/redirections/`extra_model_paths.yaml`, de façon réversible.

### 2.1 Manifeste de tiering (source de vérité)
`application/config/storage_manifest.json` : liste déclarative `{ id, kind(llm|image|video|3d|voice|output|orphan), hot_path, cold_path, size_gb, tier(hot|cold|staged), pin(true si jamais déplaçable, ex. LLM), last_access }`. Le manager lit/écrit ce manifeste ; c'est lui qui documente honnêtement où vit chaque octet.

### 2.2 Stratégie de redirection (par type, réversible)
- **Modèles HuggingFace** (`~/.cache/huggingface/hub/models--ORG--NAME`) : déplacer le dossier du modèle vers `/mnt/aurora_models/hf/hub/models--ORG--NAME`, puis **symlink** à l'emplacement d'origine. HF résout les symlinks nativement. (Ou `HF_HOME` par-sous-processus pointant sur la clé pour les modèles froids — mais le symlink par-modèle est plus granulaire et robuste.)
- **Modèles ComfyUI** (checkpoints/unet/vae/loras vidéo) : les poser sur la clé et les enregistrer via **`extra_model_paths.yaml`** de ComfyUI (mécanisme natif) pointant `/mnt/aurora_models/comfyui/...` — pas de symlink fragile, ComfyUI scanne ces chemins.
- **Sorties** : `application/output/videos` et la galerie finale → **symlink vers `/mnt/aurora_models/outputs/videos`**. Le pipeline écrit son `final.mp4` là sans le savoir.
- **Scratch de rendu** : `temp/cinema/job_*` **reste sur l'interne** (frames PNG = écritures rapides) ; à la fin d'un job, le manager **migre le `final.mp4` vers la clé** et remplace par un symlink (ou met à jour la galerie).

### 2.3 Garde d'espace — « ne JAMAIS manquer de place » (le cœur)
Fonction `ensure_space(target_tier, needed_gb)` appelée **avant tout téléchargement, tout rendu, toute écriture lourde** :
- **⚠️ RÉSERVATION CALCULÉE, PAS PLANCHER FIXE.** Un plancher constant est **structurellement faux dès le 4K**. Chiffres pour 13 s à 30 fps (390 frames) : **4K 16 bits ≈ 49,8 Mo/frame → 19,4 Go par séquence** ; **8K 16 bits ≈ 199 Mo/frame → 78 Go par séquence**. La chaîne de post-prod fait cohabiter **plusieurs séquences** (deflicker → SR → étalonnage → grain) : avec ~90 Go libres, **un seul plan 8K sature le disque**. → `needed_gb = f(largeur × hauteur × frames × bits × étages_simultanés)` évalué **AVANT** de démarrer, refus honnête sinon. **Intermédiaires en FFV1/ProRes ; séquences PNG interdites au-delà de 1440p.**
- **Planchers durs (en plus de la réservation)** : interne **jamais < 20 Go libres**, clé **jamais < 20 Go libres**. `df` réel à chaque appel.
- Si l'étage cible manque de place :
  1. **Éviction LRU vers la clé** : déplacer le modèle froid le moins récemment utilisé (hors `pin`) interne→clé, re-symlinker, mettre à jour le manifeste.
  2. Si toujours insuffisant (ou étage = clé pleine) : **refus explicite avec erreur honnête** (`{ok:false, reason:"disk_full", tier, free_gb, needed_gb, suggestion}`), **jamais d'écriture silencieuse qui remplit le disque**.
- **Zéro échec silencieux** : chaque décision (éviction, refus, migration) est loggée et remontée dans le résultat du job (`warnings[]`).

### 2.4 Cycle installe→mesure→garde/purge (autonomie)
Quand un nouveau modèle est évalué (boucle A/B des chantiers vidéo) : `stage_for_eval()` le pose sur la clé (froid), `ensure_space()` avant DL ; si l'A/B le retient → `pin`/garde ; sinon → `purge()` propre (suppression fichiers + entrée manifeste, zéro résidu). La clé étant grande (982 Go), **on garde toute la bibliothèque de candidats froids installée** au lieu de re-télécharger — meilleur pour l'autonomie.

### 2.5 GC (nettoyage)
`gc()` : purge `temp/cinema/job_*` finis > N min (aujourd'hui AUCUN nettoyage n'existe → le disque se remplit), archive les takes perdants du scoring vidéo, propose la suppression du scratchpad 3D expérimental (21 Go) et des orphelins (chatterbox 13G, doublon flux1-dev 17G).

### 2.6 Robustesse clé absente / débranchée
- `fstab` avec `nofail` (déjà posé) → le boot ne bloque pas sans la clé.
- Au démarrage du bridge, le manager **vérifie `os.path.ismount('/mnt/aurora_models')`**. Si absent :
  - Modèles froids sur clé = **indisponibles → erreur honnête** (`{ok:false, reason:"cold_storage_offline", model, action:"rebrancher la clé AURORA_MODELS"}`), jamais un crash ni un fallback muet.
  - Nouvelles sorties → **repli temporaire sur l'interne** + warning (« clé absente, écriture sur disque interne, place limitée »).
- Le symlink cassé (clé absente) est détecté et signalé, pas suivi aveuglément.

### 2.7 Endpoints bridge (`bridge_server.py`, additifs)
- `GET /api/storage/status` → `{ key_mounted, tiers:{internal:{total_gb,free_gb}, key:{total_gb,free_gb}}, models:[{id,tier,size_gb,path,last_access}], outputs_tier, warnings[] }`. **Alimente un panneau UI de vérité de stockage.**
- `POST /api/storage/tier` `{model_id, tier}` → migre + re-symlink + manifeste.
- `POST /api/storage/stage` `{model_id}` / `POST /api/storage/unstage` → promote/demote chaud temporaire.
- `POST /api/storage/gc` `{dry_run}` → nettoyage (dry-run par défaut, comme les skills `aurora-cleanup-*`).
- `POST /api/storage/purge` `{model_id}` → suppression propre d'un candidat rejeté.

### 2.8 Setup initial (script one-shot, idempotent)
`application/python-services/storage/setup_key.py` : vérifie le montage, crée l'arbre `/mnt/aurora_models/{hf/hub, comfyui/{checkpoints,unet,vae,loras,upscale_models,frame_interpolation,audio_encoders}, outputs/videos, archive}`, applique les redirections du manifeste, écrit le rapport dans `application/docs/VIDEO_WEIGHTS_INVENTORY.md`. Réexécutable sans casse.

---

## 3. REDIRECTION DES SORTIES — proprement (détail)

1. **Générations vidéo** : le pipeline écrit dans `application/output/videos/` → ce dossier est un **symlink vers `/mnt/aurora_models/outputs/videos/`**. Zéro ligne de code métier changée.
2. **Scratch cinéma** : `temp/cinema/` **reste interne** ; hook de fin de job (`_run_python_job`, bridge_server.py:3397) → `migrate_final_to_key(job_dir)` copie `final.mp4` vers la clé, met à jour `status.json` avec le chemin clé, purge le job_dir.
3. **Galerie** : nouvelle route `GET /api/video/gallery` qui liste `/mnt/aurora_models/outputs/videos/*.mp4` (survit au reboot et au changement de module ; aujourd'hui l'UI oublie les rendus). Servie via `/api/asset/`.
4. **Fallback** : si clé absente au moment d'écrire, `ensure_output_target()` renvoie l'interne + warning, et re-migre vers la clé au prochain montage.

---

## 4. LA STACK MODÈLES VIDÉO STUDIO (recherche web confirmée juillet 2026) — avec étage

> Toutes ces briques tiennent sur 16 Go via offload/block-swap (temps indifférent). Intégration cible : **ComfyUI devient le moteur résident** (queue native, poids gardés en RAM entre plans) piloté par l'API `/prompt` (comme `flux_reference_synth.py` pour FLUX). Le block-swap Wan A14B Q8 (15,4 Go) sur 16 Go = « faisable avec block-swap important » + `prefetch_blocks=1` (masque le transfert) — c'est le régime offload+swap assumé.

| Rôle | Modèle (nom exact) | Taille | Étage | Note |
|---|---|---|---|---|
| **Génération — socle prouvé** | Wan 2.2 A14B T2V+I2V GGUF **Q8_0** (city96/QuantStack) + umt5-xxl FP16 + wan_2.1_vae | ~15,4 Go/expert ×2 | CLÉ | via kijai **WanVideoWrapper** + ComfyUI-GGUF + **SageAttention2** + torch.compile ; 720p natif, 20+20 steps, CFG 3,5-4/3-3,5 ; jamais LoRA lightning/TeaCache en final |
| **Wan 2.7** | ⚠️ **POIDS OUVERTS NON CONFIRMÉS au 2026-07-27** | — | — | Vérification directe de `huggingface.co/Wan-AI` : **rien au-delà de la série Wan 2.2**. Les seules sources affirmant « Apache 2.0 » sont wan27.org / nemovideo / creativeaishow — du SEO. **NE RIEN PLANIFIER DESSUS.** Re-vérifier uniquement sur huggingface.co/Wan-AI, github.com/Wan-Video, blog.comfy.org |
| ~~Génération — physique/détail~~ | 🔴 **HunyuanVideo 1.5 — PERSO UNIQUEMENT, EXCLU DU PROFIL COMMERCIAL** | ~14-17 Go | — | **Fait vérifié dans le LICENSE** : le « Territory » **exclut l'UE, le UK et la Corée du Sud** ; art. 5.c interdit l'usage des œuvres **et de leurs Outputs** hors Territoire. Depuis la France : **aucune concession de droits, même personnelle**. + seuil 100 M MAU + interdiction d'entraîner sur les sorties. Idem **HunyuanVideo-Foley** (texte identique) → **MMAudio devient le défaut Foley** |
| Génération — audio+vidéo 1 passe | LTX-2 (déjà « 2.3 » en blueprint local) FP8 non-distillé | ~12-15 Go | CLÉ | 4K/50fps + audio synchrone |
| **Fidélité identité — zero-shot** | Wan 2.2 **VACE Fun R2V** + **Stand-In** (visage) + **Phantom 14B** (multi-sujets) + MAGREF | Q8 + swap | CLÉ | réf **détourée SAM3/RMBG** obligatoire |
| **Fidélité identité — studio** | **LoRA Wan 2.2** via **musubi-tuner** (rank 32, fp8_base, blocks_to_swap 20-30, 1 nuit) | LoRA légers | CLÉ | entraîne high+low, low porte l'identité |
| Talking-head image fixe | **Wan2.2-S2V-14B** ; long → **InfiniteTalk** | fp8 + swap | CLÉ | S2V = corps+visage+caméra |
| Lipsync sur vidéo générée | **InfiniteTalk V2V** ; finition **LatentSync 1.6** | fp8 + swap | CLÉ | dialogue multi-perso : **MultiTalk** (`model_multitalk.py` déjà présent) |
| Voix FR clonage | **Fun-CosyVoice 3 0.5B** + **RVC** (verrou timbre) + **MFA** (align) | < 6 Go | CLÉ/interne | remplace XTTS/F5 morts ; Fish Speech NC = exclu |
| Upscale/restauration | **SeedVR2 v2.5 7B** FP16 + BlockSwap (batchs 4n+1) | ~ swap | CLÉ | seul upscaler diffusion temporellement cohérent |
| Interpolation | **GIMM-VFI** (repli RIFE 4.9) | ~3-6 Go | CLÉ | après lipsync, jamais avant |
| Restauration visage | **KEEP** (temporel — jamais CodeFormer frame-par-frame) | < 8 Go | CLÉ | |
| Étalonnage / grain | ComfyUI-VideoColorGrading (LUT) + color-matcher + ProPost grain | légers | CLÉ | grain = dernier effet |
| Foley / musique | **MMAudio** (défaut commercial) + **ACE-Step 1.5** (remplace MusicGen) | offload | CLÉ | HunyuanVideo-Foley **interdit** (§ligne 114). Consigner honnêtement que les benchmarks 2026 placent Hunyuan-Foley devant MMAudio : le profil commercial paie une perte mesurable, à compenser par une bibliothèque de SFX libres. + DeepFilterNet3, Matchering, loudnorm -14 LUFS |
| **Fidélité de LIEU / univers** (nouveau) | Video-Depth-Anything ou **DA3Metric-Large (Apache ; Large/Giant sont NC)** · SAM3 + MatAnyone · **Wan2.2-VACE-Fun-A14B** (Apache) · **Qwen-Image-Edit-2511** (Apache) · LoRA de style | ~25-30 Go | CLÉ | catégories de manifeste à ajouter : `location_pack`, `style_universe`, `lora`, `master` |
| **Chaîne 4K** | **SeedVR2 v2.5 7B sharp** fp16 16,5 Go (fp8 8,24 Go) · RealESRNet/RealESRGAN · RIFE · TiledDiffusion | ~20 Go | CLÉ | tuilage obligatoire au-delà de 1440p ; **FlashVSR** en challenger A/B (previews seulement, artefacts en grille) |

**Purger/décider (libère l'interne) :** chatterbox 13G (orphelin), doublon flux1-dev 17G, ltxv-13b 15G dormant. **Somme des poids cibles ≈ 150-170 Go → sur la clé, jamais sur l'interne.**

---

## 5. DEFINITION OF DONE & TESTS (exécution réelle observée)

1. **Stockage** : `GET /api/storage/status` renvoie la vérité (montée, espace par étage, tier de chaque modèle) ; un modèle froid déplacé sur la clé se **charge et génère** réellement ; l'interne ne descend jamais sous 20 Go (garde testée par un scénario de saturation) ; clé débranchée → erreur honnête, **aucun crash, aucun remplissage silencieux** ; sorties écrites sur la clé et **relisibles après reboot** (fstab).
2. **Redirection sorties** : un rendu vidéo atterrit dans `/mnt/aurora_models/outputs/videos/`, apparaît dans `/api/video/gallery`, survit au reboot ; `temp/cinema` est nettoyé par le GC.
3. **Génération** : un plan 5 s 720p natif A14B Q8 chargé **depuis la clé** vers RAM+VRAM, rendu et **observé** ; VRAM stable sur 3 rendus consécutifs (block-swap + swap NVMe).
4. **Tests** : unitaires du storage manager (tiering, ensure_space avec disque simulé plein, fallback clé absente, symlink/rollback) ; smoke-render E2E ; garde anti-orphelin.
5. **Traçabilité** : `application/docs/VIDEO_WEIGHTS_INVENTORY.md` (nom, taille, licence, étage, chemin) + `REFONTE_VIDEO_JOURNAL.md` (décisions, A/B, temps réels).

---

## 6. ÉTAT DU SETUP CLÉ (fait / à finir)
- Clé `/dev/sda` 982 Go **reformatée ext4** (label `AURORA_MODELS`), montée `/mnt/aurora_models`, droits `juan`. `fstab` automount `nofail`. *(Commandes fournies hors de ce document ; vérifier `df -h /mnt/aurora_models` avant de coder.)*
- **Vitesse : ~23 Mo/s (USB 2.0)** — dépannage froid pour les POIDS et les livrables compressés uniquement.
- 🔴 **AVEC L'EXIGENCE 4K/8K, LE SSD NVMe EXTERNE DEVIENT UN PRÉREQUIS, PAS UN CONFORT.** La clé ne peut porter ni les intermédiaires (19,4 Go/séquence en 4K) ni les masters (88 Mo/s requis contre 23 disponibles). Écrire noir sur blanc : **le 4K/8K ne se livre pas sur une clé USB 2.0.** Les 3 ports 20 Gbps de la machine donnent ~2 Go/s à un SSD NVMe externe, qui pourrait accueillir *aussi* les modèles chauds. Le storage manager reste **agnostique au support** (chemin de montage configurable) pour basculer clé→SSD sans réécriture.

---

**Commence par : vérifier le montage `/mnt/aurora_models`, coder le storage manager (§2) + la redirection des sorties (§3), prouver la garde d'espace et le fallback clé-absente, PUIS installer la stack §4 sur la clé et rendre un premier plan chargé depuis la clé. Le seul critère est la qualité finale — et tu ne remplis JAMAIS le disque en silence.**
