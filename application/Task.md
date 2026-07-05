# AuroraIA-v2 - Task.md

Suivi des ameliorations et bugs en cours / resolus.

---

## Corrections appliquees (session 2026-04-04 - vague 7)

### 3D - runner Hunyuan resilient aux crashes natifs Windows
- `python-services/hunyuan3d_run.py`
  - Le script principal n execute plus directement toute la pipeline lourde dans le process Tauri.
  - Nouveau mode orchestrateur + worker:
    - l orchestrateur relance un worker protege pour la generation lourde
    - les `PROGRESS:*` du worker sont relayes en temps reel
    - les crashes natifs `-1073741819` / `torch._dynamo` / `allow_in_graph` ne font plus tomber tout le script principal
  - Strategies de recuperation ordonnees:
    - `gpu_quality_guarded`
    - `gpu_stable_no_offload`
    - `single_view_recovery` si la multivue semble instable
    - `cpu_shape_rescue` en dernier recours pour sauver un mesh shape-only exploitable
  - `TORCHDYNAMO_DISABLE=1` est force cote worker, l offload CPU peut etre coupe automatiquement, la texture peut etre desactivee sur le dernier secours.
  - Sur echec final, le script renvoie maintenant un JSON `ok:false` propre au lieu de laisser Tauri n afficher qu un `Script failed (...)` peu exploitable.

### 3D - references exactes encore plus strictes
- `src/services/threeDReferenceSupport.ts`
  - Le profil de recherche ajoute maintenant:
    - `requiredPageTerms`
    - `preferredDomains`
    - `blockedDomains`
  - Les references exactes produits / personnages demandent un score minimum plus haut.
  - Les requetes ajoutent plus souvent:
    - pages officielles marque / produit
    - `site:lian-li.com` pour `Strimer`
    - `solo no companion` / `site:fandom.com` pour les personnages connus
- `src/services/referenceVisualResearch.ts`
  - Les candidates sont maintenant triees par priorite de source avant verification vision.
  - Rejet deterministe en amont si:
    - domaine bloque
    - titre/page hors categorie attendue
    - aucun terme de page requis sur un cas d identite stricte
  - Cela durcit le cas ou une page "bonne marque" remonte quand meme une mauvaise image produit ou un contexte parasite.

### Validation
- `python -m py_compile python-services/hunyuan3d_run.py` passe
- `npx tsc --noEmit` passe
- `npm run build` passe
- Smoke tests:
  - plan de recovery Hunyuan verifie
  - recherche native `Lian Li Strimer Plus v2 isolated cable product` remonte bien la page produit officielle Lian Li en tete

---

## Corrections appliquees (session 2026-04-04 - vague 6)

### 3D - injection description visuelle enrichie dans chaque vue synthetique
- `src/services/threeDViewPlanner.ts`
  - `buildViewGenerationDirectives()` reecrit pour accepter un parametre `enrichedDescription` (la description visuelle complete issue de taskIntelligence).
  - Cette description est injectee dans CHAQUE directive de vue synthetique, pas seulement le label court.
  - Avant ce fix, FLUX ne recevait que "Front view of Naruto" sans savoir a quoi Naruto ressemble => resultat non ressemblant.
  - Maintenant FLUX recoit la description complete: costume, couleurs, traits, accessoires, pose, etc.
  - `prepareThreeDViewPlan()` et `buildViewStrategy()` mis a jour pour propager `enrichedDescription`.
- `src/views/ModelView.tsx`
  - Passe `taskContext.generationPrompt` comme `enrichedDescription` a `prepareThreeDViewPlan`.
  - Denoise abaisse pour plus de fidelite cross-vue:
    - Back: 0.68 → 0.55
    - Sides: 0.58 → 0.45
  - +6 steps ajoutes au workflow synthetique pour plus de precision.
  - Resultat: chaque vue synthetique est maintenant basee sur la meme description visuelle complete, avec plus de fidelite au seed front et plus de precision de generation.

### Validation
- `npm run build` passe apres ces changements.

---

## Corrections appliquees (session 2026-04-03 - vague 2)

### 3D - fidelite reference beaucoup plus stricte, cadrage isole/contexte et auto-correction
- `src/services/threeDIntent.ts`
  - Nouveau champ `referenceFraming`:
    - `isolated_subject`
    - `host_context`
    - `scene_context`
  - Le module ne traite plus automatiquement un cable / produit comme s il etait installe dans un hote.
  - Exemple critique corrige:
    - `Strimer`, cable LED, harnais ou composant demande seul => produit isole
    - contexte carte mere / boitier / chassis seulement si le prompt le demande explicitement
  - Les `anchoredPartsFocus`, `motionGuidance`, `researchQueries` et `motionPresets` changent maintenant selon ce cadrage.
  - Pour `pc_cabling` isole, les presets a droite ne poussent plus uniquement vers "carte mere + boitier", mais aussi vers:
    - produit isole
    - guides LED
    - connecteurs
