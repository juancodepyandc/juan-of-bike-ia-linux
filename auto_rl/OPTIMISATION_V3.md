# Profil radical v3

Le profil `radical-v3` est le profil par défaut du contrôleur. Il garde la base
officielle intacte, entraîne un candidat dans une branche de lignée, puis ne
publie ce candidat qu'après comparaison avec la base, le champion et le parent.

Chaque cycle suit la même frontière de données : les sujets `train` produisent
des préférences mesurées sur le PC, les sujets `audit` sont réservés jusqu'au
retour de Kaggle. Les préférences fiables sont réparties dans plusieurs paires
de validation, au lieu de prendre uniquement la dernière famille réussie.
Les erreurs de génération deviennent des cas négatifs rejouables ; aucune
référence d'audit ne passe dans l'apprentissage.

Les recettes sont spécialisées :

- 3D : DPO sur latents de flow matching, replay de maillages difficiles,
  score multi-vues, topologie, intersections et alignement de style ;
- image : recherche active dans le sous-espace de poids à partir de mesures
  FLUX locales, avec scores d'alignement, esthétique et artefacts ;
- vidéo : recherche active avec continuité optique, erreur de warp, mouvement
  et cohérence image par image ;
- animation : recherche bornée avec action, longueurs d'os, jerk, contacts et
  pénétration du sol ;
- voix : WER, saturation, niveau et dynamique sur des phrases phonétiques ;
- code, conversation, cyber, cowork et apprentissage : DPO à références
  vérifiées, exécution isolée et suites de cas adversariaux.

Les briefs visuels et temporels couvrent désormais le photoréalisme, le
cartoon cel-shaded, l'anime, le low-poly, la pâte à modeler et la bande
dessinée. Chaque style possède son groupe d'audit et ne peut pas masquer une
régression dans un autre style.

Un arrêt contrôlé transmet le signal même pendant l'audit local après Kaggle,
attend la frontière de sauvegarde, puis supprime seulement les marqueurs
`.pending`, `.tmp`, `.part` et `stop_signal`. Les poids, métriques, rapports,
prévisualisations et journaux restent conservés.
