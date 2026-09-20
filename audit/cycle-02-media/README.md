# Cycle 2 — Image, Dessin explicatif et mesures 3D

État vérifié le 20 septembre 2026. Reprise depuis `01595e8` sur `refonte/module-code`. Le code de ce cycle est enregistré dans le commit local `8ebec41` ; aucun push ni redémarrage des services. Les commits du cycle 1 restent documentés dans [le rapport précédent](../cycle-01-resilience/README.md).

## 1. Ce qui a changé

| Parcours | Correction | Référence |
|---|---|---|
| Image et Dessin via ComfyUI | Un seul moniteur : sélection par `prompt_id`, erreurs d’exécution remontées dès lecture, sorties temporaires écartées, sous-dossier conservé, cinq échecs réseau consécutifs au maximum. | `application/src/services/comfyJobMonitor.ts:11` |
| Attentes longues | Suivi annulable, y compris si la lecture de l’historique reste bloquée. Délai de suivi de 30 minutes, contre 6 pour Image et 4 pour Dessin. Cela n’accélère pas l’inférence. | `application/src/services/comfyJobMonitor.ts:62` |
| Reprise Image | Le même moniteur suit le job sauvegardé après rechargement. Un échec ne supprime plus automatiquement son identifiant. Suppression du seul identifiant effectivement récupéré. | `application/src/hooks/useImageViewLogic.ts:313` |
| Protection des rendus longs | Renouvellement du verrou toutes les 60 secondes pendant une génération active ; un ancien propriétaire ne peut pas renouveler celui d’un autre rendu. | `application/src/hooks/useImageViewLogic.ts:508`, `application/src/services/imageGenerationSafety.ts:55` |
| Dessin explicatif | Demande de graphe JSON au modèle Ollama, validation des identifiants et relations, mise en page SVG avec vrais textes, flèches et retours de cycle. Export SVG, mode monochrome conservé. Ce chemin ne lance pas FLUX. | `application/src/hooks/useDrawingViewLogic.ts:607`, `application/src/services/drawingExplanation.ts:33` |
| Correction autonome des schémas | Si le JSON ou les relations sont invalides, une seconde demande reçoit le diagnostic et la réponse précédente. Deux tentatives maximum ; annulation respectée ; une erreur réseau reste explicite. | `application/src/services/drawingExplanation.ts:128`, `application/src/hooks/useDrawingViewLogic.ts:610` |
| Dessin artistique | Suppression du preset manga systématique. Le prompt et la référence pilotent le style. Encodage du croquis par blocs pour éviter le dépassement de pile ; annulation transmise à l’analyse vision. | `application/src/hooks/useDrawingViewLogic.ts:696`, `application/src/services/drawingExplanation.ts:159` |
| Mesure GPU 3D | Correction de l’inversion entre mémoire libre et totale renvoyées par `torch.cuda.mem_get_info()`. | `application/python-services/aurora_hunyuan/pipeline_hunyuan_robust.py:44` |
| Benchmark Image | Inférence réelle par défaut, simulation uniquement avec `--simulate`. Contrat `package_files`, résolution réelle, erreurs persistées, seeds et temps médian/p95. Aucun verdict de fidélité visuelle déduit des seules métriques. | `application/python-services/run_deep_image_benchmark.py:82`, `application/python-services/run_deep_image_benchmark.py:114` |

Aucune modification supplémentaire du dépôt CLI dans ce cycle. La reprise SSE du cycle 1 reste distincte de la reprise des images dans le navigateur.

## 2. Preuves et limites des mesures