- `src/services/threeDReferenceSupport.ts`
  - Extraction du sujet vise plus stricte:
    - nettoie les verbes d instruction
    - retire les mots comme `identique`, `exact`, `fidele`
    - garde le vrai nom du sujet a rechercher
  - Le profil de recherche 3D ajoute maintenant:
    - `identityTerms`
    - `forbiddenPageTerms`
    - `minimumScore`
  - Les references exactes / variantes sensibles imposent un seuil plus haut avant acceptation.
  - Les personnages imposent plus fortement:
    - solo character
    - full body
    - no companion
  - Les produits type Strimer / cable LED imposent plus fortement:
    - produit isole
    - connecteurs visibles
    - aucun boitier PC parasite
- `src/services/referenceVisualResearch.ts`
  - Verification des references encore plus stricte:
    - rejet si le titre/page porte deja des signaux parasites interdits (`case`, `tower`, etc.)
    - compatibilite titre/page durcie quand l identite est stricte
    - seuil d acceptation variable selon `minimumScore`
  - Nouveau verifier pour l image de reference generee elle-meme avant Hunyuan3D.
- `python-services/reference_visual_search.py`
  - Nouveau moteur de recherche web natif cote runtime local.
  - Cherche des pages sujet via DuckDuckGo HTML, inspecte leurs meta `og:image` / `twitter:image` / JSON-LD / images principales, puis remonte des candidates image.
  - Sert a sortir du seul couple Wikipedia / Wikimedia, trop faible pour les produits reels et beaucoup de personnages connus.
  - Le telechargement image passe aussi par ce script en fallback pour eviter les blocages du `fetch` navigateur sur certaines images cross-origin.
- `src/services/referenceVisualResearch.ts`
  - Utilise maintenant le moteur Python web natif en plus des sources wiki.
  - Les candidates image sont telechargees nativement si besoin avant verification vision.
  - Cas verifie localement:
    - `Lian Li Strimer Plus v2 isolated cable product` remonte bien la page produit officielle Lian Li avec plusieurs vraies images produit exploitables.
- `src/views/ModelView.tsx`
  - Le prompt de reference injecte maintenant:
    - `reference framing`
    - `exact subject label`
    - `required visible elements`
    - `forbidden parasite elements`
  - Le style de reference change mieux selon le sujet:
    - personnage anime => `anime`
    - cable produit isole / produit exact => plus souvent `realistic` au lieu de tout basculer en `technical_render`
  - Denoise plus bas pour les sujets exacts / identite stricte afin de limiter la deformation.
  - Nouvelle verification automatique de l image de reference juste apres FLUX:
    - si la reference derive, elle est regeneree avec un prompt correctif
    - si ca derive encore et qu une reference externe stricte existe, fallback direct dessus
    - si le sujet reste faux sur un cas critique (personnage, produit exact, cable isole), le pipeline echoue au lieu d envoyer une mauvaise reference a Hunyuan3D
  - Cela evite notamment:
    - `Natsu` qui part sur un autre personnage ou un duo parasite
    - `Lian Li Strimer Plus v2` qui part sur un boitier PC

### 3D - autonomie multi-vue, generation synthetique et verification per-vue
- `src/services/threeDViewPlanner.ts`
  - Nouveau type de source de vue: `synthetic` pour la generation autonome via FLUX quand la recherche externe echoue.
  - Analyse de symetrie intelligente par type d objet:
    - Personnages/creatures: gauche-droite symetriques OK, mais face et dos TOUJOURS differents (visage vs dos de la tete, poitrine vs dos). JAMAIS de reuse front->back.
    - Cables avec connecteurs differents aux extremites: chaque vue peut montrer un connecteur different.
    - Vehicules: gauche-droite symetriques, avant et arriere differents.
    - Objets axialement symetriques (engrenages, poulies, axes): toutes les vues equivalentes.
    - Systemes articules (charnieres, bielles): chaque vue revele des details mecaniques differents.
  - Generation autonome de directives FLUX per-vue:
    - Chaque vue (front, back, left, right) recoit un prompt specifique decrivant exactement ce qui doit etre visible.
    - Personnages: face visible, costume, silhouette (front) vs dos de la tete, cheveux, cape (back).
    - Cables: connecteurs face camera (front) vs sortie cable et strain relief (back).
    - Mecanique: face fonctionnelle principale (front) vs points de fixation arriere (back).
    - LED/lumineux: exigences emissives injectees dans chaque directive de vue.
  - Verification per-vue par modele vision apres generation ou recherche:
    - Verifie: angle correct, sujet present, details fonctionnels trouves/manquants, coherence LED.
    - Si verification echoue: regeneration avec prompt corrige (max 2 tentatives).
    - Resultats de verification stockes dans chaque assignment pour traçabilite.
  - Verification fonctionnelle: connecteurs, charnieres, pivots, axes, guides lumineux par vue.
  - Export des nouvelles fonctions: `verifyViewImage`, `getSyntheticViewDirective`, `buildCorrectedViewDirective`.
  - Le LLM reçoit maintenant les regles de symetrie strictes pour ne plus reuser front->back sur les personnages.
