# HANDOFF — Aurora Modules Expert Uplift

**Mission**: Hisser CHAQUE module d'AuroraIA-v2 au niveau "principal engineer 15+ ans d'expérience" sur tous les axes (système prompts, logique métier, UX, edge cases, perf, accessibilité, sécurité). Pas de surface — pousse à fond sur les détails qu'un user lambda ne penserait pas à demander.

---

## 1. Contexte zéro à connaître

**cwd**: `C:\Users\Juan\Desktop\ia\AuroraIA-v2\` (Windows 11, Python 3.12, Node 24, Ollama local avec `qwen3-coder:30b-a3b-q4_K_M` + `qwen3-vl:30b` + `qwen3:14b`).

**User**: Juan, lycéen STI2D/SIN (futur ingénieur). Veut une IA polyvalente qui pense PROFONDÉMENT, pas un assistant générique.

**Architecture déjà en place** (cf. `AGENT_SYSTEM.md`): 37 agents claude-opus-4-7, 11 modules (conversation, code, image, voice, video, drawing, 3d, learning, cyber, simulator, cowork), bridge Python sur :3001, Vite sur :1420, tunnel cloudflared.

**Stack 3D**: Hunyuan3D-2 (cu128 sur Blackwell SM 12.0) + Reinhard rebake + HDRI Poly Haven. Trellis cloné mais bloqué par ABI kaolin/torch.

**Stack code**: standalone Python loop sous `application/python-services/aurora_code/` qui pipe Ollama → CDP screenshot → vision validation. 12/12 success queue grandiose, avg score 0.84.

**Travaux déjà committés en `auroraExpertPrompts.ts`**: specs expert hand-craftées pour 11 modules. Lis ce fichier en premier — il te dit la voix Aurora.

**Loop d'audit déjà en place**: `application/python-services/aurora_uplift/aurora_module_uplift.py`. Re-runnable. Génère `_dev/uplift_proposals/<module>/<basename>.md`. Première passe a produit 9 proposals.

---

## 2. Ce que "expert level" signifie pour CHAQUE module

Pour chaque module, ne te contente pas de "améliore le system prompt". Va aussi loin que ça :

### conversation
- Mémoire long terme: structure RAG (vector store local + re-ranking) ou simple résumé glissant ?
- Gestion des digressions: comment Aurora redirige proprement sans frustrer ?
- Routing implicite vers code/3d/image quand pertinent — détection d'intent par embedding plutôt que keywords ?
- Tone: tutoiement, niveau lycéen sup., pas paternaliste.
- Edge case: utilisateur écrit en franglish, fautes de frappe, message vide, message multi-langue.
- Cache des réponses pour questions identiques récentes.
- Streaming token + indicateur "Aurora réfléchit" sur les longues réponses.

### code
- Sandbox isolation: dockerless? chroot? subprocess + ulimit?
- Multi-pass: génération → critique LLM → patch → re-test (boucle 3x max).
- Detection du "framework requis" par le brief: si user dit "page web" → static, si "todo app" → react+vite, etc. Le classifier actuel est keyword-based, passe en embedding.
- Live preview via CDP avec runtime error capture (déjà fait).
- Auto-save de chaque génération avec snapshot Git.
- Format: code + README + lancement.bat + tests minimaux.
- Test auto: lance le projet généré, vérifie qu'il démarre, screenshot, OK/KO.
- 22+ langages supportés — quels sont les gaps actuels ?

### image
- Prompt engineering FLUX/SDXL: composition + lumière + style + qualifiers.
- Negative prompt approprié par catégorie.
- Pre-processing du brief: extraire sujet/contexte/style/format.
- Upscaling x4 via Real-ESRGAN local si demande "haute résolution".
- Inpainting: si user édite un masque, applique avec ControlNet.
- Variations: générer 4 candidats, picker visuel automatique via qwen3-vl.
- Préserve la palette du brief si user mentionne des couleurs.
- Métadonnées EXIF avec prompt source (pour reproductibilité).

### voice
- TTS: choix automatique de voix par contexte (cours = pédagogique, conversation = naturelle, hype = énergique).
- STT: Whisper local large-v3 + diarisation pour multi-locuteurs.
- Lipsync: phoneme map FR → viseme (pas anglais par défaut).
- Idle talking-head: micro-expressions toutes les 3-5s, blink 250ms.
- Cancel/interrupt: si user parle pendant que TTS joue, fade out + écoute.
- Low-latency: streaming TTS (Sherpa-ONNX ou Piper) pour <500ms time-to-first-audio.
- Persistence: voix favorites par contexte (l'user choisit "Aurora-prof", "Aurora-pote").

### video
- Composition: intro hook 3s, rythme cuts toutes les 8s, outro CTA.
- Talking-head + B-roll auto: pendant que la voix off parle, le module switch sur des scènes 3D ou images générées.
- Sous-titres FR auto-générés via STT + correction LLM.
- Lower-thirds: nom du locuteur, source, timecode visible si pertinent.
- Branding consistent: jingles, fonts, couleurs Aurora.
- Export multi-format: 16:9 cours, 9:16 shorts TikTok/Reels.
- Music ducking sous voix (-18dB side-chain).

### drawing
- Détection automatique du style intent: schéma technique vs croquis artistique.
- Pour schémas: ligne propre, labels typographiés, alignement grille.
- Pour croquis: aquarelle, ink, vector flat — choix selon ton du brief.
- ControlNet edge-detection: l'output respecte la composition exacte du croquis.
- Multi-pass refinement: brouillon → revue automatique → version finale.
- Si user a labellé des zones, garde le texte (pas re-générer aléatoire).
- Export SVG quand vectoriel possible.

### 3d
- Pipeline actuel: FLUX → rembg → Hunyuan3D shape+paint → Reinhard rebake → Blender HDRI render.
- Décimation par catégorie (déjà fait): object 140k, character 180k, vehicle 220k, mech 260k.
- Animations procédurales (déjà fait): rotate, hover, emission_pulse, particles, mechanical_articulate.
- Manque: skeletal rigging auto (Mixamo-like) pour characters/creatures animés vraiment.
- Manque: UV unwrap propre + texture transfer fidèle au prompt (Reinhard ≠ fidélité 100%).
- Manque: LOD generation (2-3 niveaux: 50k, 100k, 200k faces) pour usage web.
- Manque: export multi-format (FBX, USD, glTF avec animations, OBJ avec matlib).
- Manque: validation physique (manifold, no self-intersection, watertight si demandé).

### learning
- Filière de Juan: STI2D/SIN. Le module DOIT connaître le BO officiel.
- Formats multiples (déjà spec): QCM, vrai/faux, ouvert court, schéma à annoter, mini-projet SIN, exercice de programmation.
- Adaptation niveau: 1ère vs Tle, débutant vs avancé, révision vs découverte.
- Spaced repetition: l'algo Anki (SM-2 ou FSRS) pour retours sur cartes.
- Ressources BAC: scraping + cache des sujets officiels par filière/année.
- Génération de fiches: structure cours → exercices → corrigé → synthèse → quiz auto.
- Suivi de progression: courbe d'apprentissage, points faibles détectés.
- Co-création: l'user peut éditer une fiche, le module apprend ses préférences.

### cyber
- DÉFENSIF UNIQUEMENT (déjà spec). Pas d'aide offensive.
- CTF éducatifs: walkthroughs avec le "pourquoi" derrière chaque étape.
- Password analyzer: zxcvbn + suggestions concrètes (longueur, gestionnaire, 2FA, passphrase XKCD).
- Hash identification + crack-strength estimation.
- Crypto: explique ECB cassé, CBC padding oracle, GCM nonce reuse, Argon2 vs bcrypt.
- OSINT défensif: vérifie ta propre surface (have-i-been-pwned, certificate transparency).
- Refus catégorique: phishing templates, malware, ransomware, bypass DRM.
- Sandbox pour expé: dockerless ou VM headless pour tester des hashes/crypto.

### simulator
- Mécanique newtonienne: chute libre, pendule, ressort, choc 1D/2D, collisions élastiques.
- Ondes: corde vibrante, onde plane, interférences, Doppler.
- Fluides: 2D smooth particle hydrodynamics ou grid-based Navier-Stokes simplifié.
- Réactions chimiques: cinétique, équilibre, titrages.
- Optique géométrique: lentilles, miroirs, prismes, dispersion.
- Optique ondulatoire: diffraction Young, réseau, polarisation.
- Électromagnétisme: champs E/B autour de charges/courants.
- Stabilité numérique: RK4 ou Verlet (pas Euler simple), dt adaptatif si raide.
- UI: sliders pour tous params, pause/play/reset, graphes temps réel, units affichées.
- Code commenté avec équations sous-jacentes (// F = ma, // ω² = k/m).
- Export: capture des graphes, données CSV.

### cowork
- Méta-orchestrateur (déjà spec): décompose intention → plan → exécute → ré-oriente sur échec.
- Plan EXPLICITE listé avant exécution.
- Logging transparent: l'user voit la chaîne d'exécution en temps réel.
- Critères de succès par step (fidelityScore >= 0.8, exit 0, HTTP 200).
- Connecteurs externes (déjà fait): GitHub, OpenAI, Slack, Notion, etc.
- Connecteurs machines (déjà fait): localhost, Pi, Linux VPS, SSH générique.
- Connecteurs internes Aurora (déjà fait): aurora_code/3d/image/voice/video/drawing/learning.
- À pousser: confirmation user pour chaines >6 steps, dry-run mode, rollback de plan.
- À pousser: estimation de coût (tokens externes, durée) avant exécution.
- À pousser: persistence des plans favoris ("voici ma routine matinale").

---

## 3. Outils à utiliser

```powershell
# Audit + propose pour 1 module
py application/python-services/aurora_uplift/aurora_module_uplift.py --module <name> --dry-run