- `npm run check` réussit : TypeScript, **25 tests** Node et compilation Vite. Les avertissements de bundling concernent notamment `web-tree-sitter` et deux imports dynamiques également importés statiquement ; ils ne sont pas corrigés ici. Journal : [frontend-check.log.gz](frontend-check.log.gz).
- **14 tests Python réussissent**, dont 7 nouveaux : métadonnées Image et distinction simulation/réel, mémoire GPU, puis 7 tests existants du contrôle Hunyuan. Journal : [python-tests.log.gz](python-tests.log.gz).
- **9/9 cas de packaging simulé** valident le contrat actuel. Médiane : **44,17 ms**, p95 : **138,79 ms**. Ces temps mesurent la simulation et les fichiers, **pas FLUX**. Les fichiers de test étaient sous `/tmp/aurora-image-structure-check` et peuvent disparaître au redémarrage. Rapport : [image-structure-benchmark.json](image-structure-benchmark.json).
- Fixture de dessin créée explicitement pour tester la mise en page : **4 nœuds, 4 relations, 8 libellés, 0 débordement de texte** dans Chromium. Une flèche de retour passe à côté des boîtes. [SVG](explanation-fixture.svg), [capture](explanation-fixture.png), [mesures](svg-browser-measurements.json). Cette fixture n’a pas été générée par un modèle.
- La première capture automatisée a échoué ; l’attente des polices et de deux frames avant capture de l’élément SVG résout le contrôle final. Le journal initial est conservé : [svg-browser-check-initial.log.gz](svg-browser-check-initial.log.gz).
- Le test d’erreur ComfyUI signale l’échec au **premier poll**, au lieu de le masquer jusqu’au timeout. L’interrogation normale reste espacée de 1,5 seconde. Le test d’encodage traite **400 000 octets** sans perte ni dépassement de pile. Sources : `application/src/__tests__/comfyJobMonitor.test.ts`, `application/src/__tests__/drawingExplanation.test.ts`.

Commandes et résultats : [verification.json](verification.json). Aucun gain de VRAM ou de temps d’inférence Image/3D n’est revendiqué. Aucun nouveau modèle 3D ni image FLUX n’a été produit pour cette validation. L’essai avec un modèle Ollama déjà chargé a été abandonné avant inférence car `/api/ps` ne renvoyait plus de modèle chargé ; le parcours modèle vers SVG reste à valider de bout en bout.

### Autonomie effectivement implémentée

Le module Dessin peut maintenant produire le graphe, le contrôler, demander une correction ciblée et livrer uniquement un graphe structurellement valide. Les cinq tests de cette boucle vérifient : une seule inférence si la première réponse est valide, correction guidée par le diagnostic, arrêt après deux réponses invalides, annulation, propagation d’une panne du modèle. Cela n’équivaut pas à une validation factuelle autonome de l’explication.

L’autonomie globale reste partielle : la reprise durable des missions, les critères sémantiques Image/3D, le transfert vérifié et la capitalisation des échecs entre tous les parcours restent dans la liste suivante. Aucune capacité générale à se modifier seul et à garantir toutes ses productions n’est annoncée.

## 3. Notation pondérée, provisoire

Notes d’audit du code et des tests, non scores de qualité visuelle : `(3 × justesse + 2 × robustesse + 3 × parité + 2 × observabilité) / 10`. Les autres composants conservent l’évaluation du cycle 1.

| Composant | Justesse ×3 | Robustesse ×2 | Parité CLI ×3 | Observabilité ×2 | /10 |
|---|---:|---:|---:|---:|---:|
| Interface Image | 6 | 6 | 3 | 5 | 5,0 |
| Dessin explicatif | 6 | 5 | 2 | 5 | 4,4 |
| Benchmark Image | 6 | 5 | 3 | 7 | 5,1 |
| Hunyuan et 3D | 6 | 5 | 3 | 5 | 4,7 |

Les notes restent sous 9 en l’absence de corpus de qualité et de parité démontrée. Elles servent à prioriser les patches suivants. [CSV](scores.csv).

## 4. Liste d’améliorations et de performances à reprendre