- `src/views/ModelView.tsx`
  - Pipeline integre la generation synthetique autonome:
    - Quand des vues sont marquees `synthetic`, elles sont generees via FLUX avant materialisation.
    - Chaque vue synthetique utilise la vue front comme seed de coherence (denoise 0.72) pour maintenir l identite du sujet.
    - Boucle generate + verify + retry (max 2 tentatives) avec correction automatique du prompt si verification echoue.
  - Le message assistant inclut maintenant: nombre de vues synthetiques, vues verifiees OK/partielles, details fonctionnels confirmes/manquants.
  - Les parametres de sauvegarde incluent les nouvelles metriques de verification.
  - Le panneau Plan De Vues dans l UI affiche:
    - Quelles vues seront generees automatiquement.
    - Resultats de verification per-vue (OK ou partiel avec details).
    - Resume de verification fonctionnelle.
  - Personnages: le plan de vues exige maintenant front + back + left comme vues requises (au lieu de front + left seulement).

### Validation
- `npm run build` passe apres ces changements.

---

## Corrections appliquees (session 2026-04-03)

### 3D - reference image beaucoup plus guidee
- `src/views/ModelView.tsx`
  - Le module 3D ne depend plus seulement d un prompt libre pour fabriquer l image de reference avant Hunyuan3D.
  - Il peut maintenant chercher une reference visuelle externe quand le sujet ressemble a un objet connu, un composant, un personnage ou une reference existante.
  - Si une bonne reference est trouvee, elle sert soit directement de reference visible, soit de seed pour un raffinement FLUX quand il faut nettoyer la vue, appliquer un preset de mouvement ou respecter de meilleurs rapports dimensionnels.
  - Une vraie reference utilisateur n est plus raffinee par defaut juste parce que le sujet est technique : sans demande de transformation, elle reste prioritaire pour maximiser la fidelite.
  - Pour les personnages / personnes, le pass de reference force maintenant un fond noir studio par defaut tant qu aucun fond ou decor n est explicitement demande.
  - Les references seedees gardent un denoise plus bas quand l identite doit etre preservee, pour reduire les deformations de personnage ou de produit exact.
  - Si plusieurs images sont jointes et qu elles peuvent etre mappees en `front / left / back / right`, le module passe en mode multivue direct au lieu de repainter une unique vue.
  - Le module affiche maintenant un plan de vues explicite: quelles faces sont retenues, quelles vues sont verifiees et quels signaux LED / lumineux doivent rester presents.
  - Les presets de mouvement ont maintenant un vrai bouton d execution : `Regenerer avec ce preset`, pour appliquer concretement la pose ou l etude mecanique sur la prochaine reference et pas seulement changer l etat visuel.
  - Le viewer affiche aussi les informations de reference active et les dimensions / rapports trouves quand ils existent.
- `src/services/threeDViewPlanner.ts`
  - Nouveau planificateur de vues pour le 3D.
  - Il decide si une multivue est utile, quelles vues doivent etre cherchees, et quelles vues peuvent etre re-utilisees car le sujet est assez symetrique.
  - Il ajoute des verifications fonctionnelles par vue: connecteurs, charnieres, axes, pivots, light guides, branches, etc.
  - Il ajoute aussi des exigences lumineuses quand le sujet contient des LED / RGB / emissive.
  - Si une vue manque, il peut la rechercher strictement par face (`front`, `left`, `back`, `right`) avant reconstruction.
- `src/services/threeDReferenceSupport.ts`
  - Nouveau service de support 3D pour :
    - detecter si la demande vise un sujet libre, un sujet connu ou une reference exacte
    - extraire des notes de dimensions depuis la recherche native
    - lancer une recherche visuelle externe et reutiliser la meilleure image candidate
    - construire un profil de recherche strict du sujet vise (elements requis, elements interdits, isolement)
  - Les dimensions utilisateur restent prioritaires ; sinon le module prefere les dimensions auto-recherchees quand le sujet existe.
- `src/services/referenceVisualResearch.ts`
  - Le filtrage des references est maintenant plus strict pour le 3D :
    - verification du sujet exact vise
    - rejet des personnages parasites ou mauvais variants
    - rejet des environnements dominants comme un boitier PC complet quand le sujet demande un cable ou un composant isole
    - compatibilite titre/page plus stricte quand l identite doit etre respectee
    - verification optionnelle par face (`front/back/left/right`)
    - verification explicite de details fonctionnels et d elements lumineux quand ils sont demandes