# Audit tous modules
py application/python-services/aurora_uplift/aurora_module_uplift.py --all --dry-run

# Re-run (les proposals s'accumulent dans _dev/uplift_proposals/)
```

Pour intégrer une proposal manuellement après review :
1. Lis `_dev/uplift_proposals/<module>/<basename>.md`
2. Identifie le literal cible dans le .ts (par offset)
3. Replace via Edit tool avec escapes corrects (backticks/${}/quotes)
4. `npx tsc --noEmit` doit passer
5. Commit avec message descriptif

Pour le code-loop standalone (test génération end-to-end) :
```powershell
cd application/python-services/aurora_code
py aurora_code_loop.py --prompt "ton prompt" --name slug --max-retries 2
```

Pour le 3D pipeline :
```powershell
cd C:\Users\Juan\Desktop\ia\Hunyuan3D-2
.\venv\Scripts\python.exe aurora_loop.py --prompt "ton prompt" --name slug
```

---

## 4. Méthodologie attendue

Pour CHAQUE module (dans cet ordre de priorité ou parallèle si tu peux) :

1. **Audit profond** : lis les fichiers du module dans `application/src/services/<module>*.ts` ou `services/<module>/`, lis les views `application/src/views/AuroraV*<Module>View.tsx`, lis les hooks `application/src/hooks/use<Module>*.ts`.
2. **Identifie les 5-10 améliorations les plus impactantes** — pas juste les prompts, AUSSI la logique métier, les edge cases non gérés, les opportunités de simplification, les manques de robustesse.
3. **Pour chaque amélioration** : propose un patch concret avec diff style. Si la modification est mécanique et safe, applique-la directement avec garde-fous (tsc, eslint).
4. **Test** : `npx tsc --noEmit` après chaque fichier modifié. Si erreur, rollback ce fichier.
5. **Commit** : un commit par module ou par groupe cohérent, message descriptif (pas "improve module").
6. **Rapport final** : `_dev/expert_uplift_report.md` listant ce qui a été fait par module + ce qui reste pour les sessions suivantes.

---

## 5. Garde-fous

- **NE PAS** casser le build TypeScript. Vérifie après chaque édit.
- **NE PAS** modifier le user-facing tone si c'est juste pour reformuler. Modifie seulement quand ça améliore réellement.
- **NE PAS** introduire de nouvelles dépendances npm sans validation explicite (lourdeur build).
- **NE PAS** toucher aux secrets, .env, tunnel_url.txt, .ssh/.
- **NE PAS** supprimer des features existantes — ajoute, ne soustrais que si redondant.
- **Conserver** la mémoire utilisateur dans `C:\Users\Juan\.claude\projects\C--Users-Juan\memory\` — c'est précieux.
- **Conserver** les artifacts 3D dans `application/output/3d/pbr_*_pack/` et code dans `application/output/code-loop/` (déjà committés).

---

## 6. Critères de succès

À la fin de ta session, tu peux dire "fait" si :

- [ ] Chaque module a été audité en profondeur (pas juste son prompt principal).
- [ ] Au moins 3 améliorations concrètes appliquées par module (ou explicitement justifié pourquoi 0).
- [ ] `npx tsc --noEmit` passe en fin de session.
- [ ] `_dev/expert_uplift_report.md` synthétise ce qui a changé + ce qui reste.
- [ ] Commits propres, un par module ou groupe logique.
- [ ] Tu n'as PAS dit "j'ai fait quelque chose" sans l'avoir vraiment fait (vérifie le diff git avant de commit).

Tu peux faire 1 module à fond et bien plutôt que 11 à moitié.

---

## 7. À éviter (pièges des sessions précédentes)

- Auto-replace de string literals dans les .ts via regex — les escapes des template literals cassent tsc. Préfère ouvrir le fichier dans l'éditeur (Edit tool), appliquer une modif chirurgicale, vérifier tsc, commit.
- LLM auditor trop indulgent ou trop strict — calibre ton prompt critic.
- Génération de 100k+ chars de réponse — fixe `num_predict` raisonnable (8k-15k).
- Vouloir tout faire en 1 session — vise 1 ou 2 modules en profondeur.

---

## 8. Driver prompt à coller dans la nouvelle conversation

```
@HANDOFF_AURORA_EXPERT_UPLIFT.md

Lis ce handoff en premier. Puis choisis 1 ou 2 modules à pousser au niveau expert
profond — pas juste les system prompts mais TOUT (logique, edge cases, perf,
accessibilité, robustesse, UX). Audite, propose, applique avec tsc check,
commit. Tu peux installer des deps si c'est essentiel pour le module. À la fin,
écris _dev/expert_uplift_report.md avec un bilan par module touché.

Priorités suggérées (mais à toi de décider selon ce qui rendra Juan le plus
content): conversation (mémoire long terme + routing), 3d (skeletal rigging),
learning (formats variés + spaced repetition), simulator (numerical stability +
graphes), code (multi-pass critique LLM).

cwd = C:/Users/Juan/Desktop/ia/AuroraIA-v2/
```
