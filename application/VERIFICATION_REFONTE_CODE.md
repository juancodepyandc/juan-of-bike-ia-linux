# Rapport de vérification consolidé — Refonte Module Code AuroraIA

## Verdict global : SOLIDE AVEC RÉSERVES
**Niveau de confiance : MOYEN** (synthèse de 20 rapports adversariaux + re-vérification directe des 5 allégations structurantes par grep/inspection ; les preuves d'exécution runtime — artefacts WS12, isolation podman — n'ont pas été re-jouées).

La refonte est un travail d'ampleur réelle et globalement honnête : la baseline passe de 391 à **707 tests verts (0 échec)**, les monolithes sont authentiquement démantelés, le code mort inventorié est physiquement supprimé, et cinq chantiers (WS1, WS4, WS12, WS13, WS15) sont **conformes ET câblés de bout en bout**, WS12 étant même exemplaire (preuves binaires vérifiables). Ce **n'est pas** un mirage de stubs cosmétiques.

**Mais** un motif récurrent contamine la moitié des chantiers : des **livrables phares sont implémentés, testés en vase clos, puis laissés ORPHELINS** — jamais appelés hors de leurs propres tests. C'est précisément l'anti-pattern `aurora_code_loop.py` que la mission devait éradiquer, et il ressurgit sous une forme plus insidieuse : la couverture de tests verts entretient une **illusion de complétude** alors que la fonctionnalité est inerte dans le pipeline réel.

---

## Tableau récapitulatif par chantier

| Chantier | Verdict | Câblé | Synthèse |
|---|---|---|---|
| vague0-quickwins | Partiel | Oui | Dégradations actives supprimées (Unsplash→SVG, plagiat, launcher Linux) réelles ; télémétrie anti-null non livrée. |
| WS1 | **Conforme** | Oui | Monolithes découpés <400 l., code mort supprimé du disque, verrouillé par test-garde. |
| WS2 | Partiel | Partiel | Protocole longueur-déclarée réel ; writer disque ORPHELIN + issues ignorées → drop silencieux. |
| WS3 | Partiel | Partiel | Moteur agentique TS vivant/exclusif ; moteur bridge NDJSON MORT par défaut ; preuve LLM stubbée. |
| WS4 | **Conforme** | Oui | Routage par rôle réel, plan JSON bloquant, vérifieur distinct prouvé ; qwen3:32b absent (fallback). |
| WS5 | Partiel | Partiel | Index+RAG+apply_patch réels ; contexte-patch ORPHELIN + garde non-régression test-only. |
| WS6 | Partiel | Partiel | Taxonomie/routage mot-clé réels ; classifieur LLM + registre générateurs MORTS. |
| WS7 | Partiel | Partiel | Orchestration Podman réelle et fail-closed ; acceptation = regex statique ; jamais exécuté (podman absent). |
| WS8 | Partiel | Partiel | 3 bugs corrigés (scanner lexical) ; tree-sitter WASM ORPHELIN. |
| WS9 | Partiel | Partiel | Vrai juge rendu pixel+vision ; render-APRÈS-livraison, hors boucle ; static_web non audité. |
| WS10 | Partiel | Partiel | Brand-check deltaE réel+câblé ; design-spec (contrat+émission) = CODE MORT. |
| WS11 | Partiel | Oui | Atelier + esbuild-wasm + CodeMirror6 réels ; bridge runtime iframe inerte ; UIs non unifiées. |
| WS12 | **Conforme** | Oui | Labo multi-appareils authentique (APK/AVD, Renode, QEMU, Playwright) — preuves binaires. |
| WS13 | **Conforme** | Oui | Harnais anti-régression réel et câblé ; escalade reste indexée sur compteur. |
| WS14 | Partiel | Oui | Noyau A/B en venv isolé prouvé ; portée étroite (slugify), ReAct déclaratif, pas de sandbox WS7. |
| WS15 | **Conforme** | Oui | Assets réels (avif/webp, GLB 10Mo, WAV, RAG ollama) ; régénération 3D in-flow non prouvée. |
| CC — fichiers partagés | Partiel | n/a | TS/CSS/save additifs et sûrs ; dépassement bridge voice/web hors périmètre. |
| CC — câblage e2e | Partiel | Partiel | Moteur WS3 TS actif, WS7 en boucle ; 2 moteurs divergents, WS9 hors boucle. |
| CC — qualité tests | **Conforme** | n/a | Tests significatifs, 0 tautologie ; isolation testée au niveau args, proofs stubent le LLM. |
| CC — contraintes | **Conforme** | n/a | Viewer 3D intact, licences permissives, 0 secret, pas de pollution racine. |

**Bilan : 5 conformes · 13 partiels · 0 non-conforme franc · 2 contrôles conformes.** Aucun chantier n'est un pur théâtre, mais 13 sur 20 restent inachevés faute de câblage ou de profondeur.

---

## Forces réelles (vérifiées)