- `src/services/threeDReferenceSupport.ts`
  - Le profil de recherche fallback est plus strict pour les variantes produit / personnage (`v2`, `plus`, `24-pin`, `strimer`, etc.).
  - Les prompts de type cable LED / Strimer ajoutent maintenant des elements requis comme light guides, cable combs et connecteurs visibles, tout en interdisant plus fortement le boitier PC complet parasite.
- `src/services/threeDIntent.ts`
  - L intention 3D favorise davantage la recherche automatique pour les sujets connus, produits, personnages, references et pieces reelles.
  - Pour une piece mecanique connue sans cotes fournies, le module cherche d abord au lieu de demander trop vite une clarification.
- `src/services/taskIntelligence.ts`
  - La distillation 3D preserve maintenant aussi les rapports dimensionnels ou proportions connus quand ils sont presents dans le contexte de recherche.

### Image - fidelite reference, anti-pixellisation et continuite de session
- `src/views/ImageView.tsx`
  - Le module image recharge maintenant la bonne session via `SessionSwitcher` : changement de conversation, suppression et nouvelle conversation rehydratent la galerie locale au lieu de rester bloques sur l ancienne.
  - La reprise auto est isolee par session : `lastGeneratedPathRef` est recale sur la session active pour eviter qu une nouvelle discussion reutilise par erreur la derniere image d une autre conversation.
  - Ajout d une continuite visible cote UI avec rappel du dernier contexte actif dans la session image.
  - Le plan de rendu est plus agressif pour les cas sensibles (`anime`, reference existante, composant technique) : resolution plus haute et davantage de steps quand la fidelite prime.
  - Les requetes automatiques de reference sont enrichies pour chercher mieux les designs de personnages, photos isolees de pieces et dimensions quand elles existent.
- `src/components/SessionSwitcher.tsx`
  - Suppression du `useMemo` sur les sessions et la session active. Le composant lit desormais l etat courant du store a chaque rendu, ce qui corrige le comportement ou "Nouvelle conversation" ou la corbeille semblaient ne pas changer de discussion avant redemarrage.
- `src/stores/moduleHistoryStore.ts`
  - Apres suppression d une session active, le module bascule vers la session la plus recente du module au lieu d un choix implicite dependant de l ordre interne.

### Image - recherche visuelle externe mieux filtree
- `src/services/referenceVisualResearch.ts`
  - Nouveau chemin de recherche visuelle combine :
    - Wikimedia Commons pour objets, composants et photos propres.
    - Pages Wikipedia FR/EN quand une illustration de sujet connu existe.
  - Chaque image candidate est filtree par le modele vision pour rejeter :
    - pixellisation parasite
    - collage, UI, memes, captures parasites
    - hors-sujet ou sujet trop encombre
  - Le module ne retient plus une reference si elle est jugee `cluttered` meme avec un bon score global.

### Image - prompting FLUX plus fidele
- `src/services/taskIntelligence.ts`
  - Le contexte de recherche et le contexte multimodal sont maintenant injectes jusqu au prompt final de diffusion.
  - La distillation image insiste davantage sur :
    - preservation des traits iconiques
    - silhouette et costume pour personnages existants
    - layout connecteurs / proportions / dimensions connues pour composants
    - rejet explicite de la pixellisation et du faux upscale basse resolution
- `src/services/generationContract.ts`
  - Les prompts image/drawing ajoutent desormais par defaut des priorites qualite anti-pixellisation et anti-drift identitaire quand on vise un personnage ou un sujet reconnaissable.
- `src/utils/fluxWorkflow.ts`
  - Les presets FLUX sont renforces pour la fidelite :
    - `technical_render` plus strict sur le hard-surface et les details propres
    - `anime` davantage oriente "on-model", lineart propre et sans texture boueuse
    - `none` utilise maintenant un sampler plus qualitatif
  - Le prompt style ajoute des garde-fous globaux contre les blocs, artefacts JPEG, bords en escalier, derive d identite et incoherences mecaniques.

### Validation
- `npm run build` passe apres ces changements.

---

## Corrections appliquees (session 2026-04-02)

### 3D - Runtime Hunyuan, fidelite technique et mouvement
- `python-services/hunyuan3d_run.py`
  - Fallback automatique de `tencent/Hunyuan3D-2.1` vers `tencent/Hunyuan3D-2` quand le snapshot exige `hy3dshape` mais que le runtime local est base sur `hy3dgen`.
  - Correction du crash `Hunyuan3DDiTFlowMatchingPipeline object has no attribute components` : l offload CPU est maintenant ignore proprement quand le pipeline ne l expose pas.
  - Ajout de strategies adaptatives shape (`balanced`, `memory_safe`, `stability_fallback`) et retries texture.
  - Support direct du mode multivue `front / back / left / right` branche sur `tencent/Hunyuan3D-2mv` quand plusieurs references utilisateur sont presentes.
  - Le runner accepte aussi les vues re-utilisees ou auto-cherchees par le planificateur, pas seulement les images uploades brut.
  - Si le multivue n est pas disponible, le runner retombe proprement sur une vue principale au lieu d echouer.
