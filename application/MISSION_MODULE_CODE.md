# MISSION — Module Code d'AuroraIA (spécification canonique)

> Version propre, nette et complète de la demande initiale. C'est la **référence d'intention** : tout travail sur le Module Code doit s'y conformer. Elle dit *ce qui est voulu* (le quoi et le pourquoi) ; le *comment* (état du code, endpoints, chantiers) vit dans `PROMPT_REFONTE_MODULE_CODE.md`, `AUDIT_MODULE_CODE.md`, `VERIFICATION_REFONTE_CODE.md`.

---

## 0. Intention, en une phrase

Rendre le Module Code **puissant, intelligent, autonome, fiable, précis et qualitatif** — capable de **produire n'importe quel projet, proprement, à la qualité maximale techniquement réalisable, de façon autonome, et sans jamais mentir sur son résultat.**

**Principe absolu :** le **seul** critère de décision est la **qualité finale**. Jamais la rapidité, jamais la simplicité, jamais l'économie de ressources. Si une solution demande 10× plus de travail, de calcul, de mémoire ou d'étapes mais produit un résultat nettement supérieur, **c'est elle qu'on retient**.

---

## 1. Objectif de qualité (invariable)

Le module doit produire, **à qualité constante et sans jamais baisser quand le projet se complexifie** :
calculatrice · landing page · site vitrine · web-app complexe · SaaS · CRM · ERP · IDE · moteur graphique · moteur 3D · jeu · app mobile native · app desktop · compilateur · OS complet · système distribué · microcontrôleur (ESP32, Arduino…) · projets extrêmement volumineux.

La complexité croissante n'est **jamais** une excuse à une qualité moindre.

---

## 2. Périmètre

