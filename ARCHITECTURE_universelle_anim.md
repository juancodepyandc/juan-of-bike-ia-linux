All claims verified against real code. I have complete grounding. Here is the synthesis.

---

# AuroraIA — ARCHITECTURE MAÎTRE : Animation universelle, type-aware, auto-corrective

**Document de référence d'implémentation.** Statut réel du disque (vérifié) : seuls `anim_metrics.py` + `test_anim_metrics.py` existent parmi les modules d'animation ; `motion_metrics.py`, `auto_correct.py`, `verify_anim.js`, `rigkit.py`, `morphology_classifier.py` sont **fictifs** (le brief les présente comme acquis — ils ne le sont pas). Libs réellement dispo dans `application/.venv` : **scipy 1.18, sklearn 1.9, networkx 3.6, numpy 2.4, trimesh 4.12** — utilisez-les. Le rig réel = **Rigify** (`armature_human_metarig_add()` inconditionnel, **sans doigts**), pas MIA. Les catégories réelles = les **6** de `motion_intent_classifier.py`. Ce document résout d'abord les ruptures de contrat inter-modules, puis livre les 6 sections demandées.

---

## SECTION 0 — LES CONTRATS FONDATEURS (à figer avant tout code)

La critique a prouvé que les 6 facettes ne se branchent pas : 3 enums de `class` sous un même nom de schéma, aucune `class` consommée par un baker, métriques aux noms inexistants, catégories manquantes pour Goldorak/Caine. **On fige 4 contrats. Rien d'autre ne doit être codé avant.**

### 0.1 — UN seul module, UN seul enum de morphologie

Fichier unique : `/home/juan/AuroraIA/application/python-services/morphology.py`, schéma `aurora.morphology.v2` (v2 pour tuer les 3 v1 concurrents). **Interdiction** de recréer `morphology_profile.py` / `morphology_classifier.py` séparés : un seul module, importé par la boucle et le bouton mouvement.

`class` (= stratégie de rig) ∈ **8 valeurs finales** :
```
HUMANOID_BIPED · QUADRUPED · WINGED_FLYER · ROBOT_RIGID_MECH
CREATURE_NONSTANDARD · MECHANISM_ARTICULATED · SOFT_OBJECT · OBJECT_INERT
```
Deux axes **orthogonaux** portent le détail (modèle de CLASSIFIEUR, retenu) :
- `body_plan` ∈ `biped | quadruped | winged | serpent | radial | multiped | amorphous | none`
- `deformation` ∈ `soft_skin | rigid_segments | screen_texture | emissive_only | procedural_sim | none`