- `src/services/threeDIntent.ts`
  - L intention 3D detecte desormais la famille de systeme (`belt_drive`, `gear_train`, `cylinder_actuator`, `hinge_joint`, `linkage`, `cable_routing`, `pc_cabling`, `electrical_harness`).
  - Ajout de `movingPartsFocus` et `anchoredPartsFocus` pour distinguer les elements mobiles des supports fixes.
  - Ajout de `representationGoal` pour differencier lisibilite cinematique, lisibilite de routage et rigging.
  - Les prompts de cablage PC / LED sont mieux classes et imposent davantage que seul l assemblage cable soit rendu, pas un boitier complet invente.
- `src/utils/fluxWorkflow.ts`
  - Nouveau preset `technical_render` pour generer des references mecaniques / electriques propres sans les artefacts du preset photo humain.
- `src/views/ModelView.tsx`
  - Le pipeline choisit maintenant style, resolution et nombre de steps de la reference FLUX selon l intention 3D et le hardware.
  - Les prompts de reference injectent la separation mobile / fixe et les priorites systeme avant la reconstruction Hunyuan3D.
  - Le viewer n applique plus de rotation automatique aux personnages / creatures.
  - Ajout d un panneau a droite avec presets d action / mouvement contextuels : marche, applaudissement, salut, course pour les personnages ; etudes de courroie, verin, charniere, routage cable, etc. pour les systemes techniques.
  - Quand un preset est selectionne, la vue est verrouillee pour garder une lecture claire du mouvement ou de la pose au lieu de faire tourner le mesh.
- `src/services/generationContract.ts` + `src/services/taskIntelligence.ts`
  - Declenchement de recherche native elargi aux prompts mecaniques, actuateurs, courroies/poulies, cablage, connecteurs et routage technique.
  - Distillation du prompt 3D amelioree pour garder la chaine fonctionnelle complete au lieu d un seul element visuel dominant.

### Voix - VAD (Voice Activity Detection)
- `useVoiceLive.ts`
  - Bug de fermeture stale corrige. `checkVAD` fermait sur `phase === 'idle'` depuis la closure du `useCallback`, ce qui empechait la detection de silence de s executer. Remplace par un `isRecordingActiveRef` mis a jour explicitement a chaque demarrage / arret.
- `ConversationView.tsx`
  - Le bouton "Parler" manuel utilisait `MediaRecorder` brut sans detection de silence. Ajout d un pipeline VAD via `AnalyserNode` + `Float32Array` : arret automatique apres 1.8 secondes de silence (seuil RMS 0.012).

### Code - Contexte conversation stale
- `CodeView.tsx`
  - `conversationHistory` etait capture a la creation du `useCallback`. Deplace a l interieur de `generate()` avec `const conversationHistory = getRecentMessages('code', 6)`. Contexte maintenant frais a chaque generation.

### Code - Sauvegarde meme si sandbox echoue
- `CodeView.tsx`
  - `setSaveDialogData` n etait appele que si `sandboxResult?.ok`. Modifie : dialogue propose des que des fichiers sont generes, avec `fidelityScore: 68` si sandbox KO et `92` si sandbox OK.

### Module dessin - interpretation du croquis
- `DrawingView.tsx`
  - Valeurs de denoise augmentees pour que FLUX interprete librement au lieu de reproduire.
  - Ajout de `analyzeSketchWithVision()` pour decrire ce qui est dessine dans le croquis puis combiner cela avec l intention utilisateur.

### Module video - duree action vs duree totale
- `VideoView.tsx`
  - `parseDurationFromPrompt()` ameliore pour eviter de confondre duree d action et duree totale.
  - Nouvelle fonction `extractActionDurations()` injectee dans le `generationPrompt`.
  - Detection de duree totale cherche maintenant dans `taskContext.enrichedPrompt`.

### Nommage semantique des fichiers
- `saveSystem.ts`
  - Ajout de `generateSemanticSlug()` via `llama4:scout` avec fallback sur `slugify(prompt)`.
  - `saveToWorkspace()` et `saveAndExportZip()` utilisent maintenant ce slug semantique.

### Module academique - ClarificationDialog
- `LearningView.tsx`
  - Ajout de `ClarificationDialog` dans `QuizPanel`, `CoursesPanel` et `ParcoursPanel`.
  - Les `throw new Error(taskContext.clarificationQuestion)` ont ete remplaces par un vrai dialog.

