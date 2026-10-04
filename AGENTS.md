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

Le maître est la source documentaire. Le code et les résultats observés restent l'autorité pour le comportement réel.
