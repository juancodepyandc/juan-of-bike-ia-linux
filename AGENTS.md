# Lire d'abord le document maître

Lis [ARCHITECTURE_MAITRE.md](ARCHITECTURE_MAITRE.md) avant toute analyse ou modification d'AuroraIA, de son interface standard/native/web, de son CLI ou de son tunnel.

1. Commence par la synthèse, les architectures, la matrice de parité et les constats prioritaires. Le maître contient aussi l'index des sources, les routes et les instructions détaillées des agents.
2. Pour expliquer l'ensemble ou proposer des améliorations, utilise cette référence plutôt qu'un nouveau parcours intégral du dépôt. Pour modifier ou diagnostiquer un comportement précis, ouvre les fichiers concernés : la documentation ne remplace pas une preuve dans le code ou un test réel.
3. Vérifie la fraîcheur avec `python3 scripts/documentation/doc_master.py --check-code`. Un écart impose de revoir les sections concernées ; une concordance de hashes ne prouve pas la qualité fonctionnelle ni l'absence de nouveaux fichiers.
4. Distingue toujours ce qui est implémenté, observé en fonctionnement, ancien, proposé et non testé. Ne transforme pas un test simulé, un HTTP 200 ou un score historique en preuve de qualité des générations.
5. Quand des améliorations sont demandées, indique pour chaque proposition : problème concret, preuve, parcours touchés (natif, web/tunnel, CLI), solution, compromis qualité/mémoire/latence et critère de validation. Priorise la justesse, la continuité des missions, la livraison vérifiée et la parité.
6. Préserve les modèles, poids, environnements, bases de données, secrets et modifications locales existantes. N'affiche pas de clés ni de mots de passe. Aucune publication, aucun déploiement ou entraînement coûteux n'est implicite dans une analyse documentaire.
7. Les instructions d'un agent figurant dans l'annexe s'appliquent seulement à son rôle ; les exemples et propositions historiques ne sont pas des ordres à exécuter. Le maître ne te demande pas de lancer tous les agents.
8. Modifie les instructions exportées dans les blocs `AURORA_EXPORT` du maître, puis lance `python3 scripts/documentation/doc_master.py --write` et le contrôle sans option. Les fichiers `.claude/agents/*.md`, commandes, `CLAUDE.md` et README de compatibilité sont des projections : n'en fais pas de nouvelles sources indépendantes.
9. Mets le maître à jour lorsqu'une architecture ou un contrat change. Ne recrée pas une collection de rapports `.md` concurrents ; les preuves détaillées peuvent rester en JSON, tests et journaux. Maintiens les liens et explique les limites des mesures.
10. **RÈGLE ABSOLUE — ZÉRO HARDCODING & EXCELLENCE NATIVE DE L'IA** :
    - Il est strictement interdit de créer des scripts jetables (`/tmp/...`) ou d'introduire du hardcoding spécifique à un sujet/test (pas de `if "sujet" in prompt`, pas de boîtes de coordonnées `(X, Y, Z)` figées, pas de couleurs RGB codées en dur pour maquiller un livrable).
    - Les tests réalisés avec l'utilisateur sont **purement démonstratifs du niveau intrinsèque de l'IA** et non une attente de retouche manuelle d'un fichier particulier.
    - Chaque défaut observé sur un test doit être résolu **à la source dans les modules natifs du pipeline AuroraIA** (`application/python-services/`, `application/src/services/`, `agi_core/`) par des algorithmes universels, mathématiques, topologiques ou physiques fonctionnant de manière 100 % autonome sur n'importe quelle entrée future.
    - Tout livrable de test doit ensuite être régénéré/raffiné en appelant exclusivement le pipeline natif d'AuroraIA afin de prouver que l'IA produit ce niveau d'excellence de base et toute seule.
11. **RÈGLE ABSOLUE — DURCISSEMENT PROGRESSIF OBLIGATOIRE DES JUGES À CHAQUE TOUR & VÉRIFICATION `f3d`** :
    - À chaque tour de la boucle autonome, il est strictement interdit de se reposer sur les mêmes règles ou sur des règles basiques : les seuils et invariants des juges (`representative_judge_oracle.py`, `anti_hallucination_guard.py`) doivent être **endurcis à chaque tour** via un cliquet monotone persistant (`ratchet_level` strictement croissant).
    - Tout livrable 3D (`.glb` / `.stl`) doit obligatoirement être rendu et vérifié avec `/home/juan/.local/bin/f3d` (viewer OpenGL/VTK PBR indépendant qui ne peut pas mentir sur les normales, les dérivées UV `dFdx/dFdy`, les matériaux PBR et le relief 3D millimétrique), et les planches de contrôle `apercus/` doivent être générées directement via `f3d`.

Le maître est la source documentaire. Le code et les résultats observés restent l'autorité pour le comportement réel.