---

## Corrections appliquees (session 2026-04-03 - vague 3)

### 3D - Correction deformation multi-vue et poussee qualite maximale
- Probleme critique: FLUX generait une image composite (vue gauche + vue droite sur une seule image) au lieu d une entite unique par vue, causant des deformations et deux personnages au lieu d un seul.
- Cause racine: `buildReferencePrompt` dans `ModelView.tsx` injectait des notes de contrat multi-vue dans un prompt destine a une generation d image UNIQUE, ce qui faisait que FLUX interpretait le prompt comme "genere plusieurs vues sur une image".

#### `src/utils/fluxWorkflow.ts`
  - Ajout de 8 regles anti-split/anti-multi-panel dans `GLOBAL_VISUAL_RULES`:
    - "ONE entity only in the frame"
    - "NEVER split the image into multiple panels or views"
    - "NEVER render side-by-side left and right views on the same image"
    - "NEVER generate a multi-view composite sheet"
    - "NEVER show the same subject from two different angles in one image"
    - "the entire frame must show ONE single continuous view of ONE subject"
    - "no mirror copies", "no tiled character turnarounds"

#### `src/services/threeDViewPlanner.ts`
  - Directives per-vue renforcees: chaque vue synthetique recoit maintenant des instructions explicites anti-split (9 lignes d isolation par vue).
  - Personnages: les 4 vues (front, back, left, right) sont maintenant TOUTES requises (avant: front+back+left requis, right optionnel).
  - Sujets structures: front+back+left requis (avant: front+left seulement).
  - Verification per-vue renforcee: nouveau champ `singleEntity` dans `ThreeDViewVerification`.
    - Le modele vision verifie maintenant explicitement si l image est un composite multi-panel.
    - Si l image contient deux copies du sujet ou des vues cote a cote, `singleEntity = false` et la vue est rejetee.
    - Le retry injecte une correction explicite anti-split quand `singleEntity` echoue.
  - Toutes les vues manquantes (requises ET optionnelles) sont marquees `synthetic` quand multiview est actif.

#### `src/views/ModelView.tsx`
  - `buildReferencePrompt`: suppression totale des notes multi-vue, view-plan, verification et lighting du prompt de reference unique.
    - Ajout de 6 lignes d instructions anti-split explicites au debut du contrat 3D.
    - Le prompt de reference ne contient plus AUCUNE mention de "plusieurs vues" ou "coherence inter-vues".
  - `generateSyntheticView`: ajout d un suffixe anti-split force a CHAQUE prompt FLUX synthetique.
  - Generation front-first: quand la vue front est synthetique (pas de source utilisateur/externe), elle est generee EN PREMIER sans seed, avec +4 steps de qualite. Elle devient ensuite l ancre de coherence pour toutes les autres vues.
  - Denoise inter-vues ajuste: vues laterales a 0.58 (plus fidele au front), vue back a 0.68 (permet de montrer le dos correctement).
  - Resolution et steps augmentes partout:
    - Personnages: 1024x1024, 40 steps (avant: 896x896, 32 steps)
    - Technique: 1024x1024, 40-42 steps (avant: 896-1024, 36-38 steps)
    - Anime: 1024x1024, 40 steps (avant: 896-1024, 32-36 steps)
    - General: 896-1024, 30-36 steps (avant: 768-896, 24-28 steps)

#### `python-services/hunyuan3d_run.py`
  - Nouvelle strategie `maximum_quality` en tete de cascade (avant `balanced`):
    - `num_inference_steps`: 56-70 (avant: 42-50)
    - `octree_resolution`: 384-512 (avant: 320-384)
    - `num_chunks`: 10000-12000 (avant: 8000-9000)
  - Personnages: octree 448+, steps 60+, chunks 11000+
  - Multiview: octree 448+, steps +6, chunks 11000+
  - 4 strategies en cascade au lieu de 3 (maximum_quality → balanced → memory_safe → stability_fallback)
  - Texture paint: 3 tentatives au lieu de 2

### Validation
- `npm run build` passe apres ces changements.
- `python -m py_compile python-services/hunyuan3d_run.py` passe.

---

## Corrections appliquees (session 2026-04-03 - vague 4)

### 3D - Injection d identite produit/sujet et fidelite des presets de mouvement

Probleme critique: FLUX generait un boitier PC au lieu d un cable Strimer parce que l identite produit n atteignait jamais le prompt de diffusion.
Cause racine: `detectKnownProductDescription` ecrivait les descriptions dans `intent.referencePromptAdditions`, mais celles-ci n etaient ajoutees qu en notes de contrat a la FIN de `buildReferencePrompt`. Le prompt FLUX reel etait distille par `distillToGenerationPrompt` qui ne recevait que le contexte de recherche Wikipedia et le contexte multimodal — zero connaissance produit.