1. **WS12 — le sommet du lot.** Preuves d'exécution non falsifiables sur cet hôte : APK signé de 12 Ko installé sur un AVD Android réel qui boote en ~40 s, firmware Rust bare-metal exécuté sous Renode et QEMU avec marqueurs mémoire/UART, 3 moteurs Playwright réels (Chromium/Firefox/WebKit), throttling CPU/réseau injecté via CDP. Ce sont des artefacts binaires, pas du JSON fabriqué.
2. **WS1 — la dette de fond authentiquement traitée.** Monolithes découpés en modules à responsabilité unique <400 l., code mort SUPPRIMÉ du disque (`git diff --diff-filter=D`), `selectModel` NO-OP remplacé par un vrai routeur, absence d'imports résiduels verrouillée par un test-garde structurel.
3. **WS4 — routage réel et bloquant.** Le plan d'architecture JSON invalide BLOQUE la génération (double garde `throw`), et le vérifieur distinct du coder est prouvé empiriquement sur les 6 modèles réellement installés.
4. **WS13 — garde anti-régression câblée.** Snapshot comportemental (exports/endpoints/scripts) + rollback réel branché aux 3 seuls points d'adoption de fichiers ; suppression effective des stratégies dégradantes vérifiée dans le diff.
5. **WS15 — vrais assets inter-modules.** avif/webp+srcset, GLB de 10 Mo à magic `glTF` valide, WAV RIFF, RAG avec embeddings ollama réels, sur disque.
6. **Qualité de tests saine** (CC) : 0 tautologie sur 70 fichiers, `apply_patch` et parsing NDJSON fragmenté réellement exercés.
7. **Contraintes dures respectées** : Viewer 3D totalement intact, licences permissives, aucun secret, pas de pollution racine.

---

## Failles critiques (classées par gravité)

### Gravité HAUTE
- **WS10 — cœur mort.** `verifyCodeDesignSpecAgainstFiles` et `buildDesignDirectives`/l'émission de la design-spec sont ORPHELINS (**confirmé par grep : seules les définitions, 0 appelant de production**). Le « contrat design vérifié » n'existe pas dans le pipeline réel ; le contrat CSS web reste appliqué au mobile/jeu. Seul le brand-check deltaE est un vrai progrès câblé.
- **WS6 — livrables phares morts.** `classifyCodeIntentWithSemanticModel` (classifieur LLM structuré, cœur du DoD) et le registre `ProjectGenerator` n'ont **aucun appelant réel** (confirmé grep). La génération tourne toujours sur le classifieur regex. La « preuve compilateur » stubbe la génération et n'a pas la métrique fraction-critères exigée.
- **CC — dépassement de périmètre bridge.** Confirmé en direct (`bridge_server.py:282/2372/2494`) : `voice_tts`, `web_search`, `web_extract` — endpoints PARTAGÉS par voix/cowork/learning — sont rebranchés **inconditionnellement** sur le venv du module Code, avec timeouts portés de 30 s à 180 s. Cold-start jusqu'à 120 s et panne possible si le venv échoue. Le mandat autorisait à AJOUTER des `/api/code/*`, pas à dégrader les autres modules.

