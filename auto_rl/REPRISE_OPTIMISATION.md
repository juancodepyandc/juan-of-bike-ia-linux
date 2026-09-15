# Aurora — point de reprise du 14 septembre 2026

## Objectif et état réel

Utiliser exclusivement Kaggle pour améliorer les dix modules : 3D, image,
voix, code, conversation, cyber, cowork, vidéo, animation et apprentissage.
Conserver le modèle officiel intact, repartir du meilleur parent compatible,
et ne promouvoir une version que si un audit indépendant démontre son gain.
Afficher séparément le gain contre l'original et celui contre le parent.

Le dernier candidat 3D connu reste refusé (environ −0,100 point contre
l'original) ; aucun poids officiel n'a été remplacé. Le profil `radical-v2`
est le choix par défaut de la page et du CLI, avec T4×2, essais locaux bornés,
puis utilisation de toute la durée Kaggle choisie. Le profil `standard` reste
disponible explicitement pour un essai court.

## Déjà disponible avant ce chantier

- Page locale : http://127.0.0.1:3001/api/training/ui
- Sélection des dix modules, temps écoulé, cycles continus, changement au
  prochain cycle et arrêt propre après sauvegarde et audit du cycle courant.
- Choix du modèle officiel ou d'une version validée ; aucun candidat refusé
  n'est automatiquement mis en production dans Aurora.
- Contrôle CLI : `application/.venv/bin/python -m auto_rl.control status`.

## Nouveau code enregistré, à valider

- `lineage.py` : contrôle des empreintes, copie exacte du parent, filiation,
  priorité au champion validé puis sélection expérimentale parmi les candidats
  comparables. Le classement par perte utilise un même contrat de validation.
  Un repli sur les anciens audits est explicitement expérimental et impose un
  nouvel audit ; il ne transforme pas le candidat en champion.
- `strategy.py`, `challenge_curriculum.py`, les générateurs de curriculum :
  profil radical avec cas plus détaillés, 24 cas d'audit, quatre graines,
  familles séparées et aucune régression tolérée sur les mesures contrôlées.
  Les 24 cas représentent huit familles avec trois variantes, pas 24 familles
  indépendantes. Ils ne prouvent pas une absence de régression universelle.
- `evaluation.py` : comparaisons original, parent et champion ; intervalles
  de confiance, contrôles par cas et certaines métriques de qualité ; rapport
  HTML avec résultats parent et lecture vidéo.
- `lora.py`, `preference_train.py`, `autonomous_train.py` : référence parent
  figée, cache des probabilités de référence, terme supervisé et conservation
  de la référence entre tentatives. Leur comportement GPU reste à vérifier.
- `parallel_preferences.py`, `cloud_worker.py` : deux essais prédéfinis sur
  les GPU Kaggle disponibles, sélection sur validation avant audit final,
  export et vérification des empreintes. Le budget choisi est consommé
  jusqu'à sa limite, avec marge d'export.
- `runner.py`, `surrogate.py` : propositions déterministes et chargement des
  poids complets pour comparer parent, champion et candidat.
- `media.py`, `serve.py`, `integration.py`, `versions.py` et `previews.py` :
  aperçus des dix modules, dépôt d'une référence image pour la 3D, liste des
  parents, accès aux rapports et champs de gains original/parent. La page
  montre les fichiers déjà produits pendant le cycle, y compris maillages et
  squelettes animés.

## Vérifications et limites

Les 43 tests Python passent et le test navigateur passe. Journal :
`Outputs/auto_rl/radical-tests.log`. Ce sont des tests de non-régression du
socle ; ils ne valident pas tous les nouveaux chemins ni un entraînement GPU.
Les contrôles navigateur et le test d'inférence du chantier précédent avaient
réussi ; ils ne couvrent pas la future interface des nouveaux aperçus.

Le problème CUDA de l'animation a ensuite été reproduit puis corrigé. HY-Motion
ne construit plus Qwen en 4 bits sur le GPU avant le déplacement du DiT : le
texte est chargé en RAM CPU à pleine précision et seules les représentations
compactes sont transférées sur la carte. Le service `aurora-trained-models`
est suspendu automatiquement pendant un cycle local afin de libérer sa mémoire
CUDA, puis redémarré après le cycle. Un test réel de génération de 0,7 seconde
sur la RTX 5070 Ti a réussi sans OOM et a produit un NPZ.

Le profil `radical-v2` demande l'accélérateur Kaggle `gpu_t4_x2`, lance les
essais parallèles quand deux GPU sont exposés et utilise le budget sélectionné
jusqu'à la limite de la session. La présence de deux GPU et la durée réellement
accordée restent à vérifier lors du prochain lancement Kaggle.

Le bridge accepte maintenant la stratégie envoyée par la page après son
redémarrage. Les sorties d'apprentissage invalides ou sous le seuil sont
conservées par module dans `Outputs/auto_rl/failure_memory/`, puis rejouées
comme cas prioritaires au cycle suivant. Les sujets d'audit restent exclus de
cette mémoire. Les arrêts et changements de module propagent également un
signal durable au processus enfant afin de libérer le GPU après une demande
d'arrêt.

L'image, la vidéo et l'animation utilisent encore une optimisation de petits
coefficients avec un modèle de score intermédiaire. Ce n'est pas encore un
entraînement complet par gradient des générateurs. En 3D, seule une partie du
modèle reçoit l'adaptateur. Une puissance GPU supérieure ne garantit donc pas
à elle seule une amélioration radicale. Il faut des données pertinentes, des
objectifs adaptés, des gradients vérifiés et des évaluateurs fiables.

## À faire ensuite, dans cet ordre

1. Ajouter des tests ciblés : sélection et intégrité du parent, incompatibilité
   de contrats, référence figée, terme supervisé, audit strict par cas et
   métrique, export des essais parallèles et sécurité des fichiers d'aperçu.
   Vérifier l'oracle des intervalles pondérés par comparaison exhaustive sur
   de petits exemples ; son calcul sur les grands exemples a été remplacé
   par une programmation dynamique pour éviter une explosion exponentielle.
2. Faire un essai Kaggle court sur T4 ×2 avec les données existantes ; vérifier
   les deux GPU, les pertes finies, l'effet réel des gradients, l'arrêt,
   l'export et le choix indépendant du jeu d'audit. Respecter le verrou unique
   du notebook privé existant. Aucun autre fournisseur GPU n'est autorisé.
3. Dimensionner les générations et audits multimédias : le coût local peut
   dépasser largement le budget d'entraînement Kaggle. Un cycle vidéo complet
   du nouveau profil peut prendre des heures. Mesurer avant lancement long.
4. Lancer une comparaison fraîche original/parent/candidat. Promouvoir
   uniquement si tous les critères passent ; publier les gains mesurés et les
   refus réels, sans abaisser les seuils pour obtenir une promotion.
5. Pour une amélioration plus profonde des générateurs, développer leurs
   objectifs d'entraînement natifs, données et adaptateurs compatibles avec
   la VRAM Kaggle, puis les valider module par module. Cette partie reste à
   implémenter ; le profil radical actuel ne la remplace pas.

Le mode continu relance des cycles jusqu'à la demande d'arrêt et reste soumis
aux quotas Kaggle. Dernière lecture connue : environ 24,24 heures GPU restantes,
à recontrôler avant lancement. Ne pas lancer un entraînement long seulement
pour vérifier que l'interface s'affiche.

## Recherche retenue

- [Article DPO](https://arxiv.org/abs/2305.18290) et
  [documentation officielle TRL](https://huggingface.co/docs/trl/dpo_trainer) :
  objectifs de préférence, référence et combinaison avec supervision.
- [Étude sur la suroptimisation en DPO](https://arxiv.org/abs/2406.02900) :
  une hausse du score d'entraînement ne suffit pas à démontrer une meilleure
  qualité ; conserver un audit indépendant et des critères de régression.
- [Diffusion-DPO](https://arxiv.org/abs/2311.12908) : piste pour des objectifs
  natifs de générateurs de diffusion, à adapter et tester, pas une validation
  de l'optimisation actuelle par petits coefficients.
- [Annonce officielle Kaggle T4 ×2](https://www.kaggle.com/product-feedback/361104)
  et [utilisation GPU Kaggle](https://www.kaggle.com/docs/efficient-gpu-usage) :
  exploiter les ressources réellement disponibles dans les quotas du compte.

## Précautions de reprise du dépôt

Racine : `/home/juan/AuroraIA`. Le dépôt contient beaucoup de changements
préexistants ; `auto_rl/` est encore non suivi par Git. Les fichiers sont
enregistrés sur disque, sans commit global. Ne pas réinitialiser le dépôt et
ne pas inclure les identifiants Kaggle dans des journaux ou sauvegardes publiques.