#### `src/views/ModelView.tsx`
  - Injection de l identite produit dans `workingPrompt` AVANT `prepareTaskIntelligence`:
    - Les lignes d identite (`THIS IS NOT`, `Visual description:`, `DO NOT generate`, `Generate ONLY`) sont extraites de `intent.referencePromptAdditions`
    - Injectees comme section `CRITICAL PRODUCT/SUBJECT IDENTITY` dans le prompt de travail
    - Le LLM de distillation voit maintenant ces descriptions comme contexte primaire
  - Injection des presets de mouvement comme directives fortes:
    - Section `ACTIVE MOTION/POSE DIRECTIVE` ajoutee au prompt de travail avant distillation
    - `MANDATORY:` devant la directive du preset
  - `buildReferencePrompt` restructure:
    - Section `MANDATORY SUBJECT IDENTITY` en PREMIER (juste apres le prompt principal)
    - Section `MANDATORY POSE/MOTION` en deuxieme position
    - Les lignes d identite ne sont plus repetees dans les notes de contrat en bas
    - Les notes de contrat restent pour les additions non-identitaires

#### `src/services/taskIntelligence.ts`
  - `distillToGenerationPrompt` renforce pour les sujets connus:
    - Nouvelle regle CRITICAL: si le contexte contient une section PRODUCT/SUBJECT IDENTITY, elle doit etre la base PRIMAIRE de la generation
    - Nouvelle regle: un produit nomme (marque + modele) doit decrire ce produit exact, pas une version generique
    - Nouvelle regle: si une MOTION/POSE DIRECTIVE est presente, elle est MANDATORY

#### `src/services/threeDIntent.ts`
  - `detectKnownProductDescription` elargi de cables-seulement a une base de connaissance etendue:
    - PC cables: Strimer (descriptions renforcees avec forme visuelle precise), CableMod, RGB extensions, sleeved cables, 12VHPWR
    - Systemes mecaniques: courroies, trains d engrenages, verins, charnieres, biellettes
    - Composants PC: AIO coolers, GPU, cartes meres, alimentations, RAM, ventirads, SSD, ventilateurs
  - Chaque famille inclut des descriptions visuelles precises de la FORME du produit

#### `src/services/threeDReferenceSupport.ts`
  - `detectReferenceMode` reconnait maintenant les marques connues (Strimer, Lian Li, Noctua, Corsair, NZXT, etc.) comme `exact_reference` automatiquement
  - Un produit nomme par marque active le score minimum de fidelite le plus eleve (88/100)

#### `src/services/threeDViewPlanner.ts`
  - Les directives per-vue synthetiques incluent maintenant les lignes d identite produit dans le prefixe partage
  - Chaque vue generee par FLUX sait ce que le produit EST, pas seulement son nom

### Validation
- `npm run build` passe apres ces changements.

---

## Corrections appliquees (session 2026-04-03 - vague 5)

### 3D - Comprehension profonde et prompt FLUX natif pour TOUT sujet

Probleme: aucune ressemblance dans les generations. Le LLM de distillation (`distillToGenerationPrompt`) corrompait systematiquement les descriptions avant que FLUX ne les voie. Pour un cable Strimer, FLUX generait un objet rectangulaire plat sans aucun rapport. Pour les personnages, composants, mecaniques — meme probleme de comprehension.

Cause racine profonde: le pipeline passait par TROIS etapes de corruption:
1. L utilisateur ecrit un prompt (ex: "strimer lian li v2 plus")
2. `distillToGenerationPrompt` demandait au LLM local de "distiller en anglais" → le LLM NE SAIT PAS ce qu est un Strimer et produit une description generique ou fausse
3. `buildReferencePrompt` ajoutait les descriptions produit en notes de contrat EN BAS → FLUX les ignore (le text encoder donne plus de poids au debut du prompt)

#### NOUVEAU: `buildFluxVisualDescription` dans `threeDIntent.ts`
  - Nouvelle fonction exportee qui court-circuite COMPLETEMENT la distillation generique
  - Produit un prompt FLUX natif (comma-separated tags, termes visuels concrets) optimise pour les modeles de diffusion
  - Utilise le LLM avec un prompt specialise "FLUX prompt engineer":
    - Decrit l APPARENCE PHYSIQUE EXACTE du sujet: forme, materiaux, couleurs, textures, proportions
    - Si une connaissance produit existe (detectKnownProductDescription), elle est OBLIGATOIRE comme base primaire
    - Les presets de mouvement sont integres comme directives imperatives
    - Le contexte de recherche (Wikipedia, web) est utilise pour la precision visuelle
  - Fallback manuel: si le LLM echoue, `buildManualFluxDescription` construit le prompt directement a partir de la connaissance produit + intent
  - Verification post-LLM: si le LLM a ignore les descriptions visuelles connues (ex: cable pc_cabling sans mention de light-guide), le prompt est corrige automatiquement