| Priorité | Travail concret | Critère de validation |
|---|---|---|
| P0 | Porter la gestion explicite des erreurs ComfyUI au moteur Python. `image_module_engine.py:265` masque encore les exceptions ; son appel à la ligne 341 limite le suivi à 360 secondes. | Un crash GPU, un job interrompu et un téléchargement en échec donnent une erreur identifiable ; aucun renvoi de fichier simulé en mode réel. |
| P0 | Exécuter le benchmark Image en réel, puis ajouter une grille de contenu : sujet, nombre d’objets, relations spatiales, couleurs, identité, texte et retouches. `image_module_engine.py:453` ne fournit encore qu’un statut de mesures. | Conserver prompt, seed, workflow, sortie et verdict séparé pour chaque critère. Comparer les mêmes cas avant/après, pas seulement netteté et contraste. |
| P0 | Partager un contrôle de livraison entre le pipeline 3D principal et les wrappers Hunyuan/TRELLIS. Le gate du cycle 1 est dans `aurora_loop_robust.py:92` ; le wrapper TRELLIS publie aussi un résultat via `aurora_trellis_wrapper.py:529`. | Un GLB vide/corrompu, une géométrie rejetée ou une critique indisponible ne produit jamais un statut validé. Tester chaque point de livraison réellement utilisé. |
| P1 | Évaluer la fidélité 3D sur plusieurs vues et les déformations après rigging. Géométrie fermée et sujet correct sont deux critères différents. | Captures de face/profil/dos, comparaison à la référence, axes/échelle/matériaux vérifiés ; animations avec intersections et volumes mesurés. |
| P1 | Valider les explications avec le modèle configuré, un croquis réel et l’interface complète. Ajouter la validation factuelle et mesurer l’efficacité de la réparation JSON bornée déjà implémentée. | Corpus d’explications, relations orientées correctes, libellés exacts, absence d’éléments inventés ; échec explicite après tentative bornée. |
| P1 | Étendre les sorties vectorielles spécialisées : circuits, coupes, plans et graphiques de données. Le mode ajouté représente des relations par boîtes et flèches ; il n’est pas un moteur de CAO. | Primitives et conventions adaptées au domaine ; mesures et axes conservés ; corpus de graphes denses pour intersections et lisibilité. |
| P1 | Exposer le même contrat de job/artefact à la CLI et conserver durablement l’étape d’édition, le `prompt_id`, le seed et l’état. | Rechargement, déconnexion et redémarrage sans relancer une génération déjà acceptée ; une édition à étapes reprend à la bonne étape. |
| P1 | Centraliser la file GPU entre vision, FLUX et 3D. Mesurer avant de modifier les profils, notamment les 50 steps de `human_prompt_director.py:89` et suivants. | Comparaison à seed/résolution constants des steps, médiane/p95 à froid et à chaud, pic VRAM, erreurs OOM et score de fidélité. Réduire les steps uniquement si le compromis est mesuré. |
| P1 | Revoir les déchargements systématiques et conserver les modèles utiles entre tâches compatibles. | Mesurer séparément chargement, attente de file, inférence, décodage et transfert ; publier le gain et la consommation résidente. |
| P0 transverse | Terminer le transport avec manifeste SHA-256, reprise HTTP Range et écriture atomique ; appliquer les protections API hors CLI identifiées au cycle 1. | Coupures injectées pendant transfert de gros assets : checksum identique, zéro fichier partiel présenté comme complet. |

Les restrictions techniques restent explicites : budget mémoire, limites du graphe, délais et validations. Aucune levée générale des restrictions des modèles ou garantie de contenu « sans restriction » n’est démontrée par ces changements.

## 5. Prochaine itération et commandes

Cible suivante : le suivi Python `application/python-services/image_module_engine.py:265`, puis un premier corpus réel commun aux parcours Image et 3D. Le benchmark actuel rend cette mesure possible ; il ne constitue pas déjà une preuve de cohérence.

Depuis `/home/juan/AuroraIA` :

```bash
npm --prefix application run check
application/.venv/bin/python -m unittest tests_agi.test_image_benchmark_contract tests_agi.test_hunyuan_hardware tests_agi.test_hunyuan_quality_gate -v
node --experimental-strip-types application/scripts/verify-explanation.mjs /tmp/aurora-svg-check
application/.venv/bin/python application/python-services/run_deep_image_benchmark.py --simulate --output-dir /tmp/aurora-image-packaging
# Lance réellement ComfyUI et consomme le GPU :
application/.venv/bin/python application/python-services/run_deep_image_benchmark.py --real --limit 1 --seed 42 --output-dir /tmp/aurora-image-real
```

Les archives de preuve et la compilation sont disponibles localement. Le build seul ne prouve pas que le serveur actif serve déjà cette version. Aucun objectif d’AGI n’est considéré atteint.
