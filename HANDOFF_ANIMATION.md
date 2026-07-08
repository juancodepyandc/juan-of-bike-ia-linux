# AuroraIA — Passation « Animation universelle auto-corrective »

> **But** : qu'une autre IA (Codex, Gemini, session future) reprenne SANS être perdue entre **le vrai app** et **mes
> prototypes scratchpad**. Rédigé le 2026-07-08 par Claude. Compagnon détaillé : `ARCHITECTURE_universelle_anim.md`.
> NB : `HANDOFF.md` (à côté) est le snapshot PROJET auto-généré par `/aurora-handoff` — NE PAS le confondre ni l'écraser.

---

## 1. LE BUT (vision de Juan)

AuroraIA = appli 100 % **locale** (RTX 5070 Ti 16 Go) qui, **à partir d'un prompt**, génère un asset 3D **et l'anime**
avec **fidélité parfaite**, **en autonomie totale** (l'IA détecte et répare ses défauts elle-même). Exigences :
- **N'IMPORTE QUELLE morphologie** : humanoïde (mains à phalanges, bouche, yeux), **robot rigide** (Goldorak :
  armure qui NE se déforme PAS), **créature non-standard** (Caine de Digital Circus : visage = **écran**, gants
  flottants sans bras), **objet non-personnage** (RAM : si pas personnifiée → PAS de squelette, juste la **LED /
  lumière / gaz / flux** qui s'anime).
- **Détecter le type → appliquer la BONNE stratégie** (hardcoder « attraper un objet » universellement est faux).
- **Auto-correction en boucle fermée** : mesurer ses imprécisions, chercher le correctif, reboucler jusqu'à convergence.
- **Batteries de tests** sur cas durs (Caine, Goldorak, RAM). **Qualité > temps.** OK plus lent / meilleurs modèles / offload.

---

## 2. ⚠️ ÉTAT RÉEL DE L'APP (à RÉUTILISER — ne pas réinventer)

Pipeline prod : **`/home/juan/AuroraIA/application/python-services/`** + un **`.venv`** (scipy 1.18, sklearn 1.9,
trimesh 4.12, networkx 3.6, numpy 2.4). C'est **AuroraIA-v2**, déjà mûr, local et semi-type-aware :

| Module | Rôle réel (vérifié à la lecture) |
|---|---|
| `aurora_3d_pipeline.py` | **Orchestrateur** (prompt → asset → rig → mouvement → bake). |
| `motion_intent_classifier.py` | Classe le prompt via **Ollama LOCAL** (gemma3:12b / qwen3:14b) en **6 catégories** : `led_emission`, `fan_pwm`, `oled_screen`, `creature_organic`(+locomotion), `mechanical_simple`, `rigid_static`. → gère DÉJÀ RAM, ventilo, écran, objet inerte. |
| `anim_metrics.py` (1206 l.) | **Métriques objectives type-dispatchées** = LE module de mesure. Familles `luminous / screen / humanoid / creature / mecha_rigid`. Métriques : `m_edge_stretch`(déchirure), `m_foot_ground`, `m_heel_toe_roll`, `m_contralateral_arm_swing`, `m_head_carriage`, `m_self_intersection`, `m_hand_flexion`, `m_finger_spread`, `m_part_rigidity`, `m_plate_interpenetration`, `m_screen_face_coherence`… `evaluate(take, family)` lance la famille et **renvoie des knobs classés** (= hooks d'auto-correction). Entrée = dict `take` (verts déformés/frame, edges, part_labels, joints, finger_chains, emission, screen_features…). |
| `rigify_autorig.py` | Auto-rig **Rigify** (metarig humain), **SANS doigts** par défaut. |
| `motion_baker.py`, `motion_parser.py`, `motion_intent_baker.py`, `glb_animation_injector.py` | **Mouvement par PRESETS** (≈45 presets : character.climb, creature.roar, mechanism.vibrate…) + parser + bake dans le GLB. (Approche DIFFÉRENTE de mon text-to-motion génératif.) Testés : motion_baker 13 cas, motion_parser 17 cas, parité TS↔Python 42 fixtures. |
| `proc_*.py` (refrigerator, origami, uluru) | Animations **procédurales** (cas non-personnage déjà scriptés). |
| `bake_oled_screen.py` + bakers | **Écran OLED** (= visage de Caine), normal map, textures, vertex colors. |
| `openpose_skeleton.py`, `flux_reference_synth.py` | Génération perso. `blender_bridge.py`, `aurora_3d_mcp.py` = pont Blender / MCP. |

→ L'app a DÉJÀ : classification d'intention (Ollama) + métriques type-dispatchées + presets de mouvement + procédural
+ 38 agents + self-test 33 gates. Voir `HANDOFF.md` (auto-généré) pour l'état projet global.

---

## 3. MES PROTOTYPES SCRATCHPAD (R&D parallèle — NE PAS confondre avec l'app)

Session passée **hors app**, dans `/tmp/claude-1000/.../scratchpad/` + `/home/juan/.local/share/auroraia/external/`,
à prototyper la chaîne HUMANOÏDE générative. Ce sont des **idées prouvées à rapatrier**, pas du code à brancher tel quel :

| Prototype | Ce qu'il PROUVE | À faire dans l'app |
|---|---|---|
| **Make-It-Animatable** (env conda `mia`) | Rig Mixamo **avec 30 os de DOIGTS** — > Rigify (sans doigts) quand `has_phalanges`. | Activer fingers-rig Rigify conditionnel, ou brancher MIA. |
| `rigkit.py::weld_mesh` | Mesh TRELLIS = soupe de ~38k fragments → géo fine explose. **Souder (remove_doubles) AVANT skinning** (718k→460k). | Étape soudage post-TRELLIS. |
| `auto_correct.py` (boucle) | **Boucle d'auto-correction prouvée** : écharpe déchirée = **étirement d'arête p99** (3.26→1.59 via lissage Laplacien auto) ; flottement = ancrage pied/frame (0.16→0.06) ; mesure sur maillage déformé, sans œil. | ≈ `anim_metrics.evaluate` + knobs. **Fusionner** : mes correctifs = knobs de anim_metrics. |
| `motion_metrics.py` | Curation : générer N marches, scorer (bras baissés, pieds ancrés, rebond), garder la meilleure. | ≈ « bouton mouvement » + gate anim_metrics. |
| `verify_anim.js` (workflow) | **Audit VISION multi-agent** (10 agents / membre + cohérence) — attrape ce que la géométrie rate (a rejeté ma « griffe » de main). | Garder comme couche d'audit LLM au-dessus des métriques (boucle ACLA). |

**Assets** : rig testé `external/UniRig/results/natsu_MIA_tpose_native.glb` ; mouvement `external/MotionStreamer/demo_output/mstream_best.bvh`.

---

## 4. CE QUI MANQUE (travail à faire) — détail dans `ARCHITECTURE_universelle_anim.md`

1. **`morphology.py` (À CRÉER)** : classifieur **géométrique** (features scipy/sklearn : symétrie cKDTree, composantes,
   pointes FPS géodésique, planéité PCA écran, matériau émissif) qui **confirme/corrige** le prior Ollama. Schéma
   `aurora.morphology.v2` : 8 `class` + axes `body_plan`/`deformation` + flags (`face_is_screen`, `has_phalanges`,
   `composite`…) + `parts[]`. **Tourne APRÈS soudage**.
2. **BUG à corriger dans `anim_metrics.family_for_intent`** : route sur `intent.category` (le prompt). Goldorak classé
   `creature_organic+humanoid` → famille `humanoid` → lissage → **armure qui fond**. Fix : router en priorité sur
   `morphology.deformation` (`rigid_segments`→`mecha_rigid`).
3. **Table de ROUTAGE `class → {rig, baker, famille métrique}`** (dans `morphology.py`) = maillon central absent.
4. **Boucle fermée ACLA** : `render → anim_metrics (géométrique) + audit vision LLM → agent stratège choisit le knob
   → ré-applique → re-mesure`, arrêt sur seuils + anti-régression.
5. **Doigts** (fingers-rig conditionnel), **visage géométrique** (blendshapes, en plus de bake_oled_screen),
   **chaînes ailes/queue** (WINGED).
6. **Extensions d'enums** : motion-intent += `mecha_rigid_articulated`, `composite`, `soft_body` ; loco += `flight|hover|swim`.
   `composite` = liste (part, sous-intent) → Caine, voiture…

**3 PROCHAINES ACTIONS** : (a) figer les contrats §0 de l'archi ; (b) coder `morphology.py` + corriger
`family_for_intent` ; (c) monter la batterie Goldorak/Caine/RAM et mesurer avant/après avec `anim_metrics`.

---

## 5. RÉSULTAT ACTUEL (prototype humanoïde)

`natsu_AUTOCORRECT_walk.mp4` (Cycles, 101 frames) : Natsu marche, écharpe qui drape, pieds plantés, corps propre.
Gains via la boucle (audit vision) : **écharpe 9/9→3/9 cassée**, bras lisibles, **note membres 3,0→4,4**. Reste :
**mains** (rotation uniforme des doigts = griffe → il faut IK/pose par doigt) et **démarche** un peu mécanique.

---

## 6. GOTCHAS (coûteux à re-trouver ; voir aussi mémoire `pipeline-deformation-3d.md`)

- Mesh TRELLIS = fragments → **SOUDER avant skinning**.
- Géo fine (écharpe) se **déchire sur place** : la **bbox le rate**, l'**étirement d'arête p99 le voit** (= `m_edge_stretch`).
  Correctif = lissage Laplacien lourd des poids en zone haute.
- FBX→GLB : **FBX2glTF natif**, pas roundtrip Blender (déchiquette + retourne 180°).
- Retarget : **échelle armature = 1** requise ; GLB natif déjà à 1 → NE PAS transform_apply (casse le bind → explosion).
- Flottement : ancrage **pied bas par frame** + foot_lock IK.
- Text-to-motion très variable → **curer** (générer N, scorer, garder le meilleur). (L'app, elle, utilise des PRESETS.)
- **Audit vision LLM** attrape ce que la géométrie rate (ma métrique « doigts près paume » a fait une griffe).
- **Classer par prompt seul = risqué** (Goldorak « humanoïde » → armure molle) → **vérifier la géométrie**.

---

## 7. OÙ EST QUOI

- App prod : `application/python-services/` (+ `.venv`). Snapshot projet : `HANDOFF.md` (auto-généré).
- Archi cible : `ARCHITECTURE_universelle_anim.md`. Mémoire technique : `~/.claude/projects/-home-juan/memory/pipeline-deformation-3d.md`.
- Prototypes R&D : `/tmp/claude-1000/-home-juan/2484249d-3529-4b29-8c7d-a8b8cc99dbef/scratchpad/` + `~/.local/share/auroraia/external/`.
- Rendus/mp4 : `application/../modele/comfyui/output/trellis_tests/`. Envs conda : `~/.local/opt/miniforge3/envs/` (mia, mstream, momask, trellis2, unirig).

## 8. RÈGLE D'OR
Travailler **DANS l'app** (réutiliser `anim_metrics`, `motion_intent_classifier`, les bakers/presets), n'y rapatrier
que les **idées prouvées** du scratchpad, **tester** chaque nouveauté sur la batterie (Goldorak/Caine/RAM), mesurer
avant/après avec `anim_metrics`. Ne jamais « se contenter du facile pour dire c'est bon ».