Plus les switches : `is_character`, `personify`, `sub_flags{face_is_screen, floating_appendages, detached_hands, has_phalanges, composite}`, `confidence`, `escalate_vlm`, `parts[]` (chaque partie taggée → c'est ce qui aligne métriques et défauts vision).

### 0.2 — Étendre `motion-intent.v1` (le canal downstream manquant)

Les `class` ROBOT_RIGID_MECH / WINGED_FLYER / composite **n'ont aucun canal** pour descendre : le baker ne connaît que 6 catégories. On étend l'enum de `motion_intent_classifier.py` :
```
AJOUTS : mecha_rigid_articulated · composite · soft_body
locomotion += flight | hover | swim | radial_crawl
```
`composite` porte une liste `sub_intents[]` = (part_label, motion-intent classique). Caine = `composite[(body,hover),(face,oled_screen),(gloves,rigid_float)]`. Voiture = `composite[(wheels,fan_pwm),(body,translate),(chassis,rigid_static)]`. **Le mono-label est mort** ; le composite est le mécanisme générique.

### 0.3 — LA TABLE DE ROUTAGE `class → {baker, rig, famille métrique}` (le maillon central absent)

C'est le module que **personne n'avait écrit** et sans lequel tout s'arrête au bord du baker. À coder dans `morphology.py::ROUTING`.

| `class` | motion-intent émis | Recette RIG | Déformation | Famille métrique (`anim_metrics`) |
|---|---|---|---|---|
| HUMANOID_BIPED | creature_organic / loco=humanoid | Rigify humain **+ fingers rig activé** (voir 0.5) | soft_skin | `humanoid` |
| QUADRUPED | creature_organic / loco=quadruped | `_rigify_creature_skeleton` quadruped | soft_skin | `creature` |
| WINGED_FLYER | creature_organic / loco=flight | quadruped/humanoïde **+ chaînes ailes+queue** (À CODER) | soft_skin (+longeron rigide) | `creature` |
| ROBOT_RIGID_MECH | **mecha_rigid_articulated** | plaques→os 0/1 + **hiérarchie de joints** (À CODER) | **rigid_segments** | **`mecha_rigid`** |
| CREATURE_NONSTANDARD | **composite** | hybride par partie | screen_texture + rigid + soft | `creature` **+ `add_screen`** |
| MECHANISM_ARTICULATED | **composite** (multi-DoF) | hiérarchie cinématique N-joints | rigid_segments | `mecha_rigid` |
| SOFT_OBJECT | **soft_body** | **pas de squelette**, wind/cloth modifier | **procedural_sim** | `creature` (edge_stretch tol. haute) |
| OBJECT_INERT | led_emission / oled / fan_pwm / rigid_static | **aucun rig** | emissive_only / none | `luminous` / `screen` / `mecha_rigid` |

**Corrige le bug 3.1 de la critique** : la famille métrique vient de `class`/`deformation`, **JAMAIS** de `motion-intent.category`. Un Goldorak qui marche est `creature_organic+humanoid` côté intent MAIS `class=ROBOT_RIGID_MECH` → famille `mecha_rigid`. Il faut donc **modifier `anim_metrics.family_for_intent`** pour accepter en priorité `morphology.deformation` (le dispatch actuel enverrait l'armure en `humanoid` → lissage Laplacien → fonte).

### 0.4 — Figer `anim_metrics.py` comme LE module de métriques

`motion_metrics.py` / `deform_metrics.py` n'existent pas. `anim_metrics.py` existe, 17 métriques, 5 familles, testé. **On l'adopte comme unique module.** Toute référence de MOUVEMENT à `frac_planted`/`wrists_down`/`foot_corr` est réécrite sur les vrais noms : `m_foot_ground`, `m_heel_toe_roll`, `m_contralateral_arm_swing`, etc. Le gate post-vol du bouton mouvement appelle `anim_metrics.evaluate(take, family)`.

### 0.5 — Trancher doigts + visage (sinon 4 facettes mesurent du vide)

Réalité : `rigify_autorig.py:101` = metarig humain **sans** sous-rig doigts. Toute la logique `finger_spread`/`hand_flexion`/`grab()`/« la griffe » de BOUCLE porte sur des os inexistants. **Décision de référence :**
- **Doigts** : activer le **fingers rig de Rigify** (`palm`+`fingers`) conditionnellement à `sub_flags.has_phalanges` (détecté, jamais par défaut). Réintégrer MIA plus tard si la qualité doigts l'exige — non bloquant. Sans phalanges détectées → **0 os de doigts**, `grab()` → contact-paume ou refus honnête.
- **Visage** : deux chemins mutuellement exclusifs décidés par géométrie-vs-texture (planéité PCA + matériau émissif + features 2D absentes du relief 3D) : **écran** → flipbook UV (`bake_oled_screen`, existe) ; **géométrique** → face-bones/blendshapes Rigify (À CODER, manque du chemin principal, pas juste Caine).

---

## SECTION 1 — TAXONOMIE + PROCÉDURE DE CLASSIFICATION

### 1.1 Position dans le pipeline
`texte → FLUX → TRELLIS → SOUDAGE remove_doubles → [morphology.classify] → rig → bouton mouvement → boucle`. Tourne **après soudage** (sinon la soupe de 38k fragments fausse `n_comp`) sur une copie décimée 20–40k faces. **Attention prémisse 3.6** : après soudage TRELLIS `n_comp=1` → le signal « plaques = îlots » de Goldorak s'effondre → la segmentation Goldorak doit reposer sur l'**angle dièdre**, pas sur les composantes.

### 1.2 Fusion prior/géométrie
- **Prior (prompt, réutilisé)** : `extract_kind` + `motion_intent_classifier` + `detect_facets`. Le prompt ment → prior **secondaire**.
- **Évidence (géométrie)** : features F1–F15 ci-dessous, en **scipy/sklearn** (cKDTree pour Chamfer/symétrie O(N log N) au lieu du O(N²) hand-rolled ; `connected_components` ; `KMeans` ; FPS géodésique pour les pointes).
- **Fusion** : géométrie renverse le prior quand elle est franche ; sinon le prior tranche ; zone grise → VLM.

### 1.3 Features (scipy/sklearn/numpy/trimesh/bmesh)

| # | Feature | Outil | Discrimine |
|---|---|---|---|
| F1 | aspect bbox `a_tall,a_flat` | numpy | tall/long/plat |
| F2 | PCA inertie `lin,plan,sph` | numpy eigh | barre/disque/boule |
| F3 | symétrie bilat. `sym_bi` | **cKDTree** Chamfer | personnage/robot |
| F4 | symétrie rot. `sym_rot,k_rot` | cKDTree | radial → objet/ventilo |
| F5 | composantes `n_comp,n_comp_big` | **csgraph.connected_components** | Caine gants / robot |
| F6 | pointes membres `n_tips`+hauteur | **FPS géodésique** | **LE discriminant** : biped 5, quad 6, ailé +2 |
| F7 | appuis sol `n_feet,support_area` | **sklearn KMeans** 2D | biped 2 / quad 4 / objet 1 / flottant 0 |
| F8 | arêtes vives `sharp_ratio,dihedral_bimod,n_panels` | bmesh dièdre | méca rigide vs organique |
| F9 | continuité courbure `curv_smooth` | bmesh | organique vs hard-surface |
| F10 | émission `emis_frac,emis_striplike` | lecteur GLB | RAM LED |
| F11 | visage-écran `screen_score` | patch plan émissif + `_find_screen_materials` | Caine/OLED |
| F12 | doigts `digit_count` | protubérances multiples | mains (gate fingers rig) |
| F13 | matériaux `metallic,rough,hard_surface` | PBR GLB | métal robot |
| F14 | flottement `floating,detached_lower` | gap vertical composantes | Caine |
| F15 | graphe squelette (si rig tenté) | networkx | confirmation forte |

Invariantes échelle/translation ; F3/F6 invariantes rotation via alignement PCA.

### 1.4 Deux switches (répondent à la condition RAM de Juan)
- **`personify_hint`** (prompt, prioritaire) : `True` si verbe animé OU `kind∈{humanoid,character,creature,quadruped}` OU intent `creature_organic` OU identité nommée. `False` si intent inerte ET aucun verbe animé ET kind objet. **Corrige 3.3/3.4** : `personify_hint=True` **FORCE** la branche personnage même à `character_score≈0` (théière-mascotte sans membres) ; et ajouter le kind **`memory_module`** à `subject_kind_extractor` (absent → cas phare RAM instable).
- **`character_score`** (géométrie 0..1) = `sym_bi>0.80`(.25)+`n_tips≥3` allongés(.30)+`n_feet∈{2,4}`(.20)+blob-tête haut(.15)+squelette F15(.10).

### 1.5 Arbre de décision ORDONNÉ (premier match gagne)

```
G0  personify_hint=True (override prompt)  ──────────────► branche PERSONNAGE (skip G1)
G1  OBJET  : personify_hint=False ET character_score<0.45
      ├ emis_striplike / led_emission ─► OBJECT_INERT, emissive_only  ← RAM RGB
      ├ sym_rot élevé k≥3 (fan_pwm)   ─► OBJECT_INERT, rotation axe
      ├ oled_screen                   ─► OBJECT_INERT, screen flipbook
      ├ surface fine ouverte, drapeau/cape/fluide ─► SOFT_OBJECT, procedural_sim  ← trou 2.1 comblé
      ├ N joints (grue, bras robot, ciseaux)      ─► MECHANISM_ARTICULATED  ← trou 2.2
      ├ mechanical_simple 1-DoF       ─► MECHANISM_ARTICULATED (1 joint)
      └ sinon                         ─► OBJECT_INERT, none  ← RAM sans RGB
G2  ROBOT RIGIDE (Goldorak) : body-plan perso ET sharp_ratio>0.35 ET dihedral_bimod(~90°)
      ET (metallic>0.5 OU curv bas)   ─► ROBOT_RIGID_MECH, rigid_segments  [AVANT G5/G6 sinon peau molle]
G3  VISAGE-ÉCRAN / FLOTTANT (Caine) : screen_score haut OU (floating ET detached_lower en layout perso)
                                      ─► CREATURE_NONSTANDARD, composite{face_screen,detached_hands,hover}
G4  AILÉ : body-plan perso + 2 appendices latéraux hauts fins EN SURPLUS des bras/jambes
                                      ─► WINGED_FLYER
G5  QUADRUPÈDE : n_feet≈4 OU (n_tips≈6 + épine horizontale) ET sym_bi>0.80 ─► QUADRUPED
G6  HUMANOÏDE : n_feet≈2 + a_tall haut + sym_bi>0.85 + blob-tête + 2 bras ─► HUMANOID_BIPED
G7  CRÉATURE NON-STD (fallback perso) : serpent(lin↑,1 chaîne) / radial(étoile,pieuvre) /
      hybride(sirène,centaure) / blob                         ─► CREATURE_NONSTANDARD
G8  OBJET (fallback final)                                    ─► OBJECT_INERT
```
**Corrige 2.4** : radial vivant (étoile de mer posée) — ne router `sym_rot→objet` QUE si `personify_hint=False` ; sinon `body_plan=radial` en G7.

---

## SECTION 2 — MATRICE STRATÉGIE (type → rig · mouvement · métriques · correctifs)

| Type | RIG | MOUVEMENT (source) | MÉTRIQUES actives (`anim_metrics`) | DÉSACTIVÉ | KNOBS de correction |
|---|---|---|---|---|---|
| **HUMANOID_BIPED** | Rigify + fingers (si has_phalanges) + poids lissés | `generate` MoMask + curation (N=8, score joints) → joints2bvh → retarget_bvh → foot_lock | edge_stretch, foot_ground, heel_toe_roll, contralateral_arm_swing, head_carriage, self_intersection, hand_flexion, finger_spread | — | weight_smooth_iters, foot_ik_lock, root_offset, arm_swing_amp, finger_curl_gradation |
| **QUADRUPED** | `_rigify_creature_skeleton` quad + queue | `procedural` gait 4-appuis diagonal (aucun générateur SMPL) | edge_stretch, foot_ground(×4), floating_part_stability(queue) | finger_spread | footfall_phase, ik_plant, tail_amp |
| **WINGED_FLYER** | quad/humain **+ chaînes ailes+queue (À CODER)** | `procedural` flap+glide+bob | edge_stretch, flap périodicité, membrane strain>0 vs longeron rigide | foot_ground (vol) | flap_amp/freq, glide_speed, wing_phase_delay |
| **ROBOT_RIGID_MECH** | plaques→os poids **0/1**, hiérarchie joints, **PAS de Laplacien** | `generate` MoMask SI biped **mais retarget rotation_only** ; vol=keyframe | **part_rigidity** (Kabsch résidu≈0), plate_interpenetration, joint_coherence | **edge_stretch lissé, foot_ground(vol), finger_spread, Laplacien** | max_bone_influences=1, joint_gap, mechanical_stop_limit, pivot_lock |
| **CREATURE_NONSTANDARD (Caine)** | hybride : corps hover bas-DoF + visage flipbook UV + gants transforms rigides détachées | `composite` : float sinus + face oled + gants bob indépendants | float_part_stability, **screen_face_coherence** (`add_screen=True`), edge_stretch(corps) | **foot_ground, finger_spread, arm_IK, foot_lock** | float_damping, tether_stiffness, screen_uv_clamp, blink_min_interval |
| **MECHANISM_ARTICULATED** | hiérarchie cinématique N-joints (fix mesh_part_split) | `hardcode_ik`/procedural multi-DoF | part_rigidity, joint_coherence, plate_interpenetration | déformation molle | joint_limits, dof_axes |
| **SOFT_OBJECT (drapeau, cape, fluide)** | **aucun squelette** ; wind/cloth modifier Blender | `procedural_sim` | temporal_smoothness, edge_stretch (tol. HAUTE, la déformation est voulue) | tout le rig, foot_ground | wind_strength, stiffness, damping |
| **OBJECT_INERT — RAM LED** | **aucun rig** | `shader` : fcurve émission (chase/rainbow/breathing/pulse) | temporal_smoothness, pulsation_coherence, flicker, emission_dynamic_range | tout rig/déformation | emission_smoothing_frames, pulse_period_lock, min_dwell_frames |
| **OBJECT_INERT — RAM statique** | aucun | `static` : rien | acceptance gate seul (géométrie inchangée) | tout | — |

**Politique hardcode vs generate (point exact de Juan)** : GÉNÉRER = locomotion corporelle pleine sur biped **vérifié** (MoMask couvre HumanML3D). HARDCODER = (a) morphologie non couverte par un générateur (quad/ailé/serpent/méca/flottant), (b) action goal-directed vers une cible précise (grab/point/press → IK, pas échantillonnage), (c) mécanique déterministe. **Tout hardcode est PARAMÉTRÉ par l'anatomie détectée** : `grab(rig,target)` détecte les phalanges (jamais n'invente), courbe chaque doigt réellement présent avec `angle=f(taille_objet)` ; pas de phalanges → contact-paume ou `Unsupported`. **Jamais de faux mouvement** : capacité absente → `status="action_unsupported_for_morphology"`.

---

## SECTION 3 — BOUCLE FERMÉE AUTONOME (ACLA)

**Principe** : la boucle est **paramétrée par le profil morphologie**, jamais universelle. Les 3 correctifs codés en dur (écharpe/flottement/mains) deviennent des **instances** du patron `Détecteur → Défaut → Knobs candidats → Stratège choisit → applique → re-mesure`.

**Two-tier** : proxy géométrique cheap (mesuré chaque itération, sans rendu) + arbitre vision premium (audit 10 agents, sparse). `metric_trust` est le pont qui empêche le proxy de dériver de la vérité vision.

```
┌───────────────── correction_loop.py (aurora.correction_run.v1) ─────────────────┐
│ knobs = defaults(profile.knobs) ; trust = MetricTrust.load(class) ; best=None    │
│ pour step in budget.max_steps:                                                   │
│   (A) deformed = bake_deformation(rig, motion, knobs)   # Blender headless, 0 rendu │
│   (B) geo = anim_metrics.evaluate(deformed, family, add_screen)   # INNER cheap  │
│       composite = Σ trust.weight[m]·severity(geo[m], trust.objective[m])         │
│   (C) if score.better(best): best=checkpoint(knobs,geo,vis); stale=0  else stale++ │  ← KEEP-BEST
│   (D) if should_audit(step,geo,stale):                                            │
│         frames = render_preview(key_frames(geo))                                 │
│         vis = vision_audit(frames, profile.parts)   # verify_anim.js, 10 agents  │
│         trust = reconcile_and_learn(geo, vis, history, trust)   # ← APPREND      │
│         if vis.rollback: knobs = best_before_offending(history,vis).knobs; continue │
│   (E) if stop(profile,geo,vis,stale,budget): break                               │
│   (F) plan = strategist(geo,vis,knobs,trust,history)   # agent LLM décide        │
│       knobs = knobs.apply(plan.deltas)   # bornes knob_registry + guards trust   │
│ return best   # JAMAIS le dernier — toujours le meilleur checkpoint              │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**Les 4 quadrants géo↔vision (par partie)** :

| géo | vision | action |
|---|---|---|
| OK | OK | accepter, arrêter |
| DÉFAUT | DÉFAUT | stratège corrige, promote détecteur |
| **OK** | **DÉFAUT** | **la griffe** : credit-assignment → demote(×0.5) + retarget `MINIMIZE→TARGET_BAND(dernière valeur approuvée vision)` + rollback |
| DÉFAUT | OK | fausse alarme → relax (bande×1.5, poids×0.8) |
| ∅ | DÉFAUT | `detector_gap` → candidat nouveau détecteur (+ fixture obligatoire) |

**« La griffe » (récit fondateur — MAIS voir 0.5)** : `finger_spread` avec objectif `MINIMIZE` sur-courbe les doigts → vision rejette → système convertit en `TARGET_BAND`. **Ce récit exige que les os de doigts existent** ; il n'est valide qu'après activation du fingers rig (0.5). Tant que non fait, la griffe canonique de démonstration est `finger_spread` **désactivé**, et on démontre l'apprentissage sur une métrique qui existe (ex. `head_carriage` sur-corrigé).

**Arrêt** : `goals_met AND vision_ok` → succès ; `stale≥patience AND not open_critical` → plateau ; `budget.exhausted`. **Anti-régression** : retour du checkpoint, un reroute ne remplace qu'un plan qui a **échoué** un gate.

**État terminal sûr (corrige 3.2 — autonomie totale ⇒ interdit d'inventer)** : si VLM abstient aussi (`<0.70`) → **`OBJECT_INERT` statique + rapport de basse confiance journalisé**. Ne rien animer > animer faux. Codifié comme état terminal explicite.

---

## SECTION 4 — LE « BOUTON MOUVEMENT » + check de compatibilité

`plan_and_apply_movement(asset, morpho_class, prompt) -> MovementResult`, schéma `aurora.movement-plan.v1` enveloppant `motion-intent` (bit-compatible → 0 régression du baker). Deux axes orthogonaux : **A. source** (`generate|procedural|hardcode_ik|shader|static`) que le bouton décide ; **B. mode déformation** (contrainte passée au RIG).

**Le gate de compatibilité (cœur — réponse directe à Juan) — deux étages :**

**4.1 Pré-vol structurel** — « ce rig est-il un vrai bipède SMPL-mappable ? » (avant toute génération, quasi gratuit)
```
biped_fit(rig): legs = chaînes symétriques atteignant z_min (hip→knee→ankle, depth≥3)
                arms = chaînes symétriques depuis épaules ; upright = axe dominant vertical
  2 jambes + tronc vertical + rôles jambes couverts → PASS  → generate autorisé
  jambes absentes/asymétriques (Caine)              → REROUTE procedural hover (MoMask non tenté)
  rig rigide segmenté (Goldorak)                    → PASS mais force rigid_plates + rotation_only
  aucun rig (RAM)                                   → REJECT génération corporelle → shader
```
**Corrige 1.4** (le fallback regex ne produit ni hover ni vol ni robot) : **ajouter au `_regex_fallback`** les verbes `fly|vole|voler|plane|hover|flotte|float|swim|nage` → `base_loop=hover/flight`, et la reconnaissance `robot|mecha|armor|android|goldorak` → régime rigide. Sinon « Goldorak vole » → `rigid_static` = zéro mouvement dans le chemin déterministe, et le socle reproductible des TESTS est faux.

**4.2 Post-vol comportemental** — « le retarget a-t-il produit un mouvement valide ? » (avant la boucle coûteuse)
```
retarget_valid(take, family): via anim_metrics.evaluate — NOMS RÉELS :
  planted     = m_foot_ground.pass      wrists_down = pas resté en T-pose
  alternation = m_contralateral...      no_explosion = bbox_ratio ≤ 1.25 (auto_correct)
                edge_stretch p99 < 1.60
  échec → re-générer (autre candidat) ; N épuisés → REROUTE ; jamais lancer la boucle sur un mvt pourri
```
Ce double étage rattrape le faux-positif « rig MIA bruité trouve 2 jambes sur un non-humanoïde » (le structurel seul ne suffit pas).

**Capability probe** : anatomie détectée → verbes disponibles. `walk/run/jump←biped_legs` ; `grab/point/wave←has_phalanges` ; `fly/flap←wings` ; `talk/blink←screen_face` ; `glow/pulse←emissive`. Capacité absente → échec honnête.

---

## SECTION 5 — BATTERIE DE TESTS

**3 paliers.** Tier 0/1 bit-reproductibles (CI chaque commit) ; Tier 2 seedé + tolérance (nightly GPU). Score 0-10 : `10·Σwᵢsᵢ`, invariants P0 ~40% (un P0 échoué → **plafond ≤4** quelle que soit la beauté), qualité 40% (`engineer_grade`), motion 20%.

| Cas | class attendue | Casse | PASS/FAIL P0 (champs réels) |
|---|---|---|---|
| **RAM-LED** | OBJECT_INERT/emissive_only | A1 (tout≠squelette), A8 | `bone_count==0`, `has_limb_targets==False`, `has_runtime_motion_extras==True`, émission min≠max fcurve continue |
| **RAM-statique** | OBJECT_INERT/none | A1 | `has_animations==False`, `accepted==True` |
| **RAM-perso** (contraste) | CREATURE_NONSTANDARD | prouve non-hardcodé | rig produit, `has_articulated_locomotion==True` |
| **QUADRUPÈDE loup** | QUADRUPED | A2 (biped), A3 (2 appuis) | `locomotion=="quadruped"`, ≥4 cibles pied, `root_only==False`, aspect_l1 petit en `quadruped` GRAND en `humanoid` |
| **GOLDORAK** | ROBOT_RIGID_MECH | A4 (peau molle)!, A3 (vol) | `part_rigidity`: strain intra-plaque p99 |1−s|<0.02 ; **Laplacien PAS lancé (assert chemin)** ; foot_ground supprimé en vol ; `finger_bone_count≤6` |
| **CAINE** | CREATURE_NONSTANDARD/composite | A6 (visage=géo), A2 (bras), A3, mono-label | `base_loop==hover`, anim écran présente + **zéro os facial** dans target_names, foot_ground supprimé, gants = nœuds séparés non skinnés à bras fantôme |
| **DRAGON ailé** | WINGED_FLYER | A2 (ailes+queue), taxonomie loco | rig couvre ailes(≥2)+queue(≥1) EN PLUS pattes, flap périodique, foot_lock OFF, membrane strain>0 vs longeron rigide |

**Tests supplémentaires révélés par la critique (taxonomie, pas juste les 5 attendus)** : SOFT_OBJECT (drapeau/cape/vent → `procedural_sim`, pas `rigid_static`), MECHANISM_ARTICULATED (grue multi-joint), composite-objet (voiture roues+corps), radial vivant (étoile de mer → pas objet), visage géométrique (« humain parle » → face-bones), prop émissif mobile (sabre laser = translation+émissif).

**Tier 1 déterministe (sans GPU)** : GLB synthétiques trimesh encodant la structure. Ex. GOLDORAK = 2 boîtes rigidement pesées 1 os → rotation joint → assert `per_plate_strain_p99≈0` ; fixture « mauvaise » poids lissés → assert `strain>seuil` (teste « désactiver Laplacien » sans GPU). Refactorer la suppression flottement en **fonction pure** `float_defect(min_foot_height, locomotion) → bool` : FIRE en walk, SUPPRIMÉE en hover/flight.

**Test d'intégration le plus important (manquant partout)** : asserter que `morphology.class` **ATTEINT un baker** via `ROUTING` (0.3). Sans lui la classe est un trou noir.

**Ordre d'exécution (valeur × risque × ROI)** : 1. RAM (rupture la plus fondamentale A1, la moins chère, spec explicite Juan) → 2. Quadrupède (chemin rigify existe, verrouiller) → 3. Goldorak (l'auto-correction **dégrade activement** l'armure) → 4. Caine (exige archi composite) → 5. Dragon (révèle manques taxonomie). D'abord protéger ce qui marche, repousser l'exploratoire.

---

## SECTION 6 — PLAN D'IMPLÉMENTATION PRIORISÉ

**Phase 0 — Contrats (débloque tout, ~pas de ML)** : (a) `morphology.py` squelette avec l'enum 8-classes + `ROUTING` table + schéma `v2` ; (b) étendre l'enum `motion_intent_classifier` (mecha_rigid_articulated, composite, soft_body, loco flight/hover/swim) + **corriger `_regex_fallback`** (verbes vol/nage/hover, robot/mecha) ; (c) modifier `anim_metrics.family_for_intent` pour router sur `deformation` (tue le bug fonte-armure 3.1) ; (d) ajouter kind `memory_module` à `subject_kind_extractor`. **Test d'intégration classe→baker en premier.**

**Phase 1 — RAM + Quadrupède (les chemins qui existent presque)** : brancher `morphology.classify` (features F1,F2,F7,F10 en scipy suffisent pour RAM/objet) dans `aurora_3d_pipeline.py` après soudage ; router OBJECT_INERT → led/static (aucun rig) et QUADRUPED → `_rigify_creature_skeleton`. Garde anti-sur-rig dans `mesh_acceptance_gate`. Tier 0/1 verts.

**Phase 2 — Goldorak** : réécrire `mesh_part_split.py` en **segmentation dièdre + hiérarchie parent→enfant + pivots = axes de charnière** (aujourd'hui : k-means blobs, pivots=centroïdes, nœuds plats sans parentage — vérifié). Rigid skinning 0/1, `retarget_mode=rotation_only`, flag `disable_laplacian`. Métrique `part_rigidity` (Kabsch, existe dans anim_metrics).

**Phase 3 — Boucle fermée** : coder `knob_registry.py`, `strategist.py` (agent LLM qwen), `metric_trust.py`, `correction_loop.py`, `vision_audit.py` (enveloppe l'audit 10-agents). Fixtures d'or par class + test de non-régression de la griffe + test de gating morphologique (Caine → `foot_ground`/`finger_spread` absents du jeu actif).

**Phase 4 — Caine (composite) + Dragon (ailes) + visage géométrique** : mécanisme `composite` par partie, chaînes ailes/queue dans le skeleton builder, face-bones/blendshapes.

### LES 3 PROCHAINES ACTIONS CONCRÈTES

1. **Créer `/home/juan/AuroraIA/application/python-services/morphology.py`** : l'enum 8-classes + les deux axes orthogonaux + la table `ROUTING` (Section 0.3) + le schéma `aurora.morphology.v2`. Même sans features, figer le contrat que les 6 modules importent. C'est le maillon central que personne n'avait écrit.

2. **Patcher `motion_intent_classifier.py`** : étendre `CATEGORIES` (+`mecha_rigid_articulated,composite,soft_body`), étendre `locomotion` (+`flight,hover,swim`), et **corriger `_regex_fallback`** (lignes 251-256 : ajouter `fly|vole|voler|hover|flotte|swim|nage` à `explicit_locomotion` avec mapping `base_loop=hover`, et `robot|mecha|armor|goldorak` en régime rigide). Débloque le socle déterministe des tests pour les cas volants/flottants.

3. **Modifier `anim_metrics.family_for_intent`** pour prendre `morphology.deformation` en priorité sur `motion-intent.category`, + écrire le **test d'intégration `class → baker`** et le test « Goldorak-qui-marche → famille `mecha_rigid` (pas `humanoid`) ». C'est le test qui empêche l'auto-correction de faire fondre l'armure — le désastre le plus grave, et le moins cher à verrouiller.

**Fil rouge** : les 6 facettes ont raisonné en vase clos sur un pipeline en partie imaginaire (MIA, `motion_metrics.py`, boucle « qui marche »), avec des prémisses de libs fausses (scipy « interdit » alors qu'il est présent), sans jamais négocier le contrat qui les relie. Cette architecture fige d'abord ce contrat (Phase 0), puis instancie le patron générique — un seul `correction_loop`, des jeux détecteurs/knobs différents par `class` — de sorte qu'aucune règle humanoïde universelle ne soit plaquée sur Caine, Goldorak ou une RAM.