- **On modifie tout ce qui concerne le Module Code.**
- **On ne modifie aucun autre module.** On les **utilise comme services** (génération d'images, 3D, audio, vision, analyse, IA spécialisées). Si le Code a besoin d'une ressource qu'un autre module sait produire, il la **demande** — il ne la recrée pas. Coopération intelligente, sans casser la séparation des modules.

---

## 3. Règles absolues (inviolables)

1. **Aucune simplification.** On ne choisit jamais une solution parce qu'elle est plus rapide, plus simple, ou moins gourmande.
2. **Aucun échec silencieux.** Toute dégradation (fichier perdu, asset réutilisé/hors-sujet, gate contourné, modèle/service absent, qualité sous le seuil) est **remontée explicitement**, jamais avalée.
3. **Aucun code mort / capacité débranchée.** Toute capacité livrée est **réellement appelée en production** et protégée par un garde ; sinon on la câble ou on la retire. (C'est le défaut historique n°1 à ne jamais reproduire.)
4. **Aucune accumulation.** Ce qui est produit pour itérer puis devenu inutile est **supprimé proprement** (runs intermédiaires, outils/venvs d'essai rejetés). Le système reste propre. On ne touche jamais à ce qui appartient à un autre module.
5. **Sorties distinctes et organisées.** Les sorties du Code (assets image/3D/audio inclus) sont rangées dans l'espace du Code, séparément des sorties des autres modules — **jamais mélangées**, même quand on utilise ces modules.
6. **Qualité 3D maximale.** Toute génération 3D emprunte **systématiquement le chemin maximal** (multi-vues / TRELLIS, réglages hauts) ; se limiter à un chemin de moindre qualité (ex. mono-vue seul, ou Hunyuan3D sans multi-vues) **n'est pas une option par défaut** et doit être justifié et signalé. **Reprise intelligente** : noter le résultat, et tant qu'il ne convient pas (artefacts, score bas), reprendre / réparer / relancer **jusqu'à atteindre la qualité visée**. Un plafond d'itérations n'est qu'un **filet de sécurité anti-boucle-infinie**, jamais un critère de qualité ni une raison de livrer : s'il est atteint sans que le résultat soit parfait, **ce n'est pas un arrêt satisfait** — on conserve le meilleur candidat **et** on signale explicitement que la cible n'est pas atteinte (jamais livré en silence comme terminé).
7. **Vérification réelle avant "proxy".** Un score de qualité vient d'une **exécution / d'un rendu réel** dès que c'est techniquement possible, pas d'une simple présence de motifs.
8. **Ne jamais casser le Viewer 3D existant.** Ne jamais installer dans `application/.venv`. Licences permissives privilégiées.

---

## 4. Méthode obligatoire

1. **Analyse d'abord (avant toute modification).** Comprendre entièrement : architecture, fonctionnalités, dépendances, interactions inter-modules, et identifier **toutes** les limites — graphiques, fonctionnelles, d'architecture, de génération, UX/UI, des moteurs utilisés — ainsi que les **points faibles et fragilités**, les **goulets d'étranglement**, les composants obsolètes et les améliorations possibles. Aucune modification avant cette analyse.
2. **Recherche permanente.** Face à une limite, on ne dit **jamais** "impossible" sans recherche approfondie : documentation, publications, GitHub, bibliothèques récentes, frameworks, moteurs, modèles IA, **projets open source**, **outils expérimentaux** (y compris pré-release, prototypes de recherche, non stabilisés), benchmarks, comparatifs. **Aucune piste n'est écartée sous prétexte qu'elle est jeune, expérimentale ou peu répandue.** Si une meilleure solution existe, on l'utilise.
3. **Veille technologique continue.** Chercher régulièrement s'il existe un meilleur framework / lib / moteur (graphique, UI, rendu, simulation) / compilateur / architecture. Si mieux existe **et** améliore réellement le résultat, on remplace.
4. **Tests, puis validation, puis traçabilité** (voir §10, §11, §12).

---

## 5. Autonomie · auto-amélioration · auto-correction

**Auto-amélioration.** Le module doit pouvoir : détecter ses propres limites → rechercher automatiquement l'outil / la lib / le framework / le modèle / la compétence adaptés (y compris parmi les **projets open source** et les **outils expérimentaux / pré-release**) → télécharger, installer, intégrer, tester, **évaluer** → **conserver si réellement meilleur**, sinon **retirer proprement** (zéro accumulation, système propre). Les installs se font **isolées** (jamais dans `.venv`).

**Auto-correction permanente.** Le module doit détecter ses erreurs, incohérences, régressions, pertes de performance, problèmes graphiques et bugs, puis **proposer + appliquer** un correctif, **re-tester**, et **vérifier qu'aucune régression** n'a été introduite. Un correctif qui dégrade une fonctionnalité est interdit (rollback).

**Autonomie de bout en bout.** À partir d'un brief (court ou long), le module planifie → génère → exécute → teste → juge (fonctionnel **et** visuel) → corrige → et ne se déclare **terminé que lorsque la validation réelle passe** — en demandant leurs ressources aux autres modules, en s'auto-outillant si nécessaire, **sans intervention humaine** et **sans jamais surdéclarer sa réussite**.

---

## 6. Skills & MCP

- **Plan agent (l'IA qui travaille, via le harnais) :** exploite les skills `aurora-*` et les serveurs MCP (ex. audit 3D) pour analyser / générer / auditer / faire de la veille pendant le travail. Peut créer un skill **seulement s'il est réellement utilisé** (jamais orphelin).
- **Plan produit (le module à l'exécution) :** le pipeline **n'est pas** un client MCP et **n'invoque pas** les skills du harnais ; au runtime il joint les autres modules **uniquement par le pont HTTP**. Ne jamais confondre les deux plans.
- Toute capacité skill/MCP ajoutée est **câblée, testée, documentée**, sans dupliquer ce qu'un autre module fournit déjà.

---

## 7. Génération graphique / UX

Le niveau graphique doit être **nettement supérieur** : meilleures pratiques modernes, **recherche automatique des meilleures références UX/UI**, interfaces modernes, cohérentes, performantes, **accessibles** et visuellement professionnelles. La qualité visuelle est **mesurée sur un rendu réel** (screenshot + contraste WCAG mesuré sur pixels + jugement vision), pas sur la seule présence de code — et un rendu insuffisant déclenche une correction.

---

## 8. Viewer & environnement de simulation

- **Conserver** le viewer compact actuel. **Ne jamais casser** le Viewer 3D existant ; toute nouveauté s'y intègre proprement (panneau isolé).
- **Ajouter** un viewer complet : arborescence du projet, fichiers, logs, erreurs, performances, simulations, états internes.
- **Ajouter** un labo de simulation multi-appareils / multi-environnements **réel** (pas cosmétique) : PC · consoles (récentes et anciennes) · Raspberry (tous modèles) · microcontrôleurs (ESP32, Arduino…) · téléphone · tablette · tailles d'écran · navigateurs · OS · niveaux de performance · réseaux · comportements utilisateur. But : **détecter les problèmes avant toute utilisation réelle**. **Les simulations exécutent réellement le code dans l'environnement simulé** (mobile, microcontrôleurs, Raspberry, navigateurs… — partout où c'est techniquement réalisable) ; un simple habillage cosmétique (redimensionnement, changement de largeur) n'est **jamais** une simulation.

---

## 9. Coopération inter-modules (dont 3D)

- Le Code **demande** aux autres modules leurs ressources (image, 3D, audio, vision) au lieu de les recréer.
- **3D spécifiquement** : chemin qualité **maximale systématique** (multi-vues / TRELLIS + réglages hauts ; ne jamais se contenter par défaut d'un chemin de moindre qualité), **boucle de reprise intelligente** (score → réparation/rescue → relance → meilleur candidat) **jusqu'à la qualité visée** (le plafond d'itérations n'est qu'un filet anti-boucle-infinie : atteint sans perfection, on conserve le meilleur candidat **et on signale** que la cible n'est pas atteinte), **suppression des intermédiaires** une fois l'asset retenu, et **rangement dans les sorties du Code** (jamais de résidu dans l'arbre du module 3D, jamais de mélange). Si un défaut vient de la source (module 3D), on le **signale** (chantier séparé côté 3D) — on ne bricole pas le module 3D.
- Assets écrits en fichiers optimisés (image moderne + srcset ; GLB), jamais en base64 inline massif.

---

## 10. Tests obligatoires

Aucune génération n'est "terminée" sans validation. Couvrir, selon le projet : unitaires, intégration, end-to-end, fonctionnels, UI, UX, graphiques, rendu, responsive, multi-appareils, multi-résolutions, performance, mémoire, CPU, GPU, réseau, stabilité, robustesse, sécurité, régression, cohérence. **Rejouer les tests après chaque correction, sans exception.** Le score d'un projet généré est la **fraction de critères réellement verts** (non contournable).

---

## 11. Validation finale & honnêteté

À la fin de chaque tâche, se demander : **« Si j'étais l'ingénieur en chef chargé du meilleur Module Code possible, serais-je satisfait de livrer ça ? »** Si non, continuer. On ne s'arrête **jamais** parce que c'est "assez bon" — seulement quand on a atteint le meilleur niveau techniquement réalisable.

**Honnêteté de complétude (non négociable) :** on ne déclare "fini" que ce qu'on a **exécuté et observé**. Ce qui exige un environnement live (GPU en génération, vrai navigateur, émulateurs) et ne peut être prouvé sur-le-champ est **câblé au mieux** puis **documenté précisément** comme restant à valider en réel — jamais présenté comme "parfait" sans preuve.

**Cette clause ne réduit jamais l'exigence de perfection ; elle interdit seulement de mentir en attendant la preuve.** Un élément documenté « à valider en réel » **n'est jamais comptabilisé comme terminé** : il reste une tâche ouverte tracée, ne peut être présenté comme livrable final, et **doit être complété et prouvé dès que l'environnement live est disponible**. "À valider en réel" ≠ "bon avec lacunes accepté".

---

## 12. Langue & traçabilité

- Tous les livrables destinés à l'humain (réponses, journal, messages de commit, documentation) sont en **français** ; le code et les identifiants restent en anglais si c'est la convention du dépôt.
- **Documenter** à chaque étape importante : recherches effectuées, sources consultées, technologies évaluées, choix retenus et **raisons techniques** — pour que toutes les décisions soient traçables et justifiées.