### Gravité MOYENNE
- **WS7 — validation gameable.** Les « tests d'acceptation » sont une checklist REGEX statique fixe (aucune exécution). Une calculatrice au calcul FAUX passe 100 % ; le livrable web pur court-circuite le conteneur et n'est jugé qu'en regex. De plus, rien n'a tourné en réel (podman absent de l'hôte).
- **WS3 / CC — moteur bridge dormant.** La route `/api/code/generate/stream` + `bridge_agentic_stream.py` (394 l.) sont MORTS PAR DÉFAUT (`VITE_CODE_STREAM_ENGINE` jamais défini, **confirmé grep**). Deux moteurs WS3 divergent ; le bridge n'a NI WS7 NI WS9 NI WS13.
- **WS9 — juge hors boucle.** Vrai juge rendu (Chrome headless + contraste pixel + vision) mais **render-APRÈS-livraison** : n'alimente ni la correction ni `finalScore`. Le DoD « page laide corrigée » n'est pas tenu ; `static_web` n'est jamais audité.
- **WS2 — writer orphelin + drop silencieux.** Le writer disque Tauri n'a aucun appelant hors test ; `parseCodeFiles` ignore `parsed.issues` → un fichier au header valide mais longueur déclarée fausse est droppé **sans erreur remontée**.
- **WS8 — tree-sitter orphelin.** Cible explicite du DoD, jamais appelée hors tests ; l'analyse réelle reste regex/lexicale.
- **WS5 — garde non-régression inerte.** `assertCodePatchNonRegression` jamais branchée au runtime (test-only) ; `codeExistingProjectContext` orphelin après suppression de `runGenerationPhase`.

### Gravité BASSE
- **WS14** : portée réelle limitée à `python-slugify`, boucle ReAct déclarative (`run_shell`/`add_model` non implémentés), pas d'isolation WS7, pas de quotas.
- **vague0** : « télémétrie anti-null » annoncée, jamais implémentée.

---

## Risques d'échec silencieux

- **WS2** : si le LLM compte mal la longueur (UTF-16 vs octets/emoji), le fichier est droppé sans alerte — `parsed.issues` ignoré par les 2 parsers actifs. Écho direct de l'historique « échecs silencieux » du module.
- **WS7** : livrable web bogué déclaré « vert » (bypass conteneur + regex) ; calculatrice fausse notée 100 %.
- **WS9** : Chrome/Playwright ou modèle vision absent → audit `ok:false` avalé comme « indisponible », aucune garde visuelle.
- **CC bridge** : `~/.local/share/auroraia` non inscriptible ou `venv` en échec → `voice_tts`/`web_*` LÈVENT là où ils fonctionnaient → panne voix/cowork/learning **déclenchée par un changement du module Code**.
- **WS15** : `allow_existing=True` réutilise silencieusement un ancien GLB si le pipeline échoue → asset 3D « intégré » potentiellement hors-sujet.
- **WS13** : extraction par regex (pas AST) → un patch retirant une capacité via export dynamique/re-export échappe au guard.

---

## Conformité aux contraintes dures

| Contrainte | État | Détail |
|---|---|---|
| Viewer 3D intact | ✅ | Aucun fichier du pipeline 3D touché (seul match '3d' = `codeInteractive3DGate.ts`, nouveau, interne Code). |
| Aucune install .venv | ✅ (non prouvable) | Code Code = stdlib + PIL déjà présent ; `.venv` git-ignoré donc non prouvable formellement, mais aucune install nécessaire. |
| Licences permissives | ✅ | MIT/Apache-2.0/Unlicense ; bumps deps partagées (react-router-dom, vite, postcss) semver-compatibles mais non re-testés. |
| Aucun secret committé | ✅ | Seules occurrences = fixtures de test, durcissement, template démo ; la branche ajoute même une gate de scan. |
| Pas de pollution racine | ✅ | Aucun artefact/log committé à la racine. |
| **Autres modules non dégradés** | ⚠️ **NON** | `voice_tts`/`web_search`/`web_extract` rebranchés inconditionnellement sur le venv Code + timeouts x6 → risque réel voix/cowork/learning. |

**La seule non-conformité n'est pas du code factice mais un dépassement de périmètre réel** sur les endpoints partagés.

---

## Actions recommandées pour la prochaine session

**Priorité 1 (câblage & régressions)**
1. **Câbler ou supprimer les orphelins phares.** WS10 : brancher `verifyCodeDesignSpecAgainstFiles` comme gate réel + injecter la design-spec dans le prompt effectivement envoyé. WS6 : appeler `classifyCodeIntentWithSemanticModel` dans le chemin actif + injecter le registre `ProjectGenerator`. WS8 : brancher `parseCodeWithTreeSitter` ou retirer. WS2 : appeler le writer depuis l'UI/export ou le retirer.
2. **Corriger le dépassement bridge** : conditionner `_code_inter_module_runtime()` aux seuls appels du module Code (garde d'en-tête), restaurer les timeouts d'origine, ou créer des routes `/api/code/*` dédiées sans toucher les endpoints partagés.
3. **Fermer les pertes silencieuses WS2** : remonter `parsed.issues` à l'utilisateur ; fallback de parsing quand la longueur est incohérente.

**Priorité 2 (non-gameabilité & boucle)**
4. **WS7** : remplacer la checklist regex par une vraie génération+exécution de tests dans le conteneur ; couvrir le web pur (headless) ; ajouter un cas « calc fausse » qui doit échouer.
5. **WS9** : réinjecter le score visuel dans `finalScore` et déclencher une re-génération sous seuil ; étendre l'audit à `static_web`.
6. **WS3** : trancher la dualité — un seul moteur maintenu, ou suppression du bridge NDJSON dormant.

**Priorité 3 (DoD résiduels & preuves)**
7. Brancher `assertCodePatchNonRegression` au runtime (rollback réel) ; supprimer `codeExistingProjectContext`.
8. Livrer : télémétrie anti-null (vague0), métrique fraction-critères (WS6), preuve de régénération 3D in-flow (WS15).
9. Installer podman sur un runner et prouver l'isolation WS7 par un test confinant réellement une fork-bomb.

**Transverse**
10. Ajouter un **test-garde anti-orphelin généralisé** (sur le modèle de `codeModuleStructure`) qui échoue si un service listé comme livrable n'a aucun appelant de production — pour empêcher structurellement la récidive du pattern `aurora_code_loop.py`.

---

*Note de méthode : les cinq allégations les plus lourdes (orphelins WS10/WS6/WS2, flag WS3, dépassement bridge voice/web) ont été re-vérifiées en direct par grep/inspection et sont CONFIRMÉES. Les preuves d'exécution runtime (artefacts WS12, isolation podman WS7) reposent sur les rapports fournis et n'ont pas été ré-exécutées, d'où un niveau de confiance MOYEN plutôt que HAUT.*