#### `src/views/ModelView.tsx`
  - `buildFluxVisualDescription` est appele APRES l analyse d intent et AVANT la generation
  - Le resultat REMPLACE `taskContext.generationPrompt` (la distillation generique)
  - Nouvelle troisieme tentative de correction quand le sujet est FAUX:
    - Si `wrongSubject=true` ou score < 40 apres la premiere correction
    - Utilise le prompt FLUX visuel direct + correction d identite forcee
    - +8 steps supplementaires pour maximiser la fidelite
    - Le prompt inclut toutes les lignes `THIS IS NOT`, `Visual description:`, `DO NOT generate`

#### `src/services/threeDIntent.ts`
  - `detectSystemClass` elargi:
    - Marques connues (strimer, lian li, cablemod) → detection directe `pc_cabling`
    - Nouveaux termes: rallonge, pignon, biellette, manivelle, tringlerie, gond, bornier, terminal block
    - `piston` detecte comme `cylinder_actuator` sauf si contexte "engine/moteur"
  - `detectSubjectKind` elargi:
    - Marques connues → `product` direct
    - Anime + personnage/character → `character`
    - Animaux specifiques (dragon, wolf, chat, etc.) → `creature`
    - Vehicules etendus (camion, avion, bateau, train, scooter, etc.)
    - Outils etendus (marteau, perceuse, scie, pince, etc.)
    - Architecture etendue (temple, chateau, pont, immeuble, etc.)
  - `detectPurpose` elargi:
    - Marques connues → `product`
    - Anime + character → `character`
    - Composants PC specifiques → `product`

#### `src/services/threeDReferenceSupport.ts`
  - Marques connues (strimer, cablemod, lian li, noctua, corsair, nzxt, cooler master, etc.) → `exact_reference` automatique
  - Score minimum 88/100 pour les produits de marque

#### `src/services/referenceVisualResearch.ts`
  - Nouveau champ `wrongSubject` dans `ReferenceVisualAssessment`
  - Le systeme de verification verifie maintenant en PREMIER si l image montre le BON sujet:
    - "Si l utilisateur demande un cable et l image montre un boitier PC → wrongSubject=true, score=0"
    - "Un cable N EST PAS un boitier. Un GPU N EST PAS une carte mere."
    - wrongSubject=true → usable=false et exactEnough=false automatiquement

#### `src/services/threeDViewPlanner.ts`
  - Les directives per-vue synthetiques incluent les lignes d identite produit dans le prefixe partage

### Validation
- `npm run build` passe apres ces changements.

---

## En cours / A faire

### Conversation - questions LLM comme pop-up
Le LLM peut poser une question dans sa reponse. Actuellement elle apparait comme message dans le fil. A ameliorer : detecter si la reponse se termine par une question et proposer un pop-up de reponse rapide.

### Affichage des erreurs
Les erreurs dans les modules (code, video, image) sont affichees dans la sidebar gauche. Si l utilisateur a scrolle vers le bas pour voir la generation, il ne voit pas l erreur. A ameliorer : banner sticky en haut de page ou toast flottant.

### Module video - question si duree ambigue
Si le prompt contient une action sans duree totale claire (ex: "une baston"), poser la question via `ClarificationDialog` avant la generation.

### Module dessin - export du resultat + comparaison
Actuellement le resultat final est affiche mais sans bouton de sauvegarde / export evident apres generation.

### Image - references copyright / personnages connus
Le pipeline de recherche visuelle est beaucoup plus fort, mais les personnages d anime ou de licence restent limites quand aucune image de reference exploitable n est accessible automatiquement. La meilleure fidelite reste obtenue avec une reference utilisateur exacte.

---

## Architecture rappel

| Fichier | Role |
|---|---|
| `useVoiceLive.ts` | Hook VAD + STT Voxtral/Whisper + TTS Kokoro |
| `ConversationView.tsx` | Copilote vocal, pipeline 6 etapes, bouton mic VAD |
| `CodeView.tsx` | Generation code streaming, sandbox, contexte conversation |
| `DrawingView.tsx` | Canvas croquis -> vision model -> FLUX img2img |
| `VideoView.tsx` | Wan2.2 T2V/I2V, detection duree, presets motion |
| `LearningView.tsx` | Quiz/cours/parcours + gamification + ClarificationDialog |
| `saveSystem.ts` | Sauvegarde workspace + ZIP + nommage semantique |
| `taskIntelligence.ts` | Pipeline analyse/enrichissement/distillation prompts |
| `conversationOrchestrator.ts` | Pipeline LLM conversation, fast/voice path |
